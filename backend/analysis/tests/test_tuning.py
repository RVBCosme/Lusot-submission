"""Tests for the tuning module: the cutoffs, their start values and the change log (C310).

Expected numbers come from START, never the live TUNING, so a later tuning can't break
them. Only the two tests that name TUNING read it.
"""

from dataclasses import asdict, fields, replace

from lusot_analysis import tuning
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
    }
    for name in ("min_wheel_side_px", "max_vehicles", "max_people"):
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


def test_change_log_names_the_version():
    assert TUNING.version in tuning.__doc__
