# /// script
# requires-python = ">=3.13,<3.14"
# dependencies = ["boto3[crt]>=1.43.120"]
# ///
"""Set the Meta spend stop, /lusot/spend/stop-usd, never above $140 (C527, C528).

Rene or the tracker runs it with rene-dev's credentials at the submission deploy on
Nov 4: `--usd 140` raises the build phase's $60 to $140 through judging, which keeps
at least $80 of the $150 credit for the demo, the video and judges' live runs. It never
runs on its own: a pause at $60 during the build waits for the tracker to ask Rene.

It refuses a value above 140, or below what the counter already holds, and then
writes nothing. Otherwise it puts the parameter with Overwrite=True and prints the old
and new values. A deploy that updates the parameter puts it back to the template's 60,
which only pauses spending sooner, so it runs again after any later deploy
(docs/operations.md).

spend.py comes from backend/analysis, loaded by path, so the scripts and the Lambda
share one definition. The counter's table is LIMITS_TABLE_NAME, or else the lusot
stack's LimitsTable. An AWS error is reported by its code and HTTP status only.

boto3 comes with its CRT extra: the lusot profile signs in with `aws login`, and
botocore's provider for those credentials needs the CRT.

Usage, from the repo root: uv run backend/scripts/set_spend_stop.py --usd 140
Exit codes: 0 set; 1 an AWS error; 2 refused, nothing written.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from decimal import Decimal
from pathlib import Path

from botocore.exceptions import BotoCoreError, ClientError

SPEND_PY = Path(__file__).resolve().parents[1] / "analysis/src/lusot_analysis/spend.py"
MAX_STOP_USD = Decimal(140)  # Rene's limit: $10 under the $150 of credit (C528)


def _load_spend():
    """backend/analysis's spend.py, by path: it needs only boto3."""
    spec = importlib.util.spec_from_file_location("lusot_spend", SPEND_PY)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


spend = _load_spend()


def main(argv: list[str] | None = None, *, session=None) -> int:
    parser = argparse.ArgumentParser(
        description="Set the Meta spend stop (C528), never above 140."
    )
    parser.add_argument("--usd", required=True, help="the stop in USD, such as 140")
    args = parser.parse_args(argv)
    usd = spend.parse_usd(args.usd)
    if usd is None:
        print("--usd must be an amount in USD, such as 140", file=sys.stderr)
        return 2
    if usd > MAX_STOP_USD:
        print(f"refused: ${usd} is above 140; nothing written", file=sys.stderr)
        return 2
    try:
        session = spend.operator_session() if session is None else session
        ssm = session.client("ssm")
        old = ssm.get_parameter(Name=spend.SPEND_STOP_PARAM)["Parameter"]["Value"]
        total = spend.spend_total(
            ddb=session.client("dynamodb", config=spend.SPEND_CONFIG),
            table=spend.deployed_limits_table(session),
        )
        if usd < total:
            print(
                f"refused: ${usd} is below the ${total} spent; nothing written",
                file=sys.stderr,
            )
            return 2
        ssm.put_parameter(
            Name=spend.SPEND_STOP_PARAM, Value=str(usd), Type="String", Overwrite=True
        )
    except (BotoCoreError, ClientError) as exc:
        print(spend.aws_error(exc), file=sys.stderr)
        return 1
    print(f"{spend.SPEND_STOP_PARAM}: {old} -> {usd} (spent so far ${total})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
