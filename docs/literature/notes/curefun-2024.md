# CureFun: Leveraging Large Language Model as Simulated Patients for Clinical Education

- **Citation:** Li Y, Zeng C, Zhong J, et al., arXiv preprint 2024. arXiv:2404.13066.
- **Link:** https://arxiv.org/abs/2404.13066 · **Open access:** yes (full text read)
- **Code:** none found (no repo link in the paper) · **Code licence:** none
- **Paper licence:** arXiv non-exclusive
- **Informs:** memory and disclosure, evaluation, feedback/pedagogy

## Mechanism
Each simulated-patient script is turned into a case graph (BERT NER + relation classification + open attribute extraction; numeric values such as temperature attached as attributes). Per student turn the chatbot runs Extract (link mentioned entities by substring and string proximity), Retrieve (LLM writes a formal graph query for the subgraph), Rewrite (subgraph to natural-language evidence), Generate (reply from evidence, dialogue and input). For questions the script does not cover, a "controlled fictional information" step has the LLM invent a plausible attribute from known facts and common sense, then persists it in the graph so later answers stay consistent. Assessment: the exam checklist is split into "Aspects" (the student must ask about X, weight 0.3) and "Information" (the key fact must be elicited, weight 0.7); each item is scored by a vote of 5 Llama-13B checkpoints. Production backbone Llama-13B; TTS and STT included. Several LLM calls per turn.

## Evidence
8 Chinese cases (pulmonology, endocrinology, gastroenterology). Expert-blind pairwise comparison (GPT-4 judge, Chatbot-Arena style, bootstrap Elo, 1,000 reshuffles) of 5 backbones, with and without the framework: Mixtral-8x7B 1462 to 1511 (+48), Qwen-72B 1524 to 1575 (+51), PaLM 1571 to 1639 (+68), GPT-3.5-Turbo 1404 to 1654 (+250), ERNIE-Bot-4 1781 to 1880 (+99); significant at P<0.05 (one-sided Wilcoxon rank-sum). Response-length distribution unchanged. Automatic scoring vs. one expert on 80 dialogues (8 cases x 10): Spearman 0.65 to 0.95 per case (mean 0.81), Pearson 0.77 to 0.94 (mean 0.85). Six LLMs as doctors (5 repeats x 8 cases) vs 3 non-medical, 3 student, 3 expert humans: overall score ChatGPT 0.51, DISC-MedLLM 0.43, expert humans 0.78, students 0.72; LLM doctors ended consultations in fewer turns (4 to 8) than students (23).

## Limitations
- Judge is GPT-4 (authors note it penalised PaLM's short answers); one human grader for the scoring check.
- Small case set (8), Chinese only, and the persisted fabricated attributes are not audited for clinical harm.
- Case-graph pipeline needs trained NER and relation models per language.
- Results are Elo deltas without absolute human ratings; no code to check.

## For Rapport
**Verdict:** idea-only. Two usable ideas, no code: (1) when the doctor asks something the case file does not cover, let the Twin improvise but write the invented detail into a persisted "improvised facts" list so it stays consistent within and across sessions, flagged as non-clinical and never allowed to override case facts (memory items layer); (2) the Aspects/Information split for scoring (did the student ask, and did they actually elicit the fact) fits the scoring module without changing patient behaviour.
