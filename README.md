# Lusot

Lusot reports how deep a flood is at one spot in Metro Manila, in MMDA's own gauge levels and passability classes, and it shows its evidence. Each report is a phone photo. SAM 3.1 outlines the water, the wheels and the people in it. Muse Spark 1.3 names where the water meets them, and code turns that into a level. Rim geometry adds a depth range in inches only where it passes its release gate. The result goes on a live map, and Ask Lusot answers typed or spoken Taglish questions from nearby reports. When the photo can't support a reading, Lusot says it can't tell.

> Lusot estimates depth at one spot. It is not advice to cross. Follow MMDA and local advisories.

**Status:** in development for the Meta Global AI Developer Hackathon (Indie track). Everything in this repository was written during the event, from Oct 27, 2026, except the third-party files and data credited below. Progress is tracked in [docs/PROGRESS.md](docs/PROGRESS.md).

Not affiliated with MMDA.

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
git clone <repository URL> lusot
cd lusot
npm ci                                # the app's and the API's packages, from the lockfile
npm run setup                         # git uses .githooks, whose pre-commit hook runs gitleaks
uv sync --directory backend/analysis  # the analysis project's Python environment
npm run check                         # tests, linters and secret scans; CI runs the same checks
```

`npm run check` runs three parts in order and stops at the first failure: `check:node`, `check:py` and `check:secrets`. Each also runs on its own. Deploying, the smoke test, the probe and the Android build are in the "Commands" section of [CLAUDE.md](CLAUDE.md).

`npm run deploy:web`, after `npm run deploy`, builds the app against the deployed stack's API and puts it on the stack's private S3 bucket behind CloudFront; it prints the web URL.

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
| [vite-plugin-pwa](https://github.com/vite-pwa/vite-plugin-pwa) 2.0.0, with Google's [Workbox](https://github.com/GoogleChrome/workbox) (`workbox-window` in the page; `workbox-core`, `workbox-precaching` and `workbox-routing` in the service worker, which `workbox-build` writes) | Makes the website an installable web app: a service worker that precaches the app's own files only, registered on the web and never in the APK | MIT |
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
| [OpenStreetMap](https://www.openstreetmap.org/copyright) data, © OpenStreetMap contributors: the Metro Manila boundary (relation 147488, clipped to OpenStreetMap's coastline) and S2's named test places | The Metro Manila test (`backend/api/src/data/ncr.json`) and its test points (`backend/api/test/fixtures/s2-points.json`), both shared under the same licence; `backend/api/src/data/NCR_SOURCE.md` gives the sources, dates and changes | [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/) |
| [OpenStreetMap](https://www.openstreetmap.org/copyright) data, © OpenStreetMap contributors, from [Geofabrik](https://download.geofabrik.de/asia/philippines.html)'s Philippines extract of Oct 29, 2026: the points of Ask Lusot's spot list | The spot list (`backend/api/src/data/spots.json`), whose places are the locations in MMDA's and city governments' public flood alerts and whose points come from the extract, shared under the same licence; `backend/api/src/data/SPOTS_SOURCE.md` gives the sources, the extract's hash and the alert locations left out | [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/) |
| [Nominatim](https://nominatim.org/), OpenStreetMap's search service at `nominatim.openstreetmap.org`; its results are OpenStreetMap data, © OpenStreetMap contributors | Finds a place that Ask Lusot's spot list doesn't hold. It is called from the API Lambda only, at most once a second, with Lusot's User-Agent, and each answer is cached for 7 days (1 day for a miss), under its [usage policy](https://operations.osmfoundation.org/policies/nominatim/) | Its results: [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/) |
| [pyosmium](https://github.com/osmcode/pyosmium) | Reads that extract when the spot list is built on the laptop (`backend/scripts/build_spots.py`); it is not part of the deployed system | BSD-2-Clause |
| [STURM-FloodDepth Flooded Cars](https://zenodo.org/records/14833532), by Nicla Notarangelo | Development probes only. Its photos are not redistributed, and none of its code is used. | CC BY 4.0 |
| [scikit-learn](https://github.com/scikit-learn/scikit-learn) | Test only: the evaluation harness checks its Cohen's kappa against scikit-learn's (`eval/tests/test_kappa.py`) | BSD-3-Clause. Its wheels bring SciPy, joblib, threadpoolctl and cloudpickle (each BSD-3-Clause), NumPy (above) and narwhals (MIT), all read from the installed wheels' metadata |
| Development and test tools: [pytest](https://github.com/pytest-dev/pytest), [Ruff](https://github.com/astral-sh/ruff), [moto](https://github.com/getmoto/moto), [PyYAML](https://github.com/yaml/pyyaml) (the template tests), [uv](https://github.com/astral-sh/uv) (with `uv_build`), [Vitest](https://github.com/vitest-dev/vitest), [Playwright](https://github.com/microsoft/playwright) (the end-to-end suite, with the Chromium it downloads at test time), [axe-core](https://github.com/dequelabs/axe-core), through [`@axe-core/playwright`](https://github.com/dequelabs/axe-core-npm) (the suite's accessibility checks), [Testing Library](https://github.com/testing-library), [jsdom](https://github.com/jsdom/jsdom), [Oxlint](https://github.com/oxc-project/oxc), [TypeScript](https://github.com/microsoft/TypeScript), [esbuild](https://github.com/evanw/esbuild), `@vitejs/plugin-react`, `aws-sdk-client-mock`, the `@types` packages from [DefinitelyTyped](https://github.com/DefinitelyTyped/DefinitelyTyped), [gitleaks](https://github.com/gitleaks/gitleaks), and the GitHub Actions `actions/checkout`, `actions/setup-node`, `actions/upload-artifact` and `astral-sh/setup-uv` | Tests, linting, type checks, builds, secret scans and CI | MIT, except TypeScript, moto and Playwright (Apache-2.0), axe-core and `@axe-core/playwright` (MPL-2.0) and uv (MIT or Apache-2.0) |

Each library's own dependencies are pinned, with their versions, in `package-lock.json`, `backend/analysis/uv.lock`, `backend/analysis/requirements.lock.txt`, the scripts' `backend/scripts/*.py.lock` files, and MS2's `eval/data/*.py.lock`, `eval/data/tests/run_tests.py.lock` and `eval/set_b/*.py.lock` files, and MS6's `eval/tests/run_tests.py.lock`, each under its own licence. py7zr's compression and crypto libraries are pinned there, several under LGPL-2.1-or-later. The analysis image builds on AWS's `public.ecr.aws/lambda/python:3.13` base image.

## How it was built

Rene Vincent Cosme built Lusot as a solo entry, with Claude Code (Anthropic) as a coding assistant.
