"""Muse Spark's prompt and answer schema, read together by version (spec §3.6).

The caller names the folder that holds them: the repo's `prompts/`, or wherever the
image copies it. The image's layout differs from the repo's, so this module never
builds a path from its own location.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.protocols import Validator
from jsonschema.validators import validator_for

PROMPT_VERSION = "muse_spark_photo_v1"  # MS1's probe note names no v2 (P1)


@dataclass(frozen=True)
class PromptSpec:
    """One version's prompt text and answer schema.

    `schema_name` is the name `judge` sends the schema under: the version itself.
    """

    version: str
    text: str
    schema: dict
    schema_name: str


def load_prompt(prompts_dir: Path, version: str = PROMPT_VERSION) -> PromptSpec:
    """Read `<version>.md` and `<version>.schema.json` from `prompts_dir`.

    A missing file raises FileNotFoundError. The schema is checked against its own
    draft (see validator_class), and one that fails raises jsonschema's SchemaError.
    """
    text = (prompts_dir / f"{version}.md").read_text(encoding="utf-8")
    schema_file = prompts_dir / f"{version}.schema.json"
    schema = json.loads(schema_file.read_text(encoding="utf-8"))
    validator_class(schema).check_schema(schema)
    return PromptSpec(version=version, text=text, schema=schema, schema_name=version)


def validator_class(schema: dict) -> type[Validator]:
    """The validator for the draft the schema's `$schema` names, else Draft 2020-12.

    load_prompt checks the schema with it, and validate_answer checks each answer
    with it, so both read the schema under the same draft.
    """
    return validator_for(schema, default=Draft202012Validator)
