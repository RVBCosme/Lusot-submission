"""Rules §8's release gate and outcome rule (C406, C407; MS6E-Q5's default (d)).

Geometry stays only if Set A underestimation rises in neither its rate nor its count
and both guards hold. Inches show only if geometry stays and Set B's geometry variant
meets all three of its targets. Rates compare as exact fractions and inches as exact
decimals, so every boundary passes, and a check with an undefined side is neither
shown nor passed (C406). The self-check's extra row never reaches decide(), and
decide() isn't called when geometry was dropped before the freeze (C418).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction

from scoring.metrics import (
    Rate,
    SetAScores,
    WheelScores,
    fmt_inches,
    fmt_rate,
    score_wheels,
)

# Rules §8's numbers. test_gate checks them against eval/rules.md.
MEDIAN_ERROR_MAX_IN = Decimal(3)
MEASURED_MIN = Fraction(70, 100)
ENVELOPE_MIN = Fraction(80, 100)
COVERAGE_DROP_MAX = Fraction(10, 100)
PASSABILITY_DROP_MAX = Fraction(5, 100)


@dataclass(frozen=True)
class Check:
    """One check as the report shows it, with `found` and `target` as display strings.
    `name` is no_rise, coverage_drop, passability_drop, median_error, measured or
    envelope. A check with an undefined side is neither shown nor passed, and its
    found reads undefined (C406)."""

    name: str
    found: str
    target: str
    shown: bool
    passed: bool


@dataclass(frozen=True)
class Decision:
    """The outcome rule's decision. `shipped` is geometry or landmark. The checks come
    in the order of Check's names, and the reasons hold one plain sentence for each
    failed check, in the same order; when Set B wasn't run, one sentence stands for
    its three checks."""

    geometry_stays: bool
    inches_shown: bool
    shipped: str
    checks: tuple[Check, ...]
    reasons: tuple[str, ...]


def decide(
    landmark: SetAScores, geometry: SetAScores, set_b: WheelScores | None
) -> Decision:
    """The decision from the two configurations' Set A scores and the scores of Set
    B's geometry variant, or None when Set B wasn't run."""
    set_a_checks = [
        _no_rise(landmark.under, geometry.under),
        _fall(
            "coverage_drop",
            "Set A coverage",
            landmark.coverage,
            geometry.coverage,
            COVERAGE_DROP_MAX,
        ),
        _fall(
            "passability_drop",
            "Set A passability agreement",
            landmark.passability,
            geometry.passability,
            PASSABILITY_DROP_MAX,
        ),
    ]
    # Without Set B, its checks read as a Set B without wheels would: undefined.
    wheels = score_wheels((), "geometry") if set_b is None else set_b
    set_b_checks = [
        _median_error(wheels),
        _share(
            "measured",
            "Set B's share of wheels measured",
            wheels.measured,
            MEASURED_MIN,
        ),
        _share("envelope", "Set B's envelope coverage", wheels.envelope, ENVELOPE_MIN),
    ]
    reasons = [reason for _, reason in set_a_checks if reason is not None]
    if set_b is None:
        reasons.append(
            "Set B wasn't run, so its three targets can't be checked and inches"
            " aren't shown."
        )
    else:
        reasons += [reason for _, reason in set_b_checks if reason is not None]
    stays = all(check.passed for check, _ in set_a_checks)
    return Decision(
        geometry_stays=stays,
        inches_shown=stays and all(check.passed for check, _ in set_b_checks),
        shipped="geometry" if stays else "landmark",
        checks=tuple(check for check, _ in set_a_checks + set_b_checks),
        reasons=tuple(reasons),
    )


# Each check comes with its failure's sentence, or None when it passes.


def _no_rise(landmark: Rate, geometry: Rate) -> tuple[Check, str | None]:
    """MS6E-Q5's default (d): with geometry, neither the underestimation rate nor the
    number of underestimated photos rises."""
    target = "no rise in the rate or the count"
    rates = _both(landmark, geometry)
    if landmark.value is None or geometry.value is None:
        return (
            _undefined("no_rise", target),
            f"Set A underestimation can't be compared: {rates}.",
        )
    if geometry.value <= landmark.value and geometry.k <= landmark.k:
        return Check("no_rise", rates, target, True, True), None
    if geometry.k <= landmark.k:
        rose = "its rate"
    elif geometry.value <= landmark.value:
        rose = "its count"
    else:
        rose = "its rate and its count"
    return (
        Check("no_rise", rates, target, True, False),
        f"Set A underestimation rises with geometry, in {rose}: {rates}.",
    )


def _fall(
    name: str, subject: str, landmark: Rate, geometry: Rate, limit: Fraction
) -> tuple[Check, str | None]:
    """A guard: with geometry, `subject` falls by at most `limit`."""
    target = f"a fall of at most {_percent(limit)} points"
    rates = _both(landmark, geometry)
    if landmark.value is None or geometry.value is None:
        return _undefined(name, target), f"{subject} can't be compared: {rates}."
    fall = landmark.value - geometry.value
    if fall > 0:
        change = f"a fall of {_tenths(fall)} points"
    elif fall < 0:
        change = f"a rise of {_tenths(-fall)} points"
    else:
        change = "no change"
    check = Check(name, f"{change}: {rates}", target, True, fall <= limit)
    if check.passed:
        return check, None
    return check, (
        f"{subject} falls {_tenths(fall)} points with geometry, more than the"
        f" {_percent(limit)} points allowed: {rates}."
    )


def _median_error(wheels: WheelScores) -> tuple[Check, str | None]:
    """A Set B target: the median error over the measured wheels is at most
    MEDIAN_ERROR_MAX_IN."""
    target = f"at most {MEDIAN_ERROR_MAX_IN} in"
    if wheels.median_error is None:
        return _undefined("median_error", target), (
            "Set B's median depth error can't be shown:"
            f" {fmt_rate(wheels.measured)} wheels measured."
        )
    found = f"{fmt_inches(wheels.median_error)} (n = {wheels.measured.k})"
    check = Check(
        "median_error", found, target, True, wheels.median_error <= MEDIAN_ERROR_MAX_IN
    )
    if check.passed:
        return check, None
    return check, (
        f"Set B's median depth error is {found}, more than the"
        f" {MEDIAN_ERROR_MAX_IN} in allowed."
    )


def _share(
    name: str, subject: str, rate: Rate, minimum: Fraction
) -> tuple[Check, str | None]:
    """A Set B target: `rate` is at least `minimum`."""
    target = f"at least {_percent(minimum)}%"
    if rate.value is None:
        return _undefined(name, target), f"{subject} can't be shown: {fmt_rate(rate)}."
    check = Check(name, fmt_rate(rate), target, True, rate.value >= minimum)
    if check.passed:
        return check, None
    return check, (
        f"{subject} is {fmt_rate(rate)}, below the {_percent(minimum)}% required."
    )


def _undefined(name: str, target: str) -> Check:
    """A check with an undefined side: neither shown nor passed (C406)."""
    return Check(name, "undefined", target, False, False)


def _both(landmark: Rate, geometry: Rate) -> str:
    """Both configurations' rates, geometry's first."""
    return f"{fmt_rate(geometry)} with geometry, {fmt_rate(landmark)} without"


def _percent(share: Fraction) -> Decimal:
    """A share in percent, or a fall in points. It is exact for every target, and
    otherwise keeps 28 digits, so _tenths rounds a fall correctly while its
    denominator stays below 10**24."""
    return Decimal(100 * share.numerator) / share.denominator


def _tenths(fall: Fraction) -> Decimal:
    """A fall in points, rounded half up to 0.1 point as fmt_rate rounds a rate."""
    return _percent(fall).quantize(Decimal("0.1"), ROUND_HALF_UP)
