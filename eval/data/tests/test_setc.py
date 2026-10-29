"""Tests for Set C's STURM manifest, eval/data/setc.py (C215, C222).

Every tree is synthetic, under tmp_path. setc hashes each image's bytes and never
decodes them, so the images are short byte strings named .jpg, .jpeg or .png.
"""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import guards
import pytest
import setc
import synth
import table
from test_sources import LISTING_CALLS, listing_imports

DATA = Path(__file__).resolve().parents[1]  # eval/data
SETC = DATA / "setc.py"
REFUSED = "refused: path inside a folder named sealed\n"
EXISTS = "--out exists: a manifest is never rewritten\n"


def tree(root: Path, *names: str) -> Path:
    """Write each file, named relative to root with /, holding bytes of its own, and
    return root."""
    for name in names:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"synthetic {name}".encode("ascii"))
    return root


def args(root: Path, out: Path) -> list[str]:
    return ["sturm", "--root", str(root), "--out", str(out)]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def paths(out: Path) -> list[str]:
    return [row["path"] for row in table.read_table(out).rows]


def counts(files: int, levels: tuple[int, int, int, int, int], skipped: int) -> str:
    tally = " ".join(f"level{level}={n}" for level, n in enumerate(levels))
    return f"files={files}\n{tally}\nskipped={skipped}\n"


def inside(path: str, folder: Path) -> bool:
    absolute = Path(os.path.abspath(path))
    return absolute == folder or folder in absolute.parents


def test_sturm_manifest(tmp_path, capsys):
    """Each image under a Level folder gets its path, level and SHA-256, in MS2's CSV
    form; any other file counts as skipped; and only the counts print. --out sits in
    --root, as spec §5.10 runs it, and isn't listed: it's written after the walk."""
    x = "extracted/upscaled_images/Level1/x.jpg"
    y = "extracted/upscaled_images/Level3/y.png"
    root = tree(tmp_path / "sturm", x, y, "readme.txt")
    out = root / "manifest.csv"
    assert setc.main(args(root, out)) == 0
    # UTF-8 without a BOM, a header row and \n endings, as every MS2 CSV.
    assert out.read_bytes() == (
        f"path,level,sha256\n{x},1,{sha256(root / x)}\n{y},3,{sha256(root / y)}\n"
    ).encode("ascii")
    assert capsys.readouterr() == (counts(2, (0, 1, 0, 1, 0), 1), "")


@pytest.mark.parametrize("name", ["sealed", "Sealed", "SEALED"])
def test_walk_skips_sealed_folders(tmp_path, capsys, monkeypatch, name):
    """Addition 1: a folder named sealed, in any case, is pruned before the walk
    descends it. None of its files is listed or counted, and no open or os.scandir
    event falls inside it. Its name is checked before the link checks (S-R33), so it
    isn't even looked up."""
    root = tree(
        tmp_path / "sturm",
        "Level2/kept.jpg",
        f"Level2/{name}/z.jpg",
        f"Level2/{name}/Level1/w.png",
    )
    looked_up = []
    for check in ("islink", "isjunction"):
        real = getattr(os.path, check)

        def spy(path, real=real):
            looked_up.append(os.fspath(path))
            return real(path)

        monkeypatch.setattr(os.path, check, spy)
    out = tmp_path / "manifest.csv"
    assert setc.main(args(root, out)) == 0
    assert paths(out) == ["Level2/kept.jpg"]
    assert capsys.readouterr() == (counts(1, (0, 0, 1, 0, 0), 0), "")
    assert str(root / "Level2" / "kept.jpg") in looked_up
    assert [path for path in looked_up if inside(path, root / "Level2" / name)] == []
    code, events = synth.opened_paths(SETC, args(root, tmp_path / "again.csv"))
    assert code == 0
    assert [item for item in events if inside(item[1], root / "Level2" / name)] == []
    # The hook sees the walk's reads, so the check above isn't empty by default.
    assert ("os.scandir", str(root / "Level2")) in events


def test_the_walk_follows_no_link(tmp_path):
    """Addition 1: a symbolic link to a folder is never followed, so the walk can't
    leave --root through one. Windows makes such a link only in Developer Mode or as an
    administrator, so there the test is skipped; CI's Ubuntu runs it."""
    elsewhere = tree(tmp_path / "elsewhere", "Level1/x.jpg")
    root = tree(tmp_path / "sturm", "Level2/kept.jpg")
    try:
        os.symlink(elsewhere, root / "Level3", target_is_directory=True)
    except OSError:
        pytest.skip("this system can't make a symbolic link")
    out = tmp_path / "manifest.csv"
    assert setc.main(args(root, out)) == 0
    assert paths(out) == ["Level2/kept.jpg"]


def test_the_walk_enters_no_junction(tmp_path, capsys):
    """S-R33: a junction to a folder outside --root is pruned, though os.walk's
    followlinks=False alone would enter it, and nothing under it or its target opens.
    Windows makes a junction without elevation; other systems have none."""
    winapi = pytest.importorskip("_winapi")
    elsewhere = tree(tmp_path / "elsewhere", "Level1/x.jpg")
    root = tree(tmp_path / "sturm", "Level2/kept.jpg")
    winapi.CreateJunction(str(elsewhere), str(root / "Level3"))
    assert os.path.isjunction(root / "Level3")
    out = tmp_path / "manifest.csv"
    assert setc.main(args(root, out)) == 0
    assert paths(out) == ["Level2/kept.jpg"]
    assert capsys.readouterr() == (counts(1, (0, 0, 1, 0, 0), 0), "")
    code, events = synth.opened_paths(SETC, args(root, tmp_path / "again.csv"))
    assert code == 0
    assert [
        item
        for item in events
        if inside(item[1], elsewhere) or inside(item[1], root / "Level3")
    ] == []
    # The hook sees the walk's reads, so the check above isn't empty by default.
    assert ("os.scandir", str(root / "Level2")) in events


def test_a_file_link_is_skipped_and_never_read(tmp_path, capsys):
    """S-R33: a symbolic link to a file counts as skipped and is never opened, so no
    hash is read through it. Skipped where symbolic links can't be made, as on Windows
    outside Developer Mode; CI's Ubuntu runs it."""
    elsewhere = tree(tmp_path / "elsewhere", "x.jpg")
    root = tree(tmp_path / "sturm", "Level2/kept.jpg")
    link = root / "Level2" / "linked.jpg"
    try:
        os.symlink(elsewhere / "x.jpg", link)
    except OSError:
        pytest.skip("this system can't make a symbolic link")
    out = tmp_path / "manifest.csv"
    assert setc.main(args(root, out)) == 0
    assert paths(out) == ["Level2/kept.jpg"]
    assert capsys.readouterr() == (counts(1, (0, 0, 1, 0, 0), 1), "")
    code, events = synth.opened_paths(SETC, args(root, tmp_path / "again.csv"))
    assert code == 0
    assert [
        item for item in events if inside(item[1], link) or inside(item[1], elsewhere)
    ] == []


def test_a_file_the_system_calls_a_link_is_skipped(tmp_path, capsys, monkeypatch):
    """S-R33, pinned on Windows too, where a file link needs Developer Mode: a file
    os.path.islink calls a link counts as skipped and is never hashed."""
    root = tree(tmp_path / "sturm", "Level2/kept.jpg", "Level2/linked.jpg")
    link = root / "Level2" / "linked.jpg"
    islink, sha256_file = os.path.islink, table.sha256_file
    hashed = []

    def spy(path):
        hashed.append(Path(path))
        return sha256_file(path)

    monkeypatch.setattr(
        os.path, "islink", lambda path: Path(path) == link or islink(path)
    )
    monkeypatch.setattr(table, "sha256_file", spy)
    out = tmp_path / "manifest.csv"
    assert setc.main(args(root, out)) == 0
    assert paths(out) == ["Level2/kept.jpg"]
    assert capsys.readouterr() == (counts(1, (0, 0, 1, 0, 0), 1), "")
    assert hashed == [root / "Level2" / "kept.jpg"]


def test_pruning_shares_the_guards_rule(tmp_path, monkeypatch):
    """PF-C27: the walk prunes with guards.is_sealed_name itself, so the walk and the
    path guard share one rule. A stand-in rule that calls Hidden sealed prunes it."""
    monkeypatch.setattr(guards, "is_sealed_name", lambda name: name == "Hidden")
    root = tree(tmp_path / "sturm", "Level2/kept.jpg", "Level2/Hidden/z.jpg")
    out = tmp_path / "manifest.csv"
    assert setc.main(args(root, out)) == 0
    assert paths(out) == ["Level2/kept.jpg"]


def test_paths_use_slashes_and_sort(tmp_path):
    """Each path is relative to --root, with /, and the rows are sorted by path as
    Python orders strings, not in the walk's order nor case-blind. A file in a folder
    below Level1 is still at level 1."""
    root = tree(
        tmp_path / "sturm",
        "Level1/z.jpg",
        "Level1/a/b.jpg",
        "Level1/B.jpg",
        "Level0/c.png",
    )
    out = tmp_path / "manifest.csv"
    assert setc.main(args(root, out)) == 0
    rows = table.read_table(out).rows
    assert [(row["path"], row["level"]) for row in rows] == [
        ("Level0/c.png", "0"),
        ("Level1/B.jpg", "1"),
        ("Level1/a/b.jpg", "1"),
        ("Level1/z.jpg", "1"),
    ]
    assert [row["sha256"] for row in rows] == [
        sha256(root / row["path"]) for row in rows
    ]


def test_the_nearest_level_folder_sets_the_level(tmp_path, capsys):
    """Addition 2: the Level folder closest to the file sets its level, matched in any
    case, as is the image's extension. Only folders below --root count, so --root's own
    name and its parent's don't. A file without a Level folder, under Level5 or
    Level1x, or that isn't a .jpg, .jpeg or .png counts as skipped."""
    root = tree(
        tmp_path / "Level1" / "Level2",
        "x.jpg",
        "Level1/Level3/a.jpg",
        "Level3/Level1/notes/b.JPEG",
        "level4/c.PNG",
        "LEVEL0/d.jpeg",
        "Level5/e.jpg",
        "Level1x/f.jpg",
        "Level2/g.gif",
        "Level2/h.jpg.txt",
    )
    out = tmp_path / "manifest.csv"
    assert setc.main(args(root, out)) == 0
    rows = table.read_table(out).rows
    assert [(row["path"], row["level"]) for row in rows] == [
        ("LEVEL0/d.jpeg", "0"),
        ("Level1/Level3/a.jpg", "3"),
        ("Level3/Level1/notes/b.JPEG", "1"),
        ("level4/c.PNG", "4"),
    ]
    assert capsys.readouterr() == (counts(4, (1, 1, 0, 1, 1), 5), "")


@pytest.mark.parametrize("flag", ["--root", "--out"])
def test_refuses_sealed_root_or_out(tmp_path, capsys, flag):
    """C222: a --root or --out inside a folder named sealed is refused on the strings,
    before anything opens, though the tree is there to walk."""
    sealed = tmp_path / "Sealed"
    root = tree((sealed if flag == "--root" else tmp_path) / "sturm", "Level1/x.jpg")
    out = (sealed if flag == "--out" else tmp_path) / "manifest.csv"
    with pytest.raises(SystemExit) as stop:
        setc.main(args(root, out))
    assert stop.value.code == 2
    assert capsys.readouterr() == ("", REFUSED)
    code, events = synth.opened_paths(SETC, args(root, out))
    assert code == 2
    assert [item for item in events if inside(item[1], tmp_path)] == []
    assert not out.exists()


def test_existing_out_is_never_overwritten(tmp_path, capsys):
    """An --out that exists is refused by a stat before the walk, and keeps its bytes,
    so a rerun needs a new path."""
    root = tree(tmp_path / "sturm", "Level1/x.jpg")
    out = tmp_path / "manifest.csv"
    out.write_bytes(b"an earlier manifest")
    assert setc.main(args(root, out)) == 2
    assert capsys.readouterr() == ("", EXISTS)
    code, events = synth.opened_paths(SETC, args(root, out))
    assert code == 2
    assert [item for item in events if inside(item[1], tmp_path)] == []
    assert out.read_bytes() == b"an earlier manifest"


@pytest.mark.parametrize("flag", ["--root", "--out"])
def test_root_and_out_must_be_absolute(tmp_path, capsys, monkeypatch, flag):
    """Addition 4 (S-R8): a relative --root or --out is refused on the strings, before
    the walk would read a folder."""
    monkeypatch.chdir(tmp_path)
    given = {
        "--root": tree(tmp_path / "sturm", "Level1/x.jpg"),
        "--out": tmp_path / "manifest.csv",
    }
    given[flag] = Path(given[flag].name)

    def no_walk(path):
        pytest.fail("the walk read a folder")

    monkeypatch.setattr(os, "scandir", no_walk)
    assert setc.main(args(given["--root"], given["--out"])) == 2
    assert capsys.readouterr() == ("", f"refused: {flag} must be absolute\n")
    assert not (tmp_path / "manifest.csv").exists()


@pytest.mark.parametrize("broken", ["missing root", "unreadable folder"])
def test_an_unreadable_folder_stops_the_run(tmp_path, capsys, monkeypatch, broken):
    """Addition 1: a folder the walk can't read, --root included, stops the run with
    its class only, and --out isn't written, so no manifest leaves a folder out in
    silence."""
    root = tree(tmp_path / "sturm", "Level1/x.jpg", "Level3/y.png")
    if broken == "missing root":
        root, error = tmp_path / "missing", "FileNotFoundError"
    else:
        error = "PermissionError"
        scandir = os.scandir

        def denied(path):
            if Path(path).name == "Level3":
                raise PermissionError(13, "synthetic denial", path)
            return scandir(path)

        monkeypatch.setattr(os, "scandir", denied)
    out = tmp_path / "manifest.csv"
    assert setc.main(args(root, out)) == 1
    assert capsys.readouterr() == ("", f"stopped: {error}\n")
    assert not out.exists()


def test_setc_lists_folders_only_through_its_one_walk():
    """Addition 6: Task 2's source test exempts setc.py whole, so this holds it to its
    one os.walk: no other listing call and no listing import."""
    text = SETC.read_text(encoding="utf-8")
    found = {call: text.count(call) for call in LISTING_CALLS if call in text}
    assert found == {"os.walk(": 1, ".walk(": 1}  # os.walk( holds .walk( too
    assert listing_imports(text) == []


def test_setc_imports_only_the_standard_library():
    """Addition 6: a fresh interpreter that imports setc loads no numpy, OpenCV or
    py7zr, nor photos or archive, which load them, so the script runs with
    dependencies = []."""
    probe = (
        f"import sys; sys.path.insert(0, {json.dumps(str(DATA))}); "
        "import setc; "
        "print(sorted({'numpy', 'cv2', 'py7zr', 'photos', 'archive'} "
        "& set(sys.modules)))"
    )
    done = subprocess.run(
        [sys.executable, "-c", probe],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        encoding="utf-8",
        timeout=synth.TIMEOUT,
        check=False,
    )
    assert (done.returncode, done.stdout, done.stderr) == (0, "[]\n", "")


@pytest.mark.parametrize(
    ("argv", "words"), [([], ["sturm"]), (["sturm"], ["--root", "--out"])]
)
def test_setc_help_exits_0(argv, words):
    done = subprocess.run(
        [sys.executable, str(SETC), *argv, "--help"],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        encoding="utf-8",
        timeout=synth.TIMEOUT,
        check=False,
    )
    assert (done.returncode, done.stderr) == (0, "")
    for word in words:
        assert word in done.stdout
