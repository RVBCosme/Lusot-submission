"""The formats of MS2's files: each log's and output's columns, the values a column may
hold, the id patterns, and the date and time formats (spec §5.9, C209, C218, C221).

Each list keeps spec §5.9's order. eval/templates holds each log's header, and the
collection guide, docs/data/set-a-collection-guide.md, explains every column to Rene.
"""

import re
from datetime import datetime

# Set A's log: the template's 17 columns, each required (§5.3).
SET_A_COLUMNS = (
    "candidate_id",
    "logged_on",
    "platform",
    "post_url",
    "poster",
    "post_time_pht",
    "alert_time_pht",
    "spot_text",
    "city",
    "level_label_raw",
    "passability_raw",
    "photo_in_alert_post",
    "photo_file",
    "reference_visible",
    "label_in_image",
    "faces_or_plates",
    "notes",
)
# C209's optional last columns, in both logs. A-neg ignores the two alert columns.
SET_A_OPTIONAL = ("same_spot_as", "alert_poster", "alert_spot_text")
# A-neg's required columns: Set A's plus surface, the log the tracker's checklist v2
# has Rene make (C209).
A_NEG_COLUMNS = SET_A_COLUMNS + ("surface",)
# Rene's M8 export, one row per labelled item (C208).
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
# The ground-truth manifest of Set A and A-neg, the same on both sides (C207).
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
# Set B: Rene's cars.csv, one row per photo, and the generator's truth.csv, one row
# per wheel per crop.
CARS_COLUMNS = (
    "car_id",
    "photo_file",
    "model",
    "vehicle_type",
    "tire_code",
    "view",
    "taken_on",
    "consent_file",
    "consent_version",
    "notes",
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
# The other logs: Set D (M13), consented items (M9) and sidewalls (M11).
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
CONSENTED_COLUMNS = (
    "item_id",
    "file",
    "kind",
    "taken_pht",
    "place_text",
    "lat",
    "lon",
    "people",
    "source_note",
    "consent_file",
    "consent_version",
    "notes",
)
SIDEWALLS_COLUMNS = (
    "photo_file",
    "vehicle",
    "model",
    "tire_code",
    "checked_code",
    "taken_on",
    "consent_file",
    "consent_version",
    "notes",
)

# Each template in eval/templates, by file name, and its header.
TEMPLATES: dict[str, tuple[str, ...]] = {
    "set_a_log.csv": SET_A_COLUMNS + SET_A_OPTIONAL,
    "a_neg_log.csv": A_NEG_COLUMNS + ("same_spot_as",),
    "m8_labels.csv": M8_COLUMNS,
    "set_b_cars.csv": CARS_COLUMNS,
    "set_d_log.csv": SET_D_COLUMNS,
    "consented_log.csv": CONSENTED_COLUMNS,
    "sidewalls.csv": SIDEWALLS_COLUMNS,
}

# The values Set A's and A-neg's columns take, as the guide and the spec give them.
PLATFORMS = ("facebook", "x", "other")
YES_NO = ("yes", "no")
REFERENCE_VISIBLE = ("wheel", "person", "both", "none")
LABEL_IN_IMAGE = ("no", "cropped", "yes")
A_NEG_POSTERS = ("own", "friend")
SURFACES = ("wet", "dry")

# Table 5's lists: photo schema v1's enums, in its order. A test compares them with
# backend/analysis/prompts/muse_spark_photo_v1.schema.json, read as data (C200).
VEHICLE_TYPES = (
    "sedan_hatch",
    "suv_mpv",
    "pickup",
    "van",
    "jeepney",
    "tricycle",
    "motorcycle",
    "bus_truck",
    "unknown",
)
BODY_WATERLINES = (
    "below_bumper",
    "bumper",
    "door_sill",
    "mid_door",
    "window",
    "not_visible",
)
WHEEL_WATERLINES = (
    "tire_only",
    "rim_quarter",
    "hub",
    "rim_three_quarters",
    "rim_top",
    "wheel_covered",
    "not_visible",
)
PERSON_WATERLINES = (
    "ankle",
    "mid_shin",
    "knee",
    "mid_thigh",
    "waist",
    "chest",
    "above_chest",
    "not_visible",
)

# M8 (C208): each row's kind, and a photo row's marks.
M8_KINDS = ("photo", "vehicle", "wheel", "person")
QUALITIES = ("ok", "dark", "blurry")
SUBSET_TAGS = ("reflection", "splash", "moving")

# Set B and the other logs.
SET_B_TYPES = ("sedan_hatch", "suv_mpv", "van")
VIEWS = ("side", "angled")
WHEEL_SIDES = ("left", "right")
ITEM_KINDS = ("photo", "clip")
SIDEWALL_VEHICLES = ("jeepney", "tricycle", "bus", "hilux", "tamaraw", "other")

# Metro Manila's 16 cities and Pateros, its one municipality, as display names.
METRO_MANILA = (
    "Caloocan",
    "Las Piñas",
    "Makati",
    "Malabon",
    "Mandaluyong",
    "Manila",
    "Marikina",
    "Muntinlupa",
    "Navotas",
    "Parañaque",
    "Pasay",
    "Pasig",
    "Pateros",
    "Quezon City",
    "San Juan",
    "Taguig",
    "Valenzuela",
)

# The consent texts' versions Rene has approved, per log (C218). A text's version joins
# its set when he approves that text; Window 4 drafts all three.
APPROVED_CONSENT: dict[str, frozenset[str]] = {
    "m9": frozenset(),
    "set_b": frozenset(),
    "m11": frozenset(),
}

# Id patterns, each inside C221's (table.ID_PATTERN), and the photo file extensions.
SET_A_ID = r"A[0-9]{3}"
A_NEG_ID = r"N[0-9]{3}"
ITEM_ID = r"S[0-9]{3}"
CAR_ID = r"B[0-9]{2}"
SET_D_ID = r"D[0-9]{2}"
PHOTO_EXTENSIONS = ("jpg", "jpeg", "png")

# strptime alone would take "2026-8-9" and "8:20", so the shape is checked first.
_DATE_SHAPE = r"[0-9]{4}-[0-9]{2}-[0-9]{2}"
_TIME_SHAPE = _DATE_SHAPE + r" [0-9]{2}:[0-9]{2}"
_DATE_FORMAT = "%Y-%m-%d"
_TIME_FORMAT = "%Y-%m-%d %H:%M"


def is_date(text: str) -> bool:
    """True for a real date written YYYY-MM-DD."""
    return _fits(text, _DATE_SHAPE, _DATE_FORMAT)


def is_time(text: str) -> bool:
    """True for a real time written YYYY-MM-DD HH:MM, on the 24-hour clock."""
    return _fits(text, _TIME_SHAPE, _TIME_FORMAT)


def parse_time(text: str) -> datetime:
    """A time is_time accepts, as a naive datetime in Manila time.

    Any other text raises ValueError, whose message never holds the text.
    """
    if not is_time(text):
        raise ValueError("not a time written YYYY-MM-DD HH:MM")
    return datetime.strptime(text, _TIME_FORMAT)


def _fits(text: str, shape: str, form: str) -> bool:
    if re.fullmatch(shape, text) is None:
        return False
    try:
        datetime.strptime(text, form)
    except ValueError:  # not a real date or time, such as Feb 30 or 24:00
        return False
    return True
