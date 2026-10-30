r"""The sealed-run entry point (MS6's C412 and §4.5 step 6; MS3b's C329).

Rene alone runs it, once, on Nov 3, in his own PowerShell window, after MS2's audit
(MS6's §4.5). Claude builds and tests it on synthetic data only, and never runs it.
From the repo root, with MODEL_API_KEY set for that one command:

    uv run --locked --directory backend/analysis python probes/run_sealed.py
        <data>\sealed\run-1 --baseline <summary.json> --self-check-decided DATE
        --datasets JSON [--geometry-default on|off|dropped] [--dropped-reason TOKEN]
        [--resume RUN] [--rerun REASON] [--results DIR]

<data>\sealed\run-1 is the folder the archives were extracted into (MS6E-Q3), as
MS2's §5.9 lays them out: set_a\ (manifest.csv, m8.csv, photos\), a_neg\
(manifest.csv, photos\) and, when they exist, set_b\ (truth.csv, crops\) and set_d\
(set_d_log.csv, photos\). --baseline is the last development report's summary.json,
whose baseline pair and rules_version run.json takes (MS6's C424). The other flags are
run.json's, as dev_eval.py's export takes them, but --datasets is required and must
name a dataset, since run.json can't take MS2's versions later. Every path is
absolute, since uv's --directory changes the working folder.

In order (MS6's C412):
1. The folder: it reads only inside a folder named sealed, as written and resolved
   (MS2's require_sealed, twice), so it can't run on development data, as C66's
   runner can't run on sealed data. --results and --baseline inside one are refused.
   Only the strings are checked before step 2.
2. The console: stdin and stdout must both be one (MS2's console_ok, its C202).
3. The freeze (MS6's C413, C421): a tree with no changes, at the commit tagged
   freeze-1, or freeze-2 for the one disclosed rerun (--rerun REASON). git runs with
   no GIT_ variable, untracked files shown whatever its settings say, and no file
   flagged assume-unchanged or skip-worktree, so no setting hides a change.
4. The label words, from `python eval/run_eval.py --label-words` (MS6's C420), and the
   rules version, from its --rules-version, which must be --baseline's (MS6's C424),
   so the baseline was scored by the frozen harness's rules: without the harness,
   when it fails, or when the two versions differ, nothing in the folder is read.
5. The inputs, through export's path-free parsers (C315, C327). A file that breaks its
   format is named by its kind, and by its row where the parser names one, never by a
   cell's text. Every photo and crop must be there before anything is paid for. Then
   the run's lock, <folder>\outputs\run.lock, which the OS holds for this window
   until it ends: a second window, starting or resuming, is refused before anything
   is asked or sent, and a closed window's lock goes with it.
6. Rene's yes to the photos and crops to send and their estimated cost ($0.03 a photo,
   $0.0025 a SAM call). Then the labels that would be written as (other words) are
   counted, and any such count needs a second yes: those photos are excluded as
   unmapped (MS6's C420).
7. The run, its raw outputs under <folder>\outputs\<RUN> (rules §10), RUN being
   freeze-1, or freeze-2 for the rerun. Each Set A and A-neg photo goes once through
   the frozen pipeline, face blur first, with the 5 phrases the reading uses (C66),
   and is saved as the runner saves a run. Each Set B crop and Set D photo goes once
   through the face blur and SAM's floodwater, wheel and wheel rim. A photo or crop
   whose send Meta's service failed (an HTTP error after the client's retries, a
   timeout or a lost connection) is saved as failed, sent once more after the rest,
   into outputs\<RUN>\retry\, and counted; an invalid answer is never sent again
   (MS6E-Q6, default (a)). Three such sends in a row stop the run, as a lost
   connection would. A crop or Set D photo failed twice is exported with every
   variant of its wheels unmeasured as model_error, and sam_water_found null.
8. The export, once the run is complete: run.json, set_a.jsonl, a_neg.jsonl and, when
   they exist, set_b.jsonl and set_d.jsonl, through export's rows (MS6's §4.3), each
   configuration from replays of the saved outputs (C309, C315). run.json's
   service_retries counts the photos, crops and Set D photos retried in the whole
   run, resumes included (MS6E-Q6). --results defaults
   to the repo's eval/results, or eval/results/rerun with --rerun (MS6's C421); MS6's
   loader needs a rerun's folder named rerun, and only a rerun's.

A stop (a rejected key, Ctrl+C, a crash, Meta's service failing) is kept in the run's
state.json with its time and cause, and --resume RUN goes on as the same run: what was
saved is never sent again (MS6's C419). An item counts as saved once its record,
written last and whole, reads as a JSON object; one cut short is set aside, kept, and
sent again. A run that ended with no stop kept, as when its window closed, gets one at
its last saved item. A new run whose folder exists is refused, so nothing is paid for
twice. A resume must give the run's own settings.

It prints counts and timings only: never a photo's name, a path, a label, an answer,
a reason or a key, and every line masks runs of 12 digits.

Exit codes: 0 exported; 2 refused (a path, the console, the freeze, the harness or its
rules version, an input, another window's run, a no, a missing or rejected key); 3 a
stop or a failure, printed as its cause or its error's class only (R110). argparse's
own usage errors exit 2 too.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from collections import Counter
from collections.abc import Callable, Iterator, Mapping, Sequence
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_UP, Decimal
from pathlib import Path
from typing import NamedTuple, NoReturn

from lusot_analysis import export, rules
from lusot_analysis.face_blur import (
    UndecodableImage,
    blur_for_meta,
    decode_image,
    shrink_to_max_side,
)
from lusot_analysis.meta_client import SAM_MODEL, MetaApiError, MissingApiKey
from lusot_analysis.pipeline import READING_PHRASES, run_pipeline
from lusot_analysis.pipeline.quality import quality_scores
from lusot_analysis.pipeline.references import water_found
from lusot_analysis.pipeline.saved import (
    PhotoMismatch,
    RecordingClient,
    load_sam_results,
    run_config,
    save_sam_results,
)
from lusot_analysis.pipeline.segment import segment_all
from lusot_analysis.pipeline.types import (
    KEY_REJECTED_STATUSES,
    ModelClient,
    ModelKeyRejected,
)
from lusot_analysis.prompts import PromptSpec, load_prompt
from lusot_analysis.tuning import TUNING, Tuning


def _load(name: str):
    """A probe beside this one, loaded from its file, as dev_eval.py loads the runner."""
    path = Path(__file__).resolve().with_name(f"{name}.py")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = _load("run_pipeline")
guards = _load("set_b_masks")  # MS2's guard copies (its C202), used as they are
say = runner.say
# The harness's one command, run as a subprocess only (C321, MS6's C400).
RUN_EVAL = runner.REPO / "eval" / "run_eval.py"
RESULTS = runner.REPO / "eval" / "results"  # MS6's §4.3
# The estimated costs: a photo's full run, as dev_eval.py has it, and a SAM call.
FULL_PHOTO_USD = Decimal("0.03")
SAM_CALL_USD = Decimal("0.0025")
# What a Set B crop or a Set D photo is sent: set_b.py's SET_B_PHRASES.
SAM_ONLY_PHRASES = ("floodwater", "wheel", "wheel rim")
# Each side's folder and its manifest's set, and how the tool names its files.
SIDES = {"set_a": "A", "a_neg": "A-neg"}
NAMES = {"set_a": "the Set A manifest", "a_neg": "the A-neg manifest"}
RUNS = {"freeze-1": False, "freeze-2": True}  # each run, by its tag: a rerun's?
SERVICE_STREAK = 3  # sends in a row that Meta's service fails: a stop
CONSOLE_REFUSAL = "refused: run this yourself, in a Windows PowerShell window"
RECORD = "run.json"  # a saved folder's record, written last
STATE = "state.json"
LOCK = "run.lock"  # in <folder>/outputs: held by the one window running
LOCK_REFUSAL = (
    "another window is running this folder's run: let it end or close it, then resume"
)
RULES_REFUSAL = (
    "--baseline's rules version isn't the frozen harness's; rerun the development"
    " report on this freeze first"
)
# The freeze check's status: untracked files shown, whatever git's settings say.
STATUS = (
    "-c",
    "status.showUntrackedFiles=normal",
    "status",
    "--porcelain",
    "--untracked-files=normal",
)
_DATE = re.compile("[0-9]{4}-[0-9]{2}-[0-9]{2}")
_MANILA = timezone(timedelta(hours=8))  # Manila keeps no daylight saving time
_ACCOUNT = re.compile("[0-9]{12}")
_COMMIT = re.compile("[0-9a-f]{40}")
_ROW = re.compile(r"\brow ([0-9]+)\b")
_CLASSES = frozenset(rules.PASSABILITY.values())

type Git = Callable[[Sequence[str]], str | None]


# Named tuples, not dataclasses: a dataclass needs its module in sys.modules, and
# this file is loaded from its path, as the tests load it.
class Photo(NamedTuple):
    """A Set A or A-neg photo: its side's folder name, its manifest row, its §4.3
    base fields (bridge_base's) and its file."""

    side: str
    row: Mapping[str, str]
    base: Mapping[str, object]
    path: Path

    @property
    def photo_id(self) -> str:
        return self.row["photo_id"]


class Item(NamedTuple):
    """A file SAM alone is sent: a Set B crop or a Set D photo, by its id."""

    kind: str  # set_b or set_d
    key: str
    path: Path


class Inputs(NamedTuple):
    """What the sealed folder holds, checked. Set B's rows are scaled to the image
    SAM sees; Set B and Set D are None when the folder has neither."""

    photos: list[Photo]
    m8: Mapping[str, list[dict]]
    set_b: list[export.WheelRow] | None
    set_d: list[export.SetDRow] | None
    items: list[Item]


def results_folder(given: Path | None, *, rerun: bool) -> Path:
    """--results, or the repo's eval/results, or its rerun folder (MS6's C421)."""
    if given is not None:
        return given
    return RESULTS / "rerun" if rerun else RESULTS


def read_git(args: Sequence[str]) -> str | None:
    """git's output for `args`, run in the repo and stripped, or None when it fails.
    Every GIT_ variable is left out of its environment, so none can point it at
    another repo, work tree or index."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    try:
        done = subprocess.run(
            ["git", "-C", str(runner.REPO), *args],
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
            check=False,  # its exit code is read below
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.strip() if done.returncode == 0 else None


def _harness(flag: str) -> str | None:
    """What `eval/run_eval.py <flag>` prints, run once as a subprocess, or None when
    it can't be run or fails."""
    try:
        done = subprocess.run(
            [sys.executable, "-I", "-B", str(RUN_EVAL), flag],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=runner.REPO,
            check=False,  # its exit code is read below
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout if done.returncode == 0 else None


def label_words() -> frozenset[str]:
    """The words a committed label may hold, as `eval/run_eval.py --label-words`
    prints them, run once as a subprocess (MS6's C420). Without the harness, or when
    it fails or prints no word, the run is refused."""
    if not RUN_EVAL.is_file():
        _refuse("the harness isn't on this branch, so the labels can't be checked")
    printed = _harness("--label-words")
    words = frozenset(printed.split()) if printed is not None else frozenset()
    if not words:
        _refuse("the harness's --label-words gave no words")
    return words


def rules_version() -> str:
    """The rules version the frozen harness scores, as `eval/run_eval.py
    --rules-version` prints it, run once as a subprocess, stripped of its line end
    (Windows' is \\r\\n). Without the harness, or when it fails or prints nothing, the
    run is refused."""
    if not RUN_EVAL.is_file():
        _refuse(
            "the harness isn't on this branch, so the rules version can't be checked"
        )
    printed = _harness("--rules-version")
    version = printed.strip() if printed is not None else ""
    if not version:
        _refuse("the harness's --rules-version gave no version")
    return version


def main(
    argv: Sequence[str] | None = None,
    *,
    make_client: Callable[[], ModelClient] | None = None,
    git: Git | None = None,
    is_console: Callable[[int], bool] | None = None,
    ask: Callable[[str], str] | None = None,
    tuning: Tuning = TUNING,
) -> int:
    """Run the command the module's docstring describes.

    The keywords are for tests: the Meta client (the runner's make_client by
    default), git, the console check (MS2's console_ok) and Rene's answers (MS2's
    confirm). A test that pins start values passes START, since a default bound at
    import can't be patched (R128). The body runs through MS2's quiet, which prints
    an exception's class only; its 1 is R110's 3.
    """
    try:
        code = guards.quiet(
            lambda: _run(
                argv,
                make_client or runner.make_client,
                git or read_git,
                is_console,
                ask,
                tuning,
            )
        )
    except SystemExit as exc:  # a refusal, which said why
        return exc.code
    return 3 if code == 1 else code


def _run(
    argv: Sequence[str] | None,
    make_client: Callable[[], ModelClient],
    git: Git,
    is_console: Callable[[int], bool] | None,
    ask: Callable[[str], str] | None,
    tuning: Tuning,
) -> int:
    args = _parse(argv)
    run_name = args.resume or ("freeze-2" if args.rerun is not None else "freeze-1")
    rerun = RUNS[run_name]
    results = results_folder(args.results, rerun=rerun)
    folder = args.folder
    # 1. The paths, as written: nothing is touched yet.
    guards.require_sealed(folder, flag="the folder given")
    guards.refuse_sealed(results, args.baseline)
    # 2. The console, before anything inside a sealed folder is touched (C202).
    if not guards.console_ok(is_console=is_console):
        print(CONSOLE_REFUSAL, file=sys.stderr)
        return 2
    # 1 again, resolved: a link leads neither out of a sealed folder nor into one.
    guards.require_sealed(_resolved(folder), flag="the folder given")
    runner.refuse_sealed(results, args.baseline)
    if (_resolved(results).name == "rerun") != rerun:
        _refuse(
            "--results must be a folder named rerun for the rerun, and only then"
            " (MS6's C421)"
        )
    # 3. The freeze. 4. The label words, the settings run.json records, and the
    # harness's rules version, which must be --baseline's (MS6's C424).
    freeze = _freeze(git, run_name)
    words = label_words()
    settings = _settings(args)
    if rules_version() != settings["rules_version"]:
        _refuse(RULES_REFUSAL)
    # 5. The inputs, and the run's state.
    if not folder.is_dir():
        _refuse("the folder given isn't there")
    inputs = _read_inputs(folder, words)
    for name, present in (("set_b", inputs.set_b), ("set_d", inputs.set_d)):
        if present is None and (results / f"{name}.jsonl").exists():
            _refuse("--results holds rows this export won't rewrite: use another")
    outputs = folder / "outputs" / run_name
    # One window at a time: the state and what is saved are read under the lock.
    with _one_run(outputs.parent):
        return _locked_run(
            args,
            run_name,
            outputs,
            results,
            freeze,
            settings,
            inputs,
            make_client,
            ask,
            tuning,
        )


def _locked_run(
    args: argparse.Namespace,
    run_name: str,
    outputs: Path,
    results: Path,
    freeze: str,
    settings: Mapping[str, object],
    inputs: Inputs,
    make_client: Callable[[], ModelClient],
    ask: Callable[[str], str] | None,
    tuning: Tuning,
) -> int:
    """Steps 6 to 8, while this window holds the run's lock."""
    state = _state(outputs, args, run_name, freeze, settings)
    first = [p for p in inputs.photos if not _saved(_first_dir(outputs, p))]
    items = [i for i in inputs.items if not _saved(_item_dir(outputs, i))]
    retries = [p for p in inputs.photos if _to_retry(outputs, p)]
    item_retries = [i for i in inputs.items if _item_to_retry(outputs, i)]

    # 6. Rene's yes, then the labels and his second yes.
    counts = Counter(photo.side for photo in inputs.photos)
    counts.update(item.kind for item in inputs.items)
    say(
        f"inputs: set_a {counts['set_a']}, a_neg {counts['a_neg']}, set_b"
        f" {counts['set_b']}, set_d {counts['set_d']}"
    )
    total = len(inputs.photos) + len(inputs.items)
    saved = total - len(first) - len(items)
    retrying = len(retries) + len(item_retries)
    say(f"run {run_name}: {saved} of {total} saved before, {retrying} to retry")
    sending = len(first) + len(retries)
    sam_alone = len(items) + len(item_retries)
    guards.confirm(
        _masked(
            f"to send: {sending} to the pipeline and {sam_alone} to SAM alone, about"
            f" ${_cost(sending, sam_alone)}; a photo or crop Meta's service fails is"
            " sent once more (MS6E-Q6)"
        ),
        ask=ask,
    )
    marked = sum(_marked(photo.base) for photo in inputs.photos)
    say(f"labels written as (other words): {marked}")
    if marked:
        guards.confirm(
            "Their photos are excluded as unmapped (MS6's C420).",
            ask=ask,
        )
    # Before the run is marked running, so a prompt that fails leaves no state.
    prompt = load_prompt(runner.PROMPTS)
    client = None
    if sending + sam_alone:
        try:
            client = make_client()
        except MissingApiKey:
            _refuse("MODEL_API_KEY is missing or too short")

    # 7. The run, then 8. the export. Any stop from here on is kept.
    _begin(outputs, state)
    geometry = settings["geometry_default"] == "on"
    tally: Counter[str] = Counter()
    started = time.monotonic()
    send = {"prompt": prompt, "tuning": tuning, "geometry": geometry, "tally": tally}
    try:
        stop = _send_photos(first, client, outputs, state, retry=False, **send)
        if stop is None:
            stop = _send_items(items, client, outputs, state, tally, retry=False)
        if stop is None:
            retries = [p for p in inputs.photos if _to_retry(outputs, p)]
            stop = _send_photos(retries, client, outputs, state, retry=True, **send)
        if stop is None:
            item_retries = [i for i in inputs.items if _item_to_retry(outputs, i)]
            stop = _send_items(item_retries, client, outputs, state, tally, retry=True)
        if stop is not None:
            _stop(outputs, state, stop)
            say(
                f"stopped: Meta's service failed on {SERVICE_STREAK} sends in a row;"
                f" resume with --resume {run_name}"
            )
            return 3
        retried = _retried(inputs, outputs)
        written = _export(inputs, outputs, results, state, prompt, tuning, retried)
    except (ModelKeyRejected, MetaApiError) as exc:
        status = exc.status
        if isinstance(exc, ModelKeyRejected) or status in KEY_REJECTED_STATUSES:
            _stop(outputs, state, "key_rejected")
            say(f"refused: Meta rejected the key or the account (HTTP {status})")
            return 2
        _stop(outputs, state, "service_failed")  # outside a send: sent again on resume
        http = "" if status is None else f" (HTTP {status})"
        say(f"stopped: {type(exc).__name__}{http}; resume with --resume {run_name}")
        return 3
    except KeyboardInterrupt:
        _stop(outputs, state, "interrupted")
        raise
    except Exception as exc:
        _stop(outputs, state, f"crash {type(exc).__name__}")
        raise
    state["running"] = False
    _write_json(outputs / STATE, state)

    seconds = time.monotonic() - started
    say(
        f"sent: {tally['photos']} to the pipeline, {tally['items']} to SAM alone;"
        f" service failures retried: {retried}"
    )
    cost = _cost(tally["photos"], tally["items"])
    say(f"billed calls: {tally['calls']}, estimated cost ${cost}")
    say(f"seconds: {seconds:.1f}")
    say("export: " + ", ".join(f"{name} {count}" for name, count in written.items()))
    where = "" if args.results is None else " --results <the --results folder>"
    say(f"next: python eval/run_eval.py --from-saved{where} --write")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "folder", type=Path, help="the extracted copy, inside a folder named sealed"
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        required=True,
        help="the last development report's summary.json (MS6's C424)",
    )
    parser.add_argument(
        "--self-check-decided",
        type=_date,
        required=True,
        metavar="DATE",
        help="when MS3 decided the self-check (C311), as YYYY-MM-DD",
    )
    parser.add_argument(
        "--geometry-default", choices=("on", "off", "dropped"), default="on"
    )
    parser.add_argument("--dropped-reason", type=_token, metavar="TOKEN")
    parser.add_argument(
        "--datasets",
        required=True,
        metavar="JSON",
        help="MS2's dataset versions and split seeds, in MS6's run.json shape",
    )
    which = parser.add_mutually_exclusive_group()
    which.add_argument(
        "--resume", choices=tuple(RUNS), metavar="RUN", help="freeze-1 or freeze-2"
    )
    which.add_argument(
        "--rerun", type=_reason, metavar="REASON", help="the one disclosed rerun"
    )
    parser.add_argument("--results", type=Path, metavar="DIR")
    return parser


def _parse(argv: Sequence[str] | None) -> argparse.Namespace:
    """The arguments, with the checks argparse can't make itself."""
    parser = _parser()
    args = parser.parse_args(argv)
    for name in ("folder", "baseline", "results"):
        path = getattr(args, name)
        if path is not None and not path.is_absolute():
            parser.error(f"{name} must be an absolute path")
    if (args.geometry_default == "dropped") != (args.dropped_reason is not None):
        parser.error(
            "--geometry-default dropped needs --dropped-reason, and only it takes one"
        )
    try:
        named = json.loads(args.datasets) != {}
    except json.JSONDecodeError:
        # Windows PowerShell 5.1 strips the inner quotes from a native command's
        # argument, so '{"a": 1}' arrives as {a: 1}: say so, before anything is read.
        parser.error(
            '--datasets is not JSON; in Windows PowerShell 5.1, write each " as \\"'
        )
    if not named:
        parser.error(
            "--datasets must name MS2's datasets, which run.json can't add later"
        )
    return args


def _date(text: str) -> str:
    """A calendar date as YYYY-MM-DD, as MS6's _date takes it: no week date."""
    if not _DATE.fullmatch(text):
        raise argparse.ArgumentTypeError("must be a date, such as 2026-10-31")
    try:
        date.fromisoformat(text)
    except ValueError:
        raise argparse.ArgumentTypeError("must be a date, such as 2026-10-31") from None
    return text


def _token(text: str) -> str:
    """A lowercase token, so no free text reaches run.json."""
    if not re.fullmatch("[a-z][a-z0-9_]{0,31}", text):
        raise argparse.ArgumentTypeError("must be a lowercase token, such as a_reason")
    return text


def _reason(text: str) -> str:
    """A rerun's reason as MS6's loader takes it: up to 80 plain characters."""
    if not export._short(text) or not text.strip():
        raise argparse.ArgumentTypeError(
            "must be up to 80 letters, digits, spaces and ._:/,+()=-"
        )
    return text


def _refuse(message: str) -> NoReturn:
    say(f"refused: {message}")
    raise SystemExit(2)


def _invalid(label: str, error: Exception | None, row: int | None = None) -> NoReturn:
    """An input that breaks its format, named by its kind, and by its row where the
    error names one or `row` gives it, never by the error's text (Task 15)."""
    found = None if error is None else _ROW.search(str(error))
    if found is not None:
        row = int(found.group(1))
    where = "" if row is None else f", row {row}"
    say(f"invalid: {label} breaks its format{where}")
    raise SystemExit(2)


def _masked(text: str) -> str:
    return _ACCOUNT.sub("<account>", text)


def _resolved(path: Path) -> Path:
    """`path` resolved: a stand-in in tests where no link can be made."""
    return path.resolve()


def _now() -> str:
    return datetime.now(_MANILA).strftime("%Y-%m-%d %H:%M:%S")


def _cost(photos: int, items: int) -> Decimal:
    """The estimated cost, rounded up to the cent, so a paid run never reads as free."""
    cost = FULL_PHOTO_USD * photos + SAM_CALL_USD * len(SAM_ONLY_PHRASES) * items
    return cost.quantize(Decimal("0.01"), rounding=ROUND_UP)


def _freeze(git: Git, tag: str) -> str:
    """HEAD's commit, once the tree has no changes and HEAD is the commit `tag`
    names (MS6's C413, C421). A file flagged assume-unchanged (a lowercase tag in
    `git ls-files -v`) or skip-worktree (S) is refused too: git status never shows
    its edits."""
    status = git(list(STATUS))
    if status is None:
        _refuse("git couldn't read the repo")
    if status:
        _refuse("the tree has changes: commit or remove them first (MS6's C413)")
    listing = git(["ls-files", "-v"])
    if listing is None:
        _refuse("git couldn't read the repo")
    if any(line[:1].islower() or line[:1] == "S" for line in listing.splitlines()):
        _refuse(
            "the index hides changes to a file (assume-unchanged or skip-worktree):"
            " clear its flag first (MS6's C413)"
        )
    head = git(["rev-parse", "--verify", "HEAD"])
    tagged = git(["rev-parse", "--verify", "--quiet", f"refs/tags/{tag}^{{commit}}"])
    if tagged is None:
        _refuse(f"there is no {tag} tag (MS6's C413, C421)")
    if head != tagged or not _COMMIT.fullmatch(head):
        _refuse(f"HEAD isn't the commit tagged {tag}")
    return head


def _settings(args: argparse.Namespace) -> dict[str, object]:
    """What run.json records beyond the run itself: the baseline pair and the rules
    version from --baseline's summary.json (MS6's C424), and the flags."""
    try:
        datasets = json.loads(args.datasets)
    except json.JSONDecodeError:
        datasets = None
    try:
        export.check_datasets(datasets)
    except export.InputError as exc:  # its message names the rule only
        say(f"invalid: --datasets: {exc}")
        raise SystemExit(2) from None
    summary = None
    if args.baseline.is_file():
        try:
            summary = json.loads(args.baseline.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            summary = None
    if not (
        isinstance(summary, dict)
        and summary.get("kind") == "development"
        and summary.get("baseline_level") in rules.LEVELS
        and summary.get("baseline_class") in _CLASSES
        and export._short(summary.get("rules_version"))
        and summary["rules_version"]
    ):
        _refuse(
            "--baseline must be a development report's summary.json, with its"
            " baseline pair and rules version (MS6's C424)"
        )
    return {
        "rules_version": summary["rules_version"],
        "baseline_level": summary["baseline_level"],
        "baseline_class": summary["baseline_class"],
        "self_check_decided": args.self_check_decided,
        "geometry_default": args.geometry_default,
        "dropped_reason": args.dropped_reason,
        "datasets": datasets,
    }


def _read_inputs(folder: Path, words: frozenset[str]) -> Inputs:
    """The sealed folder's inputs, each checked before anything is paid for."""
    m8 = _parsed("the M8 sheet", export.parse_m8, folder / "set_a" / "m8.csv")
    photos = []
    for side, wanted in SIDES.items():
        rows = _parsed(
            NAMES[side], export.parse_manifest, folder / side / "manifest.csv"
        )
        if any(row["set"] != wanted for row in rows):
            _refuse(f"{NAMES[side]} holds a row of another set")
        # Each photo's outputs are filed by its id, and a folder name may ignore case.
        if len({row["photo_id"].casefold() for row in rows}) < len(rows):
            _refuse(f"{NAMES[side]}'s photo ids repeat when case is ignored")
        for number, row in enumerate(rows, start=1):
            labels = m8.get(row["photo_id"], []) if side == "set_a" else []
            try:
                base = export.bridge_base(row, labels, words=words)
            except export.InputError as exc:
                _invalid(NAMES[side], exc, number)
            path = folder / side / "photos" / row["photo_file"]
            photos.append(Photo(side, row, base, path))
    if not photos:
        _refuse("the manifests hold no photos")
    set_b = set_d = None
    items: list[Item] = []
    truth = folder / "set_b" / "truth.csv"
    if truth.is_file():
        set_b = _parsed("Set B's truth.csv", export.parse_truth, truth)
        crops = {row.crop_id: row.crop_file for row in set_b}
        items += [
            Item("set_b", key, truth.parent / "crops" / name)
            for key, name in crops.items()
        ]
    log = folder / "set_d" / "set_d_log.csv"
    if log.is_file():
        set_d = _parsed("Set D's set_d_log.csv", export.parse_set_d, log)
        named = {row.photo_id: row.photo_file for row in set_d}
        items += [
            Item("set_d", key, log.parent / "photos" / name)
            for key, name in named.items()
        ]
    files = [photo.path for photo in photos] + [item.path for item in items]
    missing = sum(not path.is_file() for path in files)
    if missing:
        _refuse(f"{missing} of the files the logs name are missing")
    # Each crop's scale is blur_for_meta's, so its rows' pixels become those of the
    # image SAM sees (export.scale_row), and a file that doesn't decode is refused.
    factors = {}
    for item in items:
        try:
            bgr = decode_image(item.path.read_bytes())
        except UndecodableImage:
            _refuse("a Set B crop or a Set D photo doesn't decode")
        factors[item.kind, item.key] = shrink_to_max_side(bgr).shape[1] / bgr.shape[1]
    if set_b is not None:
        set_b = [export.scale_row(row, factors["set_b", row.crop_id]) for row in set_b]
    return Inputs(photos, m8, set_b, set_d, items)


def _parsed(label: str, parse: Callable[[str], object], path: Path):
    """`parse` on the text of the file at `path`, which `label` names."""
    if not path.is_file():
        _refuse(f"{label} is missing")
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        _invalid(label, None)
    try:
        return parse(text)
    except export.InputError as exc:  # its text can name a sealed crop (Task 15)
        _invalid(label, exc)


def _marked(base: Mapping[str, object]) -> int:
    """How many of a Set A row's labels are written as (other words) (MS6's C420)."""
    if "level_label_raw" not in base:
        return 0
    written = [base["level_label_raw"], base["passability_raw"]]
    written += base["other_alerts_raw"]
    return written.count(export.OTHER_WORDS)


def _state(
    outputs: Path,
    args: argparse.Namespace,
    run_name: str,
    freeze: str,
    settings: Mapping[str, object],
) -> dict:
    """The run's state: a new one, or, with --resume, the one saved, which must have
    been started at this commit with these settings."""
    path = outputs / STATE
    if args.resume is None:
        if outputs.exists():
            _refuse(f"this freeze's run exists: resume it with --resume {run_name}")
        return {
            "run": run_name,
            "freeze_commit": freeze,
            "rerun_reason": args.rerun,
            "date": datetime.now(_MANILA).date().isoformat(),
            "settings": dict(settings),
            "stops": [],
            "running": False,
            "saved_at": _now(),
        }
    if not path.is_file():
        _refuse("there is no such run to resume")
    state = json.loads(path.read_text(encoding="utf-8"))
    if state["freeze_commit"] != freeze:
        _refuse("the run was started at another commit")
    if state["settings"] != json.loads(json.dumps(settings)):
        _refuse("the run started with other settings: give it the same flags")
    return state


def _begin(outputs: Path, state: dict) -> None:
    """Mark the run as running. A run that ended with no stop kept gets one at its
    last saved item, and every stop is marked as resumed now."""
    if state["running"]:
        stop = {"at": state["saved_at"], "cause": "ended_without_a_stop"}
        state["stops"].append(stop | {"resumed": None})
    now = _now()
    for stop in state["stops"]:
        if stop["resumed"] is None:
            stop["resumed"] = now
    state["running"] = True
    outputs.mkdir(parents=True, exist_ok=True)
    _write_json(outputs / STATE, state)


def _stop(outputs: Path, state: dict, cause: str) -> None:
    state["stops"].append({"at": _now(), "cause": cause, "resumed": None})
    state["running"] = False
    _write_json(outputs / STATE, state)


def _saved_item(outputs: Path, state: dict) -> None:
    state["saved_at"] = _now()
    _write_json(outputs / STATE, state)


@contextlib.contextmanager
def _one_run(folder: Path) -> Iterator[None]:
    """Hold the OS's lock on `folder`/run.lock while the run lasts: msvcrt's on
    Windows, flock elsewhere. A second window is refused, and the OS frees the lock
    when this one's process ends, so a closed window's run still resumes."""
    folder.mkdir(parents=True, exist_ok=True)
    fd = os.open(folder / LOCK, os.O_RDWR | os.O_CREAT)
    try:
        try:
            _os_lock(fd, take=True)
        except OSError:  # another window holds it
            _refuse(LOCK_REFUSAL)
        try:
            yield
        finally:
            _os_lock(fd, take=False)
    finally:
        os.close(fd)


def _os_lock(fd: int, *, take: bool) -> None:
    """Take the OS's lock on the file `fd` without waiting, which raises OSError
    while another process holds it, or free it."""
    if sys.platform == "win32":
        import msvcrt

        os.lseek(fd, 0, os.SEEK_SET)  # msvcrt locks bytes from the file's position
        msvcrt.locking(fd, msvcrt.LK_NBLCK if take else msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(fd, (fcntl.LOCK_EX | fcntl.LOCK_NB) if take else fcntl.LOCK_UN)


def _first_dir(outputs: Path, photo: Photo) -> Path:
    return outputs / photo.side / photo.photo_id


def _retry_dir(outputs: Path, photo: Photo) -> Path:
    return outputs / "retry" / photo.side / photo.photo_id


def _item_dir(outputs: Path, item: Item) -> Path:
    return outputs / item.kind / item.key


def _item_retry_dir(outputs: Path, item: Item) -> Path:
    return outputs / "retry" / item.kind / item.key


def _record(folder: Path) -> dict | None:
    """The folder's record, written last, or None when it isn't there or isn't whole:
    a stop mid-write can leave it empty or cut short, which isn't a JSON object."""
    try:
        record = json.loads((folder / RECORD).read_text(encoding="utf-8"))
    except (FileNotFoundError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return record if isinstance(record, dict) else None


def _saved(folder: Path) -> bool:
    """Whether the folder's record, written last, is there and whole."""
    return _record(folder) is not None


def _service_failed(outcome: Mapping, log: Mapping) -> bool:
    """Whether Meta's service failed the run (MS6E-Q6): the pipeline ends a
    MetaApiError as failed/model_error and logs its status, where an invalid answer
    logs none."""
    return outcome["reason"] == "model_error" and "meta_status" in log


def _to_retry(outputs: Path, photo: Photo) -> bool:
    """Whether the photo's first run, saved, failed at Meta's service, and its one
    retry isn't saved yet."""
    record = _record(_first_dir(outputs, photo))
    if record is None or _saved(_retry_dir(outputs, photo)):
        return False
    return _service_failed(record["outcome"], record["log"])


def _item_to_retry(outputs: Path, item: Item) -> bool:
    """Whether the crop's or Set D photo's first send, saved, failed at Meta's
    service (its record holds the status alone), and its one retry isn't saved."""
    record = _record(_item_dir(outputs, item))
    if record is None or _saved(_item_retry_dir(outputs, item)):
        return False
    return "meta_status" in record


def _retried(inputs: Inputs, outputs: Path) -> int:
    """MS6E-Q6's count for the whole run, resumes included: the photos and the Set B
    crops and Set D photos whose one retry is saved."""
    retried = sum(_saved(_retry_dir(outputs, photo)) for photo in inputs.photos)
    return retried + sum(_saved(_item_retry_dir(outputs, i)) for i in inputs.items)


def _set_aside(folder: Path) -> None:
    """Move aside a folder a stop left without its whole record, so the item is sent
    again into a new one. Nothing is deleted."""
    if not folder.exists():
        return
    number = 1
    while (aside := folder.with_name(f"{folder.name}.incomplete-{number}")).exists():
        number += 1
    folder.rename(aside)


def _send_photos(
    photos: Sequence[Photo],
    client: ModelClient,
    outputs: Path,
    state: dict,
    *,
    prompt: PromptSpec,
    tuning: Tuning,
    geometry: bool,
    tally: Counter[str],
    retry: bool,
) -> str | None:
    """Each photo once through the frozen pipeline, saved as the offline runner
    saves a run (R108, R109). It returns "service_failed" once SERVICE_STREAK photos
    in a row end on a failure at Meta's service, else None."""
    streak = 0
    label = "retry" if retry else "photo"
    config = run_config(geometry_in_level=geometry, tuning=tuning, sam_from=False)
    for number, photo in enumerate(photos, start=1):
        folder = (_retry_dir if retry else _first_dir)(outputs, photo)
        _set_aside(folder)
        began = time.monotonic()
        recording = RecordingClient(client)
        run = run_pipeline(
            photo.path.read_bytes(),
            recording,
            prompt,
            phrases=READING_PHRASES,
            geometry_in_level=geometry,
            tuning=tuning,
        )
        recording.save(folder, photo=photo.path, prompt=prompt, run=run, config=config)
        _saved_item(outputs, state)
        tally["photos"] += 1
        tally["calls"] += run.log["meta_calls"]
        say(f"{label} {number} of {len(photos)}: {time.monotonic() - began:.1f} s")
        failed = _service_failed({"reason": run.outcome.reason}, run.log)
        streak = streak + 1 if failed else 0
        if streak == SERVICE_STREAK:
            return "service_failed"
    return None


def _send_items(
    items: Sequence[Item],
    client: ModelClient,
    outputs: Path,
    state: dict,
    tally: Counter[str],
    *,
    retry: bool,
) -> str | None:
    """Each crop and Set D photo once: the face blur, then SAM's phrases, saved as
    set_b.py saves a crop: sam/ first, then its record. A send that Meta's service
    fails (any MetaApiError but a rejected key's) is saved as a record of its status
    alone (MS6E-Q6). It returns "service_failed" once SERVICE_STREAK sends in a row
    fail so (R164), else None."""
    streak = 0
    label = "retry SAM alone" if retry else "SAM alone"
    for number, item in enumerate(items, start=1):
        folder = (_item_retry_dir if retry else _item_dir)(outputs, item)
        _set_aside(folder)
        began = time.monotonic()
        data = item.path.read_bytes()
        image = blur_for_meta(data)  # before any Meta call (C20)
        try:
            sam = segment_all(client, image, SAM_ONLY_PHRASES)
        except MetaApiError as exc:
            if exc.status in KEY_REJECTED_STATUSES:
                raise
            folder.mkdir(parents=True)
            record = {"meta_status": exc.status}
        else:
            save_sam_results(folder, sam)
            record = {
                "photo_sha256": hashlib.sha256(data).hexdigest(),
                "phrases": list(SAM_ONLY_PHRASES),
                "models": {"sam": SAM_MODEL},
                "blur_version": image.blur_version,
                "image": {"width": image.width, "height": image.height},
            }
        _write_json(folder / RECORD, record)
        _saved_item(outputs, state)
        tally["items"] += 1
        tally["calls"] += len(SAM_ONLY_PHRASES)
        seconds = time.monotonic() - began
        say(f"{label} {number} of {len(items)}: {seconds:.1f} s")
        streak = streak + 1 if "meta_status" in record else 0
        if streak == SERVICE_STREAK:
            return "service_failed"
    return None


def _export(
    inputs: Inputs,
    outputs: Path,
    results: Path,
    state: Mapping,
    prompt: PromptSpec,
    tuning: Tuning,
    service_retries: int,
) -> dict[str, int]:
    """run.json, with `service_retries` (MS6E-Q6), and the rows, from the saved
    outputs, into `results`. Each photo's or item's retry, when it has one, is its
    result: an item Meta's service failed twice has every variant of its wheels
    unmeasured as model_error, and a null sam_water_found, as it was never answered.
    It returns each file's row count."""
    settings = state["settings"]
    dropped = settings["geometry_default"] == "dropped"
    configurations = {"landmark": False} if dropped else export.CONFIGURATIONS
    built: dict[str, list[dict]] = {"set_a": [], "a_neg": []}
    records = []
    for photo in inputs.photos:
        run_dir = _retry_dir(outputs, photo)
        if not _saved(run_dir):
            run_dir = _first_dir(outputs, photo)
        record = _record(run_dir)
        records.append(record)
        runs = export.replay_configurations(
            photo.path.read_bytes(),
            run_dir,
            prompt,
            tuning=tuning,
            configurations=configurations,
        )
        labels = inputs.m8.get(photo.photo_id, []) if photo.side == "set_a" else []
        spark = run_dir / "spark.json"
        saved = (
            json.loads(spark.read_text(encoding="utf-8")) if spark.is_file() else None
        )
        built[photo.side].append(
            export.saved_row(
                photo.base, runs, saved, record, prompt.schema, labels=labels
            )
        )
    sam = {}
    for item in inputs.items:
        data = item.path.read_bytes()
        run_dir = _item_retry_dir(outputs, item)
        if not _saved(run_dir):
            run_dir = _item_dir(outputs, item)
        found = _load_sam(run_dir, data)
        sam[item.kind, item.key] = (found, quality_scores(data).brightness)
    if inputs.set_b is not None:
        built["set_b"] = []
        for row in inputs.set_b:
            found, brightness = sam["set_b", row.crop_id]
            if found is None:
                estimates, water = _model_error(export.SET_B_VARIANTS), None
            else:
                estimates = export.wheel_estimates(
                    row, found, brightness, tuning=tuning
                )
                water = water_found(found["floodwater"])
            built["set_b"].append(export.set_b_row(row, estimates, water))
    if inputs.set_d is not None:
        built["set_d"] = []
        for row in inputs.set_d:
            found, brightness = sam["set_d", row.photo_id]
            if found is None:
                estimates, water = _model_error(export.SET_D_VARIANTS), None
            else:
                estimates = export.set_d_estimates(
                    row, found, brightness, tuning=tuning
                )
                water = water_found(found["floodwater"])
            built["set_d"].append(export.set_d_row(row, estimates, water))
    sent = next((record for record in records if record["phrases"]), records[0])
    manifest = export.results_manifest(
        kind="sealed",
        date=state["date"],
        rules_version=settings["rules_version"],
        tuning=tuning,
        saved_run=sent,
        geometry_default=settings["geometry_default"],
        dropped_reason=settings["dropped_reason"],
        datasets=settings["datasets"],
        freeze_commit=state["freeze_commit"],
        baseline={key: settings[key] for key in ("baseline_level", "baseline_class")},
        stops=state["stops"],
        rerun_reason=state["rerun_reason"],
        self_check_decided=settings["self_check_decided"],
        service_retries=service_retries,
    )
    results.mkdir(parents=True, exist_ok=True)
    _write(results / RECORD, json.dumps(manifest, indent=2) + "\n")
    for name, rows in built.items():
        _write(results / f"{name}.jsonl", "".join(json.dumps(r) + "\n" for r in rows))
    return {name: len(rows) for name, rows in built.items()}


def _load_sam(folder: Path, data: bytes) -> dict | None:
    """SAM's results saved in `folder` for the file `data`, or None when Meta's
    service failed the send, whose record holds the status alone."""
    record = _record(folder)
    if "meta_status" in record:
        return None
    if record["photo_sha256"] != hashlib.sha256(data).hexdigest():
        raise PhotoMismatch("saved outputs belong to another photo")
    return load_sam_results(folder)


def _model_error(variants: Sequence[str]) -> dict[str, dict]:
    """Every variant unmeasured as model_error, in MS6's estimate shape (its rows.py
    _estimate): Meta's service failed the item's send and its one retry."""
    return {variant: export._unmeasured("model_error") for variant in variants}


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def _write_json(path: Path, value: object) -> None:
    """`value` as JSON, through a file beside it, so a stop mid-write leaves the old
    one whole."""
    partial = path.with_name(f"{path.name}.partial")
    _write(partial, json.dumps(value, indent=2) + "\n")
    os.replace(partial, path)


if __name__ == "__main__":
    sys.exit(main())
