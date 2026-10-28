"""Rules §2: an alert's level and passability labels, mapped to the scale (C404, C420).

A level label maps by its words when they are one of §2's phrases, and otherwise by
its measures when they give one level (MS6E-Q1, item 15). Any other label is an
"unmapped label", never guessed (rules §2).
"""

from __future__ import annotations

import re
import string
from dataclasses import dataclass
from decimal import Decimal

from scoring.scale import level_for_inches

CM_PER_INCH = Decimal("2.54")
STATUS_WORDS = frozenset({"subsided"})
# What the export writes instead of a label that holds any other word (C420).
OTHER_WORDS = "(other words)"

# Rules §2's level phrases, and "head" as "lagpas tao" (MS6E-Q1, item 16). Each may
# end with "deep" or "level", or neither, since §2 treats the two words alike (C404;
# MS6E-Q1, item 12).
_PHRASE_LEVELS = {
    "gutter": "gutter",
    "half knee": "half_knee",
    "half tire": "half_tire",
    "knee": "knee",
    "tire": "tire",
    "waist": "waist",
    "chest": "chest",
    "half gutter": "below_gutter",
    "above gutter": "half_knee",
    "above knee": "tire",
    "lagpas tao": "above_chest",
    "head": "above_chest",
}
_WORDS_LEVELS = {
    f"{phrase}{suffix}": level
    for phrase, level in _PHRASE_LEVELS.items()
    for suffix in ("", " deep", " level")
}

# Rules §2's passability codes and phrases, a parenthetical's brackets dropped.
_CODES = {"patv": "PATV", "nplv": "NPLV", "npatv": "NPATV"}
_PHRASE_CLASSES = {
    "passable to all vehicles": "PATV",
    "passable to all types of vehicles": "PATV",
    "passable to light vehicles": "PATV",
    "not passable to light vehicles": "NPLV",
    "not passable to motorcycles and cars": "NPLV",
    "not passable to motorcycles and cars sedan": "NPLV",
    "not passable to all vehicles": "NPATV",
    "not passable to all types of vehicles": "NPATV",
    "not passable to any vehicle": "NPATV",
}
_PASSABILITY = {**_CODES, **_PHRASE_CLASSES}

_INCH_WORDS = ("inches", "inch", "in")
_CM_WORDS = ("centimeters", "centimetres", "centimeter", "centimetre", "cm")

# The words a committed label may hold (C420): the phrases' words, the units, "to"
# for a range, the statuses, and "ankle", which real alerts write beside inches
# though it is no phrase (MS6E-Q1, item 15).
LABEL_WORDS: frozenset[str] = frozenset(
    {word for text in (*_WORDS_LEVELS, *_PASSABILITY) for word in text.split()}
    | {*_INCH_WORDS, *_CM_WORDS, "to", "ankle"}
    | STATUS_WORDS
)

# A number and its unit, or a range: two numbers joined by -, – or "to", where the
# first may carry its own unit or else takes the second's (MS6E-Q1, item 13). A
# number followed by + and then its unit, as in "60+ inches", is at least that
# depth (item 16).
_NUMBER = "[0-9]+(?:[.][0-9]+)?"
_UNIT = '["”″]|(?:' + "|".join(_INCH_WORDS + _CM_WORDS) + ")(?![a-z])"
_MEASURE = re.compile(
    f"(?<![0-9.])(?P<low>{_NUMBER})"
    "(?:(?P<plus>[+])"
    f"|(?: *(?P<low_unit>{_UNIT}))? *(?:-|–|to) *(?P<high>{_NUMBER}))?"
    f" *(?P<unit>{_UNIT})"
)
# A label's last parenthetical, as in "phrase (code)" or "code (phrase)".
_PARENTHETICAL = re.compile(r"(?P<outer>.*)\((?P<inner>[^()]*)\)(?P<tail>[^()]*)")
_OUTER_MARKS = string.punctuation + "–“”″ "

# The marks a committed label may hold between its words (C420), with + as in
# "Head+ (60+ inches)" (MS6E-Q1, item 16). A "." inside a number stays part of it.
_MARKS = "-–,()\"'”“″/+"
_LABEL_CHARS = re.compile(f"[A-Za-z0-9 .{re.escape(_MARKS)}]*")
_SEPARATOR = re.compile(f"[ {re.escape(_MARKS)}]+|(?<![0-9])[.]|[.](?![0-9])")
_NUMBER_TOKEN = re.compile("[0-9]{1,3}(?:[.][0-9]{1,2})?(?:in|cm)?")


@dataclass(frozen=True)
class LevelLabel:
    """A level label's reading. `kind` is level, blank, status or unmapped."""

    kind: str
    level: str | None


@dataclass(frozen=True)
class ClassLabel:
    """A passability label's reading. `kind` is class, blank or unmapped."""

    kind: str
    cls: str | None


def map_level_label(raw: str) -> LevelLabel:
    """Map an alert's level label by rules §2 (C404). Words win when they map, and
    otherwise the measures decide by rules §1, as when there are no words (MS6E-Q1,
    item 15). Measures not joined as a range are one depth in two units, which maps
    only when they agree (item 13). "N+" is at least that depth, which maps only
    when it is over 45 in (item 16). Words with no measure stay unmapped.
    """
    if raw.strip() == "":
        return LevelLabel("blank", None)
    if raw == OTHER_WORDS:
        return LevelLabel("unmapped", None)
    # The numbers come out before the words are normalised, so no mark is lost.
    text = raw.lower()
    measures = list(_MEASURE.finditer(text))
    words = _words(_MEASURE.sub(" ", text))
    if words in STATUS_WORDS:
        return LevelLabel("status", None)
    level = _WORDS_LEVELS.get(words)
    if level is None:
        levels = {_measure_level(measure) for measure in measures}
        level = levels.pop() if len(levels) == 1 else None
    if level is None:
        return LevelLabel("unmapped", None)
    return LevelLabel("level", level)


def map_passability(raw: str) -> ClassLabel:
    """Map an alert's passability label by rules §2: a lone code or phrase, or a
    phrase and a code, one in brackets, that agree."""
    if raw.strip() == "":
        return ClassLabel("blank", None)
    text = raw.lower()
    cls = _PASSABILITY.get(_bracketless(text))
    if cls is None:
        pair = _PARENTHETICAL.fullmatch(text)
        if pair and _words(pair["tail"]) == "":
            cls = _agreeing_class(pair["outer"], pair["inner"])
    if cls is None:
        return ClassLabel("unmapped", None)
    return ClassLabel("class", cls)


def label_words_ok(raw: str) -> bool:
    """Whether a label holds only LABEL_WORDS, numbers of up to 3 digits with up to
    2 decimals (optionally glued to in or cm) and simple marks (C420). A blank
    label and the marker pass too."""
    if raw.strip() == "" or raw == OTHER_WORDS:
        return True
    if not _LABEL_CHARS.fullmatch(raw):
        return False
    tokens = [token for token in _SEPARATOR.split(raw.lower()) if token]
    return all(
        token in LABEL_WORDS or _NUMBER_TOKEN.fullmatch(token) for token in tokens
    )


def _measure_level(measure: re.Match[str]) -> str | None:
    """A measure's level by rules §1. "N+" is at least N, so it gives a level only
    when every depth from N up is above_chest. Otherwise it gives none, and a label
    whose measures decide is then unmapped: a label never sets a floor (MS6E-Q1,
    item 16)."""
    level = level_for_inches(_inches(measure))
    if measure["plus"] and level != "above_chest":
        return None
    return level


def _inches(measure: re.Match[str]) -> Decimal:
    """A measure in inches: a range at its upper value, each number in its own unit
    or the range's, with centimetres converted."""
    unit = measure["unit"]
    low = _to_inches(measure["low"], measure["low_unit"] or unit)
    if measure["high"] is None:
        return low
    return max(low, _to_inches(measure["high"], unit))


def _to_inches(number: str, unit: str) -> Decimal:
    return Decimal(number) / CM_PER_INCH if unit in _CM_WORDS else Decimal(number)


def _words(text: str) -> str:
    """Hyphens, underscores and runs of whitespace become single spaces, and outer
    punctuation goes."""
    for mark in "-–_":
        text = text.replace(mark, " ")
    return " ".join(text.split()).strip(_OUTER_MARKS)


def _bracketless(text: str) -> str:
    """A passability label's words, with a parenthetical's brackets dropped."""
    return _words(text.replace("(", " ").replace(")", " "))


def _agreeing_class(outer: str, inner: str) -> str | None:
    """The class of "phrase (code)" or "code (phrase)", when the two agree."""
    for code_part, phrase_part in ((inner, outer), (outer, inner)):
        code = _CODES.get(_bracketless(code_part))
        phrase = _PHRASE_CLASSES.get(_bracketless(phrase_part))
        if code is not None and phrase is not None:
            return code if code == phrase else None
    return None
