"""MS1 probes on STURM-FloodDepth photos (spec §3.4; C30, C34, C35, C40, C41).

Run from backend/analysis, after probes/make_test_wav.ps1, with MODEL_API_KEY set:

    uv run python probes/run_probe.py [--photos 5] [--water 10] [--voice-dir DIR]

It spends Meta credits: $0.21 with the defaults on Oct 28, most of it SAM's.
- A1: each photo is face-blurred, then gets the 7 SAM phrases at once, its numbered
  boxes, Muse Spark's input token count, and Muse Spark's answer under schema v1,
  which jsonschema and check_ids then check.
- A2: SAM's floodwater and wheel on more photos, with an overlay for the C40 review and
  each wheel's overlap with the water.
- Voice: the test clip, or every WAV in DIR instead (M12's recordings, C41), each after
  a format check.

The photos follow R7's seeded choice over Level1 to Level3. Every output goes to
LUSOT_DATA_DIR/probes/<today>/, ending with summary.json, and a run refuses to start
over an earlier summary.json. Stdout gets counts and timings only: never the key, a
photo or a model's text.

Before the client is built, MS4's spend counter is read with the lusot profile (its
`aws login` credentials need `--with "botocore[crt]==1.43.120"` after `uv run`): an
unseeded or unreadable counter, or one at its stop, exits 2. The run's cost is
recorded once, at its end, however it ends; a cost the counter couldn't record exits
3, with one spend_error line holding the amount (C527, R126).
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import math
import os
import random
import statistics
import sys
import time
import wave
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from pathlib import Path

import cv2
import numpy as np
from jsonschema import Draft202012Validator
from jsonschema.protocols import Validator
from jsonschema.validators import validator_for

from lusot_analysis.annotate import check_ids, draw_numbered_boxes, number_boxes
from lusot_analysis.face_blur import (
    FACE_BLUR_VERSION,
    BlurredImage,
    FaceBox,
    blur_for_meta,
    decode_image,
    detect_faces,
)

# check_before_paying is a seam: tests replace it, as they pass make_client (C527).
from lusot_analysis.laptop_spend import CountedClient, check_before_paying
from lusot_analysis.meta_client import (
    SAM_MODEL,
    SAM_PHRASES,
    SPARK_MODEL,
    TRANSCRIBE_MODEL,
    MetaClient,
    SamResult,
)

SEED = 20261028
LEVELS = ("Level1", "Level2", "Level3")
PROMPT_VERSION = "muse_spark_photo_v1"
PROMPTS = Path(__file__).parents[1] / "prompts"
DATA = Path(os.environ.get("LUSOT_DATA_DIR") or r"C:\Systems\Lusot\lusot-data")
STURM = DATA / "set_c" / "sturm_flooddepth" / "extracted" / "upscaled_images"
TEST_CLIP = "test_question.wav"  # written by probes/make_test_wav.ps1
MAX_SIDE = 1600  # blur_for_meta's default
FACE_MARGIN = 0.25  # blur_faces' default
BLUE, YELLOW = (255, 0, 0), (0, 255, 255)  # BGR
# Prices from docs/research/2026-10-26-verification-notes.md (dev.meta.ai, Oct 26).
# Token counting isn't priced there; it is counted as free, and the note bounds it.
SAM_USD_PER_IMAGE = 2.50 / 1000
SPARK_USD_PER_INPUT_TOKEN = 1.25 / 1e6
SPARK_USD_PER_OUTPUT_TOKEN = 4.25 / 1e6
VOICE_USD_PER_SECOND = 0.18 / 3600


def choose(photos: int, water: int) -> tuple[list[str], list[str]]:
    """R7's choice: the sorted pool, then one seeded sample; A1 first, then A2."""
    names = sorted(
        path.relative_to(STURM).as_posix()
        for level in LEVELS
        for path in (STURM / level).rglob("*")
        if path.is_file()
    )
    picked = random.Random(SEED).sample(names, photos + water)
    return picked[:photos], picked[photos:]


def segment_all(
    client: MetaClient, img: BlurredImage, phrases: Sequence[str]
) -> dict[str, SamResult]:
    """Every phrase at once, one thread each, on the one shared client."""
    with ThreadPoolExecutor(len(phrases)) as pool:
        results = pool.map(lambda phrase: client.segment(img, phrase), phrases)
        return dict(zip(phrases, results, strict=True))


def save_sam(folder: Path, img: BlurredImage, results: dict[str, SamResult]) -> None:
    """Each phrase's raw response (R11), and its masks, ids, boxes and scores."""
    folder.mkdir(parents=True, exist_ok=True)
    for phrase, result in results.items():
        stem = "sam_" + phrase.replace(" ", "_")
        (folder / f"{stem}.txt").write_text(result.raw, encoding="utf-8")
        found = result.instances
        np.savez_compressed(
            folder / f"{stem}_masks.npz",
            ids=np.array([i.id for i in found], int),
            boxes=np.array([i.box for i in found], float).reshape(-1, 4),
            scores=np.array([np.nan if i.score is None else i.score for i in found]),
            masks=np.array([i.mask for i in found], bool).reshape(
                -1, img.height, img.width
            ),
        )


def faces_as_blurred(data: bytes) -> list[FaceBox]:
    """YuNet's boxes on the pixels blur_for_meta blurred: the same decode and shrink."""
    bgr = decode_image(data)
    height, width = bgr.shape[:2]
    if max(height, width) > MAX_SIDE:
        scale = MAX_SIDE / max(height, width)
        size = (max(1, round(width * scale)), max(1, round(height * scale)))
        bgr = cv2.resize(bgr, size, interpolation=cv2.INTER_AREA)
    return detect_faces(bgr)


def faces_over_wheels(faces: list[FaceBox], wheels: SamResult) -> list[list[int]]:
    """Each face box whose blur area, the box grown by the margin, meets a wheel box."""
    hits = []
    for face in faces:
        dx, dy = math.ceil(face.w * FACE_MARGIN), math.ceil(face.h * FACE_MARGIN)
        x0, y0 = face.x - dx, face.y - dy
        x1, y1 = face.x + face.w + dx, face.y + face.h + dy
        for wheel in wheels.instances:
            wx0, wy0, wx1, wy1 = wheel.box  # half-open, like the blur area
            if x0 < wx1 and wx0 < x1 and y0 < wy1 and wy0 < y1:
                hits.append([face.x, face.y, face.w, face.h])
                break
    return hits


def probe_a1(
    client: MetaClient,
    name: str,
    prompt: str,
    schema: dict,
    validator: Validator,
    out: Path,
) -> dict:
    """One A1 photo: blur, 7 SAM phrases, numbered boxes, token count, Muse Spark."""
    data = (STURM / name).read_bytes()
    img = blur_for_meta(data)
    faces = faces_as_blurred(data)
    sam = segment_all(client, img, SAM_PHRASES)
    folder = out / "a1" / Path(name).stem
    save_sam(folder, img, sam)
    boxes = number_boxes(sam)
    drawn = draw_numbered_boxes(img, boxes)
    (folder / "numbered.jpg").write_bytes(drawn.jpeg)
    started = time.monotonic()
    counted = client.count_input_tokens(drawn, prompt=prompt)
    count_s = time.monotonic() - started
    try:
        spark = client.judge(
            drawn, prompt=prompt, schema=schema, schema_name=PROMPT_VERSION
        )
        answer, raw = spark.data, spark.raw
        tokens = {
            "input_tokens": spark.input_tokens,
            "output_tokens": spark.output_tokens,
        }
        spark_s = spark.elapsed_s
    except json.JSONDecodeError as exc:  # the answer isn't JSON: a finding (R68)
        answer, raw, spark_s = None, exc.doc, None
        tokens = {"input_tokens": None, "output_tokens": None}
    (folder / "spark_output.txt").write_text(raw, encoding="utf-8")
    if answer is None:
        errors = ["the answer isn't JSON"]
    else:
        errors = [f"{e.json_path}: {e.message}" for e in validator.iter_errors(answer)]
    valid = not errors
    return {
        "photo": name,
        "size": [img.width, img.height],
        "faces": img.faces,
        "face_boxes": [[f.x, f.y, f.w, f.h] for f in faces],
        "face_boxes_over_wheels": faces_over_wheels(faces, sam["wheel"]),
        "sam": {
            phrase: {"instances": len(r.instances), "elapsed_s": round(r.elapsed_s, 3)}
            for phrase, r in sam.items()
        },
        "numbered_boxes": {
            kind: sum(box.kind == kind for box in boxes)
            for kind in ("vehicle", "wheel", "person")
        },
        "counted_input_tokens": counted,
        "count_elapsed_s": round(count_s, 3),
        "spark": {
            **tokens,
            "elapsed_s": None if spark_s is None else round(spark_s, 3),
        },
        "schema_valid": valid,
        "schema_errors": errors,
        "id_problems": check_ids(answer, boxes) if valid else None,  # None: unchecked
        "reason_chars": len(answer["reason"]) if valid else None,
    }


def overlay(img: BlurredImage, water: np.ndarray, wheels: SamResult) -> np.ndarray:
    """The blurred photo, its water filled blue at 40% and each wheel outlined yellow.

    Each wheel's SAM id is written above its box, to match summary.json's rows.
    """
    bgr = img.bgr()
    out = bgr.copy()
    out[water] = np.round(0.6 * bgr[water] + 0.4 * np.array(BLUE)).astype(np.uint8)
    for wheel in wheels.instances:
        contours, _ = cv2.findContours(
            wheel.mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE
        )
        cv2.drawContours(out, contours, -1, YELLOW, 1)
        x0, y0 = int(wheel.box[0]), int(wheel.box[1])
        label_at = (x0, max(10, y0 - 3))
        cv2.putText(out, str(wheel.id), label_at, cv2.FONT_HERSHEY_SIMPLEX, 0.4, YELLOW)
    return out


def probe_a2(client: MetaClient, name: str, out: Path) -> dict:
    """One A2 photo: floodwater and wheel, the overlay, and each wheel's overlap."""
    img = blur_for_meta((STURM / name).read_bytes())
    sam = segment_all(client, img, ("floodwater", "wheel"))
    folder = out / "a2" / Path(name).stem
    save_sam(folder, img, sam)
    water = np.zeros((img.height, img.width), bool)
    for instance in sam["floodwater"].instances:
        water |= instance.mask
    wheels = []
    for wheel in sam["wheel"].instances:
        area = int(wheel.mask.sum())
        shared = int((wheel.mask & water).sum())
        wheels.append(
            {
                "id": wheel.id,
                "box": list(wheel.box),
                "mask_px": area,
                "overlap": round(shared / area, 4) if area else None,
            }
        )
    png = cv2.imencode(".png", overlay(img, water, sam["wheel"]))[1]
    (folder / "overlay.png").write_bytes(png.tobytes())
    return {
        "photo": name,
        "size": [img.width, img.height],
        "water_instances": len(sam["floodwater"].instances),
        "wheel_instances": len(sam["wheel"].instances),
        "wheels": wheels,
        "elapsed_s": {phrase: round(r.elapsed_s, 3) for phrase, r in sam.items()},
    }


def check_wav(data: bytes) -> dict:
    """The clip's format, and whether it is the mono, 16-bit, 16 kHz PCM it must be.

    The wave module reads PCM only, so any other encoding fails here.
    """
    try:
        with wave.open(io.BytesIO(data)) as clip:
            channels, width = clip.getnchannels(), clip.getsampwidth()
            rate, frames = clip.getframerate(), clip.getnframes()
    except (wave.Error, EOFError) as exc:
        return {"ok": False, "error": str(exc)}
    return {
        "ok": (channels, width, rate) == (1, 2, 16000),
        "channels": channels,
        "bits": 8 * width,
        "rate_hz": rate,
        "seconds": round(frames / rate, 3) if rate else None,
    }


def probe_voice(client: MetaClient, path: Path, out: Path) -> dict:
    """One clip: the format check, then the transcript if the format passes."""
    data = path.read_bytes()
    form = check_wav(data)
    row = {"file": path.name, "format": form, "text": None, "elapsed_s": None}
    if not form["ok"]:
        row["skipped"] = "not mono, 16-bit, 16 kHz PCM"
        return row
    result = client.transcribe(data)
    folder = out / "voice"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{path.stem}.json").write_text(result.raw, encoding="utf-8")
    row.update(text=result.text, elapsed_s=round(result.elapsed_s, 3))
    return row


def latency(times: list[float]) -> dict:
    """The median and the longest of one call type's times."""
    if not times:
        return {"calls": 0}
    return {
        "calls": len(times),
        "p50_s": round(statistics.median(times), 3),
        "max_s": round(max(times), 3),
    }


def totals(a1: list[dict], a2: list[dict], voice: list[dict]) -> dict:
    """Calls per model, tokens, the estimated cost, and latency per call type."""
    sam_s = [p["elapsed_s"] for row in a1 for p in row["sam"].values()]
    sam_s += [s for row in a2 for s in row["elapsed_s"].values()]
    judge_s = [row["spark"]["elapsed_s"] for row in a1]
    judge_s = [s for s in judge_s if s is not None]  # None: the answer wasn't JSON
    count_s = [row["count_elapsed_s"] for row in a1]
    voice_s = [row["elapsed_s"] for row in voice if row["elapsed_s"] is not None]
    spark_in = sum(row["spark"]["input_tokens"] or 0 for row in a1)
    spark_out = sum(row["spark"]["output_tokens"] or 0 for row in a1)
    clip_s = sum(row["format"]["seconds"] for row in voice if row["text"] is not None)
    cost = {
        "sam": len(sam_s) * SAM_USD_PER_IMAGE,
        "spark": spark_in * SPARK_USD_PER_INPUT_TOKEN
        + spark_out * SPARK_USD_PER_OUTPUT_TOKEN,
        "voice": clip_s * VOICE_USD_PER_SECOND,
    }
    cost["total"] = sum(cost.values())
    return {
        "calls": {
            SAM_MODEL: len(sam_s),
            SPARK_MODEL: {"judge": len(a1), "count_input_tokens": len(a1)},
            TRANSCRIBE_MODEL: len(voice_s),
        },
        "tokens": {
            "counted_input": sum(row["counted_input_tokens"] for row in a1),
            "judge_input": spark_in,
            "judge_output": spark_out,
        },
        "voice_seconds": round(clip_s, 3),
        "estimated_cost_usd": {k: round(v, 5) for k, v in cost.items()},
        "latency": {
            "sam": latency(sam_s),
            "judge": latency(judge_s),
            "count_input_tokens": latency(count_s),
            "transcribe": latency(voice_s),
        },
    }


def main(
    argv: Sequence[str] | None = None,
    *,
    make_client: Callable[[], MetaClient] = MetaClient,
) -> int:
    """The probe. `make_client` is for tests: MetaClient, with MODEL_API_KEY's key."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--photos", type=int, default=5, help="A1 photos")
    parser.add_argument("--water", type=int, default=10, help="A2 photos")
    parser.add_argument(
        "--voice-dir",
        type=Path,
        help="send every WAV in this folder, not the test clip",
    )
    args = parser.parse_args(argv)
    out = DATA / "probes" / date.today().isoformat()
    if (out / "summary.json").exists():
        sys.exit(f"{out / 'summary.json'} exists: move it aside, so no record is lost")
    if args.voice_dir:
        # Sealed data is never opened or listed (CLAUDE.md).
        if "sealed" in (part.lower() for part in args.voice_dir.resolve().parts):
            sys.exit("--voice-dir is inside a sealed folder")
        clips = sorted(args.voice_dir.glob("*.wav"))
    else:
        clips = [out / TEST_CLIP]
    if not clips or not all(clip.is_file() for clip in clips):
        sys.exit("no clip to send: run probes/make_test_wav.ps1, or check --voice-dir")

    a1_photos, a2_photos = choose(args.photos, args.water)
    prompt = (PROMPTS / f"{PROMPT_VERSION}.md").read_text(encoding="utf-8")
    schema_path = PROMPTS / f"{PROMPT_VERSION}.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator_class = validator_for(schema, default=Draft202012Validator)
    validator_class.check_schema(schema)
    validator = validator_class(schema)
    spend = check_before_paying()  # MS4's counter, before any client (C527)
    client = CountedClient(make_client())  # one client, so connections are kept
    try:
        return _run(client, a1_photos, a2_photos, clips, prompt, schema, validator, out)
    finally:  # the whole run's cost, once, however it ends (R126)
        spend.record_after(client.take(), "run_probe")


def _run(
    client: CountedClient,
    a1_photos: list[str],
    a2_photos: list[str],
    clips: list[Path],
    prompt: str,
    schema: dict,
    validator: Validator,
    out: Path,
) -> int:
    """The paid part: A1, A2 and the clips, then summary.json."""
    out.mkdir(parents=True, exist_ok=True)
    # Each HTTP try's model, phrase or schema name, status and time; never content.
    calls_log = logging.FileHandler(out / "meta_calls.jsonl", encoding="utf-8")
    logging.getLogger("lusot.meta").addHandler(calls_log)
    started = datetime.now().astimezone()
    clock = time.monotonic()

    a1 = []
    for n, name in enumerate(a1_photos, 1):
        row = probe_a1(client, name, prompt, schema, validator, out)
        a1.append(row)
        sam_s = [p["elapsed_s"] for p in row["sam"].values()]
        spark, problems = row["spark"], row["id_problems"]
        print(
            f"A1 {n}/{len(a1_photos)} {name}: {row['faces']} faces, "
            f"{sum(row['numbered_boxes'].values())} boxes, "
            f"SAM p50 {statistics.median(sam_s):.1f} s max {max(sam_s):.1f} s, "
            f"{row['counted_input_tokens']} tokens counted, "
            f"judge {spark['elapsed_s']} s "
            f"({spark['input_tokens']} in, {spark['output_tokens']} out), "
            f"schema {'valid' if row['schema_valid'] else 'INVALID'}, "
            f"{'unchecked' if problems is None else len(problems)} id problems"
        )
    a2 = []
    for n, name in enumerate(a2_photos, 1):
        row = probe_a2(client, name, out)
        a2.append(row)
        print(
            f"A2 {n}/{len(a2_photos)} {name}: {row['water_instances']} water, "
            f"{row['wheel_instances']} wheels, SAM {row['elapsed_s']['floodwater']} s "
            f"and {row['elapsed_s']['wheel']} s"
        )
    voice = []
    for clip in clips:
        row = probe_voice(client, clip, out)
        voice.append(row)
        took = "skipped" if row["text"] is None else f"{row['elapsed_s']} s"
        form = "ok" if row["format"]["ok"] else "FAILED"
        print(f"voice {clip.name}: format {form}, {took}")

    summary = {
        "started": started.isoformat(timespec="seconds"),
        "run_s": round(time.monotonic() - clock, 1),
        "seed": SEED,
        "levels": list(LEVELS),
        "a1_photos": a1_photos,
        "a2_photos": a2_photos,
        "blur_version": FACE_BLUR_VERSION,
        "prompt_version": PROMPT_VERSION,
        "models": [SAM_MODEL, SPARK_MODEL, TRANSCRIBE_MODEL],
        "a1": a1,
        "a2": a2,
        "voice": voice,
        "totals": totals(a1, a2, voice),
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    sums = summary["totals"]
    print(
        f"done in {summary['run_s']} s: calls {json.dumps(sums['calls'])}, "
        f"tokens {json.dumps(sums['tokens'])}, "
        f"estimated ${sums['estimated_cost_usd']['total']:.4f}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
