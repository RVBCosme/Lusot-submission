"""Tests for the overlay, its layers and the readings (MS4 Task 14; C505, C507, C524).

All three come from MS3b's evidence record alone (C328), which run_pipeline builds
from the shared fixtures with FakeClient, so no Meta call is made. A test that needs a
record the fixtures can't give edits an entry of a real one with dataclasses.replace.
Each run that pins a start-value number passes START (R128).
"""

import dataclasses
import json
import math
import re

import cv2
import numpy as np
import pytest
from fakes import (
    REPO_PROMPTS,
    FakeClient,
    answer,
    geometry_case,
    instance,
    level_case,
    person,
    vehicle,
    wheel,
)

from lusot_analysis import overlay, rules
from lusot_analysis.face_blur import blur_for_meta, decode_image
from lusot_analysis.meta_client import SamResult
from lusot_analysis.pipeline import run_pipeline
from lusot_analysis.pipeline.evidence import Evidence, EvidenceEntry
from lusot_analysis.pipeline.publish import publish_jpeg
from lusot_analysis.prompts import load_prompt
from lusot_analysis.tuning import START

FACE = (300, 120, 330, 150)  # level_case's face and plate boxes
PLATE = (220, 270, 280, 290)
DRY_PERSON = (450, 50, 480, 200)  # as test_evidence.py's: step 3 drops this one
WET_PERSON = (520, 150, 560, 280)
# S13's copy patterns, case-insensitive. Nothing the overlay says may match one.
COPY_PATTERNS = (
    r"safe",
    r"ligtas",
    r"\bcross",
    r"tawid",
    r"\b(roads?|streets?|routes?|kalsada|daan)\b",
)
SIZE = (640, 480)  # width, height


@pytest.fixture(scope="module")
def prompt():
    return load_prompt(REPO_PROMPTS)


def record(prompt, case, *, geometry: bool = False) -> Evidence:
    """The evidence record run_pipeline builds for `case`."""
    photo, sam, given = case
    client = FakeClient(sam, given)
    run = run_pipeline(photo, client, prompt, geometry_in_level=geometry, tuning=START)
    assert run.evidence is not None
    return run.evidence


@pytest.fixture(scope="module")
def level_record(prompt) -> Evidence:
    return record(prompt, level_case())


@pytest.fixture(scope="module")
def geometry_record(prompt) -> Evidence:
    return record(prompt, geometry_case(), geometry=True)


@pytest.fixture(scope="module")
def g4_record(prompt) -> Evidence:
    """A wheel geometry measured and then dropped (G4), whose entry still holds inches."""
    return record(prompt, geometry_case(waterline="rim_three_quarters"), geometry=True)


@pytest.fixture(scope="module")
def people_record(prompt) -> Evidence:
    """The level case with two people: 3, dry, whom step 3 drops, and 4, wading."""
    photo, sam, _ = level_case()
    people = [instance(0, DRY_PERSON), instance(1, WET_PERSON)]
    sam = sam | {"person": SamResult("person", people, elapsed_s=0.5, raw="")}
    given = answer(
        vehicles=[vehicle(1)],
        wheels=[wheel(2, "rim_three_quarters")],
        people=[person(3, "knee"), person(4, "knee", standing_still="no")],
    )
    return record(prompt, (photo, sam, given))


@pytest.fixture(scope="module")
def floor_record(prompt) -> Evidence:
    """Vehicle 1 read at its window and wheel 2 covered: two tire floors (C54)."""
    photo, sam, _ = geometry_case()
    given = answer(
        vehicles=[vehicle(1, body="window")], wheels=[wheel(2, "wheel_covered")]
    )
    return record(prompt, (photo, sam, given))


def swapped(evidence: Evidence, id: int, **changes) -> Evidence:
    """`evidence` with entry `id` changed."""
    return dataclasses.replace(
        evidence,
        references=tuple(
            dataclasses.replace(entry, **changes) if entry.id == id else entry
            for entry in evidence.references
        ),
    )


def entry_of(evidence: Evidence, id: int) -> EvidenceEntry:
    (found,) = (entry for entry in evidence.references if entry.id == id)
    return found


def labels_of(evidence: Evidence) -> dict[int, str]:
    return {entry.id: overlay.label(entry) for entry in evidence.references}


def stored_photo() -> np.ndarray:
    """level_case()'s stored photo, as draw_overlay decodes it."""
    photo, sam, _ = level_case()
    return decode_image(publish_jpeg(blur_for_meta(photo), sam))


def numbers(value):
    """Every number in a layers value, which holds lists, dicts and plain scalars."""
    if isinstance(value, dict):
        for item in value.values():
            yield from numbers(item)
    elif isinstance(value, list):
        for item in value:
            yield from numbers(item)
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        yield value


def luminance(colour: tuple[int, int, int]) -> float:
    """WCAG's relative luminance of a BGR colour."""

    def linear(channel: int) -> float:
        share = channel / 255
        return share / 12.92 if share <= 0.04045 else ((share + 0.055) / 1.055) ** 2.4

    b, g, r = colour
    return 0.2126 * linear(r) + 0.7152 * linear(g) + 0.0722 * linear(b)


def contrast(one: tuple[int, int, int], other: tuple[int, int, int]) -> float:
    """WCAG's contrast ratio of two BGR colours."""
    high, low = sorted((luminance(one), luminance(other)), reverse=True)
    return (high + 0.05) / (low + 0.05)


# The layers (C524)


def test_layers_follow_c524(level_record):
    layers = overlay.layers(level_record, SIZE)
    assert list(layers) == ["version", "width", "height", "water", "refs"]
    assert (layers["version"], layers["width"], layers["height"]) == (1, 640, 480)
    (water,) = layers["water"]
    assert {tuple(point) for point in water} == {
        (0, 280),
        (639, 280),
        (639, 479),
        (0, 479),
    }
    assert [ref["id"] for ref in layers["refs"]] == [1, 2]
    for ref in layers["refs"]:
        assert list(ref) == [
            "id",
            "kind",
            "box",
            "outline",
            "rim_outline",
            "landmark",
            "level",
            "level_from",
            "level_is_floor",
            "used",
            "dropped",
            "rechecked",
            "rim",
            "waterline",
        ]
    body, wheel_ref = layers["refs"]
    # The vehicle: no rim or rim outline, no waterline, and no reading.
    assert (body["kind"], body["box"], body["landmark"]) == (
        "body",
        [100, 100, 400, 300],
        "not_visible",
    )
    assert (body["rim_outline"], body["rim"], body["waterline"]) == (None, None, None)
    assert (body["level"], body["level_from"], body["used"]) == (None, None, False)
    # Wheel 2: knee from its landmark, with the waterline the record holds.
    assert (wheel_ref["kind"], wheel_ref["box"]) == ("wheel", [150, 250, 200, 300])
    assert (wheel_ref["landmark"], wheel_ref["level"]) == ("rim_three_quarters", "knee")
    assert wheel_ref["level_from"] == "landmark"
    assert (wheel_ref["used"], wheel_ref["dropped"], wheel_ref["rechecked"]) == (
        True,
        None,
        False,
    )
    assert (wheel_ref["rim_outline"], wheel_ref["rim"]) == (None, None)
    assert wheel_ref["waterline"] == [[150, 280], [199, 280]]
    # Whole pixels, as plain ints, in plain lists: the file is JSON.
    assert all(type(value) is int for value in numbers(layers))
    assert json.loads(json.dumps(layers)) == layers


def test_layers_for_a_geometry_wheel(geometry_record):
    layers = overlay.layers(geometry_record, SIZE)
    entry = entry_of(geometry_record, 2)
    wheel_ref = layers["refs"][1]
    assert (wheel_ref["level"], wheel_ref["level_from"]) == ("half_knee", "geometry")
    # The fit, as cv2.fitEllipse gave it, rounded to 0.1.
    assert list(wheel_ref["rim"]) == ["center", "axes", "angle"]
    assert wheel_ref["rim"] == {
        "center": [round(v, 1) for v in entry.rim.centre],
        "axes": [round(v, 1) for v in entry.rim.axes],
        "angle": round(entry.rim.angle_deg, 1),
    }
    assert all(
        math.isclose(v * 10, round(v * 10), abs_tol=1e-6)
        for v in numbers(wheel_ref["rim"])
    )
    # The linked rim's mask, as polygons of whole pixels.
    (rim_polygon,) = wheel_ref["rim_outline"]
    assert len(rim_polygon) >= 8
    assert all(type(v) is int for point in rim_polygon for v in point)
    # Two points at the same height, from the first touching column to the last.
    first, last = wheel_ref["waterline"]
    assert first[1] == last[1] and first[0] < last[0]
    assert wheel_ref["waterline"] == [[round(x), round(y)] for x, y in entry.waterline]


def test_no_inches_anywhere(g4_record, geometry_record):
    # S12. The dropped wheel's record holds inches, and so does a geometry level's.
    assert entry_of(g4_record, 2).inches is not None
    assert entry_of(g4_record, 2).dropped == "wheel_methods_disagree"
    assert entry_of(geometry_record, 2).inches is not None
    for evidence in (g4_record, geometry_record):
        dumped = json.dumps(overlay.layers(evidence, SIZE)).lower()
        assert "inches" not in dumped and "depthin" not in dumped
        for entry in evidence.references:
            text = overlay.label(entry)
            assert not re.search(r"\d\s*(in\b|inch|\")", text, re.IGNORECASE), text
            # The only digits a label holds are its box number.
            assert not re.search(r"\d", text[len(str(entry.id)) :]), text


def test_no_face_or_plate_in_the_layers(level_record):
    layers = overlay.layers(level_record, SIZE)
    assert [ref["id"] for ref in layers["refs"]] == [1, 2]
    boxes = {tuple(ref["box"]) for ref in layers["refs"]}
    assert FACE not in boxes and PLATE not in boxes
    # A face or a plate can't slip in: any kind but the three raises.
    for kind in ("face", "license plate", "vehicle"):
        faced = Evidence(
            (
                *level_record.references,
                dataclasses.replace(level_record.references[0], id=3, kind=kind),
            ),
            level_record.water_outline,
        )
        with pytest.raises(ValueError):
            overlay.layers(faced, SIZE)


def test_repeated_id_raises(level_record):
    # MS3b's record has one entry per box (R147), so a repeat is a guard, not a dedupe.
    twice = Evidence(
        (*level_record.references, level_record.references[1]),
        level_record.water_outline,
    )
    with pytest.raises(ValueError):
        overlay.layers(twice, SIZE)
    with pytest.raises(ValueError):
        overlay.readings(twice)


# The words (S13)


def test_labels(level_record, geometry_record, people_record):
    body, landmark_wheel = level_record.references
    # A landmark reading names the category and the level.
    assert overlay.label(landmark_wheel) == "2 rim three-quarters: Knee deep"
    # A geometry reading names the level alone.
    assert overlay.label(entry_of(geometry_record, 2)) == "2 Half-knee deep"
    # Unread: the landmark, or just the number without one.
    assert overlay.label(body) == "1 not visible"
    assert overlay.label(dataclasses.replace(body, landmark=None)) == "1"
    # Dropped: the landmark, never the level the record kept (C317).
    dry = entry_of(people_record, 3)
    assert (dry.level, dry.dropped) == ("knee", "no_water_contact")
    assert overlay.label(dry) == "3 knee"
    wading = entry_of(people_record, 4)
    assert overlay.label(wading) == "4 knee"
    assert overlay.label(dataclasses.replace(dry, dropped=None)) == "3 knee: Knee deep"
    assert overlay.label(dataclasses.replace(dry, dropped=None, landmark=None)) == (
        "3 Knee deep"
    )


def test_words_follow_the_copy_rules():
    # S13. The 9 levels, every category, and nothing that reads as advice.
    assert set(overlay.LEVEL_WORDS) == set(rules.LEVELS)
    categories = set(rules.WHEEL_ROWS) | set(rules.PEOPLE_ROWS) | set(rules.BODY_ROWS)
    assert set(overlay.LANDMARK_WORDS) == categories
    words = [*overlay.LEVEL_WORDS.values(), *overlay.LANDMARK_WORDS.values()]
    for word in words:
        assert word.isascii() and not re.search(r"\d", word), word
        for pattern in COPY_PATTERNS:
            assert not re.search(pattern, word, re.IGNORECASE), (pattern, word)
    # No two levels read alike.
    assert len(set(overlay.LEVEL_WORDS.values())) == len(rules.LEVELS)
    # A floor's words (C54) follow the same rules, for every level. FLOOR_WORDS is a
    # placeholder until Rene's M20 review, so this holds whatever he writes.
    assert overlay.FLOOR_WORDS.count("{level}") == 1
    for level in overlay.LEVEL_WORDS.values():
        floor = overlay.FLOOR_WORDS.format(level=level)
        assert floor.isascii() and not re.search(r"\d", floor), floor
        for pattern in COPY_PATTERNS:
            assert not re.search(pattern, floor, re.IGNORECASE), (pattern, floor)


def test_a_floor_reading_says_so(
    floor_record, level_record, geometry_record, people_record
):
    # C54, the final review's I1: a floor is "this level or deeper", so its label, its
    # layer and its reading say so. The flag is the entry's own, never the landmark's.
    body, covered = floor_record.references
    assert (body.landmark, body.level, body.level_is_floor) == ("window", "tire", True)
    assert (covered.landmark, covered.level_is_floor) == ("wheel_covered", True)
    layers = overlay.layers(floor_record, SIZE)
    assert [ref["level_is_floor"] for ref in layers["refs"]] == [True, True]
    assert [r["levelIsFloor"] for r in overlay.readings(floor_record)] == [True, True]
    tire = overlay.LEVEL_WORDS["tire"]
    floor = overlay.FLOOR_WORDS.format(level=tire)
    assert floor != tire
    assert overlay.label(body) == f"1 window: {floor}"
    assert overlay.label(covered) == f"2 wheel covered: {floor}"
    assert json.loads(json.dumps(layers)) == layers
    # An exact landmark reading and a geometry reading are not floors, and read as before.
    for evidence, id, text in (
        (level_record, 2, "2 rim three-quarters: Knee deep"),
        (geometry_record, 2, "2 Half-knee deep"),
    ):
        ref = next(r for r in overlay.layers(evidence, SIZE)["refs"] if r["id"] == id)
        found = next(r for r in overlay.readings(evidence) if r["id"] == id)
        assert (ref["level_is_floor"], found["levelIsFloor"]) == (False, False)
        assert overlay.label(entry_of(evidence, id)) == text
    # The flag is the entry's, not derived from the landmark: it moves the words alone.
    exact = entry_of(level_record, 2)
    assert exact.level_is_floor is False
    assert overlay.label(dataclasses.replace(exact, level_is_floor=True)) == (
        f"2 rim three-quarters: {overlay.FLOOR_WORDS.format(level='Knee deep')}"
    )
    assert overlay.label(dataclasses.replace(covered, level_is_floor=False)) == (
        f"2 wheel covered: {tire}"
    )
    # No reading: null with the level it goes with, and the label is as before.
    unread = entry_of(level_record, 1)
    assert (unread.level, unread.level_is_floor) == (None, False)
    ref, found = (
        overlay.layers(level_record, SIZE)["refs"][0],
        overlay.readings(level_record)[0],
    )
    assert (ref["level_is_floor"], found["levelIsFloor"]) == (None, None)
    assert overlay.label(unread) == "1 not visible"
    # A dropped entry shows no level, so no flag, even when the record kept one.
    dry = entry_of(people_record, 3)
    assert (dry.level, dry.dropped) == ("knee", "no_water_contact")
    for flag in (dry.level_is_floor, True):
        evidence = swapped(people_record, 3, level_is_floor=flag)
        ref = next(r for r in overlay.layers(evidence, SIZE)["refs"] if r["id"] == 3)
        found = next(r for r in overlay.readings(evidence) if r["id"] == 3)
        assert (ref["level_is_floor"], found["levelIsFloor"]) == (None, None)
        assert overlay.label(entry_of(evidence, 3)) == "3 knee"


# The readings (C507)


def test_readings_come_from_the_record_alone(level_record, geometry_record):
    # S16.
    assert overlay.readings(level_record) == [
        {
            "id": 1,
            "kind": "body",
            "landmark": "not_visible",
            "level": None,
            "levelIsFloor": None,
            "inches": None,
            "used": False,
            "dropped": None,
        },
        {
            "id": 2,
            "kind": "wheel",
            "landmark": "rim_three_quarters",
            "level": "knee",
            "levelIsFloor": False,
            "inches": None,
            "used": True,
            "dropped": None,
        },
    ]
    # Not a pinned pair: MS3b's values follow the live tuning.
    entry = entry_of(geometry_record, 2)
    found = overlay.readings(geometry_record)[1]
    assert found["inches"] == list(rules.round_out(*entry.inches))
    assert (found["level"], found["used"], found["dropped"]) == (
        "half_knee",
        True,
        None,
    )
    # A record whose inches aren't finite raises, whichever entry holds them.
    for bad in (
        (math.nan, math.nan),
        (7.7, math.inf),
        (-math.inf, 8.2),
        (math.nan, 8.2),
    ):
        with pytest.raises(ValueError):
            overlay.readings(swapped(geometry_record, 2, inches=bad))
        with pytest.raises(ValueError):
            overlay.readings(swapped(geometry_record, 1, inches=bad))


def test_inches_only_on_the_deciding_reading(geometry_record, g4_record):
    measured = (7.720028616892439, 8.18417225696873)
    deciding = entry_of(geometry_record, 2)
    assert (deciding.deciding, deciding.level_from) == (True, "geometry")
    # The deciding geometry wheel reads its rounded pair.
    assert overlay.readings(geometry_record)[1]["inches"] == list(
        rules.round_out(*deciding.inches)
    )

    def inches_of(evidence: Evidence, id: int = 2):
        (found,) = (r for r in overlay.readings(evidence) if r["id"] == id)
        return found["inches"]

    # A dropped wheel (G4's drop) holds inches in the record, and reads none.
    assert entry_of(g4_record, 2).inches is not None
    assert inches_of(g4_record) is None
    # A wheel that doesn't decide, with its level from its landmark.
    assert (
        inches_of(
            swapped(
                geometry_record,
                2,
                deciding=False,
                level_from="landmark",
                inches=measured,
            )
        )
        is None
    )
    # One geometry measured that doesn't decide.
    assert inches_of(swapped(geometry_record, 2, deciding=False)) is None
    # A folded box (R147) whose deciding reading was a tire floor: geometry set its
    # inches, but its level came from its landmark.
    assert inches_of(swapped(geometry_record, 2, level_from="landmark")) is None
    # A dropped wheel keeps its cause and no level, even with a level in the record.
    dropped = swapped(geometry_record, 2, dropped="no_water_contact")
    (found,) = (r for r in overlay.readings(dropped) if r["id"] == 2)
    assert (found["level"], found["inches"], found["dropped"]) == (
        None,
        None,
        "no_water_contact",
    )


def test_dropped_references_are_dimmed_and_carry_no_level(people_record):
    dry = entry_of(people_record, 3)
    assert (dry.level, dry.level_from, dry.dropped) == (
        "knee",
        "landmark",
        "no_water_contact",
    )
    # Its label, its layer and its reading hold no level.
    assert "Knee deep" not in overlay.label(dry)
    ref = overlay.layers(people_record, SIZE)["refs"][2]
    assert (ref["id"], ref["level"], ref["level_from"]) == (3, None, None)
    assert ref["dropped"] == "no_water_contact" and ref["landmark"] == "knee"
    (reading,) = (r for r in overlay.readings(people_record) if r["id"] == 3)
    assert (reading["level"], reading["inches"], reading["dropped"]) == (
        None,
        None,
        "no_water_contact",
    )
    # Its marks change the base by under half as much as the same reference undropped,
    # with a waterline and a rechecked box added so every mark counts.
    marked = dataclasses.replace(
        dry, waterline=((455.0, 190.0), (475.0, 190.0)), rechecked=True
    )
    base = np.full((480, 640, 3), 128, np.uint8)

    def change(entry: EvidenceEntry) -> int:
        evidence = Evidence((entry,), ())
        layers = overlay.layers(evidence, SIZE)
        drawn = overlay.render(base, layers, labels_of(evidence))
        return int(np.abs(drawn.astype(int) - base).sum())

    undropped = change(dataclasses.replace(marked, dropped=None))
    assert undropped > 0
    assert change(marked) < undropped / 2


# The drawing (C505, C524)


@pytest.mark.parametrize("which", ["level", "geometry", "people"])
def test_overlay_changes_only_its_marks(
    level_record, geometry_record, people_record, which
):
    # Critical 1. The marks are the pixels where render on all-0 or on all-255 differs
    # from its input. Off them, the render must equal the stored photo.
    evidence = {
        "level": level_record,
        "geometry": geometry_record,
        "people": people_record,
    }[which]
    layers = overlay.layers(evidence, SIZE)
    labels = labels_of(evidence)
    base = stored_photo()
    marks = np.zeros(SIZE[::-1], bool)
    for value in (0, 255):
        flat = np.full_like(base, value)
        marks |= (overlay.render(flat, layers, labels) != flat).any(axis=2)
    assert 0 < marks.mean() < 0.2  # it drew something, and not everything
    drawn = overlay.render(base, layers, labels)
    assert (drawn[~marks] == base[~marks]).all()
    assert (drawn[marks] != base[marks]).any()
    assert drawn.shape == base.shape and base is not drawn


def test_the_plate_stays_blurred(level_record):
    # The overlay draws on the stored photo, whose plate SAM blurred, never on the
    # image Meta saw. Off its marks, the plate's box stays as flat as the blur left it:
    # a JPEG round trip alone moves nearly every pixel, so it is compared with the
    # original photo, which holds noise there.
    original = decode_image(level_case()[0])
    base = stored_photo()
    layers = overlay.layers(level_record, SIZE)
    labels = labels_of(level_record)
    marks = np.zeros(SIZE[::-1], bool)
    for value in (0, 255):
        flat = np.full_like(base, value)
        marks |= (overlay.render(flat, layers, labels) != flat).any(axis=2)
    x0, y0, x1, y1 = PLATE
    window = (slice(y0, y1), slice(x0, x1))
    drawn = overlay.render(base, layers, labels)
    kept = ~marks[window]
    assert kept.sum() > 100  # most of the plate's box is off the marks
    before = original[window].std()
    assert before > 40  # the original holds noise there
    assert drawn[window][kept].std() <= before / 2
    assert base[window].std() <= before / 2  # and so did the blur


def test_overlay_jpeg_is_the_rendered_array(level_record):
    photo, sam, _ = level_case()
    stored = publish_jpeg(blur_for_meta(photo), sam)
    data, layers = overlay.draw_overlay(stored, level_record)
    assert layers == overlay.layers(level_record, SIZE)
    drawn = overlay.render(decode_image(stored), layers, labels_of(level_record))
    ok, expected = cv2.imencode(".jpg", drawn, [cv2.IMWRITE_JPEG_QUALITY, 90])
    assert ok and overlay.OVERLAY_JPEG_QUALITY == 90
    assert data == expected.tobytes()
    assert decode_image(data).shape[:2] == (480, 640)


def test_waterline_only_from_the_record(level_record):
    flat = np.full((480, 640, 3), 128, np.uint8)
    layers = overlay.layers(level_record, SIZE)
    # Wheel 2 holds a waterline: drawing it changes pixels along it, and only there.
    without = json.loads(json.dumps(layers))
    without["refs"][1]["waterline"] = None
    with_line = overlay.render(flat, layers, {})
    no_line = overlay.render(flat, without, {})
    changed = (with_line != no_line).any(axis=2)
    ys, xs = np.nonzero(changed)
    assert changed.any()
    assert 280 - 12 <= ys.min() and ys.max() <= 280 + 12
    assert 150 - 12 <= xs.min() and xs.max() <= 199 + 12
    # The vehicle holds none: alone, it draws nothing outside its box's edge.
    alone = {**layers, "water": [], "refs": [layers["refs"][0]]}
    drawn = overlay.render(flat, alone, {})
    marks = (drawn != flat).any(axis=2)
    inner = np.zeros_like(marks)
    inner[100 + 8 : 300 - 8, 100 + 8 : 400 - 8] = True
    outer = np.ones_like(marks)
    outer[100 - 8 : 300 + 8, 100 - 8 : 400 + 8] = False
    assert marks.any() and not (marks & (inner | outer)).any()


def test_rechecked_wheel_is_marked(level_record):
    flat = np.full((480, 640, 3), 128, np.uint8)
    plain = overlay.layers(level_record, SIZE)
    marked = json.loads(json.dumps(plain))
    marked["refs"][1]["rechecked"] = True
    x0, y0, x1, y1 = plain["refs"][1]["box"]
    inside = (slice(y0, y1), slice(x0, x1))
    one = overlay.render(flat, plain, {})
    other = overlay.render(flat, marked, {})
    assert (one[inside] != other[inside]).any()
    # The mark is inside the wheel's box: nothing outside it changes.
    changed = (one != other).any(axis=2)
    changed[inside] = False
    assert not changed.any()


@pytest.mark.parametrize("name", sorted(overlay.MARKS))
def test_marks_carry_a_halo_for_light_and_dark_photos(name):
    colour, halo = overlay.MARKS[name]
    assert contrast(colour, halo) >= 4.5
    # On a photo as bright as 245 the halo carries the mark, and on one as dark as 10
    # the colour does.
    assert contrast(halo, (245, 245, 245)) >= 4.5
    assert contrast(colour, (10, 10, 10)) >= 4.5


@pytest.mark.parametrize("photo", [245, 10])
def test_the_box_shows_its_colour_and_halo_on_flat_photos(level_record, photo):
    colour, halo = overlay.MARKS["box"]
    flat = np.full((480, 640, 3), photo, np.uint8)
    layers = overlay.layers(level_record, SIZE)
    drawn = overlay.render(flat, layers, {})
    x0, y0, x1, y1 = layers["refs"][1]["box"]
    near = drawn[y0 - 6 : y1 + 6, x0 - 6 : x1 + 6]
    assert (near == colour).all(axis=2).any()
    assert (near == halo).all(axis=2).any()
    # Both differ from the photo, so each can be told apart from it.
    assert colour != (photo,) * 3 and halo != (photo,) * 3


def test_labels_are_drawn_where_asked(level_record):
    flat = np.full((480, 640, 3), 128, np.uint8)
    layers = overlay.layers(level_record, SIZE)
    with_labels = overlay.render(flat, layers, labels_of(level_record))
    without = overlay.render(flat, layers, {})
    assert (with_labels != without).any()
    # A label sits against its box, above it when there is room.
    only_one = overlay.render(flat, layers, {2: "2 rim three-quarters: Knee deep"})
    changed = (only_one != without).any(axis=2)
    ys, xs = np.nonzero(changed)
    assert ys.max() <= 250 and 0 <= xs.min() and xs.max() < 640

    # A label never runs off the photo: at the far right it moves left to fit.
    def span(x0: int) -> tuple[int, int]:
        box = {**layers["refs"][1], "box": [x0, 100, x0 + 40, 140]}
        alone = {**layers, "water": [], "refs": [box]}
        added = overlay.render(flat, alone, {2: text}) != overlay.render(
            flat, alone, {}
        )
        xs = np.nonzero(added.any(axis=2).any(axis=0))[0]
        return int(xs.min()), int(xs.max())

    text = "2 rim three-quarters: Knee deep"
    left, right = span(0), span(600)
    assert left[0] == 0
    assert right[1] == 639 and right[1] - right[0] == left[1] - left[0]
