# Patient-Zero: Scaling Synthetic Patient Agents to Real-World Distributions without Real Patient Data

- **Citation:** Lai Y., Wang Z., Ma W., Liu Y., arXiv 2025. arXiv:2509.11078
- **Link:** https://arxiv.org/abs/2509.11078 · **Open access:** yes (full text read)
- **Code:** none found; the paper promises GitHub and Hugging Face release, no URL given (PatientHub wraps it) · **Code licence:** unknown
- **Paper licence:** CC BY 4.0
- **Informs:** identity/formulation, memory and disclosure

## Mechanism
Two parts. (1) Medically-Aligned Hierarchical Synthesis: from a disease concept in a knowledge base, four stages (disease outline, then baseline attributes B, symptoms S, examination results E) with stratified attribute permutation; every stage is LLM-verified and regenerated if it fails. (2) Dual-Track Cognitive Memory: the record is split into atomic facts (semantic memory, static) plus an episodic log of the dialogue; a behavioural persona (Reserved, Verbose, Upset) is injected. Each turn the patient LLM drafts a reply; an NLI-Verifier LLM checks it against every fact, labelling entail / contradict / neutral with priority C > E > N, and also checks persona adherence. Contradiction or persona violation: reject and regenerate with corrective instruction (cost: at least 2 LLM calls per turn, more per fact check). Entail: emit unchanged. Neutral: extract new atomic facts and add them to episodic memory (monotonic expansion).

## Evidence
60,000 synthetic records, 6 specialties (including Psychiatry), 98 diseases. Interaction fidelity with Doctor-R1 as adversarial doctor: Patient-Zero logical consistency 100.00, factual recall 33.27, persona alignment 83.70, stylistic stability 75.50, hallucination rate 1.82 (lower is better), inducibility resistance 97.22. Ablation without the dual-track memory: 81.36 / 7.88 / 61.10 / 46.61 / 10.45 / 69.17. Baselines: EvoPatient 87.49 consistency, hallucination 5.01; AI Hospital 97.95, 6.67; MediQ 81.83, 8.46; Patient-Psi 78.75, 2.00. Downstream: Qwen3-8B fine-tuned on the data MedQA 61.00 to 85.00, MMLU 69.50 to 83.00 (real data 83.50 and 85.50). Human test: 2 senior physicians, blind discrimination pass rate 57.1% for Patient-Zero vs 50.0% for real records (chance 50%); "indistinguishable" rests on n=2 raters.

## Limitations
- Human evaluation is two physicians; metrics are LLM-scored with LLM verification.
- Idealisation bias: records are cleaner than real ones; authors flag this.
- Medical history-taking, not psychiatric affect or resistance; persona is a label checked for style only.
- Verifier loop multiplies latency and local-model cost; not designed for live voice.

## For Rapport
**Verdict:** idea-only. The "compliance bias" finding (patients inventing symptoms to please the doctor, inducibility resistance 69 to 97) is the failure the Twin's memory items and locks must prevent. Adopt the mechanism in code: split case facts into atomic items and check the utterance against them with rules or a small NLI model after the single call (no second LLM call live); run the full LLM verifier only in the nightly evaluation. Unlicensed code: ideas only.
