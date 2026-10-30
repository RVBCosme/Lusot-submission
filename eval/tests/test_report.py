"""The report, its summary and Rene's review sheet (spec §4.4; C409, C418, C421,
C422, C424 to C426)."""

from __future__ import annotations

import csv
import io
import json
import random
import re
from collections.abc import Callable, Sequence
from decimal import Decimal
from pathlib import Path

import pytest
import scoring
from builders import (
    a_neg_row,
    level,
    nfs,
    refused,
    run_json,
    set_a_row,
    set_b_row,
    write_run,
)
from scoring.exclusions import REASONS
from scoring.metrics import (
    Rate,
    excluded_a_neg,
    excluded_set_a,
    fmt_inches,
    fmt_rate,
    measured_errors,
    score_set_a,
)
from scoring.report import build_report, build_review
from scoring.rows import Run, load_run
from test_rows import answer, m8, person, vehicle, wheel
from test_set_a import HAND_SET
from test_wheels import measured, unmeasured

# The brief's copy, word for word.
FOOTER = (
    "Lusot estimates depth at one spot. It is not advice to cross."
    " Follow MMDA and local advisories.\n"
    "\n"
    "Not affiliated with MMDA.\n"
)
NOT_RUN = "Not run in this results folder."
NO_LATENCY = "Latency wasn't measured in this run."
SYNTHETIC = (
    "Synthetic test data for the harness's own tests. These are not Lusot's results."
)
HEADINGS = [
    "# Lusot evaluation report",
    "## Reported first",
    "## Release gate",
    "## Set A: every metric",
    "## Baseline",
    "## By the alert's level",
    "## Set A: level matrices",
    "## Landmark agreement",
    "## A-neg: flood-free photos",
    "## Correct refusals",
    "## Subsets",
    "## Set B",
    "## Set D",
    "## Latency",
    "## Exclusions",
    "## Frozen versions and data",
    "## Rebuild this report",
]
# The sections that list photos and versions rather than figures.
NOT_METRICS = ("Exclusions", "Frozen versions and data", "Rebuild this report")
LABELS = {"landmark": "Landmark alone", "geometry": "Landmark plus geometry"}

KNEE = level("knee")
UNDER = level("half_tire")
REFUSED = refused("too_dark")


# The rows


# A01's answer and M8 labels: a body that agrees, a wheel that doesn't, a person who
# agrees, a box the answer skipped, and a person's point that matched no box.
A01_ANSWER = answer(
    wheels=[wheel(3, "rim_top")],
    vehicles=[vehicle(2, "sedan_hatch", "door_sill")],
    people=[person(5, "knee")],
)
A01_M8 = [
    m8(3, "wheel", "hub"),
    m8(5, "person", "knee"),
    m8(2, "vehicle", "door_sill", "pickup"),
    m8(7, "wheel", "hub"),
    m8(None, "person", "knee"),
]


def set_a_rows() -> list[dict]:
    """Task 3's hand-computed set, A01 to A10 (A10 excluded), with M8 labels on A01
    and on A10, a dark photo and two subsets; then A11, whose passability label
    doesn't map, A15 on a second event, and four more exclusions."""
    rows = [dict(row) for row in HAND_SET]
    rows[0].update(answer=A01_ANSWER, m8=A01_M8, subsets=["splash"])
    rows[4].update(quality="dark")  # A05, refused as too dark
    rows[8].update(subsets=["reflection"])  # A09
    rows[9].update(answer=A01_ANSWER, m8=A01_M8)  # A10, excluded
    waist = level("waist")
    return [
        *rows,
        set_a_row("A11", passability="passable"),
        set_a_row("A12", poster_kind="other"),
        set_a_row("A13", others=("chest deep",)),
        set_a_row("A14", duplicate=True),
        set_a_row(
            "A15",
            event_id="E02",
            label="waist deep",
            passability="NPATV",
            landmark=waist,
            geometry=waist,
        ),
        set_a_row("A16", event_id="E02", metro_manila=False),
    ]


def a_neg_rows() -> list[dict]:
    """Flood-free photos, wet and dry: a false flood for landmark alone, a dark photo
    refused, and two exclusions."""
    return [
        a_neg_row("N01"),
        a_neg_row(
            "N02",
            surface="dry",
            outcomes={"landmark": level("gutter"), "geometry": nfs()},
        ),
        a_neg_row(
            "N03", quality="dark", outcomes={"landmark": REFUSED, "geometry": REFUSED}
        ),
        a_neg_row("N04", surface="dry", duplicate=True),
        a_neg_row("N05", surface="dry", decodes=False),
    ]


VARIANTS = (
    "geometry",
    "geometry_uncalibrated",
    "known_waterline",
    "known_waterline_uncalibrated",
)


def wheel_rows(prefix: str) -> list[dict]:
    """Eight wheels 11.25 in deep on four crops of two cars. Wheel k (from 0) has an
    error of 0.25 k in, inside its envelope, except the last, which isn't measured.
    SAM found no water at wheel 5. Every variant repeats geometry's estimate."""
    rows = []
    for index in range(8):
        point = Decimal("11.25") + Decimal("0.25") * index
        estimate = (
            unmeasured("axis_ratio")
            if index == 7
            else measured(str(point), "10.25", str(point + 1))
        )
        rows.append(
            set_b_row(
                f"{prefix}{index // 2 + 1:02d}",
                index % 2 + 1,
                car_id=f"C{index // 4 + 1:02d}",
                vehicle_type="sedan_hatch" if index < 4 else "suv_mpv",
                sam_water_found=index != 5,
                bins={"view": "side" if index % 2 else "front"},
                estimates=dict.fromkeys(VARIANTS, estimate),
            )
        )
    return rows


LATENCY = [
    {"test_id": f"L{number}", "seconds": Decimal(seconds)}
    for number, seconds in enumerate(("6.5", "3.2", "9.1", "4.25", "5"), start=1)
]


def full_run_json(**overrides: object) -> dict:
    """A sealed run's manifest, with a stop and every set's dataset recorded."""
    fields = {
        "kind": "sealed",
        "stops": [{"at": "21:10", "cause": "lost connection", "resumed": "21:40"}],
        "datasets": {
            name: {"version": "v1", "split_seed": "7"}
            for name in ("set_a", "a_neg", "set_b", "set_d")
        },
    }
    return run_json(**{**fields, **overrides})


def load(folder: Path, run: dict, **sets: Sequence[dict]) -> Run:
    """Write a results folder with the builders, then load it as the harness does."""
    return load_run(write_run(folder, run=run, **sets))


def full_run(folder: Path, **overrides: object) -> Run:
    """A sealed run that reaches every section, its manifest changed by `overrides`."""
    return load(
        folder,
        full_run_json(**overrides),
        set_a=set_a_rows(),
        a_neg=a_neg_rows(),
        set_b=wheel_rows("B"),
        set_d=wheel_rows("D")[:2],
        latency=LATENCY,
    )


def photos(*groups: tuple[int, dict, dict]) -> list[dict]:
    """Set A photos given as (count, landmark's result, geometry's result), each with
    an alert of knee deep and NPLV, as test_gate's are."""
    results = [(alone, added) for count, alone, added in groups for _ in range(count)]
    return [
        set_a_row(f"A{number:03d}", passability="NPLV", landmark=alone, geometry=added)
        for number, (alone, added) in enumerate(results, start=1)
    ]


def with_third(rows: list[dict]) -> list[dict]:
    """The rows with geometry without the self-check too, read as landmark alone."""
    return [
        {
            **row,
            "outcomes": {
                **row["outcomes"],
                "geometry_no_self_check": row["outcomes"]["landmark"],
            },
        }
        for row in rows
    ]


def landmark_only(rows: list[dict]) -> list[dict]:
    """The rows with only landmark alone's result, as after geometry is dropped."""
    return [
        {**row, "outcomes": {"landmark": row["outcomes"]["landmark"]}} for row in rows
    ]


def without(manifest: dict, *keys: str) -> dict:
    return {key: value for key, value in manifest.items() if key not in keys}


# In-sample and replay readings for landmark alone, every alert knee: 5 of 6 within
# one level in-sample, 2 of 6 in replay (test_other_sets).
REPLAY_READINGS = (
    ("knee", "knee"),
    ("knee", "knee"),
    ("knee", "chest"),
    ("tire", "chest"),
    ("half_tire", "chest"),
    ("chest", "chest"),
)


def replay_rows() -> list[dict]:
    return [
        set_a_row(
            f"A0{number}",
            outcomes={
                "landmark": level(in_sample),
                "geometry": KNEE,
                "landmark_replay": level(replay),
            },
        )
        for number, (in_sample, replay) in enumerate(REPLAY_READINGS, start=1)
    ]


RERUN_REASON = "fix 3 changed the depth output"


# Each kind of run, as (run, first_run).


def rerun_pair(folder: Path) -> tuple[Run, Run]:
    """A first run and its rerun, in which A02 reads knee in both configurations."""
    first = full_run(folder / "first")
    rows = set_a_rows()
    rows[1] = {**rows[1], "outcomes": {"landmark": KNEE, "geometry": KNEE}}
    rerun = load(
        folder / "first" / "rerun",
        full_run_json(rerun_reason=RERUN_REASON, date="2026-11-02"),
        set_a=rows,
        a_neg=a_neg_rows(),
        set_b=wheel_rows("B"),
    )
    return rerun, first


def empty_sets(folder: Path) -> Run:
    """A sealed run whose Set A photos are all refused, with an empty A-neg and an
    empty Set B, and no Set D or latency."""
    return load(
        folder,
        run_json(kind="sealed"),
        set_a=photos((3, REFUSED, REFUSED)),
        a_neg=[],
        set_b=[],
    )


# Window 4 creates no folder named sealed, so a run's folder takes its place in this
# table, never its name.
RUNS: dict[str, Callable[[Path], tuple[Run, Run | None]]] = {
    "final": lambda folder: (full_run(folder), None),
    "development": lambda folder: (full_run(folder, kind="development"), None),
    "self-check on": lambda folder: (
        load(
            folder,
            full_run_json(self_check="on"),
            set_a=with_third(set_a_rows()),
            a_neg=with_third(a_neg_rows()),
            set_b=wheel_rows("B"),
        ),
        None,
    ),
    "geometry dropped": lambda folder: (
        load(
            folder,
            full_run_json(
                geometry_default="dropped",
                geometry_dropped_reason="median error over 3 in",
            ),
            set_a=landmark_only(set_a_rows()),
            a_neg=landmark_only(a_neg_rows()),
            set_b=wheel_rows("B"),
        ),
        None,
    ),
    "rerun": rerun_pair,
    "empty sets": lambda folder: (empty_sets(folder), None),
    "Set B only": lambda folder: (
        load(folder, run_json(), set_b=wheel_rows("B")),
        None,
    ),
    "synthetic": lambda folder: (full_run(folder, synthetic=True), None),
    "retried": lambda folder: (full_run(folder, service_retries=2), None),
    "replay": lambda folder: (load(folder, run_json(), set_a=replay_rows()), None),
}


# Reading the report


def report_of(run: Run, first_run: Run | None = None) -> str:
    return build_report(run, first_run=first_run)["report.md"].decode("utf-8")


def headings(report: str) -> list[str]:
    return [line for line in report.split("\n") if line.startswith(("# ", "## "))]


def section_text(report: str, heading: str) -> str:
    """The text under `## heading`, up to the next ## heading."""
    start = report.index(f"\n## {heading}\n") + len(heading) + 5
    end = report.find("\n## ", start)
    return report[start:] if end == -1 else report[start:end]


def section(report: str, heading: str) -> list[str]:
    """The non-blank lines under `## heading`."""
    return [line for line in section_text(report, heading).split("\n") if line.strip()]


def paragraphs(text: str) -> list[list[str]]:
    """The text's blocks, each its lines; the report puts one blank line between."""
    return [block.split("\n") for block in text.strip().split("\n\n")]


def cells(row: str) -> list[str]:
    return [cell.strip() for cell in row.strip().strip("|").split("|")]


def is_separator(line: str) -> bool:
    return re.fullmatch(r"\|(?:---\|)+", line) is not None


def metric_rows(text: str) -> list[str]:
    """The data rows of the tables in `text`, apart from the charts' twins: a table
    right after a chart."""
    rows = []
    after_chart = False
    for block in paragraphs(text):
        if block[0].startswith("|") and not after_chart:
            assert is_separator(block[1]), block
            rows += block[2:]
        after_chart = block[0].startswith("![")
    return rows


def metric_header(report: str) -> str:
    return next(
        line
        for line in section(report, "Set A: every metric")
        if line.startswith("| Metric |")
    )


# The tests


def test_sections_in_order(tmp_path):
    report = report_of(full_run(tmp_path))
    assert headings(report) == HEADINGS
    assert report.endswith("\n\n" + FOOTER)


def test_every_metric_row_has_n(tmp_path):
    with_n = re.compile(" of [0-9]+ |n = [0-9]+")
    checked = 0
    for number, (name, make) in enumerate(RUNS.items()):
        run, first = make(tmp_path / f"run{number}")
        report = report_of(run, first)
        for heading in headings(report)[1:]:
            title = heading.removeprefix("## ")
            if title in NOT_METRICS:
                continue
            for row in metric_rows(section_text(report, title)):
                assert with_n.search(row), (name, title, row)
                checked += 1
    assert checked > 300


def test_each_chart_has_its_twin(tmp_path):
    run = full_run(tmp_path)
    files = build_report(run)
    blocks = paragraphs(files["report.md"].decode("utf-8"))
    charts = []
    for index, block in enumerate(blocks):
        if not block[0].startswith("!["):
            continue
        link = re.fullmatch(r"!\[[^\]]+\]\(([a-z_-]+\.svg)\)", block[0])
        assert link, block[0]
        charts.append(link[1])
        twin = blocks[index + 1]
        assert twin[0].startswith("|") and is_separator(twin[1]), block[0]
    assert sorted(charts) == sorted(name for name in files if name.endswith(".svg"))
    assert sorted(charts) == [
        "level-matrix-geometry.svg",
        "level-matrix-landmark.svg",
        "set-b-errors.svg",
    ]
    for name in charts:
        assert files[name].startswith(b"<svg ") and files[name].endswith(b"</svg>\n")
    # The error chart's twin lists each measured wheel's error, smallest first.
    errors = blocks[
        [block[0] for block in blocks].index(
            "![Set B: depth error per measured wheel (geometry)](set-b-errors.svg)"
        )
        + 1
    ]
    assert errors[2:] == [
        f"| {rank} | {fmt_inches(error)} |"
        for rank, error in enumerate(measured_errors(run.set_b, "geometry"), start=1)
    ]
    # The matrix's twin lists each non-empty cell.
    matrix = section(files["report.md"].decode("utf-8"), "Set A: level matrices")
    landmark = matrix.index(
        "![Landmark alone: the alert's level against Lusot's]"
        "(level-matrix-landmark.svg)"
    )
    assert matrix[landmark + 1 : landmark + 4] == [
        "| The alert's level | Lusot's level | Photos |",
        "|---|---|---|",
        "| below_gutter | no flood seen | 1 |",
    ]


def test_set_b_only_report(tmp_path):
    run = load(tmp_path, run_json(), set_b=wheel_rows("B"))
    files = build_report(run)
    report = files["report.md"].decode("utf-8")
    for heading in (
        "Reported first",
        "Outcome rule on development data",
        "Set A: every metric",
        "Baseline",
        "By the alert's level",
        "Set A: level matrices",
        "Landmark agreement",
        "Vehicle types (development)",
        "A-neg: flood-free photos",
        "Correct refusals",
        "Subsets",
        "Set D",
        "Exclusions",
    ):
        assert section(report, heading) == [NOT_RUN], heading
    assert section(report, "Latency") == [NO_LATENCY]
    assert [cells(row)[0] for row in metric_rows(section_text(report, "Set B"))] == [
        *VARIANTS,
        "geometry, vehicle type sedan_hatch",
        "geometry, vehicle type suv_mpv",
        "geometry, view front",
        "geometry, view side",
    ]
    assert water_line("7 of 8 (87.5%)", 0) in section(report, "Set B")
    summary = json.loads(files["summary.json"])
    for key in ("configurations", "shipped", "geometry_stays", "inches_shown"):
        assert summary[key] is None, key
    assert summary["set_b"]["measured"] == {"k": 7, "n": 8}
    assert sorted(name for name in files if name.endswith(".svg")) == [
        "set-b-errors.svg"
    ]
    # Rene's sheet then holds only its header.
    assert build_review(run).decode("utf-8").count("\r\n") == 1


def test_synthetic_report(tmp_path):
    report = report_of(full_run(tmp_path / "synthetic", synthetic=True))
    lines = report.split("\n")
    assert lines[:3] == [
        "# Lusot evaluation report (synthetic test data)",
        "",
        SYNTHETIC,
    ]
    assert "ran once on the sealed sets" not in report
    assert "ran once on the sealed sets" in report_of(full_run(tmp_path / "plain"))


def test_opening_paragraph(tmp_path):
    lines = report_of(full_run(tmp_path)).split("\n")
    assert lines[2] == (
        "The frozen pipeline ran once on the sealed sets, on 2026-10-30. Its figures"
        " are agreement with the labels MMDA and the cities posted, mapped by"
        " eval/rules.md §2 (v0.7) before any result was seen. With samples this small,"
        " every figure is indicative and carries its n."
    )


A_NEG_LEAD = (
    "The A-neg photos are openly licensed Wikimedia Commons photos"
    " (CC0, public domain or CC BY)."
    ' Flood-free photos that got a level instead of "no flood seen" or a refusal,'
    " over the A-neg photos kept. A processing failure counts in the n, never as a"
    " false flood."
)


def test_a_neg_lead_names_its_source(tmp_path):
    # Rules §4 (v0.7's item 4.5): A-neg comes from Wikimedia Commons, and the report's
    # A-neg section says so, in a sealed and in a development report alike.
    for kind in ("sealed", "development"):
        run = full_run(tmp_path / f"{kind}-run", kind=kind)
        lead = section(report_of(run), "A-neg: flood-free photos")[0]
        assert lead == A_NEG_LEAD, kind
        # The copy rules: the source and its licences, and nothing of any photo's
        # credit (it stays in the private manifest), file or link; never ShareAlike;
        # and no "accuracy". The report's banned-word guard covers the rest.
        for word in ("credit", "http", "by-sa", "sharealike", "accuracy"):
            assert word not in lead.lower(), (kind, word)
    # With no A-neg rows the section still says only that it wasn't run.
    empty = load(tmp_path / "empty", run_json(), set_a=HAND_SET)
    assert section(report_of(empty), "A-neg: flood-free photos") == [NOT_RUN]


def test_latency_says_upload_to_the_final_result(tmp_path):
    # Rules §7 (v0.7's item 7.8, C416): the live tests use samples, and uploads placed
    # outside Metro Manila never pin, so the report can't call the figure "upload to
    # pin". The docstrings say so too.
    lines = section(report_of(full_run(tmp_path)), "Latency")
    assert lines[:2] == [
        (
            "Live tests' seconds from upload, or a sample's start, to the final result"
            " (C416)."
        ),
        "| Measure | Upload, or a sample's start, to the final result |",
    ]
    assert "pin" not in " ".join(lines).lower()
    for path in Path(scoring.__file__).parent.glob("*.py"):
        assert "upload to pin" not in path.read_text(encoding="utf-8").lower(), path


def test_baseline_section(tmp_path):
    no_pair = without(run_json(), "baseline_level", "baseline_class")
    # Geometry reads A01 and A02 as chest: 2 of 6 within one level, against the
    # baseline's 3 of 6 on the same rows. Landmark alone keeps its 4 of 6.
    rows = [
        {**row, "outcomes": {**row["outcomes"], "geometry": level("chest")}}
        if row["photo_id"] in ("A01", "A02")
        else row
        for row in HAND_SET
    ]
    report = report_of(load(tmp_path / "computed", no_pair, set_a=rows))
    lines = section(report, "Baseline")
    assert lines[0] == (
        "The baseline gives every photo the same answers: the level knee and the class"
        " NPATV. Both are computed from these development rows: the most common level"
        " the alerts gave, and the most common class they stated (C424)."
    )
    # One sentence where the baseline's figure is the better one, and none for a tie:
    # NPLV photos caught (2 of 2 on both sides), and geometry's underestimation.
    # The within-one sentence comes only under landmark plus geometry.
    npatv = (
        "- The baseline catches more NPATV photos: 2 of 2 (100.0%) against"
        " 1 of 2 (50.0%)."
    )
    assert [line for line in lines if line.startswith(("**", "- "))] == [
        "**Landmark alone**",
        (
            "- The baseline's underestimation is lower: 2 of 6 (33.3%) against"
            " 3 of 6 (50.0%)."
        ),
        npatv,
        "**Landmark plus geometry**",
        (
            "- The baseline's within-one agreement is higher: 3 of 6 (50.0%) against"
            " 2 of 6 (33.3%)."
        ),
        npatv,
    ]
    assert metric_rows(section_text(report, "Baseline"))[:2] == [
        (
            "| Landmark alone | 2 of 6 (33.3%) | 4 of 6 (66.7%) | 3 of 6 (50.0%)"
            " | 4 of 6 (66.7%) | 2 of 2 (100.0%) | 1 of 2 (50.0%) |"
        ),
        (
            "| Baseline, same rows | 2 of 6 (33.3%) | 3 of 6 (50.0%) | 2 of 6 (33.3%)"
            " | 2 of 6 (33.3%) | 2 of 2 (100.0%) | 2 of 2 (100.0%) |"
        ),
    ]
    # In Task 3's set itself, the baseline is behind on within-one for both.
    same = section(
        report_of(load(tmp_path / "same", no_pair, set_a=HAND_SET)), "Baseline"
    )
    assert not [line for line in same if "within-one" in line]
    # A sealed run takes the pair from run.json.
    frozen = section(
        report_of(
            load(
                tmp_path / "frozen",
                run_json(kind="sealed"),
                set_a=HAND_SET,
                a_neg=[a_neg_row("N01")],
            )
        ),
        "Baseline",
    )
    assert frozen[0] == (
        "The baseline gives every photo the same answers: the level knee and the class"
        " NPLV. Both come from run.json."
    )


def test_by_level_hides_small_percentages(tmp_path):
    rows = [set_a_row(f"A0{number}") for number in range(1, 5)]
    rows += [
        set_a_row(
            f"A1{number}",
            label="waist deep",
            landmark=level("waist"),
            geometry=level("tire"),
        )
        for number in range(5)
    ]
    lines = section(
        report_of(load(tmp_path, run_json(), set_a=rows)), "By the alert's level"
    )
    knee = [line for line in lines if line.startswith("| knee |")]
    waist = [line for line in lines if line.startswith("| waist |")]
    # One table for each configuration.
    assert knee == ["| knee | n = 4 | 4 | 4 | 4 | 0 |"] * 2
    assert waist == [
        "| waist | n = 5 | 5 | 5 of 5 (100.0%) | 5 of 5 (100.0%) | 0 of 5 (0.0%) |",
        "| waist | n = 5 | 5 | 0 of 5 (0.0%) | 5 of 5 (100.0%) | 5 of 5 (100.0%) |",
    ]


def test_replay_columns(tmp_path):
    report = report_of(load(tmp_path / "replayed", run_json(), set_a=replay_rows()))
    assert metric_header(report) == (
        "| Metric | Landmark alone | Landmark alone (replay) | Landmark plus geometry |"
    )
    assert (
        "- Landmark alone, within one level: 5 of 6 (83.3%) in-sample, 2 of 6 (33.3%)"
        " in replay (3 fewer photos)."
    ) in section(report, "Set A: every metric")
    plain = report_of(load(tmp_path / "plain", run_json(), set_a=HAND_SET))
    assert "(replay)" not in plain
    assert "fewer photo" not in plain


def test_no_verdict_words(tmp_path):
    no_pair = without(run_json(), "baseline_level", "baseline_class")
    # Every photo read as "no flood seen", against knee-deep alerts: the constant
    # knee is ahead on every compared figure.
    behind = load(
        tmp_path / "behind",
        no_pair,
        set_a=photos((6, nfs(), nfs())),
        a_neg=[a_neg_row("N01")],
    )
    report = report_of(behind)
    assert (
        len([line for line in section(report, "Baseline") if line.startswith("- ")])
        == 8
    )
    assert "overfit" not in report.lower()
    assert "underfit" not in report.lower()


def test_review_sheet(tmp_path):
    run = full_run(tmp_path / "development", kind="development")
    text = build_review(run).decode("utf-8")
    assert text.endswith("\r\n")
    assert "\n" not in text.replace("\r\n", "")
    header, *rows = csv.reader(io.StringIO(text, newline=""))
    assert header == [
        "set",
        "photo_id",
        "event_id",
        "excluded",
        "alert_level",
        "alert_class",
        "landmark_result",
        "landmark_class",
        "landmark_landmark",
        "geometry_result",
        "geometry_class",
        "geometry_landmark",
        "m8_agreement",
        "m8_detail",
        "claude_check",
        "rene_verdict",
        "rene_note",
    ]
    assert [row[:2] for row in rows] == [
        *(["set_a", f"A{number:02d}"] for number in range(1, 17)),
        *(["a_neg", f"N0{number}"] for number in range(1, 6)),
    ]
    by_id = {row[1]: dict(zip(header, row)) for row in rows}
    assert by_id["A10"]["excluded"] == "depth or passability label visible in the image"
    assert by_id["N04"]["excluded"] == "duplicate or repost"
    assert by_id["A01"]["excluded"] == ""
    # Claude annotates first, then Rene reviews (C426): all three start blank.
    assert all(row[-3:] == ["", "", ""] for row in rows)
    a01 = by_id["A01"]
    assert [a01[key] for key in header[4:9]] == ["knee", "NPLV", "knee", "NPLV", "hub"]
    assert a01["m8_agreement"] == "2 of 4"
    assert a01["m8_detail"] == (
        "body 2: door_sill/door_sill; wheel 3: hub/rim_top; person 5: knee/knee;"
        " wheel 7: hub/unanswered"
    )
    # An excluded photo's labels count for nothing, as in landmark agreement.
    assert (by_id["A10"]["m8_agreement"], by_id["A10"]["m8_detail"]) == ("", "")
    assert [by_id[photo]["geometry_result"] for photo in ("A03", "A05", "A06")] == [
        "no_flood_seen",
        "refused:too_dark",
        "failed:model_error",
    ]
    # The class is the one scoring counts: PATV for "no flood seen" (rules §7), and
    # none for a refusal or a failure.
    assert [by_id[photo]["geometry_class"] for photo in ("A03", "A05", "A06")] == [
        "PATV",
        "",
        "",
    ]
    assert by_id["A03"]["geometry_landmark"] == ""
    assert [by_id["N01"][key] for key in ("landmark_class", "geometry_class")] == [
        "PATV",
        "PATV",
    ]
    assert [by_id["A08"][key] for key in ("alert_level", "alert_class")] == ["", "NPLV"]
    assert [by_id["N02"][key] for key in header[3:9]] == [
        "",
        "",
        "",
        "gutter",
        "PATV",
        "hub",
    ]
    assert build_review(full_run(tmp_path / "final")) is None


def test_required_words(tmp_path):
    report = report_of(full_run(tmp_path))
    assert "indicative" in report
    assert "agreement" in report
    lines = report.split("\n")
    assert (
        "Lusot estimates depth at one spot. It is not advice to cross."
        " Follow MMDA and local advisories."
    ) in lines
    assert "Not affiliated with MMDA." in lines
    assert "accuracy" not in report.lower()
    assert "mmda's 9 levels" not in report.lower()


def test_never_says_safe(tmp_path):
    for number, (name, make) in enumerate(RUNS.items()):
        run, first = make(tmp_path / f"run{number}")
        files = build_report(run, first_run=first)
        for file, content in files.items():
            assert "safe" not in content.decode("utf-8").lower(), (name, file)
        review = build_review(run)
        assert review is None or "safe" not in review.decode("utf-8").lower(), name


def banned(word: str) -> str:
    return (
        f"report.md would contain a banned word ({word}); check the run's text and"
        " reason fields"
    )


def test_report_refuses_its_banned_words(tmp_path):
    # Only free text copied from run.json can bring one in, such as a rerun's reason,
    # or a token from the rows, such as a refusal's reason.
    first = load(tmp_path / "first", run_json(), set_a=HAND_SET)
    rerun = load(
        tmp_path / "first" / "rerun",
        run_json(rerun_reason="rerun: unsafe light"),
        set_a=HAND_SET,
    )
    with pytest.raises(ValueError) as refused:
        build_report(rerun, first_run=first)
    assert str(refused.value) == banned("safe")
    # The message names the file and the word, never the text around it.
    assert str(refused.value).isascii()
    assert "light" not in str(refused.value)
    # Any case, from any of run.json's free-text fields.
    stop = {"at": "21:10", "cause": "Safety restart", "resumed": "21:40"}
    cases = [
        (run_json(stops=[stop]), HAND_SET, "safe"),
        (run_json(frozen={"model": "ACCURACY-1"}), HAND_SET, "accuracy"),
        (
            run_json(
                geometry_default="dropped", geometry_dropped_reason="underfits Set A"
            ),
            landmark_only(list(HAND_SET)),
            "underfit",
        ),
        (
            run_json(),
            [
                set_a_row(
                    "A01",
                    landmark={"status": "refused", "refusalReason": "overfit_glare"},
                )
            ],
            "overfit",
        ),
    ]
    for number, (manifest, rows, word) in enumerate(cases):
        run = load(tmp_path / f"case{number}", manifest, set_a=rows)
        with pytest.raises(ValueError) as refused:
            build_report(run)
        assert str(refused.value) == banned(word), word


def test_both_configurations_and_the_self_check_line(tmp_path):
    off = report_of(full_run(tmp_path / "off"))
    assert metric_header(off) == "| Metric | Landmark alone | Landmark plus geometry |"
    assert "Self-check: off (decided 2026-10-29, MS3)." in section(off, "Release gate")
    on, _ = RUNS["self-check on"](tmp_path / "on")
    report = report_of(on)
    assert metric_header(report) == (
        "| Metric | Landmark alone | Landmark plus geometry"
        " | Landmark plus geometry, without the self-check |"
    )
    assert (
        "Self-check: on (decided 2026-10-29, MS3). Its extra row, geometry without the"
        " self-check, is reported but never chosen (eval/rules.md §8)."
    ) in section(report, "Release gate")
    # The extra row is reported, but it is neither of the two that the rule chooses
    # between.
    assert len(metric_rows(section_text(report, "Reported first"))) == 2
    assert (
        "geometry_no_self_check"
        in json.loads(build_report(on)["summary.json"])["configurations"]
    )
    undecided = without(run_json(), "self_check_decided")
    lines = section(
        report_of(load(tmp_path / "undecided", undecided, set_a=HAND_SET)),
        "Outcome rule on development data",
    )
    assert "Self-check: off (decided: not recorded, MS3)." in lines


def test_shipped_configuration_comes_first(tmp_path):
    # Geometry answers the 10 photos that landmark alone refused and underestimates one
    # of them, so the count rises (test_gate).
    rise = photos(
        (3, UNDER, UNDER), (1, REFUSED, UNDER), (13, KNEE, KNEE), (9, REFUSED, KNEE)
    )
    report = report_of(load(tmp_path / "rise", run_json(), set_a=rise))
    assert metric_rows(section_text(report, "Reported first")) == [
        (
            "| Landmark alone (ships) | 3 of 16 (18.8%) | 16 of 16 (100.0%)"
            " | 16 of 26 (61.5%) |"
        ),
        (
            "| Landmark plus geometry | 4 of 26 (15.4%) | 26 of 26 (100.0%)"
            " | 26 of 26 (100.0%) |"
        ),
    ]
    stays = report_of(
        load(tmp_path / "stays", run_json(), set_a=photos((20, KNEE, KNEE)))
    )
    first, second = metric_rows(section_text(stays, "Reported first"))
    assert first.startswith("| Landmark plus geometry (ships) |")
    assert second.startswith("| Landmark alone |")


def test_gate_rows_and_decision(tmp_path):
    full = section(report_of(full_run(tmp_path / "full")), "Release gate")
    assert (
        "**Decision:** Geometry stays in the level path, so landmark plus geometry"
        " ships. Inches are shown."
    ) in full
    assert not [line for line in full if line.startswith("- ")]
    # Geometry's count rises while Set B meets its three targets, so the decision line
    # itself says why no inches show.
    rise = load(
        tmp_path / "rise",
        run_json(kind="sealed"),
        set_a=photos(
            (3, UNDER, UNDER), (1, REFUSED, UNDER), (13, KNEE, KNEE), (9, REFUSED, KNEE)
        ),
        a_neg=[],
        set_b=wheel_rows("B"),
    )
    lines = section(report_of(rise), "Release gate")
    assert (
        "**Decision:** Geometry doesn't stay, so landmark alone ships. Inches aren't"
        " shown, because geometry doesn't ship."
    ) in lines
    assert [line for line in lines if line.startswith("- ")] == [
        (
            "- Set A underestimation rises with geometry, in its count:"
            " 4 of 26 (15.4%) with geometry, 3 of 16 (18.8%) without."
        )
    ]
    # An undefined check still shows its n, taken from the scores.
    unanswered = load(
        tmp_path / "unanswered", run_json(), set_a=photos((5, KNEE, REFUSED))
    )
    rows = {
        cells(row)[0]: cells(row)[1:]
        for row in metric_rows(
            section_text(report_of(unanswered), "Outcome rule on development data")
        )
    }
    assert rows["Set A underestimation"] == [
        "0 of 0 (undefined) with geometry, 0 of 5 (0.0%) without",
        "no rise in the rate or the count",
        "no (undefined)",
    ]
    assert rows["Set A coverage (guard)"][2] == "no"
    assert rows["Set B median depth error"] == [
        "Set B wasn't run (n = 0)",
        "at most 3 in",
        "no (undefined)",
    ]


def test_development_report(tmp_path):
    report = report_of(full_run(tmp_path, kind="development"))
    expected = list(HEADINGS)
    expected[0] = "# Lusot evaluation report (development data)"
    expected[expected.index("## Release gate")] = "## Outcome rule on development data"
    expected.insert(
        expected.index("## Landmark agreement") + 1, "## Vehicle types (development)"
    )
    assert headings(report) == expected
    assert report.split("\n")[2].startswith(
        "This report scores development data, not the sealed run."
    )
    assert section(report, "Outcome rule on development data")[0] == (
        "On development data, this outcome rule sets geometry's live default (C309)."
        " It isn't the release gate."
    )
    assert metric_rows(section_text(report, "Vehicle types (development)")) == [
        "| pickup | sedan_hatch | 1 of 1 (100.0%) |"
    ]


def test_rerun_report(tmp_path):
    rerun, first = rerun_pair(tmp_path)
    report = report_of(rerun, first)
    expected = list(HEADINGS)
    expected.insert(expected.index("## Exclusions"), "## First run, for comparison")
    assert headings(report) == expected
    opening = report.split("\n\n")[2]
    assert "eval/rules.md §10's one disclosed rerun" in opening
    assert f'"{RERUN_REASON}"' in opening
    assert "ran a second time on the sealed sets, on 2026-11-02" in report
    comparison = section(report, "First run, for comparison")
    for config in ("landmark", "geometry"):
        scores = score_set_a(first.set_a, config)
        rates = (scores.under, scores.passability, scores.coverage)
        row = next(
            line for line in comparison if line.startswith(f"| {LABELS[config]}")
        )
        assert row.endswith(" | ".join(map(fmt_rate, rates)) + " |"), config
    # The rerun's own headline differs: A02 now reads knee.
    assert "| Landmark alone | 3 of 8 (37.5%) |" in "\n".join(comparison)
    assert "| Landmark alone | 2 of 8 (25.0%) |" in "\n".join(
        section(report, "Reported first")
    )
    assert "### Release gate" in comparison
    with pytest.raises(ValueError, match="C421"):
        build_report(rerun)
    with pytest.raises(ValueError, match="C421"):
        build_report(first, first_run=first)


def test_geometry_dropped_report(tmp_path):
    run, _ = RUNS["geometry dropped"](tmp_path)
    files = build_report(run)
    report = files["report.md"].decode("utf-8")
    assert sorted(name for name in files if name.startswith("level-matrix-")) == [
        "level-matrix-landmark.svg"
    ]
    reported = metric_rows(section_text(report, "Reported first"))
    assert [cells(row)[0] for row in reported] == ["Landmark alone (ships)"]
    assert metric_header(report) == "| Metric | Landmark alone |"
    # decide() isn't called, so the section shows no checks and no targets.
    assert section(report, "Release gate") == [
        "Self-check: off (decided 2026-10-29, MS3).",
        (
            "Geometry was dropped before the freeze. The reason run.json records:"
            ' "median error over 3 in". With landmark alone left, the outcome rule'
            " has nothing to choose (C418), and no inches show."
        ),
    ]
    summary = json.loads(files["summary.json"])
    assert (summary["shipped"], summary["geometry_stays"], summary["inches_shown"]) == (
        "landmark",
        False,
        False,
    )
    assert list(summary["configurations"]) == ["landmark"]


def test_report_with_empty_sets(tmp_path):
    run = empty_sets(tmp_path)
    files = build_report(run)
    report = files["report.md"].decode("utf-8")
    assert metric_rows(section_text(report, "Reported first")) == [
        (
            "| Landmark alone (ships) | 0 of 0 (undefined) | 0 of 0 (undefined)"
            " | 0 of 3 (0.0%) |"
        ),
        (
            "| Landmark plus geometry | 0 of 0 (undefined) | 0 of 0 (undefined)"
            " | 0 of 3 (0.0%) |"
        ),
    ]
    assert "| False flood rate | 0 of 0 (undefined) | 0 of 0 (undefined) |" in section(
        report, "A-neg: flood-free photos"
    )
    assert (
        "| geometry | 0 of 0 (undefined) | undefined (n = 0) | undefined (n = 0)"
        in ("\n".join(section(report, "Set B")))
    )
    assert section(report, "Set D") == [NOT_RUN]
    assert section(report, "Latency") == [NO_LATENCY]
    summary = json.loads(files["summary.json"])
    assert summary["set_b"] == {
        "wheels": 0,
        "measured": {"k": 0, "n": 0},
        "median_error_in": None,
        "worst_error_in": None,
        "envelope": {"k": 0, "n": 0},
        "sam_water_found": {"k": 0, "n": 0},
        "no_answer": 0,
    }
    assert build_review(run) is None


def test_report_ignores_row_order(tmp_path):
    def shuffled(rows: list) -> list:
        rows = list(rows)
        random.Random(6).shuffle(rows)
        return rows

    sets = {
        "set_a": set_a_rows(),
        "a_neg": a_neg_rows(),
        "set_b": wheel_rows("B"),
        "set_d": wheel_rows("D")[:2],
        "latency": LATENCY,
    }
    for number, kind in enumerate(("sealed", "development")):
        manifest = full_run_json(kind=kind)
        ordered = load(tmp_path / f"kind{number}" / "ordered", manifest, **sets)
        mixed = load(
            tmp_path / f"kind{number}" / "mixed",
            manifest,
            **{name: shuffled(rows) for name, rows in sets.items()},
        )
        assert mixed.set_a != ordered.set_a and mixed.set_b != ordered.set_b
        assert build_report(mixed) == build_report(ordered), kind
        assert build_review(mixed) == build_review(ordered), kind


def test_summary_json(tmp_path):
    run = full_run(tmp_path)
    files = build_report(run)
    text = files["summary.json"].decode("utf-8")
    summary = json.loads(text)
    assert text == json.dumps(summary, indent=2, sort_keys=True) + "\n"
    assert set(summary) == {
        "kind",
        "synthetic",
        "rerun",
        "date",
        "rules_version",
        "shipped",
        "geometry_stays",
        "inches_shown",
        "configurations",
        "set_b",
        "baseline_level",
        "baseline_class",
        "service_retries",
    }
    assert [summary[key] for key in ("kind", "date", "rules_version")] == [
        "sealed",
        "2026-10-30",
        "0.7",
    ]
    assert (summary["synthetic"], summary["rerun"]) == (False, False)
    assert (summary["shipped"], summary["geometry_stays"], summary["inches_shown"]) == (
        "geometry",
        True,
        True,
    )
    assert (summary["baseline_level"], summary["baseline_class"]) == ("knee", "NPLV")
    reported = metric_rows(
        section_text(files["report.md"].decode("utf-8"), "Reported first")
    )
    assert reported[0].startswith(f"| {LABELS[summary['shipped']]} (ships) |")
    assert list(summary["configurations"]) == ["geometry", "landmark"]
    for config, figures in summary["configurations"].items():
        scores = score_set_a(run.set_a, config)
        assert figures == {
            "underestimation": {"k": scores.under.k, "n": scores.under.n},
            "passability": {"k": scores.passability.k, "n": scores.passability.n},
            "coverage": {"k": scores.coverage.k, "n": scores.coverage.n},
            "exact": {"k": scores.exact.k, "n": scores.exact.n},
            "within_one": {"k": scores.within_one.k, "n": scores.within_one.n},
            "refused": scores.refused,
            "failed": scores.failed,
        }
        row = next(line for line in reported if line.startswith(f"| {LABELS[config]}"))
        rates = [
            fmt_rate(Rate(**figures[key]))
            for key in ("underestimation", "passability", "coverage")
        ]
        assert cells(row)[1:] == rates, config
    # Errors of 0 to 1.5 in on 7 of 8 wheels, each inside its envelope.
    assert summary["set_b"] == {
        "wheels": 8,
        "measured": {"k": 7, "n": 8},
        "median_error_in": "0.75",
        "worst_error_in": "1.50",
        "envelope": {"k": 7, "n": 7},
        "sam_water_found": {"k": 7, "n": 8},
        "no_answer": 0,
    }


def water_line(rate: str, left_out: int) -> str:
    return (
        f"SAM found water on {rate} wheels; left out: {left_out} with no usable answer"
        " from Meta (model_error)."
    )


def test_a_wheel_with_no_answer_is_counted_beside_the_water_rate(tmp_path):
    # MS3b exports a wheel whose Meta call failed twice with every variant
    # model_error and no water answer. It stays a wheel that wasn't measured, but
    # SAM's water rate leaves it out, and the report and summary count it.
    def silent(crop_id: str) -> dict:
        estimates = dict.fromkeys(VARIANTS, unmeasured("model_error"))
        return set_b_row(crop_id, sam_water_found=None, estimates=estimates)

    run = load(
        tmp_path,
        run_json(),
        set_b=[*wheel_rows("B"), silent("B09")],
        set_d=[silent("D01")],
    )
    files = build_report(run)
    report = files["report.md"].decode("utf-8")
    assert water_line("7 of 8 (87.5%)", 1) in section(report, "Set B")
    assert water_line("0 of 0 (undefined)", 1) in section(report, "Set D")
    rows = metric_rows(section_text(report, "Set B"))
    assert rows[0].startswith("| geometry | 7 of 9 (77.8%) |")
    summary = json.loads(files["summary.json"])["set_b"]
    assert summary["wheels"] == 9
    assert summary["measured"] == {"k": 7, "n": 9}
    assert summary["sam_water_found"] == {"k": 7, "n": 8}
    assert summary["no_answer"] == 1


def test_summary_marks_synthetic_data_and_the_rerun(tmp_path):
    # The accuracy page reads summary.json (C409), so a fixture's figures can't pass
    # for a sealed run's (C422), nor a rerun's for a first run's (C421).
    def marks(run: Run, first_run: Run | None = None) -> tuple[object, object]:
        summary = json.loads(build_report(run, first_run=first_run)["summary.json"])
        return summary["synthetic"], summary["rerun"]

    assert marks(full_run(tmp_path / "final")) == (False, False)
    assert marks(full_run(tmp_path / "synthetic", synthetic=True)) == (True, False)
    assert marks(*rerun_pair(tmp_path / "rerun")) == (False, True)


FROZEN = "Frozen versions and data"


def retries_line(count: int) -> str:
    return (
        "Photos and crops retried once after a Meta service failure in this run"
        f" (MS6E-Q6): {count}."
    )


def run_without_retries(folder: Path, **overrides: object) -> Run:
    """A full run whose run.json lacks service_retries, which only a development run
    may do."""
    return load(
        folder,
        without(full_run_json(kind="development", **overrides), "service_retries"),
        set_a=set_a_rows(),
        a_neg=a_neg_rows(),
        set_b=wheel_rows("B"),
        set_d=wheel_rows("D")[:2],
        latency=LATENCY,
    )


def test_service_retries_line(tmp_path):
    # MS6E-Q6 (a): a sealed report always discloses how many photos and crops were
    # retried, and a development report only when there were some. The count covers
    # the whole run (Set A's photos, and Set B's and Set D's items), so the line sits
    # with the run's other events, beside the stops table, and not in a set's section.
    for number, (kind, count) in enumerate((("sealed", 0), ("sealed", 3))):
        run = full_run(tmp_path / f"run{number}", kind=kind, service_retries=count)
        report = report_of(run)
        lines = section(report, FROZEN)
        assert lines.count(retries_line(count)) == 1, (kind, count)
        assert lines[lines.index(retries_line(count)) - 1].startswith("| 21:10 |")
        assert "retried once" not in "".join(section(report, "Set A: every metric"))
    two = full_run(tmp_path / "two", kind="development", service_retries=2)
    assert retries_line(2) in section(report_of(two), FROZEN)
    for name, run in (
        ("an absent count", run_without_retries(tmp_path / "absent")),
        (
            "a count of 0",
            full_run(tmp_path / "zero", kind="development", service_retries=0),
        ),
    ):
        assert "retried once" not in report_of(run), name
    # Set A not run: its section says so and nothing else, and the count shows in the
    # run's own section.
    set_b_only = load(
        tmp_path / "set_b_only",
        run_json(service_retries=2),
        set_b=wheel_rows("B"),
    )
    report = report_of(set_b_only)
    assert section(report, "Set A: every metric") == [NOT_RUN]
    assert retries_line(2) in section(report, FROZEN)


def test_service_retries_in_the_summary(tmp_path):
    def summarised(run: Run) -> object:
        return json.loads(build_report(run)["summary.json"])["service_retries"]

    assert summarised(full_run(tmp_path / "final", service_retries=3)) == 3
    assert summarised(full_run(tmp_path / "zero", service_retries=0)) == 0
    absent = summarised(run_without_retries(tmp_path / "absent"))
    assert absent == 0 and type(absent) is int
    two = full_run(tmp_path / "two", kind="development", service_retries=2)
    assert summarised(two) == 2


def test_exclusions_listed(tmp_path):
    run = full_run(tmp_path)
    text = section_text(report_of(run), "Exclusions")
    lines = section(report_of(run), "Exclusions")
    for photo, reason in (*excluded_set_a(run.set_a), *excluded_a_neg(run.a_neg)):
        assert any(
            cells(line)[0] == reason and photo in cells(line)[2].split(", ")
            for line in lines
            if line.startswith("|")
        ), photo
    # Each rules §9 reason in its order, with its count and its ids, zeros included
    # (spec §4.4, item 7). A-neg has only its own two (MS6E-Q1, item 6).
    tables = [block for block in paragraphs(text) if block[0].startswith("|")]
    header = ["| Reason | Photos | Ids |", "|---|---|---|"]
    assert tables == [
        [
            *header,
            "| not posted by MMDA or a city government | 1 | A12 |",
            "| depth or passability label visible in the image | 1 | A10 |",
            "| no matching alert | 0 | none |",
            "| unmapped label | 0 | none |",
            "| conflicting alerts | 1 | A13 |",
            "| duplicate or repost | 1 | A14 |",
            "| outside Metro Manila | 1 | A16 |",
            "| the file can't be decoded | 0 | none |",
        ],
        [
            *header,
            "| duplicate or repost | 1 | N04 |",
            "| the file can't be decoded | 1 | N05 |",
        ],
    ]
    assert [cells(row)[0] for row in tables[0][2:]] == list(REASONS)
    # With nothing excluded, each reason still shows, at 0.
    clean = load(tmp_path / "clean", run_json(), a_neg=[a_neg_row("N01")])
    assert paragraphs(section_text(report_of(clean), "Exclusions"))[1:] == [
        [f"**Set A:** {NOT_RUN}"],
        ["**A-neg:** 0 of 1 (0.0%) photos excluded."],
        [
            *header,
            "| duplicate or repost | 0 | none |",
            "| the file can't be decoded | 0 | none |",
        ],
    ]
    assert "**Set A:** 5 of 16 (31.3%) photos excluded." in lines
    assert "**A-neg:** 2 of 5 (40.0%) photos excluded." in lines
    assert [line for line in lines if line.startswith("Left out")] == [
        (
            "Left out of passability agreement only, because the passability label"
            " didn't map: A11 (n = 1)."
        )
    ]


def test_landmark_agreement_counts_refusals(tmp_path):
    # Muse Spark answered, then Lusot refused: no coverage, but the photo's labels
    # count in landmark agreement, and its lead says so, since coverage's "answered"
    # leaves refusals out.
    row = set_a_row(
        "A01",
        landmark=REFUSED,
        geometry=REFUSED,
        answer=answer(wheels=[wheel(1, "hub")]),
        m8=[m8(1, "wheel", "hub")],
    )
    report = report_of(load(tmp_path, run_json(), set_a=[row]))
    lines = section(report, "Landmark agreement")
    assert lines[0] == (
        "Muse Spark's landmark against our M8 label for the same box (C415), over the"
        " Set A photos kept that Muse Spark answered, Lusot's refusals included. Every"
        " configuration shares Muse Spark's answer, so this is counted once."
    )
    assert "| All | 1 of 1 (100.0%) |" in lines
    assert "| Coverage | 0 of 1 (0.0%) | 0 of 1 (0.0%) |" in section(
        report, "Set A: every metric"
    )


def test_sections_show_their_scores(tmp_path):
    report = report_of(full_run(tmp_path))
    expected = {
        "Set A: every metric": [
            "| Underestimation | 3 of 8 (37.5%) | 3 of 8 (37.5%) |",
            # 1 - 35/81 over the 8 pairs, "no flood seen" read as below_gutter.
            "| Weighted kappa (quadratic) | 0.57 (n = 8) | 0.57 (n = 8) |",
        ],
        "Landmark agreement": [
            "| Wheel | 0 of 2 (0.0%) |",
            "| Vehicle body | 1 of 1 (100.0%) |",
            "| Person | 1 of 1 (100.0%) |",
            "| All | 2 of 4 (50.0%) |",
            (
                "Boxes that Muse Spark's answer skipped, which count as disagreements:"
                " 1 of 4 (25.0%). M8 labels that matched no box, which are left out:"
                " n = 1."
            ),
        ],
        "A-neg: flood-free photos": [
            "| False flood rate | 1 of 3 (33.3%) | 0 of 3 (0.0%) |",
            "| False flood rate, wet surface | 0 of 2 (0.0%) | 0 of 2 (0.0%) |",
            "| False flood rate, dry surface | 1 of 1 (100.0%) | 0 of 1 (0.0%) |",
        ],
        # A05 and N03, both dark and refused.
        "Correct refusals": [
            "| Correct refusals | 2 of 2 (100.0%) | 2 of 2 (100.0%) |"
        ],
        # A03, A06, A09 and A15; A06 failed.
        "Subsets": [
            (
                "| tire or deeper, by the alert | n = 4 | 3 of 4 (75.0%)"
                " | 1 of 3 (33.3%) | 2 of 3 (66.7%) |"
            )
        ],
        # Errors 0, 0.25, 0.5 and 0.75 in: a median of 0.375 in, rounded half up.
        "Set B": [
            (
                "| geometry, vehicle type sedan_hatch | 4 of 4 (100.0%)"
                " | 0.38 in (n = 4) | 0.75 in (n = 4) | 4 of 4 (100.0%) |"
            )
        ],
        "Latency": [
            "| Median | 5.0 s (n = 5) |",
            "| 95th percentile, nearest rank | 9.1 s (n = 5) |",
        ],
    }
    for heading, lines in expected.items():
        found = section(report, heading)
        for line in lines:
            assert line in found, (heading, line)


def test_frozen_versions_and_data(tmp_path):
    lines = section(report_of(full_run(tmp_path)), "Frozen versions and data")
    # The freeze commit and geometry's live default come before the lists.
    assert lines[:4] == [
        "Scored by eval/rules.md v0.7.",
        f"Freeze commit: `{'ab' * 20}`.",
        "Geometry's live default before the run (C309): on.",
        "| Frozen | Version |",
    ]
    dropped, _ = RUNS["geometry dropped"](tmp_path / "dropped")
    assert (
        "Geometry's live default before the run (C309): dropped before the freeze"
        " (C418)."
    ) in section(report_of(dropped), "Frozen versions and data")
    unrecorded = without(run_json(), "freeze_commit", "geometry_default")
    assert section(
        report_of(load(tmp_path / "unrecorded", unrecorded, set_a=HAND_SET)),
        "Frozen versions and data",
    )[1:3] == [
        "Freeze commit: not recorded.",
        "Geometry's live default before the run (C309): not recorded.",
    ]
    assert "| model | muse-spark-1.3 |" in lines
    assert "| Set A | v1 | 7 | 16 photos from 2 events |" in lines
    assert "| A-neg | v1 | 7 | 5 photos from 1 event |" in lines
    assert "| Set B | v1 | 7 | 8 wheels in 4 crops of 2 cars |" in lines
    assert "| 21:10 | lost connection | 21:40 |" in lines
    assert lines[-1] == (
        "The face blur runs before Meta receives a photo. It can miss faces that are"
        " very small, side-on, partly covered or in the dark."
    )
    rebuild = section(report_of(full_run(tmp_path / "again")), "Rebuild this report")
    assert "python eval/run_eval.py --from-saved" in rebuild
    assert "python3 eval/run_eval.py --from-saved" in rebuild
