"""Tests for Muse Spark's versioned prompt and schema, and the answer's schema check.

The files load from the folder the caller names, never through a path built from the
module's own location, because the image's layout differs from the repo's (spec
§3.6). An answer that fails the schema is a model error (C47).
"""

import inspect
import json
import re
import tomllib
from pathlib import Path

import pytest
from fakes import REPO_PROMPTS, answer, person, vehicle, wheel
from jsonschema.exceptions import SchemaError

from lusot_analysis import prompts
from lusot_analysis.pipeline.references import validate_answer
from lusot_analysis.pipeline.types import ModelAnswerError
from lusot_analysis.prompts import PROMPT_VERSION, load_prompt
from lusot_analysis.rules import BODY_ROWS, PEOPLE_ROWS, READING_TYPES, WHEEL_ROWS

PYPROJECT = Path(__file__).parents[1] / "pyproject.toml"
# Draft 4 reads exclusiveMinimum as a flag on minimum, while Draft 2020-12 needs a
# number there. So only Draft 4 accepts this schema, and only it reads n = 1 as valid.
FLAG_SCHEMA = {
    "type": "object",
    "properties": {"n": {"type": "number", "minimum": 0, "exclusiveMinimum": True}},
}
DRAFT_4 = {"$schema": "http://json-schema.org/draft-04/schema#", **FLAG_SCHEMA}


@pytest.fixture(scope="module")
def schema() -> dict:
    """Schema v1, as the pipeline loads it."""
    return load_prompt(REPO_PROMPTS).schema


def copy_prompt(folder: Path, suffixes: tuple[str, ...], version: str) -> None:
    """Copy the repo's prompt files with these suffixes into `folder` as `version`."""
    for suffix in suffixes:
        source = REPO_PROMPTS / f"{PROMPT_VERSION}{suffix}"
        (folder / f"{version}{suffix}").write_bytes(source.read_bytes())


def test_load_prompt_reads_the_versioned_files():
    spec = load_prompt(REPO_PROMPTS)
    assert spec.version == PROMPT_VERSION == spec.schema_name
    assert PROMPT_VERSION == "muse_spark_photo_v1"  # MS1's probe note names no v2 (P1)
    assert spec.text.strip()
    md = REPO_PROMPTS / f"{PROMPT_VERSION}.md"
    assert spec.text == md.read_text(encoding="utf-8")
    assert spec.schema["additionalProperties"] is False


def test_load_prompt_reads_the_folder_it_is_given(tmp_path):
    # The image keeps the files somewhere else (spec §3.6): the folder and the version
    # alone name them.
    copy_prompt(tmp_path, (".md", ".schema.json"), "muse_spark_photo_v9")
    spec = load_prompt(tmp_path, "muse_spark_photo_v9")
    assert (spec.version, spec.schema_name) == ("muse_spark_photo_v9",) * 2
    repo = load_prompt(REPO_PROMPTS)
    assert (spec.text, spec.schema) == (repo.text, repo.schema)


@pytest.mark.parametrize(
    "present",
    [
        pytest.param((), id="neither-file"),
        pytest.param((".md",), id="text-only"),
        pytest.param((".schema.json",), id="schema-only"),
    ],
)
def test_missing_prompt_raises(tmp_path, present):
    copy_prompt(tmp_path, present, PROMPT_VERSION)
    with pytest.raises(FileNotFoundError):
        load_prompt(tmp_path)


def test_prompts_module_never_walks_up_from_its_file():
    assert "__file__" not in inspect.getsource(prompts)


def test_schema_is_checked_under_the_draft_it_names(tmp_path):
    for version, named in (("draft4", DRAFT_4), ("plain", FLAG_SCHEMA)):
        (tmp_path / f"{version}.md").write_text("Fill in the schema.", encoding="utf-8")
        schema_file = tmp_path / f"{version}.schema.json"
        schema_file.write_text(json.dumps(named), encoding="utf-8")
    assert load_prompt(tmp_path, "draft4").schema == DRAFT_4
    with pytest.raises(SchemaError):
        load_prompt(tmp_path, "plain")  # no $schema, so Draft 2020-12
    # validate_answer reads the schema under the same draft.
    validate_answer({"n": 1}, DRAFT_4)
    with pytest.raises(ModelAnswerError):
        validate_answer({"n": 0}, DRAFT_4)


def test_jsonschema_is_a_runtime_dependency():
    # The Lambda checks every answer with it (C47), so the image must install it.
    project = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]
    names = {
        re.match(r"[\w.-]+", entry)[0].lower() for entry in project["dependencies"]
    }
    assert "jsonschema" in names


def test_rules_cover_every_schema_enum(schema):
    # Task 1's tables read every value Muse Spark can answer, and nothing else.
    fields = {
        name: schema["properties"][name]["items"]["properties"]
        for name in ("vehicles", "wheels", "people")
    }
    assert set(fields["wheels"]["waterline"]["enum"]) == set(WHEEL_ROWS)
    assert set(fields["people"]["waterline"]["enum"]) == set(PEOPLE_ROWS)
    assert set(fields["vehicles"]["body_waterline"]["enum"]) == set(BODY_ROWS)
    assert READING_TYPES <= set(fields["vehicles"]["type"]["enum"])


def test_answer_builder_matches_the_schema(schema):
    validate_answer(
        answer(
            vehicles=[vehicle(1)], wheels=[wheel(2, "hub")], people=[person(3, "knee")]
        ),
        schema,
    )
    validate_answer(answer(), schema)  # its empty lists are JSON arrays too


@pytest.mark.parametrize(
    "data",
    [
        pytest.param(json.dumps(answer()), id="a-string"),
        pytest.param({**answer(), "depth": "knee"}, id="an-extra-key"),
        pytest.param(answer(wheels=[{**wheel(2, "hub"), "id": "2"}]), id="a-string-id"),
        # knee is a person's mark, outside the wheel enum
        pytest.param(answer(wheels=[wheel(2, "knee")]), id="a-waterline-off-its-enum"),
    ],
)
def test_validate_answer_rejects_bad_answers(schema, data):
    with pytest.raises(ModelAnswerError) as raised:
        validate_answer(data, schema)
    assert "REASON-MARKER-31" not in str(raised.value)  # never quotes the answer (C62)


def test_validate_answer_needs_an_object_whatever_the_schema():
    # The empty schema accepts any JSON value, but the later steps read an object.
    validate_answer({}, {})
    with pytest.raises(ModelAnswerError):
        validate_answer([], {})
