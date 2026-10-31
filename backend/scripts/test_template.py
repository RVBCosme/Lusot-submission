"""Tests for backend/template.yaml: MS4's routes, APIs, tables, CORS, throttles,
lifecycle, retentions, alarms and role grants (MS4 spec §4.3 to §4.7; plan Task 1),
and Ask Lusot's two routes, grants, switch and alarms (Ask plan Task 13).

They read the template through cfn_template.load_template, so nothing reaches AWS.
check:py runs this file with the scripts' dependencies. Alone, from the repo root:
    uv run --python 3.13 --with pytest --with boto3 --with httpx --with numpy
        --with "opencv-python-headless<5" --with pyyaml pytest -q
        backend/scripts/test_template.py
"""

import re

from cfn_template import TEMPLATE, load_template, raw_lines

T = load_template()
RES = T["Resources"]
ANALYSIS_SRC = TEMPLATE.parent / "analysis" / "src" / "lusot_analysis"
REPORT_STORE = ANALYSIS_SRC / "report_store.py"
SPEND = ANALYSIS_SRC / "spend.py"
API_ROUTER = TEMPLATE.parent / "api" / "src" / "index.ts"
API_LIMITS = TEMPLATE.parent / "api" / "src" / "limits.ts"
ASK_DEADLINE = TEMPLATE.parent / "api" / "src" / "ask" / "deadline.ts"
ASK_HANDLER = TEMPLATE.parent / "api" / "src" / "ask" / "handler.ts"
ASK_NOMINATIM = TEMPLATE.parent / "api" / "src" / "ask" / "nominatim.ts"
ALARM_TOPIC = [{"Ref": "AlarmTopic"}]
SSM_ARN = "arn:${AWS::Partition}:ssm:${AWS::Region}:${AWS::AccountId}:parameter"
# The website's resources (MS5 Task 19, C622) and the managed CloudFront policies they use.
WEB_RESOURCES = (
    "WebBucket",
    "WebOriginAccessControl",
    "WebDistribution",
    "WebBucketPolicy",
)
CACHING_OPTIMIZED = "658327ea-f89d-4fab-a63d-7e88639e58f6"
SECURITY_HEADERS = "67f7725c-6f97-4210-82d7-5512b31e9d03"
# A sample distribution domain, as CloudFormation's docs give it, to resolve the CORS lists with.
WEB_DOMAIN = "d111111abcdef8.cloudfront.net"


def resource(name):
    assert name in RES, f"{name} is missing from the template"
    return RES[name]


def props(name):
    return resource(name).get("Properties", {})


def of_type(kind):
    return {name: r for name, r in RES.items() if r["Type"] == kind}


def as_list(value):
    return value if isinstance(value, list) else [value]


def route_keys(api):
    """Each route on `api`: its functions' HttpApi events and its OpenAPI paths."""
    keys = set()
    for function in of_type("AWS::Serverless::Function").values():
        for event in function["Properties"].get("Events", {}).values():
            p = event.get("Properties", {})
            if event["Type"] == "HttpApi" and p.get("ApiId") == {"Ref": api}:
                keys.add(f"{p['Method'].upper()} {p['Path']}")
    paths = props(api).get("DefinitionBody", {}).get("paths", {})
    for path, methods in paths.items():
        keys.update(f"{method.upper()} {path}" for method in methods)
    return keys


def statements(role):
    return [
        statement
        for policy in props(role)["Policies"]
        for statement in policy["PolicyDocument"]["Statement"]
    ]


def resource_name(value):
    """`!Sub "${X.Arn}/a/*"` as "${X.Arn}/a/*", and `!GetAtt X.Arn` as "${X.Arn}"."""
    if isinstance(value, dict) and "Fn::Sub" in value:
        return value["Fn::Sub"]
    if isinstance(value, dict) and "Fn::GetAtt" in value:
        return "${" + ".".join(value["Fn::GetAtt"]) + "}"
    return value


def granted(role, action):
    """Every resource on which `role` is allowed `action`."""
    return {
        resource_name(r)
        for s in statements(role)
        if s["Effect"] == "Allow" and action in as_list(s["Action"])
        for r in as_list(s["Resource"])
    }


def bucket_paths(*prefixes):
    return {f"${{UploadBucket.Arn}}/{prefix}/*" for prefix in prefixes}


def resolve(value, params, attrs, conditions=None):
    """What CloudFormation makes of Ref, Fn::GetAtt, Fn::Join, Fn::Split, Fn::Sub and Fn::If
    in `value`, given parameter values, resource attributes and condition values: enough for
    the CORS lists and the Nominatim User-Agent."""
    conditions = conditions or {}
    if isinstance(value, list):
        return [resolve(item, params, attrs, conditions) for item in value]
    if not (isinstance(value, dict) and len(value) == 1):
        return value
    ((fn, arg),) = value.items()
    if fn == "Ref":
        return params[arg]
    if fn == "Fn::GetAtt":
        return attrs[tuple(arg)]
    if fn == "Fn::Join":
        return arg[0].join(resolve(arg[1], params, attrs, conditions))
    if fn == "Fn::Split":
        return resolve(arg[1], params, attrs, conditions).split(arg[0])
    if fn == "Fn::Sub":
        text, names = arg if isinstance(arg, list) else (arg, {})
        names = {k: resolve(v, params, attrs, conditions) for k, v in names.items()}

        def name(m):
            key = m.group(1)
            return names[key] if key in names else attrs[tuple(key.split(".", 1))]

        return re.sub(r"\$\{([^}]+)\}", name, text)
    if fn == "Fn::If":
        condition, on, off = arg
        return resolve(on if conditions[condition] else off, params, attrs, conditions)
    return value


def cors_origins(value, app_origins, web=True):
    return resolve(
        value,
        {"AppOrigins": app_origins},
        {("WebDistribution", "DomainName"): WEB_DOMAIN} if web else {},
        {"HasWeb": web},
    )


def unguarded(value):
    """The web resources `value` names outside the on branch of an Fn::If on HasWeb. With
    WebHosting off they don't exist, and CloudFormation refuses a template that names one."""
    found = set()
    if isinstance(value, list):
        for item in value:
            found |= unguarded(item)
    elif isinstance(value, dict):
        for key, arg in value.items():
            if key == "Fn::If" and arg[0] == "HasWeb":
                found |= unguarded(arg[2])
                continue
            if key == "Ref" and isinstance(arg, str):
                found.add(arg)
            elif key == "Fn::GetAtt":
                found.add(arg[0])
            elif key == "Fn::Sub":
                text = arg[0] if isinstance(arg, list) else arg
                found.update(re.findall(r"\$\{([A-Za-z0-9]+)", text))
            found |= unguarded(arg)
    return found & set(WEB_RESOURCES)


def references(value):
    """The template's resources that `value` names through Ref, Fn::GetAtt or Fn::Sub."""
    found = set()
    if isinstance(value, list):
        for item in value:
            found |= references(item)
    elif isinstance(value, dict):
        for key, arg in value.items():
            if key == "Ref" and isinstance(arg, str):
                found.add(arg)
            elif key == "Fn::GetAtt":
                found.add(arg[0])
            elif key == "Fn::Sub":
                text = arg[0] if isinstance(arg, list) else arg
                found.update(re.findall(r"\$\{([A-Za-z0-9]+)", text))
            found |= references(arg)
    return found & set(RES)


def test_routes():
    assert route_keys("HttpApi") == {
        "POST /uploads",
        "GET /reports/{id}",
        "GET /reports",
        "GET /map/pins",
        "POST /reports/{id}/flag",
        "GET /samples",
        "POST /samples/{sampleId}",
        "POST /ask",
        "POST /ask/voice",
    }
    assert route_keys("FeedApi") == {"GET /pins.geojson"}


def test_ask_routes():
    """Ask's two routes on HttpApi: AskTyped and AskVoice, POST only, and no other."""
    events = props("ApiFunction")["Events"]
    assert events.get("AskTyped") == {
        "Type": "HttpApi",
        "Properties": {"ApiId": {"Ref": "HttpApi"}, "Method": "POST", "Path": "/ask"},
    }
    assert events.get("AskVoice") == {
        "Type": "HttpApi",
        "Properties": {"ApiId": {"Ref": "HttpApi"}, "Method": "POST", "Path": "/ask/voice"},
    }
    deployed = route_keys("HttpApi") | route_keys("FeedApi")
    assert {key for key in deployed if "/ask" in key} == {"POST /ask", "POST /ask/voice"}


def test_routes_match_the_api_router():
    """Critical 2: each deployed route has a case in index.ts's route(), and each case a route."""
    source = API_ROUTER.read_text(encoding="utf-8")
    router = re.search(r"export async function route\(.*?\n}\n", source, re.DOTALL)
    assert router, "route() is missing from index.ts"
    cases = set(re.findall(r'^\s*case "([^"]+)":', router.group(0), re.MULTILINE))
    deployed = route_keys("HttpApi") | route_keys("FeedApi")
    assert len(deployed) == 10
    assert cases == deployed


def test_api_environment():
    env = props("ApiFunction")["Environment"]["Variables"]
    assert set(env) == {
        "TABLE_NAME",
        "INDEX_NAME",
        "BUCKET_NAME",
        "STOP_PARAM_PREFIX",
        "NODE_OPTIONS",
        "LIMITS_TABLE_NAME",
        "FEED_INDEX_NAME",
        "INCHES_SHOWN",
        "MODEL_KEY_PARAM",
        "NOMINATIM_USER_AGENT",
    }
    # Ask's two (C701), read only on its two routes. The key's name, never the key; the
    # analysis function reads the same parameter.
    assert env["MODEL_KEY_PARAM"] == "/lusot/meta/model-api-key"
    analysis = props("AnalysisFunction")["Environment"]["Variables"]
    assert env["MODEL_KEY_PARAM"] == analysis["MODEL_KEY_PARAM"]
    # Identifies the app to Nominatim (its usage policy) by name and, with the website on,
    # the site's address; never an email address.
    agent = env["NOMINATIM_USER_AGENT"]
    attrs = {("WebDistribution", "DomainName"): WEB_DOMAIN}
    assert resolve(agent, {}, attrs, {"HasWeb": True}) == f"Lusot/1.0 (+https://{WEB_DOMAIN})"
    assert resolve(agent, {}, {}, {"HasWeb": False}) == "Lusot/1.0"
    assert env["LIMITS_TABLE_NAME"] == {"Ref": "LimitsTable"}
    assert env["FEED_INDEX_NAME"] == "feed-index"
    # A literal string, never a parameter (C515): YAML's bare false would be a bool.
    assert env["INCHES_SHOWN"] == "false"
    assert isinstance(env["INCHES_SHOWN"], str)
    assert not [name for name in T["Parameters"] if "inches" in name.lower()]


def test_api_timeout_is_15():
    """C701: a backstop. Ask's own marks end a question, the last of them (the pause
    after a failed spend write, C736) inside the timeout."""
    timeout = props("ApiFunction")["Timeout"]
    assert timeout == 15
    source = ASK_DEADLINE.read_text(encoding="utf-8")
    pause_by = re.search(r"^\s*pauseBy:\s*(\d+),", source, re.MULTILINE)
    assert pause_by, "pauseBy not found in ask/deadline.ts"
    assert int(pause_by.group(1)) < timeout * 1000


def test_analysis_environment():
    """MS3a's four, MS3b's geometry setting (C309) and the limits table that holds the
    spend counter (C527)."""
    env = props("AnalysisFunction")["Environment"]["Variables"]
    assert set(env) == {
        "TABLE_NAME",
        "BUCKET_NAME",
        "STOP_PARAM_PREFIX",
        "MODEL_KEY_PARAM",
        "GEOMETRY_IN_LEVEL",
        "LIMITS_TABLE_NAME",
    }
    assert env["GEOMETRY_IN_LEVEL"] == "on"  # a quoted literal, never YAML's bare on
    assert env["LIMITS_TABLE_NAME"] == {"Ref": "LimitsTable"}


def test_free_plan_units():
    read = write = 0
    for table in of_type("AWS::DynamoDB::Table").values():
        p = table["Properties"]
        for part in [p, *p.get("GlobalSecondaryIndexes", [])]:
            read += part["ProvisionedThroughput"]["ReadCapacityUnits"]
            write += part["ProvisionedThroughput"]["WriteCapacityUnits"]
    assert (read, write) == (19, 14)
    assert read <= 25 and write <= 25


def test_limits_table():
    assert resource("LimitsTable")["Type"] == "AWS::DynamoDB::Table"
    p = props("LimitsTable")
    assert p["BillingMode"] == "PROVISIONED"
    assert p["AttributeDefinitions"] == [{"AttributeName": "pk", "AttributeType": "S"}]
    assert p["KeySchema"] == [{"AttributeName": "pk", "KeyType": "HASH"}]
    assert p["ProvisionedThroughput"] == {
        "ReadCapacityUnits": 2,
        "WriteCapacityUnits": 2,
    }
    assert p["TimeToLiveSpecification"] == {
        "AttributeName": "expiresAt",
        "Enabled": True,
    }
    assert "GlobalSecondaryIndexes" not in p


def test_limits_table_is_retained():
    # The spend counter lives here (C527). A deploy whose template leaves the table
    # out, or replaces it, keeps the old table and its counter instead of deleting them.
    table = resource("LimitsTable")
    assert table.get("DeletionPolicy") == "Retain"
    assert table.get("UpdateReplacePolicy") == "Retain"
    # A generated name, so a table created again never collides with the retained one.
    assert "TableName" not in props("LimitsTable")


def test_feed_index():
    p = props("ReportsTable")
    indexes = {i["IndexName"]: i for i in p["GlobalSecondaryIndexes"]}
    assert "feed-index" in indexes
    index = indexes["feed-index"]
    assert index["KeySchema"] == [
        {"AttributeName": "feedPart", "KeyType": "HASH"},
        {"AttributeName": "visibleUntil", "KeyType": "RANGE"},
    ]
    types = {a["AttributeName"]: a["AttributeType"] for a in p["AttributeDefinitions"]}
    assert types["feedPart"] == "S"
    assert types["visibleUntil"] == "N"
    assert index["ProvisionedThroughput"] == {
        "ReadCapacityUnits": 2,
        "WriteCapacityUnits": 2,
    }
    assert index["Projection"] == {
        "ProjectionType": "INCLUDE",
        "NonKeyAttributes": [
            "reportId",
            "lat",
            "lng",
            "gpsAccuracyM",
            "capturedAt",
            "mode",
            "level",
            "landmark",
            "passability",
            "levelIsFloor",
            "basis",
            "flags",
            "credit",
            "place",
            "event",
            "depthInMin",
            "depthInMax",
        ],
    }


def test_cors():
    cors = props("HttpApi")["DefinitionBody"]["x-amazon-apigateway-cors"]
    assert sorted(cors["allowMethods"]) == ["GET", "POST"]
    assert sorted(cors["allowHeaders"]) == ["content-type", "x-lusot-device"]
    assert cors["exposeHeaders"] == ["retry-after"]
    # Any origin, GET only, and no credentials.
    assert props("FeedApi")["CorsConfiguration"] == {
        "AllowOrigins": ["*"],
        "AllowMethods": ["GET"],
    }
    rules = props("UploadBucket")["CorsConfiguration"]["CorsRules"]
    assert len(rules) == 1
    assert sorted(rules[0]["AllowedMethods"]) == ["GET", "POST"]


def test_cors_origins_add_the_website():
    """C622: the API and the photo bucket allow AppOrigins and the website's origin, or
    AppOrigins alone with WebHosting off."""
    api = props("HttpApi")["DefinitionBody"]["x-amazon-apigateway-cors"]["allowOrigins"]
    (rule,) = props("UploadBucket")["CorsConfiguration"]["CorsRules"]
    bucket = rule["AllowedOrigins"]
    assert api == bucket
    default = T["Parameters"]["AppOrigins"]["Default"].split(",")
    # The Capacitor app and the local dev and preview servers keep working.
    assert default == [
        "https://localhost",
        "http://localhost:5173",
        "http://localhost:4173",
    ]
    web = f"https://{WEB_DOMAIN}"
    for origins in (api, bucket):
        assert cors_origins(origins, default) == [*default, web]
        # AppOrigins stays a list: a deploy that passes other origins keeps each one.
        other = ["https://a.example", "https://b.example"]
        assert cors_origins(origins, other) == [*other, web]
        # Off: no CloudFront origin, and still a list.
        assert cors_origins(origins, default, web=False) == default
        assert cors_origins(origins, other, web=False) == other


def test_web_hosting_switch():
    """Oct 31: AWS refused the account's first CloudFront distribution until it verifies the
    account, so WebHosting can leave the website out. On by default; npm run deploy needs it
    set by name in samconfig.toml."""
    p = T["Parameters"]["WebHosting"]
    assert p["Type"] == "String"
    assert p["AllowedValues"] == ["on", "off"]
    assert p["Default"] == "on"
    # Strings, never YAML 1.1's booleans (C309).
    assert all(isinstance(value, str) for value in [*p["AllowedValues"], p["Default"]])
    assert T["Conditions"] == {"HasWeb": {"Fn::Equals": [{"Ref": "WebHosting"}, "on"]}}


def test_only_the_website_needs_the_switch():
    """Off leaves out the four web resources and the three outputs deploy:web reads, and
    nothing else."""
    assert {name for name, r in RES.items() if "Condition" in r} == set(WEB_RESOURCES)
    assert all(RES[name]["Condition"] == "HasWeb" for name in WEB_RESOURCES)
    outputs = T["Outputs"]
    web_outputs = {"WebUrl", "WebBucketName", "WebDistributionId"}
    assert {name for name, o in outputs.items() if "Condition" in o} == web_outputs
    assert all(outputs[name]["Condition"] == "HasWeb" for name in web_outputs)


def test_nothing_left_in_names_the_website():
    """With WebHosting off, every resource and output left in must name no web resource,
    except in the on branch of an Fn::If on HasWeb."""
    for name, r in RES.items():
        if r.get("Condition") == "HasWeb":
            continue
        assert not unguarded(r), name
        assert not set(as_list(r.get("DependsOn", []))) & set(WEB_RESOURCES), name
    for name, o in T["Outputs"].items():
        if o.get("Condition") != "HasWeb":
            assert not unguarded(o), name


def test_web_bucket():
    """Private, owner-enforced, SSE-S3; no website hosting, versioning, logging or CORS."""
    assert resource("WebBucket")["Type"] == "AWS::S3::Bucket"
    p = props("WebBucket")
    assert p == {
        "PublicAccessBlockConfiguration": {
            "BlockPublicAcls": True,
            "BlockPublicPolicy": True,
            "IgnorePublicAcls": True,
            "RestrictPublicBuckets": True,
        },
        "OwnershipControls": {"Rules": [{"ObjectOwnership": "BucketOwnerEnforced"}]},
        "BucketEncryption": {
            "ServerSideEncryptionConfiguration": [
                {"ServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}
            ]
        },
    }


def test_web_resources_delete_like_the_upload_bucket():
    """The brief: the photo bucket's DeletionPolicy and UpdateReplacePolicy, which it
    leaves to CloudFormation's default (Delete)."""
    upload = resource("UploadBucket")
    assert "DeletionPolicy" not in upload and "UpdateReplacePolicy" not in upload
    for name in WEB_RESOURCES:
        for attribute in ("DeletionPolicy", "UpdateReplacePolicy"):
            assert resource(name).get(attribute) == upload.get(attribute), name


def test_web_origin_access_control():
    assert (
        resource("WebOriginAccessControl")["Type"]
        == "AWS::CloudFront::OriginAccessControl"
    )
    config = props("WebOriginAccessControl")["OriginAccessControlConfig"]
    assert config["OriginAccessControlOriginType"] == "s3"
    assert config["SigningBehavior"] == "always"
    assert config["SigningProtocol"] == "sigv4"
    assert config["Name"] == {"Fn::Sub": "${AWS::StackName}-web"}


def test_web_distribution():
    assert resource("WebDistribution")["Type"] == "AWS::CloudFront::Distribution"
    config = props("WebDistribution")["DistributionConfig"]
    assert config["Enabled"] is True
    assert config["DefaultRootObject"] == "index.html"
    assert config["HttpVersion"] == "http2and3"
    assert config["PriceClass"] == "PriceClass_200"
    assert config["Origins"] == [
        {
            "Id": "web-bucket",
            "DomainName": {"Fn::GetAtt": ["WebBucket", "RegionalDomainName"]},
            "OriginAccessControlId": {"Fn::GetAtt": ["WebOriginAccessControl", "Id"]},
            "S3OriginConfig": {"OriginAccessIdentity": ""},
        }
    ]
    # Whole, so nothing else (real-time logs, other methods, forwarded values) rides along.
    assert config["DefaultCacheBehavior"] == {
        "TargetOriginId": "web-bucket",
        "ViewerProtocolPolicy": "redirect-to-https",
        "CachePolicyId": CACHING_OPTIMIZED,
        "ResponseHeadersPolicyId": SECURITY_HEADERS,
        "Compress": True,
    }
    # Hash routes need no error page that turns a missing file into the app.
    assert "CustomErrorResponses" not in config
    assert "CacheBehaviors" not in config
    # The managed SecurityHeadersPolicy sends Referrer-Policy strict-origin-when-cross-origin.
    # OpenStreetMap's tiles need a referrer, so no policy of the template's own may replace it.
    assert not of_type("AWS::CloudFront::ResponseHeadersPolicy")


def test_web_logging_stays_off():
    """C622, PRIV-Q9: neither the distribution nor the web bucket logs a visitor."""
    config = props("WebDistribution")["DistributionConfig"]
    assert "Logging" not in config
    assert "RealtimeLogConfigArn" not in config["DefaultCacheBehavior"]
    assert not of_type("AWS::CloudFront::RealtimeLogConfig")
    # CloudFront's newer standard logging is a CloudWatch log delivery: none is made.
    kinds = {r["Type"] for r in RES.values()}
    assert not [kind for kind in kinds if kind.startswith("AWS::Logs::Delivery")]
    assert "LoggingConfiguration" not in props("WebBucket")


def test_web_bucket_policy():
    """CloudFront reads the bucket for this distribution only; no account ID is written."""
    assert resource("WebBucketPolicy")["Type"] == "AWS::S3::BucketPolicy"
    p = props("WebBucketPolicy")
    assert p["Bucket"] == {"Ref": "WebBucket"}
    assert p["PolicyDocument"]["Statement"] == [
        {
            "Effect": "Allow",
            "Principal": {"Service": "cloudfront.amazonaws.com"},
            "Action": "s3:GetObject",
            "Resource": {"Fn::Sub": "${WebBucket.Arn}/*"},
            "Condition": {
                "StringEquals": {
                    "AWS:SourceArn": {
                        "Fn::Sub": "arn:${AWS::Partition}:cloudfront::${AWS::AccountId}"
                        ":distribution/${WebDistribution.Id}"
                    }
                }
            },
        }
    ]


def test_web_outputs():
    outputs = T["Outputs"]
    assert outputs["WebUrl"]["Value"] == {
        "Fn::Sub": "https://${WebDistribution.DomainName}"
    }
    assert outputs["WebBucketName"]["Value"] == {"Ref": "WebBucket"}
    assert outputs["WebDistributionId"]["Value"] == {"Ref": "WebDistribution"}


def test_no_dependency_cycle():
    """The CORS lists name the distribution, so nothing it needs may need them."""
    graph = {
        name: references(r.get("Properties", {})) | set(as_list(r.get("DependsOn", [])))
        for name, r in RES.items()
    }
    assert "WebDistribution" in graph["UploadBucket"]
    assert "WebDistribution" in graph["HttpApi"]
    done = set()

    def visit(name, path):
        assert name not in path, " -> ".join([*path, name])
        if name not in done:
            for other in sorted(graph[name]):
                visit(other, [*path, name])
            done.add(name)

    for name in sorted(graph):
        visit(name, [])


def test_throttles():
    assert props("HttpApi")["DefaultRouteSettings"] == {
        "ThrottlingRateLimit": 10,
        "ThrottlingBurstLimit": 20,
    }
    assert props("HttpApi").get("RouteSettings") == {
        "GET /reports/{id}": {"ThrottlingRateLimit": 30, "ThrottlingBurstLimit": 60},
    }
    assert props("FeedApi")["DefaultRouteSettings"] == {
        "ThrottlingRateLimit": 5,
        "ThrottlingBurstLimit": 10,
    }


def test_access_logs_stay_off():
    """MS4-Q6: no access logs, S3 server access logs or CloudTrail trail."""
    # MS1's template has no FeedApi, so this test can't pass on it.
    assert resource("FeedApi")["Type"] == "AWS::Serverless::HttpApi"
    for name in ("HttpApi", "FeedApi"):
        assert "AccessLogSettings" not in props(name), name
    assert "LoggingConfiguration" not in props("UploadBucket")
    assert not of_type("AWS::CloudTrail::Trail")


def test_lifecycle():
    rules = props("UploadBucket")["LifecycleConfiguration"]["Rules"]
    # A rule without a prefix would cover the whole bucket, samples/ included.
    days = {rule["Prefix"]: rule["ExpirationInDays"] for rule in rules}
    assert days == {"raw/": 1, "blurred/": 7, "overlay/": 7, "demo/": 60}
    assert all(rule["Status"] == "Enabled" for rule in rules)
    demo = [rule["Id"] for rule in rules if rule["Prefix"] == "demo/"]
    assert demo == ["demo-60-days"]
    # MS4-Q11: samples stay while the sample button exists.
    assert not [prefix for prefix in days if prefix.startswith("samples")]


def test_queue_retentions():
    """C525: an uploader's IP address is gone within 7 days."""
    dead = props("DeadLetterQueue").get("MessageRetentionPeriod")
    upload = props("UploadQueue").get("MessageRetentionPeriod")
    assert (dead, upload) == (518400, 345600)
    assert dead > upload


def test_lease_fits_the_timeouts():
    """Pins today's values, MS3a's: a characterization test (T10), not new behaviour.

    A claim's lease outlives one analysis run and ends before the message comes back.
    """
    match = re.search(
        r"^LEASE_S\s*=\s*(\d+)", REPORT_STORE.read_text(encoding="utf-8"), re.M
    )
    assert match, "LEASE_S not found in report_store.py"
    lease = int(match.group(1))
    timeout = props("AnalysisFunction")["Timeout"]
    queue = props("UploadQueue")
    visibility = queue["VisibilityTimeout"]
    assert timeout < lease < visibility
    assert visibility >= 6 * timeout
    assert queue["RedrivePolicy"]["maxReceiveCount"] == 5
    # The values themselves (C525, C801): nothing else guards AnalysisFunction's.
    assert (timeout, lease, visibility) == (180, 900, 1080)


def test_alarms():
    dead = props("DeadLetterAlarm")
    assert dead["AlarmActions"] == ALARM_TOPIC
    assert dead.get("OKActions") == ALARM_TOPIC
    for name, function, threshold in (
        ("AnalysisInvocationsAlarm", "AnalysisFunction", 100),
        ("ApiInvocationsAlarm", "ApiFunction", 5000),
    ):
        assert resource(name)["Type"] == "AWS::CloudWatch::Alarm"
        p = props(name)
        assert p["Namespace"] == "AWS/Lambda", name
        assert p["MetricName"] == "Invocations", name
        assert p["Dimensions"] == [
            {"Name": "FunctionName", "Value": {"Ref": function}}
        ], name
        assert p["Statistic"] == "Sum", name
        assert p["Period"] == 3600, name
        assert p["EvaluationPeriods"] == 1, name
        assert p["Threshold"] == threshold, name
        assert p["ComparisonOperator"] == "GreaterThanThreshold", name
        assert p["TreatMissingData"] == "notBreaching", name
        assert p["AlarmActions"] == ALARM_TOPIC, name
    # Inside the free plan's 10 alarms.
    assert len(of_type("AWS::CloudWatch::Alarm")) <= 10


def test_api_alarm_stays_5000():
    """C735: Ask adds at most 60 counted questions an hour, well inside 5,000. The
    threshold MS4 left for Ask's spec to set is now set, and its comment says so."""
    p = props("ApiInvocationsAlarm")
    assert (p["Threshold"], p["Period"]) == (5000, 3600)
    lines = [line.strip() for line in raw_lines()]
    above = lines[lines.index("ApiInvocationsAlarm:") - 1]
    assert above.startswith("#") and "C735" in above
    assert not [line for line in lines if "until Ask Lusot's spec sizes it" in line]


def test_alarms_fit_the_free_ten():
    """CloudWatch's free tier: 10 alarms and 10 custom metrics. Ask's cap alarm is the
    sixth alarm and its refusals the third metric."""
    alarms = of_type("AWS::CloudWatch::Alarm")
    assert "AskCapAlarm" in alarms
    assert len(alarms) <= 10
    metrics = {
        (t["MetricNamespace"], t["MetricName"])
        for f in of_type("AWS::Logs::MetricFilter").values()
        for t in f["Properties"]["MetricTransformations"]
    }
    assert ("Lusot", "AskCapRefusals") in metrics
    assert len(metrics) <= 10


def test_roles():
    # The analysis role: MS3a's grants on raw/, plus the stored photos' prefixes.
    assert granted("AnalysisRole", "s3:GetObject") == bucket_paths("raw")
    assert granted("AnalysisRole", "s3:PutObject") == bucket_paths(
        "blurred", "overlay", "demo"
    )
    assert granted("AnalysisRole", "s3:DeleteObject") == bucket_paths(
        "raw", "blurred", "overlay", "demo"
    )
    queue = [
        s
        for s in statements("AnalysisRole")
        if s["Resource"] == {"Fn::GetAtt": ["UploadQueue", "Arn"]}
    ]
    assert len(queue) == 1
    assert sorted(queue[0]["Action"]) == [
        "sqs:ChangeMessageVisibility",
        "sqs:DeleteMessage",
        "sqs:GetQueueAttributes",
        "sqs:ReceiveMessage",
    ]
    # The spend stop (C527): the counter in limits, read at the claim and added to
    # after a run; the stop read; and only the model-calls switch put.
    assert granted("AnalysisRole", "dynamodb:GetItem") == {"${LimitsTable.Arn}"}
    assert granted("AnalysisRole", "dynamodb:UpdateItem") == {
        "${ReportsTable.Arn}",
        "${LimitsTable.Arn}",
    }
    # Minor 3: on limits, the counter's item only, never the API's counters or flags.
    # One statement names the table, and its condition holds spend.py's SPEND_PK.
    source = SPEND.read_text(encoding="utf-8")
    spend_pk = re.search(r'^SPEND_PK\s*=\s*"([^"]+)"', source, re.MULTILINE)
    assert spend_pk, "SPEND_PK not found in spend.py"
    assert spend_pk.group(1) == "spend#meta"
    on_limits = [
        s
        for s in statements("AnalysisRole")
        if any("LimitsTable" in resource_name(r) for r in as_list(s["Resource"]))
    ]
    assert len(on_limits) == 1
    (spend_grant,) = on_limits
    assert as_list(spend_grant["Resource"]) == [{"Fn::GetAtt": ["LimitsTable", "Arn"]}]
    assert sorted(as_list(spend_grant["Action"])) == [
        "dynamodb:GetItem",
        "dynamodb:UpdateItem",
    ]
    assert spend_grant["Condition"] == {
        "ForAllValues:StringEquals": {"dynamodb:LeadingKeys": [spend_pk.group(1)]}
    }
    assert granted("AnalysisRole", "ssm:GetParameter") == {
        f"{SSM_ARN}/lusot/stop/*",
        f"{SSM_ARN}/lusot/meta/model-api-key",
        f"{SSM_ARN}/lusot/spend/stop-usd",
    }
    assert granted("AnalysisRole", "ssm:PutParameter") == {
        f"{SSM_ARN}/lusot/stop/model-calls"
    }
    analysis_actions = {
        action for s in statements("AnalysisRole") for action in as_list(s["Action"])
    }
    assert {a for a in analysis_actions if a.startswith("ssm:")} == {
        "ssm:GetParameter",
        "ssm:PutParameter",
    }

    # The API role's switches, and Ask's key and spend stop (C701, C736): the stop
    # read, and only the model-calls switch put, as the analysis role has them.
    assert granted("ApiRole", "ssm:GetParameter") == {
        f"{SSM_ARN}/lusot/stop/*",
        f"{SSM_ARN}/lusot/meta/model-api-key",
        f"{SSM_ARN}/lusot/spend/stop-usd",
    }
    assert granted("ApiRole", "ssm:PutParameter") == {
        f"{SSM_ARN}/lusot/stop/model-calls"
    }
    api_actions = {
        action for s in statements("ApiRole") for action in as_list(s["Action"])
    }
    assert {a for a in api_actions if a.startswith("ssm:")} == {
        "ssm:GetParameter",
        "ssm:PutParameter",
    }

    # The API role: presigned links and the sample copy's source; uploads to raw/ only.
    assert granted("ApiRole", "s3:GetObject") == bucket_paths(
        "blurred", "overlay", "demo", "samples"
    )
    assert granted("ApiRole", "s3:PutObject") == bucket_paths("raw")
    listing = [
        s for s in statements("ApiRole") if "s3:ListBucket" in as_list(s["Action"])
    ]
    assert len(listing) == 1
    assert as_list(listing[0]["Action"]) == ["s3:ListBucket"]
    assert listing[0]["Resource"] == {"Fn::GetAtt": ["UploadBucket", "Arn"]}
    assert listing[0]["Condition"] == {"StringLike": {"s3:prefix": "samples/*"}}

    # A flag's TransactWriteItems puts on limits and updates the report; the
    # counters update limits. Each part is governed by PutItem or UpdateItem.
    tables = {"${ReportsTable.Arn}", "${LimitsTable.Arn}"}
    assert granted("ApiRole", "dynamodb:Query") == {
        "${ReportsTable.Arn}",
        "${ReportsTable.Arn}/index/reportId-index",
        "${ReportsTable.Arn}/index/feed-index",
    }
    assert granted("ApiRole", "dynamodb:PutItem") == tables
    assert granted("ApiRole", "dynamodb:UpdateItem") == tables
    # Ask's reads (C701): the spend counter, the place cache and the Nominatim slot,
    # all in limits; never a report.
    assert granted("ApiRole", "dynamodb:GetItem") == {"${LimitsTable.Arn}"}
    # The API writes every kind of limits item, so its grant has no key condition.
    assert not [s for s in statements("ApiRole") if "dynamodb:LeadingKeys" in str(s)]
    dynamodb = {
        action
        for s in statements("ApiRole")
        for action in as_list(s["Action"])
        if action.startswith("dynamodb:")
    }
    assert dynamodb == {
        "dynamodb:Query",
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:UpdateItem",
    }

    for role in of_type("AWS::IAM::Role"):
        # A managed policy would bring grants this test never sees.
        assert "ManagedPolicyArns" not in props(role), role
        for s in statements(role):
            assert "*" not in as_list(s["Resource"]), role
            actions = as_list(s["Action"])
            assert not [action for action in actions if "*" in action], role
            assert "dynamodb:Scan" not in actions, role


def test_api_role_reads_only_the_model_key():
    """C701: the API role reads the Meta key's one parameter, and nothing else under
    /lusot/meta. No resource is exactly "*" (MS1's /lusot/stop/* grant holds one
    inside its ARN), and no KMS grant: the key is a SecureString under the AWS managed
    aws/ssm key, whose policy lets the account's SSM callers decrypt."""
    env = props("ApiFunction")["Environment"]["Variables"]
    model_key = f"{SSM_ARN}{env['MODEL_KEY_PARAM']}"
    assert model_key == f"{SSM_ARN}/lusot/meta/model-api-key"
    named = [
        (s, resource_name(r))
        for s in statements("ApiRole")
        for r in as_list(s["Resource"])
    ]
    assert {name for _, name in named if "/lusot/meta" in str(name)} == {model_key}
    (on_key,) = [s for s, name in named if name == model_key]
    assert on_key["Effect"] == "Allow"
    assert as_list(on_key["Action"]) == ["ssm:GetParameter"]
    assert "Condition" not in on_key
    assert not [name for _, name in named if name == "*"]
    actions = {a for s in statements("ApiRole") for a in as_list(s["Action"])}
    assert not [a for a in actions if a.startswith("kms:")]


def test_spend_stop_parameter():
    """C527, C528: the build phase's $60, a literal like INCHES_SHOWN."""
    assert resource("SpendStopParameter")["Type"] == "AWS::SSM::Parameter"
    p = props("SpendStopParameter")
    assert p == {"Name": "/lusot/spend/stop-usd", "Type": "String", "Value": "60"}
    assert isinstance(p["Value"], str)  # YAML's bare 60 would be a number
    # The name the handler and the scripts read.
    source = SPEND.read_text(encoding="utf-8")
    match = re.search(r'^SPEND_STOP_PARAM\s*=\s*"([^"]+)"', source, re.MULTILINE)
    assert match, "SPEND_STOP_PARAM not found in spend.py"
    assert match.group(1) == p["Name"]
    # And the name Ask's handler reads before its first Meta call (C736). A wrong one
    # fails closed, but every typed question would then get the plain list.
    source = ASK_HANDLER.read_text(encoding="utf-8")
    match = re.search(
        r'^export const SPEND_STOP_PARAM = "([^"]+)";', source, re.MULTILINE
    )
    assert match, "SPEND_STOP_PARAM not found in the Ask handler"
    assert match.group(1) == p["Name"]
    assert "GetParameterCommand({ Name: SPEND_STOP_PARAM })" in source
    assert not [name for name in T["Parameters"] if "spend" in name.lower()]


def test_nominatim_switch_is_off():
    """Ask spec §4.8: the off switch Nominatim's policy asks for. Off, so places resolve
    through Nominatim; a missing switch reads as on, and every such place would be
    lookup_unavailable."""
    assert resource("StopNominatimParameter")["Type"] == "AWS::SSM::Parameter"
    p = props("StopNominatimParameter")
    assert p == {"Name": "/lusot/stop/nominatim", "Type": "String", "Value": "off"}
    assert isinstance(p["Value"], str)  # YAML 1.1's bare off would be false
    # Under the prefix the API reads its switches by, which its /lusot/stop/* grant covers.
    prefix = props("ApiFunction")["Environment"]["Variables"]["STOP_PARAM_PREFIX"]
    assert p["Name"] == f"{prefix}nominatim"
    assert f"{SSM_ARN}/lusot/stop/*" in granted("ApiRole", "ssm:GetParameter")
    # The name the geocoder reads.
    source = ASK_NOMINATIM.read_text(encoding="utf-8")
    assert re.search(r'isStopped\("nominatim",', source)


def test_budget():
    """C528: one $150 cost budget, credits and refunds left out, alerts at 50, 100, 140."""
    budgets = of_type("AWS::Budgets::Budget")
    assert list(budgets) == ["MetaAndAwsBudget"]
    p = props("MetaAndAwsBudget")
    budget = p["Budget"]
    assert budget["BudgetType"] == "COST"
    assert budget["BudgetLimit"] == {"Amount": 150, "Unit": "USD"}
    # It doesn't reset on Nov 1. With no start date it runs by the Budgets default,
    # the calendar year: Jan 1 to Dec 31.
    assert budget["TimeUnit"] == "ANNUALLY"
    assert "TimePeriod" not in budget
    # So it measures the credits being used up, not the bill after them.
    assert budget["CostTypes"] == {"IncludeCredit": False, "IncludeRefund": False}
    notifications = p["NotificationsWithSubscribers"]
    assert [n["Notification"] for n in notifications] == [
        {
            "NotificationType": "ACTUAL",
            "ComparisonOperator": "GREATER_THAN",
            "Threshold": threshold,
            "ThresholdType": "ABSOLUTE_VALUE",
        }
        for threshold in (50, 100, 140)
    ]
    for n in notifications:
        assert n["Subscribers"] == [
            {"SubscriptionType": "EMAIL", "Address": {"Ref": "AlarmEmail"}}
        ]


def check_count_alarm(filter_name, pattern, metric, alarm_name):
    """A log filter that counts each matching line as 1, and its alarm at 1 in 5 min."""
    assert resource(filter_name)["Type"] == "AWS::Logs::MetricFilter"
    f = props(filter_name)
    assert f["LogGroupName"] == {"Ref": "AnalysisLogGroup"}
    assert f["FilterPattern"] == pattern
    # No DefaultValue: a quiet period publishes nothing, which notBreaching reads.
    assert f["MetricTransformations"] == [
        {"MetricNamespace": "Lusot", "MetricName": metric, "MetricValue": "1"}
    ]
    assert resource(alarm_name)["Type"] == "AWS::CloudWatch::Alarm"
    a = props(alarm_name)
    assert (a["Namespace"], a["MetricName"]) == ("Lusot", metric)
    assert "Dimensions" not in a
    assert a["Statistic"] == "Sum"
    assert (a["Period"], a["EvaluationPeriods"], a["Threshold"]) == (300, 1, 1)
    assert a["ComparisonOperator"] == "GreaterThanOrEqualToThreshold"
    assert a["TreatMissingData"] == "notBreaching"
    assert a["AlarmActions"] == ALARM_TOPIC
    assert "OKActions" not in a  # the alarm clearing doesn't clear what it reports
    return a


def test_spend_pause_alarm():
    """Every spend pause emails (C527): a lost write or a stop reached sets the switch."""
    alarm = check_count_alarm(
        "SpendPauseFilter",
        '?"spend_error" ?"spend_stop"',
        "SpendPauses",
        "SpendPauseAlarm",
    )
    description = alarm["AlarmDescription"]
    assert "until" in description and "cleared" in description
    assert "docs/operations.md" in description
    assert len(of_type("AWS::CloudWatch::Alarm")) <= 10
    # Ask's pauses (C736) are logged in the API's group: a second filter there feeds
    # the same metric, so the one alarm covers both.
    assert resource("ApiSpendPauseFilter")["Type"] == "AWS::Logs::MetricFilter"
    api = props("ApiSpendPauseFilter")
    assert api["LogGroupName"] == {"Ref": "ApiLogGroup"}
    assert api["FilterPattern"] == '?"spend_error" ?"spend_stop"'
    assert (
        api["MetricTransformations"]
        == props("SpendPauseFilter")["MetricTransformations"]
    )


def test_publish_read_alarm():
    """Task 7's Minor 4: a failed publish read leaves live and demo results unpinned."""
    check_count_alarm(
        "PublishReadFilter", '"publish_switch"', "PublishReadErrors", "PublishReadAlarm"
    )
    assert set(of_type("AWS::CloudWatch::Alarm")) == {
        "DeadLetterAlarm",
        "AnalysisInvocationsAlarm",
        "ApiInvocationsAlarm",
        "SpendPauseAlarm",
        "PublishReadAlarm",
        "AskCapAlarm",
    }
    # Three custom metrics, inside the free tier's 10.
    metrics = {
        (t["MetricNamespace"], t["MetricName"])
        for f in of_type("AWS::Logs::MetricFilter").values()
        for t in f["Properties"]["MetricTransformations"]
    }
    assert metrics == {
        ("Lusot", "SpendPauses"),
        ("Lusot", "PublishReadErrors"),
        ("Lusot", "AskCapRefusals"),
    }


def test_ask_cap_alarm():
    """C727: each question_cap refusal counts 1, matched by the term, since Lambda's text
    log format puts a timestamp and the request id before each JSON line. Any refusal in
    an hour emails, and so does the alarm clearing."""
    assert resource("AskCapMetricFilter")["Type"] == "AWS::Logs::MetricFilter"
    f = props("AskCapMetricFilter")
    assert f["LogGroupName"] == {"Ref": "ApiLogGroup"}
    assert f["FilterPattern"] == '"question_cap"'
    # No DefaultValue: a quiet hour publishes nothing, which notBreaching reads.
    assert f["MetricTransformations"] == [
        {"MetricNamespace": "Lusot", "MetricName": "AskCapRefusals", "MetricValue": "1"}
    ]
    assert resource("AskCapAlarm")["Type"] == "AWS::CloudWatch::Alarm"
    a = props("AskCapAlarm")
    assert (a["Namespace"], a["MetricName"]) == ("Lusot", "AskCapRefusals")
    assert "Dimensions" not in a
    assert a["Statistic"] == "Sum"
    assert (a["Period"], a["EvaluationPeriods"], a["Threshold"]) == (3600, 1, 1)
    assert a["ComparisonOperator"] == "GreaterThanOrEqualToThreshold"
    assert a["TreatMissingData"] == "notBreaching"
    assert a["AlarmActions"] == ALARM_TOPIC
    assert a.get("OKActions") == ALARM_TOPIC
    # The code the API's global question refusal carries.
    source = API_LIMITS.read_text(encoding="utf-8")
    assert re.search(r'question:\s*\{[^}]*all:\s*"question_cap"', source)
    # The description names the cap limits.ts sets (N1: 60 an hour, Rene, Oct 31).
    (cap,) = re.findall(r"question:\s*\{\s*device:\s*\d+,\s*all:\s*(\d+)\s*\}", source)
    assert cap == "60"
    assert a["AlarmDescription"] == f"Ask Lusot refused a question at its cap of {cap} an hour."


def test_visibility_grant_comment():
    """F2: the comment says who uses the queue and why the visibility grant stays."""
    lines = [line.strip() for line in raw_lines()]
    at = lines.index("- sqs:ChangeMessageVisibility")
    above = lines[at - 1]
    assert above.startswith("#")
    assert "ReportNotFound" in above and "R92" in above
    assert lines[at - 2] == "- sqs:GetQueueAttributes"

    start = max(i for i in range(at) if lines[i].startswith("- Effect:"))
    opening = []
    i = start - 1
    while lines[i].startswith("#"):
        opening.insert(0, lines[i])
        i -= 1
    comment = " ".join(opening)
    assert "handler" in comment
    assert "event source mapping" in comment
    old = "# What the SQS event source mapping polls with, on this queue only."
    assert old not in lines


def test_feed_output():
    outputs = T["Outputs"]
    assert outputs.get("FeedApiUrl", {}).get("Value") == {
        "Fn::GetAtt": ["FeedApi", "ApiEndpoint"]
    }
    assert {
        "ApiUrl",
        "BucketName",
        "TableName",
        "QueueName",
        "DeadLetterQueueName",
    } <= set(outputs)
