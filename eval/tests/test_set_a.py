"""Set A's scores on a hand-computed set (rules §7 and §9; C405, C406; spec E5)."""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from decimal import Decimal
from pathlib import Path

from builders import (
    a_neg_row,
    failed,
    level,
    nfs,
    refused,
    run_json,
    set_a_row,
    write_run,
)
from scoring.metrics import (
    Rate,
    excluded_a_neg,
    excluded_set_a,
    fmt_inches,
    fmt_rate,
    left_out_of_passability,
    score_set_a,
)
from scoring.rows import PhotoRow, load_run


def hand_row(
    photo_id: str, label: str, passability: str, result: dict, **fields: object
) -> dict:
    """A row of the hand-computed set, with the same result in both configurations."""
    return set_a_row(
        photo_id,
        label=label,
        passability=passability,
        landmark=result,
        geometry=result,
        **fields,
    )


# The hand-computed set (plan Task 3), each row with what it scores as.
HAND_SET = (
    # Exact; the class agrees.
    hand_row("A01", "knee deep", "NPLV", level("knee")),
    # Under, within one level; the alert states no class.
    hand_row("A02", "knee deep", "", level("half_tire")),
    # Under (-1 against 5); PATV disagrees.
    hand_row("A03", "tire deep", "NPATV", nfs()),
    # Over; NPATV disagrees; one floor.
    hand_row("A04", "half-knee deep", "PATV", level("tire", floor=True)),
    # Unanswered: a refusal.
    hand_row("A05", "gutter deep", "PATV", refused("too_dark")),
    # Unanswered: a processing failure.
    hand_row("A06", "waist deep", "NPATV", failed("model_error")),
    # Under (-1 against 0), within one level; PATV agrees.
    hand_row("A07", "half gutter deep", "PATV", nfs()),
    # An alert with only a class: it agrees.
    hand_row("A08", "", "NPLV", level("knee")),
    # Exact; the class agrees.
    hand_row("A09", "chest deep", "NPATV", level("chest")),
    # Excluded: the label is visible in the image.
    hand_row("A10", "knee deep", "NPLV", level("knee"), label_in_image="yes"),
)


def load_set_a(folder: Path, rows: Sequence[dict]) -> tuple[PhotoRow, ...]:
    """Write Set A rows with the builders, then load them as the harness does."""
    return load_run(write_run(folder, run=run_json(), set_a=rows)).set_a


def with_outcome(row: dict, result: dict) -> dict:
    """The row with `result` in both configurations."""
    return {**row, "outcomes": {"landmark": result, "geometry": result}}


def test_hand_computed_set(tmp_path):
    rows = load_set_a(tmp_path, HAND_SET)
    scores = score_set_a(rows, "landmark")
    assert (scores.config, scores.scored, scores.answered) == ("landmark", 9, 7)
    assert (scores.coverage, scores.refused, scores.failed) == (Rate(7, 9), 1, 1)
    assert scores.under == Rate(3, 6)
    assert scores.over == Rate(1, 6)
    assert scores.exact == Rate(2, 6)
    assert scores.within_one == Rate(4, 6)
    assert scores.passability == Rate(4, 6)
    assert (scores.no_flood_seen, scores.floors) == (2, 1)
    assert scores.refusal_reasons == (("too_dark", 1),)
    assert scores.failure_reasons == (("model_error", 1),)
    assert excluded_set_a(rows) == (
        ("A10", "depth or passability label visible in the image"),
    )


def test_matrix_counts(tmp_path):
    scores = score_set_a(load_set_a(tmp_path, HAND_SET), "landmark")
    # Nothing for A05 and A06 (unanswered), A08 (no level) or A10 (excluded).
    assert scores.matrix == (
        (0, -1, 1),
        (2, 5, 1),
        (4, 3, 1),
        (4, 4, 1),
        (5, -1, 1),
        (7, 7, 1),
    )


def test_configurations_are_scored_apart(tmp_path):
    before = load_set_a(tmp_path / "before", HAND_SET)
    # A02's geometry result becomes knee, an exact reading; landmark keeps half_tire.
    changed = [
        {**row, "outcomes": {**row["outcomes"], "geometry": level("knee")}}
        if row["photo_id"] == "A02"
        else row
        for row in HAND_SET
    ]
    after = load_set_a(tmp_path / "after", changed)
    assert score_set_a(after, "landmark") == score_set_a(before, "landmark")
    geometry = score_set_a(after, "geometry")
    assert geometry != score_set_a(before, "geometry")
    assert (geometry.under, geometry.exact) == (Rate(2, 6), Rate(3, 6))
    assert (4, 4, 2) in geometry.matrix


def test_all_refused_gives_undefined_rates(tmp_path):
    rows = load_set_a(
        tmp_path,
        [
            set_a_row(photo_id, passability="NPLV", landmark=refused(reason))
            for photo_id, reason in (
                ("A01", "too_dark"),
                ("A02", "too_blurry"),
                ("A03", "too_dark"),
            )
        ],
    )
    scores = score_set_a(rows, "landmark")
    assert scores.coverage == Rate(0, 3)
    assert scores.under.value is None
    assert scores.passability.value is None
    assert scores.kappa is None
    assert scores.kappa_n == 0
    # Reasons come sorted by their text, each with its count.
    assert scores.refusal_reasons == (("too_blurry", 1), ("too_dark", 2))
    assert fmt_rate(scores.under) == "0 of 0 (undefined)"


def test_exclusions_never_read_results(tmp_path):
    expected = excluded_set_a(load_set_a(tmp_path / "hand", HAND_SET))
    assert expected
    for name, result in (("refused", refused("too_dark")), ("level", level("tire"))):
        rows = load_set_a(
            tmp_path / name, [with_outcome(row, result) for row in HAND_SET]
        )
        assert excluded_set_a(rows) == expected, name
        assert score_set_a(rows, "landmark").scored == 9, name


def test_formatters():
    assert fmt_rate(Rate(3, 17)) == "3 of 17 (17.6%)"
    assert fmt_rate(Rate(1, 16)) == "1 of 16 (6.3%)"  # half up
    assert fmt_rate(Rate(0, 0)) == "0 of 0 (undefined)"
    assert fmt_inches(Decimal("2.1")) == "2.10 in"
    assert fmt_inches(Decimal("2.125")) == "2.13 in"
    assert fmt_inches(None) == "undefined"


def test_left_out_of_passability(tmp_path):
    kept, unmapped, excluded = load_set_a(
        tmp_path,
        [
            set_a_row("A01", passability="NPLV"),
            set_a_row("A02", passability="NPLV"),
            set_a_row("A03", passability="NPLV", duplicate=True),
        ],
    )
    # The loader refuses "closed" (C420), so it is set on the loaded rows.
    rows = [
        kept,
        dataclasses.replace(unmapped, passability_raw="closed"),
        dataclasses.replace(excluded, passability_raw="closed"),
    ]
    assert left_out_of_passability(rows) == ("A02",)
    # It leaves the photo out of passability only (MS6E-Q1, item 2).
    scores = score_set_a(rows, "landmark")
    assert (scores.scored, scores.exact, scores.passability) == (
        2,
        Rate(2, 2),
        Rate(1, 1),
    )


def test_lists_are_sorted_by_id(tmp_path):
    run = load_run(
        write_run(
            tmp_path,
            run=run_json(),
            set_a=[
                set_a_row("A04"),
                set_a_row("A03", duplicate=True),
                set_a_row("A02"),
                set_a_row("A01", poster_kind="other"),
            ],
            a_neg=[
                a_neg_row("N03", decodes=False),
                a_neg_row("N02"),
                a_neg_row("N01", duplicate=True),
            ],
        )
    )
    assert excluded_set_a(run.set_a) == (
        ("A01", "not posted by MMDA or a city government"),
        ("A03", "duplicate or repost"),
    )
    assert excluded_a_neg(run.a_neg) == (
        ("N01", "duplicate or repost"),
        ("N03", "the file can't be decoded"),
    )
    # The loader refuses "closed" (C420), so it is set on the loaded rows.
    rows = [dataclasses.replace(row, passability_raw="closed") for row in run.set_a]
    assert left_out_of_passability(rows) == ("A02", "A04")
