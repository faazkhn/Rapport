# PatientHub: A Unified Framework for Patient Simulation

- **Citation:** Sabour S, Ng T, Huang M. EMNLP 2026 Demo. arXiv:2602.11684.
- **Link:** https://arxiv.org/abs/2602.11684 · **Open access:** yes (abstract plus HTML sections on CARS)
- **Code:** https://github.com/Sahandfer/PatientHub · **Code licence:** MIT
- **Paper licence:** CC BY 4.0
- **Informs:** evaluation, behaviour/resistance, cross-session memory

## Mechanism
Modular framework with 16 patient simulators, a graph-based orchestrator for multi-turn and multi-session runs, a configurable LLM-as-judge evaluator (turn and session rubrics), and a CLI to generate profiles, simulate and evaluate.

## Evidence
16 simulators compared under a shared protocol; a new variant prototyped with minimal code. CARS ends sessions itself, averaging 5.1 of 15 turns. No other numbers read.

## Limitations
- Demo paper; comparison is shallow.
- Counselling (CBT) focus, not psychiatric OSCE.

## For Rapport
**Verdict:** adapt. MIT code: reuse the rubric-based turn/session LLM-judge design for the evaluation harness around the Digital Twin, with attribution.
