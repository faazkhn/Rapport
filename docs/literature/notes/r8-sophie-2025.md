# SOPHIE: AI Standardized Patient Improves Human Conversations in Advanced Cancer Care

- **Citation:** Haut K, Hasan M, Carroll T, et al., arXiv 2505.02694, 2025.
- **Link:** https://arxiv.org/abs/2505.02694 · **Open access:** yes (full text read)
- **Code:** https://github.com/ROC-HCI/SOPHIE-1.0 (analysis code and 506 ratings only, not the dialogue system) · **Code licence:** MIT
- **Paper licence:** arXiv non-exclusive
- **Informs:** feedback/pedagogy, evaluation, expression/embodiment, affect

## Mechanism
Spoken serious-illness-communication trainer: a 60-year-old woman with newly diagnosed incurable lung cancer on an Unreal Engine 5.1 MetaHuman. STT feeds a hybrid schema-guided dialogue manager: a rule-based classifier plus a BERT classifier tag each clinician utterance as Empathize / Be Explicit / Empower (the 3Es of the MVP framework); the schema picks the conversational state and passes a suggested response to gpt-3.5-turbo, which writes the reply and an emotion tag (neutral plus six basic emotions). The tag selects a mocap facial animation and TTS tone. Expressions are deliberately exaggerated: if the learner misses her emotional state the intensity escalates, and after three misses the conversation ends. The session ends early once a skill has been shown several times, or after 5 minutes of repeated failure. Post-session feedback shows "What you did well" / "Opportunities to improve" with the classified utterances and AI suggestions.

## Evidence
- Randomised trial, 51 health professionals and students (SOPHIE n=26, control n=25 reading module); pre and post conversations with 13 human standardised patients; 102 conversations, 506 ratings (SP plus 4 blinded third-party raters per video, ICC 0.882).
- Overall skill change: SOPHIE +0.15 (d=1.55 within group) vs control +0.06 (d=0.48); between-group on change: Overall p=0.002, d=0.92; Empower p=0.004 d=0.85; Explicit p=0.003 d=0.87; Empathy p=0.002 d=0.59. Scores normalised 0-1.
- Baseline Empower differed (p=0.031); sensitivity subset (20 vs 24) still significant (p=0.036, d=0.65).
- Survey: perceived improvement 4.31 vs 3.83 (p<0.01); feedback quality 4.68/5, usability 4.22/5, avatar realism only 3.40/5. Interviewees called it "creepy/uncanny", noting limited emotional range, abrupt speech, no eye contact, robotic stock phrases.

## Limitations
- One case (a single patient role), one session type, no retention follow-up; control was reading, not an equally engaging alternative.
- Gains measured against human SPs on oncology communication, not psychiatry; dialogue manager and avatar not released.
- Avatar realism rated lowest; the old gpt-3.5 reply model gives stock phrasing.
- Skill classifier trained on pilot data from the same lab.

## For Rapport
**Verdict:** adapt. The strongest lesson: learners valued actionable feedback (4.7/5) far above avatar fidelity (3.4/5), so build the post-OSCE debrief (utterance tagged by skill, "did well / improve") before polishing the body. Also adopt the emotion-tag-to-face/voice mapping with exaggerated, readable cues, and the escalate-if-missed rule as an expression-map option; MIT code is analysis only, so little to reuse directly.
