# AgentClinic: a multimodal agent benchmark to evaluate AI in simulated clinical environments

- **Citation:** Schmidgall S, Ziaei R, Harris C, et al. arXiv 2405.07960 (v5, May 2025), 2024.
- **Link:** https://arxiv.org/abs/2405.07960 · **Open access:** yes (full text read)
- **Code:** https://github.com/SamuelSchmidgall/AgentClinic · **Code licence:** MIT (GitHub repo page shows MIT; raw LICENSE path not retrievable at HEAD/main/master, so confirm before copying code)
- **Paper licence:** arXiv non-exclusive
- **Informs:** evaluation, behaviour/resistance, affect, learning

## Mechanism
Four LLM agents, each given private information from a structured JSON case: doctor (the model under test, up to N=20 patient/measurement turns), patient (symptoms and history only; told to answer in 1-3 sentences and never name the disease), measurement agent (returns exam/test results, "Normal Readings" if not in the data), and moderator (compares the final diagnosis to ground truth). Cases come from MedQA (215), MIMIC-IV, NEJM (120 image cases), MedMCQA specialties including psychiatry (260 over 9 specialties) and 7 languages (749). Bias is injected by adding a line to the patient or doctor system prompt (23-24 cognitive and implicit biases, e.g. "you are uncomfortable with your doctor because of their orientation and do not trust their judgement"). After the consult the patient agent rates confidence, compliance and willingness to return (1-10). Doctor tools include a notebook that persists notes across cases.

## Evidence
- Doctor accuracy on AgentClinic-MedQA (GPT-4 patient): Claude-3.5 62.1%, OpenBioLLM-70B 58.3%, 3 human physicians 54% (SD 28.5), GPT-4 51.6%, GPT-4o 34.2%, Llama 3 70B 19%; MedQA accuracy only weakly predicts it. N=10 turns drops GPT-4 from 52% to 25%.
- Patient model matters: GPT-4 patient 52%, GPT-3.5 48%, Mixtral 46% (more detailed answers help the doctor).
- Bias: GPT-4 loses at most 4 points absolute (avg 1.5), partly because it refused the bias instruction in 25 of 215 gender-bias dialogues; Mixtral drops 31-37% to 29-33%. Patient-side ratings fall much more than accuracy: self-diagnosis patients cut confidence by 4.7 points; implicit biases (education worst) lower all three ratings.
- Notebook tool: Llama 3 up to 92% relative gain; GPT-3.5 fell with all tools (adaptive book retrieval -27.1%). Claude 3.5 peaked at 56.1% with the notebook.
- Clinician realism study: 3 MDs rated 20 dialogues on four axes (doctor, patient, measurement, empathy, 1-10).

## Limitations
- Moderator, patient and measurement are LLMs, so patient ratings are simulated attitudes, not real; measurement agent may hallucinate results.
- Possible MedQA contamination; same-model doctor/patient pairs may favour each other.
- Aligned models resist playing biased or uncooperative patients, so simulated resistance is understated.
- Psychiatry is a few MedMCQA case reports; no affect or non-verbal modelling.

## For Rapport
**Verdict:** adapt (MIT code, confirm LICENSE). Reuse the structure of private-per-agent case JSON (what the patient knows vs what the examiner knows) in the Twin case schema, and the three post-consult patient ratings (confidence, compliance, would return) as cheap trust/rapport read-outs for the Twin view and evaluation suite. Prompt-injected "distrust" traits are the simplest way to script resistance variants for self-play doctors; the "never name the disease" line is a ready disclosure guard.
