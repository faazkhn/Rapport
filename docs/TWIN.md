# Digital Twin

The Digital Twin is the patient's mind for each live turn. It decides what the patient recalls, what stays locked, how they answer and how their trust and mood change; the language model only voices that choice. It supersedes `PATIENT_BRAIN.md` §3–5. Brain-inspired, **not** a neural simulation. All clinical content is draft.

Version: `twin-0.1` (sent in every snapshot as `brain_version`).

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

## Data

- `data/brain/behaviours.json`: 16 reactions (each with `trust_step` −2..2), 13 behaviours, 4 resistance styles, each with a description and an example line.
- `data/brain/expression_map.json`: reaction/behaviour → cues + speed.
- Case facts (key stays `facts`; code calls them memory items) gain `activation_tags`, `kind`, `generates_discomfort` and an optional examiner-facing `label` (≤ 40 chars). Cases gain `formulation` (5Ps), `core_belief`, `attachment_style`, `dialect`. Migrate a case with `server/patient-service/scripts/migrate_memory.py <case.json>`, then hand-write the tags.
- `state_rules.json` gains `reaction_trust_unit` (2) and `mood_rate` (0.3), both draft.

## Twin view

- Live: `http://127.0.0.1:8765/twin/?live=1`. The page reads `ws://<host>/twin/ws`; a late viewer receives the session so far and its clock catches up.
- Replay: every live session is logged to `logs/twin/<time>_<case>.jsonl` (git-ignored, local only). `python3 tools/demo/log_to_timeline.py <log> -o <timeline.json>`, then `?timeline=<url>`.
- Unity writes each `brain_snapshot` to its `SessionLog`.

## Measured

`tools/latency/ws_bench.py --runs 1`, 26 turns, Gemma 4 E4B, M5 Pro, 2026-10-20: reply audio ready p50 1,598 ms, p90 1,731 ms (the same-day run before the Twin: p50 1,853 ms). With all four labels before the utterance it was p50 3,068 ms.

## Known limits

- Recall is lexical. A paraphrase with none of the tag words is missed; add tags or move to embeddings (Phase D2).
- At low trust the patient still tends to say "No... not like that" to a direct suicide question; tune in the voice-quality pass (Phase G).
- Reaction is generated after the words, so it describes the reply rather than steering it; behaviour steers it.
- Substance-case states (SimPatient, stage of change) and learning are later plans.
