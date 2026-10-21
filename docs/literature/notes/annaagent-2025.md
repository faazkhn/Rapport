# AnnaAgent: Dynamic Evolution Agent System with Multi-Session Memory for Realistic Seeker Simulation

- **Citation:** Wang M, Wang P, Wu L, et al., Findings of ACL 2025, pp. 23221-23235.
- **Link:** https://aclanthology.org/2025.findings-acl.1192/ · **Open access:** yes (full text read)
- **Code:** https://github.com/sci-m-wang/AnnaAgent · **Code licence:** AGPL-3.0 (LICENSE file at HEAD confirmed) so ideas only
- **Paper licence:** CC BY 4.0 (ACL Anthology default, believed)
- **Informs:** affect, cross-session memory, behaviour/resistance, identity/formulation

## Mechanism
The seeker (counselling client) prompt has fixed slots: profile (static), complaint, situation, status, emotion. Two agent groups fill the dynamic slots, and a reminder of current emotion and complaint is injected after every dialogue round. (1) Emotion: a Qwen2.5-7B emotion inferencer, fine-tuned on D4 counselling dialogues (conversation cut at random seeker turns, next-utterance emotion labelled by GPT-4o using GoEmotions categories), predicts the seeker's next-turn emotion from profile plus dialogue so far; an emotion perturber then samples a nearby emotion group (probability weighted by group distance, same group distance 0, neighbouring 1) so mood drifts but small without strong stimuli. (2) Chief complaint: a trained generator makes a staged "complaint chain" before the session (expert-checked); a complaint elicitor decides after each round whether to advance to the next stage (Algorithm 1 in appendix). Tertiary memory: real-time = current conversation in full; short-term = self-report scales (SCL-90, BDI, SAAS) filled by the simulator before each session plus randomly drawn matched life events (CBT triggering events), summarised into status/situation; long-term = previous sessions' conversations and scale records, fetched by an agentic-RAG querier that checks after each round whether the topic touches a previous session. That is several small model calls per turn.

## Evidence
- Backbone Qwen2.5-7B-Instruct; counsellor models PsycoLLM, EmoLLM, SoulChat; datasets D4 (Chinese) and DAIC-WOZ (English); baselines Chen 2023, Duro 2024, Qiu and Lan 2024.
- Anthropomorphism (BERTScore F1 vs real seeker utterances, 10% sampled pairs): D4 AnnaAgent 0.6691 / 0.6649 / 0.6682 (three counsellors), best baseline 0.6866 on PsycoLLM, 0.6539 on SoulChat; DAIC 0.4910 / 0.4694 / 0.4827 vs best baseline 0.4864 (Duro) on PsycoLLM and 0.3901 on EmoLLM.
- Ablation without dynamic evolution (PsycoLLM counsellor): D4 F1 0.6144 vs 0.6691; DAIC 0.4408 vs 0.4910. Without long-term memory, G-Eval (GPT-4o, 1-5) accuracy on questions about previous sessions drops markedly (bar chart only, no numbers in text).
- Backbone swap (GPT-4o-mini, Llama-3.1-8B): relative SD under 10% on D4; Llama on DAIC dropped to 0.37-0.42 F1.
- Personality fidelity by G-Eval on InCharacter-style interview questions: "overall superior" (figure only). No human raters, no n of dialogues stated in text.

## Limitations
- Metrics are text-overlap and LLM-judge based; no clinician or learner evaluation; wins are small and not uniform across counsellors.
- Authors call the emotion model and memory "formally simplified" and "rudimentary".
- Counselling (non-psychiatric) client, Chinese-heavy data; trained on D4 real-counselling data not fully released (privacy).
- Multiple extra model calls per turn and a trained emotion model; AGPL code.

## For Rapport
**Verdict:** adapt (AGPL, so ideas only). Closest published match to the Digital Twin: (a) separate emotion sampled near the previous one by group distance is a code-side analogue of our clamped PAD steps and could add small random drift without an LLM call; (b) a staged chief-complaint chain (what the patient is willing to say at each stage) maps onto trust-locked memory items; (c) tertiary memory (full dialogue, between-session status and events, retrieved past-session facts) is a template for the cross-session memory design, with self-report scales filled before each session as a mood baseline.
