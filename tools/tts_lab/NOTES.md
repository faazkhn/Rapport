# Staged demo voices: TTS notes

Render: `tools/tts_lab/.venv/bin/python tools/tts_lab/render_staged.py [--only female_3 ...]`
Output: `demo/staged/audio/{female,male}_<i>.wav` (24 kHz, mono, PCM16). Per-line results go to `tools/tts_lab/report.json`.

## Model
- Qwen3-TTS-12Hz-1.7B-VoiceDesign, MLX bf16 conversion: https://huggingface.co/mlx-community/Qwen3-TTS-12Hz-1.7B-VoiceDesign-bf16
  (upstream https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign). **Licence: Apache-2.0**, ungated.
- Runtime: mlx-audio 0.6.0 (MIT), https://github.com/Blaizzy/mlx-audio, in an isolated uv venv (Python 3.12).
- The voices come only from text descriptions. No reference audio and no cloning.
- Measurement only (not used to render): mlx-community/Qwen3-TTS-12Hz-1.7B-Base-8bit (Apache-2.0), for its speaker encoder.

## Voice descriptions (also in render_staged.py)
- Ananya (seed base 1234): "A 24-year-old Indian woman from Bengaluru with a soft, natural Indian-English accent. Young, warm but tired voice, mid-low pitch, speaking quietly and slowly, like someone who is depressed and exhausted. Natural and human, not a narrator."
- Arjun (seed base 4321): "A 24-year-old Indian man from Bengaluru with a natural Indian-English accent. Young, low and soft male voice, tired and heavy, speaking quietly and slowly, like someone who is depressed and exhausted. Natural and human, not a narrator."
- Each line's instruct is the description, then "In this line: <voice field>.", then a nonverbal hint when there is one (e.g. "Begin with a small audible sigh."). No SFX files are added.
- Seed per line = base + 1000*index + retry. `mx.random.seed` does not make output bit-identical: a re-render gives a new take of the same voice and style.

## Measurements (M5 Pro 24 GB, the patient service and llama-server running alongside)
- Load: 5.0 s cold, 2.4-2.7 s warm (from the HF cache).
- Non-streaming, the full 14-line render: RTF 0.88 (gen time / audio time, including the first warm-up line).
- Streaming (`stream=True, streaming_interval=0.5`): time to first audio 290-345 ms, RTF 0.55.
- Peak memory: 8.9 GB (MLX peak); process max RSS 4.3 GB.
- Whole run, 14 lines plus the STT check: 113 s.

## Quality checks
- STT: Parakeet (server/patient-service stt.transcribe, resampled 24k->16k). 14/14 lines pass at >= 0.9 word accuracy on the first try.
  The lowest scores are minor: female_7 0.96 (the shaky breath was transcribed as "ugh"), female_10 0.95 ("amma" was heard as "Ama"), male_1 0.91 (an added "Uh").
- Levels: every file peaks at -3.0 dBFS. RMS runs from -17.5 to -24.0 dBFS; female_2 "Okay. Thank you." is the quietest.
- Silence: leading audio is 11-60 ms and trailing audio is at most 120 ms. Pauses inside lines are about 0.7-1.5 s and line up with the script's "...".
- Speaker consistency: the Base speaker-encoder cosine to the centroid is 0.97-0.99 for every line, but a deliberately different woman (American, 40) also scored 0.98. So this metric cannot detect drift. In the first full render, median F0 across Ananya's lines was 188-325 Hz; the highest was the short line female_2, which has since been re-rendered. **Listen for drift.** If one line sounds like a different person, re-render it with `--only`. If drift is widespread, the fallback is to clone from one generated Ananya take with the Base model, which drops the per-line emotion instruct.
