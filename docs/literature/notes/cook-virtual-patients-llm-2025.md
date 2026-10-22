# Cook 2025: Virtual Patients Using Large Language Models: Scalable, Contextualized Simulation of Clinician-Patient Dialogue With Feedback

- **Citation:** Cook DA, Overgaard J, Pankratz VS, et al. J Med Internet Res 27:e68486, 2025. DOI 10.2196/68486
- **Link:** https://pmc.ncbi.nlm.nih.gov/articles/PMC12008702/ (the list link PMC11605890 is a different paper, Brugge et al., BMC Med Educ 2024) · **Open access:** yes (first 100k chars read)
- **Code:** none found · **Code licence:** none
- **Paper licence:** CC BY 4.0
- **Informs:** identity/formulation, evaluation, feedback/pedagogy

## Mechanism
GPT plays a patient defined by a one-page case description with planted preferences (e.g. cost-sensitive, less testing, lifestyle), then generates personalised feedback on the clinician. Conversations rated by physicians and by GPT as rater on a 1-6 scale.

## Evidence
60 conversations (48 with human clinicians, 12 GPT self-chat); chronic cough and diabetes. Authenticity 4.7 (SD 0.7), user experience 4.9, humanlike 4.6, feedback 4.7. Planted preferences perceived in 42-98% of dialogues (cost case 47/48). GPT rated authenticity 5.2 vs humans 4.7; human ICC 0.17-0.40. Cost about US$0.51 per conversation (GPT-4 Turbo).

## Limitations
- Text only, two topics, investigators as clinicians.
- Poor rater reproducibility; LLM judge inflates its own output.
- Feedback not tested on real learners.

## For Rapport
**Verdict:** idea-only. Shows persona preferences are not reliably expressed (42-98%) and LLM self-judging inflates, so the Digital Twin eval should use a different judge model and check planted traits.
