"""Tests for the offline runner, probes/run_pipeline.py (spec §3.7; C62, C66, C73, C87).

The runner isn't a package module, so it is loaded from its file. Wherever a run goes
live, make_client is replaced by a FakeClient, so no Meta call is made. Every test
runs with MODEL_API_KEY unset and LUSOT_DATA_DIR inside tmp_path, so none can reach
Meta or the real data folder.
"""

import dataclasses
import importlib.util
import json
import re
from pathlib import Path

import pytest
from fakes import (
    REPO_PROMPTS,
    FakeClient,
    geometry_case,
    level_case,
    meta_error,
    noise_jpeg,
)

from lusot_analysis import handler
from lusot_analysis.meta_client import ModelRefused
from lusot_analysis.pipeline import READING_PHRASES
from lusot_analysis.pipeline.types import Outcome
from lusot_analysis.tuning import START, TUNING

RUNNER = Path(__file__).parents[1] / "probes" / "run_pipeline.py"
REASON = "REASON-MARKER-31"  # the reason fakes.answer gives every answer
# The settings MS3b's runs record in run.json (v0.7 item 10.1)
CONFIG_KEYS = (
    "geometry_in_level",
    "tuning",
    "tire_codes_version",
    "reasoning_effort",
    "drawing_version",
    "sam_from",
)


def load_runner():
    spec = importlib.util.spec_from_file_location("run_pipeline_script", RUNNER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = load_runner()


@pytest.fixture(autouse=True)
def offline(tmp_path, monkeypatch):
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    monkeypatch.setenv("LUSOT_DATA_DIR", str(tmp_path / "data"))


def no_client():
    raise AssertionError("the runner built a Meta client")


def write_photo(path: Path) -> Path:
    """The level case's photo, written to `path`."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(level_case()[0])
    return path


def live_run(tmp_path, monkeypatch, capsys, client=None, *, case=level_case, flags=()):
    """A live run of `case`'s photo, tmp_path/street.jpg, through main, with `flags`.

    make_client gives `client`, by default a FakeClient on `case`, the level case by
    default, and the data folder is tmp_path. The run starts from START (R128).
    Returns the photo, the run folder, the fake and stdout.
    """
    data, sam, given = case()
    fake = FakeClient(sam, given) if client is None else client
    monkeypatch.setattr(runner, "make_client", lambda: fake)
    photo = tmp_path / "street.jpg"
    photo.write_bytes(data)
    argv = ["live", str(photo), "--data-dir", str(tmp_path), *flags]
    assert runner.main(argv, tuning=START) == 0
    (run_dir,) = (tmp_path / "runs").glob("*/*")
    return photo, run_dir, fake, capsys.readouterr().out


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def judged_efforts(client: FakeClient) -> list[object]:
    """The reasoning effort of each judge call the fake recorded."""
    return [
        keywords["reasoning_effort"]
        for (kind, _, _), keywords in zip(client.calls, client.keywords, strict=True)
        if kind == "judge"
    ]


def no_segment(phrase: str) -> None:
    """A segment hook for a run that must pay for no SAM call."""
    raise AssertionError("a SAM call was made")


@pytest.mark.parametrize(
    "parts",
    [
        ("sealed", "x.jpg"),
        ("a", "Sealed", "x.jpg"),
        ("sealed", "sub", "..", "x.jpg"),
    ],
    ids=["sealed", "any-case", "dot-dot"],
)
def test_refuses_paths_inside_sealed_folders(tmp_path, monkeypatch, capsys, parts):
    # None of these exists, and the test creates none: the refusal comes before
    # anything is opened, listed or built (C66).
    path = tmp_path.joinpath(*parts)
    monkeypatch.setattr(runner, "make_client", no_client)
    assert runner.main(["live", str(path)]) == 2
    assert "refused: path inside a folder named sealed" in capsys.readouterr().out
    with pytest.raises(SystemExit) as exc:
        runner.refuse_sealed(path)
    assert exc.value.code == 2
    assert list(tmp_path.iterdir()) == []
    runner.refuse_sealed(tmp_path / "unsealed" / "x.jpg")  # a part must equal it


class LinkedPath:
    """Stands in for a link: as written it names no sealed folder, but it resolves
    into one. Nothing is made on disk, so no symlink and no sealed folder is needed.
    """

    def __init__(self, written: Path, resolved: Path) -> None:
        self.written, self.resolved = written, resolved

    def absolute(self) -> Path:
        return self.written

    def resolve(self) -> Path:
        return self.resolved


def test_refuses_a_path_that_resolves_into_a_sealed_folder(tmp_path, capsys):
    link = LinkedPath(tmp_path / "a" / "x.jpg", tmp_path / "sealed" / "x.jpg")
    with pytest.raises(SystemExit) as exc:
        runner.refuse_sealed(link)
    assert exc.value.code == 2
    assert capsys.readouterr().out == "refused: path inside a folder named sealed\n"
    # Resolving elsewhere passes, and nothing was made.
    runner.refuse_sealed(LinkedPath(tmp_path / "a" / "x.jpg", tmp_path / "b" / "x.jpg"))
    assert list(tmp_path.iterdir()) == []


def test_refuses_sealed_data_and_run_folders(tmp_path, monkeypatch, capsys):
    # The folders written to and read from are checked too, before the photo is read.
    photo = tmp_path / "street.jpg"  # never written
    monkeypatch.setattr(runner, "make_client", no_client)
    data_dir = tmp_path / "SEALED" / "data"
    assert runner.main(["live", str(photo), "--data-dir", str(data_dir)]) == 2
    assert runner.main(["replay", str(photo), str(tmp_path / "sealed" / "run")]) == 2
    out = capsys.readouterr().out
    assert out.count("refused: path inside a folder named sealed") == 2
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("folder", ["sturm_flooddepth", "STURM_FloodDepth"])
def test_live_refuses_sturm_photos(tmp_path, monkeypatch, capsys, folder):
    # C87: STURM photos stay offline. No client is built, so nothing reaches Meta.
    sturm = tmp_path / "set_c" / folder / "x.jpg"
    monkeypatch.setattr(runner, "make_client", no_client)
    assert runner.main(["live", str(sturm)]) == 2
    assert "refused: STURM photos stay offline" in capsys.readouterr().out
    assert list(tmp_path.iterdir()) == []
    # A replay makes no Meta call, so this rule doesn't refuse it: the same bytes,
    # recorded live from another folder, replay from the STURM one.
    _, run_dir, _, _ = live_run(tmp_path, monkeypatch, capsys)
    write_photo(sturm)
    monkeypatch.setattr(runner, "make_client", no_client)
    assert runner.main(["replay", str(sturm), str(run_dir)]) == 0
    assert "same as saved: True" in capsys.readouterr().out


@pytest.mark.parametrize("where", ["under", "root", "dot"])
def test_live_refuses_a_data_folder_inside_the_repo(
    tmp_path, monkeypatch, capsys, where
):
    # R111: a run folder holds masks and Muse Spark's reason (C62), and runs/ isn't
    # git-ignored, so runs stay out of the repo (spec §3.7). None of these exists,
    # and none is made: the refusal comes before any client, call or folder.
    analysis = RUNNER.parents[1]
    repo_runner = runner.REPO / "backend" / "analysis" / "probes" / "run_pipeline.py"
    assert repo_runner == RUNNER.resolve()  # the repo is exactly 3 folders up
    data_dir = {
        "under": analysis / "runs-r111-test",
        "root": analysis.parents[1],
        "dot": Path("."),  # the folder the runner is run from
    }[where]
    monkeypatch.chdir(analysis)
    monkeypatch.setattr(runner, "make_client", no_client)
    photo = write_photo(tmp_path / "street.jpg")
    assert runner.main(["live", str(photo), "--data-dir", str(data_dir)]) == 2
    assert capsys.readouterr().out == "refused: the data folder is inside the repo\n"
    assert not (analysis / "runs-r111-test").exists()
    assert not (analysis / "runs").exists()
    assert not (analysis.parents[1] / "runs").exists()


def test_the_sealed_check_comes_before_the_repo_check(tmp_path, monkeypatch, capsys):
    # The repo check resolves the data folder, so a folder that names sealed must be
    # refused first, before anything resolves it.
    monkeypatch.setattr(runner, "make_client", no_client)
    data_dir = LinkedPath(tmp_path / "sealed" / "data", RUNNER.parents[1] / "runs")
    with pytest.raises(SystemExit) as exc:
        runner.live(write_photo(tmp_path / "street.jpg"), data_dir)
    assert exc.value.code == 2
    assert capsys.readouterr().out == "refused: path inside a folder named sealed\n"


def test_live_sends_the_reading_phrases_and_saves_under_the_data_dir(
    tmp_path, monkeypatch, capsys
):
    photo, run_dir, fake, out = live_run(tmp_path, monkeypatch, capsys)
    # <data dir>/runs/<YYYY-MM-DD>/<photo stem>-<HHMMSS>, outside the repo (C8, C30)
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", run_dir.parent.name)
    assert re.fullmatch(r"street-\d{6}", run_dir.name)
    assert (run_dir / "run.json").is_file()
    # The 5 phrases the reading uses, never a face or a plate (C66).
    segments = [phrase for kind, phrase, _ in fake.calls if kind == "segment"]
    assert sorted(segments) == sorted(READING_PHRASES)
    assert [kind for kind, _, _ in fake.calls].count("judge") == 1
    # The offline runner sets no deadline (C84).
    assert all(keywords["deadline"] is None for keywords in fake.keywords)
    # Counts and timings only: never the answer, its reason or a path.
    assert "meta_calls" in out
    assert REASON not in out
    # Geometry is on by default. The level case has no rim, so its wheel keeps the
    # landmark reading.
    assert out.splitlines() == [
        "outcome: done/level, level knee",
        "level_from: landmark",
        "meta_calls: 6",
        "reasoning_effort: default",
        "drawing_version: boxes-v1",
        "SAM floodwater: instances 1, 500 ms",
        "SAM wheel: instances 1, 500 ms",
        "SAM wheel rim: instances 0, 500 ms",
        "SAM person: instances 0, 500 ms",
        "SAM vehicle: instances 1, 500 ms",
        "Muse Spark: 1500 ms, tokens 1000 in, 200 out",
        "reasoning_tokens: None",
        "drops: {}",
        "wheels_measured: 0",
        'geometry_checks: {"rim_missing": 1}',
    ]
    assert str(photo.parent) not in out


@pytest.mark.parametrize("key", ["\x16", None], ids=["short", "missing"])
def test_missing_or_short_key_exits_2_without_echo(tmp_path, monkeypatch, capsys, key):
    # The real make_client: MetaClient refuses the key before any network use.
    if key is not None:
        monkeypatch.setenv("MODEL_API_KEY", key)
    photo = write_photo(tmp_path / "street.jpg")
    assert runner.main(["live", str(photo), "--data-dir", str(tmp_path)]) == 2
    captured = capsys.readouterr()
    assert captured.out == "refused: MODEL_API_KEY is missing or too short\n"
    assert "\x16" not in captured.out + captured.err
    assert not (tmp_path / "runs").exists()


def test_rejected_key_exits_2(tmp_path, monkeypatch, capsys):
    # C73: Meta rejected the key or the account. That isn't the photo's result, so
    # nothing is saved.
    def rejected(phrase: str) -> None:
        raise meta_error(401)

    _, sam, given = level_case()
    fake = FakeClient(sam, given, on_segment=rejected)
    monkeypatch.setattr(runner, "make_client", lambda: fake)
    photo = write_photo(tmp_path / "street.jpg")
    assert runner.main(["live", str(photo), "--data-dir", str(tmp_path)]) == 2
    out = capsys.readouterr().out
    assert out == "refused: Meta rejected the key or the account (HTTP 401)\n"
    assert not (tmp_path / "runs").exists()


def test_replay_needs_no_key(tmp_path, monkeypatch, capsys):
    photo, run_dir, _, live_out = live_run(tmp_path, monkeypatch, capsys)
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    monkeypatch.setattr(runner, "make_client", no_client)
    assert runner.main(["replay", str(photo), str(run_dir)]) == 0
    out = capsys.readouterr().out
    assert "same as saved: True" in out
    # The same counts and timings as the live run, then the comparison.
    assert out.splitlines() == [*live_out.splitlines(), "same as saved: True"]
    assert REASON not in out


def failing_wheel(error: Exception):
    """A segment hook that fails the wheel call with `error`, and no other call."""

    def hook(phrase: str) -> None:
        if phrase == "wheel":
            raise error

    return hook


@pytest.mark.parametrize(
    ("judged", "hook", "outcome"),
    [
        pytest.param(
            ModelRefused("Muse Spark refused to answer"),
            None,
            "refused/model_declined",
            id="refusal",
        ),
        pytest.param(
            None, failing_wheel(meta_error(500)), "failed/model_error", id="sam-500"
        ),
        pytest.param(
            None,
            failing_wheel(AttributeError("boom")),
            "failed/pipeline_error",
            id="not-meta",
        ),
    ],
)
def test_refused_and_failed_runs_replay_as_saved(
    tmp_path, monkeypatch, capsys, judged, hook, outcome
):
    # R109: `same as saved` flags only real differences, so a run that ended on a
    # refusal or a failed call replays to its live outcome.
    _, sam, given = level_case()
    client = FakeClient(sam, given if judged is None else judged, on_segment=hook)
    photo, run_dir, _, live_out = live_run(tmp_path, monkeypatch, capsys, client)
    assert live_out.splitlines()[0] == f"outcome: {outcome}"
    monkeypatch.setattr(runner, "make_client", no_client)
    assert runner.main(["replay", str(photo), str(run_dir)]) == 0
    out = capsys.readouterr().out.splitlines()
    assert (out[0], out[-1]) == (f"outcome: {outcome}", "same as saved: True")


def test_replay_of_another_photo_exits_2(tmp_path, monkeypatch, capsys):
    _, run_dir, _, _ = live_run(tmp_path, monkeypatch, capsys)
    other = tmp_path / "other.jpg"
    other.write_bytes(noise_jpeg(seed=1))
    assert runner.main(["replay", str(other), str(run_dir)]) == 2
    out = capsys.readouterr().out
    assert out == "refused: saved outputs belong to another photo\n"


def test_replay_that_differs_exits_1(tmp_path, monkeypatch, capsys):
    photo, run_dir, _, _ = live_run(tmp_path, monkeypatch, capsys)
    saved = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    saved["outcome"] = dataclasses.asdict(Outcome.no_flood())
    (run_dir / "run.json").write_text(json.dumps(saved), encoding="utf-8")
    assert runner.main(["replay", str(photo), str(run_dir)]) == 1
    assert capsys.readouterr().out.splitlines()[-1] == "same as saved: False"


@pytest.mark.parametrize("command", ["live", "replay"])
def test_a_missing_photo_exits_3(tmp_path, monkeypatch, capsys, command):
    # R110: a run that can't read what it needs ends 3, never 1 (a replay that
    # differs), and names the error's class only: no path, no message.
    _, sam, given = level_case()
    monkeypatch.setattr(runner, "make_client", lambda: FakeClient(sam, given))
    photo = tmp_path / "gone-r110.jpg"
    folder = ["--data-dir", str(tmp_path)] if command == "live" else [str(tmp_path)]
    assert runner.main([command, str(photo), *folder]) == 3
    captured = capsys.readouterr()
    assert captured.out == "failed: FileNotFoundError\n"
    assert photo.name not in captured.out + captured.err


@pytest.mark.parametrize(
    ("text", "error"),
    [(None, "FileNotFoundError"), ("{not json", "JSONDecodeError")],
    ids=["missing", "corrupt"],
)
def test_a_missing_or_corrupt_run_record_exits_3(
    tmp_path, monkeypatch, capsys, text, error
):
    photo, run_dir, _, _ = live_run(tmp_path, monkeypatch, capsys)
    if text is None:
        (run_dir / "run.json").unlink()
    else:
        (run_dir / "run.json").write_text(text, encoding="utf-8")
    assert runner.main(["replay", str(photo), str(run_dir)]) == 3
    captured = capsys.readouterr()
    assert captured.out == f"failed: {error}\n"
    assert photo.name not in captured.out + captured.err


def test_live_and_replay_return_their_runs(tmp_path, monkeypatch):
    # live and replay are what the handler's B3 test calls (Task 13).
    _, sam, given = level_case()
    monkeypatch.setattr(runner, "make_client", lambda: FakeClient(sam, given))
    photo = write_photo(tmp_path / "street.jpg")
    run_dir, live = runner.live(photo, tmp_path)
    assert run_dir.parent.parent == tmp_path / "runs"
    monkeypatch.setattr(runner, "make_client", no_client)
    replayed = runner.replay(photo, run_dir)
    assert replayed.outcome == live.outcome
    assert replayed.log == live.log


# MS3b: the geometry setting, the tuning, the effort and the drawing in saved runs


def test_live_records_the_geometry_config(tmp_path, monkeypatch):
    # v0.7 item 10.1: a run folder records what it was run with (C316).
    data, sam, given = geometry_case()
    monkeypatch.setattr(runner, "make_client", lambda: FakeClient(sam, given))
    photo = tmp_path / "street.jpg"
    photo.write_bytes(data)
    run_dir, run = runner.live(photo, tmp_path, tuning=START)
    assert run.outcome.level_from == "geometry"
    saved = read_json(run_dir / "run.json")
    assert {key: saved[key] for key in CONFIG_KEYS} == {
        "geometry_in_level": True,
        "tuning": {**dataclasses.asdict(START), "untuned": sorted(START.untuned)},
        "tire_codes_version": "tire-codes-v1",
        "reasoning_effort": None,
        "drawing_version": "boxes-v1",
        "sam_from": False,
    }
    assert saved["tuning"]["version"] == "tuning-v1"


@pytest.mark.parametrize(
    ("geometry", "outcome"),
    [("off", "refused/no_usable_reference"), ("on", "done/level, level half_knee")],
)
def test_replay_uses_the_saved_config(tmp_path, monkeypatch, capsys, geometry, outcome):
    # C309, C318: off, a van is dropped by its type; on, geometry alone reads its
    # wheel. A replay takes the setting and the tuning from run.json, so each run
    # replays to its own outcome.
    photo, run_dir, _, live_out = live_run(
        tmp_path,
        monkeypatch,
        capsys,
        case=lambda: geometry_case("van"),
        flags=("--geometry", geometry),
    )
    assert live_out.splitlines()[0] == f"outcome: {outcome}"
    assert read_json(run_dir / "run.json")["geometry_in_level"] is (geometry == "on")
    monkeypatch.setattr(runner, "make_client", no_client)
    assert runner.main(["replay", str(photo), str(run_dir)]) == 0
    out = capsys.readouterr().out.splitlines()
    assert (out[0], out[-1]) == (f"outcome: {outcome}", "same as saved: True")


def test_effort_and_drawing_flags_reach_judge(tmp_path, monkeypatch, capsys):
    # C312, C325: a development run's flags change what Muse Spark is sent, and the
    # run records them, so runs at different settings never mix (finding 5).
    photo, run_dir, fake, out = live_run(
        tmp_path,
        monkeypatch,
        capsys,
        flags=("--effort", "low", "--drawing", "boxes-v2"),
    )
    assert judged_efforts(fake) == ["low"]
    saved = read_json(run_dir / "run.json")
    assert (saved["reasoning_effort"], saved["drawing_version"]) == ("low", "boxes-v2")
    assert (saved["tuning"]["reasoning_effort"], saved["tuning"]["drawing"]) == (
        "low",
        "boxes-v2",
    )
    assert {"reasoning_effort: low", "drawing_version: boxes-v2"} <= set(
        out.splitlines()
    )
    # `default` sends no effort, even when the tuning names one: Muse Spark picks.
    _, sam, given = level_case()
    fake = FakeClient(sam, given)
    monkeypatch.setattr(runner, "make_client", lambda: fake)
    run_dir = tmp_path / "default-effort"
    argv = ["live", str(photo), "--run-dir", str(run_dir), "--effort", "default"]
    high = dataclasses.replace(START, reasoning_effort="high")
    assert runner.main(argv, tuning=high) == 0
    assert judged_efforts(fake) == [None]
    assert read_json(run_dir / "run.json")["reasoning_effort"] is None


@pytest.mark.parametrize(
    "flags",
    [("--effort", "extreme"), ("--drawing", "boxes-v9"), ("--geometry", "maybe")],
    ids=["effort", "drawing", "geometry"],
)
def test_unknown_flag_values_are_usage_errors(tmp_path, monkeypatch, capsys, flags):
    # R146: argparse's choices refuse them with its usage error, exit 2, before any
    # file is opened, any client is built or anything is paid for.
    photo = tmp_path / "street.jpg"  # never written
    monkeypatch.setattr(runner, "make_client", no_client)
    with pytest.raises(SystemExit) as exc:
        runner.main(["live", str(photo), *flags])
    assert exc.value.code == 2
    assert "invalid choice" in capsys.readouterr().err
    assert list(tmp_path.iterdir()) == []


@pytest.fixture
def handler_prompts(monkeypatch):
    """The repo's prompts as the handler's PROMPTS_DIR, read fresh by the test."""
    monkeypatch.setenv("PROMPTS_DIR", str(REPO_PROMPTS))
    handler._prompt.cache_clear()
    yield
    handler._prompt.cache_clear()


def test_handler_and_runner_send_the_same_effort(
    tmp_path, monkeypatch, handler_prompts
):
    # §D2: with their defaults, the laptop and the Lambda send Muse Spark the live
    # TUNING's effort and draw its boxes the same way. It reads TUNING's fields, with
    # no number of its own (R128).
    data, sam, given = level_case()
    laptop, cloud = FakeClient(sam, given), FakeClient(sam, given)
    monkeypatch.setattr(runner, "make_client", lambda: laptop)
    photo = tmp_path / "street.jpg"
    photo.write_bytes(data)
    run_dir, live = runner.live(photo, tmp_path)
    handled = handler.analyse(data, cloud)
    assert judged_efforts(laptop) == judged_efforts(cloud) == [TUNING.reasoning_effort]
    assert live.log["reasoning_effort"] == handled.log["reasoning_effort"]
    assert live.log["drawing_version"] == handled.log["drawing_version"]
    assert handled.log["drawing_version"] == TUNING.drawing
    saved = read_json(run_dir / "run.json")
    assert (saved["reasoning_effort"], saved["drawing_version"]) == (
        TUNING.reasoning_effort,
        TUNING.drawing,
    )


def test_sam_from_pays_only_for_judge(tmp_path, monkeypatch, capsys):
    # C312's runs of Muse Spark alone: --sam-from reuses a saved run's SAM outputs,
    # so only judge is paid for, and the run is saved as a run of its own.
    photo, first, _, _ = live_run(tmp_path, monkeypatch, capsys)
    _, sam, given = level_case()
    fake = FakeClient(sam, given, on_segment=no_segment)
    monkeypatch.setattr(runner, "make_client", lambda: fake)
    judged = tmp_path / "judged"
    argv = ["live", str(photo), "--run-dir", str(judged), "--sam-from", str(first)]
    assert runner.main(argv, tuning=START) == 0
    assert [kind for kind, _, _ in fake.calls] == ["judge"]
    assert capsys.readouterr().out.splitlines()[0] == "outcome: done/level, level knee"
    saved = read_json(judged / "run.json")
    assert saved["sam_from"] is True
    assert saved["phrases"] == list(READING_PHRASES)
    # The new run replays to its own saved outcome, with no call at all.
    monkeypatch.setattr(runner, "make_client", no_client)
    assert runner.main(["replay", str(photo), str(judged)]) == 0
    assert capsys.readouterr().out.splitlines()[-1] == "same as saved: True"


def test_run_dir_flag_writes_there(tmp_path, monkeypatch, capsys):
    _, sam, given = level_case()
    monkeypatch.setattr(runner, "make_client", lambda: FakeClient(sam, given))
    photo = write_photo(tmp_path / "street.jpg")
    run_dir = tmp_path / "elsewhere" / "run-1"
    argv = ["live", str(photo), "--data-dir", str(tmp_path / "data"), "--run-dir"]
    assert runner.main([*argv, str(run_dir)], tuning=START) == 0
    assert (run_dir / "run.json").is_file()
    assert not (tmp_path / "data").exists()
    assert "elsewhere" not in capsys.readouterr().out  # no path is printed
    returned, _ = runner.live(
        photo, tmp_path / "data", run_dir=tmp_path / "run-2", tuning=START
    )
    assert returned == tmp_path / "run-2"
    assert (returned / "run.json").is_file()


@pytest.mark.parametrize("flag", ["--run-dir", "--sam-from"])
def test_sealed_run_dirs_are_refused(tmp_path, monkeypatch, capsys, flag):
    # C66: the run folder written and the one read from are checked too, before the
    # photo is read. None of these exists, and none is made.
    photo = tmp_path / "street.jpg"  # never written
    monkeypatch.setattr(runner, "make_client", no_client)
    folder = tmp_path / "Sealed" / "run"
    argv = ["live", str(photo), "--data-dir", str(tmp_path / "data"), flag]
    assert runner.main([*argv, str(folder)]) == 2
    assert capsys.readouterr().out == "refused: path inside a folder named sealed\n"
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("flag", ["--run-dir", "--sam-from"])
def test_repo_run_dirs_are_refused(tmp_path, monkeypatch, capsys, flag):
    # R131: a run folder holds masks and Muse Spark's reason (C62), so one inside the
    # repo is refused, to write or to read, before any client, call or folder.
    folder = RUNNER.parents[1] / "runs-r131-test"
    monkeypatch.setattr(runner, "make_client", no_client)
    photo = write_photo(tmp_path / "street.jpg")
    argv = ["live", str(photo), "--data-dir", str(tmp_path), flag, str(folder)]
    assert runner.main(argv) == 2
    assert capsys.readouterr().out == "refused: the data folder is inside the repo\n"
    assert not folder.exists()
    assert not (tmp_path / "runs").exists()


def test_old_runs_replay_with_geometry_off(tmp_path, monkeypatch, capsys):
    # An MS3a run folder: its run.json has none of the new keys, and its outcome none
    # of Task 4's three fields. It replays with geometry off and START. The level
    # case's water touches its wheel, so step 3 changes nothing, and the outcome is
    # the saved one (R141).
    photo, run_dir, _, _ = live_run(tmp_path, monkeypatch, capsys)
    saved = read_json(run_dir / "run.json")
    for key in CONFIG_KEYS:
        del saved[key]
    for key in ("level_from", "depth_in_min", "depth_in_max"):
        del saved["outcome"][key]
    (run_dir / "run.json").write_text(json.dumps(saved), encoding="utf-8")
    monkeypatch.setattr(runner, "make_client", no_client)
    replayed = runner.replay(photo, run_dir)
    logged = (replayed.log["geometry_in_level"], replayed.log["tuning_version"])
    assert logged == ("off", START.version)
    assert "wheels_measured" not in replayed.log
    assert runner.main(["replay", str(photo), str(run_dir)]) == 0
    assert capsys.readouterr().out.splitlines()[-1] == "same as saved: True"


def test_replay_refuses_runs_saved_under_other_cut_values(
    tmp_path, monkeypatch, capsys
):
    # R144: C56's 40 px rule and C70's caps are constants, never swept, so a replay
    # can't number boxes under a run's own values. A run.json that records others is
    # refused before the pipeline runs.
    photo, run_dir, _, _ = live_run(tmp_path, monkeypatch, capsys)
    monkeypatch.setattr(runner, "make_client", no_client)
    text = (run_dir / "run.json").read_text(encoding="utf-8")
    for name in ("min_wheel_side_px", "max_vehicles", "max_people"):
        saved = json.loads(text)
        saved["tuning"][name] += 1
        (run_dir / "run.json").write_text(json.dumps(saved), encoding="utf-8")
        assert runner.main(["replay", str(photo), str(run_dir)]) == 1
        out = capsys.readouterr().out
        assert out == "refused: saved under other C56/C70 values\n"


def test_every_line_masks_twelve_digit_runs(capsys):
    # Built here, so the repo's account-ID scan stays clean.
    twelve = "1234567890" + "12"
    runner.say(f"id {twelve}, time 123456")
    assert capsys.readouterr().out == "id <account>, time 123456\n"
