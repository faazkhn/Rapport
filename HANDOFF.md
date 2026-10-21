# Rapport (formerly PsychSim): handoff, 2026-10-20

**To continue:** open Claude Code in `/Users/faazkhn/Documents/Med` and say:
> Read `HANDOFF.md`, then implement `KICKOFF_PROMPT_v4.md` (the Rapport / Digital Twin plan), starting at Phase A.

## 1. Owner decisions (don't ask again)
- New name **Rapport**; the patient brain is the **Digital Twin**. Plan: `KICKOFF_PROMPT_v4.md` (owner-approved, not started).
- **Commits are authored `faazkhn <faazkhn1000@gmail.com>` with no Claude co-author / "Generated with" lines.** History was rewritten and force-pushed on 2026-10-20 (local backup branch `backup/pre-author-rewrite`).
- Demo doctor voice: KittenTTS `Hugo`, fed through the real mic path. The owner will not record their voice.
- Raw demo takes are shown unedited. The staged demo (`demo/Rapport_demo_staged.mp4`) has no title/end cards or badges (owner, 2026-10-20); its replies are pre-scripted, so say so when presenting it.
- Clinical content stays draft. Release builds are blocked by the content gate until faculty approve; ship Development builds.

## 2. State
- `main` on GitHub = `654a222`. The §4 work is committed locally on top of it (not pushed).
- Live stack: llama-server (Gemma 4 E4B, `gemma4-nothink.jinja`) + patient service (`server/patient-service/run.sh`) + Unity 6000.6.2f1. Measured latency and the free cloud fallbacks: `docs/latency.md`.
- Playable app: `PsychSim.command` → `unity/PsychSim/Builds/PsychSim.app` (Development build, VAD 500 ms). Rebuild after the §4 fixes.
- Demos (not in git; LFS budget): `demo/PsychSim_demo_v2.mp4` (raw live take, 4:00) and `demo/Rapport_demo_staged.mp4` (staged, 4:00).

## 3. Staged concept preview (how it was made)
- Service staged mode: `RAPPORT_STAGED=$PWD/demo/staged/script.json server/patient-service/run.sh` (`staged.py`). Doctor audio still goes through the mic path and VAD; each turn answers with the next scripted line and its pre-rendered WAV at a planned 0.6 s gap, plus a `brain_snapshot` event.
- Script and brain blocks: `demo/staged/script.json`. Voices: Qwen3-TTS 1.7B VoiceDesign (Apache-2.0) via mlx-audio, designed from text (no cloning): `tools/tts_lab/render_staged.py`, `tools/tts_lab/NOTES.md`, output `demo/staged/audio/`.
- Unity menu **PsychSim/Record Staged Demo** (+ Arjun cut) → `demo/raw/Rapport_staged*.mp4`.
- `tools/demo/staged_cut.py` (turn times; trims any dead air) → `staged_timeline.py` → `capture_twin.mjs` (Digital Twin, 600x1080) → `staged_compose.py` (Twin over the side panel, then the Arjun take; `--twin-in 20.3 --twin-out 188.5` for the 2026-10-20 take).
- Digital Twin v1: `server/patient-service/twin/` (served at `http://127.0.0.1:8765/twin/`; README inside). Driven by a scripted timeline only; the live `brain_snapshot` wiring is Phase F.

## 4. Changes since the last push (committed locally, not pushed)
- **Real bug fixed, `VoiceSession.cs` `Send`:** awaits resumed on the main thread, capping the mic at ~30 frames/s (31.25 needed), so mic latency grew all session (3 s → 13.5 s over 12 turns in a take). This also hit live use with a real mic. Now `ConfigureAwait(false)`. The virtual mic is also paced by `Time.captureDeltaTime` while recording. **Verify with a fresh take / `ws_bench` and re-measure `docs/latency.md`.**
- macOS App Nap disabled for Unity (`defaults write com.unity3d.UnityEditor5.x NSAppSleepDisabled -bool YES`). Without it the editor nearly stops in the background and recordings stall.
- Hair (Ananya): the CC3 import had merged two hair materials, so the main hairstyle used the bangs' sparse atlas (26% coverage → 73%). New `Hair_Transparency_Main.mat` + `Hair_Transparency_Diffuse_0001_A.png`, cutoff 0.22, coverage-preserving mips, tint to the source brown. Arjun's blond hair matches the supplied model (owner may want it darker).
- Debrief hides the greyed tablet panel. The UI title reads "Rapport". Hands-exam close-up in `DemoDirector`.
- `cue_wipe_tears` reads as touching the nose. A single clip can't fit both bodies (measured: Matt's fingers land 1.5–3 cm deeper). Decision: hand IK in Unity, aiming at each body's eye bone (do it with the Phase H exam IK). It is switched off for staged demos only (`CueDriver.WipeTears`). The candidate Blender patch was in a scratchpad that has since been cleared.
- Service: `staged.py`, `/twin` static mount in `app.py`, staged test (41 tests pass).

## 4b. Live Digital Twin (branch `live-digital-twin`, 2026-10-20)
- Plan: `docs/superpowers/plans/2026-10-20-live-digital-twin.md`; spec of what was built: `docs/TWIN.md`; decision: `docs/adr/0001-digital-twin-architecture.md`.
- Every live turn: lexical recall with trust locks → one structured call (`behaviour, emotion, utterance, reaction, intensity, resistance, …`) → guard → expression map → `twin.update` (trust step + PAD mood) → `brain_snapshot`.
- Twin view live at `http://127.0.0.1:8765/twin/?live=1` (`/twin/ws`); sessions logged to `logs/twin/*.jsonl`, replay via `tools/demo/log_to_timeline.py`.
- Latency p50 1,598 ms / p90 1,731 ms (ws_bench, 26 turns). The owner chose behaviour-only before the words after all-labels-first measured p50 3,068 ms.
- Service tests 75 pass; Unity EditMode 28 pass.

## 4c. Production readiness (branch `production-readiness`, paused 2026-10-21)
- Repo renamed on GitHub to **faazkhn/Rapport** (remote updated). PR #1 (`live-digital-twin`) is open, not merged.
- Phase A audit done: `docs/STATE_AUDIT.md` (owner feedback → root causes, what's left).
- Phase G done 2026-10-21 (plan `docs/superpowers/plans/2026-10-21-phase-g-voice-quality.md`):
  - Task 1 (reply realism, hesitation cap) + Task 2 (pauses ≤ 1.2 s): committed. **Eval gate skipped by owner**; `docs/voice-quality.md` not written. Baseline only: `tests/llm-eval/results/g-before.jsonl`.
  - Task 3 bake-off: `docs/tts-bakeoff.md`, blind page `docs/listening/index.html`. Winner **Qwen3-TTS 1.7B VoiceDesign** (TTFA 174 ms, RTF 0.57, word acc 1.0, emotion sep 3.92 vs Kitten 0.67). Run offline: Kokoro, Qwen 0.6B, Chatterbox not tested; re-run `tools/tts_lab/bakeoff.py` online.
  - Task 4: `voice.QwenDesign` streaming backend (`RAPPORT_TTS`, default `qwen3-design`; `kitten` to force old), emotion instruction from `expression_map.json` (`voice`, `emotions`) + case `voice_description`; Kitten fallback on load or synthesis error.
  - Task 5: speculative STT (STT wait p50 227 → 0 ms), Smart Turn code (`stt.SmartTurn`, needs `models/smart-turn-v3.onnx`, not downloaded: offline), first-clause split. ADR 0002.
  - **Latency: p50 2,326 / p90 3,018 ms, target 700 missed.** Regression from 1,598 is Task 1's prompt (TTFT 400 vs 224, first sentence 1,150 vs 604), not TTS. Levers in `docs/latency.md`.
  - App rebuilt (`PsychSim > Build macOS (Development)`, `Editor/BuildMac.cs`); start screen checked. Service tests 99, Unity EditMode 29/29.
  - Open risks: Qwen speaker drift between sentences (seed fixed per variant); Qwen ignores speed (pressured speech); possible audio underrun when GPU busy.
  - Next: Smart Turn download + re-measure, realism eval gate.
- Phase H done 2026-10-21 (plan `docs/superpowers/plans/2026-10-21-phase-h-camera-exam.md`):
  - Exam router `server/patient-service/exam_router.py` (rules, lexicon `data/exam_router.json`, no embeddings: offline). 367-utterance set, 100% / 0 false triggers. The author wrote the set, so it is optimistic: `docs/exam-actions.md`.
  - The service gates trust and agitation (`brain.exam_for_turn`), sends `exam` before `thinking`, and the Twin acknowledges, refuses or asks "Which hand?". The LLM no longer picks `exam_action`.
  - Unity: `Cues/ExamQueue.cs` (order, hold until relax or 30 s, sits before sleeves, stands before a walk) + `Cues/ExamController.cs`:
    - hand IK on the clip, palms;
    - jaw and tongue blendshapes;
    - follow_finger gaze;
    - stand, walk and sit;
    - IK for wipe_tears (not checked live).
  - New clips `stand_up`, `stand_idle` (`make_clips.py --only`).
  - Camera: `Platform/CameraDirector.cs` (Cinemachine runtime, 42° FOV, scroll lean-in, close-ups per action), `docs/camera.md` with stills.
  - Tests: service 118, Unity EditMode 37. App rebuilt.
  - Known: single-hand pose keeps lap-curled fingers; palms-up has no forearm supination; walk direction tuned for this room only (`ExamController.WalkTurnDeg`).
  - Final review (fresh reviewer) fixed:
    - interview phrases ("walk me through", "stand up for yourself") no longer trigger stand or walk;
    - "I'd like to see your hands" works;
    - "Which hand?" can be answered next turn;
    - chained commands no longer wait 30 s;
    - hands come down at once on relax;
    - the staged demo sends exam messages.
    Router set is now 385 items. Deferred minors are in the ledger rulings in the final report.
- Next: Phases B leftovers, C, E, I.
- Live demo guide: `docs/LIVE_DEMO_GUIDE.md` (run from the Unity editor until the app is rebuilt).

## 5. Next steps
1. Commit §4; rebuild the player; re-measure latency after the send fix.
2. `KICKOFF_PROMPT_v4.md` Phases A–I: audit, rename (repo, product, bundle id, menus, `PSYCHSIM_*` → `RAPPORT_*` aliases), literature review, Digital Twin brain, self-learning with A/B, Twin live wiring, TTS bake-off (Qwen3-TTS is the lead candidate) + Smart Turn + streaming STT, camera and exam router with IK, gates, demo v3, release `v0.2-twin`.

## 6. Open for the owner
- Chair angle (~156°, the brief asks 90–120°), Arjun's hair colour, and faculty sign-off on the clinical content.
- LFS: 678 MB uploaded on the last push, against the 900 MB budget. Check usage on GitHub before adding more binaries.
