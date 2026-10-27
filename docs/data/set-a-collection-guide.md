# Set A collection guide (for Rene, by hand)

Set A is the main evaluation set: Metro Manila flood photos, each matched to an MMDA or city flood alert for the same spot (plan §11, Table 12; manual action M7). We need about **50 photos**. The split into development and sealed photos happens later, by script, so you don't have to think about it while collecting.

**Why by hand:** Facebook's and X's terms ban automated collection (plan M7), and this is a Meta-run hackathon. You do the searching and saving. Claude does everything after that: checks, matching, event IDs, the split and the audit.

## What counts as a good Set A photo

**Only photos that MMDA or a city government posted itself count** (plan §11, Table 25, M7, as updated Oct 27). The rules disqualify data used without the rights to it. Philippine law gives no copyright to works of the Government, so these photos may be used privately, but they are never redistributed.

1. **Best:** an MMDA post (or a Quezon City post, since QC uses the same gauge) that contains **both** the alert and a photo. The photo and the label then share one source and one time.
2. **Also fine:** a photo that MMDA or a city government posted separately, at the **same named spot** and within **30 minutes** of an MMDA or city alert for that spot.
3. **Never:** photos from news outlets, private pages or anyone else. News lists only help you find the official posts.
4. The photo must show the water against something Lusot can read: a parked car's wheel, or an adult standing still. A wide aerial shot is useless.
5. Inside Metro Manila only.
6. **Labels printed on the picture:**
   - **Why it matters:** alert cards, banners and captions burned into the image can show the depth or passability. The AI can read that text, which would give it the answer.
   - **Crop or skip:** crop the text off when you save the photo, as long as the wheel or person stays in frame. If cropping would cut the reference out, skip the photo.
   - **Log it:** record this in `label_in_image` (see below).

Skip a photo if any of these is true:
- it wasn't posted by MMDA or a city government
- the spot or time can't be pinned down
- the alert gives no depth label
- it is a repost of an older photo
- it was shot at night and nothing is visible

## Where to look (you browse; Claude never does)

- MMDA's official Facebook page and X account. Look at flood-alert posts on heavy-rain days.
- Quezon City's official city pages, which also post flood alerts with gauge levels.
- The plan cites two well-documented days to start with: **Jul 10, 2026** and **Aug 9, 2026**. On Aug 9, MMDA listed 4 flooded spots and Quezon City listed 38. The July and August 2026 monsoon days in general are the best hunting ground.
- Claude has built an **alert index from public news articles** (`docs/research/2026-10-26-alert-index.md`: times, spots and levels from "LIST: flooded areas" stories). Use it to go straight to the matching official posts. The news photos themselves are never used.

## How to log each photo

1. Save the image to `C:\Systems\Lusot\lusot-data\set_a\raw\` as `A001.jpg`, `A002.jpg` and so on. This folder is outside the repo. **Never** put these photos in the repo or share them.
2. Add one row to `C:\Systems\Lusot\lusot-data\set_a\set_a_log.csv`. Copy the empty template from `eval/templates/set_a_log.csv`.
3. Write labels **exactly as the post says them**, for example "gutter deep", "above gutter level" or "NPLV". The mapping to Lusot's levels is fixed separately in `eval/rules.md`, so don't translate.

| Column | What to put |
|---|---|
| `candidate_id` | A001, A002, … (matches the file name) |
| `logged_on` | Today's date, YYYY-MM-DD |
| `platform` | `facebook`, `x` or `other` (for example a city government website) |
| `post_url` | Link to the official post |
| `poster` | The government office that posted it, e.g. MMDA or Quezon City |
| `post_time_pht` | Post time in Manila time, YYYY-MM-DD HH:MM |
| `alert_time_pht` | Time the alert refers to, if the text gives one (otherwise blank) |
| `spot_text` | The location exactly as written |
| `city` | Manila, Quezon City, Makati, … |
| `level_label_raw` | The depth words exactly as written |
| `passability_raw` | The passability words or code exactly as written (blank if none) |
| `photo_in_alert_post` | `yes` if the photo is in the same post as the alert, otherwise `no` |
| `photo_file` | `A001.jpg` |
| `reference_visible` | `wheel`, `person`, `both` or `none` |
| `label_in_image` | `no` if no depth or passability words appear on the image; `cropped` if you cropped them off; `yes` if they're still visible (the photo is then excluded, per `eval/rules.md` §9) |
| `faces_or_plates` | `yes` or `no` (for privacy handling) |
| `notes` | Anything odd: angle, reflections, moving cars, partial wheel |

Target by kickoff, from the plan's Phase 0: **about 20 candidates.** Target by Oct 30: about 50 matched photos (MS2).

## A-neg (about 15 photos, no social media needed)

Wet-but-not-flooded streets and dry streets, ideally with parked cars or people in view. Take them yourself, or use photos from friends with their OK. Save them to `lusot-data\a_neg\raw\` and log them in `a_neg_log.csv` with the same columns (level label `none`).

## Consented sample photos (M9, separate from Set A)

These are flood photos and clips from friends, family or community groups, for the "Try a sample" button and the demo. For each one, keep:
- a written OK (a screenshot of the chat is fine)
- a note of who appears in it
- **where it was taken** (street and cross street or landmark) and **when** (date and approximate time). Demo pins are placed at the photo's real spot.

Save them to `lusot-data\consented\`. They are **never** mixed into Set A.

**The written OK must cover every use.** A chat "sure" isn't enough, because the rules require us to hold the rights to everything we submit. Draft message for Rene to adapt and approve; translate it into Taglish if you like (M20):

> Hi [name]! I'm building Lusot, a flood-depth app, for the Meta Global AI Developer Hackathon. May I use your flood photo/video from [place], [date]? If you agree, it will be:
> 1. sent to Meta's AI service for analysis, with faces blurred first (Meta may use what it receives to improve its products)
> 2. shown in the Lusot app as a sample and as a labelled demo pin, for as long as the app runs
> 3. used in my demo video and in a post on X
> 4. submitted to the hackathon, whose organizers get a permanent licence to use submissions
>
> Faces and plate numbers are blurred before anything is shown. Who appears in it, and did they agree too? Where exactly, and at what time, was it taken? If you agree, please reply: "Yes, you may use it for all four." You can say no or withdraw any time before Nov 3.

Keep the reply (a screenshot is fine) next to the photo. Note who appears in it and where and when it was taken.

**Independent labels (M8, later).** The person labelling Set A without seeing Lusot's output records two things for each wheel and person: the landmark, and the **vehicle type**.
