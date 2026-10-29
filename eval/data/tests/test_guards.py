"""Tests for the guards (C202, C206, C222), and for synth.opened_paths, which later
tests use to prove which files a tool opens.

The sealed paths here are strings under tmp_path. None of them exists, and no test
creates one.
"""

import os
import subprocess
import sys
from pathlib import Path

import guards
import pytest
import synth

DATA = Path(__file__).resolve().parents[1]  # eval/data

SEALED_PATHS = [
    ("sealed", "x.csv"),
    ("a", "Sealed", "x.csv"),
    ("SEALED",),
    ("sealed", "sub", "..", "x.csv"),
    ("x", "sealed", "..", "y.csv"),  # refused as given, although it normalises outside
    ("sealed.", "x.csv"),
    pytest.param(
        ("sealed::$INDEX_ALLOCATION", "x.csv"),
        marks=pytest.mark.skipif(sys.platform != "win32", reason="an NTFS stream name"),
    ),
]


@pytest.mark.parametrize("parts", SEALED_PATHS)
def test_refuse_sealed_paths(tmp_path, capsys, parts):
    with pytest.raises(SystemExit) as stop:
        guards.refuse_sealed(tmp_path.joinpath(*parts))
    assert stop.value.code == 2
    assert capsys.readouterr().err == "refused: path inside a folder named sealed\n"


@pytest.mark.skipif(sys.platform != "win32", reason="a drive-relative path")
def test_refuse_sealed_resolves_a_drive_relative_path(capsys):
    # As given, C:sealed\x.csv splits into "C:sealed", whose name before ":" is C. Only
    # its absolute form, under the current folder, names sealed. Nothing is created.
    with pytest.raises(SystemExit) as stop:
        guards.refuse_sealed(os.path.splitdrive(os.getcwd())[0] + "sealed\\x.csv")
    assert stop.value.code == 2
    assert capsys.readouterr().err == "refused: path inside a folder named sealed\n"


def test_refuse_sealed_lets_other_names_pass(tmp_path):
    guards.refuse_sealed(
        tmp_path / "unsealed" / "x.csv",
        tmp_path / "sealed.csv",
        tmp_path / "sealed_notes" / "x",
    )


@pytest.mark.parametrize(
    ("name", "sealed"),
    [
        ("sealed", True),
        ("Sealed", True),
        ("SEALED", True),
        ("sealed.", True),
        ("sealed ", True),
        ("SEALED.", True),
        ("Sealed ..", True),
        ("sealed::$INDEX_ALLOCATION", True),
        ("unsealed", False),
        ("sealed.csv", False),
        ("sealed_notes", False),
        ("", False),
    ],
)
def test_is_sealed_name(name, sealed):
    assert guards.is_sealed_name(name) is sealed


# Spellings of sealed with trailing dots and spaces, which is_sealed_name strips, as
# Windows does from a path's last name (MS3b's R156).
TRAILING = ["sealed.", "sealed ", "SEALED.", "Sealed .."]


@pytest.mark.parametrize("leaf", [False, True], ids=["inside", "leaf"])
@pytest.mark.parametrize("form", TRAILING)
def test_refuse_sealed_trailing_dots_and_spaces(tmp_path, capsys, form, leaf):
    """Each spelling is refused inside a path and as its last name. On Windows, making
    the path absolute already turns "sealed." and "SEALED." into a plain sealed
    anywhere, and every spelling as the last name, so those cases hold there even
    without the guard's own strip. "sealed " and "Sealed .." inside a path keep their
    trailing characters, and other systems change nothing, so those cases need it."""
    path = tmp_path / form if leaf else tmp_path / form / "x.csv"
    with pytest.raises(SystemExit) as stop:
        guards.refuse_sealed(path)
    assert stop.value.code == 2
    assert capsys.readouterr().err == "refused: path inside a folder named sealed\n"


@pytest.mark.parametrize("form", TRAILING)
def test_require_sealed_takes_trailing_dots_and_spaces(tmp_path, form):
    guards.require_sealed(tmp_path / form / "a.7z", flag="--archive")


def test_require_sealed(tmp_path, capsys):
    guards.require_sealed(tmp_path / "sealed" / "a.7z", flag="--archive")
    # A folder flag, such as set_b_masks' --photos, may name the sealed folder itself.
    guards.require_sealed(tmp_path / "sealed", flag="--photos")
    for outside in (tmp_path / "a.7z", tmp_path / "sealed" / ".." / "a.7z"):
        with pytest.raises(SystemExit) as stop:
            guards.require_sealed(outside, flag="--archive")
        assert stop.value.code == 2
        assert capsys.readouterr().err == (
            "refused: --archive must be inside a folder named sealed\n"
        )


def test_console_needs_both_handles():
    assert guards.console_ok(is_console=lambda fd: fd in (0, 1)) is True
    assert guards.console_ok(is_console=lambda fd: fd == 0) is False  # stdout piped
    assert guards.console_ok(is_console=lambda fd: fd == 1) is False


def test_nul_stdin_and_piped_stdout_fail_the_console_check():
    console_check = [
        sys.executable,
        "-c",
        "import guards, sys; sys.exit(0 if guards.console_ok() else 3)",
    ]
    env = {**os.environ, "PYTHONPATH": str(DATA)}
    piped = subprocess.run(
        console_check,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        timeout=synth.TIMEOUT,
        check=False,
    )
    assert piped.returncode == 3
    if sys.platform == "win32":
        # C412's trap: NUL is a character device, so isatty calls it a terminal.
        trap = subprocess.run(
            [
                sys.executable,
                "-c",
                "import os, sys; sys.exit(0 if os.isatty(0) else 3)",
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            timeout=synth.TIMEOUT,
            check=False,
        )
        assert trap.returncode == 0
        # With NUL on both handles, isatty would pass both, yet GetConsoleMode fails.
        both_nul = subprocess.run(
            console_check,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            timeout=synth.TIMEOUT,
            check=False,
        )
        assert both_nul.returncode == 3


def test_require_console_message(monkeypatch, capsys):
    synth.console(monkeypatch)
    guards.require_console()
    monkeypatch.setattr(guards, "console_ok", lambda **_: False)
    with pytest.raises(SystemExit) as stop:
        guards.require_console()
    assert stop.value.code == 2
    assert capsys.readouterr().err == (
        "refused: run this yourself, in a Windows PowerShell window\n"
    )


def test_password_typed_twice(monkeypatch, capsys):
    synth.typed(monkeypatch, "p q r", "p q r")
    assert guards.ask_password() == "p q r"

    prompts = []

    def record(prompt):
        prompts.append(prompt)
        return "p q r"

    guards.ask_password(ask=record)
    assert prompts == ["Archive password: ", "Type it again: "]

    synth.typed(monkeypatch, "a", "b")
    with pytest.raises(SystemExit) as stop:
        guards.ask_password()
    assert stop.value.code == 2
    assert capsys.readouterr().err == (
        "refused: the two entries differ; nothing was written\n"
    )

    synth.typed(monkeypatch, "", "")
    with pytest.raises(SystemExit) as stop:
        guards.ask_password()
    assert stop.value.code == 2
    assert capsys.readouterr().err == "refused: empty password\n"


def test_password_utf16_cant_encode_is_refused(monkeypatch, capsys):
    """Windows getpass gives an emoji as two lone surrogates, which UTF-16-LE, the
    encoding 7z derives its key from, can't encode (Task 13's addition 3). The refusal
    comes before the second prompt, prints no part of the password, and holds no
    exception that does."""
    surrogate = chr(0xD83D)  # as getpass reads an emoji's first UTF-16 unit
    phrase = f"test phrase {surrogate} for synthetic archives"
    prompts = []

    def record(prompt):
        prompts.append(prompt)
        return phrase

    with pytest.raises(SystemExit) as stop:
        guards.ask_password(ask=record)
    assert stop.value.code == 2
    assert (stop.value.__cause__, stop.value.__context__) == (None, None)
    assert prompts == ["Archive password: "]
    out, err = capsys.readouterr()
    assert (out, err) == ("", "refused: the password can't be encoded\n")

    synth.typed(monkeypatch, phrase, phrase)
    with pytest.raises(SystemExit) as stop:
        guards.ask_password()
    assert stop.value.code == 2
    out, err = capsys.readouterr()
    assert err == "refused: the password can't be encoded\n"
    assert surrogate not in out + err
    assert "test phrase" not in out + err


def test_confirm_needs_yes(monkeypatch, capsys):
    for answer in ("yes", " yes "):
        synth.typed(monkeypatch, answer)
        guards.confirm("split 12 rows")
        assert capsys.readouterr().out == "split 12 rows\n"

    prompts = []

    def record(prompt):
        prompts.append(prompt)
        return "yes"

    guards.confirm("split 12 rows", ask=record)
    assert prompts == ["Type yes to continue: "]

    for answer in ("y", ""):
        synth.typed(monkeypatch, answer)
        with pytest.raises(SystemExit) as stop:
            guards.confirm("split 12 rows")
        assert stop.value.code == 2
        assert capsys.readouterr().err == "stopped: nothing was done\n"


def test_quiet_prints_the_class_only(capsys):
    assert guards.quiet(lambda: 0) == 0

    def fails():
        raise ValueError("A007.jpg")

    assert guards.quiet(fails) == 1
    err = capsys.readouterr().err
    assert err == "stopped: ValueError\n"
    assert "A007" not in err

    def interrupted():
        raise KeyboardInterrupt

    assert guards.quiet(interrupted) == 1
    assert capsys.readouterr().err == "stopped: KeyboardInterrupt\n"

    def refuses():
        raise SystemExit(2)

    with pytest.raises(SystemExit) as stop:
        guards.quiet(refuses)
    assert stop.value.code == 2


def test_opened_paths_sees_every_open(tmp_path):
    tool = tmp_path / "tool"
    tool.mkdir()
    (tool / "tiny_sibling.py").write_text("VALUE = 1\n", encoding="utf-8")
    script = tool / "tiny.py"
    script.write_text(
        "import os\n"
        "import sys\n"
        "from pathlib import Path\n"
        "\n"
        "import tiny_sibling  # found only with the script's folder on sys.path\n"
        "\n"
        "a, b, c, folder = sys.argv[1:]\n"
        "open(a, 'rb').close()\n"
        "os.close(os.open(b, os.O_RDONLY))\n"
        "Path(c).read_bytes()\n"
        "os.listdir(folder)  # one folder, listed both ways\n"
        "list(os.scandir(folder))\n",
        encoding="utf-8",
    )
    folder = tmp_path / "files"
    folder.mkdir()
    a, b, c = (folder / name for name in ("a.txt", "b.txt", "c.txt"))
    for path in (a, b, c):
        path.write_bytes(b"x")

    code, events = synth.opened_paths(script, [str(a), str(b), str(c), str(folder)])

    assert code == 0
    assert {
        ("open", str(a)),
        ("open", str(b)),
        ("open", str(c)),
        ("os.listdir", str(folder)),
        ("os.scandir", str(folder)),
    } <= set(events)


def test_opened_paths_times_out(tmp_path, monkeypatch):
    # A tool that waits for input fails instead of hanging the suite. On Windows,
    # getpass reads the console itself, which NUL can't feed.
    script = tmp_path / "waits.py"
    script.write_text("import time\n\ntime.sleep(30)\n", encoding="utf-8")
    monkeypatch.setattr(synth, "TIMEOUT", 1)
    with pytest.raises(subprocess.TimeoutExpired):
        synth.opened_paths(script, [])
