# SimPatient: Scaffolding Empathy: Training Counselors with Simulated Patients and Utterance-level Performance Visualizations

- **Citation:** Steenstra I, Nouraei F, Bickmore TW. CHI '25 (conditionally accepted), 2025. arXiv:2502.18673.
- **Link:** https://arxiv.org/abs/2502.18673 · **Open access:** yes (full text, HTML)
- **Code:** none found · **Code licence:** none
- **Paper licence:** CC BY 4.0
- **Informs:** affect, expression/embodiment, feedback/pedagogy, evaluation

## Mechanism
Multi-agent GPT-4o patient for motivational interviewing (alcohol misuse). A Patient Response Agent produces verbal and nonverbal replies from persona, history and between-session events. A Cognitive Model Agent scores Control, Self-Efficacy, Awareness and Reward (1-10) after each trainee utterance via chain-of-thought. Nonverbal behaviour = baseline animation plus LLM-chosen cues; TTS voice. A dashboard gives MI radar, behaviour-code counts, reflection:question ratio, annotated transcript, and cognitive-factor line graph.

## Evidence
Training study 18 analysed (10 professionals, 8 students), three 10-min sessions. MI self-efficacy 8.08 (SD 0.95) to 8.82 (SD 0.59), F(3,48)=15.56, p<0.001. SUS 88.1. Dashboard utility 8.83/10, patient change realism 7.94/10. Persona fidelity: gender 94%, occupation 72%; age, ethnicity, personality not identified.

## Limitations
- Single group, no control, small n, alcohol only.
- Patients too agreeable; users wanted more resistance/ambivalence.
- Text input only, robotic voice; agent validation used two raters on 20 examples.

## For Rapport
**Verdict:** adapt. The per-turn hidden cognitive-state scores (Control, Self-Efficacy, Awareness, Reward) are a model for extra Twin state variables, and the utterance-level dashboard suits feedback/pedagogy; keep scoring in code, not extra live LLM calls.
