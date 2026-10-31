"""Tests for build_spots.py: the spot list from MMDA's alerts and an OpenStreetMap
extract (Ask Lusot spec C715, C733, AskL-Q8; plan Task 3).

Fakes only: the extract's reader is replaced by a function that returns the ways, the
node points and the named places a real read would, so nothing here needs osmium or
the 612 MB file. The last test reads the committed spots.json and spots_sources.csv.

check:py runs this file with the scripts' dependencies. Alone, from the repo root:
    uv run --python 3.13 --with pytest pytest -q backend/scripts/test_build_spots.py
"""

import csv
import json
import re
import sys
import types
from pathlib import Path

import build_spots
import pytest
from build_spots import build, fold, locate_intersection, locate_named, main
from metro_manila import in_metro_manila

DATA = Path(__file__).resolve().parents[1] / "api" / "src" / "data"
COLUMNS = [
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
]
# A corner in Sampaloc, Manila, and a point in Cebu City.
CORNER = (14.61433, 120.99813)
CEBU = (10.31672, 123.89071)


def at_metres(point, north=0.0, east=0.0):
    """A point `north` and `east` metres from `point` (small distances only)."""
    lat, lng = point
    return (lat + north / 111_320.0, lng + east / 107_700.0)


def metres(p, q):
    return build_spots._metres(p, q)


# --- locate_intersection ---------------------------------------------------------


def test_an_intersection_is_the_shared_node_of_the_two_named_ways():
    ways = {
        "España Boulevard": [[1, 2, 3], [9, 8]],
        "Maceda Street": [[3, 4, 5]],
        "Other Street": [[2, 6]],
    }
    nodes = {n: at_metres(CORNER, north=10 * n) for n in range(1, 10)}
    assert (
        locate_intersection(ways, nodes, "España Boulevard", "Maceda Street")
        == (nodes[3])
    )
    # Node 2 is on España and Other Street only; it is not Maceda's.
    assert (
        locate_intersection(ways, nodes, "España Boulevard", "Other Street")
        == (nodes[2])
    )


def test_ways_that_share_no_node_give_none():
    ways = {"España Boulevard": [[1, 2]], "Maceda Street": [[3, 4]]}
    nodes = {n: at_metres(CORNER, north=10 * n) for n in range(1, 5)}
    assert locate_intersection(ways, nodes, "España Boulevard", "Maceda Street") is None
    assert (
        locate_intersection(ways, nodes, "España Boulevard", "No Such Street") is None
    )


def test_a_shared_node_without_a_point_is_skipped():
    # The reader keeps only nodes inside Metro Manila's box, so a shared node outside
    # it has no point, and the street's other crossing inside the box is the answer.
    ways = {"A Road": [[1, 2]], "B Road": [[1, 2]]}
    nodes = {2: CORNER}
    assert locate_intersection(ways, nodes, "A Road", "B Road") == CORNER
    assert locate_intersection(ways, {}, "A Road", "B Road") is None


def test_accents_and_case_dont_matter():
    ways = {"España Boulevard": [[1, 2]], "MACEDA  street": [[2, 3]]}
    nodes = {1: at_metres(CORNER, north=5), 2: CORNER, 3: at_metres(CORNER, north=-5)}
    for a, b in [
        ("Espana Boulevard", "maceda STREET"),
        ("ESPAÑA BOULEVARD", "Maceda Street"),
        ("espana boulevard", "Maceda Street"),
    ]:
        assert locate_intersection(ways, nodes, a, b) == CORNER
    assert fold("Doña Ñandú  Ave") == "dona nandu ave"
    # The way's own key folds too: unaccented keys find accented asks, and back.
    assert (
        locate_intersection(
            {"Espana Boulevard": [[1, 2]], "Maceda Street": [[2]]},
            nodes,
            "España Boulevard",
            "Maceda Street",
        )
        == CORNER
    )


def test_a_street_cannot_cross_itself():
    ways = {"A Road": [[1, 2, 3]]}
    nodes = {1: CORNER, 2: at_metres(CORNER, north=5), 3: at_metres(CORNER, north=9)}
    assert locate_intersection(ways, nodes, "A Road", "a road") is None


def test_two_far_apart_shared_nodes_give_none():
    # A street that meets another twice, 500 m apart.
    ways = {"Loop Road": [[1, 2, 3, 4]], "Main Road": [[1, 9], [4, 8]]}
    nodes = {1: CORNER, 4: at_metres(CORNER, north=500), 2: CORNER, 3: CORNER}
    nodes.update({9: at_metres(CORNER, east=40), 8: at_metres(CORNER, east=60)})
    assert locate_intersection(ways, nodes, "Loop Road", "Main Road") is None


def test_shared_nodes_within_150_m_give_their_mean():
    # A divided road crosses twice, 100 m apart: the mean is the middle.
    far = at_metres(CORNER, north=100)
    ways = {"Wide Avenue": [[1, 2]], "Side Street": [[1, 2]]}
    nodes = {1: CORNER, 2: far}
    got = locate_intersection(ways, nodes, "Wide Avenue", "Side Street")
    assert got == pytest.approx(((CORNER[0] + far[0]) / 2, (CORNER[1] + far[1]) / 2))
    # The limit is 150 m between the farthest pair.
    inside = {1: CORNER, 2: at_metres(CORNER, north=149)}
    outside = {1: CORNER, 2: at_metres(CORNER, north=151)}
    assert locate_intersection(ways, inside, "Wide Avenue", "Side Street") is not None
    assert locate_intersection(ways, outside, "Wide Avenue", "Side Street") is None


def test_the_150_m_rule_is_between_the_farthest_pair_not_the_mean():
    # Three nodes in a row, 100 m apart: neighbours are close, the ends are 200 m.
    ways = {"A Road": [[1, 2, 3]], "B Road": [[1, 2, 3]]}
    nodes = {
        1: CORNER,
        2: at_metres(CORNER, north=100),
        3: at_metres(CORNER, north=200),
    }
    assert locate_intersection(ways, nodes, "A Road", "B Road") is None


# --- locate_named ----------------------------------------------------------------


def test_a_named_node_is_its_own_point():
    assert (
        locate_named(
            {},
            {},
            {"Philippine General Hospital": [CORNER]},
            "philippine general hospital",
        )
        == CORNER
    )


def test_a_named_way_is_the_mean_of_its_nodes_in_the_box():
    square = [
        at_metres(CORNER, north=0, east=0),
        at_metres(CORNER, north=40, east=0),
        at_metres(CORNER, north=40, east=40),
        at_metres(CORNER, north=0, east=40),
    ]
    nodes = {n: p for n, p in enumerate(square, start=1)}
    ways = {"SM City Marikina": [[1, 2, 3, 4, 1]]}
    got = locate_named(ways, nodes, {}, "SM City Marikina")
    assert got == pytest.approx(at_metres(CORNER, north=20, east=20), abs=1e-5)
    # Nodes outside the box (no point) are left out; no point at all gives none.
    assert (
        locate_named(ways, {1: square[0], 2: square[1]}, {}, "SM City Marikina")
        is not None
    )
    assert locate_named(ways, {}, {}, "SM City Marikina") is None


def test_a_named_feature_on_a_node_and_a_way_within_150_m_is_one_point():
    ways = {"Oyster Plaza": [[1, 2]]}
    nodes = {1: at_metres(CORNER, north=20), 2: at_metres(CORNER, north=40)}
    got = locate_named(ways, nodes, {"Oyster Plaza": [CORNER]}, "Oyster Plaza")
    assert got is not None
    assert metres(got, CORNER) < 30


def test_two_namesakes_far_apart_give_none():
    places = {"Savemore": [CORNER, at_metres(CORNER, north=2000)]}
    assert locate_named({}, {}, places, "Savemore") is None
    assert locate_named({}, {}, places, "No Such Place") is None


# --- build ------------------------------------------------------------------------


def write_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in COLUMNS})
    return path


def row(**fields):
    base = {
        "id": "espana-maceda",
        "name": "España Blvd cor. Maceda St",
        "city": "Manila",
        "aliases": "Espana Maceda;España cor. Maceda",
        "locator": "intersection",
        "a": "España Boulevard",
        "b": "A. Maceda Street",
        "source": "MMDA alert, Jul 10, 2026 (GMA News)",
    }
    base.update(fields)
    return base


def extract(ways=None, nodes=None, places=None):
    """A reader that returns this fixed extract, and records what it was asked for."""
    asked = []

    def read(osm_path, streets, features):
        asked.append((Path(osm_path), set(streets), set(features)))
        return (ways or {}), (nodes or {}), (places or {})

    read.asked = asked
    return read


CORNER_EXTRACT = {
    "ways": {"España Boulevard": [[1, 2]], "A. Maceda Street": [[2, 3]]},
    "nodes": {1: at_metres(CORNER, north=5), 2: CORNER, 3: at_metres(CORNER, north=-5)},
}


def test_build_places_an_intersection_and_writes_the_documented_fields(
    tmp_path, capsys
):
    sources = write_csv(tmp_path / "s.csv", [row()])
    reader = extract(**CORNER_EXTRACT)
    spots = build(sources, tmp_path / "x.pbf", read=reader)
    assert spots == [
        {
            "id": "espana-maceda",
            "name": "España Blvd cor. Maceda St",
            "city": "Manila",
            "lat": 14.61433,
            "lng": 120.99813,
            "roads": ["España Boulevard", "A. Maceda Street"],
            "aliases": ["Espana Maceda", "España cor. Maceda"],
        }
    ]
    # The reader is asked for the folded street names only, and no feature.
    ((_, streets, features),) = reader.asked
    assert streets == {"espana boulevard", "a. maceda street"}
    assert features == set()
    assert "1 placed, 0 not placed" in capsys.readouterr().out


def test_points_are_rounded_to_5_decimals(tmp_path):
    point = (14.6143349, 120.9981351)
    sources = write_csv(tmp_path / "s.csv", [row()])
    spots = build(
        sources,
        tmp_path / "x.pbf",
        read=extract(
            ways={"España Boulevard": [[1]], "A. Maceda Street": [[1]]},
            nodes={1: point},
        ),
    )
    assert (spots[0]["lat"], spots[0]["lng"]) == (14.61433, 120.99814)
    for field in ("lat", "lng"):
        assert len(repr(spots[0][field]).split(".")[1]) <= 5


def test_a_named_row_uses_its_feature_and_lists_its_roads(tmp_path):
    named = row(
        id="taft-pgh",
        name="Taft Ave in front of PGH",
        aliases="Taft front of PGH",
        locator="named",
        a="Philippine General Hospital",
        b="",
        roads="Taft Avenue;Taft",
    )
    reader = extract(places={"philippine general hospital": [CORNER]})
    spots = build(
        write_csv(tmp_path / "s.csv", [named]), tmp_path / "x.pbf", read=reader
    )
    assert spots[0]["roads"] == ["Taft Avenue", "Taft"]
    assert (spots[0]["lat"], spots[0]["lng"]) == CORNER
    ((_, streets, features),) = reader.asked
    assert streets == set() and features == {"philippine general hospital"}


def test_an_intersection_lists_its_two_roads_then_the_extra_names(tmp_path):
    spot = row(roads="España;Maceda;España Boulevard")
    spots = build(
        write_csv(tmp_path / "s.csv", [spot]),
        tmp_path / "x.pbf",
        read=extract(**CORNER_EXTRACT),
    )
    assert spots[0]["roads"] == [
        "España Boulevard",
        "A. Maceda Street",
        "España",
        "Maceda",
    ]


def test_a_manual_row_keeps_its_point_and_a_row_with_no_point_is_reported_not_written(
    tmp_path, capsys
):
    manual = row(
        id="here",
        name="A hand-picked spot",
        aliases="",
        locator="manual",
        a="",
        b="",
        roads="Somewhere Street",
        lat="14.60950",
        lng="120.98940",
    )
    no_point = row(
        id="ghost",
        name="Ghost Corner",
        aliases="",
        locator="manual",
        roads="X",
        a="",
        b="",
    )
    unmatched = row(
        id="nowhere", name="Nowhere Corner", aliases="", a="Nowhere Road", b="No Street"
    )
    sources = write_csv(tmp_path / "s.csv", [manual, no_point, unmatched, row()])
    reader = extract(**CORNER_EXTRACT)
    spots = build(sources, tmp_path / "x.pbf", read=reader)
    assert [s["id"] for s in spots] == ["here", "espana-maceda"]
    assert (spots[0]["lat"], spots[0]["lng"]) == (14.6095, 120.9894)
    out = capsys.readouterr().out
    assert "2 placed, 2 not placed" in out
    assert "ghost: no point" in out
    assert "nowhere: no match in the extract" in out


def test_points_outside_the_ncr_bounds_are_refused(tmp_path, capsys):
    assert in_metro_manila(*CORNER) and not in_metro_manila(*CEBU)
    cebu_manual = row(
        id="cebu",
        name="Colon Street",
        aliases="",
        locator="manual",
        a="",
        b="",
        roads="Colon Street",
        lat=str(CEBU[0]),
        lng=str(CEBU[1]),
    )
    # An intersection whose only shared node lies in Cebu is refused the same way.
    cebu_corner = row(
        id="cebu-corner",
        name="Cebu Corner",
        aliases="",
        a="Colon Street",
        b="Osmena Boulevard",
    )
    reader = extract(
        ways={"Colon Street": [[7]], "Osmena Boulevard": [[7]]}, nodes={7: CEBU}
    )
    sources = write_csv(tmp_path / "s.csv", [cebu_manual, cebu_corner])
    assert build(sources, tmp_path / "x.pbf", read=reader) == []
    out = capsys.readouterr().out
    assert "cebu: outside Metro Manila" in out
    assert "cebu-corner: outside Metro Manila" in out


def test_the_output_has_every_id_once_and_no_alias_appears_under_two_spots(tmp_path):
    reader = extract(**CORNER_EXTRACT)
    other = row(id="other", name="Other Corner")
    # Two rows with one id: refused, naming the id.
    again = write_csv(tmp_path / "a.csv", [row(), row(name="Another")])
    with pytest.raises(ValueError, match="espana-maceda.*twice"):
        build(again, tmp_path / "x.pbf", read=reader)
    # One alias under two spots, however it is spelled: refused, naming both.
    shared = write_csv(
        tmp_path / "b.csv",
        [row(), other | {"aliases": "ESPANA  maceda"}],
    )
    with pytest.raises(ValueError, match="espana maceda.*espana-maceda.*other"):
        build(shared, tmp_path / "x.pbf", read=reader)
    # An alias that is another spot's display name is the same clash.
    clash = write_csv(
        tmp_path / "c.csv", [row(), other | {"aliases": "españa blvd cor. maceda st"}]
    )
    with pytest.raises(ValueError, match="españa blvd cor. maceda st|espana blvd"):
        build(clash, tmp_path / "x.pbf", read=reader)
    # Distinct ids and aliases build.
    fine = write_csv(tmp_path / "d.csv", [row(), other | {"aliases": "Other"}])
    ids = [s["id"] for s in build(fine, tmp_path / "x.pbf", read=reader)]
    assert len(ids) == len(set(ids)) == 2


@pytest.mark.parametrize(
    "bad, message",
    [
        ({"id": "Not Kebab"}, "id"),
        ({"locator": "somewhere"}, "locator"),
        ({"a": ""}, "street"),
        ({"city": ""}, "city"),
        ({"name": ""}, "name"),
        ({"source": ""}, "source"),
    ],
)
def test_a_malformed_row_is_refused_by_name(tmp_path, bad, message):
    sources = write_csv(tmp_path / "s.csv", [row(**bad)])
    with pytest.raises(ValueError, match=message):
        build(sources, tmp_path / "x.pbf", read=extract())


def test_a_landmark_the_alert_puts_on_no_road_keeps_an_empty_roads_list(tmp_path):
    named = row(
        id="mall",
        name="Some Mall",
        aliases="",
        locator="named",
        a="Some Mall",
        b="",
        roads="",
    )
    reader = extract(places={"some mall": [CORNER]})
    (spot,) = build(
        write_csv(tmp_path / "s.csv", [named]), tmp_path / "x.pbf", read=reader
    )
    assert spot["roads"] == [] and spot["aliases"] == []


def test_a_named_row_that_is_not_placed_gives_its_real_cause(tmp_path, capsys):
    mall = row(
        id="mall", name="Some Mall", aliases="", locator="named", a="Some Mall", b=""
    )
    sources = write_csv(tmp_path / "s.csv", [mall])
    path = tmp_path / "x.pbf"
    apart = {"some mall": [CORNER, at_metres(CORNER, north=2000)]}
    # Two namesakes in Metro Manila's box that are too far apart.
    assert build(sources, path, read=extract(places=apart)) == []
    assert "mall: no match in the extract: the namesakes are over 150 m apart" in (
        capsys.readouterr().out
    )
    # A way of that name whose nodes the reader dropped (outside the box) gives no
    # point at all, so it is not a pair of namesakes.
    outside = extract(ways={"some mall": [[1, 2]]})
    assert build(sources, path, read=outside) == []
    assert "mall: no match in the extract: nothing named 'Some Mall' here" in (
        capsys.readouterr().out
    )
    assert build(sources, path, read=extract()) == []
    assert "nothing named 'Some Mall' here" in capsys.readouterr().out


def test_the_extract_is_not_read_when_no_row_needs_it(tmp_path):
    manual = row(
        id="here",
        name="A hand-picked spot",
        aliases="",
        locator="manual",
        a="",
        b="",
        roads="Somewhere Street",
        lat="14.6095",
        lng="120.9894",
    )
    reader = extract()
    build(write_csv(tmp_path / "s.csv", [manual]), tmp_path / "x.pbf", read=reader)
    assert reader.asked == []


# --- main --------------------------------------------------------------------------


def test_main_writes_the_list_only_with_write(tmp_path, capsys):
    sources = write_csv(tmp_path / "s.csv", [row()])
    out_file = tmp_path / "spots.json"
    reader = extract(**CORNER_EXTRACT)
    where = {"read": reader, "sources": sources, "out": out_file}
    argv = ["--osm", str(tmp_path / "x.pbf")]
    assert main(argv, **where) == 0
    assert not out_file.exists()
    assert main([*argv, "--write"], **where) == 0
    text = out_file.read_text(encoding="utf-8")
    assert text.endswith("]\n") and "\r" not in text and "España" in text
    assert json.loads(text)[0]["id"] == "espana-maceda"
    assert "wrote 1 spots" in capsys.readouterr().out


def test_main_exits_1_and_lists_unplaced_ids_but_still_writes_the_placed(
    tmp_path, capsys
):
    sources = write_csv(
        tmp_path / "s.csv",
        [row(), row(id="lost", name="Lost", aliases="", a="Q", b="R")],
    )
    out_file = tmp_path / "spots.json"
    argv = ["--osm", str(tmp_path / "x.pbf"), "--write"]
    where = {"read": extract(**CORNER_EXTRACT), "sources": sources, "out": out_file}
    assert main(argv, **where) == 1
    assert [s["id"] for s in json.loads(out_file.read_text(encoding="utf-8"))] == [
        "espana-maceda"
    ]
    assert "lost: no match in the extract" in capsys.readouterr().out


def test_main_exits_1_on_a_malformed_sources_file(tmp_path, capsys):
    sources = write_csv(tmp_path / "s.csv", [row(locator="somewhere")])
    argv = ["--osm", str(tmp_path / "x.pbf")]
    assert main(argv, read=extract(), sources=sources) == 1
    assert "locator" in capsys.readouterr().out


@pytest.mark.parametrize(
    "folder", ["sealed", "SEALED", "sealed.", "sealed ", "sealed::$INDEX_ALLOCATION"]
)
def test_a_path_with_a_part_named_sealed_is_refused_before_any_read(folder, tmp_path):
    reader = extract(**CORNER_EXTRACT)
    sources = write_csv(tmp_path / "s.csv", [row()])
    # Nothing is made on disk: the path only has to name the folder.
    argv = ["--osm", str(tmp_path / folder / "x.pbf")]
    with pytest.raises(SystemExit) as stop:
        main(argv, read=reader, sources=sources)
    assert stop.value.code == 2
    assert reader.asked == []


def test_a_missing_extract_is_a_clear_error_not_a_trace(tmp_path, capsys):
    sources = write_csv(tmp_path / "s.csv", [row()])
    argv = ["--osm", str(tmp_path / "missing.pbf")]
    assert main(argv, sources=sources) == 1
    out = capsys.readouterr().out
    assert "the extract is not a file" in out
    assert str(tmp_path) not in out and "missing.pbf" not in out


def test_a_missing_sources_file_is_named_without_its_path(tmp_path, capsys):
    argv = ["--osm", str(tmp_path / "x.pbf")]
    assert main(argv, read=extract(), sources=tmp_path / "gone.csv") == 1
    out = capsys.readouterr().out
    assert "the sources file could not be read (FileNotFoundError)" in out
    assert str(tmp_path) not in out and "gone.csv" not in out


# --- the reader, on a stand-in for osmium ---------------------------------------------


class FakeObject:
    """What osmium's FileProcessor yields: a node or a way with its tags."""

    def __init__(self, kind, id, tags=None, point=None, refs=()):
        self.kind, self.id, self.tags = kind, id, tags or {}
        self.location = point and types.SimpleNamespace(lat=point[0], lon=point[1])
        self.nodes = [types.SimpleNamespace(ref=ref) for ref in refs]

    def is_node(self):
        return self.kind == "n"


def node(id, point, **tags):
    return FakeObject("n", id, tags, point=point)


def way(id, refs, **tags):
    return FakeObject("w", id, tags, refs=refs)


def fake_osmium(objects=(), fail=None):
    """A module with the parts of osmium that read_extract uses: FileProcessor with
    with_filter, KeyFilter, IdFilter and the NODE and WAY flags."""
    node_flag, way_flag = 1, 2

    class KeyFilter:
        def __init__(self, *keys):
            self.keys = keys

    class IdFilter:
        def __init__(self, ids):
            self.ids = set(ids)

    class FileProcessor:
        def __init__(self, path, entities):
            if fail is not None:
                raise fail
            self.entities, self.filters = entities, []

        def with_filter(self, one):
            self.filters.append(one)
            return self

        def __iter__(self):
            for obj in objects:
                if not self.entities & (node_flag if obj.is_node() else way_flag):
                    continue
                if all(self.passes(one, obj) for one in self.filters):
                    yield obj

        @staticmethod
        def passes(one, obj):
            if isinstance(one, KeyFilter):
                return any(key in obj.tags for key in one.keys)
            return obj.id in one.ids

    return types.SimpleNamespace(
        osm=types.SimpleNamespace(NODE=node_flag, WAY=way_flag),
        filter=types.SimpleNamespace(KeyFilter=KeyFilter, IdFilter=IdFilter),
        FileProcessor=FileProcessor,
    )


def test_a_way_without_a_highway_tag_is_never_used_for_an_intersection(
    tmp_path, monkeypatch
):
    decoy = at_metres(CORNER, north=3000)
    objects = [
        node(1, CORNER),
        node(2, at_metres(CORNER, north=5)),
        node(3, at_metres(CORNER, north=-5)),
        node(8, decoy),
        node(9, at_metres(decoy, east=10)),
        way(100, [1, 2], highway="primary", name="España Boulevard"),
        way(101, [1, 3, 8], highway="tertiary", name="A. Maceda Street"),
        # A building that carries the street's name and meets Maceda 3 km away.
        way(102, [8, 9], building="yes", name="España Boulevard"),
    ]
    monkeypatch.setitem(sys.modules, "osmium", fake_osmium(objects))
    (tmp_path / "x.pbf").write_bytes(b"")
    sources = write_csv(tmp_path / "s.csv", [row()])
    (spot,) = build(sources, tmp_path / "x.pbf")
    assert (spot["lat"], spot["lng"]) == (round(CORNER[0], 5), round(CORNER[1], 5))


def test_a_reader_failure_names_the_extract_and_not_its_path(
    tmp_path, monkeypatch, capsys
):
    path = tmp_path / "x.pbf"
    path.write_bytes(b"")
    broken = fake_osmium(fail=RuntimeError(f"cannot read {path}"))
    monkeypatch.setitem(sys.modules, "osmium", broken)
    sources = write_csv(tmp_path / "s.csv", [row()])
    assert main(["--osm", str(path)], sources=sources) == 1
    out = capsys.readouterr().out
    assert "the extract could not be read (RuntimeError)" in out
    assert str(tmp_path) not in out and "x.pbf" not in out


# --- the committed list ------------------------------------------------------------


def test_the_committed_spot_list_is_well_formed():
    spots = json.loads((DATA / "spots.json").read_text(encoding="utf-8"))
    # utf-8-sig, as the script reads it: Excel's "CSV UTF-8" adds a BOM.
    with (DATA / "spots_sources.csv").open(encoding="utf-8-sig", newline="") as file:
        sources = list(csv.DictReader(file))
    assert 25 <= len(spots) <= 80
    ids = [s["id"] for s in spots]
    assert len(ids) == len(set(ids))
    # Every spot is on the list of sources, and no row was dropped silently.
    assert ids == [r["id"] for r in sources]
    texts = [fold(t) for s in spots for t in [s["name"], *s["aliases"]]]
    assert len(texts) == len(set(texts))
    for spot in spots:
        assert set(spot) == {"id", "name", "city", "lat", "lng", "roads", "aliases"}
        assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", spot["id"])
        assert isinstance(spot["roads"], list), spot["id"]
        assert in_metro_manila(spot["lat"], spot["lng"]), spot["id"]
        for field in ("lat", "lng"):
            assert round(spot[field], 5) == spot[field], spot["id"]
        assert all(isinstance(t, str) and t.strip() for t in spot["aliases"])


def test_the_list_has_the_spots_that_ask_lusots_tests_name():
    spots = {
        s["id"]: s
        for s in json.loads((DATA / "spots.json").read_text(encoding="utf-8"))
    }
    corner = spots["espana-maceda"]
    wanted = {fold("España cor. Maceda"), fold("Espana Maceda")}
    assert wanted <= {fold(t) for t in [corner["name"], *corner["aliases"]]}
    # Several España spots and no plain España spot (Task 4's roadSpots case).
    on_espana = [s for s in spots.values() if "espana" in {fold(r) for r in s["roads"]}]
    assert len(on_espana) >= 2
    assert not any(
        fold(t) == "espana" for s in spots.values() for t in [s["name"], *s["aliases"]]
    )


def test_no_bare_name_that_is_also_a_place_outside_metro_manila_is_listed():
    # Antipolo (the city in Rizal), Quirino (the province) and Aurora (the province)
    # each name a place outside Metro Manila. A spot whose roads or aliases held one
    # of them alone would answer a question about that place with a Manila corner
    # before Nominatim is asked. The multi-word forms ("Antipolo Street") are fine.
    bare = {"antipolo", "quirino", "aurora"}
    spots = json.loads((DATA / "spots.json").read_text(encoding="utf-8"))
    for spot in spots:
        for text in [*spot["aliases"], *spot["roads"]]:
            assert fold(text) not in bare, (spot["id"], text)
    # They are not dropped from where they belong: the street names still hold them.
    streets = {fold(r) for spot in spots for r in spot["roads"]}
    assert {"antipolo street", "quirino avenue", "aurora boulevard"} <= streets
