# /// script
# requires-python = ">=3.13,<3.14"
# dependencies = []
# ///
r"""Check Rene's logs before the split (spec §5.3, C201, C204, C208, C218).

The intake reads his Set A and A-neg logs and, when given, his M8 export and the
consented items' and sidewall photos' logs. It looks for each file they name with a
stat, never reading its bytes (C201), works out each Set A photo's match, and groups
each set's flood events (C203). It prints only ids, row and column numbers, column
names, fixed kinds and counts, never a label, spot, link or note (C201). It writes no
file.

Usage, from the repo root (Claude runs it, any time before the split):
    uv run --locked --script eval/data/intake.py
        --set-a-log <data>\set_a\set_a_log.csv --set-a-photos <data>\set_a\raw
        --a-neg-log <data>\a_neg\a_neg_log.csv --a-neg-photos <data>\a_neg\raw
        [--m8 <data>\set_a\m8_labels.csv]
        [--consented <data>\consented\consented_log.csv]
        [--sidewalls <data>\sidewalls\sidewalls.csv]
It prints, in order:
    set_a rows=<r> photos=<p> no_class=<k>
    a_neg rows=<r> photos=<p>
    m8 rows=<n> photo_rows=<k>                    with --m8
    each problem, then each warning
    events set_a=<n> largest=<k> single=<m>
    events a_neg=<n> largest=<k> single=<m>
    problems=<n> warnings=<m>
no_class counts the Set A photos whose stated passability maps to no class, so C204
can't count them as deep. A problem prints as <id> <column>: <kind> and a warning as
<id> <fact>=<value>, and a ref that names no id starts with its log's name, as in
set_a row 3 or a_neg log column 18 (Task 7's M7). The events come from the logs' text
alone, so photos posted twice aren't joined yet: the split joins them.

Exit codes: 0 no problem; 1 a problem, or a log that can't be found, decoded as UTF-8
or read whole, for which only its finding prints; 2 a usage error, or a path inside a
folder named sealed (C222).
"""

import argparse
import sys
from collections import Counter
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import events
import guards
import otherlogs
import setlogs
import strata
import table
from otherlogs import M8Check
from setlogs import Photo, SetCheck
from table import Fact, Finding


@dataclass
class IntakeResult:
    """Each set's check, M8's when it is given and read, and the problems and warnings
    of every log, in the order the logs are read. A ref that names no id starts with
    its log's name."""

    set_a: SetCheck
    a_neg: SetCheck
    m8: M8Check | None
    problems: list[Finding]
    warnings: list[Fact]


def run_intake(
    *,
    set_a_log: Path,
    set_a_photos: Path,
    a_neg_log: Path,
    a_neg_photos: Path,
    m8: Path | None = None,
    consented: Path | None = None,
    sidewalls: Path | None = None,
    allow_missing_m8: bool = False,
) -> IntakeResult:
    """Check the logs given (spec §5.3). The split reuses this.

    Every path is refused first if a part of it names sealed (C222). The logs are then
    read in this order: Set A, A-neg, M8 against Set A's photos, the consented items and
    the sidewall photos. M8 is read only when Set A's log has all its columns, since
    without them there are no photos to check it against (S-R11's M3).

    A log that can't be found, decoded as UTF-8 or read whole raises table.MalformedCsv,
    and no later log is read. Its finding is led by the log's name: set_a log:
    file_missing, set_a log: not_utf8, or one that names a row or a header column, such
    as set_a row 4 cells: too_many.
    """
    others = [path for path in (m8, consented, sidewalls) if path is not None]
    guards.refuse_sealed(set_a_log, set_a_photos, a_neg_log, a_neg_photos, *others)
    with _log_named("set_a"):
        set_a = setlogs.check_set_log(set_a_log, set_a_photos, set_name="A")
    with _log_named("a_neg"):
        a_neg = setlogs.check_set_log(a_neg_log, a_neg_photos, set_name="A-neg")
    problems = [_named("set_a", problem) for problem in set_a.problems]
    problems += [_named("a_neg", problem) for problem in a_neg.problems]
    warnings = set_a.warnings + a_neg.warnings
    m8_check = None
    if m8 is not None and "missing_column" not in {p.kind for p in set_a.problems}:
        set_a_ids = [photo.photo_id for photo in set_a.photos]
        with _log_named("m8"):
            m8_check = otherlogs.check_m8(m8, set_a_ids, allow_missing=allow_missing_m8)
        problems += m8_check.problems
    for name, path, check in (
        ("consented", consented, otherlogs.check_consented),
        ("sidewalls", sidewalls, otherlogs.check_sidewalls),
    ):
        if path is not None:
            with _log_named(name):
                found, facts = check(path)
            problems += found
            warnings += facts
    return IntakeResult(set_a, a_neg, m8_check, problems, warnings)


@contextmanager
def _log_named(log: str) -> Iterator[None]:
    """Raise again, as a MalformedCsv whose finding is led by the log's name, the error
    from a log that can't be found (file_missing), decoded as UTF-8 (not_utf8) or read
    whole (S-R11's M2). The finding holds fixed words only, never a path or a text."""
    try:
        yield
    except table.MalformedCsv as error:
        raise table.MalformedCsv(_named(log, error.args[0])) from None
    except FileNotFoundError:
        raise table.MalformedCsv(Finding(log, "log", "file_missing")) from None
    except UnicodeDecodeError:
        raise table.MalformedCsv(Finding(log, "log", "not_utf8")) from None


def _named(log: str, finding: Finding) -> Finding:
    """The finding with the log's name before a ref that names no id, such as row 3,
    log or header (Task 7's M7). A ref made by id stays as it is."""
    if table.is_id(finding.ref):
        return finding
    return Finding(f"{log} {finding.ref}", finding.column, finding.kind)


def _event_counts(photos: Sequence[Photo]) -> tuple[int, int, int]:
    """The number of events, the largest one's photos and the one-photo events, grouped
    from the log's text alone (C203)."""
    rows = [
        events.EventInput(
            photo.photo_id, photo.event_date, photo.spot_key, photo.same_spot_as
        )
        for photo in photos
    ]
    sizes = list(Counter(events.group_events(rows).values()).values())
    return len(sizes), max(sizes, default=0), sizes.count(1)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check Rene's logs before the split, printing only ids, kinds and "
        "counts (C201)."
    )
    parser.add_argument("--set-a-log", required=True, type=Path, help="Set A's log")
    parser.add_argument(
        "--set-a-photos", required=True, type=Path, help="Set A's raw photos folder"
    )
    parser.add_argument("--a-neg-log", required=True, type=Path, help="A-neg's log")
    parser.add_argument(
        "--a-neg-photos", required=True, type=Path, help="A-neg's raw photos folder"
    )
    parser.add_argument("--m8", type=Path, help="Rene's M8 export, m8_labels.csv")
    parser.add_argument("--consented", type=Path, help="the consented items' log (M9)")
    parser.add_argument("--sidewalls", type=Path, help="the sidewall photos' log (M11)")
    args = parser.parse_args(argv)
    try:
        result = run_intake(
            set_a_log=args.set_a_log,
            set_a_photos=args.set_a_photos,
            a_neg_log=args.a_neg_log,
            a_neg_photos=args.a_neg_photos,
            m8=args.m8,
            consented=args.consented,
            sidewalls=args.sidewalls,
        )
    except table.MalformedCsv as error:
        print(error.args[0])
        return 1

    set_a, a_neg = result.set_a, result.a_neg
    no_class = sum(
        strata.class_of(photo.passability_raw) is None for photo in set_a.photos
    )
    print(f"set_a rows={set_a.rows} photos={len(set_a.photos)} no_class={no_class}")
    print(f"a_neg rows={a_neg.rows} photos={len(a_neg.photos)}")
    if result.m8 is not None:
        photo_rows = sum(row.get("kind") == "photo" for row in result.m8.rows)
        print(f"m8 rows={len(result.m8.rows)} photo_rows={photo_rows}")
    for item in [*result.problems, *result.warnings]:
        print(item)
    for name, check in (("set_a", set_a), ("a_neg", a_neg)):
        count, largest, single = _event_counts(check.photos)
        print(f"events {name}={count} largest={largest} single={single}")
    print(f"problems={len(result.problems)} warnings={len(result.warnings)}")
    return 1 if result.problems else 0


if __name__ == "__main__":
    sys.exit(guards.quiet(main))
