# AIPatient: Simulating Patients with EHRs and LLM Powered Agentic Workflow

- **Citation:** Yu H, Zhou J, Li L, et al. (25 authors), arXiv 2409.18924 (v4 Nov 2025), cs.CL. No peer-reviewed venue shown on the page.
- **Link:** https://arxiv.org/abs/2409.18924 · **Open access:** yes (arXiv abstract page read; full PDF not read)
- **Code:** none found · **Code licence:** unknown
- **Paper licence:** arXiv non-exclusive
- **Informs:** identity/formulation, memory and disclosure, evaluation

## Mechanism
Patient simulator built on a knowledge graph of de-identified MIMIC-III ICU records, with retrieval-augmented generation and six task-specific LLM agents (retrieval, rewriting, answer generation and so on) answering history-taking questions grounded in the record.

## Evidence
EHR question-answering accuracy 94.15% with all six agents (lower with fewer); knowledge-base F1 0.89; median Flesch Reading Ease 68.77, Flesch-Kincaid grade 6.4; no significant variance across repeated trials (ANOVA F=0.61 and 0.78, p>0.1). Medical students rated it comparable or better than human simulated patients (n not read).

## Limitations
- Six agents per turn implies several LLM calls, incompatible with live voice.
- Somatic ICU data, not psychiatric; no affect or resistance.
- Authors call trustworthiness an open challenge.

## For Rapport
**Verdict:** idea-only. Grounding answers in a fact store matches the Twin's per-case facts; the useful idea is a repeat-trial consistency check on fact recall for the evaluation harness, not the multi-agent pipeline.
