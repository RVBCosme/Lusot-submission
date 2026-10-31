# /// script
# requires-python = ">=3.13,<3.14"
# dependencies = [
#     "osmium>=4.3.2",
# ]
# ///
"""Build Ask Lusot's spot list, spots.json, from spots_sources.csv and an OpenStreetMap
extract (spec C715, C733, AskL-Q8; plan Task 3).

Each CSV row names one spot: a corner (`intersection`, two street names `a` and `b`), a
landmark (`named`, the feature's name in `a`) or a hand-picked point (`manual`, with
`lat` and `lng`). The point comes from the extract, never from Nominatim: an
intersection is the node that a way named `a` and a way named `b` share, a landmark is
the node, or the mean of the way's nodes, that carries its name. Names are compared
after folding case and accents, and any of OpenStreetMap's name keys counts. Several
candidates give their mean when every pair is within 150 m, and no match otherwise.
A point outside Metro Manila (the API's ncr.json) is refused, so nothing is written for
it and the id is listed.

`roads` is the intersection's two streets, then the names in the row's `roads` column
(the short forms people say, such as "EDSA"); for a landmark or a manual spot it is the
column alone, and empty when the alert names no road for it. Points are rounded to 5
decimals.

The extract is read in two passes without a location index, so a 600 MB file needs
little memory (spec: the laptop has about 2 GB free). Pass 1 keeps the ways, and the
named nodes, that carry a wanted name (a street counts only with a `highway` tag), and
pass 2 reads the coordinates of those ways' nodes only, in batches of node ids because
osmium's id filter allocates 4 MiB for each 33 million ids it spans. It imports osmium
inside the reader only, so the tests need no osmium.

Output: counts, and the id and cause of each row not placed, never a path or a key.

Usage: uv run backend/scripts/build_spots.py --osm <extract.osm.pbf> [--write]
Exit codes: 0 every row placed; 1 a row not placed or malformed, or no extract;
2 refused: a path with a part named sealed.
"""

from __future__ import annotations

import argparse
import csv
import functools
import itertools
import json
import math
import re
import unicodedata
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from guards import refuse_sealed, say
from metro_manila import in_metro_manila, ncr_boundary

DATA = Path(__file__).resolve().parents[1] / "api" / "src" / "data"
SOURCES = DATA / "spots_sources.csv"
SPOTS = DATA / "spots.json"
COLUMNS = (
    "id",
    "name",
    "city",
    "aliases",
    "locator",
    "a",
    "b",
    "roads",
    "lat",
    "lng",
    "source",
)
LOCATORS = ("intersection", "named", "manual")
ID = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
# Every key OpenStreetMap uses for a place's names: MMDA writes "EDSA" where one way
# has name=EDSA and another has name=Epifanio de los Santos Avenue.
NAME_KEYS = (
    "name",
    "alt_name",
    "old_name",
    "name:en",
    "short_name",
    "official_name",
)
MAX_SPREAD_M = 150.0
EARTH_RADIUS_M = 6_371_000.0
CHUNK_BITS = 25  # osmium's dense id set: 4 MiB for each 2**25 ids
CHUNKS_PER_BATCH = 32  # at most 128 MiB for one batch of node ids

Point = tuple[float, float]
Ways = dict[str, list[list[int]]]  # a name to the node ids of each way that carries it
Nodes = dict[int, Point]  # a node id to its (lat, lng), inside Metro Manila's box only
Places = dict[str, list[Point]]  # a name to the points of the nodes that carry it
Reader = Callable[[Path, set[str], set[str]], tuple[Ways, Nodes, Places]]


@functools.lru_cache(maxsize=1 << 16)
def fold(text: str) -> str:
    """`text` without accents, in lower case, with runs of spaces as one space."""
    decomposed = unicodedata.normalize("NFKD", text)
    bare = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(bare.casefold().split())


def _metres(p: Point, q: Point) -> float:
    (lat1, lng1), (lat2, lng2) = p, q
    d_lat, d_lng = math.radians(lat2 - lat1), math.radians(lng2 - lng1)
    h = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lng / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(h))


def _centre(points: list[Point]) -> Point | None:
    """The mean of `points` when every pair is within 150 m; None when there are none
    or two are further apart (two places that share a name, or a street that meets
    another twice)."""
    if not points:
        return None
    if any(_metres(p, q) > MAX_SPREAD_M for p, q in itertools.combinations(points, 2)):
        return None
    return (
        sum(lat for lat, _ in points) / len(points),
        sum(lng for _, lng in points) / len(points),
    )


def _node_ids(ways: Ways, name: str) -> set[int]:
    wanted = fold(name)
    return {
        node
        for key, lists in ways.items()
        if fold(key) == wanted
        for ids in lists
        for node in ids
    }


def locate_intersection(ways: Ways, nodes: Nodes, a: str, b: str) -> Point | None:
    """The node that a way named `a` and a way named `b` share, or the mean of several
    within 150 m of each other; None if there is none, or they are further apart.
    Only nodes that have a point count: the reader keeps Metro Manila's box only."""
    if fold(a) == fold(b):
        return None
    shared = _node_ids(ways, a) & _node_ids(ways, b)
    return _centre([nodes[n] for n in sorted(shared) if n in nodes])


def _named_points(ways: Ways, nodes: Nodes, places: Places, name: str) -> list[Point]:
    """The point of each node called `name`, and the mean of the nodes (that have a
    point) of each way called `name`."""
    wanted = fold(name)
    points = [p for key, ps in places.items() if fold(key) == wanted for p in ps]
    for key, lists in ways.items():
        if fold(key) != wanted:
            continue
        for ids in lists:
            known = [nodes[n] for n in dict.fromkeys(ids) if n in nodes]
            if known:
                points.append(
                    (
                        sum(lat for lat, _ in known) / len(known),
                        sum(lng for _, lng in known) / len(known),
                    )
                )
    return points


def locate_named(ways: Ways, nodes: Nodes, places: Places, name: str) -> Point | None:
    """The point of a feature called `name`: a node's own point, or the mean of a way's
    nodes (a building or an area), and the mean of several within 150 m of each other."""
    return _centre(_named_points(ways, nodes, places, name))


@dataclass(frozen=True)
class Row:
    id: str
    name: str
    city: str
    aliases: tuple[str, ...]
    locator: str
    a: str
    b: str
    roads: tuple[str, ...]
    lat: str
    lng: str
    source: str


def _split(cell: str) -> tuple[str, ...]:
    """A `;`-separated cell as its non-empty parts, once each (folded) in order."""
    seen: dict[str, str] = {}
    for part in cell.split(";"):
        if part.strip():
            seen.setdefault(fold(part), part.strip())
    return tuple(seen.values())


def read_rows(path: Path) -> list[Row]:
    """The sources file's rows, checked. A malformed row, a repeated id, or an alias
    (or display name) that two spots share raises ValueError naming it."""
    try:
        with path.open(encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            missing = [c for c in COLUMNS if c not in (reader.fieldnames or [])]
            if missing:
                raise ValueError(f"the sources file has no column {', '.join(missing)}")
            records = list(reader)
    except OSError as error:  # its message holds the path, which is never printed
        raise ValueError(
            f"the sources file could not be read ({type(error).__name__})"
        ) from None
    rows: list[Row] = []
    for n, record in enumerate(records, start=2):  # line 1 is the header
        cell = {c: (record.get(c) or "").strip() for c in COLUMNS}
        who = f"row {n} ({cell['id'] or 'no id'})"
        if not ID.fullmatch(cell["id"]):
            raise ValueError(f"row {n}: id {cell['id']!r} is not kebab-case")
        for column in ("name", "city", "source"):
            if not cell[column]:
                raise ValueError(f"{who}: {column} is empty")
        if cell["locator"] not in LOCATORS:
            raise ValueError(
                f"{who}: locator {cell['locator']!r} is not one of {', '.join(LOCATORS)}"
            )
        if cell["locator"] == "intersection" and not (cell["a"] and cell["b"]):
            raise ValueError(f"{who}: an intersection needs both street names, a and b")
        if cell["locator"] == "intersection" and fold(cell["a"]) == fold(cell["b"]):
            raise ValueError(f"{who}: a street cannot cross itself")
        if cell["locator"] == "named" and not cell["a"]:
            raise ValueError(f"{who}: a named spot needs the feature's name in a")
        extra = _split(cell["roads"])
        streets = (cell["a"], cell["b"]) if cell["locator"] == "intersection" else ()
        rows.append(
            Row(
                id=cell["id"],
                name=cell["name"],
                city=cell["city"],
                aliases=_split(cell["aliases"]),
                locator=cell["locator"],
                a=cell["a"],
                b=cell["b"],
                roads=_split(";".join([*streets, *extra])),
                lat=cell["lat"],
                lng=cell["lng"],
                source=cell["source"],
            )
        )
    _check_unique(rows)
    return rows


def _check_unique(rows: list[Row]) -> None:
    ids: set[str] = set()
    owner: dict[str, str] = {}  # a folded display name or alias to its spot's id
    for row in rows:
        if row.id in ids:
            raise ValueError(f"id {row.id!r} appears twice")
        ids.add(row.id)
        for text in dict.fromkeys(fold(t) for t in (row.name, *row.aliases)):
            if text in owner:
                raise ValueError(
                    f"alias {text!r} is under two spots: {owner[text]} and {row.id}"
                )
            owner[text] = row.id


def _place(
    row: Row, ways: Ways, nodes: Nodes, places: Places
) -> tuple[Point | None, str]:
    """The row's point and "", or None and why it has none."""
    if row.locator == "manual":
        try:
            return (float(row.lat), float(row.lng)), ""
        except ValueError:
            return None, "no point"
    if row.locator == "intersection":
        point = locate_intersection(ways, nodes, row.a, row.b)
        if point is not None:
            return point, ""
        known = {name: _node_ids(ways, name) & nodes.keys() for name in (row.a, row.b)}
        for name, ids in known.items():
            if not ids:
                return None, f"no match in the extract: no way named {name!r} here"
        if not known[row.a] & known[row.b]:
            return None, "no match in the extract: the two ways share no node"
        return None, "no match in the extract: the crossings are over 150 m apart"
    points = _named_points(ways, nodes, places, row.a)
    point = _centre(points)
    if point is not None:
        return point, ""
    if points:
        return None, "no match in the extract: the namesakes are over 150 m apart"
    return None, f"no match in the extract: nothing named {row.a!r} here"


def place_all(
    sources_csv: Path, osm_path: Path, read: Reader | None = None
) -> tuple[list[dict], list[tuple[str, str]]]:
    """The spots that could be placed, in the file's order, and (id, cause) for each
    row that could not. The extract is read only if a row needs it."""
    rows = read_rows(Path(sources_csv))
    streets = {
        fold(name) for r in rows if r.locator == "intersection" for name in (r.a, r.b)
    }
    features = {fold(r.a) for r in rows if r.locator == "named"}
    if streets or features:
        ways, nodes, places = (read or read_extract)(Path(osm_path), streets, features)
    else:
        ways, nodes, places = {}, {}, {}
    spots: list[dict] = []
    unplaced: list[tuple[str, str]] = []
    for row in rows:
        point, why = _place(row, ways, nodes, places)
        if point is None:
            unplaced.append((row.id, why))
        elif not in_metro_manila(*point):
            unplaced.append((row.id, "outside Metro Manila"))
        else:
            spots.append(
                {
                    "id": row.id,
                    "name": row.name,
                    "city": row.city,
                    "lat": round(point[0], 5),
                    "lng": round(point[1], 5),
                    "roads": list(row.roads),
                    "aliases": list(row.aliases),
                }
            )
    return spots, unplaced


def report(spots: list[dict], unplaced: list[tuple[str, str]]) -> None:
    say(f"{len(spots)} placed, {len(unplaced)} not placed")
    for spot_id, why in unplaced:
        say(f"  {spot_id}: {why}")


def build(sources_csv: Path, osm_path: Path, read: Reader | None = None) -> list[dict]:
    """The placed spots (see place_all), after printing the counts and each unplaced id."""
    spots, unplaced = place_all(sources_csv, osm_path, read)
    report(spots, unplaced)
    return spots


def _box() -> tuple[float, float, float, float]:
    """Metro Manila's box (south, north, west, east) from the API's boundary file."""
    boundary = ncr_boundary()
    if boundary is None:
        raise ValueError("ncr.json is missing or malformed")
    points = [p for polygon in boundary for ring in polygon for p in ring]
    lngs, lats = [p[0] for p in points], [p[1] for p in points]
    return min(lats), max(lats), min(lngs), max(lngs)


def read_extract(
    osm_path: Path, streets: set[str], features: set[str]
) -> tuple[Ways, Nodes, Places]:
    """Read the extract for the folded names in `streets` and `features`.

    Pass 1 (nodes and ways with a name): a way named for a street counts if it has a
    `highway` tag, a way or a node named for a feature always counts; Metro Manila's box
    is applied to a node's own point, and to a way's nodes in pass 2. Pass 2 (nodes by
    id, in batches): the points of the kept ways' nodes inside the box.
    """
    refuse_sealed(osm_path)
    if not osm_path.is_file():
        raise ValueError("the extract is not a file")
    import osmium  # here only, so the tests need no osmium

    try:
        return _scan_extract(osmium, str(osm_path), streets, features)
    except (OSError, RuntimeError) as error:  # osmium's messages hold the path
        raise ValueError(
            f"the extract could not be read ({type(error).__name__})"
        ) from None


def _scan_extract(
    osmium, path: str, streets: set[str], features: set[str]
) -> tuple[Ways, Nodes, Places]:
    south, north, west, east = _box()

    def inside(lat: float, lng: float) -> bool:
        return south <= lat <= north and west <= lng <= east

    ways: Ways = defaultdict(list)
    places: Places = defaultdict(list)
    wanted: set[int] = set()
    named = osmium.FileProcessor(path, osmium.osm.NODE | osmium.osm.WAY).with_filter(
        osmium.filter.KeyFilter(*NAME_KEYS)
    )
    for obj in named:
        names = {fold(obj.tags[key]) for key in NAME_KEYS if key in obj.tags}
        if obj.is_node():
            hits = names & features
            if hits and inside(obj.location.lat, obj.location.lon):
                for name in hits:
                    places[name].append((obj.location.lat, obj.location.lon))
            continue
        hits = names & features
        if "highway" in obj.tags:
            hits = hits | (names & streets)
        if hits:
            ids = [ref.ref for ref in obj.nodes]
            wanted.update(ids)
            for name in hits:
                ways[name].append(ids)

    nodes: Nodes = {}
    ids = sorted(wanted)
    start = 0
    while start < len(ids):
        first = ids[start] >> CHUNK_BITS
        end = start
        while end < len(ids) and (ids[end] >> CHUNK_BITS) - first < CHUNKS_PER_BATCH:
            end += 1
        batch = ids[start:end]
        left = len(batch)
        found = osmium.FileProcessor(path, osmium.osm.NODE).with_filter(
            osmium.filter.IdFilter(batch)
        )
        for node in found:
            if inside(node.location.lat, node.location.lon):
                nodes[node.id] = (node.location.lat, node.location.lon)
            left -= 1
            if left == 0:
                break  # nodes come in id order, so the rest of the file has none
        start = end
    return dict(ways), nodes, dict(places)


def main(
    argv: Sequence[str] | None = None,
    *,
    read: Reader | None = None,
    sources: Path = SOURCES,
    out: Path = SPOTS,
) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--osm", required=True, type=Path, help="the .osm.pbf extract")
    parser.add_argument(
        "--write", action="store_true", help="write spots.json (otherwise a dry run)"
    )
    args = parser.parse_args(argv)
    refuse_sealed(args.osm)
    try:
        spots, unplaced = place_all(sources, args.osm, read)
    except ValueError as error:  # every message names a file by its role, not its path
        say(str(error))
        return 1
    report(spots, unplaced)
    if args.write:
        text = json.dumps(spots, ensure_ascii=False, indent=2) + "\n"
        out.write_text(text, encoding="utf-8", newline="\n")
        say(f"wrote {len(spots)} spots to {out.name}")
    return 1 if unplaced else 0


if __name__ == "__main__":
    raise SystemExit(main())
