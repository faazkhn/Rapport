# EvoPatient: LLMs Can Simulate Standardized Patients via Agent Coevolution

- **Citation:** Du Z, Zheng L, Hu R, et al., ACL 2025. arXiv:2412.11716.
- **Link:** https://arxiv.org/abs/2412.11716 · **Open access:** yes (full text read)
- **Code:** https://github.com/ZJUMAI/EvoPatient · **Code licence:** none found (repo exists; no LICENSE file at HEAD, main or master) so ideas only
- **Paper licence:** arXiv non-exclusive
- **Informs:** learning, memory and disclosure, evaluation

## Mechanism
Built from real medical records (hospital IRB data plus MTSamples and MIMIC II, over 20,000 cases). Patient agent: one of 5,000 generated profiles (background, Big Five openness), RAG over the record. Doctor agents ask questions, recruit other-discipline doctors through a DAG, and use instant plus summarised memory. Coevolution has two stores. (1) Attention library: for each question an attention agent distils "attention requirements" (what to reveal or withhold) from the standardised-patient requirements; if the answer is validated as good, <question, record, answer, attention requirement> is stored. At use time the new question retrieves top-k similar entries (embedding similarity, threshold 0.9) as few-shot demos plus requirements. (2) Trajectories library: validated question-to-next-question chains, retrieved by answer similarity, push doctor agents toward efficient professional questions that train the patient. Training stops when no new item is added for 6 consecutive cases. Inference is one patient call per answer with retrieved context.

## Evidence
- Table 1 (averages; Qwen 2.5 72B for Chinese, GPT-3.5-Turbo for English, temperature 1): EvoPatient ability 0.8597, faithfulness 0.8786, robustness 0.9412, relevance 0.7589; best baseline Few-shot(2) ability 0.7626, robustness 0.8207; CoT 0.6481. Roughly 3,000 questions over 150 cases; baselines significantly lower (p<=0.05).
- Pairwise (GPT-4 and human judges): vs CoT on "cheat" questions (trying to extract the diagnosis), humans preferred EvoPatient 86% (baseline 0.2%); vs Few-shot(2) 51% vs 10%. Training on only 50 cases already gave mostly draws on standard questions and 45% wins on cheat questions.
- Cost per answer: 401 tokens, 6.7 s vs CoT 782 tokens (EvoPatient uses about half the tokens).
- A library seeded with 1,000 real doctor-patient dialogues did worse than the self-evolved one (barely beat CoT baselines).
- Abstract: 200+ cases in 10 hours; over 10% better requirement alignment.

## Limitations
- Metrics are LLM/embedding-based (relevance is a cosine distance); human evaluation covered only pairwise samples, not full dialogues.
- Medical interview of record-based disease cases, not psychiatric affect, trust or resistance; agents "answer like machines" on unfamiliar or cheat questions.
- Doctor agents do not generalise to unseen diseases; libraries grow with cases and need retrieval at run time.
- No licence on the code.

## For Rapport
**Verdict:** adapt (ideas only, no licence). The attention-library entry (question + record + answer + "what to reveal or hold back") is a validated experience-library format for the planned self-learning loop: store only vetted replies, retrieve 1-2 as few-shot at inference to keep the one-call budget. The "cheat question" robustness metric (does the patient leak the diagnosis or too much detail) belongs in the evaluation suite alongside memory trust locks.
