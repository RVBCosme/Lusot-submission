"""W11 (MS7 Task 17; spec section 4.5): no vehicle verdict in the output.

The frozen Muse Spark schema names no verdict, and no field of `GET /reports/{id}`
names a vehicle type. Read from the repo's own files, with no network call.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PROMPTS = REPO / "backend" / "analysis" / "prompts"
REPORTS_TS = REPO / "backend" / "api" / "src" / "reports.ts"

VERDICT = re.compile(r"verdict|passable|safe|cross|can_?pass|recommend", re.IGNORECASE)
# Vehicle types, as a field name's words (camelCase and snake_case split into words).
VEHICLE_TYPE = re.compile(
    r"^(sedans?|suvs?|pickups?|vans?|trucks?|bus|buses|jeepneys?|motorcycles?|tricycles?|cars?)$",
    re.IGNORECASE,
)


def property_names(node: object) -> set[str]:
    """Every name under a `properties` key, at any depth of a JSON Schema."""
    found: set[str] = set()
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "properties" and isinstance(value, dict):
                found.update(value)
            found |= property_names(value)
    elif isinstance(node, list):
        for item in node:
            found |= property_names(item)
    return found


def words(name: str) -> list[str]:
    # snake_case, camelCase and acronyms: "SUVCount" gives SUV and Count.
    return [w for w in re.split(r"_|(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", name) if w]


def report_fields(source: str) -> set[str]:
    """The fields `GET /reports/{id}` writes: the body literal's keys, `body.<name> =`, a
    reading's keys (with `inches`), `basis`'s keys, `LINKS`' URLs and the demo fields. Each
    shape it reads must be found, so a rewrite of reports.ts fails here, never silently."""
    fields: set[str] = set()
    literal = re.search(r"const body: Record<string, unknown> = \{(.*?)\};", source, re.DOTALL)
    assert literal is not None, "reports.ts no longer builds `body` as the test reads it"
    fields.update(re.findall(r"^\s*(\w+):", literal.group(1), re.MULTILINE))
    fields.update(re.findall(r"\bbody\.(\w+)\s*=", source))
    reading = re.search(r"return \{ (id, kind, [^}]*?)(?:, \.\.\.|\})", source)
    assert reading is not None, "reports.ts no longer builds a reading as the test reads it"
    fields.update(name.strip() for name in reading.group(1).split(","))
    demo = re.search(r"DEMO_FIELDS\s*=\s*\[([^\]]*)\]", source)
    assert demo is not None, "reports.ts no longer lists DEMO_FIELDS as the test reads it"
    fields.update(re.findall(r"\"(\w+)\"", demo.group(1)))
    links = re.search(r"const LINKS = \[(.*?)\] as const;", source, re.DOTALL)
    assert links is not None, "reports.ts no longer lists LINKS as the test reads it"
    fields.update(re.findall(r"\[\"(\w+)\",", links.group(1)))
    if re.search(r"\binches: stored\.\w+", source):
        fields.add("inches")
    basis = re.search(r"body\.basis = \{ (\w+): [^,]+, (\w+): ", source)
    assert basis is not None, "reports.ts no longer builds basis as the test reads it"
    fields.update(basis.groups())
    return fields


def test_no_vehicle_verdict_in_the_schema():
    schemas = sorted(PROMPTS.glob("*.schema.json"))
    assert schemas, "no Muse Spark schema found"
    for path in schemas:
        names = property_names(json.loads(path.read_text(encoding="utf-8")))
        assert names, path.name
        assert not [n for n in names if VERDICT.search(n)], path.name

    fields = report_fields(REPORTS_TS.read_text(encoding="utf-8"))
    assert {"status", "level", "passability", "basis", "readings", "photoUrl", "credit", "vehicles", "inches"} <= fields
    assert not [f for f in fields if any(VEHICLE_TYPE.match(w) for w in words(f))]
    assert not [f for f in fields if VERDICT.search(f) and f != "passability"]


def test_the_checks_would_catch_a_verdict():
    assert property_names({"properties": {"a": {"properties": {"can_pass_sedan": {}}}}}) == {"a", "can_pass_sedan"}
    assert VERDICT.search("can_pass_sedan")
    assert any(VEHICLE_TYPE.match(w) for w in words("forSuv"))
    assert any(VEHICLE_TYPE.match(w) for w in words("jeepney_ok"))
    assert any(VEHICLE_TYPE.match(w) for w in words("SUVCount"))
    assert VERDICT.search("canPass")
    assert not any(VEHICLE_TYPE.match(w) for w in words("basis"))
