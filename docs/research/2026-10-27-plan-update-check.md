# Plan update check (Oct 27, 2026)

Rene updated the plan on Oct 27. This note records how the new version was checked, what changed, where the staging documents no longer match it, and which of its facts were checked against their sources.

- **Old version:** Oct 26, 64 pages (text kept from the Oct 26 session's extraction).
- **New version:** generated Oct 27, 8:35 PM Manila, 78 pages. Its date line still reads Oct 26.
- The staging text copy `docs/plan/lusot-build-plan.txt` (regenerated 8:37 PM) has the same words as the new PDF; only line layout differs.

Markers: ✅ matches · ➕ new in the plan · ⚠️ needs action or a decision.

## 1. How it was checked

- Both versions were extracted with pdftotext and compared section by section (changed words per section). Then the new version was read in full, along with Figures 1, 2 and 5.
- A first read lost 19 lines that contain non-ASCII characters (≤, ñ, ×) in a shell filter. They were recovered from a UTF-8 extraction and read. None changed a conclusion.
- The plan's 108 links were extracted from the PDF. The external claims were then checked against those sources by four parallel reviewers (§5).
- Arithmetic was recomputed: rubric totals 77.25 and 86.25 (the plan says about 77 and 86), points to 10 of 13.75, clip cost $0.07, a 15 s question $0.00075, a few hundred card-paid photos under $10, DynamoDB 15 and 10 units inside the free 25, and Amplify $3 for 100 builds. All ✅.
- Time zones were recomputed for every row of Table 1, with US daylight saving ending Sunday, Nov 1. All ✅.

## 2. What changed in the plan

§8 to §10 (measurement, output rules, weakness register) and §15 are unchanged apart from page numbers.

| Area | Change | Plan ref |
|---|---|---|
| ➕ Rules | Posted Oct 26 in the participant guide and Discord #rules. New work only: the demo may show only what was built during the event. Submit a public repo, a 3-minute video and every member. Judges score the video, the code and the live product. Solo allowed; approved participants only. Disqualification for using code, data or assets without the rights to them. Avoid "simple image analyzers". 18 or older. Who owns the work is still unstated. | §2 |
| ➕ Pitch | Never pitch Lusot as a photo analyzer; lead with the whole system. | §1, §19, Table 18 |
| ➕ Scope | A new **Should have** tier: clip mode (Nov 1 to 2), an overlay that draws itself, photo to pin in under 10 s, a public read-only GeoJSON pin feed, and one stakeholder quote (M28). A new **Gated** tier: the Muse Spark self-check of SAM's wheel outlines, decided Oct 31, finished before the sealed run or dropped. The human baseline is gone. | §4, §7 step 4, Table 5, Table 21 |
| ➕ Set A | Government-posted photos only (MMDA and city governments). No news-outlet photos; news lists only help find the official posts. | §11, Table 25, M7 |
| ➕ Evaluation | No human baseline. The ablation gains a self-check row when it is built. One-command check: per-photo results (no photos) are committed, and `python eval/run_eval.py --from-saved` rebuilds every table without an API key. Set D is final only and reported apart from Set B. | §11, Table 13 |
| ➕ API | `GET /pins.geojson`: live pins only, read-only, cached 60 s. | Table 15 |
| ➕ Privacy | Meta's Billing page says credit-paid content "may be used for product improvement". Rene asks the organizers whether credit-paid calls count as Standard (M32, by Oct 30). If not, calls that carry people's photos move to card-paid Standard calls. | §13, Table 18, §23 |
| ➕ Budget | Meta credits are claimed by Nov 4, 9:00 PM ET (ours arrived Oct 27). A card check and pre-authorization hold come first. A Spend Limit only sends alerts. Partner credits: Baseten, Modal, Fireworks. | Table 16, §14 |
| ➕ Engineering | Tests run in GitHub Actions on every push. | §19 |
| ➕ Schedule | Figure 5 adds "Clip mode, SAM video tracking, Nov 1 to 2". Phase 0 ends Oct 27. Phase 6 adds the one-command rebuild, Phase 8 adds captions and the X post, and Phase 9 adds the closing ceremony (Nov 10, 1:00 AM Manila) and the community vote. | Figure 5, Table 22 |
| ➕ Submission | The README judge path includes the one command. English captions run throughout (M30). The demo goes on X for Most Viral. The video opens with "built during the event, Oct 27 to Nov 4" and runs 2:40. | §18, Table 19 |
| ➕ Manual actions | M26 X post, M27 community vote, M28 stakeholder, M29 rain kit, M30 captions, M31 IAM user `rene-dev` with `aws login --profile lusot`, M32 credits question. Several of M1 to M25 are reworded. | Table 27 |
| ➕ Account status | Recorded by Rene on the evening of Oct 27. The AWS account exists with $120 of credits and the $5 budget. Lambda concurrency in Singapore is 10, with 1,000 requested. The Meta credits are active and one API key exists; the Spend Limit alert isn't set. No IAM users yet. **This section lists account IDs, so the plan stays out of the public repo.** | §24 |
| ➕ Rubric | New §25: a self-score of 77 out of 100, a target of 86 if every gap closer lands, and Table 29 on what a 10 would take. | §25 |

## 3. Where the staging documents no longer match the plan

All ⚠️; they are fixed together after Rene answers the open questions.

- **`CLAUDE.md`:**
  - says 64 pages
  - says the rules aren't posted
  - counts manual actions as M1 to M25
  - places the plan at `docs/plan/` in the repo
  - calls the 9 levels "MMDA's" (MMDA has 7; Lusot adds below gutter and above chest)
  - is missing:
    - Set D in the sealed list
    - government-only Set A
    - deploying as `rene-dev` and never as root
    - CI on every push
    - the stop switch
    - keeping account IDs out of the repo
    - the "built during the event" line in the video
- **Build design:**
  - dates (finals are Nov 10, 1:00 AM Manila)
  - rules status
  - M1 to M25
  - milestone contents: should-haves, the gated self-check, the pin feed, CI, captions, the one-command rebuild
  - R2 is now answered by plan §24
- **`docs/PROGRESS.md`:**
  - the manual-action table (M1 to M32, with Oct 27 statuses)
  - the MS0 checklist
  - T1 to T6 statuses
- **`eval/rules.md`:**
  - government-only Set A
  - the self-check row, decided on development data before the sealed run
  - Set D reported apart from Set B
  - the one-command rebuild
- **`docs/data/set-a-collection-guide.md`:** still accepts news-site photos ("Also fine: a photo from another source (a news site…)"). The plan no longer does.
- **`docs/research/2026-10-26-alert-index.md`:** still valid as a finder aid; it needs a line saying news photos are never used.

## 4. Inconsistencies inside the plan

1. ⚠️ **M4** is marked "Not started", but §2 summarizes the posted rules, and §26 says the Discord #rules, #faqs and #announcements were read on Oct 27.
2. ⚠️ **§7 step 8** says the conditional write stops "a second paid analysis". It only stops a second *write*: two workers can both pay Meta before either writes. Gap fix G2 (claim the report before paying) is still needed, and `CLAUDE.md` already requires it.
3. ⚠️ **Table 14** still lets only `live` pins reach the map, yet §19 and Table 21 want labelled demo pins on it. Gap fix G1 (a `demo` mode) is still needed.
4. ⚠️ **Table 7 and §23** still list the Mirage G4 as "to measure". The Oct 26 lookup found 185/55R15 on Mitsubishi PH's own page (G5).
5. ⚠️ **Phase 5's "done when"** includes the stakeholder quote, which §4 calls a should-have that can drop without harm.
6. ⚠️ **M32's fallback** assumes calls with people's photos can be billed to the card while credits remain. Nothing public says Meta allows that (see §5). Ask in the same office-hours question.
7. ⚠️ **Phase 0** is due Oct 27 ("about 20 candidate photos"), but the Set A log had no rows at 9 PM (§6).
8. The date line still reads Oct 26 (cosmetic).

## 5. Fact check of the plan's claims (Oct 27, about 9 to 10 PM)

Four reviewers read the cited sources in parallel; the AWS Region item was re-checked directly. ✅ confirmed · ⚠️ partly right, or a correction · ❓ couldn't be checked from outside (a login wall or a blocked page).

### Meta Model API and terms (dev.meta.ai)

- ✅ **Models and prices:**
  - model IDs; prices; per-team rate limits
  - Muse Spark 1.3's 1,048,576-token context
- ✅ **Files API:** files don't expire unless `expires_after` is set (1 hour to 30 days); `DELETE /v1/files/{id}`.
- ✅ **Terms:**
  - §6.2: a privacy policy is required, and no personal information may go to the Contributor Services
  - §10.1: end users must be 18 or older
  - §5.1: no training on Standard Services
  - §4.4: content is kept "as needed"
- ✅ **Policies:**
  - the acceptable-use rule on safety decisions
  - the Philippines isn't restricted; Pakistan, Myanmar and Cambodia are
- ✅ **Tools and libraries:**
  - `POST /v1/responses/input_tokens`
  - `meta-sam-parser` 0.1.0 (Python 3.10 or newer, **SAM License**, so credit it in the README)
  - `@meta-sam/parser` 0.1.0 and `@meta-sam/graphics` 0.1.13 (ESM-only; Node ^20.17 or 22.9 and newer)
  - facebookresearch/sam3: Python 3.12+, PyTorch 2.7+, CUDA 12.6+
- ⚠️ Structured output: `strict` **defaults to false**. Set `strict: true` in `text.format` on the Responses API.
- ⚠️ For 504 timeouts, Meta's documented fix is `background: true` plus polling. Streaming doesn't help when processing the input is what's slow. SAM's own docs still recommend streaming, especially for video.
- ⚠️ The Files API takes video as MP4 only (SAM also accepts MOV). Team storage is capped at 100 GiB.
- ⚠️ **File transcription takes WAV only:** mono, 16-bit PCM, 16 or 24 kHz, at most 32 MB and 10 minutes. The app must record or convert to that. Meta says the 25 languages are "supported"; Tagalog is listed.
- ⚠️ Muse Spark 1.3 also takes audio ("not fully supported"). `muse-spark-1.3-contributor` exists (150 requests and 3M tokens per minute); it is never used.
- ⚠️ The Messenger "people with a role" limit is in Meta's quick start, not in the FAQ the plan cites.
- ❓ **Credit-paid calls:** nothing public ties "product improvement" to them.
  - ToS §13.3: promotional credits may expire.
  - ToS §17.2: Meta's IP indemnity excludes use "through promotional credits".
  - Billing is per team, and no per-project or per-key billing is documented. The M32 fallback may not be possible (§4, item 6).

### Hackathon (event page, Meta's event page, secondary guides)

- ✅ **Where the rules are:** the **Official Rules and Event Waiver (dated Oct 25)** are in the event page's HTML; summarizing tools miss them.
- ✅ **What they confirm:**
  - Weights: Impact 30%, Use of Meta AI Tooling 25%, Technical Depth and Execution 20%, Demo 25%.
  - Indie prizes run from $150K to $25K.
  - Teams: solo or up to 4. One representative names every member; approved participants only.
  - Eligibility: 18 or older, with the exclusions.
  - Deadline: Nov 4, 9:00 PM ET. The portal stores Nov 5, 02:00 UTC, which is 10:00 AM Manila.
- ⚠️ **Ownership is stated:** the entrant keeps ownership. The organizers get "a perpetual, irrevocable, worldwide, royalty-free, and non-exclusive license" to use the submission for any purpose. Anything shared during the event isn't confidential. Plan §2 says this is unstated.
- ⚠️ "$150 in Meta Model API credits, **valid for a 10-day development window**." So judging traffic will likely bill the card. A "Credit Terms" PDF is linked from the rules; it sits on Facebook's file server, so Claude didn't open it.
- ⚠️ **Dates and prizes:**
  - The rules page says "Nov 4 – Nov 8: Judging"; the plan says Nov 5 to 8.
  - Bonus prizes, including a public-vote prize, are "announced on or about November 10"; the plan says Nov 16.
  - Bonus prizes total "up to $50,000"; the organizers set the categories and amounts. The plan's $20K and $10K come from the gated guide.
- ⚠️ "About 20,000 participants" is a **cap** on accepted applicants.
- ⚠️ Fitting a problem statement is scored inside Impact in the public rules. The guide's pass or fail stage can't be checked.
- ✅ Open source is allowed when its licences are followed and the project "enhances or builds upon" it. "Dates may be subject to change"; recheck the page.
- ➕ **Payout needs:** the signed waiver and a W-8BEN (non-US). Payment goes through Tremendous.
- ❓ **Visible only after sign-in** (the participant guide and Discord):
  - the new-work-only wording, the 3-minute video, "simple image analyzers"
  - session and office-hour times, the Nov 3 cutoff
  - the claim-form deadline, the card check, partner-credit details
  - the X-post rule and its Nov 8 window
  - Rene can read these.

### AWS, Android and tools

- ✅ **`aws login`:** exists from AWS CLI 2.32.0 (announced Nov 19, 2025).
  - Credentials refresh every 15 minutes for up to 12 hours; after that, log in again.
  - A new profile prompts for a Region; enter ap-southeast-1.
  - The IAM user needs the permissions in the `SignInLocalDevelopmentAccess` managed policy. M31's AdministratorAccess allows every action, so it should cover them.
  - SAM CLI 1.148.0 or newer reads these credentials (1.170.0 is current).
- ✅ **Free plan:** $100 plus $20 for each of 5 activities, for 6 months. The account then closes and its data is kept 90 days. Credits last 12 months, and upgrading keeps them.
- ✅ **Always-free amounts and prices:** Lambda, SQS, DynamoDB, CloudWatch and SSM allowances; Amplify prices; WAF at $15 a month.
- ⚠️ **Singapore prices:** HTTP API is $1.25 per million (the plan's $1.00 is the US price). Its 1M free calls are a 12-month trial that the free plan doesn't include. A NAT Gateway is about $43 a month (the plan says $33).
- ⚠️ **No reserved concurrency** can be set while the account limit is 10. Use the SQS event source's `MaximumConcurrency` (minimum 2). New accounts also have a reduced memory quota; check it before sizing the container.
- ✅ **SQS, API Gateway and DynamoDB:**
  - SQS maximum concurrency is 2 to 1,000.
  - The visibility timeout is at least 6× the function timeout, plus any batching window. maxReceiveCount is at least 5.
  - The HTTP API's 30 s timeout can't be raised.
  - DynamoDB TTL deletes in the background.
- ⚠️ **Image functions need Docker** to build on Windows (Finch is macOS and Linux only), or GitHub Actions. `sam deploy` needs `--resolve-image-repos` or `--image-repository`.
- ⚠️ **Android developer verification:** the 2026 phase covers installs from participating stores in Brazil, Indonesia, Singapore and Thailand. Sideloading in the Philippines in November 2026 is unaffected. It goes global in 2027.
- ✅ **Capacitor 8:** the origin is `https://localhost`, and Camera falls back to a file input. Version 8.1.0 deprecates `getPhoto` and `pickImages` in favour of `takePhoto` and `chooseFromGallery`.
- ⚠️ **Nominatim:** limits apply per application, not per user. Geocode on the server with a cache and an off switch, and show attribution.
- ✅ OpenCV's ellipse fits need at least 5 points.
- ⚠️ **Region risk:** AWS's new sign-up experience (a limited rollout) assigns an account with a Philippines contact address to a project in **Sydney (ap-southeast-2)**. "Any Regional resources that you create will be hosted in that Region" unless advanced features are activated ([AWS](https://docs.aws.amazon.com/accounts/latest/reference/project-regions.html)). **Checked at 9:30 PM with Claude in Chrome (read-only):** AWS Settings lists no projects, so this is a standard account and Singapore works ✅.
- **Meta Billing page** (read-only, 9:35 PM):
  - ✅ "While using free credits your content may be used for product improvement", as plan §13 says.
  - ➕ A **"Stop using free credits"** switch exists for the whole team, so card-paid Standard calls are possible, though not chosen per call.
  - ✅ An email alert at $100 monthly spend is set (M3).
  - The card is charged when the balance reaches ₱600 or on Nov 1.
  - Neither the Billing page nor the dashboard shows when the credits expire.

### Philippine sources and research

- ✅ **MMDA gauge:** 7 levels, with the inches and classes in Table 10. The source (Interaksyon) is secondary.
- ⚠️ **"Over 500 flooding incidents in the July 2025 monsoon" is wrong:** it was a **24-hour** count. GMA, Jul 22, 2025: "More than 500 flood incidents were reported in Metro Manila in the last 24 hours". By 11 AM it had dropped to 273. The video's opening line (Table 19) and §3 need "within 24 hours".
- ✅ **49 flood-prone areas** (seen through search, since ABS-CBN blocked the fetch).
- ✅ **Aug 9, 2026:** MMDA's 2:02 PM list has 4 spots, and QC's 2:20 PM list has 38 entries.
- ✅ **Legal points:**
  - the NPC's lawful-basis principles
  - no copyright in government works (IP Code §176.1, seen through search)
- ⚠️ **NPC registration has three triggers:** 250 or more employees; sensitive personal information of 1,000 or more people; processing likely to pose a risk. Automated decisions are an *example* of risky processing (NPC Circular 2022-04, per Baker McKenzie). The NDV page itself was blocked.
- ⚠️ **PAGASA:** the outlook was issued Jul 8 and is national only, with no Metro Manila monthly figures. Newer releases may exist, so cite the latest one. The Sep 30 thunderstorm advisory says "within the next two hours".
- ✅ DOH's leptospirosis advice; the World Bank's figures.
- ✅ **Research numbers:**
  - FloodVision: 15.62 to 8.75 cm.
  - arXiv 2006.11802 is the person-and-pose method: 89.2% on 250 test images and 76.18% on Hurricane Harvey photos.
  - arXiv 2007.06749 is the multi-task ranking network on DeepFlood: 8,145 images, about 11 cm RMSE.
- ❓ **The two MDPI papers couldn't be read (403):** the tire RMSE of 11.4 and 9.9 cm on about 200 images, and 1,283 Beijing photos. Open them in a browser before quoting. Table 9 mixes MAE, RMSE and accuracy on different data, so don't rank them side by side.
- ✅ **Sales ranks and tires:** Hilux 4, Mirage G4 8, Tamaraw 9; all seven tire codes in Table 7.

## 6. Status at 9 PM, Oct 27 (checked on this PC)

| Item | State |
|---|---|
| AWS CLI (M31 needs 2.32 or newer for `aws login`), AWS SAM CLI, WSL, Docker, Android Studio and its JDK | Not installed (T1 to T4) |
| Android SDK platforms | 31 to 35 installed; 36 missing (Capacitor 8 targets 36) |
| Disk C: | 41.4 GB free; the T6 target is about 60 GB |
| Memory | 4.2 GB free of 15.7 GB |
| `MODEL_API_KEY` | Not set in this shell or as a user variable |
| Node, npm, Python, git, GitHub CLI | 22.22.2, 10.9.7, 3.10.11, 2.48.1, 2.100.0 |
| Set A, A-neg and consented-photo logs in `lusot-data` | 0 rows each (counted without opening any photo) |
| Obsidian | 1.14.5 installed; one new vault in OneDrive with only `Welcome.md` (created 8:46 PM) |
| Repo | Not created |

Tonight's Discord office hours run 10:00 to 11:00 PM Manila: the first chance to ask M32. The first live session (Agents 101) starts at midnight.
