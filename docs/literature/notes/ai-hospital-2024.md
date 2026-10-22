# AI Hospital: Benchmarking Large Language Models in a Multi-agent Medical Interaction Simulator

- **Citation:** Fan Z, Tang J, Chen W, et al., arXiv 2402.09742, 2024 (rev. June 2024).
- **Link:** https://arxiv.org/abs/2402.09742 · **Open access:** yes (full text read)
- **Code:** https://github.com/LibertFan/AI_Hospital · **Code licence:** MIT (LICENSE file at HEAD confirmed)
- **Paper licence:** arXiv non-exclusive
- **Informs:** evaluation, memory and disclosure, behaviour/resistance

## Mechanism
Three NPC agents plus the player doctor (the LLM under test). One medical record per case is split by who may know it: subjective information (symptoms, history, habits) goes only to the Patient (GPT-3.5), objective information (lab, imaging) only to the Examiner (GPT-3.5), and the Chief Physician (GPT-4) holds everything and later scores the doctor; the doctor gets nothing. Patient prompt: cooperate and answer truthfully but do not volunteer everything; colloquial language, omit details or show subjective bias; curious about the diagnosis; plus a GPT-4-imagined personality and emotional-response backstory per record. Dialogue is addressed by prefix symbols to the Patient or Examiner. After the chat the doctor writes a 5-part report (symptoms, exams, diagnosis, rationale, treatment), which the Chief Physician scores 1-4 per part against the record (multi-view evaluation), plus entity-overlap F1 on ICD-linked diagnoses. A collaboration mode has several doctors debate through the Chief Physician as dispute resolver.

## Evidence
- Benchmark: 506 Chinese medical records (surgery 180, internal medicine 153, OB-GYN 94, ...); physician check of 50 records (10 departments x 5) found 94% fundamentally correct.
- Simulator behaviour (human check of 50 dialogues per doctor model): patient relevance 100%, honesty 98.1-99.7%; examiner accuracy 98.2-100%; doctor report consistency 98-100%.
- Interaction results (normalised 0-100): GPT-4 symptoms 69.03, exams 25.10, diagnosis 29.36, rationale 30.76, treatment 26.93; versus GPT-4 given the ground-truth symptoms and exams in one step: diagnosis 58.89, treatment 53.16. So information gathering, not reasoning, is the bottleneck. Medical-tuned HuatuoGPT-II 34B: diagnosis 25.20, symptoms 68.43.
- Collaboration: 2 doctors with dispute resolution diagnosis 38.06 vs 35.56 without; 3 doctors 39.60; symptom coverage 80.26 for 3 doctors.

## Limitations
- Chinese records only; GPT-4 acts as judge and as the creator of patient backstories; text only.
- Patient agent is mainly a truthful record reader; no affect, trust or resistance; treatment scoring ignores valid alternatives.
- Simulator reliability checked on only 50 dialogues per model by manual labels.
- Heavy reliance on OpenAI APIs.

## For Rapport
**Verdict:** adapt (MIT). The information partition (patient sees only subjective facts, examiner only objective findings, judge sees all) is exactly the right shape for the Digital Twin: keep exam-command results in a separate source from patient-speakable memory, and use the Chief-Physician-style report-vs-record scoring in the evaluation suite. Code may be reused with attribution; the Patient prompt behaviours (cooperate but do not volunteer, colloquial, omit details) can seed the disclosure style without changing clinical facts.
