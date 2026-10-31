# MS5 user-test kit (M17): five people, one change

> **For Rene, before the first tester.** Written Nov 1, 2026 (Window 2). The plan's file name keeps its Oct 31 due date. It implements MS5's C634 and plan Task 22 Steps 1 and 2, with filming under **MS8-Q5 (a)** (Rene, Nov 1) and the tracker's five clarifications (F1 to F5 below). The filming consent form is `docs/drafts/m17-filming-consent-draft.md`. Nothing is filmed until Rene has approved that form and the tester has signed it (F4). Testing without filming can start sooner.
>
> **No names, here or in the notes.** Testers are P1 to P5 everywhere: on the observation sheet, in file names and in the log.

## 1. Who

- **Five adults,** each 18 or older. At least two of them drive or commute through floods.
- **Each gives a spoken OK** to being watched and noted, before anything else. This comes on top of the in-app consent, which each tester passes on their own (the 18+ check and the notice). What Rene asks:
  - *English:* "I'd like to watch you try my flood app, Lusot, and take notes on where it's unclear. I won't write down your name. Is that OK?"
  - *Taglish (draft for Rene's M20 review):* "Gusto sana kitang panoorin habang sinusubukan mo ang flood app kong Lusot, at magsusulat ako ng notes kung saan ito nakakalito. Hindi ko isusulat ang pangalan mo. OK lang ba?"
- **Filming is a separate question,** asked only after the test is explained (§7). A tester who says no to filming still takes the test.

## 2. What to tell them first

Before they open the app, Rene says:
- **Shoot from the sidewalk,** away from traffic and water. Any street will do, flooded or dry, so don't go looking for water. Don't step into the water or the road.
- **If Lusot reads a level from a photo taken inside Metro Manila, it becomes a public pin** on the map for 3 hours, showing the blurred photo at that spot. A photo taken outside Metro Manila is shown only to the person who took it.

In Taglish (draft for Rene's M20 review):
- Kumuha mula sa bangketa, malayo sa mga sasakyan at sa tubig. Kahit anong kalsada, may baha man o wala, kaya huwag nang maghanap ng tubig. Huwag lumusong sa baha o pumunta sa kalsada.
- Kapag nabasa ng Lusot ang level mula sa photo na kinunan sa loob ng Metro Manila, magiging public pin ito sa mapa nang 3 oras, at ipapakita ang naka-blur na photo sa spot na iyon. Ang photo na kinunan sa labas ng Metro Manila ay makikita lang ng kumuha nito.

Nothing more. The app's own notice tells them what happens to the photo, and they read it themselves.

## 3. Setting up

- **Which app:** the web link if the website is live by then. While CloudFront waits for AWS's verification, use the APK on Rene's Android phone. A tester with an iPhone uses Rene's phone too, since iOS gets the web app only. Note the phone and the build for each tester.
- **A fresh start for each tester,** so each one meets the gates: on the APK, clear the app's storage in Android's settings; on the web, use a new private window.
- **The map:** before each tester, open the map. If it shows no pins, Task 5 can't be done, and the sheet says "map empty" (see §4).
- **Credits:** each street photo and each sample run is one paid analysis on Rene's Meta credits, about $0.03 each in Task 21's live runs. Five testers come to well under $1. Log the counter before and after, as for any paid run.
- **Filming only:** the camera on the stand must be a second device of Rene's, since the tester may be using his phone. Without a second device, film only testers who use their own phone on the web link. Both phones' notifications are silenced (MS8's C906).

## 4. The tasks, in order

Read each task to the tester as written, then say nothing more:
1. Open the link (or the app).
2. Get past the first screens.
3. Take a photo of a street.
4. Read the result aloud.
5. Find a pin on the map. *(Skip it if the map was empty, and write "map empty, n/a".)*
6. Try a sample.
7. Switch the app to Taglish.

In Taglish (draft for Rene's M20 review): 1. Buksan ang link (o ang app). 2. Lampasan ang mga unang screen. 3. Kumuha ng photo ng isang kalsada. 4. Basahin nang malakas ang resulta. 5. Maghanap ng pin sa mapa. 6. Subukan ang isang sample. 7. Gawing Taglish ang app.

## 5. How to watch

- **No help.** If a tester asks how, answer "What would you try?" Step in only if they head toward traffic or water.
- **Note where they stop:** a pause, a wrong tap, a misread result, a question. A tester stuck for about two minutes moves on to the next task, and the note says so.
- **Task 4 matters most.** Write down how they read the level and the passability class, in their own words, paraphrased.

## 6. The observation sheet

One row per tester and task. Filled sheets go to `$env:LUSOT_DATA_DIR\m17\`, never into the repo.

| Tester | Role | Phone and build | Task | What happened | Their words (paraphrased) | Severity |
|---|---|---|---|---|---|---|
| P1 | driver / commuter / other | e.g. Android, APK 0.5.0 | 1 to 7 | | | 0 to 3, or n/a |

Severity: **0** no trouble; **1** slowed down, but recovered alone; **2** needed several tries, or misread something minor; **3** couldn't finish the task, or misread the level or the class; **n/a** the task couldn't be tried (such as an empty map).

## 7. Filming (MS8-Q5 (a), Rene, Nov 1)

- **The gate (F4):** nothing is filmed until Rene has approved the form and that tester has signed it.
- **Who is filmed:** only a tester whose form is signed, framed as their ticks allow. By default that's their hands and the phone's screen. A face needs the face tick, a voice the voice tick, and a quote in a caption the quote tick.
- **Sound (F1):** testers read results aloud, so record with the sound off, or remove the audio in editing, unless that tester ticked voice. Passers-by's voices are never kept.
- **The camera screen:** the in-app camera view and the photo check show the street before Lusot blurs it, with any passer-by or plate in view. Pause recording, or cut in editing, from the camera view until the result appears, which shows Lusot's blurred copy.
- **Who films and edits:** Rene, with a phone on a stand (MS8's C906), never another person. Rene edits the footage himself.
- **What stays out of frame:** passers-by, their faces, car plates and anything that shows a home's location. Keep the browser's address bar out of frame too, or use the APK, so no report id shows as text (F3; a pin's address holds its report id, MS5's C620; C906). Claude's frame check of the final cut (C906) still runs before any upload.
- **Footage:** copy it to `$env:LUSOT_DATA_DIR\m17\`, never into the repo, and name each file by the tester's code (P1 to P5). The form promises to delete the raw footage by a date Rene fills in.
- **Forms (F5):** signed forms carry names, so they stay on paper or as scans in `$env:LUSOT_DATA_DIR\m17\forms\`, never in the repo or any upload. The tester's code goes on their form, so a withdrawal can be matched to its footage.
- **Withdrawal (F2):** until Rene submits, by Nov 4 at the latest, a tester can withdraw, and their footage is deleted unused. After the submission, the organizers' copy can't be recalled under their licence (C18), but Rene removes the tester from his own X post and any later cut on request.

## 8. After the test (plan Task 22, Step 4)

Pick the **one** change with the most effect on the testers' tasks. Write it as a task in MS5's plan with its test, build it through the usual loop, and log the reason. Rene's notes stay outside the repo; the plan names the change and the severity count behind it, never a tester.
