# ClientCAST: Towards a Client-Centered Assessment of LLM Therapists by Client Simulation

- **Citation:** Wang J, Xiao Y, Li Y, et al. arXiv preprint, 2024. arXiv:2406.12266
- **Link:** https://arxiv.org/abs/2406.12266 · **Open access:** yes (full text read)
- **Code:** https://github.com/wangjs9/ClientCAST · **Code licence:** unknown (README badge says MIT, but no LICENSE file found)
- **Paper licence:** CC BY 4.0
- **Informs:** evaluation, behaviour/resistance, identity/formulation

## Mechanism
An LLM is given a psychological profile (problems and reasons for visiting, displayed symptoms, apparent traits such as Big Five, emotion fluctuation, unwillingness to express emotion, resistance toward therapist) derived from a real counselling transcript, and talks to an LLM therapist. Afterwards the simulated client fills questionnaires (session outcome, working alliance, self-reported feelings, client evaluation of counsellor). Used to rank therapist LLMs.

## Evidence
Built on two human counselling datasets (High-Low Quality Counseling, AnnoMI); 213 high-quality and 87 low-quality sessions used. Simulated clients (Claude-3 Haiku, GPT-3.5, LLaMA3-70B, Mixtral 8x7B) kept problems, symptoms and tone consistent but reproduced apparent traits less accurately; trait recall/F1 varied by model (e.g. LLaMA3-70B openness 0.89 recall, Mixtral emotion-fluctuation 0.42). Questionnaires distinguished high from low quality sessions. Stronger models simulated more consistently.

## Limitations
- Simulated clients are imperfect and inconsistent, especially on traits.
- Client is an LLM answering questionnaires; no human clients validate the scores.
- Therapist-side counselling, not OSCE/psychiatry interview.

## For Rapport
**Verdict:** idea-only. Licence unclear. Useful as a self-play evaluation template: a profiled simulated client scores the doctor on alliance and feelings, and trait-consistency checks could gate the Digital Twin's resistance/affect profile.
