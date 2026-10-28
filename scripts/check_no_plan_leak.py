"""Check that no plan text or plan account detail has entered the repo (build design C4).

The plan's text copy stays outside every repo, so this script reads it from
staging at run time. It prints file names and counts only, never the matched
text, so the check itself can't leak what it looks for.

Usage: python scripts/check_no_plan_leak.py [PLAN_TEXT_PATH]   (or set LUSOT_PLAN_TEXT)
Exit codes: 0 clean, 1 leak found, 2 bad usage, or a plan path that is missing, unreadable or empty
(the check fails closed).
Only when CI=true and the default plan path is missing does it print a notice and exit 0,
because the CI runner has no plan text by design.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

DEFAULT_PLAN = Path(r"C:\Systems\Lusot\Lusot-Staging\docs\plan\lusot-build-plan.txt")
MIN_LINE = 60  # plan lines at least this long count as plan text
MAX_SHARED_LINES = 5  # more than this many plan lines in one file looks like a paste
ACCOUNT_SECTION = re.compile(r"^\s*24\. Manual actions", re.M)
NEXT_SECTION = re.compile(r"^\s*25\. ", re.M)
LONG_NUMBER = re.compile(r"(?<!\d)\d{8,}(?!\d)")


def repo_files() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "-c", "-o", "--exclude-standard"],
        check=True, capture_output=True, text=True,
    ).stdout
    return [Path(p) for p in out.splitlines() if p]


def fail_closed(message: str) -> int:
    print(message, file=sys.stderr)
    return 2


def main() -> int:
    args = sys.argv[1:]
    if len(args) > 1 or any(a.startswith("-") for a in args):
        return fail_closed("usage: check_no_plan_leak.py [PLAN_TEXT_PATH]  (or set LUSOT_PLAN_TEXT)")
    explicit = args[0] if args else os.environ.get("LUSOT_PLAN_TEXT")
    plan_path = Path(explicit) if explicit is not None else DEFAULT_PLAN
    if not plan_path.is_file():
        if explicit is None and os.environ.get("CI") == "true":  # the CI runner has no plan text by design
            print(f"plan text not found at {plan_path}; skipping the plan-leak check")
            return 0
        return fail_closed(f"plan text not found at {plan_path}")
    try:
        plan = plan_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return fail_closed(f"plan text at {plan_path} is not readable")
    start = ACCOUNT_SECTION.search(plan)
    end = NEXT_SECTION.search(plan, start.end()) if start else None
    section24 = plan[start.start(): end.start()] if start and end else ""
    secrets = set(LONG_NUMBER.findall(section24))
    plan_lines = {ln.strip() for ln in plan.splitlines() if len(ln.strip()) >= MIN_LINE}
    if not plan_lines:  # an empty or wrong file would pass vacuously
        return fail_closed(f"plan text at {plan_path} has no line of {MIN_LINE}+ characters, so it can't be the plan")

    leaks = 0
    for path in repo_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        hits = sum(1 for s in secrets if s in text)
        if hits:
            print(f"LEAK: {path} contains {hits} account-detail number(s) from plan section 24")
            leaks += 1
        shared = sum(1 for ln in plan_lines if ln in text)
        if shared > MAX_SHARED_LINES:
            print(f"LEAK: {path} shares {shared} whole lines with the plan (limit {MAX_SHARED_LINES})")
            leaks += 1
    print(f"checked {len(repo_files())} files against {len(secrets)} section-24 numbers and {len(plan_lines)} plan lines: "
          + ("clean" if not leaks else f"{leaks} problem(s)"))
    return 1 if leaks else 0


if __name__ == "__main__":
    raise SystemExit(main())
