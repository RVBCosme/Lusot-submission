# Verification notes: double-check of the plan (Oct 26, 2026)

These notes record what was checked against the plan (`Lusot Hackathon Build Plan.pdf`), how it was checked and what came out. Each line is marked:
- ✅ matches the plan
- ➕ new fact the plan doesn't have
- ⚠️ needs action or confirmation

## 1. Internal consistency (recomputed with a script)

- ✅ **Table 7:** all 11 overall tire diameters match the formula. Example: 205/55R17 gives 25.88 in, and the plan says 25.9.
- ✅ **Table 8:** the wheel landmark ranges match tire geometry for 23 to 27 in tires on 14 to 17 in rims.
  - Quarter mark: 7.98 to 9.25 in. The plan says 8 to 9.5.
  - Hub: 11.48 to 13.34 in. The plan says 11.5 to 13.5.
  - Three-quarter mark: 14.98 to 17.59 in. The plan says 15 to 18.
  - Rim top: 18.48 to 21.84 in. The plan says 18.5 to 22.
- ✅ **Figure 3 example:** a Vios on 185/60R15 has a 4.37 in sidewall and R = 11.87 in. The plan says 4.4 and 11.9.
- ✅ **Table 10:** every inch-to-centimetre conversion matches.
- ✅ **Costs:**
  - SAM 3.1 per photo: 7 × $0.0025 = $0.0175
  - Muse Spark per photo (2,000 input and 300 output tokens): $0.0038
  - Total $0.0213 per photo, so $150 covers about 7,050 photos
  - Evaluation photos (5 SAM requests only): $0.0125
  - Clip: 7 × 50 frames × $0.0002 = $0.07
  - Spoken question (15 s): $0.00075
- ✅ **Lambda:** 1 GB × 20 s × 7,000 photos = 140,000 GB-seconds, inside the 400,000 free.
- ✅ **Geohash:** the example point (14.6095, 120.9894) encodes to `wdw515`, as the plan says. A 6-character cell at Manila's latitude is 1.18 × 0.61 km, so the "at least 600 m per side" claim holds.
- ✅ **Dates:** kickoff Oct 26, 12:00 PM ET is Oct 27, 12:00 AM Manila. Nov 4, 9:00 PM ET (after US daylight saving ends on Sunday, Nov 1) is Nov 5, 10:00 AM Manila.
- ✅ **Schedule:** Figure 5 matches the runbook phases (Table 22), and the "working core by Oct 29" claim is consistent throughout.
- ✅ **Model IDs** are spelled the same everywhere: `sam-3.1`, `muse-spark-1.3`, `muse-voice-transcribe-1.0`, `muse-spark-1.3-contributor`.
- ⚠️ **Gaps found:** demo pins, paying twice for one photo, rim-scale ground truth, level-rule edge cases and Table 7 lookups. They are written up as G1 to G5 in the build design (§9).

## 2. Hackathon page (checked about 10:20 PM Manila, Oct 26)

- ✅ **Cerebral Valley event page:** the event runs "Oct 26 at 12:00 PM – Nov 4 at 9:00 PM (EST)". Submissions are due Nov 4, 9:00 PM ET. Judging is Nov 4 to 8, with finals on Nov 9.
- ✅ **Indie track:** "For individual builders and students", judged on "creativity, technical ambition, and whether it works".
- ⚠️ **Official Rules:** still not linked. The page says they "will be published before the Hackathon begins on October 26, 2026". The waiver page renders only with JavaScript, so its text couldn't be read.
- ✅ **The reconscribe guide** (cited by the plan) quotes these weights from the waiver: Impact 30%, Use of Meta AI Tooling 25%, Demo 25%, Technical Depth and Execution 20%. It also says:
  - teams of up to 4, each member accepted individually, and one member submits
  - "Open-source software or hardware is allowed too, provided you follow its licences"
  - $150 of Meta credits per selected participant

Sources: [event page](https://cerebralvalley.ai/e/meta-ai-developer-hackathon) · [reconscribe guide](https://reconscribe.com/meta-global-ai-developer-hackathon-2026/)

## 3. Meta Model API (dev.meta.ai, read Oct 26)

- ✅ **Access:** base URL `https://api.meta.ai/v1`, with a Bearer key in `MODEL_API_KEY`. "Model availability can vary by country."
- ✅ **Models:**
  - `muse-spark-1.3`: text, image, video, audio and PDF in; text out; 1,048,576-token context
  - `sam-3.1`: text prompt, image or video in; boxes and masks out
  - `muse-voice-transcribe-1.0`: audio in, transcript out
- ✅ **Prices and limits:**
  - Muse Spark 1.3: $1.25 per million input tokens and $4.25 per million output tokens; 3,000 requests and 4M tokens per minute
  - Contributor variant: $0.10 and $0.20, and it lets Meta train on the inputs
  - SAM 3.1: $2.50 per 1,000 images, $0.20 per 1,000 video frames, at least 50 frames billed per video request; 3,000 requests per minute
  - Voice: $0.18 per hour of audio; 256 concurrent streams
  - Limits are **per team, not per key**
- ✅ **SAM 3.1 requests:**
  - `POST /v1/responses` with `"model": "sam-3.1"`. Streaming is recommended.
  - One concept per request; comma, semicolon or plus lists return zero matches.
  - Options: `metadata.mask_encoding` (`lossless` by default, or `one_bit`) and `metadata.include_confidence` (sent as the strings `"true"` or `"false"`).
  - Video: MP4 or MOV up to 15,000 frames, tracking up to 16 objects.
  - An empty result is `response.completed` with an empty `output_text`, which is normal and not an error.
  - Results can vary slightly between runs.
- ➕ **SAM prompt detail:** joining two concepts with "and", or putting them on separate lines or in two text parts, still segments only one concept. Negations and spatial phrases are unreliable. Keep the seven noun phrases plain.
- ✅ **Structured output:**
  - Set it with `text.format` in the Responses API, or `response_format` in Chat Completions.
  - Strict mode needs `additionalProperties: false` on every object and every key listed in `required`.
  - The root must be a plain object. `allOf` and `oneOf` aren't supported, and `anyOf` is allowed only below the root.
  - ➕ Limits: nesting up to 10 levels, 5,000 properties, 1,000 enum values by default. Table 5's schema fits easily.
- ✅ **Voice:** `POST /v1/asr/transcribe` for files (realtime uses `wss://api.meta.ai/v1/asr/realtime`). It covers 25 evaluated languages with code-switching and supports keyword biasing.
- ➕ **Muse Spark and audio:** audio understanding in Muse Spark 1.3 "is not fully supported". The plan already uses Muse Voice Transcribe for audio, so nothing changes.
- ➕ **`muse-wonder-1.0` exists, and the plan doesn't mention it.**
  - It takes the same requests on the same endpoints, so switching is a model ID change. It supports structured output, tool calling and image understanding.
  - It costs $4.00 per million input tokens and $20.00 per million output tokens, about $0.014 per photo against Muse Spark's $0.0038.
  - Meta's guidance: use Spark for "high-volume, latency-sensitive, or cost-sensitive work, such as … classification", and Wonder for long, complex work. **Suggestion:** keep Muse Spark as the default. In the MS1 probe, optionally run both on the same development photos (a few cents) and keep Wonder only if its landmark reading is clearly better per dollar. Freeze the choice before the sealed run.
- ➕ **Background responses** are capped at 600 submissions per minute per team. They aren't needed, since analysis already runs off the queue.

Sources: [models](https://dev.meta.ai/docs/models) · [pricing and rate limits](https://dev.meta.ai/docs/pricing-rate-limits) · [segmenting](https://dev.meta.ai/docs/sam/segmenting) · [structured output](https://dev.meta.ai/docs/structured-output) · [overview](https://dev.meta.ai/docs/overview)

## 4. Tire sizes for the Table 7 gaps (G5)

| Vehicle | Tire code | Overall diameter (in) | Source and confidence |
|---|---|---|---|
| Mitsubishi Mirage G4 (GLX MT, GLX CVT, GLS CVT) | 185/55R15 82V | 23.01 | ✅ Official Mitsubishi PH model page. All three variants share it. |
| Toyota Tamaraw, 2025 (short wheelbase or 5MT, steel wheels) | 195R14C | 26.3 to 26.6 (no aspect ratio is printed; 80 to 82% assumed) | ⚠️ CarGuide.PH only, and the trim isn't clearly tied. Confirm with a sidewall photo. |
| Toyota Tamaraw, 2025 (long wheelbase, 6AT, alloy wheels) | 215/65R16 | 27.00 | ⚠️ CarGuide.PH only. Confirm. |
| Toyota Hilux, new generation (PH launch expected in the second half of 2026) | 265/60R18 | 30.52 | ⚠️ Top Gear PH, from Toyota Thailand data. The Hilux models already on Manila streets weren't verified: Toyota PH's site returned 403. |

⚠️ **Why this matters:** a Hilux on 265/60R18 (30.5 in) is far outside the 23 to 28 in envelope used for "unknown" light vehicles. If Muse Spark calls a pickup an SUV, the landmark rows would read about one level **too shallow** at the hub (15.3 in is knee, while Table 8 gives half-tire). That is the dangerous direction. MS3 should check the vehicle-type confusion matrix (W14) for pickups specifically. It should also keep the plan's rule that pickups aren't measured until their sizes are confirmed, ideally with Hilux sidewall photos alongside the jeepney, tricycle and bus (M11).

Sources:
- [Mitsubishi PH: Mirage G4](https://www.mitsubishi-motors.com.ph/cars/mirage-g4)
- [CarGuide.PH: 2025 Tamaraw full specs](https://www.carguide.ph/2024/11/here-are-full-specs-of-2025-toyota.html?m=0)
- [Top Gear PH: Hilux vs Ranger, 2026](https://www.topgear.com.ph/features/feature-articles/toyota-hilux-ford-ranger-2026-size-comparo-a2588-20260209)

## 5. Set C datasets

| Dataset | Verified facts | Use |
|---|---|---|
| **STURM-FloodDepth Flooded Cars** | ✅ Zenodo record 14833532, published Feb 7, 2025, **CC BY 4.0**, 4 files, 176 MB. Matches the plan. | Development only: debugging the wheel landmark reading. Never used for MMDA claims. |
| **FloodDET** (the plan's "urban flood submersion dataset") | ✅ Mendeley Data, DOI 10.17632/px48m7vwvf.1, published May 1, 2026, by Gautam Singha and Debanga Raj Neog (IIT Guwahati), **CC BY 4.0**. It has 10,262 images (7,477 train, 1,535 validation, 1,250 test) and a 45-class COCO schema: Person, Bicycle, Car and Bus at levels 0 to 10, plus Flood. Download size isn't listed. | Development only: checking person and vehicle categories. |

⚠️ FloodDET re-annotates images from DEEPFLOOD, FloodIMG, Mapillary Vistas and MS COCO, and the underlying images keep their original terms. Use them for development only and never redistribute them or show them in the demo.

Sources: [Zenodo 14833532](https://zenodo.org/records/14833532) · [FloodDET on Mendeley Data](https://data.mendeley.com/datasets/px48m7vwvf/1)

## 6. Code foundation candidates (D3)

- ✅ **`aws-samples/serverless-patterns`:** active (last push Oct 22, 2026), about 1,800 stars. Its LICENSE is MIT-style ("Permission is hereby granted, free of charge…"), but GitHub doesn't detect it automatically, so re-read it before copying. Relevant patterns include `s3-lambda-container-sam`, `apigw-sqs-lambda`, `apigw-http-api-sqs-lambda-sls` and `cdk-s3-sqs-lambda-dynamodb`.
- ⚠️ **`aws-samples/amazon-s3-presigned-urls-aws-sam`:** archived (last push June 2024). Use it as a reference only.

## 7. Local machine (checked about 10:15 PM, Oct 26)

- ✅ **Present:** git 2.48, GitHub CLI 2.100 (signed in as RVBCosme), Node 22.22, npm 10.9, Python 3.10.11 with pypdf and PyMuPDF, and the Android SDK.
- ⚠️ **Missing:** AWS CLI, AWS SAM CLI, Docker, and `java` on the PATH. Android Studio isn't in its default folder.
- ⚠️ **WSL isn't installed** ("The Windows Subsystem for Linux is not installed"). Docker Desktop needs it on Windows 11 Home: run `wsl --install` as admin, then restart.
- ✅ **Caches from earlier projects:** Gradle, npm and Playwright browser caches already exist.
- ⚠️ **Disk:** C: is the only drive, with **42.9 GB free** (432.6 GB used).
- ⚠️ **Memory:** 15.7 GB RAM, with 3.7 GB free at 11:14 PM. Claude Code stopped a background job for low memory. Cap WSL 2 with `.wslconfig` and avoid running Docker builds and Android Studio together (build design, T3).
- ⚠️ **GitHub connector:** the one in Claude Code fails with HTTP 401. The GitHub CLI works.
