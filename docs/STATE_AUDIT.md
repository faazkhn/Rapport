# State audit (Phase A)

**Date:** 2026-10-20 · **Branch:** `live-digital-twin` (PR #1, includes the Rapport rename) · Spec: `KICKOFF_PROMPT_v4.md` Phase A.

The live voice loop and the Digital Twin work end to end on this Mac and are fast enough to talk to (p50 1.7 s), but they are not production ready. Replies are hesitant and samey, the voice has no emotion, the exam and camera are demo-grade, and no clinical content is faculty-validated.

## What works (with evidence)

| Area | Evidence (2026-10-20) |
|---|---|
| Service tests | 83 pass (`server/patient-service`, `pytest -q`); `validate_data.py` OK |
| Unity EditMode tests | 28/28 pass |
| Voice loop, real mic path | `tools/latency/ws_bench.py --runs 1`: 26 turns, synthesised doctor audio as 32 ms frames, 0 failures |
| Latency | p50 1,687 ms, p90 1,866 ms (doctor stops → patient audio ready); barge-in stop p50 30 ms |
| Digital Twin | per-turn `brain_snapshot`; locked memories never leave the service (tested); live Twin view and replay checked by screenshot |
| TTS intelligibility | 5 real replies synthesised (KittenTTS `Luna`, speed 0.9) and transcribed back with Parakeet: 98% word recall over 52 words |
| Staged demo | `demo/Rapport_demo_staged.mp4`, 4:00, no cards or badges |

## What is broken or missing

- **No GitHub issues exist** (`gh issue list --state all` is empty), although `CLAUDE.md` says the tracker is GitHub Issues. Nothing below is tracked yet.
- **The playable macOS build is stale.** `unity/PsychSim/Builds/PsychSim.app` predates the mic-send fix, the Rapport title and the Digital Twin. `PsychSim.command` launches the old one.
- **No faculty validation.** Every case, catalogue and rule file is `status: draft`; release builds are blocked by the content gate by design.
- **The LLM evaluation suite has not been run on the Twin build** (`tools/llm_eval/run_eval.py`); the last run predates the Twin labels.
- **The repo and product are still named PsychSim**: GitHub repo, Unity product name and bundle id, `PsychSim/…` menus, `PSYCHSIM_*` env vars, `PsychSim.command`, C# namespaces (Phase B).
- **Uncommitted WIP:** `demo/PsychSim_demo_v1.mp4` and `demo/stills/still_1–6.png` are modified in the working tree (binary, LFS, from before this session). Not touched: the owner decides whether to keep or restore them.

## Docs that disagree with the code

- `server/patient-service/README.md` still describes Grok as the default backend and lists `PSYCHSIM_*` variables; the default is the local llama-server.
- `STAGE_1_NOTES.md` still lists the invalid xAI key and 18 service tests as current.
- `DESIGN.md` §7.2 shows the old reply contract (`emotion, utterance, …`); the live contract is in `docs/TWIN.md`.
- `HANDOFF.md` §4 says "41 tests pass"; it is now 83.

## Owner feedback → root causes

| # | Complaint | Root cause (file / config) | Evidence | Fix (phase) |
|---|---|---|---|---|
| a | Replies aren't liked | The prompt over-teaches hesitation: `brain.REALISM_RULES` asks for "hesitate, trail off", and the case `speech_style` says "short sentences with pauses". The model uses only 2 of 13 behaviours, and the engagement band in `brain.describe_state` caps length at about 12 words. | In the last 42-turn session: "..." appears in 29 replies (69%), the average reply is 5.5 words, 41 of 42 turns are `answers_plainly` or `guarded_short`, "I'm not myself" repeats, and work and family get "okay, I guess" despite case facts. | Behaviour variety and length targets by state, less hesitation, repetition control, experience-library examples (G, E) |
| b | Voice type isn't liked | KittenTTS mini 0.8 has 8 stock voices (`session.VOICES`); Ananya is `Luna`, Arjun `Leo`. No voice was designed for the characters. | `mdd_01.json` `variants.*.voice_id` | Bake-off with designed voices; Qwen3-TTS is the lead (G) |
| c | Voice isn't natural | Each sentence is synthesised alone (`session.speak` per `SentenceSplitter` chunk), so prosody resets every sentence; the model has no expressive control. | Architecture; listening test not yet run | Phrase-level streaming TTS and a better model (G) |
| d | Too slow | End of speech → audio: VAD silence 512 ms + STT ~70–470 ms + first sentence ~800 ms + TTS ~190 ms. The kickoff target is p50 ≤ 700 ms. | p50 1,687 ms, p90 1,866 ms | Smart Turn instead of a fixed 500 ms silence, incremental STT, faster first phrase (G) |
| e | Too many pauses | Three sources stack. (1) The `slowed` cue adds a deliberate 1–3 s pre-reply pause for mdd_01 (`brain.slowed_pause_s`). (2) The "..." in most replies becomes long TTS pauses. (3) Speed is 0.9 or lower (`tts_speed`). | 5 real replies of 7–21 words took 5.6–8.6 s to speak: about 1.0–1.4 words/s for short replies, against roughly 2.5 for natural speech | Strip or cap ellipses before TTS, size the `slowed` pause to the case, faster base speed (G) |
| f | No emotion in the voice | KittenTTS takes only text, voice and speed. `emotion` and the Twin's reaction never reach the TTS; only a speed factor does (`twin.expression`). | `session.synth(text, voice, speed)` | Instruction-following TTS driven by the expression map (G) |
| g | Camera angles are poor | `EncounterSceneBuilder` sets FOV 60° (the kickoff asks for 40–45°) at eye height 1.20 m. `DesktopRig` auto-follows the head with a fixed 17° yaw offset, so the patient sits off-centre. There are no close-ups outside `DemoDirector`. The chair faces ~156°, against a 90–120° brief. | `EncounterSceneBuilder.cs:48-50`, `DesktopRig.cs`, HANDOFF §6 | Camera states, Cinemachine close-ups, chair angle (H) |
| h | "Hold out your hand" doesn't work well | No command router exists. An exam action fires only if the LLM chooses `exam_action`, which it generates after the utterance. It is also trust-gated (`roll_up_sleeves` needs trust 30). Only 3 actions have clips (hold_out_hands, roll_up_sleeves, look_at_light). There is no hold-until-relax, no ask-back ("Which hand?") and no IK. | `EncounterManager.cs:255`, `CueDriver.PlayExamAction`, `art/Animations/ANIMATIONS.md` | Embedding + rules router on the transcript, IK presentation, more clips (H) |

## Today's numbers

| Stage | p50 ms | p90 ms |
|---|---|---|
| VAD endpoint | 512 | 512 |
| STT | 72–467 (varies with load) | 111–686 |
| LLM first token | 289 | 359 |
| LLM first sentence | 805 | 886 |
| TTS first chunk | 190 | 250 |
| **Audio ready** | **1,687** | **1,866** |

## What is left for production

1. **B: rename** to Rapport everywhere, including `gh repo rename` (needs the owner's go-ahead; GitHub redirects the old URL).
2. **G: voice and replies** (complaints a–f). Includes a blocking blind listening test for the owner.
3. **H: camera and exam router** (complaints g, h).
4. **C + D8: literature matrix and PatientHub baseline.**
5. **E: learning** (experience library, faculty principles, gated prompt optimisation). Includes a blocking blind A/B test for the owner.
6. **I: release gates.** Run the eval suite, rebuild the macOS app, record demo v3 with live replies, write the README, release `v0.2-twin`.
7. **Owner and faculty, outside code:** clinical sign-off on mdd_01, more cases, and ethics approval before any learner pilot.
