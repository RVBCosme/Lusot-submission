"""The release gate and the outcome rule (rules §8; C406, C407; MS6E-Q5)."""

from __future__ import annotations

from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from typing import NamedTuple

import pytest
import rules_md
from builders import level, refused, set_a_row
from scoring.gate import (
    COVERAGE_DROP_MAX,
    ENVELOPE_MIN,
    MEASURED_MIN,
    MEDIAN_ERROR_MAX_IN,
    PASSABILITY_DROP_MAX,
    Check,
    Decision,
    decide,
)
from scoring.metrics import SetAScores, WheelScores, score_set_a, score_wheels
from test_set_a import load_set_a
from test_wheels import load_set_b, measured, unmeasured, wheel_row

# Every Set A photo here has an alert of knee deep and NPLV. Against it, knee is exact,
# half_tire underestimates and tire overestimates, and only tire's class disagrees.
KNEE = level("knee")
UNDER = level("half_tire")
OVER = level("tire")
REFUSED = refused("too_dark")


class Wheels(NamedTuple):
    """Set B wheels 13.1 in deep: a measured wheel for each error, its point that far
    above the true depth, and the first `outside` of them with the true depth below
    their envelope; then `not_measured` wheels. At 13.1 in, float subtraction would
    put a 3 in error above 3: 16.1 - 13.1 is 3.0000000000000018."""

    errors: tuple[str, ...]
    not_measured: int = 0
    outside: int = 0


# Comfortably inside every target: 20 photos that both configurations read exactly,
# and 25 wheels, 20 of them measured with a 2 in error and 18 of those inside their
# envelope.
EASY_A = ((20, KNEE, KNEE),)
EASY_B = Wheels(("2",) * 20, not_measured=5, outside=2)

# The same 3 photos underestimated, but geometry refuses one more photo.
HIGHER_RATE = ((3, UNDER, UNDER), (12, KNEE, KNEE), (1, KNEE, REFUSED))
RATE_RISES = (
    "Set A underestimation rises with geometry, in its rate:"
    " 3 of 15 (20.0%) with geometry, 3 of 16 (18.8%) without."
)
NO_RISE = "no rise in the rate or the count"
NO_SET_B = (
    "Set B wasn't run, so its three targets can't be checked and inches aren't shown."
)


def set_a(
    folder: Path, *groups: tuple[int, dict, dict], label: str = "knee deep"
) -> tuple[SetAScores, SetAScores]:
    """Landmark's and geometry's scores on Set A photos given as groups of (count,
    landmark's result, geometry's result), each with an alert of `label` and NPLV."""
    results = [(alone, added) for count, alone, added in groups for _ in range(count)]
    rows = [
        set_a_row(
            f"A{number:03d}",
            label=label,
            passability="NPLV",
            landmark=alone,
            geometry=added,
        )
        for number, (alone, added) in enumerate(results, start=1)
    ]
    loaded = load_set_a(folder, rows)
    return score_set_a(loaded, "landmark"), score_set_a(loaded, "geometry")


def set_b(folder: Path, wheels: Wheels) -> WheelScores:
    """Set B's geometry scores on `wheels`."""
    depth = Decimal("13.1")
    estimates = []
    for index, error in enumerate(wheels.errors):
        point = depth + Decimal(error)
        low = depth + Decimal("0.5") if index < wheels.outside else depth - 1
        estimates.append(measured(str(point), str(low), str(point + 1)))
    estimates += [unmeasured("axis_ratio")] * wheels.not_measured
    rows = [
        wheel_row(f"B{number:03d}", str(depth), estimate)
        for number, estimate in enumerate(estimates, start=1)
    ]
    return score_wheels(load_set_b(folder, rows), "geometry")


def gate(
    folder: Path,
    groups: tuple[tuple[int, dict, dict], ...] = EASY_A,
    wheels: Wheels | None = EASY_B,
) -> Decision:
    """decide() on Set A photos given as set_a()'s groups and on `wheels`, or without
    Set B when `wheels` is None."""
    landmark, geometry = set_a(folder / "set_a", *groups)
    scores = None if wheels is None else set_b(folder / "set_b", wheels)
    return decide(landmark, geometry, scores)


def by_name(decision: Decision) -> dict[str, Check]:
    return {check.name: check for check in decision.checks}


def test_numbers_match_rules_md():
    text = rules_md.section(8)
    assert isinstance(MEDIAN_ERROR_MAX_IN, Decimal)
    shares = (MEASURED_MIN, ENVELOPE_MIN, COVERAGE_DROP_MAX, PASSABILITY_DROP_MAX)
    assert all(isinstance(share, Fraction) for share in shares)
    coverage, passability = (
        f"**{share * 100} percentage points**"
        for share in (COVERAGE_DROP_MAX, PASSABILITY_DROP_MAX)
    )
    for words in (
        f"median depth error ≤ **{MEDIAN_ERROR_MAX_IN} in**",
        f"At least **{MEASURED_MIN * 100}%** of Set B wheels measured",
        f"Envelope coverage ≥ **{ENVELOPE_MIN * 100}%**",
        f"coverage falls by no more than {coverage}",
        f"passability agreement falls by no more than {passability}",
    ):
        assert words in text, words


def test_geometry_stays_with_inches(tmp_path):
    # Geometry lifts two underestimates, and adds a refusal and an overestimate whose
    # class disagrees: no rise, and two small falls.
    decision = gate(
        tmp_path,
        groups=(
            (26, KNEE, KNEE),
            (2, UNDER, KNEE),
            (1, KNEE, OVER),
            (1, KNEE, REFUSED),
        ),
    )
    assert decision == Decision(
        geometry_stays=True,
        inches_shown=True,
        shipped="geometry",
        checks=(
            Check(
                "no_rise",
                "0 of 29 (0.0%) with geometry, 2 of 30 (6.7%) without",
                NO_RISE,
                True,
                True,
            ),
            Check(
                "coverage_drop",
                "a fall of 3.3 points:"
                " 29 of 30 (96.7%) with geometry, 30 of 30 (100.0%) without",
                "a fall of at most 10 points",
                True,
                True,
            ),
            Check(
                "passability_drop",
                "a fall of 3.4 points:"
                " 28 of 29 (96.6%) with geometry, 30 of 30 (100.0%) without",
                "a fall of at most 5 points",
                True,
                True,
            ),
            Check("median_error", "2.00 in (n = 20)", "at most 3 in", True, True),
            Check("measured", "20 of 25 (80.0%)", "at least 70%", True, True),
            Check("envelope", "18 of 20 (90.0%)", "at least 80%", True, True),
        ),
        reasons=(),
    )


# Each Set B target missed by one wheel, with the one reason it gives.
SET_B_MISSES = {
    # 10 errors of 2 in and 10 of 4 in would give a median of exactly 3 in.
    "median error": (
        Wheels(("2",) * 9 + ("4",) * 11, not_measured=5, outside=2),
        "Set B's median depth error is 4.00 in (n = 20), more than the 3 in allowed.",
    ),
    # 18 of 25 would reach 70%.
    "measured": (
        Wheels(("2",) * 17, not_measured=8, outside=2),
        "Set B's share of wheels measured is 17 of 25 (68.0%), below the 70% required.",
    ),
    # 16 of 20 would reach 80%.
    "envelope": (
        Wheels(("2",) * 20, not_measured=5, outside=5),
        "Set B's envelope coverage is 15 of 20 (75.0%), below the 80% required.",
    ),
}


@pytest.mark.parametrize(
    ("wheels", "reason"), list(SET_B_MISSES.values()), ids=list(SET_B_MISSES)
)
def test_geometry_stays_without_inches(tmp_path, wheels, reason):
    decision = gate(tmp_path, wheels=wheels)
    assert (decision.geometry_stays, decision.shipped) == (True, "geometry")
    assert decision.inches_shown is False
    assert decision.reasons == (reason,)


def test_a_higher_rate_drops_geometry(tmp_path):
    decision = gate(tmp_path, groups=HIGHER_RATE)
    no_rise, coverage, passability = decision.checks[:3]
    assert no_rise == Check(
        "no_rise",
        "3 of 15 (20.0%) with geometry, 3 of 16 (18.8%) without",
        NO_RISE,
        True,
        False,
    )
    assert coverage.passed and passability.passed
    # 1 of 16 is 6.25 points, which rounds half up.
    assert coverage.found == (
        "a fall of 6.3 points:"
        " 15 of 16 (93.8%) with geometry, 16 of 16 (100.0%) without"
    )
    assert passability.found == (
        "no change: 15 of 15 (100.0%) with geometry, 16 of 16 (100.0%) without"
    )
    assert (decision.geometry_stays, decision.inches_shown, decision.shipped) == (
        False,
        False,
        "landmark",
    )
    assert decision.reasons == (RATE_RISES,)


def test_a_higher_count_drops_geometry(tmp_path):
    # Geometry answers the 10 photos that landmark alone refused, and underestimates
    # one of them.
    decision = gate(
        tmp_path,
        groups=(
            (3, UNDER, UNDER),
            (1, REFUSED, UNDER),
            (13, KNEE, KNEE),
            (9, REFUSED, KNEE),
        ),
    )
    no_rise, coverage, passability = decision.checks[:3]
    assert no_rise == Check(
        "no_rise",
        "4 of 26 (15.4%) with geometry, 3 of 16 (18.8%) without",
        NO_RISE,
        True,
        False,
    )
    assert coverage.passed and passability.passed
    assert coverage.found == (
        "a rise of 38.5 points:"
        " 26 of 26 (100.0%) with geometry, 16 of 26 (61.5%) without"
    )
    assert (decision.geometry_stays, decision.shipped) == (False, "landmark")
    count_rises = (
        "Set A underestimation rises with geometry, in its count:"
        " 4 of 26 (15.4%) with geometry, 3 of 16 (18.8%) without."
    )
    assert decision.reasons == (count_rises,)


class Scenario(NamedTuple):
    """One check, the found it shows, gate()'s Set A groups and Set B wheels, and the
    reason given when the check fails."""

    name: str
    found: str
    groups: tuple[tuple[int, dict, dict], ...] = EASY_A
    wheels: Wheels | None = EASY_B
    reason: str | None = None


# One scenario per boundary, everything else comfortably passing.
BOUNDARIES = {
    # Exactly as many photos underestimated, at exactly the same rate.
    "no rise": Scenario(
        "no_rise",
        "3 of 20 (15.0%) with geometry, 3 of 20 (15.0%) without",
        groups=((3, UNDER, UNDER), (17, KNEE, KNEE)),
    ),
    # 8 of 20 to 6 of 20: in floats, 0.4 - 0.3 is 0.10000000000000003.
    "coverage": Scenario(
        "coverage_drop",
        "a fall of 10.0 points: 6 of 20 (30.0%) with geometry, 8 of 20 (40.0%) without",
        groups=((6, KNEE, KNEE), (2, KNEE, REFUSED), (12, REFUSED, REFUSED)),
    ),
    # 20 of 20 to 19 of 20: in floats, 1.0 - 0.95 is 0.050000000000000044.
    "passability": Scenario(
        "passability_drop",
        "a fall of 5.0 points:"
        " 19 of 20 (95.0%) with geometry, 20 of 20 (100.0%) without",
        groups=((19, KNEE, KNEE), (1, KNEE, OVER)),
    ),
    # Every error is 16.1 - 13.1 in, which floats put above 3.
    "median error": Scenario(
        "median_error",
        "3.00 in (n = 20)",
        wheels=Wheels(("3",) * 20, not_measured=5, outside=2),
    ),
    # 14 of 20, with 12 of the 14 inside their envelope.
    "measured": Scenario(
        "measured",
        "14 of 20 (70.0%)",
        wheels=Wheels(("2",) * 14, not_measured=6, outside=2),
    ),
    # 8 of 10 measured wheels inside.
    "envelope": Scenario(
        "envelope", "8 of 10 (80.0%)", wheels=Wheels(("2",) * 10, outside=2)
    ),
}


@pytest.mark.parametrize("scenario", list(BOUNDARIES.values()), ids=list(BOUNDARIES))
def test_each_boundary_passes(tmp_path, scenario):
    decision = gate(tmp_path, scenario.groups, scenario.wheels)
    assert by_name(decision)[scenario.name].found == scenario.found
    assert all(check.shown and check.passed for check in decision.checks)
    assert (decision.geometry_stays, decision.inches_shown, decision.shipped) == (
        True,
        True,
        "geometry",
    )
    assert decision.reasons == ()


# Each boundary just missed.
MISSES = {
    # One more photo underestimated: 4 of 20 against 3 of 20.
    "no rise": Scenario(
        "no_rise",
        "4 of 20 (20.0%) with geometry, 3 of 20 (15.0%) without",
        groups=((3, UNDER, UNDER), (1, KNEE, UNDER), (16, KNEE, KNEE)),
        reason="Set A underestimation rises with geometry, in its rate and its count:"
        " 4 of 20 (20.0%) with geometry, 3 of 20 (15.0%) without.",
    ),
    "coverage": Scenario(
        "coverage_drop",
        "a fall of 15.0 points: 5 of 20 (25.0%) with geometry, 8 of 20 (40.0%) without",
        groups=((5, KNEE, KNEE), (3, KNEE, REFUSED), (12, REFUSED, REFUSED)),
        reason="Set A coverage falls 15.0 points with geometry, more than the 10"
        " points allowed: 5 of 20 (25.0%) with geometry, 8 of 20 (40.0%) without.",
    ),
    "passability": Scenario(
        "passability_drop",
        "a fall of 10.0 points:"
        " 18 of 20 (90.0%) with geometry, 20 of 20 (100.0%) without",
        groups=((18, KNEE, KNEE), (2, KNEE, OVER)),
        reason="Set A passability agreement falls 10.0 points with geometry, more"
        " than the 5 points allowed:"
        " 18 of 20 (90.0%) with geometry, 20 of 20 (100.0%) without.",
    ),
    "median error": Scenario(
        "median_error",
        "3.01 in (n = 20)",
        wheels=Wheels(("3.01",) * 20, not_measured=5, outside=2),
        reason="Set B's median depth error is 3.01 in (n = 20), more than the 3 in"
        " allowed.",
    ),
    "measured": Scenario(
        "measured",
        "13 of 20 (65.0%)",
        wheels=Wheels(("2",) * 13, not_measured=7, outside=2),
        reason="Set B's share of wheels measured is 13 of 20 (65.0%), below the 70%"
        " required.",
    ),
    "envelope": Scenario(
        "envelope",
        "7 of 10 (70.0%)",
        wheels=Wheels(("2",) * 10, outside=3),
        reason="Set B's envelope coverage is 7 of 10 (70.0%), below the 80% required.",
    ),
}


@pytest.mark.parametrize("scenario", list(MISSES.values()), ids=list(MISSES))
def test_each_boundary_just_missed_fails(tmp_path, scenario):
    decision = gate(tmp_path, scenario.groups, scenario.wheels)
    for check in decision.checks:
        assert check.shown, check.name
        assert check.passed is (check.name != scenario.name), check.name
    assert by_name(decision)[scenario.name].found == scenario.found
    assert decision.reasons == (scenario.reason,)
    set_a_guard = scenario.name in ("no_rise", "coverage_drop", "passability_drop")
    assert decision.geometry_stays is not set_a_guard
    assert decision.shipped == ("landmark" if set_a_guard else "geometry")
    assert decision.inches_shown is False


def test_undefined_rate_drops_geometry(tmp_path):
    # Geometry answers no Set A photo.
    decision = gate(tmp_path / "unanswered", groups=((5, KNEE, REFUSED),))
    assert decision.checks[0] == Check("no_rise", "undefined", NO_RISE, False, False)
    assert decision.shipped == "landmark"
    no_rate = (
        "Set A underestimation can't be compared:"
        " 0 of 0 (undefined) with geometry, 0 of 5 (0.0%) without."
    )
    coverage_falls = (
        "Set A coverage falls 100.0 points with geometry, more than the 10 points"
        " allowed: 0 of 5 (0.0%) with geometry, 5 of 5 (100.0%) without."
    )
    no_agreement = (
        "Set A passability agreement can't be compared:"
        " 0 of 0 (undefined) with geometry, 5 of 5 (100.0%) without."
    )
    assert decision.reasons == (no_rate, coverage_falls, no_agreement)
    # An undefined rate alone drops geometry. These alerts state a class but no
    # depth, so neither configuration has an underestimation rate, while both guards
    # pass.
    landmark, geometry = set_a(tmp_path / "no_depth", (5, KNEE, KNEE), label="")
    alone = decide(landmark, geometry, set_b(tmp_path / "set_b", EASY_B))
    assert [(check.shown, check.passed) for check in alone.checks[:3]] == [
        (False, False),
        (True, True),
        (True, True),
    ]
    assert (alone.geometry_stays, alone.shipped) == (False, "landmark")
    neither_rate = (
        "Set A underestimation can't be compared:"
        " 0 of 0 (undefined) with geometry, 0 of 0 (undefined) without."
    )
    assert alone.reasons == (neither_rate,)


def test_no_set_b_means_no_inches(tmp_path):
    decision = gate(tmp_path / "easy", wheels=None)
    assert (decision.geometry_stays, decision.shipped) == (True, "geometry")
    assert decision.inches_shown is False
    assert decision.checks[3:] == (
        Check("median_error", "undefined", "at most 3 in", False, False),
        Check("measured", "undefined", "at least 70%", False, False),
        Check("envelope", "undefined", "at least 80%", False, False),
    )
    assert decision.reasons == (NO_SET_B,)
    # Its one sentence follows Set A's.
    rise = gate(tmp_path / "rise", groups=HIGHER_RATE, wheels=None)
    assert rise.reasons == (RATE_RISES, NO_SET_B)


def test_set_b_with_nothing_to_count(tmp_path):
    # Five wheels, none measured: the share measured is shown and fails, and the
    # median error and envelope coverage are undefined.
    unmeasured_only = gate(tmp_path / "unmeasured", wheels=Wheels((), not_measured=5))
    assert [
        (check.found, check.shown, check.passed) for check in unmeasured_only.checks[3:]
    ] == [
        ("undefined", False, False),
        ("0 of 5 (0.0%)", True, False),
        ("undefined", False, False),
    ]
    assert unmeasured_only.geometry_stays
    assert unmeasured_only.inches_shown is False
    assert unmeasured_only.reasons == (
        "Set B's median depth error can't be shown: 0 of 5 (0.0%) wheels measured.",
        "Set B's share of wheels measured is 0 of 5 (0.0%), below the 70% required.",
        "Set B's envelope coverage can't be shown: 0 of 0 (undefined).",
    )
    # A Set B without wheels leaves all three undefined, each with its own sentence.
    empty = gate(tmp_path / "empty", wheels=Wheels(()))
    assert not any(check.shown or check.passed for check in empty.checks[3:])
    no_median = (
        "Set B's median depth error can't be shown: 0 of 0 (undefined) wheels measured."
    )
    assert empty.reasons == (
        no_median,
        "Set B's share of wheels measured can't be shown: 0 of 0 (undefined).",
        "Set B's envelope coverage can't be shown: 0 of 0 (undefined).",
    )


def test_rates_compare_exactly(tmp_path):
    # Landmark alone answers 3 of 6 photos and underestimates 1; geometry answers all
    # 6 and underestimates 2. As fractions the rates are equal, so only the count
    # rises.
    decision = gate(
        tmp_path / "count",
        groups=(
            (1, UNDER, UNDER),
            (1, REFUSED, UNDER),
            (2, KNEE, KNEE),
            (2, REFUSED, KNEE),
        ),
    )
    assert decision.checks[0] == Check(
        "no_rise",
        "2 of 6 (33.3%) with geometry, 1 of 3 (33.3%) without",
        NO_RISE,
        True,
        False,
    )
    count_rises = (
        "Set A underestimation rises with geometry, in its count:"
        " 2 of 6 (33.3%) with geometry, 1 of 3 (33.3%) without."
    )
    assert decision.reasons == (count_rises,)
    # 1 of 3 against 1 of 3 passes.
    same = gate(tmp_path / "same", groups=((1, UNDER, UNDER), (2, KNEE, KNEE)))
    assert same.checks[0] == Check(
        "no_rise",
        "1 of 3 (33.3%) with geometry, 1 of 3 (33.3%) without",
        NO_RISE,
        True,
        True,
    )
    assert same.geometry_stays
