# MindVoyager (via PatientHub): no standalone paper found

- **Citation:** Listed in Sabour S, Ng T, Huang M. PatientHub: A Unified Framework for Patient Simulation, arXiv:2602.11684, 2026.
- **Link:** https://arxiv.org/abs/2602.11684 · **Open access:** yes (PatientHub paper, partial read); MindVoyager original paper not found
- **Code:** https://github.com/Sahandfer/PatientHub · **Code licence:** MIT (framework)
- **Paper licence:** unknown
- **Informs:** none

## Mechanism
PatientHub classes MindVoyager as a CBT counselor-training simulator using multi-agent prompting over multi-turn dialogue.

## Evidence
In PatientHub cross-method runs it had the highest per-session API cost among prompted methods (about $0.11 under a cooperative CBT therapist), attributed to extra agent calls.

## Limitations
- Original paper not located; mechanism details unknown.
- Multi-agent design conflicts with a one-call-per-turn live budget.

## For Rapport
**Verdict:** skip. Not found as a standalone paper, and multi-agent per-turn calls exceed the live latency budget.
