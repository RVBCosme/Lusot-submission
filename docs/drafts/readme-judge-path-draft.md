# README opening: the 60-second judge path (draft for Rene)

> **Draft, Oct 29, 2026 (Window 4, Phase D).** This is the top of the submitted README (plan §18). Rene approves every line. The links are placeholders until the URL, the APK, the video and the post exist. Nothing here goes public before Rene says so (CLAUDE.md's gates).

---

**Lusot is a live flood map built from phone photos.** Each reading estimates the depth at one spot against MMDA's own gauge (its 7 gauge levels plus 2 off-scale levels) and MMDA's three passability classes, and shows its evidence. When it can't tell, it says so.

Lusot estimates depth at one spot. It is not advice to cross. Follow MMDA and local advisories.

Not affiliated with MMDA. Everything in this repo was built during the hackathon, from Oct 27, 2026, apart from the third-party files and libraries credited below.

## In 60 seconds

1. **Open the live map:** [web URL]. Labelled demo pins show what reports look like, each with its photo, the outlines it used and its reading.
2. **Press "Try a sample"** on the accuracy page. A consented or openly licensed flood photo, shown with its credit line, runs through the live pipeline without adding a pin, and a level result's overlay draws its work.
3. **Watch the video** (under 3 minutes): [video link].
4. **Check the numbers yourself.** From the repo's root, with no install, no key and no network:

   ```
   python eval/run_eval.py --from-saved
   ```

   It rebuilds every table and chart in the [evaluation report](eval/results/report/report.md) from the committed per-photo results, and prints `report: N files identical`. Use `python3` where `python` isn't installed.

## What to look at next

- **The evaluation:**
  - one sealed run on held-back photos, with each figure's n
  - landmark readings alone, against geometry, in the same run
  - the release gate that decides whether inches are shown

  The rules were fixed before any result was seen: [`eval/rules.md`](eval/rules.md).
- **Ask Lusot:** typed or spoken Taglish questions. Muse Spark decides the lookup and calls one tool, `get_reports`; code checks every pin it cites, and the answer shows them.
- **Privacy:**
  - faces are blurred automatically before any photo reaches Meta, and faces and plates are blurred before storage (automatic blurring can miss some)
  - reports are deleted after 7 days
  - no accounts

  See the [privacy policy](PRIVACY.md).
- **The Android app:** [APK link] (debug build, SHA-256 [hash]).

---

*Draft notes for Rene, not for the README:*
- The command and its output line come from MS6's spec (C401). The bare command reads `eval/results/`, so it passes only once the sealed run's results are committed; until then it exits 2 ("no results folder"). **Before submission (MS8's checklist):** run it bare in a fresh clone of the submitted repo, and expect exit 0 with `report: N files identical`. It is tested on Python 3.9 to 3.13 (MS6's E10), and the report path imports nothing outside the standard library.
- The link targets are placeholders: `eval/results/report/report.md` exists once the sealed run's export is committed, and `PRIVACY.md` once MS5 publishes the policy.
- Copy rules: CLAUDE.md's banned word stays out in every form, there's no crossing advice, it's "at this spot" only, and the 9 levels use the names the app shows.
- The opening leads with the whole system, the live map first, never "a photo analyzer" (CLAUDE.md, plan §1 and §19). The Ask Lusot line follows its spec on `ask-lusot-specs` (C702, C705): one tool, which the model may call a second time.
