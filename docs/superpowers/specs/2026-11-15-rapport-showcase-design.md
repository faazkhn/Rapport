# Rapport showcase: website and 4K launch film (design)

Date: 2026-11-15. Owner: Faaz Khan Mohammad.

## 1. Intent

Rapport is a Mac app: a doctor talks out loud to a 3D psychiatry patient who answers in her own voice, does exam requests,
and shows her inner state in the Digital Twin. Nobody can try it from a link. The owner wants it on their portfolio and in
posts on LinkedIn and other platforms, so two things must *show* it:

1. **A showcase website** that people open from the portfolio, built to impress ("mind blowing"): a z-axis zoom, scroll-driven
   animation, full Framer Motion, fully responsive on every device.
2. **A launch film**, 4K (3840x2160) at 60 fps, with the doctor speaking in the owner's own cloned voice, enhanced with the
   `/brag` skill. The owner uploads it to YouTube; the site embeds it (placeholder link until then).

Success: someone who has never heard of Rapport understands in 10 seconds what it is, and leaves believing it is real,
polished work. The owner is happy to share both publicly without edits.

## 2. Goals, non-goals, anti-goals

**Goals**
- A standalone static site, deployable to Netlify, linked from the portfolio.
- Hero: a real 3D camera flight from outside the consult room, through the door, to the patient's face, scrubbed by scroll.
- Further scroll-driven sections in Framer Motion (depth parallax, typed speech, live Digital Twin replay).
- Responsive from 320 px phones to 4K desktop; smooth on a mid-range phone.
- Launch film: about 75-90 s, 3840x2160, 60 fps, YouTube-grade encode; fresh staged Unity take; doctor = owner's cloned voice.
- A YouTube description with the disclosure (below), and a share caption for LinkedIn.

**Non-goals** (not in this round)
- Deploying or buying a domain (the owner deploys; the repo includes a working Netlify config).
- A live (unscripted) take. The owner chose staged for now.
- A vertical/short cut, a second language, analytics, a contact form, a CMS.
- Shipping the 3D character models to the browser.

**Anti-goals** (a failure even if it works)
- Upscaled 1080p passed off as 4K.
- A robotic doctor voice.
- Claims the project can't back up: "clinically validated", "used by hospitals", invented user numbers, or any metric not in
  `docs/GATES_v0.3.md` / `docs/latency.md`. Draft clinical content must not be presented as approved.
- A site that stutters on scroll, blocks on a huge download, or is unreadable on a phone.
- The old names (PsychSim in public copy, Sanvaad, Chitta). The product is **Rapport**; the brain is the **Digital Twin**.
- Motion that ignores `prefers-reduced-motion`.

## 3. Constraints

- **Disclosure (owner decision 2026-11-15):** the film carries **no** on-screen "staged / scripted" note. Disclosure lives in
  the YouTube description, which we write: staged concept walkthrough, patient replies pre-scripted to show planned
  behaviour, doctor voice is the owner's voice cloned with Qwen3-TTS, clinical content is a draft pending faculty review, the
  patient is fictional. The site shows one small caption under the embedded film ("Staged walkthrough · clinical content
  in draft") - builder's proposal, the owner may drop it.
- **Licensing:** Character Creator / Reallusion bodies may appear in rendered footage and stills only, never as meshes or
  textures served to the browser.
- **Private repo:** no code links. The site may list the stack and the four paper drafts by title, without links.
- **Patient names are fictional** (Ananya Rao, 24, case `mdd_01`; Arjun). Keep them.
- **Commits** are authored `faazkhn <faazkhn1000@gmail.com>` with no co-author lines.
- **Large media stays out of git** in the Med repo (LFS budget). The site repo commits only the web-optimised media it serves.
- **Hardware:** one Apple Silicon Mac. Unity renders offline (Recorder paces frames), so 4K60 does not need real-time 4K.

## 4. Approaches considered

| Approach | Trade-off | Decision |
|---|---|---|
| **A. Scroll-scrubbed 4K camera flight + Framer Motion sections + React Digital Twin** | Real 3D depth without shipping models; one Unity render feeds both site and film; the frame sequence needs a careful size budget | **Chosen** |
| B. Real 3D patient in the browser (three.js / R3F) | Most interactive in theory; 50-150 MB characters, Reallusion licence forbids shipping meshes, weak on phones | Rejected |
| C. Motion design over stills and video loops | Simple and light; the z-zoom would be faked with flat images and read as a template | Rejected |

Film: one sensible way. Fresh staged take recorded in Unity at 3840x2160 / 60 fps, then composed in Hyperframes through
`/brag` at 4K60. If Hyperframes cannot render 4K60 natively, render its graphics layer at 4K60 with alpha (or over the
footage as a background track) and composite in ffmpeg.

## 5. What exists and gets reused

| Need | Existing piece |
|---|---|
| Owner's voice clone | `~/Downloads/modern-apartment/Video/cii-final/tts_clone.py` (Qwen3-TTS 1.7B Base 8-bit via mlx-audio; 4 takes per line scored by Whisper transcript match, speaker similarity, pitch) and the reference `voice/reference-faaz.wav`. Copy the logic into `tools/tts_lab/` in Med rather than running from Downloads. |
| Staged conversation | `demo/staged/script.json` (12 turns mdd_01 + 2 Arjun turns; per turn: doctor line, patient line, emotion, voice, cues, brain block, facts, exam action) and the patient WAVs in `demo/staged/audio/` |
| Staged playback | Service staged mode: `RAPPORT_STAGED=$PWD/demo/staged/script.json server/patient-service/run.sh` (`staged.py`); doctor audio goes through the real mic path and VAD |
| Recording | Unity menu `Rapport/Record Staged Demo` in `unity/PsychSim/Assets/Scripts/Editor/DemoRecorder.cs` (Recorder, game view, now 1920x1080 / 60 fps constant) |
| Post | `tools/demo/staged_cut.py`, `staged_timeline.py`, `capture_twin.mjs`, `staged_compose.py` |
| Digital Twin visuals | `server/patient-service/twin/` (`twin.js`, `twin.css`, `twin3d.js`, `demo_timeline.json`), the staged timeline with memory items, trust, PAD mood |
| Facts and numbers | `docs/GATES_v0.3.md`, `docs/latency.md`, `docs/TWIN.md`, `DESIGN.md`, `README.md` |
| Earlier film | `brag-output/` (24 s, 1080p30) - superseded, kept for reference |
| Browser checks | `~/Documents/agent-browser` (Vercel Labs agent-browser; not installed globally) |

## 6. The film

**Pipeline**
1. Doctor lines: render every doctor line in `script.json` with the owner's cloned voice (best of 4 takes), 48 kHz, into
   `demo/staged/doctor_faaz/`. Listen-check the report: any line with transcript match below 0.9 or audibly wrong is re-run.
   The staged script may be tightened for the film (shorter doctor lines, the strongest beats) - builder's call, the clinical
   facts must stay as in `mdd_01`.
2. Unity: give `DemoRecorder` a resolution option and record at 3840x2160, 60 fps, constant, with audio. Doctor audio is fed
   through the mic path as today. Check the UI canvas and subtitles scale correctly at 4K.
3. Post: cut with the existing staged tools, then `/brag` (Hyperframes) for the hook, kinetic titles, Digital Twin overlays
   (rendered at 4K from the twin page), depth transitions, music and the outro. Outro: **Rapport** + a one-line tagline + the
   owner's name (no role line). No staged note on screen. Uses turns 0-7 and 10-11 of `script.json` (not 8-9).
4. Deliver: `demo/showcase/Rapport_launch_4k60.mp4` (H.264 High or HEVC, 3840x2160, 60 fps, about 60-70 Mbps, AAC 48 kHz
   320 kbps, SDR BT.709), `poster.jpg` at 4K, `youtube-description.txt` (with the disclosure), `share-copy.txt` (LinkedIn).

**Story** (the builder refines it in `/brag`'s storyboard step; roughly 75-90 s)
1. Hook (0-5 s): a dark open, her face, one quiet word answered.
2. Reveal: Rapport title over the flight into the room.
3. The interview: the owner's voice asks, she answers, the camera holds on small signs (gaze, slump).
4. The exam: "Can you hold your hands out?" - she does, they shake.
5. Inside her: the Digital Twin - trust climbing, memories unlocking, mood moving.
6. Runs offline on a Mac: the local stack in one beat (speech in, local model, her voice out).
7. Outro.

## 7. The website

**Location and stack:** new repo `~/Documents/rapport-site`. Vite + React + TypeScript, Framer Motion (`motion`), Lenis for
smooth scroll, Tailwind if the design-system pass wants it. Static build to `dist/`, `netlify.toml` included. Design system
generated with `/ui-ux-pro-max` before any page code; the film's palette and type (teal `#11998a` trust accent, deep
`#0b1218` panel) are the starting point, not a constraint.

**Sections** (order may change in the design pass)
1. **Hero - the z-axis zoom.** A sticky full-viewport canvas plays a Unity-rendered frame sequence (door -> room -> her face)
   as you scroll; the title and tagline sit on depth layers that come toward the viewer and dissolve. Ends with her looking up.
2. **The problem.** Why practising psychiatry interviews is hard (standardised patients are scarce and costly; the hard parts
   are rapport, hidden facts, risk). Short, large type.
3. **She talks back.** Scroll-typed exchange from the staged script with waveform motion; the voice loop explained in one
   line.
4. **Inside her mind - the Digital Twin.** A React rebuild of the Twin panel, driven by `demo_timeline.json` and bound to
   scroll: trust rises, memory items unlock, the mood dot moves. The centrepiece interaction.
5. **She shows it.** Exam requests and physical signs: short muted 4K-sourced loops (hands tremor, gaze avoidance).
6. **Built to run offline.** The local stack as layered depth cards (speech-to-text, local LLM, Digital Twin, TTS, Unity).
7. **Measured, not claimed.** A few honest numbers from the gates doc (e.g. 0 jailbreak and portrayal failures across runs,
   244 service tests, latency p50), labelled with what they measure.
8. **The film.** YouTube embed (placeholder `https://www.youtube.com/watch?v=PLACEHOLDER`, one constant), poster from the film,
   click-to-load (no YouTube script until clicked), the small caption.
9. **Footer.** Owner name (no role line), LinkedIn https://www.linkedin.com/in/faazkhn/, the four paper drafts by title.

**Media budget**
- Flight frames rendered at 3840x2160 PNG from Unity (new editor tool: a camera path through the existing room, same
  lighting as the takes), then encoded per breakpoint: desktop about 150 frames at 1920 px wide, mobile about 90 frames at
  960 px, AVIF with WebP fallback. Target: hero first frame visible under 1.5 s on 4G; full desktop sequence under about 12 MB,
  mobile under about 5 MB, loaded progressively (first frames first).
- Section loops: H.264/HEVC MP4 plus WebM, muted, under about 2 MB each, lazy-loaded.
- Lighthouse (mobile) Performance 85+, Accessibility 95+.

**Responsive and accessible**
- Breakpoints checked with agent-browser screenshots at 375x812, 390x844, 768x1024, 1024x768, 1440x900, 1920x1080, 2560x1440.
- `prefers-reduced-motion`: the hero shows the final frame with a fade, scroll-scrub sections become static steps.
- Text contrast WCAG AA, keyboard reachable, alt text on media, no layout shift from media.

## 8. Decided by the owner
- Approach A for the site; film made the one sensible way (section 4).
- Staged footage, no on-screen disclosure in the film; disclosure in the YouTube description.
- Doctor voice: the owner's cloned voice (replaces the 2026-10-20 handoff note "the owner will not record their voice").
- 4K 60 fps; `/brag` used for the film; `/ui-ux-pro-max` used for the site design.
- YouTube placeholder link on the site for now.
- **Suicide-risk beat:** include one short moment (turn 7, "Some nights... it'd be easier") in the film; leave out the plans
  and means questions (turns 8-9). The YouTube description opens with a content note and a helpline line (India: Tele-MANAS
  14416; plus a "find a helpline" link). The site may show the same moment in the typed-exchange section, with the same note.
- **Introduction:** the owner's name, Faaz Khan Mohammad, with no role line; the link is https://www.linkedin.com/in/faazkhn/
  (site footer and the film's outro as text, no URL burned in if it hurts the design).
- **Reply timing:** keep the staged 0.6 s gap in the film. The YouTube description says response timing is tightened for the
  walkthrough. The site's numbers section states measured latency only with a label saying what it measures.

## 9. Left to the builder (calls made, owner may correct)
- Site stack and repo location (section 7); film length about 75-90 s; the small caption under the embed.
- Final storyboard, music, typography and palette (through `/brag` and `/ui-ux-pro-max`).
- Exact section order and copy, within the honesty rules in section 2.
- Tightening the staged script for the film, keeping `mdd_01` facts.
- **4K capture vs the wall-clock mic path:** Recorder at constant 60 fps slows game time when a 4K frame takes longer than
  1/60 s, while the service and VAD run on wall-clock time. First try a short 4K test take through the mic path (the virtual
  mic is already paced by `Time.captureDeltaTime`). If lip sync or turn timing drifts, add a timeline-driven playback mode
  (the staged turns played in game time, no service) and mix all audio in post from the same WAVs. Either way the footage is
  the real renderer and the real scripted turns.
- **`/brag`:** run the full `/brag` (Hyperframes) path, not the `/brag-slim` hand-off, and override its default 15-25 s
  length to the film length here.
- **Arjun** is left out of the film and site; the story is Ananya's.
- **Hero flight start:** if the scene has no corridor outside the door, start the flight from a dark void or from outside the
  window into the room, rather than building a set.
