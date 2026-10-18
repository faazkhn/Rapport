# What the literature tells us, and what to change

**Status:** proposal for review. Nothing in `DESIGN.md`, the briefs or `KICKOFF_PROMPT.md` changes until you give the green flag. Edit or strike anything below.
**Date:** 2026-10-18 · **VR is parked:** nothing here depends on it.

## Sources actually read
| # | Source | Read |
|---|---|---|
| R1 | Piot et al. 2021, *Simulation Training in Psychiatry for Medical Education: A Review*, Front. Psychiatry (`references/fpsyt-12-658967.pdf`) | Full |
| R2 | Voigt et al. 2025, *LLM-Powered Virtual Patient Agents … Automated Feedback*, arXiv 2508.13943 (`references/2508.13943v1.pdf`) | Full |
| R3 | PSYCHE, arXiv 2501.01594 (psychiatric patient simulation and evaluation, 10 psychiatrists) | Results, methods, discussion |
| R4 | PATIENT-Ψ, arXiv 2405.19660 (CBT patient simulation, 20 experts + 13 trainees) | Method, findings |
| R5 | Roleplay-doh, arXiv 2407.00870 (expert-defined principles for AI patients, 25 experts) | Method, pipeline, results |
| R6 | SimPatient, arXiv 2502.18673 (motivational interviewing for alcohol misuse, with avatar) | Design, stakeholder findings |
| R7 | MedSimAI, arXiv 2503.05793 (3 medical schools, 410 students, 1,024 encounters) | Design, results, lessons |
| R8 | SOPHIE, arXiv 2505.02694 (avatar standardized patient, randomised trial, n=51) | Design, trial results |
| R9 | LLM chatbots for psychiatrist and patient simulation, arXiv 2305.13614 | Prompt design, metrics |
| R10 | Embodied VPs for psychiatric and geriatric communication, Front. Virtual Real. 2022 | Summary of the review |
| R11 | LLM patient simulation + structured feedback RCT, BMJ Health Care Inform 2024 (PMC11605890) | Summary |
| — | 13 further abstracts from the Awesome-LLM-Patient-Simulators list (AIPatient, EvoPatient, CureFun, ClientCAST, AMIE, Satir-style patients, etc.) | Abstract only |

*Not read:* the Springer psychiatric VP design guidelines (paywalled) and JMIR e59213 (page wouldn't load). The repo list has about 70 papers; this plan does not claim to cover all of them.

---

## Part 1: Where PsychSim sits

The papers above name these gaps themselves. PsychSim already addresses each one by design:

| Gap the literature names | Who says so | What PsychSim does about it |
|---|---|---|
| LLM patients are **text only**, with no non-verbal signs to observe | R2, R10, R11 (listed as a limitation), JMIR 2023 in the repo list | The cue system: tremor, gaze, sweating, pupils and the rest, rendered on a 3D body. **Noticing them is graded**, through the MSE. |
| Out-of-the-box LLM patients are **too forthcoming, polite and formal**: "like doing therapy with a therapist" | R4, R9, R3 | Trust-gated hidden facts, plus behaviour instructions (strengthened in Part 2) |
| Psychiatric SBE is underused because **human actors struggle to portray psychosis or mania**, and acting suicidality can harm actors, especially adolescents | R1 | A virtual patient portrays hard conditions consistently, with no actor harm |
| LLM simulators stop at **history taking and diagnosis** | R2, R7, R11 (all history-taking or checklist focused) | The **management step is graded too**: the prescription is checked for dose, contraindications and interactions by deterministic code, and the disposition follows Indian mental health law. None of the papers read grade prescribing safety. |
| **Addiction and withdrawal** need physical signs as well as talk | R6 is the closest, and it is text-and-avatar MI only | Withdrawal is shown on the body (CIWA/COWS signs) and graded |
| **Low trainer-to-learner ratios** limit simulation | R1 | On-demand practice with automated formative feedback, in an Indian medical college |
| **Few randomised trials**, little on behaviour, retention or attitudes | R1, R10 | A pilot built as a randomised trial (Part 3) |

**One-line positioning (draft):** *PsychSim is an embodied psychiatry and addiction OSCE simulator in which observing non-verbal signs and making safe management decisions are graded, not only history taking. It is built on a case-locked LLM patient with a deterministic safety layer, and evaluated in an Indian medical college.*

---

## Part 2: Insights we can use, and the change each implies

Each change is tagged by when it lands: **S1** = this Stage 1 run, **S2/S3** = later stages, **Pilot** = the dean's study.

### A. Making the patient behave like a patient

| # | Insight (source) | Change to PsychSim | When |
|---|---|---|---|
| A1 | Telling the model **how the patient behaves in mental state exam (MSE) terms** (affect, speech, thought form, insight) made a significant difference. "Act like a patient with X" was clearly worse, and removing the behaviour block hurt affect most. (R3, ablation with 10 psychiatrists) | Add a `behavior` block to the case schema in MSE terms: affect, speech rate/volume/latency, thought form, thought content, perception, insight, cooperation. The same block drives the prompt **and** the cue engine **and** the answer key. | S1 |
| A2 | LLM patients are too calm and polite, use DSM-style words, and cooperate too readily. These instructions fixed it: describe symptoms vaguely and colloquially, relate them to daily life, let mood fluctuate, resist the doctor. (R9; same pattern in R3, R4) | Fixed **realism rules** in the patient prompt, plus a banned-words list per case (for example, a depressed patient never says "depressed" or "anhedonia" unless the case says so; R3 notes real MDD patients say "down" or "sick"). | S1 |
| A3 | **Instructions fade after a few turns.** A short, temporary reminder appended to the latest turn only (never stored in history) kept the style stable for the whole conversation. (R9) | PatientBrain appends a one-line reminder built from the case's `behavior` and style to the latest learner turn on every call. It costs a few tokens. | S1 |
| A4 | Asking the model to **"write the patient's next line in this dialogue"** instead of "you are the patient" reduced slips into helpful-assistant mode. (R5) | Use the next-line framing; the tester A/B tests it against role-play framing. | S1 |
| A5 | **Six conversation styles** act as a difficulty curriculum on top of any case: plain, upset, verbose, reserved, tangent, pleasing. (R4) | Add `style` as a case setting, independent of the diagnosis. Each case × style is a new encounter, giving cheap replay value and difficulty tiers. | S2 |
| A6 | Disorder features LLMs **fail to portray** unless told explicitly: irritability and threat in mania (0% conformity on homicide risk, probably model safety policy), flight of ideas and circumstantiality (only when prompted), and the difference between intellectual and emotional insight. (R3) | Case authors must script these as explicit behaviours with example lines. The tester gets a per-disorder **portrayal checklist**. **Grok must be tested on the threatening-mania case specifically**, because its safety policy may block it. | S1 (checklist), S2 (cases) |
| A7 | Faculty make better patients by giving **kudos, critique or rewrite** on single replies, which an LLM turns into written rules. Plain GPT-4 broke these rules in about 20% of turns; a check-and-rewrite pass cut awkward replies from 15% to 2.5%. (R5) | **Faculty tuning mode:** faculty chat with the patient and mark replies; the rules are saved into the case file as `principles`. Run the rule check in the tester's offline evaluation; live only if latency allows. | S3 |
| A8 | Addiction patients are well described by four internal states (control, self-efficacy, awareness, craving/reward) updated every turn with a reason; counsellors found graphing them useful. (R6) | Add these four as extra state for substance-use cases only. Show them as a line graph in the debrief. | S2 |

### B. Embodiment

| # | Insight (source) | Change | When |
|---|---|---|---|
| B1 | Giving the LLM patient an **action space** (function calls the 3D model executes, such as "raise your arm") was rated highly by experts. Experts also wanted it to follow two commands in one sentence. (R2) | Extend `event_cues` into **exam actions** the patient performs on request: `hold_out_hands` (tremor exam), `roll_up_sleeves` (track marks or scars), `look_at_light` (pupils), `stand_up`, `walk_to_door`. The doctor asks in words and the patient complies or refuses based on trust. | S1 (the first three), S2 (rest) |
| B2 | VPs were rated **less authentic than human actors**, even when stress and performance were equal. Most VP systems recorded learners' non-verbal behaviour but never analysed it. (R10) | Don't claim parity with human SPs. Position PsychSim as **rehearsal before** human SP or real patients (R1 says the same). Learner non-verbal analysis is parked with VR. | Pilot (wording) |

### C. Feedback and scoring

| # | Insight (source) | Change | When |
|---|---|---|---|
| C1 | **Construct-grounded scoring:** compare what the learner concluded (MSE, risk, diagnosis) with the case's ground truth. Weighting **risk 5 : MSE/behaviour 2 : history 1** correlated r = 0.85 with psychiatrists, and stayed above 0.78 across weightings. (R3) | Reweight `DESIGN.md` §8 so risk assessment carries the most weight, and score the MSE panel element by element against the case `behavior` block (A1). A learner cannot pass without the risk items. | S1 |
| C2 | Learners valued **feedback that quotes their own words**. (R7) | Every debrief item cites the learner's line and its timestamp ("At 04:12 you asked '…' — a closed question; try …"). | S1 basic, S3 full |
| C3 | Counsellors **preferred feedback after the session**, because live feedback broke the flow and caused anxiety. A tutor you ask for hints was useful in practice. (R6, R2) | Feedback only at debrief by default. An optional **"Ask tutor" hint button in Practice mode**, switched off in Assessment mode. | S3 |
| C4 | Different encounters need **different validated rubrics**: MIRS for general interviewing, MITI for motivational interviewing, SSHADESS for adolescents. Checklists must be editable by faculty. (R7, R6) | Each case declares its rubric: MIRS by default, MITI for substance cases, SSHADESS/HEADSS for the adolescent case, C-SSRS items for risk. The deterministic checklist stays faculty-owned. | S3 |
| C5 | **Formulate, then reveal:** the trainee writes their formulation, then sees it side by side with the ground truth. Experts and trainees rated this highly. (R4) | Make the debrief explicitly side by side: your MSE / risk / diagnosis / plan next to the case truth, with mismatches highlighted. | S1 basic |
| C6 | Debriefing works best with **psychological safety, Socratic questions and attention to the learner's own emotions**, not only plus/delta corrections. (R1) | Add 3–4 reflective prompts to the debrief ("What did you notice first?", "When did you feel stuck?", "How did you feel when she mentioned suicide?"). Add a prebrief screen (objectives, safety, "you can pause any time"). | S1 (prebrief), S3 (reflection) |
| C7 | **Automated scoring isn't exam-grade:** 32.5% exact match, 64% within one point, 87% correct pass/fail split versus human raters. Fine for practice feedback and triage, not formal assessment. (R7) | Label scores **formative**. Report agreement with faculty the same way (exact / ±1 / threshold). Any summative use needs a faculty review step. | Pilot |
| C8 | **LLM judges are biased about realism**: they underrated the realistic patient and favoured their own baseline, though they judged factual accuracy well. (R4) | The tester never uses an LLM to judge *realism*; realism comes from faculty ratings. LLM judges are allowed for *accuracy* checks (invented facts, rule adherence). | S1 |

### D. Learning design

| # | Insight (source) | Change | When |
|---|---|---|---|
| D1 | **One session doesn't stick**; knowledge faded after a single VP session. (R10) | The pilot uses repeated sessions (at least 3 per learner, spaced out), and the roadmap adds a retention check. | Pilot |
| D2 | **Prototype portrayals risk stereotypes**; R1 recommends several variations per disorder and involving people with lived experience. | At least 2 variants per disorder (different age, sex, background and presentation). Add a **lived-experience reviewer** (for example, a peer support worker) to the case review panel. | S2 / S3 |
| D3 | **Patient journeys over time** teach more than a snapshot (R1). Follow-up sessions with a between-session event (for example, a relapse) were requested. (R6) | **Follow-up visits**: the same patient returns with an event in between (relapse, side effect, missed dose), and their state carries over. | S3 |
| D4 | **Station length should match the real OSCE**; fixed 30-minute sessions didn't fit a 20-minute exam station. (R7) | The case time limit comes from the college's actual psychiatry OSCE timing (ask faculty). | S1 (setting) |
| D5 | **Gains only appeared where use was built into the curriculum** (d = 0.75); voluntary use showed no gain. (R7) | The pilot is scheduled inside the psychiatry rotation, not optional. | Pilot |
| D6 | Junior students wanted confidence and flow; senior students wanted complex cases and diagnostic reasoning. (R7) | Two tiers: **Foundation** (plain style, higher starting trust, single diagnosis) and **Advanced** (resistant styles, comorbidity, a substance-induced differential). | S2 |
| D7 | Typing feels unnatural, so students want voice, but **unreliable speech recognition hurt realism and adoption**; some teams fell back on a hidden human operator. (R7, R10) | Keep typed chat as a solid fallback. Speech-to-text must pass the accent test in the tester brief before voice becomes the default. | S2 |

### E. Testing the AI patient

| # | Insight (source) | Change to `briefs/03-tester.md` | When |
|---|---|---|---|
| E1 | Five **jailbreak categories** that work for patient simulators: ask for the hidden case data, ask how it works internally, swap roles (patient becomes doctor), ask it to become a different patient, ask meta-questions about being an AI. (R3) | Add all five to the prompt-injection tests (§2.2 type 6). | S1 |
| E2 | Automatic **honesty and resistance metrics**: wrong-symptom ratio (reported symptoms not in the case), unmentioned-symptom ratio (resistance), robot-like word ratio, Distinct-1. (R9) | Add these to the evaluation output. Also add an **instruction-decay test**: compare style adherence in turns 1–5 with turns 20–25 (checks A3). | S1 |
| E3 | Per-element **conformity rating by psychiatrists** gives a clinical fidelity score with reliability statistics. (R3) | For each case, at least 2 faculty psychiatrists rate each MSE element as conforming or not. Report the percentage and inter-rater agreement (Gwet's AC1). This replaces vague "realism" ratings. | S3 |
| E4 | A fast cloud model answered in about 2 s; whisper-tiny was the only real-time speech model on CPU. (R2) | This confirms our 2.5 s target. Benchmark whisper-tiny/base on the M5 Pro alongside the Grok latency test. | S1/S2 |

---

## Part 3: Pilot study design for the dean (replaces `DESIGN.md` §9.5 item 3)

Modelled on R8 (SOPHIE) and R11, with gaps from R1 and R10 filled.

| Item | Proposal |
|---|---|
| Design | Randomised controlled trial, two arms, stratified by year of study |
| Arms | **PsychSim** (3 spaced sessions inside the psychiatry rotation, different cases) vs **control** (a reading module plus case vignettes covering the same content). The same total time for both. |
| Primary outcome | Change in score on a **human standardised-patient OSCE station** (pre and post), rated by **blinded faculty** from recordings using the college's OSCE checklist plus MIRS. Report inter-rater ICC (R8 achieved 0.88). |
| Secondary outcomes | Risk-assessment completeness; MSE accuracy; attitudes and stigma toward mental illness (faculty pick a validated scale); self-confidence; **retention at about 3 months** (R1 and R10 both call for it) |
| AI-score validity | Agreement between PsychSim's automated score and faculty scores of the same sessions: exact, ±1 and pass/fail split (as in R7) |
| Size | About 50 learners (25 per arm) to detect a large effect (d ≈ 0.8, which R8 found); exact sample size to be confirmed with a statistician |
| Ethics | Institutional ethics committee approval before starting; consent; content notes for suicide and self-harm cases; data handling under §9.4 |
| Lived experience | At least one person with lived experience reviews the cases and the debrief wording |

---

## Part 4: What I'll change once you give the green flag

1. **`DESIGN.md`**
   - §3.2 / §3.3: realism rules, turn reminders, next-line framing, conversation styles, addiction states.
   - §4: exam actions.
   - §6.1: case schema gains `behavior` (MSE terms), `style`, `banned_words`, `principles`, `rubric`, `variants`.
   - §8: risk-first weights, quote-grounded and side-by-side debrief, scores labelled formative.
   - §9.5: the trial design above.
   - §10: roadmap tags from this file.
   - New §13: Positioning and evidence (Part 1).
2. **`briefs/02-developer.md`**: prompt-building rules (A1–A4), reminder injection, exam action functions, scoring weights, prebrief screen.
3. **`briefs/01-3d-artist.md`**: three extra Stage 1 clips: `action_hold_out_hands`, `action_roll_up_sleeves`, `action_look_at_light`.
4. **`briefs/03-tester.md`**: E1–E4, the portrayal checklist (A6), the rule that LLM judges never rate realism (C8), and a Grok threatening-mania test.
5. **`KICKOFF_PROMPT.md`**: fold in only the **S1** items, so the first run stays the same size apart from them.
6. **`references/`**: save the 7 arXiv PDFs read for this plan, plus a `references/README.md` mapping R1–R11 to files and links.

## Questions for you before I start
1. How long is the college's real psychiatry OSCE station? (Sets D4; the default stays 15 minutes.)
2. Is a lived-experience reviewer realistic at your college? If not, I'll mark D2's reviewer as optional.
3. Should the pilot's control arm be reading material (as in R8), or the college's usual teaching?
