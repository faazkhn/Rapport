# A "virtual brain" for the patient: what already exists, and what to build on

**Date:** 2026-10-20 · **Status:** research and proposal for review. Nothing in the project has changed yet.

**Short answer:** yes, people have built this, and we don't need to start from scratch. The best base is **PatientHub** (`Sahandfer/PatientHub`, MIT licence). It packages **16 published patient simulators** behind one interface. Its newest one, **PatientAct** (EMNLP 2026), is very close to the brain you're describing. For "improves over time", **EvoPatient** (`ZJUMAI/EvoPatient`, Apache-2.0) has a simple, working learning loop we can adopt. Everything else below is supporting parts.

---

## 1. What "a brain that behaves naturally and improves over time" breaks down into

| Part of the brain | What it does for the patient | Who has built it |
|---|---|---|
| **Identity and formulation** | Who they are, why they're unwell, what keeps them unwell | PSYCHE (MSE-based construct), PatientAct (5Ps clinical formulation, core beliefs, attachment style) |
| **Memory with locks** | What they know and are willing to share, opened gradually by trust | PatientAct (memory items with trust thresholds and "activation tags"), SAPS (disclosure depends on how specific the question is) |
| **Feelings** | A moment-to-moment emotional reaction plus slower mood | PatientAct (7 reactions × intensity), AnnaAgent (28 emotion categories, evolving), affect-kernel / emotion-engine (OCC appraisal → PAD mood) |
| **Behaviour choice** | Cooperate, deflect, minimise, open up, get hostile | PatientAct (8 behaviours + 7 resistance patterns), ConsistentMI (stages-of-change state machine), PATIENT-Ψ (6 conversation styles) |
| **Expression** | Words, voice, face and body | Ours: the cue system, KittenTTS, animation. Voigt et al. 2025 (LLM picks actions that the 3D patient executes) |
| **Memory across visits** | Remembers the doctor and last week's visit | AnnaAgent (multi-session memory), SimPatient (between-session events), Generative Agents (memory stream + reflection) |
| **Learning over time** | Gets more realistic the more it's used and tested | EvoPatient (quality-checked experience library), Roleplay-doh (expert principles), GEPA / DSPy (optimise prompts against our test suite) |

---

## 2. What I found on GitHub (checked 2026-10-20)

### Patient simulators
| Repo | ★ | Last push | Licence | What's useful to us | Can we use the code? |
|---|---|---|---|---|---|
| **[Sahandfer/PatientHub](https://github.com/Sahandfer/PatientHub)** | 22 | 2026-08 | **MIT** | 16 simulators in one interface (PATIENT-Ψ, PSYCHE, Roleplay-doh, SimPatient, Eeyore, AnnaAgent, ClientCAST, PatientAct, Patient-Zero, ConsistentMI, AdaptiveVP, SAPS, TalkDep, CARS, MindVoyager, DEProfile). Profile generators (including PSYCHE), an LLM-judge evaluator, multi-session orchestration. Works with **any OpenAI-compatible endpoint**, so it can use our local `llama-server`. | **Yes**: the base layer |
| **PatientAct** (inside PatientHub; [paper](https://arxiv.org/abs/2608.12750)) | — | 2026 | MIT | **The closest thing to a patient brain.** Per turn: find relevant memories → trust-gate them → choose a reaction (understood, hopeful, gained clarity, challenged, scared, misunderstood, none) and its intensity → choose a behaviour → if resisting, choose how (minimal talk, irrelevant talk, superficial, intellectualising, hostility, defensiveness, compliance without engagement) → speak → update trust. Reported to significantly beat baselines on resistance quality and realism. | **Yes**: adapt it |
| [ZJUMAI/EvoPatient](https://github.com/ZJUMAI/EvoPatient) | 25 | 2026-05 | **Apache-2.0** | **The learning loop:** each patient answer is checked against requirements (stay vague, no medical jargon, answer only from the case); passing answers are stored with an embedding and reused as worked examples for similar future questions. Also a "vagueness" module that blurs records into patient-like recall. | **Yes**: copy the pattern |
| [ruiyiw/patient-psi](https://github.com/ruiyiw/patient-psi) | 116 | 2026-02 | MIT | 106 expert-made CBT cognitive models; 6 conversation styles | Yes (also inside PatientHub) |
| [SamuelSchmidgall/AgentClinic](https://github.com/SamuelSchmidgall/AgentClinic) | 366 | 2026-10 | MIT | Patient agents with injected **cognitive and implicit biases**; a benchmark harness | Ideas and the test harness |
| [sci-m-wang/AnnaAgent](https://github.com/sci-m-wang/AnnaAgent) | 95 | 2026-10 | **AGPL-3.0** | Emotions that evolve over time, multi-session memory, complaint stages | **Ideas only**: AGPL would force us to open-source PsychSim if we embed it. PatientHub reimplements it under MIT. |
| [MAXNORM8650/MedAgentSim](https://github.com/MAXNORM8650/MedAgentSim) | 184 | 2026-10 | **CC BY-NC-SA** | Self-evolving doctor/patient/measurement agents | **Ideas only**: non-commercial licence |
| [IanSteenstra/SimPatient](https://github.com/IanSteenstra/SimPatient) | 7 | 2025-02 | none stated | Addiction internal states (control, self-efficacy, awareness, reward) | Ideas only (also inside PatientHub) |
| [LibertFan/AI_Hospital](https://github.com/LibertFan/AI_Hospital), [sotopia-lab/sotopia](https://github.com/sotopia-lab/sotopia) | 198 / 338 | 2024 / 2026 | MIT | Multi-agent clinical and social evaluation | Evaluation ideas |

### General "agent brain" parts
| Repo | ★ | Licence | Use for PsychSim |
|---|---|---|---|
| [joonspk-research/generative_agents](https://github.com/joonspk-research/generative_agents) | 22k | Apache-2.0 | The classic memory stream (rank memories by recency, importance and relevance) plus "reflection". The pattern for memory across visits. |
| [google-deepmind/concordia](https://github.com/google-deepmind/concordia) | 1.8k | Apache-2.0 | A component-based agent library with a "game master". Useful later for a second character in the room (a parent, a partner). Not needed now. |
| [HumanoidAgents/HumanoidAgents](https://github.com/HumanoidAgents/HumanoidAgents) | 327 | Apache-2.0 | Basic needs, emotion, relationship closeness. Pattern only. |
| [gepa-ai/gepa](https://github.com/gepa-ai/gepa) · [stanfordnlp/dspy](https://github.com/stanfordnlp/dspy) | 7k / 39k | MIT | **Offline self-improvement:** automatically rewrite the patient's prompts to score better on *our* test suite (invented facts, resistance quality, portrayal checklist). |
| [letta-ai/letta](https://github.com/letta-ai/letta) · [mem0ai/mem0](https://github.com/mem0ai/mem0) · [getzep/graphiti](https://github.com/getzep/graphiti) | 25k / 68k / 32k | Apache-2.0 | Full memory platforms. **Overkill for now**: each adds a server. Revisit if memory across visits grows complex. |
| [undreamai/LLMUnity](https://github.com/undreamai/LLMUnity) | 1.7k | Apache-2.0 | llama.cpp running **inside Unity**, with JSON-grammar output and retrieval, on macOS, iOS and Android. Keep in mind for a standalone build later (VR is parked). |
| [pioneerjeff-labs/emotion-engine](https://github.com/pioneerjeff-labs/emotion-engine) · affect-kernel (PyPI) | 26 / — | MIT / Apache | OCC appraisal → PAD mood. Small and young; the affect-kernel GitHub repo returned 404. **Copy the idea, not the code.** |

### ⚠️ Name clash
**[usc-psychsim/psychsim](https://github.com/usc-psychsim/psychsim)** is an established academic framework from USC called **PsychSim**: social simulation with decision-theoretic agents and theory of mind, MIT licence, cited for about 20 years. Before we publish or pitch, decide whether to keep our name or qualify it (for example "PsychSim OSCE"). It isn't a legal problem I can assess, just a findability and confusion risk.

---

## 3. Proposed PsychSim brain: built from these parts, tuned for live voice

PatientAct makes **about 6 LLM calls per turn**. That would break our 1.2-second voice target on a local model. So we keep its *ideas* and restructure them into a **fast path** (what you hear) and a **slow path** (thinking that happens while the patient is talking). This "feel first, then speak" split also matches a 2026 dual-process proposal, *Feeling First, Speaking Second* (LREC 2026).

```
Doctor speaks
   │
   ▼  FAST PATH (blocks the voice; one LLM call)
 ① Recall (no LLM, about 10 ms): embed the doctor's words → match memory items by
    activation tags and similarity → apply the trust gate.
    Locked items that match send only a "discomfort" signal, never their content.
 ② One structured LLM call, fields in this order ("feel first, speak second"):
      reaction · intensity · behaviour · resistance_pattern · emotion · utterance · …
    Short labels come first (about 15 tokens), then the utterance streams straight to TTS.
 ③ Expression: reaction → face, behaviour/resistance → body cues and voice speed
   │
   ▼  SLOW PATH (runs in parallel or just after; never delays the voice)
 ④ Trust and state update: a categorical step (−0.5 … +0.5, as in PatientAct), plus
    our rule-based nudges (empathy +, judgment −), clamped by code
 ⑤ Intent tagging for scoring
 ⑥ Mood drift (slow PAD-style mood that colours the next turns)
 ⑦ Episode memory written for this visit (for follow-ups)
```

**How the brain's labels drive the 3D patient:**
| Brain label | Face | Body and voice |
|---|---|---|
| reaction `scared` (high) | `face_anxious` | gaze_avoid ↑, fidget ↑, speech faster and shorter |
| reaction `misunderstood` | `face_sad` / frown | turns away (`guarded`), longer pause |
| reaction `understood` / `hopeful` | softer face | looks up, more open posture, longer answers |
| resistance `minimal_talk` | `face_flat` | slumped, 1–3 word replies |
| resistance `hostility` | anger | `restless`, louder TTS, may stand (agitation) |
| resistance `defensiveness` | — | crossed arms (`base_sit_guarded`), head shake |
| behaviour `affective_exploration` | `face_sad` | tearful ↑, `cue_wipe_tears` |

**Case file changes** (fold into the schema that the plan already extends):
- `formulation`: the 5Ps (predisposing, precipitating, perpetuating, protective, presenting), plus `core_belief` and `attachment_style`, as in PatientAct.
- `facts` → **`memory_items`**: `content`, `activation_tags`, `trust_min` (PatientAct's disclosure level), `generates_discomfort`, `kind` (symptom / history / trigger / formative memory).
- Optional per case type: `stage_of_change` (ConsistentMI, for substance cases) and SimPatient's 4 addiction states.

---

## 4. "Improves with time": four mechanisms, safest first

| # | Mechanism | Where it comes from | What it changes | Who approves |
|---|---|---|---|---|
| L1 | **Experience library.** Each case keeps a store of *good* patient answers. On a similar future question, the top 2–3 are added as examples. It grows with every session. | EvoPatient | Style and realism of wording only | An answer enters only if it passes the automatic checks (no invented facts, no jargon, rules followed) **and** faculty mark it 👍 in tuning mode |
| L2 | **Faculty principles.** Kudos, critique or rewrite on a reply → a written rule stored in the case | Roleplay-doh | How the patient behaves in that case | Faculty, directly |
| L3 | **Nightly prompt optimisation.** GEPA/DSPy rewrites the shared prompt templates to score better on the tester's suite | GEPA / DSPy | Prompt templates (versioned) | Automatic, but a new version only goes live if it beats the current one on **every** safety test |
| L4 | **Fine-tune the local model** (LoRA via mlx-lm) on approved transcripts | Eeyore (fine-tuning + preference optimisation) | Model weights | Later stage, faculty sign-off, a full re-run of the tests |

**Guardrails (non-negotiable):**
- **Learning never changes clinical facts**, the answer key or scoring. It only changes *how* the patient says things.
- Every brain change is **versioned** (`brain_version` in each SessionLog) and can be rolled back.
- **Nothing is learned from a learner's session without consent.** A learner's words never become patient facts.
- The tester's evaluation suite is the gate: a new version must not regress on invented facts, jailbreaks or portrayal.

---

## 5. Suggested order

1. **Stage 1 (current run), small additions:**
   - Use PatientAct's taxonomies (reactions, behaviours, resistance patterns) in our single structured call.
   - Use `memory_items` with activation tags and trust thresholds.
   - Map the brain labels to cues.
   - Record `brain_version`.
   - Install PatientHub as a **dev dependency for testing only**: run its PSYCHE, PATIENT-Ψ and PatientAct simulators on the same case as a comparison baseline, and use its evaluator.
2. **Stage 2:**
   - L1 experience library and L2 faculty tuning mode.
   - Slow-path mood drift.
   - ConsistentMI stages of change for addiction cases.
3. **Stage 3:**
   - L3 nightly prompt optimisation with the regression gate.
   - Memory across visits (Generative Agents-style ranking) for follow-up visits.
4. **Later:** L4 fine-tuning, and Concordia if we need a second character in the room.

## 6. Open points for you
1. Keep the name **PsychSim** despite the USC project, or rename or qualify it?
2. Should faculty approval be required before an answer enters the experience library (L1)? I recommend yes.
3. Should learner sessions be allowed to feed learning at all, with consent? Or only faculty and tester sessions?

## Sources
- PatientHub: https://github.com/Sahandfer/PatientHub · paper https://arxiv.org/abs/2602.11684
- PatientAct: https://arxiv.org/abs/2608.12750
- EvoPatient: https://github.com/ZJUMAI/EvoPatient · https://aclanthology.org/2025.acl-long.846/
- PATIENT-Ψ: https://github.com/ruiyiw/patient-psi · AgentClinic: https://github.com/SamuelSchmidgall/AgentClinic
- AnnaAgent: https://github.com/sci-m-wang/AnnaAgent · MedAgentSim: https://github.com/MAXNORM8650/MedAgentSim
- Generative Agents: https://github.com/joonspk-research/generative_agents · Concordia: https://github.com/google-deepmind/concordia
- GEPA: https://github.com/gepa-ai/gepa · DSPy: https://github.com/stanfordnlp/dspy
- LLMUnity: https://github.com/undreamai/LLMUnity · emotion-engine: https://github.com/pioneerjeff-labs/emotion-engine · affect-kernel: https://libraries.io/pypi/affect-kernel
- Agethos: https://pypi.org/project/agethos/ · *Feeling First, Speaking Second* (LREC 2026 CAS): https://corpora.ficlit.unibo.it/People/Tamburini/Pubs/CAS_LREC2026.pdf
- PsychSim (USC, name clash): https://github.com/usc-psychsim/psychsim
