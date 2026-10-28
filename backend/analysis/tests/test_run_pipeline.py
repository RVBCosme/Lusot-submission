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
from fakes import FakeClient, level_case, meta_error, noise_jpeg

from lusot_analysis.meta_client import ModelRefused
from lusot_analysis.pipeline import READING_PHRASES
from lusot_analysis.pipeline.types import Outcome

RUNNER = Path(__file__).parents[1] / "probes" / "run_pipeline.py"
REASON = "REASON-MARKER-31"  # the reason fakes.answer gives every answer


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


def live_run(tmp_path, monkeypatch, capsys, client=None):
    """A live run of the level case's photo, tmp_path/street.jpg, through main.

    make_client gives `client`, by default a FakeClient on the level case, and the
    data folder is tmp_path. Returns the photo, the run folder, the fake and stdout.
    """
    _, sam, given = level_case()
    fake = FakeClient(sam, given) if client is None else client
    monkeypatch.setattr(runner, "make_client", lambda: fake)
    photo = write_photo(tmp_path / "street.jpg")
    assert runner.main(["live", str(photo), "--data-dir", str(tmp_path)]) == 0
    (run_dir,) = (tmp_path / "runs").glob("*/*")
    return photo, run_dir, fake, capsys.readouterr().out


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
    assert out.splitlines() == [
        "outcome: done/level, level knee",
        "meta_calls: 6",
        "SAM floodwater: instances 1, 500 ms",
        "SAM wheel: instances 1, 500 ms",
        "SAM wheel rim: instances 0, 500 ms",
        "SAM person: instances 0, 500 ms",
        "SAM vehicle: instances 1, 500 ms",
        "Muse Spark: 1500 ms, tokens 1000 in, 200 out",
        "drops: {}",
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


def test_every_line_masks_twelve_digit_runs(capsys):
    runner.say("id 123456789012, time 123456")
    assert capsys.readouterr().out == "id <account>, time 123456\n"
