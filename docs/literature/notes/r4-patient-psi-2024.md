# PATIENT-Psi: Using Large Language Models to Simulate Patients for Training Mental Health Professionals

- **Citation:** Wang R, Milani S, Chiu JC, et al. EMNLP 2024 (Main). arXiv:2405.19660
- **Link:** https://arxiv.org/abs/2405.19660 · **Open access:** yes (full text read)
- **Code:** https://github.com/ruiyiw/patient-psi · **Code licence:** MIT per repo sidebar (README badge says Apache-2.0; verify LICENSE file)
- **Paper licence:** arXiv non-exclusive
- **Informs:** identity/formulation, affect, behaviour/resistance, feedback/pedagogy

## Mechanism
Patients are driven by a CBT cognitive conceptualisation diagram (situation, automatic thought, emotion, behaviour, intermediate/core beliefs; 3 core belief families, 19 core-belief categories, 9 emotions) plus a conversational style (e.g. reserved, tangential). GPT-4 role-plays from the model. PATIENT-Psi-TRAINER has trainees reconstruct the cognitive model through a role-play session and get feedback.

## Evidence
PATIENT-Psi-CM dataset: 106 clinician-written cognitive models. Formative interviews with 12 experts/trainees. User study with 13 trainees and 20 experts: PATIENT-Psi judged more effective than GPT-4 baseline (expert 1.4, trainee 1.1 on a -2..2 scale) and than traditional training (1.7 and 1.6). Experts rated higher fidelity on cognitions (+0.6, p<0.05), emotional states (+1.1) and conversational styles (+1.3).

## Limitations
- GPT-4 only; perceived, not objective, skill gain after two sessions; small sample.
- CBT for depression-type cases, not addiction or psychosis.
- Text only; no embodiment.

## For Rapport
**Verdict:** adapt. Style plus cognitive-model fields give the Digital Twin a structured formulation layer feeding resistance and emotion; the 106-model dataset is idea source, reuse code only after confirming licence.
