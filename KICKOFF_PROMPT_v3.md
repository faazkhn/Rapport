# Kickoff prompt for Claude Code (v3): Sanvaad + Chitta

Open Claude Code in `/Users/faazkhn/Documents/Med` and paste the whole block below. It supersedes `KICKOFF_PROMPT.md` (v2), which stays for history.

```text
You are the **lead** on this project. Until today it was called **PsychSim**: an embodied psychiatry and addiction OSCE simulator in which a doctor talks out loud to a 3D patient, running fully locally on this Mac. In this run you (1) audit where it stands, (2) rename it to **Sanvaad** (संवाद, "dialogue"), (3) give the patient a research-grounded, self-improving brain called **Chitta** (Sanskrit for "mind"), with a live visual **digital twin**, and (4) fix what the owner (Dr. Faaz) disliked: the patient's replies, the voice, the lag and pauses, the camera, and exam commands such as "hold out your hands".

Delegate to subagents (Agent tool) wherever work is independent. Keep integration, review and every owner checkpoint yourself. Only one agent may drive the Unity editor at a time.

## 0. House rules (read before anything else)
- Read and follow `CLAUDE.md`. Issues live in GitHub Issues via `gh` (`docs/agents/issue-tracker.md`). Domain docs are `GLOSSARY.md` + `docs/adr/` (`docs/agents/domain.md`). **Record each significant decision in this run as an ADR**: the rename, the brain architecture, the TTS choice, the turn detection, the learning loop, and whether to adopt Pipecat.
- Owner decisions in `HANDOFF.md` §1 still hold unless this prompt changes them.
- Everything stays local: no cloud calls, no accounts, no sign-ins, no licence acceptances, no purchases. If something needs one, stop and ask.
- Clinical content stays **draft** and is never presented as validated. Learning may change *how* the patient talks, **never** clinical facts, the answer key or scoring.
- Verify before claiming: tests, measured numbers, screenshots you have actually looked at, audio you have transcribed back.
- Blocked after 2 attempts on the same problem → stop and tell me what you tried.

## Phase A: audit the current state (no feature work yet)
The project changed a lot across several sessions; don't trust any document blindly.
1. Read: `HANDOFF.md`, `STAGE_1_NOTES.md`, `DESIGN.md`, `PLAN_insights.md`, `PATIENT_BRAIN.md`, `RIG_REPORT.md`, `docs/*.md`, `briefs/*`, `references/README.md`, `server/patient-service/README.md`, `art/Animations/ANIMATIONS.md`, the open GitHub issues, and `git status` / `git log`.
2. Run everything:
   - service tests
   - Unity EditMode tests (through the Unity MCP)
   - `tools/latency/ws_bench.py`
   - the playable macOS build, or Play mode
   - one full encounter by voice, using synthesised doctor audio through the real mic path

   Record 5 patient replies as audio and transcribe them back.
3. Write `docs/STATE_AUDIT.md`:
   - what works (with evidence)
   - what's broken
   - uncommitted or unverified work-in-progress (HANDOFF §4–5)
   - places where the docs and the code disagree
   - test and latency numbers as they are today
   - a section **"Owner feedback → root causes"** that traces each of these complaints to specific code or config:
     - (a) the replies aren't liked
     - (b) the voice type isn't liked
     - (c) the voice isn't natural
     - (d) it's too slow
     - (e) there are too many pauses
     - (f) there's no emotion in the voice
     - (g) the camera angles are poor
     - (h) commands like "hold out your hand" don't work well
4. Review and commit or discard the leftover WIP as HANDOFF §5.1 says. Check LFS stays under 900 MB.
5. **Checkpoint 1 (non-blocking):** post a 10-line summary of the audit to me, then continue.

## Phase B: rename PsychSim → Sanvaad
Why: **`usc-psychsim/psychsim`** is an established USC research framework with the same name. Sanvaad has no meaningful clash on GitHub.
- `gh repo rename Sanvaad --repo faazkhn/PsychSim`. Update the git remote. GitHub redirects the old URL, but update all links anyway.
- Rename everywhere it's user-facing:
  - README, docs, deck, menus (`PsychSim/…` → `Sanvaad/…`)
  - Unity product name and bundle id
  - the build name, `PsychSim.command` → `Sanvaad.command`
  - service names, env var prefixes (`PSYCHSIM_*` → `SANVAAD_*`, keeping the old names working as deprecated aliases for one release)
  - window titles and demo cards
- Rename C# namespaces and asmdefs only if it's mechanical and the tests stay green; otherwise record it as a follow-up issue.
- Add "Sanvaad (formerly PsychSim)" to the README and `GLOSSARY.md`. Write the ADR.

## Phase C: read every paper and merge the findings into Chitta
Sources:
1. **Every paper** in https://github.com/FreedomIntelligence/Awesome-LLM-Patient-Simulators (about 70; parse the README).
2. R1–R11 in `references/README.md` and the full texts already in `references/`.
3. The **16 simulators in PatientHub** (https://github.com/Sahandfer/PatientHub, MIT) and their papers, especially **PatientAct** (arXiv 2608.12750).
4. Everything cited in `PATIENT_BRAIN.md`, including EvoPatient, AgentClinic, AnnaAgent, MedAgentSim, Generative Agents, Concordia, GEPA, DSPy, *Feeling First, Speaking Second* (LREC 2026).

How:
- Split the list across **parallel reader subagents** (about 10 papers each).
- Each paper gets a record with: citation · link · open access? · code repo and **code licence** · what part of the brain it informs (identity/formulation, memory and disclosure, affect, behaviour and resistance, expression/embodiment, memory across sessions, learning, evaluation, feedback/pedagogy) · the mechanism · the evidence (numbers) · limitations · verdict **adopt / adapt / idea-only / skip**, with a reason.
- Use the abstract when the full text isn't open, and say so.
- Licence rules for code: MIT, Apache or BSD → may reuse with attribution. AGPL, non-commercial or no licence → ideas only. Licence rules for PDFs: commit only CC BY or CC0; otherwise link only.

Outputs:
- `docs/literature/matrix.md` (one row per paper)
- `docs/literature/notes/<id>.md`
- `docs/literature/insights.md`: a de-duplicated list of design insights, each mapped to a Chitta component and a status (built in this run / later / rejected)
- an updated `references/README.md`

Then write **`docs/CHITTA.md`**, the brain spec. It supersedes `PATIENT_BRAIN.md` §3–5 and uses these owner defaults for its open questions:
- Keep the new name Sanvaad.
- The experience library has two tiers: **candidate** (passed the automatic checks; used in Practice mode) and **approved** (faculty 👍; required for Assessment mode).
- Learner sessions **never** feed learning unless a per-session consent flag is set; the default is off.

## Phase D: build Chitta, the patient brain (developer subagent, in `server/patient-service`)
Start from `PATIENT_BRAIN.md` §3 and `docs/CHITTA.md`. Reuse MIT/Apache code from PatientHub and EvoPatient where it fits (with attribution); don't run PatientHub inside the live loop.

1. **Identity and formulation:**
   - PSYCHE-style MSE behaviour block (already in the v0.3 schema)
   - PatientAct-style **5Ps formulation**, `core_belief`, `attachment_style`
   - per-case `dialect` (default: natural Indian English; light code-mixing only if the case enables it)
2. **Memory with locks:** migrate `facts` to `memory_items` (`content`, `activation_tags`, `trust_min`, `generates_discomfort`, `kind`). Recall uses **local embeddings plus tags, with no LLM call**. Locked items that match send only a discomfort signal. Write a migration script, migrate `mdd_01`, and keep the old format readable for one release.
3. **Feelings:**
   - fast **reaction plus intensity** each turn
   - slow **mood** (PAD-style: pleasure, arousal, dominance) that drifts and colours later turns
   - existing state values: trust, distress, agitation, engagement
   - for substance cases: SimPatient's control, self-efficacy, awareness, reward, plus **stage of change** (ConsistentMI)

   All updates are categorical steps clamped by code; the model proposes, the code decides.
4. **Behaviour, adapted for a psychiatric assessment interview rather than therapy.** A behaviour set that faculty can review, for example:
   - answers plainly · minimises · denies · deflects · vague timeline · answers a different question · tangential · guarded/short · hostile · tearful disclosure · asks a question back · complies without engaging

   Plus PatientAct's resistance styles (quantity, content, style) and PATIENT-Ψ's 6 conversation styles as a per-case bias. Ship the list as data (`data/brain/behaviours.json`) with descriptions and an example line each.
5. **Fast path (one structured call; "feel first, speak second"):** schema order `reaction, intensity, behaviour, resistance, emotion, utterance, …`. Labels are short; the utterance streams to TTS. **Slow path** (parallel slot, never delays the voice): state and trust update, intent tagging, mood drift, episode memory, the learning hooks.
6. **Expression mapping:** a data table `data/brain/expression_map.json` maps reaction, behaviour and resistance onto the face preset, body cues, gaze, posture, **voice emotion/instruction, speaking rate, pitch and volume**, and non-verbal sounds (sigh, sniff, shaky breath, soft crying).
7. Every turn emits a **`brain_snapshot`** event (the full serialised brain state and the reasons for each decision) to the WebSocket and the SessionLog. The digital twin is built on this.
8. **Comparison baseline:** install PatientHub as a **dev-only** dependency, pointed at the local `llama-server` (OpenAI-compatible). Run its PSYCHE, PATIENT-Ψ and PatientAct simulators on `mdd_01`-equivalent profiles under the same doctor scripts, and use its evaluator. Record in `docs/brain-baseline.md` whether Chitta is at least as good on resistance quality and realism, while being fast enough for live voice.

## Phase E: self-learning that demonstrably works
Implement and **prove** these mechanisms (from `PATIENT_BRAIN.md` §4):
- **L1 Experience library** (EvoPatient pattern): per case, store good patient replies with embeddings after a quality gate (no invented facts, no banned words, rules followed, length fits the state). Retrieve the top 2–3 similar ones as examples. Two tiers, candidate and approved, as in Phase C.
- **L2 Faculty tuning** (Roleplay-doh pattern): 👍 / 👎 / "rewrite" on any reply → an LLM turns it into a principle → stored in the case's `principles` with an author and date. A yes/no rule check runs in evaluation (and live, if it costs under 50 ms).
- **L3 Nightly prompt optimisation** with **GEPA** (MIT; DSPy as the fallback) on the shared prompt templates, scored by our evaluation suite. A new `brain_version` goes live only if it **beats the current one and regresses on no safety test** (invented facts = 0, jailbreak set, portrayal checklist). Every version is stored and can be rolled back with one command. `brain_version` is in every SessionLog.
- **L4** (fine-tuning) is out of scope. Write it up as a later issue.

**Self-play engine:** simulated doctors of varied skill ("excellent", "average", "rushed/closed", "judgmental", "prompt-injector") built from PatientHub's therapist agents and our own LLM doctor personas, plus the scripted lines. They generate sessions → L1/L3 learn → evaluation on a **held-out** conversation set the learning never sees.

**Proof (`docs/LEARNING_REPORT.md`):**
- **5 or more brain versions** with curves for realism proxies:
  - unmentioned-symptom ratio fidelity
  - banned-word rate
  - repetition
  - length-fits-state
  - resistance appropriateness, judged for *accuracy* only (never for realism, per plan C8)
- Safety metrics flat at zero.
- **Checkpoint 2 (blocking): a blind A/B test for me.** Take 10 pairs of replies, brain v0 against the latest version, in random order. I pick the more natural one in a small page inside the twin. Report the result honestly, including if I preferred v0.

## Phase F: Chitta Twin, the visual digital twin
A local web app served by the service at **http://127.0.0.1:8765/twin**. It works live during a session (WebSocket `brain_snapshot`) and as **replay** of any past session from its SessionLog. It runs fully offline: vendor any JS libraries into the repo (no CDNs).

**Visual centrepiece:** a stylised brain (SVG) whose regions light up with module activity. Label it clearly as a **metaphor, not neuroscience**:
- hippocampus = memory recall (flash on recall; locked items pulse red)
- amygdala = reaction and intensity
- prefrontal = behaviour and resistance choice
- language areas = the utterance being formed
- insula/brainstem = arousal, agitation and body cues

**Panels:**
- state gauges (trust, distress, agitation, engagement; mood PAD as a 3D or 2D dot) with history sparklines
- current reaction, behaviour and resistance with the model's reasons
- a **memory map**: a graph of memory items showing their trust thresholds, locked/unlocked state and what activated them, live
- the 5Ps formulation card
- stage of change (substance cases)
- a turn timeline you can click to scrub the whole brain state back in time
- the expression output: what the face, body and voice were told to do

**Learning tab:**
- brain versions and their changelog
- experience-library growth (candidate vs approved)
- evaluation curves from `LEARNING_REPORT`
- a **faculty review queue**: approve or reject candidates; 👍 / 👎 / rewrite → principles (this is the L1/L2 UI)
- the A/B test page for Checkpoint 2

Also add a compact in-Unity overlay (toggle with F2) that shows a mini version of the twin (gauges plus the current reaction and behaviour) for the demo.

**Quality bar:**
- readable at 1440×900 and 1920×1080
- light and dark themes
- 60 fps animation with no layout jank
- screenshot every view and **look at the screenshots** before calling it done
- document it in `docs/TWIN.md` with screenshots

## Phase G: voice and conversation quality (owner complaints a–f)
**Replies (a):**
- Use the audit transcripts to find what's wrong (likely: therapist-speak, repetition, over-polished sentences, wrong length, flat content).
- Fix through Chitta's behaviour choice, the realism rules, few-shot examples from L1, length targets by state, repetition control, and dialect.
- Before/after transcripts go in `docs/voice-quality.md`.

**Voice type, naturalness, emotion (b, c, f): TTS bake-off on this Mac.**
- Candidates (prefer mlx-audio, https://github.com/Blaizzy/mlx-audio, for Apple Silicon):
  - **Qwen3-TTS** 0.6B and 1.7B (CustomVoice / VoiceDesign; natural-language emotion and prosody instructions; Apache-2.0)
  - **Chatterbox** (emotion exaggeration control)
  - **Kokoro-82M** (the speed baseline)
  - **Kyutai Pocket TTS**, if it's available locally
  - **KittenTTS 2** retested on MPS or MLX (it was 4× too slow on CPU)
  - the current KittenTTS mini (the baseline to beat)
- Check every licence, and skip anything gated.
- Voices: create **Ananya** (24, female) and **Arjun** (24, male) with natural Indian-English accents using **voice design from a text description**. **Never clone a real person's voice** unless I provide written consent and the recordings.
- Measure for each candidate: time to first audio when streaming, real-time factor, memory use, and whether emotion follows the Chitta instruction.
- **Checkpoint 3 (blocking): a blind listening test.** Use 8 lines across emotions (flat-depressed, tearful, guarded, irritable, relieved), rendered by each viable candidate, in a randomised page inside the twin. I rate naturalness and emotion. Choose by my ratings plus the speed bar.
- Wire the winner to the expression map: emotion instruction or exaggeration, rate, pitch, volume and non-verbal sounds. Use the model's own sounds where supported; otherwise use a CC0 SFX set (record its source and licence).

**Speed and pauses (d, e):**
- **Turn detection:** add **Pipecat Smart Turn v3.2** (BSD-2, local ONNX, about 10 ms; https://github.com/pipecat-ai/smart-turn) on top of Silero VAD, so the end of the doctor's turn is judged by meaning and intonation, not a fixed 500 ms silence. Tune it on the doctor-lines set so it never cuts the doctor off mid-question.
- **Streaming STT:** run Parakeet incrementally while the doctor is still talking, so the final transcript costs about 50 ms after the turn ends.
- **TTS:** stream by phrase, not by sentence. Keep a look-ahead buffer so there is **no gap over 200 ms inside a reply**.
- **Backchannels:** when compute will clearly be slow, play an in-character backchannel within 300 ms ("mm…", a breath, "I don't know…"), chosen by the brain. Never in Assessment mode if faculty disable it.
- **Deliberate hesitation** (the `slowed` cue) applies only where the case calls for it, is clinically sized, and is logged separately.
- Evaluate adopting **Pipecat** (BSD-2) for the voice pipeline against the current hand-rolled one. Record the decision in an ADR; don't rewrite unless it's measurably better.
- **Targets on this Mac**, from the moment the doctor stops talking to the first patient audio, excluding deliberate hesitation: **p50 ≤ 700 ms, p90 ≤ 1,000 ms**. Gaps inside a reply ≤ 200 ms. Barge-in ≤ 150 ms. Per-stage table in `docs/latency.md`. If you miss the targets, show me the breakdown before trading away quality.

## Phase H: camera and exam commands (complaints g–h)
**Camera:**
- The doctor's view is at seated eye height, about 1.20 m, with a natural field of view (start at 40–45° vertical and tune it on screenshots).
- The patient's head and torso fill the frame comfortably, with the eyes in the upper third.
- No wide-angle distortion, no clipping, smooth limited mouse-look, and an optional subtle "lean in" on the doctor's command.
- When an exam action runs, the Cinemachine camera **cuts or eases to a matching close-up** (hands, forearms, eyes or pupils, face or tongue, full body for gait), holds, then returns.
- The patient looks at the doctor camera by default; gaze cues override it.
- The demo uses separate cinematic cameras.
- Acceptance: one still per camera state in `docs/camera.md`, reviewed by you.

**Exam commands:**
- An **action router** runs on the partial and final transcript: fast embedding and rule matching (≤ 30 ms), not a full LLM call.
- Actions with slots:
  - `hold_out_hands{palms: down|up, which: left|right|both}`
  - `show_forearms` / `roll_up_sleeves{which}`
  - `look_at_light`, `follow_finger`, `open_mouth`, `stick_out_tongue`, `stand_up`, `sit_down`, `walk_few_steps`
  - `relax` / `you_can_put_them_down`
- It supports paraphrases and Indian-English phrasings, and multiple commands in one sentence, run in order. When a command is ambiguous, the patient asks back ("Which hand?").
- Compliance is gated by trust and agitation, and the patient's short verbal acknowledgement comes from Chitta, consistent with the state.
- Animation uses IK so the hands are presented toward the doctor at a sensible height. The patient holds the pose until told to relax (or a timeout), and **cues stay visible during the hold** (for example, the tremor on outstretched hands).
- Author the missing clips in Blender on the shared CC3 skeleton for **both** models.
- Test set: **≥ 300 labelled utterances**, including 20 or more negatives that must not trigger. Accuracy ≥ 95% and false triggers ≤ 1%. Results in `docs/exam-actions.md`.

## Phase I: gates, demo v3, documentation, release
1. Run all the tests and the evaluation suite (the plan's E1–E4, the A6 portrayal checklist, 0 invented facts) on the final brain version and voice. Both patient variants must play end to end. File bugs as GitHub issues and fix them until only Minor or Cosmetic ones remain.
2. **Demo v3** (`demo/Sanvaad_demo_v3.mp4`, 1080p60 with audio, 2–3 min). Dr. Faaz is synthesised as before and fed through the real mic path; patient replies are live. It shows:
   - natural emotional voice and quick turn-taking
   - an exam command with a camera close-up
   - Chitta Twin side by side (picture-in-picture) as trust rises and a memory unlocks
   - the learning curve
   - both patients

   Verify with ffprobe, a frame every 10 s that you look at, and an audio transcription. Also export a teaser of 10 MB or less and 6 stills.
3. **README** (renamed): what Sanvaad is · the teaser · features · Chitta and the Twin (screenshots) · how learning works and its guardrails · the voice stack with licences · measured latency · the literature matrix summary · how to run · roadmap · disclaimer · credits (Dr. Faaz). Refresh the **pitch deck** (PPTX and PDF) to match.
4. Push, then create release **`v0.2-chitta`** with the demo, deck and learning report attached. Close the issues you resolved.

## Report back with
- `docs/STATE_AUDIT.md` summary, the ADR list, and the literature-matrix count (papers read in full vs abstract only).
- Chitta vs the PatientHub baselines; the learning curve; my A/B result.
- The TTS winner with my listening scores; the latency table before and after; exam-action accuracy; camera stills.
- Links: repo, release, demo, deck. Open issues and what you'd do next.
```
