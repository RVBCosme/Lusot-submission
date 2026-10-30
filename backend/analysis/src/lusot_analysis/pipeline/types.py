"""Types the pipeline steps share: the outcome, a reference and the model client.

The Meta client's result types and BlurredImage are imported for type checking only
(R80). The annotations stay strings, so this file loads neither the OpenAI SDK nor
OpenCV.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Protocol

from lusot_analysis import rules

if TYPE_CHECKING:
    from lusot_analysis.face_blur import BlurredImage
    from lusot_analysis.meta_client import SamResult, SparkResult

# The reasons a report ends with (spec §3.4). One field, refusalReason, carries both
# lists, and the status tells them apart (C50).
REFUSED_REASONS = (
    "too_dark",
    "too_blurry",
    "photo_unusable",
    "water_unsure",
    "no_water_found",
    "no_usable_reference",
    "references_disagree",
    "model_declined",  # Muse Spark refused to answer (C86)
)
FAILED_REASONS = (
    "model_calls_paused",
    "photo_missing",
    "bad_file",
    "model_error",
    "pipeline_error",
)
_REASONS = {"refused": REFUSED_REASONS, "failed": FAILED_REASONS}


@dataclass(frozen=True)
class Outcome:
    """A report's result: a level, no flood seen, a refusal or a failure (C42, C50).

    Build one with `refused`, `failed`, `no_flood` or `level_result`. Any other shape
    raises ValueError, so the three outcomes plan §9 keeps apart can't mix.

    A level result records what set it. When geometry did, it carries its unrounded
    inches, and its level is theirs (C307, C308). A level result built without a
    source becomes a landmark one, as MS3a's were.
    """

    status: Literal["done", "refused", "failed"]
    reason: str | None = None
    no_flood_seen: bool = False
    level: str | None = None
    landmark: str | None = None
    passability: str | None = None
    level_is_floor: bool = False
    basis: Mapping[str, int] | None = None
    level_from: Literal["landmark", "geometry"] | None = None
    depth_in_min: float | None = None
    depth_in_max: float | None = None

    def __post_init__(self) -> None:
        if self.status in _REASONS:
            if self.reason not in _REASONS[self.status]:
                raise ValueError(f"not a {self.status} reason: {self.reason!r}")
            if self.no_flood_seen or self._has_level_fields():
                raise ValueError(f"a {self.status} outcome carries only its reason")
        elif self.status != "done":
            raise ValueError(f"unknown status: {self.status!r}")
        elif self.reason is not None:
            raise ValueError("a done outcome carries no reason")
        elif self.no_flood_seen:
            if self._has_level_fields():
                raise ValueError("no flood seen carries no level fields")
        else:
            self._check_level()
            self._check_source()

    def _has_level_fields(self) -> bool:
        """True when any field that only a level result sets is set."""
        return self.level_is_floor or any(
            value is not None
            for value in (
                self.level,
                self.landmark,
                self.passability,
                self.basis,
                self.level_from,
                self.depth_in_min,
                self.depth_in_max,
            )
        )

    def _check_level(self) -> None:
        if self.level is None:
            raise ValueError("a done outcome needs a level or no_flood_seen")
        if self.level not in rules.LEVELS:
            raise ValueError(f"unknown level: {self.level!r}")
        if not self.landmark or self.basis is None:
            raise ValueError("a level result needs its landmark and basis")
        if self.passability != rules.PASSABILITY[self.level]:
            raise ValueError(f"{self.level} takes {rules.PASSABILITY[self.level]}")
        if set(self.basis) != {"vehicles", "people"}:
            raise ValueError("basis counts vehicles and people, nothing else")
        counts = self.basis.values()
        if min(counts) < 0 or sum(counts) == 0:
            raise ValueError("basis counts are 0 or more, with at least one reference")

    def _check_source(self) -> None:
        if self.level_from is None:
            object.__setattr__(self, "level_from", "landmark")  # MS3a's shape
        if self.level_from not in ("landmark", "geometry"):
            raise ValueError(f"unknown level source: {self.level_from!r}")
        inches = (self.depth_in_min, self.depth_in_max)
        if self.level_from == "landmark":
            if inches != (None, None):
                raise ValueError("a landmark level carries no inches (C307)")
            return
        low, high = inches
        if low is None or high is None:
            raise ValueError("a geometry level carries both its inches")
        if not (math.isfinite(low) and math.isfinite(high) and 0 < low <= high):
            raise ValueError(f"impossible inches: {low!r} to {high!r}")
        if self.level != rules.level_for_inches(high):
            raise ValueError(f"{high!r} in isn't {self.level}")

    @classmethod
    def refused(cls, reason: str) -> Outcome:
        return cls("refused", reason)

    @classmethod
    def failed(cls, reason: str) -> Outcome:
        return cls("failed", reason)

    @classmethod
    def no_flood(cls) -> Outcome:
        return cls("done", no_flood_seen=True)

    @classmethod
    def level_result(
        cls,
        level: str,
        landmark: str,
        level_is_floor: bool,
        basis: Mapping[str, int],
        *,
        level_from: Literal["landmark", "geometry"] = "landmark",
        depth_in: tuple[float, float] | None = None,
    ) -> Outcome:
        """A level with its class. That lookup is step 7 (map).

        `depth_in` is geometry's unrounded min and max, in inches.
        """
        depth_in_min, depth_in_max = depth_in if depth_in is not None else (None, None)
        return cls(
            "done",
            level=level,
            landmark=landmark,
            # .get: an unknown level then fails __post_init__ with a ValueError
            passability=rules.PASSABILITY.get(level),
            level_is_floor=level_is_floor,
            basis=basis,
            level_from=level_from,
            depth_in_min=depth_in_min,
            depth_in_max=depth_in_max,
        )

    def item_fields(self) -> dict[str, object]:
        """The report item's result attributes, as Table 14 names them (spec §3.5).

        A geometry level's inches are stored rounded outward to 0.1 in (C308).
        """
        if self.status != "done":
            return {"status": self.status, "refusalReason": self.reason}
        if self.no_flood_seen:
            return {"status": "done", "noFloodSeen": True}
        fields = {
            "status": "done",
            "noFloodSeen": False,
            "level": self.level,
            "landmark": self.landmark,
            "passability": self.passability,
            "levelIsFloor": self.level_is_floor,
            "basis": dict(self.basis),
            "levelFrom": self.level_from,
        }
        if self.level_from == "geometry":
            low, high = rules.round_out(self.depth_in_min, self.depth_in_max)
            fields |= {"depthInMin": low, "depthInMax": high}
        return fields

    @property
    def log_name(self) -> str:
        """The log line's outcome: done/level, done/no_flood_seen or status/reason."""
        if self.status != "done":
            return f"{self.status}/{self.reason}"
        return "done/no_flood_seen" if self.no_flood_seen else "done/level"


@dataclass(frozen=True)
class Reference:
    """One reference's reading, from a wheel, a vehicle's body or a person.

    `box_id` is the numbered box it came from: the vehicle's, for a body reading.
    `landmark` is always Muse Spark's category, even when geometry set the reading
    (C320). `depth_in` is geometry's unrounded min and max, in inches. A reference
    that step 3 dropped doesn't decide: it can refuse the photo, never decide it
    (C317).
    """

    kind: Literal["wheel", "body", "person"]
    box_id: int
    landmark: str
    reading: rules.Reading
    level_from: Literal["landmark", "geometry"] = "landmark"
    depth_in: tuple[float, float] | None = None
    decides: bool = True


class ModelClient(Protocol):
    """The Meta client as the pipeline uses it, so tests and replays can pass fakes.

    `deadline` is the run's deadline as a time.monotonic() value, or None (C84).
    """

    def segment(
        self, image: BlurredImage, phrase: str, *, deadline: float | None = None
    ) -> SamResult: ...

    def judge(
        self,
        image: BlurredImage,
        *,
        prompt: str,
        schema: dict,
        schema_name: str,
        deadline: float | None = None,
        reasoning_effort: str | None = None,
    ) -> SparkResult: ...


class ModelAnswerError(Exception):
    """Muse Spark's answer isn't valid JSON or fails the schema (C47)."""


# Meta's statuses for a rejected key or account, which aren't the photo's fault (C73).
KEY_REJECTED_STATUSES = frozenset({401, 402, 403})


class ModelKeyRejected(Exception):
    """Meta answered 401, 402 or 403: it rejected the key or the account (C73).

    It isn't an outcome, because the photo isn't at fault.
    """

    def __init__(self, status: int) -> None:
        super().__init__(status)
        self.status = status
