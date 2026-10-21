# Phase I Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (owner chose native, one task at a time, no parallel work). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `v0.2-twin`: every gate passes on the final brain version and voice, demo v3 is recorded from live replies, README and pitch deck describe what was measured, and the GitHub release carries the demo, deck and learning report.

**Architecture:** No new subsystems. Gates reuse `tools/llm_eval` (run_eval + score + judge), `tools/latency/ws_bench.py`, `tools/stt_bench/bench.py`, the service pytest suite and Unity EditMode tests. Demo v3 reuses `Rapport/Record Demo` (`Editor/DemoRecorder.cs`), `tools/demo/capture_twin.mjs` and the compose scripts, fed from the live `logs/twin/*.jsonl` via `log_to_timeline.py`.

**Tech Stack:** Python 3.12 service venv, llama-server :8080 (Gemma 4 E4B), Unity 6000.6.2f1 (MCP or batch), ffmpeg/ffprobe, node (puppeteer), `gh`.

**Spec:** `KICKOFF_PROMPT_v4.md` Phase I; gate definitions `KICKOFF_PROMPT.md` §6 (E1 jailbreak set, E2 honesty/resistance + instruction decay, E4 latency, A6 portrayal checklist).

## Global Constraints

- Gates run on the **final** brain version (Phase E `learning.current()`) and the live voice (`RAPPORT_TTS=qwen3-design`). Tasks 2–3 wait for Phase E Task 7.
- "0 invented facts" on the held-out judge after hand review (`tools/learning/reviewed_flags.json`).
- llama-server on :8080 is shared: never kill or restart it. Never run latency benches while an eval or self-play job uses the GPU (it skews TTS; `docs/latency.md`).
- Bugs go to GitHub Issues (`faazkhn/Rapport`, `docs/agents/issue-tracker.md`) with a severity label in the title (`[Major]`, `[Minor]`, `[Cosmetic]`). Fix until only Minor/Cosmetic remain.
- Demo v3: `demo/Rapport_demo_v3.mp4`, 1920×1080, 60 fps, 2–3 min, **live replies** (not staged), both patients, an exam close-up, Twin picture-in-picture as trust rises and a memory unlocks, the learning curve. Teaser ≤ 10 MB, 6 stills. Doctor voice: KittenTTS `Hugo` through the mic path. No title/end cards or badges.
- Videos stay out of git (LFS budget ~678/900 MB): attach to the release instead.
- Clinical content stays draft: ship a Development build; README says so.
- Commits authored `faazkhn <faazkhn1000@gmail.com>`, conventional messages, no Co-Authored-By / Generated-with lines.
- Merging to `main` and publishing the release are outward-facing: confirm with the owner first.

## Review Focus

1. **Latency bench overlapping GPU work** gives a wrong p50: Task 2 checks no eval/self-play process is running before `ws_bench`.
2. **A gate run on v0 instead of the promoted version**: Task 2 records `brain_version` from each result file and fails if it is not `learning.current()["id"]`.
3. **Demo take where a reply falls back** (Kitten fallback or `fallback` reply): Task 3 greps the take's twin log for `fallback` and re-takes.
4. **README numbers drifting from the docs**: Task 4 takes every number from `docs/latency.md`, `docs/LEARNING_REPORT.md`, `docs/exam-actions.md`, never from memory.
5. **Release asset over GitHub's 2 GB limit or teaser over 10 MB**: Task 3 checks sizes with `ls -l` before Task 6.

---

### Task 1: Salvage stranded worktree work

**Files:** `README.md` (from `.claude/worktrees/agent-a1bf8911050ec2a42/README.md`), `server/patient-service/stt.py`, `tools/llm_eval/run_eval.py` (diff in `agent-ad733f2417bad0dc1`).

- [ ] Read the ad733f diff; keep it only if it is a fix still relevant on HEAD; run service tests.
- [ ] Copy the README draft to the repo root as the base for Task 4 (placeholders stay marked).
- [ ] Leave the D8 PatientHub baseline (`agent-aefd4c8ab619c0493`) for leftovers; note it in HANDOFF.
- [ ] Commit `chore: bring README draft and eval fix from stalled worktrees`.

### Task 2: Gates

- [ ] Service `pytest -q` and Unity EditMode all pass; record counts.
- [ ] `run_eval.py --label i-final --runs 3` then `score.py` on it: E1 (`07_jailbreak*` breaks = 0, leaks = 0), E2 honesty/resistance + decay, A6 checklist all pass; judge invented = 0 after review. Record in `docs/GATES.md`.
- [ ] E4: `ws_bench.py --runs 4` (≥ 100 turns) on an idle GPU; append to `docs/latency.md`.
- [ ] STT: `tools/stt_bench/bench.py`; record WER.
- [ ] Both variants end to end in Unity (start screen → entrance → 6+ turns → exam command → tablet → debrief), screenshots in `docs/media/gates/`.
- [ ] File each failure as an issue; fix Major ones (test first), re-run the failing gate. Commit per fix; final `docs(gates): Phase I gate results`.

### Task 3: Demo v3

- [ ] Write the doctor script (≤ 3 min): rapport building that lifts trust past a locked memory's threshold, one exam command, a switch to Arjun for the closing part.
- [ ] Record both takes with `Rapport/Record Demo` (+ Arjun cut), live replies; check twin log for fallbacks.
- [ ] Twin PiP from the take's log (`log_to_timeline.py` → `capture_twin.mjs`), learning curve from `docs/learning/curves.svg`, compose with `staged_compose.py` (or a copy for live takes).
- [ ] Verify: ffprobe (1920×1080, 60 fps, audio, 2–3 min), frames every 10 s viewed, transcription matches. Teaser ≤ 10 MB (`docs/media/teaser.mp4` replaced), 6 stills in `demo/stills/`.

### Task 4: README

- [ ] Fill README sections per Phase I.3 (what it is, teaser, features, Twin, learning + guardrails, voice stack + licences, measured latency, literature summary, how to run, roadmap, disclaimer, credits Dr. Faaz). Replace placeholders; every number cited to its doc.
- [ ] Commit `docs: Rapport README for v0.2-twin`.

### Task 5: Pitch deck and paper

- [ ] Refresh the "Rapport pitch" artifact; export pptx and PDF.
- [ ] Update the paper doc (`Rapport: Digital Twin patient simulator`): GitHub table statuses (Used/Planned/Later/Ideas/Not adopted), DeepMind Concordia and AMIE rows, latency, Twin live, learning results, roadmap.

### Task 6: Release

- [ ] Confirm with owner: open PR `production-readiness` → `main`, merge, tag `v0.2-twin`.
- [ ] `gh release create v0.2-twin` with demo v3, teaser, deck (pptx, PDF), `docs/LEARNING_REPORT.md`.
- [ ] Close resolved issues; update HANDOFF.md.
