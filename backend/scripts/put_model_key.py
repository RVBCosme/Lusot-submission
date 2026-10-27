# /// script
# requires-python = ">=3.13,<3.14"
# dependencies = ["boto3[crt]>=1.43.120"]
# ///
"""Store the Meta key in SSM Parameter Store (spec §3.5, C16).

CloudFormation can't create a SecureString, so this script does it once. It reads
MODEL_API_KEY, writes /lusot/meta/model-api-key as a SecureString under the AWS managed
key aws/ssm, then reads it back with decryption and compares the two in memory.

It prints the parameter's name, its type and the value's length, never the value. An AWS
error is reported by its code and HTTP status only: its message can carry an ARN, and an
ARN carries the account ID.

boto3 comes with its CRT extra: the lusot profile signs in with `aws login`, and
botocore's provider for those credentials needs the CRT.

Usage, as one PowerShell command (the shell's own copy of MODEL_API_KEY may be stale):
    $env:MODEL_API_KEY = [Environment]::GetEnvironmentVariable('MODEL_API_KEY','User');
    uv run backend/scripts/put_model_key.py
Exit codes: 0 stored and read back; 1 an AWS error or a read-back mismatch;
2 the key is missing or too short.
"""

from __future__ import annotations

import os
import sys

import boto3
from botocore.exceptions import BotoCoreError, ClientError

PARAM = "/lusot/meta/model-api-key"
MIN_KEY_LENGTH = 20  # as in the analysis stub; the real key has 48 characters (spec A8)


def main(ssm=None) -> int:
    key = os.environ.get("MODEL_API_KEY", "")
    if len(key) < MIN_KEY_LENGTH:
        print(
            f"MODEL_API_KEY is missing or too short: length {len(key)},"
            f" at least {MIN_KEY_LENGTH} needed",
            file=sys.stderr,
        )
        return 2
    try:
        if ssm is None:
            # Always lusot: a stray AWS_PROFILE could store the key in another account.
            session = boto3.Session(profile_name="lusot", region_name="ap-southeast-1")
            ssm = session.client("ssm")
        ssm.put_parameter(
            Name=PARAM,
            Value=key,
            Type="SecureString",
            KeyId="alias/aws/ssm",
            Overwrite=True,
            Tier="Standard",
        )
        stored = ssm.get_parameter(Name=PARAM, WithDecryption=True)["Parameter"]
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
    matches = stored["Value"] == key
    print(
        f"stored {PARAM} ({stored['Type']}), length {len(key)},"
        f" read-back matches: {matches}"
    )
    return 0 if matches else 1


if __name__ == "__main__":
    raise SystemExit(main())
