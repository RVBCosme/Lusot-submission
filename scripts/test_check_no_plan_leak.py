"""Tests for scripts/check_no_plan_leak.py: it must fail closed on a bad argument.

The tests use a tiny fake plan under tmp_path and never read the real plan text.
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).with_name("check_no_plan_leak.py")


@pytest.fixture
def leak_check(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location("check_no_plan_leak", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "DEFAULT_PLAN", tmp_path / "no-such-plan" / "plan.txt")
    monkeypatch.delenv("LUSOT_PLAN_TEXT", raising=False)
    monkeypatch.delenv("CI", raising=False)
    return module


def run(module, monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["check_no_plan_leak.py", *args])
    return module.main()


@pytest.mark.parametrize("flag", ["--help", "-h"])
def test_help_fails_closed(leak_check, monkeypatch, capsys, flag):
    assert run(leak_check, monkeypatch, flag) == 2
    out, err = capsys.readouterr()
    assert "usage" in err.lower()
    assert "clean" not in out


def test_two_paths_fail_closed(leak_check, monkeypatch, capsys, tmp_path):
    assert run(leak_check, monkeypatch, str(tmp_path / "a.txt"), str(tmp_path / "b.txt")) == 2
    out, err = capsys.readouterr()
    assert "usage" in err.lower()
    assert "clean" not in out


def test_missing_explicit_path_fails_closed(leak_check, monkeypatch, capsys, tmp_path):
    missing = tmp_path / "missing-plan.txt"
    assert run(leak_check, monkeypatch, str(missing)) == 2
    assert str(missing) in capsys.readouterr().err

    monkeypatch.setenv("LUSOT_PLAN_TEXT", str(missing))
    assert run(leak_check, monkeypatch) == 2
    out, err = capsys.readouterr()
    assert str(missing) in err
    assert "skipping" not in out


def test_missing_default_plan_fails_on_the_laptop(leak_check, monkeypatch, capsys):
    assert run(leak_check, monkeypatch) == 2
    out, err = capsys.readouterr()
    assert str(leak_check.DEFAULT_PLAN) in err
    assert "skipping" not in out


def test_missing_default_plan_skips_in_ci(leak_check, monkeypatch, capsys):
    monkeypatch.setenv("CI", "true")
    assert run(leak_check, monkeypatch) == 0
    assert "skipping the plan-leak check" in capsys.readouterr().out


def test_missing_explicit_path_fails_closed_even_in_ci(leak_check, monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("CI", "true")
    missing = tmp_path / "missing-plan.txt"
    assert run(leak_check, monkeypatch, str(missing)) == 2
    out, err = capsys.readouterr()
    assert str(missing) in err
    assert "skipping" not in out

    monkeypatch.setenv("LUSOT_PLAN_TEXT", str(missing))
    assert run(leak_check, monkeypatch) == 2
    out, err = capsys.readouterr()
    assert str(missing) in err
    assert "skipping" not in out


def test_empty_or_short_line_plan_fails_closed(leak_check, monkeypatch, capsys, tmp_path):
    empty = tmp_path / "empty.txt"
    empty.write_text("", encoding="utf-8")
    short = tmp_path / "short.txt"
    short.write_text("a short line\nanother short line\n", encoding="utf-8")
    for plan in (empty, short):
        assert run(leak_check, monkeypatch, str(plan)) == 2
        out, err = capsys.readouterr()
        assert str(plan) in err
        assert "clean" not in out


def test_directory_or_invalid_utf8_plan_fails_closed(leak_check, monkeypatch, capsys, tmp_path):
    directory = tmp_path / "a-directory"
    directory.mkdir()
    invalid = tmp_path / "invalid.txt"
    invalid.write_bytes(b"\xff\xfe\x80 not utf-8 \xc3\x28\n")
    for plan in (directory, invalid):
        assert run(leak_check, monkeypatch, str(plan)) == 2
        out, err = capsys.readouterr()
        assert str(plan) in err
        assert "clean" not in out


@pytest.mark.skipif(shutil.which("git") is None, reason="git is not on PATH")
def test_clean_run_and_a_leak(leak_check, monkeypatch, capsys, tmp_path):
    plan = tmp_path / "fake-plan.txt"
    fake_lines = [f"Fake plan line number {i:02d} is written long enough to count as plan text here." for i in range(8)]
    plan.write_text("\n".join(fake_lines) + "\n", encoding="utf-8")
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    (repo / "clean.txt").write_text("nothing from the plan is in this file\n", encoding="utf-8")
    monkeypatch.chdir(repo)

    assert run(leak_check, monkeypatch, str(plan)) == 0
    assert "clean" in capsys.readouterr().out

    (repo / "pasted.txt").write_text("\n".join(fake_lines[:6]) + "\n", encoding="utf-8")
    assert run(leak_check, monkeypatch, str(plan)) == 1
    out = capsys.readouterr().out
    assert "LEAK: pasted.txt" in out
    assert "Fake plan line" not in out
