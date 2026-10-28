# Lusot privacy policy: draft for Rene

> **Draft, Oct 28, 2026 (Window 4).** Rene approves every line (M21), and reviews the copy as a native speaker (M20). Text in square brackets depends on a result or decision that is still open; each is listed under "Open items" at the end. This draft is information, not legal advice.
>
> English comes first. The app's other languages follow at M20 (R3); no Taglish line is drafted here.

---

**Lusot privacy policy**

Last updated: [date of publication]

Lusot estimates the depth of a flood at one spot from a photo you take. This page explains what Lusot collects, why, how long it keeps it, and who else receives it.

Not affiliated with MMDA.

## Who runs Lusot

Lusot is a solo project by Rene Vincent Cosme, built for the Meta Global AI Developer Hackathon. He is the person accountable for how Lusot handles personal data. Contact: [privacy contact, added at publication (PRIV-Q4)].

## Who can use Lusot

Only adults, 18 or older. Before your first upload, Lusot asks you to confirm your age and to accept a short consent notice. [It asks the same before your first question to Ask Lusot (PRIV-Q3).]

## What Lusot collects

| What | When | Why |
|---|---|---|
| A photo you take in the app [or a 5-second clip, if clip mode ships] | when you report | to estimate the depth at that spot |
| Your phone's location (GPS), how accurate it is, and how far you moved the pin | with each report | to put the pin at the spot |
| The time the photo was taken, and the time it reached Lusot | with each report | to show how recent a reading is, and to turn away old photos |
| A random device id, made when you first open Lusot, on your phone or in your browser | with each report or question | to limit how many reports and questions one device sends in an hour |
| Your typed or spoken question to Ask Lusot, and your phone's location for a question about "dito" | when you ask | to answer from nearby reports |
| A flag you put on a wrong or fake pin | when you flag | to check or hide that pin |

Lusot has no accounts. It never asks for your name, email or phone number.

## What happens to your photo

1. **Faces are blurred before anything goes to Meta.** On Lusot's own server, a face detector that isn't Meta's blurs every face it finds. It can miss a face, such as a small or turned-away one, and a face it misses reaches Meta unblurred.
2. **Meta analyses the face-blurred photo.** Lusot sends it to Meta's AI service, which outlines the water, wheels and people and names where the water reaches. Licence plates are not blurred at this step, so Meta receives them, along with everything else in the photo, such as bodies, clothes, houses and signs.
3. **Meta may use what it receives to improve its products.** Lusot's calls to Meta are paid with Meta's hackathon credits, and Meta's billing page says content sent under those credits may be used for product improvement. Lusot uses photos only to estimate depth at one spot and show that result.
4. **Faces and plates are blurred again before Lusot keeps a copy.** Until the analysis ends, your original waits in a private area that only the analysis can read. Then faces are blurred again, and licence plates are blurred, using the outlines Meta returns. Other details in the photo stay visible.
5. **The original is deleted.** Lusot deletes your original photo as soon as the result is saved. An automatic rule removes any original left behind about a day later, for example after a failed analysis.
6. **Only a blurred copy is kept,** and only when Lusot gives a level.

[If clip mode ships: faces in a clip are blurred first, as in a photo. The clip is uploaded to Meta's file storage with a 1-hour expiry, and deleted from it after analysis.]

## What Meta keeps

- Meta's terms say it keeps content it receives as needed, with no fixed period.
- [if store: false works] Lusot asks Meta not to store the requests that analyse your photo, and Meta accepts that. The exception is when Meta's service is slow: Lusot then sends a request again in a mode that Meta stores, so the answer can be collected.
- [if Meta stores photos] Lusot asks Meta not to store the request that reads your photo. Meta's outlining service (SAM) can't be asked that, and keeps a copy of each request it receives. Lusot sends it about 7 requests per photo, one for each kind of object it looks for, so Meta may hold about 7 copies of each face-blurred photo.
- Lusot never uses Meta's "contributor" model, which lets Meta train on what it receives.

## Public pins

- **When a result becomes a pin.** A photo taken inside Metro Manila that Lusot reads a level from becomes a public pin, on the map and in Lusot's public pin feed. [Whether a "no flood seen" result also becomes a pin is still being decided (PRIV-Q2).]
- **What a pin shows:**
  - the spot, which is your phone's GPS position, with its accuracy
  - the time the photo was taken
  - the level, the landmark it was read from, and its passability class (PATV, NPLV or NPATV)
  - how many reference objects the reading used
  - [an inches range, only if Lusot's measurement passes its own tests]
- **The photo on a pin.** [In the app, a pin also shows the blurred photo with the outlines Lusot used, so anyone can check how the reading was made (PRIV-Q2).]
- **How long a pin stays.** A pin fades after 1 hour and leaves the map after 3 hours. The report and its blurred photo are deleted 7 days after the photo was taken; the storage service removes them in the background, shortly after that. [Whether a pin's photo can still be opened through its link until then is checked when the backend is built (PRIV-Q2).]
- **The pin feed** carries only what the map shows, never photos, outlines or device ids. Other flood maps may copy pins from the feed, and Lusot can't delete their copies.
- **Demo pins and samples.** Lusot also shows labelled demo pins and sample photos, made from photos whose owners agreed to share them for this. They stay up longer than 3 hours and 7 days, and they never count as reports.
- **Outside Metro Manila.** A photo taken outside Metro Manila is analysed, and the result is shown only to you. It never becomes a pin. The photo still goes to Meta as described above, and the report is kept for 7 days like any other.

## Ask Lusot

- **Your question goes to Meta.** A typed question goes to Meta's AI service, which answers it from the nearby reports Lusot finds for it: their level, place and time, which are public pins anyway. A spoken question first goes to Meta's transcription service. Both are paid with the same credits, so Meta may use them to improve its products.
- [Whether Lusot asks Meta not to store your questions is decided when Ask Lusot is built (PRIV-Q3).]
- [Lusot doesn't store your questions or recordings (PRIV-Q3).]
- **Place names.** When your question names a place that isn't on Lusot's list of MMDA flood-prone spots, Lusot sends the place name, and nothing about you, to OpenStreetMap's Nominatim service to find it on the map. Lusot keeps a list of place names and their map positions [for … (PRIV-Q3)], not who asked.
- **"Dito" questions.** A question about "dito" uses your phone's location to find reports near you. [It may also pass that location to Meta's AI service to look them up. It isn't stored (PRIV-Q3).]

## Who processes data, and where

| Who | What they do | Where |
|---|---|---|
| Amazon Web Services | Lusot's servers, storage and logs | Singapore |
| Meta | AI analysis: outlining and reading photos, transcribing spoken questions, and answering questions | [Meta's locations] |
| OpenStreetMap Foundation | place-name lookups (Nominatim) and the map's images | [OpenStreetMap's locations] |

When you open the map, your phone loads the map's images from OpenStreetMap's servers, which see your IP address like any website does. [Lusot's own servers don't record your IP address (PRIV-Q5).]

## How long Lusot keeps data

| Data | Kept for |
|---|---|
| your original photo | deleted after analysis; any leftover is removed about a day later |
| the blurred photo, its outlines, and the report (level, spot and times) | 7 days after the photo was taken |
| the random device id | [kept for … (PRIV-Q7)] |
| a pin on the map | fades after 1 hour; gone after 3 hours |
| server logs: timings, model names and the reasons for "can't tell" (never photos or locations) | 14 days |
| your questions and recordings | [not stored (PRIV-Q3)] |
| the list of place names and their map positions | [… (PRIV-Q3)] |

## Why Lusot may use this data

[You agree to the consent notice before your first upload, and Lusot relies on that for your photos and questions. People who appear in a photo haven't agreed to anything: Lusot blurs their faces and plates before keeping a copy, and deletes it after 7 days. The lawful basis for processing their data is still open (PRIV-Q8).]

## Your rights

Under the Data Privacy Act of 2012 (Republic Act No. 10173), you can ask to see, correct or delete data about you, and you can object to how it's used. You can also complain to the National Privacy Commission at privacy.gov.ph. Lusot has no accounts, so include the time and place you took the photo [and the report id, if the app showed you one], so Lusot can find your report. Contact: [privacy contact (PRIV-Q4)].

## Keeping data secure

- Lusot's keys stay on its servers. The app never calls Meta directly.
- Each upload link works for 5 minutes, and for one report only.
- A report that isn't a pin can be fetched only by its random report id.

## Changes to this policy

If anything here changes, this page and its date change too.

---

Lusot estimates depth at one spot. It is not advice to cross. Follow MMDA and local advisories.

---

## Open items (for Rene; not part of the page)

The question numbers continue in `consent-notice-draft.md`. The full questions, with options and defaults, are in Window 4's handoff note.

- **PRIV-Q1:** whether Lusot must register with the National Privacy Commission (the handoff note has the official sources).
- **PRIV-Q2: what a pin exposes.**
  - whether a "no flood seen" result becomes a pin (MS4)
  - whether a pin's detail shows the blurred photo with its outlines to everyone (the plan's overlay feature says anyone can check the reading)
  - whether a pin's photo link still opens until day 7
- **PRIV-Q3: Ask Lusot.**
  - Plan §13 says spoken questions are never stored, but says nothing about typed questions or a "dito" location; the plan's data model has no field for either.
  - whether a "dito" location reaches Meta, and whether questions are sent with `store: false`
  - how long the place-name list is kept
  - whether the age check and the notice come before the first question too. Plan Table 4 puts them only before the first upload, but questions go to Meta as well, and Meta's terms require adult users.
- **PRIV-Q4:** the contact for privacy requests. No email address may be written into the repo, so it is added when the page is published.
- **PRIV-Q5:** whether to name OpenStreetMap's map servers, and to state that Lusot's servers don't record IP addresses (to be confirmed at MS7's privacy check).
- **PRIV-Q6, [if store: false works] / [if Meta stores photos]:** MS3a's C85 test settles which bracket stays. It is one SAM call with `store: false`, before the first deploy, and hadn't run at 2:58 PM, Oct 28. "Works" should mean that SAM's reply echoes `store: false`, not just that it raises no error. Even then, the slow-service fallback (a 504, then background mode) is stored. Rene approves the wording of whichever line stays.
- **PRIV-Q7:** how long the device id and the hourly limit counters are kept (MS4).
- **PRIV-Q8:** the lawful basis for processing the data of people who appear in photos.
- **[clip mode]** and **[inches range]** stay only if clip mode ships and the release gate passes.
