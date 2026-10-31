"""Tests for MS7's template hardening (MS7 plan Task 12; spec §4.6, D-d and D-e).

The bucket refuses plain HTTP, the region is asserted, each stop switch says what a
deploy does to it, and MS4's alarms report recovery and email Rene. They read the
template through MS4's cfn_template loader, so nothing reaches AWS. check:py runs this
file with the scripts' dependencies. Alone, from the repo root:
    uv run --python 3.13 --with pytest --with pyyaml pytest -q
        backend/scripts/test_template_hardening.py
"""

import re

from cfn_template import load_template, raw_lines

T = load_template()
RES = T["Resources"]
ALARM_TOPIC = {"Ref": "AlarmTopic"}
SWITCHES = (
    "StopUploadsParameter",
    "StopPublishParameter",
    "StopModelCallsParameter",
    # Ask Lusot's place lookup: the same warning (the tracker, Oct 31, Cloud 4's item 4).
    "StopNominatimParameter",
)


def props(name):
    assert name in RES, f"{name} is missing from the template"
    return RES[name].get("Properties", {})


def as_list(value):
    return value if isinstance(value, list) else [value]


def comment_above(name):
    """The comment lines just above a resource's line, joined into one lower-case line."""
    lines = raw_lines()
    at = lines.index(f"  {name}:")
    block = []
    for line in reversed(lines[:at]):
        if not line.strip().startswith("#"):
            break
        block.insert(0, line.strip().lstrip("#").strip())
    text = " ".join(block).lower().replace('"', "").replace("`", "")
    return re.sub(r"\s+", " ", text)


def test_bucket_refuses_plain_http():
    """D-e (R51): every request to the upload bucket or its objects over plain HTTP is
    refused, whoever sends it. The policy only denies, so it grants nobody anything."""
    policy = RES.get("UploadBucketPolicy")
    assert policy is not None, "UploadBucketPolicy is missing from the template"
    assert policy["Type"] == "AWS::S3::BucketPolicy"
    # Not behind the WebHosting switch: the bucket exists either way.
    assert "Condition" not in policy
    p = policy["Properties"]
    assert p["Bucket"] == {"Ref": "UploadBucket"}
    # This one statement and no other, so no stray Deny can lock the app out.
    assert p["PolicyDocument"] == {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "DenyPlainHttp",
                "Effect": "Deny",
                "Principal": "*",
                "Action": "s3:*",
                "Resource": [
                    {"Fn::GetAtt": ["UploadBucket", "Arn"]},
                    {"Fn::Sub": "${UploadBucket.Arn}/*"},
                ],
                "Condition": {"Bool": {"aws:SecureTransport": "false"}},
            }
        ],
    }


def test_region_is_asserted():
    """D-d: a deploy anywhere but Singapore fails at the change set, before the stack
    changes. SAM's companion stack and its uploads come earlier, so they can still land."""
    rules = T.get("Rules", {})
    asserted = [
        rule
        for rule in rules.values()
        if any(
            a["Assert"] == {"Fn::Equals": [{"Ref": "AWS::Region"}, "ap-southeast-1"]}
            for a in rule.get("Assertions", [])
        )
    ]
    assert len(asserted) == 1
    (rule,) = asserted
    # No RuleCondition, so the rule holds for every deploy.
    assert "RuleCondition" not in rule
    assert all(a.get("AssertDescription") for a in rule["Assertions"])


def test_switch_parameters_warn_about_deploys():
    """D-d: a deploy that changes a switch's resource writes its template value, off, over
    a switch flipped by hand, so after a deploy during an incident every switch is read
    again. YAML loaders drop comments, so this reads the raw text."""
    for name in SWITCHES:
        assert props(name)["Value"] == "off", name
        text = comment_above(name)
        assert "a deploy that changes this parameter" in text, name
        assert "resets it to off" in text, name
        assert "after a deploy during an incident, read every switch again" in text, name


def test_every_stop_switch_is_listed():
    """A switch added later carries the same warning: every /lusot/stop/ parameter is in SWITCHES."""
    stops = {
        name
        for name, r in RES.items()
        if r["Type"] == "AWS::SSM::Parameter"
        and str(r["Properties"]["Name"]).startswith("/lusot/stop/")
    }
    assert stops == set(SWITCHES)


def test_dead_letter_alarm_reports_recovery():
    """MS4's OKActions (D-d gives MS7 the check): Rene hears when the alarm clears."""
    assert RES["AlarmTopic"]["Type"] == "AWS::SNS::Topic"
    p = props("DeadLetterAlarm")
    assert ALARM_TOPIC in as_list(p["AlarmActions"])
    assert ALARM_TOPIC in as_list(p.get("OKActions", []))


def test_invocation_alarms_email_rene():
    """C830 (MS9's N6): one hourly invocation alarm per function, at MS4's thresholds
    (Task 12's names), each sending to the topic that emails Rene."""
    alarms = {
        name: r["Properties"]
        for name, r in RES.items()
        if r["Type"] == "AWS::CloudWatch::Alarm"
    }
    for function, threshold in (("AnalysisFunction", 100), ("ApiFunction", 5000)):
        watching = [
            p
            for p in alarms.values()
            if p.get("Namespace") == "AWS/Lambda"
            and p.get("MetricName") == "Invocations"
            and p.get("Dimensions")
            == [{"Name": "FunctionName", "Value": {"Ref": function}}]
        ]
        assert len(watching) == 1, function
        (p,) = watching
        assert (p["Statistic"], p["Period"]) == ("Sum", 3600), function
        assert p["Threshold"] == threshold, function
        assert p["ComparisonOperator"] == "GreaterThanThreshold", function
        assert ALARM_TOPIC in as_list(p["AlarmActions"]), function
    # The topic emails the address passed at deploy time, never one written here (D17).
    subscriptions = [
        r["Properties"]
        for r in RES.values()
        if r["Type"] == "AWS::SNS::Subscription"
        and r["Properties"]["TopicArn"] == ALARM_TOPIC
    ]
    assert [(s["Protocol"], s["Endpoint"]) for s in subscriptions] == [
        ("email", {"Ref": "AlarmEmail"})
    ]
