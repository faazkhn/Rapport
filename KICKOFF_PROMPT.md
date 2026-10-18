# Kickoff prompt for Claude Code

Open Claude Code in `/Users/faazkhn/Documents/Med`, make sure `XAI_API_KEY` is set in that shell, and paste the whole block below.

```text
You are the **lead** on PsychSim, a VR-ready clinical training simulator where doctors interview 3D psychiatric and addiction patients. You coordinate three specialist subagents (3D artist, developer, tester) and personally own integration, the final review and the demo video.

## Goal for this run
Deliver **Stage 0 and Stage 1** from `DESIGN.md` §10, plus a patient entrance, then a polished demo video:

> In the outpatient consult room, the patient **walks in through the door, sits down** in the patient chair, and the learner interviews them by typing. The patient answers through Grok (xAI), speaks with KittenTTS, lip-syncs, and shows the case's cues live (gaze avoidance, slumped posture, slowed replies, flat affect, tearfulness, fidgeting, fine tremor, restlessness). The learner fills the MSE panel, picks a diagnosis, writes a prescription and sees the basic score screen. Everything runs on this Mac.

Out of scope this run: voice input, other rooms, other cases, scales, VR, the hub. Don't build them.

## Read these first, in this order
1. `DESIGN.md`: the source of truth. If anything else disagrees with it, it wins.
2. `RIG_REPORT.md`: the state of the two patient models.
3. `briefs/01-3d-artist.md`, `briefs/02-developer.md`, `briefs/03-tester.md`: one brief per subagent.
4. `tools/tts/tts_check.py`: working KittenTTS code (the venv is at `tools/tts/.venv`).

## What already exists
- `art/Matt/Matt.Fbx`: Matt rebuilt at 79.5k triangles. **Use this, not `art_source/Blender/Matt.Fbx`.**
- `art_source/Mégane_Blender/Mégane_Blender.Fbx`: Mégane, 83.8k triangles, usable as-is.
- Both are Character Creator 3+ rigs (101 bones, 149 facial blendshapes, 8 visemes). `.json` material files sit next to the originals.
- The patient's language model is **xAI Grok** (not Claude): OpenAI-compatible API at `https://api.x.ai/v1`, key in `XAI_API_KEY`, JSON-schema structured output via `response_format`. Default model `grok-4.20-0309-non-reasoning`; comparison model `grok-4.7` with reasoning effort `low`. Check docs.x.ai if a model name or parameter has changed.
- KittenTTS `KittenML/kitten-tts-mini-0.8` is installed and measured at about 0.4 s per sentence.
- Machine: Apple M5 Pro, macOS 26.6. Installed: Unity Hub, **Unity Editor 6000.6.2f1** (use this version), Blender 5.2 LTS, ffmpeg, ffprobe, git, git-lfs.
- MCP servers: **Unity MCP** (drives the Unity editor) and **Blender MCP** (drives a running Blender). Use them.

## Setup (do this yourself before spawning anyone)
1. `git init` in this folder with git-lfs for `*.fbx *.Fbx *.png *.jpg *.tga *.wav *.mp4 *.blend`. Ignore `.venv/`, `art_source/` (too big; it is source material), Unity's `Library/ Temp/ Logs/ UserSettings/`, and `.env`. Make the first commit.
2. Create the Unity project at `unity/PsychSim` with URP using Editor 6000.6.2f1. Open it so the Unity MCP connects. Confirm the connection by reading `mcpforunity://editor/state`.
3. Check that `XAI_API_KEY` is available to the patient service. If it is not set, **stop and ask me**. Never write the key into any file except a git-ignored `.env`.

## Team and order of work
Spawn the subagents with the Agent tool. Give each one its brief path, the relevant `DESIGN.md` sections, and exact done-criteria. Only one agent may drive the Unity editor at a time, because the Unity MCP talks to a single editor. Run work in parallel only when it uses different tools.

**Phase A (parallel):**
- **3D artist (Blender MCP, Blender files only):** author these clips on the shared CC3 skeleton and export them as FBX animation files to `art/Animations/`:
  - `walk_in` (about 4 m, root motion)
  - `sit_down` (stand to seated, ending on the chair at 0.45 m)
  - `base_sit_neutral`, `base_sit_slumped`
  - `cue_fidget_nails_Hands`, `cue_wipe_tears`
  - `gesture_talk_small` (×2), `gesture_nod`, `gesture_head_shake`

  Keyframed animation is acceptable, but it must not look robotic: add weight shift, overlapping motion and breathing. There is no motion-capture source, so **do not** create accounts or download from Mixamo or asset stores. Also make 5 face-expression presets from blendshapes: `face_neutral`, `face_sad`, `face_flat`, `face_anxious`, `face_ashamed`.
- **Developer (code outside Unity first):**
  - Build `server/patient-service`: FastAPI with `/reply` (Grok via the OpenAI Python SDK with `base_url="https://api.x.ai/v1"`, model `grok-4.20-0309-non-reasoning`, structured JSON per `DESIGN.md` §7.2 using `response_format` JSON schema with `strict: true`) and `/tts` (KittenTTS mini, voice and speed). Reuse the venv approach in `tools/tts`.
  - Write the JSON schemas and `data/` files (cues, intents, diagnoses, dispositions, a small formulary skeleton).
  - Write case `mdd_01.json` (major depressive disorder with passive suicidal ideation; Indian setting and name; patient model Mégane `female_20s_a`; voice `Bella` or `Luna`). Mark it `"status": "draft"`. Leave doses `null` for faculty to fill.
  - Write unit tests for the service.

**Phase B (one at a time, in Unity):**
1. Artist builds the **outpatient consult room** in Unity to the artist brief §2: DoctorAnchor, PatientAnchor, door, a bare corner, baked light, and the Quest 3S budgets. Imports both patients (try CC Unity Tools; if that fails, use plain Humanoid FBX import with URP Lit materials) and the clips from Phase A.
2. Developer builds the Stage 1 systems from `briefs/02-developer.md`: EncounterManager, CaseLoader, PatientBrain + GuardCheck (calls the patient service), PatientState, CueDriver for the 8 slice cues, uLipSync on the CC visemes, typed chat with subtitles, MSE panel, DiagnosisPicker, PrescriptionPad, basic score, SessionLog. Add an **entrance sequence**: door opens, the patient walks from the door to the chair (NavMesh or a spline with root motion), sits, looks at the doctor, and the encounter starts.
3. Tester runs the Stage 0 and Stage 1 gates from `briefs/03-tester.md`, including the LLM evaluation suite for `mdd_01` (no invented facts, prompt injection, judgmental learner, and the other cases in §2.2). File bugs in `bugs/` using the template. Developer and artist fix them. Repeat until the gates pass or only Minor and Cosmetic bugs remain.

Commit after each agent's deliverable lands, with a clear message.

## Demo video (you own this, after the gates pass)
Make a **2–3 minute, 1920×1080, 60 fps MP4 with audio**: `demo/PsychSim_demo_v1.mp4`.

- **Capture:** install `com.unity.recorder` and Cinemachine. Build a `DemoDirector` that plays a scripted, deterministic run: the doctor's typed lines come from `demo/script.json`. Speak them with a KittenTTS male voice that differs from the patient's, so viewers hear both sides. Patient replies are **live Grok**. Pre-roll it until a take shows the hidden-fact reveal and cues clearly, then lock that take.
- **Shots (Cinemachine):**
  1. Title card: "PsychSim · Clinical encounter simulator · For education only"
  2. Establishing shot of the room
  3. Door opens, patient walks in and sits
  4. Over-the-shoulder doctor view during the interview
  5. Close-ups when a cue fires (gaze drop, tearful eyes, fidgeting hands, a slowed reply)
  6. The moment trust rises and the patient discloses passive suicidal thoughts
  7. Tablet UI: MSE ticks, diagnosis picked, prescription written
  8. Score and debrief screen
  9. End card: what is coming next (voice input, 10 cases, VR on Quest 3S) and "Draft content, not yet faculty-validated"
- Subtitles on for both speakers. Soft room tone under the dialogue. No music over speech.
- **Post with ffmpeg:** title and end cards, light crossfades, loudness normalised to about −16 LUFS, H.264 high profile, AAC 192k.
- **Verify before you call it done:**
  - `ffprobe` shows 1920×1080, about 60 fps, an audio stream, and a duration of 120–180 s.
  - Extract one frame every 10 s and **look at every frame**: no pink or missing materials, no T-poses, no clipping through the chair, subtitles readable.
  - Listen-check by transcribing the audio back with whisper and comparing it to the script.

  Fix and re-render until all three pass. Also export `demo/shotlist.md` and 6 still frames (`demo/stills/`) for slides.

## Rules
- Clinical content is **draft**. Never present doses, codes or legal points as validated. The demo end card says so.
- Do not create accounts, accept licences, buy assets, or download anything that needs sign-in. If something needs one, stop and ask me.
- Don't build beyond Stage 1 (except the entrance sequence and the demo tooling above).
- Keep the xAI API key out of git, logs and the video.
- If you are blocked for more than 2 attempts on the same problem, stop and tell me what you tried.

## Report back with
- `STAGE_1_NOTES.md`: what was built, how to run it (one command for the service, one for Unity), gate results with numbers (fps, latency p90, LLM eval pass rate), and open bugs.
- The demo video path, its ffprobe summary, and the 6 stills.
- What you would do next for Stage 2.
```
