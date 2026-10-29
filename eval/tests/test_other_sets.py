"""Landmark agreement, A-neg, the quality subset, subsets, the baseline and replay
(rules §7; C405, C414, C415, C424, C425)."""

from __future__ import annotations

from collections.abc import Sequence
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
    ANegScores,
    BaselineScores,
    LandmarkAgreement,
    LevelRow,
    QualityScores,
    Rate,
    ReplayComparison,
    SubsetScores,
    baseline_from_rows,
    caught,
    correct_refusals,
    landmark_agreement,
    replay_comparison,
    score_a_neg,
    score_baseline,
    score_by_level,
    score_set_a,
    score_subsets,
    vehicle_type_matrix,
)
from scoring.rows import PhotoRow, load_run
from test_rows import answer, m8, person, vehicle, wheel
from test_set_a import HAND_SET, load_set_a


def kinds(
    wheels: Rate, bodies: Rate, people: Rate, every: Rate
) -> tuple[tuple[str, Rate], ...]:
    """Landmark agreement's by_kind, in its order."""
    return (("wheel", wheels), ("body", bodies), ("person", people), ("all", every))


def load_a_neg(folder: Path, rows: Sequence[dict]) -> tuple[PhotoRow, ...]:
    """Write A-neg rows with the builders, then load them as the harness does."""
    return load_run(write_run(folder, run=run_json(), a_neg=rows)).a_neg


def test_landmark_agreement(tmp_path):
    rows = [
        set_a_row(
            "A01",
            answer=answer(wheels=[wheel(1, "hub"), wheel(2, "rim_top")]),
            m8=[m8(1, "wheel", "hub"), m8(2, "wheel", "hub")],
        ),
        set_a_row(
            "A02",
            answer=answer(
                vehicles=[vehicle(1, "sedan_hatch", "door_sill")],
                people=[person(2, "knee")],
            ),
            m8=[m8(1, "vehicle", "door_sill", "sedan_hatch"), m8(2, "person", "knee")],
        ),
    ]
    assert landmark_agreement(load_set_a(tmp_path, rows)) == LandmarkAgreement(
        kinds(Rate(1, 2), Rate(1, 1), Rate(1, 1), Rate(3, 4)), unanswered=0, unmatched=0
    )


def test_landmark_agreement_counts_unanswered_and_unmatched(tmp_path):
    rows = [
        # The answer lacks box 5, and the person's point matched no box.
        set_a_row(
            "A01",
            answer=answer(wheels=[wheel(1, "hub")]),
            m8=[m8(5, "wheel", "hub"), m8(None, "person", "knee")],
        ),
        # A photo with no answer adds nothing at all.
        set_a_row(
            "A02",
            landmark=failed("model_error"),
            geometry=failed("model_error"),
            answer=None,
            m8=[m8(1, "wheel", "hub"), m8(None, "wheel", "hub")],
        ),
    ]
    assert landmark_agreement(load_set_a(tmp_path, rows)) == LandmarkAgreement(
        kinds(Rate(0, 1), Rate(0, 0), Rate(0, 0), Rate(0, 1)), unanswered=1, unmatched=1
    )


def test_landmark_agreement_skips_excluded_rows(tmp_path):
    readings = {
        "answer": answer(wheels=[wheel(1, "hub")]),
        "m8": [
            m8(1, "wheel", "hub"),
            m8(2, "wheel", "hub"),
            m8(None, "person", "knee"),
        ],
    }
    rows = [set_a_row("A01", **readings), set_a_row("A02", duplicate=True, **readings)]
    # Only A01 counts: its agreeing wheel, its skipped box 2 and its unmatched person.
    assert landmark_agreement(load_set_a(tmp_path, rows)) == LandmarkAgreement(
        kinds(Rate(1, 2), Rate(0, 0), Rate(0, 0), Rate(1, 2)), unanswered=1, unmatched=1
    )


def test_m8_without_a_landmark_is_left_out(tmp_path):
    row = set_a_row(
        "A01",
        answer=answer(wheels=[wheel(1, "hub"), wheel(2, "rim_top"), wheel(3, "hub")]),
        m8=[
            m8(1, "wheel", None),
            m8(4, "wheel", None),  # nor is it counted as unanswered
            m8(2, "wheel", "rim_top"),
            # not_visible is a mark M8 made, so it counts: here, a disagreement.
            m8(3, "wheel", "not_visible"),
        ],
    )
    assert landmark_agreement(load_set_a(tmp_path, [row])) == LandmarkAgreement(
        kinds(Rate(1, 2), Rate(0, 0), Rate(0, 0), Rate(1, 2)), unanswered=0, unmatched=0
    )


def test_vehicle_type_matrix(tmp_path):
    rows = [
        set_a_row(
            "A01",
            answer=answer(
                vehicles=[
                    vehicle(1, "sedan_hatch", "bumper"),
                    vehicle(2, "unknown", "bumper"),
                ]
            ),
            m8=[
                m8(1, "vehicle", "bumper", "sedan_hatch"),
                m8(2, "vehicle", "bumper", "pickup"),
            ],
        ),
        set_a_row(
            "A02",
            answer=answer(vehicles=[vehicle(3, "sedan_hatch", "door_sill")]),
            m8=[m8(3, "vehicle", "door_sill", "sedan_hatch")],
        ),
    ]
    assert vehicle_type_matrix(load_set_a(tmp_path, rows)) == (
        ("pickup", "unknown", 1),
        ("sedan_hatch", "sedan_hatch", 2),
    )


def test_vehicle_type_matrix_counts_boxes_in_answered_kept_photos(tmp_path):
    labels = [
        m8(1, "vehicle", "bumper", "van"),
        m8(2, "vehicle", "bumper", "jeepney"),  # a box the answer lacks
        m8(None, "vehicle", "bumper", "bus_truck"),  # matched no box: left out
        m8(3, "wheel", "hub"),  # not a body: left out
    ]
    spark = answer(vehicles=[vehicle(1, "van", "bumper")], wheels=[wheel(3, "hub")])
    rows = [
        set_a_row("A01", answer=spark, m8=labels),
        set_a_row("A02", answer=None, m8=labels),  # no answer: left out
        set_a_row("A03", answer=spark, m8=labels, duplicate=True),  # excluded
    ]
    assert vehicle_type_matrix(load_set_a(tmp_path, rows)) == (
        ("jeepney", "unanswered", 1),
        ("van", "van", 1),
    )


def test_false_flood_rate(tmp_path):
    def flood_free(photo_id: str, result: dict, surface: str, **fields: object) -> dict:
        return a_neg_row(
            photo_id,
            outcomes={"landmark": result, "geometry": nfs()},
            surface=surface,
            **fields,
        )

    rows = load_a_neg(
        tmp_path,
        [
            flood_free("N01", level("gutter"), "dry"),
            flood_free("N02", nfs(), "wet"),
            flood_free("N03", refused("too_dark"), "wet"),
            flood_free("N04", failed("model_error"), "dry"),
            flood_free("N05", level("knee"), "wet"),
            # A duplicate is left out (MS6E-Q1, item 6).
            flood_free("N06", level("knee"), "dry", duplicate=True),
        ],
    )
    assert score_a_neg(rows, "landmark") == ANegScores(
        scored=5,
        levels=2,
        no_flood_seen=1,
        refused=1,
        failed=1,
        false_flood=Rate(2, 5),
    )
    assert score_a_neg(rows, "landmark", surface="dry") == ANegScores(
        2, 1, 0, 0, 1, Rate(1, 2)
    )
    assert score_a_neg(rows, "landmark", surface="wet") == ANegScores(
        3, 1, 1, 1, 0, Rate(1, 3)
    )
    assert score_a_neg(rows, "geometry").false_flood == Rate(0, 5)


def test_correct_refusals(tmp_path):
    def flood_free(photo_id: str, result: dict, **fields: object) -> dict:
        return a_neg_row(
            photo_id, outcomes={"landmark": result, "geometry": nfs()}, **fields
        )

    run = load_run(
        write_run(
            tmp_path,
            run=run_json(),
            set_a=[
                set_a_row("A01", quality="dark", landmark=refused("too_dark")),
                set_a_row("A02", quality="blurry", landmark=refused("too_blurry")),
                set_a_row("A03", quality="dark"),  # a level, knee
                set_a_row("A04", quality="ok", landmark=refused("too_dark")),
                set_a_row("A05", quality=None, landmark=refused("too_dark")),
                set_a_row(
                    "A06", quality="dark", landmark=refused("too_dark"), duplicate=True
                ),
            ],
            # A-neg photos are unmarked in practice (C423); these check that they
            # count too, unless excluded.
            a_neg=[
                flood_free("N01", failed("model_error"), quality="dark"),
                flood_free(
                    "N02", refused("too_dark"), quality="blurry", duplicate=True
                ),
            ],
        )
    )
    assert correct_refusals(run.set_a, run.a_neg, "landmark") == QualityScores(
        n=4,
        refused=2,
        answered=1,
        failed=1,
        correct=Rate(2, 4),
        refusal_reasons=(("too_blurry", 1), ("too_dark", 1)),
    )
    assert correct_refusals(run.set_a, run.a_neg, "geometry").correct == Rate(0, 4)


def test_subsets(tmp_path):
    rows = load_set_a(
        tmp_path / "tagged",
        [
            # Knee, exact; NPLV agrees.
            set_a_row("A01", passability="NPLV", subsets=["splash"]),
            set_a_row(
                "A02",
                passability="NPLV",
                subsets=["splash", "reflection"],
                landmark=refused("too_dark"),
            ),
            # Under; PATV agrees.
            set_a_row(
                "A03",
                label="gutter deep",
                passability="PATV",
                subsets=["reflection"],
                landmark=nfs(),
            ),
            # Knee against waist: under; NPLV disagrees.
            set_a_row("A04", label="waist deep", passability="NPATV"),
            # Exact; NPATV agrees.
            set_a_row(
                "A05", label="tire deep", passability="NPATV", landmark=level("tire")
            ),
            # Excluded, so neither its tag nor its depth counts.
            set_a_row("A06", label="chest deep", subsets=["moving"], duplicate=True),
        ],
    )
    assert score_subsets(rows, "landmark") == (
        SubsetScores("reflection", 2, Rate(1, 2), Rate(1, 1), Rate(1, 1)),
        SubsetScores("splash", 2, Rate(1, 2), Rate(0, 1), Rate(1, 1)),
        SubsetScores("tire_or_deeper", 2, Rate(2, 2), Rate(1, 2), Rate(1, 2)),
    )
    # tire_or_deeper is always there, undefined when it holds nothing.
    shallow = load_set_a(tmp_path / "shallow", [set_a_row("A01")])
    assert score_subsets(shallow, "landmark") == (
        SubsetScores("tire_or_deeper", 0, Rate(0, 0), Rate(0, 0), Rate(0, 0)),
    )


def test_baseline_ties(tmp_path):
    # The shallower level and the laxer class come first, so the file's order can't
    # break either tie.
    labels = [("gutter deep", "PATV")] * 3 + [("knee deep", "NPLV")] * 3
    labels.append(("tire deep", "NPATV"))
    rows = [
        set_a_row(f"A0{index}", label=label, passability=cls)
        for index, (label, cls) in enumerate(labels, start=1)
    ]
    assert baseline_from_rows(load_set_a(tmp_path / "ties", rows)) == ("knee", "NPLV")
    assert baseline_from_rows([]) == (None, None)
    # Excluded photos count for nothing, and each answer needs its own labels.
    cases = {
        "excluded": (set_a_row("A01", passability="NPLV", duplicate=True), None, None),
        "level_only": (set_a_row("A01"), "knee", None),
        "class_only": (set_a_row("A01", label="", passability="NPATV"), None, "NPATV"),
    }
    for case, (row, baseline_level, baseline_class) in cases.items():
        found = baseline_from_rows(load_set_a(tmp_path / case, [row]))
        assert found == (baseline_level, baseline_class), case


def test_baseline_on_the_hand_computed_set(tmp_path):
    rows = load_set_a(tmp_path / "hand", HAND_SET)
    assert baseline_from_rows(rows) == ("knee", "NPATV")
    assert score_baseline(rows, "landmark", "knee", "NPATV") == BaselineScores(
        config="landmark",
        level="knee",
        cls="NPATV",
        exact=Rate(2, 6),
        within_one=Rate(3, 6),
        under=Rate(2, 6),  # A03 and A09
        passability=Rate(2, 6),
        caught_nplv=Rate(2, 2),
        caught_npatv=Rate(2, 2),
    )
    # A03's "no flood seen" reads PATV, so it isn't caught.
    assert caught(rows, "landmark") == (Rate(2, 2), Rate(1, 2))
    # Each configuration's own answered rows: here geometry refuses A01.
    changed = [
        {**row, "outcomes": {**row["outcomes"], "geometry": refused("too_dark")}}
        if row["photo_id"] == "A01"
        else row
        for row in HAND_SET
    ]
    rows = load_set_a(tmp_path / "geometry", changed)
    geometry = score_baseline(rows, "geometry", "knee", "NPATV")
    assert (geometry.within_one, geometry.passability, geometry.caught_nplv) == (
        Rate(2, 5),
        Rate(2, 5),
        Rate(1, 1),
    )


def test_by_level(tmp_path):
    assert score_by_level(load_set_a(tmp_path, HAND_SET), "landmark") == (
        LevelRow("below_gutter", 1, 1, 0, 1, 1),  # A07's "no flood seen"
        LevelRow("gutter", 1, 0, 0, 0, 0),  # A05 refused
        LevelRow("half_knee", 1, 1, 0, 0, 0),  # A04 reads tire
        LevelRow("knee", 2, 2, 1, 2, 1),  # A01 and A02; A10 is excluded
        LevelRow("tire", 1, 1, 0, 0, 1),  # A03's "no flood seen"
        LevelRow("waist", 1, 0, 0, 0, 0),  # A06 failed
        LevelRow("chest", 1, 1, 1, 1, 0),  # A09
    )


def test_replay_comparison(tmp_path):
    # Every alert gave knee. In-sample, 5 of 6 read within one level; in replay, 2.
    readings = [
        ("knee", "knee"),
        ("knee", "knee"),
        ("knee", "chest"),
        ("tire", "chest"),
        ("half_tire", "chest"),
        ("chest", "chest"),
    ]
    rows = load_set_a(
        tmp_path / "replayed",
        [
            set_a_row(
                f"A0{index}",
                outcomes={
                    "landmark": level(in_sample),
                    "geometry": level("knee"),
                    "landmark_replay": level(replay),
                },
            )
            for index, (in_sample, replay) in enumerate(readings, start=1)
        ],
    )
    comparison = replay_comparison(rows, "landmark")
    assert comparison == ReplayComparison(
        config="landmark",
        in_sample=score_set_a(rows, "landmark"),
        replay=score_set_a(rows, "landmark_replay"),
        within_one_drop=3,
    )
    assert (comparison.in_sample.within_one, comparison.replay.within_one) == (
        Rate(5, 6),
        Rate(2, 6),
    )
    assert comparison.replay.config == "landmark_replay"
    assert replay_comparison(rows, "geometry") is None
    plain = load_set_a(tmp_path / "plain", HAND_SET)
    assert replay_comparison(plain, "landmark") is None
