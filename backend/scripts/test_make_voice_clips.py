"""Tests for make_voice_clips.py: Ask Lusot's synthetic spoken questions (plan Task 21,
Step 0; spec C729).

No torch, no transformers and no model: synthesis is a stub (or, for the call
sequence, fake torch and transformers modules), and the noise is a stub except in the
one test that runs the real FFmpeg, which is skipped where FFmpeg isn't installed. The
manifest is invented here; none of Rene's scripts is read or written. The one test of
the real model's seed is skipped unless the model is already in the local Hugging Face
cache, and never downloads.

check:py runs this file with the scripts' dependencies. Alone, from the repo root:
    uv run --python 3.13 --with pytest==9.2.0 --with numpy==2.5.4 pytest -q
        backend/scripts/test_make_voice_clips.py
"""

import json
import math
import re
import shutil
import subprocess
import sys
import types
import wave
from pathlib import Path

import make_voice_clips
import numpy as np
import pytest
from make_voice_clips import (
    RATE,
    main,
    mix_at_snr,
    pink_noise,
    synthesize,
    write_wav,
)

REPO = Path(__file__).resolve().parents[2]
REVISION = "0123456789abcdef0123456789abcdef01234567"
SEALED = r"^refused: a path inside a folder named sealed$"
IN_REPO = r"^refused: a path inside the repo$"
# Invented words that must reach no output line: a script, and the notes beside it.
SCRIPT = "INVENTED-SCRIPT-WORDS"
LONG_SCRIPT = "INVENTED-LONG-SCRIPT"  # the stub makes it 20 s
NOTE = "INVENTED-NOTE-WORDS"


def entry(n, text=SCRIPT, **over):
    return {
        "id": f"V{n}",
        "wav": f"v{n}.wav",
        "text": text,
        "here": None,
        "place_meant": NOTE,
        "why": NOTE,
        "expect": {"kind": "reports", "crossing": False, "vehicle": None},
        "reviewed": True,
        **over,
    }


def write_manifest(folder, entries):
    path = folder / "m12-scripts.json"
    path.write_text(json.dumps({"about": NOTE, "reviewed_by": NOTE, "scripts": entries}))
    return path


class Stubs:
    """A synthesis and a noise that record their calls, with no model and no FFmpeg."""

    def __init__(self):
        self.synth_calls = []
        self.noise_calls = []

    def synthesize(self, text, *, seed, revision):
        self.synth_calls.append((text, seed, revision))
        seconds = 20.0 if text == LONG_SCRIPT else 1.0
        t = np.arange(round(seconds * RATE)) / RATE
        return 0.3 * np.sin(2 * np.pi * 440 * t), RATE

    def noise(self, n, seed):
        self.noise_calls.append((n, seed))
        return np.random.default_rng(seed).standard_normal(n)


def run(tmp_path, entries, *extra, stubs=None, manifest=None, out=None):
    stubs = stubs or Stubs()
    manifest = manifest or write_manifest(tmp_path, entries)
    out = out or tmp_path / "clips"
    argv = ["--manifest", str(manifest), "--out", str(out), "--revision", REVISION, *extra]
    code = main(argv, synthesize=stubs.synthesize, noise=stubs.noise)
    return code, stubs, out


def read_wav(path):
    with wave.open(str(path), "rb") as f:
        params = f.getparams()
        frames = np.frombuffer(f.readframes(f.getnframes()), dtype="<i2")
    return params, frames.astype(np.float64) / 32768


def power(x):
    return float(np.mean(np.square(x)))


def snr_db(speech, noise):
    return 10 * math.log10(power(speech) / power(noise))


# --- the WAV ---------------------------------------------------------------------------------


def test_the_wav_is_16_khz_mono_16_bit_and_keeps_the_samples(tmp_path):
    samples = 0.5 * np.sin(2 * np.pi * 300 * np.arange(8000) / RATE)

    write_wav(tmp_path / "a.wav", samples)

    params, back = read_wav(tmp_path / "a.wav")
    assert (params.nchannels, params.sampwidth, params.framerate, params.nframes) == (1, 2, 16000, 8000)
    assert np.max(np.abs(back - samples)) < 1 / 32768  # one step of 16 bits


def test_the_wav_clips_instead_of_wrapping(tmp_path):
    write_wav(tmp_path / "a.wav", np.array([2.0, -2.0, 0.0]))

    _, back = read_wav(tmp_path / "a.wav")

    assert back[0] > 0.99 and back[1] < -0.99 and back[2] == 0


# --- the mix ---------------------------------------------------------------------------------


@pytest.mark.parametrize("target", [0.0, 6.0, 15.0, 25.0])
def test_the_mix_gives_the_stated_snr(target):
    t = np.arange(2 * RATE) / RATE
    speech = 0.3 * np.sin(2 * np.pi * 440 * t)
    noise = np.random.default_rng(5).standard_normal(len(t))

    mixed = mix_at_snr(speech, noise, target)

    assert abs(snr_db(speech, mixed - speech) - target) < 0.1
    assert len(mixed) == len(speech)


def test_the_mix_refuses_silence_and_unequal_lengths():
    with pytest.raises(ValueError):
        mix_at_snr(np.zeros(100), np.ones(100), 15)
    with pytest.raises(ValueError):
        mix_at_snr(np.ones(100), np.zeros(100), 15)
    with pytest.raises(ValueError):
        mix_at_snr(np.ones(100), np.ones(99), 15)


# --- the noise -------------------------------------------------------------------------------


def test_the_noise_asks_ffmpeg_for_seeded_pink_noise_at_16_khz():
    seen = []

    def fake_run(cmd, **kwargs):
        seen.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout=np.zeros(8100, dtype="<i2").tobytes(), stderr=b"")

    noise = pink_noise(8000, 7, ffmpeg="ffmpeg-here", run=fake_run)

    [cmd] = seen
    joined = " ".join(cmd)
    assert cmd[0] == "ffmpeg-here"
    assert "anoisesrc=color=pink" in joined and "seed=7" in joined and "sample_rate=16000" in joined
    assert "-f s16le" in joined and "-ac 1" in joined and "-ar 16000" in joined and joined.endswith("pipe:1")
    assert len(noise) == 8000  # trimmed to the clip's length


def test_the_noise_fails_when_ffmpeg_fails_or_gives_too_little():
    def bad_exit(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 1, stdout=b"", stderr=b"secret path C:\\x")

    def too_short(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 0, stdout=np.zeros(10, dtype="<i2").tobytes(), stderr=b"")

    with pytest.raises(RuntimeError, match="exit 1") as raised:
        pink_noise(8000, 7, run=bad_exit)
    assert "secret" not in str(raised.value)  # FFmpeg's stderr is never relayed
    with pytest.raises(RuntimeError):
        pink_noise(8000, 7, run=too_short)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="FFmpeg isn't installed")
def test_the_same_seed_gives_the_same_pink_noise_with_the_real_ffmpeg():
    a = pink_noise(RATE, 11)
    b = pink_noise(RATE, 11)
    c = pink_noise(RATE, 12)

    assert len(a) == RATE
    assert np.array_equal(a, b)
    assert not np.array_equal(a, c)
    assert power(a) > 0
    # Pink: more power in the low half of the spectrum than the high half.
    spectrum = np.abs(np.fft.rfft(a)) ** 2
    assert spectrum[: len(spectrum) // 2].sum() > 3 * spectrum[len(spectrum) // 2 :].sum()


# --- main: what is written and printed ---------------------------------------------------------


def test_main_writes_one_wav_per_entry_with_the_stated_snr_and_prints_no_text(tmp_path, capsys):
    entries = [entry(1), entry(2), entry(3)]

    code, _, out = run(tmp_path, entries)

    assert code == 0
    assert sorted(p.name for p in out.iterdir()) == ["v1.wav", "v2.wav", "v3.wav"]
    for p in out.iterdir():
        params, written = read_wav(p)
        assert (params.nchannels, params.sampwidth, params.framerate, params.nframes) == (1, 2, 16000, 16000)
        # The speech is the stub's sine: the least-squares share of it in the file, the rest being noise.
        sine = 0.3 * np.sin(2 * np.pi * 440 * np.arange(RATE) / RATE)
        share = float(np.dot(written, sine) / np.dot(sine, sine))
        assert abs(snr_db(share * sine, written - share * sine) - 15.0) < 0.1
    # The default is 15 dB, and --snr-db changes it.
    _, _, out2 = run(tmp_path, [entry(1)], "--snr-db", "6", out=tmp_path / "six")
    _, written = read_wav(out2 / "v1.wav")
    sine = 0.3 * np.sin(2 * np.pi * 440 * np.arange(RATE) / RATE)
    share = float(np.dot(written, sine) / np.dot(sine, sine))
    assert abs(snr_db(share * sine, written - share * sine) - 6.0) < 0.1

    printed = capsys.readouterr().out
    lines = [line for line in printed.splitlines() if line.startswith("V")]
    assert [line.split(":")[0] for line in lines] == ["V1", "V2", "V3", "V1"]
    assert all("1.00 s" in line and "dB" in line for line in lines)
    assert "15.0 dB" in lines[0] and "6.0 dB" in lines[3]
    assert SCRIPT not in printed and NOTE not in printed


def test_main_gives_each_clip_its_own_seed_from_the_base_seed_and_its_index(tmp_path):
    entries = [entry(1), entry(2), entry(3)]

    _, stubs, _ = run(tmp_path, entries)

    assert [call[1] for call in stubs.synth_calls] == [1234, 1235, 1236]  # the default --seed, plus the index
    assert [call[1] for call in stubs.noise_calls] == [1234, 1235, 1236]
    assert {call[2] for call in stubs.synth_calls} == {REVISION}
    assert [call[0] for call in stubs.synth_calls] == [SCRIPT] * 3

    _, stubs, _ = run(tmp_path, entries, "--seed", "50", out=tmp_path / "other")
    assert [call[1] for call in stubs.synth_calls] == [50, 51, 52]
    assert [n for n, _ in stubs.noise_calls] == [RATE] * 3  # the noise is the clip's length


def test_main_is_repeatable_clip_for_clip(tmp_path):
    entries = [entry(1), entry(2)]
    run(tmp_path, entries, out=tmp_path / "a")
    run(tmp_path, entries, out=tmp_path / "b")

    for name in ("v1.wav", "v2.wav"):
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes()


def test_main_fails_a_clip_outside_the_handlers_length_and_writes_the_others(tmp_path, capsys):
    entries = [entry(1), entry(2, text=LONG_SCRIPT), entry(3)]

    code, _, out = run(tmp_path, entries)

    assert code == 1
    assert sorted(p.name for p in out.iterdir()) == ["v1.wav", "v3.wav"]
    printed = capsys.readouterr().out
    assert "V2" in printed and "0.5" in printed and "15" in printed
    assert LONG_SCRIPT not in printed


def test_main_fails_a_silent_synthesis(tmp_path):
    stubs = Stubs()
    stubs.synthesize = lambda text, *, seed, revision: (np.zeros(RATE), RATE)

    code, _, out = run(tmp_path, [entry(1)], stubs=stubs)

    assert code == 1
    assert not (out / "v1.wav").exists()


def test_main_refuses_a_model_that_isnt_16_khz(tmp_path):
    stubs = Stubs()
    stubs.synthesize = lambda text, *, seed, revision: (0.3 * np.ones(22050), 22050)

    code, _, out = run(tmp_path, [entry(1)], stubs=stubs)

    assert code == 1
    assert not (out / "v1.wav").exists()


def test_main_runs_the_ffmpeg_path_which_returned_not_the_bare_name(tmp_path, monkeypatch):
    # Windows searches Python's folder and the working folder before PATH for a bare name, so the path that
    # shutil.which resolved is the one that runs.
    seen = []

    def fake_pink_noise(n, seed, *, ffmpeg):
        seen.append(ffmpeg)
        return np.random.default_rng(seed).standard_normal(n)

    resolved = {"ffmpeg": r"C:\tools\ffmpeg\ffmpeg.exe", "my-ffmpeg": r"D:\bin\my-ffmpeg.exe"}
    monkeypatch.setattr(make_voice_clips, "pink_noise", fake_pink_noise)
    monkeypatch.setattr(make_voice_clips.shutil, "which", resolved.get)
    manifest = write_manifest(tmp_path, [entry(1)])

    assert main(argv_for(manifest, tmp_path / "a"), synthesize=Stubs().synthesize) == 0
    assert main(argv_for(manifest, tmp_path / "b", "--ffmpeg", "my-ffmpeg"), synthesize=Stubs().synthesize) == 0

    assert seen == [r"C:\tools\ffmpeg\ffmpeg.exe", r"D:\bin\my-ffmpeg.exe"]


def test_a_clip_that_fails_deletes_the_older_file_of_its_id(tmp_path, capsys):
    # A later harness run reads <out>/<wav>; a failed clip must not leave an older one there to be used instead.
    out = tmp_path / "clips"
    out.mkdir()
    for n in (1, 2, 3, 4, 5):
        (out / f"v{n}.wav").write_bytes(b"older clip")
    (out / "other.wav").write_bytes(b"not in the manifest")

    def synth(text, *, seed, revision):
        if text == LONG_SCRIPT:
            return 0.3 * np.ones(20 * RATE), RATE  # past 15 s
        if text == "SILENT":
            return np.zeros(RATE), RATE
        if text == "SLOW-RATE":
            return 0.3 * np.ones(22050), 22050
        return 0.3 * np.sin(2 * np.pi * 440 * np.arange(RATE) / RATE), RATE

    stubs = Stubs()
    stubs.synthesize = synth
    entries = [entry(1), entry(2, text=LONG_SCRIPT), entry(3, text="SILENT"), entry(4, text="SLOW-RATE"), entry(5)]

    code, _, _ = run(tmp_path, entries, stubs=stubs, out=out)

    assert code == 1
    assert sorted(p.name for p in out.iterdir()) == ["other.wav", "v1.wav", "v5.wav"]
    for name in ("v1.wav", "v5.wav"):
        assert (out / name).read_bytes() != b"older clip"  # rewritten
    assert (out / "other.wav").read_bytes() == b"not in the manifest"  # nothing else is touched
    assert "3 failed" in capsys.readouterr().out


def test_an_interrupted_run_leaves_no_older_clip_of_any_entry(tmp_path):
    # The model or FFmpeg can raise part way; every clip the manifest names is cleared before the first is made,
    # so the harness finds a missing clip (and refuses) rather than an older one.
    out = tmp_path / "clips"
    out.mkdir()
    for n in (1, 2, 3):
        (out / f"v{n}.wav").write_bytes(b"older clip")
    (out / "other.wav").write_bytes(b"not in the manifest")

    def synth(text, *, seed, revision):
        if text == "BOOM":
            raise RuntimeError("synthesis failed")
        return 0.3 * np.sin(2 * np.pi * 440 * np.arange(RATE) / RATE), RATE

    stubs = Stubs()
    stubs.synthesize = synth
    with pytest.raises(RuntimeError):
        run(tmp_path, [entry(1), entry(2, text="BOOM"), entry(3)], stubs=stubs, out=out)

    assert sorted(p.name for p in out.iterdir()) == ["other.wav", "v1.wav"]
    assert (out / "v1.wav").read_bytes() != b"older clip"  # rewritten before the failure
    assert (out / "other.wav").read_bytes() == b"not in the manifest"


# --- main: the refusals, all before any synthesis ----------------------------------------------


def refused(tmp_path, capsys, argv, stubs=None, *, why):
    """Runs main to a refusal (exit 2) before any synthesis. `why` is a regex the printed line must match, so a refusal
    for another reason (a manifest that doesn't exist, say) can't pass as the one under test."""
    stubs = stubs or Stubs()
    with pytest.raises(SystemExit) as exit_:
        main(argv, synthesize=stubs.synthesize, noise=stubs.noise)
    assert exit_.value.code == 2
    assert stubs.synth_calls == [] and stubs.noise_calls == []
    printed = capsys.readouterr().out
    assert printed.startswith("refused: ")
    assert re.search(why, printed), printed
    for secret in (SCRIPT, NOTE, str(tmp_path)):
        assert secret not in printed
    return printed


def argv_for(manifest, out, *extra, revision=REVISION):
    return ["--manifest", str(manifest), "--out", str(out), "--revision", revision, *extra]


@pytest.mark.parametrize("sealed", ["sealed", "Sealed", "SEALED.", "sealed ", "sealed::$INDEX_ALLOCATION"])
def test_a_sealed_manifest_or_output_is_refused(tmp_path, capsys, sealed):
    manifest = write_manifest(tmp_path, [entry(1)])

    # Neither path exists, so each would be refused anyway (a manifest that can't be read, say); the printed reason
    # is what proves the sealed rule did it.
    refused(tmp_path, capsys, argv_for(tmp_path / sealed / "m.json", tmp_path / "clips"), why=SEALED)
    refused(tmp_path, capsys, argv_for(manifest, tmp_path / sealed / "clips"), why=SEALED)
    assert not (tmp_path / "clips").exists()  # nothing was made, and no sealed folder was either
    assert not (tmp_path / sealed).exists()


def test_an_unreviewed_entry_is_refused_with_its_count_only(tmp_path, capsys):
    entries = [entry(1), entry(2, reviewed=False), entry(3, reviewed="true")]
    manifest = write_manifest(tmp_path, entries)

    refused(tmp_path, capsys, argv_for(manifest, tmp_path / "clips"), why=r"2 of 3 manifest entries are not reviewed$")
    assert not (tmp_path / "clips").exists()


def test_a_path_inside_the_repo_is_refused(tmp_path, capsys):
    manifest = write_manifest(tmp_path, [entry(1)])
    inside = REPO / "zz-voice-clips-must-not-exist"

    # The manifest in the repo doesn't exist either, so only the printed reason shows the repo rule refused it.
    refused(tmp_path, capsys, argv_for(manifest, inside), why=IN_REPO)
    refused(tmp_path, capsys, argv_for(REPO / "zz-manifest.json", tmp_path / "clips"), why=IN_REPO)
    assert not inside.exists()


def test_a_missing_manifest_is_refused(tmp_path, capsys):
    refused(tmp_path, capsys, argv_for(tmp_path / "nope.json", tmp_path / "clips"), why=r"the manifest can't be read as JSON$")


@pytest.mark.parametrize(
    ("content", "why"),
    [
        ("{ not json", r"can't be read as JSON$"),
        ("[]", r"the manifest has no scripts$"),
        (json.dumps({"scripts": []}), r"the manifest has no scripts$"),
        (json.dumps({"scripts": "x"}), r"the manifest has no scripts$"),
    ],
)
def test_a_manifest_that_isnt_usable_is_refused_without_quoting_it(tmp_path, capsys, content, why):
    path = tmp_path / "m.json"
    path.write_text(content)

    refused(tmp_path, capsys, argv_for(path, tmp_path / "clips"), why=why)


@pytest.mark.parametrize(
    ("bad", "why"),
    [
        ({"wav": "..\\outside.wav"}, r"entry V1 has a bad clip name$"),
        ({"wav": "sub/v1.wav"}, r"entry V1 has a bad clip name$"),
        ({"wav": "v1.mp3"}, r"entry V1 has a bad clip name$"),
        ({"wav": 5}, r"entry V1 has a bad clip name$"),
        ({"id": ""}, r"entry 1 has no usable id$"),
        ({"id": "has space"}, r"entry 1 has no usable id$"),
        ({"text": ""}, r"entry V1 has no text$"),
        ({"text": 7}, r"entry V1 has no text$"),
    ],
)
def test_a_bad_entry_is_refused(tmp_path, capsys, bad, why):
    manifest = write_manifest(tmp_path, [entry(1, **bad)])

    refused(tmp_path, capsys, argv_for(manifest, tmp_path / "clips"), why=why)


def test_a_repeated_wav_name_is_refused(tmp_path, capsys):
    manifest = write_manifest(tmp_path, [entry(1), entry(2, wav="v1.wav")])

    refused(tmp_path, capsys, argv_for(manifest, tmp_path / "clips"), why=r"the manifest repeats a clip name$")


@pytest.mark.parametrize("revision", ["main", "", "abc123", "G" * 40, "0" * 39, "0" * 41])
def test_the_revision_must_be_a_full_commit_hash(tmp_path, capsys, revision):
    manifest = write_manifest(tmp_path, [entry(1)])

    refused(tmp_path, capsys, argv_for(manifest, tmp_path / "clips", revision=revision), why=r"full commit hash")


def test_relative_paths_are_refused(tmp_path, capsys):
    manifest = write_manifest(tmp_path, [entry(1)])

    refused(tmp_path, capsys, argv_for("m12-scripts.json", tmp_path / "clips"), why=r"take absolute paths$")
    refused(tmp_path, capsys, argv_for(manifest, "clips"), why=r"take absolute paths$")


# --- the real synthesis function, with fake torch and transformers ---------------------------------


def test_importing_the_script_imports_neither_torch_nor_transformers():
    code = (
        "import sys; import make_voice_clips; "
        "assert 'torch' not in sys.modules and 'transformers' not in sys.modules"
    )

    done = subprocess.run(
        [sys.executable, "-c", code],
        cwd=Path(make_voice_clips.__file__).parent,
        capture_output=True,
        text=True,
        check=False,
    )

    assert done.returncode == 0, done.stderr


class FakeTensor:
    def __init__(self, array):
        self.array = np.asarray(array)

    def __getitem__(self, item):
        return FakeTensor(self.array[item])

    def cpu(self):
        return self

    def numpy(self):
        return self.array


def install_fake_torch_and_transformers(monkeypatch, record):
    torch = types.ModuleType("torch")

    class NoGrad:
        def __enter__(self):
            record.append("no_grad on")

        def __exit__(self, *exc):
            record.append("no_grad off")

    torch.no_grad = NoGrad
    transformers = types.ModuleType("transformers")

    class Tokenizer:
        @classmethod
        def from_pretrained(cls, name, **kwargs):
            record.append(("tokenizer", name, kwargs))
            return cls()

        def __call__(self, text, return_tensors=None):
            record.append(("tokenize", text, return_tensors))
            return {"input_ids": text}

    class Model:
        config = types.SimpleNamespace(sampling_rate=16000)

        @classmethod
        def from_pretrained(cls, name, **kwargs):
            record.append(("model", name, kwargs))
            return cls()

        def __call__(self, **inputs):
            record.append(("forward", inputs))
            return types.SimpleNamespace(waveform=FakeTensor([[0.1, -0.2, 0.3]]))

    transformers.AutoTokenizer = Tokenizer
    transformers.VitsModel = Model
    transformers.set_seed = lambda seed: record.append(("set_seed", seed))
    monkeypatch.setitem(sys.modules, "torch", torch)
    monkeypatch.setitem(sys.modules, "transformers", transformers)
    monkeypatch.setattr(make_voice_clips, "_LOADED", {})


def test_synthesis_loads_the_pinned_model_seeds_and_returns_the_waveform(monkeypatch):
    record = []
    install_fake_torch_and_transformers(monkeypatch, record)

    samples, rate = synthesize("some text", seed=99, revision=REVISION)

    assert rate == 16000 and samples.tolist() == pytest.approx([0.1, -0.2, 0.3])
    assert ("tokenizer", "facebook/mms-tts-tgl", {"revision": REVISION}) in record
    assert ("model", "facebook/mms-tts-tgl", {"revision": REVISION}) in record
    assert record.index(("set_seed", 99)) < record.index("no_grad on") < record.index(("forward", {"input_ids": "some text"}))
    assert record[-1] == "no_grad off"


def test_synthesis_loads_the_model_once_per_revision(monkeypatch):
    record = []
    install_fake_torch_and_transformers(monkeypatch, record)

    synthesize("one", seed=1, revision=REVISION)
    synthesize("two", seed=2, revision=REVISION)

    assert sum(1 for r in record if isinstance(r, tuple) and r[0] == "model") == 1
    assert [r[1] for r in record if isinstance(r, tuple) and r[0] == "tokenize"] == ["one", "two"]


# --- the real model's seed, only when its files are already in the local cache --------------------


def cached_revision():
    """A commit hash of facebook/mms-tts-tgl in the local Hugging Face cache, or None.
    It reads the cache only: HF_HUB_OFFLINE is set first, so nothing is downloaded."""
    pytest.importorskip("torch")
    pytest.importorskip("transformers")
    huggingface_hub = pytest.importorskip("huggingface_hub")
    for repo in huggingface_hub.scan_cache_dir().repos:
        if repo.repo_id == "facebook/mms-tts-tgl" and repo.revisions:
            return max(repo.revisions, key=lambda r: r.last_modified).commit_hash
    return None


def test_the_same_seed_gives_the_same_speech_with_the_real_model(monkeypatch):
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    revision = cached_revision()
    if revision is None:
        pytest.skip("facebook/mms-tts-tgl isn't in the local Hugging Face cache; this test never downloads it")

    a, rate = synthesize("Magandang umaga po.", seed=3, revision=revision)
    b, _ = synthesize("Magandang umaga po.", seed=3, revision=revision)
    c, _ = synthesize("Magandang umaga po.", seed=4, revision=revision)

    assert rate == RATE and len(a) > RATE // 2
    assert np.array_equal(a, b)
    assert not np.array_equal(a, c)
