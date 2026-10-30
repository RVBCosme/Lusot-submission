"""The offline runner: the pipeline on one local photo, live or replayed (spec §3.7).

Run from backend/analysis:

    uv run python probes/run_pipeline.py live <photo> [--data-dir DIR]
        [--run-dir DIR] [--geometry on|off] [--effort E] [--drawing D]
        [--sam-from RUN_DIR]
    uv run python probes/run_pipeline.py replay <photo> <run folder>

- live: the pipeline on the photo, face-blurred first, with the key from
  MODEL_API_KEY. It spends Meta credits: SAM for the 5 phrases the reading uses,
  never `face` or `license plate` (C66), and one Muse Spark answer. It sets no
  deadline (C84). What the models return, Muse Spark's reason included (C62), is
  saved to the run folder: --run-dir, or DIR/runs/<YYYY-MM-DD>/<photo stem>-<HHMMSS>.
  DIR defaults to LUSOT_DATA_DIR. A data or run folder inside the repo is refused,
  so nothing is saved in the repo (C8, C30, R111, R131).
  - Geometry is on unless --geometry off (C309). The live tuning sets the cutoffs;
    --effort (one of meta_client's REASONING_EFFORTS, or `default`, which sends
    none) and --drawing (one of annotate's DRAWINGS) change what Muse Spark is sent
    (C312, C325). run.json records all of it (v0.7 item 10.1).
  - --sam-from reuses that run folder's SAM outputs, for the same photo, and pays
    for Muse Spark alone (C312).
  - What it pays goes to MS4's spend counter (C527): the counter is read first,
    with the lusot profile, and a counter that is unseeded, unreadable or at its
    stop refuses the run. The cost is recorded after the save. The profile's
    `aws login` credentials need botocore's CRT, so a live run adds
    `--with "botocore[crt]==1.43.120"` after `uv run`.
- replay: the pipeline again, from a run folder, with no key and no Meta call, and
  with the geometry setting and tuning it was saved with: geometry off and START
  for an MS3a run, which recorded neither. It says whether the outcome is the saved
  one (B3).

Before any file is opened or listed, it refuses a path inside a folder named sealed
(C66), a live run on a STURM photo (C87), and a data or run folder inside the repo
(R111, R131). It prints counts and timings only: never the answer, its reason or the
key, and every line masks runs of 12 digits.

Exit codes:
- 0: done
- 1: the replay's outcome isn't the saved one, or the run was saved under other C56
  or C70 values than the live ones (R144)
- 2: refused: a sealed path, a STURM photo, a data or run folder inside the repo, a
  run folder that already exists, a missing, short or rejected key, another
  photo's outputs, or a spend counter that can't take the run. argparse's own usage
  errors exit 2 too, an unknown --effort, --drawing or --geometry among them (R146).
- 3: the run couldn't read or write what it needed, a run.json with a missing or
  unknown key among them. It prints `failed:` and the error's class only, never a
  path or the error's text (R110). A cost the spend counter couldn't record exits 3
  too, with one spend_error line holding the amount, for spend.py's add (R126).
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

from lusot_analysis.annotate import DRAWINGS

# check_before_paying is a seam, as make_client is: tests replace it (C527).
from lusot_analysis.laptop_spend import (
    CountedClient,
    SpendCounter,
    check_before_paying,
)
from lusot_analysis.meta_client import REASONING_EFFORTS, MetaClient, MissingApiKey
from lusot_analysis.pipeline import (
    READING_PHRASES,
    PipelineRun,
    references,
    run_pipeline,
)
from lusot_analysis.pipeline.saved import (
    PhotoMismatch,
    RecordingClient,
    SavedOutputsClient,
    SavedSamLiveJudge,
    rebuild_outcome,
    run_config,
    saved_config,
)
from lusot_analysis.pipeline.types import ModelKeyRejected
from lusot_analysis.prompts import load_prompt
from lusot_analysis.tuning import TUNING, Tuning

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
    """True when a part of `path` names `folder` as Windows reads it: in any case, by
    its name before any ":", and without trailing dots and spaces. So the NTFS stream
    `sealed::$INDEX_ALLOCATION`, `sealed.` and `sealed ` all count (R156), as in
    MS2's is_sealed_name (eval/data/guards.py).

    The path is checked first as written, made absolute, so a path that names the
    folder never reaches the disk: on Windows, resolving opens what exists of it.
    Then it is checked resolved, so `..` and links can't hide the folder.
    """

    def names(checked: Path) -> bool:
        return any(
            part.split(":", 1)[0].rstrip(". ").casefold() == folder
            for part in checked.parts
        )

    return names(path.absolute()) or names(path.resolve())


def make_client() -> MetaClient:
    """The Meta client, with the key from MODEL_API_KEY. Tests replace it.

    A missing key, or one under 20 characters, raises MissingApiKey before any
    network use, and the message never holds the key.
    """
    return MetaClient()


def live(
    photo: Path,
    data_dir: Path,
    *,
    run_dir: Path | None = None,
    geometry_in_level: bool = True,
    tuning: Tuning = TUNING,
    sam_from: Path | None = None,
    spend: SpendCounter | None = None,
    source: str = "run_pipeline",
) -> tuple[Path, PipelineRun]:
    """Run the pipeline on `photo` with Meta's models, and save what they return.

    Returns the run folder and the run. The folder is `run_dir`, or else
    <data_dir>/runs/<YYYY-MM-DD>/<photo stem>-<HHMMSS> on the local clock when the run
    began. One that already exists exits 2 before any client is built, so nothing is
    paid for that the save would then lose. run.json records `geometry_in_level`,
    `tuning` and the rest of run_config's settings. With `sam_from`, a run folder for
    the same photo, SAM's results come from there and only Muse Spark is paid for
    (C312); other outputs there raise PhotoMismatch. A key or account Meta rejects
    raises ModelKeyRejected (C73), and nothing is saved.

    The run's Meta cost goes to MS4's spend counter as `source` (C527). `spend` is
    the counter a caller has already checked, as dev_eval.py's run does once for its
    rows; without one, check_before_paying reads it here, after the refusals and
    before any client is built, and exits 2 when it can't take the run. The cost is
    recorded once the run is saved, or once it fails after paying, so a call paid for
    is recorded either way; a failed record exits 3 (SpendNotRecorded), with the run
    folder kept.
    """
    folders = [folder for folder in (run_dir, sam_from) if folder is not None]
    refuse_sealed(photo, data_dir, *folders)
    for folder in (data_dir, *folders):
        refuse_data_in_repo(folder)
    refuse_sturm_live(photo)
    started = datetime.now()
    if run_dir is None:
        day, stamp = started.strftime("%Y-%m-%d"), started.strftime("%H%M%S")
        run_dir = data_dir / "runs" / day / f"{photo.stem}-{stamp}"
    if run_dir.exists():
        say("refused: the run folder already exists")
        raise SystemExit(2)
    prompt = load_prompt(PROMPTS)
    data = photo.read_bytes()
    saved = None if sam_from is None else SavedOutputsClient(sam_from, data)
    if spend is None:
        spend = check_before_paying()
    model = CountedClient(make_client())
    client = RecordingClient(
        model if saved is None else SavedSamLiveJudge(saved, model)
    )
    try:
        run = run_pipeline(
            data,
            client,
            prompt,
            phrases=READING_PHRASES,
            geometry_in_level=geometry_in_level,
            tuning=tuning,
        )
        config = run_config(
            geometry_in_level=geometry_in_level,
            tuning=tuning,
            sam_from=saved is not None,
        )
        client.save(run_dir, photo=photo, prompt=prompt, run=run, config=config)
    finally:  # what was paid for, saved or not (R126)
        spend.record_after(model.take(), source)
    return run_dir, run


def replay(photo: Path, run_dir: Path) -> PipelineRun:
    """Run the pipeline on `photo` again, from the outputs saved in `run_dir` (B3).

    It needs no key and makes no Meta call. It runs with the geometry setting and
    tuning run.json records, or geometry off and START for an MS3a run. Outputs saved
    for another photo raise PhotoMismatch. A run saved under other C56 or C70 values
    than the live constants exits 1, since its boxes would be numbered differently
    (R144).
    """
    refuse_sealed(photo, run_dir)
    data = photo.read_bytes()
    client = SavedOutputsClient(run_dir, data)
    record = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    geometry_in_level, tuning = saved_config(record)
    cuts = (tuning.min_wheel_side_px, tuning.max_vehicles, tuning.max_people)
    live_cuts = (
        references.MIN_WHEEL_SIDE_PX,
        references.MAX_VEHICLES,
        references.MAX_PEOPLE,
    )
    if cuts != live_cuts:
        say("refused: saved under other C56/C70 values")
        raise SystemExit(1)
    return run_pipeline(
        data,
        client,
        load_prompt(PROMPTS),
        phrases=READING_PHRASES,
        geometry_in_level=geometry_in_level,
        tuning=tuning,
    )


def main(argv: list[str] | None = None, *, tuning: Tuning = TUNING) -> int:
    """The commands. `tuning` is what a live run starts from, before its flags.

    A test that pins start values passes START, since a default bound at import
    can't be patched (R128). A replay takes its run's own tuning.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    live_command = commands.add_parser("live", help="run with Meta's models (paid)")
    live_command.add_argument("photo", type=Path)
    live_command.add_argument(
        "--data-dir", type=Path, help="where runs/ goes; default: LUSOT_DATA_DIR"
    )
    live_command.add_argument(
        "--run-dir", type=Path, help="the run folder; default: one under runs/"
    )
    live_command.add_argument(
        "--geometry", choices=("on", "off"), default="on", help="default: on"
    )
    live_command.add_argument(
        "--effort",
        choices=(*REASONING_EFFORTS, "default"),
        help="Muse Spark's reasoning effort; `default` sends none; default: tuning's",
    )
    live_command.add_argument(
        "--drawing", choices=DRAWINGS, help="the boxes' drawing; default: tuning's"
    )
    live_command.add_argument(
        "--sam-from",
        type=Path,
        help="a run folder whose SAM outputs to reuse: pays for Muse Spark only",
    )
    replay_command = commands.add_parser("replay", help="rerun a saved run (free)")
    replay_command.add_argument("photo", type=Path)
    replay_command.add_argument("run_dir", type=Path)
    args = parser.parse_args(argv)

    sam_from = args.command == "live" and args.sam_from is not None
    try:
        if args.command == "live":
            data_dir = args.data_dir or Path(
                os.environ.get("LUSOT_DATA_DIR") or DATA_DIR
            )
            if args.effort is not None:
                effort = None if args.effort == "default" else args.effort
                tuning = dataclasses.replace(tuning, reasoning_effort=effort)
            if args.drawing is not None:
                tuning = dataclasses.replace(tuning, drawing=args.drawing)
            _, run = live(
                args.photo,
                data_dir,
                run_dir=args.run_dir,
                geometry_in_level=args.geometry == "on",
                tuning=tuning,
                sam_from=args.sam_from,
            )
        else:
            run = replay(args.photo, args.run_dir)
            saved = json.loads((args.run_dir / "run.json").read_text(encoding="utf-8"))
            saved_outcome = rebuild_outcome(saved["outcome"])
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
    except (OSError, ValueError, KeyError, TypeError) as exc:
        # R110: the class only, as an error's text can hold a path. A run.json with a
        # missing or unknown key raises KeyError or TypeError.
        say(f"failed: {type(exc).__name__}")
        return 3
    _print_run(run, sam_from=sam_from)
    if args.command == "live":
        return 0
    # Rebuilt, so an MS3a run isn't judged by the keys its outcome lacks (R141). A
    # real change, as step 3 now runs with geometry off too, still shows (P12).
    same = run.outcome == saved_outcome
    say(f"same as saved: {same}")
    return 0 if same else 1


def _print_run(run: PipelineRun, *, sam_from: bool = False) -> None:
    """The outcome and its level, then the log's counts, timings and settings.

    The log never holds the answer or its reason (C62), so neither is printed. A key
    is printed only once its step has run: `level_from` on a level, and
    `wheels_measured` and `geometry_checks` once geometry has (spec §3.7, C316).

    `meta_calls` counts the pipeline's calls, served from a saved run or not. With
    `sam_from`, SAM's came from a saved run, so only the judge call beyond them, if
    the run got that far, was paid for, and that count is printed too.
    """
    outcome, log = run.outcome, run.log
    level = "" if outcome.level is None else f", level {outcome.level}"
    say(f"outcome: {outcome.log_name}{level}")
    if "level_from" in log:
        say(f"level_from: {log['level_from']}")
    say(f"meta_calls: {log['meta_calls']}")
    if sam_from:
        say("sam_from: True")
        say(f"paid_calls: {max(log['meta_calls'] - len(READING_PHRASES), 0)}")
    for key in ("reasoning_effort", "drawing_version"):
        if key in log:
            say(f"{key}: {log[key]}")
    for phrase, count in log.get("instances", {}).items():
        say(f"SAM {phrase}: instances {count}, {log['sam_ms'][phrase]} ms")
    if "spark_ms" in log:
        tokens = f"tokens {log['input_tokens']} in, {log['output_tokens']} out"
        say(f"Muse Spark: {log['spark_ms']} ms, {tokens}")
        say(f"reasoning_tokens: {log['reasoning_tokens']}")
    if "drops" in log:
        say(f"drops: {json.dumps(log['drops'], sort_keys=True)}")
    if "wheels_measured" in log:
        say(f"wheels_measured: {log['wheels_measured']}")
    if "geometry_checks" in log:
        say(f"geometry_checks: {json.dumps(log['geometry_checks'], sort_keys=True)}")


if __name__ == "__main__":
    sys.exit(main())
