# PatientAct: Theory-Grounded Mental Health Client Simulation

- **Citation:** Sabour S, Ng T, Chen Y, et al. arXiv:2608.12750 (2026).
- **Link:** https://arxiv.org/abs/2608.12750 · **Open access:** yes (full text HTML; last ~13k characters unread)
- **Code:** https://github.com/Sahandfer/PatientHub · **Code licence:** MIT (PatientHub framework, per the PatientHub paper)
- **Paper licence:** CC BY 4.0
- **Informs:** identity/formulation, memory and disclosure, affect, behaviour/resistance, evaluation

## Mechanism
Profiles built from 5Ps formulation plus intermediate beliefs, triggers, coping, CCRT patterns, validated by rule checker and LLM judge. Static always-on layer plus dynamic memory: each item has disclosure level 1.0-4.0 mapped to seven trust levels, activation tags, and a discomfort flag; items above current trust are blocked. Each turn the model picks one of 7 reactions with low/moderate/high intensity, then one of 8 behaviours; resistance varies by quantity, content, style. Trust starts 2.5, steps of 0.25 or 0.5, clamped 1.0-4.0, gains small and frequent, losses rarer and larger, modulated by attachment style.

## Evidence
40 situations (20 depression, 20 anxiety), 160 conversations of 15 turns with GPT-4o; human raters scored 80. Versus best baseline Patient-psi: resistance quality +0.67, behavioural realism +0.63, disclosure pacing +0.50, coherence +0.39, emotional authenticity +0.32. Profile plausibility 4.43/5; attachment style identified 77.5%. Ablations: removing dynamic memory hurt most; LLM judge (GPT-5.4) disagreed with humans on some dimensions.

## Limitations
- Depression and anxiety only; single session; English; one backbone (GPT-4o).
- Ratings only, no downstream training outcome.
- LLM judge unreliable where humans disagree.

## For Rapport
**Verdict:** adapt. Closely matches the existing Twin design (trust locks, reaction/intensity/behaviour/resistance, clamped trust). Adopt disclosure levels with activation tags, the asymmetric trust step sizes and attachment modulation, and the "pull back after consecutive therapeutic behaviours" rule in code. MIT code reusable with attribution.
