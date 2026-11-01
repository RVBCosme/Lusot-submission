"""Tests for the tuning module: the cutoffs, their start values and the change log (C310).

Expected numbers come from START, never the live TUNING, so a later tuning can't break
them. Six tests read TUNING, and none expects a number of its own: each untuned name
still equals START's value, MS3a's five constants equal TUNING's values, the touch
check is no looser than START's (C331), tuning-v2's changes are named in the change
log, the change log names TUNING's version, and TUNING's effort and drawing are known
values.
"""

from dataclasses import asdict, fields, replace

from lusot_analysis import tuning
from lusot_analysis.annotate import DRAWINGS
from lusot_analysis.meta_client import REASONING_EFFORTS
from lusot_analysis.pipeline import quality, references
from lusot_analysis.pipeline.quality import QualityScores, quality_refusal
from lusot_analysis.tuning import START, TUNING, Tuning


def test_start_values_are_the_specs():
    values = asdict(START)
    untuned = values.pop("untuned")
    assert values == {
        "version": "tuning-v1",
        "touch_tolerance_px": 5.0,  # T (C301)
        "touch_share_min": 0.25,  # C302
        "ragged_iqr_share": 0.10,  # C303, R86
        "daylight_brightness_min": 80.0,  # C305
        "rim_score_min": 0.5,
        "rim_size_low": 0.85,  # check 9 (C305)
        "rim_size_high": 1.15,
        "rim_edge_k": 1.0,  # G3
        "brightness_min": 40.0,  # C44
        "sharpness_min": 25.0,
        "min_wheel_side_px": 40,  # C56
        "max_vehicles": 6,  # C70
        "max_people": 6,
        "reasoning_effort": None,  # C312: Muse Spark picks its own
        "drawing": "boxes-v1",  # C325
        "min_person_side_px": 0,  # C92: off, so no person is too small
        "no_flood_share_max": 1.0,  # C93: off, so SAM's water never unsettles a no
    }
    for name in (
        "min_wheel_side_px",
        "max_vehicles",
        "max_people",
        "min_person_side_px",
    ):
        assert type(values[name]) is int
    # Every value starts untuned.
    assert untuned == {f.name for f in fields(Tuning)} - {"version", "untuned"}
    assert isinstance(untuned, frozenset)


def test_untuned_values_are_still_their_start_values():
    names = {f.name for f in fields(Tuning)}
    for name in TUNING.untuned:
        assert name in names - {"version", "untuned"}
        assert getattr(TUNING, name) == getattr(START, name)


def test_ms3a_cutoffs_read_the_tuning_module():
    assert (quality.BRIGHTNESS_MIN, quality.SHARPNESS_MIN) == (
        TUNING.brightness_min,
        TUNING.sharpness_min,
    )
    assert (
        references.MIN_WHEEL_SIDE_PX,
        references.MAX_VEHICLES,
        references.MAX_PEOPLE,
    ) == (TUNING.min_wheel_side_px, TUNING.max_vehicles, TUNING.max_people)
    # A replay can raise the quality cutoffs (R128: built on START).
    scores = QualityScores(45.0, 100.0)
    assert quality_refusal(scores, START) is None
    assert quality_refusal(scores, replace(START, brightness_min=50.0)) == "too_dark"
    assert quality_refusal(scores, replace(START, sharpness_min=150.0)) == "too_blurry"


def _relaxes_touch_check(candidate: Tuning) -> bool:
    """True when the touch check keeps more references than START's does (C331).

    Written as "not within the bounds", so a NaN, which compares False with
    everything and would turn the share check off, counts as relaxed.
    """
    return not (
        candidate.touch_tolerance_px <= START.touch_tolerance_px
        and candidate.touch_share_min >= START.touch_share_min
    )


def test_the_touch_check_is_never_relaxed():
    # C331. Scored on the 55 photos the Nov 2 blind double relabel agreed on (Set C,
    # development only): at START, 10 scored levels, 8 exact, 0 under. A 10 px
    # tolerance gives 3 under, each a passability class read lower; 15 px gives 4. A
    # 0.10 share passed on the agreed labels, but was held: OL131, whose label is
    # unsure, would read knee where one relabel read tire. So the live tuning may
    # tighten the check but never loosen it.
    assert not _relaxes_touch_check(TUNING)
    assert _relaxes_touch_check(replace(START, touch_tolerance_px=10.0))
    assert _relaxes_touch_check(replace(START, touch_share_min=0.10))
    assert _relaxes_touch_check(replace(START, touch_share_min=float("nan")))
    assert not _relaxes_touch_check(replace(START, touch_tolerance_px=4.0))
    assert not _relaxes_touch_check(replace(START, touch_share_min=0.30))


def test_tuning_v2_names_each_change_in_the_change_log():
    # tuning-v2 (Nov 2): the person cutoff (C92) and the no-flood share (C93). Each
    # changed value is named in the change log, and is out of `untuned`.
    assert TUNING.version == "tuning-v2"
    changed = {
        f.name
        for f in fields(Tuning)
        if f.name not in ("version", "untuned")
        and getattr(TUNING, f.name) != getattr(START, f.name)
    }
    assert changed == {"min_person_side_px", "no_flood_share_max"}
    entry = tuning.__doc__.split("- tuning-v2")[1]
    for name in changed:
        assert name in entry
        assert name not in TUNING.untuned


def test_change_log_names_the_version():
    assert TUNING.version in tuning.__doc__


def test_tuning_effort_and_drawing_are_known_values():
    # What the Lambda and the offline runner send Muse Spark (C312, C325): no effort,
    # or one Muse Spark takes, and a drawing annotate knows.
    effort = TUNING.reasoning_effort
    assert effort is None or effort in REASONING_EFFORTS
    assert TUNING.drawing in DRAWINGS
