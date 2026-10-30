"""Tests for MS1's probe, probes/run_probe.py: its spend reaches MS4's counter (C527).

The probe isn't a package module, so it is loaded from its file. Its STURM folder
and data folder are synthetic ones under tmp_path, a FakeClient stands in for Meta,
and a FakeSpend for the counter, so no test reaches Meta, AWS or lusot-data.
"""

import importlib.util
import io
import json
import logging
import wave
from datetime import date
from pathlib import Path

import pytest
from fakes import FakeClient, FakeSpend, level_case, noise_jpeg

from lusot_analysis.meta_client import SAM_PHRASES, TranscriptResult
from lusot_analysis.spend import cost_of

PROBE = Path(__file__).parents[1] / "probes" / "run_probe.py"


def load_probe():
    spec = importlib.util.spec_from_file_location("run_probe_script", PROBE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


probe = load_probe()


class ProbeClient(FakeClient):
    """A FakeClient that also counts input tokens and transcribes, as MS1's probe
    asks of the Meta client."""

    def count_input_tokens(self, image, *, prompt):
        return 4321

    def transcribe(self, data, **_):
        return TranscriptResult("text", 0.5, json.dumps({"transcript": "text"}))


@pytest.fixture
def sturm(tmp_path, monkeypatch):
    """Two synthetic Level1 photos as the STURM folder, the data folder under
    tmp_path, and today's 2.5 s test clip. The probe's log handler is removed after."""
    data = tmp_path / "data"
    folder = data / "set_c" / "sturm"
    (folder / "Level1").mkdir(parents=True)
    for number in (1, 2):
        (folder / "Level1" / f"p{number}.jpg").write_bytes(noise_jpeg(seed=number))
    monkeypatch.setattr(probe, "DATA", data)
    monkeypatch.setattr(probe, "STURM", folder)
    out = data / "probes" / date.today().isoformat()
    out.mkdir(parents=True)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as clip:
        clip.setnchannels(1)
        clip.setsampwidth(2)
        clip.setframerate(16_000)
        clip.writeframes(b"\0\0" * 40_000)
    (out / probe.TEST_CLIP).write_bytes(buffer.getvalue())
    meta = logging.getLogger("lusot.meta")
    before = list(meta.handlers)
    yield out
    for handler in meta.handlers[:]:
        if handler not in before:
            meta.removeHandler(handler)
            handler.close()


def test_the_probe_records_its_cost_after_checking_the_counter(
    sturm, monkeypatch, capsys
):
    events = []
    spend = FakeSpend(on_record=lambda: events.append("record"))
    monkeypatch.setattr(
        probe, "check_before_paying", lambda: events.append("check") or spend
    )
    _, sam, given = level_case()
    fake = ProbeClient(sam, given)
    argv = ["--photos", "1", "--water", "1"]
    assert probe.main(argv, make_client=lambda: events.append("client") or fake) == 0
    # The counter is read before the client is built, and the run is recorded once,
    # after its summary is written.
    assert events == ["check", "client", "record"]
    assert (sturm / "summary.json").is_file()
    # A1's 7 phrases and answer, A2's 2 phrases, and the clip's 3 whole seconds.
    usd = cost_of(
        sam_images=len(SAM_PHRASES) + 2,
        spark_input_tokens=1000,
        spark_output_tokens=200,
        audio_seconds=3,
    )
    assert spend.records == [(usd, "run_probe")]
    assert "spend" not in capsys.readouterr().out


class Crashes(ProbeClient):
    """A ProbeClient whose transcript call crashes, after A1 and A2 are paid for."""

    def transcribe(self, data, **_):
        raise RuntimeError("a crash mid-call")


def test_a_failure_mid_run_still_records_what_was_paid(sturm, monkeypatch):
    spend = FakeSpend()
    monkeypatch.setattr(probe, "check_before_paying", lambda: spend)
    _, sam, given = level_case()
    fake = Crashes(sam, given)
    with pytest.raises(RuntimeError):
        probe.main(["--photos", "1", "--water", "1"], make_client=lambda: fake)
    assert not (sturm / "summary.json").exists()
    usd = cost_of(
        sam_images=len(SAM_PHRASES) + 2,
        spark_input_tokens=1000,
        spark_output_tokens=200,
        audio_seconds=3,  # a call that crashed may still have been billed
    )
    assert spend.records == [(usd, "run_probe")]


def test_a_refusal_before_paying_reads_no_counter(sturm, monkeypatch):
    def no_counter():
        raise AssertionError("the spend counter was read")

    monkeypatch.setattr(probe, "check_before_paying", no_counter)
    (sturm / "summary.json").write_text("{}", encoding="utf-8")

    def no_client():
        raise AssertionError("a Meta client was built")

    with pytest.raises(SystemExit):
        probe.main([], make_client=no_client)
