"""MS6's results rows, from saved runs (C315, C321, C327; MS6's §4.3 and C412).

The development tool (probes/dev_eval.py) and the sealed-run entry point (Task 19)
both build their rows here, so the sealed rows are bridged by the code that bridged
the development ones. Apart from replay_configurations, which replays a run folder,
every function is path-free: text and objects in, rows out. Each tool opens its own
files after its own path guard (R135, M9).

The rows follow MS6's row contract as its loader checks it (`eval/scoring/rows.py`,
on Window 4's branch at 1cafc88), whose names win where the plan's differ:
- run.json's versions are `frozen`, a flat map of names to short strings
- the self-check is `self_check` ("off") and `self_check_decided`
- a dropped geometry's reason is `geometry_dropped_reason`
- `wheel_inches` is a list of {box_id, depthInMin, depthInMax}
- each `m8` entry carries `vehicle_type`, null on a wheel or a person

MS2's formats win over the plan's too (its §5.9): its manifest carries `duplicate`
as yes or no, worked out from `duplicate_of`, so `duplicate` is bridged like the
other yes-or-no facts and `duplicate_of`, an id, stays out.

Nothing here imports eval/ (C321, MS6's C400). The label words come from
`python eval/run_eval.py --label-words`, which the tool runs.
"""

from __future__ import annotations

import csv
import dataclasses
import io
import math
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Literal

from lusot_analysis import rules
from lusot_analysis.face_blur import MAX_SIDE
from lusot_analysis.pipeline import READING_PHRASES, PipelineRun, run_pipeline
from lusot_analysis.pipeline.evidence import Evidence
from lusot_analysis.pipeline.references import validate_answer
from lusot_analysis.pipeline.saved import SavedOutputsClient
from lusot_analysis.pipeline.types import ModelAnswerError
from lusot_analysis.prompts import PromptSpec
from lusot_analysis.tuning import TUNING, Tuning

# Each outcome key and its geometry_in_level (C309, C315).
CONFIGURATIONS = {"landmark": False, "geometry": True}
# What a label with any other word is written as (MS6's C420).
OTHER_WORDS = "(other words)"

# A mirror of the harness's scoring.labels.label_words_ok, as committed on Window 4's
# branch (P1): its three patterns, copied exactly. A "." outside a number separates
# words, and a number may be glued to `in` or `cm`.
_MARKS = "-–,()\"'”“″/+"
_LABEL_CHARS = re.compile(f"[A-Za-z0-9 .{re.escape(_MARKS)}]*")
_SEPARATOR = re.compile(f"[ {re.escape(_MARKS)}]+|(?<![0-9])[.]|[.](?![0-9])")
_NUMBER_TOKEN = re.compile("[0-9]{1,3}(?:[.][0-9]{1,2})?(?:in|cm)?")

# The columns the tools need (P10). A Set A row also needs its event_id.
_MANIFEST_NEEDS = ("photo_id", "set", "photo_file")
_M8_COLUMNS = (
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
# MS6's §4.3 base fields, in its order: a Set A row's, and an A-neg row's, which has
# no labels and adds `surface`.
SET_A_FIELDS = (
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
)
_LABELS = ("level_label_raw", "passability_raw", "other_alerts_raw")
A_NEG_FIELDS = (*(f for f in SET_A_FIELDS if f not in _LABELS), "surface")
# Each M8 kind: the evidence record's kind for its boxes (a vehicle's is `body`), and
# the M8 column that holds its landmark.
_M8_KINDS = {
    "wheel": ("wheel", "waterline"),
    "vehicle": ("body", "body_waterline"),
    "person": ("person", "waterline"),
}
# The Meta client never asks Meta to store a request (R76).
_STORE = "false"
# A byte-order mark, which a CSV saved on Windows may start with.
_BOM = chr(0xFEFF)
# MS6's loader's patterns (rows.py, at 1cafc88): a name in run.json's maps, and a
# short string, which can hold no link or email (and no "://", checked apart).
_TOKEN = re.compile("[a-z][a-z0-9_]{0,31}")
_SHORT = re.compile("[A-Za-z0-9 ._:/,+()=-]{0,80}")
# run.json's datasets, each {version, split_seed} (MS6's rows.py, MS2's C216).
_DATASETS = ("set_a", "a_neg", "set_b", "set_d")
_DATASET_FIELDS = {"version", "split_seed"}
# The answer's lists, and the box ids MS6's loader takes in them (R152).
_ANSWER_LISTS = ("vehicles", "wheels", "people")
_MAX_BOX_ID = 9999


class InputError(ValueError):
    """Input breaks its format: MS2's files, or run.json's datasets. The message names
    the row, the column or the rule, never a cell's text."""


def parse_manifest(text: str) -> list[dict]:
    """MS2's manifest.csv, from its text: one dict per row, in file order.

    A byte-order mark is dropped. photo_id, set and photo_file must be filled in,
    photo_id must be unique, and a Set A row (set A) needs its event_id; other
    manifests, such as Task 16's for Set C, may leave it out (P10).
    """
    reader = csv.DictReader(io.StringIO(text.removeprefix(_BOM)))
    for column in _MANIFEST_NEEDS:
        if column not in (reader.fieldnames or ()):
            raise InputError(f"the manifest has no {column} column")
    rows: list[dict] = []
    seen: set[str] = set()
    for number, row in enumerate(reader, start=1):
        for column in _MANIFEST_NEEDS:
            if not row[column]:
                raise InputError(f"manifest row {number} has no {column}")
        if row["photo_id"] in seen:
            raise InputError(
                f"manifest row {number}: photo_id repeats an earlier row's"
            )
        if row["set"] == "A" and not row.get("event_id"):
            raise InputError(f"manifest row {number}: a Set A row needs its event_id")
        seen.add(row["photo_id"])
        rows.append(dict(row))
    return rows


def parse_m8(text: str) -> dict[str, list[dict]]:
    """MS2's m8.csv, from its text: its rows grouped by photo_id, in file order."""
    reader = csv.DictReader(io.StringIO(text.removeprefix(_BOM)))
    for column in _M8_COLUMNS:
        if column not in (reader.fieldnames or ()):
            raise InputError(f"the M8 sheet has no {column} column")
    grouped: dict[str, list[dict]] = {}
    for row in reader:
        grouped.setdefault(row["photo_id"], []).append(dict(row))
    return grouped


def label_or_marker(label: str, words: frozenset[str]) -> str:
    """`label` as written when the harness's label_words_ok would pass it, or else
    OTHER_WORDS (C327, MS6's C420).

    A blank label and the marker itself stay as they are. Any other label stays when
    it holds only the label characters, and each of its words is in `words` (the
    harness's --label-words) or is a number of up to 3 digits with up to 2 decimals,
    optionally glued to `in` or `cm`.
    """
    if label.strip() == "" or label == OTHER_WORDS:
        return label
    if not _LABEL_CHARS.fullmatch(label):
        return OTHER_WORDS
    tokens = [token for token in _SEPARATOR.split(label.lower()) if token]
    if all(token in words or _NUMBER_TOKEN.fullmatch(token) for token in tokens):
        return label
    return OTHER_WORDS


def bridge_base(
    row: Mapping, m8_rows: Sequence[Mapping], *, words: frozenset[str]
) -> dict:
    """One Set A or A-neg manifest row as MS6's §4.3 base fields.

    `yes` and `no` become booleans and `;`-separated lists become lists. Every label
    goes through label_or_marker with `words`. `quality` and `subsets` come from
    M8's photo row in `m8_rows`, and stay null and empty without one (MS6's C423).
    An A-neg row has no labels, a null `match` and its `surface`. Cities, spots,
    notes, file names, hashes, sizes and times stay out.
    """
    if row["set"] not in ("A", "A-neg"):
        raise InputError("bridge_base takes Set A and A-neg rows only")
    set_a = row["set"] == "A"
    photo = next((found for found in m8_rows if found["kind"] == "photo"), None)
    base: dict[str, object] = {"photo_id": row["photo_id"], "event_id": row["event_id"]}
    if set_a:
        base |= {
            "level_label_raw": label_or_marker(row["level_label_raw"], words),
            "passability_raw": label_or_marker(row["passability_raw"], words),
            "other_alerts_raw": [
                label_or_marker(label, words)
                for label in _split(row["other_alerts_raw"])
            ],
        }
    base |= {
        "poster_kind": row["poster_kind"],
        "label_in_image": row["label_in_image"],
        "match": row["match"] if set_a else None,
        "duplicate": _yes_no(row, "duplicate"),
        "metro_manila": _yes_no(row, "metro_manila"),
        "decodes": _yes_no(row, "decodes"),
        "quality": (photo["quality"] or None) if photo is not None else None,
        "subsets": _split(photo["subsets"]) if photo is not None else [],
    }
    if not set_a:
        base["surface"] = row["surface"]
    return base


def answer_data(spark: Mapping | None) -> Mapping | None:
    """Muse Spark's answer, reason and all, from a run folder's spark.json content.

    None when the run saved no spark.json (`spark` None) or saved a refusal (C86).
    """
    if spark is None or spark.get("refused"):
        return None
    return spark["data"]


def answer_without_reason(data: Mapping | None, schema: dict) -> dict | None:
    """Muse Spark's saved answer without its `reason` (C62).

    None when no answer was saved, or when the answer fails the schema, since MS6's
    allow-list would refuse such a row (P13). None too when an id would make MS6's
    loader refuse the whole file, though the schema passes it (R152): see
    loader_takes_ids. The answer itself is never changed.
    """
    if data is None:
        return None
    try:
        validate_answer(data, schema)
    except ModelAnswerError:
        return None
    if not loader_takes_ids(data):
        return None
    return {key: value for key, value in data.items() if key != "reason"}


def loader_takes_ids(answer: Mapping) -> bool:
    """Whether MS6's loader would take the ids in the answer's lists (R152).

    In each list, every item's id must be a whole number from 0 to 9999, an int
    and not a float such as 2.0, which the schema's Draft 2020-12 counts as an
    integer. It must also come once in that list. An id may still repeat across
    lists, as the loader allows.
    """
    for name in _ANSWER_LISTS:
        ids = [item.get("id") for item in answer.get(name, ())]
        if any(type(i) is not int or not 0 <= i <= _MAX_BOX_ID for i in ids):
            return False
        if len(set(ids)) < len(ids):
            return False
    return True


def replay_configurations(
    photo_data: bytes,
    run_dir: Path,
    prompt: PromptSpec,
    *,
    tuning: Tuning = TUNING,
    configurations: Mapping[str, bool] = CONFIGURATIONS,
) -> dict[str, PipelineRun]:
    """One replay of the run saved in `run_dir` per configuration, with no Meta call.

    Each configuration's value is its geometry_in_level (C309, C315), and every
    replay runs with `tuning` and the phrases the offline runner sends (C66). Outputs
    saved for another photo raise PhotoMismatch.
    """
    client = SavedOutputsClient(run_dir, photo_data)
    return {
        key: run_pipeline(
            photo_data,
            client,
            prompt,
            phrases=READING_PHRASES,
            geometry_in_level=geometry_in_level,
            tuning=tuning,
        )
        for key, geometry_in_level in configurations.items()
    }


def m8_boxes(
    labels: Sequence[Mapping], evidence: Evidence | None, size: tuple[int, int]
) -> list[dict]:
    """Each labelled reference in M8's rows, joined to a numbered box (C327, MS6's
    C415, MS2's C208).

    Its point, scaled to the sent image's `size` (width, height), goes to the
    numbered box of its kind that holds it, edges included: M8's `vehicle` is the
    evidence record's `body`. Where two hold it, the one whose centre is nearest wins,
    the lower id on a tie, and where none does, the box id is null. With no evidence
    record, as on a failed run, every box id is null. M8's photo row is no reference.
    Each entry has `box_id`, `kind` (M8's), `landmark` (a wheel's or a person's
    `waterline`, a vehicle's `body_waterline`, null when unmarked) and `vehicle_type`
    (a vehicle's, else null).
    """
    entries = () if evidence is None else evidence.references
    width, height = size
    joined = []
    for label in labels:
        if label["kind"] == "photo":
            continue
        kind, column = _M8_KINDS[label["kind"]]
        x, y = float(label["x"]) * width, float(label["y"]) * height
        holding = [
            entry
            for entry in entries
            if entry.kind == kind
            and entry.box[0] <= x <= entry.box[2]
            and entry.box[1] <= y <= entry.box[3]
        ]
        nearest = min(
            holding, key=lambda entry: _distance(entry.box, x, y), default=None
        )
        joined.append(
            {
                "box_id": None if nearest is None else nearest.id,
                "kind": label["kind"],
                "landmark": label[column] or None,
                "vehicle_type": (label["vehicle_type"] or None)
                if label["kind"] == "vehicle"
                else None,
            }
        )
    return joined


def photo_row(
    base: Mapping[str, object],
    runs: Mapping[str, PipelineRun],
    answer: Mapping | None,
    *,
    m8: Sequence[dict] = (),
    replay: Mapping[str, Mapping] | None = None,
) -> dict[str, object]:
    """One photo's §4.3 row: `base`'s §4.3 fields, then its results.

    `base` is bridge_base's: a row with its labels is a Set A row. Only its side's
    §4.3 fields are kept, so a stray manifest cell can't reach a row.
    - `outcomes`: each configuration's item_fields() by its key, then, for each
      configuration in `replay`, its event-replay result as `<key>_replay` (C324,
      MS6's C425)
    - `answer`: Muse Spark's, never with its `reason` (C62), and null when an id
      would make MS6's loader refuse the file (R152, loader_takes_ids)
    - `wheel_inches`: each wheel the `geometry` run's evidence record measured, by box
      id, its inches unrounded to 4 decimal places (C327; finding 2); empty without a
      geometry run (MS6's C418)
    - `m8`, on a Set A row: the entries m8_boxes gave, possibly none
    """
    set_a = "level_label_raw" in base
    kept = SET_A_FIELDS if set_a else A_NEG_FIELDS
    row = {key: base[key] for key in kept if key in base}
    outcomes = {key: run.outcome.item_fields() for key, run in runs.items()}
    for key, replayed in (replay or {}).items():
        outcomes[f"{key}_replay"] = dict(replayed)
    row["outcomes"] = outcomes
    if answer is None or not loader_takes_ids(answer):
        row["answer"] = None
    else:
        row["answer"] = {key: value for key, value in answer.items() if key != "reason"}
    geometry = runs.get("geometry")
    row["wheel_inches"] = _wheel_inches(None if geometry is None else geometry.evidence)
    if set_a:
        row["m8"] = [dict(entry) for entry in m8]
    return row


def saved_row(
    base: Mapping[str, object],
    runs: Mapping[str, PipelineRun],
    spark: Mapping | None,
    record: Mapping,
    schema: dict,
    *,
    labels: Sequence[Mapping] = (),
    replay: Mapping[str, Mapping] | None = None,
) -> dict[str, object]:
    """One photo's row from its saved run, as the development tool and Task 19 both
    build it.

    `runs` are replay_configurations' replays of the run. `spark` is the run
    folder's spark.json content, or None without one, and `record` its run.json.
    `schema` is the answer schema. `labels` are the photo's M8 rows, and `replay` its
    event-replay outcomes by configuration.
    - The answer goes through answer_without_reason, so it is null when it fails the
      schema or holds an id MS6's loader refuses (P13, R152).
    - The M8 points join the `landmark` run's numbered boxes, scaled to the image SAM
      saw. Boxes are numbered alike in every configuration.
    - photo_row gives the rest: `wheel_inches` from the `geometry` run, and `m8` on
      a Set A row only.
    """
    answer = answer_without_reason(answer_data(spark), schema)
    image = record["image"]
    size = (0, 0) if image is None else (image["width"], image["height"])
    boxes = m8_boxes(labels, runs["landmark"].evidence, size)
    return photo_row(base, runs, answer, m8=boxes, replay=replay)


def results_manifest(
    *,
    kind: Literal["development", "sealed"] = "development",
    date: str,
    rules_version: str,
    tuning: Tuning,
    saved_run: Mapping,
    geometry_default: str,
    dropped_reason: str | None,
    datasets: Mapping,
    freeze_commit: str | None = None,
    baseline: Mapping | None = None,
    stops: Sequence[Mapping] = (),
    rerun_reason: str | None = None,
    self_check_decided: str | None = None,
) -> dict:
    """run.json, in MS6's names (its §4.3).

    - `kind`, the Manila `date` and `rules_version`
    - for a sealed run (Task 19): `freeze_commit`, `baseline_level` and
      `baseline_class` from `baseline` (the last development report's summary.json
      names them so, MS6's C424), `stops` (C419) and a rerun's `rerun_reason`
      (C421). It needs the first three. A development run carries none of these.
    - `frozen` (v0.7 item 10.1): the models, the prompt and schema, the drawing, the
      blur, `store`, `max_side`, the SAM phrases sent, the tuning version, every
      numeric Tuning field under its own name (k among them, so a `--set`
      candidate's run.json states its cutoffs, R153), the tire codes and the
      reasoning effort ("default" when none is sent, as C316's log writes it). What
      the models were sent comes from `saved_run`, one saved run's run.json; the
      rest from `tuning` and the rules the replays ran. Each name must be an MS6
      token and each value a short string, or ValueError.
    - `datasets`, checked by check_datasets, and the self-check: "off", and
      `self_check_decided` once C311 has decided, which MS6 requires of a sealed run
    - `geometry_default`: on, off or dropped, with `geometry_dropped_reason` when
      dropped (MS6's C418)
    """
    check_datasets(datasets)
    sealed = kind == "sealed"
    if sealed and None in (freeze_commit, baseline, self_check_decided):
        raise ValueError(
            "a sealed run.json needs the freeze commit, the baseline pair and the"
            " self-check's decision"
        )
    sealed_only = (freeze_commit, baseline, rerun_reason)
    if not sealed and (stops or any(value is not None for value in sealed_only)):
        raise ValueError(
            "a development run.json carries no freeze commit, baseline, stop or rerun"
        )
    if (geometry_default == "dropped") != (dropped_reason is not None):
        raise ValueError("a dropped geometry, and only it, has a reason (MS6's C418)")
    manifest: dict[str, object] = {
        "kind": kind,
        "date": date,
        "rules_version": rules_version,
    }
    if sealed:
        manifest["freeze_commit"] = freeze_commit
    frozen = {
        "sam_model": saved_run["models"]["sam"],
        "spark_model": saved_run["models"]["spark"],
        "prompt": saved_run["prompt_version"],
        "schema": saved_run["schema_name"],
        "drawing": tuning.drawing,
        # A run that never decoded its photo blurred nothing.
        "blur": saved_run["blur_version"] or "",
        "store": _STORE,
        "max_side": str(MAX_SIDE),
        "sam_phrases": ",".join(saved_run["phrases"]),
        "tuning": tuning.version,
    }
    for field in dataclasses.fields(tuning):
        value = getattr(tuning, field.name)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            frozen[field.name] = str(value)
    frozen["tire_codes"] = rules.TIRE_CODES_VERSION
    frozen["reasoning_effort"] = tuning.reasoning_effort or "default"
    for name, value in frozen.items():
        if not _TOKEN.fullmatch(name) or not _short(value):
            raise ValueError(f"frozen's {name} isn't an MS6 token with a short value")
    manifest["frozen"] = frozen
    manifest["datasets"] = {name: dict(found) for name, found in datasets.items()}
    manifest["self_check"] = "off"  # until C311 says otherwise
    if self_check_decided is not None:
        manifest["self_check_decided"] = self_check_decided
    manifest["geometry_default"] = geometry_default
    if dropped_reason is not None:
        manifest["geometry_dropped_reason"] = dropped_reason
    if sealed:
        manifest["baseline_level"] = baseline["baseline_level"]
        manifest["baseline_class"] = baseline["baseline_class"]
        manifest["stops"] = [dict(stop) for stop in stops]
        if rerun_reason is not None:
            manifest["rerun_reason"] = rerun_reason
    return manifest


def check_datasets(datasets: object) -> None:
    """Raise InputError unless `datasets` has MS6's shape for run.json (its rows.py):
    an object whose names are among set_a, a_neg, set_b and set_d, each holding
    exactly `version` and `split_seed` as short strings (MS2's C216 records)."""
    if not isinstance(datasets, Mapping):
        raise InputError("datasets must be an object")
    for name, found in datasets.items():
        if name not in _DATASETS:
            raise InputError(f"datasets may name only {', '.join(_DATASETS)}")
        if not isinstance(found, Mapping) or set(found) != _DATASET_FIELDS:
            raise InputError("each dataset holds exactly version and split_seed")
        if not all(_short(value) for value in found.values()):
            raise InputError(
                "a dataset's version and split_seed are up to 80 plain characters"
            )


def _short(value: object) -> bool:
    """A string MS6's loader takes as short: up to 80 plain characters, no link."""
    return (
        isinstance(value, str) and bool(_SHORT.fullmatch(value)) and "://" not in value
    )


def _split(text: str) -> list[str]:
    """A `;`-separated cell as a list, each entry stripped and blanks dropped, as
    MS2's intake reads its subsets. A blank cell is an empty list."""
    return [part.strip() for part in text.split(";") if part.strip()]


def _yes_no(row: Mapping, column: str) -> bool:
    value = row[column]
    if value not in ("yes", "no"):
        raise InputError(f"{column} must be yes or no")
    return value == "yes"


def _distance(box: tuple[int, int, int, int], x: float, y: float) -> float:
    """How far (x, y) lies from the box's centre."""
    return math.hypot((box[0] + box[2]) / 2 - x, (box[1] + box[3]) / 2 - y)


def _wheel_inches(evidence: Evidence | None) -> list[dict]:
    """Each measured wheel's unrounded inches, to 4 decimal places, by box id."""
    if evidence is None:
        return []
    return [
        {
            "box_id": entry.id,
            "depthInMin": round(entry.inches[0], 4),
            "depthInMax": round(entry.inches[1], 4),
        }
        for entry in evidence.references
        if entry.kind == "wheel" and entry.inches is not None
    ]
