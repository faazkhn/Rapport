# TTS bake-off (Phase G)

Date: 2026-10-21 · M5 Pro 24 GB, llama-server (Gemma 4 E4B) loaded · script: `tools/tts_lab/bakeoff.py`

**Decision rule (fixed before the run):** eligible = licence MIT/Apache/BSD, Parakeet word accuracy ≥ 0.93, time to first audio ≤ 450 ms (streaming where the model supports it), real-time factor ≤ 0.8. Among eligible models the largest emotion separation wins; ties go to the lower TTFA. None eligible → keep KittenTTS.

**Winner: qwen3-tts-1.7b-voicedesign**

| Model | Licence | TTFA ms | RTF | Peak GB | Word acc | Emotion sep | Instructions | Note |
|---|---|---|---|---|---|---|---|---|
| chatterbox-turbo | MIT (weights) / Apache-2.0 (MLX port) | | | | | | | not run: offline and not in the local cache |
| kitten-tts-mini-0.8 | Apache-2.0 | 410 | 0.08 |  | 1.0 | 0.67 | no | no streaming: TTFA = whole first sentence |
| kokoro-82m | Apache-2.0 | | | | | | | not run: offline and not in the local cache |
| qwen3-tts-0.6b-customvoice | Apache-2.0 | | | | | | | not run: offline and not in the local cache |
| qwen3-tts-1.7b-voicedesign | Apache-2.0 | 174 | 0.57 | 8.1 | 1.0 | 3.92 | yes |  |

Skipped: kitten-tts-2 (Stellon Labs Community License: revenue-capped, not MIT/Apache/BSD); kyutai pocket-tts (upstream repo is gated (terms click-through); the ungated mirror is not used).

Emotion separation is a proxy (pitch and loudness distance between a sad and an anxious rendering of the same sentence), not a judgement of how natural the emotion sounds. The owner's blind listening page is `docs/listening/index.html`.

**Run conditions (2026-10-21):** the Mac had no network, so only cached models ran; Kokoro, Qwen3-TTS 0.6B CustomVoice and Chatterbox Turbo are untested, not rejected. Re-run `bakeoff.py` online to complete the table.

**Known risk, voice consistency:** VoiceDesign builds the voice from the text description on every call. Median pitch across the 8 neutral lines spreads 6.7 semitones (KittenTTS 2.1), part content, part speaker drift. The live backend fixes the sampling seed per session to keep one speaker; listen for drift on the listening page.
