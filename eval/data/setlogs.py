"""Checks of Rene's Set A and A-neg logs, the match of each Set A photo to its alerts,
and each photo's text-only facts (spec §5.3, §5.9, C209, C223, C224).

A log has one row per alert a photo may fit, so a photo's id repeats on its alert
rows, and they repeat its photo's columns (C223). The checks read only the log's text.
The caller refuses a log or photos folder inside a folder named sealed first (C222).
A photo is looked for only once its name is the id's own, so the look stays inside the
photos folder, and it is a stat, which never reads the photo's bytes (C201). A problem
or a warning holds ids, column names and fixed words, never a cell's text.

A list value, such as yes or cropped, is read in any case and kept in lower case, since
a spreadsheet may capitalise it (Review Focus 1).
"""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import formats
import places
import table
from table import Fact, Finding

# The columns an id's rows must repeat, and A-neg's surface too. Every other column is
# each row's own: logged_on, alert_time_pht, level_label_raw, passability_raw,
# photo_in_alert_post, alert_poster, alert_spot_text and notes.
PHOTO_COLUMNS = (
    "platform",
    "post_url",
    "poster",
    "post_time_pht",
    "spot_text",
    "city",
    "photo_file",
    "reference_visible",
    "label_in_image",
    "faces_or_plates",
    "same_spot_as",
)

# A separate alert fits within 30 minutes of the photo's post, inclusive (C223).
_WINDOW = timedelta(minutes=30)
_DATES = ("logged_on",)
_TIMES = ("post_time_pht", "alert_time_pht")
# A label may not hold a ;, since other_alerts_raw puts ; between labels (S-R10).
_LABELS = ("level_label_raw", "passability_raw")
# Each list column and its values, as formats lists them. A-neg adds its own.
_LISTS = {
    "platform": formats.PLATFORMS,
    "photo_in_alert_post": formats.YES_NO,
    "reference_visible": formats.REFERENCE_VISIBLE,
    "label_in_image": formats.LABEL_IN_IMAGE,
    "faces_or_plates": formats.YES_NO,
}


@dataclass(frozen=True)
class _Rules:
    """What one set's log must hold (C209)."""

    id_pattern: str
    columns: tuple[str, ...]  # the columns the log must have
    checked: tuple[str, ...]  # the columns read, in the order they are checked
    required: tuple[str, ...]  # the values every row needs
    separate_required: tuple[str, ...]  # what a separate-post row needs as well
    lists: Mapping[str, tuple[str, ...]]
    photo_columns: tuple[str, ...]


_RULES = {
    "A": _Rules(
        id_pattern=formats.SET_A_ID,
        columns=formats.SET_A_COLUMNS,
        checked=formats.SET_A_COLUMNS + formats.SET_A_OPTIONAL,
        required=(
            "candidate_id",
            "logged_on",
            "platform",
            "post_url",
            "poster",
            "post_time_pht",
            "spot_text",
            "city",
            "photo_in_alert_post",
            "photo_file",
            "reference_visible",
            "label_in_image",
            "faces_or_plates",
        ),
        separate_required=("alert_poster", "alert_spot_text", "alert_time_pht"),
        lists=_LISTS,
        photo_columns=PHOTO_COLUMNS,
    ),
    # A-neg ignores the alert's poster and spot, and its level is always none.
    "A-neg": _Rules(
        id_pattern=formats.A_NEG_ID,
        columns=formats.A_NEG_COLUMNS,
        checked=formats.A_NEG_COLUMNS + ("same_spot_as",),
        required=(
            "candidate_id",
            "logged_on",
            "poster",
            "post_time_pht",
            "spot_text",
            "city",
            "photo_file",
            "reference_visible",
            "label_in_image",
            "faces_or_plates",
            "level_label_raw",
            "surface",
        ),
        separate_required=(),
        lists=_LISTS
        | {
            "poster": formats.A_NEG_POSTERS,
            "level_label_raw": ("none",),
            "surface": formats.SURFACES,
        },
        photo_columns=PHOTO_COLUMNS + ("surface",),
    ),
}


@dataclass
class Photo:
    """One photo of Set A or A-neg, with the facts of §5.9's manifest that its log rows
    give. Its photo columns come from its first row.

    post_time is None, and event_date blank, when post_time_pht isn't a time. That is a
    problem, so no such photo reaches the split.
    """

    photo_id: str
    set: str  # A or A-neg
    photo_file: str
    event_date: str  # the Manila date of post_time, YYYY-MM-DD
    post_time: datetime | None
    city: str
    metro_manila: str
    spot_key: str
    same_spot_as: frozenset[str]
    poster_kind: str
    match: str
    level_label_raw: str
    passability_raw: str
    other_alerts_raw: str
    label_in_image: str
    reference_visible: str
    faces_or_plates: str
    surface: str
    notes: str
    rows: int  # the photo's rows in the log


@dataclass
class SetCheck:
    """One log's check: its photos in log order, its problems and warnings, and the
    number of rows it read."""

    photos: list[Photo]
    problems: list[Finding]
    warnings: list[Fact]
    rows: int


def check_set_log(log: Path, photos_dir: Path, *, set_name: str) -> SetCheck:
    """Check one set's log, A or A-neg, and work out each photo's facts (§5.3).

    The header comes first: each missing required column, then each name the set
    doesn't know, as `log column <n>: unknown`, n counting from 1 at the left. When a
    required column is missing, those are the only problems, and no row is checked.
    Otherwise each row is checked, then each photo's rows are compared, then its links.
    A row whose id is blank or bad is named as row n, its data row number, which is
    spreadsheet row n + 1, and is checked no further. A problem found on several rows
    of a photo is listed once. A malformed CSV raises table.MalformedCsv.
    """
    rules = _RULES[set_name]
    found = table.read_table(log)
    missing = [
        Finding("log", column, "missing_column")
        for column in rules.columns
        if column not in found.columns
    ]
    # A misspelt name, such as same_spot for same_spot_as, would otherwise read as a
    # blank column in silence. It is named by its place, never by its text (S-R10).
    known = rules.columns + formats.SET_A_OPTIONAL
    unknown = [
        Finding("log", f"column {number}", "unknown")
        for number, name in enumerate(found.columns, start=1)
        if name not in known
    ]
    if missing:
        return SetCheck([], missing + unknown, [], len(found.rows))
    problems = list(unknown)
    rows_of: dict[str, list[dict[str, str]]] = {}
    for row in found.rows:
        # An optional column the log lacks reads as blank.
        cells = {column: row.get(column, "") for column in rules.checked}
        photo_id = cells["candidate_id"]
        if re.fullmatch(rules.id_pattern, photo_id) is None:
            kind = "bad_id" if photo_id else "missing"
            problems.append(Finding(f"row {row['#']}", "candidate_id", kind))
            continue
        rows_of.setdefault(photo_id, []).append(cells)
        problems += _row_problems(photo_id, cells, rules, photos_dir)
    photos = [_photo(set_name, photo_id, rows) for photo_id, rows in rows_of.items()]
    for photo_id, rows in rows_of.items():
        problems += _differences(photo_id, rows, rules)
    problems += _bad_links(photos)
    warnings = [
        fact for photo in photos for fact in _warnings(photo, rows_of[photo.photo_id])
    ]
    return SetCheck(photos, list(dict.fromkeys(problems)), warnings, len(found.rows))


def match_alerts(rows: Sequence[Mapping[str, str]]) -> tuple[str, str, str, str]:
    """(match, level_label_raw, passability_raw, other_alerts_raw) for one Set A photo's
    rows, each an alert the photo may fit (C223, C224, S-R9).

    A row fits when photo_in_alert_post is yes. Otherwise it fits when its alert_poster
    is MMDA or a Metro Manila city, its alert_spot_text and spot_text are the same spot,
    and its alert_time_pht is at most 30 minutes from post_time_pht.

    The fitting row nearest in time gives the match, same_post or separate_post, and
    its two labels as logged. A same-post row whose distance can't be measured, as one
    without alert_time_pht, counts as 0, and a tie goes to a same-post row, then to the
    earlier row. The other fitting rows' level labels that aren't blank make
    other_alerts_raw, joined by ; in log order. With no fitting row, the match is none
    and the labels are blank. A column a row lacks reads as blank.
    """
    fitting = [(number, row) for number, row in enumerate(rows) if _fits(row)]
    if not fitting:
        return "none", "", "", ""
    nearest, row = min(
        fitting,
        key=lambda item: (_distance(item[1]), not _same_post(item[1]), item[0]),
    )
    others = [
        other.get("level_label_raw", "")
        for number, other in fitting
        if number != nearest and other.get("level_label_raw", "")
    ]
    return (
        "same_post" if _same_post(row) else "separate_post",
        row.get("level_label_raw", ""),
        row.get("passability_raw", ""),
        ";".join(others),
    )


def _fits(row: Mapping[str, str]) -> bool:
    if _same_post(row):
        return True
    gap = _gap(row)
    return (
        gap is not None
        and gap <= _WINDOW
        and places.poster_kind(row.get("alert_poster", "")) in ("mmda", "city")
        and places.same_spot(
            places.spot_names(row.get("spot_text", "")),
            places.spot_names(row.get("alert_spot_text", "")),
        )
    )


def _same_post(row: Mapping[str, str]) -> bool:
    return row.get("photo_in_alert_post", "").lower() == "yes"


def _gap(row: Mapping[str, str]) -> timedelta | None:
    """The time between the alert and the photo's post, or None unless both are times."""
    post, alert = row.get("post_time_pht", ""), row.get("alert_time_pht", "")
    if formats.is_time(post) and formats.is_time(alert):
        return abs(formats.parse_time(alert) - formats.parse_time(post))
    return None


def _distance(row: Mapping[str, str]) -> timedelta:
    gap = _gap(row)
    return timedelta(0) if gap is None else gap


def _row_problems(
    photo_id: str, cells: Mapping[str, str], rules: _Rules, photos_dir: Path
) -> list[Finding]:
    """A row's problems, column by column in the template's order."""
    required = rules.required
    if cells["photo_in_alert_post"].lower() == "no":
        required += rules.separate_required
    problems = []
    for column in rules.checked:
        value = cells[column]
        if not value:
            kind = "missing" if column in required else None
        elif column == "photo_file":
            kind = _file_problem(photo_id, value, photos_dir)
        else:
            kind = _value_problem(column, value, rules.lists)
        if kind is not None:
            problems.append(Finding(photo_id, column, kind))
    return problems


def _value_problem(
    column: str, value: str, lists: Mapping[str, tuple[str, ...]]
) -> str | None:
    if column in _DATES and not formats.is_date(value):
        return "bad_date"
    if column in _TIMES and not formats.is_time(value):
        return "bad_time"
    if column in lists and value.lower() not in lists[column]:
        return "not_in_list"
    if column in _LABELS and ";" in value:
        return "semicolon"
    return None


def _file_problem(photo_id: str, name: str, photos_dir: Path) -> str | None:
    """id_file_mismatch unless the name is the id's own, <id>.<jpg|jpeg|png> in any
    case. Only then is the photo looked for, with a stat (C201)."""
    own = {f"{photo_id}.{ext}".casefold() for ext in formats.PHOTO_EXTENSIONS}
    if name.casefold() not in own:
        return "id_file_mismatch"
    if not (photos_dir / name).is_file():
        return "file_missing"
    return None


def _differences(
    photo_id: str, rows: Sequence[Mapping[str, str]], rules: _Rules
) -> list[Finding]:
    """differs for each photo column whose cells aren't alike on all the photo's rows,
    compared in lower case in a list column."""
    problems = []
    for column in rules.photo_columns:
        lower = column in rules.lists
        if len({row[column].lower() if lower else row[column] for row in rows}) > 1:
            problems.append(Finding(photo_id, column, "differs"))
    return problems


def _bad_links(photos: Sequence[Photo]) -> list[Finding]:
    """bad_link for each photo whose same_spot_as names an id that isn't a photo of the
    log from the same date."""
    dates = {photo.photo_id: photo.event_date for photo in photos}
    return [
        Finding(photo.photo_id, "same_spot_as", "bad_link")
        for photo in photos
        if any(dates.get(link) != photo.event_date for link in photo.same_spot_as)
    ]


def _photo(set_name: str, photo_id: str, rows: Sequence[Mapping[str, str]]) -> Photo:
    """The photo's facts: its match and notes from all its rows, the rest from the
    first."""
    first = rows[0]
    post = first["post_time_pht"]
    post_time = formats.parse_time(post) if formats.is_time(post) else None
    city = places.city_name(first["city"])
    if set_name == "A":
        match, level, passability, others = match_alerts(rows)
        poster_kind = places.poster_kind(first["poster"])
    else:  # A-neg has no alert, and its poster is always other (§5.9).
        match, level, passability, others = "", "none", "", ""
        poster_kind = "other"
    return Photo(
        photo_id=photo_id,
        set=set_name,
        photo_file=first["photo_file"],
        event_date="" if post_time is None else post_time.date().isoformat(),
        post_time=post_time,
        city=first["city"] if city is None else city,
        metro_manila="no" if city is None else "yes",
        spot_key=places.spot_key(places.spot_names(first["spot_text"])),
        same_spot_as=frozenset(
            link.strip() for link in first["same_spot_as"].split(";") if link.strip()
        ),
        poster_kind=poster_kind,
        match=match,
        level_label_raw=level,
        passability_raw=passability,
        other_alerts_raw=others,
        label_in_image=first["label_in_image"].lower(),
        reference_visible=first["reference_visible"].lower(),
        faces_or_plates=first["faces_or_plates"].lower(),
        surface=first.get("surface", "").lower(),
        notes=" | ".join(dict.fromkeys(row["notes"] for row in rows if row["notes"])),
        rows=len(rows),
    )


def _warnings(photo: Photo, rows: Sequence[Mapping[str, str]]) -> list[Fact]:
    """The photo's warnings. Rules §9 leaves the photo out for metro_manila=no and, in
    Set A, for poster_kind=other and match=none. Set A's others ask Rene to check his
    rows:
    - alert_poster=other: a filled alert poster counts as other, so on a separate-post
      row its alert never fits and never reaches other_alerts_raw (S-R4)
    - same_post=several: two or more same-post rows, though a post listing several
      spots has one alert for the photo's own spot (S-R10)
    - nearest=tied: another fitting alert is as near as the nearest, with a level or
      passability label that differs, so the tie-break chose the labels (S-R10)
    """
    warnings = []
    if photo.metro_manila == "no":
        warnings.append(Fact(photo.photo_id, "metro_manila", "no"))
    if photo.set == "A":
        if photo.poster_kind == "other":
            warnings.append(Fact(photo.photo_id, "poster_kind", "other"))
        if any(
            row["alert_poster"] and places.poster_kind(row["alert_poster"]) == "other"
            for row in rows
        ):
            warnings.append(Fact(photo.photo_id, "alert_poster", "other"))
        if sum(_same_post(row) for row in rows) >= 2:
            warnings.append(Fact(photo.photo_id, "same_post", "several"))
        if _tied(rows):
            warnings.append(Fact(photo.photo_id, "nearest", "tied"))
        if photo.match == "none":
            warnings.append(Fact(photo.photo_id, "match", "none"))
    return warnings


def _tied(rows: Sequence[Mapping[str, str]]) -> bool:
    """True when the fitting rows nearest in time don't all give the same level and
    passability labels."""
    fitting = [row for row in rows if _fits(row)]
    if not fitting:
        return False
    nearest = min(_distance(row) for row in fitting)
    labels = {
        (row.get("level_label_raw", ""), row.get("passability_raw", ""))
        for row in fitting
        if _distance(row) == nearest
    }
    return len(labels) > 1
