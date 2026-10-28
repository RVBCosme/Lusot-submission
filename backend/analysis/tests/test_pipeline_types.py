"""Tests for the pipeline's shared types: the outcome and its reasons (C42, C50)."""

import ast
from pathlib import Path

import pytest

from lusot_analysis.pipeline import types as pipeline_types
from lusot_analysis.pipeline.types import (
    FAILED_REASONS,
    REFUSED_REASONS,
    ModelKeyRejected,
    Outcome,
)

# One valid shape of each kind. Each bad shape below changes one thing in one of them.
LEVEL = {
    "status": "done",
    "level": "knee",
    "landmark": "rim_three_quarters",
    "passability": "NPLV",
    "basis": {"vehicles": 1, "people": 1},
}
NO_FLOOD = {"status": "done", "no_flood_seen": True}
REFUSED = {"status": "refused", "reason": "too_dark"}
FAILED = {"status": "failed", "reason": "model_error"}
# A set value for each field that only a done outcome may carry.
RESULT_FIELDS = {
    "no_flood_seen": True,
    "level": "knee",
    "landmark": "rim_three_quarters",
    "passability": "NPLV",
    "level_is_floor": True,
    "basis": {"vehicles": 1, "people": 1},
}


def test_reasons_are_the_spec_lists():
    assert REFUSED_REASONS == (
        "too_dark",
        "too_blurry",
        "photo_unusable",
        "water_unsure",
        "no_water_found",
        "no_usable_reference",
        "references_disagree",
    )
    assert FAILED_REASONS == (
        "model_calls_paused",
        "photo_missing",
        "bad_file",
        "model_error",
        "pipeline_error",
    )


def test_builders_make_the_valid_shapes():
    level = Outcome.level_result(
        "knee", "rim_three_quarters", False, {"vehicles": 1, "people": 1}
    )
    assert level == Outcome(**LEVEL)
    assert Outcome.no_flood() == Outcome(**NO_FLOOD)
    assert Outcome.refused("too_dark") == Outcome(**REFUSED)
    assert Outcome.failed("model_error") == Outcome(**FAILED)


def test_outcome_item_fields():
    knee = Outcome.level_result(
        "knee", "rim_three_quarters", False, {"vehicles": 1, "people": 1}
    )
    assert knee.item_fields() == {
        "status": "done",
        "noFloodSeen": False,
        "level": "knee",
        "landmark": "rim_three_quarters",
        "passability": "NPLV",
        "levelIsFloor": False,
        "basis": {"vehicles": 1, "people": 1},
    }
    assert Outcome.no_flood().item_fields() == {"status": "done", "noFloodSeen": True}
    assert Outcome.refused("too_dark").item_fields() == {
        "status": "refused",
        "refusalReason": "too_dark",
    }
    assert Outcome.failed("model_error").item_fields() == {
        "status": "failed",
        "refusalReason": "model_error",
    }


@pytest.mark.parametrize(
    "fields",
    [
        # A reason from the wrong list, no reason where one is needed, or one on done.
        pytest.param(REFUSED | {"reason": "model_error"}, id="refused-failed-reason"),
        pytest.param(FAILED | {"reason": "too_dark"}, id="failed-refused-reason"),
        pytest.param(FAILED | {"reason": "pipeline_not_built"}, id="failed-ms1-reason"),
        pytest.param(REFUSED | {"reason": None}, id="refused-without-reason"),
        pytest.param(FAILED | {"reason": None}, id="failed-without-reason"),
        pytest.param(NO_FLOOD | {"reason": "too_dark"}, id="no-flood-with-reason"),
        pytest.param(LEVEL | {"reason": "water_unsure"}, id="level-with-reason"),
        # Done with neither a level nor no flood seen, or with both.
        pytest.param({"status": "done"}, id="done-with-neither"),
        pytest.param(LEVEL | {"no_flood_seen": True}, id="done-with-both"),
        # A level result's fields.
        pytest.param(LEVEL | {"level": "deep"}, id="unknown-level"),
        pytest.param(LEVEL | {"landmark": None}, id="level-without-landmark"),
        pytest.param(LEVEL | {"basis": None}, id="level-without-basis"),
        pytest.param(LEVEL | {"passability": "PATV"}, id="level-with-another-class"),
        pytest.param(LEVEL | {"passability": None}, id="level-without-class"),
        # No flood seen carries nothing else.
        pytest.param(NO_FLOOD | {"landmark": "hub"}, id="no-flood-with-landmark"),
        pytest.param(NO_FLOOD | {"passability": "PATV"}, id="no-flood-with-class"),
        pytest.param(
            NO_FLOOD | {"basis": {"vehicles": 1, "people": 0}}, id="no-flood-with-basis"
        ),
        pytest.param(NO_FLOOD | {"level_is_floor": True}, id="no-flood-with-floor"),
        # The basis counts vehicles and people, at least one reference in all.
        pytest.param(LEVEL | {"basis": {"vehicles": 1}}, id="basis-without-people"),
        pytest.param(
            LEVEL | {"basis": {"vehicles": 1, "people": 0, "wheels": 2}},
            id="basis-with-an-extra-key",
        ),
        pytest.param(
            LEVEL | {"basis": {"cars": 1, "people": 0}}, id="basis-with-a-wrong-key"
        ),
        pytest.param(
            LEVEL | {"basis": {"vehicles": 0, "people": 0}}, id="basis-sums-to-0"
        ),
        pytest.param(
            LEVEL | {"basis": {"vehicles": -1, "people": 2}}, id="basis-negative-count"
        ),
        # Result fields on a refusal or a failure.
        *[
            pytest.param(REFUSED | {name: value}, id=f"refused-with-{name}")
            for name, value in RESULT_FIELDS.items()
        ],
        pytest.param(
            FAILED | {name: LEVEL[name] for name in LEVEL if name != "status"},
            id="failed-with-a-level",
        ),
        # A status the report never ends in.
        pytest.param({"status": "processing"}, id="unknown-status"),
    ],
)
def test_outcome_rejects_bad_shapes(fields):
    with pytest.raises(ValueError):
        Outcome(**fields)


def test_level_result_rejects_an_unknown_level():
    # The class lookup (step 7) raises the same ValueError, not a KeyError.
    with pytest.raises(ValueError):
        Outcome.level_result("deep", "hub", False, {"vehicles": 1, "people": 0})


def test_every_reason_has_a_log_name():
    for reason in REFUSED_REASONS:
        assert Outcome.refused(reason).log_name == f"refused/{reason}"
    for reason in FAILED_REASONS:
        assert Outcome.failed(reason).log_name == f"failed/{reason}"
    assert Outcome.no_flood().log_name == "done/no_flood_seen"
    assert Outcome(**LEVEL).log_name == "done/level"


def test_pipeline_not_built_is_not_a_new_reason():
    # MS1's reason stays readable on old reports only (spec §3.4).
    assert "pipeline_not_built" not in FAILED_REASONS


WATCHED = {"meta_client", "face_blur"}


def is_type_checking(test: ast.expr) -> bool:
    """`if TYPE_CHECKING:` or `if typing.TYPE_CHECKING:`."""
    return (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING") or (
        isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
    )


def watched_modules(node: ast.Import | ast.ImportFrom) -> set[str]:
    """Which of meta_client and face_blur an import names, absolute or relative."""
    names = [alias.name for alias in node.names]
    if isinstance(node, ast.ImportFrom) and node.module:
        names.append(node.module)
    return {part for name in names for part in name.split(".")} & WATCHED


def test_types_import_the_meta_client_only_for_type_checking():
    # R80: meta_client isn't on this branch until MS1 closes, and the import stays
    # guarded after the merge. Reading the file keeps this true once Task 8's
    # pipeline/__init__.py imports meta_client at runtime.
    tree = ast.parse(Path(pipeline_types.__file__).read_text(encoding="utf-8"))
    guarded = {
        child
        for node in ast.walk(tree)
        if isinstance(node, ast.If) and is_type_checking(node.test)
        for statement in node.body
        for child in ast.walk(statement)
    }
    inside, outside = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            (inside if node in guarded else outside).update(watched_modules(node))
    assert inside == WATCHED
    assert outside == set()


def test_key_rejected_keeps_its_status():
    assert ModelKeyRejected(401).status == 401
