# MS8 Submit: spec

- **Date:** Oct 29, 2026 (Manila), written from 12:12 AM
- **Status:** Claude's draft; Rene approves. Written overnight without a live conversation, under Rene's instruction (D7, D15). Claude proceeds on the calls in §6 and the defaults in §8 until he answers. Nothing in MS8 becomes public unless Rene does it himself (§5).
- **Checked before commit:**
  - a builder check (§11; its three questions became MS8-Q2, MS8-Q4 and MS8-Q5)
  - one independent accuracy review of this spec, the plan and the four drafts (Opus 5.5 at max, finished about 1:20 AM): 17 Important and many Minor findings, all fixed (§12)
  - the tracker's input on the author address (MS8-Q1)
- **Implements:**
  - design §8's MS8 row, design §7's R7 (as MS8-Q1), D9 and D11
  - plan §2 (rules), §18 (the submission checklist and Table 19), §19 (the demo and judging practices) and §24's M23, M24, M26, M30 and M33
- **Builds on** (read, not changed):
  - **the MS5 spec**, committed on `ms5-app-specs` (latest `5f01188`, aligned with MS4's second draft): C601, C608, C609, C610, C614, C615, C616, C617, C618, C627, C631, C632, C634; MS5-Q2, MS5-Q3 and MS5-Q5. Also MS5's plan, which is uncommitted: its `REPORT_URL` (Task 15) and its user-test kit (Task 22).
  - **MS4's second draft**, uncommitted in `lusot-wt\ms4`: C503, C504 (pins now carry the report id), C506, C510, C512, C515
  - **the MS7 spec** on `ms7-harden-specs` (`4554d74`): C813, C819, C821, C827, C829; MS7-Q8. Also MS7's plan, which is uncommitted: Tasks 7a and 9. MS8 reuses MS7's scans and copy rules (C922).
  - the MS6 spec (on `w4-independent`): C401, C409, C421, C422; MS6E-Q4
  - the consent notice and privacy policy drafts (`docs/drafts/` on `w4-independent`)
  - the research notes behind every public claim (`docs/research/`), and C14's corrected wording
  - the Official Rules and Event Waiver, read in the event page's raw HTML at 11:57 PM, Oct 28
- **Drafts:** [README outline](../../drafts/ms8/readme-outline.md), [video script outline](../../drafts/ms8/video-script-outline.md), [write-up outline](../../drafts/ms8/write-up-outline.md), [submission checklist](../../drafts/ms8/submission-checklist.md). **Plan:** [MS8 plan](../plans/2026-10-29-ms8-submit.md).

## 1. Intent

MS8 turns a working, evaluated Lusot into an entry that judges can score in minutes and check in depth.

- **A judge with 60 seconds sees the whole system,** not a photo analyzer: the live map, one sample through the real pipeline, the video, and the single command that rebuilds every table of the evaluation.
- **Every claim can be checked.** Each number comes from the committed evaluation report, each fact from a cited source, and the repository's history shows when each part was written.
- **Nothing leaks and nothing breaks a rule.** No key, account ID, email address, plan text, sealed or Set A photo, CC BY-SA photo or social-media content goes public, and every public step is Rene's.

## 2. Goals, non-goals, anti-goals

**Goals**
1. The judges' README, the video (2:40, English captions throughout) and the write-up, finished on Nov 4 from the drafts here.
2. The submission repository (D9), built from `main`'s history under MS8-Q1, with the whole history scanned before anything goes public.
3. The submission on the Cerebral Valley platform by Nov 4, 10:00 PM Manila: Indie track, solo, also entered for the Best agentic use case prize (M33), with the X post's link added (M26).

**Non-goals**
- Anything that changes how depth is measured (design §8's freeze), and any app, API or pipeline change. MS8 changes the README, docs and media only.
- New features, including anything dropped earlier (design §8, "When we slip").
- Keeping the demo live through judging, and the gallery link (MS9: M25, M27).

**Anti-goals** (failures even if the entry goes in)
- A number that the one command doesn't rebuild, a figure without its n, or Set A results called accuracy (MS6).
- In the README, video, captions, write-up or X post: the word "safe" in any form, crossing advice, a whole road or route, a level outside the 9 levels or a class outside MMDA's 3, or "MMDA's 9 levels".
- Calling Lusot the first, or pitching it as a photo analyzer (CLAUDE.md; plan §19).
- A "built during the event" claim that the history or the files' own dates contradict (MS8-Q3).
- A video frame with work from before kickoff, a console, a key, an account ID, an email address, a report id, an unblurred face, a CC BY-SA photo, a Set A or news photo, or social-media content.
- A speed claim, such as "under 10 seconds", that no measurement shows (MS5's C631).
- Anything made public that Rene didn't do himself.

## 3. Constraints

- **Dates (Manila):**
  - our target: Nov 4, 10:00 PM
  - the hard cutoff: Nov 5, 10:00 AM. The event page's Key Dates say "Nov 4: Project submissions due by 9:00 PM ET", and the portal stores Nov 5, 02:00 UTC.
  - the finals: Nov 10, 1:00 AM
  - answers needed before then:
    - MS8-Q5 by Oct 31 (MS5's test kit)
    - MS8-Q2 by Nov 2 (the repository exists)
    - MS8-Q1 (R7, design §7), MS8-Q3, MS8-Q4, MS8-Q8 and MS8-Q9 by Nov 3
    - MS8-Q6 and MS8-Q7 by Nov 4

  The rules say dates may change, so the event page is rechecked (C916).
- **The rules.** The hackathon's rules override the plan and the design. The [submission checklist](../../drafts/ms8/submission-checklist.md) lists each requirement with its source. These shape MS8:
  - From the **Official Rules** (public):
    - one track per project
    - the representative submits and names every team member (solo: Rene alone)
    - the submission is original work, owned outright, and infringes no one's rights; open source only within its licences
    - the organizers get a perpetual licence to the submission, marketing included
    - the four criteria and their weights
    - bonus prizes "may include" a community vote award and a most viral award
  - From the **participant guide, the Discord and the kickoff stream**, known only through plan §2 and §24: new work only, a public repository, a 3-minute video and the X-post rule (the guide and Discord), and the agentic prize (the kickoff stream, M33). These wait for Rene to confirm (the checklist's "Rene confirms" list).
- **Product copy** (CLAUDE.md; plan §9, §19):
  - only the 9 levels and MMDA's 3 classes, always "at this spot"
  - never "safe", no crossing advice, never "first"
  - the exact safety line: "Lusot estimates depth at one spot. It is not advice to cross. Follow MMDA and local advisories."
  - "Not affiliated with MMDA." and no MMDA logo
  - lead with the whole system
- **Material** (CLAUDE.md, M23, Rene's 8:26 PM decision on Oct 28, which covers photos): consented footage, the credited CC0 and CC BY photos marked `demo_use ok`, and Rene's own voice-over. For music, C904 narrows M23's "royalty-free" to CC0 or none, as Claude's call.
- **Data:** never open or list a `sealed` folder; never open a Set A or A-neg photo.
- **Plan text** stays out of every repo (C4): it is cited by section and table and paraphrased, never copied. The plan's figures are redrawn, not copied (C905, C920).
- **Budget:** MS8's Meta spend stays under about $1. That covers sample runs for screen captures, the GIF and the demo-ready check, at about $0.034 a photo. No paid service is added. X Premium, if Rene wants it (MS8-Q7), is his own choice, outside the project budget.

## 4. What MS8 delivers

| # | Deliverable | Draft | Final made by | Final by (Manila) |
|---|---|---|---|---|
| 1 | The judges' README | README outline | Claude writes; Rene approves its wording (M20) | Nov 4 |
| 2 | The video: 2:40, English captions burned in, plus an SRT file | video script outline | Rene records the footage and voice-over (M23); the cut follows MS8-Q8; Rene checks the captions (M30) | first cut Nov 3, final Nov 4 |
| 3 | A backup recording of the live flow, uncut, for the live final round (plan §19, M25) | video script outline | Rene records it | Nov 3 to 4 |
| 4 | The write-up (a tagline, a summary and the full text) and the agentic prize paragraph (M33) | write-up outline | Claude writes; Rene approves | Nov 4 |
| 5 | The X post's text (M26) | video script outline | Claude drafts it; Rene posts it by hand | Nov 4 |
| 6 | The README's media: a GIF of the overlay drawing itself, a new figure of the wheel landmarks and rim geometry, and an architecture diagram | README outline | Claude (C920) | Nov 3 |
| 7 | The submission repository's export, scanned | the plan | Claude builds and scans it (C902, C903); Rene creates the repository by Nov 2 (MS8-Q2), pushes or approves the push, and makes it public | Nov 4 |
| 8 | The APK for judges, on a GitHub Release with its SHA-256 | the plan | Rene publishes it (C917) | Nov 4 |
| 9 | The submission (M24), with the bonus entry (M33) and the X link (M26) | submission checklist | Rene | Nov 4, 10:00 PM |
| 10 | The records: PROGRESS.md ticks with evidence, the log, any new decisions | the plan | Claude | Nov 4 to 5 |

## 5. Gates: Rene's steps

These always wait for Rene (CLAUDE.md; D7, D11). Claude prepares each one and never does it:
1. **Making code public:**
   - creating the submission repository
   - pushing to it. Only an export that has passed C903's scan is ever pushed: by Rene, or by Claude on his written OK while the repository is still private (MS8-Q2).
   - making it public
   - publishing the GitHub Release with the APK
2. **The X post,** from his own account, by hand. CLAUDE.md bars automated access to X.
3. **The submission** on the platform: the form, the track, the team, the bonus entry and the X link.
4. **Any spend beyond the budget alerts:** Meta's $100 monthly alert and AWS's $5 budget.

Only Rene can also:
- record his voice-over and the phone footage, and show the first cut to three people (M23)
- check the captions and every Taglish line (M30, M20)
- approve the README, the write-up, the video and the X post
- upload the video to his own account
- choose the repository licence (M22, an MS7 item)
- under MS8-Q1 (b), change the repository's commit address to his no-reply one, then turn on GitHub's two email-privacy settings, in that order
- approve, on the day, any move of the submission past Nov 4, 10:00 PM (MS8-Q4's buffer), even under D7
- answer §8's questions
- confirm the checklist's "Rene confirms" items in the participant guide and the Discord

## 6. Calls (Claude's, C900 onward)

| # | Call | Why |
|---|---|---|
| C900 | **MS8's boundary and timing.** MS8 writes docs and media and builds the export. It changes no app, API or pipeline code. It starts after MS7's checks, except for work that changes nothing public, which the plan runs earlier:
- these drafts
- the scan additions and the link check (Tasks 1 and 2)
- the claim sources and the export rehearsal (Tasks 3 and 4)
- the event-page rechecks (Task 5)
- the README's media (Task 6)
- the video's preparation, recording, first cut and three-viewer test (Tasks 7 to 10)

The final README, write-up and captions are written on Nov 4 from the committed report. | Design §8: MS8 follows MS7, and the freeze holds after the sealed run. Early drafts let Rene review the shape before Nov 4. |
| C901 | **Every number has a source a judge can follow.**<ul><li>**Results** come only from `eval/results/report/` (`summary.json` and `report.md`), which the one command rebuilds. Each figure carries its n and the word "indicative", and is called agreement with the labels MMDA and the cities posted, never accuracy.</li><li>**Facts about the problem** come only from the checked notes in `docs/research/`, in C14's corrected wording: "more than 500 flood incidents within 24 hours", not "the July 2025 monsoon".</li><li>**Speed** comes only from `eval/results/latency.jsonl` (C416, C631).</li></ul>Until those exist, the drafts hold placeholders such as `[from the evaluation report]`. | Design §3 (goal 4); MS6's anti-goal; MS5's C616. |
| C902 | **The export: scanned before every push, and private until Rene's step.**<ol><li>By Nov 2, Rene creates the submission repository, empty (no README, licence or `.gitignore` from GitHub's form) and private, under a name other than the development repository's (MS8-Q2).</li><li>Claude clones `main` alone, with the freeze tag or tags named one by one (MS6 §4.6), into a scratch folder outside every repo. Each tag must lie on `main`'s line (`git merge-base --is-ancestor`), so the scan of `main` covers it. Claude applies MS8-Q1's choice there and runs C903's scan. The pushes then name `main` and those tags, never `--tags`.</li><li>**Only an export that has passed the scan is ever pushed,** by Rene or by Claude on his written OK. A rehearsal export may go first, on Nov 3 or early on Nov 4 once MS8's scan additions are in (plan Task 4, Step 8), to try CI on the new repository. Both the rehearsal and the final export must make the same `Claude-Session` choice (MS8-Q1), since dropping those lines changes every hash after them. The final export on Nov 4 then lands as a fast-forward, because filter-repo rewrites the same commits to the same hashes. A push that would need `--force` means Rene deletes the repository and creates it again, empty.</li><li>While it is still private, Claude checks that CI passes, that the README renders with working links, and that a fresh clone runs the one command with exit 0.</li><li>Then Rene makes it public.</li></ol> | D9's separate, clean repository, which only `main` and its tags reach. GitHub can keep pushed commits reachable by their hash after a force push, so nothing unscanned may ever reach the repository, not even while it is private. A private push lets every check run before anything is public, and leaves the public act with Rene. |
| C903 | **The whole-history scan before any push.** It runs on exactly what will be pushed: every commit, every blob in history, and every author, committer and tagger line, not just the latest files. It uses MS7's tools with MS8's additions (C922). It checks for:<ul><li>**secrets:** gitleaks in git mode</li><li>**account details:** 12-digit runs, with the account-ID scan's exclusions, and the numbers in plan §24, read at run time from the text copy outside the repo. On the export run, a missing plan file fails the scan; it doesn't skip the rule.</li><li>**plan text:** the plan-leak check's line rule, over every blob in history</li><li>**email addresses:** in blobs and in commit messages. Allowed: no-reply addresses, and notices that a licence requires word for word (R11), allow-listed by their exact blob.</li><li>**links:** AWS's and Meta's console and sign-in links</li><li>**files that must never be committed:** env files other than `.env.example`, `samconfig.toml`, keystores, APKs and archives. Also any path with a part named `sealed`, which is never opened and is reported by commit and count only, since its file names could say what it holds.</li><li>**images:** any image outside an allow-list of path globs: the credited test fixtures, the Android template's icons, the app's own icons (MS5's `app/public/`), and the README's media (`docs/media/`)</li><li>**identities:** author, committer and tagger addresses, counted by domain</li></ul>It also counts the `Claude-Session` trailers (MS8-Q1). It prints commits, paths and counts, never the matched text. Any other hit stops the push until it is fixed, or until it is allow-listed by its exact blob with a written reason. Rene reads those reasons before the push. MS8-Q1 and MS7-Q8 decide the rest.<br><br>**Dry run** (Claude, read-only, 12:10 AM, Oct 29: 175 commits on every ref of the development repo):<ul><li>No plan §24 number, console link or never-commit file in any blob.</li><li>Email-like strings appear only in the YuNet licence (R11) and in Claude's no-reply co-author lines.</li><li>One 12-digit run sits in three older versions of an MS3a test file, on `ms3a-landmark-core`, so it enters `main`'s history when MS3a merges. It is the masking test's literal, built at run time since `baa69a0`, and it matches no §24 number.</li><li>**Every author and committer field (350 of them) carries Rene's personal email** (MS8-Q1).</li></ul> | R51 sent the history scan to R7. Publishing a history publishes every old blob and every commit's metadata. The working-tree checks can't see either. |
| C904 | **Video material and music.**<ul><li>**Allowed:** screen and phone recordings of Lusot as built; consented footage (M9, M29) whose written consent covers the video, the X post and the organizers' licence (C18); the CC0 and CC BY photos marked `demo_use ok` and not share-alike (MS5's C617), shown only as Lusot's blurred output, with the credit line in frame and in the video description; Rene's own voice.</li><li>**Music:** one CC0 track or none, with its source page recorded. This narrows M23's "royalty-free". Rene can widen it to any track whose licence lets the organizers reuse the video.</li><li>**Never:** CC BY-SA; Set A, A-neg, or news photos and footage; any social-media post or screenshot; MMDA's logo or the look of its advisories; anyone filmed without written consent.</li></ul> | CLAUDE.md and Rene's 8:26 PM decision. The Official Rules let the organizers use the submission, video included, for marketing. A typical stock-music licence can't pass that on; CC0 can. |
| C905 | **The storyboard keeps plan Table 19's scenes and time budget, with nine departures:**<ol><li>The opening statistic uses C14's wording, with its sources on screen.</li><li>No "under 10 seconds" claim unless measured. Where a wait is cut, a label shows the real seconds (C631).</li><li>**The clip scene:** under MS5-Q5's default (clip mode dropped), its 15 s show the map with labelled demo pins. With no demo pins (MS5-Q2), they show a sample run from the Tested page, which is the remote judge's path.</li><li>**The capture scene:** a real flood if it rains (M29, filmed from a dry curb). Otherwise R6's labelled fallback: a real puddle beside a parked car. Staged footage is never passed off as a flood.</li><li>**The Ask scene** asks about depth, never about passing. Instead of Table 19's question about a sedan getting through, Rene asks how deep it is at a spot that has real pins nearby (demo or live), and says that he drives a sedan. The answer on screen reports only spots, levels, classes and ages, and cites its pins (plan §9).</li><li>The refusal scene uses D19's line, not the plan's.</li><li>The technical scene's figure is a new drawing from the code (C920), not the plan's Figure 3.</li><li>One caption names any should-have that was dropped (design §8, "When we slip").</li><li>**The rain variant** keeps the plan's ruler check from the dry curb (plan §18, §25), but leaves out the commuter choosing another way. A story about the decision can read as advice.</li></ol> | Each change follows a later decision or a rule. Table 19's order already serves each criterion. A question about getting through, followed by a class line, reads as a yes or a no about crossing (CLAUDE.md). |
| C906 | **Nothing private on screen.**<ul><li>Recordings use a clean browser profile, the deployed site only, and phones with notifications silenced.</li><li>No console, terminal, editor, email, key, account ID, report id shown as text (MS5's C610; an unpublished report's id is the key to its result, MS4's C503), home location or unconsented face appears.</li><li>If Rene appears on camera, a tripod or a phone stand does the filming. No one else operates the camera or edits, because only approved participants may take part in making the project (checklist G9).</li><li>Before Rene uploads, Claude pulls a frame at every scene change and every 5 s of the final cut with FFmpeg, and checks each frame for these and for the copy rules.</li></ul> | The video stays public, and the organizers hold a licence to it. |
| C907 | **The safety line outside the app.** App frames carry it already (MS5's C608). Every other card in the video carries it in small type. The closing card shows it full size, with "Not affiliated with MMDA.". The video description, the X post, the end of the write-up and the top of the README carry it word for word. | CLAUDE.md puts the line on every screen, and a card in the video is a screen too. |
| C908 | **Captions.**<ul><li>English captions cover the whole video: the voice-over and every Taglish line.</li><li>They are burned into the picture, so they show on every host, X included. An SRT file goes to hosts that accept one.</li><li>At most two lines of about 42 characters, each on screen for 1 to 6 s. They never cover the app's safety line, the map's OpenStreetMap attribution or a credit line.</li><li>Claude drafts them from the final script; Rene checks the translation and the timing (M30, M20).</li></ul> | Plan §18 wants captions throughout, so judges can follow with the sound off. The finals judges watch the video live, where a host's caption setting can't be relied on. |
| C909 | **The opening line.** On screen and in the voice-over, in Rene's final words. Draft, matching MS8-Q3 (a): "All of Lusot's code, and everything this video shows of it, was built during the hackathon, Oct 27 to Nov 4, 2026." Under it: "Photos are credited on screen."<ul><li>The line speaks of Lusot's code and the product shown, not of the credited third-party photos.</li><li>It doesn't cover the planning notes begun on Oct 26, `eval/rules.md`'s first drafts among them (MS8-Q3). So the video says only that the scoring rules were fixed before any result existed, never when they were first written.</li></ul> | Plan Table 19 and M23 ask for the line, and it must be true of everything it covers. |
| C910 | **The first-cut test (M23).** Three adults who haven't seen Lusot, and weren't among M17's five testers, each watch the first cut once and then say what they remember. Whatever none of the three recalls is cut or reworked. No names are recorded, and the notes stay outside the repo. | M23; plan §25 counts the test toward Demo. M17's testers have already seen Lusot. |
| C911 | **Format and host.** 1920 × 1080 at 30 fps, H.264 video and AAC audio in MP4. Target 2:40 (Table 19), never over 3:00. Rene uploads it to YouTube as Unlisted, with the SRT, unless the guide names another host or setting (Rene confirms). The X post follows MS8-Q7. | A link that judges can open without signing in. YouTube accepts SRT files. |
| C912 | **The README's order,** as the README outline lays it out:<ol><li>the safety line and the 60-second judge path (C913)</li><li>plan §19's lead: the problem with its sources, the overlay GIF, the numbers with their n</li><li>the limits, including the weakness register (W1 to W28, each Done with its evidence or explained; plan §18) and what was dropped. MS7 drafts this "Known limits" section (its C821), and MS8 keeps it, reworded wherever it would break the copy rules.</li><li>how Lusot works: the live map, the pipeline with MMDA's gauge, geometry and its release gate</li><li>the three Meta models and their jobs</li><li>Ask Lusot's tool and voice</li><li>the sealed evaluation</li><li>the engineering</li><li>privacy</li><li>how to run it yourself</li><li>what is new and how it was built (MS8-Q3), keeping MS1's line that Rene built Lusot solo with Claude Code as a coding assistant</li><li>credits: MS1's table, plus the sample photos, map tiles, fonts, icons and any music</li><li>the licence (M22)</li><li>"Not affiliated with MMDA."</li></ol>Links are relative (D6). | Plan §18 and §19, and CLAUDE.md's rule on how Lusot is pitched. |
| C913 | **The judge path:** four steps that a judge can start within a minute.<ol><li>The live URL.</li><li>One sample run from the Tested page. It gives the real waiting time (C901), and says that a sample never reaches the map. It also says what a judge sees **if new analyses are paused** (MS9's N4), because the README can't change after the cutoff (C921):<ul><li>The Meta credits may lapse during judging, and MS9-Q1 decides whether analysis then goes on, billed to the card up to a limit, or pauses. A pause can come under any of its options, at the lapse or at the limit, so the note is written as an "if", and it holds either way.</li><li>While paused, the sample shows the app's paused line instead of a new reading. That line is MS5's string, as MS9's N1 asks, and Rene reviews it (M20).</li><li>Everything already stored still works: the map and its pins, the Tested page's figures, the samples' photos, the video and the one command.</li><li>A saved sample result, if MS9's N2 ships it, is marked as saved, with its date.</li></ul></li><li>The video link.</li><li>After `git clone` and `cd`, the one command: `python eval/run_eval.py --from-saved`. Use `python3` where `python` isn't installed (macOS and many Linux systems), or `py` on Windows. Expected: the headline counts, then "identical", with exit code 0 (MS6's C401, MS6E-Q4's default).</li></ol>The APK link and its SHA-256 follow, with a note that the web URL is the main path (M15). The README's development section explains how `npm run check` behaves on a judge's machine (N3). | Plan §18's judge path. The one command needs only Python 3.9 or newer. |
| C914 | **The write-up comes in three lengths:** a one-line tagline, a summary of about 60 words, and the full text. Each is cut to the form's limits once Rene has seen the form (Rene confirms). The full text's sections follow MS8-Q6's order, and each one answers the Official Rules' own description of its criterion. | Forms often have a short field and a long one. One source text keeps them consistent. |
| C915 | **The agentic prize paragraph (M33)** names only what is built and tested by the freeze:<ul><li>Muse Spark choosing and calling Ask Lusot's one tool, `get_reports`</li><li>answering only from what that tool returns, citing the reports it used and showing the transcript of a spoken question (plan §9)</li><li>the self-check, only if it shipped (decided Oct 31)</li></ul>The tool's final name and the test counts wait for the Ask Lusot spec (C700 onward) and MS6's 10 typed and 10 spoken test questions. | M33. An agentic claim has to survive a judge reading the code. |
| C916 | **Recheck the event page.** On Nov 3 and on the morning of Nov 4, Claude fetches the event page's raw HTML with curl, as on Oct 28 and 29. It checks the key dates, the rules and the portal's stored deadline. The 6-hour grace field in the page data is never relied on. Any change goes to Rene at once. | The rules say dates may change, CLAUDE.md asks for a recheck before each milestone, and summaries miss the rules section. |
| C917 | **The APK for judges** is the signed release build from `main` (MS8-Q9's default, (b)), or MS5's debug build (C627) if Rene picks (a). Rene attaches it to a GitHub Release on the submission repository, with its SHA-256 in the release notes and in the README. It is never committed to git, and its bundle has passed MS7's secret scan. | Plan §18 lists a downloadable APK. A Release keeps a binary out of the history. |
| C918 | **The X post (M26).** Rene posts it from his own account, by hand. Claude drafts the text under the copy rules: what Lusot does at one spot, the safety line, the live URL and the repository link, and any tags the guide requires (Rene confirms). The video follows MS8-Q7. The post's link then goes into the form. | CLAUDE.md bars automated access to X, and plan M26 needs the link on the platform. |
| C919 | **The demo-ready check.** Within the hour before Rene submits, Claude:<ul><li>opens the live URL at phone and desktop sizes</li><li>runs one sample</li><li>checks the map, the Tested page, the privacy page and the safety line</li><li>checks the APK's link and its SHA-256</li><li>clones the public repository fresh and runs the one command</li><li>tries every link in the README except the YouTube and X links, which Rene opens by hand (CLAUDE.md bars automated access to both)</li><li>checks that the app's count of unreviewed lines is 0 (MS5's C609; MS7 §4.4)</li></ul>Each result goes into the log with the clock's time. | The Demo criterion asks whether the product holds up live, and a broken link is the cheapest point to lose. |
| C920 | **The README's media,** all in `docs/media/`:<ul><li>**A GIF of the overlay drawing itself.** Claude records it at phone size with Playwright, from one sample run of a CC0 or CC BY photo marked `demo_use ok`, and converts it with FFmpeg to about 5 MB or less. The credit line stays in frame, and the credit under the GIF says Lusot blurred the photo and drew the outlines. It draws itself only if MS4 serves the layers file (N9); otherwise it shows MS5's fade-in (C615).</li><li>**A figure of the wheel landmarks and rim geometry,** drawn as SVG from the landmark table in the code and from MS3b's geometry. The README and the video both use it.</li><li>**An architecture diagram,** drawn as SVG from the SAM template</li></ul> | Plan §19 leads the README with a GIF of the overlay. The plan's own figures stay out of the repo (C4). |
| C921 | **After the cutoff, the submission repository doesn't change.** Nothing is pushed after Nov 5, 10:00 AM, unless the guide allows it (Rene confirms). Fixes during judging go to the private repository, and to the live stack under MS9's rules. | A commit dated after the deadline invites doubt about what was submitted. |
| C922 | **MS8's checks reuse MS7's tools,** with additions:<ul><li>**The history scan** is MS7's `scripts/check_history.mjs` (C829). MS8 adds the rest of C903's list: plan text over every blob, the path and image rules, tagger addresses, the `Claude-Session` count, an allow-list by exact blob with reasons, and failing on a missing plan in the export run. MS7 can build these in (N7). If it hasn't, MS8 adds them test first.</li><li>**The copy rules** are MS7's `scripts/copy-rules.json` and `scripts/check_copy.mjs` (C819). MS8 adds its own texts to the files the rules read, and requires the safety line in them. It makes the `banned-safe` rule fail in `README.md`, where MS7's plan (Task 9, uncommitted) only flags it for review, because the README is product copy.</li><li>**MS8 adds only one new tool:** a link check, `scripts/check_links.mjs`. It fails on a relative link whose target is missing, and on any link to the private development repository.</li></ul> | One implementation per check, as MS7's C819 asks for copy. The README must never say "safe" (CLAUDE.md and this spec's anti-goals). A link that works in the private repository can be dead in the public one. |

## 7. Done when

| # | Check | Evidence |
|---|---|---|
| S1 | Submitted by Nov 4, 10:00 PM Manila (design §8) | Rene reports the platform's confirmation, and Claude logs the time he gives |
| S2 | The README opens with the judge path, and every link in it works | C919, run on the public repository |
| S3 | The one command rebuilds the report from a fresh clone of the public repository | Exit 0 and "identical" |
| S4 | Every number in the README, video, write-up and X post matches `summary.json` or a cited source | The plan's number table, ticked line by line with each number's source |
| S5 | The copy rules hold in the README, write-up, captions and X post | MS7's copy check (C819, with C922's changes), run on those files, finds no fail. Rene has seen each review hit (M20). The link check passes on the README. |
| S6 | The video: at most 3:00; the opening line; captions throughout; credits; nothing private | Claude's frame check (C906); the three-viewer test (M23); Rene's review |
| S7 | The export's whole-history scan (C903, C922) is clean, or every hit is allow-listed with a reason Rene has read | The scan's output (counts and paths only) |
| S8 | The submission repository is public, carries `main`'s history under MS8-Q1, and its CI passes | `gh repo view` reads PUBLIC; the CI run's result |
| S9 | The bonus entry (M33) and the X link (M26) are in the form | Rene's word, or a screenshot that he keeps |
| S10 | PROGRESS.md: the MS8 row is Done, and M23, M24, M26, M30 and M33 are ticked with evidence | The records commit |
| S11 | The app's count of unreviewed lines is 0, which MS5's C609 and MS7 §4.4 hand to MS8's release | `LUSOT_RELEASE=1 npm run copy:review -w app` reports 0 unreviewed lines |

## 8. Questions for Rene

Each question has a default that the drafts and the plan follow until he answers (D7). Most important first.

### MS8-Q1: how the submission repository gets its history (R7)

MS7-Q8 asks the same question from the scan's side. One answer settles both, and the two defaults agree.

**The finding.** `main` will hold every milestone's merged work.
- Every commit so far carries Rene's personal email as its author and committer address: 186 commits on all branches at 1:12 AM, Oct 29. It comes from his global git config, and no repository setting overrides it.
- That does no harm while the repository is private. But any option that publishes the history publishes that address in the commit metadata, where anyone can read it. CLAUDE.md keeps email addresses out of the repo, and this is the same rule applied to history metadata.

Two more facts bear on this:
- **Commits carry `Claude-Session` links** to his Claude Code sessions: 32 at 12:10 AM, and one more with each new commit. Those sessions read plan text, account IDs included, so the links must open only for him. A signed-out curl got Cloudflare's bot challenge (HTTP 403), which proves nothing either way. **Rene confirms** by opening one link in a private window: it should ask him to sign in.
- **The logs and docs cite commit hashes throughout.**

| Option | What happens |
|---|---|
| (a) | **Keep it.** Publish `main`'s history as it is: hashes, dates and identities unchanged. Only if Rene is fine with his personal email being public. |
| (b) | **Rewrite the authors, then lock the setting.**<ul><li>In the export only, `git filter-repo` uses a mailmap to change author, committer and tagger addresses to his GitHub no-reply address. `--replace-text` removes any scan hit he decides to remove.</li><li>Dates, messages, files and every commit stay, but every hash changes. filter-repo rewrites the hashes cited in commit messages itself (its documentation, read through Context7).</li><li>A map from old hash to new, `commit-map.csv`, resolves the hashes cited in the logs and docs. It is attached to the GitHub Release, not committed, so the repository's `main` stays exactly the rewritten history, and a later fix can still land as a fast-forward.</li><li>Then Rene turns on GitHub's "Keep my email addresses private" and "Block command line pushes that expose my email".</li><li>The block checks the newest commit of every push, in any repository (GitHub's documentation, through Context7). So first, the development repository's new commits must use the no-reply address: one repository-level `git config user.email`, which every worktree shares. Otherwise the routine pushes (D11) are refused.</li></ul> |
| (c) | **A fresh squashed or snapshot repository,** with the no-reply author: one commit, or a few. Nothing old is published, but judges can no longer see when each part was written, which works against the new-work rule (checklist G1; MS8-Q3). |
| (d) | Rewrite only the scan's hits, and keep his personal email (MS7-Q8's (c)). |

Making the development repository itself public is ruled out by D9.

**Default: (b)**, which is MS7-Q8's (a). It keeps every commit and every date, which is the trail that shows judges what is new, and it publishes no address or account detail. The private repository stays as it is.

**Answer: MS8-Q1: (b), Rene, Nov 1, 2026** (this also answers MS7-Q8). git-filter-repo with a mailmap to his GitHub no-reply address, in the export only; `commit-map.csv` goes on the Release and is never committed. His two GitHub email settings come before the repository goes public (Task 16). The Claude-Session lines wait for his O6 private-window check.
- **A rewrite needs Rene's OK,** because it changes the commit hashes that the logs and docs cite. The commit map keeps them traceable.
- **His steps under (b):** the repository-level commit address, then the two GitHub settings, before the submission repository goes public (plan Task 16).
- **For every option that publishes history** ((a), (b) and (d)), C903's full-history secret and account-ID scan runs on exactly what will be pushed, before the push. Under (c), the same scan covers the snapshot.
- The `Claude-Session` lines stay if his private-window check shows a sign-in page. Otherwise (b) drops them too, with filter-repo's `--replace-message`. This check (checklist O6) is a gate before any push (plan Tasks 4 and 15), because dropping the lines later would change every hash.

**Needed by Nov 3.**

### MS8-Q2: the submission repository's name, and when it exists

**The repository's URL goes into things finished before Nov 4:**
- MS5's Tested page links to the report there. Its `REPORT_URL` is built into the web app and the APK that MS7 scans on Nov 3.
- The video's closing card and description, the README's clone line and the X post all show it.

**The development repository is `RVBCosme/lusot`, and the one `origin` remote that every worktree shares points at it.** If the public repository took that name, the development repository would have to be renamed first. GitHub's documentation (read through Context7) warns that a new repository under a renamed repository's old name ends the old name's redirects. From then on, every worktree's routine push (D11) would go to the public repository, raw branches and Rene's personal email included.

| Option | What happens |
|---|---|
| (a) | A new name of his choice under his account, such as `lusot-submission`, created empty and private by Nov 2. Its URL goes into MS5's final build and the video. His answer also lets Claude push scanned exports to it while it is private (C902). Making it public stays his step. |
| (b) | The name `lusot`. He renames the development repository first (for example to `lusot-dev`), then points the shared `origin` at the new name and checks a push from each worktree, and only then creates the new `RVBCosme/lusot`. |
| (c) | He creates it on Nov 4. The Tested page ships without its report link, and the URL reaches the video and the README late. |

**Default: (a).** No existing remote can reach it, it costs Rene one step, and everything that shows the URL can be finished on time. Docs that name `RVBCosme/lusot` would point judges at a private repository, so the README says the work was developed there and carried over with its history (MS8-Q1). **Needed by Nov 2.**

**Answer: MS8-Q2: (a), Rene, Nov 1, 2026.** He created the repository empty and private that evening; its URL is in the README outline's clone line and the video outline's closing card (exact case). The answer also covers C902: scanned exports may be pushed to it while it's private. Making it public stays his step (Task 16).

### MS8-Q3: planning notes from before kickoff, and the new-work line

Kickoff was Oct 27, 12:00 AM Manila. Some planning documents began on Oct 26, before kickoff (PROGRESS.md lists MS0's "before kickoff" work). For example:
- the build design's first version
- the two research notes dated Oct 26
- `eval/rules.md`, whose change log dates v0.1 to v0.3 to Oct 26
- the Set A collection guide
- the MS0 checklist on the board

Plan §20 allowed planning only before kickoff, and no code was written then. These files came into git on Oct 28 and have been revised since.

The README now says that everything in the repository was written from Oct 27, which isn't true of these files. As plan §2 summarizes the guide's rule, all the work a project presents has to come from the event itself, and a project is disqualified if judges can't tell its new work apart.

| Option | What happens |
|---|---|
| (a) | Keep the files, and say so. The README's line becomes: "All code, and everything the demo shows, was written from Oct 27, 2026 (Manila), after kickoff. Planning notes begun on Oct 26 hold no code, and each carries its own date." A short list of those files follows, made at MS8 from their own dates. Rene also asks the organizers by Nov 3, the last full day for submission questions (plan Table 1), and follows the answer. Office hours take API questions, so he uses whichever channel the guide gives for rules questions (Rene confirms). |
| (b) | Leave the files out of the submission repository (with filter-repo). This drops the trail of evaluation rules written before any result was seen, which supports the evaluation's credibility, and breaks the docs that link to them. |
| (c) | Keep the files and the README line as it is. Not recommended: the line is inaccurate. |

**Default: (a).** It is true, it lets judges tell exactly what is new, and the organizers' answer settles any doubt before the deadline. **Needed by Nov 3.**

**Answer: MS8-Q3: (a), the tracker, under Rene's written delegation, Nov 1, 2026 (9:58 PM).**

### MS8-Q4: if the sealed run lands late

The sealed run is planned for Nov 3. Only some steps wait for its report, and everything else can be finished first with placeholders and approved: the wording, the other scenes, the captions and the cards.

**The steps that wait for the report take about 7 hours,** from the plan's task times:
1. the numbers table and its checks (Task 11), about 1 hour
2. then, side by side, about 3 hours:
   - the numbers card, the final cut, Rene's caption check and the upload (Tasks 13 and 14)
   - MS5's rebuild of the web app and the APK (C616), and MS7's APK scan (its C827)
3. the export and its scan (Task 15), about 1 hour
4. the repository's push, checks and Release (Task 16), about 1.5 hours
5. the demo-ready check (Task 17), then the X post and the submission (Task 18), about 1 hour together

| Option | What happens |
|---|---|
| (a) | **Keep the plan's day if the report is on `main` by Nov 4, 2:00 PM:** the submission goes in by 9:00 PM, under the 10:00 PM target. If the report lands later, use the buffer: a report by 11:00 PM still gives a complete entry by Nov 5, 6:00 AM, 4 hours before the cutoff. If no report is on `main` by Nov 4, 11:00 PM, submit by 6:00 AM with the evaluation marked as pending: the method, the rules and the one command, and no figures. Development results never stand in for sealed ones, since they stay private (MS6). |
| (b) | Always submit by Nov 4, 10:00 PM with what exists, marking the evaluation as pending if need be. Update the entry later only if the form allows edits (checklist O1). |
| (c) | Hold the entry until the report is in, up to the cutoff. |

**Default: (a).** The buffer exists to absorb a slip, 4 hours stay as margin, and no gap is filled with numbers the rules don't allow.

**Answer: MS8-Q4: (a), the tracker, under Rene's written delegation, Nov 1, 2026 (9:58 PM).** Moving the day-of buffer stays Rene's call.

**The move into the buffer waits for Rene's OK on the day, even under D7.** Both late paths, the complete entry by 6:00 AM and the entry marked as pending, pass CLAUDE.md's "Submit by Nov 4, 2026, 10:00 PM Manila time". That target is his rule. If he hasn't answered by Nov 3, D7 would apply this default without him, so the plan marks the step itself as his. **Needed by Nov 3.**

### MS8-Q5: filming the five-person test for scene 7

Scene 7 (1:55 to 2:20) is the video's evidence that real people used Lusot, which serves Impact, the 30% criterion. Today it can only be text cards:
- MS5's kit for M17 (its C634, plan Task 22) asks testers only for a spoken OK to being watched and noted.
- C904 never allows anyone filmed without written consent.

The test runs Nov 1 to 3, before MS8 starts, so the choice has to reach MS5's kit by Oct 31.

| Option | What happens |
|---|---|
| (a) | Film the testers who agree in writing. The form covers the video, the X post and the organizers' licence (C18). The camera frames hands and the screen by default, and a face or a voice needs its own tick on the form. MS5's kit adds the form and a filming step (N8). |
| (b) | No filming. Scene 7 shows text cards, and before-and-after screens of the change. |

**Default: (a).** Real hands using the real app is the strongest Impact shot the video can have, and the default framing keeps testers' faces out unless they choose otherwise. **Needed by Oct 31.**

**Answer: MS8-Q5: (a), Rene, Nov 1, 2026.** The M17 testers who consent in writing are filmed; the filming form M17-v1 was approved Nov 1.

### MS8-Q6: the write-up's order

| Option | Order |
|---|---|
| (a) | The Official Rules' order: Impact, Use of Meta AI Tooling, Technical Depth & Execution, Demo |
| (b) | Plan §18's order, which follows the weights: Impact, then Meta's models, then Demo, then Technical Depth |

**Default: (a).** The rules override the plan, and judges score from the rules' list. If the form has a field per criterion, its order wins (Rene confirms). **Needed by Nov 4.**

**Answer: MS8-Q6: (a), the tracker, under Rene's written delegation, Nov 1, 2026 (9:58 PM).**

### MS8-Q7: the video on X

Several 2026 guides put X's video limit for accounts without Premium at 2 min 20 s (140 s), and the video runs 2:40. Claude hasn't checked this on X's own help pages, which it doesn't open (CLAUDE.md).

| Option | What happens |
|---|---|
| (a) | A cut of at most 2:15 for X, made from the same footage (shorter technical and user-test scenes), posted natively, with the full video linked in a reply |
| (b) | The full 2:40, posted natively, which needs X Premium, a paid subscription and his choice |
| (c) | A link to the full video only |

**Default: (a)**, or (b) if he already has Premium. Rene confirms whether the guide's X rule asks for the submitted video itself. **Needed by Nov 4.**

**Answer: MS8-Q7: (a), Rene, Nov 1, 2026** (no X Premium): an X cut of at most 2:15, posted natively, with the full video linked in a reply.

### MS8-Q8: who cuts the video

| Option | What happens |
|---|---|
| (a) | Claude assembles the first cut with FFmpeg, from Rene's footage and voice-over, Claude's screen captures and cards, and the burned-in captions. It works from an edit list kept with the footage in `LUSOT_DATA_DIR\video\`, outside the repo. Rene reviews the cut and can re-cut it in any editor. |
| (b) | Rene edits it in his own editor, from the shot list, the cards and the captions file. |

**Default: (a).** It saves Rene hours on Nov 3 and 4, and a scripted cut is quick to redo after the three-viewer test. **Needed by Nov 3.**

**Answer: MS8-Q8: (a), the tracker, under Rene's written delegation, Nov 1, 2026 (9:58 PM).**

### MS8-Q9: the APK

| Option | What happens |
|---|---|
| (a) | MS5's debug build (C627) |
| (b) | A release build, signed with a new keystore kept outside the repo |

**Default: (b), the signed release built from `main`** (the tracker's call, Nov 1; the default was (a)). The default was (a) because a keystore is one more secret to guard, but MS5 has had a release keystore outside the repo since Nov 1, and its signed release build passes `apksigner verify`, so that reason no longer holds. Judges sideload either one, and the web URL is the main path (M15). **Needed by Nov 3.**

**Answer: MS8-Q9: (b), the tracker, under Rene's written delegation, Nov 1, 2026 (9:58 PM).**

## 9. What MS8 needs from other milestones

| # | From | Need | For | If missing |
|---|---|---|---|---|
| N1 | MS6 | Exact and within-one level agreement in `summary.json` (MS5's M1), and `latency.jsonl` (C416, C631) | The README's and the video's numbers | The README links to `report.md` for level agreement. The video makes no speed claim. |
| N2 | MS4, MS5 | Demo pins (MS5-Q2); samples whose credit lines are in frame (C617); the Tested page live | Video scenes 2 and 3; the judge path | The sample flow stands in for the map (C905). |
| N3 | Window 1 or MS7 | Once MS3a's fail-closed plan-leak check reaches `main`, `npm run check` exits 2 on any clone without the private plan unless `CI=true` | The README's development section | The README says that `npm run check:node` and `npm run check:py` run on any machine with Node 22 and uv after `npm ci`, and that `check:secrets` needs gitleaks and, for its plan step, the private plan (CI skips that step). |
| N4 | Ask Lusot (C700 onward) | The answer shows its cited pins and the transcript; pins exist near the asked place | Video scene 5; the M33 paragraph | Typed Ask Lusot (plan Table 18's fallback) |
| N5 | MS7 | The copy review (M20) covers the README, write-up, captions and X post; the APK's secret scan; the full claude-security scan (W26); the licence (M22, with R52's SAM License question) | The export | MS8 holds the export until each one is done. |
| N6 | MS3b | The self-check decision (Oct 31) and the release gate's result | The M33 paragraph; the numbers scene | Their lines stay conditional. |
| N7 | MS7 | The history scan (C829) gains C922's additions, and the copy rules (C819) fail `banned-safe` in `README.md` | C903; S5; S7 | MS8's plan adds them, test first, once MS7's tasks have merged |
| N8 | MS5 | The submission repository's URL in `REPORT_URL` before its final build (MS8-Q2). Under MS8-Q5 (a), the filming consent form and filming step in the M17 kit, by Oct 31. | The Tested page's report link; scene 7 | The link stays empty (MS5's own default), and scene 7 stays text cards. |
| N9 | MS4 | The layers file (`layersUrl` in MS4's second draft; MS5's N5), so the overlay draws itself; and each sample's place and date (MS5's N9), beyond the credit line that MS4's C512 already serves | The GIF (C920); video scenes 2 and 3 | The overlay fades in instead (MS5's C615), and samples show their credit line only. |
| N10 | MS5 and MS9 | The app's final paused line (MS9's N1), and whether a paused sample shows its saved result (MS9's N2) | The README's note on a pause (C913; MS9's N4) | The README describes the pause in its own words, without quoting the app |

## 10. Risks

- **No rain and no demo pins.** The capture and map scenes fall back (C905), and samples still show real readings.
- **Ask Lusot's voice lands late.** The video shows typed Ask Lusot.
- **The sealed run slips past Nov 3.** MS8-Q4's rule decides. The other scenes are recorded on Nov 3, a day early, as plan §19 advises.
- **The history rewrite goes wrong** (MS8-Q1 (b)). It is rehearsed before Nov 4, and the scan runs on the result.
- **An unscanned push.** GitHub can keep pushed commits reachable by their hash, so no unscanned export is ever pushed, and a push that would need `--force` means recreating the empty repository instead (C902).
- **The form differs from what's known.** Rene reads it by Nov 3, while organizers still answer submission questions.
- **X's length limit** (MS8-Q7).
- **The live demo fails during the finals.** The backup recording stands in (deliverable 3), and MS9 watches the stack.
- **The laptop's memory.** FFmpeg encodes never run alongside a Docker or Gradle build (the work queue's rule).

## 11. Builder check (Oct 29)

A fresh reviewer (Opus 5.5 at max effort) read this spec as if it had to plan MS8 alone. It also read CLAUDE.md, the build design, the plan's §2, §18 to §20, §24 and §25, the MS5, MS6 and MS7 drafts, and the four drafts here. It opened nothing under `lusot-data`. It asked three questions, all of them Rene's to answer, and made one check request:

| # | Question (short) | Pile | Settled as |
|---|---|---|---|
| BC1 | **The submission repository: its name, its owner, and when it exists.**<ul><li>Its URL is built into MS5's app and APK (`REPORT_URL`) and into the video before Nov 4.</li><li>Can it be created early and private?</li><li>May Claude push to it while it is private?</li><li>If it reused the name `lusot`, the worktrees' remotes could push raw branches to it.</li></ul> | Rene's | MS8-Q2, defaulting to a new name created by Nov 2. C902 now pushes only scanned exports, as fast-forwards. N8 carries the URL to MS5. |
| BC2 | **What if the sealed run lands late?** The latest workable time, and whether the entry slips into the buffer or goes in with the evaluation pending | Rene's | MS8-Q4 |
| BC3 | **Should the M17 testers be filmed for scene 7?** That would need written consent added to MS5's kit by Oct 31. | Rene's | MS8-Q5, with N8 for MS5's kit |
| BC4 | **Verify that the `Claude-Session` links are login-gated before keeping them.** Those sessions read plan text, account IDs included. | Claude's check | A signed-out curl got Cloudflare's bot challenge (HTTP 403), which proves nothing either way. Rene checks one link in a private window (MS8-Q1; checklist O6). |

**Ruled out by the reviewer:**
- CI on `main` needs no secret and nothing tied to the development repository, so it runs on a new repository.
- `.gitleaks.toml` and the scan scripts pin no commit hash, so a rewrite can't break CI's gitleaks job.
- The coordinates in `main` are the plan's public §12 example.
- The drafts hold no contact details.

**Folding these in** also aligned MS8 with MS7's spec, which was committed (4554d74) while the check ran. MS7 owns the history scan and the copy rules, and MS8 extends them (C922, N7), rather than building its own.

## 12. Accuracy review (Oct 29)

A second fresh reviewer (Opus 5.5 at max effort) checked all six files against their sources. Those were CLAUDE.md, the design, PROGRESS.md, the plan, the Official Rules (fetched again at 12:49 AM, and unchanged since Oct 28, by SHA-256), the MS3a to MS7 drafts, the research notes and the git history.

**It found nothing Critical. All 17 Important findings were fixed:**
- **Plan text:** whole plan lines in the drafts were reworded (C4).
- **Tags:** tags are fetched by name and checked against `main` (C902).
- **The `Claude-Session` check** is now a gate (MS8-Q1).
- **The commit map** moved to the Release (MS8-Q1).
- **The image allow-list** gained `docs/media/` and `app/public/` (C903).
- **W23's wording** is reworded for the README (plan Task 12).
- **The Ask scene** asks about depth (C905).
- **"Every pin shows its work"** now follows MS5-Q3.
- **The opening line** matches MS8-Q3 (C909), and `eval/rules.md` joins MS8-Q3's list.
- **The Aug 9 citation** now points at the afternoon lists.
- **Commands:** FFmpeg's `-fps_mode`, the budgets call's account ID, and no scripted YouTube or X access (C919).
- **MS8-Q4's thresholds** are derived from the steps that wait for the report.
- **The unreviewed-line count** is checked (S11).
- **The copy checks' timing** is fixed (plan Tasks 6 and 7).
- **The write-up's causal claim** about D14 is gone.

**The Minor findings were fixed too:** the sources and dates, the wording about MMDA's levels, the README's facts, the judge path's `py`, the shared `origin`, the plan's paths and extractor order, the allow-list's kinds, the new N9, and the video's material notes.

**Also checked and found correct:**
- the rules R1 to R22 and their sections
- every time-zone sum
- the git-history counts
- the safety line wherever it is quoted
- the cited calls and questions in MS3a to MS7
