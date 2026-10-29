"""Tests for backend/template.yaml: MS4's routes, APIs, tables, CORS, throttles,
lifecycle, retentions, alarms and role grants (MS4 spec §4.3 to §4.7; plan Task 1).

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
REPORT_STORE = (
    TEMPLATE.parent / "analysis" / "src" / "lusot_analysis" / "report_store.py"
)
ALARM_TOPIC = [{"Ref": "AlarmTopic"}]
APP_ORIGINS = {"Ref": "AppOrigins"}


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


def test_routes():
    assert route_keys("HttpApi") == {
        "POST /uploads",
        "GET /reports/{id}",
        "GET /reports",
        "GET /map/pins",
        "POST /reports/{id}/flag",
        "GET /samples",
        "POST /samples/{sampleId}",
    }
    assert route_keys("FeedApi") == {"GET /pins.geojson"}


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
    }
    assert env["LIMITS_TABLE_NAME"] == {"Ref": "LimitsTable"}
    assert env["FEED_INDEX_NAME"] == "feed-index"
    # A literal string, never a parameter (C515): YAML's bare false would be a bool.
    assert env["INCHES_SHOWN"] == "false"
    assert isinstance(env["INCHES_SHOWN"], str)
    assert not [name for name in T["Parameters"] if "inches" in name.lower()]


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
    assert cors["allowOrigins"] == APP_ORIGINS
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
    assert rules[0]["AllowedOrigins"] == APP_ORIGINS


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
    dynamodb = {
        action
        for s in statements("ApiRole")
        for action in as_list(s["Action"])
        if action.startswith("dynamodb:")
    }
    assert dynamodb == {"dynamodb:Query", "dynamodb:PutItem", "dynamodb:UpdateItem"}

    for role in of_type("AWS::IAM::Role"):
        for s in statements(role):
            assert "*" not in as_list(s["Resource"]), role
            actions = as_list(s["Action"])
            assert not {"*", "dynamodb:*", "dynamodb:Scan"} & set(actions), role


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
