# Vignette populations: Simulating Diverse Patient Populations Using Patient Vignettes and Large Language Models

- **Citation:** Denecke K, Reichenpfader D. CL4Health @ LREC-COLING 2024, pp. 20-25.
- **Link:** https://aclanthology.org/2024.cl4health-1.3.pdf · **Open access:** yes (full text read)
- **Code:** Zenodo doi:10.5281/zenodo.10889465 · **Code licence:** unknown
- **Paper licence:** CC BY-NC 4.0
- **Informs:** identity/formulation, memory and disclosure

## Mechanism
From six sources they derive 16 vignette dimensions: primary (symptoms, history, medication, triggers, psychosocial, family, occupation) and secondary (personality, communication style, health literacy, race/location, sex/gender, emotion, language proficiency, digital literacy, socioeconomic status). A GPT-4 role prompt is filled with the vignette and asked an 11-question anamnesis; two ablations remove secondary info or all but current symptoms.

## Evidence
Single vignette, 11 questions, rated by the two authors. Compliance, coherence, correctness 100% in all three variants; containment (answer stated in vignette) 64% (7/11) baseline, 45% (5/11) ablation 1, 9% (1/11) ablation 2; clarification questions 0%. Mean answer length 53, 41 and 78 words. Cost about USD 3.58.

## Limitations
- One vignette, two raters, no inter-rater statistics.
- Under-specified vignettes make GPT-4 invent facts (ten of eleven answers in ablation 2), which is dangerous for fixed-fact cases.
- Not psychiatry-specific.

## For Rapport
**Verdict:** idea-only. The 16-dimension checklist is a good schema audit for Digital Twin case identity; the invention result is evidence for keeping facts in code and having a "not in record" fallback.
