# Local models (git-ignored)

Only this README is committed. Everything else here is downloaded by hand from public, ungated Hugging Face repos.

| File | Source | Licence | Used by |
|---|---|---|---|
| `gemma-4-E4B-it-Q4_K_M.gguf` | Gemma 4 E4B GGUF (LLM bake-off winner, `tests/llm-eval/results/`) | Gemma terms | `server/patient-service/run.sh` (llama-server) |
| `gemma-4-E2B-it-Q4_K_M.gguf`, `Qwen3.5-4B-Q4_K_M.gguf`, `Qwen3.5-9B-Q4_K_M.gguf` | LLM bake-off candidates | as published | `tools/llm_eval/bakeoff.sh` |
| `smart-turn-v3.onnx` | [`pipecat-ai/smart-turn-v3`](https://huggingface.co/pipecat-ai/smart-turn-v3): download the CPU ONNX file listed in the repo and rename it | BSD-2-Clause | `stt.SmartTurn` (turn endpointing). Missing = silence-only endpointing, the service still runs. Override the path with `SMART_TURN_ONNX` |

The TTS and STT models (Qwen3-TTS VoiceDesign, KittenTTS, Parakeet) download themselves into the Hugging Face cache on first use.
