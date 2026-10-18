# Stage 1 notes (2026-10-18)

## Built
- **Room:** the low-poly office pack (`Office.rar` + `Texture.rar`, source in `art_source/Office/`) converted by `tools/blender/make_office.py`. The script scales the room to real size, closes it with two walls, a ceiling, a door and a corridor (using the pack's own palette), moves the desk against the new wall, turns the doctor's chair to face the patient on the sofa, and adds the room-contract anchors. Output: `art/Environments/Office/` (FBX, blend, previews), imported to `Assets/Art/Environments/Office/`. The earlier generated room (`art/Environments/OutpatientConsult/`) is no longer used.
- **Unity Stage 1 systems** (from the earlier session): EncounterManager, entrance sequence, CaseLoader, PatientBrain + GuardCheck, PatientState, CueDriver (8 cues), uLipSync, chat with subtitles, MSE, diagnosis, prescription, disposition, scoring, SessionLog. `PsychSim/Build Placeholder Encounter Scene` now uses the office room when its FBX is present.
- **Demo tooling:** `DemoDirector` (staged take from `demo/script.json`), `PsychSim/Record Demo` (Unity Recorder, 1080p60 with audio) and `tools/demo/post.py` (cards, room tone, -16 LUFS, checks, stills). See `demo/shotlist.md`.

## Fixes this session
- The entrance never started: `GetComponent<T>() ?? AddComponent<T>()` does not work on Unity objects, which come back as a "fake null" rather than real null, so `??` never falls through. It threw on the door's missing AudioSource. The same bug was in 3 places, all fixed.
- The CC3 eye and hair layers that are transparent at alpha 0 still reflected the default sky, which showed as cyan eyes indoors. Environment reflections are now off in the built scene.
- The demo needs the editor in run-in-background mode, set by the record menu.

## How to run
- Service, live Grok: `server/patient-service/run.sh` (needs a valid `XAI_API_KEY`)
- Service, demo take: `PSYCHSIM_DEMO_SCRIPT=$PWD/demo/script.json server/patient-service/run.sh --mock`
- Unity: open `unity/PsychSim`, scene `Assets/Scenes/Encounter.unity`, press Play (or **PsychSim/Record Demo**).

## Results
- Service tests: 18 passed. Unity EditMode tests: 26/26 passed.
- Demo: `demo/PsychSim_demo_v1.mp4`: 1920x1080, 60 fps, with audio, 178.6 s, -15.8 LUFS. Check frames reviewed: no missing materials, no T-poses, no clipping into the sofa. Score screen: "No critical errors", 73.4/100.
- The take records at a steady 60 fps in the editor on this Mac with the editor focused.

## Open issues
- **xAI API key invalid.** Both the shell `XAI_API_KEY` and `.env` are rejected by api.x.ai ("Incorrect API key provided"). The demo take therefore uses scripted patient replies (stated on the end card). The LLM evaluation suite (0 invented facts in 50 conversations) has **not** been run, and Stage 1 is not gated until it has.
- Not done (fast-tracked for the PoC demo): play-mode integration test, `bugs/` triage, profiler gate on M1, whisper listen-check of the demo audio.
- Lighting is real-time, not baked; Quest budgets have not been checked for the office room (13,960 triangles, 1 material).
- All clinical content is draft and not faculty-validated.

## Next for Stage 2
Fix the API key and run the LLM eval suite on both models. Then add voice input (whisper.cpp) with latency logging, bake the lighting, and do a per-cue readability review at 1.5 m.
