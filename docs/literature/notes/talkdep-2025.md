# TalkDep: Clinically Grounded LLM Personas for Conversation-Centric Depression Screening

- **Citation:** Wang X, Perez A, Parapar J, Crestani F, CIKM 2025, pp. 6554-6558. DOI 10.1145/3746252.3761617; arXiv 2508.04248.
- **Link:** https://arxiv.org/abs/2508.04248 · **Open access:** yes (full text read, 5 pages)
- **Code:** https://github.com/Anxo06/TalkDep · **Code licence:** none (no LICENSE file; GitHub reports no licence), so ideas only
- **Paper licence:** arXiv non-exclusive (ACM copyright notice in the PDF)
- **Informs:** identity/formulation, affect, evaluation

## Mechanism
Three clinical psychologists designed an eight-group persona template: demographics with a fixed BDI-II score, up to four key symptoms, life history and social context ("memory and reflection"), communication style (past-tense and low-future language), behaviour constraints, response goals, environment, and example Q&A. Generation loop with GPT-4o: LLM 1 plays therapist and generates 5 dialogues with the persona (1 overall severity, 4 per major symptom); LLM 2 reads them as session records and predicts severity; the persona is accepted only if |predicted BDI - target BDI| < 5, otherwise the prompt is refined and the loop repeats. Accepted dialogues plus profile become the in-context prompt of the final simulator (LLM 3). Live use is one call per turn.

## Evidence
12 personas, BDI-II 5 to 40 (3 each at minimal, mild, moderate, severe). LLM-judge pairwise severity ranking over 66 persona pairs: Llama3.1-8B 75.81%, Gemma-3-27B 77.27%, Llama3.1-70B 81.67%, DeepSeek-R1-14B 86.36%; errors mostly between adjacent levels, Marco (BDI 38) often ranked below moderate personas. Two certified clinical psychologists (not the designers) interacted with each persona and rated on 1-5: overall mean 3.92; general interaction (humanness, naturalness, fluency) 4.01; depression-oriented (emotional consistency, symptom realism, engagement, cognitive load) 3.84, falling to 3.71 for the severe band. Used as ground truth for the CLEF eRisk 2025 conversational pilot.

## Limitations
- Depression only, 12 personas, two raters, no inter-rater statistic; severity check uses an LLM rather than a clinician (authors say so).
- GPT-4o dependent; open-model personas not tested for generation.
- Adjacent severity levels remain hard to separate; symptom portrayal rated lower than fluency.
- No licence on the repo.

## For Rapport
**Verdict:** idea-only. The accept-if-judge-recovers-the-target loop is a cheap, offline quality gate for new cases: generate sessions, have a judge infer severity (and for addiction, a scale score), keep the case only if it lands within a tolerance. That fits the Digital Twin identity block (a severity target per case) and the evaluation harness; note that the pairwise-judge accuracy (76 to 86%) shows a small judge is only moderately reliable, so keep a clinician check.
