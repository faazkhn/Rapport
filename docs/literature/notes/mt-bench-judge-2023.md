# MT-Bench / Chatbot Arena: Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena

- **Citation:** Zheng L, Chiang W-L, Sheng Y, et al., NeurIPS 2023 Datasets and Benchmarks. arXiv 2306.05685
- **Link:** https://arxiv.org/abs/2306.05685 · **Open access:** yes (full text read)
- **Code:** https://github.com/lm-sys/FastChat (llm_judge) · **Code licence:** Apache-2.0 (LICENSE file checked)
- **Paper licence:** arXiv non-exclusive
- **Informs:** evaluation, learning

## Mechanism
Three judge set-ups: pairwise comparison (A / B / tie), single-answer grading (score 1-10), and reference-guided grading (the judge first solves the problem, or is given a reference). Mitigations tested for judge flaws: swap answer order and count only consistent verdicts (otherwise tie), a few-shot judge, chain-of-thought judge, reference-guided judge, and a "rename" prompt (assistants named differently). MT-Bench is 80 two-turn questions over 8 categories (writing, roleplay, reasoning, math, coding, extraction, STEM, humanities). One LLM call per judgement.

## Evidence
Position bias (80 pairs-with-swap, consistency): Claude-v1 23.8%, GPT-3.5 46.2%, GPT-4 65.0% (75% of Claude's inconsistent verdicts favoured the first answer). Few-shot judge raised GPT-4 consistency 65.0% to 77.5% but made calls 4x more expensive. "Repetitive list" verbosity attack: failure 91.3% for Claude-v1 and GPT-3.5, 8.7% for GPT-4 (23 answers). Math grading failures on 10 questions x 2 orders: default 14/20, chain-of-thought 6/20, reference-guided 3/20. Self-enhancement: GPT-4 favoured itself by +10% win rate, Claude-v1 by +25%, GPT-3.5 not; authors say data too small to conclude. Agreement on MT-Bench (58 expert labelers, about 3K votes): GPT-4 vs. human 66% (S1, ties included; random 33%) and 85% (S2, no ties; random 50%), against human-human 81% in S2; humans judged GPT-4's disagreeing verdicts reasonable in 75% of cases and changed their vote in 34%. Chatbot Arena: 3K votes sampled from 30K, 2,114 unique voters.

## Limitations
- General chat and instruction following; no persona fidelity, clinical or emotional realism.
- Agreement drops once ties are included (about 66%); the headline 80%+ is non-tie.
- Position, verbosity and self-enhancement biases remain, and weak judges (Claude-v1, GPT-3.5) are much worse than GPT-4.
- The judge is a strong API model; a small local judge will be less reliable (not tested).

## For Rapport
**Verdict:** adapt. Apache-2.0 judge prompts and the swap-and-require-consistency rule are directly usable as the pairwise gate in the nightly GEPA/DSPy loop and in self-play evaluation of the Digital Twin's replies. Use reference-guided judging (the case facts as the reference) for factual consistency, add code checks, and do not let Gemma judge its own replies alone.
