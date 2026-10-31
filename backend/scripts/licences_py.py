"""The licence check for the analysis image's Python packages (MS7 Task 8; spec §4.2, C816).

It reads the runtime packages from `requirements.lock.txt`, takes each licence from the
locked environment's package metadata, and classes it by `scripts/licence-policy.json`, the
same file and rules as `scripts/licences.mjs`:
  ok      permissive licences
  review  weak copyleft and custom licences, such as the SAM License, listed for a reviewer
  fail    strong copyleft, non-commercial, UNLICENSED, and an empty or unknown licence
A package's licence is its `License-Expression`, else the first line of its `License`, else
its `License ::` classifiers joined with OR. python-dateutil's `License` says only "Dual
License", so such a package's licences come from its classifiers too.

Run from the repo root, in the analysis package's locked environment:
  uv run --locked --directory backend/analysis python ../scripts/licences_py.py requirements.lock.txt
It prints a Markdown table of package, version, licence, where it ships and its class, then
one line per finding. Exit codes: 0 clean, 1 a `fail` licence or a package not installed at
its locked version, 2 bad usage.
"""

from __future__ import annotations

import importlib.metadata
import json
import re
import sys
from pathlib import Path

POLICY = Path(__file__).resolve().parents[2] / "scripts" / "licence-policy.json"
RANK = {"fail": 0, "review": 1, "ok": 2}
# A License field that names no licence, so the classifiers are read instead.
NOT_A_LICENCE = {"dual license"}
# The analysis image runs on Linux: these marker variables are known there, and any other
# variable (python_version, platform_machine and the like) is taken as true, so a package
# is left out only when its marker excludes Linux.
LINUX = {"sys_platform": "linux", "platform_system": "Linux", "os_name": "posix"}
REQUIREMENT = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s;\\]+)\s*(?:;\s*([^\\]*?))?\s*\\?\s*$")
MARKER_TOKEN = re.compile(r"""\s*(\(|\)|\band\b|\bor\b|'[^']*'|"[^"]*"|==|!=|<=|>=|~=|<|>|\bnot in\b|\bin\b|[A-Za-z_][A-Za-z0-9_.]*)""")


def _marker_holds_on_linux(marker: str) -> bool:
    tokens = MARKER_TOKEN.findall(marker)
    at = 0

    def peek() -> str | None:
        return tokens[at] if at < len(tokens) else None

    def take() -> str:
        nonlocal at
        at += 1
        return tokens[at - 1]

    def value(token: str) -> str | None:
        if token[:1] in "'\"":
            return token[1:-1]
        return LINUX.get(token)

    def atom() -> bool:
        if peek() == "(":
            take()
            result = either()
            take()  # ")"
            return result
        left, op, right = take(), take(), take()
        a, b = value(left), value(right)
        if a is None or b is None:
            return True  # a variable Linux doesn't fix
        return {"==": a == b, "!=": a != b, "in": a in b, "not in": a not in b}.get(op, True)

    def both() -> bool:
        result = atom()
        while peek() == "and":
            take()
            result = atom() and result
        return result

    def either() -> bool:
        result = both()
        while peek() == "or":
            take()
            result = both() or result
        return result

    try:
        return either()
    except IndexError:
        return True  # a marker this reader can't parse is kept, never dropped


def runtime_names(lock_path: Path) -> list[tuple[str, str]]:
    """The `name==version` lines of a uv-exported lock, less those whose marker excludes Linux."""
    names = []
    for line in Path(lock_path).read_text(encoding="utf-8").splitlines():
        match = REQUIREMENT.match(line.strip())
        if not match:
            continue  # a comment, a hash line, or a blank one
        name, version, marker = match.groups()
        if marker and not _marker_holds_on_linux(marker):
            continue
        names.append((name, version))
    return names


def licence_of(name: str) -> str:
    meta = importlib.metadata.metadata(name)
    expression = (meta.get("License-Expression") or "").strip()
    if expression:
        return expression
    first = next((line.strip() for line in (meta.get("License") or "").splitlines() if line.strip()), "")
    if first and first.lower() not in NOT_A_LICENCE:
        return first
    classifiers = [c.split(" :: ")[-1].strip() for c in meta.get_all("Classifier") or [] if c.startswith("License ::")]
    return " OR ".join(classifiers)


def _pattern(entry: str) -> re.Pattern[str]:
    return re.compile("^" + ".*".join(re.escape(part) for part in entry.split("*")) + "$", re.IGNORECASE | re.DOTALL)


def _lookup(mapping: dict[str, str], key: str) -> str | None:
    lower = key.lower()
    return next((value for name, value in (mapping or {}).items() if name.lower() == lower), None)


def _classify_id(licence_id: str, policy: dict) -> str:
    name = _lookup(policy.get("aliases", {}), licence_id) or licence_id
    if any(entry.lower() == name.lower() for entry in policy["ok"]):
        return "ok"
    if any(_pattern(entry).match(name) for entry in policy["fail"]):
        return "fail"
    if any(_pattern(entry).match(name) for entry in policy["review"]):
        return "review"
    return "fail"  # unknown


def classify(expr: str, policy: dict) -> str:
    """'ok', 'review' or 'fail', by the same rules as `classify` in scripts/licences.mjs."""
    text = (expr or "").strip()
    if not text:
        return "fail"
    whole = _lookup(policy.get("aliases", {}), text) or text
    if not re.search(r"\s(?:AND|OR|WITH)\s", whole, re.IGNORECASE):
        return _classify_id(whole, policy)
    # Split at the operators and parentheses only, so a name with spaces stays one leaf.
    tokens = [t.strip() for t in re.split(r"(\(|\)|\s+(?:AND|OR|WITH)\s+)", whole, flags=re.IGNORECASE) if t and t.strip()]
    at = 0

    def peek() -> str | None:
        return tokens[at].upper() if at < len(tokens) else None

    def atom() -> str:
        nonlocal at
        if at < len(tokens) and tokens[at] == "(":
            at += 1
            inner = either()
            if at >= len(tokens) or tokens[at] != ")":
                raise SyntaxError("unclosed (")
            at += 1
            return inner
        if at >= len(tokens) or tokens[at] == ")" or tokens[at].upper() in {"AND", "OR", "WITH"}:
            raise SyntaxError("expected a licence")
        licence_id = tokens[at]
        at += 1
        if peek() == "WITH":
            at += 1
            if at >= len(tokens):
                raise SyntaxError("expected an exception")
            at += 1
        return _classify_id(licence_id, policy)  # an exception never makes a licence better

    def both() -> str:
        nonlocal at
        result = atom()
        while peek() == "AND":
            at += 1
            result = min(result, atom(), key=RANK.__getitem__)
        return result

    def either() -> str:
        nonlocal at
        result = both()
        while peek() == "OR":
            at += 1
            result = max(result, both(), key=RANK.__getitem__)
        return result

    try:
        result = either()
    except SyntaxError:
        return "fail"
    return result if at == len(tokens) else "fail"


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1 or args[0].startswith("-"):
        print("usage: licences_py.py REQUIREMENTS_LOCK", file=sys.stderr)
        return 2
    lock = Path(args[0])
    try:
        names = runtime_names(lock)
        policy = json.loads(POLICY.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        print(f"licences_py: {error.__class__.__name__} reading the lock or the policy", file=sys.stderr)
        return 2
    print("| package | version | licence | ships in | class |")
    print("|---|---|---|---|---|")
    findings = []
    notes = []
    for name, version in names:
        try:
            installed = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            findings.append(f"FAIL: {name}=={version} is not installed")
            continue
        if installed != version:
            findings.append(f"FAIL: {name}=={version} is installed at {installed}")
            continue
        licence = licence_of(name)
        cls = classify(licence, policy)
        print(f"| {name} | {version} | {licence or '(none)'} | analysis image | {cls} |")
        if cls == "fail":
            findings.append(f"FAIL: {name}=={version} ({licence or 'no licence'})")
        elif cls == "review":
            notes.append(f"REVIEW: {name}=={version} ({licence})")
    print()
    for line in notes + findings:
        print(line)
    print(f"licences_py: {len(names)} runtime packages: {f'{len(findings)} finding(s)' if findings else 'clean'}")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
