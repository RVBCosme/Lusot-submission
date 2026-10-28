"""The committed records (C216, spec §5.9): their kinds, their fields, and how they are
written. Every record's format comes from here.

A record holds counts and hashes only, never an id, a label, a link, a spot, a location
or a photo (§5.9). It is JSON with sorted keys, a two-space indent, ASCII only and a
final newline, and is created once and never rewritten. Each builder gives the record a
sealing step writes into its archive. The committed record adds the archive's block,
and the split's adds its copy check too.

The audit, seal_set_d, water_check and freeze_record import this module, and their
environments hold no numpy, OpenCV or py7zr. So it loads only the standard library and
MS2's standard-library modules: archive's name is imported for annotations only.
"""

from __future__ import annotations

import json
import platform
import re
import subprocess
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from pathlib import Path
from typing import TYPE_CHECKING

import draw
import manifest
import table

if TYPE_CHECKING:
    from archive import ArchiveFacts

# Each record kind, by the tool that writes it. The audit reads a record's kind from
# its tool (C220).
RECORD_KINDS = {
    "eval/data/split.py": "split",
    "eval/set_b/generate.py": "set_b_final",
    "eval/data/seal_set_d.py": "set_d",
}
# Manila keeps +08:00 all year. zoneinfo would need the tzdata package on Windows.
_MANILA = timezone(timedelta(hours=8))
_GIT_SECONDS = 30
_COMMIT = re.compile(r"[0-9a-f]{40}")


def record_kind(record: Mapping) -> str:
    """split, set_b_final or set_d, from the record's tool. A record with any other
    tool, or none, raises ValueError, whose message holds no text of the record's."""
    tool = record.get("tool")
    if not isinstance(tool, str) or tool not in RECORD_KINDS:
        raise ValueError("the record's tool has no record kind")
    return RECORD_KINDS[tool]


def git_state(repo: Path) -> dict:
    """{"commit", "dirty"}: the commit checked out in repo, and whether the tree differs
    from it, an untracked file included.

    git runs in repo with a timeout, and its output is captured, never printed. When it
    fails or times out, as outside a repo, the commit is unknown and the tree counts as
    dirty, so a record never claims a clean tree it couldn't check.
    """
    try:
        head = _git(repo, "rev-parse", "HEAD").decode("ascii", "replace").strip()
        dirty = bool(_git(repo, "status", "--porcelain").strip())
    except (OSError, subprocess.SubprocessError):  # no git, an error or a timeout
        return {"commit": "unknown", "dirty": True}
    if _COMMIT.fullmatch(head) is None:
        return {"commit": "unknown", "dirty": True}
    return {"commit": head, "dirty": dirty}


def _git(repo: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        timeout=_GIT_SECONDS,
        check=True,
    ).stdout


def manila_now() -> str:
    """The time in Manila now, ISO 8601 to the second: 2026-10-30T21:05:09+08:00."""
    return datetime.now(_MANILA).isoformat(timespec="seconds")


def base_record(tool: str, repo: Path) -> dict:
    """The fields every record starts with: the tool that writes it, as a path from the
    repo root, the repo's git state, the date, and the Python version."""
    return {
        "tool": tool,
        "git": git_state(repo),
        "date": manila_now(),
        "python": platform.python_version(),
    }


def archive_block(facts: ArchiveFacts) -> dict:
    """The archive's bare file name, its size in bytes and its SHA-256, which the sealed
    run checks before anything else (C220)."""
    return {"file": facts.file, "size": facts.size, "sha256": facts.sha256}


def record_bytes(record: Mapping) -> bytes:
    """The record's bytes, the same whatever its keys' order."""
    text = json.dumps(record, sort_keys=True, ensure_ascii=True, indent=2)
    return (text + "\n").encode("ascii")


def write_record(path: Path, record: Mapping) -> str:
    """Create the record's file, and any missing folders, and return its SHA-256.

    An existing file raises FileExistsError and keeps its bytes. The path may be
    relative, since Rene's commands give records from the repo root (S-R13).
    """
    return table.write_new(path, record_bytes(record))


def split_record(
    *,
    repo: Path,
    inputs: Mapping[str, str],
    draws: Mapping[str, Mapping[str, draw.GroupDraw]],
    sides: Mapping[str, Mapping[str, Sequence[Mapping[str, str]]]],
    missing_m8: int,
    dev_files: Mapping[str, str],
) -> dict:
    """The split's record (C204), which the split also writes into its archive.

    inputs holds the SHA-256 of set_a_log, a_neg_log and m8, and dev_files that of
    set_a_manifest, set_a_m8 and a_neg_manifest. draws and sides go by set, A or A-neg:
    draws to each group's draw, sides to the dev and sealed manifest rows.

    For each set, the record holds each side's counts, the share, the sealed rows over
    all the set's rows as an unreduced k/n, and whether it lies between the set's target
    and cap, both included and compared exactly. A float 0.4 lies above 2/5, so 8 of 20
    rows would read as out of range. Each group holds its events and rows, in all and
    per side, and its move. No event id is recorded.
    """
    sets = {}
    for set_name, rows in sides.items():
        dev, sealed = manifest.counts(rows["dev"]), manifest.counts(rows["sealed"])
        total = dev["rows"] + sealed["rows"]
        target, cap = draw.SHARES[set_name]
        sets[set_name] = {
            "dev": dev,
            "sealed": sealed,
            "share": f"{sealed['rows']}/{total}",
            "share_in_range": target <= Fraction(sealed["rows"], total) <= cap,
            "groups": {
                group: _group_counts(found) for group, found in draws[set_name].items()
            },
        }
    return base_record("eval/data/split.py", repo) | {
        "seed": draw.SPLIT_SEED,
        "inputs": dict(inputs),
        "sets": sets,
        "missing_m8_photo_rows": missing_m8,
        "audit": "PASS",
        "dev_files": dict(dev_files),
    }


def _group_counts(found: draw.GroupDraw) -> dict:
    return {
        "events": len(found.dev) + len(found.sealed),
        "rows": found.rows,
        "dev": {"events": len(found.dev), "rows": found.rows - found.sealed_rows},
        "sealed": {"events": len(found.sealed), "rows": found.sealed_rows},
        "moved": found.moved,
    }


def set_b_final_record(
    *,
    repo: Path,
    counts: Mapping,
    generator_version: str,
    generator_seed: int,
    inputs: Mapping[str, str],
) -> dict:
    """Set B's final-car record (C214), which generate --final also writes into its
    archive.

    inputs holds the SHA-256 of the final cars.csv, the final masks' files.txt and the
    development cars.csv. counts holds cars, photos, crops, wheels and
    wheels_without_rim, drops by cause, warnings, and the crops by band, size_bin,
    vehicle_type and view. cars and crops count only what reaches truth.csv, and a
    dropped car counts under drops alone, so the sealed run's audit can match them.
    Both are recorded as given, so neither may hold a car, crop or photo id.
    """
    return base_record("eval/set_b/generate.py", repo) | {
        "generator_version": generator_version,
        "generator_seed": generator_seed,
        "inputs": dict(inputs),
        "counts": dict(counts),
        "overlap_check": "PASS",
    }


def set_d_record(
    *,
    repo: Path,
    counts: Mapping,
    inputs: Mapping[str, str],
    extends: Mapping | None,
) -> dict:
    """Set D's record (C217), which seal_set_d also writes into its archive.

    inputs holds the SHA-256 of set_d_log.csv, and counts the photos, by vehicle_type
    and by wheel, both recorded as given, so neither may hold an id. extends, when
    given, names the freeze record this one extends by its file and SHA-256 (C216).
    """
    record = base_record("eval/data/seal_set_d.py", repo) | {
        "inputs": dict(inputs),
        "counts": dict(counts),
    }
    if extends is not None:
        record["extends"] = dict(extends)
    return record
