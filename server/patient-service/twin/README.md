# Chitta Twin

A visual "digital twin" of the simulated patient's brain state: regions that glow with recall, reaction, choice, speech and arousal; state gauges; a PAD mood dot; the memory ladder (items unlock as trust rises); the 5Ps formulation; and the expression output. **Metaphor, not neuroscience.** Concept preview; the formulation is a draft that faculty have not validated.

Static and offline: `index.html`, `twin.css`, `twin.js`, plus `demo_timeline.js` / `demo_timeline.json` (the staged mdd_01 demo with invented times). There are no CDNs, external fonts or libraries.

## Modes (query string)

| URL | What it does |
|---|---|
| `index.html` | Replays the bundled `demo_timeline.js`. Works from `file://`. |
| `?timeline=<url>` | Replays a timeline JSON (loaded by XHR). Over `file://`, Chrome needs `--allow-file-access-from-files`, or pass a `.js` timeline (`window.TWIN_TIMELINE = {...};`), which loads by script tag. |
| `&render=1` | Hides the controls. Time moves only through `twin.setTime(s)`. Dark theme unless `&theme=light`. |
| `&t=<s>` | Starts paused at `s` seconds. |
| `&theme=light\|dark` | Forces a theme. Otherwise the page follows `prefers-color-scheme` (render mode defaults to dark). |
| `?live=1` | Live mode: the clock is wall time since load (or since the last `init`), and events come in through `twin.push`. |

Replay controls: space to play or pause, ←/→ to jump 5 s, click a turn to jump to it, drag across the strip to scrub.

Layouts: landscape (1920x1080, 1440x900) uses three columns. Tall portrait (aspect below 4:5) uses a single stacked column for the 600x1080 video side panel, rendered at 1200x2160. Portrait hides the Expression and 5Ps cards and shows a one-line expression summary under "Now". Portrait text is at least 26 px at 1200 wide.

## JS API

```js
await twin.ready;          // the timeline is loaded and the first frame is drawn
twin.setTime(42.5);        // draw the exact state at t = 42.5 s (pure function of t; no wall clock)
twin.duration;             // last event time (s)
twin.load(timeline);       // replace the timeline
twin.push(obj);            // live: append an event stamped "now" (see below)
twin.play(); twin.pause();
```

Live feed (for a later WebSocket bridge in the service): call `twin.push(obj)` directly, `window.postMessage({chitta: obj}, "*")`, or `new BroadcastChannel("chitta-twin").postMessage(obj)`. `obj` is one of:
- `{"type": "init", "meta", "memory_items", "formulation", "state_start"}`: resets the clock and the history.
- `{"type": "doctor_start", "doctor": "..."}`, `{"type": "doctor_end"}`, `{"type": "patient_start"}`, `{"type": "patient_end"}`.
- A snapshot: any object without one of those types, with the fields below. `mood` is derived from `state` if it is missing.

`turn` is optional in live mode: each `doctor_start` increments it.

## Timeline format

```jsonc
{
  "meta": {"case_id": "mdd_01", "patient": "Ananya Rao", "age": 24, "variant": "female", "staged": true, "title": "Tired all the time"},
  "memory_items": [{"id": "f_sleep", "label": "Sleep: wakes at 4 a.m.", "trust_min": 10, "gated": false}],
  "formulation": {"status": "Draft — not faculty-validated", "presenting": "...", "predisposing": "...",
                  "precipitating": "...", "perpetuating": "...", "protective": "..."},
  "state_start": {"trust": 30, "distress": 55, "agitation": 15, "engagement": 35},
  "events": [                                     // sorted by t (seconds from video start)
    {"t": 1.0, "type": "doctor_start", "turn": 1, "doctor": "Hello, ..."},
    {"t": 5.0, "type": "doctor_end", "turn": 1},
    {"t": 6.0, "type": "snapshot", "turn": 1,
     "doctor": "Hello, ...", "utterance": "Hmm... my company doctor said ...",
     "state": {"trust": 36, "distress": 55, "agitation": 15, "engagement": 38},   // absolute, after the turn
     "mood": {"p": -0.30, "a": -0.37, "d": -0.20},                                // each -1..1
     "reaction": "wary", "intensity": 2, "behaviour": "guarded_short", "resistance": "quantity",
     "why": "First contact with a stranger ...",
     "recalled": ["f_pc"], "locked_hit": [],
     "cues": [{"id": "gaze_avoid", "intensity": 0.6, "duration_s": 3}],
     "exam_action": null, "emotion": "flat",
     "expression": {"face": "face_flat", "body": ["gaze_avoid"], "gaze": "averted, down and away",
                    "voice": "quiet, low energy, ...", "nonverbal": "sigh"},
     "latency_ms": 1000},
    {"t": 6.0, "type": "patient_start", "turn": 1},
    {"t": 10.3, "type": "patient_end", "turn": 1}
  ]
}
```

Semantics:
- **Memory states.** An item is *locked* while displayed trust < `trust_min`. A `gated` item (`must_be_asked`) shows *must ask* once trust allows it. Any item recalled at or before t is *disclosed*. A recall flashes the item and the hippocampus. A `locked_hit` pulses the item and the hippocampus red.
- **Brain.**
  - Hippocampus: recall.
  - Amygdala: `intensity`.
  - Prefrontal: resistance, plus the "thinking" gap between `doctor_end` and `patient_start`.
  - Broca: patient speaking.
  - Wernicke: doctor speaking.
  - Insula: arousal plus active body cues.
  - Brainstem: agitation plus non-verbal sounds (sigh, breath).
- **Motion.** Glows fade over about 0.6 s and gauges ease over 0.8 s. Every tween is a pure function of t.

## Building a timeline

```bash
python3 tools/demo/staged_timeline.py --fake-times -o server/patient-service/twin/demo_timeline.json   # invented times
python3 tools/demo/staged_timeline.py --times demo/staged/turn_times.json -o demo/staged/timeline.json
```

The turn-times file is `[{"turn": 1, "doctor_start": s, "doctor_end": s, "patient_start": s, "patient_end": s}, ...]` (turns are 1-based, seconds from video start). The script works as follows:
- State applies `state_delta` cumulatively from the case's `state_start`, clamped to 0–100.
- Mood PAD is a fixed formula of state (`mood_pad` in the script).
- `latency_ms = patient_start − doctor_end`.
- Memory labels and the 5Ps live in the script.

## Capturing video

```bash
cd tools/demo && npm install && cd ../..          # once: puppeteer-core into tools/demo/node_modules
node tools/demo/capture_twin.mjs --timeline server/patient-service/twin/demo_timeline.json --start 0 --end 30 -o demo/staged/twin.mp4
node tools/demo/capture_twin.mjs --still 78.5 --width 1920 --height 1080 --theme light -o shot.png
```

Defaults:
- Size: 1200x2160 at deviceScaleFactor 1, downscaled 2x to 600x1080 by ffmpeg (lanczos).
- 30 fps, H.264, yuv420p, CRF 16.
- The script uses the installed `/Applications/Google Chrome.app` in headless mode.

Frames are deterministic: identical PNGs on repeat runs. Speed is about 18–19 frames/s at 1200x2160.
