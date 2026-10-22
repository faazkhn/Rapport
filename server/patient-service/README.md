# Rapport patient service

Local Python service that plays the patient (the Digital Twin, on a local llama-server by default; Grok only with `PATIENT_LLM=grok`) and speaks for it (Qwen3-TTS VoiceDesign, KittenTTS fallback). For education only.

## Run

```bash
cd server/patient-service
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r requirements.txt   # first time only
./run.sh            # serves on http://127.0.0.1:8765 (PORT=... to change)
```

The venv is its own (`kittenml` 0.9.4 installs cleanly into a fresh Python 3.12 venv; `tools/tts/.venv` is not used).
The TTS model loads once at startup (about 1 s when cached, about 13 s on the very first download).

## Environment

| Variable | Default | Meaning |
|---|---|---|
| `XAI_API_KEY` | read from the environment, else from the repo-root `.env` | xAI key. Never logged or returned. |
| `PATIENT_LLM` | `local` | `grok` uses xAI (needs `XAI_API_KEY`); otherwise the local llama-server at `LLAMA_URL`. |
| `RAPPORT_MODEL` | `local` | Model name sent to llama-server (informational); a request can override it. |
| `RAPPORT_DATA_DIR` | `<repo>/unity/PsychSim/Assets/StreamingAssets/data` | Canonical data folder (shared with Unity). |
| `RAPPORT_LLM` | unset | `mock` uses the keyword mock patient (`run.sh --mock`). |
| `RAPPORT_TTS` | `qwen3-design` | Voice backend; `kitten` forces KittenTTS. |
| `RAPPORT_SKIP_TTS` / `_STT` / `_WARMUP` | unset | `1` skips loading that part at startup (tests). |
| `RAPPORT_STAGED` | unset | Path to a staged script (`staged.py`): pre-scripted replies for concept previews. |

`PSYCHSIM_*` names still work as deprecated aliases until v0.3 (ADR 0003).
| `PORT` | `8765` | Port for `run.sh`. |

## Endpoints

- `GET /health` → `{"ok": true, "model": "...", "tts_loaded": true}`
- `POST /reply`
  ```json
  {"case_id": "mdd_01",
   "messages": [{"role": "doctor", "text": "Hello, I'm Dr Rao."}],
   "state": {"trust": 30, "distress": 55, "agitation": 15, "engagement": 35},
   "elapsed_min": 2, "model": null, "reasoning_effort": null, "summary": null}
  ```
  Returns the DESIGN §7.2 contract (`utterance, emotion, state_delta{4 ints}, event_cues, revealed_fact_ids, doctor_intents`) plus
  `meta: {model, latency_ms, allowed_fact_ids, guard_dropped, fallback, attempts | errors}`.
  - The prompt contains only facts with `trust_min <= state.trust`; the last 20 messages are sent verbatim, plus `summary` if given.
  - The response schema is built per request (`strict: true`) with enums for allowed fact ids, case cue ids, intent ids and emotions.
  - Server guard (mirror of Unity GuardCheck): drops unknown/locked facts, facts marked `must_be_asked` when none of their `unlock_intents` was tagged this turn, unknown cues and intents; clamps `state_delta` to ±10 and cue intensity to 0–1. Everything dropped is listed in `meta.guard_dropped`.
  - On a parse/validation/API error it retries once, then returns a random `fallback_lines` entry with `meta.fallback: true` (HTTP 200).
  - The server does **not** apply the state change. The client does: `brain.apply_turn` (LLM delta + `state_rules.json` nudges, clamped per turn) is the reference for Unity's `PatientState`.
- `POST /tts` `{"text": "...", "voice": "Bella", "speed": 0.9}` → `audio/wav`, 24 kHz mono 16-bit, in memory only. Voices: Bella, Luna, Rosie, Kiki, Jasper, Bruno, Hugo, Leo. Header `X-Gen-Ms` gives generation time. Not streamed per sentence yet (the client can split sentences and call per sentence).

Service logs (stdout) hold latency, model and counts only: no conversation text and no key. The Digital Twin session log (below) is the exception: it holds the conversation text, stays on this machine, and is git-ignored.

## Model notes (docs.x.ai, checked 2026-10-18)

- `docs.x.ai/docs/models` lists both `grok-4.20-0309-non-reasoning` (1M context) and `grok-4.7` (500k context), plus `grok-4.20-0309-reasoning`.
- Reasoning effort parameter: **`reasoning_effort`**, values `low | medium | high (default) | xhigh`. Docs say grok-4.7, 4.6 and 4.5 support it. The service sends it only when the request sets it, so leave it out for the non-reasoning model.
- Structured outputs: `response_format={"type": "json_schema", "json_schema": {..., "strict": true}}`. The docs' examples use grok-4.7. An `enum` with zero values is a 400 error, so an empty fact allow-list becomes `{"type": "array", "maxItems": 0}`. `minimum`/`maximum` are accepted but not enforced, which is why the guard clamps numbers.
- To compare models: `scripts/demo_convo.py --model grok-4.7 --reasoning-effort low`.

## Digital Twin (docs/TWIN.md)

- WebSocket `/session` now also sends, per live turn: `twin_event` (`init` at start, then `doctor_end`, `patient_start`, `patient_end`) and one `brain_snapshot` (state, PAD mood, reaction, intensity, behaviour, resistance, why, recalled, locked_hit, cues, expression, brain_version).
- `WS /twin/ws`: the same events for Twin view viewers (`/twin/?live=1`); a late viewer gets the session so far. Never blocks the voice.
- Each live session is logged to `logs/twin/<time>_<case>.jsonl` (`RAPPORT_TWIN_LOG_DIR` overrides). Local only; contains the conversation text.
- Reply contract fields (in generation order): `behaviour, emotion, utterance, reaction, intensity, resistance, state_delta, event_cues, revealed_fact_ids, exam_action`.

## Learning (Phase E, docs/adr/0004-learning-loop.md, docs/LEARNING_REPORT.md)

- `learning.py`: brain versions (`learned/versions/`, live one in `learned/current.json`), the quality gate, the experience library (`learned/experience/<case>.jsonl`, MiniLM ONNX embeddings, local) and faculty principles. Learning changes how the patient talks, never facts, the answer key or scoring.
- `brain_version` (`twin-0.1+v<n>`) is in every `brain_snapshot` and in `/reply` `meta`, with the example ids used (`meta.examples`).
- WebSocket `start` takes `mode` (`practice` default; `assessment` uses only faculty-approved examples) and `learning_consent` (default false: a learner's turns are never stored).
- `POST /learning/feedback {case_id, doctor, utterance, rating: up|down|rewrite, rewrite?, comment?, author}` → a principle appended to the case's `principles`; 👍 also stores the line as an approved example. `POST /learning/approve {case_id, entry_id}`.
- Offline loop: `.venv/bin/python ../../tools/learning/loop.py heldout|round|rescore|decide|report` (see its docstring). Rollback: `.venv/bin/python learning.py rollback v0`; `learning.py list` shows every version.

## Data and checks

```bash
.venv/bin/python validate_data.py          # schemas + cross-references for every data file
.venv/bin/python -m pytest                 # offline tests (TTS test skips if the model can't load)
.venv/bin/python -m pytest -m live         # real /reply call; needs a valid XAI_API_KEY
.venv/bin/python scripts/demo_convo.py     # 6-turn live demo; service must be running
```

All clinical content in the data folder is an AI draft (`status: draft`, `verified_by: null`, doses null) for faculty review.
