# The spot list: sources and licence

`spots.json` is Ask Lusot's list of named places (spec C715, C733; AskL-Q8). The API reads it to turn a place in a question into one point, and its display names of at most 30 characters, then three short aliases for long names, then its roads, go to the voice transcription as keywords (spec C740, C741). `spots_sources.csv` is the input, and `backend/scripts/build_spots.py` builds the output from it and an OpenStreetMap extract. Rerun on the same two files, it writes the same `spots.json`.

© OpenStreetMap contributors. `spots.json` is derived from OpenStreetMap data, which is available under the [Open Data Commons Open Database License (ODbL) 1.0](https://opendatacommons.org/licenses/odbl/1-0/) (see [openstreetmap.org/copyright](https://www.openstreetmap.org/copyright)). `spots.json` is shared under the same licence. Lusot is not affiliated with MMDA.

| Field | Value |
|---|---|
| Names | The places are the locations in the public MMDA and city flood alerts that [the alert index](../../../../docs/research/2026-10-26-alert-index.md) lists, read by hand from a handful of GMA News articles (Jul 10, Aug 9 and Aug 10, 2026). A name in an alert is a fact about a street or a landmark. No other list was searched: the MMDA list search was dropped under the data-collection rule, and no social platform was read. Each row of `spots_sources.csv` gives the list and date it came from in its `source` column. |
| Points | Every point comes from the OpenStreetMap extract below. None comes from Nominatim, from a map click or from a person's location, and the file holds no `manual` row. |
| Extract | Geofabrik's Philippines extract dated Oct 29, 2026 (`philippines-261029.osm.pbf`), 612,150,451 bytes, SHA-256 `35f6c13a45079a08ab82d450567ee092ed121ee98c7d52104121488f51a6eb2f`. It is kept in the private data folder (`LUSOT_DATA_DIR`, under `osm\geofabrik\`), outside every repo. |
| Licence | **ODbL 1.0**, as Geofabrik's download page says for its extracts of OpenStreetMap data. Confirmed on that page on Oct 30, 2026, before this file was committed (AskL-Q8). |
| Placing | Names are compared after folding case and accents, and any of OpenStreetMap's name keys counts (`name`, `alt_name`, `old_name`, `name:en`, `short_name`, `official_name`), because MMDA writes "EDSA" where one way is named `EDSA` and another is named `Epifanio de los Santos Avenue`. An **intersection** is the node that a way named `a` and a way named `b` share (a street counts only if it has a `highway` tag). A **named** spot is the point of the node, or the mean of the way's nodes, that carries the feature's name. Several candidates give their mean when every pair is within 150 m, and no point otherwise. A point outside Metro Manila (`ncr.json`) is refused. Points are rounded to 5 decimals, about 1 m. |
| Memory | The reader makes two passes over the extract and holds no location index. Pass 1 keeps the ways, and the named nodes, whose folded name a row asks for. Pass 2 reads the coordinates of those ways' nodes only, in batches of node ids, because osmium's id filter allocates 4 MiB for each 33 million ids it spans. On Oct 30, 2026 the whole build took about 40 s with a peak of about 305 MB. |
| Result | 31 spots, all placed, none refused. |
| Tools | Python 3.13 with pyosmium 4.3.2 (BSD-2-Clause). `uv run backend/scripts/build_spots.py --osm <extract> [--write]`. |

## Reading the points

A spot is one point, named as one (C733). A corner is the shared node of its two streets, which can be a few tens of metres from the middle of a wide crossing. A landmark is the landmark's own point in OpenStreetMap, not the kerb in front of it, so "in front of PGH" is a point at the hospital, within about 150 m of Taft Avenue. Ask Lusot answers "within 300 m of" a spot, so the gap is smaller than the window.

## The 31 spots

Every spot's `name` is a display name, and its `aliases` hold the forms the alerts wrote (for example "Espana Maceda", "F. Ortigas cor. Boni" and "EDSA Kamuning") besides a few plain variants. Its `roads` hold OpenStreetMap's name for each street and the short forms people say ("EDSA", "España", "Roxas Blvd"). OpenStreetMap's current names differ from MMDA's in places: Kabihasnan Street is now Victor Medina Street, Santolan Road is now Colonel Bonny Serrano Avenue, and Buendia Avenue is now Senator Gil J. Puyat Avenue. No display name or alias appears under two spots, and none is a bare road name, so a bare "España" matches the roads of the two España spots and is no one spot's alias.

Three short forms are left out on purpose. "Antipolo", "Quirino" and "Aurora" each also name a place outside Metro Manila (Antipolo City in Rizal, and the provinces of Quirino and Aurora), so none stands alone in any spot's `roads` or `aliases`. Otherwise a one-word question about Antipolo would be answered with a Manila corner before Nominatim is asked. The spots keep the multi-word forms and OpenStreetMap's names ("Antipolo Street", "Quirino Avenue", "Aurora Boulevard"). "Roxas" stays in the `roads` of the five Roxas Boulevard spots: it also names Roxas City, but a bare "Roxas" matches all five, so Ask Lusot answers "too broad" and offers some of them. `test_no_bare_name_that_is_also_a_place_outside_metro_manila_is_listed` holds the three words out.

| Id | Display name | City | Point | List |
|---|---|---|---|---|
| `ortigas-boni` | F. Ortigas St cor. Boni Ave | Mandaluyong | the node that `F. Ortigas Street` and `Boni Avenue` share | MMDA alert, Jul 10, 2026 (GMA News); MMDA alert, Aug 9, 2026 (GMA News) |
| `edsa-aurora` | EDSA cor. Aurora Blvd | Quezon City | the feature `EDSA-Cubao Underpass Pumping Station` | MMDA alert, Jul 10, 2026 (GMA News) |
| `edsa-kamuning` | EDSA cor. Kamuning Rd | Quezon City | the node that `EDSA` and `Kamuning Road` share | MMDA alert, Jul 10, 2026 (GMA News) |
| `araneta-rodriguez` | G. Araneta Ave cor. E. Rodriguez Sr. Ave | Quezon City | the node that `Gregorio Araneta Avenue` and `E. Rodriguez Sr. Avenue` share | MMDA alert, Jul 10, 2026 (GMA News); Quezon City LGU list, Aug 9, 2026 (GMA News); MMDA update, Aug 10, 2026 (GMA News) |
| `edsa-santolan` | EDSA cor. Col. Bonny Serrano Ave (Santolan) | Quezon City | the node that `EDSA` and `Colonel Bonny Serrano Avenue` share | MMDA alert, Jul 10, 2026 (GMA News) |
| `edsa-north-avenue` | EDSA cor. North Ave | Quezon City | the node that `EDSA` and `North Avenue` share | MMDA alert, Jul 10, 2026 (GMA News) |
| `quezon-biak-na-bato` | Quezon Ave cor. Biak-na-Bato St | Quezon City | the node that `Quezon Avenue` and `Biak na Bato Street` share | MMDA alert, Jul 10, 2026 (GMA News) |
| `edsa-main-avenue` | EDSA cor. Main Ave | Quezon City | the node that `EDSA` and `Main Avenue` share | MMDA alert, Jul 10, 2026 (GMA News) |
| `taft-pgh` | Taft Ave in front of PGH | Manila | the feature `Philippine General Hospital` | MMDA alert, Jul 10, 2026 (GMA News) |
| `espana-maceda` | España Blvd cor. Maceda St | Manila | the node that `España Boulevard` and `A. Maceda Street` share | MMDA alert, Jul 10, 2026 (GMA News) |
| `espana-antipolo` | España Blvd cor. Antipolo St | Manila | the node that `España Boulevard` and `Antipolo Street` share | MMDA update, Aug 10, 2026 (GMA News) |
| `marcos-sm-marikina` | Marcos Highway at SM Marikina | Marikina | the feature `SM Marikina Pedestrian Link Bridge` | MMDA alert, Jul 10, 2026 (GMA News) |
| `edsa-shaw` | EDSA cor. Shaw Blvd | Mandaluyong | the node that `EDSA` and `Shaw Boulevard` share | MMDA alert, Jul 10, 2026 (GMA News) |
| `edsa-p-tuazon` | EDSA cor. P. Tuazon Blvd | Quezon City | the node that `EDSA` and `P. Tuazon Boulevard` share | MMDA alert, Aug 9, 2026 (GMA News) |
| `oyster-plaza` | Ninoy Aquino Ave at Oyster Plaza | Parañaque | the feature `Oyster Plaza Hotel` | MMDA alert, Aug 9, 2026 (GMA News) |
| `sucat-sm` | Dr. A. Santos Ave in front of SM Sucat | Parañaque | the feature `SM Hypermarket Sucat` | MMDA alert, Aug 9, 2026 (GMA News) |
| `roxas-edsa` | Roxas Blvd cor. EDSA | Pasay | the node that `Roxas Boulevard` and `EDSA` share | MMDA alert, Aug 9, 2026 (GMA News); MMDA update, Aug 10, 2026 (GMA News) |
| `roxas-pedro-gil` | Roxas Blvd cor. Pedro Gil St | Manila | the node that `Roxas Boulevard` and `Pedro Gil Street` share | MMDA alert, Aug 9, 2026 (GMA News); MMDA update, Aug 10, 2026 (GMA News) |
| `un-ave-taft` | UN Ave cor. Taft Ave | Manila | the node that `United Nations Avenue` and `Taft Avenue` share | MMDA alert, Aug 9, 2026 (GMA News) |
| `araneta-baloy` | G. Araneta Ave cor. Baloy St | Quezon City | the node that `Gregorio Araneta Avenue` and `Baloy Street` share | Quezon City LGU list, Aug 9, 2026 (GMA News) |
| `santo-domingo-calamba` | Sto. Domingo Ave cor. Calamba St | Quezon City | the node that `Santo Domingo Avenue` and `Calamba Street` share | Quezon City LGU list, Aug 9, 2026 (GMA News) |
| `samat-don-jose` | Samat St cor. Don Jose St | Quezon City | the node that `Samat Street` and `Don Jose Street` share | Quezon City LGU list, Aug 9, 2026 (GMA News) |
| `amoranto-don-jose` | N.S. Amoranto Ave cor. Don Jose St | Quezon City | the node that `N. S. Amoranto Sr. Avenue` and `Don Jose Street` share | Quezon City LGU list, Aug 9, 2026 (GMA News) |
| `taft-quirino` | Taft Ave cor. Quirino Ave | Manila | the node that `Taft Avenue` and `Quirino Avenue` share | Manila LGU note, Aug 9, 2026 (GMA News) |
| `roxas-us-embassy` | Roxas Blvd at the US Embassy | Manila | the feature `Embassy of the United States of America Chancery` | MMDA update, Aug 10, 2026 (GMA News) |
| `roxas-kalaw` | Roxas Blvd cor. T.M. Kalaw Ave | Manila | the node that `Roxas Boulevard` and `Kalaw Avenue` share | MMDA update, Aug 10, 2026 (GMA News) |
| `roxas-buendia` | Roxas Blvd cor. Gil Puyat Ave (Buendia) | Pasay | the node that `Roxas Boulevard` and `Senator Gil J. Puyat Avenue` share | MMDA update, Aug 10, 2026 (GMA News) |
| `araneta-maria-clara` | G. Araneta Ave cor. Maria Clara St | Quezon City | the node that `Gregorio Araneta Avenue` and `Maria Clara Street` share | MMDA update, Aug 10, 2026 (GMA News) |
| `valenzuela-3s-dalandanan` | 3S Center, Dalandanan | Valenzuela | the feature `Bulwagang Pambarangay ng Dalandanan` | MMDA update, Aug 10, 2026 (GMA News) |
| `valenzuela-toyota-dalandanan` | Toyota Dalandanan | Valenzuela | the feature `Toyota - Valenzuela` | MMDA update, Aug 10, 2026 (GMA News) |
| `ninoy-aquino-kabihasnan` | Ninoy Aquino Ave cor. Kabihasnan St | Parañaque | the node that `Ninoy Aquino Avenue` and `Victor Medina Street` share | MMDA update, Aug 10, 2026 (GMA News) |

### Where a landmark stands in for the name an alert uses

These are the named spots whose OpenStreetMap feature is not called what the alert calls it. Rene may swap any of them for a better feature by changing one cell of `spots_sources.csv` and rerunning the script.

- `edsa-aurora`: Aurora Boulevard meets EDSA twice in Metro Manila, at Cubao and in Pasay, so the two streets do not give one corner. The point is the pumping station of the EDSA-Cubao underpass (`EDSA-Cubao Underpass Pumping Station`), about 30 m from the middle of the Cubao crossing's shared nodes.
- `taft-pgh`: the Philippine General Hospital, which OpenStreetMap maps as one building outline and two nodes within 150 m of each other.
- `marcos-sm-marikina`: the footbridge at the mall (`SM Marikina Pedestrian Link Bridge`). OpenStreetMap has no feature named SM City Marikina.
- `oyster-plaza`: `Oyster Plaza Hotel`. OpenStreetMap has no feature named Oyster Plaza alone, and the hotel is the nearest feature that carries the name. It lies about 145 m from `ninoy-aquino-kabihasnan`.
- `sucat-sm`: `SM Hypermarket Sucat`, which sits inside SM City Sucat. The mall's two buildings are 290 m apart, too far to take together.
- `roxas-us-embassy`: the embassy's chancery building (`Embassy of the United States of America Chancery`).
- `valenzuela-3s-dalandanan`: Dalandanan's barangay hall (`Bulwagang Pambarangay ng Dalandanan`), whose OpenStreetMap `alt_name` is "3S Center".
- `valenzuela-toyota-dalandanan`: the dealership `Toyota - Valenzuela`.

The last two have no `roads`: the alert names no road for them.

## Locations in the alerts that are not spots

Each location in the alert index is a spot, is merged into a spot, or is listed here with the reason.

| Location (as written) | Date | Why it is not a spot |
|---|---|---|
| Along Araneta between Quezon Ave. and E. Rodriguez | Jul 10 | A stretch between two corners. Its E. Rodriguez end is the spot `araneta-rodriguez`, from other rows, and the alert does not choose an end. |
| White Plains (WB, EB) | Jul 10 | A bare road, with no corner or landmark. |
| Valle Verde VI (outermost lane) | Jul 10 | In OpenStreetMap, Valle Verde 6 is a neighbourhood (an area), not a street. |
| C5 Ortigas Valle Verde 6 (SB, innermost lane) | Jul 10 | The same neighbourhood; no street named Valle Verde 6 meets C-5. |
| Alabang Zapote Junction | Aug 9 | Alabang-Zapote Road meets several roads, and the extract has no feature that names this junction in Las Piñas. Choosing one would be a guess. |
| Marcos Alvarez Road, Wonderland to Savemore | Aug 9 | A stretch from one landmark to another. |
| Roxas Heritage intersection | Aug 9 | No street is called Heritage. The extract has a hotel called The Heritage Hotel near Roxas Boulevard and EDSA, but the alert names an intersection, not the hotel, and gives no second street. Left out rather than guessed. |
| M.H. Del Pilar St. Maysilo (Malabon) | Aug 9 | Maysilo is a barangay. The extract's Maysilo Street and Maysilo Circle share no node with M. H. del Pilar Street. |
| M.H. Del Pilar St. (Tatawid) Santulan | Aug 9 | Santulan is a barangay (an area). |
| Don Basilio Bautista Hulong Duhat | Aug 9 | A street inside a barangay, with no corner or landmark. |
| 29, 42, 48 Kapiligan (looban, tabing-ilog), Brgy. Doña Imelda | Aug 9 | House numbers along an interior street. The street alone would be a bare road, and the numbers are not mapped as points. |
| Zamboanga St. Kanan Dulo near Bai Compound, Brgy. Vasra | Aug 9 | A street end near a compound that is not in the extract. |
| Bocobo Robinsons to Remedios Circle (Manila LGU's second place) | Aug 9 | A stretch from one landmark to another. Its first place, Taft cor. Quirino, is the spot `taft-quirino`. |
| Valenzuela LGU, 5:55 a.m. | Aug 9 | The index names no location. |
| Brgy. Dela Paz Kabutihan Rd and K115 St. (Pasig LGU) | Aug 9 | Bare interior roads in a barangay, with no corner or landmark. |
| Roxas Blvd SB - HK Plaza | Aug 10 | The extract has no feature named HK Plaza. |
| Dr. A. Santos Ave., Olivarez School to Canaynay | Aug 10 | A stretch from one landmark to another. |

"España and Taft subsided" (Jul 10) is a status, not a place.

### Rows merged into one spot

An alert row that names the same point as another becomes an alias of its spot, so no point is listed twice.

- `edsa-aurora`: EDSA Aurora Tunnel (NB/SB) and EDSA Aurora Service Road (NB).
- `ortigas-boni`: F. Ortigas St. cor. Boni Avenue (Jul 10), the later 4:35 p.m. line the same day, and F. Ortigas cor Boni Ave. (Aug 9).
- `araneta-rodriguez`: Araneta E. Rodriguez (SB/NB) (Jul 10), Araneta - E. Rodriguez (Quezon City LGU, Aug 9) and E Rodriguez - G. Araneta Intersection (Aug 10).
- `sucat-sm`: Dr. A. Santos Ave. in front of SM Sucat NB and SB.
- `roxas-pedro-gil`: Roxas Pedro Gil service road (Aug 9) and Roxas Blvd. - Pedro Gil NB and SB (Aug 10).
- `roxas-edsa`: Roxas Edsa intersection (Aug 9) and Roxas Blvd. - EDSA Intersection (Aug 10).
- `edsa-shaw`: EDSA Shaw Tunnel (NB), from the "later the same day" line of Jul 10.
- `taft-pgh`: Taft Avenue, Pedro Gil to front of PGH (NB).

## Not used

The "more dated GMA lists to check" at the end of the alert index were not read. A spot that one of them would add is a new row in `spots_sources.csv` and a rerun.
