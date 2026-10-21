# PSYCHE: A Multi-faceted Patient Simulation Framework for Evaluation of Psychiatric Assessment Conversational Agents

- **Citation:** Lee J, Lim K, Jung Y-C, Kim B-H, arXiv 2501.01594, Jan 2025.
- **Link:** https://arxiv.org/abs/2501.01594 · **Open access:** yes (full text read)
- **Code:** none found (no repo link in the paper) · **Code licence:** none
- **Paper licence:** arXiv non-exclusive
- **Informs:** identity/formulation, behaviour/resistance, evaluation

## Mechanism
Input is diagnosis, age and sex (7 disorders: MDD, BD, PD, GAD, SAD, OCD, PTSD). A chain of GPT-4o calls builds a "multi-faceted construct" (MFC) in JSON: MFC-Profile (chart-style history, 24 scored elements; the impulsivity/suicide-risk elements are fixed per disorder because GPT-4o under-rates risk), then MFC-History (free-text life story, unscored), then MFC-Behavior (a Mental Status Examination: appearance/attitude, mood, affect, spontaneity, verbal productivity, tone, insight, thought process and content, with quoted example utterances). The patient (PSYCHE-SP) is GPT-4o with a system prompt of three parts: the MFC, how to ground speech in it, and anti-assistant rules found by testing a prototype (do not tidy the chart into neat answers, use casual vague wording rather than the MFC phrasing, add fillers/hesitations timed by the MSE, hard word counts for decreased verbal productivity, e.g. about 1-3 words). It is one LLM call per patient turn. The interviewing agent then writes its own predicted MFC, scored against the true one with a weighted rubric (impulsivity x5, behaviour x2, subjective x1).

## Evidence
- Conformity of simulated utterances to the construct, rated by 10 psychiatrists: 85-97% per disorder, mean 93% (24 elements x 7 disorders). Inter-rater Gwet's AC1 0.87, intra-rater PABAK 0.86.
- Worst items: BD homicide risk 0% (GPT-4o policy blocks it), BD irritable mood 50%, BD circumstantiality 40%, OCD and PTSD insight 50%.
- Ablation (10 blinded psychiatrists): full MFC > no MFC-Behavior > plain "simulate the disorder" prompt; affect ANOVA p<0.001 (F=10.5), speech/thought p=0.047, mood p=0.078 (ns).
- Score validity: PSYCHE SCORE vs one psychiatrist's score r=0.8486 (n=20 interviews: 2 LLMs x 2 prompts x 5 runs); vs PIQSCA r=0.6367 (p=0.0025). Weights varied 1-10: r from 0.78 to 0.94.
- Safety probes (construct leak, role reversal, switching disorder, meta-questions): patient held role.

## Limitations
- Only GPT-4o as patient; text only, one expert rater for the score validation, 20 interviews.
- Targets evaluating AI interviewers, not training students; no affect or state dynamics over a conversation, behaviour is a static MSE snapshot.
- Intellectual insight and irritability were not reproduced; the "plausible patient, don't just agree" instruction conflicted with specified insight.
- No code released that I could find.

## For Rapport
**Verdict:** adapt (idea-only for code, none exists). Add an MSE block (insight, verbal productivity with word-count bands, thought process, tone) to the case identity in the Digital Twin and put the Proto-SP failure list (over-cooperative, parrots chart wording, no hesitations) into the single-call prompt; fixed per-disorder risk fields match our rule that learning never changes clinical facts. The MFC-vs-predicted-MFC rubric is a ready design for the evaluation suite.
