"""Tests for Muse Spark's prompt and answer schema, v1: plan Table 5 without outline_fits."""

import json
from pathlib import Path

from jsonschema import Draft202012Validator

PROMPTS = Path(__file__).parents[1] / "prompts"
SCHEMA = json.loads(
    (PROMPTS / "muse_spark_photo_v1.schema.json").read_text(encoding="utf-8")
)
YES_NO_UNSURE = ["yes", "no", "unsure"]

# Every object's fields in order, keyed by where the object sits.
FIELDS = {
    (): ["photo_usable", "standing_water", "vehicles", "wheels", "people", "reason"],
    ("vehicles",): ["id", "type", "moving", "wake_visible", "body_waterline"],
    ("wheels",): ["id", "waterline"],
    ("people",): ["id", "adult", "standing_still", "waterline"],
}
# Every field that isn't an enum, and its type.
TYPES = {
    ("vehicles",): "array",
    ("wheels",): "array",
    ("people",): "array",
    ("reason",): "string",
    ("vehicles", "id"): "integer",
    ("vehicles", "wake_visible"): "boolean",
    ("wheels", "id"): "integer",
    ("people", "id"): "integer",
}
# Every enum's values, in Table 5's order.
ENUMS = {
    ("photo_usable",): ["yes", "no"],
    ("standing_water",): YES_NO_UNSURE,
    ("vehicles", "type"): [
        "sedan_hatch",
        "suv_mpv",
        "pickup",
        "van",
        "jeepney",
        "tricycle",
        "motorcycle",
        "bus_truck",
        "unknown",
    ],
    ("vehicles", "moving"): YES_NO_UNSURE,
    ("vehicles", "body_waterline"): [
        "below_bumper",
        "bumper",
        "door_sill",
        "mid_door",
        "window",
        "not_visible",
    ],
    ("wheels", "waterline"): [
        "tire_only",
        "rim_quarter",
        "hub",
        "rim_three_quarters",
        "rim_top",
        "wheel_covered",
        "not_visible",
    ],
    ("people", "adult"): YES_NO_UNSURE,
    ("people", "standing_still"): YES_NO_UNSURE,
    ("people", "waterline"): [
        "ankle",
        "mid_shin",
        "knee",
        "mid_thigh",
        "waist",
        "chest",
        "above_chest",
        "not_visible",
    ],
}


def objects(schema: dict, path: tuple = ()):
    """Each object in the schema, with where it sits; a list's items count as the list."""
    if schema["type"] == "object":
        yield path, schema
        for name, field in schema["properties"].items():
            yield from objects(field, path + (name,))
    elif schema["type"] == "array":
        yield from objects(schema["items"], path)


def fields(schema: dict):
    """Each field's schema, keyed by its path."""
    for path, obj in objects(schema):
        for name, field in obj["properties"].items():
            yield path + (name,), field


def keywords(schema: dict) -> set[str]:
    """Every keyword the schema uses; field names under `properties` aren't keywords."""
    found = set(schema)
    for field in schema.get("properties", {}).values():
        found |= keywords(field)
    if "items" in schema:
        found |= keywords(schema["items"])
    return found


def test_schema_is_strict_and_matches_table5():
    found = dict(objects(SCHEMA))
    assert {path: list(obj["properties"]) for path, obj in found.items()} == FIELDS
    # Strict mode needs both on every object (Meta's structured-output page).
    for obj in found.values():
        assert obj["additionalProperties"] is False
        assert obj["required"] == list(obj["properties"])
    enums = {path: field["enum"] for path, field in fields(SCHEMA) if "enum" in field}
    assert enums == ENUMS
    for path, field in fields(SCHEMA):
        assert field["type"] == TYPES.get(path, "string")
    assert "outline_fits" not in json.dumps(SCHEMA)


def test_schema_uses_only_plain_keywords():
    # Meta's page names neither maxLength nor $schema: reason's 200 characters are
    # asked for in the prompt, and the answer is checked as Draft 2020-12.
    plain = {"type", "properties", "required", "additionalProperties", "items", "enum"}
    assert keywords(SCHEMA) <= plain
    Draft202012Validator.check_schema(SCHEMA)


def test_prompt_never_says_safe():
    prompt = (PROMPTS / "muse_spark_photo_v1.md").read_text(encoding="utf-8")
    assert "safe" not in prompt.lower()
    assert "200 characters" in prompt
