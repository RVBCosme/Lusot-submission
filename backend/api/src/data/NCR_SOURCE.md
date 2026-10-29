# Metro Manila boundary: source and licence

`ncr.json` is the boundary that the Metro Manila test reads (spec C502, MS4-Q1). The API bundles it (`../metroManila.ts`), and the scripts read the same file (`backend/scripts/metro_manila.py`). Its test points are in `backend/api/test/fixtures/s2-points.json` (spec §7, S2).

© OpenStreetMap contributors. Both files are derived from OpenStreetMap data, which is available under the [Open Data Commons Open Database License (ODbL) 1.0](https://opendatacommons.org/licenses/odbl/1-0/) (see [openstreetmap.org/copyright](https://www.openstreetmap.org/copyright)). Both files are shared under the same licence.

| Field | Value |
|---|---|
| Source | OpenStreetMap relation [147488](https://www.openstreetmap.org/relation/147488), "Metro Manila" (`boundary=administrative`, `admin_level=3`, `ISO3166-2=PH-00`, `wikidata=Q13580`), version 252 of Aug 19, 2026 |
| Downloaded | Oct 29, 2026, 15:37 UTC, as one file from the OpenStreetMap API: `https://api.openstreetmap.org/api/0.6/relation/147488/full.json` (626,394 bytes, SHA-256 `e0dab6d92a7d96062c2f6794666815cdbd009e5f148f88d478ff878cc5c4226c`). No Nominatim call was made. |
| Licence | **ODbL 1.0.** The copyright page says: "OpenStreetMap is open data, licensed under the Open Data Commons Open Database License (ODbL) by the OpenStreetMap Foundation (OSMF)", and "If you alter or build upon our data, you may distribute the result only under the same license." The download itself names `http://opendatacommons.org/licenses/odbl/1-0/`. Checked on Oct 29, 2026. |
| Clipping | The relation reaches west to 120.79° E, far into Manila Bay, so it was clipped to OpenStreetMap's coastline. The coastline is a second download: the 326 `natural=coastline` ways in the box 14.30° to 14.85° N, 120.75° to 121.05° E, from the Overpass API (`overpass-api.de`, data as of Oct 29, 2026, 15:39 UTC; 620,628 bytes, SHA-256 `173bcc466a44e5e56e7bc779583e6dc14bd6b802ffa6dafac98f1a766f10b65f`). The relation's polygon was split along those ways. OpenStreetMap draws a coastline with land on its left, so each piece was kept or dropped by sample points about 0.2 m to either side of every coastline segment: 3 pieces, the bay dropped, and the mainland and one reclaimed island off Pasay kept. Laguna de Bay is a lake, not coastline, so the relation's line through it stays as it is. |
| Simplification | Douglas-Peucker at a tolerance of 0.00005° (Shapely 2.2.0's `simplify` with `preserve_topology=True`). The simplified border is at most 5.5 m from the clipped one (Hausdorff distance, measured in UTM zone 51N). Every S2 point keeps its side. |
| Rounding | Every coordinate is rounded to 6 decimal places (about 0.1 m), then repeated points are dropped and rings are oriented as RFC 7946 asks. Longer floats would put 12-digit runs in the file, which the account-ID scan fails (F4). |
| Result | A GeoJSON `MultiPolygon` of 2 polygons and 1,889 points: 43,100 bytes, SHA-256 `3716aea4de458881c14c82383bd1d2ce4081519749052f0b2d870a4c06a2a1f2`. |
| Tools | A one-off Python 3.13 script with Shapely 2.2.0 (BSD-3-Clause) and pyproj 3.8.0 (MIT), run outside the repo. Neither is a dependency of Lusot. The raw downloads stay in `lusot-data/osm/`, outside every repo. |

## S2's test points

`s2-points.json` holds 15 named places: one on each side of the seven borders that spec §7's S2 names, and one in Manila Bay.

- **Where they come from.** Each is an OpenStreetMap node, read from the OpenStreetMap API on Oct 29, 2026. Its `source` gives the node, its version and its tag. None is an offset from the polygon.
- **Each land point's side** comes from the place's own address tag (`addr:city` or `addr:town`), not from any boundary.
- **The bay point** is the Manila Yacht Club marina (`seamark:type=harbour`), on the water side of the coastline. The unclipped relation contains it, so it also checks the clipping.
- **`border_m`** is the point's distance to the border in `ncr.json`, in UTM zone 51N, rounded to the metre. Distances to the clipped border before simplification differ by at most 5 m.

Eleven points lie 130 m to 370 m from the border. Four lie further out, because no barangay hall, church, school or station nearer the line was mapped as a node with an address tag:
- JSIGM Bagumbong, Caloocan, 667 m
- Center for Positive Futures, Taguig, 825 m. Taguig meets Taytay only at Napindan's lakeshore.
- Purok 5 Outpost Barangay Santa Ana, Taytay, 466 m
- The Birthright Educators Foundation, Muntinlupa, 404 m
