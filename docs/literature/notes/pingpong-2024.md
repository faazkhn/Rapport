# PingPong: A Benchmark for Role-Playing Language Models with User Emulation and Multi-Model Evaluation

- **Citation:** Gusev I. arXiv:2409.06820 (2024; v2 2025)
- **Link:** https://arxiv.org/abs/2409.06820 · **Open access:** yes (arXiv HTML read)
- **Code:** https://github.com/ilyagusev/ping_pong_bench · **Code licence:** Apache-2.0 (per GitHub API)
- **Paper licence:** CC BY 4.0
- **Informs:** evaluation, identity/formulation

## Mechanism
A player model role-plays a character, an interrogator model emulates a user in a situation, and an ensemble of judge models scores multi-turn dialogues for character consistency, entertainment, and fluency. Averaging judges tracks humans better than any single judge.

## Evidence
40+ models, English and Russian, 64 conversations per model (8 characters x 8 situations). Spearman vs humans: English avg of Claude 3.5 Sonnet and GPT-4o 0.604 (single 0.517-0.554); Russian 0.612. Top English: Claude 3.5 Sonnet 4.65.

## Limitations
- 64 conversations per model.
- Annotator agreement low (Krippendorff alpha 0.25 English, 0.34 Russian).
- Simple criteria; LLM judge bias.

## For Rapport
**Verdict:** adapt. Two-model judge ensemble plus an LLM interrogator is a reusable pattern (Apache-2.0) for the self-play doctor and persona-consistency eval; keep local-model cost in mind.
