# Digital Twin

The Digital Twin is the patient's mind for each live turn. It decides what the patient recalls, what stays locked, how they answer and how their trust and mood change; the language model only voices that choice. It supersedes `PATIENT_BRAIN.md` §3–5. Brain-inspired, **not** a neural simulation. All clinical content is draft.

Version: `twin-0.2` (sent in every snapshot as `brain_version`, e.g. `twin-0.2+v2`). The twin-0.2 features are switched on per
brain version (`learned/versions/<id>.json` `features`): `v2` has them all, `v0` none, so `python learning.py rollback v0` restores
the twin-0.1 behaviour on the voice path. The section "twin-0.2" below describes them; the table that follows is the v0 order.

## Per-turn order

| Step | Path | Where | What it does |
|---|---|---|---|
| 1. Recall | fast, no LLM, < 10 ms | `twin.recall` | Matches the doctor's words to each fact's `activation_tags` (stemmed words; phrases with possessives folded, so "ending their life" matches "ending your life"). Open matches (trust ≥ `trust_min`) best first, max 3; locked matches are only reported as `locked_hit`. |
| 2. Prompt | fast | `brain.build_messages(..., recalled=)` | The per-turn tail gets "WHAT COMES TO MIND": the open facts only. A locked hit adds one line telling the patient to show discomfort, be evasive and neither reveal nor flatly deny. Locked fact text never enters the prompt or any message. |
| 3. One structured call | fast | `brain.build_reply_schema` | Field order: `behaviour, emotion, utterance, reaction, intensity, resistance, state_delta, event_cues, revealed_fact_ids, exam_action`. Only `behaviour` and `emotion` precede the words (see the ADR on latency). |
| 4. Guard | fast | `brain.guard` | Unknown labels fall back (`reaction`/`resistance` → `none`, `behaviour` → `answers_plainly`), `intensity` is clamped to 0–10; each fix is listed in `guard_dropped`. |
| 5. Expression | after the voice | `twin.expression` | Reaction and behaviour add cues from `data/brain/expression_map.json` (only cues the case has, no duplicates, max 2 in total) and a TTS speed factor applied to the next reply. |
| 6. Update | after the voice | `twin.update` | The reaction's `trust_step × reaction_trust_unit` joins the model's trust delta before the single clamp in `brain.apply_turn`; the PAD mood moves `mood_rate` (0.3) of the way toward `pad_from(new state)`. The model proposes, the code decides. |
| 7. Snapshot | after the voice | `twin.snapshot`, `Session.twin` | One `brain_snapshot` per turn, plus `init`, `doctor_end`, `patient_start`, `patient_end` events, to the client, the Twin view bus and the session log. |

The reason line (`why`) is built by code (`twin.why`), not by the model: e.g. "Mood memory open (trust 39 ≥ 20). Touched something locked (needs trust 55); showed discomfort. Reaction afraid, guarded short."

## Typed mode (`POST /reply`)

The typed path uses the same recall and the same locked-hit rule, but the client applies state with `brain.apply_turn` (Unity `PatientState`), so the reaction's trust step and the PAD mood are voice-path only for now.

A painful locked hit always ends with a reaction that does not raise trust (`twin.enforce_discomfort`; changed to `wary` and listed in `guard_dropped`). Replies are validated against a loose copy of the schema (`brain.loose`), so out-of-range numbers or unknown labels are clamped by the guard instead of turning the whole reply into a fallback.

## Data

- `data/brain/behaviours.json`: 16 reactions (each with `trust_step` −2..2), 13 behaviours, 4 resistance styles, each with a description and an example line.
- `data/brain/expression_map.json`: reaction/behaviour → cues + speed.
- Case facts (key stays `facts`; code calls them memory items) gain `activation_tags`, `kind`, `generates_discomfort` and an optional examiner-facing `label` (≤ 40 chars). Cases gain `formulation` (5Ps), `core_belief`, `attachment_style`, `dialect`. Migrate a case with `server/patient-service/scripts/migrate_memory.py <case.json>`, then hand-write the tags.
- `state_rules.json` gains `reaction_trust_unit` (2) and `mood_rate` (0.3), both draft.
- Seeded patients (`slots`, `styles_allowed`), conversation styles (`data/brain/styles.json`) and ward `events`: `docs/PATIENTS.md`.

## Twin view

- Live: `http://127.0.0.1:8765/twin/`. The page reads `ws://<host>/twin/ws`; a late viewer receives the session so far and its clock catches up.
- Replay: every live session is logged to `logs/twin/<time>_<case>.jsonl` (git-ignored, local only). `python3 tools/demo/log_to_timeline.py <log> -o <timeline.json>`, then `?timeline=<url>`.
- Unity writes each `brain_snapshot` to its `SessionLog`.

## Measured

`tools/latency/ws_bench.py --runs 1`, 26 turns, Gemma 4 E4B, M5 Pro, 2026-10-20: reply audio ready p50 1,598 ms, p90 1,731 ms (the same-day run before the Twin: p50 1,853 ms). With all four labels before the utterance it was p50 3,068 ms.

## Known limits

- (v0 only) Recall is lexical. twin-0.2 adds embeddings; see below.
- At low trust the patient still tends to say "No... not like that" to a direct suicide question; tune in the voice-quality pass (Phase G).
- (v0 only) Reaction is generated after the words. In twin-0.2 code decides the reaction shortlist before the call.
- Substance-case states (SimPatient, stage of change) and learning are later plans.

## Decisions (supersede `PATIENT_BRAIN.md` §3–6)

- **Name:** the product is Rapport (ADR 0003); the brain is the Digital Twin.
- **Experience library, two tiers:**
  - *candidate*: the reply passed the automatic checks (no invented facts, no banned words, the case rules followed, a length that fits the state). Practice mode uses candidates.
  - *approved*: faculty gave it a thumbs-up. Assessment mode uses approved entries only.
- **Consent:** learner sessions never feed learning unless that session's consent flag is set. The flag is off by default. A learner's words never become patient facts.
- **Learning changes how the patient talks, never the clinical facts, the answer key or the scoring.** Every brain change gets a version number (`brain_version`) and can be rolled back.
- **One LLM call per live turn.** Critique, reflection, adherence checks and prompt optimisation all run offline and reach the patient only through the prompt.

## Literature basis

83 papers were reviewed in Phase C. The notes are in `docs/literature/notes/` and the table is in `docs/literature/matrix.md`. `docs/literature/insights.md` maps each insight to a Twin component, marked built, Phase E, later or rejected. Next steps it points to, outside Phase E:

- a Mental Status Exam block in the case (PSYCHE);
- a rubric table in code that turns the doctor's last move into a clamped resistance and trust step (Adaptive-VP);
- explicit rules for when resistance softens;
- a contradiction check against atomic case facts after the call (Patient-Zero);
- debrief items backed by verbatim quotes (MedSimAI).


## twin-0.2 (v0.3, 2026-11-14)

One pipeline for both paths (`mind.py`): the voice session (`session.run_turn`) and typed `POST /reply` (`brain.generate_reply`)
run the same steps. The typed path returns the new `state` and the session's `twin` (the mind: mood, memory, resistance, fired
events), which the client sends back next turn (`mind.load` and `memory.sanitize` check every field), so typed turns now get ward
events, the trust step and the PAD mood too. Unity's `PatientBrain` applies the service's state and carries the mind.

| Step | Where | What it does |
|---|---|---|
| Move | `rubric.moves`, `data/brain/rubric.json` (draft) | Reads the doctor's line as moves: greeting, open/closed question, empathy, explaining why, apology, choice, summary, judgement, abuse, threat, premature reassurance, jargon, stacked questions, rushing, jailbreak, "are you an AI", small talk, repeated question, interruption, risk question. Code only. |
| Pre-step | `rubric.pre_step` | The moves step trust, distress, agitation and engagement before recall (style gains; a kind line never lowers trust), so a kind risk question can be answered kindly. The prompt prefix still uses the start-of-turn state (cache). |
| Recall | `twin.recall` | Tags plus bge-small-en-v1.5 similarity over each fact's `recall_probes`, generated doctor lines (`data/recall/<case>.json`), tags and text; thresholds in `data/brain/recall.json` (dev half). Trust locks after matching. `strong` hits (tag or similarity >= `SIM_STRONG`) are the only ones that can force a disclosure. |
| Resistance | `rubric.resistance` | Level 0 open .. 3 hostile. Rises with judgement, abuse, threats (+2) and interrupting, rushing, premature reassurance (+1); falls by one a turn with validation, explaining why, apology or a choice, and after two calm turns towards the style's base; capped at 1 past the style's `softens_at_trust`. An upset style starts at 2. |
| Decide | `rubric.decide` | Shortlists 1-3 behaviours, reactions and resistance labels; the reply schema only allows those (the model picks within). Open risk fact asked kindly and strongly: disclose behaviours. Locked hit: evasive behaviours, never `denies`. Variety: a behaviour used on each of the last two turns goes to the back. MSE: no tangents unless the case allows them. |
| Memory | `memory.py` | Episodes: what the patient already told (and in what words), locked questions, hurt and its repair, kindness, promises, permission to leave, and everyday backstory the patient made up. At most three lines a turn ("You asked me that already"). |
| Prompt | `brain.build_messages` | Post-tail adds `THIS MOMENT` (the decision) and `REMEMBERS FROM THIS CONSULTATION`. System prompt adds the case's MSE line and, with `improvise`, a hard rule that allows made-up everyday details and forbids anything clinical. |
| Speech | `mind.speakable`, `consistency.py` | Every sentence before TTS: numbers and durations corrected to the facts the line touched, age, fixed names (a brother is always Rohan), the death wish dropped when locked or never asked (`locked_leak`, `volunteered_risk`), apology stripped while an upset patient is still upset, near-repeats dropped. A possible flat denial is held to the end of the reply: an open, kindly asked risk fact is never flatly denied (the case's `disclosure_line` is said instead), a locked one gets evasion, not "No". Every clash is in `meta.consistency` and the Twin log. |
| After | `mind.finish` | Guard, labels held to the shortlist, MSE intensity cap; state update with the model's own trust delta limited to +-3 and the per-turn clamp counted from the start of the turn; mood; memory. |
| End | `mind._should_end` | Three hurtful moves within six turns at trust <= 15, or agitation >= 90: the patient ends the interview (stage direction, stands up, `patient_ended` to Unity, which turns hands-free off). |

Voice: one TTS instruction per reply (with Qwen3-TTS VoiceDesign the instruction is the speaker, so a new one per sentence drifted),
carrying the decided reaction from the first word, scaled by distress or agitation, with pace words and a pitch-preserving stretch.

Case data added (draft, for clinician review): `mse` blocks, `disclosure_line` on must-ask risk facts, `recall_probes`, `topics`.
Measured results and gates: `docs/GATES_v0.3.md`.
