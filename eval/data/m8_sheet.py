# /// script
# requires-python = ">=3.13,<3.14"
# dependencies = []
# ///
r"""Write the M8 page, set_a\m8_sheet.html, from Rene's Set A log (spec §5.4, C208).

The page lists each Set A photo once, by id, and shows it from raw\ beside the page.
Rene labels the photos there, in his own browser. Of the log, the command uses only
candidate_id and photo_file, and it checks that each photo exists with a stat, never
reading its bytes (C201). So the page holds the ids, the file names and Table 5's lists,
and no label, passability, link or spot text.

The page is one self-contained file that makes no network call: an inline stylesheet,
then one classic inline script at the end of the body, which holds m8_sheet.js verbatim
and then calls M8.start with the page's data.

Usage, from the repo root (Claude runs it, and again whenever Rene adds photos):
    uv run --locked --script eval/data/m8_sheet.py
        --set-a-log <data>\set_a\set_a_log.csv --out <data>\set_a\m8_sheet.html
It prints photos=<n> and a reminder to export the labels before the next remake.
Exit codes: 0 the page is written; 1 a problem, each printed as <id> <column>: <kind>
(row <n> when the id itself is bad), and nothing written; 2 a path inside a folder
named sealed (C222).
"""

import argparse
import html
import json
import re
import sys
from collections.abc import Sequence
from pathlib import Path

import formats
import guards
import table

# Rene's rule for a waterline between two marks, final since his MS3b-Q5 answer on
# Oct 28. Prompt v1 gives Muse Spark the same rule (C208).
IN_BETWEEN_RULE = (
    "When the water sits between two marks, pick the higher mark. "
    "This holds for wheels, people and car bodies alike."
)
# The browser's localStorage key for the page's autosave, the labels as CSV text.
STORAGE_KEY = "lusot-m8-v1"
SCRIPT = Path(__file__).with_name("m8_sheet.js")

# The photos carry the page, so the rest stays quiet. The in-between rule is the one
# thing set apart. System fonts only, since the page loads nothing. m8_sheet.js styles
# the photo, its markers and its row inline, so no rule here touches them: an inline
# style wins, and the click geometry depends on it. The tools stay in view only where
# they fit on one row; a taller sticky bar would hide the photos.
STYLE = """\
:root {
  color-scheme: light;
  --ink: #14212b;
  --muted: #4a5864;
  --paper: #ffffff;
  --rule: #c7d1d9;
  --edge: #6b7a87;
  --surface: #f3f6f9;
  --water: #1e4e79;
  --water-wash: #e9f1f8;
}
body {
  max-width: 75rem;
  margin: 0 auto;
  padding: 0 16px 48px;
  background: var(--paper);
  color: var(--ink);
  font: 16px/1.5 "Segoe UI", system-ui, -apple-system, Roboto, sans-serif;
}
h1 { margin: 24px 0 8px; font-size: 1.5rem; line-height: 1.25; }
.m8-how { max-width: 70ch; margin: 0 0 12px; color: var(--muted); }
.m8-rule {
  max-width: 70ch;
  margin: 0 0 16px;
  padding: 12px 16px;
  border-left: 6px solid var(--water);
  background: var(--water-wash);
}
.m8-tools {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 16px;
  padding: 12px 0;
  border-bottom: 1px solid var(--rule);
  background: var(--paper);
}
.m8-tools [role="status"] { flex: 1 0 100%; min-height: 1.5em; margin: 0; }
.m8-tools label, .m8-tools input { max-width: 100%; }
@media (min-width: 56em) {
  .m8-tools { position: sticky; top: 0; z-index: 1; }
  .m8-photo { scroll-margin-top: 9rem; }
}
button, select, input { font: inherit; color: inherit; }
button, select {
  min-height: 44px;
  padding: 0 12px;
  border: 1px solid var(--edge);
  border-radius: 6px;
  background: var(--surface);
  cursor: pointer;
}
button:hover, select:hover { border-color: var(--water); }
:focus-visible { outline: 3px solid var(--water); outline-offset: 2px; }
label {
  display: inline-flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  min-height: 44px;
}
input[type="checkbox"], input[type="radio"] {
  width: 18px;
  height: 18px;
  margin: 0;
  accent-color: var(--water);
}
a { color: var(--water); }
.m8-todo { margin-top: 12px; }
.m8-todo summary { min-height: 44px; padding: 10px 0; font-weight: 600; cursor: pointer; }
.m8-photo { margin-top: 24px; padding-top: 24px; border-top: 1px solid var(--rule); }
.m8-photo h2 { margin: 0 0 12px; font-size: 1.25rem; font-variant-numeric: tabular-nums; }
.m8-photo label { margin-right: 12px; }
.m8-photo li { margin: 0 0 12px; }
fieldset {
  margin: 0 0 12px;
  padding: 4px 12px 8px;
  border: 1px solid var(--rule);
  border-radius: 6px;
}
legend { padding: 0 4px; font-weight: 600; }
"""

# The script element comes last in the body, so M8.start, which appends to the body,
# puts the tools and the photos after the rule.
PAGE = """\
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>M8 labels</title>
<style>
{style}</style>
</head>
<body>
<h1>M8: label each Set A photo</h1>
<p class="m8-how">On each photo, click each vehicle, wheel and person you can read, \
and pick its values. Then set the photo's marks. A photo with nothing you can read gets \
its marks only.</p>
<p class="m8-rule"><strong>Between two marks:</strong> {rule}</p>
<script>
{script}M8.start(document, window, {data});
</script>
</body>
</html>
"""


def build_page(photos: Sequence[tuple[str, str]]) -> str:
    """The page for the photos, each an (id, file name) pair, listed in the order given.

    The data holds exactly the keys M8.start reads. Every < in it is escaped, so no file
    name can end the script element or open a comment in it; m8_sheet.js holds no </.
    """
    data = {
        "photos": [{"id": photo_id, "file": name} for photo_id, name in photos],
        "vehicleTypes": list(formats.VEHICLE_TYPES),
        "bodyWaterlines": list(formats.BODY_WATERLINES),
        "wheelWaterlines": list(formats.WHEEL_WATERLINES),
        "personWaterlines": list(formats.PERSON_WATERLINES),
        "storageKey": STORAGE_KEY,
    }
    return PAGE.format(
        style=STYLE,
        rule=html.escape(IN_BETWEEN_RULE, quote=False),
        script=SCRIPT.read_text(encoding="utf-8"),
        data=json.dumps(data).replace("<", "\\u003c"),
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Write the M8 page for the photos in Rene's Set A log (C208)."
    )
    parser.add_argument("--set-a-log", required=True, help="the Set A log's CSV")
    parser.add_argument(
        "--out", required=True, help="the page to write, beside the photos' raw folder"
    )
    args = parser.parse_args(argv)
    guards.refuse_sealed(args.set_a_log, args.out)
    try:
        log = table.read_table(Path(args.set_a_log))
    except table.MalformedCsv as error:
        print(error.args[0])
        return 1

    raw = Path(args.out).parent / "raw"
    photos: dict[str, str] = {}
    problems: list[table.Finding] = []
    for row in log.rows:
        photo_id, name = row["candidate_id"], row["photo_file"]
        if re.fullmatch(formats.SET_A_ID, photo_id) is None:
            problems.append(table.Finding(f"row {row['#']}", "candidate_id", "bad_id"))
        elif photo_id not in photos:  # an alert row repeats its photo's row (C223)
            photos[photo_id] = name
            guards.refuse_sealed(raw / name)
            if not (raw / name).is_file():  # a stat, which reads no byte (C201)
                problems.append(table.Finding(photo_id, "photo_file", "missing"))
    for problem in problems:
        print(problem)
    if problems:
        return 1

    # A rerun overwrites the page, as Rene adds photos. A remake that drops a photo
    # would drop its saved labels at his next change, hence the reminder.
    Path(args.out).write_bytes(build_page(sorted(photos.items())).encode("utf-8"))
    print(f"photos={len(photos)}")
    print("Before the page is remade, export your labels from it, so none is lost.")
    return 0


if __name__ == "__main__":
    sys.exit(guards.quiet(main))
