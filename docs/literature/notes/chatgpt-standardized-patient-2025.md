# ChatGPT as a Standardized Patient: Application of Large Language Models in Medical Training Evaluation, Using ChatGPT as a Standardized Patient: Multimetric Assessment

- **Citation:** Wang C, Li S, Lin N, et al. J Med Internet Res 2025;27:e59435. DOI 10.2196/59435
- **Link:** https://www.jmir.org/2025/1/e59435 · **Open access:** yes (PMC full text read)
- **Code:** none found (datasets on request only) · **Code licence:** none
- **Paper licence:** CC BY 4.0
- **Informs:** evaluation, memory and disclosure, feedback/pedagogy

## Mechanism
GPT-4 plays a standardized patient (inflammatory bowel disease history-taking, Chinese dialogue) from a case record plus role prompt, and also scores the student's inquiry against a rubric. Prompts were revised to avoid jargon, avoid over-eager answers, stay faithful to the record, and deny symptoms not in the record.

## Evidence
Phase 1: 30 runs per inquiry-quality group; mean scores 74.7 (SD 5.44) poor, 82.67 (5.30) medium, 85.00 (3.27) good; poor vs medium/good P<.001, medium vs good P=.16. Phase 2: 300 runs; score-difference percentage fell from 29.83% (original prompt) to 6.06% (revised). Separate script, 60 runs, 4 language combinations: average 3.21%, language effect not significant.

## Limitations
- Single disease and rubric; objective criteria only; Chinese dialogue with English prompts.
- Output tone described as "mechanical" after revision; text has internal numeric inconsistencies.
- Data not public; no psychiatry, no emotion or voice.

## For Rapport
**Verdict:** idea-only. Its prompt rules (answer only what is asked, deny what is not in the record) match the Digital Twin's trust-locked memory items; the repeated-run score-difference check is a cheap regression test for the evaluation harness.
