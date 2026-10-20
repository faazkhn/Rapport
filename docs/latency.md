# Voice latency

**Lag** is the time from when the doctor stops speaking to when the patient's first audio is ready, through the real WebSocket path:
VAD → Parakeet STT → local LLM (streamed JSON) → KittenTTS. It is measured with `tools/latency/ws_bench.py`, which streams synthesised `say` en_IN doctor lines as real-time 32 ms mic frames. The bench never uses the microphone.

Lag does **not** include the deliberate `slowed` pause. That pause is how a depressed patient with psychomotor slowing hesitates (DESIGN §5, 1–3 s from the `slowed` cue). Since 2026-10-20 the pause is counted from the end of the doctor's speech, so it absorbs compute time. The patient starts speaking at `max(pause, compute)` after the doctor stops, not `pause + compute`.

Hardware: Apple M5 Pro, 24 GB, llama.cpp build 10809 (Metal), `-fa on -ngl 99 -np 2`.

## Raw model speed (llama-bench, pp256 / tg64)

| Model (Q4_K_M) | Prompt t/s | Generation t/s |
|---|---|---|
| Gemma 4 E2B | 2,497 | 68.5 |
| Gemma 4 E4B | 1,463 | 38.1 |
| Qwen3.5 4B | 1,569 | 39.0 |
| Qwen3.5 9B | 711 | 22.4 |

## Baseline (2026-10-20, before fixes): Gemma 4 E4B, 52 turns

| Stage | p50 ms | p90 ms |
|---|---|---|
| VAD endpoint | 512 | 512 |
| STT | 173 | 401 |
| LLM first token | 1,099 | 2,007 |
| LLM first sentence | 1,674 | 2,634 |
| TTS first chunk | 425 | 660 |
| **Lag (audio ready)** | **3,046** | **4,100** |
| + `slowed` pause, which was added on top | 1,868 | 1,920 |
| Barge-in stop | 63 | 68 |

So the patient started about 4.9 s after the doctor stopped.

## Fixes

1. **Pause absorbs compute** (`session.py`). The deliberate pause used to be slept *after* the first audio was ready. Saves up to ~1.9 s per turn. `speaking` is now sent when audio actually starts, so the UI no longer shows "Speaking" during the silence.
2. **No-thinking Gemma 4 template** (`gemma4-nothink.jinja`, passed by `run.sh`). Gemma sometimes opened a thought on its own. With the stock template, llama-server holds the JSON grammar until the thought ends, so the reply ran to `max_tokens` with no JSON, and the parse failed or fell back. This hit up to 1 in 4 turns on E2B and also happened on E4B. With the template, 0 of 24 turns failed, and the eval shows 100% schema-valid output.
3. **Bounded schema** (`brain.py`). `revealed_fact_ids` has at most 3 items, `event_cues` at most 2, and deltas are limited to −10..10. This stops lists from growing until the token cap.
4. **Next-turn prefill** (`session.py` `warm`). After every reply the service prefills slot 0 with the next prompt up to the doctor's words. A trust change rewrites the facts block (881 tokens) near the start of the prompt, and Gemma's sliding-window cache cannot reuse anything after it (`--cache-reuse` is not supported), which caused 0.9–1.3 s prompt spikes on about half the turns. That work now happens while the doctor is talking.
5. **Unity VAD silence** 650 → 500 ms (service default 450 ms).

## After fixes (2026-10-20): Gemma 4 E4B, 26 turns, `ws_bench.py --runs 1`

| Stage | p50 ms | p90 ms |
|---|---|---|
| VAD endpoint | 512 | 512 |
| STT | 366 | 444 |
| LLM first token | **224** (was 1,099) | 269 |
| LLM first sentence | 604 | 637 |
| TTS first chunk | 185 | 236 |
| **Lag (audio ready)** | **1,616** (was 3,046) | **1,796** (was 4,100) |
| Extra `slowed` wait after audio was ready | 320 | 453 |

The patient now starts about 1.9 s after the doctor stops, down from about 4.9 s. For mdd_01 that equals the clinically intended hesitation, so compute is hidden. A case without the `slowed` cue would wait the full 1.6 s lag.

**Target p50 ≤ 1.2 s is still missed by ~0.4 s.** What is left: VAD silence (0.5 s; shorter cuts the doctor off mid-sentence), STT 0.37 s, and generating the first sentence (the `emotion` field comes first, then the opening words of the utterance).

### Model choice: Gemma 4 E4B (kept)

E2B is about 1.8× faster to generate (time to first token 242 ms in its bake-off probe). With the template fix it has 0 character breaks and 100% valid JSON on 24 eval conversations. E4B's replies are clearly better on the same gold-standard script: terser, with less "I just feel…" repetition, and it answers "What keeps you going?" with real protective factors where E2B gives a vague line. With the prefill, E4B's time to first token is 224 ms, so the speed gap no longer justifies the quality loss. To switch, run `LLM_GGUF=models/gemma-4-E2B-it-Q4_K_M.gguf server/patient-service/run.sh`.

The E4B eval was stopped after 6 of 24 conversations to save time. E2B results: `tests/llm-eval/results/gemma-4-E2B-it.jsonl`.

### Free cloud fallbacks (not wired in, except Grok)

Only worth using if the local model is too slow on a weaker Mac. All of these send the conversation off the device.

- **Groq** (OpenAI-compatible; around 30 req/min, 1,000 req/day, 200k tokens/day free per model): strict JSON schema on `openai/gpt-oss-20b`, `gpt-oss-120b` and `qwen/qwen3.8-27b`, but **no streaming with structured outputs**. Each reply arrives whole, in about 0.3–0.6 s plus network. It is the best free option, but not a drop-in: the service would need a Groq backend like the Grok one (no llama-server extras, non-streaming replies split into sentences after they arrive). Not implemented.
- **Google Gemini API** (AI Studio key, no card): Flash / Flash-Lite are free within per-project limits shown in AI Studio. Free-tier prompts may be used by Google outside the EEA, UK and Switzerland, so it is not suitable for anything real.
- **Cerebras**: now a card-required trial, not a free tier.
- The existing path, `PATIENT_LLM=grok` (xAI, paid key), already works.
