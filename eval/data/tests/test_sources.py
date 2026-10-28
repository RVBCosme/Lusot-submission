"""Checks on the source of every tool in eval/data and eval/set_b.

They enforce the plan's Global Constraints. The tests folders are left out, and so is
any folder named sealed, which the walk never enters.
"""

import ast
import os
from pathlib import Path

import guards

EVAL = Path(__file__).resolve().parents[2]
LISTING_CALLS = (
    "listdir(",
    "scandir(",
    "os.walk(",
    ".iterdir(",
    ".glob(",
    ".rglob(",
    ".walk(",
    "import glob",
    "copytree(",
    "rmtree(",
    "writeall(",
)
CAP_LINE = 'os.environ["OPENCV_IO_MAX_IMAGE_PIXELS"] = "50000000"'


def tool_sources() -> dict[Path, str]:
    sources = {}
    for top in (EVAL / "data", EVAL / "set_b"):
        for folder, subfolders, files in os.walk(top):
            subfolders[:] = [
                name
                for name in subfolders
                if name != "tests" and not guards.is_sealed_name(name)
            ]
            for name in files:
                if name.endswith(".py"):
                    path = Path(folder, name)
                    sources[path] = path.read_text(encoding="utf-8")
    return sources


def test_sources_list_no_folder():
    found = [
        (path.name, call)
        for path, text in tool_sources().items()
        if path.name != "setc.py"  # setc's walk prunes sealed folders (§5.2)
        for call in LISTING_CALLS
        if call in text
    ]
    assert found == []


def test_sources_read_no_environment():
    found = []
    for path, text in tool_sources().items():
        found += [
            (path.name, word)
            for word in ("getenv", "environ.get(", "LUSOT_DATA_DIR")
            if word in text
        ]
        found += [
            (path.name, line.strip())
            for line in text.splitlines()
            if "environ[" in line
            and (path.name, line.strip()) != ("photos.py", CAP_LINE)
        ]
    assert found == []


def test_sources_never_import_lusot_analysis_or_scoring():
    found = []
    for path, text in tool_sources().items():
        for node in ast.walk(ast.parse(text)):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            found += [
                (path.name, name)
                for name in names
                if name.split(".")[0] in ("lusot_analysis", "scoring")
            ]
    assert found == []


def test_no_password_option():
    found = [
        (path.name, option)
        for path, text in tool_sources().items()
        for option in ("--password", "--pass")
        if option in text
    ]
    assert found == []
