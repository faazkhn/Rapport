# Rapport

**Rapport (formerly PsychSim)** is a psychiatry OSCE simulator that runs on one Mac. The doctor talks out loud to a 3D patient, who answers in a synthetic voice, with facial and body cues. The patient's mind is the **Digital Twin**: code decides what the patient remembers, what stays locked until there is enough trust, and how trust and mood change, and a local language model voices that choice. At the end, a scored debrief covers history, risk, the mental state exam, diagnosis and management.

It was renamed because `usc-psychsim/psychsim` is an established research framework with the same name (`docs/adr/0003-rename-to-rapport.md`). The C# namespaces are now `Rapport.*`; only the Unity folder `unity/PsychSim` still carries the old name (issue #2).

> **Draft clinical content. For education only.** Not validated by faculty, and not a medical device. See [Disclaimer](#disclaimer).

## Teaser

[`docs/media/teaser.mp4`](docs/media/teaser.mp4): 18 s, 1280×720, from an earlier take (the UI still reads "PsychSim"). That take predates the Digital Twin and the new voice.

Demo v3: `demo/Rapport_demo_v3.mp4` (3:06, one continuous take, live replies, attached to the release, not kept in git). A different interview from v2: a full session with Arjun, new questions in a new order, the look-at-the-light exam, and the risk question asked early. Arjun withholds the passive death wish at trust 53 and discloses it when the doctor comes back to it at trust 61. The script is `demo/v3/script.json`; record with **Rapport/Record Demo v3 (Arjun, new script)**. The earlier take with Ananya is `demo/PsychSim_demo_v2.mp4`.

The older demos are not in git (LFS budget). In `demo/Rapport_demo_staged.mp4` the patient's replies are **pre-scripted** (staged mode, `RAPPORT_STAGED`). Say so whenever you show it.

## Features

- **Voice in, voice out, all local.** Silero VAD and Smart Turn end the doctor's turn, Parakeet transcribes it, Gemma 4 E4B (llama.cpp) writes the reply as streamed JSON, and Qwen3-TTS VoiceDesign speaks it sentence by sentence. KittenTTS is the fallback. The doctor can interrupt the patient (barge-in). Push-to-talk and typed input also work.
- **One case, two patients.** `mdd_01` ("Tired all the time"): a 24-year-old software test engineer in Bengaluru with depression. It is played by Ananya (`female`) or Arjun (`male`). The patient's facts, cues, rubric and answer key are in `unity/PsychSim/Assets/StreamingAssets/data/cases/mdd_01.json`.
- **Surprise me: a different patient each time** (branch `personalities`, draft). A seed varies the person but never the answer key: family details, a hobby, the home town, and one of six conversation styles (plain, reserved, eager to please, upset, talkative, tangential), each turned into code parameters. Assessment mode keeps the authored style. See [`docs/PATIENTS.md`](docs/PATIENTS.md).
- **A ward station with things that happen** (draft): `ward_01` "I want to go home", the same patient a week later on the acute ward asking to leave. Code-timed events (a shout in the corridor, standing up when agitation peaks, a message from mother) and marking on reasons, risk, capacity, rights and choices under the Mental Healthcare Act 2017.
- **Digital Twin** with trust-locked memory, reactions, behaviours, resistance and a PAD mood (below), plus a live **Twin view** for the examiner.
- **Exam commands** in the doctor's own words, typed or spoken: "hold out your hands", "show me your tongue", "roll up your sleeves", "look at the light", "follow my finger", "stand up and walk a few steps", "sit down", "relax". A rule-based router handles them in the service. The patient refuses at low trust or high agitation, asks "Which hand?" when it is unclear, and holds a pose until told to relax (`docs/exam-actions.md`). Unity plays them with hand IK and a close-up camera (`docs/camera.md`).
- **Camera:** a Cinemachine doctor view at 42° FOV, scroll to lean in, and close-ups for each exam action ([stills](docs/camera.md)).
- **Tablet and debrief:** MSE, Diagnosis, Prescription and Disposition tabs, then a scored, formative debrief with risk-first critical items.

| Doctor view | Hands close-up | Face close-up |
|---|---|---|
| ![](docs/media/camera/camera_doctor.jpg) | ![](docs/media/camera/camera_hands.jpg) | ![](docs/media/camera/camera_face.jpg) |

## The Digital Twin and the Twin view

Spec: [`docs/TWIN.md`](docs/TWIN.md). Decision: [`docs/adr/0001-digital-twin-architecture.md`](docs/adr/0001-digital-twin-architecture.md). It is inspired by the brain, **not** a neural simulation.

Every live turn:

1. **Recall** (no LLM, under 10 ms): the doctor's words are matched to each memory item's activation tags. Items the patient trusts the doctor enough to share come to mind. A **locked** item that was touched only makes the patient uncomfortable and evasive; its text never enters the prompt.
2. **One structured LLM call.** Field order: `behaviour, emotion, utterance, reaction, intensity, resistance, …`. Only behaviour and emotion come before the words, which keeps latency down.
3. **Guard:** unknown labels fall back, numbers are clamped, and locked or unknown facts are dropped. Every fix is listed in `guard_dropped`.
4. **Expression** from a fixed map (`data/brain/expression_map.json`): facial and body cues plus the voice's emotion and speed.
5. **Update:** trust moves by the model's delta plus the reaction's step, then a single clamp. The mood moves 30% of the way toward the new state. The model proposes; the code decides.
6. **Snapshot:** one `brain_snapshot` per turn goes to Unity, the Twin view and a local session log.

The **Twin view** (`http://127.0.0.1:8765/twin/?live=1`) shows trust and the other states, the mood dot, memories unlocking (a grey chip turns green), the reaction and behaviour, and a reason line written by code, e.g. "Touched something locked (needs trust 55); showed discomfort." The brain is a 3D glass model you can turn and zoom. Each zone glows with its activity, and every memory item is a node inside it: deeper means it needs more trust, and a lock means locked. Each turn draws its thought path: what was heard, what was recalled, the behaviour chosen, what was said. Zoom in for memory labels, stay in the middle for a live card per zone, zoom out for zone names with activity. Click a node for details. A 2D button switches back to the flat map (`server/patient-service/twin/README.md`).

| Thought path (regions) | Zoomed in (memory) | Zoomed out (zones), light theme |
|---|---|---|
| ![](docs/media/twin/twin3d_regions.jpg) | ![](docs/media/twin/twin3d_detail.jpg) | ![](docs/media/twin/twin3d_light.jpg) |

Every session is logged to `logs/twin/*.jsonl` (git-ignored; it holds the conversation text and stays on this Mac) and can be replayed (`tools/demo/log_to_timeline.py`).

## Learning and its guardrails

Self-learning (Phase E) is built (ADR 0004, `server/patient-service/learning.py`, `tools/learning/`): an experience library of vetted replies (L1), faculty feedback turned into case principles (L2), and GEPA prompt optimisation of the realism rules, promoted only when it beats the live version on a held-out set (L3). Simulated doctors (excellent, average, rushed, judgmental, prompt-injector) generate the learning data; the held-out scripted conversations are never used for learning. Guardrails:

- **Learning changes how the patient talks, never the clinical facts, the answer key or the scoring.**
- **Two tiers of experience library.** *Candidate* entries passed the automatic checks (no invented facts, no banned words, the case rules followed, a length that fits the state); practice mode uses them. *Approved* entries got a faculty thumbs-up; assessment mode uses only these.
- **Consent.** A learner's session feeds learning only if that session's consent flag is set, and the flag is off by default. A learner's words never become patient facts.
- **Versioned and reversible.** Every brain change gets a `brain_version` and can be rolled back.
- **One LLM call per live turn.** Critique, reflection, adherence checks and prompt optimisation all run offline. They reach the patient only through the prompt.

**Result so far** ([`docs/LEARNING_REPORT.md`](docs/LEARNING_REPORT.md)): one learning round. v1 (v0 plus 36 self-play examples; GEPA found no better rules) scored 0.952 against v0's 0.957 on the held-out set and had one confirmed safety flag (it denied a passive death wish), so the gate rejected it and **v0 stays live**. The flag exposed a recall bug, now fixed. The 5-round curve and the blind A/B test are still to do.

## Voice stack and licences

| Part | Model / tool | Licence | Source |
|---|---|---|---|
| Patient LLM | Gemma 4 E4B, Q4_K_M GGUF, on llama.cpp `llama-server` | Gemma terms | `models/README.md` |
| Speech to text | Parakeet TDT 0.6B v2 (`mlx-community/parakeet-tdt-0.6b-v2`) | CC-BY-4.0 per its model card (not yet recorded in `models/README.md`) | `server/patient-service/stt.py` |
| Voice activity | Silero VAD | MIT per its repo | `stt.py` |
| Turn end | Smart Turn v3 (`pipecat-ai/smart-turn-v3`, ONNX on CPU) | BSD-2-Clause | `models/README.md`, ADR 0002 |
| Patient voice | Qwen3-TTS 1.7B VoiceDesign via mlx-audio (default, `RAPPORT_TTS=qwen3-design`) | Apache-2.0 | `docs/tts-bakeoff.md` |
| Fallback voice | KittenTTS mini 0.8 | Apache-2.0 | `docs/tts-bakeoff.md` |

The voices are **designed from a text description, never cloned** from a real person. Each reply's emotion and the Twin's reaction set the voice's tone (`voice.instruction`, `expression_map.json`).

The TTS bake-off (`docs/tts-bakeoff.md`, 2026-10-21) used a decision rule fixed before the run. Qwen3-TTS VoiceDesign won: time to first audio 174 ms, real-time factor 0.57, word accuracy 1.0, emotion separation 3.92 (KittenTTS 0.67). Kokoro, Qwen3-TTS 0.6B and Chatterbox were not tested because the Mac was offline, so they are untested, not rejected. Known risk: the speaker can drift between sentences, because pitch spread across 8 neutral lines is 6.7 semitones against 2.1 for KittenTTS.

Not adopted: kitten-tts-2 (revenue-capped licence), kyutai pocket-tts (gated repo), and Pipecat as a framework (ADR 0002). Cloud backends are optional and off by default. `PATIENT_LLM=grok` sends the conversation to xAI.

## Measured latency

Lag is the time from the end of the doctor's speech to the first patient audio being ready. It is measured through the real WebSocket path with `tools/latency/ws_bench.py` (synthesised doctor audio as 32 ms frames; Apple M5 Pro, 24 GB). All numbers are from [`docs/latency.md`](docs/latency.md).

| Build (date) | Lag p50 | Lag p90 |
|---|---|---|
| Baseline, KittenTTS (2026-10-20) | 3,046 ms | 4,100 ms |
| After the prefill and template fixes, KittenTTS (2026-10-20) | 1,616 ms | 1,796 ms |
| Phase G: Qwen3-TTS + speculative STT (2026-10-21) | 2,326 ms | 3,018 ms |
| + Smart Turn + tail before the doctor's words, run 1 (2026-10-21) | **2,164 ms** | 4,024 ms |
| Same, run 2, GPU shared with another job | 2,488 ms | 3,648 ms |

**The 700 ms p50 target is missed by about 1.5 s.** The emotional voice and the longer, more natural replies cost about 0.5–0.7 s compared with the KittenTTS build. What remains is mostly the first sentence (about 0.9 s after the first token) and TTS sharing the GPU with the LLM. Each figure comes from one 26-turn run, so the p90s are noisy. For `mdd_01`, part of the lag is hidden by the patient's clinically intended hesitation (psychomotor slowing). Next steps are in `docs/latency.md`. Barge-in stops the voice in about 30–60 ms.

## Literature basis

Phase C reviewed **83 papers** on LLM patient simulators: 37 read in full, 35 from the abstract only, 11 not reachable. Verdicts: adopt 1, adapt 21, idea-only 38, skip 23 ([`docs/literature/matrix.md`](docs/literature/matrix.md), notes in `docs/literature/notes/`). [`docs/literature/insights.md`](docs/literature/insights.md) maps 28 insights to Twin components. What the field agrees on, and what Rapport does about it:

1. **Keep facts, state and locks in code, and let the model voice them.** Invented details rise when the case is thin or style is pushed hard. An NLI verifier cut hallucination from 10.5 to 1.8 (Patient-Zero). Rapport does this already.
2. **One live call per turn; everything else offline.** Multi-agent designs (PatientAct at about 6 calls per turn, AIPatient, Concordia) are too slow for live voice.
3. **Resistance has to be designed in, with explicit conditions under which it softens.** Otherwise patients are too agreeable (SimPatient, PSYCHE). Softening rules are still to do.
4. **Learners value the debrief more than the avatar.** In SOPHIE's RCT (n=51), feedback was rated 4.7/5 and the avatar 3.4/5.
5. **LLM judges alone are weak evidence.** The best LLM judge identified roles correctly 68.8% of the time against 90.8% for humans (PersonaEval). Gates need code checks, order-swapped pairwise judging by a model other than the generator, and faculty spot checks.

## How to run

Requirements: an Apple Silicon Mac (measured on an M5 Pro, 24 GB), `llama-server` (llama.cpp) on the PATH, Unity 6000.6.2f1 for the editor or a rebuild, and the model files described in [`models/README.md`](models/README.md). Once the models are downloaded, nothing needs the internet.

```bash
# 1. the patient service (starts llama-server on :8080 if it is not running; serves on :8765)
cd server/patient-service
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r requirements.txt   # first time only
./run.sh                 # PORT=… to change; ./run.sh --mock for a keyword mock with no model; RAPPORT_TTS=kitten for the light voice
curl -s http://127.0.0.1:8765/health
```

2. **The app:** double-click [`Rapport.command`](Rapport.command). It starts the service if needed, opens `unity/PsychSim/Builds/Rapport.app` (a Development build) and stops the service when the app quits. To build it, use the Unity menu **Rapport > Build macOS (Development)**. To use the editor instead, open `unity/PsychSim`, load the scene `Assets/Scenes/Encounter.unity` and press Play.
3. **The Twin view:** `http://127.0.0.1:8765/twin/?live=1`.

[`docs/LIVE_DEMO_GUIDE.md`](docs/LIVE_DEMO_GUIDE.md) has the full checklist, a 6-minute demo script and troubleshooting. The service's endpoints and environment variables are in [`server/patient-service/README.md`](server/patient-service/README.md). `PSYCHSIM_*` variables still work as deprecated aliases for `RAPPORT_*` until v0.3.

Release gates and what was skipped: [`docs/GATES.md`](docs/GATES.md).

Tests:

```bash
cd server/patient-service && .venv/bin/python -m pytest -q      # 153 pass (2026-10-22)
.venv/bin/python validate_data.py                                # data schemas and cross-references
# Unity EditMode: 39 pass (2026-10-21, batch mode)
```

## Roadmap

Open issues ([GitHub](https://github.com/faazkhn/Rapport/issues)):

- #2 Rename the Unity folder from PsychSim to Rapport (namespaces done).
- #3 L4: fine-tune the local patient model on approved transcripts (LoRA via mlx-lm).

Planned but not scheduled ("Later" in `docs/literature/insights.md`):

- A Mental Status Exam block in the case, plus the PSYCHE failure modes (insight 5).
- A rubric table in code that maps the doctor's last move to a clamped resistance and trust step (7), with explicit rules for when resistance softens (8).
- A contradiction check of each utterance against atomic case facts after the call (12), and a flagged list of details the patient improvised, kept consistent (11).
- Debrief items backed by verbatim quotes (22) and post-session ratings from the patient's side (21).
- Cross-session memory as time-stamped cards (23), and substance-use cases with stage of change (13).
- Embedding recall for paraphrases that lexical tags miss (`docs/TWIN.md`, Known limits).
- Latency: start speculative STT earlier, and a shorter opening phrase (`docs/latency.md`).
- More cases, faculty sign-off on `mdd_01`, and ethics approval before any learner pilot (`docs/STATE_AUDIT.md`).

## Disclaimer

Rapport is a teaching prototype. **All clinical content (cases, catalogues, rules, rubric, answer key) is an AI-assisted draft** (`status: draft`, `verified_by: null`, doses left blank). It has **not been validated** by faculty. It is for **education only**. It is **not a medical device**, not for diagnosis or treatment, and not a substitute for supervised clinical training. Release builds are blocked by a content gate until faculty approve the content; only Development builds ship. The patients are fictional, and their voices are synthetic: designed from text, never cloned. The case includes thoughts of death and suicide.

## Credits

Created and directed by **Dr. Faaz** (owner). The models and libraries are listed under [Voice stack and licences](#voice-stack-and-licences) and in `models/README.md`. The literature behind the design is in `docs/literature/`.
