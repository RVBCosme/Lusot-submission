# /// script
# requires-python = ">=3.13,<3.14"
# dependencies = [
#     "pyyaml==6.0.3",
# ]
# ///
"""The freeze guard: has the measuring path changed since the freeze tag? (C801)

After the freeze, a fix lands only if it can't change a depth output. This checks the
two proofs a script can give; the third, MS3a's B3 replay, runs beside it:
- no file on the measuring path changed (PATH_FILES, as the plan's Task 14a names
  record them, less what OFF_PATH names inside them);
- the template's AnalysisFunction resource is unchanged, read as values, so a comment
  doesn't count.

handler.py mixes both kinds of code, so a change to it is reported for a reviewer's
read against the run's deadline code, and doesn't fail the check by itself.

--decision allows DECISION_VARIABLE alone, for the commit that applies the sealed run's
decision (C801's exception), and only as "on" or "off". INCHES_SHOWN sits in the API
function's environment (MS4's C515), off the path, so it needs no flag.

With no HEAD named, the deploy builds the working tree, so an uncommitted change to
anything checked here fails too.

Usage, from the repo root:
    uv run --locked --script backend/scripts/check_freeze.py [--decision] <freeze tag> [HEAD]

Exit 0 when nothing on the path changed, 1 when something did, 2 when it can't check.
"""

from __future__ import annotations

import argparse
import copy
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import yaml

from cfn_template import parse_template

PACKAGE = "backend/analysis/src/lusot_analysis"
TEMPLATE = "backend/template.yaml"
HANDLER = f"{PACKAGE}/handler.py"
# The measuring path's files and folders (C801; the plan's Global Constraints, checked
# against main's layout in Task 14a's names). A folder ends with "/".
PATH_FILES: tuple[str, ...] = (
    f"{PACKAGE}/pipeline/",
    f"{PACKAGE}/__init__.py",  # the pixel cap (R26)
    f"{PACKAGE}/annotate.py",
    f"{PACKAGE}/face_blur.py",
    f"{PACKAGE}/meta_client.py",
    f"{PACKAGE}/prompts.py",
    f"{PACKAGE}/rules.py",
    f"{PACKAGE}/tire_codes.json",  # rules.py loads it for geometry (C304)
    f"{PACKAGE}/tuning.py",  # MS3b's tuning module (C310)
    f"{PACKAGE}/models/",
    "backend/analysis/prompts/",
    "backend/analysis/uv.lock",
    "backend/analysis/requirements.lock.txt",
    "backend/analysis/Dockerfile",
    "backend/analysis/.dockerignore",  # what reaches the image
)
# Named off the path, so every tracked file of the package and its build is placed.
OFF_PATH: tuple[str, ...] = (
    f"{PACKAGE}/pipeline/publish.py",  # the publish blur, after the result
    HANDLER,  # read by a reviewer instead
    f"{PACKAGE}/export.py",
    f"{PACKAGE}/laptop_spend.py",
    f"{PACKAGE}/overlay.py",
    f"{PACKAGE}/report_store.py",
    f"{PACKAGE}/spend.py",
    "backend/analysis/pyproject.toml",  # can't change the image without uv.lock
    "backend/analysis/.python-version",
    "backend/analysis/probes/",
    "backend/analysis/tests/",
)
# The name of geometry_in_level's variable in AnalysisFunction's environment (C309).
DECISION_VARIABLE = "GEOMETRY_IN_LEVEL"
DECISION_VALUES = ("on", "off")
DEADLINE_CODE = "DEADLINE_MARGIN_S, _deadline and analyse (C84, C88)"

Git = Callable[[list[str]], str]


class CheckError(Exception):
    """The guard couldn't check: a bad ref, git failing, or an unreadable template."""


def _under(name: str, entries: tuple[str, ...]) -> bool:
    return any(
        name == e.rstrip("/") or name.startswith(e.rstrip("/") + "/") for e in entries
    )


def _pathspecs() -> list[str]:
    excluded = [e for e in OFF_PATH if _under(e, PATH_FILES)]
    return [*PATH_FILES, *(f":(exclude){e}" for e in excluded)]


def changed_path_files(base: str, head: str, git: Git) -> list[str]:
    """The path's files that differ between two commits. Without renames, so a file
    moved off the path still names its old path."""
    out = git(
        ["diff", "--name-only", "-z", "--no-renames", base, head, "--", *_pathspecs()]
    )
    return sorted(name for name in out.split("\0") if name)


def uncommitted_files(git: Git) -> list[str]:
    """Working-tree changes, untracked files included, to anything the guard checks."""
    out = git(
        [
            "status",
            "--porcelain=v1",
            "-z",
            "--no-renames",
            "--untracked-files=all",
            "--",
            *_pathspecs(),
            TEMPLATE,
            HANDLER,
        ]
    )
    # Each entry is "XY path"; --no-renames leaves no second path.
    return sorted(entry[3:] for entry in out.split("\0") if entry)


def _analysis(text: str, allow: frozenset[str]) -> object:
    resources = parse_template(text).get("Resources") or {}
    resource = copy.deepcopy(resources.get("AnalysisFunction"))
    if isinstance(resource, dict):
        variables = ((resource.get("Properties") or {}).get("Environment") or {}).get(
            "Variables"
        )
        if isinstance(variables, dict):
            for name in allow:
                variables.pop(name, None)
    return resource


def analysis_resource_changed(
    base_text: str, head_text: str, *, allow: frozenset[str] = frozenset()
) -> bool:
    """Whether the template's AnalysisFunction resource differs between two versions,
    as values, leaving out the environment variables named in `allow`."""
    return _analysis(base_text, allow) != _analysis(head_text, allow)


def decision_value(text: str) -> object:
    resource = (parse_template(text).get("Resources") or {}).get(
        "AnalysisFunction"
    ) or {}
    env = ((resource.get("Properties") or {}).get("Environment") or {}).get("Variables")
    return env.get(DECISION_VARIABLE) if isinstance(env, dict) else None


def _runner(repo: Path) -> Git:
    def git(args: list[str]) -> str:
        done = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        if done.returncode != 0:
            raise CheckError(f"git {args[0]} failed (exit {done.returncode})")
        return done.stdout

    return git


def _commit(git: Git, ref: str) -> str:
    try:
        return git(
            [
                "rev-parse",
                "--verify",
                "--quiet",
                "--end-of-options",
                f"{ref}^{{commit}}",
            ]
        ).strip()
    except CheckError:
        raise CheckError(f"{ref} is not a commit here") from None


def _template_at(git: Git, commit: str) -> str:
    return git(["show", f"{commit}:{TEMPLATE}"])


def _check(args: argparse.Namespace, git: Git, repo: Path) -> int:
    base = _commit(git, args.tag)
    head = _commit(git, args.head or "HEAD")
    print(f"freeze guard: {args.tag} to {args.head or 'HEAD and the working tree'}")
    clean = True

    changed = changed_path_files(base, head, git)
    uncommitted = [] if args.head else uncommitted_files(git)
    if changed or uncommitted:
        clean = False
        print(f"path files: {len(changed)} changed, {len(uncommitted)} uncommitted")
        for name in changed:
            print(f"  changed: {name}")
        for name in uncommitted:
            print(f"  uncommitted: {name}")
    else:
        print("path files: none changed")

    base_text = _template_at(git, base)
    if args.head:
        head_text = _template_at(git, head)
    else:
        head_text = (repo / TEMPLATE).read_text(encoding="utf-8")
    try:
        whole = analysis_resource_changed(base_text, head_text)
        rest = analysis_resource_changed(
            base_text, head_text, allow=frozenset({DECISION_VARIABLE})
        )
        value = decision_value(head_text)
    except yaml.YAMLError:
        raise CheckError("the template doesn't parse") from None
    if not whole:
        print("AnalysisFunction: unchanged")
    elif args.decision and not rest:
        print(
            f"AnalysisFunction: changed only in {DECISION_VARIABLE}, which --decision allows"
        )
        if value not in DECISION_VALUES:
            clean = False
            print(
                f'  {DECISION_VARIABLE} must be "on" or "off", quoted (C309); it reads {value!r}'
            )
    else:
        clean = False
        print("AnalysisFunction: changed")

    handler_changed = (
        bool(git(["diff", "--name-only", "-z", base, head, "--", HANDLER]))
        or HANDLER in uncommitted
    )
    if handler_changed:
        print(f"handler.py: changed: a reviewer reads it against {DEADLINE_CODE}")
    else:
        print("handler.py: unchanged")

    print("freeze: clean" if clean else "freeze: CHANGED")
    return 0 if clean else 1


def main(argv: list[str] | None = None, *, repo: Path | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="check_freeze.py",
        description="Check that the measuring path hasn't changed since the freeze (C801).",
    )
    parser.add_argument(
        "--decision",
        action="store_true",
        help=f"allow {DECISION_VARIABLE} alone to change (the sealed run's decision)",
    )
    parser.add_argument("tag", help="the freeze tag, such as freeze-1")
    parser.add_argument(
        "head",
        nargs="?",
        help="the commit to check (default: HEAD and the working tree)",
    )
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2
    try:
        if repo is None:
            repo = Path(_runner(Path.cwd())(["rev-parse", "--show-toplevel"]).strip())
        return _check(args, _runner(repo), repo)
    except CheckError as exc:
        print(f"freeze guard: {exc}; not a commit, or not checked", flush=True)
        return 2


if __name__ == "__main__":
    sys.exit(main())
