# Ask Lusot's typed results (Oct 31, 2026)

Ask Lusot ships typed only (Oct 30). Two paid runs check it on Oct 31, both against the stack deployed at 1:57 PM from `main` at `55f6ec5`, with `WebHosting=off`. AWS hasn't yet verified the account for CloudFront, so the website is left out, and the API and analysis are as built. The prompt is `ask_v1`, the model `muse-spark-1.3` at effort `low`.

## The cloud check (plan Task 19, Step 5)

`uv run --locked --script backend/scripts/ask_cloud_check.py`, run from the laptop after the smoke test and before the 10 questions, gave `ASK CHECK OK in 22.8 s`. It posted five typed questions to the deployed `POST /ask`, each with its own random device id. The time is the client's, from the post to the reply.

| Question | HTTP | Source | Kind | Time |
|---|---|---|---|---|
| a listed spot | 200 | model | `no_reports` | 4.9 s |
| a small landmark (Nominatim) | 200 | model | `no_reports` | 4.4 s |
| "dito", at a public point | 200 | model | `no_reports` | 3.0 s |
| a sedan at a named road | 200 | model | `no_reports` | 2.4 s |
| Bacoor (outside Metro Manila) | 200 | model | `outside_metro_manila` | 3.4 s |

- **What it proves:** the listed spot's answer came from the model, which needs no Nominatim call. So the deployed function reads the key and calls Meta.
- **No reports:** no live pins were near any question's place at the time, so `no_reports` is the right kind for the four inside Metro Manila.
- **Cost:** MS4's spend counter went from $3.372262 to $3.401956, $0.029694 for the five, about $0.006 a question.
- **Not run:** the plan's synthetic WAV, since voice was dropped (Oct 30).

## The 10 typed questions (plan Task 20, Step 1)

`npm run ask:eval -w backend/api` (with `LUSOT_ASK_EVAL=1`, the key from the user environment and `LIMITS_TABLE_NAME` from the stack) exited 0. Its run id is `2026-10-31T06:04:53.443Z` (2:04 PM). The harness asks Task 18's frozen T1 to T10 on the laptop, with real Muse Spark calls and MS4's real spend counter. The answers are saved in the private data folder (`ask\2026-10-31\answers.jsonl`), never in the repo.

- **Passed:** 10 of 10, each HTTP 200 with every check it carries passing. There was no spend error and no spend stop, and `/lusot/stop/model-calls` stayed off.
- **Model against plain list:** 9 answers from the model, and 1 plain list (T4).
- **T4:** its first turn used exactly 800 output tokens, 685 of them reasoning. That is `MAX_OUTPUT_TOKENS` in `backend/api/src/ask/agent.ts`, so the turn was cut off, and the answer fell back to the plain list (`fallback: model_error`), as designed. Its checks pass. Raising the cap is Rene's call, and nothing has changed.
- **Times** (the harness's, per question, on the laptop): median 4.43 s, largest 4.74 s, smallest 2.01 s. All are within 10 s.
- **Calls and tokens:** 18 Meta calls: two per question, except one each for T4 and T10. 27,079 input, 6,313 output and 4,867 reasoning tokens.
- **Cost:** the harness's estimate was $0.060679, about $0.0061 a question. MS4's spend counter went from $3.401956 to $3.462638 ($0.060682), recorded once.

**Still open for AK1:** Task 20's Step 2 renders the saved answers in English and Taglish and runs the copy check over them. It needs the app's Task 14, which is with the cloud session on `ask-app`. AK1 stays unticked until then.

## The day's paid runs and the running total

| Run | Cost (counter) | Counter after |
|---|---|---|
| (before) | | $3.204402 |
| `smoke_upload.py`: `SMOKE OK` in 345 s | $0.167860 | $3.372262 |
| the cloud check | $0.029694 | $3.401956 |
| the 10 typed questions | $0.060682 | $3.462638 |

Together, $0.258236. The build's stop is at $60.
