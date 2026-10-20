# PsychSim: status and pending work (handoff, 2026-10-18 night)

**To continue:** open Claude Code in `/Users/faazkhn/Documents/Med` and say:
> Read `HANDOFF.md` and `KICKOFF_PROMPT.md`, then continue from "Next steps" in HANDOFF.md.

The full brief is `KICKOFF_PROMPT.md`. It covers Phases 0–6, the rules and what to report. This file records where that run stopped.

---

## 1. Owner decisions already made (don't ask again)
- `PLAN_insights.md` is approved. The OSCE station is **15 min**, the lived-experience reviewer is **optional**, and the pilot control arm is **reading material**.
- Demo doctor voice: **synthesise Dr. Faaz with KittenTTS voice `Hugo`**. The owner declined to record. The lines are in `demo/doctor_lines.txt` (11 lines). They must still go through the real mic path (VAD → STT → LLM → TTS).
- Branch is `main`. The remote is `https://github.com/faazkhn/PsychSim` (private).
- The existing repo history was kept: `master` was renamed to `main` instead of running a fresh `git init`.

## 2. Done and pushed (origin/main = `7109cd7`)
| Commit | What |
|---|---|
| `b4c0739` | **Phase 0.** `DESIGN.md` v0.3 with changelog (plan Part 4 + voice in Stage 1, local LLM, Parakeet, sex variants, lighting, latency targets, §13). All 3 briefs updated. `references/README.md` (R1–R11). Only the 5 CC BY PDFs are committed; the 4 arXiv PDFs are git-ignored. `.gitignore` covers `models/`. LFS covers `*.gguf *.onnx`. |
| `7109cd7` | **Phase 3.1 lighting (Unity).** Key 5,000 K, fill 3,200 K, rim, baked GI, light probes, reflection probe, post volume. Warm off-white walls with a terracotta accent. Window, blinds and tissues added. Matt's textures extracted (he was rendering white). Code: `Assets/Scripts/Editor/EncounterLighting.cs` and `LightingStills.cs` (menu **PsychSim/Capture Lighting Stills**), checked by `tools/lighting/face_luminance.py`. **Face luminance: Mégane 0.502, Matt 0.500 (PASS 0.45–0.60), 0% blown.** Before: 0.624 (fail). Details in `docs/lighting.md`. |

## 3. Done locally, NOT pushed
- `1409f73` (committed by the developer agent): **Phase 1 data + service start.**
  - v0.3 case schema: `behavior`, `style`, `banned_words`, `principles`, `rubric`, `variants`, `exam_actions`.
  - `mdd_01` has the Ananya/Arjun variants.
  - The reply schema is ordered `emotion, utterance, …` and includes `exam_action`.
  - New `session.py` (WebSocket), `stream.py` (incremental parser) and `stt.py`.
  - Tests for variants.
  - `tools/stt_bench/questions.txt` (104 questions).

## 4. Uncommitted work in progress (left by the two stopped agents)
Review it before committing. Nothing here has been verified by the lead.

**Developer (service):**
- Modified: `server/patient-service/run.sh` and `session.py`.
- New: `tests/test_session.py`, `tests/test_stream.py`, `tools/latency/ws_bench.py` with `tools/latency/doctor_lines.txt` (WebSocket latency bench using macOS `say` en_IN voices, never the mic), and `tools/stt_bench/bench.py`.
- **Service tests currently: 40 passed, 1 deselected.**
- `parakeet_mlx` and `mlx_whisper` import fine in `server/patient-service/.venv`, but **they are not listed in `requirements.txt`**. Add them.
- Models downloaded to `models/` (git-ignored): `gemma-4-E2B-it-Q4_K_M.gguf` (2.9 GB), `gemma-4-E4B-it-Q4_K_M.gguf` (4.6 GB), `Qwen3.5-4B-Q4_K_M.gguf` (2.6 GB), `Qwen3.5-9B-Q4_K_M.gguf` (5.3 GB). All four downloaded with no sign-in.
- **Not produced yet:**
  - the bake-off (`docs/model-bakeoff.md`)
  - `models/README.md`
  - the STT benchmark results
  - `docs/latency.md`
  - the LLM eval set (`tests/llm-eval/mdd_01/*.yaml`)
  - `server/patient-service/PROTOCOL.md`
  - the list of C# changes Unity needs for the new data shape
- The orphaned `llama-server` (port 8080) and two `uvicorn` processes (ports 8765, 8766) were stopped.

**Artist (Blender):**
- New clips: `art/Animations/action_hold_out_hands.fbx`, `action_roll_up_sleeves.fbx`, `action_look_at_light.fbx`, plus `Face/face_squint.json`.
- **All existing clips were re-exported** (`base_sit_*`, cues and gestures; the latest change was a +8 mm seat-height compromise between the two bodies). `tools/blender/make_clips.py` was updated (+350 lines).
- About 116 preview PNGs were modified or added in `art/Animations/previews/`, including new `matt_*` previews for every clip.
- It was stopped while checking `base_sit_slumped` on Matt, so that clip is **unverified**.
- `art/Animations/ANIMATIONS.md` has **not** been updated for the new clips.
- Blender is still open, with the agent's scene.

## 5. Next steps (in order)
1. **Review and commit the WIP** (§4).
   - Look at the `matt_*` and `action_*` previews for clipping or T-poses.
   - Finish the `base_sit_slumped` check on both models.
   - Update `ANIMATIONS.md`.
   - Check the LFS size before pushing: `git lfs ls-files -s`. It is ~636 MB unique now, with a **900 MB limit**. The previews are PNGs, so they go through LFS; keep them small.
2. **Finish Phase 1** (developer, outside Unity):
   - PROTOCOL.md.
   - The eval set (≥10 conversations × 5 runs, the PSYCHE jailbreaks, the A6 checklist, the E2 metrics).
   - The 4-model bake-off. Choose the smallest model that passes, then time it under LM Studio MLX.
   - The STT benchmark: Parakeet vs whisper-large-v3-turbo. Try an ungated Indian-English dataset; otherwise use synthetic `say` en_IN audio, labelled as a proxy.
   - Latency: ≥50 turns through the WebSocket. Target p50 ≤ 1.2 s, p90 ≤ 1.8 s. **If it's missed, show the owner the per-stage breakdown before trading quality.**
   - Write `docs/model-bakeoff.md`, `docs/latency.md` and `models/README.md`.
3. **Phase 3, Unity** (one agent at a time on the Unity MCP):
   - Import the 3 exam-action clips and the re-exported clips.
   - Developer Stage 1 systems from `KICKOFF_PROMPT.md` §5.2:
     - the voice WebSocket client, with hands-free / PTT on Space / typed modes, a mic meter, a listening/thinking/speaking indicator and subtitles
     - exam actions gated by trust
     - C# updates for the v0.3 data and the variants
     - realism rules
     - risk-first weights
     - the quote-grounded side-by-side debrief
     - the prebrief
     - the 15-min timer
   - The start screen (case → Female Ananya / Male Arjun → Practice/Assessment).
   - The entrance sequence for both models.
4. **Phase 4 tester gates** (`KICKOFF_PROMPT.md` §6). File bugs in `bugs/` and loop until only Minor or Cosmetic bugs remain.
5. **Phase 5 demo:** 2–3 min, 1080p60, Hugo as Dr. Faaz through the real mic path, all 12 shots, ffmpeg post, a ≤10 MB teaser, 6 stills, and the verify loop. **Don't commit the demo MP4** (LFS budget); attach it to the release instead.
6. **Phase 6:**
   - README with the Mermaid diagram, the local model stack and licences, and the measured latency.
   - The pitch deck as pptx and PDF.
   - `gh release create v0.1-stage1` with the MP4 and the deck PDF.
   - Update `STAGE_1_NOTES.md`. It is still the PoC version from the earlier Grok/scripted run.

## 6. Open issues and decisions for the owner
- **Chair angle:** the doctor faces the patient at ~156° (almost straight across); the brief asks for 90–120°. Fixing it moves the doctor's chair by the window and puts the door behind the doctor. Not changed; owner's call.
- **Room colours:** the recolour exists only in Unity's palette texture. Re-running `tools/blender/make_office.py` would bring the grey walls back.
- **Old demo in history:** the old PoC demo (`demo/PsychSim_demo_v1.mp4`, 131 MB, scripted replies) is in git history and counts toward LFS. The new demo should go only on the release.
- **Repo clutter:** `*.rar` archives (~1.4 GB) sit in the repo root. They are git-ignored, so they're harmless.
- **Ambient occlusion:** there's no SSAO on the mobile/Quest renderer (VR is parked, so it isn't urgent). Mégane's hair edges look stringy.
- **Clinical content:** all of it is draft and not faculty-validated.
