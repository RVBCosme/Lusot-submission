"""Tests for ops_common.py: the operator scripts' one copy of their shared helpers.

check:py runs this file with the scripts' dependencies. Alone, from the repo root:
    uv run --python 3.13 --with pytest --with boto3 --with httpx --with numpy
        --with "opencv-python-headless<5" pytest -q backend/scripts/test_ops_common.py
"""

import subprocess
import sys
from pathlib import Path

import boto3
import demo_pins
import eval_runs
import guards
import hide_pin
import ops_common
import pytest
import redrive_dlq
import samples
import smoke_upload

SHARED = ("REGION", "REPORT_ID", "PHT", "WAIT_S", "STACK", "lusot_session", "guarded")


def test_the_scripts_keep_no_copy_of_the_shared_helpers():
    # Review, Minor 4: each name a script holds is ops_common's own object.
    for module in (
        demo_pins,
        samples,
        hide_pin,
        redrive_dlq,
        eval_runs,
        smoke_upload,
        guards,
    ):
        for name in SHARED:
            if hasattr(module, name):
                assert getattr(module, name) is getattr(ops_common, name), (
                    f"{module.__name__}.{name}"
                )
    assert smoke_upload.STACK is ops_common.STACK == "lusot"
    assert ops_common.REGION == "ap-southeast-1"
    assert ops_common.WAIT_S == 180
    assert ops_common.REPORT_ID.fullmatch("r_" + "0" * 32)
    assert not ops_common.REPORT_ID.fullmatch("r_" + "0" * 31)


def test_ops_common_and_guards_import_only_the_standard_library():
    # So hide_pin.py's and redrive_dlq.py's headers and locks stay boto3-only, and
    # smoke_upload.py's are unchanged.
    folder = Path(__file__).resolve().parent
    code = (
        f"import sys; sys.path.insert(0, {str(folder)!r}); import ops_common, guards;"
        " print(sorted(m for m in ('boto3', 'botocore', 'httpx', 'cv2', 'numpy')"
        " if m in sys.modules))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert result.stdout.strip() == "[]"


def test_lusot_session_is_always_the_lusot_profile(monkeypatch):
    made = []
    monkeypatch.setattr(boto3, "Session", lambda **kwargs: made.append(kwargs) or "s")
    monkeypatch.setenv("AWS_PROFILE", "someone-else")
    assert ops_common.lusot_session() == "s"
    assert made == [{"profile_name": "lusot", "region_name": "ap-southeast-1"}]


class Shown(Exception):
    pass


def test_guarded_ends_each_error_in_one_line(capsys):
    def raising(exc):
        def command():
            raise exc

        return command

    assert ops_common.guarded(lambda: 0) == 0
    assert ops_common.guarded(raising(SystemExit(2))) == 2
    # A message the script wrote to be printed, and the errors printed by class only.
    assert ops_common.guarded(raising(Shown("no credit line")), shown=(Shown,)) == 1
    for exc in (ValueError("a value"), KeyError("a key"), OSError("C:\\a\\path")):
        assert ops_common.guarded(raising(exc)) == 1
    assert ops_common.guarded(raising(LookupError("x")), errors=(LookupError,)) == 1
    assert ops_common.guarded(raising(Shown("x")), label="EVAL FAILED", shown=(Shown,))
    out, err = capsys.readouterr()
    assert out.splitlines() == [
        "failed: no credit line",
        "failed: ValueError",
        "failed: KeyError",
        "failed: OSError",
        "failed: LookupError",
        "EVAL FAILED: x",
    ]
    assert err == ""
    # Anything else is a bug, and propagates.
    with pytest.raises(ZeroDivisionError):
        ops_common.guarded(raising(ZeroDivisionError()))
