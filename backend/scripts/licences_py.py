"""The licence check for the analysis image's Python packages (MS7 Task 8; spec §4.2, C816).

It reads the runtime packages from `requirements.lock.txt`, takes each licence from the
locked environment's package metadata, and classes it by `scripts/licence-policy.json`, the
same file and rules as `scripts/licences.mjs`:
  ok      permissive licences
  review  weak copyleft and custom licences, such as the SAM License, listed for a reviewer
  fail    strong copyleft, non-commercial, UNLICENSED, and an empty or unknown licence
A package's licence is its `License-Expression`, else the first line of its `License`, else
its `License ::` classifiers joined with OR. A `License` of "Dual License" (python-dateutil's)
or "UNKNOWN" names no licence, so such a package's classifiers are read instead.

Run from the repo root, in the analysis package's locked environment:
  uv run --locked --directory backend/analysis python ../scripts/licences_py.py requirements.lock.txt
It prints a Markdown table of package, version, licence, where it ships and its class, then
one line per finding. Exit codes: 0 clean, 1 a `fail` licence or a package not installed at
its locked version, 2 bad usage, or a lock line this tool can't read.
"""

from __future__ import annotations

import importlib.metadata
import json
import platform
import re
import sys
from pathlib import Path

POLICY = Path(__file__).resolve().parents[2] / "scripts" / "licence-policy.json"
RANK = {"fail": 0, "review": 1, "ok": 2}
OPERATOR = re.compile(r"\s(?:AND|OR|WITH)\s")
PRINTABLE = re.compile(r"[\x20-\x7e\t]*")
# A License field that names no licence, so the classifiers are read instead.
NOT_A_LICENCE = {"dual license", "unknown"}
# The analysis image runs this Python on Linux, so these marker variables are known: the
# platform's from Linux, the interpreter's from the one running this check (the locked
# environment's, the image's version). Any other variable is taken as true, so a package is
# left out only when its marker excludes it.
LINUX = {"sys_platform": "linux", "platform_system": "Linux", "os_name": "posix"}
INTERPRETER = {
    "python_version": f"{sys.version_info[0]}.{sys.version_info[1]}",
    "python_full_version": platform.python_version(),
    "implementation_name": sys.implementation.name,
    "platform_python_implementation": platform.python_implementation(),
}
VERSIONED = {"python_version", "python_full_version"}
REQUIREMENT = re.compile(
    r"^([A-Za-z0-9][A-Za-z0-9._-]*)(?:\[[A-Za-z0-9._,\s-]*\])?==([^\s;\\]+)\s*(?:;\s*([^\\]*?))?\s*\\?\s*$"
)
MARKER_TOKEN = re.compile(
    r"""\s*(\(|\)|\band\b|\bor\b|'[^']*'|"[^"]*"|==|!=|<=|>=|~=|<|>|\bnot in\b|\bin\b|[A-Za-z_][A-Za-z0-9_.]*)"""
)


class LockLineError(ValueError):
    """A lock line that isn't blank, a comment, a hash continuation or `name==version`."""


def _version_key(text: str) -> tuple:
    return tuple(
        int(part) if part.isdigit() else part for part in re.split(r"[.]", text)
    )


def _compare(op: str, a: str, b: str, versioned: bool) -> bool | None:
    if op in {"in", "not in"}:
        return (a in b) if op == "in" else (a not in b)
    x, y = (_version_key(a), _version_key(b)) if versioned else (a, b)
    try:
        return {
            "==": x == y,
            "!=": x != y,
            "<": x < y,
            "<=": x <= y,
            ">": x > y,
            ">=": x >= y,
        }.get(op)
    except TypeError:
        return None  # parts that don't compare, such as "13" against "rc1"


def _marker_holds(marker: str) -> bool:
    tokens = MARKER_TOKEN.findall(marker)
    at = 0

    def peek() -> str | None:
        return tokens[at] if at < len(tokens) else None

    def take() -> str:
        nonlocal at
        at += 1
        return tokens[at - 1]

    def value(token: str) -> tuple[str | None, bool]:
        if token[:1] in "'\"":
            return token[1:-1], False
        known = LINUX.get(token, INTERPRETER.get(token))
        return known, token in VERSIONED

    def atom() -> bool:
        if peek() == "(":
            take()
            result = either()
            if take() != ")":
                raise IndexError("unclosed (")
            return result
        left, op, right = take(), take(), take()
        (a, va), (b, vb) = value(left), value(right)
        if a is None or b is None:
            return True  # a variable this check doesn't fix
        result = _compare(op, a, b, va or vb)
        return True if result is None else result

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
        result = either()
    except IndexError:
        return True  # a marker this reader can't parse is kept, never dropped
    return result if at == len(tokens) else True


def runtime_names(lock_path: Path) -> list[tuple[str, str]]:
    """The `name==version` lines of a uv-exported lock, less those whose marker excludes them.

    Any other line that isn't blank, a comment or a `--hash` continuation raises
    LockLineError, so a package pinned some other way (a URL, a path, `-e`) can't drop out.
    """
    names = []
    for number, line in enumerate(
        Path(lock_path).read_text(encoding="utf-8").splitlines(), 1
    ):
        text = line.strip()
        if not text or text.startswith(("#", "--hash")):
            continue
        match = REQUIREMENT.match(text)
        if not match:
            raise LockLineError(f"line {number} of the lock isn't name==version")
        name, version, marker = match.groups()
        if marker and not _marker_holds(marker):
            continue
        names.append((name, version))
    return names


def licence_of(name: str) -> str:
    meta = importlib.metadata.metadata(name)
    expression = (meta.get("License-Expression") or "").strip()
    if expression:
        return expression
    first = next(
        (
            line.strip()
            for line in (meta.get("License") or "").splitlines()
            if line.strip()
        ),
        "",
    )
    if first and first.lower() not in NOT_A_LICENCE:
        return first
    classifiers = [
        c.split(" :: ")[-1].strip()
        for c in meta.get_all("Classifier") or []
        if c.startswith("License ::")
    ]
    return " OR ".join(classifiers)


def _pattern(entry: str) -> re.Pattern[str]:
    return re.compile(
        "^" + ".*".join(re.escape(part) for part in entry.split("*")) + "$",
        re.IGNORECASE,
    )


def _entry(mapping: dict, key: str) -> tuple[str, object] | None:
    lower = key.lower()
    return next(
        (
            (name, value)
            for name, value in (mapping or {}).items()
            if name.lower() == lower
        ),
        None,
    )


def _classify_name(name: str, policy: dict) -> str:
    text = name
    while text.startswith("(") and text.endswith(")"):
        text = text[1:-1].strip()  # "(MIT)" is MIT
    if any(entry.lower() == text.lower() for entry in policy["ok"]):
        return "ok"
    if any(_pattern(entry).match(text) for entry in policy["fail"]):
        return "fail"
    if any(_pattern(entry).match(text) for entry in policy["review"]):
        return "review"
    return "fail"  # unknown


def tokenize(text: str) -> list[str]:
    """The tokens of an expression, as `tokenize` in scripts/licences.mjs splits them."""
    tokens: list[str] = []
    leaf = ""
    own = 0
    i = 0

    def flush() -> None:
        nonlocal leaf, own
        if leaf.strip():
            tokens.append(leaf.strip())
        leaf, own = "", 0

    while i < len(text):
        op = re.match(r"\s+(AND|OR|WITH)(?=\s)", text[i:]) if own == 0 else None
        if op:
            flush()
            tokens.append(op.group(1))
            i += op.end()
            continue
        ch = text[i]
        i += 1
        if ch == "(" and not leaf.strip():
            tokens.append("(")
        elif ch == ")" and own == 0:
            flush()
            tokens.append(")")
        else:
            own += {"(": 1, ")": -1}.get(ch, 0)
            leaf += ch
    flush()
    return tokens


def _parse(text: str, policy: dict, package: str | None) -> str:
    tokens = tokenize(text)
    exceptions = {e.lower() for e in policy.get("exceptions", [])}
    at = 0

    def atom() -> str:
        nonlocal at
        if at < len(tokens) and tokens[at] == "(":
            at += 1
            inner = either()
            if at >= len(tokens) or tokens[at] != ")":
                raise SyntaxError("unclosed (")
            at += 1
            return inner
        if at >= len(tokens) or tokens[at] in {")", "AND", "OR", "WITH"}:
            raise SyntaxError("expected a licence")
        licence_id = tokens[at]
        at += 1
        if at < len(tokens) and tokens[at] == "WITH":
            at += 1
            if at >= len(tokens) or tokens[at].lower() not in exceptions:
                raise SyntaxError("not a listed exception")
            at += 1
        return _classify_leaf(
            licence_id, policy, package
        )  # an exception never makes a licence better

    def both() -> str:
        nonlocal at
        result = atom()
        while at < len(tokens) and tokens[at] == "AND":
            at += 1
            result = min(result, atom(), key=RANK.__getitem__)
        return result

    def either() -> str:
        nonlocal at
        result = both()
        while at < len(tokens) and tokens[at] == "OR":
            at += 1
            result = max(result, both(), key=RANK.__getitem__)
        return result

    try:
        result = either()
    except SyntaxError:
        return "fail"
    return result if at == len(tokens) else "fail"


def classify(expr: str, policy: dict, package: str | None = None) -> str:
    """'ok', 'review' or 'fail', by the same rules as `classify` in scripts/licences.mjs."""
    if not PRINTABLE.fullmatch(expr or ""):
        return "fail"
    text = (expr or "").strip()
    if not text:
        return "fail"
    if _entry(policy.get("aliases", {}), text) or not OPERATOR.search(text):
        return _classify_leaf(text, policy, package)
    return _parse(text, policy, package)


def _classify_leaf(name: str, policy: dict, package: str | None) -> str:
    """One name, through its alias if it has one, but never parsed again (as in the JS)."""
    alias = _entry(policy.get("aliases", {}), name)
    result = _classify_name(alias[1] if alias else name, policy)
    only = alias and _entry(policy.get("aliasPackages", {}), alias[0])
    if only and package not in only[1]:
        result = min(result, "review", key=RANK.__getitem__)
    return result


def _same_version(installed: str, locked: str) -> bool:
    def norm(v: str) -> str:
        return re.sub(r"[-_.]+", ".", v.strip().lower())

    return norm(installed) == norm(locked)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1 or args[0].startswith("-"):
        print("usage: licences_py.py REQUIREMENTS_LOCK", file=sys.stderr)
        return 2
    lock = Path(args[0])
    try:
        names = runtime_names(lock)
        policy = json.loads(POLICY.read_text(encoding="utf-8"))
    except LockLineError as error:
        print(f"licences_py: {error}", file=sys.stderr)
        return 2
    except (OSError, ValueError) as error:
        print(
            f"licences_py: {error.__class__.__name__} reading the lock or the policy",
            file=sys.stderr,
        )
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
        if not _same_version(installed, version):
            findings.append(f"FAIL: {name}=={version} is installed at {installed}")
            continue
        licence = licence_of(name)
        cls = classify(licence, policy, name)
        print(
            f"| {name} | {version} | {licence or '(none)'} | analysis image | {cls} |"
        )
        if cls == "fail":
            findings.append(f"FAIL: {name}=={version} ({licence or 'no licence'})")
        elif cls == "review":
            notes.append(f"REVIEW: {name}=={version} ({licence})")
    print()
    for line in notes + findings:
        print(line)
    print(
        f"licences_py: {len(names)} runtime packages: {f'{len(findings)} finding(s)' if findings else 'clean'}"
    )
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
