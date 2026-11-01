# README outline for judges (draft)

> **Claude's draft, Oct 29, 2026, for MS8** ([spec](../../superpowers/specs/2026-10-29-ms8-submit-design.md): C901, C907, C912, C913, C920). The final README replaces today's root `README.md` on Nov 4 and is written from the committed evaluation report. Rene approves its wording (M20).
>
> - **Placeholders:** `[from the evaluation report]` means `eval/results/report/summary.json` or `report.md` only. Other brackets name the file or decision that fills them. No number is invented, and none is typed in by hand without its source (C901).
> - **Copy rules for every line below:** only the 9 levels and MMDA's 3 classes; "at this spot"; never "safe" in any form; no crossing advice; never a whole road or route; never "MMDA's 9 levels"; never "first"; never "accuracy" for Set A (it is agreement with posted labels, and indicative). Lead with the whole system, never "upload a photo, get an answer".
> - **Links** are relative (D6), except the live URL, the video, the APK release and outside sources.

---

## The outline

### Title and opening (above the fold)

- **Title:** Lusot
- **One line (draft):** "Lusot is a live map of flood depth at street spots in Metro Manila. Each pin gives the level at one spot, on MMDA's gauge or just outside it, with MMDA's passability class and the evidence it was read from. When a photo can't support a reading, Lusot tells the person who took it, and nothing is pinned."
- **The safety line,** as a quote block, word for word: "Lusot estimates depth at one spot. It is not advice to cross. Follow MMDA and local advisories."
- "Not affiliated with MMDA."
- One badge only: CI passing on `main` (plan §19: the repo shows the tests passing).

### 1. Judge path: 60 seconds

Numbered, one line each, so a judge can start all four within a minute (C913):

1. **Open the live app:** `[live URL]`, on a phone or a desktop. No account needed.
2. **Run a sample:** open **Tested**, pick a sample, press **Run this sample**, and confirm you are 18 or older. The real pipeline reads a credited flood photo, which takes about `[median seconds, from eval/results/latency.jsonl]` (median of `[n]` runs). A sample never reaches the map.

   Then one line for a pause (C913; MS9's N4). It holds whatever MS9-Q1 decides, because the README can't change after the cutoff (C921). Draft:

   "If new analyses are paused (the hackathon's model credits may run out during judging), the sample shows `[the app's paused line, MS5's string, as MS9's N1 asks]` instead of a new reading. Everything already stored still works: the map and its pins, the Tested page's figures, the samples' photos, the video, and the one command below. `[Only if MS9's N2 ships: a sample's saved result is marked as saved, with its date.]`"
3. **Watch the video** (2:40, English captions): `[video link]`
4. **Rebuild the evaluation report.** This needs Python 3.9 or newer, and no key, network or install:

   ```sh
   git clone https://github.com/RVBCosme/Lusot-submission lusot
   cd lusot
   python eval/run_eval.py --from-saved   # python3 on macOS and many Linux systems
   ```

   On Windows, where only the launcher may be installed: `py eval/run_eval.py --from-saved`.

   Expected: the headline counts, then `identical`, with exit code 0. *(Paste the real last lines from C919's clean-clone run.)*

Then one line for Android: "Android APK: `[GitHub Release link]` (SHA-256 `[…]`). The web URL is the main path; the APK is the same app." (C917, M15)

### 2. The problem

Two or three sentences, each with a source checked in `docs/research/` and its link recorded there first (C901):
- Two separate facts, never joined by "yet":
  - In July 2025, MMDA identified 49 flood-prone areas in the National Capital Region (ABS-CBN).
  - On Jul 22, 2025, MMDA reported more than 500 flood incidents in Metro Manila in the last 24 hours (GMA News). This is C14's wording, with the day and the reporter named.
- On Aug 9, 2026, GMA News carried two lists from different publishers, with different scopes: MMDA's 2:02 PM list named 4 flooded spots, and Quezon City's 2:20 PM list held 38 street entries, in the same gauge words. The source is the plan-update check, §5 of `docs/research/2026-10-27-plan-update-check.md`, not the alert index, whose Aug 9 lists are the morning ones.
- MMDA's alert lists name the spots it reports, and crowd reports, such as MapaKalamidad's, come as a photo, a location and the reporter's own description; Lusot can give a reading at other spots too. (The last clause is Lusot's own framing, not a sourced fact. The idea is plan §3's, in new words, and Task 3 records the sources for the first two.)

Then, honestly (plan §19): "Reading flood depth from objects of known size is established research (FloodVision and others; see `docs/research/`). Lusot adds MMDA's own gauge and classes, Metro Manila's streets, Taglish, a live map of expiring pins, and an open evaluation." Never "first". No MDPI figure is quoted (C14).

### 3. See it work

- `docs/media/overlay.gif`: the overlay drawing itself on a sample (C920). Under it, the credit line: "`[title]` by `[author]`, `[CC0 or CC BY x.0]`, `[source link]`. Lusot blurred faces and plates and drew the outlines."
- One sentence on what the GIF shows: the water, each wheel or person with its reading (a reference the pipeline dropped shows its reason, never a level), then the level, the landmark and the class.

### 4. The numbers

A table, filled only from `summary.json` (C901), for the configuration that ships, then the other:

| | Shipped configuration `[landmark only, or with geometry]` | The other | n |
|---|---|---|---|
| Underestimation: Lusot's level was shallower than the posted label | `[k of n (p%)]` | `[…]` | `[n answered]` |
| Passability agreement | `[…]` | `[…]` | `[n]` |
| Coverage: photos answered, out of every scored photo. Refusals and processing failures both count against it (rules §7). | `[…]` | `[…]` | `[n scored]` |
| Exact level agreement, and within one level | `[…]` *(once MS6 adds them, N1)* | `[…]` | `[n]` |
| Set B median error, geometry | `[x in, over n wheels]` | — | `[n wheels]` |
| The release gate for inches | `[passed, or not passed and why]` | — | — |
| The self-check | `[shipped or not; decided Oct 31]` | — | — |

Words under the table (draft): "These are agreement figures with the labels MMDA and the cities posted, mapped by rules written before any result was seen ([`eval/rules.md`](../../../eval/rules.md)). The sealed set has about `[n]` photos, so every figure is indicative. The full report, with every table, chart and exclusion, is `eval/results/report/report.md`." (In the final README this is a relative link; the folder exists only from the sealed run.) If rules §10's one disclosed rerun happened, its figures are shown beside the first run's, with the reason (MS6's C421).

### 5. Limits: read these before trusting a pin

- One photo gives the depth at one spot, at one moment. Lusot never describes a road or a route, and it isn't advice to cross; MMDA's advisories stay the authority.
- It needs a parked car's wheel or an adult in view. Without one, it says it can't tell.
- Dark, blurry or rain-streaked photos are refused.
- People on foot get the level only. MMDA's classes are for vehicles (plan §9).
- Inches show only if geometry passed its release gate: `[status]`.
- Faces are blurred before Meta receives a photo, but the blur can miss very small, side-on, covered or dark faces (W25).
- Pins fade after 1 hour and leave the map at 3 hours.
- **The weakness register,** W1 to W28. MS7 drafts this "Known limits" section (its C821), and MS8 keeps it, checked against `docs/PROGRESS.md` §3 on Nov 4. Each row is Done, with its evidence link, or explained in one line (plan §18).
  - The README's copy rules apply here too. PROGRESS's own wording for W23 holds the banned word, so its README row reads, for example, "A pin read as a guarantee", fixed by "the banned-word check and the copy review".
  - MS7's draft gets the same check (plan Task 12).
- **What was dropped,** and why (design §8, "When we slip"): for example, clip mode under MS5-Q5's default, and any other should-have that wasn't solid by its date.

### 6. How Lusot works

- **A new diagram** (SVG in `docs/media/`, drawn from the template and the code, not from the plan's figures): phone → upload link → S3 `raw/` → SQS, with its dead-letter queue → the analysis Lambda → DynamoDB → the API → the map. Ask Lusot goes from the API to Muse Spark and its tool.
- **The pipeline,** step by step as built (plan §7, paraphrased), each step one line:
  0. on the phone, before upload: the quality check (MS5's C604)
  1. on the server, first: the face blur (YuNet from OpenCV Zoo, by Wu, Peng and Yu, MIT licence; not a Meta model), before any photo goes to Meta (C20)
  2. the quality check again
  3. SAM 3.1 masks, one short phrase per request: `[SAM_PHRASES in backend/analysis/src/lusot_analysis/meta_client.py, as frozen]`
  4. numbered boxes drawn on the photo. Muse Spark 1.3 says, by box number, where the water line falls on each wheel or person, as categories in strict structured output; models never output inches.
  5. code turns the landmarks into one of the 9 levels and MMDA's class. Rim geometry adds a range in inches only if the release gate passed.
  6. combining: the deepest believable reading wins, and readings more than one level apart mean a refusal (D13)
  7. publishing: faces and plates blurred again with SAM's masks before storage, the raw photo deleted, and the pin set to expire
- **The figure** of the wheel landmarks and rim geometry (`docs/media/wheel-landmarks.svg`, C920).

### 7. Three Meta models, one job each

| Model ID | Its job in Lusot |
|---|---|
| `sam-3.1` | Masks for the water, the wheels and the people, plus faces and plates for the blur before storage |
| `muse-spark-1.3` | Names the landmarks from the numbered boxes (strict structured output), and runs Ask Lusot's tool calls |
| `muse-voice-transcribe-1.0` | Transcribes spoken Taglish questions |

How they are called, one line each: the Meta Model API through the OpenAI SDK at `https://api.meta.ai/v1`; SAM streamed; retries only on 429, 500 and 503, with backoff and jitter; prompts and schemas in versioned files; while the hackathon credits last, every call runs on them (D10). That wording holds after the credits lapse, whatever MS9-Q1 decides, and matches the privacy texts (MS9's N3). On voice: Muse Voice Transcribe lists code-switching among 25 evaluated languages; Lusot tests it on Taglish questions (`[MS6's result]`).

### 8. Ask Lusot

`[From the Ask Lusot spec, C700 onward.]` The outline, from plan §9:
- Typed or spoken Taglish. A spoken question is transcribed first, and the transcript shows with the answer.
- Muse Spark calls Lusot's single tool, `get_reports`, and builds its answer from those reports alone: the deepest one from the past 3 hours within 300 m, how many there are, and how old they are.
- It names the reports behind the answer, and marks demo pins "(demo)" (G1). When there are none, it says so.
- It sorts a vehicle into MMDA's classes, and goes no finer than that.
- `[One real example question and answer, copied from a test run, never invented.]`

### 9. The evaluation

- The rules were written before any result was seen: `eval/rules.md`, version `[v]`, approved by Rene on `[date]`.
- The sets: Set A (photos MMDA or a city posted itself, split by flood event into `[n]` development and `[n]` sealed photos); A-neg (`[n]`); Set B (synthetic waterlines on `[n]` cars and `[n]` crops); Set D (`[if it rained]`).
- One sealed run on `[date]`, at the freeze tag `[tag]`. The per-photo results are committed in `eval/results/`; no photos are.
- The ablation: landmark only, against landmark plus geometry, `[and without the self-check, if it shipped]`.
- The one command, again, with what "identical" proves.

### 10. Engineering

- One AWS SAM template in `ap-southeast-1`, with no manual console changes. The API is an HTTP API with a Node.js Lambda in TypeScript; the analysis runs in a Python container Lambda. S3 holds `raw/`, `blurred/`, `overlay/`, `demo/` and `samples/`; SQS has a dead-letter queue (5 receives, with an alarm); DynamoDB uses TTL. SSM holds the stop switches, CloudWatch the alarms, and Amplify Hosting serves the site.
- Each report is claimed before any Meta call, so a duplicate message never pays twice (G2). A claim that expires after a timeout can be taken again.
- The tests (pytest, Vitest, Playwright) run in GitHub Actions on every push: `[counts from the last CI run]`.

### 11. Privacy

From the privacy policy as Rene approves it (M21), with nothing beyond it:
- Faces are blurred before Meta receives a photo, and faces and plates again before Lusot stores a copy.
- The original is deleted after analysis. Reports, and their copies in `blurred/` and `overlay/`, are kept 7 days.
- Two kinds of photo are kept longer, as the privacy policy states:
  - demo pins' photos in `demo/`, which a 60-day backstop removes if the demo script doesn't (MS4's C510)
  - the sample photos in `samples/`, kept while the sample button exists (MS4-Q11), in the form the approved policy describes (MS7-Q7 settles whether they are stored blurred)
- No accounts and no names.
- Meta may use what it receives on the hackathon credits to improve its products, as Meta's billing page for accounts that use free credits says (checked by Rene, Nov 1, 2026), and the consent notice says so (D10). Beside it, Meta's Model API Terms of Service (§5.1, last updated Oct 9, 2026) say Meta won't use content sent to its Standard Services to train Meta Models: https://dev.meta.ai/legal/terms-of-service. While the hackathon credits last, Lusot's calls run on them. That wording holds after the credits lapse (MS9-Q1; MS9's N3).
- Link: `[privacy policy URL]`.

### 12. Run it yourself

- MS1's setup block, as it is today.
- The `npm run check` note (N3): "`npm run check:node` and `npm run check:py` run on any machine with Node 22 and uv, after `npm ci`. `check:secrets` needs gitleaks, and its plan-leak step reads a private planning file that isn't in this repository, so CI skips that step and a local run without the file stops there."
- Deploying needs your own AWS account and Meta key: see "Commands" in [`CLAUDE.md`](../../../CLAUDE.md).

### 13. What's new, and how it was built

- **The new-work line,** per MS8-Q3 (Rene, Nov 1): "All code, and everything the demo shows, was written from Oct 27, 2026 (Manila time), after kickoff." Nothing says everything in the repository dates from Oct 27, and no list of earlier planning notes is added; those files keep their own dates.
- **How to check it:**
  - The commit history starts on Oct 28, 2026. Lusot was developed in a private repository and carried over with its full history (MS8-Q1, MS8-Q2), so docs that name the private repository or link to it point at a page judges can't open.
  - Under MS8-Q1 (b), `commit-map.csv`, attached to the GitHub Release, maps the hashes cited in the docs to this repository's. It is linked by its full Release URL, never by a relative link.
  - `docs/superpowers/` holds each milestone's spec and plan, `docs/log/` the daily work log, and `docs/PROGRESS.md` the board.
- MS1's line, kept: "Rene Vincent Cosme built Lusot as a solo entry, with Claude Code (Anthropic) as a coding assistant." Added: no one else built, labelled or submitted it (M5).

### 14. Credits

MS1's table as it stands, except that its OpenStreetMap row is replaced by the map line below (the row must not call the tiles' cartography CC BY-SA 2.0), plus:
- the sample and demo photos: a credits file listing, for CC0 and CC BY photos, the title, author, licence and source link; for consented M9 photos, the donor's chosen credit line and "used with permission", with no source link; and, for each photo, the note that Lusot blurred it and drew outlines (CC BY's change notice; MS5's C617)
- the map: OpenStreetMap data under the Open Database License (ODbL), with the attribution "© OpenStreetMap contributors" linking to openstreetmap.org/copyright (MS5's C612)
- the Metro Manila boundary, with its source and licence (MS4-Q1)
- Leaflet (BSD-2-Clause), the fonts (OFL; the font row's copyright line is to check against the font repository before Nov 4), Lucide icons (ISC), and any other library MS5 adds
- the video's music, if any (CC0, C904)

### 15. Licence

MIT for Lusot's own code (MS7-Q4, Rene, Nov 1, 2026; M22). Third-party parts keep their own licences, and `meta-sam-parser` is under the SAM License (R52).

### Footer

"Not affiliated with MMDA." and the safety line, word for word.

---

## Checks before the final README is committed

- [ ] Every bracket is filled from its named source, or its line is cut
- [ ] MS7's copy check (its C819, with C922's changes) finds no fail in the file, and Rene has seen each review hit. The safety line appears word for word at the top and in the footer.
- [ ] The link check (`scripts/check_links.mjs`, C922) passes: no relative link to a missing file, and no link to the private development repository
- [ ] Every link works, checked on the private push and again once the repository is public (C902, C919)
- [ ] The plan-leak check and the account-ID scan are clean, and the file holds no email address
- [ ] Rene has approved the wording (M20)
