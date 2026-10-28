"""Types the pipeline steps share: the outcome, a reference and the model client.

The Meta client's result types and BlurredImage are imported for type checking only
(R80). The annotations stay strings, so this file loads neither the OpenAI SDK nor
OpenCV.
"""

from __future__ import annotations

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
    """

    status: Literal["done", "refused", "failed"]
    reason: str | None = None
    no_flood_seen: bool = False
    level: str | None = None
    landmark: str | None = None
    passability: str | None = None
    level_is_floor: bool = False
    basis: Mapping[str, int] | None = None

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

    def _has_level_fields(self) -> bool:
        """True when any field that only a level result sets is set."""
        return self.level_is_floor or any(
            value is not None
            for value in (self.level, self.landmark, self.passability, self.basis)
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
        cls, level: str, landmark: str, level_is_floor: bool, basis: Mapping[str, int]
    ) -> Outcome:
        """A level with its class. That lookup is step 7 (map)."""
        return cls(
            "done",
            level=level,
            landmark=landmark,
            # .get: an unknown level then fails __post_init__ with a ValueError
            passability=rules.PASSABILITY.get(level),
            level_is_floor=level_is_floor,
            basis=basis,
        )

    def item_fields(self) -> dict[str, object]:
        """The report item's result attributes, as Table 14 names them (spec §3.5)."""
        if self.status != "done":
            return {"status": self.status, "refusalReason": self.reason}
        if self.no_flood_seen:
            return {"status": "done", "noFloodSeen": True}
        return {
            "status": "done",
            "noFloodSeen": False,
            "level": self.level,
            "landmark": self.landmark,
            "passability": self.passability,
            "levelIsFloor": self.level_is_floor,
            "basis": dict(self.basis),
        }

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
    """

    kind: Literal["wheel", "body", "person"]
    box_id: int
    landmark: str
    reading: rules.Reading


class ModelClient(Protocol):
    """The Meta client as the pipeline uses it, so tests and replays can pass fakes."""

    def segment(self, image: BlurredImage, phrase: str) -> SamResult: ...

    def judge(
        self, image: BlurredImage, *, prompt: str, schema: dict, schema_name: str
    ) -> SparkResult: ...


class ModelAnswerError(Exception):
    """Muse Spark's answer isn't valid JSON or fails the schema (C47)."""


class ModelKeyRejected(Exception):
    """Meta answered 401, 402 or 403: it rejected the key or the account (C73).

    It isn't an outcome, because the photo isn't at fault.
    """

    def __init__(self, status: int) -> None:
        super().__init__(status)
        self.status = status
