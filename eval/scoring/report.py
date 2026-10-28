"""The evaluation report, its summary and Rene's review sheet (spec §4.4; C409, C410,
C418, C421, C424 to C426).

build_report writes what judges read: report.md in spec §4.4's order, summary.json for
the app's accuracy page (MS5), and the charts. build_review writes Rene's sheet for a
development run. Both sort every set's rows by id first and read no clock, so the same
rows always give the same bytes. Every figure carries its n: a rate through fmt_rate,
and a count, a median or a kappa with n = N beside it.
"""

from __future__ import annotations

import csv
import dataclasses
import io
import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from scoring import RULES_VERSION
from scoring.exclusions import REASONS
from scoring.gate import MEDIAN_ERROR_MAX_IN, Check, Decision, decide
from scoring.labels import map_level_label, map_passability
from scoring.metrics import (
    LevelRow,
    QualityScores,
    Rate,
    SetAScores,
    WheelScores,
    baseline_from_rows,
    caught,
    correct_refusals,
    excluded_a_neg,
    excluded_set_a,
    fmt_inches,
    fmt_rate,
    landmark_agreement,
    left_out_of_passability,
    lusot_class,
    measured_errors,
    replay_comparison,
    score_a_neg,
    score_baseline,
    score_by_level,
    score_latency,
    score_set_a,
    score_subsets,
    score_wheels,
    vehicle_type_matrix,
    wheel_groups,
)
from scoring.rows import CONFIGS, SET_B_VARIANTS, PhotoRow, Result, Run, WheelRow
from scoring.scale import LEVELS, NO_FLOOD_INDEX
from scoring.svg import error_plot_svg, level_matrix_svg

_FOOTER = (
    "Lusot estimates depth at one spot. It is not advice to cross. Follow MMDA and"
    " local advisories.\n"
    "\n"
    "Not affiliated with MMDA.\n"
)
_NOT_RUN = "Not run in this results folder."
_NO_LATENCY = "Latency wasn't measured in this run."
_SYNTHETIC = (
    "Synthetic test data for the harness's own tests. These are not Lusot's results."
)
_INDICATIVE = "With samples this small, every figure is indicative and carries its n."
_FACE_BLUR = (
    "The face blur runs before Meta receives a photo. It can miss faces that are very"
    " small, side-on, partly covered or in the dark."
)
# Words no built file may hold, in any case (C409 and the copy rules). "safe" also
# catches "unsafe" and "safety".
_BANNED = (
    "safe",
    "overfit",
    "underfit",
    "accuracy",
    "mmda's 9 levels",
    "mmda's level",
)
_LABELS = {
    "landmark": "Landmark alone",
    "geometry": "Landmark plus geometry",
    "geometry_no_self_check": "Landmark plus geometry, without the self-check",
}
# The two configurations that the outcome rule chooses between (rules §8).
_NAMED = ("landmark", "geometry")

_ERRORS_FILE = "set-b-errors.svg"
_ERRORS_TITLE = "Set B: depth error per measured wheel (geometry)"
_ERRORS_DESCRIPTION = (
    "Each measured wheel's depth error in inches, smallest first, with the release"
    " gate's 3 in target as a solid line and the median marked."
)
_MATRIX_DESCRIPTION = (
    "Answered Set A photos counted by the alert's level, down the side with the"
    " deepest at the top, and Lusot's level, across with no flood seen first. The"
    " outlined cells are exact agreement."
)


# The two files


def build_report(run: Run, *, first_run: Run | None = None) -> dict[str, bytes]:
    """The report's files by name: report.md, summary.json, a level matrix for each
    configuration when Set A was run, and set-b-errors.svg when Set B was. Each is
    UTF-8 text with \\n line endings and a final newline. `first_run` comes with a
    rerun's report, and only then (C421). Raises ValueError when a file would hold a
    banned word."""
    if (first_run is None) != (run.rerun_reason is None):
        raise ValueError("first_run comes with a rerun's report, and only then (C421)")
    run = _sorted(run)
    outcome = _outcome(run)
    sections = [
        _opening(run),
        _section("## Reported first", *_headline(run, outcome)),
        _section(f"## {_gate_title(run)}", *_gate(run, outcome)),
        _every_metric(run, outcome),
        _baseline(run),
        _by_level(run),
        _matrices(outcome),
        _landmarks(run),
    ]
    if run.kind == "development":
        sections.append(_vehicle_types(run))
    sections += [
        _a_neg(run),
        _correct_refusals(run),
        _subsets(run),
        _wheels("## Set B", run.set_b, _SET_B_LEAD, chart=True),
        _wheels("## Set D", run.set_d, _SET_D_LEAD, chart=False),
        _latency(run),
    ]
    if first_run is not None:
        sections.append(_first_run(_sorted(first_run)))
    sections += [_exclusions(run), _frozen(run), _rebuild()]
    report = "\n\n".join("\n".join(lines) for lines in sections)
    files = {
        "report.md": f"{report}\n\n---\n\n{_FOOTER}",
        "summary.json": _summary(run, outcome),
        **_charts(run, outcome),
    }
    for name, text in files.items():
        _refuse_banned(name, text)
    return {name: text.encode("utf-8") for name, text in files.items()}


def _refuse_banned(name: str, text: str) -> None:
    """Raise ValueError when a file would hold one of _BANNED in any case. The
    report's own copy holds none, so only free text copied from run.json can bring
    one in. The message names the file and the word, never the text around it."""
    folded = text.casefold()
    for word in _BANNED:
        if word in folded:
            raise ValueError(
                f"{name} would contain a banned word ({word}); check run.json's"
                " free-text fields"
            )


_REVIEW_FIELDS = ("result", "class", "landmark")


def build_review(run: Run) -> bytes | None:
    """Rene's review sheet for a development run (C426), or None for a sealed one: a
    row for each Set A photo, then each A-neg photo, sorted by id, with empty columns
    for his verdict and note. CSV in UTF-8, with \\r\\n line endings."""
    if run.kind != "development":
        return None
    run = _sorted(run)
    configs = _configs(run)
    sheet = io.StringIO()
    writer = csv.writer(sheet, lineterminator="\r\n")
    writer.writerow(
        [
            "set",
            "photo_id",
            "event_id",
            "excluded",
            "alert_level",
            "alert_class",
            *(f"{config}_{field}" for config in configs for field in _REVIEW_FIELDS),
            "m8_agreement",
            "m8_detail",
            "rene_verdict",
            "rene_note",
        ]
    )
    for name, rows, excluded in (
        ("set_a", run.set_a, excluded_set_a),
        ("a_neg", run.a_neg, excluded_a_neg),
    ):
        if rows is not None:
            reasons = dict(excluded(rows))
            for row in rows:
                writer.writerow(
                    _review_row(name, row, reasons.get(row.photo_id), configs)
                )
    return sheet.getvalue().encode("utf-8")


def _review_row(
    name: str, row: PhotoRow, reason: str | None, configs: Sequence[str]
) -> list[str]:
    alert = map_level_label(row.level_label_raw)
    stated = map_passability(row.passability_raw)
    cells = [
        name,
        row.photo_id,
        row.event_id,
        reason or "",
        alert.level if alert.kind == "level" else "",
        stated.cls if stated.kind == "class" else "",
    ]
    for config in configs:
        result = row.results[config]
        # The class that scoring counts: PATV for "no flood seen" (rules §7).
        cells += [
            _result_text(result),
            lusot_class(result) or "",
            result.landmark or "",
        ]
    # A-neg photos have no M8 labels, so only Set A's are ever counted.
    return [*cells, *_m8_cells(row, counted=reason is None and row.answered), "", ""]


def _result_text(result: Result) -> str:
    """A result as the sheet shows it: its level, no_flood_seen, refused:<reason> or
    failed:<reason>."""
    if result.status != "done":
        return f"{result.status}:{result.reason}"
    return "no_flood_seen" if result.no_flood_seen else result.level


def _m8_cells(row: PhotoRow, *, counted: bool) -> tuple[str, str]:
    """The photo's M8 agreement as k of n and each reference's two landmarks, over
    the references with a box and an M8 landmark, counted as landmark_agreement
    counts them: only in an answered photo that rules §9 keeps, with a box the answer
    skipped a disagreement. Both are empty when there is nothing to count."""
    references = sorted(
        (
            reference
            for reference in row.references
            if reference.box_id is not None and reference.m8_landmark is not None
        ),
        key=lambda reference: (reference.box_id, reference.kind),
    )
    if not counted or not references:
        return "", ""
    agreeing = sum(
        reference.spark_landmark == reference.m8_landmark for reference in references
    )
    detail = "; ".join(
        f"{reference.kind} {reference.box_id}: {reference.m8_landmark}/"
        f"{reference.spark_landmark or 'unanswered'}"
        for reference in references
    )
    return f"{agreeing} of {len(references)}", detail


# What every section reads


def _sorted(run: Run) -> Run:
    """The run with each set's rows sorted by id, so no output follows file order."""

    def photos(rows: Sequence[PhotoRow] | None) -> tuple[PhotoRow, ...] | None:
        if rows is None:
            return None
        return tuple(sorted(rows, key=lambda row: row.photo_id))

    def wheels(rows: Sequence[WheelRow] | None) -> tuple[WheelRow, ...] | None:
        if rows is None:
            return None
        return tuple(sorted(rows, key=lambda row: (row.crop_id, row.wheel)))

    return dataclasses.replace(
        run,
        set_a=photos(run.set_a),
        a_neg=photos(run.a_neg),
        set_b=wheels(run.set_b),
        set_d=wheels(run.set_d),
        latency=None if run.latency is None else tuple(sorted(run.latency)),
    )


def _configs(run: Run) -> tuple[str, ...]:
    """The configurations every photo carries, as the loader reads them: landmark
    alone once geometry is dropped, or else landmark and geometry, and
    geometry_no_self_check with the self-check on."""
    if run.geometry_dropped:
        return CONFIGS[:1]
    return CONFIGS if run.self_check else CONFIGS[:2]


@dataclass(frozen=True)
class _Outcome:
    """Set A's scores by configuration, Set B's geometry scores (None without Set B)
    and the outcome rule's result. `decision` is None when geometry was dropped
    before the freeze, since decide() isn't called then (C418)."""

    scores: dict[str, SetAScores]
    wheels: WheelScores | None
    decision: Decision | None
    shipped: str
    geometry_stays: bool
    inches_shown: bool


def _outcome(run: Run) -> _Outcome | None:
    """The outcome, or None when Set A wasn't run."""
    if run.set_a is None:
        return None
    scores = {config: score_set_a(run.set_a, config) for config in _configs(run)}
    wheels = None if run.set_b is None else score_wheels(run.set_b, "geometry")
    if run.geometry_dropped:
        return _Outcome(scores, wheels, None, "landmark", False, False)
    # Only Set B's geometry variant gates, and the self-check's extra row never
    # reaches decide() (C407; MS6E-Q1, item 3 (a)).
    decision = decide(scores["landmark"], scores["geometry"], wheels)
    return _Outcome(
        scores,
        wheels,
        decision,
        decision.shipped,
        decision.geometry_stays,
        decision.inches_shown,
    )


def _baseline_answers(run: Run) -> tuple[str | None, str | None, bool]:
    """The baseline's level and class, and whether run.json gave them (C424): a
    sealed run always does; a development run without them computes them from its
    own Set A rows. Each is None when there is nothing to take it from."""
    if run.baseline_level is not None:
        return run.baseline_level, run.baseline_class, True
    if run.set_a is None:
        return None, None, False
    level, cls = baseline_from_rows(run.set_a)
    return level, cls, False


# The opening, the headline and the gate


def _opening(run: Run) -> list[str]:
    date = run.meta["date"]
    agreement = (
        "Its figures are agreement with the labels MMDA and the cities posted, mapped"
        f" by eval/rules.md §2 (v{RULES_VERSION})"
    )
    if run.synthetic:
        title = "# Lusot evaluation report (synthetic test data)"
        opening = _SYNTHETIC
    elif run.kind == "development":
        title = "# Lusot evaluation report (development data)"
        opening = (
            "This report scores development data, not the sealed run. The run is dated"
            f" {date}. {agreement}. {_INDICATIVE}"
        )
    else:
        title = "# Lusot evaluation report"
        ran = "once" if run.rerun_reason is None else "a second time"
        opening = (
            f"The frozen pipeline ran {ran} on the sealed sets, on {date}. {agreement}"
            f" before any result was seen. {_INDICATIVE}"
        )
    blocks = [opening]
    if run.rerun_reason is not None:
        blocks.append(
            "This is eval/rules.md §10's one disclosed rerun. The reason run.json"
            f' records: "{run.rerun_reason}". The first run\'s headline and gate rows'
            ' are under "First run, for comparison", and this rerun\'s decision is the'
            " one applied (C421)."
        )
    return _section(title, *blocks)


def _headline(run: Run, outcome: _Outcome | None) -> list[object]:
    """Rules §7's three headline figures: the configuration that ships, then the
    other one named in advance."""
    if outcome is None:
        return [_NOT_RUN]
    named = [config for config in _NAMED if config in outcome.scores]
    order = [
        outcome.shipped,
        *(config for config in named if config != outcome.shipped),
    ]
    rows = []
    for config in order:
        scores = outcome.scores[config]
        label = _LABELS[config] + (" (ships)" if config == outcome.shipped else "")
        rows.append(
            [
                label,
                fmt_rate(scores.under),
                fmt_rate(scores.passability),
                fmt_rate(scores.coverage),
            ]
        )
    if run.geometry_dropped:
        lead = "Rules §7's three headline figures, for the one configuration run."
    else:
        lead = (
            "Rules §7's three headline figures, for the configuration that ships and"
            " then for the other."
        )
    header = ["Configuration", "Underestimation", "Passability agreement", "Coverage"]
    return [lead, _table(header, rows)]


def _gate_title(run: Run) -> str:
    if run.kind == "development":
        return "Outcome rule on development data"
    return "Release gate"


_CHECK_NAMES = {
    "no_rise": "Set A underestimation",
    "coverage_drop": "Set A coverage (guard)",
    "passability_drop": "Set A passability agreement (guard)",
    "median_error": "Set B median depth error",
    "measured": "Set B wheels measured",
    "envelope": "Set B envelope coverage",
}


def _gate(run: Run, outcome: _Outcome | None) -> list[object]:
    """Rules §8's checks with the values found, the self-check line, the decision,
    and whether inches show, with the reasons when they don't."""
    if outcome is None:
        return [_NOT_RUN]
    decision = outcome.decision
    blocks: list[object] = []
    if run.kind == "development":
        blocks.append(
            "On development data, this outcome rule sets geometry's live default"
            " (C309). It isn't the release gate."
        )
    elif decision is not None:
        blocks.append(
            "Rules §8's targets and guards, each with the value found. Geometry stays"
            " only if Set A underestimation doesn't rise and both guards hold, and"
            " inches show only if geometry stays and Set B meets its three targets."
        )
    blocks.append(_self_check_line(run))
    if decision is None:
        blocks.append(
            "Geometry was dropped before the freeze. The reason run.json records:"
            f' "{run.meta["geometry_dropped_reason"]}". With landmark alone left, the'
            " outcome rule has nothing to choose (C418), and no inches show."
        )
        return blocks
    rows = [_check_row(check, outcome) for check in decision.checks]
    blocks += [
        _table(["Check", "Found", "Target", "Passed"], rows),
        _decision(decision),
    ]
    if decision.reasons:
        blocks += ["Reasons:", [f"- {reason}" for reason in decision.reasons]]
    return blocks


def _self_check_line(run: Run) -> str:
    """MS3's self-check decision, and with the self-check on, what its extra row is
    (rules §8)."""
    decided = run.meta.get("self_check_decided")
    when = "decided: not recorded" if decided is None else f"decided {decided}"
    if not run.self_check:
        return f"Self-check: off ({when}, MS3)."
    line = f"Self-check: on ({when}, MS3)."
    if run.geometry_dropped:
        return line
    return (
        f"{line} Its extra row, geometry without the self-check, is reported but"
        " never chosen (eval/rules.md §8)."
    )


def _check_row(check: Check, outcome: _Outcome) -> list[str]:
    """A check's row. An undefined check's found reads only "undefined" (C406), so
    its row takes the figures, and their n, from the scores."""
    found = check.found if check.shown else _undefined(check.name, outcome)
    if check.passed:
        passed = "yes"
    else:
        passed = "no" if check.shown else "no (undefined)"
    return [_CHECK_NAMES[check.name], found, check.target, passed]


_SET_A_FIGURES: dict[str, Callable[[SetAScores], Rate]] = {
    "no_rise": lambda scores: scores.under,
    "coverage_drop": lambda scores: scores.coverage,
    "passability_drop": lambda scores: scores.passability,
}


def _undefined(name: str, outcome: _Outcome) -> str:
    if name in _SET_A_FIGURES:
        figure = _SET_A_FIGURES[name]
        geometry = figure(outcome.scores["geometry"])
        landmark = figure(outcome.scores["landmark"])
        return f"{fmt_rate(geometry)} with geometry, {fmt_rate(landmark)} without"
    wheels = outcome.wheels
    if wheels is None:
        return "Set B wasn't run (n = 0)"
    if name == "median_error":
        return f"undefined (n = {wheels.measured.k})"
    return fmt_rate(wheels.measured if name == "measured" else wheels.envelope)


def _decision(decision: Decision) -> str:
    if decision.geometry_stays:
        ships = "Geometry stays in the level path, so landmark plus geometry ships."
    else:
        ships = "Geometry doesn't stay, so landmark alone ships."
    if decision.inches_shown:
        inches = "Inches are shown."
    elif decision.geometry_stays:
        inches = "Inches aren't shown."
    else:
        # When Set B meets its targets, no reason says why inches aren't shown, so
        # the decision line says it.
        inches = "Inches aren't shown, because geometry doesn't ship."
    return f"**Decision:** {ships} {inches}"


# Set A


def _every_metric(run: Run, outcome: _Outcome | None) -> list[str]:
    """Every Set A metric by configuration, with each configuration's replay beside
    it on a development run (C425)."""
    heading = "## Set A: every metric"
    if outcome is None:
        return _section(heading, _NOT_RUN)
    columns = []
    comparisons = []
    for config, scores in outcome.scores.items():
        columns.append((_LABELS[config], scores))
        comparison = replay_comparison(run.set_a, config)
        if comparison is not None:
            columns.append((f"{_LABELS[config]} (replay)", comparison.replay))
            comparisons.append(comparison)
    every = [scores for _, scores in columns]
    refusals = sorted({reason for s in every for reason, _ in s.refusal_reasons})
    failures = sorted({reason for s in every for reason, _ in s.failure_reasons})
    metrics: list[tuple[str, Callable[[SetAScores], str]]] = [
        ("Photos scored", lambda s: f"n = {s.scored}"),
        ("Coverage", lambda s: fmt_rate(s.coverage)),
        ("Refused (can't tell)", lambda s: _share(s.refused, s)),
        *(
            (f"Refused: {reason}", _reason_share(reason, refused=True))
            for reason in refusals
        ),
        ("Processing failed", lambda s: _share(s.failed, s)),
        *(
            (f"Processing failed: {reason}", _reason_share(reason, refused=False))
            for reason in failures
        ),
        ("Underestimation", lambda s: fmt_rate(s.under)),
        ("Overestimation", lambda s: fmt_rate(s.over)),
        ("Level agreement, exact", lambda s: fmt_rate(s.exact)),
        ("Level agreement, within one level", lambda s: fmt_rate(s.within_one)),
        ("Passability agreement", lambda s: fmt_rate(s.passability)),
        ("Weighted kappa (quadratic)", _kappa),
        ('"No flood seen" readings', lambda s: _share(s.no_flood_seen, s)),
        ('Floor readings ("at least" a level)', lambda s: _share(s.floors, s)),
    ]
    lead = (
        "Each configuration's Set A figures over the photos that rules §9 keeps (rules"
        " §7). The level figures and kappa are over answered photos whose alert gave a"
        " level, and passability agreement over answered photos whose alert stated a"
        " class."
    )
    if comparisons:
        lead += (
            " A (replay) column scores its configuration with settings chosen on the"
            " other flood events (C425)."
        )
    table = _metric_table(
        [name for name, _ in metrics],
        {label: [show(scores) for _, show in metrics] for label, scores in columns},
    )
    replays = [
        f"- {_LABELS[comparison.config]}, within one level:"
        f" {fmt_rate(comparison.in_sample.within_one)} in-sample,"
        f" {fmt_rate(comparison.replay.within_one)} in replay"
        f" ({_fewer(comparison.within_one_drop)})."
        for comparison in comparisons
    ]
    return _section(heading, lead, table, replays)


def _share(count: int, scores: SetAScores) -> str:
    """A count over every photo scored."""
    return fmt_rate(Rate(count, scores.scored))


def _reason_share(reason: str, *, refused: bool) -> Callable[[SetAScores], str]:
    def show(scores: SetAScores) -> str:
        reasons = scores.refusal_reasons if refused else scores.failure_reasons
        return _share(dict(reasons).get(reason, 0), scores)

    return show


def _kappa(scores: SetAScores) -> str:
    """Kappa rounded half up to 0.01, with its n."""
    if scores.kappa is None:
        return f"undefined (n = {scores.kappa_n})"
    exact = Decimal(scores.kappa.numerator) / scores.kappa.denominator
    shown = exact.quantize(Decimal("0.01"), ROUND_HALF_UP)
    # A kappa just below 0 would otherwise read -0.00.
    return f"{abs(shown) if shown == 0 else shown} (n = {scores.kappa_n})"


def _fewer(drop: int) -> str:
    """The photos within one level in-sample less those in replay, in words."""
    if drop == 0:
        return "no change"
    photos = "photo" if abs(drop) == 1 else "photos"
    return f"{abs(drop)} {'fewer' if drop > 0 else 'more'} {photos}"


def _baseline(run: Run) -> list[str]:
    """The constant answers scored on each configuration's own answered rows (C424),
    and a sentence for each compared figure where the baseline's is the better one."""
    heading = "## Baseline"
    if run.set_a is None:
        return _section(heading, _NOT_RUN)
    level, cls, from_run_json = _baseline_answers(run)
    if level is None or cls is None:
        missing = " or ".join(
            name for name, value in (("level", level), ("class", cls)) if value is None
        )
        return _section(
            heading,
            f"The baseline can't be set: these development rows give no {missing} to"
            " take (C424).",
        )
    if from_run_json:
        source = "Both come from run.json."
    else:
        source = (
            "Both are computed from these development rows: the most common level the"
            " alerts gave, and the most common class they stated (C424)."
        )
    answers = (
        "The baseline gives every photo the same answers: the level"
        f" {level} and the class {cls}. {source}"
    )
    order = (
        "Each configuration comes first, then the baseline on the same answered rows."
        " Exact agreement is shown, not compared."
    )
    rows = []
    behind: list[object] = []
    for config in _configs(run):
        scores = score_set_a(run.set_a, config)
        base = score_baseline(run.set_a, config, level, cls)
        ours = (
            scores.exact,
            scores.within_one,
            scores.under,
            scores.passability,
            *caught(run.set_a, config),
        )
        theirs = (
            base.exact,
            base.within_one,
            base.under,
            base.passability,
            base.caught_nplv,
            base.caught_npatv,
        )
        rows.append([_LABELS[config], *map(fmt_rate, ours)])
        rows.append(["Baseline, same rows", *map(fmt_rate, theirs)])
        sentences = _ahead(theirs, ours)
        if sentences:
            behind += [f"**{_LABELS[config]}**", sentences]
    header = [
        "Answers",
        "Exact (shown, not compared)",
        "Within one level",
        "Underestimation",
        "Passability agreement",
        "NPLV photos caught",
        "NPATV photos caught",
    ]
    return _section(heading, answers, order, _table(header, rows), *behind)


# The figures compared with the baseline, by their place in the baseline table's
# figures, each with 1 when a higher figure is the better one and -1 when a lower
# one is. Exact agreement, at place 0, is shown but not compared (C424).
_COMPARED = (
    (1, 1, "The baseline's within-one agreement is higher"),
    (2, -1, "The baseline's underestimation is lower"),
    (3, 1, "The baseline's passability agreement is higher"),
    (4, 1, "The baseline catches more NPLV photos"),
    (5, 1, "The baseline catches more NPATV photos"),
)


def _ahead(theirs: Sequence[Rate], ours: Sequence[Rate]) -> list[str]:
    """One sentence for each compared figure where the baseline's is the better one,
    stated as numbers. A figure undefined on either side isn't compared."""
    sentences = []
    for place, better, sentence in _COMPARED:
        base, lusot = theirs[place], ours[place]
        if base.value is None or lusot.value is None:
            continue
        if (base.value - lusot.value) * better > 0:
            sentences.append(
                f"- {sentence}: {fmt_rate(base)} against {fmt_rate(lusot)}."
            )
    return sentences


def _by_level(run: Run) -> list[str]:
    """Each configuration's table by the alert's level (C424)."""
    heading = "## By the alert's level"
    if run.set_a is None:
        return _section(heading, _NOT_RUN)
    lead = (
        "Each configuration's Set A photos by the level the alert gave: the photos"
        " kept, those answered, and how many of those Lusot read exactly, within one"
        " level and below the alert's level. A level with 5 or more photos also shows"
        " the three as shares of its answered photos."
    )
    blocks: list[object] = [lead]
    header = [
        "The alert's level",
        "Photos",
        "Answered",
        "Exact",
        "Within one level",
        "Underestimated",
    ]
    for config in _configs(run):
        rows = [_level_row(row) for row in score_by_level(run.set_a, config)]
        blocks.append(f"**{_LABELS[config]}**")
        if rows:
            blocks.append(_table(header, rows))
        else:
            blocks.append("No photo kept has an alert that gave a level (n = 0).")
    return _section(heading, *blocks)


def _level_row(row: LevelRow) -> list[str]:
    counts = (row.exact, row.within_one, row.under)
    if row.n >= 5:
        shown = [fmt_rate(Rate(count, row.answered)) for count in counts]
    else:
        shown = [str(count) for count in counts]
    return [row.level, f"n = {row.n}", str(row.answered), *shown]


def _matrices(outcome: _Outcome | None) -> list[str]:
    """Each configuration's level matrix (C410), each with its table twin: a row for
    each non-empty cell, as the chart's tooltips give them."""
    heading = "## Set A: level matrices"
    if outcome is None:
        return _section(heading, _NOT_RUN)
    lead = (
        "One matrix for each configuration, over the answered photos whose alert gave a"
        " level: the alert's level down the side, Lusot's across. Each chart's table"
        " lists its non-empty cells, since GitHub shows a chart without its tooltips."
    )
    blocks: list[object] = [lead]
    for config, scores in outcome.scores.items():
        blocks.append(f"![{_matrix_title(config)}]({_matrix_file(config)})")
        blocks.append(
            _table(
                ["The alert's level", "Lusot's level", "Photos"],
                [
                    [LEVELS[alert], _reading(reading), str(count)]
                    for alert, reading, count in scores.matrix
                ],
            )
        )
    return _section(heading, *blocks)


def _matrix_file(config: str) -> str:
    return f"level-matrix-{config}.svg"


def _matrix_title(config: str) -> str:
    return f"{_LABELS[config]}: the alert's level against Lusot's"


def _reading(index: int) -> str:
    """A reading's name, as the matrix's tooltips give it."""
    return "no flood seen" if index == NO_FLOOD_INDEX else LEVELS[index]


_REFERENCE_NAMES = {
    "wheel": "Wheel",
    "body": "Vehicle body",
    "person": "Person",
    "all": "All",
}


def _landmarks(run: Run) -> list[str]:
    """Landmark agreement with M8, once for the run (C415)."""
    heading = "## Landmark agreement"
    if run.set_a is None:
        return _section(heading, _NOT_RUN)
    agreement = landmark_agreement(run.set_a)
    counted = dict(agreement.by_kind)["all"].n
    return _section(
        heading,
        "Muse Spark's landmark against our M8 label for the same box (C415), over the"
        " answered Set A photos kept. Every configuration shares Muse Spark's answer,"
        " so this is counted once.",
        _table(
            ["Reference", "Agreement with M8"],
            [
                [_REFERENCE_NAMES[kind], fmt_rate(rate)]
                for kind, rate in agreement.by_kind
            ],
        ),
        "Boxes that Muse Spark's answer skipped, which count as disagreements:"
        f" {fmt_rate(Rate(agreement.unanswered, counted))}. M8 labels that matched no"
        f" box, which are left out: n = {agreement.unmatched}.",
    )


def _vehicle_types(run: Run) -> list[str]:
    """M8's vehicle type against Muse Spark's (W14), on a development run only."""
    heading = "## Vehicle types (development)"
    if run.set_a is None:
        return _section(heading, _NOT_RUN)
    matrix = vehicle_type_matrix(run.set_a)
    lead = (
        "M8's vehicle type against Muse Spark's for the same box (W14), over the"
        " answered Set A photos kept. A development diagnostic, not a headline figure."
    )
    if not matrix:
        return _section(
            heading, lead, "No vehicle box with an M8 type was counted (n = 0)."
        )
    boxes = sum(count for _, _, count in matrix)
    return _section(
        heading,
        lead,
        _table(
            ["M8's type", "Muse Spark's type", "Boxes"],
            [[m8, spark, fmt_rate(Rate(count, boxes))] for m8, spark, count in matrix],
        ),
    )


# A-neg, the quality subset and the subsets


_A_NEG_METRICS = (
    "False flood rate",
    "False flood rate, wet surface",
    "False flood rate, dry surface",
    '"No flood seen"',
    "Refused (can't tell)",
    "Processing failed",
)


def _a_neg(run: Run) -> list[str]:
    """The false flood rate, overall and by surface (W9), with what else the
    flood-free photos got."""
    heading = "## A-neg: flood-free photos"
    if run.a_neg is None:
        return _section(heading, _NOT_RUN)
    columns = {
        _LABELS[config]: _a_neg_column(run.a_neg, config) for config in _configs(run)
    }
    return _section(
        heading,
        'Flood-free photos that got a level instead of "no flood seen" or a refusal,'
        " over the A-neg photos kept. A processing failure counts in the n, never as a"
        " false flood.",
        _metric_table(_A_NEG_METRICS, columns),
    )


def _a_neg_column(rows: Sequence[PhotoRow], config: str) -> list[str]:
    """One configuration's figures, in _A_NEG_METRICS' order."""
    every, wet, dry = (
        score_a_neg(rows, config, surface) for surface in (None, "wet", "dry")
    )
    return [
        fmt_rate(every.false_flood),
        fmt_rate(wet.false_flood),
        fmt_rate(dry.false_flood),
        *(
            fmt_rate(Rate(count, every.scored))
            for count in (every.no_flood_seen, every.refused, every.failed)
        ),
    ]


def _correct_refusals(run: Run) -> list[str]:
    """The quality subset's correct refusals (C414), over Set A and A-neg together."""
    heading = "## Correct refusals"
    if run.set_a is None and run.a_neg is None:
        return _section(heading, _NOT_RUN)
    scores = {
        config: correct_refusals(run.set_a or (), run.a_neg or (), config)
        for config in _configs(run)
    }
    reasons = sorted(
        {reason for s in scores.values() for reason, _ in s.refusal_reasons}
    )
    metrics = [
        "Correct refusals",
        *(f"Refused: {reason}" for reason in reasons),
        "Answered",
        "Processing failed",
    ]
    columns = {
        _LABELS[config]: _quality_column(quality, reasons)
        for config, quality in scores.items()
    }
    return _section(
        heading,
        "The quality subset: the Set A and A-neg photos kept that were marked dark or"
        " blurry before the run (C414). A refusal is correct here, and a processing"
        " failure is not a refusal.",
        _metric_table(metrics, columns),
    )


def _quality_column(scores: QualityScores, reasons: Sequence[str]) -> list[str]:
    """One configuration's figures: correct refusals, each reason, answered, failed."""
    counts = dict(scores.refusal_reasons)
    return [
        fmt_rate(scores.correct),
        *(fmt_rate(Rate(counts.get(reason, 0), scores.n)) for reason in reasons),
        fmt_rate(Rate(scores.answered, scores.n)),
        fmt_rate(Rate(scores.failed, scores.n)),
    ]


def _subsets(run: Run) -> list[str]:
    """Each subset's coverage, underestimation and passability agreement (C414; W6)."""
    heading = "## Subsets"
    if run.set_a is None:
        return _section(heading, _NOT_RUN)
    lead = (
        "Each subset marked before the run (C414), then the photos whose alert gave"
        " tire or deeper (W6)."
    )
    blocks: list[object] = [lead]
    header = [
        "Subset",
        "Photos",
        "Coverage",
        "Underestimation",
        "Passability agreement",
    ]
    for config in _configs(run):
        rows = [
            [
                "tire or deeper, by the alert"
                if subset.tag == "tire_or_deeper"
                else subset.tag,
                f"n = {subset.n}",
                fmt_rate(subset.coverage),
                fmt_rate(subset.under),
                fmt_rate(subset.passability),
            ]
            for subset in score_subsets(run.set_a, config)
        ]
        blocks += [f"**{_LABELS[config]}**", _table(header, rows)]
    return _section(heading, *blocks)


# Set B, Set D and latency


_SET_B_LEAD = "Only the geometry variant counts for the release gate."
_SET_D_LEAD = (
    "Set D is final only and never tuned on, so it is reported apart from Set B"
    " (rules §4)."
)
_WHEELS_LEAD = (
    "Each variant's figures come first, then the geometry variant's by vehicle type"
    " and by each bin. A wheel's error is the distance between its point estimate and"
    " its true depth."
)


def _wheels(
    heading: str, rows: Sequence[WheelRow] | None, lead: str, *, chart: bool
) -> list[str]:
    """A wheel set's table: each variant present, then the geometry variant by
    vehicle type and by each bin's value (W7; C423), and SAM's water, with the error
    chart and its twin when `chart` is set (Set B's)."""
    if rows is None:
        return _section(heading, _NOT_RUN)
    present = set(rows[0].estimates) if rows else {"geometry"}
    table = [
        _wheel_row(variant, score_wheels(rows, variant))
        for variant in SET_B_VARIANTS
        if variant in present
    ]
    bins = sorted({bin_name for row in rows for bin_name in row.bins})
    for by in ("vehicle_type", *bins):
        for value, group in wheel_groups(rows, by):
            label = f"vehicle type {value}" if by == "vehicle_type" else f"{by} {value}"
            table.append(
                _wheel_row(f"geometry, {label}", score_wheels(group, "geometry"))
            )
    header = [
        "Variant or group",
        "Measured",
        "Median error",
        "Worst error",
        "Envelope coverage",
    ]
    water = score_wheels(rows, "geometry").sam_water_found
    blocks: list[object] = [
        f"{lead} {_WHEELS_LEAD}",
        _table(header, table),
        f"SAM found water on {fmt_rate(water)} wheels.",
    ]
    if chart:
        errors = measured_errors(rows, "geometry")
        blocks += [
            f"![{_ERRORS_TITLE}]({_ERRORS_FILE})",
            _table(
                ["Wheel, smallest error first", "Error"],
                [
                    [str(rank), fmt_inches(error)]
                    for rank, error in enumerate(errors, start=1)
                ],
            ),
        ]
    return _section(heading, *blocks)


def _wheel_row(label: str, scores: WheelScores) -> list[str]:
    n = f"(n = {scores.measured.k})"
    return [
        label,
        fmt_rate(scores.measured),
        f"{fmt_inches(scores.median_error)} {n}",
        f"{fmt_inches(scores.worst_error)} {n}",
        fmt_rate(scores.envelope),
    ]


def _latency(run: Run) -> list[str]:
    """Live tests' seconds from upload to pin (C416), when measured."""
    heading = "## Latency"
    if run.latency is None:
        return _section(heading, _NO_LATENCY)
    scores = score_latency(run.latency)
    return _section(
        heading,
        "Live tests' seconds from upload to pin (C416).",
        _table(
            ["Measure", "Upload to pin"],
            [
                ["Median", _seconds(scores.median, scores.n)],
                ["95th percentile, nearest rank", _seconds(scores.p95, scores.n)],
            ],
        ),
    )


def _seconds(value: Decimal | None, n: int) -> str:
    """Seconds rounded half up to 0.1 s, with their n."""
    if value is None:
        return f"undefined (n = {n})"
    return f"{value.quantize(Decimal('0.1'), ROUND_HALF_UP)} s (n = {n})"


# The rerun's first run, exclusions, the frozen versions and the rebuild


def _first_run(first: Run) -> list[str]:
    """The first run's headline and gate rows, beside a rerun's own (C421)."""
    outcome = _outcome(first)
    return _section(
        "## First run, for comparison",
        f"The first run's figures, from {first.meta['date']}, as they were committed."
        " The rerun's decision above is the one applied (C421).",
        "### Reported first",
        *_headline(first, outcome),
        f"### {_gate_title(first)}",
        *_gate(first, outcome),
    )


def _exclusions(run: Run) -> list[str]:
    """Each rules §9 reason with its count and its photos, then the photos left out of
    passability alone (MS6E-Q1, item 2)."""
    heading = "## Exclusions"
    if run.set_a is None and run.a_neg is None:
        return _section(heading, _NOT_RUN)
    lead = (
        "Rules §9's reasons, read from each photo's facts and labels before scoring,"
        " never from Lusot's output."
    )
    blocks: list[object] = [lead]
    blocks += _excluded("Set A", run.set_a, excluded_set_a)
    blocks += _excluded("A-neg", run.a_neg, excluded_a_neg)
    if run.set_a is not None:
        ids = left_out_of_passability(run.set_a)
        blocks.append(
            "Left out of passability agreement only, because the passability label"
            f" didn't map: {', '.join(ids) or 'none'} (n = {len(ids)})."
        )
    return _section(heading, *blocks)


def _excluded(
    name: str,
    rows: Sequence[PhotoRow] | None,
    excluded_of: Callable[[Sequence[PhotoRow]], tuple[tuple[str, str], ...]],
) -> list[object]:
    if rows is None:
        return [f"**{name}:** {_NOT_RUN}"]
    excluded = excluded_of(rows)
    blocks: list[object] = [
        f"**{name}:** {fmt_rate(Rate(len(excluded), len(rows)))} photos excluded."
    ]
    by_reason: dict[str, list[str]] = {}
    for photo, reason in excluded:
        by_reason.setdefault(reason, []).append(photo)
    if by_reason:
        blocks.append(
            _table(
                ["Reason", "Photos", "Ids"],
                [
                    [reason, str(len(by_reason[reason])), ", ".join(by_reason[reason])]
                    for reason in REASONS
                    if reason in by_reason
                ],
            )
        )
    return blocks


_DATASETS = (
    ("set_a", "Set A"),
    ("a_neg", "A-neg"),
    ("set_b", "Set B"),
    ("set_d", "Set D"),
)


def _frozen(run: Run) -> list[str]:
    """What run.json froze, the datasets with their counts, each stop, and the face
    blur's known limits (C419; W25)."""
    frozen = run.meta["frozen"]
    blocks: list[object] = [f"Scored by eval/rules.md v{RULES_VERSION}."]
    if frozen:
        blocks.append(
            _table(
                ["Frozen", "Version"], [[name, frozen[name]] for name in sorted(frozen)]
            )
        )
    else:
        blocks.append("run.json records no frozen versions.")
    datasets = run.meta["datasets"]
    rows = []
    for key, name in _DATASETS:
        recorded = datasets.get(key)
        rows.append(
            [
                name,
                recorded["version"] if recorded else "not recorded",
                recorded["split_seed"] if recorded else "not recorded",
                _contents(getattr(run, key), photos=key in ("set_a", "a_neg")),
            ]
        )
    blocks.append(
        _table(["Dataset", "Version", "Split seed", "In this results folder"], rows)
    )
    stops = run.meta.get("stops", ())
    if stops:
        blocks.append(
            _table(
                ["Stopped", "Cause", "Resumed"],
                [[stop["at"], stop["cause"], stop["resumed"]] for stop in stops],
            )
        )
    else:
        blocks.append("The run recorded no stops.")
    blocks.append(_FACE_BLUR)
    return _section("## Frozen versions and data", *blocks)


def _contents(
    rows: Sequence[PhotoRow] | Sequence[WheelRow] | None, *, photos: bool
) -> str:
    if rows is None:
        return "not run"
    if photos:
        events = len({row.event_id for row in rows})
        return f"{_count(len(rows), 'photo')} from {_count(events, 'event')}"
    wheels = _count(len(rows), "wheel")
    crops = _count(len({row.crop_id for row in rows}), "crop")
    cars = _count(len({row.car_id for row in rows}), "car")
    return f"{wheels} in {crops} of {cars}"


def _count(number: int, noun: str) -> str:
    return f"{number} {noun}" + ("" if number == 1 else "s")


def _rebuild() -> list[str]:
    return _section(
        "## Rebuild this report",
        "With no API key, this command rebuilds the report from the saved rows:",
        ["```sh", "python eval/run_eval.py --from-saved", "```"],
        "Where `python` isn't installed, as on macOS and many Linux systems:",
        ["```sh", "python3 eval/run_eval.py --from-saved", "```"],
    )


# The summary and the charts


def _summary(run: Run, outcome: _Outcome | None) -> str:
    """summary.json for the app's accuracy page (MS5), with nulls for Set A and the
    gate when Set A wasn't run."""
    level, cls, _ = _baseline_answers(run)
    configurations = None
    if outcome is not None:
        configurations = {
            config: {
                "underestimation": _pair(scores.under),
                "passability": _pair(scores.passability),
                "coverage": _pair(scores.coverage),
                "refused": scores.refused,
                "failed": scores.failed,
            }
            for config, scores in outcome.scores.items()
        }
    set_b = None
    if run.set_b is not None:
        wheels = score_wheels(run.set_b, "geometry")
        set_b = {
            "wheels": wheels.wheels,
            "measured": _pair(wheels.measured),
            "median_error_in": _inches(wheels.median_error),
            "worst_error_in": _inches(wheels.worst_error),
            "envelope": _pair(wheels.envelope),
        }
    summary = {
        "kind": run.kind,
        "date": run.meta["date"],
        "rules_version": RULES_VERSION,
        "shipped": None if outcome is None else outcome.shipped,
        "geometry_stays": None if outcome is None else outcome.geometry_stays,
        "inches_shown": None if outcome is None else outcome.inches_shown,
        "configurations": configurations,
        "set_b": set_b,
        "baseline_level": level,
        "baseline_class": cls,
    }
    return json.dumps(summary, indent=2, sort_keys=True) + "\n"


def _pair(rate: Rate) -> dict[str, int]:
    return {"k": rate.k, "n": rate.n}


def _inches(value: Decimal | None) -> str | None:
    """Inches as fmt_inches rounds them, without the unit, or None."""
    return None if value is None else fmt_inches(value).removesuffix(" in")


def _charts(run: Run, outcome: _Outcome | None) -> dict[str, str]:
    charts = {}
    if outcome is not None:
        for config, scores in outcome.scores.items():
            charts[_matrix_file(config)] = level_matrix_svg(
                scores.matrix,
                title=_matrix_title(config),
                description=_MATRIX_DESCRIPTION,
            )
    if run.set_b is not None:
        charts[_ERRORS_FILE] = error_plot_svg(
            measured_errors(run.set_b, "geometry"),
            target=MEDIAN_ERROR_MAX_IN,
            title=_ERRORS_TITLE,
            description=_ERRORS_DESCRIPTION,
        )
    return charts


# Markdown


def _section(heading: str, *blocks: object) -> list[str]:
    """A heading and its blocks, with a blank line between each. A block is a line or
    a list of lines; an empty list adds nothing."""
    lines = [heading]
    for block in blocks:
        if isinstance(block, str):
            lines += ["", block]
        elif block:
            lines += ["", *block]
    return lines


def _metric_table(
    metrics: Sequence[str], columns: dict[str, Sequence[str]]
) -> list[str]:
    """A table with a row for each metric and a column for each of `columns`, a
    column's label with its cells in the metrics' order."""
    return _table(
        ["Metric", *columns],
        [
            [metric, *(cells[place] for cells in columns.values())]
            for place, metric in enumerate(metrics)
        ],
    )


def _table(header: Sequence[str], rows: Sequence[Sequence[str]]) -> list[str]:
    return [
        "| " + " | ".join(header) + " |",
        "|" + "---|" * len(header),
        *("| " + " | ".join(row) + " |" for row in rows),
    ]
