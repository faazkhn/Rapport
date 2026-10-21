# MedSimAI: Simulation and Formative Feedback Generation to Enhance Deliberate Practice in Medical Education

- **Citation:** Hicke Y, Geathers J, Vu K, et al., LAK 2026 (arXiv 2503.05793 v2, Jan 2026; v1 2025). DOI 10.1145/3785022.3785092.
- **Link:** https://arxiv.org/abs/2503.05793 · **Open access:** yes (full text read)
- **Code:** none found (prompts, templates and analysis on OSF, osf.io/f2dvk; not checked) · **Code licence:** none
- **Paper licence:** CC BY 4.0
- **Informs:** feedback/pedagogy, evaluation

## Mechanism
History-taking AI patient for medical students, co-designed with faculty at three US schools. The patient is GPT-4o from instructor-authored templates (demographics, history, communication style, emotional state, vitals, vocabulary, how much to volunteer) with prompts to avoid jargon and use lay terms; voice uses OpenAI Realtime; sessions up to 30 min. After the encounter a separate assessment pass scores each rubric item independently (28-item Master Interview Rating Scale, 1-5, anchored criteria, quote-grounded justification, JSON output) plus instructor-editable checklists (assessed / not assessed, present / absent / unknown, with excerpts); results take 2-3 minutes. A "Learning Hub" adds goal setting, reflection and progress by Kalamazoo elements.

## Evidence
- Deployment: 1,024 encounters, 410 learners, 3 schools, 30 cases; 59.5% did 2+ cases; mean 2.50 cases; about 38 turns and 18.5 min per case. MIRS overall 3.60, checklist completion 55.2%.
- Institution A, uncontrolled cohort comparison (n=100 vs 100): OSCE history-taking 82.8 to 88.8 (+6.0, d=0.75, p<0.001).
- Institution B, self-selected (88 users vs 91 non-users): no significant gain (history 85.3 vs 84.2, d=0.09; all p>0.3).
- Scoring vs trained human raters, 104 OSCE transcripts, 19 MIRS items: exact 32.5%, off-by-one 64.1%, pass/fail threshold (1-2 vs 3-5) 87.0%.
- Survey (n=19): feedback constructive 4.38/5, actionable 4.46/5; common complaints: glitches, cases simpler than OSCE, low realism. 840 reflections coded: missed items 26.3%, flow 23.0%, ROS technique 22.4%, empathy 18.3%.
- Voice sessions scored slightly lower MIRS than text (beta -0.132, p=0.001). SRL features were barely used.

## Limitations
- Historical-cohort comparison confounded; the one voluntary cohort showed no effect.
- Exact agreement of automated scoring is poor (a third); only usable as formative triage.
- Medical history-taking, not psychiatry; no affect, resistance or non-verbal modelling; no code.
- Voice and session-length friction limited adoption.

## For Rapport
**Verdict:** adapt (ideas only). Copy the post-session assessment design for the Twin's feedback screen: independently scored rubric items with verbatim quote evidence, case checklists the faculty can edit (kept separate from the live brain so scoring never touches clinical facts). Treat 87% threshold vs 32% exact agreement as the honest bar for any automated grading; use faculty-controlled "how much to volunteer" as a case parameter in the memory/disclosure settings.
