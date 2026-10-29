"""The offline runner: the pipeline on one local photo, live or replayed (spec §3.7).

Run from backend/analysis:

    uv run python probes/run_pipeline.py live <photo> [--data-dir DIR]
    uv run python probes/run_pipeline.py replay <photo> <run folder>

- live: the pipeline on the photo, face-blurred first, with the key from
  MODEL_API_KEY. It spends Meta credits: SAM for the 5 phrases the reading uses,
  never `face` or `license plate` (C66), and one Muse Spark answer. It sets no
  deadline (C84). What the models return, Muse Spark's reason included (C62), is
  saved to DIR/runs/<YYYY-MM-DD>/<photo stem>-<HHMMSS>. DIR defaults to
  LUSOT_DATA_DIR, and one inside the repo is refused, so nothing is saved in the repo
  (C8, C30, R111).
- replay: the pipeline again, from a run folder, with no key and no Meta call. It
  says whether the outcome is the saved one (B3).

Before any file is opened or listed, it refuses a path inside a folder named sealed
(C66), a live run on a STURM photo (C87), and a data folder inside the repo (R111).
It prints counts and timings only: never the answer, its reason or the key, and every
line masks runs of 12 digits.

Exit codes:
- 0: done
- 1: the replay's outcome isn't the saved one
- 2: refused: a sealed path, a STURM photo, a data folder inside the repo, a
  missing, short or rejected key, or another photo's outputs. argparse's own usage
  errors exit 2 too.
- 3: the run couldn't read or write what it needed. It prints `failed:` and the
  error's class only, never a path or the error's text (R110).
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from lusot_analysis.meta_client import MetaClient, MissingApiKey
from lusot_analysis.pipeline import READING_PHRASES, PipelineRun, run_pipeline
from lusot_analysis.pipeline.saved import (
    PhotoMismatch,
    RecordingClient,
    SavedOutputsClient,
)
from lusot_analysis.pipeline.types import ModelKeyRejected
from lusot_analysis.prompts import load_prompt

# The repo's prompts. Only package code must not walk up from its own file, and the
# runner runs only in the repo.
PROMPTS = Path(__file__).resolve().parents[1] / "prompts"
REPO = Path(__file__).resolve().parents[3]  # above probes/, analysis/ and backend/
DATA_DIR = r"C:\Systems\Lusot\lusot-data"  # when LUSOT_DATA_DIR is unset
_ACCOUNT_ID = re.compile(r"[0-9]{12}")


def say(line: str) -> None:
    """Print a line, with every run of 12 digits masked as <account>."""
    print(_ACCOUNT_ID.sub("<account>", line), flush=True)


def refuse_sealed(*paths: Path) -> None:
    """Exit 2 when a path lies inside a folder named sealed, in any case (C66).

    It runs before any file is opened or listed.
    """
    if any(_inside(path, "sealed") for path in paths):
        say("refused: path inside a folder named sealed")
        raise SystemExit(2)


def refuse_sturm_live(photo: Path) -> None:
    """Exit 2 when the photo lies inside sturm_flooddepth, in any case (C87).

    STURM photos stay offline, so a live run, which sends the photo to Meta, refuses
    them. A replay makes no Meta call, so it doesn't call this.
    """
    if _inside(photo, "sturm_flooddepth"):
        say("refused: STURM photos stay offline")
        raise SystemExit(2)


def refuse_data_in_repo(data_dir: Path) -> None:
    """Exit 2 when the data folder, resolved, lies inside the repo (spec §3.7, R111).

    A run folder holds masks and Muse Spark's reason (C62), and runs/ isn't
    git-ignored. It runs after refuse_sealed, which must see the folder before
    anything resolves it.
    """
    if data_dir.resolve().is_relative_to(REPO):
        say("refused: the data folder is inside the repo")
        raise SystemExit(2)


def _inside(path: Path, folder: str) -> bool:
    """True when a part of `path` is `folder`, ignoring case.

    The path is checked first as written, made absolute, so a path that names the
    folder never reaches the disk: on Windows, resolving opens what exists of it.
    Then it is checked resolved, so `..` and links can't hide the folder.
    """
    named = folder in (part.lower() for part in path.absolute().parts)
    return named or folder in (part.lower() for part in path.resolve().parts)


def make_client() -> MetaClient:
    """The Meta client, with the key from MODEL_API_KEY. Tests replace it.

    A missing key, or one under 20 characters, raises MissingApiKey before any
    network use, and the message never holds the key.
    """
    return MetaClient()


def live(photo: Path, data_dir: Path) -> tuple[Path, PipelineRun]:
    """Run the pipeline on `photo` with Meta's models, and save what they return.

    Returns the run folder, <data_dir>/runs/<YYYY-MM-DD>/<photo stem>-<HHMMSS> on
    the local clock when the run began, and the run. A key or account Meta rejects
    raises ModelKeyRejected (C73), and nothing is saved.
    """
    refuse_sealed(photo, data_dir)
    refuse_data_in_repo(data_dir)
    refuse_sturm_live(photo)
    started = datetime.now()
    prompt = load_prompt(PROMPTS)
    client = RecordingClient(make_client())
    run = run_pipeline(photo.read_bytes(), client, prompt, phrases=READING_PHRASES)
    day, stamp = started.strftime("%Y-%m-%d"), started.strftime("%H%M%S")
    run_dir = data_dir / "runs" / day / f"{photo.stem}-{stamp}"
    client.save(run_dir, photo=photo, prompt=prompt, run=run)
    return run_dir, run


def replay(photo: Path, run_dir: Path) -> PipelineRun:
    """Run the pipeline on `photo` again, from the outputs saved in `run_dir` (B3).

    It needs no key and makes no Meta call. Outputs saved for another photo raise
    PhotoMismatch.
    """
    refuse_sealed(photo, run_dir)
    data = photo.read_bytes()
    client = SavedOutputsClient(run_dir, data)
    return run_pipeline(data, client, load_prompt(PROMPTS), phrases=READING_PHRASES)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    live_command = commands.add_parser("live", help="run with Meta's models (paid)")
    live_command.add_argument("photo", type=Path)
    live_command.add_argument(
        "--data-dir", type=Path, help="where runs/ goes; default: LUSOT_DATA_DIR"
    )
    replay_command = commands.add_parser("replay", help="rerun a saved run (free)")
    replay_command.add_argument("photo", type=Path)
    replay_command.add_argument("run_dir", type=Path)
    args = parser.parse_args(argv)

    try:
        if args.command == "live":
            data_dir = args.data_dir or Path(
                os.environ.get("LUSOT_DATA_DIR") or DATA_DIR
            )
            _, run = live(args.photo, data_dir)
        else:
            run = replay(args.photo, args.run_dir)
            saved = json.loads((args.run_dir / "run.json").read_text(encoding="utf-8"))
    except SystemExit as exc:  # a refusal, which said why
        return exc.code
    except MissingApiKey:
        say("refused: MODEL_API_KEY is missing or too short")
        return 2
    except ModelKeyRejected as exc:  # C73
        say(f"refused: Meta rejected the key or the account (HTTP {exc.status})")
        return 2
    except PhotoMismatch:  # a ValueError, so before the next clause
        say("refused: saved outputs belong to another photo")
        return 2
    except (OSError, ValueError) as exc:
        # R110: the class only, as an error's text can hold a path.
        say(f"failed: {type(exc).__name__}")
        return 3
    _print_run(run)
    if args.command == "live":
        return 0
    same = dataclasses.asdict(run.outcome) == saved["outcome"]
    say(f"same as saved: {same}")
    return 0 if same else 1


def _print_run(run: PipelineRun) -> None:
    """The outcome and its level, then the log's counts and timings (spec §3.7).

    The log never holds the answer or its reason (C62), so neither is printed.
    """
    outcome, log = run.outcome, run.log
    level = "" if outcome.level is None else f", level {outcome.level}"
    say(f"outcome: {outcome.log_name}{level}")
    say(f"meta_calls: {log['meta_calls']}")
    for phrase, count in log.get("instances", {}).items():
        say(f"SAM {phrase}: instances {count}, {log['sam_ms'][phrase]} ms")
    if "spark_ms" in log:
        tokens = f"tokens {log['input_tokens']} in, {log['output_tokens']} out"
        say(f"Muse Spark: {log['spark_ms']} ms, {tokens}")
    if "drops" in log:
        say(f"drops: {json.dumps(log['drops'], sort_keys=True)}")


if __name__ == "__main__":
    sys.exit(main())
