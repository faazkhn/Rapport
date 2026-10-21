# MedAgentSim: Self-Evolving Multi-Agent Simulations for Realistic Clinical Interactions

- **Citation:** Almansoori M, Kumar K, Cholakkal H. MICCAI 2025 (oral). arXiv:2503.22678
- **Link:** https://arxiv.org/abs/2503.22678 · **Open access:** yes (arXiv HTML read)
- **Code:** https://github.com/MAXNORM8650/MedAgentSim · **Code licence:** unknown (GitHub reports no standard licence)
- **Paper licence:** CC BY-NC-SA 4.0
- **Informs:** learning, evaluation

## Mechanism
Open simulated hospital with doctor, patient and measurement agents; the doctor requests exams and imaging. Doctor agents self-improve by storing successful cases (conversation, diagnosis) and reflections on corrected misdiagnoses, retrieving nearest cases by CLIP-embedding KNN as few-shot examples. Failed corrections are discarded. Final diagnosis by multi-doctor CoT and majority vote.

## Evidence
LLaMA 3.3 70B: NEJM 26.7% vs 20.0% baseline (15 core cases); MedQA 70.8% vs 62.3%; MIMIC-IV 79.5% vs 42.7%. Ablation 54.7% to 70.8% (+measurement, +memory, +CoT, +ensemble). Human realism: doctors missed the human agent in 62.5% of 8 judgments.

## Limitations
- Tiny NEJM set; preliminary human study (8 judgments).
- LLM-judged diagnoses; QA datasets converted by GPT-4o.
- Text/inconsistent table numbers; it trains the doctor, not the patient.

## For Rapport
**Verdict:** idea-only. The filtered experience buffer (keep only verified-good cases, retrieve as few-shot) matches the planned experience library of good replies; licence unclear and NC-SA paper, so no code reuse.
