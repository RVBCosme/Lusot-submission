# Video script outline (draft)

> **Claude's draft, Oct 29, 2026, for MS8** ([spec](../../superpowers/specs/2026-10-29-ms8-submit-design.md): C904 to C911 and C918). It follows plan Table 19's scenes and time budget, with C905's nine departures.
>
> - Rene records the footage and his own voice-over (M23). The cut follows MS8-Q8. Rene checks every caption (M30) and every Taglish line (M20).
> - **Target 2:40, never over 3:00.** The 20 s of buffer is the plan's, because the finals judges watch the video live.
> - Every voice-over line below is a draft for Rene to say in his own words. Every number is `[from the evaluation report]` until the sealed run is committed (C901).

## Rules for every frame and every line

- **Material** (C904):
  - Allowed: screen and phone recordings of Lusot as built; consented footage (M9, M29) whose written consent covers the video, the X post and the organizers' licence; the CC0 and CC BY photos marked `demo_use ok` and not share-alike, shown only as Lusot's blurred output, with the credit line in frame; Rene's own voice; one CC0 music track or none. CC0 narrows M23's "royalty-free" as Claude's call, and Rene can widen it (C904).
  - Never: CC BY-SA, Set A or A-neg photos, news photos or footage, any social-media post or screenshot, MMDA's logo or the look of its advisories, or anyone filmed without written consent.
- **Dates and credits:** every photo or clip that isn't Rene's own capture shows its date, its place and its credit while it is on screen. A 2009 photo never sits under a 2025 statistic as if it were from 2025.
- **Copy rules:**
  - only the 9 levels and MMDA's 3 classes, always "at this spot"
  - never "safe" in any form ("safer", "safest", "safely", "safety", "unsafe"), and no word that contains "ligtas" (MS7's C819 list)
  - no crossing advice: nothing like "you can cross" or "go ahead"
  - never a whole road or route, never "first", never "MMDA's 9 levels"
  - lead with the whole system, not "upload a photo, get an answer"
- **No speed claim unless measured** (C631). Where a wait is cut, an on-screen label gives that run's real seconds, such as "38 s later".
- **Nothing private on screen** (C906):
  - a clean browser profile, the deployed site only, and phones with notifications silenced
  - no console, terminal, editor, email, key, account ID, report id, home location or unconsented face
  - Claude checks a frame at every scene change and every 5 s of the final cut
- **The safety line** (C907): app frames carry it already. Every other card carries it in small type at the bottom. The closing card shows it full size.
- **No work from before kickoff on screen:** not the plan, not the staging folder, nothing dated before Oct 27 (G1).

## Shot list and beats

Times follow plan Table 19. The voice-over word budgets assume about 2.2 words a second, so the captions stay readable.

### Scene 1, 0:00 to 0:15: built during the event; the problem

| Part | On screen (source) | Voice-over beat (draft) | Captions and on-screen text |
|---|---|---|---|
| 0:00 to 0:05 | A plain card with the opening line (C909), on screen in full: "All of Lusot's code, and everything this video shows of it, was built during the hackathon, Oct 27 to Nov 4, 2026 (Manila time)." Under it: "Photos are credited on screen." The safety line in small type at the bottom. | A shorter spoken version, about 11 words: "Everything you'll see of Lusot was built during this hackathon." | The card's own text; the voice-over captioned |
| 0:05 to 0:15 | A flooded Metro Manila street: consented footage (M9), or a CC0 or CC BY `demo_use ok` photo as Lusot's blurred output, with its place, date and credit in the corner. Two lines appear over it in turn, as two separate facts: "In July 2025, MMDA identified 49 flood-prone areas in the National Capital Region." and "On Jul 22, 2025, MMDA reported more than 500 flood incidents in Metro Manila in the last 24 hours." A small sources line under them: "ABS-CBN News, Jul 14, 2025 · GMA News, Jul 22, 2025". | About 15 words, so they don't compete with the figures on screen: "How deep is the water at this spot? Lusot reads it against MMDA's gauge." | The second line is C14's wording, with the day named. Both sources are recorded in `docs/research/` first (C901). |

**Proves:** the work is new (G1), and the problem is real and measured (Impact).

### Scene 2, 0:15 to 0:45: from a photo to a pin

| Part | On screen (source) | Voice-over beat (draft) | Captions and on-screen text |
|---|---|---|---|
| 0:15 to 0:25 | Phone footage: an adult (Rene, or a consenting adult) stands on a dry curb and takes a photo in Lusot. Cut to the phone's own screen recording: the camera, the GPS fix, Send. | About 55 words across the scene: "From a dry spot, a photo goes to Lusot. Faces are blurred before anything else. Meta's SAM 3.1 outlines the water, the wheels and the people. Muse Spark reads where the water line falls on each one, and code turns that into a level and MMDA's passability class, at this spot." Then one of two endings, set by Rene's MS5-Q3 answer. Under its current default, every published pin shows its photo and overlay while it is visible: "Every pin shows its work." Under the narrower option: "Your result shows its work." | The voice-over; the elapsed-time label at the cut (C905, item 2) |
| 0:25 to 0:30 | The waiting screen, then a cut with the label "`[n]` s later", giving that run's real seconds | (continues) | |
| 0:30 to 0:45 | The overlay draws itself: the water first, then each wheel or person with its reading (a reference the pipeline dropped shows its reason, never a level), then the rim and waterline if MS3b's geometry shipped (MS5's C615). Then the level line ("`[Level]` at this spot (MMDA level)."), the landmark line and the class line. The pin appears on the map. | (continues) | The result card's text is in English on screen, so no extra caption is needed |

**Which footage:**
- **(A) If it rains (M29):**
  - A real flooded street, filmed from a dry curb.
  - A ruler held from the curb then checks the level (plan §18, §25), shown as a check on the reading, never as a decision about crossing (C905, item 9).
  - No one crosses on Lusot's word, and no one is filmed in the water.
- **(B) If it doesn't (R6's labelled fallback):**
  - A real puddle beside a parked car, captured live in the app, with an on-screen label: "A real puddle, not a flood."
  - The reading is whatever the pipeline says, even "no flood seen". Under MS4's second draft (C506), that stays on his phone and isn't pinned.
- **Never:** staged water, a printed photo, or a sample passed off as a live capture.
- **Who films:** if Rene is in the shot, a tripod or a phone stand films him. Otherwise he films a consenting adult, as M29 does. No one else operates the camera (C906; checklist G9).

A capture inside Metro Manila becomes a real public pin for 3 hours, so it is filmed on a public street, not at home (MS5's C630).

**Proves:** it works end to end, and it shows its work (Demo, Technical depth).

### Scene 3, 0:45 to 1:00: the live map (clip mode's slot)

| Variant | On screen (source) | Voice-over beat (draft) |
|---|---|---|
| **Default** (MS5-Q5 (a), clip mode dropped) | The map with labelled demo pins, then one pin's detail: its Demo badge, date, place and credit line (MS5's C618). The OpenStreetMap attribution stays in frame. | About 30 words: "Live pins fade after an hour and leave the map after three. Demo pins carry a label and stay put, and anyone, anywhere, can run a sample through the live pipeline." |
| **No demo pins** (MS5-Q2) | Tested, then a sample, then **Run this sample**, then the result card with its Sample badge and credit line: the remote judge's path | The same beat, ending on the sample |
| **Clip mode shipped** (MS5-Q5 (b)) | Plan Table 19's clip scene: a passing jeepney's wheels tracked by SAM 3.1 across frames, set aside by the motion check, and the parked car beside it measured | About 30 words on SAM 3.1's video tracking and the motion check |

**Proves:** the live map is real and checkable from anywhere (Demo, Impact), and with clip mode, Meta tooling beyond a basic call.

### Scene 4, 1:00 to 1:10: it knows its limits

| On screen (source) | Voice-over beat (draft) | Captions |
|---|---|---|
| A real photo taken in the dark, sent from the app. The refusal appears with D19's line: "I can't tell from this photo. Retake it from a dry spot with a parked car's wheel or a person standing still in view. Don't step into the water or the road." | About 18 words: "When a photo can't support a reading, Lusot says so, and says how to retake it from a dry spot." | The voice-over |

**Proves:** a refusal beats a guess (Technical depth, Demo).

### Scene 5, 1:10 to 1:30: Ask Lusot, by voice

| Part | On screen (source) | Voice-over beat (draft) | Captions |
|---|---|---|---|
| 1:10 to 1:17 | Rene's phone: Ask Lusot, the microphone, and Rene asking in Taglish. He asks how deep it is at a spot that has real pins nearby, and says he drives a sedan. This replaces plan Table 19's question about getting through (C905, item 5). | No voice-over while he asks | English caption of the question, in Rene's words (M30, M20). Draft: "How deep is it at `[spot]`? I drive a sedan." |
| 1:17 to 1:30 | The transcript appears, then the answer: the deepest report nearby from the last 3 hours, with its level at that spot, MMDA's class, how many reports there are and how old, citing its pins. Demo pins are marked "(demo)". | About 30 words: "Muse Voice Transcribe turns the question into text. Muse Spark decides what to look up, calls Lusot's report tool, and answers from the reports it found, naming each one." | The answer captioned in English if it is in Taglish |

**The answer must stay in MMDA's terms.** It reports spots, levels, classes and ages. It never says go or don't go, and the voice-over adds no advice. MMDA's class for light vehicles is MMDA's own statement, not Lusot's verdict on his car. A question about depth keeps the class line from reading as a yes or a no.

**Fallback:** typed Ask Lusot, if voice isn't solid (plan Table 18; N4).

**Proves:** Meta tooling (voice, tool calling, Taglish), and the bonus entry (M33, only if the submission form offers it). Nothing on screen or in the voice-over names that award or a prize amount.

### Scene 6, 1:30 to 1:55: the system and its numbers

| Part | On screen (source) | Voice-over beat (draft) |
|---|---|---|
| 1:30 to 1:38 | A card: three Meta models, one job each: `sam-3.1` for masks, `muse-spark-1.3` for landmarks and tool calls, `muse-voice-transcribe-1.0` for spoken Taglish | About 55 words across the scene: "Three Meta models, one job each. Code does the measuring: the models never output inches. The scoring rules were fixed before any result existed. `[n]` government-posted photos, split by flood event, stayed sealed until the frozen pipeline ran on them `[once, or once more with both results disclosed, if rules §10's rerun happened]`. `[One sentence with the headline figures and their n, from the report.]` One command rebuilds every table." The rules' first drafts date from Oct 26, so the line never says when they were written (C909). |
| 1:38 to 1:45 | The new figure of the wheel landmarks and rim geometry (C920), not the plan's Figure 3 | (continues) |
| 1:45 to 1:55 | A numbers card from `summary.json` only: underestimation, passability agreement and coverage, each as "k of n"; Set B's median error with its n; the release gate's decision. Small type: "Agreement with posted labels · indicative". Then one line naming any should-have that was dropped (C905, item 8). | (continues) |

**Proves:** technical depth and honest error.

### Scene 7, 1:55 to 2:20: real people used it

| On screen (source) | Voice-over beat (draft) |
|---|---|
| **Under MS8-Q5's default (a):** footage from M17 of the testers who agreed in writing, framed on their hands and the screen. A face or a voice appears only if that tester ticked it on the form. Then the one change their feedback caused, as before-and-after screens with the change's commit. Then the stakeholder's quote (M28), if one came, as text, with a name or role only if they agreed to be named. **Under (b):** the same scene as text cards. | About 50 words: "`[Five adults tried Lusot, at least two of whom drive or commute through floods. What they did, in one sentence.]` `[What changed because of them.]` `[The stakeholder's line, if given, and their group's commitment, if any.]`" |

If no quote came, the scene shows the user test only (C13). No tester appears on camera without written consent that covers the video, the X post and the organizers' licence.

**Proves:** Impact: real people used it.

### Scene 8, 2:20 to 2:40: privacy, the pitch line, the close

| Part | On screen (source) | Voice-over beat (draft) |
|---|---|---|
| 2:20 to 2:28 | A privacy card, taken from the privacy policy as Rene approves it (M21). Draft: "Faces are blurred before Meta receives a photo. The original is deleted after analysis. No accounts, no names." | Rene reads the card. |
| 2:28 to 2:35 | The pitch line, in Rene's words. Draft, about 16 words, paraphrasing plan §1's line: "Lusot reads a flood against tires and knees, the landmarks that give MMDA's flood levels their names." Tire and knee are words in MMDA's level names, not marks on a gauge; the source (Interaksyon (Philstar), Sep 4, 2024) is recorded in Task 3, and nothing is claimed about how MMDA's staff work. | Rene says it. |
| 2:35 to 2:40 | The closing card: Lusot, the live URL, the submission repository's URL, https://github.com/RVBCosme/Lusot-submission (MS8-Q2: (a), Rene, Nov 1, 2026; fixed now because the card is burned in), the safety line full size, "Not affiliated with MMDA.", and the music credit if there is music | Silence, or the music's end |

**Proves:** a memorable close that claims no more than the product does.

**Voice-over total:** about 300 words, about 1.9 a second on average, and no scene above about 2.3.

## Captions (M30, C908)

- English captions run through the whole video: every voice-over line and every Taglish line. They are burned into the picture, and an SRT file goes with the upload.
- **Style:** sentence case, at most 2 lines of about 42 characters, each on screen for 1 to 6 s, in white on a dark box, in the band below the phone frame. They never cover the app's safety line, the OpenStreetMap attribution or a credit line.
- **Taglish lines:** the caption gives the English meaning, which Rene writes or checks (M20). The app is recorded in English except the Ask scene, so the screens need no extra captions.
- **Order of work:** Claude drafts the SRT from the final script and the cut's timings. Rene checks the translation and the timing on a full watch with the sound off.
- After his check, the SRT may be committed under `docs/media/`, since it holds only the script.

## Production notes

- **Footage and files:** everything goes in `LUSOT_DATA_DIR\video\`, outside the repo: raw footage, the edit list, the cards, the SRT drafts and the cuts.
- **Screen captures by Claude:** the deployed web app at a phone's size, in a clean Chromium profile with Playwright, running samples only, so nothing pins. Each capture costs one sample run, about $0.034 (budget: spec §3).
- **Phone captures by Rene:** the phone's own screen recorder, with notifications off.
- **Framing:** 1920 × 1080 at 30 fps. Phone screens sit centred on a plain background, and the captions sit in the band below them.
- **Cards:** Claude makes them as SVG, then PNG at 1920 × 1080, in the app's fonts and colours (MS5-Q1's direction). Each carries the safety line in small type.
- **Audio:**
  - Rene's voice-over is recorded in a quiet room, one take per scene, so a scene can be redone alone.
  - The CC0 track, if any, sits low under the voice-over, and stops during the Ask scene's question.
- **The first-cut test** (C910): three adults who haven't seen Lusot and weren't among M17's testers each watch the cut once, then say what they remember. Anything none of them recalls is cut or reworked.
- **The X cut** (MS8-Q7 (a)): at most 2:15. It shortens scene 6 to one card (about 10 s saved), scene 7 to the change and the quote (about 10 s saved), and scene 2's waiting part (about 5 s saved).
- **The backup recording** (spec §4, item 3): one uncut screen recording of the live flow on the deployed site:
  - the map, then a sample run from Tested, then the result, then a pin's detail
  - Ask Lusot, typed
  - the Tested page's figures

  It is used only if the live demo fails in the final round (M25), and it follows the same frame rules.

## The video's description (on the host)

- **Title (draft):** "Lusot: flood depth at one spot, in MMDA's words (Meta Global AI Developer Hackathon)"
- **Text:**
  - one paragraph on what Lusot is, leading with the system
  - "All of Lusot's code, and everything this video shows of it, was built during the hackathon, Oct 27 to Nov 4, 2026 (Manila time)."
  - the live URL and the repository's URL
  - the safety line, word for word
  - "Not affiliated with MMDA."
  - a credit line for every photo shown (for CC0 and CC BY photos, the title, author, licence and source link; for consented M9 photos, the donor's chosen credit line and "used with permission", with no source link; and, for each photo, the note that Lusot blurred it and drew outlines), and for the music if any
  - "English captions throughout."

## The X post (M26, C918)

Rene posts it by hand from his own account. Draft (X counts each link as 23 characters, so this comes to about 250 of the 280):

> Lusot: a live Metro Manila flood map that reads depth at street spots against MMDA's gauge, with the evidence shown.
>
> Lusot estimates depth at one spot. It is not advice to cross. Follow MMDA and local advisories.
>
> `[live URL]` https://github.com/RVBCosme/Lusot-submission

- Add any tag or mention the guide requires (Rene confirms, G6).
- The video follows MS8-Q7. After posting, the post's link goes into the submission form.
- The copy rules apply to any reply he adds, too.
