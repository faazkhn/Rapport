# Kickoff prompt for Claude Code (v2)

Open Claude Code in `/Users/faazkhn/Documents/Med` and paste the whole block below. No API key is needed: everything runs locally. `XAI_API_KEY` is optional and only enables Grok as a comparison.

```text
You are the **lead** on PsychSim, an embodied psychiatry and addiction OSCE simulator. A doctor walks into a consult room, a 3D patient walks in and sits down, and the doctor **talks to the patient out loud**. The patient answers in a natural voice, shows real non-verbal signs, hides things until trust is earned, and the doctor is graded on observation, risk assessment, diagnosis and safe management. You coordinate three subagents (3D artist, developer, tester) and personally own integration, the final review, the demo video, the README and the pitch deck.

The doctor in all demo material is **Dr. Faaz**. The patient for this run is **Ananya Rao (24, female)** or **Arjun Rao (24, male)**; the learner picks one at the start.

## 0. Read first, in this order
1. `PLAN_insights.md`: **approved**. Parts 1–4 are decisions, not suggestions. Answers to its open questions: OSCE station = **15 minutes**; lived-experience reviewer = **optional**; pilot control arm = **reading material**.
2. `DESIGN.md`: the source of truth once you have applied Part 4 of the plan (Phase 0).
3. `RIG_REPORT.md`, then `briefs/01-3d-artist.md`, `briefs/02-developer.md`, `briefs/03-tester.md`.
4. `references/` (papers R1–R11 cited in the plan) and `tools/tts/tts_check.py` (working KittenTTS code).

## 1. What already exists
- `art/Matt/Matt.Fbx`: male patient model, 79.5k triangles, rebuilt and verified. **Use this, not `art_source/Blender/Matt.Fbx`.**
- `art_source/Mégane_Blender/Mégane_Blender.Fbx`: female patient model, 83.8k triangles, usable as-is.
- Both are Character Creator 3+ rigs: same 101-bone skeleton, 149 facial blendshapes, 8 visemes. Animations made for one work on the other.
- KittenTTS `KittenML/kitten-tts-mini-0.8` is installed in `tools/tts/.venv` and measured at about 0.4 s per sentence on this Mac (12× faster than real time). 8 voices: female Bella, Luna, Rosie, Kiki; male Jasper, Bruno, Hugo, Leo.
- Machine: **Apple M5 Pro, 24 GB RAM**, macOS 26.6. Installed: Unity Editor **6000.6.2f1**, Blender 5.2 LTS, **llama.cpp (`llama-server`)**, Ollama, LM Studio (`lms`), ffmpeg, ffprobe, git, git-lfs, `gh` (logged in as faazkhn), uv.
- MCP servers: **Unity MCP** and **Blender MCP**. Use them.
- GitHub: **https://github.com/faazkhn/PsychSim** (private, currently empty). Everything ends up there.

## 2. Phase 0: setup and documentation (you, before spawning anyone)
1. **Apply `PLAN_insights.md` Part 4** to `DESIGN.md` and the three briefs exactly as listed, plus these updates that came after the plan:
   - **Voice moves into Stage 1.** The doctor must be able to talk, not just type.
   - **The patient's language model is now local and open source** (chosen in Phase 1). Grok becomes an optional cloud fallback.
   - **Speech-to-text is Parakeet** (Phase 1).
   - **Patient sex is selectable** for every case (Phase 3).
   - **The lighting spec** in Phase 3 replaces the artist brief's lighting line.

   Bump `DESIGN.md` to v0.3 and keep a short changelog at its top.
2. **Git:**
   - `git init`, branch `main`, remote `https://github.com/faazkhn/PsychSim.git`.
   - git-lfs for `*.fbx *.Fbx *.blend *.png *.jpg *.tga *.wav *.mp4 *.gguf *.onnx`.
   - `.gitignore`: `.venv/`, `art_source/` (source material, too big), `models/` (downloaded AI weights), Unity's `Library/ Temp/ Logs/ UserSettings/ Build/`, `.env`, `__pycache__/`.
   - **Keep LFS usage under 900 MB** (`git lfs ls-files -s`). If it would go over, stop and ask me.
3. **References and licences.** Create `references/README.md` listing R1–R11 from the plan with full citation, link and licence. Commit **only** the PDFs whose licence allows redistribution: `fpsyt-12-658967.pdf` (Frontiers, CC BY), `2502.18673.pdf`, `2503.05793.pdf`, `2505.02694.pdf`, `2305.13614.pdf` (all CC BY 4.0). **Link only, never commit:** `2501.01594`, `2405.19660`, `2407.00870`, `2508.13943v1` (arXiv non-exclusive licence). Also link the source list: https://github.com/FreedomIntelligence/Awesome-LLM-Patient-Simulators.
4. Create the Unity project at `unity/PsychSim` (URP, Editor 6000.6.2f1). Open it so the Unity MCP connects. Confirm by reading `mcpforunity://editor/state`.
5. First commit and push.

## 3. Phase 1: the local voice loop (developer subagent; it gates everything else)
Goal: the doctor speaks; the patient's voice starts so quickly that it **feels like a person, not a machine**. Everything runs on this Mac, offline after the downloads.

**Architecture:** `server/patient-service`, a Python FastAPI app with a **WebSocket** at `ws://127.0.0.1:8765/session`. Unity streams 16 kHz mono microphone PCM in. The service streams patient audio (24 kHz) and event JSON back. A REST `/reply` endpoint stays available for typed input and tests.

**Speech-to-text:**
- Silero VAD for end-of-speech detection (start with 450 ms of silence; make it tunable), then **`parakeet-mlx` with `mlx-community/parakeet-tdt-0.6b-v2`** (English-only, the fastest on Apple Silicon in public benchmarks).
- Benchmark it against `whisper-large-v3-turbo` (mlx-whisper) on Indian-accented English clips (tester brief §2.3b). Keep the faster one that meets the accuracy target.

**Language model: bake-off, then pick the smallest that passes.**
- Serve each candidate through `llama-server` (Metal, OpenAI-compatible, `response_format` JSON schema with grammar-constrained decoding, `-np 2` parallel slots) using Q4_K_M GGUFs from Unsloth. Candidates:
  1. `unsloth/gemma-4-E2B-it-GGUF` (the lightest)
  2. `unsloth/gemma-4-E4B-it-GGUF` (the expected winner)
  3. `unsloth/Qwen3.5-4B-GGUF` (thinking **off**)
  4. `unsloth/Qwen3.5-9B-GGUF` (the quality ceiling; about 6.6 GB, fits in 24 GB)
- Also time the winner under LM Studio's MLX engine (`lms`, OpenAI-compatible on :1234, structured output via Outlines). Use MLX only if it is at least 20% faster **and** the JSON stays valid.
- If a download needs sign-in or licence acceptance, skip that candidate and tell me.
- Store weights in `models/` (git-ignored). Write `models/README.md` with the exact repo, file and licence of what you chose.
- **Pass bar for a candidate:**
  - 100% schema-valid replies.
  - **0 invented facts** across the `mdd_01` evaluation set (tester brief §2, at least 10 scripted conversations × 5 runs).
  - Passes the PSYCHE jailbreak set (plan E1) and the MDD portrayal checklist (plan A6).
  - No assistant-style slips (no DSM jargon, not "too polite").
- **Choose the smallest model that passes**, and record the full table (model, size, tokens/s, time to first token, pass/fail per check) in `docs/model-bakeoff.md`.
- Grok (`grok-4.20-0309-non-reasoning`, `https://api.x.ai/v1`) stays as a config switch, `PATIENT_LLM=grok`, used only if `XAI_API_KEY` is set. It's the same OpenAI client with a different `base_url`.

**Text-to-speech:** KittenTTS mini, loaded once at startup. Speak **sentence by sentence while the model is still generating**.

**Making it fast (apply all of these):**
- Order the reply schema `emotion, utterance, …rest`. Parse the stream incrementally, and send each finished sentence of `utterance` to TTS immediately.
- **Facts the patient hasn't unlocked are never sent to the model.** Only facts that passed `trust_min` are in the prompt. This is what makes speaking before the full reply arrives safe. GuardCheck still validates `revealed_fact_ids` and state changes when the reply completes.
- Run **intent tagging as a separate parallel request** on the second slot. It must never delay the patient's voice.
- Keep the system prompt and case block as a fixed prefix so `llama-server` reuses its KV cache (`cache_prompt`). Warm the model up at startup.
- Add a per-turn **transient style reminder** (plan A3) and use **next-line framing** (plan A4).
- **Barge-in:** if the doctor starts talking while the patient is speaking, stop the patient within 150 ms. The exception is the `pressured_speech` cue, where the patient talks over the doctor for 1–2 s.
- The `slowed` cue adds a **deliberate** pause. Log it separately so it isn't counted as lag.

**Latency target**, measured from the moment the doctor stops talking to the first patient audio, on this Mac, excluding the deliberate `slowed` pause: **p50 ≤ 1.2 s, p90 ≤ 1.8 s.** Log every stage in milliseconds (VAD end-point, STT, time to first token, first sentence, TTS first chunk, audio start) to the SessionLog. Write the results to `docs/latency.md`. If you can't hit the target, show me the per-stage breakdown before trading away quality.

## 4. Phase 2: in parallel, different tools
**3D artist (Blender MCP, Blender files only).** Author on the shared CC3 skeleton and export FBX clips to `art/Animations/`:
- `walk_in` (about 4 m, root motion), `sit_down` (ends on a 0.45 m seat)
- `base_sit_neutral`, `base_sit_slumped`
- `cue_fidget_nails_Hands`, `cue_wipe_tears`
- `gesture_talk_small` ×2, `gesture_nod`, `gesture_head_shake`
- **Exam actions (plan B1):** `action_hold_out_hands`, `action_roll_up_sleeves`, `action_look_at_light`
- Face presets from blendshapes: `face_neutral`, `face_sad`, `face_flat`, `face_anxious`, `face_ashamed`

Every clip must look right on **both** models. Use keyframe animation with weight shift, overlap and breathing; nothing robotic. Don't create accounts or download from Mixamo or asset stores.

**Developer (outside Unity).**
- JSON schemas plus `data/` (cues, intents, diagnoses, dispositions, a formulary skeleton), with the new schema fields from plan Part 4: `behavior` in MSE terms, `style`, `banned_words`, `principles`, `rubric`, `variants`.
- Case `mdd_01.json`: major depressive disorder with passive suicidal ideation, Indian setting, `"status": "draft"`, doses `null`.
- **Sex variants:** `variants.female` → Ananya Rao, model `female_20s_a` (Mégane), voice `Luna`. `variants.male` → Arjun Rao, model `male_20s_a` (Matt), voice `Leo`. Clinical facts are identical; only name, pronouns, model and voice change. Use templates (`{name}`, `{they}`), never duplicated text. Sex-specific questions (such as pregnancy) follow the variant.
- Unit tests for the service and schemas.

## 5. Phase 3: Unity (one agent at a time, because the Unity MCP drives a single editor)
1. **Artist: consult room and lighting.** Build the room per the artist brief §2 (DoctorAnchor, PatientAnchor, door, a bare corner). Import both patients: try CC Unity Tools first, otherwise plain Humanoid import with URP Lit. Import all clips.

   **Lighting: the previous look was too dull. Make it bright, warm and clinical-but-humane:**
   - **Key:** soft daylight through the window, about 5,000 K, aimed so the patient's face is lit three-quarters from the doctor's side.
   - **Fill:** a warm practical desk or ceiling lamp, about 3,200 K.
   - **Rim:** a subtle light separating the patient from the wall.
   - **Light and reflection:** baked GI and light probes around the chair, plus one reflection probe so eyes and tears catch highlights.
   - **Post-processing volume:** Neutral or ACES tonemapping, post-exposure tuned up, contrast +10, saturation +5, mild bloom, SSAO, very light vignette.
   - **Surfaces:** off-white walls with one warm accent wall. Avoid grey-on-grey.
   - **Acceptance:** in a 1080p frame from the doctor's view, the **patient's face has a mean luminance of 0.45–0.60**, and no large area is crushed black or blown white. Measure it with a script on the stills, before and after, and include both stills in `docs/lighting.md`.
2. **Developer: Stage 1 systems.** Build these from `briefs/02-developer.md`, now including **voice**:
   - EncounterManager, CaseLoader, PatientBrain + GuardCheck, PatientState
   - CueDriver for the 8 slice cues
   - **Exam actions** triggered by spoken requests ("hold your hands out for me") and gated by trust
   - uLipSync on the CC visemes
   - **Voice UI:** hands-free mode (VAD) by default, push-to-talk on Space as an option, typed chat always available as a fallback. A mic level meter, a "listening / thinking / speaking" indicator, and live subtitles for both sides.
   - MSE panel, DiagnosisPicker, PrescriptionPad, basic score and SessionLog
   - **The S1 items from the plan:**
     - realism rules and banned words (A2)
     - risk-first scoring weights (C1)
     - quote-grounded side-by-side debrief (C2, C5)
     - prebrief screen (C6)
     - 15-minute station timer (D4)
3. **Start screen:** choose the case, then choose **patient: Female (Ananya) / Male (Arjun)**, then Practice or Assessment mode.
4. **Entrance sequence:** the door opens, the chosen patient walks in, sits, looks at the doctor, and the encounter starts.

## 6. Phase 4: test gates (tester subagent)
Run the Stage 0 and Stage 1 gates from `briefs/03-tester.md` plus the plan's S1 test items:
- **E1:** the PSYCHE jailbreak set
- **E2:** automatic honesty and resistance metrics, plus the instruction-decay test
- **E4:** latency, verifying Phase 1's numbers independently with 100 timed voice turns
- **The A6 portrayal checklist**
- **No LLM ever judges realism (C8)**
- **Speech-to-text accuracy** on Indian-accented English (§2.3b)
- **Both sex variants** play end to end
- **The lighting acceptance check**

File bugs in `bugs/`. Developer and artist fix them. Repeat until the gates pass or only Minor and Cosmetic bugs remain. Commit after every deliverable that lands.

## 7. Phase 5: the staged demo video (you own this, after the gates pass)
Make a **2–3 minute, 1920×1080, 60 fps MP4 with audio**: `demo/PsychSim_demo_v1.mp4`.
- **Dr. Faaz speaks.** Ask me once whether I want to record Dr. Faaz's lines myself (give me the script and a one-line command to record). If I decline, synthesise them with KittenTTS voice **Hugo**. Either way, **feed the doctor's audio into the real microphone path** (VAD → STT → model → TTS), so the demo proves the live voice loop. Never fake it with pre-baked patient answers. Patient replies are generated live; pre-roll until a take shows the disclosure and the cues clearly, then lock that take.
- **Shots** (Cinemachine, with `com.unity.recorder` for capture):
  1. Title card: "PsychSim · Embodied psychiatry & addiction OSCE simulator · For education only"
  2. Start screen: choose the case, show **both** patient options, pick Ananya
  3. Establishing shot of the brighter room
  4. Door opens; Ananya walks in and sits
  5. Over-the-shoulder interview with Dr. Faaz speaking: the listening/thinking/speaking indicator and subtitles visible
  6. Close-ups on cues: gaze drop, tearful eyes, fidgeting hands, a slowed reply
  7. Dr. Faaz asks her to hold out her hands (exam action)
  8. Trust rises and she discloses passive suicidal thoughts
  9. Tablet: MSE ticks, diagnosis, prescription
  10. Debrief: side-by-side truth, risk-first score, quoted feedback
  11. A 10-second cut of **Arjun** in the same room, showing the male variant
  12. End card: the latency number you actually measured, what's next, "Draft clinical content, not yet faculty-validated"
- **Post with ffmpeg:** cards, light crossfades, loudness around −16 LUFS, H.264 high profile, AAC 192k. Also export a **≤10 MB teaser** (`docs/media/teaser.gif` or `.mp4`, under 20 s) and **6 stills** (`demo/stills/`).
- **Verify before calling it done:**
  - `ffprobe`: 1080p, about 60 fps, an audio stream, 120–180 s
  - Extract a frame every 10 s and **look at every one**: no pink materials, T-poses or chair clipping; readable subtitles; brightness inside the lighting range
  - Transcribe the audio back and compare it to the script

  Fix and re-render until all of these pass.

## 8. Phase 6: README, pitch deck, GitHub
1. **`README.md` (the repo front page):**
   - what PsychSim is (the one-line positioning from plan Part 1)
   - the teaser at the top and a link to the full demo
   - features (voice, cues, trust-gated disclosure, exam actions, male/female patients, risk-first debrief, Indian MHCA dispositions)
   - an architecture diagram (Mermaid)
   - the **local model stack** with exact model names and licences (LLM, Parakeet, KittenTTS)
   - measured latency
   - how to run: one command for the service, one for Unity
   - the roadmap (Stages 2–4; VR parked)
   - "Evidence and positioning", summarising plan Parts 1–3 with links to R1–R11
   - the safety and "for education only" disclaimer
   - credits: Dr. Faaz
2. **Pitch deck:** `docs/pitch/PsychSim_pitch.pptx` plus a PDF export. 16:9, 10–12 slides. Use the pptx skill if this session has it, otherwise python-pptx.
   - Slides: problem (psychiatry simulation is underused; actors struggle with psychosis and mania; low trainer ratios; R1) → why LLM patients alone fall short (text-only, too forthcoming; R2–R4, R9) → PsychSim → live demo stills → how it works → what's new compared with the literature (plan Part 1 table) → safety design → measured numbers (latency, evaluation pass rates) → evidence plan (the randomised trial from plan Part 3) → India fit (MHCA, NLEM, Tele-MANAS) → roadmap → the ask (a pilot in the psychiatry rotation, faculty case reviewers).
   - Use only numbers you actually measured or that the cited papers report, with the paper named on the slide.
3. **GitHub:** push `main`. Create release `v0.1-stage1` with `gh release create`, attaching the full demo MP4 and the deck PDF. Release assets avoid LFS limits. Link both from the README. Check the README renders correctly with `gh browse` or `gh api`.

## 9. Rules
- `PLAN_insights.md` (approved) and `DESIGN.md` are the source of truth. Raise conflicts with me; don't resolve them silently.
- Clinical content is **draft**. Never present doses, codes or legal points as validated.
- No accounts, licence acceptances, purchases, or downloads that need sign-in. If one is needed, stop and ask.
- Nothing personal leaves this Mac: no cloud model calls unless `PATIENT_LLM=grok` is set explicitly. Never write microphone audio to disk except the demo's doctor recordings, which I approve.
- Don't build past Stage 1, except the voice loop, exam actions, sex variants, the lighting work, and the demo and doc tooling above. VR is parked.
- If you are blocked after 2 attempts on the same problem, stop and tell me what you tried.

## 10. Report back with
- `STAGE_1_NOTES.md`: what was built, how to run it, gate results with numbers (latency p50/p90 per stage, model bake-off winner, evaluation pass rates, STT word error rate, lighting luminance), and open bugs.
- Links: the GitHub repo, the release, the demo, the deck. Plus the 6 stills.
- What you'd do next for Stage 2.
```
