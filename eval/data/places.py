"""Spot, city and poster names for Set A and A-neg (C203, C224, MS2-Q4).

A spot is the set of names its text gives: a street, its cross street or a landmark,
each folded. A barangay's or a zone's name, and a Manila district's, is marked: it
groups events, but never counts toward the same spot (S-R9). The tools can't place a
spot on a map, so Rene links nearby spots with other names, and corners on a city
boundary, in same_spot_as (C203).

The word lists are the plan's, with the additions noted below. Like the rest of the
normalisation, they are fixed and tested before the split (spec §10).
"""

import re
import unicodedata

import formats

# The office words a city's poster may end with (MS2-Q4 (a)). The collection guide
# lists the same words for Rene, and a test ties the two.
OFFICE_WORDS = (
    "government",
    "city government",
    "city hall",
    "lgu",
    "drrmo",
    "cdrrmo",
    "pio",
    "public information office",
    "information office",
)
_MMDA_NAMES = (
    "mmda",
    "metropolitan manila development authority",
    "metro manila development authority",
)
_OTHER_WORDS = frozenset({"barangay", "brgy", "police", "pnp", "fire", "bfp"})

# spot_names, step 1: the raw text splits on these marks, and on a hyphen or dash with
# a space on each side, then each folded piece splits on the connector words. "front of"
# and "to" extend the plan's list, for spans such as "Pedro Gil to front of PGH" and
# "Olivarez School to Canaynay" in the alert index.
_MARKS = re.compile(r"[,;/&+()\[\]]|\s[-\N{HYPHEN}-\N{HORIZONTAL BAR}]\s")
_CONNECTORS = re.compile(
    r"\b(?:cor|corner|near|along|at|and|in front of|infront of|fronting|beside"
    r"|between|intersection|front of|to)\b"
)
# Step 3: the words dropped from a name. "of" extends the plan's area words, so that
# "corner of" and "intersection of" leave no "of" behind.
_STREET_WORDS = (
    "street",
    "st",
    "avenue",
    "ave",
    "av",
    "boulevard",
    "blvd",
    "road",
    "rd",
    "highway",
    "hwy",
    "drive",
    "dr",
    "extension",
    "ext",
    "lane",
    "ln",
)
_DIRECTION_WORDS = (
    "nb",
    "sb",
    "eb",
    "wb",
    "northbound",
    "southbound",
    "eastbound",
    "westbound",
    "bound",
)
_AREA_WORDS = ("area", "vicinity", "portion", "brgy", "barangay", "city", "the", "of")
_LANE_NOTES = ("innermost", "outermost", "pagbaba")  # S-R9; service stays a name
_DROPPED = frozenset(_STREET_WORDS + _DIRECTION_WORDS + _AREA_WORDS + _LANE_NOTES)
_SHORT_FORMS = {"sto": "santo", "sta": "santa"}
_EDSA = re.compile(r"\bepifanio (?:de los|delos) santos\b")
# Before step 3, a lone letter joins the number after it, so C-5, C 5 and C5 all give
# c5 (S-R9).
_LETTER_NUMBER = re.compile(r"\b([a-z]) (?=[0-9]+\b)")

# Marked names (S-R9): a segment whose first word is one of these keys is a barangay's
# or a zone's, and gives one name that starts with the key's value. A name equal to a
# Manila district's is marked too.
_MARKERS = {"brgy": "brgy", "barangay": "brgy", "zone": "zone"}
MANILA_DISTRICTS = (
    "Binondo",
    "Ermita",
    "Intramuros",
    "Malate",
    "Paco",
    "Pandacan",
    "Port Area",
    "Quiapo",
    "Sampaloc",
    "San Andres",
    "San Miguel",
    "San Nicolas",
    "Santa Ana",
    "Santa Cruz",
    "Santa Mesa",
    "Tondo",
)


def fold(text: str) -> str:
    """The text in NFKD without its combining marks (ñ becomes n), casefolded, with
    every character outside a-z and 0-9 made a space and the spaces collapsed."""
    bare = "".join(
        char
        for char in unicodedata.normalize("NFKD", text)
        if not unicodedata.category(char).startswith("M")
    )
    return " ".join(re.sub(r"[^a-z0-9]", " ", bare.casefold()).split())


def _city_forms() -> dict[str, str]:
    """Each folded form city_name finds, mapped to its display name."""
    forms = {"municipality of pateros": "Pateros"}
    for name in formats.METRO_MANILA:
        if name == "Quezon City":  # plain Quezon is the province
            variants = ("quezon city", "qc", "q c")
        else:
            base = fold(name)
            variants = (base, f"{base} city", f"city of {base}")
        forms.update(dict.fromkeys(variants, name))
    return forms


_CITY_FORMS = _city_forms()


def city_name(text: str) -> str | None:
    """The display name of the Metro Manila city that the text names, or None.

    The folded text must be the city's name, the name and "city", or "city of" and the
    name. Quezon City is found only as quezon city, qc or q c, and Pateros also as
    municipality of pateros.
    """
    return _CITY_FORMS.get(fold(text))


def _name(words: list[str]) -> str:
    """Step 3 on a segment's words: the name left once the dropped words and single
    letters are gone and the short forms are written out."""
    kept = [
        _SHORT_FORMS.get(word, word)
        for word in words
        if word not in _DROPPED and not (len(word) == 1 and word.isalpha())
    ]
    return _EDSA.sub("edsa", " ".join(kept))


# The districts as step 3 leaves them, such as santa mesa, and port for Port Area.
_DISTRICT_NAMES = frozenset(
    _name(fold(district).split()) for district in MANILA_DISTRICTS
)


def spot_names(text: str) -> frozenset[str]:
    """The names a spot's text gives (C203, C224), in four steps:

    1. The raw text splits on , ; / & + ( ) [ ] and on a hyphen or dash with a space on
       each side. Each piece is folded and splits again on the connector words.
    2. A segment that is a Metro Manila city is dropped whole, so Quezon City never
       leaves quezon. In the rest, a lone letter joins the number after it (c 5 gives
       c5).
    3. The street, direction and area words and the lane notes are dropped, and so is
       a single letter, such as the A of A. Maceda; a single digit stays. Then sto, sta
       and Epifanio de los Santos are written as santo, santa and edsa.
    4. Each non-empty remainder is one name. A segment that starts with brgy, barangay
       or zone gives one marked name, such as brgy dona imelda (S-R9).
    """
    names = set()
    for piece in _MARKS.split(text):
        for segment in _CONNECTORS.split(fold(piece)):
            if city_name(segment) is not None:
                continue
            words = _LETTER_NUMBER.sub(r"\1", segment).split()
            marker = _MARKERS.get(words[0]) if words else None
            name = _name(words[1:] if marker else words)
            if name:
                names.add(f"{marker} {name}" if marker else name)
    return frozenset(names)


def spot_key(names: frozenset[str]) -> str:
    """The names sorted and joined by |, as the manifest's spot_key holds them."""
    return "|".join(sorted(names))


def names_of(key: str) -> frozenset[str]:
    """The names in a spot key. An empty key has none."""
    return frozenset(name for name in key.split("|") if name)


def marked(name: str) -> bool:
    """True for a barangay's or a zone's name, or a Manila district's (S-R9). A marked
    name groups events, but never counts toward the same spot."""
    return name.split(" ", 1)[0] in _MARKERS.values() or name in _DISTRICT_NAMES


def same_spot(a: frozenset[str], b: frozenset[str]) -> bool:
    """True when two spots share at least two names that aren't marked, such as a
    street and its cross street or landmark (C224, S-R9). One shared name is never
    enough, even when it is each spot's only name."""
    return len([name for name in a & b if not marked(name)]) >= 2


def poster_kind(text: str) -> str:
    """mmda, city or other, for a poster or an alert poster (MS2-Q4 (a)).

    MMDA by its name or initials. Then other when any word names a barangay, the police
    or the fire service. Then city when the folded text is a Metro Manila city, alone or
    followed by one of OFFICE_WORDS. Anything else is other.
    """
    folded = fold(text)
    if folded in _MMDA_NAMES:
        return "mmda"
    if not _OTHER_WORDS.isdisjoint(folded.split()):
        return "other"
    if city_name(folded) is not None:
        return "city"
    for office in OFFICE_WORDS:
        city = folded.removesuffix(f" {office}")
        if city != folded and city_name(city) is not None:
            return "city"
    return "other"
