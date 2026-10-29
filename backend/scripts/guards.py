"""The operator scripts' shared guards and helpers (MS4 spec §4.5, §4.7, C66; Task 8).

- **The sealed-path rule,** in one copy: a path with a part naming `sealed`, in any
  case and in the forms Windows opens as that folder (R156), as written (made
  absolute) or resolved, so `..` and links can't hide one. Every script that reads
  lusot-data refuses one before reading anything (exit 2).
- **The output mask:** every printed line has each run of 12 digits replaced by
  `<account>`. Scripts print counts, outcomes and ids through `say`, never a path, a
  coordinate, a message body, a receipt handle, a queue URL, an IP or an email.
- **The one allow-list** (spec §4.5): demo pins and samples come only from the
  open-licensed manifest's rows that pass `open_licence_ok` and the consent log's rows
  that pass `consent_ok`, read by `allowed_sources`. More consented photos arrive as
  rows in the same log, so no code changes. Set A photos never become either: no
  function here reads a Set A or A-neg folder.

Beside them, the few helpers every script shares: the stack's outputs, the reports by
id, and how an error and a count are printed. Standard library only, and AWS clients
come in as arguments, so a script that imports it keeps its own header and lock.
"""

from __future__ import annotations

import csv
import importlib.util
import os
import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PureWindowsPath
from typing import Literal

STACK = "lusot"  # samconfig's stack_name
INDEX_NAME = "reportId-index"  # the reports table's, in the template
DATA_DIR = r"C:\Systems\Lusot\lusot-data"  # when LUSOT_DATA_DIR is unset
# MS2's formats module, which imports only the standard library (C218).
FORMATS_PY = Path(__file__).resolve().parents[2] / "eval" / "data" / "formats.py"
OPEN_MANIFEST = ("set_c", "open-licensed-ph", "open_licensed_manifest.csv")
CONSENT_LOG = ("consented", "consented_log.csv")
# MS5's C617 pattern: CC0 or CC BY of any version, so no SA, NC, ND or PD mark.
OPEN_LICENCES = re.compile(r"(CC0( 1\.0)?|CC BY \d(\.\d)?)")
# The donor messages that ask for every use together, the sample and the labelled demo
# pin among them, so a reply on file is the demo OK (spec §4.5). Only M9-v4 (the
# tracker's call, Oct 29, 10:31 PM). A version that makes any use optional needs its
# own rule before it joins.
FOUR_USE_VERSIONS = frozenset({"M9-v4"})
# Every credit ends with CC BY's change note (C523). Rene reviews both lines (M20).
CHANGE_NOTE = "Faces and plates blurred, and outlines drawn, by Lusot."
CONSENT_CREDIT = "Photo used with its owner's permission."
CONSENT_LICENSE = "used with permission"  # the exact value MS5's getSamples keeps
_ACCOUNT_ID = re.compile(r"[0-9]{12}")
_REPORT_ID = re.compile(r"(r_[0-9a-f]{32})")
_DAY = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


def is_sealed(path: Path) -> bool:
    """Whether `path` has a part naming sealed, as written or resolved.

    A part names it in any case, with an NTFS stream suffix dropped and trailing dots
    and spaces stripped, since Windows opens the folder itself for `sealed.`,
    `sealed ` and `sealed::$INDEX_ALLOCATION` (R156, as MS2's guard and the MS6
    harness read it). A drive part such as `C:\\` reads as `C`. The path is checked as
    written, made absolute, so a path that names the folder never reaches the disk,
    then resolved, so `..` and links can't hide the folder.
    """

    def inside(checked: Path) -> bool:
        return any(
            part.split(":", 1)[0].rstrip(". ").casefold() == "sealed"
            for part in checked.parts
        )

    return inside(path.absolute()) or inside(path.resolve())


def refuse_sealed(*paths: Path) -> None:
    """Exit 2 if any of `paths` is sealed, before anything is opened or listed."""
    if any(is_sealed(path) for path in paths):
        say("refused: a path inside a folder named sealed")
        raise SystemExit(2)


def mask(line: str) -> str:
    """`line` with each run of 12 digits, an account ID's length, as <account>.

    Report ids (C32's `r_` and 32 hex digits) pass whole: they are random, so about 1
    in 14 holds a 12-digit run, and the scripts print them for the operator to use.
    """
    parts = _REPORT_ID.split(line)  # the ids at odd places
    return "".join(
        part if n % 2 else _ACCOUNT_ID.sub("<account>", part)
        for n, part in enumerate(parts)
    )


def say(line: str) -> None:
    print(mask(line), flush=True)


def failure(exc: BaseException) -> str:
    """An error as the scripts print it: an AWS error's code and HTTP status, or the
    class name. Never a message, which can hold an ARN, a path or a URL."""
    response = getattr(exc, "response", None)
    if isinstance(response, dict) and "Error" in response:
        code = response["Error"].get("Code")
        status = response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        return f"AWS error in {exc.operation_name}: {code} (HTTP {status})"
    return type(exc).__name__


def data_dir() -> Path:
    return Path(os.environ.get("LUSOT_DATA_DIR") or DATA_DIR)


def stack_outputs(session) -> dict[str, str]:
    """The lusot stack's outputs, by key: names and the API's URL, never a queue URL."""
    cloudformation = session.client("cloudformation")
    [stack] = cloudformation.describe_stacks(StackName=STACK)["Stacks"]
    return {o["OutputKey"]: o["OutputValue"] for o in stack.get("Outputs", [])}


def items_by_id(ddb, table: str, report_id: str) -> list[dict]:
    """Every item with this report id, from reportId-index, every page.

    A global secondary index is eventually consistent only (Context7, DynamoDB's
    developer guide), so it can lag a write by a moment.
    """
    pages = ddb.get_paginator("query").paginate(
        TableName=table,
        IndexName=INDEX_NAME,
        KeyConditionExpression="#reportId = :id",
        ExpressionAttributeNames={"#reportId": "reportId"},
        ExpressionAttributeValues={":id": {"S": report_id}},
    )
    return [item for page in pages for item in page["Items"]]


def counts(counter: Counter) -> str:
    """A counter as the scripts print it: "1 a, 2 b", by name."""
    return ", ".join(f"{n} {name}" for name, n in sorted(counter.items()))


def yes(flag: bool) -> str:
    return "yes" if flag else "no"


def open_licence_ok(row: dict[str, str]) -> bool:
    """An open-licensed manifest row may be shown: demo_use ok, not share-alike, and
    CC0 or CC BY (C617)."""
    return (
        (row.get("demo_use") or "").strip() == "ok"
        and (row.get("share_alike") or "").strip() == "no"
        and OPEN_LICENCES.fullmatch(row.get("license") or "") is not None
    )


def consent_ok(row: dict[str, str], approved: frozenset[str]) -> bool:
    """A consent log row may be used: a photo with its OK on file, answering a
    four-use version that Rene has approved."""
    version = (row.get("consent_version") or "").strip()
    return (
        (row.get("kind") or "").strip() == "photo"
        and bool((row.get("consent_file") or "").strip())
        and version in FOUR_USE_VERSIONS
        and version in approved
    )


def approved_m9_versions(path: Path | None = None) -> frozenset[str]:
    """MS2's APPROVED_CONSENT["m9"] (C218), loaded from formats.py by path.

    Empty until Rene approves a text, and while the file isn't on the branch, so no
    consented photo is used before then.
    """
    path = FORMATS_PY if path is None else path
    if not path.is_file():
        return frozenset()
    spec = importlib.util.spec_from_file_location("lusot_ms2_formats", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return frozenset(module.APPROVED_CONSENT.get("m9", ()))


@dataclass(frozen=True)
class Source:
    """One allowed photo: an open-licensed manifest row or a consent log row."""

    source_id: str
    kind: Literal["open", "consented"]
    photo: Path
    row: dict[str, str]

    def _field(self, name: str) -> str:
        return (self.row.get(name) or "").strip()

    @property
    def credit(self) -> str:
        """The credit line, or the consent line, ending with CHANGE_NOTE."""
        line = self._field("credit_line") if self.kind == "open" else CONSENT_CREDIT
        return f"{line if line.endswith('.') else line + '.'} {CHANGE_NOTE}"

    @property
    def license(self) -> str:
        return self._field("license") if self.kind == "open" else CONSENT_LICENSE

    @property
    def place(self) -> str:
        return self._field("place" if self.kind == "open" else "place_text")

    @property
    def date(self) -> str:
        """The capture date, YYYY-MM-DD, or "" when the source gives none."""
        day = self._field("date_taken" if self.kind == "open" else "taken_pht")[:10]
        if _DAY.fullmatch(day) is None:
            return ""
        try:
            datetime.strptime(day, "%Y-%m-%d")  # a real date, not 2023-02-30
        except ValueError:
            return ""
        return day

    @property
    def event(self) -> str:
        """The event, when the source names one. MS2's log has no such column."""
        return self._field("event")

    @property
    def note(self) -> str:
        """The private source note, for lusot-data's sample_sources.csv only."""
        return self._field("source_note" if self.kind == "consented" else "source_page")


def _rows(path: Path) -> list[dict[str, str]]:
    """A CSV's rows, or none when it doesn't exist. utf-8-sig: Windows writes a BOM."""
    refuse_sealed(path)
    if not path.is_file():
        return []
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def allowed_sources(
    ids: Iterable[str], approved: frozenset[str]
) -> tuple[dict[str, Source], Counter]:
    """The allowed sources among `ids`, in order, and the others counted by cause.

    It reads data_dir()'s open-licensed manifest and consent log, once each. Causes:
    not_on_allow_list (in neither file, or failing its row rule), consent_not_approved
    (a four-use reply whose version Rene hasn't approved) and no_credit (an
    open-licensed row without the credit line CC BY needs). A photo is opened by its
    listed file's base name beside its file, so no path from a data file is trusted.
    """
    base = data_dir()
    open_path, consent_path = base.joinpath(*OPEN_MANIFEST), base.joinpath(*CONSENT_LOG)
    refuse_sealed(base, open_path, consent_path)
    # The first row for an id wins.
    open_rows = {row["id"]: row for row in reversed(_rows(open_path))}
    consented = {row["item_id"]: row for row in reversed(_rows(consent_path))}
    found: dict[str, Source] = {}
    refused: Counter = Counter()
    for source_id in ids:
        if source_id in open_rows:
            row = open_rows[source_id]
            if not open_licence_ok(row):
                refused["not_on_allow_list"] += 1
            elif not (row.get("credit_line") or "").strip():
                refused["no_credit"] += 1
            else:
                photo = open_path.parent / PureWindowsPath(row["filename"]).name
                found[source_id] = Source(source_id, "open", photo, row)
        elif source_id in consented:
            row = consented[source_id]
            if consent_ok(row, approved):
                photo = consent_path.parent / PureWindowsPath(row["file"]).name
                found[source_id] = Source(source_id, "consented", photo, row)
            elif consent_ok(row, FOUR_USE_VERSIONS):
                refused["consent_not_approved"] += 1
            else:
                refused["not_on_allow_list"] += 1
        else:
            refused["not_on_allow_list"] += 1
    return found, refused
