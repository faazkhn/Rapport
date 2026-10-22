# Beyond the Script (Bodonhelyi-2025): Modeling Challenging Patient Interactions: LLMs for Medical Communication Training

- **Citation:** Bodonhelyi A, Stegemann-Philipps C, Sonanini A, et al., arXiv 2503.22250 (v2 Apr 2025). Listed title "Beyond the Script: Testing LLMs for Authentic Patient Communication Styles in Healthcare".
- **Link:** https://arxiv.org/abs/2503.22250 · **Open access:** yes (full text read)
- **Code:** none found (paper links no repo) · **Code licence:** unknown
- **Paper licence:** arXiv non-exclusive
- **Informs:** behaviour/resistance, affect

## Mechanism
Two GPT-4 (OpenAI chat API) virtual patients, an "accuser" and a "rationalizer" (Satir communication styles), each case coded into an illness script with fields (patient details, concerns, symptoms, history, mood, communication tendencies, typical reactions). Prompt layers: a first assistant message that sets mood; an "author's note" injected as a continuing system message to reinforce style; hidden thoughts and feelings visible only to the LLM. Stubbornness is done with if-else rules in the Communicativeness field with sample sentences: skeptical if the doctor links stress to symptoms, hesitant willingness once feelings are validated and the link explained, flat refusal when the explanation is lacking. One LLM call per turn. They tried and dropped fixed answer pools for "no" replies (repetitive) and asterisk non-verbal cues (repeated "quiet sigh", exaggerated table-slamming).

## Evidence
Psychotherapy professionals at a conference, final n=14 (accuser) and 15 (rationalizer), 15 and 17 recruited. About 15 messages and 16-17 minutes per session. Authenticity of style (5-point): accuser 3.8 +/- 1.0, rationalizer 3.7 +/- 0.8; realism of five rated Q-A pairs 3.7 +/- 0.8 and 3.5 +/- 1.1; would recommend 3.2 +/- 1.1 and 3.5 +/- 1.1. Satir adjective match 56.4% (accuser) and 41.5% (rationalizer). In chat logs, 5 of 14 and 7 of 15 participants suggested psychotherapy and both VPs eventually accepted. Hume AI sentiment (0-9, predominant): accuser 3.1 +/- 0.6, rationalizer 4.0 +/- 0.4. Without the conditional rules, VPs refused therapy even after ten explanations.

## Limitations
- Small, self-selected sample of therapists; some were not native speakers in either language; no student raters.
- Only two styles, both with refusal of therapy written into the case; accuser often misread as congruent or rationalizer.
- No control condition without the stubbornness or author's-note layers, so contributions are not isolated.
- Prompt-only: resistance is not tracked as state, so progress depends on the LLM reading the rules.

## For Rapport
**Verdict:** idea-only. Their key finding is that fully rigid resistance is unrealistic and that explicit conditions for softening (validated feelings, link explained) fix it; this maps to the Twin's resistance field and trust locks, where the conditions should be code (trust thresholds), not prose. Also supports dropping LLM-written non-verbal cues: ours come from the expression map.
