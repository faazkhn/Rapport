# Kickoff v4: Sanvaad + Chitta (owner-approved 2026-10-20; not started)

You are the **lead** on this project. Until today it was called **PsychSim**: an embodied psychiatry and addiction OSCE simulator in which a doctor talks out loud to a 3D patient, running fully locally on this Mac. In this run you (1) audit where it stands, (2) rename it to **Sanvaad** (संवाद, "dialogue"), (3) give the patient a research-grounded, self-improving brain called **Chitta** (Sanskrit for "mind"), with a live visual **digital twin**, and (4) fix what the owner (Dr. Faaz) disliked: the patient's replies, the voice, the lag and pauses, the camera, and exam commands such as "hold out your hands".

Delegate to subagents (Agent tool) wherever work is independent. Keep integration, review and every owner checkpoint yourself. Only one agent may drive the Unity editor at a time.

## 0. House rules
- Read and follow `CLAUDE.md` and `HANDOFF.md`. Issues: GitHub Issues via `gh`. Domain docs: `GLOSSARY.md` + `docs/adr/`. Record each significant decision as an ADR: the rename, the brain architecture, the TTS choice, the turn detection, the learning loop, and whether to adopt Pipecat.
- Commits are authored `faazkhn <faazkhn1000@gmail.com>` with no Claude attribution lines.
- Everything stays local: no cloud calls, no accounts, no sign-ins, no licence acceptances, no purchases. If something needs one, stop and ask.
- Clinical content stays **draft** and is never presented as validated. Learning may change *how* the patient talks, **never** clinical facts, the answer key or scoring.
- Verify before claiming: tests, measured numbers, screenshots you have actually looked at, audio you have transcribed back.
- Blocked after 2 attempts on the same problem → stop and report what you tried.

## Phase A: audit (no feature work)
1. Read: HANDOFF.md, STAGE_1_NOTES.md, DESIGN.md, PLAN_insights.md, PATIENT_BRAIN.md, RIG_REPORT.md, docs/*.md, briefs/*, references/README.md, server/patient-service/README.md, art/Animations/ANIMATIONS.md, the open GitHub issues, and git status / log.
2. Run everything:
   - the service tests
   - the Unity EditMode tests
   - `tools/latency/ws_bench.py`
   - the macOS build or Play mode
   - one full voice encounter with synthesised doctor audio through the real mic path

   Record 5 patient replies and transcribe them back.
3. Write `docs/STATE_AUDIT.md`:
   - what works (with evidence)
   - what's broken
   - uncommitted or unverified WIP
   - places where docs and code disagree
   - today's test and latency numbers
   - **"Owner feedback → root causes"**, tracing each complaint to specific code or config:
     - (a) the replies aren't liked
     - (b) the voice type isn't liked
     - (c) the voice isn't natural
     - (d) it's too slow
     - (e) there are too many pauses
     - (f) there's no emotion in the voice
     - (g) the camera angles are poor
     - (h) commands like "hold out your hand" don't work well
4. Review and commit or discard the leftover WIP. Keep LFS under 900 MB.
5. Checkpoint 1 (non-blocking): a 10-line summary to the owner.

## Phase B: rename PsychSim → Sanvaad
Why: `usc-psychsim/psychsim` is an established USC research framework with the same name.
- Run `gh repo rename Sanvaad --repo faazkhn/PsychSim` and update the remote and all links.
- Rename everything user-facing:
  - README, docs, deck
  - menus (`PsychSim/…` → `Sanvaad/…`)
  - Unity product name and bundle id
  - the build, `PsychSim.command` → `Sanvaad.command`
  - service names
  - env var prefixes `PSYCHSIM_*` → `SANVAAD_*`, keeping the old names as deprecated aliases for one release
  - window titles and demo cards
- Rename C# namespaces and asmdefs only if it's mechanical and the tests stay green; otherwise file a follow-up issue.
- Add "Sanvaad (formerly PsychSim)" to the README and `GLOSSARY.md`, and write the ADR.

## Phase C: literature review → Chitta spec
Sources:
1. Every paper in https://github.com/FreedomIntelligence/Awesome-LLM-Patient-Simulators (about 70).
2. R1–R11 in `references/README.md`.
3. The 16 simulators in PatientHub (https://github.com/Sahandfer/PatientHub, MIT) and their papers, especially PatientAct (arXiv 2608.12750).
4. Everything cited in `PATIENT_BRAIN.md`: EvoPatient, AgentClinic, AnnaAgent, MedAgentSim, Generative Agents, Concordia, GEPA, DSPy, and *Feeling First, Speaking Second* (LREC 2026).

Split the papers across parallel reader subagents (about 10 papers each). Each paper gets a record:
- citation, link, open access?
- code repo and code licence
- which part of the brain it informs (identity/formulation, memory and disclosure, affect, behaviour/resistance, expression/embodiment, cross-session memory, learning, evaluation, feedback/pedagogy)
- mechanism, evidence (numbers), limitations
- verdict: adopt / adapt / idea-only / skip, with a reason

Use the abstract when the full text isn't open, and say so.

Licence rules:
- Code: MIT, Apache or BSD → may reuse with attribution. AGPL, non-commercial or no licence → ideas only.
- PDFs: commit only CC BY or CC0; otherwise link only.

Outputs:
- `docs/literature/matrix.md` (one row per paper)
- `docs/literature/notes/<id>.md`
- `docs/literature/insights.md`: each insight mapped to a Chitta component and a status (built in this run / later / rejected)
- an updated `references/README.md`

Then write `docs/CHITTA.md`, superseding `PATIENT_BRAIN.md` §3–5. Defaults for its open questions:
- Keep the name Sanvaad.
- The experience library has two tiers: **candidate** (passed the automatic checks; used in Practice mode) and **approved** (faculty 👍; required for Assessment mode).
- Learner sessions never feed learning unless a per-session consent flag is set (default off).

## Phase D: build Chitta (server/patient-service)
1. **Identity:**
   - PSYCHE-style MSE behaviour block
   - PatientAct 5Ps formulation, `core_belief`, `attachment_style`
   - per-case `dialect` (default: natural Indian English; light code-mixing only if the case enables it)
2. **Memory with locks:**
   - migrate `facts` → `memory_items` (`content`, `activation_tags`, `trust_min`, `generates_discomfort`, `kind`)
   - recall uses local embeddings plus tags, with no LLM call
   - locked items that match send only a discomfort signal
   - a migration script; migrate `mdd_01`; keep the old format readable for one release
3. **Feelings:**
   - fast reaction plus intensity each turn
   - slow PAD mood that drifts and colours later turns
   - the existing trust, distress, agitation and engagement
   - substance cases: SimPatient's control, self-efficacy, awareness and reward, plus ConsistentMI stage of change

   All updates are categorical steps clamped by code: the model proposes, the code decides.
4. **Behaviour set** for an assessment interview, shipped as data in `data/brain/behaviours.json` with a description and an example line each:
   - answers plainly · minimises · denies · deflects · vague timeline · answers a different question · tangential · guarded/short · hostile · tearful disclosure · asks a question back · complies without engaging
   - plus PatientAct's resistance styles (quantity, content, style) and PATIENT-Ψ's 6 conversation styles as a per-case bias
5. **Fast path** (one structured call, "feel first, speak second"): schema order `reaction, intensity, behaviour, resistance, emotion, utterance, …`, with the utterance streaming to TTS. **Slow path** (parallel slot, never delays the voice): state and trust update, intent tagging, mood drift, episode memory, learning hooks.
6. **Expression map**, `data/brain/expression_map.json`: reaction, behaviour and resistance → face preset, body cues, gaze, posture, voice emotion/instruction, rate, pitch, volume, and non-verbal sounds (sigh, sniff, shaky breath, soft crying).
7. Every turn emits a `brain_snapshot` (the full state plus the reason for each decision) to the WebSocket and the SessionLog.
8. **Baseline:** PatientHub as a dev-only dependency, pointed at the local llama-server. Run its PSYCHE, PATIENT-Ψ and PatientAct simulators on `mdd_01`-equivalent profiles with the same doctor scripts, scored by its evaluator. Record in `docs/brain-baseline.md` whether Chitta is at least as good on resistance quality and realism while being fast enough for live voice.

## Phase E: self-learning that demonstrably works
- **L1 experience library** (EvoPatient):
  - after a quality gate (no invented facts, no banned words, rules followed, length fits the state), store good replies with embeddings
  - retrieve the top 2–3 similar ones as examples
  - two tiers: candidate and approved
- **L2 faculty tuning** (Roleplay-doh):
  - 👍 / 👎 / rewrite on any reply → an LLM turns it into a principle → stored in the case's `principles` with an author and date
  - a yes/no rule check runs in evaluation (and live, if it costs under 50 ms)
- **L3 nightly prompt optimisation** with GEPA (DSPy as the fallback):
  - a new `brain_version` goes live only if it beats the current one and regresses on no safety test (invented facts = 0, jailbreak set, portrayal checklist)
  - every version is stored and can be rolled back with one command
  - `brain_version` is in every SessionLog
- **L4** (fine-tuning) is out of scope; file it as a later issue.
- **Self-play:**
  - simulated doctors of varied skill (excellent, average, rushed/closed, judgmental, prompt-injector) plus the scripted lines
  - learning runs on the self-play sessions; evaluation runs on a held-out set the learning never sees
- **Proof** in `docs/LEARNING_REPORT.md`: 5 or more versions with curves for:
  - unmentioned-symptom ratio fidelity
  - banned-word rate
  - repetition
  - length-fits-state
  - resistance appropriateness, judged for accuracy only

  Safety metrics stay flat at zero.
- **Checkpoint 2 (blocking):** a blind A/B test for the owner, 10 pairs (v0 vs the latest) in the twin. Report the result honestly.

## Phase F: Chitta Twin (v1 exists: server/patient-service/twin/)
- Wire it live to the WebSocket `brain_snapshot` and replay from the SessionLog. Fully offline (vendor JS, no CDNs).
- The SVG brain stays labelled "metaphor, not neuroscience":
  - hippocampus = memory recall
  - amygdala = reaction
  - prefrontal = behaviour and resistance
  - language areas = the utterance being formed
  - insula/brainstem = arousal and body cues
- Panels:
  - gauges with sparklines
  - PAD mood
  - reaction, behaviour and resistance with the reasons
  - a memory map with thresholds and locks
  - the 5Ps
  - stage of change (substance cases)
  - a clickable turn timeline that scrubs the whole brain state
  - expression output
- **Learning tab:**
  - brain versions and their changelog
  - experience-library growth (candidate vs approved)
  - evaluation curves
  - a faculty review queue (approve/reject candidates; 👍 / 👎 / rewrite → principles)
  - the A/B page
- An in-Unity F2 mini overlay (gauges plus the current reaction and behaviour).
- Quality bar:
  - readable at 1440×900 and 1920×1080
  - light and dark themes
  - 60 fps animation with no layout jank
  - screenshot every view and look at the screenshots
  - `docs/TWIN.md`

## Phase G: voice and conversation quality (a–f)
- **Replies:** find the problems in the audit transcripts (therapist-speak, repetition, over-polish, wrong length, flat content). Fix them through behaviour choice, realism rules, L1 few-shot examples, length targets by state, repetition control and dialect. Before/after transcripts go in `docs/voice-quality.md`.
- **TTS bake-off** (prefer mlx-audio):
  - Qwen3-TTS 0.6B and 1.7B (already working for the staged demo, `tools/tts_lab/`)
  - Chatterbox
  - Kokoro-82M
  - Kyutai Pocket TTS
  - KittenTTS 2 on MPS/MLX
  - KittenTTS mini (the baseline to beat)

  Check every licence and skip anything gated. Voices for Ananya and Arjun come from text descriptions; never clone a real person. Measure time to first audio, real-time factor, memory, and whether emotion follows the instruction.

  **Checkpoint 3 (blocking):** a blind listening test, 8 lines across emotions, in the twin.

  Wire the winner to the expression map, using the model's own non-verbal sounds or a CC0 SFX set (record its source and licence).
- **Speed:**
  - Pipecat Smart Turn v3.2 on top of Silero VAD, tuned so it never cuts the doctor off
  - incremental Parakeet STT
  - phrase-level TTS streaming with no gap over 200 ms inside a reply
  - brain-chosen backchannels within 300 ms when compute is slow (never in Assessment mode if faculty disable them)
  - the `slowed` hesitation only where the case calls for it, logged separately
  - an ADR on adopting Pipecat

  Targets: p50 ≤ 700 ms and p90 ≤ 1,000 ms from end of speech to the first patient audio; barge-in ≤ 150 ms. If missed, show the owner the breakdown before trading quality.

## Phase H: camera and exam commands (g–h)
- **Camera:**
  - seated eye height about 1.20 m, 40–45° vertical FOV, eyes in the upper third
  - smooth, limited mouse-look, plus an optional "lean in"
  - Cinemachine close-ups per exam action (hands, forearms, eyes, face or tongue, full body for gait), then return
  - the patient looks at the doctor by default; gaze cues override it
  - separate cinematic cameras for demos
  - one still per camera state in `docs/camera.md`
- **Exam action router** on the partial and final transcript, using embeddings plus rules (≤ 30 ms, no LLM call):
  - actions with slots: `hold_out_hands{palms, which}`, `show_forearms` / `roll_up_sleeves{which}`, `look_at_light`, `follow_finger`, `open_mouth`, `stick_out_tongue`, `stand_up`, `sit_down`, `walk_few_steps`, `relax`
  - paraphrases and Indian-English phrasings; several commands in one sentence, run in order
  - ask back when ambiguous ("Which hand?")
  - compliance gated by trust and agitation, with the verbal acknowledgement coming from Chitta
  - IK presents the hands toward the doctor; the patient holds until told to relax, and cues stay visible during the hold
  - **the IK also fixes `cue_wipe_tears`**
  - author missing clips for both bodies
  - test set of ≥ 300 utterances (≥ 20 negatives): accuracy ≥ 95%, false triggers ≤ 1%, results in `docs/exam-actions.md`

## Phase I: gates, demo v3, documentation, release
1. All tests and the evaluation suite (E1–E4, the A6 checklist, 0 invented facts). Both patients play end to end. File and fix bugs until only Minor or Cosmetic ones remain.
2. Demo v3, `demo/Sanvaad_demo_v3.mp4`, 1080p60, 2–3 min, with live replies. It shows:
   - natural emotional voice and quick turn-taking
   - an exam close-up
   - the Twin picture-in-picture as trust rises and a memory unlocks
   - the learning curve
   - both patients

   Verify with ffprobe, frames every 10 s, and a transcription. Also a teaser of 10 MB or less and 6 stills.
3. README (Sanvaad):
   - what it is, the teaser, features
   - Chitta and the Twin
   - learning and its guardrails
   - the voice stack and licences
   - measured latency
   - the literature summary
   - how to run, roadmap, disclaimer, credits (Dr. Faaz)

   Refresh the pitch deck (pptx and PDF).
4. Push, then create release `v0.2-chitta` with the demo, deck and learning report attached. Close resolved issues.

## Report back with
- the audit summary, the ADR list, and the literature count (full text vs abstract only)
- Chitta vs the PatientHub baselines, the learning curve, and the A/B result
- the TTS winner with the owner's listening scores, the latency table before and after, exam-action accuracy, and the camera stills
- links to the repo, release, demo and deck, plus open issues and what you'd do next
