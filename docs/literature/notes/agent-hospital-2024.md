# Agent Hospital: A Simulacrum of Hospital with Evolvable Medical Agents

- **Citation:** Li J, Lai Y, Li W, et al., arXiv 2024 (v3 Jan 2025). arXiv:2405.02957
- **Link:** https://arxiv.org/abs/2405.02957 · **Open access:** yes (full text via arXiv HTML)
- **Code:** none found · **Code licence:** none
- **Paper licence:** CC BY-NC-SA 4.0
- **Informs:** learning, evaluation

## Mechanism
A simulated hospital where patients, nurses and doctors are all LLM agents. Doctor agents "evolve" (MedAgent-Zero) without weight updates: a case base of correctly treated cases retrieved by embedding similarity, plus an experience base of natural-language rules written after wrong answers and kept only if they fix outcomes on new cases. Doctors also turn textbooks into multiple-choice items for the case base.

## Evidence
MedQA accuracy (%), Direct / best baseline (Medprompt) / MedAgent-Zero: GPT-3.5 58.29 / 73.76 / 74.31; GPT-4 78.16 / 89.47 / 89.71; GPT-4o 88.22 / 91.52 / 92.22; o1-preview 95.05 / 95.36 / 96.15. Up to 20,000 simulated patients per department, 200 held-out per department, 21 departments; average examination accuracy 66.14 to 98.76 and diagnosis 76.98 to 95.31.

## Limitations
- Base LLM frozen; only retrieval and rule stores change.
- Gains plateau and can regress (Cardiology dropped at 12k-14k cases), suggesting bad rules get stored.
- Patients are LLM-generated, so biases are inherited; only high-level treatment.

## For Rapport
**Verdict:** adapt. The gated experience base (rule is kept only if it improves outcomes on new cases) maps directly onto the planned experience library / faculty principles: promote a principle only after a replay check. Ideas only (no code, NC licence).
