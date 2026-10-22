# Literature insights for the Digital Twin

From the 83 notes in `notes/` (matrix: `matrix.md`). Each insight names the Digital Twin component it changes and its status. **Built** means it is in the code today. **Phase E** means the self-learning work in progress on its own branch. **Later** means planned but not scheduled. **Rejected** means considered and not taken, with the reason.

Read in full: 37 papers. Abstract only: 35. Not found or paywalled: 11 (listed in the matrix). Verdicts that rest on an abstract are marked "(abstract)".

## What the field agrees on

1. **Keep facts, state and locks in code, and let the model voice them.** Several papers report the same failure: the model invents symptoms or details to please the interviewer, and does so more often when it is pushed hard on style or when the case is thin. Containment fell from 64% to 9% as vignette detail was removed (`vignette-patient-populations-2024`). Stronger style cues lowered symptom fidelity (`r9-llm-psychiatrist-patient-chatbots-2023`). An NLI verifier cut hallucination from 10.5 to 1.8 (`r-patient-zero-2025`). The Twin already works this way (trust-locked recall, a guard, code-clamped state). Keep it.
2. **One live call per turn. Everything else goes offline.** Every multi-agent design is too slow for live voice: PatientAct (about 6 calls per turn), AIPatient (6 agents), Concordia, Generative Agents and the AMIE critic chain. The usable pattern is to do the expensive work offline (critique, reflection, optimisation) and feed it back into the single prompt.
3. **Patients are too agreeable unless resistance is designed in.** SimPatient users asked for more resistance (`r6-simpatient-mi-2025`). PSYCHE lists "over-cooperative" and "no hesitation" as failure modes (`r3-psyche-2025`). Fully rigid resistance read as unrealistic too (`beyond-the-script-2025`). Resistance needs explicit conditions under which it softens.
4. **Learners value the debrief more than the avatar.** In SOPHIE's RCT (n=51), feedback was rated 4.7/5 and the avatar 3.4/5 (`r8-sophie-2025`). MedSimAI (`r7-medsimai-2025`) and the Brügge RCT (`r11-llm-patient-feedback-rct-2024`) show rubric-based feedback improves scores, but the gains are modest and not always replicated. Of the student-facing work, the debrief is what pays off most.
5. **LLM judges are weak evidence on their own.** The best LLM judge identified roles correctly 68.8% of the time against 90.8% for humans (`personaeval-2025`). Position consistency was only 65% (`mt-bench-judge-2023`), and a judge rates its own model higher (`cook-virtual-patients-llm-2025`). Any gate needs code checks, order-swapped pairwise judging with a judge model other than Gemma, and faculty spot checks.

## Insights by component

| # | Insight | Component | Status | Sources |
|---|---|---|---|---|
| 1 | Reaction, behaviour and resistance labels; trust-gated memory items with activation tags; clamped trust steps; 5Ps formulation, core belief, attachment style | identity, memory, affect, behaviour | **Built** (`twin.py`, `data/brain/behaviours.json`) | `r-patientact-2026` |
| 2 | Affect is decided before the words ("feel first, speak second"); a reply should not down-regulate the felt reaction too far | affect, fast path | **Built** in part: `behaviour` and `emotion` come before the utterance, `reaction` after it, for latency (ADR 0001). Later: cap how far the utterance may soften a high-intensity reaction. | `feeling-first-speaking-second-2026` |
| 3 | Locked memories give a discomfort signal, never their content; declining to answer is a measurable behaviour | memory and disclosure | **Built** (`twin.recall`, `enforce_discomfort`) | `r-patientact-2026`, `usability-simulated-patient-2021` |
| 4 | Keep what the examiner finds on examination separate from what the patient can say | memory, exam | **Built** in part: the exam router plus `exam_note`; findings are not yet a separate source. Later. | `ai-hospital-2024`, `agentclinic-2024` |
| 5 | A Mental Status Exam block in the case (insight, verbal-productivity bands, thought process), plus the PSYCHE failure modes listed in the prompt | identity | **Later** (kickoff D1; not in `mdd_01` yet) | `r3-psyche-2025` |
| 6 | Cognitive model (situation, thought, emotion, behaviour, core belief) and a conversational style per case | identity, behaviour | **Later**. `core_belief` is built; style is not yet a per-case bias | `r4-patient-psi-2024` |
| 7 | The doctor's last move (empathy, premature empathy, invalidation, limit-setting) maps through a table to a clamped resistance and trust step | affect, behaviour | **Later**. Today trust moves via the model's delta plus the reaction step. A rubric table in code would make it auditable | `adaptive-vp-2025`, `beyond-the-script-2025` |
| 8 | Resistance softens under explicit conditions (feelings validated, link explained), implemented as trust thresholds in code | behaviour/resistance | **Built** in part (trust locks); softening rules **Later** | `beyond-the-script-2025` |
| 9 | Pre-classify the doctor's turn (specific, vague, unanswerable, off-topic, physical request) in code to set what may be disclosed | memory and disclosure | **Built** in part (intent tagging; exam router for physical requests). Vague-question "fishing" handling **Later** | `saps-2024` |
| 10 | Stage what the patient raises over a session (complaint chain); sample the next mood near the current one | affect, cross-session | **Built** in part (PAD mood drifts toward state at rate 0.3); complaint chain **Later**. AnnaAgent is AGPL, so ideas only | `annaagent-2025` |
| 11 | Persist details the patient improvises in a flagged list so they stay consistent; never let them override case facts | memory | **Later** | `curefun-2024` |
| 12 | Check each utterance against atomic case facts after the call, in code; run the LLM verifier only in nightly evaluation | guard, evaluation | **Built** in part (guard drops locked and unknown fact ids, banned words). Contradiction check **Later** | `r-patient-zero-2025` |
| 13 | Substance cases: per-turn control, self-efficacy, awareness and reward, plus stage of change | affect | **Later** (no substance case yet) | `r6-simpatient-mi-2025`, `r-consistent-mi-2025` |
| 14 | Experience library of validated tuples (question, record, answer, what to reveal or hold back); retrieve 1–3 as examples inside the single call | learning L1 | **Phase E** | `evopatient-2024`, `medagentsim-2025`, `dspy-2023` |
| 15 | Keep a learned rule or example only if a replay shows it improves outcomes | learning L1/L2 | **Phase E** (quality gate before storage) | `agent-hospital-2024` |
| 16 | Faculty thumbs-up, thumbs-down or rewrite become general "when X, do Y" principles; yes/no adherence checks run offline. In Roleplay-doh this cut awkward replies from 15% to 2.5% | learning L2 | **Phase E** | `r5-roleplay-doh-2024` |
| 17 | GEPA reflective prompt evolution on the single patient prompt, with feedback text built from code checks and promotion only on a held-out win | learning L3 | **Phase E** (GEPA is MIT; the only "adopt" verdict) | `gepa-2025`, `dspy-2023` |
| 18 | Self-play with simulated doctors (biased, rushed, adversarial), with a critic that knows the ground truth, offline | learning, evaluation | **Phase E** | `agentclinic-2024`, `amie-2024`, `pingpong-2024` |
| 19 | Pairwise judging with order swapped; a tie unless both orders agree; reference = case file; judge model other than the generator; spot checks by faculty | evaluation | **Phase E** gate; kickoff Checkpoint 2 is the owner's blind A/B | `mt-bench-judge-2023`, `personaeval-2025`, `cook-virtual-patients-llm-2025` |
| 20 | Accept a case only if a judge reading generated sessions recovers its severity target within tolerance | evaluation | **Later** | `talkdep-2025` |
| 21 | Post-session ratings from the patient's side (felt heard, alliance, would return) as cheap rapport read-outs | evaluation, feedback | **Later** | `clientcast-2024`, `agentclinic-2024` |
| 22 | Debrief: independently scored rubric items with verbatim quote evidence, faculty-editable checklists, scored apart from the live brain | feedback/pedagogy | **Built** in part (Unity scoring and debrief; no quote evidence). Quote evidence **Later** | `r7-medsimai-2025`, `r11-llm-patient-feedback-rct-2024`, `r8-sophie-2025` |
| 23 | Cross-session memory as time-stamped cards, built offline by importance-gated reflection that never overwrites case facts | cross-session memory | **Later** (single-visit only today) | `generative-agents-2023`, `deprofile-2026` |
| 24 | Readable, slightly exaggerated emotion cues from a fixed map; cues the LLM writes freely come out repetitive | expression | **Built** (`expression_map.json`) | `r8-sophie-2025`, `beyond-the-script-2025` |
| 25 | Psychiatrists, not students, judge fidelity; keep ambivalence in the formulation; vary demographics across cases | evaluation, content | **Later** (faculty sign-off is an open owner item) | `r1-psychiatry-simulation-review-2021`, `r10-embodied-vp-review-2022` |
| 26 | Fine-tuning on real or expert-preferred dialogues (Eeyore) | learning L4 | **Rejected for now**: out of scope (kickoff), and there is no consented real data. Filed as a later issue in Phase E | `eeyore-2025` |
| 27 | Multi-agent per-turn pipelines (PatientAct as published, AIPatient, MedAgentSim, MindVoyager) | architecture | **Rejected**: too many calls per turn for live voice; ideas only | see note 2 above |
| 28 | Reuse AGPL or non-commercial code (AnnaAgent, MedAgentSim, DEProfile) | licence | **Rejected**: ideas only under the licence rules | `annaagent-2025`, `medagentsim-2025`, `deprofile-2026` |

## Gaps in this review

- 11 papers could not be reached (publisher 403 or not found). They are listed as "not found" and none of them shaped a decision.
- 35 verdicts rest on abstracts. Every paper cited for a Built or Phase E row was read in full, with one exception: `usability-simulated-patient-2021` (row 3) was read as an abstract only. PatientHub's CARS and MindVoyager simulators have no standalone paper, so their notes come from the PatientHub paper.
- Licences marked "unknown" in the matrix are not cleared for reuse. Check the repo's LICENSE before copying any code.
