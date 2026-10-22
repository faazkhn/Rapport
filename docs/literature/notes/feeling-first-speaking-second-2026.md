# Feeling First, Speaking Second: A Dual-Process Cognitive-Affective Architecture for LLM Agents

- **Citation:** Buscaroli N, Tamburini F. Proc. Computational Affective Science (CAS) @ LREC 2026, pp. 74-92.
- **Link:** https://corpora.ficlit.unibo.it/People/Tamburini/Pubs/CAS_LREC2026.pdf · **Open access:** yes (full text read)
- **Code:** none found · **Code licence:** none
- **Paper licence:** unknown (ELRA proceedings)
- **Informs:** affect, behaviour/resistance, memory and disclosure, evaluation

## Mechanism
Local-first (Ollama, Qwen3-4B-Thinking) CoALA-style agent with sequential internal actions: think (interpret utterance, stored in ChromaDB episodic memory), plan (balance hard narrative goals and soft relational goals), Appraisal (System 1, visceral reaction grounded in memory and emotional state), Formulation (System 2, regulated utterance). Adds long-term memory, personality and goal tracking.

## Evidence
Two scenarios (therapy first session, police interrogation), 4 test conversations, 54 judged turns, judges GPT-5 and Gemini 2.5 Pro. Planning 3.89/5 (scenario 1) vs 2.87/5 (scenario 2); affective plausibility 4.78/5; synthesis 4.20 vs 3.50; hard-goal completion 100% (human-checked); Big Five cosine similarity to gold profile 0.96 and 0.91.

## Limitations
- 8 conversation logs total; findings explicitly anecdotal; LLM-as-judge dependence.
- Several sequential LLM calls per turn, too slow for real time (the paper says so).
- Under pressure, planning over-regulates the emotion ("arational bias"), the agent seems too calm.

## For Rapport
**Verdict:** adapt. Confirms the "feel first, speak second" split and warns that strategic suppression can erase affect: keep affect upstream of utterance, clamp how much the utterance can down-regulate the reaction, in the single-call Digital Twin schema. Do not copy the multi-call cycle (latency).
