# /// script
# requires-python = ">=3.13,<3.14"
# dependencies = [
#     "numpy>=2.5.4",
#     "torch>=2.5",
#     "transformers>=4.50",
# ]
#
# [tool.uv.sources]
# torch = [{ index = "pytorch-cpu" }]
#
# [[tool.uv.index]]
# name = "pytorch-cpu"
# url = "https://download.pytorch.org/whl/cpu"
# explicit = true
# ///
"""Makes Ask Lusot's synthetic spoken questions (plan Task 21, Step 0; spec C729).

It reads Rene's reviewed scripts from his private manifest, speaks each one with
Meta's MMS-TTS Tagalog model (`facebook/mms-tts-tgl`, through Transformers' VitsModel),
mixes generated street noise under it at a stated signal-to-noise ratio, and writes each
clip as a 16 kHz mono 16-bit WAV, the form POST /ask/voice takes (backend/api/src/ask/wav.ts).

- **The model** is pinned by --revision, a full commit hash, which the results note
  records. The clips are made on this laptop only. The model is CC BY-NC 4.0, so the
  clips are private test data: never in the repo, the video or the submission.
- **The noise** is generated, not a recording: FFmpeg's `anoisesrc=color=pink`, seeded,
  at the clip's length and 16 kHz, read back as raw PCM. It is mixed in with numpy, its
  gain set so that the speech-to-noise power ratio over the whole clip is --snr-db
  exactly (15 by default).
- **Seeds:** clip n (counting from 0 in the manifest's order) uses --seed + n for both
  the speech and the noise, so a rerun with the same model, the same torch build and the
  same --seed gives the same clips. --seed defaults to 1234.
- **Refused before any synthesis,** exit 2: a path with a part named sealed, a manifest
  or output folder inside the repo or not absolute, a manifest that is missing or not
  usable, any entry not reviewed (its count only), an entry whose id, clip name or text
  is unusable, and a --revision that is not a 40-digit hex commit hash.
- **Printed:** one line per clip, its manifest id, its length and its SNR. Never a
  script, a note, a path or a transcript. A clip outside the handler's 0.5 to 15 s, or
  a silent one, is reported as failed and not written; the exit code is then 1.

Torch and Transformers are imported inside `synthesize` only, so the tests that check
the rest of this file run without them (check:py has numpy but not torch).

Run it only with at least 2 GB of memory free, never beside Docker or Gradle. From the
repo root, in PowerShell, with `$d` the data folder:
  uv run --locked --script backend/scripts/make_voice_clips.py --manifest "$d\\voice\\m12-scripts.json" --out "$d\\voice\\m12-synthetic" --revision <commit hash>
The first run downloads the model (about 150 MB) into Hugging Face's cache.

Exit codes: 0 every clip written, 1 a clip failed, 2 a refusal or a bad argument.
"""

from __future__ import annotations

import argparse
import functools
import json
import math
import re
import shutil
import subprocess
import wave
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import NoReturn

import guards
import numpy as np

RATE = 16000  # Hz: MMS-TTS's own rate, and one of the two Meta's transcription takes
MODEL_ID = "facebook/mms-tts-tgl"
MIN_S, MAX_S = 0.5, 15.0  # the handler's clip length (backend/api/src/ask/wav.ts)
PEAK = 0.95  # a mix that would go past this is scaled down whole, which keeps its SNR
REPO = Path(__file__).resolve().parents[2]
REVISION = re.compile(r"[0-9a-f]{40}")
ENTRY_ID = re.compile(r"[A-Za-z0-9_-]{1,32}")
WAV_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\.wav", re.IGNORECASE)

# The model and its tokenizer, loaded once for each revision.
_LOADED: dict[str, tuple] = {}


def power(x: np.ndarray) -> float:
    return float(np.mean(np.square(x)))


def mix_at_snr(speech: np.ndarray, noise: np.ndarray, snr_db: float) -> np.ndarray:
    """`speech` plus `noise` scaled so that power(speech) / power(scaled noise) is
    exactly `snr_db`, over the whole clip. Silent speech or noise, or unequal lengths,
    is a ValueError."""
    if len(speech) != len(noise):
        raise ValueError("the speech and the noise differ in length")
    speech_power, noise_power = power(speech), power(noise)
    if speech_power <= 0 or noise_power <= 0:
        raise ValueError("the speech or the noise is silent")
    gain = math.sqrt(speech_power / (noise_power * 10 ** (snr_db / 10)))
    return speech + gain * noise


def write_wav(path: Path, samples: np.ndarray) -> None:
    """`samples` (floats in -1 to 1, clipped beyond) as a 16 kHz mono 16-bit PCM WAV."""
    pcm = np.clip(np.round(np.asarray(samples, dtype=np.float64) * 32768), -32768, 32767)
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(RATE)
        f.writeframes(pcm.astype("<i2").tobytes())


def pink_noise(
    n_samples: int,
    seed: int,
    *,
    ffmpeg: str = "ffmpeg",
    run: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> np.ndarray:
    """`n_samples` of seeded pink noise at 16 kHz, floats in about -0.5 to 0.5, from
    FFmpeg's anoisesrc read back as raw 16-bit PCM. The same seed gives the same noise
    from the same FFmpeg build. A failed run is a RuntimeError naming its exit code
    only, since FFmpeg's messages hold paths."""
    seconds = n_samples / RATE + 0.05  # a little over, then trimmed
    source = f"anoisesrc=color=pink:seed={seed}:duration={seconds:.4f}:sample_rate={RATE}:amplitude=0.5"
    command = [ffmpeg, "-nostdin", "-v", "error", "-f", "lavfi", "-i", source]
    command += ["-f", "s16le", "-ac", "1", "-ar", str(RATE), "pipe:1"]
    done = run(command, capture_output=True, check=False)
    if done.returncode != 0:
        raise RuntimeError(f"ffmpeg failed (exit {done.returncode})")
    pcm = np.frombuffer(done.stdout, dtype="<i2")
    if len(pcm) < n_samples:
        raise RuntimeError(f"ffmpeg gave {len(pcm)} samples, {n_samples} were needed")
    return pcm[:n_samples].astype(np.float64) / 32768


def synthesize(text: str, *, seed: int, revision: str) -> tuple[np.ndarray, int]:
    """`text` spoken by facebook/mms-tts-tgl at `revision`, as floats and the model's
    sampling rate. The seed is set just before the model runs, since VITS draws its
    noise at random. Torch and Transformers are imported here and nowhere else."""
    import torch
    from transformers import AutoTokenizer, VitsModel, set_seed

    if revision not in _LOADED:
        _LOADED[revision] = (
            AutoTokenizer.from_pretrained(MODEL_ID, revision=revision),
            VitsModel.from_pretrained(MODEL_ID, revision=revision),
        )
    tokenizer, model = _LOADED[revision]
    inputs = tokenizer(text, return_tensors="pt")
    set_seed(seed)
    with torch.no_grad():
        output = model(**inputs)
    waveform = output.waveform[0].cpu().numpy().astype(np.float64)
    return waveform, int(model.config.sampling_rate)


def refuse(reason: str) -> NoReturn:
    guards.say(f"refused: {reason}")
    raise SystemExit(2)


def inside_repo(path: Path) -> bool:
    return any(form.is_relative_to(REPO.resolve()) for form in (path.absolute(), path.resolve()))


def load_entries(manifest: Path) -> list[tuple[str, str, str]]:
    """The manifest's entries as (id, clip name, text), once every one is reviewed. Each
    refusal names an entry by its id and says what is wrong, never what it holds."""
    try:
        data = json.loads(manifest.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        refuse("the manifest can't be read as JSON")
    scripts = data.get("scripts") if isinstance(data, dict) else None
    if not isinstance(scripts, list) or not scripts:
        refuse("the manifest has no scripts")
    unreviewed = sum(not (isinstance(e, dict) and e.get("reviewed") is True) for e in scripts)
    if unreviewed:
        refuse(f"{unreviewed} of {len(scripts)} manifest entries are not reviewed")
    entries, names = [], set()
    for n, e in enumerate(scripts, 1):
        eid, wav, text = e.get("id"), e.get("wav"), e.get("text")
        if not (isinstance(eid, str) and ENTRY_ID.fullmatch(eid)):
            refuse(f"manifest entry {n} has no usable id")
        if not (isinstance(wav, str) and WAV_NAME.fullmatch(wav)):
            refuse(f"manifest entry {eid} has a bad clip name")
        if not (isinstance(text, str) and text.strip()):
            refuse(f"manifest entry {eid} has no text")
        if wav.casefold() in names:
            refuse("the manifest repeats a clip name")
        names.add(wav.casefold())
        entries.append((eid, wav, text))
    return entries


def main(
    argv: Sequence[str] | None = None,
    *,
    synthesize: Callable[..., tuple[np.ndarray, int]] = synthesize,
    noise: Callable[[int, int], np.ndarray] | None = None,
) -> int:
    """Make the clips. `synthesize` and `noise` are for the tests: by default speech is
    MMS-TTS's and the noise is FFmpeg's seeded pink noise."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--manifest", type=Path, required=True, help="the reviewed scripts (an absolute path)")
    parser.add_argument("--out", type=Path, required=True, help="the folder for the WAVs (an absolute path)")
    parser.add_argument("--revision", required=True, help="the model's commit hash (40 hex digits)")
    parser.add_argument("--seed", type=int, default=1234, help="the first clip's seed; each next one adds 1")
    parser.add_argument("--snr-db", type=float, default=15.0, help="speech-to-noise power ratio in dB")
    parser.add_argument("--ffmpeg", default="ffmpeg", help="FFmpeg's path, when it is not on PATH")
    args = parser.parse_args(argv)

    guards.refuse_sealed(args.manifest, args.out)
    for path in (args.manifest, args.out):
        if not path.is_absolute():
            refuse("the manifest and the output folder take absolute paths")
        if inside_repo(path):
            refuse("a path inside the repo")
    if not REVISION.fullmatch(args.revision):
        refuse("--revision is the model's full commit hash (40 hex digits)")
    entries = load_entries(args.manifest)
    if noise is None:
        if shutil.which(args.ffmpeg) is None:
            refuse("FFmpeg isn't installed or isn't on PATH (see --ffmpeg)")
        noise = functools.partial(pink_noise, ffmpeg=args.ffmpeg)

    args.out.mkdir(parents=True, exist_ok=True)
    written = failed = 0
    for index, (eid, wav, text) in enumerate(entries):
        seed = args.seed + index
        speech, rate = synthesize(text, seed=seed, revision=args.revision)
        seconds = len(speech) / RATE
        if rate != RATE:
            guards.say(f"{eid}: failed, the model's rate is {rate} Hz, not {RATE} Hz")
        elif not MIN_S <= seconds <= MAX_S:
            guards.say(f"{eid}: failed, {seconds:.2f} s is outside the handler's {MIN_S:g} to {MAX_S:g} s")
        else:
            try:
                mixed = mix_at_snr(speech, noise(len(speech), seed), args.snr_db)
            except ValueError:
                guards.say(f"{eid}: failed, the speech or the noise is silent")
                failed += 1
                continue
            achieved = 10 * math.log10(power(speech) / power(mixed - speech))
            peak = float(np.max(np.abs(mixed)))
            write_wav(args.out / wav, mixed * (PEAK / peak) if peak > PEAK else mixed)
            guards.say(f"{eid}: {seconds:.2f} s, SNR {achieved:.1f} dB")
            written += 1
            continue
        failed += 1
    guards.say(f"voice clips: {written} written, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
