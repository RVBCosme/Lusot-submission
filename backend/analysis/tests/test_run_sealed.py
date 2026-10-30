"""Tests for the sealed-run entry point, probes/run_sealed.py (MS6's C412; C329).

Synthetic data only. Each test makes its own folder named sealed under tmp_path, which
is synthetic, not sealed data, and no one opens it by hand. No test reads lusot-data or
a real sealed folder, every export goes to a --results folder under tmp_path, and
FakeClient stands in for Meta, so no test makes a Meta call. git, the console and
Rene's answers are fakes passed to main, but for one test that reads a real git repo
under tmp_path. The harness's --label-words and --rules-version come from a stand-in
script that prints WORDS and RULES, so a test never runs the harness but where it
checks them against it.

MS2's guard copies are on this branch (probes/set_b_masks.py), so run_sealed uses them
as they are and makes no copies: there is no parity test to run (R132).
"""

import contextlib
import csv
import dataclasses
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import threading
from pathlib import Path

import pytest
from fakes import FakeClient, geometry_case, instance, meta_error, noise_jpeg

from lusot_analysis import export
from lusot_analysis.meta_client import SamResult
from lusot_analysis.tuning import START

TOOL = Path(__file__).parents[1] / "probes" / "run_sealed.py"
REPO = Path(__file__).resolve().parents[3]  # as the runner resolves it
TIMEOUT = 120  # seconds a subprocess may run, so a stray prompt fails instead of hangs
FREEZE_1 = "1a2b3c4d5e" * 4  # the commits the fake tags name: 40 hex characters
FREEZE_2 = "9f8e7d6c5b" * 4
BRIGHT = 127.0  # a daylight brightness, over check 4's 80
CONSOLE_REFUSAL = "refused: run this yourself, in a Windows PowerShell window\n"
FOLDER_REFUSAL = "refused: the folder given must be inside a folder named sealed\n"
REASON = "REASON-MARKER-31"  # the reason fakes.answer gives every answer
# Markers for the inputs' free text and labels, which nothing printed may hold.
FREE_TEXT = ("NOTE-MARKER-17", "CITY-MARKER-23", "SPOT-MARKER-29", "PLACE-MARKER-37")
OTHER_LABEL = "Knee deep near MARKETMARKER"  # "near" isn't a label word
TIME = re.compile("[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}")
# The harness's --label-words, as eval/run_eval.py prints them, which the last test
# checks.
WORDS = [
    "above",
    "all",
    "and",
    "ankle",
    "any",
    "cars",
    "centimeter",
    "centimeters",
    "centimetre",
    "centimetres",
    "chest",
    "cm",
    "deep",
    "gutter",
    "half",
    "head",
    "in",
    "inch",
    "inches",
    "knee",
    "lagpas",
    "level",
    "light",
    "motorcycles",
    "not",
    "npatv",
    "nplv",
    "of",
    "passable",
    "patv",
    "sedan",
    "subsided",
    "tao",
    "tire",
    "to",
    "types",
    "vehicle",
    "vehicles",
    "waist",
]
# The stand-in harness's rules version, which write_summary's --baseline names too.
RULES = "0.6"
RULES_REFUSAL = (
    "refused: --baseline's rules version isn't the frozen harness's; rerun the"
    " development report on this freeze first\n"
)
# MS2's columns (its formats.py and §5.9), written out: backend/analysis can't import
# eval/.
MANIFEST_COLUMNS = (
    "photo_id",
    "set",
    "split",
    "event_id",
    "event_date",
    "city",
    "metro_manila",
    "spot_key",
    "same_spot_as",
    "poster_kind",
    "match",
    "level_label_raw",
    "passability_raw",
    "other_alerts_raw",
    "label_in_image",
    "reference_visible",
    "faces_or_plates",
    "surface",
    "duplicate",
    "duplicate_of",
    "decodes",
    "photo_file",
    "photo_sha256",
    "photo_dhash",
    "width",
    "height",
    "notes",
)
M8_COLUMNS = (
    "photo_id",
    "ref_id",
    "kind",
    "x",
    "y",
    "vehicle_type",
    "body_waterline",
    "waterline",
    "quality",
    "subsets",
)
TRUTH_COLUMNS = (
    "crop_id",
    "car_id",
    "split",
    "photo_file",
    "crop_file",
    "wheel",
    "view",
    "vehicle_type",
    "tire_code",
    "rim_in",
    "diameter_in",
    "crop_scale",
    "size_bin",
    "x0",
    "y0",
    "x1",
    "y1",
    "ground_row",
    "top_row",
    "px_per_in",
    "waterline_left_row",
    "waterline_right_row",
    "waterline_row",
    "true_depth_in",
    "band",
    "rim_edge_ratio",
    "generator_version",
)
SET_D_COLUMNS = (
    "photo_id",
    "photo_file",
    "taken_pht",
    "place_text",
    "model",
    "vehicle_type",
    "tire_code",
    "wheel",
    "ruler_depth_in",
    "notes",
)
WHEEL_BOX = (263, 183, 378, 257)  # geometry_case's wheel box
# MS6's §4.3 fields, as its loader checks them (rows.py on Window 4's branch).
SET_A_FIELDS = {
    "photo_id",
    "event_id",
    "level_label_raw",
    "passability_raw",
    "other_alerts_raw",
    "poster_kind",
    "label_in_image",
    "match",
    "duplicate",
    "metro_manila",
    "decodes",
    "quality",
    "subsets",
    "outcomes",
    "answer",
    "wheel_inches",
    "m8",
}
A_NEG_FIELDS = SET_A_FIELDS - {
    "level_label_raw",
    "passability_raw",
    "other_alerts_raw",
    "m8",
} | {"surface"}
WHEEL_FIELDS = {
    "crop_id",
    "wheel",
    "car_id",
    "vehicle_type",
    "tire_code",
    "true_depth_in",
    "sam_water_found",
    "bins",
    "estimates",
}
ESTIMATE_FIELDS = {"measured", "depthInPoint", "depthInMin", "depthInMax", "fail"}
# A sealed run.json's fields: MS6's loader needs all but the last three, which a run
# carries only with a stop, a rerun or a dropped geometry.
SEALED_RUN_FIELDS = {
    "kind",
    "date",
    "rules_version",
    "freeze_commit",
    "frozen",
    "datasets",
    "self_check",
    "self_check_decided",
    "geometry_default",
    "baseline_level",
    "baseline_class",
    "service_retries",
}
OPTIONAL_RUN_FIELDS = {"stops", "rerun_reason", "geometry_dropped_reason"}
# --datasets, in MS6's shape: each set's MS2 version and split seed.
DATASETS = {
    name: {"version": "v1", "split_seed": "seed-1"} for name in ("set_a", "a_neg")
}
# The freeze check's git calls (Minor 2): the status, whatever git's configuration
# says of untracked files, and the index's tags.
STATUS = (
    "-c",
    "status.showUntrackedFiles=normal",
    "status",
    "--porcelain",
    "--untracked-files=normal",
)
LISTING = ("ls-files", "-v")
LOCK_REFUSAL = "refused: another window is running this folder's run"
# An estimate that Meta's service failed twice (MS6E-Q6, (a)), in MS6's shape.
MODEL_ERROR = {
    "measured": False,
    "depthInPoint": None,
    "depthInMin": None,
    "depthInMax": None,
    "fail": "model_error",
}


def load_tool():
    spec = importlib.util.spec_from_file_location("run_sealed_script", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tool = load_tool()


def fail(*_args, **_kwargs):
    raise AssertionError("called before the checks before it passed")


def stand_in(script: Path, version: str | None = RULES) -> None:
    """A stand-in eval/run_eval.py at `script`: --label-words prints WORDS, and
    --rules-version prints `version` and Windows' line end, on every OS. With
    `version` None it knows no --rules-version, as an older harness wouldn't, and
    exits 2, as argparse would."""
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(
        "import sys\n"
        f"WORDS = {WORDS!r}\n"
        f"VERSION = {version!r}\n"
        "if sys.argv[1:] == ['--label-words']:\n"
        "    print('\\n'.join(WORDS))\n"
        "elif sys.argv[1:] == ['--rules-version'] and VERSION is not None:\n"
        "    sys.stdout.buffer.write(VERSION.encode() + b'\\r\\n')\n"
        "else:\n"
        "    sys.exit(2)\n",
        encoding="utf-8",
    )


@pytest.fixture(autouse=True)
def offline(tmp_path, monkeypatch):
    """No key, no real client, and the stand-in harness."""
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    monkeypatch.setattr(tool.runner, "make_client", fail)
    script = tmp_path / "harness" / "eval" / "run_eval.py"
    stand_in(script)
    monkeypatch.setattr(tool, "RUN_EVAL", script)


class FakeGit:
    """git as the freeze check reads it: the status, the index's tags, HEAD and the
    freeze tags. A None status or listing is a git that fails."""

    def __init__(
        self, *, status="", listing="H eval/rules.md", head=FREEZE_1, tags=None
    ):
        self.status = status
        self.listing = listing
        self.head = head
        self.tags = {"freeze-1": FREEZE_1} if tags is None else tags
        self.calls = []

    def __call__(self, args):
        self.calls.append(tuple(args))
        if tuple(args) == STATUS:
            return self.status
        if tuple(args) == LISTING:
            return self.listing
        match tuple(args):
            case ("rev-parse", "--verify", "HEAD"):
                return self.head
            case ("rev-parse", "--verify", "--quiet", ref):
                tag = ref.removeprefix("refs/tags/").removesuffix("^{commit}")
                return self.tags.get(tag)
        raise AssertionError(f"an unexpected git call: {args}")


RERUN_GIT = {"head": FREEZE_2, "tags": {"freeze-1": FREEZE_1, "freeze-2": FREEZE_2}}


class Judged(FakeClient):
    """A FakeClient whose answers come from a list, call by call: an answer, or an
    exception (Ctrl+C's among them) to raise."""

    def __init__(self, sam, answers):
        super().__init__(sam)
        self.answers = list(answers)

    def judge(self, image, **keywords):
        answer = self.answers.pop(0)
        if isinstance(answer, BaseException) and not isinstance(answer, Exception):
            raise answer
        self.answer = answer
        return super().judge(image, **keywords)


def photo_client(**keywords) -> FakeClient:
    """geometry_case's SAM results and answer, for every photo and crop."""
    _, sam, given = geometry_case()
    return FakeClient(sam, given, **keywords)


def judged(*answers) -> Judged:
    return Judged(geometry_case()[1], answers)


class SamAloneFails(FakeClient):
    """geometry_case's client, whose SAM-alone sends fail with HTTP `status`: the
    first `failures` of them, or every one when it is None. A SAM-alone send is one
    made once all `photos` have their answer, as the run makes them, and is one
    blurred image asked SAM's three phrases. `sends` holds each send's image."""

    def __init__(self, photos: int, failures: int | None = None, status: int = 400):
        _, sam, given = geometry_case()
        super().__init__(sam, given)
        self.photos = photos
        self.failures = failures
        self.status = status
        self.sends = []
        self._sending = threading.Lock()

    def segment(self, image, phrase, *, deadline=None):
        if calls(self, "judge") >= self.photos:
            with self._sending:
                if not any(sent is image for sent in self.sends):
                    self.sends.append(image)
                send = next(n for n, sent in enumerate(self.sends) if sent is image)
            if self.failures is None or send < self.failures:
                raise meta_error(self.status)
        return super().segment(image, phrase, deadline=deadline)


@contextlib.contextmanager
def another_window(lock: Path):
    """The OS's lock on `lock`, held as another window's run would hold it."""
    lock.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(lock, os.O_RDWR | os.O_CREAT)
    try:
        if sys.platform == "win32":
            import msvcrt

            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            try:
                yield
            finally:
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield
    finally:
        os.close(fd)


def git_in(repo: Path, *args: str) -> None:
    """git in a test's own repo, with no GIT_ variable and no global or system
    configuration, so neither the machine's settings nor a hook's can reach it."""
    empty = repo.parent / "empty.gitconfig"
    empty.touch()
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env |= {"GIT_CONFIG_GLOBAL": str(empty), "GIT_CONFIG_NOSYSTEM": "1"}
    identity = ("-c", "user.name=Test", "-c", "user.email=test@example.invalid")
    subprocess.run(
        ["git", "-C", str(repo), *identity, *args],
        env=env,
        capture_output=True,
        timeout=TIMEOUT,
        check=True,
    )


def csv_text(columns, rows) -> str:
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


def manifest_row(photo_id: str, **cells: str) -> dict[str, str]:
    """A sealed manifest row in MS2's columns. A Set A row unless `set` says not."""
    a_neg = cells.get("set") == "A-neg"
    row = dict.fromkeys(MANIFEST_COLUMNS, "")
    row |= {
        "photo_id": photo_id,
        "set": "A",
        "split": "sealed",
        "event_id": "E01",
        "event_date": "2026-10-20",
        "city": FREE_TEXT[1],
        "metro_manila": "yes",
        "spot_key": FREE_TEXT[2],
        "poster_kind": "other" if a_neg else "mmda",
        "match": "" if a_neg else "same_post",
        "level_label_raw": "none" if a_neg else "Knee deep",
        "passability_raw": "" if a_neg else "NPLV",
        "label_in_image": "no",
        "surface": "wet" if a_neg else "",
        "duplicate": "no",
        "decodes": "yes",
        "photo_file": f"{photo_id}.jpg",
        "photo_sha256": "ab" * 32,
        "width": "640",
        "height": "480",
        "notes": FREE_TEXT[0],
    }
    return row | cells


def truth_row(crop_id: str = "B02-1-1", wheel: str = "1", **cells: str) -> dict:
    """A truth.csv row in MS2's columns: geometry_case's wheel, a sedan_hatch on
    175/65R14 at 5.0 px an inch, with the drawn waterline at row 257."""
    x0, y0, x1, y1 = WHEEL_BOX
    row = {
        "crop_id": crop_id,
        "car_id": crop_id.split("-")[0],
        "split": "sealed",
        "photo_file": crop_id.rsplit("-", 1)[0] + ".jpg",
        "crop_file": f"{crop_id}.jpg",
        "wheel": wheel,
        "view": "side",
        "vehicle_type": "sedan_hatch",
        "tire_code": "175/65R14",
        "rim_in": "14",
        "diameter_in": "22.9567",
        "crop_scale": "1.0",
        "size_bin": "full",
        "x0": str(x0),
        "y0": str(y0),
        "x1": str(x1),
        "y1": str(y1),
        "ground_row": "297",
        "top_row": "183",
        "px_per_in": "5.0",
        "waterline_left_row": "257",
        "waterline_right_row": "257",
        "waterline_row": "257",
        "true_depth_in": "8.08",
        "band": "half_knee",
        "rim_edge_ratio": "1.0",
        "generator_version": "setb-gen-v1",
    }
    return row | cells


def set_d_row(photo_id: str = "D01", wheel: str = "left", **cells: str) -> dict:
    """A set_d_log.csv row in MS2's columns, its free text marked."""
    row = {
        "photo_id": photo_id,
        "photo_file": f"{photo_id}.jpg",
        "taken_pht": "TAKEN-MARKER-43",
        "place_text": FREE_TEXT[3],
        "model": "MODEL-MARKER",
        "vehicle_type": "sedan_hatch",
        "tire_code": "175/65R14 82T",
        "wheel": wheel,
        "ruler_depth_in": "7.5",
        "notes": FREE_TEXT[0],
    }
    return row | cells


@dataclasses.dataclass
class Sealed:
    """A synthetic folder named sealed under tmp_path, laid out as MS2's archives
    extract (its §5.9), and the development summary.json beside it."""

    root: Path
    summary: Path
    rows: dict[str, dict[str, str]]

    def outputs(self, run: str = "freeze-1") -> Path:
        return self.root / "outputs" / run

    def argv(self, results: Path, *flags: str, folder: Path | None = None) -> list:
        return argv_for(folder or self.root, self.summary, results, *flags)


def argv_for(folder: Path, summary: Path, results: Path, *flags: str) -> list[str]:
    return [
        str(folder),
        "--baseline",
        str(summary),
        "--self-check-decided",
        "2026-10-31",
        "--datasets",
        json.dumps(DATASETS),
        "--results",
        str(results),
        *flags,
    ]


def write_summary(tmp_path: Path, **fields) -> Path:
    summary = tmp_path / "data" / "dev-results" / "report" / "summary.json"
    summary.parent.mkdir(parents=True, exist_ok=True)
    content = {
        "kind": "development",
        "rules_version": RULES,
        "baseline_level": "knee",
        "baseline_class": "NPLV",
    } | fields
    summary.write_text(json.dumps(content), encoding="utf-8")
    return summary


def write_sealed(
    tmp_path: Path,
    set_a=("A101", "A102"),
    a_neg=("N101",),
    *,
    cells=None,
    set_b=None,
    set_d=None,
) -> Sealed:
    """The sealed side: both manifests, the M8 sheet and each row's photo, and Set B's
    truth.csv with its crops and Set D's log with its photos when rows are given."""
    root = tmp_path / "data" / "sealed" / "run-1"
    rows = {}
    for number, photo_id in enumerate(set_a, start=1):
        rows[photo_id] = manifest_row(photo_id, event_id=f"E{number:02}")
    for number, photo_id in enumerate(a_neg, start=1):
        rows[photo_id] = manifest_row(photo_id, set="A-neg", event_id=f"E{number:02}")
    for photo_id, changes in (cells or {}).items():
        rows[photo_id] |= changes
    photo = noise_jpeg()
    for side, ids in (("set_a", set_a), ("a_neg", a_neg)):
        (root / side / "photos").mkdir(parents=True)
        (root / side / "manifest.csv").write_text(
            csv_text(MANIFEST_COLUMNS, [rows[i] for i in ids]), encoding="utf-8"
        )
        for photo_id in ids:
            (root / side / "photos" / rows[photo_id]["photo_file"]).write_bytes(photo)
    m8 = [
        {"photo_id": set_a[0], "ref_id": "P1", "kind": "photo", "quality": "ok"},
        # Wheel 2's hub, in geometry_case's numbered boxes.
        {"photo_id": set_a[0], "ref_id": "R1", "kind": "wheel", "x": "0.5"}
        | {"y": "0.45", "waterline": "hub"},
    ]
    (root / "set_a" / "m8.csv").write_text(csv_text(M8_COLUMNS, m8), encoding="utf-8")
    if set_b is not None:
        (root / "set_b" / "crops").mkdir(parents=True)
        (root / "set_b" / "truth.csv").write_text(
            csv_text(TRUTH_COLUMNS, set_b), encoding="utf-8"
        )
        for name in dict.fromkeys(row["crop_file"] for row in set_b):
            (root / "set_b" / "crops" / name).write_bytes(photo)
    if set_d is not None:
        (root / "set_d" / "photos").mkdir(parents=True)
        (root / "set_d" / "set_d_log.csv").write_text(
            csv_text(SET_D_COLUMNS, set_d), encoding="utf-8"
        )
        for name in dict.fromkeys(row["photo_file"] for row in set_d):
            (root / "set_d" / "photos" / name).write_bytes(photo)
    return Sealed(root, write_summary(tmp_path), rows)


def ask_with(*answers):
    """Rene's answers, in order, keeping each prompt; with none left, he types no."""
    given = list(answers)
    asked = []

    def ask(prompt):
        asked.append(prompt)
        return given.pop(0) if given else "no"

    ask.asked = asked
    return ask


def clients(*made):
    """A make_client that hands out these clients in turn, and fails past them."""
    left = list(made)

    def make():
        if not left:
            raise AssertionError("a Meta client was built")
        return left.pop(0)

    return make


def run(
    sealed: Sealed,
    results: Path,
    *flags: str,
    made=(),
    git=None,
    answers=("yes",),
    folder=None,
):
    """main on `sealed`, from a console, with these clients, git and answers. It
    returns the exit code and the prompts asked."""
    ask = ask_with(*answers)
    code = tool.main(
        sealed.argv(results, *flags, folder=folder),
        make_client=clients(*made),
        git=git or FakeGit(),
        is_console=lambda fd: True,
        ask=ask,
        tuning=START,
    )
    return code, ask.asked


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_lines(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def calls(fake: FakeClient, method: str) -> int:
    return sum(1 for call in fake.calls if call[0] == method)


def make_link(link: Path, target: Path, monkeypatch) -> None:
    """`link` to the folder `target`: a directory junction on Windows, which needs no
    admin rights, and a symbolic link elsewhere. Where neither can be made, a stand-in
    for the tool's Path.resolve maps one to the other."""
    target.mkdir(parents=True, exist_ok=True)
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        if sys.platform == "win32":
            done = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(link), str(target)],
                capture_output=True,
                timeout=TIMEOUT,
                check=False,
            )
            if done.returncode != 0:
                raise OSError("mklink /J failed")
        else:
            link.symlink_to(target, target_is_directory=True)
    except OSError:
        real = tool._resolved
        monkeypatch.setattr(
            tool, "_resolved", lambda path: target if path == link else real(path)
        )


def test_refuses_a_folder_not_named_sealed(tmp_path, monkeypatch, capsys):
    sealed = write_sealed(tmp_path)
    results = tmp_path / "results"
    plain = tmp_path / "plain"
    plain.mkdir()
    through = tmp_path / "through"  # reaches the sealed folder only through a link
    make_link(through, sealed.root, monkeypatch)
    named = tmp_path / "links" / "sealed"  # a link named sealed, to a plain folder
    make_link(named, plain, monkeypatch)
    for folder in (plain, through, named, through / "set_a"):
        git = FakeGit()
        code, asked = run(sealed, results, folder=folder, git=git, made=[])
        assert code == 2
        assert capsys.readouterr().err == FOLDER_REFUSAL
        assert (asked, git.calls) == ([], [])
        assert not results.exists()
        assert not (sealed.root / "outputs").exists()
    # The sealed folder itself passes, as far as the next check.
    git = FakeGit(status=" M backend/analysis/src/lusot_analysis/rules.py")
    assert run(sealed, results, git=git, made=[]) == (2, [])
    assert git.calls[0] == STATUS


def test_refuses_a_non_console_stdin(tmp_path):
    # From an agent's shell: stdin on NUL, a pipe or a file. Nothing is read, and
    # nothing is made: the folder, the summary and --results don't exist. The
    # refusal's words aren't compared, as another OS may add a warning to them, but
    # nothing printed holds a path.
    folder = tmp_path / "data" / "sealed" / "run-1"
    summary = tmp_path / "data" / "dev-results" / "summary.json"
    results = tmp_path / "results"
    argv = [sys.executable, str(TOOL), *argv_for(folder, summary, results)]
    stdin_file = tmp_path / "stdin.txt"
    stdin_file.write_text("yes\n", encoding="utf-8")
    with stdin_file.open("rb") as typed:
        for stdin in (subprocess.DEVNULL, subprocess.PIPE, typed):
            shell = subprocess.run(
                argv,
                stdin=stdin,
                capture_output=True,
                text=True,
                timeout=TIMEOUT,
                check=False,
            )
            assert shell.returncode == 2
            printed = shell.stdout + shell.stderr
            for path in (str(tmp_path), tmp_path.name, "run-1", "summary.json"):
                assert path not in printed
            assert not (tmp_path / "data").exists()
            assert not results.exists()


def test_refuses_a_console_stdout_with_another_stdin(tmp_path, monkeypatch, capsys):
    # console_ok's own check finds stdout a console but stdin not: refused before
    # git, the harness, the summary, the folder or any prompt is reached.
    sealed = write_sealed(tmp_path)
    results = tmp_path / "results"
    for reader in ("label_words", "_settings", "rules_version", "_read_inputs"):
        monkeypatch.setattr(tool, reader, fail)
    asked = []

    def is_console(fd):
        asked.append(fd)
        return fd == 1

    code = tool.main(
        sealed.argv(results),
        make_client=fail,
        git=fail,
        is_console=is_console,
        ask=fail,
        tuning=START,
    )
    assert code == 2
    assert asked[0] == 0
    assert capsys.readouterr().err == CONSOLE_REFUSAL
    assert not results.exists()
    assert not (sealed.root / "outputs").exists()


def test_datasets_are_required(tmp_path, capsys):
    # MS6's run.json can't take MS2's datasets later, so a run without them, or with
    # none named, is refused before anything is read.
    folder = tmp_path / "data" / "sealed" / "run-1"
    argv = argv_for(folder, tmp_path / "summary.json", tmp_path / "results")
    at = argv.index("--datasets")
    for given in (
        argv[:at] + argv[at + 2 :],
        [*argv[: at + 1], "{ }", *argv[at + 2 :]],
    ):
        code = tool.main(
            given, make_client=fail, git=fail, is_console=fail, ask=fail, tuning=START
        )
        assert code == 2
        assert "--datasets" in capsys.readouterr().err
    # Windows PowerShell 5.1 strips the inner quotes, so the JSON arrives broken: the
    # refusal says how to quote it.
    stripped = [*argv[: at + 1], "{set_a: {version: v1}}", *argv[at + 2 :]]
    code = tool.main(
        stripped, make_client=fail, git=fail, is_console=fail, ask=fail, tuning=START
    )
    assert code == 2
    assert 'write each " as \\"' in capsys.readouterr().err
    assert not (tmp_path / "data").exists()
    assert not (tmp_path / "results").exists()


def test_the_decision_date_is_a_calendar_date(tmp_path, capsys):
    # An ISO week date is 10 characters too, and date.fromisoformat takes it.
    folder = tmp_path / "data" / "sealed" / "run-1"
    argv = argv_for(folder, tmp_path / "summary.json", tmp_path / "results")
    at = argv.index("--self-check-decided") + 1
    for text in ("2026-W44-5", "20261031", "2026-10-31T00"):
        argv[at] = text
        code = tool.main(
            argv, make_client=fail, git=fail, is_console=fail, ask=fail, tuning=START
        )
        assert code == 2
        assert "--self-check-decided" in capsys.readouterr().err


def test_refuses_a_dirty_tree_or_another_commit(tmp_path, capsys):
    # The folder doesn't exist: each refusal comes before anything is read.
    folder = tmp_path / "data" / "sealed" / "run-1"
    summary = write_summary(tmp_path)
    results = tmp_path / "results"

    def main(git, *flags, out=results):
        return tool.main(
            argv_for(folder, summary, out, *flags),
            make_client=fail,
            git=git,
            is_console=lambda fd: True,
            ask=fail,
            tuning=START,
        )

    hidden = "the index hides changes to a file"
    refused = [
        ("the tree has changes", FakeGit(status="?? stray.txt")),
        ("git couldn't read the repo", FakeGit(status=None)),
        # A file flagged assume-unchanged (a lowercase tag) or skip-worktree (S),
        # whose edits git status never shows.
        (hidden, FakeGit(listing="H eval/rules.md\nh eval/run_eval.py")),
        (hidden, FakeGit(listing="S eval/run_eval.py\nH eval/rules.md")),
        (hidden, FakeGit(listing="s eval/run_eval.py")),
        ("git couldn't read the repo", FakeGit(listing=None)),
        ("HEAD isn't the commit tagged freeze-1", FakeGit(head=FREEZE_2)),
        ("there is no freeze-1 tag", FakeGit(tags={})),
    ]
    for message, git in refused:
        assert main(git) == 2
        assert message in capsys.readouterr().out
        assert git.calls[:2] == [STATUS, LISTING][: len(git.calls)]
    # The one disclosed rerun runs at freeze-2 only (MS6's C421).
    rerun = ("--rerun", "a fix to the waterline step")
    out = results / "rerun"
    assert main(FakeGit(), *rerun, out=out) == 2
    assert "there is no freeze-2 tag" in capsys.readouterr().out
    at_first = FakeGit(tags=RERUN_GIT["tags"])
    assert main(at_first, *rerun, out=out) == 2
    assert "HEAD isn't the commit tagged freeze-2" in capsys.readouterr().out
    assert not folder.exists()
    assert not results.exists()


@pytest.mark.skipif(shutil.which("git") is None, reason="git isn't installed")
@pytest.mark.parametrize("hidden", ["skip-worktree", "assume-unchanged", "untracked"])
def test_the_freeze_check_reads_git_itself(tmp_path, monkeypatch, capsys, hidden):
    # A real repo at its freeze-1 tag, with a change git is told to hide: a flagged
    # file's edit, or an untracked file under status.showUntrackedFiles=no. GIT_DIR,
    # GIT_WORK_TREE and GIT_INDEX_FILE point elsewhere, so a git that kept them
    # couldn't read the repo at all.
    repo = tmp_path / "repo"
    repo.mkdir()
    git_in(repo, "init", "-q")
    (repo / "frozen.txt").write_text("frozen\n", encoding="utf-8")
    git_in(repo, "add", "frozen.txt")
    git_in(repo, "commit", "-q", "-m", "freeze")
    git_in(repo, "tag", "freeze-1")
    if hidden == "untracked":
        git_in(repo, "config", "status.showUntrackedFiles", "no")
        (repo / "stray.txt").write_text("stray\n", encoding="utf-8")
        expected = "the tree has changes"
    else:
        git_in(repo, "update-index", f"--{hidden}", "frozen.txt")
        (repo / "frozen.txt").write_text("changed\n", encoding="utf-8")
        expected = "the index hides changes to a file"
    for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        monkeypatch.setenv(name, str(tmp_path / "elsewhere"))
    monkeypatch.setattr(tool.runner, "REPO", repo)
    folder = tmp_path / "data" / "sealed" / "run-1"  # never reached
    code = tool.main(
        argv_for(folder, write_summary(tmp_path), tmp_path / "results"),
        make_client=fail,
        is_console=lambda fd: True,
        ask=fail,
        tuning=START,
    )
    assert code == 2
    assert expected in capsys.readouterr().out
    assert not (tmp_path / "results").exists()


def test_results_go_where_told(tmp_path, capsys):
    sealed = write_sealed(tmp_path)
    results = tmp_path / "out" / "results"
    assert run(sealed, results, made=[photo_client()])[0] == 0
    assert sorted(path.name for path in results.iterdir()) == [
        "a_neg.jsonl",
        "run.json",
        "set_a.jsonl",
    ]
    capsys.readouterr()
    # A --results folder inside one named sealed, in any case, is refused.
    for inside in (sealed.root / "results", tmp_path / "x" / "Sealed." / "results"):
        assert run(sealed, inside, made=[]) == (2, [])
        assert not inside.exists()
    # --rerun needs freeze-2 at HEAD, and a --results folder named rerun; a folder
    # named rerun is a rerun's only (MS6's loader).
    rerun = ("--rerun", "a fix to the waterline step")
    assert run(sealed, results / "rerun", *rerun, made=[]) == (2, [])
    git = FakeGit(**RERUN_GIT)
    assert run(sealed, results / "other", *rerun, git=git, made=[]) == (2, [])
    assert run(sealed, tmp_path / "out" / "rerun", made=[]) == (2, [])
    capsys.readouterr()
    code, _ = run(sealed, results / "rerun", *rerun, git=git, made=[photo_client()])
    assert code == 0
    manifest = read_json(results / "rerun" / "run.json")
    assert manifest["rerun_reason"] == "a fix to the waterline step"
    assert manifest["freeze_commit"] == FREEZE_2
    assert (sealed.outputs("freeze-2") / "state.json").is_file()
    # The defaults: the repo's eval/results, and its rerun folder (MS6's C421).
    assert tool.results_folder(None, rerun=False) == REPO / "eval" / "results"
    assert tool.results_folder(None, rerun=True) == REPO / "eval" / "results" / "rerun"
    assert tool.results_folder(results, rerun=False) == results


def two_wheels() -> dict[str, SamResult]:
    """SAM's results for a Set D photo: geometry_case's water and rim, its wheel on
    the left and a second wheel on the right, which no rim links. The right one comes
    first, so the pick is by position, not by order."""
    sam = geometry_case()[1]
    left = sam["wheel"].instances[0]
    right = instance(1, (450, 183, 565, 257), mask=left.mask)
    return {
        "floodwater": sam["floodwater"],
        "wheel": SamResult("wheel", [right, left], 0.5, ""),
        "wheel rim": sam["wheel rim"],
    }


def test_set_d_rows():
    log = csv_text(SET_D_COLUMNS, [set_d_row(), set_d_row(wheel="right")])
    left, right = export.parse_set_d(chr(0xFEFF) + log)
    assert (left.photo_id, left.photo_file, left.wheel) == ("D01", "D01.jpg", "left")
    assert left.tire_code.code == "175/65R14"  # read as MS2 reads a sidewall's
    assert left.ruler_depth_in == 7.5
    sam = two_wheels()
    measured = export.set_d_estimates(left, sam, BRIGHT, tuning=START)
    unlinked = export.set_d_estimates(right, sam, BRIGHT, tuning=START)
    variants = ("geometry", "geometry_uncalibrated")
    assert tuple(measured) == tuple(unlinked) == variants
    for estimate in measured.values():
        assert set(estimate) == ESTIMATE_FIELDS
        assert (estimate["measured"], estimate["fail"]) == (True, None)
        assert estimate["depthInPoint"] == pytest.approx(7.94, abs=0.02)
    assert {estimate["fail"] for estimate in unlinked.values()} == {"rim_missing"}
    # No SAM wheel at all.
    dry = sam | {"wheel": SamResult("wheel", [], 0.5, "")}
    none = export.set_d_estimates(left, dry, BRIGHT, tuning=START)
    assert {estimate["fail"] for estimate in none.values()} == {"wheel_not_found"}
    # The row: MS6's Set B fields, with the ruler depth as the truth and the photo as
    # its car, and no bins.
    row = export.set_d_row(left, measured, True)
    assert set(row) == WHEEL_FIELDS - {"bins"}
    assert (row["crop_id"], row["wheel"], row["car_id"]) == ("D01", 1, "D01")
    assert (row["tire_code"], row["true_depth_in"]) == ("175/65R14", 7.5)
    assert row["estimates"] == measured
    assert export.set_d_row(right, unlinked, True)["wheel"] == 2


@pytest.mark.parametrize(
    "cells",
    [
        {"photo_id": "d01"},  # not an opaque id
        {"photo_id": "D01/.."},
        {"photo_file": "..\\D01.jpg"},
        {"photo_file": "photos/D01.jpg"},
        {"photo_file": "D01.jpg:stream"},
        {"wheel": "middle"},
        {"vehicle_type": "jeepney"},
        {"tire_code": "MARKER-195R14"},
        {"ruler_depth_in": "123.5"},  # at most 99.9999 in, as MS6's loader takes
        {"ruler_depth_in": "7.12345"},
        {"ruler_depth_in": "deep"},
        {"ruler_depth_in": ""},
    ],
)
def test_parse_set_d_names_the_row_only(cells):
    with pytest.raises(export.InputError) as refused:
        export.parse_set_d(csv_text(SET_D_COLUMNS, [set_d_row(**cells)]))
    assert str(refused.value).startswith("set_d_log.csv row 1: ")
    for text in cells.values():
        if text:
            assert text not in str(refused.value)


def test_parse_set_d_checks_columns_and_repeats():
    columns = [column for column in SET_D_COLUMNS if column != "ruler_depth_in"]
    row = {key: value for key, value in set_d_row().items() if key in columns}
    with pytest.raises(export.InputError, match="no ruler_depth_in column"):
        export.parse_set_d(csv_text(columns, [row]))
    with pytest.raises(export.InputError, match="row 2: photo_id and wheel repeat"):
        export.parse_set_d(csv_text(SET_D_COLUMNS, [set_d_row(), set_d_row()]))
    other_file = set_d_row(wheel="right", photo_file="D01-b.jpg")
    with pytest.raises(export.InputError, match="row 2: photo_file differs"):
        export.parse_set_d(csv_text(SET_D_COLUMNS, [set_d_row(), other_file]))


def test_checks_every_label_before_paying(tmp_path, capsys):
    sealed = write_sealed(tmp_path, cells={"A102": {"level_label_raw": OTHER_LABEL}})
    results = tmp_path / "results"
    seen = []

    def ask_after_reading(*answers):
        ask = ask_with(*answers)

        def asked(prompt):
            seen.append(capsys.readouterr().out)
            return ask(prompt)

        return asked

    for answers, code in ((("yes", "no"), 2), (("no",), 2)):
        fake = photo_client()
        assert (
            tool.main(
                sealed.argv(results),
                make_client=clients(fake),
                git=FakeGit(),
                is_console=lambda fd: True,
                ask=ask_after_reading(*answers),
                tuning=START,
            )
            == code
        )
        assert fake.calls == []
        assert not sealed.outputs().exists()
    # The label is counted, before the second yes and before any call.
    assert "labels written as (other words): 1" in seen[1]
    assert "to send: 3 to the pipeline and 0 to SAM alone" in seen[0]
    fake = photo_client()
    code, asked = run(sealed, results, made=[fake], answers=("yes", "yes"))
    assert code == 0
    assert len(asked) == 2
    assert calls(fake, "judge") == 3
    rows = {row["photo_id"]: row for row in read_lines(results / "set_a.jsonl")}
    assert rows["A102"]["level_label_raw"] == export.OTHER_WORDS
    assert rows["A101"]["level_label_raw"] == "Knee deep"
    assert OTHER_LABEL not in (results / "set_a.jsonl").read_text(encoding="utf-8")


def test_pays_once_and_resumes(tmp_path, capsys):
    sealed = write_sealed(tmp_path, set_a=("A101", "A102", "A103"), a_neg=("N101",))
    results = tmp_path / "results"
    first = photo_client()

    def reject_at_the_third_photo(phrase):
        if calls(first, "judge") == 2:
            raise meta_error(401)

    first.on_segment = reject_at_the_third_photo
    assert run(sealed, results, made=[first])[0] == 2
    assert "Meta rejected the key or the account (HTTP 401)" in capsys.readouterr().out
    state = read_json(sealed.outputs() / "state.json")
    assert [stop["cause"] for stop in state["stops"]] == ["key_rejected"]
    assert not results.exists()  # only a completed run is exported
    # A new run on this freeze is refused, so nothing is paid twice.
    assert run(sealed, results, made=[]) == (2, [])
    assert "--resume freeze-1" in capsys.readouterr().out
    # A resume at another commit is refused.
    moved = FakeGit(head=FREEZE_2, tags={"freeze-1": FREEZE_2})
    assert run(sealed, results, "--resume", "freeze-1", git=moved, made=[]) == (2, [])
    # The resume sends only the two photos not saved.
    second = photo_client()
    assert run(sealed, results, "--resume", "freeze-1", made=[second])[0] == 0
    assert len(first.calls) + len(second.calls) == 4 * 6  # 5 SAM phrases, 1 answer
    assert (calls(first, "judge"), calls(second, "judge")) == (2, 2)
    manifest = read_json(results / "run.json")
    (stop,) = manifest["stops"]
    assert set(stop) == {"at", "cause", "resumed"}
    assert stop["cause"] == "key_rejected"
    assert TIME.fullmatch(stop["at"]) and TIME.fullmatch(stop["resumed"])
    # A completed run resumed again pays nothing, and writes the same rows.
    before = {name: (results / name).read_bytes() for name in ("set_a.jsonl",)}
    assert run(sealed, results, "--resume", "freeze-1", made=[])[0] == 0
    assert (results / "set_a.jsonl").read_bytes() == before["set_a.jsonl"]


def test_service_failure_is_retried_once(tmp_path, capsys):
    # A101's answer fails at Meta's service (503 after the client's retries); A102's
    # fails the schema; N101's is fine. Only A101 is sent again (MS6E-Q6, (a)).
    sealed = write_sealed(tmp_path)
    results = tmp_path / "results"
    given = geometry_case()[2]
    fake = judged(meta_error(503), {"photo_usable": "maybe"}, given, given)
    assert run(sealed, results, made=[fake])[0] == 0
    out = capsys.readouterr().out
    assert "service failures retried: 1" in out
    assert read_json(results / "run.json")["service_retries"] == 1
    assert calls(fake, "judge") == 4
    assert fake.answers == []
    assert (sealed.outputs() / "retry" / "set_a" / "A101" / "run.json").is_file()
    assert not (sealed.outputs() / "retry" / "set_a" / "A102").exists()
    rows = {row["photo_id"]: row for row in read_lines(results / "set_a.jsonl")}
    assert rows["A101"]["outcomes"]["landmark"]["status"] == "done"
    assert rows["A101"]["answer"] is not None
    assert rows["A102"]["outcomes"]["landmark"] == {
        "status": "failed",
        "refusalReason": "model_error",
    }
    # The first try's outputs stay beside the retry's, under sealed.
    first = read_json(sealed.outputs() / "set_a" / "A101" / "run.json")
    assert first["log"]["meta_status"] == 503


def test_service_failures_in_a_row_stop_the_run(tmp_path, capsys):
    # Three photos in a row that Meta's service fails are a lost connection: a stop.
    sealed = write_sealed(tmp_path)
    results = tmp_path / "results"
    down = judged(*(meta_error(503) for _ in range(3)))
    assert run(sealed, results, made=[down])[0] == 3
    assert "stopped: Meta's service failed on 3 sends in a row" in (
        capsys.readouterr().out
    )
    state = read_json(sealed.outputs() / "state.json")
    assert [stop["cause"] for stop in state["stops"]] == ["service_failed"]
    # On resume each gets its one retry, and no photo is sent a third time.
    given = geometry_case()[2]
    up = judged(given, given, given)
    assert run(sealed, results, "--resume", "freeze-1", made=[up])[0] == 0
    assert "service failures retried: 3" in capsys.readouterr().out
    assert up.answers == []
    rows = read_lines(results / "set_a.jsonl") + read_lines(results / "a_neg.jsonl")
    assert {row["outcomes"]["landmark"]["status"] for row in rows} == {"done"}


def test_every_stop_is_recorded(tmp_path, capsys):
    sealed = write_sealed(tmp_path)
    results = tmp_path / "results"
    given = geometry_case()[2]
    # Ctrl+C during the second photo.
    assert run(sealed, results, made=[judged(given, KeyboardInterrupt())])[0] == 3
    assert capsys.readouterr().err == "stopped: KeyboardInterrupt\n"
    path = sealed.outputs() / "state.json"
    state = read_json(path)
    assert [(stop["cause"], stop["resumed"]) for stop in state["stops"]] == [
        ("interrupted", None)
    ]
    # A run whose window closed records nothing: the resume adds its stop, at the
    # last item saved.
    state["running"] = True
    state["saved_at"] = "2026-11-03 21:10:00"
    path.write_text(json.dumps(state), encoding="utf-8")
    again = judged(given, KeyboardInterrupt())
    assert run(sealed, results, "--resume", "freeze-1", made=[again])[0] == 3
    later = judged(given)
    assert run(sealed, results, "--resume", "freeze-1", made=[later])[0] == 0
    stops = read_json(results / "run.json")["stops"]
    assert [stop["cause"] for stop in stops] == [
        "interrupted",
        "ended_without_a_stop",
        "interrupted",
    ]
    assert stops[1]["at"] == "2026-11-03 21:10:00"
    assert all(TIME.fullmatch(stop["resumed"]) for stop in stops)


@pytest.mark.parametrize("cut", ["empty", "truncated", "not_an_object"])
def test_a_cut_short_record_is_sent_again(tmp_path, capsys, cut):
    # A101 is saved, then Ctrl+C comes during A102. A101's record is then cut short,
    # as a kill or a closed window mid-write would leave it: it isn't saved, so it is
    # set aside, kept, and A101 is sent once more (C419).
    sealed = write_sealed(tmp_path)
    results = tmp_path / "results"
    given = geometry_case()[2]
    assert run(sealed, results, made=[judged(given, KeyboardInterrupt())])[0] == 3
    record = sealed.outputs() / "set_a" / "A101" / "run.json"
    text = record.read_text(encoding="utf-8")
    left = {"empty": "", "truncated": text[: len(text) // 2], "not_an_object": "[]"}
    record.write_text(left[cut], encoding="utf-8")
    capsys.readouterr()
    again = judged(given, given, given)  # A101 again, then A102 and N101
    assert run(sealed, results, "--resume", "freeze-1", made=[again])[0] == 0
    assert (calls(again, "judge"), again.answers) == (3, [])
    assert "run freeze-1: 0 of 3 saved before" in capsys.readouterr().out
    aside = sealed.outputs() / "set_a" / "A101.incomplete-1" / "run.json"
    assert aside.read_text(encoding="utf-8") == left[cut]
    assert read_json(record)["outcome"]["status"] == "done"
    rows = {row["photo_id"]: row for row in read_lines(results / "set_a.jsonl")}
    assert sorted(rows) == ["A101", "A102"]
    assert rows["A101"]["outcomes"]["landmark"]["status"] == "done"


def test_a_cut_short_retry_is_sent_again(tmp_path, capsys):
    # A101's first run fails at Meta's service; Ctrl+C comes during its retry, whose
    # record a closed window then leaves empty. The resume sends the retry again.
    sealed = write_sealed(tmp_path)
    results = tmp_path / "results"
    given = geometry_case()[2]
    first = judged(meta_error(503), given, given, KeyboardInterrupt())
    assert run(sealed, results, made=[first])[0] == 3
    retry = sealed.outputs() / "retry" / "set_a" / "A101"
    retry.mkdir(parents=True)
    (retry / "run.json").write_text("", encoding="utf-8")
    capsys.readouterr()
    again = judged(given)
    assert run(sealed, results, "--resume", "freeze-1", made=[again])[0] == 0
    assert again.answers == []
    assert "service failures retried: 1" in capsys.readouterr().out
    assert (retry.with_name("A101.incomplete-1") / "run.json").is_file()
    rows = {row["photo_id"]: row for row in read_lines(results / "set_a.jsonl")}
    assert rows["A101"]["outcomes"]["landmark"]["status"] == "done"


SAM_ALONE = {
    "set_b": ("B02-1-1", {"set_b": [truth_row(), truth_row(wheel="2")]}),
    "set_d": ("D01", {"set_d": [set_d_row(), set_d_row(wheel="right")]}),
}


@pytest.mark.parametrize("kind", ["set_b", "set_d"])
def test_an_item_meta_fails_is_retried_once(tmp_path, capsys, kind):
    # A Set B crop or a Set D photo whose send fails at Meta's service (a 400 on
    # every call) is saved as failed, sent once more after the rest, and counted
    # (MS6E-Q6, (a)). Failing again, its wheels are unmeasured as model_error, and
    # whether SAM found water is null.
    key, rows = SAM_ALONE[kind]
    variants = export.SET_B_VARIANTS if kind == "set_b" else export.SET_D_VARIANTS
    sealed = write_sealed(tmp_path / "down", **rows)
    results = tmp_path / "down" / "results"
    down = SamAloneFails(photos=3)
    assert run(sealed, results, made=[down])[0] == 0
    assert len(down.sends) == 2
    assert "service failures retried: 1" in capsys.readouterr().out
    # Each send's record holds the status alone, under the synthetic sealed folder.
    outputs = sealed.outputs()
    for folder in (outputs / kind / key, outputs / "retry" / kind / key):
        assert read_json(folder / "run.json") == {"meta_status": 400}
        assert sorted(path.name for path in folder.iterdir()) == ["run.json"]
    exported = read_lines(results / f"{kind}.jsonl")
    assert len(exported) == 2
    for row in exported:
        assert row["estimates"] == dict.fromkeys(variants, MODEL_ERROR)
        assert row["sam_water_found"] is None  # never answered (MS6E-Q6)
    assert read_json(results / "run.json")["service_retries"] == 1
    # A 400 once, then an answer: the retry's row is the row a clean run gives.
    clean = write_sealed(tmp_path / "clean", **rows)
    clean_results = tmp_path / "clean" / "results"
    assert run(clean, clean_results, made=[photo_client()])[0] == 0
    sealed = write_sealed(tmp_path / "once", **rows)
    results = tmp_path / "once" / "results"
    once = SamAloneFails(photos=3, failures=1)
    capsys.readouterr()
    assert run(sealed, results, made=[once])[0] == 0
    assert len(once.sends) == 2
    assert "service failures retried: 1" in capsys.readouterr().out
    retried = read_lines(results / f"{kind}.jsonl")
    assert retried == read_lines(clean_results / f"{kind}.jsonl")
    assert any(e["measured"] for row in retried for e in row["estimates"].values())
    assert all(isinstance(row["sam_water_found"], bool) for row in retried)
    assert read_json(results / "run.json")["service_retries"] == 1


def test_item_service_failures_in_a_row_stop_the_run(tmp_path, capsys):
    # Three Set D photos in a row that Meta's service fails are a lost connection,
    # as three photos are (R164): a stop, and each keeps its one retry.
    set_d = [set_d_row(photo_id) for photo_id in ("D01", "D02", "D03")]
    sealed = write_sealed(tmp_path, set_d=set_d)
    results = tmp_path / "results"
    down = SamAloneFails(photos=3, status=503)
    assert run(sealed, results, made=[down])[0] == 3
    assert len(down.sends) == 3
    assert "stopped: Meta's service failed on 3 sends in a row" in (
        capsys.readouterr().out
    )
    state = read_json(sealed.outputs() / "state.json")
    assert [stop["cause"] for stop in state["stops"]] == ["service_failed"]
    up = photo_client()
    assert run(sealed, results, "--resume", "freeze-1", made=[up])[0] == 0
    assert (calls(up, "segment"), calls(up, "judge")) == (3 * 3, 0)
    assert "service failures retried: 3" in capsys.readouterr().out
    assert read_json(results / "run.json")["service_retries"] == 3  # the whole run's
    rows = read_lines(results / "set_d.jsonl")
    assert [row["crop_id"] for row in rows] == ["D01", "D02", "D03"]
    assert all(row["estimates"]["geometry"]["measured"] for row in rows)


def test_service_retries_count_photos_and_items(tmp_path, capsys):
    # MS6E-Q6's count is the whole run's, every set's (MS6's report, Window 4's
    # word): A101's answer and the crop's first send fail at Meta's service, and
    # each is sent once more. The count is 2, as printed.
    sealed = write_sealed(tmp_path, set_b=[truth_row()])
    results = tmp_path / "results"
    fake = SamAloneFails(photos=3, failures=1, status=503)
    given = fake.answer
    first = [meta_error(503)]

    def first_answer_fails():
        fake.answer = first.pop() if first else given

    fake.on_judge = first_answer_fails
    assert run(sealed, results, made=[fake])[0] == 0
    assert "service failures retried: 2" in capsys.readouterr().out
    assert calls(fake, "judge") == 4
    assert (sealed.outputs() / "retry" / "set_a" / "A101" / "run.json").is_file()
    assert (sealed.outputs() / "retry" / "set_b" / "B02-1-1" / "run.json").is_file()
    assert read_json(results / "run.json")["service_retries"] == 2
    (row,) = read_lines(results / "set_b.jsonl")
    assert isinstance(row["sam_water_found"], bool)


def test_one_run_at_a_time(tmp_path, capsys):
    # Another window holds the run's lock: a start and a resume are refused before
    # any client is built or any prompt asked. The OS frees the lock when that
    # window ends, as when it closes, and the run resumes.
    sealed = write_sealed(tmp_path)
    results = tmp_path / "results"
    lock = sealed.root / "outputs" / "run.lock"
    with another_window(lock):
        assert run(sealed, results, made=[]) == (2, [])
        assert LOCK_REFUSAL in capsys.readouterr().out
    assert not sealed.outputs().exists()
    given = geometry_case()[2]
    assert run(sealed, results, made=[judged(given, KeyboardInterrupt())])[0] == 3
    state = sealed.outputs() / "state.json"
    before = state.read_bytes()
    with another_window(lock):
        assert run(sealed, results, "--resume", "freeze-1", made=[]) == (2, [])
        assert LOCK_REFUSAL in capsys.readouterr().out
    assert state.read_bytes() == before
    again = judged(given, given)
    assert run(sealed, results, "--resume", "freeze-1", made=[again])[0] == 0
    stops = read_json(results / "run.json")["stops"]
    assert [stop["cause"] for stop in stops] == ["interrupted"]


def test_a_prompt_that_fails_to_load_leaves_no_run(tmp_path, monkeypatch, capsys):
    # The prompt loads before the run is marked running, so its failure leaves no
    # state behind: a new start then goes ahead as the first.
    sealed = write_sealed(tmp_path)
    results = tmp_path / "results"
    loaded = tool.load_prompt

    class PromptUnreadable(Exception):
        pass

    def unreadable(folder):
        raise PromptUnreadable

    monkeypatch.setattr(tool, "load_prompt", unreadable)
    fake = photo_client()
    assert run(sealed, results, made=[fake])[0] == 3
    assert capsys.readouterr().err == "stopped: PromptUnreadable\n"
    assert fake.calls == []
    assert not sealed.outputs().exists()
    monkeypatch.setattr(tool, "load_prompt", loaded)
    assert run(sealed, results, made=[photo_client()])[0] == 0
    assert read_json(results / "run.json")["stops"] == []


def test_export_holds_only_the_row_contract(tmp_path, capsys):
    sealed = write_sealed(
        tmp_path,
        set_b=[truth_row(), truth_row(wheel="2")],
        set_d=[set_d_row(), set_d_row(wheel="right")],
    )
    results = tmp_path / "results"
    fake = photo_client()
    assert run(sealed, results, made=[fake])[0] == 0
    # 3 photos with their 5 phrases and an answer, then a crop and a Set D photo with
    # SAM's 3 phrases each.
    assert len(fake.calls) == 3 * 6 + 2 * 3
    assert sorted(path.name for path in results.iterdir()) == [
        "a_neg.jsonl",
        "run.json",
        "set_a.jsonl",
        "set_b.jsonl",
        "set_d.jsonl",
    ]
    manifest = read_json(results / "run.json")
    assert SEALED_RUN_FIELDS <= set(manifest) <= SEALED_RUN_FIELDS | OPTIONAL_RUN_FIELDS
    assert manifest["kind"] == "sealed"
    assert manifest["freeze_commit"] == FREEZE_1
    assert (manifest["baseline_level"], manifest["baseline_class"]) == ("knee", "NPLV")
    assert manifest["rules_version"] == "0.6"
    assert manifest["self_check_decided"] == "2026-10-31"
    assert (manifest["self_check"], manifest["geometry_default"]) == ("off", "on")
    assert manifest["stops"] == []
    assert manifest["service_retries"] == 0  # a clean run (MS6E-Q6)
    assert manifest["datasets"] == DATASETS
    assert (
        manifest["frozen"]["sam_phrases"] == "floodwater,wheel,wheel rim,person,vehicle"
    )
    set_a = read_lines(results / "set_a.jsonl")
    a_neg = read_lines(results / "a_neg.jsonl")
    assert [set(row) for row in set_a] == [SET_A_FIELDS] * 2
    assert [set(row) for row in a_neg] == [A_NEG_FIELDS]
    for row in set_a + a_neg:
        assert set(row["outcomes"]) == {"landmark", "geometry"}  # no replay results
        assert "reason" not in row["answer"]
    assert set_a[0]["m8"] == [
        {"box_id": 2, "kind": "wheel", "landmark": "hub", "vehicle_type": None}
    ]
    set_b = read_lines(results / "set_b.jsonl")
    assert [(row["crop_id"], row["wheel"]) for row in set_b] == [
        ("B02-1-1", 1),
        ("B02-1-1", 2),
    ]
    assert all(set(row) == WHEEL_FIELDS for row in set_b)
    assert set(set_b[0]["estimates"]) == {
        "geometry",
        "geometry_uncalibrated",
        "known_waterline",
        "known_waterline_uncalibrated",
    }
    set_d = read_lines(results / "set_d.jsonl")
    assert [(row["crop_id"], row["wheel"]) for row in set_d] == [("D01", 1), ("D01", 2)]
    assert all(set(row) == WHEEL_FIELDS - {"bins"} for row in set_d)
    assert all(
        set(row["estimates"]) == {"geometry", "geometry_uncalibrated"} for row in set_d
    )
    assert set_d[0]["estimates"]["geometry"]["measured"] is True
    # Nothing private reaches the export: no reason, free text or file name.
    written = "".join(path.read_text(encoding="utf-8") for path in results.iterdir())
    for private in (REASON, *FREE_TEXT, "MODEL-MARKER", "TAKEN-MARKER", ".jpg"):
        assert private not in written
    # The raw outputs stay under the synthetic sealed folder, Muse Spark's reason
    # among them (rules §10).
    outputs = sealed.outputs()
    spark = read_json(outputs / "set_a" / "A101" / "spark.json")
    assert spark["data"]["reason"] == REASON
    for folder in ("set_a/A102", "a_neg/N101", "set_b/B02-1-1", "set_d/D01"):
        assert (outputs / folder / "run.json").is_file()
        assert (outputs / folder / "sam" / "wheel.npz").is_file()


def test_prints_counts_only(tmp_path, capsys):
    twelve = "1234567890" + "12"  # built here, so the repo's account-ID scan is clean
    sealed = write_sealed(
        tmp_path,
        cells={"A102": {"level_label_raw": OTHER_LABEL, "notes": twelve}},
        set_b=[truth_row()],
        set_d=[set_d_row()],
    )
    results = tmp_path / "results"
    fake = judged(meta_error(503), *[geometry_case()[2]] * 3)
    code, _ = run(sealed, results, made=[fake], answers=("yes", "yes"))
    assert code == 0
    captured = capsys.readouterr()
    printed = captured.out + captured.err
    assert "inputs: set_a 2, a_neg 1, set_b 1, set_d 1" in printed
    assert "sent: 4 to the pipeline, 2 to SAM alone" in printed
    assert "labels written as (other words): 1" in printed
    assert "service failures retried: 1" in printed
    assert re.search("billed calls: [0-9]+, estimated cost [$][0-9.]+", printed)
    assert "export: set_a 2, a_neg 1, set_b 1, set_d 1" in printed
    private = [
        *sealed.rows,
        "B02",
        "D01",
        ".jpg",
        "Knee",
        "NPLV",
        "MARKETMARKER",
        REASON,
        *FREE_TEXT,
        str(tmp_path),
        tmp_path.name,
        "sealed",
        "run-1",
    ]
    assert [text for text in private if text in printed] == []
    assert re.search("[0-9]{12}", printed) is None


def test_inputs_are_named_by_kind_never_by_cell(tmp_path, monkeypatch, capsys):
    results = tmp_path / "results"

    def refused(sealed, expected):
        assert run(sealed, results, made=[]) == (2, [])
        out = capsys.readouterr().out
        assert expected in out
        return out

    # Set B's parser names a sealed crop by its id: only the kind is printed.
    sealed = write_sealed(tmp_path / "1", set_b=[truth_row(vehicle_type="jeepney")])
    out = refused(sealed, "invalid: Set B's truth.csv breaks its format\n")
    assert "B02" not in out
    # A row number, where the parser names one.
    sealed = write_sealed(tmp_path / "2", set_b=[truth_row(crop_id="bad crop")])
    refused(sealed, "invalid: Set B's truth.csv breaks its format, row 1\n")
    sealed = write_sealed(tmp_path / "3", cells={"A102": {"photo_file": "../A102.jpg"}})
    refused(sealed, "invalid: the Set A manifest breaks its format, row 2\n")
    sealed = write_sealed(tmp_path / "4", set_d=[set_d_row(wheel="middle")])
    refused(sealed, "invalid: Set D's set_d_log.csv breaks its format, row 1\n")
    sealed = write_sealed(tmp_path / "5", cells={"N101": {"duplicate": "maybe"}})
    refused(sealed, "invalid: the A-neg manifest breaks its format, row 1\n")
    # Every file the logs name is there before anything is paid for.
    sealed = write_sealed(tmp_path / "6", set_b=[truth_row()])
    (sealed.root / "set_b" / "crops" / "B02-1-1.jpg").unlink()
    refused(sealed, "refused: 1 of the files the logs name are missing\n")
    # A development summary.json, with its baseline pair, or nothing is read.
    sealed = write_sealed(tmp_path / "7")
    write_summary(tmp_path / "7", kind="sealed")
    refused(sealed, "refused: --baseline must be a development report's summary.json")
    # Without the harness, the labels can't be checked: refused before the folder is
    # read, so a folder that doesn't exist is never reached.
    monkeypatch.setattr(tool, "RUN_EVAL", tmp_path / "nowhere" / "run_eval.py")
    missing = Sealed(tmp_path / "8" / "sealed", write_summary(tmp_path / "8"), {})
    refused(missing, "refused: the harness isn't on this branch")
    assert not missing.root.exists()


def test_a_resume_takes_the_run_s_own_settings(tmp_path, capsys):
    sealed = write_sealed(tmp_path)
    results = tmp_path / "results"
    first = judged(KeyboardInterrupt())
    assert run(sealed, results, made=[first])[0] == 3
    # Another geometry default, or another baseline, than the run started with.
    changed = ("--resume", "freeze-1", "--geometry-default", "off")
    assert run(sealed, results, *changed, made=[]) == (2, [])
    write_summary(tmp_path, baseline_level="waist")
    assert run(sealed, results, "--resume", "freeze-1", made=[]) == (2, [])
    assert "the run started with other settings" in capsys.readouterr().out


def test_the_rules_version_is_checked_before_paying(tmp_path, capsys):
    # The stand-in prints 0.6 and \r\n, as Windows ends it. --baseline's 0.5 isn't
    # the frozen harness's: refused before any client is built, any prompt asked or
    # anything made under outputs/, and nothing printed names a path.
    sealed = write_sealed(tmp_path)
    results = tmp_path / "results"
    write_summary(tmp_path, rules_version="0.5")
    assert run(sealed, results, made=[]) == (2, [])
    out = capsys.readouterr().out
    assert out.endswith(RULES_REFUSAL)
    for path in (str(tmp_path), tmp_path.name, "summary.json", "run_eval"):
        assert path not in out
    assert not (sealed.root / "outputs").exists()
    assert not results.exists()
    # --baseline's 0.6 is the harness's: the run goes on.
    write_summary(tmp_path, rules_version=RULES)
    fake = photo_client()
    assert run(sealed, results, made=[fake])[0] == 0
    assert calls(fake, "judge") == 3
    assert read_json(results / "run.json")["rules_version"] == RULES


def test_the_rules_version_needs_the_harness(tmp_path, monkeypatch, capsys):
    sealed = write_sealed(tmp_path)
    results = tmp_path / "results"
    no_version = "refused: the harness's --rules-version gave no version\n"
    # An older harness, which knows no --rules-version, and one that prints a blank
    # line: refused before anything is paid for or made.
    for version in (None, " "):
        stand_in(tool.RUN_EVAL, version)
        assert run(sealed, results, made=[]) == (2, [])
        assert capsys.readouterr().out.endswith(no_version)
        assert not (sealed.root / "outputs").exists()

    # One that can't be run.
    def times_out(*args, **kwargs):
        raise tool.subprocess.TimeoutExpired(cmd="run_eval.py", timeout=60)

    with monkeypatch.context() as patched:
        patched.setattr(tool.subprocess, "run", times_out)
        with pytest.raises(SystemExit) as refused:
            tool.rules_version()
    assert refused.value.code == 2
    assert capsys.readouterr().out == no_version
    # A missing harness: a run is refused at the label words, before the version,
    # and the version's own check refuses it too.
    monkeypatch.setattr(tool, "RUN_EVAL", tmp_path / "nowhere" / "run_eval.py")
    assert run(sealed, results, made=[]) == (2, [])
    assert "refused: the harness isn't on this branch" in capsys.readouterr().out
    with pytest.raises(SystemExit) as refused:
        tool.rules_version()
    assert refused.value.code == 2
    assert capsys.readouterr().out == (
        "refused: the harness isn't on this branch, so the rules version can't be"
        " checked\n"
    )
    assert not (sealed.root / "outputs").exists()
    assert not results.exists()


def test_words_are_the_harness_s(monkeypatch):
    # The stand-in prints WORDS: they must be the words the real harness prints, run
    # as the tool runs it (MS6's C420).
    harness = REPO / "eval" / "run_eval.py"
    if not harness.is_file():
        pytest.skip("eval/run_eval.py isn't in this tree")
    monkeypatch.setattr(tool, "RUN_EVAL", harness)
    assert sorted(tool.label_words()) == WORDS


def test_the_rules_version_is_the_harness_s(tmp_path, monkeypatch):
    # The real harness's --rules-version, run as the tool runs it, stripped, is a
    # version the tool takes from --baseline's summary.json (MS6's C424).
    harness = REPO / "eval" / "run_eval.py"
    if not harness.is_file():
        pytest.skip("eval/run_eval.py isn't in this tree")
    monkeypatch.setattr(tool, "RUN_EVAL", harness)
    version = tool.rules_version()
    assert isinstance(version, str) and version and version == version.strip()
    folder = tmp_path / "data" / "sealed" / "run-1"  # never reached
    summary = write_summary(tmp_path, rules_version=version)
    argv = argv_for(folder, summary, tmp_path / "results")
    assert tool._settings(tool._parse(argv))["rules_version"] == version


def test_the_harness_loads_a_sealed_export(tmp_path, monkeypatch):
    # End to end through MS6's own loader, run as its command, so nothing here
    # imports eval/ (C321): a synthetic sealed export whose one crop Meta's service
    # failed twice loads, with its service_retries and a null sam_water_found, and
    # its report is written under tmp_path.
    harness = REPO / "eval" / "run_eval.py"
    if not harness.is_file():
        pytest.skip("eval/run_eval.py isn't in this tree")
    monkeypatch.setattr(tool, "RUN_EVAL", harness)
    sealed = write_sealed(tmp_path, set_b=[truth_row(), truth_row(wheel="2")])
    write_summary(tmp_path, rules_version=tool.rules_version())
    results = tmp_path / "results"
    assert run(sealed, results, made=[SamAloneFails(photos=3)])[0] == 0
    assert read_json(results / "run.json")["service_retries"] == 1
    rows = read_lines(results / "set_b.jsonl")
    assert [row["sam_water_found"] for row in rows] == [None, None]
    done = subprocess.run(
        [sys.executable, "-I", "-B", str(harness), "--from-saved"]
        + ["--results", str(results), "--write"],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert done.returncode == 0, done.stdout[-2000:]
    summary = read_json(results / "report" / "summary.json")
    assert (summary["kind"], summary["service_retries"]) == ("sealed", 1)
    assert summary["set_b"]["sam_water_found"] == {"k": 0, "n": 0}
    assert summary["set_b"]["no_answer"] == 2
