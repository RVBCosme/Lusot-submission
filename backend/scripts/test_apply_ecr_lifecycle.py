"""Tests for apply_ecr_lifecycle.py: the image repository keeps its last 3 images (C38).

Run: uv run --with pytest --with boto3 pytest backend/scripts
"""

import json

import apply_ecr_lifecycle
import pytest
from botocore.exceptions import ClientError

# Built at run time, so the repo's 12-digit scan never meets a literal account ID.
ACCOUNT = "1" * 12
REGISTRY = f"{ACCOUNT}.dkr.ecr.ap-southeast-1.amazonaws.com"
# The shape of the names SAM's companion stack gives its repositories.
REPO = "lusot1a2b3c4d/analysisfunction5e6f7a8brepo"
FUNCTION = "lusot-AnalysisFunction-Ab12Cd34Ef56"
DIGEST = "sha256:" + "0123456789abcdef" * 4


def aws_error(code, operation):
    """An AWS error whose message holds an ARN, as AccessDenied messages do."""
    message = f"User: arn:aws:iam::{ACCOUNT}:user/rene-dev is not authorized"
    return ClientError(
        {
            "Error": {"Code": code, "Message": message},
            "ResponseMetadata": {"HTTPStatusCode": 400},
        },
        operation,
    )


class FakeCloudFormation:
    def describe_stack_resource(self, StackName, LogicalResourceId):
        if (StackName, LogicalResourceId) != ("lusot", "AnalysisFunction"):
            raise aws_error("ValidationError", "DescribeStackResource")
        return {
            "StackResourceDetail": {
                "StackName": "lusot",
                "StackId": (
                    f"arn:aws:cloudformation:ap-southeast-1:{ACCOUNT}:stack/lusot/x"
                ),
                "LogicalResourceId": "AnalysisFunction",
                "PhysicalResourceId": FUNCTION,
                "ResourceType": "AWS::Lambda::Function",
                "ResourceStatus": "UPDATE_COMPLETE",
            }
        }


class FakeLambda:
    def get_function(self, FunctionName):
        if FunctionName != FUNCTION:
            raise aws_error("ResourceNotFoundException", "GetFunction")
        return {
            "Configuration": {
                "FunctionName": FUNCTION,
                "FunctionArn": (
                    f"arn:aws:lambda:ap-southeast-1:{ACCOUNT}:function:{FUNCTION}"
                ),
                "PackageType": "Image",
            },
            "Code": {
                "RepositoryType": "ECR",
                "ImageUri": f"{REGISTRY}/{REPO}:analysisfunction-0f1e2d3c4b5a-ms1",
                "ResolvedImageUri": f"{REGISTRY}/{REPO}@{DIGEST}",
            },
        }


class FakeECR:
    def __init__(self):
        self.puts = []

    def put_lifecycle_policy(self, repositoryName, lifecyclePolicyText):
        self.puts.append(
            {
                "repositoryName": repositoryName,
                "lifecyclePolicyText": lifecyclePolicyText,
            }
        )
        return {
            "registryId": ACCOUNT,
            "repositoryName": repositoryName,
            "lifecyclePolicyText": lifecyclePolicyText,
        }


class FakeSession:
    def __init__(self, cloudformation=None):
        self.ecr = FakeECR()
        self._clients = {
            "cloudformation": cloudformation or FakeCloudFormation(),
            "lambda": FakeLambda(),
            "ecr": self.ecr,
        }

    def client(self, service):
        return self._clients[service]


@pytest.mark.parametrize(
    "uri",
    [
        f"{REGISTRY}/{REPO}:analysisfunction-0f1e2d3c4b5a-ms1",
        f"{REGISTRY}/{REPO}@{DIGEST}",
    ],
    ids=["tag", "digest"],
)
def test_repository_name_from_image_uri(uri):
    assert apply_ecr_lifecycle.repository_name(uri) == REPO


def test_non_ecr_image_uri_is_refused():
    with pytest.raises(ValueError):
        apply_ecr_lifecycle.repository_name("public.ecr.aws/lambda/python:3.13")


def test_puts_keep_last_3_and_prints_only_the_name(capsys):
    session = FakeSession()

    assert apply_ecr_lifecycle.main(session) == 0

    [put] = session.ecr.puts
    assert put["repositoryName"] == REPO
    [rule] = json.loads(put["lifecyclePolicyText"])["rules"]
    assert rule["selection"] == {
        "tagStatus": "any",
        "countType": "imageCountMoreThan",
        "countNumber": 3,
    }
    assert rule["action"] == {"type": "expire"}
    assert capsys.readouterr().out.splitlines() == [
        f"repository: {REPO}",
        "lifecycle: keep 3",
    ]


def test_rerun_puts_the_same_policy():
    session = FakeSession()

    apply_ecr_lifecycle.main(session)
    apply_ecr_lifecycle.main(session)

    first, second = session.ecr.puts
    assert first == second


def test_missing_profile_is_one_line_not_a_traceback(monkeypatch, capsys, tmp_path):
    # An empty AWS config: boto3 fails on the profile before any network call.
    (tmp_path / "config").write_text("")
    monkeypatch.setenv("AWS_CONFIG_FILE", str(tmp_path / "config"))
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", str(tmp_path / "config"))
    monkeypatch.delenv("AWS_PROFILE", raising=False)

    assert apply_ecr_lifecycle.main() == 1
    assert capsys.readouterr().err == "AWS error: ProfileNotFound\n"


def test_aws_error_prints_code_not_message(capsys):
    class DeniedCloudFormation:
        def describe_stack_resource(self, **kwargs):
            raise aws_error("AccessDenied", "DescribeStackResource")

    session = FakeSession(cloudformation=DeniedCloudFormation())

    assert apply_ecr_lifecycle.main(session) == 1

    out, err = capsys.readouterr()
    assert "AccessDenied" in err
    assert ACCOUNT not in out + err
    assert "arn:" not in out + err
    assert session.ecr.puts == []
