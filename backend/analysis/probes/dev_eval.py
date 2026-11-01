"""Development runs, and their rows for MS6's harness (C312, C315, C321, C327).

Run from backend/analysis:

    uv run python probes/dev_eval.py run --manifest F [--photos DIR] [--limit N]
        [--effort E] [--drawing D] [--repeat N] [--sam-from SETTINGS] [--yes]
    uv run python probes/dev_eval.py export --set-a F --m8 F --a-neg F --out DIR
        --rules-version V [--set NAME=VALUE ...] [--runs SETTINGS] [--datasets JSON]
        [--geometry-default on|off|dropped] [--dropped-reason TOKEN] [--replay FILE]

- run: the offline runner's live run (probes/run_pipeline.py) for each of a
  manifest's rows without a saved run in its folder,
  <data>/runs/dev/<set>/<settings>[_r<repeat>]/<photo_id>. <settings> names the
  reasoning effort and the drawing, so runs at different settings never share a
  folder (finding 5). They are the tuning's, changed by --effort (`default` sends
  none) and --drawing. --sam-from reuses SAM's outputs from that sibling settings
  folder and pays for Muse Spark alone; a row without them runs in full. --limit runs
  only the first N rows still to run, and --photos is the photo folder, relative to
  the manifest's. It spends Meta credits, so it prints the count and the estimated
  cost first ($0.03 a full photo, $0.015 for Muse Spark alone) and stops there unless
  given --yes. Then MS4's spend counter is read once, as the runner reads it, and
  each row's cost is recorded once its run is saved (C527). After the runs it prints
  counts only, never an outcome, so no Set A result shows before v0.7 (C322).
- export: MS6's §4.3 rows from the saved runs, through lusot_analysis.export, into
  --out: run.json, set_a.jsonl and a_neg.jsonl. Each saved run is replayed with no
  Meta call, once per configuration: `landmark` and `geometry`, or `landmark` alone
  with --geometry-default dropped (MS6's C418). --runs names the settings folder,
  the tuning's by default. A run saved at another effort or drawing than the
  tuning's is refused, so efforts never mix (finding 5), and so are runs that
  differ from each other in what run.json's `frozen` states once. --set NAME=VALUE
  changes a Tuning field for the replays (`default` for no reasoning effort), and
  `frozen` records every numeric field (R153). --replay adds Task 13's event-replay
  outcomes to every Set A row (MS6's C425). Labels hold only the harness's
  --label-words (C420), fetched by running `eval/run_eval.py --label-words`, never by
  importing it (C321). Without the harness, the Set A rows wait and the rest still
  write (R133). A row whose saved answer MS6's loader would refuse carries none
  (P13, R152). It prints counts only, then the harness command to run next.

<data> is LUSOT_DATA_DIR, or the runner's default. Before anything is opened, every
path given is refused when it lies inside a folder named sealed, as is every photo a
manifest names and every run folder (C66). run's data folder must lie outside the
repo (R131). export's --out must lie under the data folder, outside its runs/ folder
and outside the repo, so no row is written into the repo or beside the raw outputs. It
holds no set_b.jsonl, and no set_a.jsonl or a_neg.jsonl that this export won't rewrite.
--runs and --sam-from are single folder names. Nothing printed holds a photo's name,
a path, a label, an answer or a key, and every line masks runs of 12 digits.

Exit codes: 0 done; 2 refused, invalid input, waiting for the harness, a paid run
without --yes, or a spend counter that can't take the run; 3 the run couldn't read
or write what it needed, with the error's class only (R110), or a cost the spend
counter couldn't record, as one spend_error line (R126). argparse's own usage errors
exit 2 too.
"""

from __future__ import annotations

import argparse
import dataclasses
import importlib.util
import json
import math
import os
import re
import subprocess
import sys
from collections import Counter
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import NoReturn

from lusot_analysis import export
from lusot_analysis.annotate import DRAWINGS
from lusot_analysis.meta_client import REASONING_EFFORTS, MissingApiKey
from lusot_analysis.pipeline import references
from lusot_analysis.pipeline.saved import PhotoMismatch, saved_config
from lusot_analysis.pipeline.types import ModelKeyRejected
from lusot_analysis.prompts import load_prompt
from lusot_analysis.tuning import START, TUNING, Tuning


def _load_runner():
    """The offline runner, loaded from its file beside this one, as its tests load it."""
    path = Path(__file__).resolve().with_name("run_pipeline.py")
    spec = importlib.util.spec_from_file_location("run_pipeline", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = _load_runner()
say = runner.say
# The harness's one command, run as a subprocess only (C321, MS6's C400).
RUN_EVAL = runner.REPO / "eval" / "run_eval.py"
# The estimated cost of a photo's run: in full, and Muse Spark alone (C312).
FULL_PHOTO_USD = Decimal("0.03")
JUDGE_ONLY_USD = Decimal("0.015")
# Tuning fields --set can't change: C56's 40 px and C70's caps are constants that
# number the boxes, never swept (R144).
_FIXED_FIELDS = ("untuned", "min_wheel_side_px", "max_vehicles", "max_people")
# The drops before numbering (P2, P6), counted in export's printout.
_NUMBERING_DROPS = (
    "wheel_small",
    "wheel_unlinked",
    "vehicle_cap",
    "wheel_cap",
    "person_cap",
)
_TOKEN = re.compile("[a-z][a-z0-9_]{0,31}")
# A settings folder's name, as settings_name and --repeat make them: one name, with
# no separator, so --runs and --sam-from can't leave runs/dev/<set>/; no ":", which
# names an NTFS stream; and not ending in a dot, which Windows strips (R156).
_FOLDER = re.compile("[A-Za-z0-9_](?:[A-Za-z0-9_.-]*[A-Za-z0-9_-])?")
_MANILA = timezone(timedelta(hours=8))  # Manila keeps no daylight saving time


def settings_name(tuning: Tuning) -> str:
    """`<effort or default>_<drawing>`: the settings folder's name for `tuning`."""
    return f"{tuning.reasoning_effort or 'default'}_{tuning.drawing}"


def run_dir_for(
    data_dir: Path, row: Mapping, settings: str, *, repeat: int = 1
) -> Path:
    """<data_dir>/runs/dev/<row's set>/<settings>[_r<repeat>]/<photo_id>."""
    folder = settings if repeat == 1 else f"{settings}_r{repeat}"
    return data_dir / "runs" / "dev" / row["set"] / folder / row["photo_id"]


def read_manifest(path: Path, data_dir: Path, *, photos: str = "photos") -> list[dict]:
    """MS2's manifest at `path`, each row with its photo's path under `photo`.

    `photos` is the photo folder, relative to the manifest's folder: MS2's `photos`,
    or `commons-ph-floods\\images` for Task 16's Set C manifest. refuse_sealed runs on
    the manifest, the data folder and the photo folder before the manifest is opened,
    and on every photo it names before any is.
    """
    folder = path.parent / photos
    runner.refuse_sealed(path, data_dir, folder)
    rows = export.parse_manifest(path.read_text(encoding="utf-8"))
    for row in rows:
        row["photo"] = folder / row["photo_file"]
    runner.refuse_sealed(*(row["photo"] for row in rows))
    return rows


def label_words() -> frozenset[str] | None:
    """The words a committed label may hold, as `eval/run_eval.py --label-words`
    prints them, run once as a subprocess (MS6's C420). None when the harness isn't
    on the branch (R133). A harness that fails, or prints no word, is refused."""
    if not RUN_EVAL.is_file():
        return None
    done = subprocess.run(
        [sys.executable, "-I", "-B", str(RUN_EVAL), "--label-words"],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=runner.REPO,
        check=False,  # its exit code is read below
    )
    words = frozenset(done.stdout.split())
    if done.returncode != 0 or not words:
        _refuse("the harness's --label-words gave no words")
    return words


def run_command(args: argparse.Namespace, *, tuning: Tuning = TUNING) -> int:
    """`run`: a live run for each row without a saved run, after --yes."""
    data_dir = _data_dir()
    runner.refuse_sealed(args.manifest, data_dir)
    runner.refuse_data_in_repo(data_dir)  # R131
    rows = read_manifest(args.manifest, data_dir, photos=args.photos)
    if args.effort is not None:
        effort = None if args.effort == "default" else args.effort
        tuning = dataclasses.replace(tuning, reasoning_effort=effort)
    if args.drawing is not None:
        tuning = dataclasses.replace(tuning, drawing=args.drawing)
    settings = settings_name(tuning)
    pending = []
    for row in rows:
        run_dir = run_dir_for(data_dir, row, settings, repeat=args.repeat)
        runner.refuse_sealed(run_dir)  # a photo id can't lead into one (C66)
        if (run_dir / "run.json").is_file():
            continue
        if run_dir.exists():  # live() would refuse it, after the rows before it paid
            _refuse("a run folder without its run.json exists: remove it first")
        sam_from = None
        if args.sam_from is not None:
            sibling = run_dir_for(data_dir, row, args.sam_from)
            runner.refuse_sealed(sibling)
            if (sibling / "run.json").is_file():
                sam_from = sibling
        pending.append((row, run_dir, sam_from))
    saved = len(rows) - len(pending)
    pending = pending[: args.limit]
    for row, _, _ in pending:  # before anything is paid for, not row by row
        runner.refuse_sturm_live(row["photo"])
    judge_only = sum(1 for _, _, sam_from in pending if sam_from is not None)
    full = len(pending) - judge_only
    cost = FULL_PHOTO_USD * full + JUDGE_ONLY_USD * judge_only
    say(f"photos: {len(rows)} in the manifest, {saved} already saved")
    say(
        f"to run: {len(pending)} ({full} full, {judge_only} Muse Spark only),"
        f" estimated cost ${cost:.3f}"
    )
    if pending and not args.yes:
        say("stopped: add --yes to pay for these runs")
        return 2
    # MS4's spend counter, read once before any client; each row is recorded once its
    # run is saved (C527).
    spend = runner.check_before_paying() if pending else None
    for row, run_dir, sam_from in pending:
        runner.live(
            row["photo"],
            data_dir,
            run_dir=run_dir,
            tuning=tuning,
            sam_from=sam_from,
            spend=spend,
            source="dev_eval",
        )
    say(f"runs saved: {len(pending)}")
    return 0


def export_command(args: argparse.Namespace, *, tuning: Tuning = TUNING) -> int:
    """`export`: run.json, set_a.jsonl and a_neg.jsonl in --out, from saved runs.

    Every refusal comes before anything is written. Without the harness (R133), the
    Set A rows wait: run.json and a_neg.jsonl are written, and it exits 2.
    """
    data_dir = _data_dir()
    given = [args.set_a, args.m8, args.a_neg, args.out]
    if args.replay is not None:
        given.append(args.replay)
    runner.refuse_sealed(*given, data_dir)
    out = args.out.resolve()
    if out.is_relative_to(runner.REPO):
        _refuse("--out is inside the repo")
    if not out.is_relative_to(data_dir.resolve()):
        _refuse("--out must lie under the data folder")
    if out.is_relative_to((data_dir / "runs").resolve()):  # beside masks and reasons
        _refuse("--out must lie outside the runs folder")
    dropped = args.geometry_default == "dropped"
    if dropped != (args.dropped_reason is not None):
        _refuse(
            "--geometry-default dropped needs --dropped-reason, and only it takes one"
        )
    for text in args.set:
        tuning = _set_field(tuning, text)
    settings = args.runs or settings_name(tuning)
    datasets = _datasets(args.datasets)
    sides = {
        "set_a": read_manifest(args.set_a, data_dir),
        "a_neg": read_manifest(args.a_neg, data_dir),
    }
    for name, wanted in (("set_a", "A"), ("a_neg", "A-neg")):
        if any(row["set"] != wanted for row in sides[name]):
            _refuse(f"the {name} manifest holds a row of another set")
    m8 = export.parse_m8(args.m8.read_text(encoding="utf-8"))
    words = label_words() if sides["set_a"] else frozenset()
    if words is None:  # R133: the Set A rows wait for the harness
        del sides["set_a"]
    # Rows this export leaves in place would be scored beside its run.json: another
    # export's, or an earlier export's Set A or A-neg rows that it won't rewrite.
    if (args.out / "set_b.jsonl").exists():
        _refuse("--out holds another export's rows: use a new folder")
    for name in ("set_a", "a_neg"):
        if name not in sides and (args.out / f"{name}.jsonl").exists():
            _refuse(f"--out holds an earlier export's {name}.jsonl: use a new folder")
    if not any(sides.values()):
        if words is None:
            return _waiting()
        _refuse("the manifests hold no rows")
    configurations = {"landmark": False} if dropped else export.CONFIGURATIONS
    replays = {}
    if args.replay is not None and "set_a" in sides:
        replays = _read_replay(args.replay, sides["set_a"], configurations)
    saved = _saved_runs(sides, data_dir, settings, tuning)

    prompt = load_prompt(runner.PROMPTS)
    built: dict[str, list[dict]] = {name: [] for name in sides}
    tally: Counter[str] = Counter()
    checks: Counter[str] = Counter()
    drops = Counter(dict.fromkeys(_NUMBERING_DROPS, 0))
    for name, rows in sides.items():
        for row in rows:
            run_dir, record = saved[name, row["photo_id"]]
            runs = export.replay_configurations(
                row["photo"].read_bytes(),
                run_dir,
                prompt,
                tuning=tuning,
                configurations=configurations,
            )
            set_a = name == "set_a"
            labels = m8.get(row["photo_id"], []) if set_a else []
            # Without the harness only A-neg rows are left, and they hold no label.
            base = export.bridge_base(row, labels, words=words or frozenset())
            spark = _spark(run_dir)
            built_row = export.saved_row(
                base,
                runs,
                spark,
                record,
                prompt.schema,
                labels=labels,
                replay=replays.get(row["photo_id"]) if set_a else None,
            )
            built[name].append(built_row)
            # An answer was saved, but its row holds none (P13, R152).
            if built_row["answer"] is None and export.answer_data(spark) is not None:
                tally["withheld"] += 1
            # Task 6: these keys appear only once geometry has run.
            geometry = runs["geometry"].log if "geometry" in runs else {}
            tally["g4"] += geometry.get("drops", {}).get("wheel_methods_disagree", 0)
            tally["wheels"] += geometry.get("wheels_measured", 0)
            checks.update(geometry.get("geometry_checks", {}))
            numbered = runs["landmark"].log.get("drops", {})
            drops.update({cause: numbered.get(cause, 0) for cause in _NUMBERING_DROPS})
            if set_a:
                written = [
                    base["level_label_raw"],
                    base["passability_raw"],
                    *base["other_alerts_raw"],
                ]
                tally["marked"] += written.count(export.OTHER_WORDS)

    records = [record for _, record in saved.values()]
    sent = next((record for record in records if record["phrases"]), records[0])
    manifest = export.results_manifest(
        date=datetime.now(_MANILA).date().isoformat(),
        rules_version=args.rules_version,
        tuning=tuning,
        saved_run=sent,
        geometry_default=args.geometry_default,
        dropped_reason=args.dropped_reason,
        datasets=datasets,
    )
    args.out.mkdir(parents=True, exist_ok=True)
    _write(args.out / "run.json", json.dumps(manifest, indent=2) + "\n")
    for name, rows in built.items():
        _write(args.out / f"{name}.jsonl", "".join(json.dumps(r) + "\n" for r in rows))

    say("photos: " + ", ".join(f"{name} {len(rows)}" for name, rows in built.items()))
    say(f"g4_drops: {tally['g4']}")
    say(f"wheels_measured: {tally['wheels']}")
    say(f"geometry_checks: {json.dumps(checks, sort_keys=True)}")
    say(f"labels_as_other_words: {tally['marked']}")
    say(f"answers_withheld: {tally['withheld']}")
    say(f"drops_before_numbering: {json.dumps(drops, sort_keys=True)}")
    if words is None:
        return _waiting()
    say(
        "next: python eval/run_eval.py --from-saved --results <the --out folder> --write"
    )
    return 0


def main(argv: list[str] | None = None, *, tuning: Tuning = TUNING) -> int:
    """The commands. `tuning` is what each starts from, before its flags.

    A test that pins start values passes START, since a default bound at import
    can't be patched (R128).
    """
    args = _parser().parse_args(argv)
    try:
        if args.command == "run":
            return run_command(args, tuning=tuning)
        return export_command(args, tuning=tuning)
    except SystemExit as exc:  # a refusal, which said why
        return exc.code
    except export.InputError as exc:  # its message never holds a cell's text
        say(f"invalid: {exc}")
        return 2
    except MissingApiKey:
        say("refused: MODEL_API_KEY is missing or too short")
        return 2
    except ModelKeyRejected as exc:  # C73
        say(f"refused: Meta rejected the key or the account (HTTP {exc.status})")
        return 2
    except PhotoMismatch:  # a ValueError, so before the next clause
        say("refused: saved outputs belong to another photo")
        return 2
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        subprocess.SubprocessError,  # a --label-words that timed out among them
    ) as exc:
        # R110: the class only, as an error's text can hold a path or a value.
        say(f"failed: {type(exc).__name__}")
        return 3


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="live runs for a manifest's rows (paid)")
    run.add_argument("--manifest", type=Path, required=True)
    run.add_argument(
        "--photos",
        default="photos",
        help="the photo folder, relative to the manifest's; default: photos",
    )
    run.add_argument(
        "--limit", type=_positive, help="run only the first N rows still to run"
    )
    run.add_argument(
        "--effort",
        choices=(*REASONING_EFFORTS, "default"),
        help="Muse Spark's reasoning effort; `default` sends none; default: tuning's",
    )
    run.add_argument(
        "--drawing", choices=DRAWINGS, help="the boxes' drawing; default: tuning's"
    )
    run.add_argument("--repeat", type=_positive, default=1, help="a repeat's number")
    run.add_argument(
        "--sam-from",
        type=_folder,
        metavar="SETTINGS",
        help="a settings folder whose SAM outputs to reuse: pays for Muse Spark only",
    )
    run.add_argument("--yes", action="store_true", help="pay for the runs")
    rows = commands.add_parser("export", help="rows for MS6's harness (free)")
    for flag in ("--set-a", "--m8", "--a-neg", "--out"):
        rows.add_argument(flag, type=Path, required=True)
    rows.add_argument("--rules-version", required=True)
    rows.add_argument(
        "--set",
        action="append",
        default=[],
        metavar="NAME=VALUE",
        help="change a Tuning field for the replays",
    )
    rows.add_argument(
        "--runs",
        type=_folder,
        metavar="SETTINGS",
        help="the runs' settings folder; default: tuning's",
    )
    rows.add_argument("--datasets", default="{}", metavar="JSON")
    rows.add_argument(
        "--geometry-default", choices=("on", "off", "dropped"), default="on"
    )
    rows.add_argument("--dropped-reason", type=_token, metavar="TOKEN")
    rows.add_argument("--replay", type=Path, help="Task 13's replay.jsonl")
    return parser


def _positive(text: str) -> int:
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError("must be 1 or more")
    return value


def _token(text: str) -> str:
    """A lowercase token, so no free text reaches run.json."""
    if not _TOKEN.fullmatch(text):
        raise argparse.ArgumentTypeError("must be a lowercase token, such as a_reason")
    return text


def _folder(text: str) -> str:
    """One settings folder's name, such as default_boxes-v1: no separator, no `..`."""
    if not _FOLDER.fullmatch(text) or ".." in text:
        raise argparse.ArgumentTypeError(
            "must be one folder name, such as low_boxes-v1"
        )
    return text


def _refuse(message: str) -> NoReturn:
    say(f"refused: {message}")
    raise SystemExit(2)


def _waiting() -> int:
    say(
        "waiting: the Set A rows need the harness's --label-words, and"
        " eval/run_eval.py isn't on this branch (R133)"
    )
    return 2


def _data_dir() -> Path:
    return Path(os.environ.get("LUSOT_DATA_DIR") or runner.DATA_DIR)


def _set_field(tuning: Tuning, text: str) -> Tuning:
    """`tuning` with --set's NAME=VALUE applied, the value read as START's is typed."""
    name, equals, value = text.partition("=")
    settable = {field.name for field in dataclasses.fields(Tuning)}
    if not equals or name not in settable - set(_FIXED_FIELDS):
        _refuse(
            "--set takes NAME=VALUE for a Tuning field; untuned and C56's and C70's"
            " cuts can't be set (R144)"
        )
    if name == "reasoning_effort":
        if value != "default" and value not in REASONING_EFFORTS:
            _refuse(
                f"--set reasoning_effort takes default or one of {REASONING_EFFORTS}"
            )
        return dataclasses.replace(
            tuning, reasoning_effort=None if value == "default" else value
        )
    if name == "drawing" and value not in DRAWINGS:
        _refuse(f"--set drawing takes one of {DRAWINGS}")
    if isinstance(getattr(START, name), float):
        try:
            number = float(value)
        except ValueError:
            number = math.nan
        if not math.isfinite(number):
            _refuse(f"--set {name} takes a finite number")
        return dataclasses.replace(tuning, **{name: number})
    start = getattr(START, name)
    if isinstance(start, int) and not isinstance(start, bool):
        # An int cutoff, such as C92's person cutoff, takes a whole number from 0 up,
        # so it reaches the replay as an int and run.json records it (R153).
        if not (value.isascii() and value.isdigit()):
            _refuse(f"--set {name} takes a whole number from 0 up")
        return dataclasses.replace(tuning, **{name: int(value)})
    return dataclasses.replace(tuning, **{name: value})


def _datasets(text: str) -> dict:
    """--datasets, as a JSON object of MS6's shape, checked before anything else is
    read (an InputError, exit 2)."""
    try:
        datasets = json.loads(text)
    except json.JSONDecodeError:
        datasets = None
    if not isinstance(datasets, dict):
        _refuse("--datasets takes a JSON object")
    export.check_datasets(datasets)
    return datasets


def _read_replay(
    path: Path, set_a: list[dict], configurations: Mapping[str, bool]
) -> dict[str, dict[str, dict]]:
    """Task 13's replay.jsonl, by photo id: {configuration: its replay outcome}.

    Each line is {"photo_id": ..., "<configuration>_replay": item_fields, ...}. Every
    Set A row needs one replay outcome for each configuration, and nothing else, or
    it is refused (MS6's C425).
    """
    found = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            entry = json.loads(line)
            if not isinstance(entry, dict) or "photo_id" not in entry:
                raise ValueError("a replay line isn't an object with a photo_id")
            photo_id = entry.pop("photo_id")
            found[photo_id] = {
                key.removesuffix("_replay"): outcome for key, outcome in entry.items()
            }
    for row in set_a:
        replay = found.get(row["photo_id"])
        if replay is None or set(replay) != set(configurations):
            _refuse(
                "every Set A row needs its replay outcomes, one per configuration"
                " (MS6's C425)"
            )
    return found


def _saved_runs(
    sides: Mapping[str, list[dict]], data_dir: Path, settings: str, tuning: Tuning
) -> dict[tuple[str, str], tuple[Path, dict]]:
    """Each row's run folder and run.json, by (side, photo id).

    It refuses:
    - a row without a saved run
    - a run saved at another effort or drawing than the tuning's (finding 5)
    - a run saved under other C56 or C70 values than the live constants, since its
      boxes would be numbered differently, as the runner's replay refuses it (R144)
    - runs that differ from each other in the prompt, the models, the blur or the
      SAM phrases sent, which run.json's `frozen` states once. A run that stopped
      before the blur or before SAM is left out of those two.
    """
    saved = {}
    live_cuts = (
        references.MIN_WHEEL_SIDE_PX,
        references.MAX_VEHICLES,
        references.MAX_PEOPLE,
    )
    for name, rows in sides.items():
        for row in rows:
            run_dir = run_dir_for(data_dir, row, settings)
            runner.refuse_sealed(run_dir)  # a photo id can't lead into one (C66)
            if not (run_dir / "run.json").is_file():
                _refuse("a row has no saved run here: run `dev_eval.py run` first")
            record = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
            used = (record.get("reasoning_effort"), record.get("drawing_version"))
            if used != (tuning.reasoning_effort, tuning.drawing):
                _refuse(
                    "a saved run used another effort or drawing than the tuning's,"
                    " so efforts would mix (finding 5)"
                )
            _, saved_tuning = saved_config(record)
            cuts = (
                saved_tuning.min_wheel_side_px,
                saved_tuning.max_vehicles,
                saved_tuning.max_people,
            )
            if cuts != live_cuts:
                _refuse("a run was saved under other C56/C70 values (R144)")
            saved[name, row["photo_id"]] = (run_dir, record)
    sent = [record for _, record in saved.values()]
    kinds = {
        "prompt_version": [record["prompt_version"] for record in sent],
        "models": [record["models"] for record in sent],
        "blur_version": [record["blur_version"] for record in sent],
        "phrases": [record["phrases"] for record in sent if record["phrases"]],
    }
    for found in kinds.values():
        seen = {
            json.dumps(value, sort_keys=True) for value in found if value is not None
        }
        if len(seen) > 1:
            _refuse(
                "the saved runs differ in their prompt, models, blur or SAM phrases,"
                " which run.json states once"
            )
    return saved


def _spark(run_dir: Path) -> dict | None:
    """The run folder's spark.json, Muse Spark's reason and all, or None without one."""
    path = run_dir / "spark.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    sys.exit(main())
