Last updated: [date of publication]

Lusot estimates the depth of a flood at one spot from a photo you take. This page explains what Lusot collects, why, how long it keeps it, and who else receives it.

## Who runs Lusot

Lusot is a solo project by Rene Vincent Cosme, built for the Meta Global AI Developer Hackathon. He is the person accountable for how Lusot handles personal data. Contact: {privacyContact}.

## Who can use Lusot

Only adults, 18 or older. Before your first upload, Lusot asks you to confirm your age and to accept a short consent notice. It asks the same before your first question to Ask Lusot. The app asks for the 18+ check before samples too, as before an upload, and enforces it.

## What Lusot collects

| What | When | Why |
|---|---|---|
| A photo you take in the app | when you report | to estimate the depth at that spot |
| Your phone's location (GPS), how accurate it is, and how far you moved the pin | with each report | to put the pin at the spot |
| The time the photo was taken, and the time it reached Lusot | with each report | to show how recent a reading is, and to turn away old photos |
| A random device id, made when you first open Lusot, on your phone or in your browser | with each report, question or flag | to limit how many reports and questions one device sends in an hour, and to count one flag per device on a pin |
| Your typed question, or your spoken question as a voice clip of up to 15 seconds, and your phone's location for a question about "dito" | when you ask | to answer from nearby reports |
| A flag you put on a wrong or fake pin | when you flag | to check or hide that pin |
| Your IP address, which comes with every upload | with each report | kept only in a failed upload's queue record, so the failure can be checked (up to 7 days) |

Lusot has no accounts. It never asks for your name, email or phone number.

## What happens to your photo

1. **Faces are blurred automatically before Meta receives the photo.** On Lusot's own server, a face detector that isn't Meta's blurs the faces it finds. Automatic blurring can miss some faces: very small, side-on, partly covered or in the dark. A face it misses reaches Meta unblurred.
2. **Meta analyses the face-blurred photo.** Lusot sends it to Meta's AI service, which outlines the water, wheels and people and names where the water reaches. Licence plates are not blurred before Meta receives the photo, only before Lusot stores it. So Meta receives them, along with everything else in the photo, such as bodies, clothes, houses and signs.
3. **Meta may use what it receives to improve its products.** While Meta's hackathon credits pay for Lusot's calls, Meta's billing page says content sent under those credits may be used for product improvement. When the credits run out, analysis pauses, and the app says "New analyses are paused right now. The map and the Tested page still work." Nothing is billed beyond the credits. Lusot uses photos only to estimate depth at one spot and show that result.
4. **Faces and plates are blurred before Lusot keeps a copy.** Until the analysis ends, your original waits in a private storage area that only Lusot's analysis and its administrator can open. Then faces are blurred again, and licence plates are blurred, using the outlines Meta returns, which can also miss some. Other details in the photo stay visible.
5. **The original is deleted.** Lusot deletes your original photo as soon as the result is saved. An automatic rule removes any original left behind, usually within two days, for example after a failed analysis.
6. **Only a blurred copy is kept,** and only when Lusot gives a level.

## What Meta keeps

- **Meta may keep what it receives with no fixed period,** under its own terms. Lusot's 7-day deletion covers only Lusot's own copies, and can't delete what Meta keeps.
- **Lusot asks Meta not to store the requests that analyse your photo,** and Meta accepts that. Meta may still keep what it receives, as above.
  - **One exception:** when Meta's outlining service is slow, Lusot sends that request again as a background job, which Meta stores. Lusot deletes the job afterwards, as far as Meta allows, so until then Meta holds that copy of your face-blurred photo.
- Lusot never uses Meta's "contributor" model, which lets Meta train on what it receives.

## Public pins

- **When a result becomes a pin.** A photo taken inside Metro Manila that Lusot reads a level from becomes a public pin, on the map and in Lusot's public pin feed. A "no flood seen" result never becomes a pin; only the person who took the photo sees it.
- **What a pin shows:**
  - the spot: your phone's GPS position, or where you nudged the pin, with the GPS accuracy
  - the time the photo was taken
  - the level, the landmark it was read from, and its passability class (PATV, NPLV or NPATV)
  - how many reference objects the reading used
  - [an inches range, only if Lusot's measurement passes its own tests]
- **The photo on a pin.** In the app, a pin also shows the blurred photo with the outlines Lusot used, so anyone can check how the reading was made.
- **How long a pin stays.** A pin fades after 1 hour and leaves the map after 3 hours. The report and its blurred photo are deleted 7 days after the photo was taken. The storage services remove them in the background, usually within a few days after that. Anyone can open a pin's photo only while the pin is on the map, through a link that lasts 5 minutes. A result that isn't a pin shows its photo only to the person who took it, until it is deleted.
- **The pin feed** carries only what the map shows, never photos, outlines or device ids. Other flood maps may copy pins from the feed, and Lusot can't delete their copies.
- **Demo pins and samples.** Lusot also shows labelled demo pins and sample photos. They come from people who agreed to share their photos for this, or from openly licensed photos (CC0, public domain or CC BY, never BY-SA, from Wikimedia Commons and Flickr). Each is credited on screen with its author, licence and a link to the file. Faces and plate numbers are blurred in all of them. An open-licensed demo pin shows the photo's own date, marked as an archive photo, and is always shown as a demo pin. They stay up longer than 3 hours and 7 days, and never count as reports.
- **Outside Metro Manila.** A photo taken outside Metro Manila is analysed, and the result is shown only to you. It never becomes a pin. The photo still goes to Meta as described above, and the report is kept for 7 days like any other.
- **A photo you choose.** On the Tested page you can choose a photo from your device instead of taking one. Your device re-saves it first, which drops details stored in the file, such as where it was taken. It is analysed the same way and goes to Meta as described above. The result is shown only to you, never becomes a pin, and the report is kept for 7 days like any other.

## Ask Lusot

- **Typed questions** go to Meta's AI service, which answers them from the nearby reports Lusot finds: their level, place and time, which are public pins anyway. Lusot doesn't store your typed questions.
- **Spoken questions.** When you speak a question, the app records a voice clip of up to 15 seconds and sends it to Lusot's server. The server sends the clip to Meta's speech-to-text service, with Lusot's list of spot names so that they're heard right. The text that comes back is shown to you and answered like a typed question. Lusot doesn't store the clip or its text: the clip stays only in the server's memory until the answer is sent.
- **Questions** go to Meta on the same terms as photos: while the hackathon credits last, Meta may use them to improve its products. Meta may keep them with no fixed period. Lusot asks Meta not to store the requests that answer a question, and Meta accepts that. Meta's speech-to-text service has no such setting, so Meta receives a spoken question's voice clip and may keep it under its own terms.
- **Place names.** When your question names a place that isn't on Lusot's list of MMDA flood-prone spots, Lusot sends the place name, and nothing about you, to OpenStreetMap's Nominatim service to find it on the map. Lusot keeps OpenStreetMap's answers (a place's name and map position) for 7 days, or 1 day for a place it didn't find, filed under a one-way hash of the name, never the words you typed or who asked.
- **"Dito" questions.** A question about "dito" uses your phone's location to find reports near you. That location stays on Lusot's server: Meta receives only the distances to nearby reports, never your position, and Lusot doesn't store it.

## Who processes data, and where

| Who | What they do | Where |
|---|---|---|
| Amazon Web Services | Lusot's servers, storage, queue, logs and website | Singapore; the website is also served through AWS's worldwide network |
| Meta | AI analysis: outlining and reading photos, turning spoken questions into text, and answering questions | [Meta's locations] |
| OpenStreetMap Foundation | place-name lookups (Nominatim) and the map's images | [OpenStreetMap's locations] |
| Anthropic | an AI assistant (Claude) that Lusot's developer may use to check logs, flagged reports, privacy requests and the demo video | the United States, and other countries Anthropic names in its privacy policy |

- **The map's images.** When you open the map, your phone loads the map's images from OpenStreetMap's servers, which see your IP address, as any website does. When you place a photo's pin, the map opens around your own position, so those servers also see which area is on your screen, within about 300 m of you.
- **Your IP address.** When you upload a photo, the notice of your upload that reaches Lusot's queue carries your IP address. If the analysis fails, that notice is kept for up to 7 days so the failure can be checked, then deleted. Service logs keep no photos, locations or IP addresses.
- **The website.** When you open the Lusot website, our hosting service (AWS Amplify) records each request, including your IP address, the page asked for and the time. Lusot doesn't use these records. They are kept until the website is taken down after the hackathon's judging, by Dec 31, 2026. What the API does with IP addresses stays as described above, kept no longer than 7 days.
- **An AI assistant.** Lusot's developer may use an AI assistant (Claude, by Anthropic) to check Lusot's logs, flagged reports, privacy requests and the demo video's frames, which can include a report's blurred photo and its pin, or what a privacy request says. Anthropic keeps what it receives for 30 days, or up to 2 years if its systems flag it for a usage-policy check.

## How long Lusot keeps data

| Data | Kept for |
|---|---|
| your original photo | deleted after analysis; any leftover is removed, usually within two days |
| the blurred photo, its outlines, and the report (level, spot and times) | 7 days after the photo was taken, then removed in the background, usually within a few days |
| the notice of an upload whose analysis failed, with your IP address | up to 7 days |
| the random device id | Lusot's servers never store the id itself, only a one-way hash of it: in the hourly counters for 2 hours, and in a flag's record until 7 days after the flagged pin's photo was taken. Both are then removed in the background, usually within a few days. |
| a pin on the map | fades after 1 hour; gone after 3 hours |
| service logs: timings, model names and the reasons for "can't tell" (never photos, locations or IP addresses) | 14 days |
| your typed questions | not stored |
| your spoken questions: the voice clip and its text | not stored (the clip stays only in the server's memory until the answer is sent) |
| OpenStreetMap's answers for place names (a hashed name, the place's name and map position) | 7 days, or 1 day for a place not found |
| the website's access logs, kept by AWS Amplify: each request's IP address, page and time | until the website is taken down after the hackathon's judging, by Dec 31, 2026 |

These limits cover only Lusot's own copies. What Meta keeps is set by Meta's terms.

## Why Lusot may use this data

You agree to the consent notice before your first upload or question, and Lusot relies on that for your photos and questions. People who appear in a photo haven't agreed to anything. For them, Lusot relies on its legitimate interest in showing how deep the water is at one spot (Section 12(f) of the Data Privacy Act), and it uses as little of their data as it can. Their faces are blurred before the photo goes to Meta, and faces and plates are blurred again before Lusot keeps a copy (automatic blurring can miss some faces and plates). Nobody is identified or named, and the copy is deleted after 7 days. If you are in a photo, you can object or ask for it to be deleted (see "Your rights").

## Your rights

Under the Data Privacy Act of 2012 (Republic Act No. 10173), you can ask to see, correct or delete data about you, and you can object to how it's used. You can also complain to the National Privacy Commission at privacy.gov.ph. Lusot has no accounts, so include the time and place you took the photo [and the report id, if the app showed you one], so that Lusot can find your report. Contact: {privacyContact}.

## Keeping data secure

- Lusot's keys stay on its servers. The app never calls Meta directly.
- Each upload link works for 5 minutes, and for one report only.
- A report that isn't a pin can be fetched only by its random report id.

## Changes to this policy

If anything here changes, this page and its date change too.
