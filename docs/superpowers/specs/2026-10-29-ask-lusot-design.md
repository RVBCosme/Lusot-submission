# Ask Lusot: spec

- **Date:** Oct 29, 2026 (Manila), written from 5:20 AM
- **Status:** Claude's draft; Rene approves. Written overnight without a live conversation, under Rene's instruction (D7, D15). Claude proceeds on the calls in §6 and the defaults in §9 until he answers.
  - **Approved, Oct 29 evening:** AskL-Q1 to AskL-Q11 on their defaults, by Claude under Rene's delegation after the tracker's double-check. The conditions: Q6, the `mms-tts-tgl` clips are CC BY-NC 4.0, so they stay out of the video, the repo and the submission (C729); Q8, `spots.json` carries its ODbL credit.
  - A builder check (Opus 5.5 at max, back at 6:06 AM) asked three questions, settled as C732 to C734 and AskL-Q9 (§13).
  - An accuracy review (Opus 5.5 at xhigh, Oct 29 evening, against MS4's committed spec and plan) found 1 Critical, 13 Important and 20 Minor problems. All are folded in under Window 4's rulings, as C735, AskL-Q10 and AskL-Q11 and the edits they name (§14).
- **Implements:**
  - design §8's MS6 row, its Nov 2 half: typed Ask Lusot (the spot list, the `get_reports` tool, 300 m and 3 hours, Nominatim through the Lambda), then voice with WAV capture. Its done-when: Ask Lusot answers 10 typed and 10 spoken test questions.
  - design C10 (voice is WAV), C11 (Nominatim on the server, with a cache, an off switch and attribution) and G1 (demo pins may be cited, each labelled "(demo)")
  - plan §4 (the Ask Lusot and voice must-haves), §9 (Ask Lusot's output rules and the vehicle rule), §12 (Table 15's two Ask routes and the question limits), §13 (spoken questions never stored by us; tool arguments and citations checked in code; the model-calls switch), Table 3's geocoding and voice rows, Table 4's voice row, Table 17's geocoding row, Table 18's two Ask rows, Table 21's two Ask rows, and Table 22's Phase 6 finish line
  - row 14 of the tracker's cross-spec audit (Oct 29): what MS4, MS5, MS7, MS8, MS9 and Window 4's privacy drafts assume about Ask (§10)
- **Builds on:**
  - MS1 on `main` (`98e8266`): the API Lambda and its `stopSwitch.ts`, the template, the Meta client's rules, and the probe's voice check (C35)
  - MS4's spec and plan on `ms4-backend-specs` (`dc136ff`: spec draft 4 with its last rulings, plan revision 2): `pins.ts`, `limits.ts`, `metroManila.ts`, the publish switch (C516), the nearby read (C509), the global caps (MS4-Q13), the demo credits (C523), CORS (§4.7) and N6's API alarm
  - MS5's spec and plan on `ms5-app-specs` (`6ca31b9`): the string tables and their review marks (C609), the wording functions, the gates (C605), the fifth navigation slot (C620), the device id (C606) and the copy tests (C608)
  - MS7 (`ms7-harden-specs`, `8be1b9e`): §5's Ask row, S2, L9, P14, the copy check (C819) and the rush (C828)
  - MS8 (`ms8-submit-specs`, `1ae4913`): C905's Ask scene, C915's agentic paragraph and N4
  - MS9 (`ms9-ms10-specs`, `406f044`): F5, F6, N6 and N8
  - Window 4's consent and privacy drafts and PRIV-Q3 (`w4-independent`: the consent texts approved on Oct 29 at `fe5e4da`, `0c6643c` and `d6e5986`, and the privacy draft at `cbdc5b3`)
- **Needs first:** MS4 merged into `main` before the wiring (pins, limits and the Metro Manila test), and MS5 merged before the screen. The probe, the spot list and most modules can be built earlier on fakes (the plan's order).
- **Not here:** MS6's evaluation (its own spec leaves Ask out), and anything that changes how depth is measured.

## 1. Intent

A driver or a commuter in the rain asks, by typing or by voice and in Taglish, how deep the water is near a place. Lusot answers only from the people's reports already on its map: the deepest one within 300 m in the last 3 hours, how many there are and how old, each at its own spot and in MMDA's terms. With no report, it says so, and never implies the way is clear.

What makes it worth judging (plan Table 21, Table 28; M33, the agentic prize) is that Muse Spark acts as a small agent with guardrails: it reads a Taglish question, decides what to look up, calls one tool, reads what comes back and says which reports answer the question. Code checks every claim, and every word a person reads comes from a fixed set of lines that Rene reviews (M20). When the model is slow, wrong or switched off, the person still gets the plain list of reports within the plan's 10 seconds.

## 2. Goals, non-goals and anti-goals

**Goals**
- `POST /ask` and `POST /ask/voice` in the API Lambda, answering within 10 s at the phone, or with the plain list (plan §12).
- The tool loop (§4.2, §4.3), place resolution through the spot list and Nominatim (§4.6), and voice from WAV capture to transcript (§4.7).
- The caps, the switches and the log line that MS4, MS7 and MS9 already assume (§4.8, §4.9, §5).
- The Ask screen in MS5's fifth slot (§4.10).
- The 10 typed and 10 spoken test questions, answered and recorded (§8).

**Non-goals**
- Free conversation, advice, weather, routes or anything beyond depth at a place.
- Reading photos. Ask reads pins only, through MS4's pin code.
- Voice output (text to speech), the Messenger bot (a plan nice-to-have), and streaming answers.
- Any change to the pipeline, the pins' fields or the evaluation.

**Anti-goals** (failures even if it works)
- An answer that says "safe" or "unsafe" or any word containing "ligtas", gives crossing or travel advice, describes a whole road or route, or names a level outside the 9 levels or a class outside MMDA's 3.
- A level, age or count that no returned report supports, or "passable" said with no report.
- A cited report the tool didn't return, or a live pin shown while the publish switch hides it.
- Audio, a question, a transcript, a location or a device id kept by Lusot, or written to a log.
- A Nominatim call from anywhere but the API Lambda, faster than 1 a second, or without its cache.
- A question that can spend Meta credits past the caps, or while `model-calls` is on.

## 3. Constraints

- CLAUDE.md's rules hold throughout. The ones that bite here: the copy rules and the exact screen line on every screen, the model IDs (`muse-spark-1.3`, `muse-voice-transcribe-1.0`, never the contributor model), only Lambda reads the key, never log exact locations, WAV only for transcription, retries only on 429, 500 and 503, Nominatim only from the API Lambda, Rene's review of every Taglish line (M20), and every Meta call on the credits.
- **Lambda concurrency:** the account limit is 10 and analysis takes up to 5 (C9). A question holds an API slot for several seconds, so it is the traffic most likely to reach the limit (MS7's C828 measures it).
- **API Gateway's HTTP API** times out at 30 s, which can't be raised. The API stage throttle is 10 a second, burst 20 (MS1).
- **DynamoDB stays inside the free 25 and 25 units.** Ask adds no table and no index: its counters, its Nominatim slots and its place cache live in MS4's `limits` table (2 and 2). The place cache is read with `GetItem`, which MS4's grants leave out (its §4.7: `PutItem` and `UpdateItem` only), so Ask adds it (C701).
- **Meta's limits** are per team: Muse Spark 3,000 requests and 4M tokens a minute; transcription 256 concurrent streams (plan Table 16).

### What the sources say (read Oct 29)

| # | Fact | Source |
|---|---|---|
| F1 | **Tool calls in the Responses API:** a function tool is flat (`type`, `name`, `description`, `parameters`, optional `strict`). The model's call comes back as a `function_call` item with `call_id`, `name` and JSON `arguments`. The result goes back as a `function_call_output` item with the same `call_id`. `tool_choice` accepts only `"auto"`: `"none"`, `"required"` and a named function return HTTP 400. `parallel_tool_calls` defaults to true and can be turned off. | dev.meta.ai: Tool calling |
| F2 | **Stateless turns:** with `store: false`, the server keeps no copy of the conversation. The client resends the conversation each turn, with reasoning carried as encrypted items: `include: ["reasoning.encrypted_content"]`, and each replayed reasoning item needs a `summary` field. `include` can't be combined with `previous_response_id` (HTTP 400). Without `previous_response_id`, every `function_call_output` must match a `function_call` in the same request. | dev.meta.ai: Responses API protocol |
| F3 | **Reasoning:** `minimal` to `max`; `none` returns HTTP 400 for Muse Spark; without the field the model picks its own level. Reasoning tokens are billed as output, and `max_output_tokens` (at least 16) covers reasoning and the visible answer together. MS1's photo answers at the default effort took a median of 24.7 s, and about 95% of their output was reasoning. | dev.meta.ai: Reasoning, Responses API protocol; MS1 probe note §4 |
| F4 | **Structured output** uses `text.format` with `strict: true` (MS1's `judge` uses it). The Tool calling page documents tools with structured output only through Chat Completions' `response_format`; the Responses pages don't say whether tools and `text.format` work in the same request. | dev.meta.ai: Structured output, Tool calling |
| F5 | **File transcription:** `POST /v1/asr/transcribe`, multipart with a JSON `request` part (`model`, `audioEncoding: "WAV"`, `mode`, default `PUSH_TO_TALK`, `keywords`, and `languageBias` as language names such as `["English"]`) and an `audio` part. WAV only: mono 16-bit PCM at 16 or 24 kHz, up to 10 minutes and 32 MB. Keywords bias recognition but don't guarantee spelling, and no limit on their number is documented. Undocumented, found Oct 31 (C740): a keyword over 30 characters gets a 400 (`invalid_request_error`, "ASR keyword 3 exceeds the maximum length of 30 characters"), and 94 keywords were accepted (the voice diagnostic's call 6, HTTP 200); on Nov 1, 97 were (C741). No `store` or retention setting is documented. $0.18 an hour, billed by whole seconds; failed and 429 requests aren't billed. The response holds `transcript` and `audioDurationMs`. | dev.meta.ai: Speech to text, Voice schemas |
| F6 | **MS1's voice check:** a synthetic English WAV of 3.7 s came back word for word in 1.99 s, with "Espana" spelled "España". No Taglish clip has been tried, because M12's recordings don't exist yet. | MS1 probe note §7; C35, C41 |
| F7 | **Nominatim's usage policy:** at most 1 request a second; a User-Agent or Referer that identifies the application (stock library agents are refused); cache results; show attribution; no autocomplete; an app must be able to switch the service off at OSMF's request; a client that repeats the same query may be blocked. | operations.osmfoundation.org, Nominatim usage policy |
| F8 | **`store: false` on Muse Spark** is accepted and echoed (MS1's R76; Window 4's PRIV-Q6). | MS1 spec §8; privacy draft |

## 4. What gets built

### 4.1 The flow

**A typed question** (`POST /ask`):
1. Check the body (§5.1).
2. Count the question against the device limit, then the global cap (§4.8). A refusal costs nothing.
3. If `model-calls` is on, answer with the plain list (§4.5), with no Meta call.
4. Otherwise run the tool loop (§4.3) under the time budget below. Whatever stops it, the person gets an answer: the model's, or the plain list.
5. Write one log line (§4.9) and return the answer (§5.3).

**A spoken question** (`POST /ask/voice`) checks the WAV and reads `model-calls` first: while it is on, the answer is a 503 `voice_paused`, before anything is counted, because transcription is a Meta call. Then it counts the question, transcribes the clip (§4.7) and goes on as a typed question with the transcript. The response carries the transcript, so a misheard place is easy to spot (plan §9).

**The time budget** (C708), counted from the handler's start:

| By | What must be done |
|---|---|
| 4.0 s | the transcript, for a spoken question; otherwise a 503 `voice_failed` |
| 7.5 s | the model's last turn. Every Meta call carries this deadline, and a retry that would end after it isn't made. Nominatim is asked only with at least 2.5 s left. The final turn starts only with at least 1.5 s left, and without it the answer comes from turn 1's call (§4.3). |
| 8.5 s | the answer returned, the plain list included; otherwise a 503 `ask_unavailable` |

The phone sees the answer within about 9 to 9.5 s at worst, inside plan §12's 10 s, with room for the network and a cold start. The budget's clock starts at the handler, while the 10 s promise is at the phone (MS7's L9). For a spoken question, the clip's upload (about 640 KB of base64 for 15 s) comes before the handler's clock starts, so on a weak connection the phone can wait past 10 s; AK3 records the upload time apart, so that is measured, not assumed. The API function's timeout rises from 10 s to 15 s only as a backstop, so a slow plain list still reaches the person instead of API Gateway's error (C701). The probe (C731) measures the real turn times and may move these numbers, by a recorded ruling within C734.

### 4.2 The tool: `get_reports`

One function tool, as plan §9 and Table 15 name it (C702). Its call carries the lookup and the model's reading of the question, so the call alone holds everything the answer's crossing and vehicle lines need, with only the citations left (C734):

| Argument | Type | Meaning |
|---|---|---|
| `place` | string | the place as the person named it: a corner, a landmark, a street or an area, copied from the question. Empty when `here` is true. |
| `here` | boolean | true for a question about where the person is ("dito", "here", "near me") |
| `since_minutes` | integer | how far back to look: 180, unless the person states a shorter time |
| `kind` | `depth` or `crossing` | as in the answer schema (§4.3) |
| `vehicle` | `light`, `heavy`, `on_foot` or `none` | as in the answer schema (§4.3) |

**What code does with a call:**
1. **Checks the arguments.** `place` is cleaned (§4.6). `since_minutes` is clamped to 1 to 180, and a value under 180 counts only when the question itself states a time, such as "in the last hour" or "30 minuto", and never below that stated time: "in the last 2 hours" with the model's 30 keeps 120. Otherwise the window stays 180, so a "ngayon" can't shrink it and hide the deepest report (C732).
2. **Finds the point** (§4.6): the phone's location for `here`, or the spot list, then Nominatim, for `place`.
3. **Checks it** with MS4's `inMetroManila` first. A point outside answers `outside_metro_manila` (plan §13: tool arguments stay inside Metro Manila and the last 3 hours), even when the result is wide: a town such as Bacoor resolves to an area far wider than 300 m, and "too broad" would be the wrong answer. Then a place inside Metro Manila that is wider than the 300 m circle answers `place_too_broad` (C733).
4. **Reads the pins** through MS4's `pins.ts`, as nearby does (MS4's C509): published pins within 300 m whose `visibleUntil` hasn't passed, from the nine-cell read, at most 200 pins, newest first. The publish switch acts inside that read, so live pins vanish while it is on and demo pins stay (C516, MS4-Q7).
5. **Keeps live pins captured within the window,** re-ranked deepest first (the 9 levels in MS3a's order; a tie goes to the newer photo). Demo pins skip the window and are kept apart (C707).
6. **Answers the model** with summaries only, at most 5 live reports and 3 demo pins, the same ones the answer shows: a ref (`r1` for the deepest live report, then `r2`…, and `d1`… for demo pins), the level, `level_is_floor`, the class, the minutes since the photo (live) or its year (demo), and the distance in metres. Each result numbers its refs afresh, and the answer cites the last result's. **No coordinates and no report ids reach Meta.** The point stays in the Lambda, so a "dito" location never leaves it except as distances to pins Meta can't place (C720).

The tool's own answer is one of `ok`, `place_not_found`, `place_too_broad`, `outside_metro_manila`, `no_location` or `lookup_unavailable` (Nominatim busy, off or failing, or the place cache unreadable). The model may call the tool a second time, for example with a simpler place name after `place_not_found`, but never a third (C703).

### 4.3 The model's turns

Muse Spark (`muse-spark-1.3`) runs at most three turns for one question, each a stateless Responses call (F2) with `store: false`, `include: ["reasoning.encrypted_content"]`, `reasoning.effort` `minimal` (the probe may choose `low`), `parallel_tool_calls: false`, `tool_choice: "auto"` (F1), `max_output_tokens` 1,200 (C739; 800 until Oct 31), the versioned instructions, the tool, and the answer schema in `text.format` with `strict: true` (C703, C714).

1. **Turn 1** sends the question and one line saying whether the person shared their location. The model either calls `get_reports` or, for a question that isn't about flood depth at a place, answers `off_topic` without a call.
2. **The final turn** resends the question, the model's reasoning items, its call and the tool's output. The model answers with its citations, or calls the tool once more, and the turn after that answers.

**The answer schema** (`ask_answer_v1`), which with the tool's arguments is all the model writes (C704):

| Field | Values |
|---|---|
| `kind` | `depth`; `crossing` (it asks whether to cross, pass, go or drive through, or whether going is risky or dangerous, in any language); `off_topic` |
| `vehicle` | `heavy` (a truck or a bus); `on_foot` (walking or wading); `light` (any other vehicle, or unsure: plan §9's stricter class); `none` (no vehicle or walking mentioned) |
| `cited` | the refs of the reports that answer the question |

**How a question can end** (C734):
- **Turn 1 must give a valid call, or a valid `off_topic` answer.** Otherwise the plain list answers (§4.5): the budget ran out first (`deadline`), Meta failed (`model_error`) or rejected the key or the account (`key_rejected`), the call or the answer failed code's checks (`invalid_answer`), or the model answered `depth` or `crossing` without a call (`no_tool_call`).
- **The final turn only adds the citations.** It runs when at least 1.5 s remain after the tool. Its `cited` must be a subset of the last result's refs and include `r1` while live reports exist (plan §13; C705), and its `kind` can't be `off_topic`, which would hide the reports a call already found. If the turn doesn't run, fails, or fails that check, the answer is built from the last call's arguments with no citations: still `source: "model"`, without the "Used" marks. A late or confused final turn costs only those marks, never the crossing line or the vehicle line.
- **A third tool call isn't made.** The answer uses the second call's result and arguments, without citations.

**What code takes from the model** (C711, C712). Code can make the model's reading stricter, never looser:
- **`crossing`** is on when either call's or the answer's `kind` is `crossing`, or the question matches the crossing words.
- **`on_foot`** holds only when the question has a walking word ("lakad", "maglakad", "walk", "lumusong"), as `heavy` needs a truck or bus word, and no call or answer says `light` or `heavy` (C737). A model-only `on_foot` falls back to `none`, since a wrong `on_foot` would drop every class line: `none` keeps the class lines and adds no vehicle line, and code can't tell from the words alone whether a car was named.
- **`heavy`** holds only when the model says so, in either call or the answer, and the question names a truck or a bus ("truck", "trak", "bus"). A `heavy` without such a word, and any other vehicle, is `light`, plan §9's stricter class.
- **`none`** otherwise.

The walking, heavy-vehicle and time words sit beside the crossing words in `ask_v1.words.json` (C725).

If Meta refuses `text.format` beside tools (F4), each turn has a second form, also stateless and never `store: true` (C714):
- **Turn 1** sends the tools with no `text.format`. Besides `get_reports`, it offers a second function, `not_about_flood_depth()`, which the model calls for an off-topic question, so `off_topic` still comes back as a call that code can check.
- **The final turn** sends the question and the tool's output as plain input, with no tools, and keeps the schema.

The probe (C731) tries both turns in both forms.

### 4.4 The answer

The API returns data, never prose (§5.3). The app renders every line from MS5's string tables, in the language the person chose, with MS5's own wording functions for the level and class lines, so a pin and an answer never word one reading two ways (C724). Every line here is an English draft for Rene's review (M20). Every new `ask.*` line, English and Taglish, starts `reviewed: false` (MS5's C609), and the screen-line keys show in English until he has reviewed them (MS5's C619).

| Part | When | English draft |
|---|---|---|
| The crossing line | first, whenever the model says `crossing` or the question matches the crossing words (C711) | "I can't tell you whether to cross or go through." The screen line stays in view, as on every screen. |
| The summary | `reports` | "3 reports within 300 m of España Blvd cor. Maceda St in the last 3 hours." ("1 report…" for one). The place is always a point's name: a listed spot, a small landmark, or "you" (C733). |
| The deepest report | `reports` | MS5's level line, such as "Knee deep at this spot (MMDA level).", then MS5's class line, then "Photo taken 25 min ago, 120 m from España Blvd cor. Maceda St." ("… from you" for "dito"), the age from MS5's `ageText` |
| The vehicle line | the model's answer, `light` or `heavy` | "For MMDA's classes, Lusot counts your vehicle as a light vehicle." or "… as a heavy vehicle." With `heavy`, the crossing line also shows directly under the class line, so "not passable to light vehicles" never reads as permission (AskL-Q10's default). |
| On foot | `on_foot` | No class line on any report, and "MMDA's classes are for vehicles, so this answer gives the level only." (plan §9) |
| More reports | up to 4 more live reports, deepest first | the same card, shorter; the ones the model cited are marked "Used" |
| Demo pins | up to 3, nearest first | "(demo)", MS5's level line, the photo's own date and place, and its credit line (G1, MS5's C618). A demo pin without a credit line isn't shown (MS5's N2). |
| No report | `no_reports` | "No recent reports within 300 m of {place} in the last 3 hours." For "dito", in Taglish, plan §9's "Walang recent report dito."; in English, "No recent reports near you in the last 3 hours." Then always: "No report doesn't mean no flood." Never "passable". Demo pins follow, if any. |
| Too broad | `place_too_broad` | "That's a whole street or area. Ask about a corner or a landmark on it, or turn on your location and ask about "dito"." Then up to 3 listed spots on it, to tap. |
| No place | `no_place` | "I couldn't find that place in Metro Manila. Name a corner or a landmark, or turn on your location and ask about "dito"." |
| Lookup busy | `lookup_unavailable` | "I couldn't look up that place just now. Try again in a minute, or name a nearby landmark." Busy isn't "not found". |
| Outside | `outside_metro_manila` | "Lusot answers only about spots in Metro Manila." |
| No location | `no_location` | "Turn on your location to ask about "dito", or name a place." |
| Off topic | `off_topic` | "I can only answer about flood depth near a place in Metro Manila, from recent reports." |
| Nothing heard | `no_speech` | "I didn't catch a question. Try again, or type it." |
| The plain list's note | `source: plain_list` | "Here is the plain list of reports." |

Each report card links to its pin (MS5's `#/pin/<id>`), so the person can see the photo and its overlay. A spoken question shows "You asked:" and the transcript above the answer. The transcript is the person's own words, shown as theirs, except that a banned word in it ("safe" in any form, or "ligtas") is masked, each letter shown as "•", so no Lusot screen shows one (AskL-Q11's default). The place heard stays.

### 4.5 The plain list

The plain list is the same answer without the model's parts: no vehicle line and no "Used" marks, the crossing line only from the crossing words, all live reports deepest first (at most 5), the demo pins, and the plain list's note. It costs no Meta call (C709).

**When:** `model-calls` is on (`model_calls_paused`), or turn 1 gives no valid call or `off_topic` answer (§4.3): the budget runs out first (`deadline`), a Meta call fails after its retries (`model_error`), Meta rejects the key or the account (`key_rejected`), or the call or the answer fails code's checks (`invalid_answer`, `no_tool_call`). A failed final turn never brings the plain list: it only drops the citations.

**Its place:**
- If the model's tool call already found a point, the plain list uses it.
- Otherwise code looks for one itself. It takes the longest spot-list name found in the question, accents folded. A "here" word, or no spot found while a location was sent, means the phone's location. Nothing found gives `no_place`.
- The plain list never calls Nominatim: without the model, code can't tell which words form a place.

### 4.6 Places

The order (C713):
1. **`here`:** the location the app sent, with an accuracy of 100 m or better (§5.1). Without one, `no_location`.
2. **The spot list** (`backend/api/src/data/spots.json`, C715): each spot has an id, a display name, its city, one point, the roads it sits on, and its aliases. A spot is one point and is named as one: a corner, a landmark, or "in front of" a landmark, never a stretch of road. A bare road name finds a spot only when the list has one spot on that road. With several, the answer is `place_too_broad`, offering those spots. Matching folds case and accents ("Espana" is "España", MS1's probe note), drops punctuation, treats "cor.", "corner", "&" and "at" between two names alike, and prefers the longest alias found.
3. **Nominatim,** for a place the list doesn't have (C714):
   - **Only from the API Lambda,** and only when a question is sent, never as the person types (no autocomplete, F7).
   - **One request a second across every Lambda:** one item, `nominatim#last` in `limits`, holds the last request's write time in milliseconds. A request goes only after a conditional `PutItem` of it succeeds, on `attribute_not_exists(pk) OR writtenMs <= now - 1100`: a single-item conditional write is atomic, so no two requests fall less than 1.1 s apart, and the extra 100 ms covers small clock skew between Lambdas (the tracker's ruling under Rene's delegation, Oct 30, 6:46 PM, after Task 5's review found the per-second items let two Lambdas send 2 to 4 ms apart, simulated closed). A taken slot waits for the next one if the budget allows, and otherwise gives `lookup_unavailable`.
   - **The cache:** first in the Lambda's memory, then in `limits` under `geocode#<SHA-256 of the normalised place>`, read with `GetItem` (C701), for 7 days for a found place and 1 day for a miss, so a repeated query never repeats a request. The reader checks the item's `expiresAt` itself, since DynamoDB's TTL deletes days late (as MS4's C526 does). A failed cache read never sends a Nominatim request: that place answers `lookup_unavailable`, logged by its error name. The cache holds the hash, the name OpenStreetMap gives and the point, never the text that was asked (AskL-Q3).
   - **The request:** `/search` with `format=jsonv2`, `limit=1`, `countrycodes=ph`, Metro Manila's bounding box as a preference (`bounded=0`, so a place outside still resolves and `inMetroManila` can say it is outside), and `accept-language=en`. Its own timeout is 1.5 s.
   - **Points only** (C733): after the `inMetroManila` test on its point (§4.2, step 3), a result whose bounding box spans more than 300 m corner to corner is a street or an area, not a point. The answer is then `place_too_broad`, offering the listed spots inside that box, so Lusot never answers "within 300 m of" a whole road or barangay.
   - **The User-Agent** names the application, `Lusot/1.0`, with the live site's address once it exists. It never holds an email address (CLAUDE.md).
   - **The switch:** `/lusot/stop/nominatim`, a fourth stop switch in the template, read like the other three (MS1's `stopSwitch.ts`). When it is on, only the spot list resolves places. It is the off switch C11 asks for, and the one OSMF may ask for (F7).
   - **Attribution:** an answer whose place came from Nominatim says "Place search © OpenStreetMap contributors" under it.
4. **Every point** must pass MS4's `inMetroManila`, before any breadth test.

### 4.7 Voice

**In the app** (C718):
- The mic button starts a recording on a tap and stops it on a second tap, or at 14.9 s, so a full-length clip never crosses the server's 15 s limit by an audio quantum (plan §12 and Table 4: up to 15 s). A countdown shows the seconds left.
- The app records through the Web Audio API, not `MediaRecorder`, whose formats Meta doesn't take. It downsamples to 16 kHz mono in its own code, encodes 16-bit PCM WAV, and sends it as base64 in JSON (§5.2).
- The audio lives in memory only. It is dropped once the answer arrives or the screen closes, and is never written to `localStorage`, IndexedDB, the cache or a file.
- The APK declares Android's `RECORD_AUDIO` and `MODIFY_AUDIO_SETTINGS`: Capacitor's WebView requests both together for audio capture and refuses it if either is missing. A refused microphone gets a line that offers typing instead.

**On the server** (C719):
- The header must say RIFF/WAVE, PCM, mono, 16 bits, 16,000 or 24,000 Hz, with 0.5 to 15 s of audio. Anything else is refused before any Meta call (§5.4).
- `muse-voice-transcribe-1.0` receives the clip with `mode: "PUSH_TO_TALK"`, `languageBias: ["Tagalog", "English"]` (the probe confirms the names Meta takes), and as `keywords` (plan Table 4) the spot list's display names of at most 30 characters, then three short forms for long names (C741), then each spot's `roads`, each once and each of at most 30 characters, at most 97 in all, names first (C740), a length counted in UTF-8 bytes. On Oct 31 Meta took `["Tagalog", "English"]` as written, the 21 short names alone, and a list of 94; on Nov 1 it took this list of 97. A test pins that exact list, so a spot or road added later fails it before a deploy.
- The audio stays in the Lambda's memory, goes only to Meta, and is never stored, logged or kept after the answer (plan §13). No `store` setting exists for transcription (F5), so the notice and the policy say that Meta receives the audio and may keep it (§4.9).
- An empty transcript answers `no_speech`. A failed or late transcription answers a 503 `voice_failed`, and the app offers typing.

**M12 is synthetic** (C729; Rene's decision, Oct 29, about 10:46 PM, relayed by the tracker). In place of recordings from 10 adults, the 10 spoken questions are text-to-speech clips in Taglish with street noise mixed in, and every report of them says so. Claude drafts the 10 question scripts, each with the place it means, and Rene reviews them before any clip is made (his rule: Claude annotates first, he reviews). **The engine:** Meta's MMS text-to-speech for Tagalog, `facebook/mms-tts-tgl` (VITS, about 36M parameters, 16 kHz output, run locally with Hugging Face Transformers), licensed CC BY-NC 4.0. The clips are private test data, never shipped or shown, so the non-commercial licence fits; its known weakness is that English words in Taglish are read with Tagalog phonetics, which the results note states. A fixed seed makes each clip reproducible, since the model's durations are random. **The noise:** a CC0 street recording, or generated pink noise if none suits, mixed with FFmpeg at a stated signal-to-noise ratio, then written as 16 kHz mono 16-bit WAV. Synthetic voices are an easier test than real speakers, so AK2's count of places heard right is reported as a synthetic result, never as a test of real voices (plan M12's caution). If voice stays weak on Taglish, plan Table 18's fallback holds: typed questions stay the main path, the transcript stays visible, and voice can leave the video (Rene's call, MS8).

### 4.8 Limits, caps and switches

| Rule | Value | Refusal |
|---|---|---|
| Per device | 20 questions per UTC clock hour, typed and spoken together (plan §12) | 429 `{"error": "question_limit"}`, with `Retry-After` in seconds to the next hour |
| In all | 60 questions per UTC clock hour (C738; MS9's N8 had 300, after MS4-Q13's 300 uploads) | 429 `{"error": "question_cap"}`, with `Retry-After` |

- **The device id** comes from `X-Lusot-Device`, which MS5 sends (C606). A missing or malformed id counts in MS4's shared `none` bucket (C508).
- **The order:** the device first, then the global cap, so one device's refused questions never use up the cap (C716). A global refusal gives the device's count back, as MS4's `take` does (its §4.6). Both counts go through MS4's one `take` call, with a `question` bucket whose refusals carry Ask's codes.
- **What counts:** every question that passes its checks counts once, before any Meta or Nominatim call, whatever path answers it. A spoken question refused for `voice_paused` doesn't count.
- **Where:** MS4's `limits` table, keyed by the SHA-256 of the device id, never the id (C520), with its 2-hour TTL.
- **The app** never retries `question_limit` or `question_cap`, and shows a line for each. A 429 without one of Lusot's codes is API Gateway's throttle, retried once (C635). Ask's client retries nothing else: never a 503 (`voice_failed` or `ask_unavailable` were counted, and may have been paid), and never a request already sent when the connection drops, since the server may have counted and paid for it. So `ask` and `askVoice` don't use MS5's `retryOnce`, which also retries 503s and network errors.
- **The cap alarm** (C727): a metric filter on the API log counts `question_cap` refusals by that term (the function logs in Lambda's text format, so a JSON filter wouldn't match), and an alarm emails Rene through MS1's topic when any happen in an hour, with `OKActions`.
- **MS4's API alarm** (the tracker's N6, from MS9) stays at 5,000 invocations an hour, which this spec sets (C735).

| Switch | Effect on Ask |
|---|---|
| `/lusot/stop/model-calls` | a typed question gets the plain list, with no Meta call; a spoken one gets a 503 `voice_paused` |
| `/lusot/stop/publish` | live pins vanish from every answer, inside MS4's read; demo pins stay (MS4-Q7) |
| `/lusot/stop/nominatim` (new) | places resolve from the spot list only |
| `/lusot/stop/uploads` | no effect |

As everywhere, only an explicit `off` lets work through, an unreadable switch counts as on, and each Lambda caches a switch for 30 s (MS1).

### 4.9 Privacy and logs

**Who receives what** (C720):

| Recipient | Receives | Never receives |
|---|---|---|
| Meta, Muse Spark | the question or the transcript; whether a location was shared; the tool's summaries (level, class, minutes, distance) | coordinates, report ids, the device id |
| Meta, transcription | the WAV clip and the spot and road names as keywords (C740) | anything else |
| OpenStreetMap's Nominatim | the place as the model copied it from the question, from the Lambda's address | anything about the person |
| Lusot's storage | the counters (hashed device id), the Nominatim slots and the place cache (§4.6) | the question, the transcript, the audio, the location |

Every Muse Spark request sends `store: false` (F2, F8). Transcription has no such setting (F5). Meta's speech page mentions zero data retention, priced like standard use, without saying how a team gets it.

**The notice** (C722): MS5's gate shows the 18+ check and Window 4's consent notice before the first question, as before the first upload (C605). The Ask screen adds one short line under the box, "Your question goes to Meta's AI service. Lusot doesn't keep it.", linked to the privacy policy. Window 4's texts gain Ask's facts as AskL-Q3 settles them (§10).

**The log line** (C721): one JSON line per question in the API log, kept 14 days:

| Field | Holds |
|---|---|
| `msg`, `route` | `"ask"`; `"ask"` or `"ask_voice"` |
| `status`, `code` | the HTTP status, and the error code if any |
| `source`, `fallback`, `kind` | the answer's (§5.3) |
| `crossing` | `"model"`, `"words"`, `"both"` or null |
| `vehicle`, `place_source` | the answer's vehicle; `spots`, `nominatim`, `here` or null |
| `nominatim` | `cache`, `called`, `not_found`, `busy`, `off`, `failed` or null |
| `reports`, `demo`, `cited`, `tool_calls` | counts |
| `final` | the final turn: `ok`, `skipped` or `failed`; null when there was none |
| `meta_calls` | Meta calls made, transcription included, failed ones counted, as in the analysis log (MS3a's C80) |
| `meta_status` | the HTTP status of the Meta error that ended the model path, or null for a timeout or a lost connection; absent when none failed (MS3a's C73) |
| `input_tokens`, `output_tokens`, `reasoning_tokens` | summed over the turns |
| `audio_ms`, `transcribe_ms`, `model_ms`, `ms` | durations |
| `error` | an error's class name, for a 500 |

**Never logged:** the question, the transcript, the audio, any place text or spot id, coordinates, the device id or its hash, the IP address, report ids or refs, Meta's error text and the key. A sentinel test proves it (§8).

### 4.10 The Ask screen

- **Where:** MS5's fifth navigation slot, `#/ask` (C620), behind MS5's gate (C605), with the screen line visible without scrolling, as on every screen (C608).
- **What it holds:**
  - a question box of up to 300 characters with a send button
  - the mic button (§4.7)
  - a "Use my location" switch, off by default, which takes a fix of 100 m or better before a question is sent and explains a poorer one
  - three example questions to tap, such as "Gaano kalalim ang baha sa España cor. Maceda?" and "May baha ba dito?", each naming a point, never a bare road (C733)
  - the answer (§4.4), the transcript of a spoken question, and the attribution line
  - the notice line (§4.9)
- **Its lines** live under `ask.` keys in MS5's tables. The answer's lines are `ask.answer.*`, which MS5's `isScreenLineKey` treats as screen-line keys (C724; the name follows the tracker's ruling of 9:50 PM by its clock, §14).
- **The visual work** loads `ui-ux-pro-max` and `frontend-design`, as CLAUDE.md asks, and follows MS5's tokens.

### 4.11 Cost

| | Meta cost | Notes |
|---|---|---|
| A typed question | about $0.005 | two turns at minimal effort, about 2,400 input and 300 output tokens (an estimate; the probe measures it) |
| A spoken question | about $0.006 | plus up to $0.00075 for 15 s of audio |
| The plain list | $0 | no Meta call |
| The planning figure | $0.01 a question | MS7's C828 and MS9's N8 use it; the global cap then bounds Ask at about $3 an hour |
| Ask's own build and tests | at most $1 | the probe, the 20 questions and the cloud check, with a running total in the results note (C730) |

Nominatim is free. A question's Lambda time is a few GB-seconds, inside the free tier.

## 5. The contract

Other specs depend on these names. They change only through this spec.

### 5.1 `POST /ask`

- **Headers:** `Content-Type: application/json`; `X-Lusot-Device` (MS5's random id).
- **Body:** `{"question": string, "here"?: {"lat": number, "lng": number, "accuracyM": number}}`
  - `question`: 1 to 300 characters once trimmed
  - `here`: sent only while "Use my location" is on; `lat` and `lng` as MS1's upload checks them, and `accuracyM` from 0 to 100
- **200:** `{"answer": Answer}` (§5.3)

### 5.2 `POST /ask/voice`

- **Body:** `{"audio": string, "here"?: {...}}`, where `audio` is the base64 of a WAV file (§4.7). The body is at most 1.1 MB.
- **200:** `{"answer": Answer, "transcript": string}`. The transcript is empty for `no_speech`.

### 5.3 The answer

| Field | Type | Meaning |
|---|---|---|
| `source` | `"model"` or `"plain_list"` | who chose the parts |
| `fallback` | null, or `model_calls_paused`, `deadline`, `model_error`, `key_rejected`, `invalid_answer`, `no_tool_call` | why the plain list answered |
| `kind` | `reports`, `no_reports`, `place_too_broad`, `no_place`, `lookup_unavailable`, `outside_metro_manila`, `no_location`, `off_topic`, `no_speech` | which answer (§4.4) |
| `crossing` | boolean | show the crossing line first |
| `vehicle` | `light`, `heavy`, `on_foot`, or null | the vehicle after code's checks (§4.3); null in the plain list and when none was mentioned |
| `place` | `{"name": string, "source": "spots" \| "nominatim" \| "here"}`, or null | the place used; `name` is the spot's display name, OpenStreetMap's name, or "here" |
| `windowMin`, `radiusM` | integers | the window used (at most 180) and 300 |
| `count` | integer | live reports in the window within 300 m |
| `reports` | list | live reports, deepest first, at most 5 |
| `demo` | list | demo pins within 300 m, nearest first, at most 3 |
| `deepestId` | string or null | the report the summary is about |
| `cited` | list of ids | what the model cited, after code's checks; empty in the plain list, and when the final turn didn't run or failed |
| `suggestions` | list of strings | for `place_too_broad`, up to 3 listed spots' display names; otherwise empty |

Each report in `reports` and `demo` is MS4's public pin (its §4.4 fields, inches only once the gate shows them, and a demo pin's `credit`, `place` and `event`, MS4's C523), plus `distanceM`, an integer.

### 5.4 Errors

| Status | `error` | When | Counted |
|---|---|---|---|
| 400 | `bad_request`, with `detail` | malformed JSON, a question that is empty or too long, bad `here` fields (MS1's shape) | no |
| 400 | `bad_audio` | not base64, not a WAV of the right format, or a body over 1.1 MB | no |
| 422 | `audio_too_short`, `audio_too_long` | under 0.5 s, over 15 s | no |
| 429 | `question_limit` | the device's 21st question in the hour | no |
| 429 | `question_cap` | the 61st question in the hour, in all | no |
| 503 | `voice_paused` | `model-calls` is on, for a spoken question | no |
| 503 | `voice_failed` | transcription failed or ran past 4 s | yes |
| 503 | `ask_unavailable` | the pins couldn't be read by 8.5 s | yes |
| 500 | `internal` | anything else (MS1's handler) | yes |

The API's CORS exposes `Retry-After` (audit row 23), so the app can read it.

## 6. Calls (Claude's, C700 onward)

| # | Call | Why |
|---|---|---|
| C700 | **Ask's boundary.** Ask owns the two routes, the tool, the model loop, place resolution with the spot list and Nominatim, the question caps, voice from the app's capture to the transcript, the Ask screen and the test questions. It reads pins only through MS4's `pins.ts`, adds no table, and changes no pin field. | Design §8 gives MS6 Ask, and MS4 (its §9) left exactly these to this spec. |
| C701 | **Ask runs in the API Lambda,** as plan §5 and Figure 1 have it. The API role gains `ssm:GetParameter` on the model key, read on the first question and cached, and `dynamodb:GetItem` on `LimitsTable` for the place cache and the Nominatim slot's previous-second read (§4.6); MS4 grants only `PutItem` and `UpdateItem` there (its §4.7), so Ask's template task adds `GetItem` and updates MS4's `test_roles`. The function's timeout rises from 10 s to 15 s as a backstop (AskL-Q7). Ask's two new variables are read lazily on its own path, so MS4's missing-variable test keeps its seven names. | MS4's N6 alarm and MS9's checks (F5, §4.2) already read the API function. Only the 8.5 s budget, not the timeout, should end a question. A cache that can't be read would either call Nominatim on every repeat, against its policy (F7), or fail every place. |
| C702 | **One tool, `get_reports(place, here, since_minutes, kind, vehicle)`.** Only turn 1's second form (§4.3), used if Meta refuses tools beside `text.format`, adds a function with no arguments, `not_about_flood_depth()`, which stands in for the `off_topic` answer and reads nothing. Code finds the point, so the model never sees coordinates or report ids, only refs and distances. The call also carries the model's reading of the question (C734). | Plan §9 and Table 15 name one tool. A model that never holds a location can't leak one. |
| C703 | **At most three stateless turns and two `get_reports` calls,** with `tool_choice: "auto"` and parallel calls off. A third call isn't made. A `not_about_flood_depth` call ends the question as `off_topic` and counts as no lookup. | Meta accepts only `"auto"` (F1), so code ends a loop the model won't. Two calls allow one retry with a simpler place name, inside the budget. |
| C704 | **The model writes no answer text.** Besides its tool call's arguments, it returns `kind`, `vehicle` and `cited` in a strict schema, and the app writes every line from reviewed tables (AskL-Q1). | M20 asks Rene to review every Taglish line before release, which free text can't meet. Plan §9's rules then hold by construction. |
| C705 | **The answer is bounded by the tool's results.** The summary is the deepest live report within 300 m in the window, its age and the count, all chosen by code. `cited` must be a subset of the last result's refs and include the deepest, or the answer keeps no citations (C734). | Plan §9 and §13. A model that understated the deepest report would hide the most dangerous reading (C17's reasoning). |
| C706 | **No report says so plainly,** and adds "No report doesn't mean no flood." It never says "passable". | Plan §9. An empty map in a downpour can mean nobody has reported yet. |
| C707 | **Demo pins are listed apart,** labelled "(demo)" with their own date and credit, outside the 3-hour window, and never as the summary (AskL-Q4). | G1 lets Ask cite them with a label. A 2009 photo shown as the latest reading would mislead. |
| C708 | **The time budget:** transcription by 4 s, the model by 7.5 s, the answer by 8.5 s (§4.1). | Plan §12's 10 s at the phone, with room for the network and a cold start. |
| C709 | **The plain list** answers when `model-calls` is on or turn 1 fails (§4.5), with code's own place finding and no Nominatim. | Plan §12 and Table 18. Without the model, code can't tell which words are a place. |
| C710 | **Retries stay inside the budget.** Only 429, 500 and 503, with backoff and jitter; a `Retry-After` past the deadline means no retry. At most 3 tries a call. A 401, 402 or 403 drops the cached key, answers with the plain list (`key_rejected`) and logs `meta_status`. | CLAUDE.md's retry rule, within a 10 s promise. Meta's 503s have asked for 60 s waits (Oct 28 log). MS3a's C73 treats the same codes as account faults, and MS9 reads 402s from the logs. |
| C711 | **Crossing and risk questions get the crossing line first:** "I can't tell you whether to cross or go through." The model's `kind`, in its call or its answer, or a fixed word list (such as "tawid", "dumaan", "lusot ba", "ligtas", "cross", "safe"), turns it on, so the plain list shows it too. On foot, no class line appears. | CLAUDE.md bans crossing advice, and no such line exists yet, so this spec drafts one for M20. Two triggers mean a model outage can't drop it. Plan §9 gives people on foot the level only. |
| C712 | **Vehicles map to MMDA's classes only, and code can only make them stricter** (§4.3): `heavy` needs a truck or bus word in the question, `on_foot` needs a walking word (a model-only `on_foot` is `none`), and any other vehicle, or an unsure one, is `light` (plan §9). Each has one fixed line, and a `heavy` answer also shows the crossing line under the class line (AskL-Q10). | W11: no vehicle verdict. A `heavy` beside "not passable to light vehicles" can read as permission to go, wrong or right (the accuracy review), and a wrong `on_foot` would drop every class line (the builder check). MS8's C905 has Rene say he drives a sedan. |
| C713 | **Places resolve in this order:** here, the spot list, Nominatim. Every point passes `inMetroManila`, and every answer names the point it used (C733). | Plan §9 and Table 3. The list is instant and free. |
| C714 | **Nominatim's rules** (§4.6): the API Lambda only, a named User-Agent, one request a second across all Lambdas, a memory and table cache (7 days, misses 1 day), a bounding-box preference, no autocomplete, attribution, and a fourth stop switch. | Design C11 and the usage policy (F7). A per-Lambda limit can't hold 1 a second when several Lambdas run. The slot is one conditional item, at least 1,100 ms apart (the tracker's ruling under Rene's delegation, Oct 30, 6:46 PM, after Task 5's review found the per-second items let two Lambdas send 2 to 4 ms apart, simulated closed). |
| C715 | **The spot list** holds 40 to 80 Metro Manila spots (built with 31 on Oct 30: every alert-index location that could be placed, with the 16 left out and their reasons in `SPOTS_SOURCE.md`; 31 accepted on Oct 31 under D7, then approved by Rene, Oct 31, 12:24 PM), from MMDA's alerts in the alert index and MMDA's own published list if one is found, read as a person would. Its points come from a downloaded OpenStreetMap extract, processed on the laptop, never from Nominatim. Each spot is one point, named as one, with the roads it sits on. It is shared under ODbL with its credit, and its names are the transcription keywords (AskL-Q8; since C740, the names of at most 30 characters and the roads, and since C741 three short forms). | Plan §20 puts `spots.json` beside the API. CLAUDE.md allows Nominatim only from the API Lambda. |
| C716 | **Caps:** 20 a device and 60 in all per UTC hour (C738; 300 until Oct 31), the device first, counted before any paid call, with the codes and `Retry-After` in §4.8 (AskL-Q2). | Plan §12 and MS9's N8. Refused questions cost nothing and never use up the global cap. |
| C717 | **Switches** act as §4.8 says. A spoken question gets an error while `model-calls` is on, since its transcript would need Meta. | MS7 §5 and MS9 §5 assume exactly this. |
| C718 | **The app records WAV itself:** Web Audio, 16 kHz mono 16-bit PCM, tap to start and stop, at most 15 s, base64 in JSON, held in memory only. | Design C10; MS1 found that Meta takes WAV only. `MediaRecorder` gives WebM or MP4. One JSON shape serves both routes. |
| C719 | **The server checks the WAV header before any Meta call,** and transcribes with the spot names as keywords (since C740, the names of at most 30 characters and the roads, and since C741 three short forms) and Tagalog and English as the language bias. | Plan Table 4. A bad clip costs nothing. |
| C720 | **What leaves the Lambda** is §4.9's table, and Lusot stores nothing about a question. The place cache is keyed by a hash and holds only OpenStreetMap's answer. | Plan §13 and Window 4's PRIV-Q3. |
| C721 | **One log line per question** with §4.9's fields, `meta_calls` and `meta_status` as in the analysis log, and the never-list. | MS9's N8 and its daily check. CLAUDE.md: never log exact locations. |
| C722 | **The notice:** MS5's gate before the first question, and one line under the box on every visit. | MS5's C605 already covers questions; a person asking for the tenth time should still see where the words go. |
| C723 | **The Ask screen** as §4.10 describes, in MS5's fifth slot. | MS5's C620 left the slot and the gate for MS6. |
| C724 | **The app renders answers** with MS5's wording functions and new `ask.*` keys. The `ask.answer.*` keys are screen-line keys (MS5's `isScreenLineKey`), so their Taglish shows only once reviewed. | One wording for a reading wherever it appears; MS5's C609 and C619; MS7's copy check reads the same tables. |
| C725 | **The prompt, the tool, the answer schema and the word lists** are versioned files in `backend/api/prompts/` (`ask_v1.*`), copied into the bundle. | CLAUDE.md keeps prompts and schemas in versioned files. MS7's copy check reads prompt files for review only, since they name banned words to forbid them. |
| C726 | **The question is data, never instructions.** Prompt injection can only change an enum or a ref, which code checks, or a place string, which is trimmed to 100 characters and stripped of control characters before it reaches Nominatim. | The model's reply can't carry text to the person (C704), so injection has nowhere to show. |
| C727 | **An alarm on the global cap** (§4.8), which MS4's API alarm (the tracker's N6) doesn't catch: a cap that holds keeps invocations low. | MS9's F6 and N8 ask for the cap; Rene should hear when it is reached. |
| C728 | **The test questions run in a harness** with real Meta calls, the real code and fixture pins, and their answers are saved outside the repo. A smaller check runs on the deployed API (§8; AskL-Q5). | No test may put a pin on the public map (MS4's C513), and Nominatim runs only from the Lambda. Fixture pins let each question test one rule. |
| C729 | **M12's 10 spoken questions are synthetic Taglish clips** with street noise, made with `facebook/mms-tts-tgl` (CC BY-NC 4.0) from scripts Rene reviews first, and disclosed as synthetic wherever they are reported (§4.7; AskL-Q6). | Rene's decision (Oct 29, about 10:46 PM): no adults record. Plan M12 warns that text-to-speech isn't a fair test of real voices, so the result is labelled synthetic. Meta's own Tagalog model fits a Meta hackathon and runs offline at no cost. |
| C730 | **Cost:** about $0.005 a typed question, $0.006 a spoken one, $0.01 as the planning figure, and at most $1 for Ask's own build and tests (§4.11). | MS7's C828 and MS9's N8 take Ask's figure; the probe replaces the estimate. |
| C731 | **A probe runs before the build:** tools beside `text.format` (with each turn's second form if Meta refuses them), the stateless second turn, minimal against low effort with 10 timings each, a 15 s clip and the full keyword list, for about $0.20. Its results set the effort, the final turn's form (§4.3), the transcription slot and the budget's numbers, by recorded rulings within C734. | F3 and F4 leave the two biggest unknowns open, and the 10 s promise depends on them. |
| C732 *(from the builder check)* | **A shorter window needs a stated time.** A `since_minutes` under 180 counts only when the question states a time, such as "in the last hour" or "30 minuto", and never below that time; otherwise the window stays 180. | A model that read "ngayon" as the last hour would drop the deepest report from the answer and its count, which the plain list would have shown. |
| C733 *(from the builder check)* | **An answer is always about a point, never a road or an area.** A Nominatim result inside Metro Manila wider than 300 m corner to corner, or a bare road name with several listed spots, answers `place_too_broad` with up to 3 listed spots to ask about instead. A result outside Metro Manila answers `outside_metro_manila` first, however wide. Spots are named as points (C715). | CLAUDE.md: never describe a whole road or route. "No recent reports within 300 m of Barangay Tatalon" would read as the whole barangay. |
| C734 *(from the builder check)* | **Turn 1 carries the crossing and vehicle parts, and the final turn adds only the citations.** A late or failed final turn leaves the answer with its crossing line and vehicle line, without "Used" marks. The budget's ends stay fixed. The probe's rulings may move the transcription slot between 3.0 and 5.0 s, so that one turn still fits after it. If a 14.5 s clip doesn't fit even then, AskL-Q9 lowers the recording cap. | Plan §12's 10 s can't move without Rene, so what gives way is decided now, not on Nov 2. MS8's C915 then describes what the probe leaves (§10). |
| C735 *(from the accuracy review)* | **MS4's API alarm (the tracker's N6, from MS9) stays at 5,000 invocations an hour,** the threshold MS4 left for this spec to set (its §4.7). | Ask adds at most 60 counted questions an hour in all (C738), plus refused ones, which are cheap invocations, well inside 5,000. A rush that passes it is the unusual traffic the alarm is for. |
| C736 *(Rene's spending limit)* | **Ask's Meta calls count against MS4's spend counter** (MS4's C527). Before a question's first Meta call, a total at or over `/lusot/spend/stop-usd`, or an unreadable counter, sets `/lusot/stop/model-calls` to "on" and logs `spend_stop`: a typed question gets the plain list (`model_calls_paused`) and a spoken one a 503 `voice_paused`. After the question, `recordSpend` adds its cost (Muse Spark tokens and transcription seconds, at MS4's `PRICES`) under the source `ask`. A throttled write is retried (`maxAttempts: 5` on the client `recordSpend` uses, its own, so other routes keep the SDK's default); one that still fails logs `spend_error` with the amount and sets `/lusot/stop/model-calls` to "on", failing closed as MS4's C527 does, and never changes the answer. A filter on `ApiLogGroup` feeds MS4's `SpendPauseAlarm`, so either pause emails the alarm address. `backend/api/src/spend.ts` is `spend.py`'s TypeScript twin, writing the same `spend#meta` item and `micro_usd` attribute, pinned by the same `spend_contract.json`. | Rene's limit (Oct 29, about 11:03 PM): the $150 of Meta credit, never above. One counter for every path is the only way the $140 stop can see the whole total. |
| C737 *(Oct 31, under D7; approved by Rene, Oct 31, 12:24 PM)* | **A walking word gives `on_foot` only when no call or answer says `light` or `heavy`** (§4.3). When the model names a vehicle, the heavy and light rules decide, and a walking word changes nothing. | Task 9's review ran the code: "Kaya ba ng sedan ko… may lakad kasi ako" ("lakad" is also an errand) and "Can my SUV wade through…" came out `on_foot` over the model's `light`, dropping every class line, and a bus's crossing line too. That loosened the reading, against §4.3's "stricter, never looser". The rule holds whatever the word list holds. |
| C738 *(Rene, Oct 31, 12:24 PM: security-review's N1)* | **The cap on questions in all is 60 an hour, not 300** (§4.6, §4.8). It is `LIMITS.question.all` in `limits.ts`, a constant, so it ships in the API's bundle, and `AskCapAlarm`'s description names it. The device limit stays 20. | Device ids are free to make, so a caller who rotates them is held only by the global cap. At 300 an hour (about $3 at most), that could run to the $60 build stop in under a day, and the stop also pauses photo analysis. At 60, about $0.60 an hour at most. |
| C739 *(the tracker, Oct 31, under Rene's delegation of 2:12 PM)* | **Every turn's `max_output_tokens` is 1,200, not 800** (§4.3). It is `MAX_OUTPUT_TOKENS` in `agent.ts`, and `spend.test.ts`'s bound row is built from it. | In Task 20's run (Oct 31), T4's first turn used exactly 800 output tokens, 685 of them reasoning, so the answer was cut off and the plain list answered. A question's reported worst case rises from $0.0177 to $0.0228 (3 turns of 2,000 input tokens and the cap), $1.37 an hour at C738's cap. The unreported worst case ($0.042 a turn) doesn't change. A longer turn 1 can leave the final turn too little time, and then C734's answer without citations stands, not the plain list. |
| C740 *(the tracker, Oct 31, 11:55 PM, under Rene's delegation)* | **Transcription keywords: the display names of at most 30 characters, then each spot's `roads`, each once and each of at most 30, at most 94 in all, names first** (§4.7). C741 adds three short forms, for 97. A length is counted in UTF-8 bytes, the strictest count, since Meta doesn't say which it uses. It is `spotKeywords` in `spots.ts`, and `spots.test.ts` pins the exact list (94; 97 since C741), to be updated only after Meta takes a new list in a test call. | The voice probe after the Oct 31 deploy got a 503 `voice_failed` for both clips: Meta answered 400, "ASR keyword 3 exceeds the maximum length of 30 characters". 10 of the 31 names are 31 to 43 characters. A laptop diagnostic changed one thing at a time: `languageBias: ["Tagalog", "English"]`, the `request` part sent as a file named "blob", and 21 short names all got 200, and so did all three together with this list of 94 (call 6). Roads keep the 10 long corners' road names, the words speech-to-text mishears, in the bias. |
| C741 *(the tracker's follow-up (4) to C740, Nov 1, 2026)* | **Three short forms join the keywords: "EDSA Santolan", "Oyster Plaza" and "SM Sucat", after the names and before the roads, so the cap is 97.** They are `SHORT_FORMS` in `spots.ts`, each one of its own spot's aliases, so a transcript that holds it finds the spot. Only these three spots need one: each name is over 30 characters, and no road of theirs names the landmark. The other 7 long names are corners, and their roads carry them. | Without them, "Santolan", "Oyster Plaza" and "SM Sucat" reached no keyword. A test call on Nov 1 (the API's own transcribe code, the 97 keywords, the Oct 31 spot clip) got HTTP 200 in 3.2 s, and the transcript found its spot; it cost $0.00025, added to the spend counter. `spots.test.ts` pins the list of 97. |

## 7. Left to the builder

- The module split inside `backend/api/src/ask/`, the prompt's exact wording within §4.3, and the Ask screen's layout within MS5's tokens.
- The spot list's aliases, and which spots enter it, within C715.
- The WAV downsampler's filter, as long as the clip stays intelligible at 16 kHz.
- The User-Agent's exact text, within §4.6.
- Constant names, and the order of fields in the log line.

## 8. Done when

| # | Check | Proved by |
|---|---|---|
| AK1 | **10 typed questions answered** in the harness with real Muse Spark calls: each within 10 s, with the expected kind, place, crossing line and vehicle; where the answer has citations, `cited` a subset of the last result's refs, including the deepest; and the copy check clean on the rendered English and Taglish | the harness's results, saved outside the repo; a summary in the results note |
| AK2 | **10 spoken questions answered** from M12's synthetic clips: each within 10 s, with its transcript shown and the rules of AK1 held. The count of places heard as the script meant is reported, with no minimum, as a synthetic result (AskL-Q6). | the same; waits for Rene's review of the scripts |
| AK3 | **The deployed API:** 5 typed questions within 10 s at the client, with the spoken clip's upload time recorded apart (§4.1): a spot, a small landmark through Nominatim, "dito", a crossing question, and a place outside Metro Manila, each answered as the live pins of the moment allow; plus one synthetic spoken clip end to end | the cloud check's counts and timings |
| AK4 | **Caps:** the 21st question from one device and the 301st in all are refused with their codes and `Retry-After`; the device is counted first; no refused question makes a Meta or Nominatim call | unit tests |
| AK5 | **Fallbacks:** each trigger in §4.5 gives the plain list, with no Meta call under `model-calls`; a spoken question gets `voice_paused`; an unreadable switch counts as on | unit tests; MS7's S2 in the cloud |
| AK6 | **The publish switch:** while it is on, no live pin appears in any answer and demo pins still do | unit tests through MS4's read |
| AK7 | **Privacy:** sentinel text, audio, coordinates and device ids reach no log line and no stored item; the voice path makes no S3 call; every Muse Spark request carries `store: false`; nothing sent to Meta holds a coordinate or a report id | unit tests |
| AK8 | **Nominatim:** one request a second across Lambdas, a cache hit makes no request, the User-Agent is sent, the switch stops it, and the app shows the attribution | unit tests |
| AK9 | **Copy:** MS5's string-table tests and MS7's copy check pass on the `ask.*` keys and the saved answers; Rene's review brings the unreviewed count to 0 before release (M20) | test runs; MS7's sheet |
| AK10 | **Voice capture:** the encoder and downsampler pass their tests; the app records a WAV from a fake microphone in Playwright; nothing holds the audio afterwards; the APK records on the emulator | unit and end-to-end tests; an emulator run |
| AK11 | **The template:** the two routes, the key grant, the `GetItem` grant on `limits` (C701), the 15 s timeout, the Nominatim switch, the cap alarm and the API alarm's 5,000 (C735), with MS4's count tests updated for the new routes, variables and grant; MS4's own test keeps `Retry-After` exposed; `npm run check` and CI pass | template tests; CI |
| AK12 | **The guards** (C732 to C734): an SUV question that the model labels `heavy` answers `light`; a walking word gives `on_foot` when no call or answer names a vehicle, never over the model's `light` or `heavy` ("may lakad ako", "can my SUV wade through"; C737), and a model-only `on_foot` answers `none` with its class lines; a window under 180 minutes without a stated time stays 180, and a stated time is never shortened; a Nominatim result inside Metro Manila wider than 300 m, and a road with several listed spots, answer `place_too_broad` with suggestions, while a wide result outside answers `outside_metro_manila`; a final turn that runs late, cites wrongly or says `off_topic` leaves an answer with its reports and no citations, its crossing and vehicle lines intact | unit tests |

## 9. Questions for Rene

Each has a default that the plan follows until he answers (D7). Most important first.

| # | Question | Options | Default |
|---|---|---|---|
| AskL-Q1 | **Who writes the words of an answer?** | (a) Lusot, from reviewed lines: the model picks the kind, the vehicle and the reports, and code and the app write every word. (b) Muse Spark writes a short Taglish answer, which a word check screens, with the plain list when it fails. | (a). M20 can review every line of (a) before release, never the words of (b), and a word check can't catch every piece of crossing advice (MS5's C608). |
| AskL-Q2 | **The cap on questions across all devices** | (a) 300 an hour, about $3 an hour at most (MS9's N8); (b) 150 an hour, about $1.50; (c) none, with only `model-calls` as the brake | (a); lowered to 60 an hour by C738 |
| AskL-Q3 | **PRIV-Q3 for Ask** (Window 4's drafts) | (a) Lusot keeps no typed question or transcript; a "dito" location goes to no one, and Meta gets only distances; every Muse Spark request sends `store: false`; the place cache keeps OpenStreetMap's answers for 7 days, keyed by a hash; the 18+ check and the notice come before the first question. (b) As (a), but the place cache keeps the text asked, for debugging. | (a). The policy and the notice then state it, for your M21 approval. |
| AskL-Q4 | **Demo pins in answers** | (a) apart, labelled "(demo)" with their date and credit, never the summary; (b) mixed with live pins and labelled; (c) never in Ask | (a) |
| AskL-Q5 | **Where the 20 test questions run** | (a) in the harness, with real Meta calls and fixture pins, plus a 5-question check on the deployed API; (b) all 20 on the deployed API, against whatever pins exist then | (a). Under (b), with no flood and few demo pins, most answers would be "no recent reports". |
| AskL-Q6 | **The bar for the spoken questions** (now synthetic clips, C729) | (a) all 10 answered within the rules, with the count of places heard right reported as a synthetic result and no minimum; (b) at least 8 of 10 places heard right | (a). Whether voice stays in the video is then your call with that count in hand (plan Table 18, MS8), knowing synthetic voices are the easier test. |
| AskL-Q7 | **Ask's Lambda** | (a) the API Lambda, as plan Figure 1 has it, with the key grant added to its role; (b) its own function, so only it can read the key, with its own log and alarm | (a). (b) is tighter on privilege, and it would also keep the key away from MS4's any-origin public `FeedApi` (its C521), which runs on the same `ApiFunction`. But MS4's N6 and MS9's daily check would need updating. |
| AskL-Q8 | **The spot list's source** | (a) names from MMDA's alerts and published list, points from an OpenStreetMap extract under ODbL, credited; (b) Rene picks each point by hand | (a), with the licence confirmed on the source page before the file is committed |
| AskL-Q9 | **If the probe shows that a 15 s clip can't be transcribed in time** (C734). Asked only if it happens. | (a) The app's recording cap drops to 10 s by a recorded ruling, still within plan Table 4's "up to 15 s", and `audio_too_long` follows. (b) Keep 15 s, and a long clip answers `voice_failed` or the plain list. | (a). Short questions are the common case, and every answer still shows its transcript. |
| AskL-Q10 *(from the accuracy review)* | **The `heavy` vehicle line beside an NPLV class line** ("not passable to light vehicles") reads as "your vehicle can pass", even when `heavy` is right (M20) | (a) drop "not a light one" and, with `heavy`, show the crossing line directly under the class line; (b) show the vehicle line only for `light`; (c) drop "not a light one" only | (a) |
| AskL-Q11 *(from the accuracy review)* | **A spoken question's transcript can hold a banned word,** such as "Ligtas ba…?", which Lusot would then show (CLAUDE.md, MS5's C608) | (a) mask each banned word in the shown transcript, letter by letter as "•", keeping the rest; (b) show the transcript as quoted user input, exempt by a ruling, with MS5's and MS7's checks told which element is exempt; (c) show only the place heard | (a). The rule is absolute, and the place heard, which the transcript is there to check, stays. |

Design R6 bears on Ask too: the fewer consented demo pins exist, the more answers say "no recent reports" outside a flood.

## 10. Hand-offs

**What Ask needs from others** (through the tracker; each plan's Task 0 records the committed names):

| # | From | Need | If it doesn't come |
|---|---|---|---|
| N1 | MS4 | `pins.ts` exports a data-level read, such as `nearbyPins(lat, lng, radiusM, deps)`, returning public pins with the publish switch applied, which `nearby` wraps; and its distance function | Ask's Task 0 splits `nearby` on Ask's branch, with MS4's tests unchanged. |
| N2 | MS4 | `limits.ts`'s one `take(bucket, deviceHeader, nowS, deps)` takes a `question` bucket: 20 a device, 300 in all, refusing with Ask's codes through a per-bucket code map, while MS4's codes stay | Ask adds it, test first, and reuses `retryAfterS`. |
| N3 | MS4 | `metroManila.ts` exports `inMetroManila` | Ask imports the polygon test as MS4 wrote it. |
| N4 | MS4 | CORS exposes `Retry-After` (audit row 23) and allows `X-Lusot-Device` | **Answered:** MS4's §4.7 does both. |
| N5 | MS4 | Demo pins carry `credit`, `place` and `event` in public pins (audit row 1) | **Answered:** MS4's C523. |
| N6 (Ask's own hand-off, not MS9's N6) | MS4 | *(Dropped.)* MS4's C522 kept `device_limit` and `global_cap`, which MS5, MS7 and MS9 follow. | Ask's codes stand on their own. |
| N7 | MS5 | The fifth slot `#/ask`, the gate before the first question, `isScreenLineKey` covering `ask.answer.`, and the wording functions as exports | Ask's app tasks add them on Ask's branch. |
| N8 | Window 4 | The policy and the notice take AskL-Q3's answer: no stored questions, the location kept in the Lambda, `store: false`, the cache's 7 days, Nominatim, no `store` setting for audio, and a notice heading that covers questions as well as photos | The texts keep their PRIV-Q3 brackets, which M21 can't approve as they are. |
| N9 | MS7 | The copy check reads `ask.*` keys, the `ask_v1.*` prompt files (review only), and the saved answers' `rendered.en` and `rendered.fil` fields (the `transcript` field is the speaker's words, review only; the shown transcript is masked, AskL-Q11). The crossing line joins the allowed sentences once Rene approves it. The switch test covers `/lusot/stop/nominatim`. The APK's permission list adds `RECORD_AUDIO` and `MODIFY_AUDIO_SETTINGS`. C828's questions name spot-list places, so the rush makes no Nominatim call. | Ask's own copy test runs on its keys; the rest waits for MS7. |

**What Ask gives others:**
- **MS7:** §5's contract; the plain list marked `source: "plain_list"` with `fallback: "model_calls_paused"` and `meta_calls` 0 (S2); 10 s at the client (L9); no audio in any bucket or table (P14); the spot list at `backend/api/src/data/spots.json`; the saved answers at `LUSOT_DATA_DIR\ask\<date>\` (§8); the cost per question from AK1, else $0.01.
- **MS9:** N8 answered: the cap (60 an hour since C738) and its alarm, the log fields, the plain list under `model-calls` and `voice_paused` for voice. Ask's 402s appear in the API log as `meta_status` 402 with `fallback: "key_rejected"`.
- **MS8:** C915's facts: the tool is `get_reports`; Muse Spark reads the question, decides the lookup, calls the tool, reads its results and cites the reports it used; code checks every citation; the spoken answer shows its transcript; the counts come from AK1 and AK2. N4: answers show their cited pins ("Used") and the transcript. If the probe drops the final turn (C734), C915 says instead that Muse Spark reads the question, decides the lookup and calls the tool, and code picks the reports from what it returns.
- **MS4:** its API alarm's threshold (the tracker's N6), set at 5,000 an hour (C735), with at most 60 counted questions an hour from Ask (C738); and the `GetItem` grant on `limits` (C701), which Ask's template task adds.

## 11. Risks

- **Muse Spark is too slow even at minimal effort.** The probe shows it before the build. If two turns don't fit 7.5 s, the final turn gives way (C734), which keeps the model's place finding, the crossing line and the vehicle line.
- **Tools and `text.format` don't mix** (F4). Both turns' second forms (§4.3) are ready, and the probe tries them.
- **Taglish voice is weak,** or keywords can't hold the full list (they couldn't: C740 leaves out the 10 names over 30 characters and adds the roads, and C741 adds short forms for the 3 whose landmark no road names). Plan Table 18's fallback, and the transcript always shown.
- **Questions fill the account's 10 Lambda slots** in a rush. The caps bound the hourly total but not a burst; MS7's C828 measures it, and the per-route throttles MS4 may add (audit row 9) can include Ask's routes.
- **Nominatim blocks or slows us.** The spot list answers first, the cache second, and the switch turns Nominatim off.
- **`limits` has 2 write units.** A question writes 2 counters, plus a slot and a cache item through Nominatim, beside MS4's upload counters. A rush draws on DynamoDB's burst capacity, and MS7's C828 shows whether it is enough.
- **No pins at test time.** The harness's fixture pins cover the rules; the deployed check accepts "no recent reports" as correct where none exist.
- **The credits lapse during judging** (MS9). A 402 gives the plain list and shows in the API log.
- **Committed names in MS4 or MS5 differ** from §10's. The plan's Task 0 records them before any task starts.

## 12. Not in this spec

- MS6's evaluation and the sealed run.
- Text to speech, a Messenger bot, streaming answers and chat history.
- Per-route API throttles, which MS4 owns (audit row 9).

## 13. Builder check (Oct 29)

A fresh reviewer (Opus 5.5 at max) read this spec, CLAUDE.md, the build design, the API code, the template, and the MS4, MS5, MS7 and MS9 documents it builds on, as if it had to plan the build alone. It opened nothing under `lusot-data`, read no plan text and made no network call. It returned three questions, all settled as Claude's calls.

| # | Question (short) | Pile | Settled as |
|---|---|---|---|
| BQ1 | Should code check the model's `vehicle` and `since_minutes`, as it checks `cited`? A wrong `heavy` beside NPLV reads as permission to go; a wrong `on_foot` drops every class line; a shorter window can hide the deepest report. | Claude's call | Code can only make the model's reading stricter (§4.3): `heavy` needs a truck or bus word, a walking word gives `on_foot` only when no vehicle is named (C712, C737), and a window under 180 needs a stated time (C732). AK12 tests each. |
| BQ2 | If the probe shows the loop doesn't fit the budget, what gives way? Dropping turn 2 would lose the crossing and vehicle lines, and a 15 s clip may not transcribe in 4 s. | Claude's call; a lower recording cap is AskL-Q9 | The tool's call carries `kind` and `vehicle`, so the final turn adds only the citations, and a late one costs only the "Used" marks (C734). The transcription slot may move between 3.0 and 5.0 s by ruling, and AskL-Q9 covers a lower cap. MS8's C915 gets a conditional wording (§10). |
| BQ3 | A street or a barangay resolves to one point, so "No recent reports within 300 m of {place}" reads as the whole road or area. | Claude's call, from CLAUDE.md's rule | Answers are always about a point (C733): spots are named as points, a road with several listed spots and a Nominatim result wider than 300 m answer `place_too_broad` with up to 3 spots to ask about instead. |

It also named gaps a builder could settle: how refs number across two tool calls (each result numbers afresh, and the answer cites the last, §4.2), the final turn's other form in the probe, a fake Nominatim in the harness, freezing the 10 typed questions before the prompt is tuned, and keeping MS4's API alarm at 5,000. The plan takes each of them.

## 14. Accuracy review (Oct 29 evening)

A fresh reviewer (Opus 5.5 at xhigh) checked this spec and the plan against MS4's committed spec and plan (`d136513`), MS5 (`6ca31b9`), the code on `main` and MS3a's branch, the cross-spec audit, CLAUDE.md and dev.meta.ai. It found 1 Critical, 13 Important and 20 Minor problems, all taken under Window 4's rulings (Claude's calls, in Rene's batch). The ones that change this spec:
- **The Critical:** the place cache reads `limits`, which MS4's grants left write-only, so the API role gains `GetItem` there (C701).
- **Where the place test runs:** `inMetroManila` comes before the breadth test, so a town outside Metro Manila answers `outside_metro_manila`, not `place_too_broad` (§4.2, C733).
- **Code's checks on the model:** `on_foot` now needs a walking word (§4.3, C712). A final turn can't turn a question `off_topic` (§4.3). The two calls' readings are combined, and a stated time is never shortened (C732).
- **Turn 1's fallback form:** tools with no `text.format`, if Meta refuses the two together (§4.3, F4).
- **The client:** Ask's client never retries a 503 or a request already sent (§4.8).
- **MS4's API alarm (the tracker's N6):** it stays at 5,000 an hour (C735).
- **New lines:** a busy place lookup gets its own line, `lookup_unavailable` (§4.4, §5.3).
- **Copy questions for Rene:** the `heavy` line beside NPLV (AskL-Q10), and a transcript that holds a banned word (AskL-Q11).
- **Wording:** every avoidable form of the banned word is gone from this spec's prose. MS5's `isSafetyKey` becomes `isScreenLineKey` by the tracker's ruling of 9:50 PM by its clock, and only quoted rules and detection lists still name the word.
- **Housekeeping:** the refs to MS4 and MS5 are re-pinned, and N4 and N5 are answered. Ask's own N6 hand-off is dropped.
