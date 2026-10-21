# Eeyore: Realistic Depression Simulation via Supervised and Preference Optimization

- **Citation:** Liu S, Brie B, Li W, et al. Findings of ACL 2025. arXiv:2503.00018
- **Link:** https://arxiv.org/abs/2503.00018 · **Open access:** yes (full text read)
- **Code:** none found at time of check (paper promises open-sourcing) · **Code licence:** unknown
- **Paper licence:** arXiv non-exclusive
- **Informs:** identity/formulation, affect, behaviour/resistance, learning

## Mechanism
8B Llama-3.1 fine-tuned for depressed-client role-play. Mines 3,042 real depression-related conversations, extracts depressive traits to build structured psychological profiles (refined with expert critique), instruction-tunes for profile adherence, then iterative preference optimisation: first model-generated preferences, then a small expert-annotated set. Profile-noise creates negatives.

## Evidence
Human evaluation by 15 experts (six clinical-psychology experts reviewed trait extraction); Eeyore beats GPT-4o with SOTA prompting on linguistic authenticity and profile adherence. I did not extract exact scores.

## Limitations
- 15 experts; no ablation of alignment components.
- Hallucination remains; depression only.
- Fine-tuning does not fit a live single-call local Gemma setup.

## For Rapport
**Verdict:** idea-only. The structured trait profile plus expert preference pairs informs the faculty-principles and rewrite-feedback data, and profile-noise negatives suit the GEPA gate; no usable code.
