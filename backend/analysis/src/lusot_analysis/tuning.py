"""Every cutoff the pipeline tunes, in one versioned place (C310).

The Lambda and the offline runner read `TUNING`. `START` keeps the start values, so a
replay and the tests can name them. Each value is chosen on development data only, by
C310's rules, and frozen before the sealed run (v0.7 item 10.1). `untuned` names the
values still at their start values.

Change log. Each version names its date and every value it changed, with that value's
development evidence (n and the harness figures used), or "untuned".

- tuning-v1 (Oct 29, 2026): the start values of spec §4 (C301 to C305, C312, C325, G3)
  and MS3a's (C44, C56, C70). Untuned: every value.
- tuning-v2 (Nov 2, 2026): two values, chosen by $0 replays of the 120 Set C
  development runs and scored on the 55 photos the blind double relabel of Nov 2 agreed
  on. A-neg's 10 development photos, run once, gave no false level with either.
  - min_person_side_px 0 → 60 (C92): a smaller person's reading can refuse the photo
    but never sets the level, and blocks no one.
  - no_flood_share_max 1.0 → 0.25 (C93): 2 development "no flood" results with water
    over 0.60 of the lower half become refusals; no A-neg result changes.
  touch_share_min stays 0.25: 0.10 passed on the agreed labels but was held, since
  OL131 (label unsure) would read knee where one relabel read tire (C331). Untuned:
  every other value.
"""

from __future__ import annotations

from dataclasses import dataclass, fields


@dataclass(frozen=True)
class Tuning:
    """One version of the cutoffs. Each default is its start value."""

    version: str
    # Step 3, the touch check and the ragged edge (C301 to C303).
    touch_tolerance_px: float = 5.0  # T
    touch_share_min: float = 0.25  # of the lower-outline columns
    ragged_iqr_share: float = 0.10  # of the object's box height (R86)
    # Step 4, the geometry checks (C305).
    daylight_brightness_min: float = 80.0
    rim_score_min: float = 0.5
    # Check 9's factors, tuned on Set B development rims only (C310). rim_size_low
    # never goes below 0.50, and rim_size_high never above 1.55.
    rim_size_low: float = 0.85
    rim_size_high: float = 1.15
    rim_edge_k: float = 1.0  # k, 1.0 until Set B calibrates it (G3)
    # MS3a's quality gate (C44).
    brightness_min: float = 40.0
    sharpness_min: float = 25.0
    # MS3a's cuts before numbering, checked on Manila photos, never swept (C310).
    min_wheel_side_px: int = 40  # C56
    max_vehicles: int = 6  # C70
    max_people: int = 6
    # What Muse Spark sees and how hard it thinks (C312, C325).
    reasoning_effort: str | None = None  # None sends no effort: Muse Spark picks
    drawing: str = "boxes-v1"  # MS3a's drawing of the numbered boxes
    # Added in tuning-v2 (Nov 2). Each start value turns its rule off, so a run saved
    # before tuning-v2 replays as it was saved (B3).
    min_person_side_px: int = 0  # C92: a smaller person never decides nor blocks
    no_flood_share_max: float = 1.0  # C93: SAM's water over this share of the lower
    # half makes a "no" on standing water refused, water_unsure
    untuned: frozenset[str] = frozenset()  # the names still at their start values


START = Tuning(
    version="tuning-v1",
    untuned=frozenset(f.name for f in fields(Tuning)) - {"version", "untuned"},
)
TUNED_IN_V2 = frozenset({"min_person_side_px", "no_flood_share_max"})
TUNING = Tuning(
    version="tuning-v2",
    min_person_side_px=60,
    no_flood_share_max=0.25,
    untuned=START.untuned - TUNED_IN_V2,
)
