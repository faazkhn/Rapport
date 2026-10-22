# ConsistentMI (PatientHub): Consistent Client Simulation for Motivational Interviewing-based Counseling

- **Citation:** Yang Y, Achananuparp P, Huang H, et al., ACL 2025 (Long), 2025.acl-long.1021. arXiv:2502.02802
- **Link:** https://arxiv.org/abs/2502.02802 · **Open access:** yes (arXiv HTML, first 100k of 153k chars read)
- **Code:** https://github.com/Sahandfer/PatientHub (patienthub/clients/consistentMI.py, PatientHub reimplementation; authors' own repo not found) · **Code licence:** MIT (PatientHub)
- **Paper licence:** CC BY 4.0
- **Informs:** identity/formulation, memory and disclosure, behaviour/resistance, affect

## Mechanism
Simulated MI client with a tracked mental state (motivation, beliefs, plan, receptivity 1-5; transtheoretical stages precontemplation, contemplation, preparation, plus termination). Four modules: state transition from counsellor utterance, action selection (LLM distribution averaged with a data-derived distribution per state/receptivity), information selection (profile details pulled only for actions that need them, limiting over-disclosure), response generation. Behaviours: Deny/Engage/Accept (no profile) and Inform/Blame/Hesitate/Plan (use profile). Derived from AnnoMI; GPT-4 annotated 86 clients' sessions.

## Evidence
258 sessions per method (86 clients x 3). Profile consistency (persona/motivation/beliefs/plan): 70.57/73.37/71.70/68.51 vs best baseline 67.09/55.33/68.60/57.17. Receptivity Spearman 0.58 vs 0.33. Avg receptivity 3.32 vs 3.27 real; action KL divergence 0.06. Experts: 6 clients, 288 consistency scores; realism 3.16 vs real 4.72.

## Limitations
- Prompt sensitivity and error accumulation across multi-step prompting.
- One dataset (AnnoMI, actor sessions), MI only, client side only.
- Realism well below real clients.
- Multiple LLM calls per turn.

## For Rapport
**Verdict:** adapt. Code is MIT via PatientHub, but the multi-call pipeline breaks the one-call budget; take the idea of code-held state transition plus information selection gated by action type to refine trust/disclosure and the resistance field, with a data-derived action prior blended into the single prompt.
