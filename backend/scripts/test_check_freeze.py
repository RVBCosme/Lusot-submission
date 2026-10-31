"""Tests for check_freeze.py, the freeze guard (MS7 plan Task 14a, spec C801).

Each test builds a small git repo in tmp_path: the real template, a stand-in for the
analysis package and the API, committed and tagged `freeze-1` (MS6's C413). It then
changes one thing, commits, and runs the guard on it. No network and no AWS.
"""

import subprocess
from pathlib import Path

import pytest

import check_freeze
from cfn_template import TEMPLATE

REPO_ROOT = TEMPLATE.parents[1]
PACKAGE = "backend/analysis/src/lusot_analysis"
# Built at run time, so no address sits in the repo (Global Constraints).
EMAIL = "test" + "@" + "example." + "invalid"
TAG = "freeze-1"
SCRIPTS = TEMPLATE.parent / "scripts"
FILES = {
    "backend/template.yaml": TEMPLATE.read_text(encoding="utf-8"),
    # The guard's own files, as the frozen commit holds them.
    **{
        f"backend/scripts/{name}": (SCRIPTS / name).read_text(encoding="utf-8")
        for name in ("check_freeze.py", "check_freeze.py.lock", "cfn_template.py")
    },
    "backend/analysis/tests/test_handler.py": "def test_b3(): pass\n",
    f"{PACKAGE}/pipeline/measure.py": "LEVEL = 1\n",
    f"{PACKAGE}/pipeline/publish.py": "BLUR = 1\n",
    f"{PACKAGE}/handler.py": "DEADLINE_MARGIN_S = 30\n",
    f"{PACKAGE}/overlay.py": "WORDS = 'level'\n",
    "backend/api/src/index.ts": "export const x = 1;\n",
}


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=test",
            "-c",
            f"user.email={EMAIL}",
            "-c",
            "commit.gpgsign=false",
            "-c",
            "tag.gpgsign=false",
            *args,
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    for name, text in FILES.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "the freeze")
    git(root, "tag", TAG)
    return root


def edit(repo: Path, name: str, old: str, new: str) -> None:
    path = repo / name
    text = path.read_text(encoding="utf-8")
    assert text.count(old) == 1, f"{old!r} isn't once in {name}"
    path.write_text(text.replace(old, new), encoding="utf-8")


def commit(repo: Path) -> None:
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "a fix")


def run(repo: Path, capsys, *args: str) -> tuple[int, str]:
    code = check_freeze.main([*args], repo=repo)
    return code, capsys.readouterr().out


def test_clean_since_the_tag(repo, capsys):
    edit(repo, "backend/api/src/index.ts", "x = 1", "x = 2")
    # The app API's stage throttle, a capacity fix C801 lets land.
    edit(
        repo,
        "backend/template.yaml",
        "      DefaultRouteSettings:\n        ThrottlingRateLimit: 10\n",
        "      DefaultRouteSettings:\n        ThrottlingRateLimit: 12\n",
    )
    commit(repo)
    code, out = run(repo, capsys, TAG)
    assert code == 0
    assert "path files: none changed" in out
    assert "AnalysisFunction: unchanged" in out
    assert out.rstrip().endswith("freeze: clean")


def test_a_path_file_fails(repo, capsys):
    edit(repo, f"{PACKAGE}/pipeline/measure.py", "LEVEL = 1", "LEVEL = 2")
    commit(repo)
    code, out = run(repo, capsys, TAG)
    assert code == 1
    assert f"  changed: {PACKAGE}/pipeline/measure.py" in out
    assert out.rstrip().endswith("freeze: CHANGED")


def test_publish_is_off_the_path(repo, capsys):
    """The publish blur runs after the result (C801), as the overlay does. Its phrases
    shape the reading's, and its error would end a level, so a reviewer reads it."""
    edit(repo, f"{PACKAGE}/pipeline/publish.py", "BLUR = 1", "BLUR = 2")
    edit(repo, f"{PACKAGE}/overlay.py", "'level'", "'antas'")
    commit(repo)
    code, out = run(repo, capsys, TAG)
    assert code == 0
    assert "path files: none changed" in out
    assert "pipeline/publish.py: changed: a reviewer reads it" in out
    assert "PUBLISH_PHRASES" in out
    assert "tests/test_handler.py: unchanged" in out


def test_the_b3_tests_are_flagged_for_review(repo, capsys):
    edit(repo, "backend/analysis/tests/test_handler.py", "pass", "assert True")
    commit(repo)
    code, out = run(repo, capsys, TAG)
    assert code == 0
    assert (
        "tests/test_handler.py: changed: a reviewer reads it against MS3a's B3" in out
    )


def test_a_file_moved_off_the_path_names_its_old_path(repo, capsys):
    git(repo, "mv", f"{PACKAGE}/pipeline/measure.py", f"{PACKAGE}/measure_moved.py")
    commit(repo)
    code, out = run(repo, capsys, TAG)
    assert code == 1
    assert f"  changed: {PACKAGE}/pipeline/measure.py" in out


def test_analysis_resource_fails(repo, capsys):
    edit(
        repo,
        "backend/template.yaml",
        "      MemorySize: 1024\n      Timeout: 180\n",
        "      MemorySize: 1024\n      Timeout: 200\n",
    )
    commit(repo)
    code, out = run(repo, capsys, TAG)
    assert code == 1
    assert "AnalysisFunction: changed" in out


def test_a_change_elsewhere_in_the_template_passes(repo, capsys):
    edit(
        repo,
        "backend/template.yaml",
        "  ApiLogGroup:\n    Type: AWS::Logs::LogGroup\n    Properties:\n      RetentionInDays: 14\n",
        "  ApiLogGroup:\n    Type: AWS::Logs::LogGroup\n    Properties:\n      RetentionInDays: 7\n",
    )
    # A comment inside AnalysisFunction changes no value.
    edit(
        repo,
        "backend/template.yaml",
        "      Timeout: 180\n",
        "      # The run's ceiling.\n      Timeout: 180\n",
    )
    commit(repo)
    code, out = run(repo, capsys, TAG)
    assert code == 0
    assert "AnalysisFunction: unchanged" in out


def test_globals_count_as_the_analysis_function(repo, capsys):
    """SAM merges Globals into every function, and Lambda's environment overrides the
    image's, so a Globals pixel cap would reach the pipeline."""
    edit(
        repo,
        "backend/template.yaml",
        "Transform: AWS::Serverless-2016-10-31\n",
        "Transform: AWS::Serverless-2016-10-31\nGlobals:\n  Function:\n"
        "    Environment:\n      Variables:\n"
        '        OPENCV_IO_MAX_IMAGE_PIXELS: "1000"\n',
    )
    commit(repo)
    code, out = run(repo, capsys, "--decision", TAG)
    assert code == 1
    assert "AnalysisFunction: changed" in out


def test_the_queue_event_and_a_condition_count(repo, capsys):
    edit(
        repo,
        "backend/template.yaml",
        "            BatchSize: 1\n",
        "            BatchSize: 2\n",
    )
    commit(repo)
    code, out = run(repo, capsys, TAG)
    assert code == 1
    assert "AnalysisFunction: changed" in out
    edit(
        repo,
        "backend/template.yaml",
        "            BatchSize: 2\n",
        "            BatchSize: 1\n",
    )
    edit(
        repo,
        "backend/template.yaml",
        "  AnalysisFunction:\n    Type: AWS::Serverless::Function\n",
        "  AnalysisFunction:\n    Type: AWS::Serverless::Function\n    Condition: HasWeb\n",
    )
    commit(repo)
    code, out = run(repo, capsys, TAG)
    assert code == 1
    assert "AnalysisFunction: changed" in out


def test_an_edited_guard_fails(repo, capsys):
    """A commit could move a file off the guard's list and change it in one go."""
    edit(
        repo,
        "backend/scripts/check_freeze.py",
        '    f"{PACKAGE}/rules.py",\n',
        "",
    )
    edit(repo, f"{PACKAGE}/pipeline/measure.py", "LEVEL = 1", "LEVEL = 2")
    commit(repo)
    code, out = run(repo, capsys, TAG)
    assert code == 1
    assert "guard: changed since freeze-1" in out
    assert "  changed: backend/scripts/check_freeze.py" in out


def test_an_uncommitted_guard_change_fails(repo, capsys):
    edit(repo, "backend/scripts/cfn_template.py", '"""Load', '"""Read')
    code, out = run(repo, capsys, TAG)
    assert code == 1
    assert "  changed: backend/scripts/cfn_template.py" in out


def test_the_working_trees_template_counts(repo, capsys):
    """With no head named, the template is read as the deploy would build it."""
    edit(
        repo,
        "backend/template.yaml",
        "      MemorySize: 1024\n      Timeout: 180\n",
        "      MemorySize: 1024\n      Timeout: 900\n",
    )
    code, out = run(repo, capsys, TAG)
    assert code == 1
    assert "AnalysisFunction: changed" in out
    assert "uncommitted: backend/template.yaml" not in out


def test_an_uncommitted_change_elsewhere_passes(repo, capsys):
    """As the same change committed does: only the path, the function and the guard
    count."""
    edit(
        repo,
        "backend/template.yaml",
        "      DefaultRouteSettings:\n        ThrottlingRateLimit: 10\n",
        "      DefaultRouteSettings:\n        ThrottlingRateLimit: 12\n",
    )
    edit(repo, f"{PACKAGE}/handler.py", "= 30", "= 25")
    code, out = run(repo, capsys, TAG)
    assert code == 0
    assert "handler.py: changed: a reviewer reads it" in out
    assert out.rstrip().endswith("freeze: clean")


@pytest.mark.parametrize(
    "text",
    ["Resources: [\n", "- a list\n- not a template\n", "Resources:\n  - a\n"],
    ids=["no-parse", "a-list", "resources-a-list"],
)
def test_a_template_it_cannot_read_exits_2(repo, capsys, text):
    (repo / "backend/template.yaml").write_text(text, encoding="utf-8")
    commit(repo)
    code, out = run(repo, capsys, TAG)
    assert code == 2
    assert "can't check" in out


def test_a_missing_working_template_exits_2(repo, capsys):
    (repo / "backend/template.yaml").unlink()
    code, out = run(repo, capsys, TAG)
    assert code == 2
    assert "can't check: backend/template.yaml in the working tree" in out


def test_handler_is_flagged_for_review(repo, capsys):
    edit(repo, f"{PACKAGE}/handler.py", "= 30", "= 25")
    commit(repo)
    code, out = run(repo, capsys, TAG)
    # Not on the path itself (C801), but a reviewer reads it against the deadline code.
    assert code == 0
    assert "handler.py: changed" in out
    assert "DEADLINE_MARGIN_S" in out


def test_an_unchanged_handler_is_not_flagged(repo, capsys):
    code, out = run(repo, capsys, TAG)
    assert code == 0
    assert "handler.py: unchanged" in out


def test_the_decision_passes_only_with_its_flag(repo, capsys):
    edit(
        repo,
        "backend/template.yaml",
        'GEOMETRY_IN_LEVEL: "on"',
        'GEOMETRY_IN_LEVEL: "off"',
    )
    commit(repo)
    assert check_freeze.DECISION_VARIABLE == "GEOMETRY_IN_LEVEL"
    code, out = run(repo, capsys, "--decision", TAG)
    assert code == 0
    assert "AnalysisFunction: changed only in GEOMETRY_IN_LEVEL" in out
    code, out = run(repo, capsys, TAG)
    assert code == 1
    assert "AnalysisFunction: changed" in out


def test_another_variable_fails_even_with_the_flag(repo, capsys):
    # The analysis function's own copy, the one followed by the decision's comment.
    edit(
        repo,
        "backend/template.yaml",
        "LIMITS_TABLE_NAME: !Ref LimitsTable\n          # Geometry in the level path",
        "LIMITS_TABLE_NAME: !Ref ReportsTable\n          # Geometry in the level path",
    )
    edit(
        repo,
        "backend/template.yaml",
        'GEOMETRY_IN_LEVEL: "on"',
        'GEOMETRY_IN_LEVEL: "off"',
    )
    commit(repo)
    code, out = run(repo, capsys, "--decision", TAG)
    assert code == 1
    assert "AnalysisFunction: changed" in out


def test_the_decision_must_stay_on_or_off(repo, capsys):
    """The handler refuses any other value (C309), so every report would fail."""
    edit(
        repo,
        "backend/template.yaml",
        'GEOMETRY_IN_LEVEL: "on"',
        "GEOMETRY_IN_LEVEL: on",
    )
    commit(repo)
    code, out = run(repo, capsys, "--decision", TAG)
    assert code == 1
    assert "GEOMETRY_IN_LEVEL must be" in out


def test_inches_shown_is_off_the_path(repo, capsys):
    edit(repo, "backend/template.yaml", 'INCHES_SHOWN: "false"', 'INCHES_SHOWN: "true"')
    commit(repo)
    code, out = run(repo, capsys, TAG)
    assert code == 0
    assert out.rstrip().endswith("freeze: clean")


def test_head_can_be_named(repo, capsys):
    first = git(repo, "rev-parse", "HEAD").strip()
    edit(repo, f"{PACKAGE}/pipeline/measure.py", "LEVEL = 1", "LEVEL = 2")
    commit(repo)
    code, _ = run(repo, capsys, TAG, first)
    assert code == 0
    code, _ = run(repo, capsys, TAG, "HEAD")
    assert code == 1


def test_uncommitted_path_changes_fail(repo, capsys):
    """With no head named, the deploy builds the working tree, so its changes count."""
    edit(repo, f"{PACKAGE}/pipeline/measure.py", "LEVEL = 1", "LEVEL = 2")
    (repo / PACKAGE / "pipeline" / "new_step.py").write_text(
        "X = 1\n", encoding="utf-8"
    )
    code, out = run(repo, capsys, TAG)
    assert code == 1
    assert f"  uncommitted: {PACKAGE}/pipeline/measure.py" in out
    assert f"  uncommitted: {PACKAGE}/pipeline/new_step.py" in out


def test_an_unknown_ref_exits_2(repo, capsys):
    code, out = run(repo, capsys, "freeze-9")
    assert code == 2
    assert "not a commit" in out
    code, _ = run(repo, capsys, "--output=x")
    assert code == 2


def test_resource_compare_reads_values_not_text():
    text = TEMPLATE.read_text(encoding="utf-8")
    assert not check_freeze.analysis_resource_changed(text, text)
    moved = text.replace("      Timeout: 180\n", "      Timeout: 180 # the ceiling\n")
    assert not check_freeze.analysis_resource_changed(text, moved)
    flipped = text.replace('GEOMETRY_IN_LEVEL: "on"', 'GEOMETRY_IN_LEVEL: "off"')
    assert check_freeze.analysis_resource_changed(text, flipped)
    assert not check_freeze.analysis_resource_changed(
        text, flipped, allow=frozenset({"GEOMETRY_IN_LEVEL"})
    )


def test_path_files_name_the_repos_layout():
    """Every entry exists, and every tracked file of the analysis package and its build is
    either on the path or named off it, so a new module has to be placed."""
    named = [name for name, _ in check_freeze.REVIEWED]
    for entry in (*check_freeze.PATH_FILES, *check_freeze.OFF_PATH, *named):
        assert (REPO_ROOT / entry).exists(), entry
    for entry in check_freeze.GUARD_FILES:
        assert (REPO_ROOT / entry).is_file(), entry
    tracked = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", "-z", "backend/analysis"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split("\0")

    def under(name: str, entries: tuple[str, ...]) -> bool:
        return any(
            name == e.rstrip("/") or name.startswith(e.rstrip("/") + "/")
            for e in entries
        )

    unplaced = [
        name
        for name in tracked
        if name and not under(name, check_freeze.PATH_FILES + check_freeze.OFF_PATH)
    ]
    assert unplaced == []
    assert under(f"{PACKAGE}/pipeline/publish.py", check_freeze.OFF_PATH)
    assert not under(f"{PACKAGE}/handler.py", check_freeze.PATH_FILES)
