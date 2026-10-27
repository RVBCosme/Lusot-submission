# /// script
# requires-python = ">=3.13,<3.14"
# dependencies = ["boto3>=1.43.120"]
# ///
"""Keep the last 3 images in the analysis image's repository (C38, plan Table 16).

`sam deploy` with `resolve_image_repos` makes that repository in SAM's companion stack,
outside our template, so `npm run deploy` runs this after every deploy. It finds the
repository from the image the deployed AnalysisFunction runs, then puts the lifecycle
policy. A put replaces the repository's policy, so a re-run changes nothing.

It prints the repository's name, never the image URI, whose registry host is the account
ID. An AWS error is reported by its code and HTTP status only, since its message can
carry an ARN.

Usage: uv run backend/scripts/apply_ecr_lifecycle.py
"""

from __future__ import annotations

import json
import os
import re
import sys

import boto3
from botocore.exceptions import BotoCoreError, ClientError

STACK = "lusot"
FUNCTION = "AnalysisFunction"  # the template's logical ID
KEEP = 3
POLICY = {
    "rules": [
        {
            "rulePriority": 1,
            "description": f"Keep the last {KEEP} images (C38)",
            "selection": {
                "tagStatus": "any",
                "countType": "imageCountMoreThan",
                "countNumber": KEEP,
            },
            "action": {"type": "expire"},
        }
    ]
}
_IMAGE_URI = re.compile(
    r"[0-9]{12}\.dkr\.ecr\.[a-z0-9-]+\.amazonaws\.com/"  # <account>.dkr.ecr.<region>...
    r"([a-z0-9._/-]+)"  # the repository name
    r"(?::[\w.-]+)?(?:@sha256:[0-9a-f]{64})?"  # then a tag, a digest or both
)


def repository_name(image_uri: str) -> str:
    match = _IMAGE_URI.fullmatch(image_uri)
    if match is None:
        # Never echo the URI: its registry host is the account ID.
        raise ValueError("the function's image is not in a private ECR repository")
    return match.group(1)


def main(session=None) -> int:
    try:
        if session is None:
            session = boto3.Session(
                profile_name=os.environ.get("AWS_PROFILE") or "lusot",
                region_name="ap-southeast-1",
            )
        function = session.client("cloudformation").describe_stack_resource(
            StackName=STACK, LogicalResourceId=FUNCTION
        )["StackResourceDetail"]["PhysicalResourceId"]
        code = session.client("lambda").get_function(FunctionName=function)["Code"]
        name = repository_name(code["ImageUri"])
        session.client("ecr").put_lifecycle_policy(
            repositoryName=name, lifecyclePolicyText=json.dumps(POLICY)
        )
    except ClientError as exc:
        error = exc.response["Error"]["Code"]
        status = exc.response["ResponseMetadata"]["HTTPStatusCode"]
        print(
            f"AWS error in {exc.operation_name}: {error} (HTTP {status})",
            file=sys.stderr,
        )
        return 1
    except BotoCoreError as exc:
        print(f"AWS error: {type(exc).__name__}", file=sys.stderr)
        return 1
    print(f"repository: {name}")
    print(f"lifecycle: keep {KEEP}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
