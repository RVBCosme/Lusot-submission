"""Tests for the write-once encrypted archive (C205).

Every archive here is synthetic, written under tmp_path with the test phrase (C206).
Only these tests open one.
"""

import ast
import hashlib
import json
import random
import subprocess
import sys
from pathlib import Path

import archive
import py7zr
import pytest
import synth
from py7zr.exceptions import PasswordRequired

DATA = Path(__file__).resolve().parents[1]  # eval/data

# py7zr's ways to read an archive. ".extract" covers extractall too.
READING = (".extract", ".getnames(", ".namelist(", ".list(", ".test(", ".testzip(")

# Archive paths refused before anything opens (S-R8, S-R2, Task 2's M2), each made from
# tmp_path. The test runs in tmp_path, so a relative path would be created there. The
# rooted path's folder doesn't exist, so it can't be created anywhere.
BAD_PATHS = {
    "relative": lambda tmp: Path("lusot-sealed.7z"),
    "drive-relative": lambda tmp: Path(tmp.drive + "lusot-sealed.7z"),
    "rooted without a drive": lambda tmp: Path("\\no-such-folder\\lusot-sealed.7z"),
    "not 7z": lambda tmp: tmp / "lusot-sealed.zip",
    "an NTFS stream": lambda tmp: tmp / "sealed:a.7z",
}

# Arcnames refused before anything is created. The last one of each list is refused.
BAD_ARCNAMES = {
    "parent": ["../x"],
    "absolute": ["/x"],
    "backslash": ["a\\b"],
    "repeat": ["a/b", "a/b"],
    "repeat in another case": ["A001.jpg", "a001.jpg"],  # one file on NTFS
    "nul": ["a\x00b"],  # 7z would store a
    "lone surrogate": ["\udc80"],  # UTF-16-LE can't encode it
    "drive": ["C:x"],
    "drive and root": ["C:/x"],
    "empty": [""],
    "dot": ["."],
    "dot part": ["./x"],
    "empty part": ["a//b"],
    "folder": ["a/"],
}


def members_of(tmp_path: Path) -> list[tuple[str, bytes | Path]]:
    """Two members from memory and one from a file, as the sealing steps pass them."""
    log = tmp_path / "inputs" / "set_a_log.csv"
    log.parent.mkdir()
    log.write_bytes(b"candidate_id,photo_file\nA001,A001.jpg\n")
    return [
        ("records/split.json", b'{"seed": 20261030}\n'),
        ("set_a/photos/A001.jpg", bytes(range(256)) * 64),
        ("set_a/source/set_a_log.csv", log),
    ]


def test_archive_round_trip_with_the_test_phrase(tmp_path, capsys):
    members = members_of(tmp_path)
    path = tmp_path / "lusot-sealed.7z"
    archive.write_sealed_archive(path, synth.TEST_PHRASE, members)
    assert capsys.readouterr() == ("", "")
    out = tmp_path / "extracted"
    with py7zr.SevenZipFile(path, "r", password=synth.TEST_PHRASE) as sealed:
        assert sorted(sealed.getnames()) == sorted(name for name, _ in members)
        sealed.extractall(path=out)
    for name, source in members:
        expected = source.read_bytes() if isinstance(source, Path) else source
        assert (out / name).read_bytes() == expected


def test_members_may_be_a_generator(tmp_path):
    """The members are read once, so the checks don't spend a generator (M1)."""
    members = members_of(tmp_path)
    path = tmp_path / "lusot-sealed.7z"
    archive.write_sealed_archive(path, synth.TEST_PHRASE, (item for item in members))
    with py7zr.SevenZipFile(path, "r", password=synth.TEST_PHRASE) as sealed:
        assert sorted(sealed.getnames()) == sorted(name for name, _ in members)


def test_names_are_encrypted(tmp_path):
    members = members_of(tmp_path)
    path = tmp_path / "lusot-sealed.7z"
    archive.write_sealed_archive(path, synth.TEST_PHRASE, members)
    # The header is encrypted, so even listing the names needs the password.
    with pytest.raises(PasswordRequired):
        py7zr.SevenZipFile(path, "r").close()
    data = path.read_bytes()
    for name, _ in members:
        assert name.encode("utf-8") not in data
        assert name.encode("utf-16-le") not in data


def test_contents_are_encrypted(tmp_path):
    """C205: the contents are LZMA2 then AES-256, not only the header. Without AES,
    LZMA2 would store these incompressible bytes as they are."""
    photo = random.Random(5).randbytes(4096)
    path = tmp_path / "lusot-sealed.7z"
    archive.write_sealed_archive(
        path, synth.TEST_PHRASE, [("set_a/photos/A001.jpg", photo)]
    )
    assert photo not in path.read_bytes()
    with py7zr.SevenZipFile(path, "r", password=synth.TEST_PHRASE) as sealed:
        assert sealed.archiveinfo().method_names == ["LZMA2", "7zAES"]


def test_never_overwrites(tmp_path):
    path = tmp_path / "lusot-sealed.7z"
    path.write_bytes(b"an earlier archive")
    with pytest.raises(FileExistsError):
        archive.write_sealed_archive(path, synth.TEST_PHRASE, members_of(tmp_path))
    assert path.read_bytes() == b"an earlier archive"


@pytest.mark.parametrize("names", BAD_ARCNAMES.values(), ids=list(BAD_ARCNAMES))
def test_bad_arcnames_are_refused_before_writing(tmp_path, names):
    path = tmp_path / "lusot-sealed.7z"
    members = [("ok.csv", b"x"), *((name, b"y") for name in names)]
    with pytest.raises(ValueError) as refused:
        archive.write_sealed_archive(path, synth.TEST_PHRASE, members)
    # The message names the member by its place in members, never by its text.
    assert str(refused.value) == f"members[{len(members) - 1}] has a bad arcname"
    assert not path.exists()


@pytest.mark.parametrize("kind", ["folder", "missing file", "str", "bytearray", "link"])
def test_bad_sources_are_refused_before_writing(tmp_path, monkeypatch, kind):
    """py7zr would store a folder or a link as such, read a str as a path, and fail
    partway on a missing file or a bytearray, once the file exists (I1)."""
    file = tmp_path / "set_a_log.csv"
    file.write_bytes(b"candidate_id\nA001\n")
    folder = tmp_path / "folder"
    folder.mkdir()
    if kind == "link":
        # This account can't make symlinks (WinError 1314), so a real file stands in
        # and is_symlink calls it one.
        monkeypatch.setattr(Path, "is_symlink", lambda self: self == file)
    source = {
        "folder": folder,
        "missing file": tmp_path / "missing.csv",
        "str": str(file),
        "bytearray": bytearray(b"x"),
        "link": file,
    }[kind]
    path = tmp_path / "lusot-sealed.7z"
    with pytest.raises(ValueError) as refused:
        archive.write_sealed_archive(
            path, synth.TEST_PHRASE, [("ok.csv", b"x"), ("bad.csv", source)]
        )
    assert str(refused.value) == "members[1] is neither bytes nor a file"
    assert not path.exists()


@pytest.mark.parametrize("make", BAD_PATHS.values(), ids=list(BAD_PATHS))
def test_bad_archive_paths_are_refused_before_writing(tmp_path, monkeypatch, make):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError):
        archive.write_sealed_archive(
            make(tmp_path), synth.TEST_PHRASE, [("a.csv", b"x")]
        )
    assert list(tmp_path.iterdir()) == []


def test_empty_password_is_refused_before_writing(tmp_path):
    """C206's passwords are never empty, and one would leave the archive open to all."""
    path = tmp_path / "lusot-sealed.7z"
    with pytest.raises(ValueError):
        archive.write_sealed_archive(path, "", [("a.csv", b"x")])
    assert not path.exists()


def test_a_password_utf16_cant_encode_is_refused_before_writing(tmp_path):
    """Windows getpass gives an emoji as two lone surrogates, which UTF-16-LE, the
    encoding 7z derives its key from, can't encode (M4). No exception chained to the
    refusal holds the password."""
    emoji = chr(0xD83D) + chr(0xDE00)  # as getpass reads it, one UTF-16 unit at a time
    phrase = f"test phrase {emoji} for synthetic archives"
    path = tmp_path / "lusot-sealed.7z"
    with pytest.raises(ValueError) as refused:
        archive.write_sealed_archive(path, phrase, [("a.csv", b"x")])
    assert str(refused.value) == "the password can't be encoded"
    assert (refused.value.__cause__, refused.value.__context__) == (None, None)
    assert not path.exists()


def test_facts_are_the_file_bytes(tmp_path):
    path = tmp_path / "lusot-sealed.7z"
    facts = archive.write_sealed_archive(path, synth.TEST_PHRASE, members_of(tmp_path))
    data = path.read_bytes()
    assert facts == archive.ArchiveFacts(
        "lusot-sealed.7z", len(data), hashlib.sha256(data).hexdigest()
    )


def test_archive_module_never_reads_an_archive():
    """C205: no tool opens, lists or adds to an archive once it is written."""
    text = (DATA / "archive.py").read_text(encoding="utf-8")
    calls = [
        node
        for node in ast.walk(ast.parse(text))
        if isinstance(node, ast.Call)
        and getattr(node.func, "attr", getattr(node.func, "id", "")) == "SevenZipFile"
    ]
    assert text.count("SevenZipFile(") == len(calls) == 1
    assert ast.literal_eval(calls[0].args[1]) == "x"
    assert [method for method in READING if method in text] == []


def test_archive_imports_no_numpy_or_cv2():
    """Set D's sealer depends on py7zr alone (Task 18), so a fresh interpreter that
    imports archive loads no numpy, OpenCV or photos."""
    probe = (
        f"import sys; sys.path.insert(0, {json.dumps(str(DATA))}); import archive; "
        "print(sorted({'numpy', 'cv2', 'photos'} & set(sys.modules)))"
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
