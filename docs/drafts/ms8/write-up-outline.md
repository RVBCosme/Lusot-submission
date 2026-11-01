# Write-up outline (draft)

> **Claude's draft, Oct 29, 2026, for MS8** ([spec](../../superpowers/specs/2026-10-29-ms8-submit-design.md): C901, C914, C915).
>
> - **Order:** the four criteria in the Official Rules' order, MS8-Q6's default: Impact, Use of Meta AI Tooling, Technical Depth & Execution, Demo. Each section opens with what the rules say that criterion covers, paraphrased, and answers it point by point.
> - **No sealed figures (Nov 2):** Rene parked Set A at about 2:4x AM, Nov 2, so there is no sealed run. The write-up follows MS8-Q4's "evaluation marked as pending" path: the method, the rules and the one command, with no figures. Development results never stand in for sealed ones (MS6).
> - **Placeholders:** brackets name what fills them. No number is invented (C901), and no bracket holds an evaluation figure.
> - **Copy rules:** only the 9 levels and MMDA's 3 classes; "at this spot"; never "safe"; no crossing advice; never a whole road or route; never "first"; never an accuracy claim of any kind: Lusot "can give a reading", or says it can't tell; lead with the whole system.
> - **Final text:** Claude writes it on Nov 4 from this outline and cuts it to the form's limits once Rene has seen the form (checklist O1). Rene approves it (M20).

## The tagline (about 100 characters)

Draft: "Flood depth at one spot, read against MMDA's gauge, with its evidence, on a live Metro Manila map."

## The summary (about 60 words)

Draft: "Lusot is a live flood map for Metro Manila. From a photo taken in the app, Lusot can give a reading at that spot on MMDA's gauge, with MMDA's passability class and its evidence drawn on the photo, or an honest 'can't tell'; readings become map pins. Three Meta models each do one job, and Ask Lusot answers Taglish questions from nearby pins. The scoring rules were fixed before any result was seen; the sealed evaluation is pending."

## The full write-up

### 1. Impact (30%)

*The rules ask about the project's real-world potential, who benefits and how much it matters, whether it could become something people use, and whether it fits one of the problem statements.*

- **The problem, with sources** (C901; the same facts as the README):
  - Two separate facts, never joined by "yet": in July 2025, MMDA identified 49 flood-prone areas in the National Capital Region; and on Jul 22, 2025, MMDA reported more than 500 flood incidents in Metro Manila in the last 24 hours (GMA News; C14's wording, with the day and the reporter named).
  - On Aug 9, 2026, GMA News carried two lists from different publishers, with different scopes: MMDA's 2:02 PM list named 4 flooded spots, and Quezon City's 2:20 PM list held 38 street entries, in the same gauge words.
  - MMDA's alert lists name the spots it reports, and crowd reports, such as MapaKalamidad's, come as a photo, a location and the reporter's own description; Lusot can give a reading at other spots too (the last clause is Lusot's own framing, not a sourced fact; the idea is plan §3's, in new words).
- **Who it serves** (plan §3's idea, in new words):
  - people on foot, and drivers of cars and other light vehicles, who want the depth at a spot before they make their own call
  - drivers of jeepneys, UV Express vans and deliveries, for the spots on their way
  - later, barangay responders

  Lusot gives a depth, never a decision.
- **Why MMDA's words:** MMDA's alerts already describe floods by gauge level and passability class. The alert lists in `docs/research/2026-10-26-alert-index.md` use those words. Lusot gives the same level and class at spots MMDA's alerts don't name, in English or Taglish.
- **Real people used it:** `[M17: five adults, at least two of whom drive or commute through floods; what they did; the one change it caused, with its commit]`. `[M28: the stakeholder's one-line quote and any written commitment, only with their consent; or leave this line out (C13)]`.
- **It could become something people use:**
  - `[If the public pin feed shipped: other flood maps, such as MapaKalamidad, could pull Lusot's live pins as GeoJSON, if they chose to; this is Lusot's proposal, and no map has agreed to it (plan §3, §12).]`
  - The plan for after the hackathon is MS10's decision: `[keep running or tear down]`.
- **The problem statement:** "Build for Your World". `[Rene, in one sentence of his own: why this problem is his.]`
- **What it is not:** reading flood depth from objects of known size is established research (FloodVision and others, `[cited from docs/research/]`). Lusot's contribution is MMDA's gauge and classes, Metro Manila's streets, Taglish, a live map and evaluation rules published before any result (plan §19). Never "first".

### 2. Use of Meta AI Tooling (25%)

*The rules ask how creatively the project uses Meta's AI tooling, whether it goes beyond a basic integration, and whether it surfaced unexpected capabilities.*

- **Three models, three jobs:**
  - `sam-3.1` masks the water, the wheels and the people, and later the faces and plates for the blur before storage
  - `muse-spark-1.3` names the landmarks and runs Ask Lusot's tool calls
  - `muse-voice-transcribe-1.0` transcribes spoken Taglish
- **Meta's documentation pairs the two models** (plan §19 cites it; Task 3 records the page): Muse Spark interprets a scene and SAM 3.1 supplies pixel-accurate masks. Lusot runs them in the other order, with SAM 3.1 first and Muse Spark reading numbered boxes drawn on its masks. Lusot draws a numbered box around each wheel and person, so Muse Spark answers about each one by number. It answers in strict structured output, as categories only, and code does all the measuring, so no model ever outputs inches.
- **Tool calling:** Muse Spark chooses the lookup, calls Ask Lusot's one tool, `get_reports`, and answers only from what it returns, citing the reports it used (plan §9). `[Tool details and one real test exchange, from the Ask Lusot spec and MS6's 10 typed and 10 spoken test questions.]`
- **Voice:** spoken Taglish goes through Muse Voice Transcribe, with Lusot's spot names as keywords, and the transcript shows with the answer, so a misheard place is easy to spot (plan §9). Muse Voice Transcribe lists code-switching among 25 evaluated languages; Lusot was tried on spoken Taglish questions (`[what MS6 ran, with no score: the pending path quotes no accuracy figure]`).
- **Gated and should-have uses, only if they shipped:**
  - `[The self-check: Muse Spark reviews each wheel outline from SAM 3.1 and sends a doubtful one back for one more try, marked on the overlay (decided Oct 31).]`
  - `[Clip mode: SAM 3.1's video tracking for the motion check.]`
- **What the build learned about the models** (honest findings, from the notes in `docs/research/` and the development reports, not invented; each is about a model's behaviour, never a measure of how well Lusot reads depth):
  - `[For example, from MS1's probe on Oct 28: SAM never put water on a wheel, but it found no water in 5 of 10 flood photos. D14, decided the day before, already sends an empty water mask on to Muse Spark, so an empty mask doesn't end the reading. Recheck both against the final development report before using them.]`
  - `[Findings from MS3a and MS3b's development runs.]`
- **Careful integration:**
  - faces are blurred before any photo goes to Meta (C20)
  - Lusot asks Meta not to store SAM's streams (MS3a)
  - retries only on 429, 500 and 503, with backoff and jitter
  - SAM is streamed, with a background fallback
  - prompts and schemas sit in versioned files
  - while the hackathon credits last, every call runs on them (D10). That wording holds after the lapse, whatever MS9-Q1 decides (MS9's N3).

### 3. Technical Depth & Execution (20%)

*The rules ask whether the engineering is sound and thoughtfully refined, and whether the project shows real craft.*

- **The pipeline** (plan §7, as built): the phone's quality check; on the server, the face blur first, then the quality check again; SAM's masks; the numbered boxes and Muse Spark's landmarks; the level rules; rim geometry behind a release gate; combining (the deepest believable reading wins, and readings more than one level apart mean a refusal); publishing, with blur before storage and the raw photo deleted. Three outcomes stay apart: processing failed, no flood seen, and can't tell.
- **Geometry with a release gate:** inches show only if geometry meets the targets in `eval/rules.md` §8 on the sealed run. The sealed run is pending, so inches stay off, and pins show the level and the landmark.
- **The evaluation, pending:** "The sealed evaluation is pending, so this write-up gives no results." Then the method, as the rules fix it:
  - the rules were written before any result was seen
  - the sealed set is to hold only photos that MMDA or a city posted itself, split by flood event, so no event sits on both sides (W18)
  - one run on the frozen pipeline; both configurations scored as the ablation, against a baseline row
  - every figure has its n and is called indicative
  - the per-photo results are committed without photos, and one command, `python eval/run_eval.py --from-saved`, rebuilds every table byte for byte
  - during development the build was checked on development photos with weak labels; those checks aren't results, and no figure from them is given
- **Engineering:**
  - one AWS SAM template and no console changes
  - an SQS queue with a dead-letter queue and an alarm
  - each report is claimed before any Meta call, so a duplicate message never pays twice (G2)
  - stop switches work without a redeploy
  - 7-day retention; no keys in the app
  - tests in CI on every push: `[counts]`
  - secret, plan-text and account-ID scans
- **Known weaknesses:** W1 to W28, each Done or explained in the README. What was dropped is named there, with the reason.

### 4. Demo (25%)

*The rules ask whether the project has a working, impressive demo, whether the product holds up live, and the quality of the demo video.*

- **What a judge can do now:**
  - open the live URL
  - run a sample through the real pipeline from anywhere, without adding pins
  - see the labelled demo pins on the map `[if MS5-Q2 leaves any]`
  - install the APK
  - read the scoring rules, and the one command that will rebuild the report once the sealed run is committed
- **Holding up live:** the stack stays up through the finals, with alarms, budget alerts and stop switches watched (MS9). Photo to pin takes about `[median from latency.jsonl]` s, measured, never promised (C631).
- **The video:** 2:40, with English captions throughout, and every photo credited. Its first cut was tested on three people who hadn't seen Lusot (M23).

### The bonus entry (M33), only if the submission form offers the field

About 100 words for the form's bonus entry (C915). The "Best agentic use case" award isn't in the Official Rules or on the event page (Nov 1); its only source is the kickoff (plan §24, M33). So Rene enters this paragraph only if the form offers that field (he checks the form, as O1 does). The write-up's body, the README and the video name only the categories the rules name, or "a bonus category", and never a prize amount. Draft shape:

"Ask Lusot is a small agent with one job: answer a flood question from evidence only. Muse Spark reads a typed Taglish question, or the transcript of a spoken one, chooses the lookup, calls Lusot's `get_reports` tool, and builds its answer from the reports that come back alone, naming each: the deepest from the past 3 hours within 300 m, how many there are, and how old. When none come back, it says so. `[If the self-check shipped: in the pipeline, Muse Spark also checks SAM 3.1's wheel outlines and sends a bad one back for one retry.]` `[What was tried: MS6's typed and spoken test questions, with no score: the pending path quotes no accuracy figure.]`"

### Closing lines

- "Not affiliated with MMDA."
- The safety line, word for word: "Lusot estimates depth at one spot. It is not advice to cross. Follow MMDA and local advisories."

## Where each claim comes from

| Claim | Source to cite |
|---|---|
| 49 flood-prone areas, identified in July 2025 | ABS-CBN, checked in `docs/research/2026-10-27-plan-update-check.md` |
| More than 500 incidents in the last 24 hours, reported Jul 22, 2025 | GMA News, Jul 22, 2025, in the same note (C14) |
| Aug 9, 2026: two lists, MMDA's 4 spots and Quezon City's 38 street entries | The 2:02 PM and 2:20 PM lists, checked in `docs/research/2026-10-27-plan-update-check.md` §5, and the GMA News page that carries them. Task 3 records that page. The alert index's Aug 9 lists are the morning ones. |
| Prior work: FloodVision and others | `docs/research/2026-10-27-plan-update-check.md` (research numbers). No MDPI figure is quoted (C14). |
| MMDA's alerts use gauge levels and classes | The alert lists in `docs/research/2026-10-26-alert-index.md` |
| Crowd reports, such as MapaKalamidad's, come as a photo, a location and the reporter's own description | A source that Task 3 records, such as Philstar.com's report of Jan 30, 2024 (plan §3's Table 2 idea) |
| Meta's documentation pairs Muse Spark (interprets a scene) with SAM 3.1 (masks); Lusot runs them in the other order | Meta's documentation page, which Task 3 records (plan §19 cites it) |
| Tire and knee are words in MMDA's flood level names | Interaksyon (Philstar.com), Sep 4, 2024, which Task 3 records (plan §26 lists one) |
| Every result | None: the sealed evaluation is pending (MS8-Q4), and no development figure is used |
| Photo to pin time | `eval/results/latency.jsonl` |
| The user test and the change | Rene's M17 notes (outside the repo) and the change's commit |
| Ask Lusot's behaviour | The Ask Lusot spec and MS6's test questions |
| The probe's findings | `docs/research/2026-10-28-ms1-probe-results.md` and later notes |
