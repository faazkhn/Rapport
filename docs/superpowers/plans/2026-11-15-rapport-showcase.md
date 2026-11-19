# Rapport showcase (website + 4K launch film) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A 4K60 launch film with the owner's cloned voice as the doctor, and a standalone scroll-driven showcase site.

**Architecture:** The film is a fresh staged Unity take (a 10-turn showcase script; doctor lines rendered with Qwen3-TTS
voice cloning and served by the staged service's `/tts`), recorded at 3840x2160/60 and composed with `/brag` (Hyperframes).
The site (`~/Documents/rapport-site`, Vite + React + TS + Framer Motion + Lenis) is built around a scroll-scrubbed Unity
camera flight and a React Digital Twin driven by the staged timeline.

**Tech Stack:** Unity 6000.6.2f1 + Recorder, Python 3 (FastAPI service, mlx-audio Qwen3-TTS 1.7B Base, mlx-whisper),
ffmpeg, Node 26, Vite, React 19, TypeScript, `motion` (Framer Motion), Lenis, Vitest, Hyperframes, agent-browser.

**Spec:** `docs/superpowers/specs/2026-11-15-rapport-showcase-design.md`

## Global Constraints

- Product name **Rapport**, brain **Digital Twin**; never PsychSim (public copy), Sanvaad or Chitta.
- No claim beyond `docs/GATES_v0.3.md` / `docs/latency.md`; never "clinically validated" or "proven"; clinical content is a draft.
- Film: no on-screen staged/scripted note; turns 0-7 and 10-11 of `demo/staged/script.json` only (no plans/means questions).
- Film: 3840x2160, 60 fps, H.264 High or HEVC ~60-70 Mbps, AAC 48 kHz 320 kbps, BT.709. Never upscaled 1080p.
- Owner: "Faaz Khan Mohammad", no role line, https://www.linkedin.com/in/faazkhn/.
- YouTube placeholder: `https://www.youtube.com/watch?v=PLACEHOLDER`, one constant.
- No character meshes/textures served to the browser; footage and stills only.
- Commits authored `faazkhn <faazkhn1000@gmail.com>`, no co-author lines. Large media not committed in Med.
- Site honours `prefers-reduced-motion`; WCAG AA contrast; works 320 px to 4K.

## Review Focus

1. Fast scroll on a slow connection before all flight frames load: show the nearest loaded frame, never a blank canvas (Task 10).
2. `prefers-reduced-motion: reduce`: hero shows the final frame statically, scroll scenes become static steps (Task 10, 12).
3. Phone rotation / resize mid-scroll: canvas re-fits with cover cropping, never stretched (Task 10).
4. YouTube link still the placeholder: the film card shows the poster and "Premieres soon", never a broken iframe (Task 12).
5. Browser without AVIF (older Safari): WebP frames load instead (Task 10).

---

### Task 1: Owner-voice doctor lines

**Files:** Create `tools/tts_lab/render_doctor_clone.py`, `demo/staged/showcase/script.json` (not committed: `demo/` media rule; script is small and IS committed).

- [ ] Build `demo/staged/showcase/script.json`: same shape as `demo/staged/script.json`, `turns` = source turns [0..7, 10, 11]
  re-indexed 0-9, `arjun_turns: []`, `tools` copied, `note` updated. Copy patient WAVs `female_<src>.wav` to
  `demo/staged/showcase/audio/female_<new>.wav`.
- [ ] `render_doctor_clone.py`: port the take loop from `~/Downloads/modern-apartment/Video/cii-final/tts_clone.py`
  (model `mlx-community/Qwen3-TTS-12Hz-1.7B-Base-8bit`, ref `voice/reference-faaz.wav` + its transcript, 4+ takes, whisper
  `mlx-community/whisper-large-v3-turbo` match, speaker similarity, pitch sanity) over `turns[i].doctor`; write
  `demo/staged/showcase/doctor/female_<i>.wav` (48 kHz mono) and `report.json`; exit 1 if any `text_match < 0.9`.
- [ ] Run with `~/Downloads/TunnelVerse-CII/.venv/bin/python tools/tts_lab/render_doctor_clone.py`. Expected: 10 WAVs, exit 0.
- [ ] Commit script + tool.

### Task 2: Staged `/tts` serves the owner-voice lines

**Files:** Modify `server/patient-service/staged.py`, `server/patient-service/app.py:265`; Test `server/patient-service/tests/test_api.py`.

**Interfaces:** Produces `staged.doctor_audio(text: str, out_sr: int) -> np.ndarray | None` (float32 mono, the WAV at
`<script dir>/doctor/female_<i>.wav` whose turn's `doctor` equals `text` after whitespace strip; None otherwise).

- [ ] Test `test_tts_serves_staged_doctor_wav`: tmp script with one turn `doctor: "Hello?"`, a 0.5 s 48 kHz WAV in
  `doctor/female_0.wav`; monkeypatch `staged.PATH`; POST `/tts {"text":"Hello?","voice":<any VOICES>}` with lifespan skipped
  (model None) -> 200, `audio/wav`, duration 0.5 s ± 0.02 at `SAMPLE_RATE`. Unknown text -> 503 (model not loaded) as today.
- [ ] Run, see it fail. Implement (check staged before the model check). Run `cd server/patient-service && .venv/bin/python -m pytest -q`. Expected all pass.
- [ ] Commit.

### Task 3: 4K showcase recording

**Files:** Modify `unity/PsychSim/Assets/Scripts/Editor/DemoRecorder.cs`.

- [ ] Add menu `Rapport/Record Showcase 4K` (staged, script `demo/staged/showcase/script.json`, female, 3840x2160) and
  `Rapport/Record Showcase 4K test (2 turns)`; `StartRecording(name, w, h)`; staged path uses the given script when set.
  Output `demo/raw/Rapport_showcase_4k.mp4`.
- [ ] Start service: `RAPPORT_STAGED=$PWD/demo/staged/showcase/script.json server/patient-service/run.sh`; run the test take.
  Check with ffprobe (3840x2160, 60/1) and by eye: lip sync, subtitles, the doctor voice is the owner's, gaps ~0.6 s.
- [ ] If timing drifts: fallback per spec (timeline-driven playback, audio in post). Then the full take.
- [ ] Commit.

### Task 4: Hero flight frames

**Files:** Create `unity/PsychSim/Assets/Scripts/Editor/HeroFlight.cs`.

- [ ] Menu `Rapport/Render Hero Flight`: open `Assets/Scenes/Encounter.unity`, Ananya seated at `PatientAnchor` (same setup
  as `LightingStills`), a camera path dark/outside -> room -> face close-up (eased), 180 frames, 3840x2160, 8x MSAA
  offscreen, PNGs to `demo/showcase/flight/f_%04d.png`. Path chosen after inspecting the scene.
- [ ] Render; check first, middle, last frames by eye.

### Task 5: Film composition and delivery

- [ ] Cut the take (`tools/demo/staged_cut.py`), Twin capture at 4K: `capture_twin.mjs --scale 2` over the showcase timeline.
- [ ] Run `/brag` (full Hyperframes path), storyboard per spec §6, ~75-90 s, 3840x2160 60 fps; verify Hyperframes render
  options first; fallback: graphics rendered separately and composited in ffmpeg.
- [ ] Final encode to `demo/showcase/Rapport_launch_4k60.mp4`; `poster.jpg` 4K; `youtube-description.txt` (content note,
  Tele-MANAS 14416, staged walkthrough, scripted replies, timing tightened, cloned voice, draft content, fictional patient);
  `share-copy.txt`. Verify with ffprobe.

### Task 6: agent-browser runnable

- [ ] `cd ~/Documents/agent-browser && pnpm install && npm run build:native` (or `npm i -g agent-browser`); `agent-browser install`.
  Expected: `agent-browser --version` prints 0.43.0.

### Task 7: Site scaffold + design system

**Files:** `~/Documents/rapport-site/` (new git repo): Vite React TS, `motion`, `lenis`, `vitest`, `netlify.toml`
(`npm run build`, `dist`), `design/DESIGN-SYSTEM.md` from `/ui-ux-pro-max`, `src/styles/tokens.css`.

- [ ] `npm run build` and `npx vitest run` both exit 0. Commit.

### Task 8: Content module + honesty test

**Files:** `src/content.ts`, `src/content.test.ts`.

**Interfaces:** Produces `YOUTUBE_URL`, `LINKEDIN_URL`, `OWNER`, `content` (all section copy, stats with `label` and `what`).

- [ ] Test: serialised `content` contains none of `/PsychSim|Sanvaad|Chitta|clinically validated|proven|FDA/i`; every stat has a
  non-empty `what`; `YOUTUBE_URL === "https://www.youtube.com/watch?v=PLACEHOLDER"`.

### Task 9: Digital Twin data

**Files:** `scripts/build-twin-data.mjs`, `src/twin/data.json`, `src/twin/timeline.ts`, `src/twin/timeline.test.ts`.

**Interfaces:** `stateAt(t: number): TwinFrame` where `TwinFrame = { trust: number; mood: {p:number;a:number;d:number};
unlocked: string[]; speaker: "doctor"|"patient"|null; line: string; reaction: string | null }`, `duration: number`.

- [ ] Build script drops events of source turns 9-10 (1-based in the timeline: the plans and means turns) and rebases times.
- [ ] Tests: `stateAt(0).trust` = `state_start.trust`; trust non-decreasing over the kept turns; no `line` matches
  `/pesticide|plan.*end your life/i`; `stateAt(duration).unlocked` includes `f_pc`.

### Task 10: Hero flight

**Files:** `scripts/encode-frames.sh`, `public/flight/{d,m}/`, `src/hero/sequence.ts` (+ test), `src/hero/HeroFlight.tsx`.

**Interfaces:** `frameIndex(progress, count)`, `loadOrder(count): number[]` (coarse-to-fine), `nearestLoaded(i, loaded: boolean[])`,
`coverRect(sw, sh, dw, dh) -> {x,y,w,h}`, `pickFormat(supportsAvif: boolean) -> "avif"|"webp"`.

- [ ] Encode: desktop 150 frames 1920w, mobile 90 frames 960w, AVIF + WebP; totals printed; desktop AVIF < 12 MB, mobile < 5 MB.
- [ ] Tests pin Review Focus 1, 3, 5. Reduced motion renders the last frame only (Review Focus 2).

### Task 11: Sections

Problem, She talks back (typed exchange), She shows it (muted loops cut from the 4K take), Built to run offline (depth cards),
Measured not claimed, Footer. Each from `content`.

### Task 12: Twin section + film section

- [ ] `TwinPanel` bound to scroll via `stateAt`; reduced motion = stepped. `FilmCard`: poster, click-to-load iframe; when
  `YOUTUBE_URL` contains `PLACEHOLDER`, shows "Premieres soon" and no iframe (test).

### Task 13: Verify

- [ ] agent-browser screenshots at 375x812, 390x844, 768x1024, 1024x768, 1440x900, 1920x1080, 2560x1440; no horizontal scroll.
- [ ] Lighthouse mobile: Performance >= 85, Accessibility >= 95. `npm run build` clean. Commit.
