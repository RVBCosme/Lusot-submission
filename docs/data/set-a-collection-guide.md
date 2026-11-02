# Set A collection guide (for Rene, by hand)

Set A is the main evaluation set: Metro Manila flood photos, each paired with a flood alert that MMDA or a city posted for the same spot (plan §11, Table 12; manual action M7). We need about **50 photos**. The split into development and sealed photos happens later, by script, so you don't have to think about it while collecting.

This guide also covers A-neg, your M8 labels, Set B's cars (M10), the sidewall photos (M11), consented items (M9) and Set D (M13). Each log has an empty template in `eval/templates/`, and MS2's tools read the same columns and values (`eval/data/formats.py`, MS2 spec §5.9). Updated Oct 28 for MS2 (spec C209, C218), with the tracker's Set A search checklist v2 folded in.

**Why by hand:** Facebook's and X's terms ban automated collection (plan M7), and this is a Meta-run hackathon. You do the searching and saving. Claude's tools do the checks, the matching, the event IDs and the audit, and you run the split itself (M19), because only you hold its password. Claude never opens Facebook, X or a post's link, and never opens a Set A or A-neg photo before the split. Its checks read each log's text columns, which include the Commons rows' text that the tracker's script fills (below), and never a photo's bytes.

**Targets:** about 50 Set A photos and about 15 A-neg photos by **Oct 30, mid-afternoon**. You then label the photos on the M8 page, and you run the split that evening. Plan on about 3 minutes a photo once you're on a good day's posts (a rough guess).

## What counts as a good Set A photo

**Only photos that MMDA or a city government posted itself count** (plan §11, Table 25, M7, as updated Oct 27). The hackathon's rules disqualify an entry that uses data it holds no rights to. Under Philippine law, the Government's own works carry no copyright, so we may use these photos privately, but we never pass them on.

1. **Best:** an MMDA post (or a Quezon City post, since QC uses the same gauge) that contains **both** the alert and a photo. The photo and its label then come from one post, at one time.
2. **Also fine:** a photo that MMDA or a city government posted separately, at the **same named spot** (the same street plus its cross street or landmark) and within **30 minutes** of an MMDA or city alert for that spot.
3. **Never:** photos from news outlets, private pages or anyone else. News lists only help you find the official posts.
4. The photo must show the water against something Lusot can read: the wheel of a parked car, or an adult standing still, **in the water**. A wide aerial shot is useless.
5. Inside Metro Manila only.
6. **Labels printed on the picture:**
   - **Why it matters:** alert cards, banners and captions burned into the image can show the depth or passability. The AI can read that text, which would give it the answer.
   - **Crop or skip:** crop the text off when you save the photo, as long as the wheel or person stays in frame. If cropping would cut the reference out, skip the photo.
   - **Log it:** record this in `label_in_image` (see below).
7. **It looks real:** it's on the verified official page, on the flood day; the scene matches the named spot (signs, landmarks); and nothing is warped, such as text, wheels or hands. Official posts are the main protection against AI fakes, so skip anything doubtful.

Skip a photo if any of these is true:
- it isn't MMDA's or a city government's own photo, posted by it or credited to it
- the spot or time can't be pinned down
- the alert gives no depth, in words or inches
- it is a repost of an older photo
- it was shot at night and nothing is visible

**Which photos to take,** so the set isn't tilted toward easy ones:
- Collect every eligible photo you find, gutter deep included. Don't pick by how easy it looks, or by how clear it is.
- There is no limit per spot or per day (rules v0.10, Rene, Nov 2): log every eligible photo. The report says how many photos share a spot, so they aren't read as independent.

## Whose pages count

- MMDA's own Facebook page and X account.
- A city government's own page, or the official page of one of its offices, such as its disaster office (DRRMO) or its information office. Counting city offices is MS2-Q4's answer (a), approved on Oct 29 by Claude, under your delegation.
- **A news outlet's repost of the city's own photo** (rules v0.10): a post on X that credits the photo to the city office, with the city's own depth words. Log the office as `poster` and the repost as `post_url`. The final Set A was gathered this way, and the original city posts weren't traced.
- **Not these:** barangay pages, officials' personal pages, and police or fire pages. If you log one by mistake, the tools count its poster as `other`, and the photo is left out (`eval/rules.md` §9).
- **Skip a photo credited to anyone but MMDA or the city,** such as a resident or the news outlet itself, and don't log it. You write the poster yourself, as the credited office, so no tool can catch a photo that isn't the city's own.

Write `poster` and `alert_poster` as `MMDA`, as the city's name (`Quezon City`), or as the city's name followed by one of these office words: `Government`, `City Government`, `City Hall`, `LGU`, `DRRMO`, `CDRRMO`, `PIO`, `Public Information Office` or `Information Office`. For example: `Quezon City DRRMO`, `Manila Public Information Office`. Any other spelling, even a natural one such as "Manila DRRM Office", counts as `other`. The intake warns about every poster and alert poster it counts as `other`; when it does, check the spelling.

## Where to look (you browse; Claude never does)

- MMDA's official Facebook page and X account. Look at flood-alert posts on heavy-rain days.
- Quezon City's official city pages, which also post flood alerts with gauge levels.
- Claude has built an **alert index from public news articles** (`docs/research/2026-10-26-alert-index.md`: times, spots and levels from "LIST: flooded areas" stories). Use it to go straight to the matching official posts. The news photos themselves are never used.
- The July and August 2026 monsoon days are the best hunting ground. Start with these three days from the index:

| Day | When the lists went up | Deeper spots worth finding |
|---|---|---|
| Jul 10, 2026 (Typhoon Inday and habagat) | about 1:00 to 4:35 p.m.; MMDA's main alert at 2:50 p.m. | Pasig, Valle Verde VI (above knee level); C5 Ortigas, Valle Verde 6 (above gutter level); Mandaluyong, F. Ortigas cor. Boni (half knee at 2:50 p.m., gutter deep by 4:35 p.m.) |
| Aug 9, 2026 (habagat) | MMDA as of 8:20 a.m.; Quezon City 6:30 a.m.; Manila 7:13 a.m.; Valenzuela 5:55 a.m.; Pasig 6:20 a.m. | Las Piñas, Alabang–Zapote Junction and Marcos Alvarez Road (knee); Parañaque, Ninoy Aquino Oyster Plaza (half tire); Quezon City, Kapiligan, Brgy. Doña Imelda (waist, 37") |
| Aug 10, 2026 (habagat) | MMDA 6:38 a.m. | Quezon City, G. Araneta / Ma. Clara (waist, 37"); Valenzuela, 3S Center and Toyota Dalandanan (13–18"); Parañaque, Dr. A. Santos Ave., Olivarez School to Canaynay (12") |

- More days are in the tracker's addendum to the index (`alert-index-addendum.md`, in your handoff folder). Use it once you've OK'd it; it's on your task list. Skip Sep 2, 2024: MMDA's posts that day only say "subsided", with no depth words.

**Search words** (you type them):
- **Depth words, as MMDA's alerts write them:** "half gutter", "gutter deep", "above gutter level", "half knee", "knee deep", "above knee level", "half tire", "tire deep", "waist deep", "chest deep"
- **Passability:** "passable to all types of vehicles", "not passable to light vehicles", "NPLV"
- **Flood in Filipino:** "baha"
- **On X:** for example `from:MMDA since:2026-08-09 until:2026-08-11`, once you've checked that it's MMDA's verified account
- **On Facebook:** open the page's Photos or Posts and scroll back to the date, or search a spot's name, such as "MMDA Araneta Ma. Clara"

## Set up your logs (once)

1. Create `C:\Systems\Lusot\lusot-data\set_a\raw\` and `C:\Systems\Lusot\lusot-data\a_neg\raw\` if they don't exist.
2. **Keep a working copy of each log in Excel.** Open its template in `eval/templates/` (`set_a_log.csv`, `a_neg_log.csv`), format the date and time columns as Text, and save it as an Excel file: `C:\Systems\Lusot\lusot-data\set_a\raw\set_a_log.xlsx` and `C:\Systems\Lusot\lusot-data\a_neg\raw\a_neg_log.xlsx`. They go in `raw\` because the deny rules already keep agents out of it. Once 7-Zip has opened the split's archive, you delete `raw\` with the split's other inputs (C219). Close Excel first, because Windows can't delete a workbook that's still open. The other logs in this guide work the same way, with each working copy next to its CSV.
   - A log you already started as a CSV still works. To make it your working copy, open it through Data > From Text/CSV, with the date and time columns set to Text, and save it as `.xlsx`. If Excel already rewrote some dates or times, the intake flags them, and you fix them in the working copy.
   - Its columns can be the template's or the checklist's: a Set A log with the three new columns at the end, or an A-neg log made from the Set A template plus `surface`. A Set A log with only the 17 old columns works too, but a separate-post row needs `alert_poster` and `alert_spot_text`.
3. **Give the intake a CSV copy.** Whenever the log should be checked, and before the split, which reads only the CSV, save the working copy, then save it again as "CSV UTF-8 (Comma delimited)" under the template's name: `set_a\set_a_log.csv` and `a_neg\a_neg_log.csv`. Close that CSV without changing it, and go on in the `.xlsx`. Excel's plain "CSV" writes ñ, as in `Las Piñas`, in an encoding the check can't read.
   - Never open the CSV copy in Excel and save it again. A CSV keeps no cell formats, so Excel turns its dates and times into its own short form, such as `8/9/2026 8:20`, and the check then refuses every one.
   - If you have to open a CSV, use Data > From Text/CSV and set the date and time columns to Text.
4. **Keep every row full.**
   - Every row needs a cell for each column in the header row, even an empty one. This matters for the three optional columns at the end of Set A's header: if your header has them, every row needs their cells, even when all three are empty. A spreadsheet's CSV export does this for you.
   - Never leave a header cell blank, and never add an extra comma after the last column.
   - A row with too many or too few cells, or a header with a blank or repeated name, stops the check, so that no value slips into the wrong column.
5. **Dates and times** are Manila time. Write dates as `YYYY-MM-DD`, and times as `YYYY-MM-DD HH:MM` on the 24-hour clock, with two digits for the hour: `2026-08-09 08:20`, `2026-07-10 14:50`. Columns formatted as Text keep them exactly as you type them.

## How to log each Set A photo

1. **Save the photo** to `C:\Systems\Lusot\lusot-data\set_a\raw\` as `A001.jpg`, `A002.jpg` and so on (`.jpg`, `.jpeg` or `.png`). This folder is outside the repo. **Never** put these photos in the repo or share them.
2. **Add one row for each alert the photo may fit** (C209).
   - A **same-post row** is for the alert in the photo's own post (`photo_in_alert_post` is `yes`). A **separate-post row** is for an alert in another post (`no`).
   - Usually a photo has one row. If several alerts may fit it, log one row per alert: repeat the photo's columns exactly, its id included, and fill each row's alert columns for its own alert.
   - When the photo's post lists several spots, its same-post row is the alert for the photo's own spot only: log none of that post's other spots for this photo.
3. **Write the alert's words exactly as posted,** for example "gutter deep", "above gutter level" or "NPLV". Don't translate: `eval/rules.md` maps them to Lusot's levels separately.

| Column | What to put |
|---|---|
| `candidate_id` | `A001`, `A002`, … (matches the file name). All of a photo's rows share its id. |
| `logged_on` | The date you log the row, `YYYY-MM-DD` |
| `platform` | `facebook`, `x` or `other` (for example a city government website) |
| `post_url` | Link to the photo's official post. No tool ever opens it; the check only sees that it isn't empty. |
| `poster` | Who posted the photo, written as in "Whose pages count": `MMDA`, `Quezon City`, `Quezon City DRRMO`… |
| `post_time_pht` | When the photo's post went up, `YYYY-MM-DD HH:MM` |
| `alert_time_pht` | The alert's time, `YYYY-MM-DD HH:MM`. On a same-post row, fill it only when the text gives a time, as in "as of 8:20 a.m."; otherwise leave it blank. On a separate-post row, always fill it: the time the alert's text gives, or else the time of the alert's post. |
| `spot_text` | The photo's spot exactly as written, with its cross street or landmark |
| `city` | One of the 17 names below, as listed |
| `level_label_raw` | Only this alert's depth words, exactly as written, for example `Gutter deep, 8"`. Its passability goes in the next column. |
| `passability_raw` | This alert's passability words or code, exactly as written, such as `not passable to light vehicles` or `NPLV` (blank if none) |
| `photo_in_alert_post` | `yes` if the photo is in this row's alert post, otherwise `no` |
| `photo_file` | `A001.jpg` |
| `reference_visible` | `wheel`, `person`, `both` or `none` |
| `label_in_image` | `no` if no depth or passability words appear on the image; `cropped` if you cropped them off; `yes` if they're still visible (the photo is then excluded, per `eval/rules.md` §9) |
| `faces_or_plates` | `yes` or `no` (for privacy handling) |
| `notes` | Anything odd: angle, reflections, moving cars, partial wheel |
| `same_spot_as` | Optional. The ids of photos from the same date that show the same place under another name: a nearby spot named differently, or a corner on a city boundary. Separate several with `;`, as in `A004;A007`. Linking one side of a pair is enough. |
| `alert_poster` | Separate-post rows only: who posted the alert, written as for `poster`. Blank on same-post rows. |
| `alert_spot_text` | Separate-post rows only: the alert's spot, exactly as written. Blank on same-post rows. |

**The photo's columns and the alert's.** On a photo's extra rows, repeat `candidate_id`, `platform`, `post_url`, `poster`, `post_time_pht`, `spot_text`, `city`, `photo_file`, `reference_visible`, `label_in_image`, `faces_or_plates` and `same_spot_as` exactly; the intake flags an id whose rows differ in them. `logged_on`, `alert_time_pht`, `level_label_raw`, `passability_raw`, `photo_in_alert_post`, `alert_poster`, `alert_spot_text` and `notes` are each row's own. The tools join a photo's notes from all its rows.

**Never fill `other_alerts_raw`.** It isn't in your log: the tools work it out from your rows.

**The 17 names for `city`,** Metro Manila's 16 cities and Pateros, spelled as listed: `Caloocan`, `Las Piñas`, `Makati`, `Malabon`, `Mandaluyong`, `Manila`, `Marikina`, `Muntinlupa`, `Navotas`, `Parañaque`, `Pasay`, `Pasig`, `Pateros`, `Quezon City`, `San Juan`, `Taguig` and `Valenzuela`. A name the check doesn't recognise reads as outside Metro Manila: the intake warns, and the photo is left out (`eval/rules.md` §9).

**Link nearby spots yourself.** The tools group photos into flood events by their date and spot text, and they can't place a spot on a map. So when two photos from one date show the same place under different names, or a corner on a city boundary, link them in `same_spot_as` (C203). The tools split a spot's text into names only at a break: a word such as `cor.`, `corner`, `near`, `at`, `and` or `to`, a mark such as a comma, `/` or `&`, or a dash with a space on each side. So `Espana Maceda`, `UN Ave. Taft`, `EDSA Kamuning` and `España-Lacson` each read as one name: link photos of one date whose spot texts differ that way.

**How the tools match a photo to its alerts** (C223, C224; `eval/rules.md` §3), so you know why the spots and times matter:
- An alert in the photo's own post always fits.
- A separate alert fits when MMDA or a Metro Manila city government posted it, at the same spot, and its time and the photo's post time are at most 30 minutes apart. The same spot means the two spot texts share at least two names, such as a street and its cross street or landmark. A barangay, a zone or one of Manila's districts, such as Sampaloc, doesn't count as one of them. So a spot that reads as one name, such as a lone street or `EDSA Kamuning`, never fits.
- The fitting alert nearest in time gives the photo's labels, and the other fitting alerts' depth words become `other_alerts_raw`. If two fitting alerts disagree on the depth by two levels or more, the photo is left out as conflicting (`eval/rules.md` §3).
- A photo that no alert fits is left out as "no matching alert". The intake warns, so you can check for a slip in a spot or a time.

## When the intake flags something

Tell Claude when you've logged a batch ("logged up to A0xx"). Claude then runs the intake check on your logs (MS2 spec §5.3). It reads only the logs' text and checks that each named photo exists, and it prints only ids, column names, kinds and counts, never your text:
- **A problem** prints as `<id> <column>: <kind>`, for example `A004 city: missing`. A problem that no id can name starts with its log's name instead (`set_a`, `a_neg`, `m8`, `consented` or `sidewalls`), as in `set_a log city: missing_column` for a column the log lacks. Fix every problem before the split. Some kinds explained:
  - `missing` is an empty cell, and `file_missing` is a file the log names that isn't there, such as a photo that isn't in `raw\`.
  - `semicolon`: a depth or passability label holds a `;`, which the tools put between labels. Write it as a `,`, the one change to a post's words the check asks for.
  - `unknown`: a name in the header row that the tools don't know, often a misspelling. It prints with its log's name and its place in the header, counting the columns from 1 at the left, as in `a_neg log column 18: unknown`.
- **A warning** prints as `<id> <fact>=<value>`, for example `A007 match=none`. Warnings never stop anything. A photo warned as `metro_manila=no`, `poster_kind=other` or `match=none` is left out under `eval/rules.md` §9, with its reason logged, so check that it isn't your own slip. The next three only ask you to check the photo's rows:
  - `alert_poster=other`: an alert poster the tools count as `other`; on a separate-post row, that alert then never fits
  - `same_post=several`: two or more same-post rows (see step 2 of "How to log each Set A photo")
  - `nearest=tied`: two fitting alerts are equally near in time but give different words, so a fixed order picks the photo's labels: a same-post row first, then the row logged first
- **Row numbers:** when an id itself is bad, the intake names the row instead, after its log's name, as in `set_a row 3 candidate_id: bad_id`. It counts data rows, so data row n is your spreadsheet's row n + 1, because the header is row 1: `set_a row 3` is spreadsheet row 4.
- **A log the intake can't read** stops the check. Only one line prints, led by the log's name; fix that log, and Claude runs the check again:
  - `m8 log: file_missing`: the log isn't where Claude looked for it.
  - `set_a log: not_utf8`: the log wasn't saved as "CSV UTF-8" (step 3 of "Set up your logs").
  - `set_a row 4 cells: too_many`, or `too_few`: that row has more or fewer cells than the header row (step 4).
  - `set_a header column 21: blank`, or `duplicate`: a header cell that is empty, or repeats another's name. `reserved` means the name is `#`, which the tools keep for themselves.

Fix only your own transcription slips, never the post's words.

## A-neg (about 15 photos, no social media needed)

Wet streets that aren't flooded, and dry streets, ideally with parked cars or people in view. From Oct 29 they come from Wikimedia Commons (C209). Your own photos, and a friend's with their OK, still count.

- **Spread them out:** at least **5 places, over at least 2 days**, so the split has events to draw from.
- **Files:** `N001.jpg`, `N002.jpg` and so on, in `C:\Systems\Lusot\lusot-data\a_neg\raw\`.
- **The log:** `a_neg\a_neg_log.csv`, made from `eval/templates/a_neg_log.csv`, or the checklist's copy of the Set A template plus `surface`. Its columns are Set A's, except:
  - `candidate_id`: `N001`, `N002`, …
  - `poster`: `own`, `friend` or `commons`
  - `post_time_pht`: when the photo was taken, `YYYY-MM-DD HH:MM`
  - `spot_text` and `city`: where it was taken, in Metro Manila, as for Set A
  - `level_label_raw`: `none`
  - `surface`: `wet` or `dry`
  - `same_spot_as`: optional, as for Set A, with `N` ids
  - `licence` and `credit`: the template's last two columns, for Commons photos only (below). A log without them still works for your own and friends' photos.
  - On your own or a friend's row, `platform`, `post_url`, `alert_time_pht`, `passability_raw`, `photo_in_alert_post`, `licence` and `credit` stay blank. The template has no `alert_poster` or `alert_spot_text`; if your log has them, leave them blank too, since A-neg ignores them.
- **A Commons photo** is CC0, public domain or CC BY, never BY-SA. The tracker's script downloads each one unopened into `lusot-data\a_neg_commons_staging\` and fills its row's text columns; you review them and move the photos into `raw\`. Its row differs from your own:
  - `poster`: `commons`
  - `platform`: `other`
  - `post_url`: the photo's file page on Commons. No tool ever opens it.
  - `licence`: write exactly one of `cc0`, `pd`, `cc-by-2.0`, `cc-by-2.5`, `cc-by-3.0` or `cc-by-4.0`, matching the file page's wording to it (the page's "CC BY 4.0" becomes `cc-by-4.0`, and public domain becomes `pd`). Don't copy the page's wording over. Any other value is a problem, and we don't take `CC BY-SA` photos at all.
  - `credit`: the author's credit, as Commons gives it. The intake checks only that it isn't empty, and never prints it.
  - `post_time_pht`: the date the photo was taken. When the page gives a date only, write `00:00` for the time and "time unknown" in `notes`; for A-neg only the date is used.
  - `reference_visible`, `label_in_image` and `faces_or_plates`, and `surface` when the page doesn't say: you fill these after looking at each photo, because no Claude opens an A-neg photo before the split.
- **A friend's photo** needs their OK to send it to Meta with faces blurred, for evaluation only. It never goes into the repo or the demo.

## M8: your labels for each Set A photo (C208)

Before the split, and before Lusot ever runs on these photos, you label what each photo shows, without seeing its alert.

1. **The page.** Claude makes `set_a\m8_sheet.html` from your Set A log, and remakes it when you add photos. It shows every Set A photo once, by id. It never shows an alert's labels, passability, link or spot, so you never see the alert while labelling. Claude never opens the page in a browser, because it shows the photos.
2. **Click what you can read.** Open the page in your own browser. On each photo, click each vehicle, wheel and person you can read, and pick its values:
   - a **vehicle:** click its body, then pick its `vehicle_type` and `body_waterline`
   - a **wheel:** click its hub, then pick its `waterline`
   - a **person:** click the torso, then pick the `waterline`
3. **Mark the photo:** its `quality` (`ok`, `dark` or `blurry`) and any `subsets` that apply (`reflection`, `splash`, `moving`). A photo with nothing you can read gets its marks only.
4. **Between two marks:** when the water sits between two marks, pick the higher one. This holds for wheels, people and car bodies alike, and prompt v1 tells Muse Spark the same. It is your final rule (your MS3b-Q5 answer, Oct 28), and the page states it above the photos.
5. **Export.** The page keeps your work in the browser as you go, and can export it and import it back. When every photo is done, export `m8_labels.csv` and move it into `set_a\`. The split needs the marks of every Set A photo.
6. **After the split,** once 7-Zip has opened the archive, click **Clear saved work** on the page, so that your browser no longer holds the labels. Then close Excel, and delete the page with the split's other inputs, `raw\` included (C219).

**The values you pick from** (plan Table 5, as photo schema v1 lists them):
- `vehicle_type`: `sedan_hatch`, `suv_mpv`, `pickup`, `van`, `jeepney`, `tricycle`, `motorcycle`, `bus_truck`, `unknown`
- `body_waterline`: `below_bumper`, `bumper`, `door_sill`, `mid_door`, `window`, `not_visible`
- a wheel's `waterline`: `tire_only`, `rim_quarter`, `hub`, `rim_three_quarters`, `rim_top`, `wheel_covered`, `not_visible`
- a person's `waterline`: `ankle`, `mid_shin`, `knee`, `mid_thigh`, `waist`, `chest`, `above_chest`, `not_visible`

**What the export holds** (`eval/templates/m8_labels.csv`; you never edit it by hand):

| Column | Holds |
|---|---|
| `photo_id` | the photo's id, `A001`… |
| `ref_id` | `P1` for the photo's own row, which holds its marks; `R1`, `R2`… for each thing you clicked |
| `kind` | `photo`, `vehicle`, `wheel` or `person` |
| `x`, `y` | where you clicked, as fractions of the photo's width and height, from its top left |
| `vehicle_type`, `body_waterline` | a vehicle's values |
| `waterline` | a wheel's or a person's value |
| `quality`, `subsets` | the photo row's marks, with several subsets separated by `;` |

## Set B: parked cars (M10)

Set B tests the wheel geometry where the depth is known: you photograph dry parked cars, and the generator draws water onto them at known depths (G3).

- **Which cars:** parked, side-on, in daylight, plus an angled photo of some if there's time. The types are `sedan_hatch` (sedans and hatchbacks), `suv_mpv` (SUVs and MPVs) and `van`, each with the same tire code on both axles. Skip a car whose tire code has no aspect ratio, such as `195R14C`: the generator can't use it.
- **How many:** as many as you can by Oct 30, and about 10 in all. Fewer than 6 is fine (your decision, Oct 29): odd-numbered cars are for development and even-numbered ones are final, so 3 cars give 2 and 1.
- **Numbering (C210):** number the cars `B01`, `B02`… in the order you photograph them. Odd numbers are development cars, in `C:\Systems\Lusot\lusot-data\set_b\dev\`. Even numbers are final cars, in `set_b\sealed\`, and Claude never sees them.
- **Files:** each of those two folders holds its own `cars.csv`, made from `eval/templates/set_b_cars.csv`, with one row per photo, and the photos in `photos\` beside it: `B01-1.jpg`, `B01-2.jpg`… (the car, then the photo's number).
- **The owner's OK:** save each owner's OK (a screenshot is fine) beside `cars.csv`, name it in `consent_file`, and put the version of the text it answered in `consent_version`. Window 4 drafts the text (`docs/drafts/set-b-and-m11-permission-draft.md`, on its branch until it merges). A car without its OK is never sent to Meta. The final cars' OKs go into the Set B archive with the rest, so keep a copy outside `set_b\sealed\` if you want them at hand after the archive test.
- **Row numbers:** for the final cars, `generate.py --final` and `set_b_masks.py --final` name each problem by its row in `cars.csv`, as in `row 3 view: not_in_list`, never by a car id, so no final car id is printed. They count data rows: data row n is spreadsheet row n + 1.

| Column | What to put |
|---|---|
| `car_id` | `B01`, `B02`, … |
| `photo_file` | the photo, such as `B01-1.jpg`; one row per photo |
| `model` | the car's make and model, such as `Toyota Vios` |
| `vehicle_type` | `sedan_hatch`, `suv_mpv` or `van` |
| `tire_code` | the size code exactly as on the sidewall, such as `185/60R15` |
| `view` | `side` or `angled` |
| `taken_on` | the date, `YYYY-MM-DD` |
| `consent_file` | the file holding the owner's OK, beside `cars.csv` |
| `consent_version` | the version of the text the owner answered. The approved one is `SETB-v1`. Any other version only warns, and always will (C218). |
| `notes` | anything odd |

## Sidewall photos (M11)

Close photos of the size codes on the tire sidewalls of one jeepney, one tricycle and one bus, and of a Hilux and a Tamaraw if you can (G5). Claude reads each code from its photo and checks it against yours, and the confirmed codes go to MS3b's tire-code file.

- **Files:** the photos in `C:\Systems\Lusot\lusot-data\sidewalls\`, with `sidewalls.csv` beside them, made from `eval/templates/sidewalls.csv`, and each driver's permission (a screenshot is fine) there too. Window 4's draft of the permission text is in the same file as Set B's.
- **Row numbers:** this log has no id column, so the intake names its rows as `sidewalls row <n>`. It counts data rows too: data row n is spreadsheet row n + 1.

| Column | What to put |
|---|---|
| `photo_file` | the photo's file name |
| `vehicle` | `jeepney`, `tricycle`, `bus`, `hilux`, `tamaraw` or `other` |
| `model` | the model, if you know it |
| `tire_code` | the code as you read it on the sidewall |
| `checked_code` | leave it blank: Claude fills it in from the photo |
| `taken_on` | the date, `YYYY-MM-DD` |
| `consent_file` | the file holding the driver's permission |
| `consent_version` | the version of the text the driver answered. The approved one is `M11-v1`. Any other version only warns, and always will (C218). |
| `notes` | anything odd |

## Consented sample photos (M9, separate from Set A)

Flood photos and clips that friends, relatives or community groups give you, for the "Try a sample" button and the demo. They **never** join Set A.

- **Ask with the donor message you approve.** Window 4 drafts it in `docs/drafts/m9-donor-message-draft.md`, on its branch until it merges; its approved version is `M9-v4` (approved on Oct 29 by Claude, under your delegation), and only a v4 reply counts. It replaces the draft message this guide used to hold. The written OK must cover every use, because the rules require us to hold the rights to everything we submit, so a chat "sure" isn't enough.
- **Files:** each item in `C:\Systems\Lusot\lusot-data\consented\`, with `consented_log.csv` beside it, made from `eval/templates/consented_log.csv`, and each written OK (a screenshot of the reply is fine) there too.
- **Where and when** matter: each demo pin sits at its photo's real spot.
- **One row per item:** each item has its own `item_id`, because the demo pins are keyed by it. A row that repeats an earlier row's id gives `<id> item_id: duplicate`, such as `S002 item_id: duplicate`, once for that id; give the second item the next free id.

| Column | What to put |
|---|---|
| `item_id` | `S001`, `S002`, … |
| `file` | the photo's or clip's file name |
| `kind` | `photo` or `clip` |
| `taken_pht` | when it was taken, `YYYY-MM-DD HH:MM`, as near as the donor knows |
| `place_text` | where: the street and its cross street or landmark |
| `lat`, `lon` | the spot's latitude and longitude, read off a map by hand, in decimal degrees |
| `people` | who appears in it, and whether they agreed too |
| `source_note` | where it came from, and who took it |
| `consent_file` | the file holding the written OK |
| `consent_version` | the version of the donor message the OK answered, such as `M9-v4`. The intake accepts only a version you've approved (C218). |
| `notes` | anything odd |

## Set D (M13, only if it rains)

Set D is final only: it is sealed, and Claude never sees it. If it rains, find standing water next to a parked car, read its depth there with a ruler, and photograph it; aim for 5 or more such photos. Stay on a dry curb in boots the whole time: never wade into the water or walk onto the road.

- **Files:** the photos in `C:\Systems\Lusot\lusot-data\set_d\sealed\photos\`, and `set_d_log.csv` in `set_d\sealed\`, made from `eval/templates/set_d_log.csv`.
- **Then** you run `seal_set_d` yourself, test its archive in 7-Zip, close Excel, and empty `set_d\sealed\` (C217, C219). `seal_set_d` comes with MS2's Task 18, after MS5's core screens; until it is merged, keep the photos and the log in `set_d\sealed\`.

| Column | What to put |
|---|---|
| `photo_id` | `D01`, `D02`, … |
| `photo_file` | the photo's file name, such as `D01.jpg` |
| `taken_pht` | when, `YYYY-MM-DD HH:MM` |
| `place_text` | where: the street and its cross street or landmark |
| `model` | the car's make and model |
| `vehicle_type` | one of the nine M8 vehicle types above |
| `tire_code` | the size code exactly as on the sidewall |
| `wheel` | the wheel you measured beside: `left` or `right` in the photo |
| `ruler_depth_in` | the depth your ruler read there, in inches |
| `notes` | anything odd |

## Never

- **No news-outlet photos.** News lists only point you to the official posts.
- **Nothing goes into the repo or gets shared.** The photos and logs stay in `lusot-data`.
- **Don't ask Claude to open a Set A or A-neg photo before the split.** The deny rules block reading or editing the `raw\` photo folders. They don't cover the logs, which Claude's checks do read, as text columns only (C201).
- **No relabelling after predictions.** Never change a label because of something Lusot answered.
