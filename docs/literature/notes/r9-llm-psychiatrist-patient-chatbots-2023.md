# R9 Chen et al.: LLM-empowered Chatbots for Psychiatrist and Patient Simulation: Application and Evaluation

- **Citation:** Chen S, Wu M, Zhu KQ, et al., arXiv 2023. arXiv:2305.13614
- **Link:** https://arxiv.org/abs/2305.13614 · **Open access:** yes (arXiv HTML)
- **Code:** none found · **Code licence:** none
- **Paper licence:** arXiv non-exclusive (not confirmed)
- **Informs:** identity/formulation, behaviour/resistance, evaluation

## Mechanism
Psychiatrist-guided, iterative prompt design of gpt-3.5-turbo doctor and patient chatbots for outpatient depression interviews. Doctor variants ablate empathy and an aspect checklist (D1-D3) against a fine-tuned model (D4); patient variants are basic (P1) vs full prompt with reminders (P2). Tested with real patients and psychiatrists.

## Evidence
14 depression patients and 11 psychiatrists (7 more in objective setting), 1-4 ratings. Patient realism P1 1.93 vs P2 2.21; expression style 1.57 vs 2.21. Best doctor D3 (no checklist): expertise 3.71, diagnosis accuracy 55.56%, symptom precision 92.24%, recall 38.10%. P2 reported more wrong symptoms than P1 (18.38% vs 15.07%).

## Limitations
- Depression only, small sample, own lexicons for automatic metrics.
- Patient bot forgot instructions; stronger style/resistance cues lowered symptom fidelity.
- No code or data release.

## For Rapport
**Verdict:** idea-only. The finding that pushing resistance/style raises realism but degrades factual fidelity supports keeping facts and disclosure locks in code, with the LLM only voicing (Digital Twin memory items and behaviour/resistance fields).
