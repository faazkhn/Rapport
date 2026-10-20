# Live Digital Twin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every live turn is decided by the Digital Twin (recall → reaction → behaviour → speech → state and mood update), and the examiner's Twin view shows it live and can replay it afterwards.

**Architecture:** A new `twin.py` module in the patient service owns the Twin: lexical recall with trust locks (no LLM), the fast-path label fields at the front of the existing structured reply, a code-built `why`, and a slow-path update of state and PAD mood that runs after the voice stream. `Session.run_turn` emits a `brain_snapshot` per turn and the turn events; a `/twin/ws` broadcast feeds `twin.js` in live mode, and the same events go to a per-session JSONL that a converter turns into a replay timeline.

**Tech Stack:** Python 3.12, FastAPI, llama.cpp (Gemma 4 E4B, JSON grammar), pytest; vanilla JS (twin view); Unity 6 C# (one log hook).

**Spec:** `KICKOFF_PROMPT_v4.md`, Phase D (items 1–7) and Phase F (live wiring and replay only). Read `HANDOFF.md` first. The snapshot format is fixed by `server/patient-service/twin/README.md` ("Timeline format").

## Global Constraints

- Everything stays local: no cloud calls, accounts or new network services.
- "Learning may change *how* the patient talks, **never** clinical facts, the answer key or scoring." This plan adds no learning; nothing in it may write to a case file at runtime.
- "All updates are categorical steps clamped by code: the model proposes, the code decides."
- Locked memory items that match "send only a discomfort signal": their content never enters the prompt.
- Recall: "local embeddings plus tags, with no LLM call", ≤ 10 ms. **Decision for this plan:** tags plus word-stem overlap only; embeddings are deferred (mark with a `shortcut:` comment). Reason: no embedding model is installed and adding one is its own latency decision.
- Fast-path schema order: `reaction, intensity, behaviour, resistance, emotion, utterance, …`. The utterance must still stream to TTS.
- Live voice gate: median `audio_start_ms` from `tools/latency/ws_bench.py --runs 1` may rise by at most 150 ms over the 2026-10-20 baseline (p50 1,616 ms). Over that, stop and report.
- Clinical content stays `status: draft`. The Twin view keeps "Metaphor, not neuroscience".
- Names: product **Rapport**, the brain **Digital Twin**, the examiner page **Twin view**. Never Sanvaad, Chitta or PsychSim in new user-facing text. (C# namespaces stay `PsychSim.*` until the rename plan.)
- Commits authored `faazkhn <faazkhn1000@gmail.com>`, no Claude co-author or "Generated with" lines.
- **Decision for this plan:** case files keep the key `facts`; each fact gains the memory-item fields. Code calls them memory items. Reason: Unity's `CaseLoader` and `GuardCheck` read `facts`; renaming the key belongs to a plan that changes Unity too.

## Review Focus

1. **A doctor line that hits a locked item** (for example "Have you thought about ending your life?" at trust 30): the item id appears only in `locked_hit`, its text never in the prompt, and the reply carries a discomfort reaction. Pinned in Task 2 and Task 3.
2. **The model emits a reaction/behaviour outside the catalogue, or intensity outside 0–10** (Grok backend: `minimum/maximum` not enforced): guard replaces with `none` / clamps, records it in `guard_dropped`. Pinned in Task 3.
3. **Barge-in mid-reply**: a snapshot is still sent with the spoken part only, and the mood update still runs once. Pinned in Task 5.
4. **No Twin view connected, or a viewer disconnects mid-session**: the voice turn never waits on or fails because of `/twin/ws`. Pinned in Task 6.
5. **Staged mode (`RAPPORT_STAGED`)**: still sends its scripted `brain_snapshot` unchanged; the Twin code path does not run. Pinned in Task 5.

---

## File map

| File | Responsibility |
|---|---|
| `unity/PsychSim/Assets/StreamingAssets/data/brain/behaviours.json` (new) | Reactions, behaviours, resistance styles: id, description, example line, trust step |
| `unity/PsychSim/Assets/StreamingAssets/data/brain/expression_map.json` (new) | Reaction/behaviour → extra cues, TTS speed factor |
| `unity/PsychSim/Assets/StreamingAssets/data/schemas/brain.schema.json` (new) | Schema for both brain files |
| `unity/PsychSim/Assets/StreamingAssets/data/schemas/case.schema.json` | Optional `formulation`, `core_belief`, `attachment_style`, `dialect`; per-fact `activation_tags`, `kind`, `generates_discomfort` |
| `unity/PsychSim/Assets/StreamingAssets/data/cases/mdd_01.json` | Filled by the migration script, then hand-edited tags and formulation |
| `server/patient-service/scripts/migrate_memory.py` (new) | Adds memory-item fields with defaults to every fact; idempotent |
| `server/patient-service/twin.py` (new) | Recall, label guard, `why`, slow-path update, expression, snapshot builder |
| `server/patient-service/brain.py` | Schema label fields; prompt gets behaviour menu and recall block |
| `server/patient-service/session.py` | Calls the Twin in `run_turn`; emits snapshot and turn events; writes the session JSONL |
| `server/patient-service/twin_bus.py` (new) | In-process broadcast to `/twin/ws` viewers; never blocks |
| `server/patient-service/app.py` | `/twin/ws` route |
| `server/patient-service/validate_data.py` | Validates brain files and their cross-references |
| `server/patient-service/twin/twin.js` | `?live=1&ws=<url>` connects to the bus |
| `tools/demo/log_to_timeline.py` (new) | Session JSONL → replay timeline JSON |
| `unity/PsychSim/Assets/Scripts/Core/EncounterManager.cs` | Logs `brain_snapshot` to `SessionLog` |
| `docs/TWIN.md`, `docs/adr/0001-digital-twin-architecture.md` (new) | Spec of what was built; the decision record |

Tests live in `server/patient-service/tests/` (`test_twin.py` new; `test_brain.py`, `test_session.py`, `test_data.py` extended). Run from `server/patient-service`: `.venv/bin/python -m pytest -q`.

---

### Task 1: Brain catalogue, case fields and migration

**Files:**
- Create: `unity/PsychSim/Assets/StreamingAssets/data/brain/behaviours.json`, `.../brain/expression_map.json`, `.../schemas/brain.schema.json`, `server/patient-service/scripts/migrate_memory.py`
- Modify: `.../schemas/case.schema.json` (`facts.items` and top-level properties), `.../cases/mdd_01.json`, `server/patient-service/validate_data.py`
- Test: `server/patient-service/tests/test_data.py`

**Interfaces:**
- Produces: `behaviours.json` = `{"version", "status": "draft", "reactions": [Item], "behaviours": [Item], "resistance": [Item]}` where `Item = {"id", "description", "example", "trust_step"}` (`trust_step` ∈ {−2, −1, 0, 1, 2}; on `reactions` only, others omit it). `expression_map.json` = `{"version", "status": "draft", "reactions": {id: Expr}, "behaviours": {id: Expr}}` where `Expr = {"cues": [{"id", "intensity"}], "speed": float}` (speed 0.8–1.2, multiplies `tts_speed`). Per fact: `activation_tags: [str]` (lowercase words or short phrases), `kind: "symptom"|"history"|"trigger"|"formative"|"risk"`, `generates_discomfort: bool`. Case top level: `formulation: {presenting, predisposing, precipitating, perpetuating, protective}` (strings), `core_belief: str`, `attachment_style: str`, `dialect: str` (default `"natural Indian English"`).
- Catalogue ids (exact): reactions `none, understood, hopeful, relieved, warm, calm, wary, startled, afraid, ashamed, self_conscious, sad, numb, resigned, challenged, misunderstood` (PatientAct's set plus every reaction `demo/staged/script.json` uses, so staged and live snapshots share one vocabulary); behaviours `answers_plainly, minimises, denies, deflects, vague_timeline, answers_different_question, tangential, guarded_short, hostile, tearful_disclosure, asks_back, complies_without_engaging, complies` (`complies` = carries out an exam request; the staged script uses it); resistance `none, quantity, content, style`.

- [ ] **Step 1: Write failing tests** in `tests/test_data.py`:
  - `test_brain_catalogue_ids`: loads `brain/behaviours.json`; asserts the three id lists equal the lists above, every item has non-empty `description` and `example`, and every reaction has `trust_step` in `{-2,-1,0,1,2}`.
  - `test_expression_map_refs`: every key in `expression_map.json` exists in the catalogue; every cue id exists in `cues.json`; every `speed` in [0.8, 1.2].
  - `test_mdd01_memory_items`: every `mdd_01` fact has `activation_tags` (non-empty), `kind`, `generates_discomfort`; facts `f_passive_si` and `f_guilt` have `generates_discomfort: true`; the case has all five `formulation` keys.
  - `test_migrate_idempotent`: run `migrate_memory.migrate(case_dict)` twice on a copy of a fact without the fields; second result equals the first; existing values are never overwritten.
- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_data.py -q` — expect the four new tests to FAIL (missing files/fields).
- [ ] **Step 3: Write the two brain JSON files and `brain.schema.json`.** Descriptions and examples are draft clinical-style copy in Indian English, one line each; mark `"status": "draft"`.
- [ ] **Step 4: Extend `case.schema.json`** with the optional fields above (`additionalProperties: false` stays). Then implement `migrate(case: dict) -> dict` in `scripts/migrate_memory.py`: defaults `activation_tags` = words of the fact's `unlock_intents` with `ask_` stripped and `_` → space, `kind = "symptom"`, `generates_discomfort = false`; CLI `migrate_memory.py <case.json>` rewrites the file with `indent=1`, `ensure_ascii=False`.
- [ ] **Step 5: Run the migration on `mdd_01.json`, then hand-edit** its tags (add lay words a doctor would say: "sleep", "wake", "night"; "eat", "appetite", "weight"; "die", "end it", "alive", "hurt yourself"…), `kind`, the two discomfort flags, and copy `formulation` from `FORMULATION` in `tools/demo/staged_timeline.py` (drop its `status` key). Add `core_belief` ("I am a burden and a failure to my family."), `attachment_style` ("anxious, seeks reassurance, hides need"), `dialect`.
- [ ] **Step 6: Extend `validate_data.py`** to schema-check both brain files and run the expression-map cross-references; run `.venv/bin/python validate_data.py` — expect exit 0.
- [ ] **Step 7: Run** `.venv/bin/python -m pytest -q` — all pass. Also run the Unity EditMode tests (`mcp__unity__run_tests` EditMode, or Test Runner) — `CaseLoader` must still load `mdd_01`.
- [ ] **Step 8: Commit** `feat(twin): brain catalogue, memory-item fields, mdd_01 migration`.

### Task 2: Recall with locks (`twin.recall`)

**Files:**
- Create: `server/patient-service/twin.py`
- Test: `server/patient-service/tests/test_twin.py`

**Interfaces:**
- Consumes: case dict from `brain.load_case` (facts with Task 1 fields).
- Produces: `recall(case: dict, trust: float, doctor_text: str, limit: int = 3) -> dict` returning `{"open": [fact_id], "locked_hit": [fact_id], "discomfort": bool}`. `open` = matching facts with `trust_min <= trust`, best first, at most `limit`; `locked_hit` = matching facts above trust; `discomfort` = any `locked_hit`, or any open match with `generates_discomfort`.

- [ ] **Step 1: Write failing tests** in `tests/test_twin.py` using `brain.load_case("mdd_01")`:
  - `test_recall_sleep_open`: `recall(case, 30, "How have you been sleeping?")["open"]` contains `"f_sleep"`.
  - `test_recall_locked_suicide`: at trust 30, "Have you had thoughts of ending your life?" → `"f_passive_si"` in `locked_hit`, not in `open`, `discomfort` True.
  - `test_recall_same_line_unlocked`: same line at trust 90 → `"f_passive_si"` in `open`.
  - `test_recall_no_match`: "Nice weather today" → `open == []`, `locked_hit == []`, `discomfort` False.
  - `test_recall_fast`: 200 calls on mixed lines take < 2 s total (≤ 10 ms each).
- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_twin.py -q` — FAIL (no module).
- [ ] **Step 3: Implement `recall`.** Lowercase, split on non-letters, crude stem (strip trailing `ing|ed|s`); a fact scores 2 per multi-word tag found as a phrase in the text, 1 per single-word tag stem match; score 0 = no match. Add `# shortcut: lexical tags only, no embeddings; upgrade when an embedding model is chosen (Phase D2)`.
- [ ] **Step 4: Run tests** — PASS.
- [ ] **Step 5: Commit** `feat(twin): trust-gated lexical recall`.

### Task 3: Fast-path labels in the reply (schema, prompt, guard, why)

**Files:**
- Modify: `server/patient-service/brain.py` (`build_reply_schema`, `turn_context`/`build_messages`, `build_system_prompt`, `guard`)
- Modify: `server/patient-service/twin.py`
- Test: `tests/test_brain.py`, `tests/test_twin.py`

**Interfaces:**
- Consumes: `twin.recall` (Task 2), `brain/behaviours.json` (Task 1).
- Produces:
  - `brain.build_reply_schema(case, allowed_fact_ids, actions=None)` — properties now start `reaction` (enum of reaction ids), `intensity` (integer 0–10), `behaviour` (enum), `resistance` (enum), then `emotion`, `utterance`, … unchanged; all four new keys required.
  - `brain.build_messages(case, state, messages, summary=None, elapsed_min=None, recalled=None)` — `recalled` is a `recall()` result; the transient context gains a block "WHAT COMES TO MIND" listing only `open` fact lines (existing `_fact_line` format) and, if `discomfort`, one line: "The doctor is close to something painful you are not ready to talk about. Show discomfort; do not reveal it." Locked fact text never appears.
  - System prompt gains the behaviour menu (id: description) and `core_belief`, `attachment_style`, `dialect` when present.
  - `brain.guard` output adds `reaction, intensity, behaviour, resistance`: unknown id → `"none"` (behaviour → `"answers_plainly"`) with a `guard_dropped` entry `{"kind": "label", ...}`; intensity clamped to 0–10.
  - `twin.why(recalled: dict, reply: dict, trust: float, case: dict) -> str` — one plain sentence, built by code, e.g. `"Sleep memory open (trust 42 ≥ 10). Reaction wary, answers guarded and short."`; mentions a locked hit as `"Touched something locked (needs trust 55); showed discomfort."` using the lowest `trust_min` among `locked_hit`.

- [ ] **Step 1: Write failing tests:**
  - `test_schema_label_order` (test_brain): `list(build_reply_schema(case, [])["properties"])[:6] == ["reaction","intensity","behaviour","resistance","emotion","utterance"]`.
  - `test_prompt_hides_locked` (test_brain): with `recalled={"open":[], "locked_hit":["f_passive_si"], "discomfort":True}`, no message content contains the `f_passive_si` text and one contains "not ready to talk about".
  - `test_guard_bad_labels` (test_brain): reply with `reaction:"furious"`, `intensity:14` → `reaction == "none"`, `intensity == 10`, two `label` entries in dropped.
  - `test_why_locked` (test_twin): `why({"open": [], "locked_hit": ["f_passive_si"], "discomfort": True}, reply, 30, case)` contains "locked" and "55" (`f_passive_si.trust_min` in `mdd_01`).
  - Update the `REPLY` fixture in `tests/test_session.py` with the four label keys so existing session tests keep passing.
- [ ] **Step 2: Run** `.venv/bin/python -m pytest -q` — new tests FAIL.
- [ ] **Step 3: Implement** the schema, prompt and guard changes in `brain.py`, and `twin.why`. Keep the KV-cache layout comment true: the behaviour menu goes in the fixed system prompt; the recall block goes only in the transient context.
- [ ] **Step 4: Run all tests** — PASS. Confirm `stream.UtteranceStream` still finds the utterance with labels first (existing stream tests cover this; add a case if they don't).
- [ ] **Step 5: Commit** `feat(twin): reaction/behaviour/resistance labels before the utterance`.

### Task 4: Slow-path update and expression (`twin.update`, `twin.expression`)

**Files:**
- Modify: `server/patient-service/twin.py`, `unity/PsychSim/Assets/StreamingAssets/data/state_rules.json` (+ its schema)
- Test: `tests/test_twin.py`

**Interfaces:**
- Consumes: guarded reply (Task 3), `brain.apply_turn`, `expression_map.json`.
- Produces:
  - `update(state: dict, mood: dict, reply: dict, case: dict) -> tuple[dict, dict]` — new state = `brain.apply_turn(state, reply)` plus the reaction's `trust_step × state_rules["reaction_trust_unit"]` on trust, clamped by `clamp_per_turn` and range exactly as `apply_turn` does; new mood = `{p,a,d}` each moved 30% of the way (`state_rules["mood_rate"] = 0.3`) toward `pad_from(new_state)`, each clamped to [−1, 1].
  - `pad_from(state: dict) -> dict` — same formula as `padFrom` in `twin/twin.js` (copy it exactly, including `d`).
  - `expression(reply: dict, case: dict) -> dict` returning `{"cues": [{"id","intensity","duration_s"}], "speed": float}`: cues from the reaction and behaviour entries whose id exists in `case["cues"]`, intensity scaled by `reply["intensity"]/10`, `duration_s` 3.0; speed = product of factors, clamped to [0.8, 1.2].
  - `state_rules.json` gains `"reaction_trust_unit": 2` and `"mood_rate": 0.3` (draft numbers).

- [ ] **Step 1: Write failing tests:**
  - `test_update_understood_raises_trust`: reaction `understood` (set its `trust_step` to 1 in Task 1) with zero `state_delta` and no intents → trust rises by exactly `reaction_trust_unit`.
  - `test_update_clamped`: `state_delta.trust = 10`, reaction step +2, intents with large nudges → trust rise ≤ `clamp_per_turn`.
  - `test_mood_moves_toward_target`: from `pad_from(state)` the mood after one update is between old mood and `pad_from(new_state)` on every axis.
  - `test_pad_from_matches_js`: `pad_from({"trust":30,"distress":55,"agitation":15,"engagement":35})` equals values computed by hand from the JS formula (write them as literals in the test).
  - `test_expression_filters_unknown_cues`: a map cue not in the case is dropped; speed stays within [0.8, 1.2].
- [ ] **Step 2: Run** — FAIL.
- [ ] **Step 3: Implement** `pad_from`, `update`, `expression`; add the two keys to `state_rules.json` and its schema.
- [ ] **Step 4: Run** `.venv/bin/python -m pytest -q` and `.venv/bin/python validate_data.py` — PASS / exit 0.
- [ ] **Step 5: Commit** `feat(twin): categorical trust step, PAD mood drift, expression map`.

### Task 5: Wire the Twin into `Session.run_turn` and emit snapshots

**Files:**
- Modify: `server/patient-service/session.py`
- Modify: `server/patient-service/twin.py` (snapshot builder)
- Test: `tests/test_session.py`

**Interfaces:**
- Consumes: Tasks 2–4.
- Produces:
  - `Session.mood` (initialised in `start` to `twin.pad_from(state)`), `Session.brain_version` = `"twin-0.1"` (constant `twin.VERSION`).
  - `twin.snapshot(turn: int, doctor: str, reply: dict, recalled: dict, state: dict, mood: dict, why: str, cues: list) -> dict` returning the README snapshot shape plus `"type": "brain_snapshot"`, `"brain_version"`: keys `type, turn, doctor, utterance, state, mood, reaction, intensity, behaviour, resistance, why, recalled, locked_hit, cues, exam_action, emotion, brain_version`.
  - WebSocket messages, in order per turn: `{"type":"twin_event","event":"doctor_end","turn":n}` when the transcript is final; `{"type":"twin_event","event":"patient_start","turn":n}` at the first `speaking`; after the reply, the `brain_snapshot`; then `{"type":"twin_event","event":"patient_end","turn":n}`. At `start`: `{"type":"twin_event","event":"init","meta":{case_id, patient, age, variant, title},"memory_items":[{id,label,trust_min,gated}],"formulation":{...},"state_start":{...}}` where `label` is the first 40 characters of the fact text and `gated` = `must_be_asked`.

- [ ] **Step 1: Write failing tests** in `tests/test_session.py` with the existing fakes:
  - `test_turn_emits_snapshot`: one text turn → exactly one `brain_snapshot` after the `reply` message; it has every key listed above; `recalled` contains `f_sleep` for the fixture line "How do you sleep?".
  - `test_init_event_on_start`: first `twin_event` after `session` is `init` with 20 memory items for `mdd_01` and no fact text longer than 40 characters in labels.
  - `test_locked_text_not_sent`: for a locked-hit line, no message's JSON contains the locked fact's full text.
  - `test_barge_in_snapshot`: cancel mid-stream (existing barge-in test pattern) → still exactly one snapshot; its `utterance` ends with "..."; `Session.mood` changed once.
  - `test_staged_unchanged`: with staged mode on (existing staged test), the snapshot is the scripted one (`"staged": True`) and `twin.recall` is never called (monkeypatch it to raise).
- [ ] **Step 2: Run** — FAIL.
- [ ] **Step 3: Implement.** In `run_turn`: call `twin.recall` before building messages (pass `recalled` to `build_messages`); after the guard, merge `twin.expression` cues into `reply["event_cues"]` (cap 2 total, case cues only) and multiply the TTS speed for the *next* turn's sentences by its `speed` (this turn's speech has already started); replace `self.state = brain.apply_turn(...)` with `self.state, self.mood = twin.update(...)`; send the snapshot and events. Log only counts and ids in `log.info`, never text (README rule).
- [ ] **Step 4: Run** `.venv/bin/python -m pytest -q` — all PASS.
- [ ] **Step 5: Latency gate.** Start the live stack (`server/patient-service/run.sh` without `RAPPORT_STAGED`), run `server/patient-service/.venv/bin/python tools/latency/ws_bench.py <scratch> --runs 1 --json <scratch>/twin.json`. Expected: p50 `audio_start_ms` ≤ 1,766. Over that: stop, report the stage breakdown.
- [ ] **Step 6: Commit** `feat(twin): Twin drives live turns; brain_snapshot and turn events`.

### Task 6: Twin bus, live Twin view, session log and replay

**Files:**
- Create: `server/patient-service/twin_bus.py`, `tools/demo/log_to_timeline.py`
- Modify: `server/patient-service/app.py`, `server/patient-service/session.py`, `server/patient-service/twin/twin.js`, `server/patient-service/twin/README.md`, `.gitignore`
- Modify: `unity/PsychSim/Assets/Scripts/Core/EncounterManager.cs` (the `switch` at line ~205)
- Test: `tests/test_session.py`, `tests/test_api.py`, `tests/test_twin.py`

**Interfaces:**
- Consumes: the messages from Task 5.
- Produces:
  - `twin_bus.publish(event: dict) -> None` (non-blocking; drops for any viewer whose queue holds more than 200 events), `twin_bus.subscribe() -> asyncio.Queue`, `twin_bus.unsubscribe(q) -> None`. `Session` publishes every `twin_event` and `brain_snapshot` (unwrapped to the twin.js `push` shape: `{"type": "init"|"doctor_end"|..., ...}` or the snapshot) with `t` = seconds since session start.
  - Route `@app.websocket("/twin/ws")` streams bus events as JSON text; a viewer connecting mid-session first receives the session's events so far (keep the current session's list in `twin_bus`, reset on `init`).
  - Session JSONL: `<repo>/logs/twin/<YYYYmmdd_HHMMSS>_<case_id>.jsonl`, one bus event per line; `logs/` is git-ignored.
  - `log_to_timeline.py <session.jsonl> -o <timeline.json>`: builds the README timeline (`meta`, `memory_items`, `formulation`, `state_start` from the `init` event; `events` = the rest, sorted by `t`, snapshots typed `"snapshot"`).
  - twin.js: with `?live=1&ws=<url>` opens a WebSocket (reconnect every 2 s) and calls `push` per message; default `ws` = `ws://<location.host>/twin/ws` when served by the service.
  - Unity: `case "brain_snapshot": Log.Write("brain_snapshot", o); break;`.

- [ ] **Step 1: Write failing tests:**
  - `test_bus_never_blocks` (test_twin): publish 1,000 events with one subscriber that never reads → returns in < 0.5 s; queue length ≤ 200.
  - `test_session_publishes` (test_session): after one turn, a subscriber's queue holds `init`, `doctor_end`, `patient_start`, a snapshot, `patient_end` in that order, each with a numeric `t`.
  - `test_twin_ws_replays_history` (test_api, FastAPI `TestClient`): publish two events, then connect to `/twin/ws` → receives both.
  - `test_log_to_timeline` (test_twin): feed a 5-line JSONL fixture; output has the `init` fields at top level and 4 events sorted by `t`.
- [ ] **Step 2: Run** — FAIL.
- [ ] **Step 3: Implement** `twin_bus.py`, the route, publishing and JSONL writing in `Session`, the converter, the twin.js WebSocket client, the `.gitignore` entry, the README "Live feed" update, and the one-line Unity case.
- [ ] **Step 4: Run** `.venv/bin/python -m pytest -q` — PASS. Compile Unity (refresh, read console: zero errors).
- [ ] **Step 5: Look at it live.** Start the stack; open `http://127.0.0.1:8765/twin/?live=1` in a browser; play 4 turns in Unity Play mode (or `ws_bench.py --runs 1`). Screenshot the Twin view at 1440×900 and 1920×1080, dark and light; look at each: gauges move, memory chips unlock, `why` shows. Then convert that session's JSONL and open `?timeline=<file>`; scrub to turn 3 and check it matches the live screenshot.
- [ ] **Step 6: Commit** `feat(twin): live Twin view over /twin/ws, session log and replay`.

### Task 7: Docs and decision record

**Files:**
- Create: `docs/TWIN.md`, `docs/adr/0001-digital-twin-architecture.md`
- Modify: `HANDOFF.md` (§2 State, §5 Next steps), `server/patient-service/README.md` (new messages, `/twin/ws`)

- [ ] **Step 1: Write `docs/TWIN.md`:** components and where each lives (file:function), the per-turn order (fast path vs slow path), the snapshot fields, the catalogue, the two plan decisions (lexical recall; `facts` key kept), what is draft, and the measured p50/p90 from Task 5 Step 5. It supersedes `PATIENT_BRAIN.md` §3–5; add a one-line pointer at the top of `PATIENT_BRAIN.md`.
- [ ] **Step 2: Write the ADR:** context, decision (one structured call with labels first; code-side updates; lexical recall for now), consequences, alternatives rejected (PatientAct's ~6 calls per turn; embeddings now).
- [ ] **Step 3: Update `HANDOFF.md` and the service README.** Check: `grep -rn "Sanvaad\|Chitta" --include=*.md .` returns nothing new.
- [ ] **Step 4: Commit** `docs(twin): TWIN.md, ADR 0001, handoff`.

---

## Later plans (not in this one)

Each gets its own plan when this one lands, in this order:

1. **Phase A audit** (`docs/STATE_AUDIT.md`, owner feedback → root causes, mic-send-fix latency re-measure). Can run before or alongside this plan; it changes no code.
2. **Phase B rename** (GitHub repo, Unity product/bundle id, menus, `PSYCHSIM_*` → `RAPPORT_*` aliases, `Rapport.command`). Outward-facing; needs the owner's go-ahead for `gh repo rename`.
3. **Phase C literature matrix** and **D8 PatientHub baseline** (`docs/brain-baseline.md`).
4. **Phase E learning** (experience library, faculty principles, GEPA, self-play, `LEARNING_REPORT.md`, blind A/B checkpoint) and the Twin view's Learning tab.
5. **Phase G voice** (TTS bake-off checkpoint, Smart Turn, incremental STT, ≤ 700 ms target).
6. **Phase H camera and exam router** (Cinemachine close-ups, IK incl. `cue_wipe_tears`, ≥ 300-utterance test set).
7. **Phase I** gates, demo v3 with live replies, README, release `v0.2-twin`.
8. Substance-case states (SimPatient, ConsistentMI stage of change) arrive with the first substance case.
