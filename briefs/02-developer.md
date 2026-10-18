# Brief: Developer Agent

**Read first:** all of `DESIGN.md`. It is the source of truth; sections 2–8 describe the systems you build.
**Tools you can use:** the Unity MCP (scripts, scenes, packages, builds, tests).
**Work rule:** build one stage at a time (`DESIGN.md` section 10). Use placeholder art (Unity capsules or a free humanoid) until the artist delivers. Don't wait for them.

---

## 1. Project setup (Stage 0)
- Unity 6 LTS, URP, macOS Apple Silicon build target.
- Packages from day one: XR Interaction Toolkit, OpenXR, Input System, Animation Rigging, TextMeshPro, Unity Test Framework, Newtonsoft JSON.
- Use the **Input System only**, with action maps that work for both mouse and keyboard and XR controllers. No `Input.GetKey` anywhere. This is what makes the VR port cheap.
- Git with LFS for binary assets. Keep a `.gitignore` for Unity.

## 2. Code layout

```
Assets/Scripts/
  Core/         EncounterManager, SessionClock, GameStateMachine
  Data/         CaseLoader, schema-backed C# models, ContentStatusFilter
  Patient/      PatientBrain (LLM), PatientState, GuardCheck, FallbackLines
  Cues/         CueDriver, GazeController, TremorController, MaterialCueController, SpeechTiming
  Speech/       MicCapture, PatientServiceClient (STT + TTS calls), LipSyncBridge
  Tools/        MsePanel, ExamController, ScaleRunner, DiagnosisPicker, PrescriptionPad, Disposition
  Scoring/      IntentLedger, ScoringEngine, PrescriptionChecker, Debrief
  Platform/     InputRouter, DesktopRig, XRRig (Stage 5)
  Logging/      SessionLog
Assets/StreamingAssets/data/   cases/, scales/, cues.json, intents.json, diagnoses.json, dispositions.json, formulary.json, schemas/
Tools~/case-validator/         CLI for faculty (Stage 3)
server/patient-service/        Python service: /stt, /reply (Grok), /tts (KittenTTS); holds the API key
tools/tts/                     KittenTTS smoke test already working (tts_check.py, .venv)
```

Put each assembly in its own `.asmdef` so tests can target it.

## 3. Systems

### 3.1 EncounterManager
A state machine for the phases in `DESIGN.md` §2: `Brief → Enter → Active → Debrief`. "Interview", "Examine", "Assess" and "Plan" are **not** locked steps. The learner moves freely between them, the way a real doctor does. The manager owns the session clock, sends every event to `SessionLog`, and ends the station on time-out or when the learner submits.

### 3.2 CaseLoader
- Loads JSON from `StreamingAssets/data`. Checks each file against the JSON Schema in `data/schemas/` and shows a clear error naming the file and field if it fails.
- `ContentStatusFilter`: development builds load every status; **release builds load only `approved` content**. Enforce it in the build script so it can't be forgotten.

### 3.3 PatientBrain
For each learner turn:
1. Build the prompt: the case persona, the current `PatientState`, the facts allowed **now** (passed `trust_min`; fact ids and text only), the cue ids allowed for this case, the intent list, recent conversation, and the hard rules from `DESIGN.md` §3.3.
2. Call the patient service's `/reply` and ask for the JSON contract in `DESIGN.md` §7.2 (use structured output or tool use so the result is always valid JSON).
3. **GuardCheck:** drop any fact id that is unknown or not unlocked, any cue id not in the case, and clamp `state_delta` to ±10 per value per turn. If the utterance is empty, or the reply failed to parse twice, use a `FallbackLines` entry from the case.
4. Apply the state change and publish a `PatientReplied` event (CueDriver, TTS, IntentLedger and SessionLog all listen to it).

**Prompt-building rules (DESIGN §3.3, plan A1–A4):**
- Describe the patient from the case `behavior` block in MSE terms; never "act like a patient with X".
- Include the fixed realism rules (vague everyday words, tie symptoms to daily life, mood shifts, not too polite or cooperative, don't volunteer what wasn't asked) and the case `banned_words`. Reject or rewrite replies that contain a banned word.
- **Next-line framing:** "Write {name}'s next line in this dialogue", not "you are the patient".
- **Transient style reminder:** append one line built from `behavior` and `style` to the latest learner turn on every call. Never store it in history.
- Keep the system prompt and case block as a **fixed prefix** so `llama-server` reuses its KV cache (`cache_prompt`). The unlocked-facts list goes after the fixed prefix. **Facts that have not passed `trust_min` are never sent to the model.**
- Resolve the chosen sex variant before building anything: substitute `{name}`, `{they}`, `{them}`, `{their}`, pick `model_id` and `voice_id`, and drop facts tagged for the other variant.

**Model:** a local open-source LLM served by `llama-server` (OpenAI-compatible, `response_format` JSON schema, `-np 2`), chosen by the Phase 1 bake-off (`docs/model-bakeoff.md`). `PATIENT_LLM=grok` switches to `grok-4.20-0309-non-reasoning` at `https://api.x.ai/v1`, only when `XAI_API_KEY` is set. Keep a short in-memory history (last ~20 turns) plus a running summary so prompts stay small.

**Exam actions (DESIGN §4.4):** the reply may carry `exam_action` (`hold_out_hands`, `roll_up_sleeves`, `look_at_light`). GuardCheck drops it if the case doesn't list it or trust is below its `trust_min`; the patient then hesitates or refuses in character. A validated action plays its `action_*` clip, raises `ExamPerformed`, and (for sleeves) shows forearm decals.

**Patient service (`server/patient-service`):** a Python FastAPI app.
- `WS /session` at `ws://127.0.0.1:8765/session`: Unity streams 16 kHz mono PCM in; the service runs Silero VAD (end of speech after 450 ms of silence, tunable), Parakeet STT (`parakeet-mlx`, `mlx-community/parakeet-tdt-0.6b-v2`), the patient LLM (streamed, schema ordered `emotion, utterance, …`), and KittenTTS sentence by sentence while the LLM is still generating. It streams 24 kHz patient audio and event JSON back (`listening`, `transcript`, `thinking`, `speaking`, `reply`, `timing`).
- Intent tagging runs as a **separate parallel request** on the second `llama-server` slot and never delays the voice.
- **Barge-in:** when the doctor starts speaking while the patient talks, stop the patient within 150 ms, except under `pressured_speech` (keep talking 1–2 s).
- `POST /reply` (typed input and tests) and `POST /tts` stay.
- Warm the model up at startup; load KittenTTS once.
- Log every stage in ms (VAD end-point, STT, time to first token, first sentence, TTS first chunk, audio start) to the SessionLog. The `slowed` pause is logged separately, not as lag.

If Grok is enabled its key stays in the service's environment, **never in the Unity build or the repo**. Audio stays in memory and is never written to disk.

### 3.4 Patient state
Four floats from 0 to 100 (`DESIGN.md` §3.2), plus a per-minute drift from the case file. Rule-based nudges stack with the LLM's `state_delta`. For example, `judgmental_language` gives −8 trust and `empathy_statement` gives +4 trust. Keep these numbers in `data/state_rules.json` so faculty can tune them without code.

### 3.5 CueDriver
Each frame, for each case cue: `live = clamp01(base + gains·state + time_gain·minutes) + active event boosts`. Then send it to the right method:

| Method | Implementation |
|---|---|
| Animation clips | Animator with a base layer (base pose chosen by the case or by state) plus additive layers per mask. Layer weight = intensity. One-shot clips fire with a cooldown that gets shorter as intensity rises. |
| Gaze | `GazeController` using Animation Rigging (Multi-Aim on head and eyes). Targets: doctor's face, the floor, the empty corner (`internal_stimuli`), the door. `gaze_avoid` intensity = share of time spent looking away. Look back at the doctor briefly when they speak. |
| Tremor | `TremorController`: Perlin noise added to wrist and finger rotations after the Animator. Fine tremor around 8–12 Hz, small amplitude; coarse tremor around 4–6 Hz, larger. Amplitude scales with intensity. |
| Slowed movement | Lower Animator speed (down to 0.7) and add 1–3 s before the reply starts (`SpeechTiming`). |
| Pressured speech | Faster TTS rate, no pause before replying, and the patient keeps talking over the learner (TTS doesn't stop when the learner starts speaking). |
| Materials | `MaterialCueController` sets `_Wetness`, `_Tearfulness` and `_PupilScale` through a MaterialPropertyBlock. |
| Face | Blend the `face_<emotion>` clip from the reply. `flat_affect` lowers every face clip's weight to 30%. |
| Decals and variants | Set once when the case loads. Decals on the forearm only show during the arm exam (sleeves up). |

### 3.6 Speech
- **STT and voice UI:** hands-free mode (service-side VAD) by default; push-to-talk on Space as an option; typed chat always available as a fallback. Show a mic level meter, a "listening / thinking / speaking" indicator, and live subtitles for both sides.
- **TTS: KittenTTS** through `/tts`. Model `KittenML/kitten-tts-mini-0.8`, package `kittenml` (0.9.4 tested). Load the model once when the service starts, not per request (the first load takes about 13 s). `tools/tts/tts_check.py` shows the working calls; copy from it. Voices: Bella, Luna, Rosie, Kiki, Jasper, Bruno, Hugo, Leo. The case's `voice_id` picks one and `voice_speed` sets the base speed. `slowed` lowers the speed toward 0.85 and `pressured_speech` raises it toward 1.3. Do **not** use `kitten-tts-2`: it measured 4× slower than real time on this Mac.
- **Lip sync:** uLipSync on the TTS audio source, mapped to the Character Creator viseme blendshapes (`V_Open`, `V_Explosive`, `V_Dental_Lip`, `V_Tight_O`, `V_Tight`, `V_Wide`, `V_Affricate`, `V_Lip_Open`).
- **Typed input** always works too, as an accessibility option and fallback.
- Show subtitles for both sides (on by default).

### 3.7 Clinical tools
UI Toolkit panels for the desktop. For Stage 5 the same views go on a world-space tablet. Keep logic out of the views (views call into `Tools/` controllers), so VR only needs new views.
- **MSE panel:** tick boxes map to cue ids from `cues.json`, plus free-text fields.
- **Exam:** clicking a body region raises a `ExamPerformed(region)` event and shows the findings (vitals from the case, pupils as a close-up, rolling sleeves up to show decals).
- **ScaleRunner:** the learner picks a scale, reads each item (voice or click), the patient answers with the case's `item_scores` worded in character by the LLM, and the learner enters the score.
- **DiagnosisPicker:** searchable list from `data/diagnoses.json`, showing the DSM-5-TR name with the ICD-11 code beside it.
- **Disposition:** options from `data/dispositions.json`, each labelled with its Mental Healthcare Act 2017 basis (`DESIGN.md` §12.3).
- **PrescriptionPad:** formulary drugs only; dose, route, frequency, duration fields; checked by `PrescriptionChecker`.

### 3.8 Scoring
- **IntentLedger:** gathers `doctor_intents` from each reply, with timestamps.
- **ScoringEngine:** a pure C# class with no Unity dependency, so it is easy to unit test. Input: case answer key, intent ledger, MSE entries, exams, scale results, diagnosis, prescriptions, disposition, final state. Output: domain scores, critical errors and missed items, as `DESIGN.md` §8 describes.
- **PrescriptionChecker:** a pure C# class running the 4 checks in `DESIGN.md` §6.3. Rules are data in `formulary.json`, with a small set of named rule functions in code (for example `bipolar_monotherapy_warning` checks whether the case diagnosis is bipolar and the drug class is an antidepressant with no mood stabiliser).
- **Weights (DESIGN §8, plan C1):** risk 30, observation 20, history 12, communication 12, diagnosis 13, management 13. A learner cannot pass without the required risk items. Label the score **formative**.
- **Debrief:** side by side (learner's MSE, risk, diagnosis, plan next to the case truth, mismatches highlighted), every feedback item quoting the learner's line with its timestamp, cues present vs cues recorded, and teaching points.
- **Prebrief screen** before the station (objectives, content note, formative scoring, "you can pause any time") and a **15-minute station timer** (plan C6, D4).
- **Start screen:** case, then patient sex (Female / Male variant), then Practice or Assessment.

### 3.9 SessionLog
Append-only JSON lines per session in `Application.persistentDataPath/sessions/`: every turn, state snapshot, cue change, tool action and the final score. **Never write audio to disk.** This log is what the debrief, the tester and faculty review all use.

## 4. Stage deliverables (match `DESIGN.md` §10)

| Stage | You deliver |
|---|---|
| 0 | Project setup, packages, JSON schemas, CaseLoader with validation, a scene with placeholder room and patient |
| 1 | Encounter flow, **local voice loop** (WebSocket, VAD, Parakeet, local LLM, streamed TTS, barge-in) plus typed chat, lip sync, PatientBrain + GuardCheck with realism rules, PatientState, CueDriver for the 8 slice cues, exam actions (3), sex variants, MSE panel, diagnosis picker, prescription pad, risk-first quote-grounded debrief, prebrief, 15-minute timer |
| 2 | Conversation styles, all cues, 2 new rooms, ScaleRunner, case loading for 6 cases |
| 3 | Full ScoringEngine + PrescriptionChecker + Debrief timeline, content status enforcement in builds, case-validator CLI |
| 4 | Hub lobby and case selection, session export (zip of logs), pilot fixes |
| 5 | XR rig, seated and standing modes, world-space tablet, hand-reach exam, comfort options (snap turn, vignette), Quest performance work (single-pass instanced rendering, fixed foveated rendering, LODs) |
| 6 | Signed and notarised macOS build, build scripts, faculty guide for adding cases |

## 5. Performance targets
- Mac (M1, 1080p): 60 fps.
- Quest 3S (Stage 5): 72 fps minimum (90 preferred), at most 100 draw calls per room plus the patient, frame time under 13.9 ms.
- Voice turn latency (end of learner speech to first patient audio, excluding the deliberate `slowed` pause), on the M5 Pro: **p50 ≤ 1.2 s, p90 ≤ 1.8 s**. Results in `docs/latency.md`.

## 6. Don't
- Don't hard-code clinical content in C#. It all goes in data files.
- Don't let the LLM decide scores or what is safe to prescribe. Those are deterministic code.
- Don't build Stage 3+ features during Stage 1.
- Don't log personal data or audio.
- Don't put the API key in the client.

## 7. Done means (every stage)
- Builds on macOS with no errors and no console warnings from our scripts.
- All unit and play-mode tests pass (the tester owns the test plan, you keep tests green).
- `CHANGELOG.md` updated, and a short `STAGE_<n>_NOTES.md` listing what was built, known issues, and how to run it.
