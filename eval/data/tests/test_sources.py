"""Checks on the source of every tool in eval/data and eval/set_b.

They enforce the plan's Global Constraints. The tests folders are left out, and so is
any folder named sealed, which the walk never enters.
"""

import ast
import os
import re
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
# A from-import hides a listing call from the substrings above, as `from os import walk`
# then `walk(top)` does. These names from os or shutil count, and so does any glob one.
LISTING_NAMES = {"listdir", "scandir", "walk", "copytree", "rmtree", "*"}
ENVIRON = re.compile(r"\benvironb?\b")  # os.environ, but not the word "environment"
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


def listing_imports(text: str) -> list[str]:
    found = []
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.ImportFrom) and node.module in ("os", "shutil", "glob"):
            found += [
                f"from {node.module} import {alias.name}"
                for alias in node.names
                if node.module == "glob" or alias.name in LISTING_NAMES
            ]
    return found


def test_sources_list_no_folder():
    found = []
    for path, text in tool_sources().items():
        if path.name == "setc.py":  # setc's walk prunes sealed folders (§5.2)
            continue
        found += [(path.name, call) for call in LISTING_CALLS if call in text]
        found += [(path.name, line) for line in listing_imports(text)]
    assert found == []


def test_sources_read_no_environment():
    found = []
    for path, text in tool_sources().items():
        found += [
            (path.name, word)
            for word in ("getenv", "environ.get(", "LUSOT_DATA_DIR")
            if word in text
        ]
        # Any other use reads it too, such as os.environ.copy() or dict(os.environ).
        found += [
            (path.name, line.strip())
            for line in text.splitlines()
            if ENVIRON.search(line)
            and (path.name, line.strip()) != ("photos.py", CAP_LINE)
        ]
    assert found == []


def test_sources_read_photos_through_python():
    """cv2.imread opens its file inside OpenCV, where no audit event shows the read, so
    synth.opened_paths couldn't prove what a tool reads (C201)."""
    found = [
        (path.name, "imread(")
        for path, text in tool_sources().items()
        if "imread(" in text
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
