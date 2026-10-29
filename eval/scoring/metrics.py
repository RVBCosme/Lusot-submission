"""Rules §7's metrics, every rate an exact fraction and every inch or second an exact
decimal (C405, C406), with the baseline, the table by the alert's level and the
event replay (C424, C425).

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
from scoring.rows import REPLAY_SUFFIX, Estimate, PhotoRow, Result, WheelRow
from scoring.scale import CLASS_NAMES, CLASSES, LEVELS, NO_FLOOD_INDEX, level_index


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
    """One configuration's scores over the Set A photos that rules §9 keeps. `config`
    may also be a replay, <configuration>_replay (C425)."""
    scored = _scored_set_a(rows)
    results = [row.results[config] for row in scored]
    pairs, classes = _answered(scored, config)
    agreed = [stated == given for stated, given in classes]
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


# Landmark agreement, once per run: every configuration shares Muse Spark's answer.


@dataclass(frozen=True)
class LandmarkAgreement:
    """Muse Spark's landmark against M8's for the same box (C415), by kind: wheel,
    body, person, then all. Each rate is over the references with a box and an M8
    landmark, in the answered Set A photos that rules §9 keeps. A reference whose
    box the answer lacks is a disagreement, counted in `unanswered` too. An M8
    label that matched no box counts only in `unmatched`."""

    by_kind: tuple[tuple[str, Rate], ...]
    unanswered: int
    unmatched: int


# Reference.kind's values, in by_kind's order.
_KINDS = ("wheel", "body", "person")


def landmark_agreement(rows: Sequence[PhotoRow]) -> LandmarkAgreement:
    """Landmark agreement over Set A (C415)."""
    labels = [
        reference
        for row in _scored_set_a(rows)
        if row.answered
        for reference in row.references
    ]
    counted = [
        reference
        for reference in labels
        if reference.box_id is not None and reference.m8_landmark is not None
    ]
    groups = [
        (kind, [reference for reference in counted if reference.kind == kind])
        for kind in _KINDS
    ]
    groups.append(("all", counted))
    by_kind = []
    for kind, group in groups:
        agreeing = sum(
            reference.spark_landmark == reference.m8_landmark for reference in group
        )
        by_kind.append((kind, Rate(agreeing, len(group))))
    return LandmarkAgreement(
        by_kind=tuple(by_kind),
        unanswered=sum(reference.spark_landmark is None for reference in counted),
        unmatched=sum(reference.box_id is None for reference in labels),
    )


def vehicle_type_matrix(rows: Sequence[PhotoRow]) -> tuple[tuple[str, str, int], ...]:
    """M8's vehicle type against Muse Spark's (W14), as (M8's, Muse Spark's or
    "unanswered", count), sorted. It counts the body references with a box and an
    M8 type, in the answered Set A photos that rules §9 keeps. A development
    diagnostic, not a headline number (rules §7)."""
    pairs = Counter(
        (
            reference.m8_type,
            "unanswered" if reference.spark_type is None else reference.spark_type,
        )
        for row in _scored_set_a(rows)
        if row.answered
        for reference in row.references
        if reference.kind == "body"
        and reference.box_id is not None
        and reference.m8_type is not None
    )
    return tuple(sorted((*pair, count) for pair, count in pairs.items()))


# A-neg and the quality subset


@dataclass(frozen=True)
class ANegScores:
    """One configuration's results on the A-neg photos kept (C405). The false flood
    rate is the photos given a level over all of them, so a processing failure
    counts in its n, never as a false flood."""

    scored: int
    levels: int
    no_flood_seen: int
    refused: int
    failed: int
    false_flood: Rate


def score_a_neg(
    rows: Sequence[PhotoRow], config: str, surface: str | None = None
) -> ANegScores:
    """One configuration's A-neg scores over the photos that MS6E-Q1 item 6 keeps,
    or over only those with `surface` (wet or dry; W9) when it is given."""
    results = [
        row.results[config]
        for row in _scored_a_neg(rows)
        if surface is None or row.surface == surface
    ]
    levels = sum(result.level is not None for result in results)
    return ANegScores(
        scored=len(results),
        levels=levels,
        no_flood_seen=sum(result.no_flood_seen for result in results),
        refused=sum(result.status == "refused" for result in results),
        failed=sum(result.status == "failed" for result in results),
        false_flood=Rate(levels, len(results)),
    )


@dataclass(frozen=True)
class QualityScores:
    """One configuration's results on the quality subset: the photos kept that were
    marked dark or blurry before the run (C414). Correct refusals are the refusals
    over all of them; a processing failure is not a refusal (C405). The refusals'
    reasons come with their counts, sorted by reason."""

    n: int
    refused: int
    answered: int
    failed: int
    correct: Rate
    refusal_reasons: tuple[tuple[str, int], ...]


def correct_refusals(
    set_a: Sequence[PhotoRow], a_neg: Sequence[PhotoRow], config: str
) -> QualityScores:
    """One configuration's correct refusals, over Set A and A-neg together."""
    kept = [*_scored_set_a(set_a), *_scored_a_neg(a_neg)]
    results = [row.results[config] for row in kept if row.quality in ("dark", "blurry")]
    refused = sum(result.status == "refused" for result in results)
    return QualityScores(
        n=len(results),
        refused=refused,
        answered=sum(result.status == "done" for result in results),
        failed=sum(result.status == "failed" for result in results),
        correct=Rate(refused, len(results)),
        refusal_reasons=_reasons(results, "refused"),
    )


# Subsets


@dataclass(frozen=True)
class SubsetScores:
    """One subset's Set A scores (C414; W6): its scored photos, and its coverage,
    underestimation and passability agreement as score_set_a gives them."""

    tag: str
    n: int
    coverage: Rate
    under: Rate
    passability: Rate


def score_subsets(rows: Sequence[PhotoRow], config: str) -> tuple[SubsetScores, ...]:
    """One configuration's scores for each tag marked on a Set A photo kept, sorted,
    then for tire_or_deeper: the photos whose alert gave tire or deeper (W6), always
    there, its rates undefined when it holds none."""
    scored = _scored_set_a(rows)
    tags = sorted({tag for row in scored for tag in row.subsets})
    groups = [(tag, [row for row in scored if tag in row.subsets]) for tag in tags]
    groups.append(("tire_or_deeper", [row for row in scored if _tire_or_deeper(row)]))
    subsets = []
    for tag, members in groups:
        scores = score_set_a(members, config)
        subsets.append(
            SubsetScores(
                tag, scores.scored, scores.coverage, scores.under, scores.passability
            )
        )
    return tuple(subsets)


# The baseline (C424)


@dataclass(frozen=True)
class BaselineScores:
    """Constant answers, `level` and `cls`, scored on one configuration's rows
    (C424): the level rates over its answered photos whose alert gave a level, and
    passability and the photos caught over those whose alert stated a class.
    Exact agreement is shown, not compared."""

    config: str
    level: str
    cls: str
    exact: Rate
    within_one: Rate
    under: Rate
    passability: Rate
    caught_nplv: Rate
    caught_npatv: Rate


def baseline_from_rows(rows: Sequence[PhotoRow]) -> tuple[str | None, str | None]:
    """The baseline's level and class from Set A rows (C424): the commonest level
    among the photos kept whose alert gave one, a tie going to the deeper level,
    and the commonest class among those whose alert stated one, a tie going to the
    stricter class. Each is None when there is nothing to count."""
    scored = _scored_set_a(rows)
    alerts = Counter(index for index in map(_alert_index, scored) if index is not None)
    stated = Counter(cls for cls in map(_stated_class, scored) if cls is not None)
    level = max(alerts, key=lambda index: (alerts[index], index), default=None)
    # CLASS_NAMES runs from PATV to NPATV, so a later class is stricter.
    cls = max(
        stated, key=lambda name: (stated[name], CLASS_NAMES.index(name)), default=None
    )
    return (None if level is None else LEVELS[level], cls)


def score_baseline(
    rows: Sequence[PhotoRow], config: str, level: str, cls: str
) -> BaselineScores:
    """The constant answers scored on exactly the photos that score_set_a scores for
    `config` (C424)."""
    pairs, classes = _answered(_scored_set_a(rows), config)
    offsets = [level_index(level) - alert for alert, _ in pairs]
    caught_nplv, caught_npatv = _caught([(stated, cls) for stated, _ in classes])
    return BaselineScores(
        config=config,
        level=level,
        cls=cls,
        exact=Rate(sum(offset == 0 for offset in offsets), len(offsets)),
        within_one=Rate(sum(abs(offset) <= 1 for offset in offsets), len(offsets)),
        under=Rate(sum(offset < 0 for offset in offsets), len(offsets)),
        passability=Rate(sum(stated == cls for stated, _ in classes), len(classes)),
        caught_nplv=caught_nplv,
        caught_npatv=caught_npatv,
    )


def caught(rows: Sequence[PhotoRow], config: str) -> tuple[Rate, Rate]:
    """Lusot's catches for one configuration, to set beside the baseline's (C424): of
    the answered photos whose alert stated NPLV, then of those that stated NPATV,
    the ones Lusot gave NPLV or NPATV."""
    _, classes = _answered(_scored_set_a(rows), config)
    return _caught(classes)


# The table by the alert's level (C424)


@dataclass(frozen=True)
class LevelRow:
    """One level's row in the table by the alert's level (C424): the Set A photos
    kept whose alert gave it, those answered, and how many of those read it exactly,
    within one level, and below it. The report adds percentages from 5 photos up."""

    level: str
    n: int
    answered: int
    exact: int
    within_one: int
    under: int


def score_by_level(rows: Sequence[PhotoRow], config: str) -> tuple[LevelRow, ...]:
    """One configuration's table by the alert's level, in level order, with a row
    for each level an alert gave."""
    readings = {}  # the alert's index: Lusot's index for each photo, or None
    for row in _scored_set_a(rows):
        alert = _alert_index(row)
        if alert is not None:
            readings.setdefault(alert, []).append(scored_index(row.results[config]))
    table = []
    for alert in sorted(readings):
        offsets = [
            reading - alert for reading in readings[alert] if reading is not None
        ]
        table.append(
            LevelRow(
                level=LEVELS[alert],
                n=len(readings[alert]),
                answered=len(offsets),
                exact=sum(offset == 0 for offset in offsets),
                within_one=sum(abs(offset) <= 1 for offset in offsets),
                under=sum(offset < 0 for offset in offsets),
            )
        )
    return tuple(table)


# The event replay (C425)


@dataclass(frozen=True)
class ReplayComparison:
    """A configuration's in-sample scores beside its event replay's (C425), and the
    photos within one level in-sample less those in replay, which MS3b's guard 3
    reads."""

    config: str
    in_sample: SetAScores
    replay: SetAScores
    within_one_drop: int


def replay_comparison(rows: Sequence[PhotoRow], config: str) -> ReplayComparison | None:
    """The comparison for `config`, or None when no row carries its replay. The
    loader gives every row of a file the same replays (C425), so both sides score
    the same photos."""
    replay = config + REPLAY_SUFFIX
    if not any(replay in row.results for row in rows):
        return None
    in_sample = score_set_a(rows, config)
    replayed = score_set_a(rows, replay)
    return ReplayComparison(
        config=config,
        in_sample=in_sample,
        replay=replayed,
        within_one_drop=in_sample.within_one.k - replayed.within_one.k,
    )


# Set B, Set D and latency (rules §7; C407, C416). The errors and medians are exact:
# Decimal's 28 digits hold them for every estimate between -10**22 and 10**22 in.


@dataclass(frozen=True)
class WheelScores:
    """One variant's scores over Set B's or Set D's wheels (rules §7; C407). The
    errors are |depthInPoint - true_depth_in| over the measured wheels, and the
    envelope counts the measured wheels whose true depth lies from depthInMin to
    depthInMax, both bounds included (MS6E-Q1, item 4). sam_water_found is over
    every wheel."""

    variant: str
    wheels: int
    measured: Rate
    median_error: Decimal | None
    worst_error: Decimal | None
    envelope: Rate
    sam_water_found: Rate


def score_wheels(rows: Sequence[WheelRow], variant: str) -> WheelScores:
    """One variant's scores over the wheels given: a set's, or one of its
    wheel_groups. The median of an even count is the mean of the middle two."""
    measured = _measured(rows, variant)
    errors = measured_errors(rows, variant)
    inside = sum(estimate.low <= truth <= estimate.high for truth, estimate in measured)
    return WheelScores(
        variant=variant,
        wheels=len(rows),
        measured=Rate(len(measured), len(rows)),
        median_error=_median(errors),
        worst_error=errors[-1] if errors else None,
        envelope=Rate(inside, len(measured)),
        sam_water_found=Rate(sum(row.sam_water_found for row in rows), len(rows)),
    )


def wheel_groups(
    rows: Sequence[WheelRow], by: str
) -> tuple[tuple[str, tuple[WheelRow, ...]], ...]:
    """The wheels by vehicle type when `by` is vehicle_type, or else by the value of
    the bin named `by` (W7; C423), sorted by value. A row without that bin is left
    out, and each group keeps the rows' order."""
    groups: dict[str, list[WheelRow]] = {}
    for row in rows:
        value = row.vehicle_type if by == "vehicle_type" else row.bins.get(by)
        if value is not None:
            groups.setdefault(value, []).append(row)
    return tuple((value, tuple(groups[value])) for value in sorted(groups))


def measured_errors(rows: Sequence[WheelRow], variant: str) -> tuple[Decimal, ...]:
    """Each measured wheel's error for one variant, sorted, for the error chart."""
    return tuple(
        sorted(
            abs(estimate.point - truth) for truth, estimate in _measured(rows, variant)
        )
    )


@dataclass(frozen=True)
class LatencyScores:
    """Live tests' seconds from upload to pin (C416): their median, and their 95th
    percentile by nearest rank, the ceil(0.95 n)-th smallest of the n samples. Both
    are None without samples."""

    n: int
    median: Decimal | None
    p95: Decimal | None


def score_latency(samples: Sequence[tuple[str, Decimal]]) -> LatencyScores:
    """Latency over every (test id, seconds) sample, as Run.latency gives them."""
    seconds = sorted(value for _, value in samples)
    rank = (95 * len(seconds) + 99) // 100  # ceil(0.95 n), in whole numbers
    return LatencyScores(
        n=len(seconds),
        median=_median(seconds),
        p95=seconds[rank - 1] if seconds else None,
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


def _scored_set_a(rows: Sequence[PhotoRow]) -> list[PhotoRow]:
    """The Set A photos that rules §9 keeps, in their order."""
    return [row for row in rows if _set_a_reason(row) is None]


def _scored_a_neg(rows: Sequence[PhotoRow]) -> list[PhotoRow]:
    """The A-neg photos that MS6E-Q1 item 6 keeps, in their order."""
    return [row for row in rows if a_neg_exclusion(row.facts) is None]


def _alert_index(row: PhotoRow) -> int | None:
    """The index of the level the photo's alert gave, or None when it gave none."""
    alert = map_level_label(row.level_label_raw)
    return level_index(alert.level) if alert.kind == "level" else None


def _stated_class(row: PhotoRow) -> str | None:
    """The class the photo's alert stated, or None when it stated none that maps."""
    stated = map_passability(row.passability_raw)
    return stated.cls if stated.kind == "class" else None


def _tire_or_deeper(row: PhotoRow) -> bool:
    """Whether the photo's alert gave tire or deeper (W6)."""
    alert = _alert_index(row)
    return alert is not None and alert >= level_index("tire")


def _answered(
    scored: Sequence[PhotoRow], config: str
) -> tuple[list[tuple[int, int]], list[tuple[str, str]]]:
    """The answered photos among scored ones, as the level rates and passability
    count them (C405): (the alert's index, Lusot's index) for each whose alert gave
    a level, and (the stated class, Lusot's class) for each whose alert stated one."""
    pairs = []
    classes = []
    for row in scored:
        result = row.results[config]
        reading = scored_index(result)
        if reading is None:
            continue
        alert = _alert_index(row)
        if alert is not None:
            pairs.append((alert, reading))
        stated = _stated_class(row)
        if stated is not None:
            classes.append((stated, lusot_class(result)))
    return pairs, classes


def _caught(classes: Sequence[tuple[str, str]]) -> tuple[Rate, Rate]:
    """Of the (stated, given) class pairs that state NPLV, then of those that state
    NPATV, the ones given NPLV or NPATV (C424)."""

    def share(target: str) -> Rate:
        given = [cls for stated, cls in classes if stated == target]
        return Rate(sum(cls in ("NPLV", "NPATV") for cls in given), len(given))

    return share("NPLV"), share("NPATV")


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


def _measured(rows: Sequence[WheelRow], variant: str) -> list[tuple[Decimal, Estimate]]:
    """The wheels that `variant` measured, each as its true depth and its estimate,
    in the rows' order."""
    return [
        (row.true_depth_in, row.estimates[variant])
        for row in rows
        if row.estimates[variant].measured
    ]


def _median(ordered: Sequence[Decimal]) -> Decimal | None:
    """The middle of sorted values, or the mean of the middle two for an even count;
    None for no values."""
    if not ordered:
        return None
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2
