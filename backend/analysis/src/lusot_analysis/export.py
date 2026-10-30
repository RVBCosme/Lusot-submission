"""MS6's results rows, from saved runs (C314, C315, C321, C327; MS6's §4.3 and C412).

The development tools (probes/dev_eval.py and probes/set_b.py) and the sealed-run
entry point (Task 19) all build their rows here, so the sealed rows are bridged by the
code that bridged the development ones. Apart from replay_configurations, which
replays a run folder, every function is path-free: text and objects in, rows out. Each
tool opens its own files after its own path guard (R135, M9).

The rows follow MS6's row contract as its loader checks it (`eval/scoring/rows.py`,
on Window 4's branch at 1cafc88), whose names win where the plan's differ:
- run.json's versions are `frozen`, a flat map of names to short strings
- the self-check is `self_check` ("off") and `self_check_decided`
- a dropped geometry's reason is `geometry_dropped_reason`
- `wheel_inches` is a list of {box_id, depthInMin, depthInMax}
- each `m8` entry carries `vehicle_type`, null on a wheel or a person

- a Set B estimate always holds `measured`, `depthInPoint`, `depthInMin`,
  `depthInMax` and `fail`: three numbers and a null `fail` when measured, else three
  nulls and the failed check's token

MS2's formats win over the plan's too (its §5.9): its manifest carries `duplicate`
as yes or no, worked out from `duplicate_of`, so `duplicate` is bridged like the
other yes-or-no facts and `duplicate_of`, an id, stays out. Its truth.csv copies a
car's tire code as on the sidewall, so parse_truth reads it as MS2's reader does.

Nothing here imports eval/ (C321, MS6's C400). The label words come from
`python eval/run_eval.py --label-words`, which the tool runs.
"""

from __future__ import annotations

import csv
import dataclasses
import io
import math
import re
import statistics
from collections.abc import Mapping, Sequence
from decimal import Decimal
from pathlib import Path
from typing import Literal

from lusot_analysis import rules
from lusot_analysis.face_blur import MAX_SIDE
from lusot_analysis.meta_client import SamInstance, SamResult
from lusot_analysis.pipeline import READING_PHRASES, PipelineRun, run_pipeline
from lusot_analysis.pipeline.evidence import Evidence
from lusot_analysis.pipeline.geometry import (
    RimFit,
    depth_inches,
    fit_rim,
    link_rims,
    rim_points,
    wheel_geometry,
)
from lusot_analysis.pipeline.references import validate_answer
from lusot_analysis.pipeline.saved import SavedOutputsClient
from lusot_analysis.pipeline.segment import box_xyxy
from lusot_analysis.pipeline.types import ModelAnswerError
from lusot_analysis.pipeline.waterline import Waterline, find_waterline, water_mask
from lusot_analysis.prompts import PromptSpec
from lusot_analysis.rules import TireCode
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

# Set B (C314). The truth.csv columns read, of MS2's (its §5.9 and formats.py).
_TRUTH_NEEDS = (
    "crop_id",
    "wheel",
    "car_id",
    "crop_file",
    "vehicle_type",
    "tire_code",
    "x0",
    "y0",
    "x1",
    "y1",
    "px_per_in",
    "waterline_row",
    "true_depth_in",
    "view",
    "size_bin",
    "rim_edge_ratio",
)
# MS2's lists (its formats.py): the Set B types, which all have plan Table 7 codes,
# the views and the size bins.
SET_B_TYPES = ("sedan_hatch", "suv_mpv", "van")
_VIEWS = ("side", "angled")
_SIZE_BINS = ("full", "small")
# C314's variants, in MS6's order. The self-check's variant joins only with it on.
SET_B_VARIANTS = (
    "geometry",
    "geometry_uncalibrated",
    "known_waterline",
    "known_waterline_uncalibrated",
)
_ESTIMATE_NUMBERS = ("depthInPoint", "depthInMin", "depthInMax")
# MS6's loader's patterns (rows.py): an opaque id, which no date or spot fits, and a
# wheel, 1 the leftmost.
_ID = re.compile("[A-Z]{1,3}[0-9]{1,4}(?:-[0-9]{1,3}){0,2}")
_WHEELS = ("1", "2")
# A bare name, for a crop_file and for a manifest's photo_id, set and photo_file: no
# separator, no ":", which names an NTFS stream, and no trailing dot, which Windows
# strips (R156). ".." is refused apart.
_FILE_NAME = re.compile("[A-Za-z0-9_](?:[A-Za-z0-9_.-]*[A-Za-z0-9_-])?")
# A tire code as MS2's tires.parse_tire_code reads a sidewall's: any case, an
# optional P or LT, spaces around the R, an optional Z before it, a C suffix, and
# anything after the rim once a space separates it. Only the C is kept.
_SIDEWALL_CODE = re.compile(
    r"(?:P|LT)?([0-9]{3})/([0-9]{2})\s*Z?R\s*([0-9]{2})(C?)(?:\s.*)?", re.IGNORECASE
)
# MS6's loader takes depths from 0 to under 100 in, with at most 4 decimal places.
_MAX_DEPTH_IN = 100
_DEPTH_PLACES = 4
# Set B has no Muse Spark answer: any wheel waterline but not_visible passes check 1.
_ANSWERED = "hub"

# Set D (MS6's §4.3: as Set B, with the ruler depth as the truth). The set_d_log.csv
# columns read, of MS2's (its §5.9), and each `wheel` with its MS6 number, 1 the
# leftmost. Set D has no known waterline, so it has only the SAM-waterline variants.
_SET_D_NEEDS = (
    "photo_id",
    "photo_file",
    "wheel",
    "vehicle_type",
    "tire_code",
    "ruler_depth_in",
)
_SET_D_WHEELS = {"left": 1, "right": 2}
SET_D_VARIANTS = ("geometry", "geometry_uncalibrated")


class InputError(ValueError):
    """Input breaks its format: MS2's files, or run.json's datasets. The message names
    the row, the column or the rule, never a cell's text. A Set B row is named by its
    crop_id and wheel once both pass MS6's opaque-id and wheel checks."""


def parse_manifest(text: str) -> list[dict]:
    """MS2's manifest.csv, from its text: one dict per row, in file order.

    A byte-order mark is dropped. photo_id, set and photo_file must be filled in, each
    one bare name that leads no path out of the folder it is joined to (M6).
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
            if not _FILE_NAME.fullmatch(row[column]) or ".." in row[column]:
                raise InputError(
                    f"manifest row {number}: {column} must be one name, with no folder"
                )
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
    service_retries: int | None = None,
) -> dict:
    """run.json, in MS6's names (its §4.3).

    - `kind`, the Manila `date` and `rules_version`
    - for a sealed run (Task 19): `freeze_commit`, `baseline_level` and
      `baseline_class` from `baseline` (the last development report's summary.json
      names them so, MS6's C424), `stops` (C419), `service_retries` (MS6E-Q6: the
      run's photos and items sent once more after Meta's service failed them, a
      whole number of 0 or more) and a rerun's `rerun_reason` (C421). It needs the
      first three and `service_retries`. A development run carries none of these.
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
    counted = (
        isinstance(service_retries, int)
        and not isinstance(service_retries, bool)
        and service_retries >= 0
    )
    if sealed and not counted:
        raise ValueError(
            "a sealed run.json needs service_retries, a whole number of 0 or more"
            " (MS6E-Q6)"
        )
    sealed_only = (freeze_commit, baseline, rerun_reason, service_retries)
    if not sealed and (stops or any(value is not None for value in sealed_only)):
        raise ValueError(
            "a development run.json carries no freeze commit, baseline, stop, rerun"
            " or service_retries"
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
        manifest["service_retries"] = service_retries
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


@dataclasses.dataclass(frozen=True)
class WheelRow:
    """One wheel in one Set B crop: a row of MS2's truth.csv (its §5.9), checked.

    - `crop_id` and `wheel` (1 the leftmost) key it, and `car_id` names its car.
    - `crop_file` is the crop's bare file name in the crops folder.
    - `vehicle_type` is one of SET_B_TYPES, and `tire_code` the car's true code, as
      MS2's reader reads it; its `code` is the form MS6's loader takes.
    - `box` (x0, y0, x1, y1), MS2's half-open box of the dry wheel mask,
      `px_per_in`, G3's scale from it, and `waterline_row`, the drawn waterline's row
      at the wheel's centre, are pixels: the crop's own until scale_row scales them.
    - `true_depth_in` (G3's truth), `view` and `size_bin` (MS2's bins), and
      `rim_edge_ratio`, the dry rim mask's cross-check (MS2's C212), or None where MS2
      found no rim.
    """

    crop_id: str
    wheel: int
    car_id: str
    crop_file: str
    vehicle_type: str
    tire_code: TireCode
    box: tuple[float, float, float, float]
    px_per_in: float
    waterline_row: float
    true_depth_in: float
    view: str
    size_bin: str
    rim_edge_ratio: float | None


def parse_truth(text: str) -> list[WheelRow]:
    """MS2's Set B truth.csv, from its text: one WheelRow per row, in file order.

    A byte-order mark is dropped. Every column read must be there, and every field is
    checked: ids opaque as MS6's loader has them, the wheel 1 or 2, a bare crop file
    name, MS2's types, views and size bins, a metric radial tire code read as MS2
    reads a sidewall's, a box with x0 < x1 and y0 < y1 from 0, a positive scale,
    finite rows, a true depth from 0 to under 100 in with at most 4 decimal places,
    and a positive rim_edge_ratio or a blank. Each (crop_id, wheel) comes once, and a
    crop's rows name one crop file. A bad field raises InputError, a ValueError,
    naming the crop and the wheel, or the row when they are what is bad.
    """
    reader = csv.DictReader(io.StringIO(text.removeprefix(_BOM)))
    for column in _TRUTH_NEEDS:
        if column not in (reader.fieldnames or ()):
            raise InputError(f"truth.csv has no {column} column")
    rows: list[WheelRow] = []
    seen: set[tuple[str, int]] = set()
    files: dict[str, str] = {}
    for number, cells in enumerate(reader, start=1):
        row = _truth_row({key: cells[key] or "" for key in _TRUTH_NEEDS}, number)
        where = f"crop {row.crop_id} wheel {row.wheel}"
        if (row.crop_id, row.wheel) in seen:
            raise InputError(f"{where}: crop_id and wheel repeat an earlier row's")
        if files.setdefault(row.crop_id, row.crop_file) != row.crop_file:
            raise InputError(f"{where}: crop_file differs from the crop's first row")
        seen.add((row.crop_id, row.wheel))
        rows.append(row)
    return rows


def scale_row(row: WheelRow, factor: float) -> WheelRow:
    """`row` with its pixel values times `factor`: its box, px_per_in and
    waterline_row. `factor` is the scale blur_for_meta gives the crop, the sent width
    over the crop's, so the row's pixels become those of the image SAM saw. Inches
    and ratios stay as they are."""
    return dataclasses.replace(
        row,
        box=tuple(value * factor for value in row.box),
        px_per_in=row.px_per_in * factor,
        waterline_row=row.waterline_row * factor,
    )


def sam_wheel(row: WheelRow, wheels: Sequence[SamInstance]) -> int | None:
    """The index of the one SAM wheel whose box holds the centre of the row's true
    box, edges included, or None when none does or several do (finding 6).

    MS2's box only picks the wheel. The rim links and checks 6 and 9 then use SAM's
    box, as the pipeline does, so Set B tests the geometry the pipeline runs (C314).
    """
    x0, y0, x1, y1 = row.box
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    holding = []
    for index, wheel in enumerate(wheels):
        wx0, wy0, wx1, wy1 = box_xyxy(wheel)
        if wx0 <= cx <= wx1 and wy0 <= cy <= wy1:
            holding.append(index)
    return holding[0] if len(holding) == 1 else None


def wheel_estimates(
    row: WheelRow,
    sam: Mapping[str, SamResult],
    brightness: float,
    *,
    tuning: Tuning,
) -> dict[str, dict]:
    """The wheel's estimate in each of C314's variants, keyed in SET_B_VARIANTS'
    order, from SAM's `wheel`, `wheel rim` and `floodwater` results for its crop.

    `brightness` is the crop's quality score (check 4). sam_wheel picks the SAM wheel,
    and without one every variant is `wheel_not_found`. Its rims link by C300
    (link_rims), and each variant runs wheel_geometry with the type's tire codes and
    SAM's box, so checks 2 to 9 are the pipeline's:
    - `geometry`: the waterline step 3 finds under the SAM wheel's mask, with the
      frozen k (`tuning.rim_edge_k`). A waterline step 3 drops gives its cause.
    - `known_waterline`: the row's waterline_row as a waterline step 3 kept, with the
      frozen k (R135, M16).
    - `geometry_uncalibrated` and `known_waterline_uncalibrated`: the same, with k = 1.

    A measured variant gives `depthInPoint`, depth_inches for the true tire code from
    the reading's fit, and the reading's envelope as `depthInMin` and `depthInMax`,
    each unrounded to 4 decimal places (C327; finding 2), with a null `fail`. A point
    depth of 0 or less leaves it unmeasured as `depth_not_positive` (C306). An
    unmeasured variant gives three nulls and its cause as `fail` (MS6's loader).
    """
    wheels = sam["wheel"].instances
    index = sam_wheel(row, wheels)
    if index is None:
        return {variant: _unmeasured("wheel_not_found") for variant in SET_B_VARIANTS}
    wheel = wheels[index]
    rims = link_rims(wheels, sam["wheel rim"].instances)[index]
    water = water_mask(sam["floodwater"], wheel.mask.shape)
    found = find_waterline(wheel.mask, water, tuning)  # step 3, on SAM's wheel
    # Only y_w and the cause are read: the row's waterline, which nothing drops.
    known = Waterline(row.waterline_row, 1.0, 0.0, 0, None, None)
    k = tuning.rim_edge_k
    runs = {
        "geometry": (found, k),
        "geometry_uncalibrated": (found, 1.0),
        "known_waterline": (known, k),
        "known_waterline_uncalibrated": (known, 1.0),
    }
    return {
        variant: _estimate(
            row,
            rims,
            waterline,
            box_xyxy(wheel),
            brightness,
            dataclasses.replace(tuning, rim_edge_k=variant_k),
        )
        for variant, (waterline, variant_k) in runs.items()
    }


def known_waterline_fit(
    row: WheelRow, sam: Mapping[str, SamResult], *, tuning: Tuning
) -> RimFit | None:
    """The rim fit the known-waterline variants measure from: the SAM wheel's one
    linked rim, fitted to its points above waterline_row - T, as measure_rim fits it.

    None without one SAM wheel, one linked rim, or a fit. The Set B tool reads k's
    ratios and the axis ratios of check 9's failures from it, and draws it.
    """
    wheels = sam["wheel"].instances
    index = sam_wheel(row, wheels)
    if index is None:
        return None
    rims = link_rims(wheels, sam["wheel rim"].instances)[index]
    if len(rims) != 1:
        return None
    points = rim_points(rims[0].mask, row.waterline_row, tuning.touch_tolerance_px)
    return fit_rim(points)


def k_ratio(row: WheelRow, fit: RimFit) -> float:
    """One fit's ratio for k (G3, C310): the fitted rim's diameter at the true scale,
    2 r ÷ px_per_in, over the true code's rim size."""
    return 2 * fit.r / row.px_per_in / row.tire_code.rim_in


def k_estimate(ratios_by_car: Mapping[str, Sequence[float]]) -> float | None:
    """k: the median of each car's median ratio (C310), or None without one.

    Each car's ratios are k_ratio's, from the fit of each of its wheels whose
    `known_waterline_uncalibrated` variant measured. That variant passed check 9, so
    hubcap and whole-wheel masks give k nothing (G3). A car with none is left out.
    """
    medians = [statistics.median(ratios) for ratios in ratios_by_car.values() if ratios]
    return float(statistics.median(medians)) if medians else None


def set_b_row(
    row: WheelRow, estimates: Mapping[str, Mapping], sam_water_found: bool | None
) -> dict:
    """One set_b.jsonl row, in MS6's names (its §4.3 and C423): the row's ids, its
    true type, tire code and depth, whether SAM found any water in the crop (None
    when Meta's service failed its send and its one retry, so every estimate is
    model_error, MS6E-Q6), MS2's `view` and `size_bin` as `bins` under those names,
    and the `estimates`."""
    return {
        "crop_id": row.crop_id,
        "wheel": row.wheel,
        "car_id": row.car_id,
        "vehicle_type": row.vehicle_type,
        "tire_code": row.tire_code.code,
        "true_depth_in": row.true_depth_in,
        "sam_water_found": sam_water_found,
        "bins": {"view": row.view, "size_bin": row.size_bin},
        "estimates": {variant: dict(found) for variant, found in estimates.items()},
    }


@dataclasses.dataclass(frozen=True)
class SetDRow:
    """One wheel in one Set D photo: a row of MS2's set_d_log.csv (its §5.9), checked.

    `photo_id` is its opaque id, and `photo_file` its bare file name in the photos
    folder. `wheel` is `left` or `right` in the photo. `vehicle_type` is one of
    SET_B_TYPES, `tire_code` its true code as MS2's reader reads a sidewall's, and
    `ruler_depth_in` the depth Rene's ruler gave, the truth.
    """

    photo_id: str
    photo_file: str
    wheel: str
    vehicle_type: str
    tire_code: TireCode
    ruler_depth_in: float


def parse_set_d(text: str) -> list[SetDRow]:
    """MS2's Set D set_d_log.csv, from its text: one SetDRow per row, in file order.

    A byte-order mark is dropped, and only the columns SetDRow holds are read: the
    time, the place, the model and the notes stay out. Every field is checked: an
    opaque photo_id, as MS6's loader has its ids; a bare photo file name; the wheel
    left or right; Set B's types; a metric radial tire code; and a ruler depth from 0
    to under 100 in with at most 4 decimal places. Each (photo_id, wheel) comes once,
    and a photo's rows name one file. A bad field raises InputError naming its row
    and column, never a cell's text.
    """
    reader = csv.DictReader(io.StringIO(text.removeprefix(_BOM)))
    for column in _SET_D_NEEDS:
        if column not in (reader.fieldnames or ()):
            raise InputError(f"set_d_log.csv has no {column} column")
    rows: list[SetDRow] = []
    seen: set[tuple[str, str]] = set()
    files: dict[str, str] = {}
    for number, cells in enumerate(reader, start=1):
        where = f"set_d_log.csv row {number}"
        row = _set_d_row({key: cells[key] or "" for key in _SET_D_NEEDS}, where)
        if (row.photo_id, row.wheel) in seen:
            raise InputError(f"{where}: photo_id and wheel repeat an earlier row's")
        if files.setdefault(row.photo_id, row.photo_file) != row.photo_file:
            raise InputError(f"{where}: photo_file differs from the photo's first row")
        seen.add((row.photo_id, row.wheel))
        rows.append(row)
    return rows


def set_d_estimates(
    row: SetDRow,
    sam: Mapping[str, SamResult],
    brightness: float,
    *,
    tuning: Tuning,
) -> dict[str, dict]:
    """The wheel's estimate in each of SET_D_VARIANTS, from SAM's `wheel`, `wheel rim`
    and `floodwater` results for its photo.

    The row's wheel is SAM's leftmost or rightmost wheel, by its box's centre, as
    `row.wheel` says; with no SAM wheel, every variant is `wheel_not_found`. Then, as
    wheel_estimates' `geometry` variants: its rims link by C300, step 3 finds the
    waterline under its mask, and wheel_geometry runs with the type's tire codes and
    SAM's box, with the frozen k (`geometry`) and with k = 1
    (`geometry_uncalibrated`). Each estimate has wheel_estimates' shape.
    """
    wheels = sam["wheel"].instances
    if not wheels:
        return {variant: _unmeasured("wheel_not_found") for variant in SET_D_VARIANTS}
    centres = [(box_xyxy(wheel)[0] + box_xyxy(wheel)[2]) / 2 for wheel in wheels]
    pick = min if row.wheel == "left" else max
    index = pick(range(len(wheels)), key=centres.__getitem__)
    wheel = wheels[index]
    rims = link_rims(wheels, sam["wheel rim"].instances)[index]
    water = water_mask(sam["floodwater"], wheel.mask.shape)
    found = find_waterline(wheel.mask, water, tuning)  # step 3, on SAM's wheel
    ks = {"geometry": tuning.rim_edge_k, "geometry_uncalibrated": 1.0}
    return {
        variant: _estimate(
            row,
            rims,
            found,
            box_xyxy(wheel),
            brightness,
            dataclasses.replace(tuning, rim_edge_k=k),
        )
        for variant, k in ks.items()
    }


def set_d_row(
    row: SetDRow, estimates: Mapping[str, Mapping], sam_water_found: bool | None
) -> dict:
    """One set_d.jsonl row, in MS6's Set B names (its §4.3): the photo's id as its
    `crop_id` and, as Set D has no car id, its `car_id`; the wheel, 1 for left and 2
    for right; the true type and tire code; the ruler depth as `true_depth_in`;
    whether SAM found any water, None as set_b_row has it; and the `estimates`. Set
    D has no bins."""
    return {
        "crop_id": row.photo_id,
        "wheel": _SET_D_WHEELS[row.wheel],
        "car_id": row.photo_id,
        "vehicle_type": row.vehicle_type,
        "tire_code": row.tire_code.code,
        "true_depth_in": row.ruler_depth_in,
        "sam_water_found": sam_water_found,
        "estimates": {variant: dict(found) for variant, found in estimates.items()},
    }


def _set_d_row(cells: Mapping[str, str], where: str) -> SetDRow:
    """One set_d_log.csv row, checked as parse_set_d says. `where` names its row."""
    photo_id, photo_file = cells["photo_id"], cells["photo_file"]
    if not _ID.fullmatch(photo_id):
        raise InputError(f"{where}: photo_id must be an opaque id")
    if not _FILE_NAME.fullmatch(photo_file) or ".." in photo_file:
        raise InputError(f"{where}: photo_file must be a bare file name")
    if cells["wheel"] not in _SET_D_WHEELS:
        raise InputError(f"{where}: wheel must be left or right")
    if cells["vehicle_type"] not in SET_B_TYPES:
        allowed = ", ".join(SET_B_TYPES)
        raise InputError(f"{where}: vehicle_type must be one of {allowed}")
    code = _sidewall_code(cells["tire_code"])
    if code is None:
        raise InputError(f"{where}: tire_code isn't a metric radial code")
    text = cells["ruler_depth_in"].strip()
    try:
        depth = float(text)
    except ValueError:
        depth = math.nan
    # A finite float's text is a finite Decimal's, so its places are only read then.
    in_range = math.isfinite(depth) and 0 <= depth < _MAX_DEPTH_IN
    if not in_range or -Decimal(text).as_tuple().exponent > _DEPTH_PLACES:
        raise InputError(
            f"{where}: ruler_depth_in must be from 0 to under 100, with at most 4"
            " decimal places"
        )
    return SetDRow(
        photo_id=photo_id,
        photo_file=photo_file,
        wheel=cells["wheel"],
        vehicle_type=cells["vehicle_type"],
        tire_code=code,
        ruler_depth_in=depth,
    )


def _truth_row(cells: Mapping[str, str], number: int) -> WheelRow:
    """One truth.csv row, checked as parse_truth says. `number` counts from 1."""
    crop_id, wheel = cells["crop_id"], cells["wheel"]
    if not _ID.fullmatch(crop_id) or wheel not in _WHEELS:
        raise InputError(
            f"truth.csv row {number}: crop_id must be an opaque id, and wheel 1 or 2"
        )
    where = f"crop {crop_id} wheel {wheel}"
    for column in _TRUTH_NEEDS:
        if column != "rim_edge_ratio" and not cells[column].strip():
            raise InputError(f"{where}: no {column}")
    if not _ID.fullmatch(cells["car_id"]):
        raise InputError(f"{where}: car_id must be an opaque id")
    crop_file = cells["crop_file"]
    if not _FILE_NAME.fullmatch(crop_file) or ".." in crop_file:
        raise InputError(f"{where}: crop_file must be a bare file name")
    for column, allowed in (
        ("vehicle_type", SET_B_TYPES),
        ("view", _VIEWS),
        ("size_bin", _SIZE_BINS),
    ):
        if cells[column] not in allowed:
            raise InputError(f"{where}: {column} must be one of {', '.join(allowed)}")
    code = _sidewall_code(cells["tire_code"])
    if code is None:
        raise InputError(f"{where}: tire_code isn't a metric radial code")

    def number_in(column: str) -> float:
        try:
            value = float(cells[column])
        except ValueError:
            value = math.nan
        if not math.isfinite(value):
            raise InputError(f"{where}: {column} isn't a finite number")
        return value

    x0, y0, x1, y1 = (number_in(column) for column in ("x0", "y0", "x1", "y1"))
    if not (0 <= x0 < x1 and 0 <= y0 < y1):
        raise InputError(f"{where}: the box needs 0 <= x0 < x1 and 0 <= y0 < y1")
    px_per_in = number_in("px_per_in")
    if px_per_in <= 0:
        raise InputError(f"{where}: px_per_in must be above 0")
    depth = number_in("true_depth_in")
    places = -Decimal(cells["true_depth_in"].strip()).as_tuple().exponent
    if not 0 <= depth < _MAX_DEPTH_IN or places > _DEPTH_PLACES:
        raise InputError(
            f"{where}: true_depth_in must be from 0 to under 100, with at most 4"
            " decimal places"
        )
    ratio = None
    if cells["rim_edge_ratio"].strip():
        ratio = number_in("rim_edge_ratio")
        if ratio <= 0:
            raise InputError(f"{where}: rim_edge_ratio must be above 0, or blank")
    return WheelRow(
        crop_id=crop_id,
        wheel=int(wheel),
        car_id=cells["car_id"],
        crop_file=crop_file,
        vehicle_type=cells["vehicle_type"],
        tire_code=code,
        box=(x0, y0, x1, y1),
        px_per_in=px_per_in,
        waterline_row=number_in("waterline_row"),
        true_depth_in=depth,
        view=cells["view"],
        size_bin=cells["size_bin"],
        rim_edge_ratio=ratio,
    )


def _sidewall_code(text: str) -> TireCode | None:
    """The code as MS2's reader reads a sidewall's, written as MS6's loader takes it
    (such as 175/65R14, or 215/70R16C), or None when MS2's reader wouldn't read it."""
    found = _SIDEWALL_CODE.fullmatch(text.strip())
    if found is None:
        return None
    width, aspect, rim, van = found.groups()
    return TireCode.parse(f"{width}/{aspect}R{rim}{'C' if van else ''}")


def _estimate(
    row: WheelRow | SetDRow,
    rims: Sequence[SamInstance],
    waterline: Waterline,
    wheel_box: tuple[float, float, float, float],
    brightness: float,
    tuning: Tuning,
) -> dict[str, object]:
    """One variant's estimate: wheel_geometry at `waterline`, with tuning's k."""
    reading = wheel_geometry(
        answer_waterline=_ANSWERED,
        codes=rules.tire_codes(row.vehicle_type),
        rims=rims,
        waterline=waterline,
        wheel_box=wheel_box,
        brightness=brightness,
        tuning=tuning,
    )
    if reading == "waterline_dropped":  # only step 3's can be: name its cause
        return _unmeasured(waterline.cause)
    if isinstance(reading, str):
        return _unmeasured(reading)
    point = depth_inches(
        row.tire_code,
        centre_y=reading.fit.centre_y,
        r=reading.fit.r,
        y_w=waterline.y_w,
        k=tuning.rim_edge_k,
    )
    if point <= 0:  # C306
        return _unmeasured("depth_not_positive")
    return {
        "measured": True,
        "depthInPoint": round(point, _DEPTH_PLACES),
        "depthInMin": round(reading.depth_in_min, _DEPTH_PLACES),
        "depthInMax": round(reading.depth_in_max, _DEPTH_PLACES),
        "fail": None,
    }


def _unmeasured(cause: str) -> dict[str, object]:
    """An unmeasured estimate, in the measured one's key order."""
    return {"measured": False, **dict.fromkeys(_ESTIMATE_NUMBERS), "fail": cause}


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
