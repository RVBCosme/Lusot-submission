"""Tests for the evidence record MS4 draws its overlay from (C328; MS4's C518).

run_pipeline builds it from what steps 3 to 6 already hold, for every numbered box.
Every run here is driven by FakeClient, so no Meta call is made, and each one that
pins a start-value number passes START (R128).
"""

import json
import math
from collections.abc import Iterator

import numpy as np
import pytest
from fakes import (
    REPO_PROMPTS,
    FakeClient,
    answer,
    around,
    flat_jpeg,
    geometry_case,
    instance,
    level_case,
    meta_error,
    person,
    vehicle,
    wheel,
)

from lusot_analysis.meta_client import SamResult
from lusot_analysis.pipeline import PipelineRun, run_pipeline
from lusot_analysis.pipeline.evidence import EvidenceEntry, Polygon, outline
from lusot_analysis.pipeline.types import Outcome
from lusot_analysis.pipeline.waterline import find_waterline
from lusot_analysis.prompts import load_prompt
from lusot_analysis.tuning import START

REASON = "REASON-MARKER-31"  # the reason fakes.answer gives every answer
FACE = (300, 120, 330, 150)  # level_case's face and plate boxes
PLATE = (220, 270, 280, 290)
# A person whose lowest row is 199. The level case's water starts at row 280, so none
# comes within 5 px of it (C301). The second person's lowest row, 279, touches it.
DRY_PERSON = (450, 50, 480, 200)
WET_PERSON = (520, 150, 560, 280)


@pytest.fixture(scope="module")
def prompt():
    return load_prompt(REPO_PROMPTS)


def entries(run: PipelineRun) -> dict[int, EvidenceEntry]:
    """The record's entries by box id, which come in id order."""
    assert run.evidence is not None
    ids = [entry.id for entry in run.evidence.references]
    assert ids == sorted(ids)
    return {entry.id: entry for entry in run.evidence.references}


def with_people(
    sam: dict[str, SamResult], *boxes: tuple[float, float, float, float]
) -> dict[str, SamResult]:
    """`sam` with a person for each box, numbered after the level case's two boxes."""
    people = [instance(i, box) for i, box in enumerate(boxes)]
    return sam | {"person": SamResult("person", people, elapsed_s=0.5, raw="")}


def edge_distance(points: Polygon, mask: np.ndarray) -> float:
    """The largest distance from a point to the mask's edge pixels.

    An edge pixel is a mask pixel with one of its 4 neighbours outside the mask.
    """
    padded = np.pad(mask, 1)
    inner = padded[:-2, 1:-1] & padded[2:, 1:-1] & padded[1:-1, :-2] & padded[1:-1, 2:]
    ys, xs = np.nonzero(mask & ~inner)
    return max(float(np.min(np.hypot(xs - x, ys - y))) for x, y in points)


def polygons(run: PipelineRun) -> Iterator[Polygon]:
    """Every polygon the record holds: outlines, rim outlines and the water's."""
    assert run.evidence is not None
    for entry in run.evidence.references:
        yield from entry.outline
        yield from entry.rim_outline
    yield from run.evidence.water_outline


def inside(points: Polygon, box: tuple[int, int, int, int]) -> bool:
    """True when every point lies in `box`, edges included."""
    x0, y0, x1, y1 = box
    return all(x0 <= x <= x1 and y0 <= y <= y1 for x, y in points)


def test_outline_of_simple_masks():
    rectangle = np.zeros((480, 640), bool)
    rectangle[10:30, 20:60] = True  # rows 10 to 29, columns 20 to 59
    (polygon,) = outline(rectangle)
    assert set(polygon) == {(20, 10), (59, 10), (59, 29), (20, 29)}
    assert len(polygon) == 4
    ys, xs = np.mgrid[0:480, 0:640]
    disk = (xs - 320) ** 2 + (ys - 240) ** 2 <= 35**2
    (polygon,) = outline(disk)
    assert len(polygon) >= 8
    assert all(33.5 <= math.hypot(x - 320, y - 240) <= 35.5 for x, y in polygon)
    assert all(type(v) is int for point in polygon for v in point)  # plain ints
    assert outline(np.zeros((480, 640), bool)) == ()
    # A contour of 1 or 2 points, a dot or a 1 px line, is left out.
    rectangle[100, 100] = True
    rectangle[200, 300:340] = True
    (polygon,) = outline(rectangle)
    assert set(polygon) == {(20, 10), (59, 10), (59, 29), (20, 29)}


def test_evidence_for_a_geometry_result(prompt):
    photo, sam, given = geometry_case()
    run = run_pipeline(
        photo, FakeClient(sam, given), prompt, geometry_in_level=True, tuning=START
    )
    assert run.outcome.level_from == "geometry"
    found = entries(run)
    assert set(found) == {1, 2}
    body, wheel_entry = found[1], found[2]
    assert (body.kind, body.landmark, body.level, body.level_from) == (
        "body",
        "not_visible",
        None,
        None,
    )
    assert (body.used, body.deciding, body.dropped) == (False, False, None)
    assert (body.inches, body.rim, body.rim_outline) == (None, None, ())
    assert (wheel_entry.kind, wheel_entry.landmark) == ("wheel", "rim_quarter")
    assert (wheel_entry.level, wheel_entry.level_from) == ("half_knee", "geometry")
    low, high = wheel_entry.inches
    assert low == pytest.approx(7.720, abs=0.02)
    assert high == pytest.approx(8.184, abs=0.02)
    assert wheel_entry.rim.centre == pytest.approx((320.0, 239.6), abs=0.5)
    assert (wheel_entry.used, wheel_entry.deciding) == (True, True)
    assert (wheel_entry.dropped, wheel_entry.rechecked) == (None, False)
    # The waterline is step 3's y_w, from its first to its last touching column.
    wheel_mask = sam["wheel"].instances[0].mask
    water = sam["floodwater"].instances[0].mask
    x0, x1 = find_waterline(wheel_mask, water, START).x_span
    assert wheel_entry.waterline == ((x0, 257.0), (x1, 257.0))
    # The linked rim's outline, simplified to within 1 px of its mask (C328).
    (rim_polygon,) = wheel_entry.rim_outline
    assert len(rim_polygon) >= 8
    assert edge_distance(rim_polygon, sam["wheel rim"].instances[0].mask) <= 1.5
    # Each entry's box is its numbered box, and its outline is its mask's.
    assert (body.box, wheel_entry.box) == ((150, 100, 500, 300), (263, 183, 378, 257))
    (body_polygon,) = body.outline
    assert set(body_polygon) == {(150, 100), (499, 100), (499, 299), (150, 299)}
    (wheel_polygon,) = wheel_entry.outline
    assert edge_distance(wheel_polygon, wheel_mask) <= 1.5
    (water_polygon,) = run.evidence.water_outline
    assert set(water_polygon) == {(0, 257), (639, 257), (639, 479), (0, 479)}


def test_evidence_marks_drops_and_kept_readings(prompt):
    # Task 6's persons: 3, a dry adult standing still at knee, whom step 3 drops, and
    # 4, a wading adult at knee, whom person 3 blocks (C57). Wheel 2's knee decides.
    photo, sam, _ = level_case()
    given = answer(
        vehicles=[vehicle(1)],
        wheels=[wheel(2, "rim_three_quarters")],
        people=[person(3, "knee"), person(4, "knee", standing_still="no")],
    )
    sam = with_people(sam, DRY_PERSON, WET_PERSON)
    run = run_pipeline(photo, FakeClient(sam, given), prompt, tuning=START)
    assert run.outcome.level == "knee"
    found = entries(run)
    assert set(found) == {1, 2, 3, 4}
    wheel_entry = found[2]
    assert (wheel_entry.level, wheel_entry.level_from) == ("knee", "landmark")
    assert (wheel_entry.used, wheel_entry.deciding, wheel_entry.dropped) == (
        True,
        True,
        None,
    )
    assert wheel_entry.waterline == ((150.0, 280.0), (199.0, 280.0))
    assert (wheel_entry.inches, wheel_entry.rim) == (None, None)
    # Step 3's drop keeps the reading's level in the record (C317, M8).
    dry = found[3]
    assert (dry.kind, dry.landmark, dry.level, dry.level_from) == (
        "person",
        "knee",
        "knee",
        "landmark",
    )
    assert (dry.used, dry.deciding, dry.dropped) == (False, False, "no_water_contact")
    assert dry.waterline is None
    # A wading adult is dropped before step 3, so it has no reading and no waterline.
    wading = found[4]
    assert (wading.landmark, wading.level, wading.level_from) == ("knee", None, None)
    assert (wading.used, wading.deciding, wading.dropped) == (
        False,
        False,
        "person_wading",
    )
    assert wading.waterline is None
    assert found[1].dropped is None


def test_a_g4_drop_keeps_its_geometry(prompt):
    # G4: rim_three_quarters reads knee, two levels above geometry's half_knee, so
    # the wheel is dropped, and its vehicle has nothing left to read. Its inches and
    # its fit stay in the record (C328).
    photo, sam, given = geometry_case(waterline="rim_three_quarters")
    run = run_pipeline(
        photo, FakeClient(sam, given), prompt, geometry_in_level=True, tuning=START
    )
    assert run.outcome == Outcome.refused("no_usable_reference")
    found = entries(run)
    wheel_entry = found[2]
    assert wheel_entry.dropped == "wheel_methods_disagree"
    assert (wheel_entry.level, wheel_entry.level_from) == (None, None)
    assert (wheel_entry.used, wheel_entry.deciding) == (False, False)
    low, high = wheel_entry.inches
    assert low == pytest.approx(7.720, abs=0.02)
    assert high == pytest.approx(8.184, abs=0.02)
    assert wheel_entry.rim is not None
    assert found[1].dropped == "vehicle_no_reading"


def test_evidence_with_geometry_off(prompt):
    # C309: off, the van is dropped by its type (C45), its wheel goes with it, and no
    # geometry runs. Its rim is still linked, so its outline is kept (C328).
    photo, sam, given = geometry_case("van")
    run = run_pipeline(photo, FakeClient(sam, given), prompt, tuning=START)
    assert run.outcome == Outcome.refused("no_usable_reference")
    found = entries(run)
    assert (found[1].kind, found[1].dropped) == ("body", "vehicle_type")
    assert (found[2].kind, found[2].dropped) == ("wheel", "wheel_vehicle_dropped")
    for entry in found.values():
        assert (entry.inches, entry.rim) == (None, None)
        assert (entry.level, entry.used, entry.deciding) == (None, False, False)
    (rim_polygon,) = found[2].rim_outline
    assert edge_distance(rim_polygon, sam["wheel rim"].instances[0].mask) <= 1.5


def test_rim_outline_needs_one_linked_rim(prompt):
    # R127: a second rim, centred at (355, 245), lies inside wheel 2's box, so step 2
    # links both to it and marks it rim_several. Neither outline is drawn.
    photo, sam, given = geometry_case()
    real_rim = sam["wheel rim"].instances[0]

    def rim_outline(*rims) -> tuple:
        found = SamResult("wheel rim", list(rims), elapsed_s=0.5, raw="")
        rimmed = sam | {"wheel rim": found}
        run = run_pipeline(
            photo,
            FakeClient(rimmed, given),
            prompt,
            geometry_in_level=True,
            tuning=START,
        )
        return entries(run)[2].rim_outline

    assert rim_outline(real_rim, instance(1, around(355, 245, 10, 10))) == ()
    (polygon,) = rim_outline(real_rim)
    assert edge_distance(polygon, real_rim.mask) <= 1.5
    assert rim_outline() == ()


def test_r147_a_van_wheel_with_two_readings_shows_its_deciding_one(prompt):
    # R147: Muse Spark says van wheel 2 is covered, which holds the sedan row's tire
    # floor without deciding (R143), and geometry measures it at half_knee, which may
    # decide. The record shows the deciding reading, and the floor refuses the
    # shallower exact level (C317), so nothing decides.
    photo, sam, given = geometry_case("van", waterline="wheel_covered")
    run = run_pipeline(
        photo, FakeClient(sam, given), prompt, geometry_in_level=True, tuning=START
    )
    assert run.outcome == Outcome.refused("references_disagree")
    wheel_entry = entries(run)[2]
    assert (wheel_entry.landmark, wheel_entry.level, wheel_entry.level_from) == (
        "wheel_covered",
        "half_knee",
        "geometry",
    )
    # Its geometry reading entered the combine as one that can decide.
    assert (wheel_entry.used, wheel_entry.deciding, wheel_entry.dropped) == (
        True,
        False,
        None,
    )
    # The van's two codes: the Tamaraw's depth, then the Hiace's (M11).
    assert wheel_entry.inches == pytest.approx((9.464, 9.887), abs=0.02)
    assert wheel_entry.rim is not None


def test_an_entry_keeps_its_readings_floor(prompt):
    # C54: an entry says whether its own reading is a floor, since a landmark can't:
    # M5 holds a van wheel's hub as a floor, where a sedan's hub is exact. MS4's
    # overlay labels a floor as one (its final review's I1).
    def found(given, geometry_in_level=False, rims=True):
        photo, sam, _ = geometry_case()
        if not rims:
            sam = sam | {"wheel rim": SamResult("wheel rim", [], elapsed_s=0.5, raw="")}
        run = run_pipeline(
            photo,
            FakeClient(sam, given),
            prompt,
            geometry_in_level=geometry_in_level,
            tuning=START,
        )
        return entries(run)

    covered = found(
        answer(vehicles=[vehicle(1, body="window")], wheels=[wheel(2, "wheel_covered")])
    )
    assert (covered[1].level, covered[1].level_is_floor) == ("tire", True)
    assert (covered[2].level, covered[2].level_is_floor) == ("tire", True)
    # M5: the van's hub, with no rim to measure, holds the sedan row as a floor.
    van = found(
        answer(vehicles=[vehicle(1, "van")], wheels=[wheel(2, "hub")]),
        geometry_in_level=True,
        rims=False,
    )
    assert (van[2].level, van[2].level_from, van[2].level_is_floor) == (
        "half_tire",
        "landmark",
        True,
    )
    exact = found(answer(vehicles=[vehicle(1)], wheels=[wheel(2, "hub")]))
    assert (exact[2].level, exact[2].level_is_floor) == ("half_tire", False)
    # The same landmark, level and source; only the floor tells them apart.
    same = ("landmark", "level", "level_from")
    assert [getattr(van[2], k) for k in same] == [getattr(exact[2], k) for k in same]
    measured = found(
        answer(vehicles=[vehicle(1)], wheels=[wheel(2, "rim_quarter")]),
        geometry_in_level=True,
    )
    assert (measured[2].level_from, measured[2].level_is_floor) == ("geometry", False)
    assert (exact[1].level, exact[1].level_is_floor) == (None, False)


def test_evidence_holds_no_face_plate_or_reason(prompt):
    # Review Focus 6 (C62, C518): only the numbered boxes and the water are outlined.
    photo, sam, given = level_case()
    run = run_pipeline(photo, FakeClient(sam, given), prompt, tuning=START)
    found = entries(run)
    assert set(found) == {1, 2}
    assert not {entry.box for entry in found.values()} & {FACE, PLATE}
    for polygon in polygons(run):
        assert not inside(polygon, FACE)
        assert not inside(polygon, PLATE)
    assert REASON not in repr(run.evidence)


def keys(value: object) -> Iterator[str]:
    """Every key of every mapping in `value`, at any depth."""
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from keys(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from keys(item)


@pytest.mark.parametrize(
    ("case", "geometry_in_level"),
    [
        pytest.param(geometry_case, True, id="geometry"),
        pytest.param(level_case, False, id="level"),
    ],
)
def test_evidence_never_reaches_the_log(prompt, case, geometry_in_level):
    # Review Focus 6 (C316, C328): the record goes to MS4 through the run, never the
    # log line.
    photo, sam, given = case()
    run = run_pipeline(
        photo,
        FakeClient(sam, given),
        prompt,
        geometry_in_level=geometry_in_level,
        tuning=START,
    )
    assert run.evidence is not None
    named = {"evidence", "outline", "rim_outline", "water_outline", "rechecked"}
    assert not named & set(keys(run.log))
    assert "outline" not in json.dumps(run.log)


def test_no_evidence_before_the_answer(prompt):
    # The record is None until the answer passes the schema and the id check.
    photo, sam, given = level_case()
    dark = run_pipeline(flat_jpeg(10), FakeClient(sam, given), prompt, tuning=START)
    assert dark.outcome == Outcome.refused("too_dark")
    assert dark.evidence is None
    failed = run_pipeline(photo, FakeClient(sam, meta_error(500)), prompt, tuning=START)
    assert failed.outcome == Outcome.failed("model_error")
    assert failed.evidence is None
    # A gate result has one, where no box has a reading and step 3 hasn't run.
    dry = answer(
        standing_water="no", vehicles=[vehicle(1)], wheels=[wheel(2, "tire_only")]
    )
    run = run_pipeline(photo, FakeClient(sam, dry), prompt, tuning=START)
    assert run.outcome == Outcome.no_flood()
    found = entries(run)
    assert set(found) == {1, 2}
    assert (found[1].landmark, found[2].landmark) == ("not_visible", "tire_only")
    for entry in found.values():
        assert (entry.level, entry.level_from, entry.waterline) == (None, None, None)
        assert (entry.used, entry.deciding, entry.dropped) == (False, False, None)
    (water_polygon,) = run.evidence.water_outline
    assert set(water_polygon) == {(0, 280), (639, 280), (639, 479), (0, 479)}


def test_a_failed_publish_has_no_evidence(prompt, monkeypatch):
    # Every error path ends with no record, one after the record was built included.
    def broken(image, sam):
        raise ValueError("JPEG encoding failed")

    monkeypatch.setattr("lusot_analysis.pipeline.publish_jpeg", broken)
    photo, sam, given = level_case()
    run = run_pipeline(photo, FakeClient(sam, given), prompt, tuning=START)
    assert run.outcome == Outcome.failed("pipeline_error")
    assert run.evidence is None
