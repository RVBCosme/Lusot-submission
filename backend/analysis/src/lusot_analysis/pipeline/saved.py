"""Saved model outputs, which the offline runner keeps and replays (spec §3.7, B3).

RecordingClient passes each call on to the Meta client and keeps what comes back, and
its `save` writes a run folder. SavedOutputsClient answers from that folder, with no
key and no Meta call, so the same outputs go through the same pipeline again. The
folder keeps Muse Spark's reason, which only the offline runner saves (C62).

A run folder holds:
- `run.json`: the photo's file name and SHA-256, the phrases SAM was asked, the
  prompt version and schema name, the model ids, the blur version, the size of the
  image SAM saw, the outcome and the log
- `sam/<phrase>.json`, with the phrase's spaces as `_`: the phrase, its time, and
  each instance's id, box and score. `sam/<phrase>.npz` holds the masks, N x H x W,
  only when SAM found something, and `sam/<phrase>.raw` SAM's raw output text. A
  call that failed leaves none of the three.
- `spark.json`: Muse Spark's answer, reason included, its token counts and its time,
  with `spark.raw`, the answer's raw text. A refusal (C86) is kept as exactly
  `{"refused": true}`, with no `spark.raw`: ModelRefused carries no text. Neither
  file exists when the call failed or was never made.

A replay ends as the live run did when that run ended on a model's answer, a
refusal or a failed call (R109).
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import threading
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from lusot_analysis.face_blur import BlurredImage
from lusot_analysis.meta_client import (
    SAM_MODEL,
    SAM_PHRASES,
    SPARK_MODEL,
    MetaApiError,
    ModelRefused,
    SamInstance,
    SamResult,
    SparkResult,
)
from lusot_analysis.pipeline.publish import PUBLISH_PHRASES
from lusot_analysis.pipeline.types import ModelAnswerError, ModelClient
from lusot_analysis.prompts import PromptSpec

if TYPE_CHECKING:  # the package imports its modules, never the reverse
    from lusot_analysis.pipeline import PipelineRun


class PhotoMismatch(ValueError):
    """The saved outputs belong to another photo: its SHA-256 isn't run.json's."""


class RecordingClient:
    """A ModelClient that passes each call on and keeps what comes back (spec §3.7).

    `client` is the Meta client in the offline runner's live mode. Each call's
    keywords pass through unchanged (R108). The phrases run in parallel, so what is
    kept is kept behind a lock, but the calls themselves run outside it. A call that
    raises keeps nothing, though its phrase still counts as asked. The exception is
    a Muse Spark refusal: it is kept, then raised again unchanged (R109).
    """

    def __init__(self, client: ModelClient) -> None:
        self._client = client
        self._lock = threading.Lock()
        self._asked: set[str] = set()
        self._size: tuple[int, int] | None = None  # the image SAM saw: width, height
        self._sam: dict[str, SamResult] = {}
        self._spark: SparkResult | None = None
        self._refused = False

    def segment(
        self, image: BlurredImage, phrase: str, *, deadline: float | None = None
    ) -> SamResult:
        with self._lock:
            self._asked.add(phrase)
            self._size = (image.width, image.height)
        result = self._client.segment(image, phrase, deadline=deadline)
        with self._lock:
            self._sam[phrase] = result
        return result

    def judge(
        self,
        image: BlurredImage,
        *,
        prompt: str,
        schema: dict,
        schema_name: str,
        deadline: float | None = None,
        reasoning_effort: str | None = None,
    ) -> SparkResult:
        try:
            result = self._client.judge(
                image,
                prompt=prompt,
                schema=schema,
                schema_name=schema_name,
                deadline=deadline,
                reasoning_effort=reasoning_effort,
            )
        except ModelRefused:
            with self._lock:
                self._refused = True
            raise
        with self._lock:
            self._spark = result
        return result

    def save(
        self, run_dir: Path, *, photo: Path, prompt: PromptSpec, run: PipelineRun
    ) -> None:
        """Write the run folder for `run`, which these calls made, on `photo`.

        `run_dir` must not exist yet, so two runs never mix, and run.json is written
        last, so a folder without one is incomplete. The phrases come in
        SAM_PHRASES' order. Before any SAM call, `image` is None, and before step 0
        ran, `blur_version` is too.
        """
        sam_dir = run_dir / "sam"
        run_dir.mkdir(parents=True)
        sam_dir.mkdir()
        for phrase, result in self._sam.items():
            stem = _stem(phrase)
            instances = [
                {"id": inst.id, "box": list(inst.box), "score": inst.score}
                for inst in result.instances
            ]
            saved = {
                "phrase": phrase,
                "elapsed_s": result.elapsed_s,
                "instances": instances,
            }
            _write_json(sam_dir / f"{stem}.json", saved)
            if result.instances:
                masks = np.array([inst.mask for inst in result.instances], bool)
                np.savez_compressed(sam_dir / f"{stem}.npz", masks=masks)
            # Bytes, so line ends come back exactly as SAM sent them.
            (sam_dir / f"{stem}.raw").write_bytes(result.raw.encode("utf-8"))
        if self._refused:  # no reason or text: ModelRefused carries none (C86)
            _write_json(run_dir / "spark.json", {"refused": True})
        elif self._spark is not None:
            answer = {
                "data": self._spark.data,  # with its reason (C62)
                "input_tokens": self._spark.input_tokens,
                "output_tokens": self._spark.output_tokens,
                "reasoning_tokens": self._spark.reasoning_tokens,
                "elapsed_s": self._spark.elapsed_s,
            }
            _write_json(run_dir / "spark.json", answer)
            (run_dir / "spark.raw").write_bytes(self._spark.raw.encode("utf-8"))
        size = None
        if self._size is not None:
            size = {"width": self._size[0], "height": self._size[1]}
        record = {
            "photo": photo.name,
            "photo_sha256": hashlib.sha256(photo.read_bytes()).hexdigest(),
            "phrases": [phrase for phrase in SAM_PHRASES if phrase in self._asked],
            "prompt_version": prompt.version,
            "schema_name": prompt.schema_name,
            "models": {"sam": SAM_MODEL, "spark": SPARK_MODEL},
            "blur_version": run.log.get("blur_version"),
            "image": size,
            "outcome": dataclasses.asdict(run.outcome),
            "log": run.log,
        }
        _write_json(run_dir / "run.json", record)


class SavedOutputsClient:
    """A ModelClient that answers from a run folder, with no key and no Meta call (B3).

    It reads run.json first. When `photo_data` isn't the photo the outputs were saved
    for, it raises PhotoMismatch, a ValueError. Each call's keywords are accepted and
    ignored (R108): a replay has no deadline to keep and no effort to ask for. A
    refusal or a failed call is raised again, so the replay ends as the live run did
    (R109).
    """

    def __init__(self, run_dir: Path, photo_data: bytes) -> None:
        self._dir = run_dir
        self._run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
        if hashlib.sha256(photo_data).hexdigest() != self._run["photo_sha256"]:
            raise PhotoMismatch("saved outputs belong to another photo")

    def segment(
        self, image: BlurredImage, phrase: str, *, deadline: float | None = None
    ) -> SamResult:
        """The saved result for `phrase`, for an image of the saved size.

        Another size raises ValueError. A phrase the live run asked for but saved no
        result for failed live, and fails again (R109):
        - when the saved log has `meta_status`, the run ended on a MetaApiError, so
          this raises one with that status: failed/model_error, as live
        - otherwise KeyError, which ends failed/pipeline_error, as live

        A phrase the live run never asked for: `face` and `license plate` come back
        empty, as the runner never asks for them (C66), so the handler's pipeline
        call can replay a runner's folder. Any other raises KeyError.
        """
        if self._run["image"] != {"width": image.width, "height": image.height}:
            raise ValueError("saved outputs are for an image of another size")
        path = self._dir / "sam" / f"{_stem(phrase)}.json"
        if not path.exists():
            asked = phrase in self._run["phrases"]
            if asked and "meta_status" in self._run["log"]:
                status = self._run["log"]["meta_status"]
                raise MetaApiError("SAM's call failed in the live run", status=status)
            if not asked and phrase in PUBLISH_PHRASES:
                return SamResult(phrase, [], 0.0, "")
            raise KeyError(phrase)
        saved = json.loads(path.read_text(encoding="utf-8"))
        masks: np.ndarray | tuple[()] = ()
        if saved["instances"]:
            with np.load(path.with_suffix(".npz")) as arrays:
                masks = arrays["masks"]
        instances = [
            SamInstance(
                item["id"],
                tuple(float(value) for value in item["box"]),
                mask,
                item["score"],
            )
            for item, mask in zip(saved["instances"], masks, strict=True)
        ]
        raw = path.with_suffix(".raw").read_bytes().decode("utf-8")
        return SamResult(saved["phrase"], instances, saved["elapsed_s"], raw)

    def judge(
        self,
        image: BlurredImage,
        *,
        prompt: str,
        schema: dict,
        schema_name: str,
        deadline: float | None = None,
        reasoning_effort: str | None = None,
    ) -> SparkResult:
        """The saved answer, asked for under the schema it was saved under.

        Another `schema_name` raises ValueError, checked first. A saved refusal
        raises ModelRefused, which ends refused/model_declined, as live (C86, R109).
        When the live run saved no answer, it raises ModelAnswerError, which the
        pipeline ends as failed/model_error.
        """
        if schema_name != self._run["schema_name"]:
            raise ValueError("the saved answer is for another schema")
        path = self._dir / "spark.json"
        if not path.exists():
            raise ModelAnswerError("the live run saved no answer")
        saved = json.loads(path.read_text(encoding="utf-8"))
        if saved.get("refused"):
            raise ModelRefused("Muse Spark refused to answer")
        return SparkResult(
            data=saved["data"],
            input_tokens=saved["input_tokens"],
            output_tokens=saved["output_tokens"],
            elapsed_s=saved["elapsed_s"],
            raw=(self._dir / "spark.raw").read_bytes().decode("utf-8"),
            reasoning_tokens=saved["reasoning_tokens"],
        )


def _stem(phrase: str) -> str:
    """A phrase's file name: its spaces as `_`, so `wheel rim` is `wheel_rim`."""
    return phrase.replace(" ", "_")


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")
