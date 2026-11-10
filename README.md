# Lusot

**How deep is the flood at this spot?** Lusot turns people's photos into a live flood map of Metro Manila. Each photo gets a reading in MMDA's own gauge levels, with its evidence drawn on the photo, or an honest "can't tell" when the photo can't support one. Readings become pins on the map, and Ask Lusot answers typed or spoken questions, in English or Taglish, from nearby reports through Muse Spark's tool calls. Wheel geometry (measuring the water against a wheel's known size) didn't pass its pre-set release gate, so it is off. A sealed set of photos labelled by MMDA and city offices was run once by the frozen system.

> Lusot estimates depth at one spot. It is not advice to cross. Follow MMDA and local advisories.

> **Status, Nov 10, 2026:** the hackathon is over, and the live system (the AWS stack, its website and the Meta model key) has been shut down. The [portfolio demo](#portfolio-demo-on-vercel) runs the same app in your browser instead.

**Portfolio demo:** https://lusot.vercel.app: open **Tested → Samples** and run the **Typhoon Ondoy** sample, which shows the live system's real saved result. Everything else in the demo is simulated.
**Demo video (3 min):** https://youtu.be/u402mhh-wps: the live system, as judged.
**Android app:** [Lusot.apk, on the v1.0.0 release](https://github.com/RVBCosme/Lusot-submission/releases/tag/v1.0.0), kept as a record. It called the live API, so it no longer reads photos.

Built for the Meta Global AI Developer Hackathon (Indie track, "Build for Your World"). Everything here was written during the event, from Oct 27, 2026, except the third-party files and data credited below. Not affiliated with MMDA.

## Portfolio demo on Vercel

https://lusot.vercel.app is the real app, built in demo mode, on a laptop or a phone. It answers every call in the browser, from the app's own development mock, so no photo, location or question leaves the device, and nothing calls AWS or Meta. A banner on every screen says so.

- **Real:** the **Typhoon Ondoy** sample on the Tested page. Its result is the one the live system returned on Nov 4, 2026: the face-blurred photo, the numbered outlines, "Verdict at this spot: Not passable to any vehicle" and the details for each person and vehicle. The Tested page's figures are the real sealed run's.
- **Simulated:** everything else. The other samples, the map's pins, Ask Lusot's answers, and the result of a report or of your own photo come from the mock, with drawn pictures. The banner's **Simulated outcome** picker chooses how a report or your own photo ends: a level, "No flood seen", "can't tell" or "Processing failed", so every screen can be seen.

How it's built:
- `npm run build:demo -w app` runs `vite build --mode demo`. In that mode, `app/src/demo.ts` makes `apiFetch` use the mock (`app/src/mock/`). Every other build keeps the real `fetch`, and the bundler drops the mock.
- `app/.env.demo` sets a placeholder API address that no request reaches.
- The real result is a fixture: `app/src/mock/real/` holds its JSON, and `app/demo/` its two pictures. Only a demo build writes them to `dist/demo/` (`vite.config.ts`).
- `node app/scripts/check-bundle.mjs dist --demo` checks the demo build: it must hold the mock, and it must never hold the Meta API's host or the model key's name.
- `vercel.json` builds with `npm run build:demo -w app` and serves `app/dist`, with the live site's security headers. To deploy: `vercel deploy --prod` from a clone, or connect this repository in the Vercel project's Git settings, so each push to `main` redeploys it.

To run it locally: `npm ci`, then `npm run build:demo -w app`, then `npx vite preview` from `app/`.

## The live demo, as judged (Nov 2026)

This is how the live site worked for judging, until Nov 10, 2026. The site is shut down. The demo video shows it, and the portfolio demo above has the same screens. Each live reading ran the real pipeline on Meta's models and took about 40 seconds.

1. **Tested → Samples.** Run these credited photos. Each one runs live, except while new analyses are paused to protect the shared model budget: then the button shows the photo's saved result instead, dated and marked as saved. In our checks each read the same way 3 times out of 3: a level for the flood photos, "No flood seen" for the dry streets, and "can't tell" for Calumpit. A live run can still come out differently: the models can read a photo a little differently, and then Lusot says "can't tell", or a call to Meta can time out ("Processing failed, try again."). Then run the sample again. The samples:
   - **Typhoon Ondoy, 2009 (people pushing a cart):** tire level, so "Verdict at this spot: Not passable to any vehicle".
   - **Los Baños, Laguna, Typhoon Ondoy (water up to the waist):** waist level.
   - **Macabebe, Pampanga, Typhoon Goni, and a Bulacan street:** below gutter, so "Passable to all vehicles", read from an SUV's tyre.
   - **Makati at night, and dry streets in Manila and Quezon City:** "No flood seen".
   - **Calumpit, Bulacan:** an honest "can't tell". There's a person at ankle depth and motorcycles, but no landmark Lusot trusts.
2. **Look at the result:** the verdict (or "No verdict", for some "at least" results; see below), the level on a gauge, the level's depth range in metres and inches, and the photo with numbered outlines (the one that set the level is highlighted). Open **Details** to see why each object was used or not.
3. **Try your own photo** (Tested page): choose a flood photo from your device. It works best with a parked car's wheel or a person standing still in view. The result is shown only to you and never goes on the map.
4. **Map:** live pins from readings in Metro Manila (demo pins are labelled).
5. **Ask:** type or speak a question about a place, in English or Taglish. The answer comes only from nearby reports and names each one.

The **Android app** ([Lusot.apk, on the v1.0.0 release](https://github.com/RVBCosme/Lusot-submission/releases/tag/v1.0.0)) is the same app installed on the phone, with its own loading screen. The camera Report flow works on both the app and the website.
Fair-use limits, which protect the shared model budget: 5 sample runs and 3 chosen photos per device per hour.

## What it does

- **A depth reading from one photo.** Take a photo from a dry spot (Report), run a credited sample (Tested), or choose your own photo (Try your own photo).
- **A verdict at this spot.** The result names MMDA's passability class for the level ("Not passable to light vehicles"), the level itself ("knee"), and the level's depth range in metres and inches. The range is the level's own range, never a measured depth. A gauge shaped like the logo marks the reading among the 9 levels.
- **"At least" results.** When the water hides how deep it goes, the reading is "at least" a level: "this level or deeper". It keeps a verdict only when deeper water can't change the class ("Not passable to any vehicle"); otherwise it says "No verdict: the water may be deeper than the … level". An "at least below gutter" result says Lusot can't tell how deep the water is, and shows no depth range.
- **Evidence on the photo.** Numbered outlines show the water, the wheels and the people Lusot found, and which one set the level.
- **A live map.** A reading taken in Metro Manila becomes a pin, so others can see what's happening at that spot.
- **Ask Lusot.** Ask a question by text or voice, in English or Taglish, and get an answer drawn only from nearby reports, each one named.
- **An honest "can't tell".** No usable car wheel or adult, too dark, too blurry: Lusot says so, and says how to retake the photo from a dry spot.

## How it uses Meta's models

| Model | Its one job in Lusot |
|---|---|
| **SAM 3.1** (Meta Model API) | Outlines the water, the wheels, the vehicles and the people in the photo |
| **Muse Spark** (Meta Model API) | Reads where the water meets each outlined object (for example "tire only", "mid-thigh"), and in Ask Lusot decides what to look up and calls Lusot's report tool |
| **Muse Voice Transcribe** (Meta Model API) | Turns a spoken Taglish question into text |

**Code, not the models, does the measuring:** the models never output a depth. Lusot's own rules (in `eval/rules.md`, fixed before any result was seen) turn each object's waterline into one of 9 ordered levels: MMDA's 7 gauge levels (gutter, half-knee, half-tire, knee, tire, waist, chest) plus below gutter and above chest. The deepest believable reading wins, and an exact reading more than one level below the deepest means "can't tell". An "at least" reading is never too shallow: "at least tire" can stand beside a chest reading.

## How a reading works

1. **Photo in:** from the camera (with location, for the map) or chosen from the device (never on the map).
2. **Faces are blurred first,** on Lusot's own server, before Meta receives anything.
3. **SAM 3.1** outlines the water and the objects; **Muse Spark** names each waterline.
4. **Lusot's rules** drop what can't be trusted (a moving vehicle, or one that isn't a car or SUV; a person who isn't clearly an adult; a walking person when an adult standing still is in view) and turn the rest into a level and MMDA's class. A person at ankle depth, or too small in the photo, can't set the level alone, and a deeper reading from a small person still makes Lusot say it can't tell.
5. **The result** shows the verdict, the level, the depth range and the evidence. The original photo is deleted; a blurred copy is kept for 7 days.

## How Lusot meets the judging criteria

**Impact (30%): Build for Your World.**
- In July 2025, MMDA identified 49 flood-prone areas in Metro Manila (ABS-CBN, Jul 2025).
- Drivers, commuters, and jeepney and tricycle riders face the same question every rainy season: how deep is it at this spot right now? Lusot answers it in MMDA's own gauge words (gutter, knee, tire, waist…), which people already use. It shows the evidence, so a reader can judge it.
- Readings in Metro Manila become live map pins and feed Ask Lusot, so one person's photo helps others nearby.

**Use of Meta AI tooling (25%).**
- Three Meta models, each with a distinct job, combined with deterministic code:
  - SAM 3.1 for segmentation;
  - Muse Spark for waterline reading and as a tool-calling agent in Ask Lusot;
  - Muse Voice Transcribe for spoken Taglish questions.
- The models describe what they see; Lusot's published rules turn that into a level. That keeps the result explainable and testable, instead of trusting a model to guess inches.

**Technical depth and execution (20%).**
- **An honest evaluation:** scoring rules written before any result was seen; a sealed set of city-office photos run once, by the frozen system; every figure reported with its n. A release gate set in advance decided whether wheel geometry ships: it didn't pass, so it is off.
- **Privacy by design:**
  - faces are blurred before Meta receives a photo;
  - originals are deleted;
  - reports expire after 7 days;
  - no accounts.
- **Engineering:**
  - about 5,900 automated tests (the app, the API, the analysis and the evaluation), run in CI on every push;
  - secret scanning on every commit;
  - a serverless AWS backend with rate limits, a spending stop and alarms;
  - an accessibility check (axe) on the end-to-end suite.
- **Known limits are published,** not hidden (see below).

**Demo (25%).**
- A live website and an Android app, running on the real pipeline. See "Demo: try it in 2 minutes" above.
- Credited samples that held up in our checks, each giving the same answer 3 out of 3. A live run can still say "can't tell" or time out; run it again.
- "Try your own photo", with honest feedback when a photo can't be read.
- The 3-minute video: https://youtu.be/u402mhh-wps.

## Results: tested where it matters most (indicative, small samples)

The scoring rules were written before any result existed, and a set of photos labelled by MMDA and city offices stayed sealed until the frozen system ran on them once.

| Strength | Evidence |
|---|---|
| **No dangerous readings** | 0 readings shallow enough to change the verdict, across every test set |
| **No false alarms** | 0 of 15 flood-free street photos reported as flooded |
| **Correct when it reads** | 8 of 9 levels matched the label on open-licence photos; 9 of 9 levels matched in 15 repeat runs of 3 samples (the other 6 said "can't tell") |
| **Reads only what it can verify** | A level is given only when a car's wheel or an adult is clear in the photo (17% of open-licence flood photos; 1 of 6 sealed, read deeper than the label). Otherwise Lusot says how to retake the photo. |

Full reports: [eval/results/](eval/results/). Scope and design decisions: [docs/research/2026-11-02-known-limits-demo-judgment.md](docs/research/2026-11-02-known-limits-demo-judgment.md).

## Privacy

- Faces are blurred automatically before Meta receives a photo. Automatic blurring can miss some faces (very small, side-on or in the dark). Licence plates are blurred before Lusot stores a copy.
- The original photo is deleted after analysis. Reports are kept for 7 days.
- No accounts, no names.
- The full policy is in the app (About → Privacy).
- The portfolio demo sends no photo, location or question anywhere. Vercel, its host, keeps its usual request logs.

## Repository layout

| Path | What |
|---|---|
| `app/` | React + Vite website, wrapped by Capacitor for Android |
| `backend/` | One AWS SAM template, the Node.js API Lambda and the Python analysis Lambda |
| `eval/` | Evaluation rules, written before any result was seen, and the evaluation code |
| `docs/` | Design, milestone specs and plans, the progress board, the work log and research notes |

## Development

You need Git, Node.js 22, [uv](https://github.com/astral-sh/uv) and [gitleaks](https://github.com/gitleaks/gitleaks) on your PATH.

```sh
git clone https://github.com/RVBCosme/Lusot-submission.git lusot
cd lusot
npm ci                                # the app's and the API's packages, from the lockfile
npm run setup                         # git uses .githooks, whose pre-commit hook runs gitleaks
uv sync --directory backend/analysis  # the analysis project's Python environment
npm run check:node                    # the app's and the API's typecheck, tests and lint
npm run check:py                      # the analysis and evaluation tests
```

`npm run check` runs three parts in order and stops at the first failure: `check:node`, `check:py` and `check:secrets`. Each also runs on its own. `check:secrets` runs gitleaks, the account-ID scan and a plan-leak scan, which reads the private build plan; the plan isn't in this repository. Without it the plan-leak scan stops with an error, except in CI (`CI=true`), where it skips with a notice. So a fresh clone runs the first two parts, and those two alone are not a full pass. Deploying, the smoke test, the probe and the Android build are in the "Commands" section of [CLAUDE.md](CLAUDE.md).

The AWS stack and its website were shut down on Nov 10, 2026; the template still rebuilds them. `npm run deploy:web`, after `npm run deploy`, builds the app against the deployed stack's API and puts it on the stack's website: with `WebHosting=on`, the private S3 bucket behind CloudFront; with `WebHosting=amplify`, the Amplify Hosting app, as one manual deployment. It prints the web URL.

Building the app (`npm run build -w app`) first runs `prebuild`, which writes `app/public/licences.txt`: the name, version and full licence text of every production package, and of the build-time code that ends up in the page (`app/scripts/shipped-extra.json`). The app's Licences page shows that file. It is generated and git-ignored, and the build stops if a package has no licence file.

## Credits

Every third-party starter, model and dataset, and every library that Lusot depends on directly, is listed here with its licence. Those libraries' own dependencies aren't listed one by one; the note under the table says where they are pinned. Some carry other licences, such as certifi (MPL-2.0), tqdm (MPL-2.0 and MIT) and typing-extensions (PSF-2.0). Versions are pinned in the lockfiles.

| Component | Use | Licence |
|---|---|---|
| [Vite](https://github.com/vitejs/vite), with its `create-vite` react-ts template | The starter for `app/`, its dev server and its build | MIT |
| [React](https://github.com/facebook/react) | The app's interface | MIT |
| [Tailwind CSS](https://github.com/tailwindlabs/tailwindcss) | The app's styles | MIT |
| [Lucide](https://github.com/lucide-icons/lucide), through `lucide-react` | The app's icons, bundled as inline SVG | ISC. The icons Lucide derives from [Feather](https://github.com/feathericons/feather), among them `info`, are MIT, as its LICENSE lists them. |
| [marked](https://github.com/markedjs/marked) | Renders the app's own consent notice and privacy policy from Markdown, bundled in the web build and the APK | MIT |
| [Atkinson Hyperlegible Next](https://github.com/googlefonts/atkinson-hyperlegible-next), through [`@fontsource/atkinson-hyperlegible-next`](https://github.com/fontsource/font-files) | The app's typeface (weights 400 and 700), bundled in the web build and the APK, never loaded from Google Fonts or a CDN | SIL Open Font License 1.1 (OFL-1.1). Copyright 2020-2024 The Atkinson Hyperlegible Next Project Authors. |
| Lusot's logo and loading-screen artwork (`app/brand/Lusot-Logo.png` and `Lusot-Loading-Screen.png`), and the mark redrawn from the logo as an SVG in the same folder | The app's icons and splash screens, web and Android, and its loading screen, all drawn from the artwork (`app/scripts/render-icons.mjs`, `app/index.html`). The app's Licences page credits it too. | Designed by Rene Cosme with ChatGPT image generation (OpenAI), Nov 2026, for this project. Both PNGs keep the C2PA provenance record that ChatGPT embedded. |
| [vite-plugin-pwa](https://github.com/vite-pwa/vite-plugin-pwa) 2.0.0, with Google's [Workbox](https://github.com/GoogleChrome/workbox) (`workbox-window` and the plugin's `registerSW` in the page; `workbox-core`, `workbox-precaching`, `workbox-routing` and `workbox-strategies` in the service worker, which `workbox-build` writes, with the module loader of [`@trickfilm400/rollup-plugin-off-main-thread`](https://github.com/trickfilm400/rollup-plugin-off-main-thread)) | Makes the website an installable web app: a service worker that precaches the app's own files only, registered on the web and never in the APK | MIT; the loader Apache-2.0 |
| [Capacitor](https://github.com/ionic-team/capacitor) (core, CLI and Android) | Wraps the app for Android; `app/android/` comes from its template | MIT |
| Capacitor's [Geolocation](https://github.com/ionic-team/capacitor-geolocation) plugin | Reading the GPS fix. The photo comes from the app's own camera view, the browser's camera stream, so no camera plugin is used | MIT |
| [Leaflet](https://github.com/Leaflet/Leaflet) 1.9.4, with its [`@types/leaflet`](https://github.com/DefinitelyTyped/DefinitelyTyped/tree/master/types/leaflet) typings | Draws the live map, and the report's place step map with the pin and the fix's accuracy circle; used directly, without react-leaflet | BSD-2-Clause (Leaflet); MIT (the typings) |
| [OpenStreetMap](https://www.openstreetmap.org/copyright) map tiles | The map's background, loaded from OpenStreetMap's own tile server under its [tile usage policy](https://operations.osmfoundation.org/policies/tiles/), with the credit "© OpenStreetMap contributors" linked on the map | Map data © OpenStreetMap contributors, under the Open Database Licence (ODbL) 1.0; the tiles' cartography is CC BY-SA 2.0 |
| [Gradle](https://github.com/gradle/gradle) wrapper | Runs the Android build; part of Capacitor's Android template | Apache-2.0 |
| [AWS SAM CLI](https://github.com/aws/aws-sam-cli) | Builds and deploys `backend/template.yaml` | Apache-2.0 |
| [AWS CLI v2](https://github.com/aws/aws-cli/tree/v2) | Uploads the web app to its bucket and invalidates CloudFront's copy of its pages (`npm run deploy:web`) | Apache-2.0 |
| [AWS SDK for JavaScript v3](https://github.com/aws/aws-sdk-js-v3) | The API Lambda's calls to DynamoDB, S3 and SSM, its upload links and its 5-minute photo links | Apache-2.0 |
| [ngeohash](https://github.com/sunng87/node-geohash) | Geohash keys for reports | MIT |
| [boto3](https://github.com/boto/boto3), with its [CRT](https://github.com/awslabs/aws-crt-python) extra in the scripts | AWS calls from the analysis Lambda and the scripts in `backend/scripts/` | Apache-2.0 |
| [NumPy](https://github.com/numpy/numpy) | Image arrays in the analysis, and in MS2's data tools (Set B's masks, crops and water) | BSD-3-Clause, with bundled parts under 0BSD, MIT, Zlib and CC0-1.0. Its wheels also bundle OpenBLAS (BSD-3-Clause), LAPACK (BSD-3-Clause-Open-MPI) and the GCC runtime (GPL-3.0-or-later with the GCC Runtime Library Exception), and the Linux wheel in the Lambda image adds libquadmath (LGPL-2.1-or-later). The wheel's LICENSE.txt lists them. |
| [OpenCV](https://github.com/opencv/opencv), through [opencv-python-headless](https://github.com/opencv/opencv-python) | Decoding photos, running the face detector and blurring faces; in MS2's data tools, photo facts, crops and overlays | Apache-2.0 (the wheel's packaging scripts are MIT). Its wheels also bundle FFmpeg (LGPL-2.1) and other libraries under their own licences, listed in the wheel's LICENSE-3RD-PARTY.txt. The Linux wheel in the Lambda image also carries OpenBLAS, the GCC runtime and libquadmath, which that file doesn't list; their licences are as for NumPy. |
| [OpenAI Python SDK](https://github.com/openai/openai-python) | The client for Meta's Model API | Apache-2.0 |
| [OpenAI Node.js SDK](https://github.com/openai/openai-node) (`openai` on npm) | Ask Lusot's client for Meta's Model API, in the API Lambda | Apache-2.0 |
| [httpx](https://github.com/encode/httpx) | The Meta client's HTTP connection, which the OpenAI SDK shares, the voice transcription call, and the cloud smoke test | BSD-3-Clause |
| [py7zr](https://github.com/miurahr/py7zr) | The write-once encrypted archives of MS2's sealing steps | LGPL-2.1-or-later |
| [meta-sam-parser](https://github.com/meta-models/meta-sam) | Parses SAM 3.1's segmentation responses | **SAM License**, Meta's own licence for its SAM materials |
| [jsonschema](https://github.com/python-jsonschema/jsonschema) | Checks Muse Spark's answers against Lusot's JSON schema | MIT |
| [YuNet](https://github.com/opencv/opencv_zoo/tree/4.10.0/models/face_detection_yunet) face detection model (`face_detection_yunet_2023mar.onnx`), by Shiqi Yu and contributors | The face detector behind the face blur, vendored with its licence and source note in `backend/analysis/src/lusot_analysis/models/` | MIT |
| NASA's portrait of Mae C. Jemison ([S92-40463](https://images.nasa.gov/details/S92-40463)), from Wikimedia Commons | A face-blur test fixture only, never shown in the app; see `backend/analysis/tests/fixtures/faces/SOURCE.md` | Public domain |
| Nine photos from Wikimedia Commons: [Flooding from Typhoon Ondoy (Ketsana), Philippines 2009. Photo- AusAID (10695910543)](https://commons.wikimedia.org/wiki/File%3AFlooding_from_Typhoon_Ondoy_%28Ketsana%29%2C_Philippines_2009._Photo-_AusAID_%2810695910543%29.jpg), by the Department of Foreign Affairs and Trade; [Typhoon Ketsana aftermath near Laguna Lake1](https://commons.wikimedia.org/wiki/File%3ATyphoon_Ketsana_aftermath_near_Laguna_Lake1.jpg), by IRRI Images; [7897Tidal flooding Marilao, Bulacan 08](https://commons.wikimedia.org/wiki/File%3A7897Tidal_flooding_Marilao%2C_Bulacan_08.jpg), [8830Effects (floods) of Typhoon Goni (2020) in Poblacion, Macabebe 03](https://commons.wikimedia.org/wiki/File%3A8830Effects_%28floods%29_of_Typhoon_Goni_%282020%29_in_Poblacion%2C_Macabebe_03.jpg) and [1007San Miguel, Calumpit, Bulacan 07](https://commons.wikimedia.org/wiki/File%3A1007San_Miguel%2C_Calumpit%2C_Bulacan_07.jpg), by Judgefloro; [09889jfCity Binondo Avenue Manila Streets Landmarksfvf 02](https://commons.wikimedia.org/wiki/File:09889jfCity_Binondo_Avenue_Manila_Streets_Landmarksfvf_02.JPG), [0062jfHoly Spirit (C.O.A.) Commonwealth Avenue Sandiganbayan Quezon Cityfvf 05](https://commons.wikimedia.org/wiki/File:0062jfHoly_Spirit_%28C.O.A.%29_Commonwealth_Avenue_Sandiganbayan_Quezon_Cityfvf_05.jpg) and [09900jfCity Rizal Avenue School Manila Streets Landmarksfvf 07](https://commons.wikimedia.org/wiki/File:09900jfCity_Rizal_Avenue_School_Manila_Streets_Landmarksfvf_07.JPG), by Judgefloro; and [Manila, makati, dela rosa street](https://commons.wikimedia.org/wiki/File:Manila,_makati,_dela_rosa_street.jpg), by Sailko | The Tested page's nine samples (five flood photos and four dry streets), which anyone can run through Lusot. Lusot stores and shows its own copies, with faces and plates blurred, and each sample shows its own credit line (`GET /samples`). The portfolio demo bundles the first photo's blurred copy, and the same copy with Lusot's outlines drawn on it, in `app/demo/` | CC BY 2.0 (the two Typhoon Ondoy photos); CC0 (the three by Judgefloro with floods); public domain (the three dry Manila and Quezon City streets); CC BY 3.0 (the Makati street) |
| [OpenStreetMap](https://www.openstreetmap.org/copyright) data, © OpenStreetMap contributors: the Metro Manila boundary (relation 147488, clipped to OpenStreetMap's coastline) and S2's named test places | The Metro Manila test (`backend/api/src/data/ncr.json`) and its test points (`backend/api/test/fixtures/s2-points.json`), both shared under the same licence; `backend/api/src/data/NCR_SOURCE.md` gives the sources, dates and changes | [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/) |
| [OpenStreetMap](https://www.openstreetmap.org/copyright) data, © OpenStreetMap contributors, from [Geofabrik](https://download.geofabrik.de/asia/philippines.html)'s Philippines extract of Oct 29, 2026: the points of Ask Lusot's spot list | The spot list (`backend/api/src/data/spots.json`), whose places are the locations in MMDA's and city governments' public flood alerts and whose points come from the extract, shared under the same licence; `backend/api/src/data/SPOTS_SOURCE.md` gives the sources, the extract's hash and the alert locations left out | [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/) |
| [Nominatim](https://nominatim.org/), OpenStreetMap's search service at `nominatim.openstreetmap.org`; its results are OpenStreetMap data, © OpenStreetMap contributors | Finds a place that Ask Lusot's spot list doesn't hold. It is called from the API Lambda only, at most once a second, with Lusot's User-Agent, and each answer is cached for 7 days (1 day for a miss), under its [usage policy](https://operations.osmfoundation.org/policies/nominatim/) | Its results: [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/) |
| [pyosmium](https://github.com/osmcode/pyosmium) | Reads that extract when the spot list is built on the laptop (`backend/scripts/build_spots.py`); it is not part of the deployed system | BSD-2-Clause |
| [STURM-FloodDepth Flooded Cars](https://zenodo.org/records/14833532), by Nicla Notarangelo | Development probes only. Its photos are not redistributed, and none of its code is used. | CC BY 4.0 |
| [scikit-learn](https://github.com/scikit-learn/scikit-learn) | Test only: the evaluation harness checks its Cohen's kappa against scikit-learn's (`eval/tests/test_kappa.py`) | BSD-3-Clause. Its wheels bring SciPy, joblib, threadpoolctl and cloudpickle (each BSD-3-Clause), NumPy (above) and narwhals (MIT), all read from the installed wheels' metadata |
| [MMS-TTS](https://huggingface.co/facebook/mms-tts-tgl) (`facebook/mms-tts-tgl`), by Meta, run with Hugging Face [Transformers](https://github.com/huggingface/transformers), [PyTorch](https://github.com/pytorch/pytorch) (CPU) and [FFmpeg](https://ffmpeg.org/) | Test only: `backend/scripts/make_voice_clips.py` speaks the 10 Taglish questions of Ask Lusot's spoken test on the laptop. The clips are private test data: they are never shipped, never in this repo, and never in the video or the submission, and any result from them is reported as synthetic. The background noise under them is generated pink noise (FFmpeg's `anoisesrc`), not a recording. | CC BY-NC 4.0 (the model); Apache-2.0 (Transformers); BSD-3-Clause (PyTorch); LGPL-2.1-or-later, or GPL-2.0-or-later in some builds (FFmpeg, run as a separate program and not shipped) |
| Development and test tools: [pytest](https://github.com/pytest-dev/pytest), [Ruff](https://github.com/astral-sh/ruff), [moto](https://github.com/getmoto/moto), [PyYAML](https://github.com/yaml/pyyaml) (the template tests), [uv](https://github.com/astral-sh/uv) (with `uv_build`), [Vitest](https://github.com/vitest-dev/vitest), [Playwright](https://github.com/microsoft/playwright) (the end-to-end suite, with the Chromium it downloads at test time), [axe-core](https://github.com/dequelabs/axe-core), through [`@axe-core/playwright`](https://github.com/dequelabs/axe-core-npm) (the suite's accessibility checks), [Testing Library](https://github.com/testing-library), [jsdom](https://github.com/jsdom/jsdom), [Oxlint](https://github.com/oxc-project/oxc), [TypeScript](https://github.com/microsoft/TypeScript), [esbuild](https://github.com/evanw/esbuild), `@vitejs/plugin-react`, `aws-sdk-client-mock`, the `@types` packages from [DefinitelyTyped](https://github.com/DefinitelyTyped/DefinitelyTyped), [gitleaks](https://github.com/gitleaks/gitleaks), and the GitHub Actions `actions/checkout`, `actions/setup-node`, `actions/upload-artifact` and `astral-sh/setup-uv` | Tests, linting, type checks, builds, secret scans and CI | MIT, except TypeScript, moto and Playwright (Apache-2.0), axe-core and `@axe-core/playwright` (MPL-2.0) and uv (MIT or Apache-2.0) |

Each library's own dependencies are pinned, with their versions, in `package-lock.json`, `backend/analysis/uv.lock`, `backend/analysis/requirements.lock.txt`, the scripts' `backend/scripts/*.py.lock` files, and MS2's `eval/data/*.py.lock`, `eval/data/tests/run_tests.py.lock` and `eval/set_b/*.py.lock` files, and MS6's `eval/tests/run_tests.py.lock`, each under its own licence. py7zr's compression and crypto libraries are pinned there, several under LGPL-2.1-or-later. The analysis image builds on AWS's `public.ecr.aws/lambda/python:3.13` base image.

## How it was built

Rene Vincent Cosme built Lusot as a solo entry, with Claude Code (Anthropic) as a coding assistant, and designed its logo and loading screen with ChatGPT's image generation (OpenAI).
