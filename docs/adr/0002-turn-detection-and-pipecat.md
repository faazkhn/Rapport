# 2. Turn detection: Smart Turn on top of Silero; Pipecat not adopted

Date: 2026-10-21 · Status: accepted

## Context

The doctor's turn ended after a fixed 450–500 ms of silence (Silero VAD). That is too slow for a finished sentence and too fast for a doctor who pauses mid-thought. Phase G's latency target is p50 ≤ 700 ms from end of speech to first patient audio.

## Decision

- **Smart Turn v3** (`pipecat-ai/smart-turn-v3`, BSD-2, ONNX on CPU) is asked once Silero sees 200 ms of silence. If the probability that the doctor finished is ≥ 0.5, the turn ends there. If not, the service keeps listening, and a hard cap ends the turn at 1,200 ms of silence, so a doctor who trails off is never left waiting.
- **Speculative STT.** Parakeet starts on the audio so far at the same 200 ms point. If the doctor starts speaking again, that transcript is discarded and the final one is used.
- Without the ONNX file the service keeps the old rule (the client's `vad_silence_ms`), still with speculative STT.
- **Pipecat (the framework) is not adopted.** The service already has the whole pipeline (VAD, STT, streaming LLM with a JSON grammar, sentence TTS, barge-in, Twin events) in about 500 lines. The parts Pipecat would replace are the ones tuned for this app: a pause that absorbs compute, KV prefill between turns, the guard on streamed JSON, and the Unity wire protocol. Taking the one model Pipecat publishes gets its benefit without the dependency.

## Consequences

- Measured with Smart Turn missing (offline): STT wait after the endpoint went from p50 227 ms to 0 ms (`docs/latency.md`). The Smart Turn gain is not yet measured.
- A stale speculative run still holds the single STT thread, so a doctor who resumes talking waits for it to finish before their final transcript runs (one Parakeet pass, about 0.1–0.3 s).
