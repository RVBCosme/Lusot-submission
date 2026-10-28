"""Rules §7's metrics, every rate an exact fraction (C405, C406).

Excluded photos are scored nowhere (rules §9). The formatters are the one rounding
path that the gate and the report share.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction

from scoring.exclusions import a_neg_exclusion, set_a_exclusion
from scoring.labels import map_level_label, map_passability
from scoring.rows import PhotoRow, Result
from scoring.scale import CLASSES, NO_FLOOD_INDEX, level_index


@dataclass(frozen=True)
class Rate:
    """k of n, since every figure carries its n (rules §7)."""

    k: int
    n: int

    @property
    def value(self) -> Fraction | None:
        """k / n exactly, or None when there is nothing to count (C406)."""
        return Fraction(self.k, self.n) if self.n else None


@dataclass(frozen=True)
class SetAScores:
    """One configuration's Set A scores (C405). Coverage is over every scored photo.
    The level rates, kappa and the matrix are over answered photos whose alert gave
    a level, and passability over answered photos whose alert stated a class. The
    counts of "no flood seen" and of floors are over every scored photo. `matrix`
    holds (the alert's index, Lusot's index, count), sorted, with NO_FLOOD_INDEX for
    "no flood seen", and the reasons come with their counts, sorted by reason."""

    config: str
    scored: int
    answered: int
    refused: int
    failed: int
    coverage: Rate
    under: Rate
    over: Rate
    exact: Rate
    within_one: Rate
    passability: Rate
    kappa: Fraction | None
    kappa_n: int
    no_flood_seen: int
    floors: int
    refusal_reasons: tuple[tuple[str, int], ...]
    failure_reasons: tuple[tuple[str, int], ...]
    matrix: tuple[tuple[int, int, int], ...]


def scored_index(result: Result) -> int | None:
    """Where a result sits on the scale (C405): its level's index, a floor at its own
    level; NO_FLOOD_INDEX for "no flood seen"; None for a refusal or a failure."""
    if result.status != "done":
        return None
    if result.no_flood_seen:
        return NO_FLOOD_INDEX
    return level_index(result.level)


def lusot_class(result: Result) -> str | None:
    """A result's class: its level's, PATV for "no flood seen" (rules §7), and None
    for a refusal or a failure."""
    if result.status != "done":
        return None
    if result.no_flood_seen:
        return "PATV"
    return CLASSES[result.level]


def quadratic_kappa(
    pairs: Sequence[tuple[int, int]], levels: int = 9
) -> Fraction | None:
    """Quadratic-weighted Cohen's kappa over (alert, reading) pairs on 0 to levels - 1:
    1 - sum(w * O) / sum(w * E), with w = (i - j) ** 2, O the counts and
    E = row_i * col_j / N. None for no pairs, or when sum(w * E) is 0. A value off
    the scale raises ValueError, so none is dropped unseen (C405)."""
    if any(not 0 <= value < levels for pair in pairs for value in pair):
        raise ValueError("a kappa value lies outside the levels")
    if not pairs:
        return None
    rows = Counter(i for i, _ in pairs)
    cols = Counter(j for _, j in pairs)
    observed = sum((i - j) ** 2 for i, j in pairs)
    expected = Fraction(
        sum((i - j) ** 2 * rows[i] * cols[j] for i in rows for j in cols), len(pairs)
    )
    if expected == 0:
        return None
    return 1 - observed / expected


def excluded_set_a(rows: Sequence[PhotoRow]) -> tuple[tuple[str, str], ...]:
    """Each excluded Set A photo's id and reason (rules §9), sorted by id."""
    return _excluded(rows, _set_a_reason)


def excluded_a_neg(rows: Sequence[PhotoRow]) -> tuple[tuple[str, str], ...]:
    """Each excluded A-neg photo's id and reason (MS6E-Q1, item 6), sorted by id."""
    return _excluded(rows, lambda row: a_neg_exclusion(row.facts))


def left_out_of_passability(rows: Sequence[PhotoRow]) -> tuple[str, ...]:
    """The ids of scored Set A photos whose passability label didn't map, which
    passability alone leaves out (MS6E-Q1, item 2), sorted."""
    return tuple(
        sorted(
            row.photo_id
            for row in rows
            if _set_a_reason(row) is None
            and map_passability(row.passability_raw).kind == "unmapped"
        )
    )


def score_set_a(rows: Sequence[PhotoRow], config: str) -> SetAScores:
    """One configuration's scores over the Set A photos that rules §9 keeps."""
    scored = [row for row in rows if _set_a_reason(row) is None]
    results = [row.results[config] for row in scored]
    pairs = []  # (the alert's index, Lusot's index)
    agreed = []  # whether Lusot's class is the stated one
    for row, result in zip(scored, results):
        reading = scored_index(result)
        if reading is None:
            continue
        alert = map_level_label(row.level_label_raw)
        if alert.kind == "level":
            pairs.append((level_index(alert.level), reading))
        stated = map_passability(row.passability_raw)
        if stated.kind == "class":
            agreed.append(stated.cls == lusot_class(result))
    offsets = [reading - alert for alert, reading in pairs]
    answered = sum(result.status == "done" for result in results)
    # Kappa knows only the 9 levels, so "no flood seen" counts as below_gutter (C405).
    below_gutter = level_index("below_gutter")
    in_kappa = [
        (alert, below_gutter if reading == NO_FLOOD_INDEX else reading)
        for alert, reading in pairs
    ]
    return SetAScores(
        config=config,
        scored=len(scored),
        answered=answered,
        refused=sum(result.status == "refused" for result in results),
        failed=sum(result.status == "failed" for result in results),
        coverage=Rate(answered, len(scored)),
        under=Rate(sum(offset < 0 for offset in offsets), len(offsets)),
        over=Rate(sum(offset > 0 for offset in offsets), len(offsets)),
        exact=Rate(sum(offset == 0 for offset in offsets), len(offsets)),
        within_one=Rate(sum(abs(offset) <= 1 for offset in offsets), len(offsets)),
        passability=Rate(sum(agreed), len(agreed)),
        kappa=quadratic_kappa(in_kappa),
        kappa_n=len(in_kappa),
        no_flood_seen=sum(result.no_flood_seen for result in results),
        floors=sum(result.level_is_floor for result in results),
        refusal_reasons=_reasons(results, "refused"),
        failure_reasons=_reasons(results, "failed"),
        matrix=tuple(
            sorted(
                (alert, reading, count)
                for (alert, reading), count in Counter(pairs).items()
            )
        ),
    )


def fmt_rate(rate: Rate) -> str:
    """k of n and its share rounded half up to 0.1%, such as 3 of 17 (17.6%), or
    0 of 0 (undefined) (C406)."""
    if rate.value is None:
        return f"{rate.k} of {rate.n} (undefined)"
    # The quotient keeps 28 digits, so it rounds correctly for any n below 10**24.
    percent = (Decimal(100 * rate.k) / rate.n).quantize(Decimal("0.1"), ROUND_HALF_UP)
    return f"{rate.k} of {rate.n} ({percent}%)"


def fmt_inches(value: Decimal | None) -> str:
    """Inches rounded half up to 0.01 in, such as 2.10 in, or undefined (C406)."""
    if value is None:
        return "undefined"
    return f"{value.quantize(Decimal('0.01'), ROUND_HALF_UP)} in"


def _set_a_reason(row: PhotoRow) -> str | None:
    """Rules §9's reason for a Set A photo, from its facts and labels alone."""
    return set_a_exclusion(
        row.facts,
        map_level_label(row.level_label_raw),
        map_passability(row.passability_raw),
        [map_level_label(raw) for raw in row.other_alerts_raw],
    )


def _excluded(
    rows: Sequence[PhotoRow], reason_for: Callable[[PhotoRow], str | None]
) -> tuple[tuple[str, str], ...]:
    found = [(row.photo_id, reason_for(row)) for row in rows]
    return tuple(
        sorted((photo, reason) for photo, reason in found if reason is not None)
    )


def _reasons(results: Sequence[Result], status: str) -> tuple[tuple[str, int], ...]:
    """Each reason among the results with this status and its count, sorted by
    reason."""
    counts = Counter(result.reason for result in results if result.status == status)
    return tuple(sorted(counts.items()))
