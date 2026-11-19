# Personalities, randomized patients and ward scenarios

Research for the Digital Twin, October 2026. It builds on the 83 papers in `matrix.md` and `insights.md` and does not repeat them. All clinical content is draft and educational only, and needs faculty review before it shapes a case.

Read status: each source is marked **(full)** when the paper or guideline text was read, or **(abstract)** when only the abstract, a repository page or a summary was read. Licence rules as in `insights.md`: we copy code only under Apache-2.0, MIT or BSD. GPL, AGPL, non-commercial or no licence means ideas only.

## Summary of findings

1. **Prompted personality is measurable but fragile, and least stable in small models.** Big Five persona prompts move self-reported test scores in the intended direction in large models. Reliability is stronger in larger, instruction-tuned models. Self-report tests themselves are unreliable for LLMs: paraphrasing the prompt or reordering the options changes the scores. Conversation history makes small models *less* stable, not more.
2. **Personas drift within a few turns.** Two chatbots drifted from their instructions "within eight rounds". For a 2B Gemma patient, 0.665 of utterances were judged consistent with the persona when each utterance was judged on its own. Whole-dialogue Q&A consistency was higher (0.854).
3. **Some traits cannot be prompted at all.** Prompting fails to produce high psychopathy or low conscientiousness, and aligned models resist playing hostile or biased patients. This matters for dissociality and disinhibition presentations.
4. **A 4B model can hold one style label, a verbosity band and a few example lines.** It cannot hold five numeric trait levels, an attachment theory, defence mechanisms or a cultural model. Those must become code parameters (trust steps, disclosure thresholds, behaviour priors, length caps) that the prompt only voices. The Twin already works this way for facts and trust. The finding extends it to personality.
5. **PATIENT-Ψ's six styles** (plain, upset, verbose, reserved, tangent, pleasing) are the best-evidenced unit of "personality" for simulated psychiatric patients. They use one style per session and are MIT-licensed. ICD-11's five trait domains map onto them well, and they give the vocabulary for faculty.
6. **Randomize the patient, not the answer key.** Synthea (Apache-2.0) builds the full history from a state machine first and renders output formats afterwards. Patient-Zero and PSYCHE generate attributes in stages and pin the risk elements rather than letting the model decide them. For assessment, the diagnosis, required intents, risk tier and rubric are fixed per template. Only slots marked clinically neutral vary, under checked invariants.
7. **Human SP programmes already vary the person but keep the case fixed.** When several SPs play one case, total scores barely change. Checklist and rating scores shift more than chance would predict. Rapport's `variants` (Ananya/Arjun) already follow this pattern.
8. **Ward scenarios with clear marking exist in primary guidance.** Examples are an informal patient asking to leave (Mental Healthcare Act 2017 s.88(3): a 24-hour hold for assessment), escalating agitation (NICE NG10 1.3.12–1.3.20), capacity to refuse medication (MHCA s.4), self-harm crisis (NICE NG225: no risk tools to predict), postpartum psychosis and new confusion on the ward. The RCPsych CASC marksheets give ready-made examiner domains.
9. **Evaluate personas by interview, not by self-report questionnaire.** Use prompt-to-line, line-to-line and Q&A consistency, a non-Gemma judge, a faculty discrimination test, and a fact check against the *generated* case.

## 1. Personality models for LLM-simulated patients

### 1.1 Big Five conditioning: what the evidence says

| Source | Read | Models | Finding relevant to a 4B patient |
|---|---|---|---|
| PersonaLLM: Investigating the Ability of LLMs to Express Personality Traits, Jiang H, 2024 (NAACL Findings), https://arxiv.org/abs/2305.02547 | abstract | GPT-3.5, GPT-4 | BFI scores match the assigned type with large effect sizes. Humans perceived some traits in essays with up to 80% accuracy, and less when told the text was AI-written. No code link. |
| A psychometric framework for evaluating and shaping personality traits in LLMs (arXiv title: Personality Traits in Large Language Models), Serapio-García G, 2023/2025, https://arxiv.org/abs/2307.00184 | abstract | 18 LLMs | Measurements are reliable and valid only for some models under specific prompts. Evidence is stronger for larger, instruction-tuned models. Shaping toward target profiles works in those models. A Cambridge repository record lists a Nature Machine Intelligence version; not read. |
| Self-Assessment Tests are Unreliable Measures of LLM Personality, Gupta A, 2023, https://arxiv.org/abs/2309.08163 | abstract | ChatGPT, three Llama-2 sizes | Three equivalent prompts gave significantly different scores. Scores were not robust to option order. |
| Persistent Instability in LLM's Personality Measurements (PERSIST), Tosato T, 2025, https://arxiv.org/abs/2508.04826 | full | 1B–685B | Reordering questions alone shifts scores by about 20% of the scale. Even 400B+ models keep SD > 0.4 on 5-point scales. Conversation history increased variability in models under 50B (p < 0.001). Reasoning mostly increased variability. A schizophrenia persona raised SD. Code licence not stated. |
| TRAIT: Personality Testset designed for LLMs, Lee S, 2025 (NAACL Findings), https://arxiv.org/abs/2406.14703 | abstract | several | Prompting is "not very effective" at eliciting high psychopathy or low conscientiousness. |
| BIG5-CHAT: Shaping LLM Personalities Through Training on Human-Grounded Data, Li W, 2024, https://arxiv.org/abs/2410.16491 | abstract | Llama-class | SFT and DPO on 100k dialogues beat prompting on BFI and IPIP-NEO, with trait correlations closer to human data. Fine-tuning is out of scope for Rapport (insights row 26). |
| Quantifying the Persona Effect in LLM Simulations, Hu T, 2024 (ACL), https://arxiv.org/abs/2402.10811 | abstract | up to 70B | Persona variables explain under 10% of annotation variance. Persona prompting gives small but significant gains. |
| PersonaGym, Samuel V, 2025 (EMNLP Findings), https://arxiv.org/abs/2407.18416 | abstract | 10 LLMs | Size does not predict persona adherence. GPT-4.1 scored the same as Llama-3-8B. |
| LLM Agents in Interaction: Measuring Personality Consistency and Linguistic Alignment, Frisch I, 2024 (EACL workshop), https://arxiv.org/abs/2402.02896 | abstract | GPT-3.5 | Profiles differ in how consistent they stay and how much they converge on the partner's language. |

**Reading for Rapport.** Gemma 4 E4B sits in the size band where every study finds the weakest, least stable trait expression. Two findings matter most. First, history amplifies instability in small models (PERSIST). Second, drift appears within about eight rounds (next section). So a persona stated once in the system prompt will fade over a 15-minute station. Re-stating a short persona cue in the per-turn tail is the countermeasure that fits one call per turn. Rapport already does this with `brain.style_reminder`.

### 1.2 Persona drift and consistency over long dialogues

- Measuring and Controlling Instruction (In)Stability in Language Model Dialogs, Li K, 2024 (COLM), https://arxiv.org/abs/2402.10962 **(abstract)**. Instruction drift is "significant" within eight rounds of self-chat (LLaMA2-chat-70B, GPT-3.5). The authors link it to attention decay. Their fix, split-softmax, changes attention at inference time. That is not available through llama-server, so for us the fix is re-injecting the persona each turn.
- Consistently Simulating Human Personas with Multi-Turn RL, Abdulhai M, 2025 (NeurIPS), https://arxiv.org/abs/2511.00222 **(full; first ~60% of the HTML)**. It defines three metrics, all scored by a Llama-3.1-70B judge. *Prompt-to-line* judges each utterance alone against the persona. *Line-to-line* checks each utterance against the speaker's earlier lines. *Q&A* has the judge write 5 multiple-choice questions from the persona, which the simulator then answers in context. On the mental-health patient task, the baselines scored as follows. Gemma-2-2B: prompt-to-line 0.665, line-to-line 0.984, Q&A 0.854. Mistral-7B: 0.863, 0.964, 0.810. Llama-3.1-8B: 0.657, 0.681, 0.779. PPO fine-tuning raised prompt-to-line consistency by 37.6% on the patient task. The paper's tables and text disagree on the human-agreement figures (80% vs 77%). Code: https://github.com/abdulhaim/consistent-LLMs, **no LICENSE file, so ideas only**. Two lessons. A small model can stay locally consistent (line-to-line) while drifting from the brief (prompt-to-line). And prompt-to-line is the metric to track.

### 1.3 Conversational styles (PATIENT-Ψ)

PATIENT-Ψ: Using LLMs to Simulate Patients for Training Mental Health Professionals, Wang R, 2024 (EMNLP), https://arxiv.org/abs/2405.19660 **(full)**. It defines six styles, each inserted as one guideline in the GPT-4 prompt, one style per session:

| Style | Definition (Table 1/8) |
|---|---|
| plain | direct, straightforward |
| upset | frustration, resistance; dismisses suggestions, argues, struggles to trust |
| verbose | overly expressive; long answers, hard to steer |
| reserved | minimal, restrained; brief, vague or evasive; needs prompting; sceptical |
| tangent | starts to answer, drifts into unrelated anecdotes; needs redirecting |
| pleasing | agreeable to a fault; downplays concerns, seeks approval, agrees without understanding |

Each cognitive model is annotated with the styles that are valid for it, so not every style pairs with every case. Experts rated style fidelity above plain GPT-4 by about 1.3 points on a −2..2 scale. 100% wanted the style option. No per-style fidelity numbers were reported. **Code licence: MIT** (LICENSE file checked this round, which resolves the badge mismatch noted in `r4-patient-psi-2024`). Rapport's case already has `style: "plain"`. It is a free string today, not one of a closed set.

### 1.4 Attachment, defence mechanisms and ICD-11 trait domains

- **Attachment.** The ECR-R (anxiety × avoidance → secure, preoccupied, dismissing, fearful) has been given to LLMs in PsychoBench (Who is ChatGPT? Benchmarking LLMs' Psychological Portrayal Using PsychoBench, Huang J, 2024, https://arxiv.org/abs/2310.01386, **abstract**). The repo is **GPL-3.0 and marked "no commercial use", so ideas only**. A 2026 preprint applies the ECR-R to 32 LLMs and asks whether prompting shifts it (Which LLM Is Your Ideal Companion?, Zhou J, 2026, https://arxiv.org/abs/2608.13168, **abstract; no results visible**). No study tests whether a *prompted* attachment style holds across a clinical interview. Rapport's `attachment_style` is a free-text line in the prompt. Treat it as flavour, and put its behavioural effect (for example "seeks reassurance, then withdraws if not given it") into code as a trust-step rule.
- **Defence mechanisms.** The best available work detects them; it does not simulate them. PsyDefConv annotates 200 ESConv dialogues with the 7 DMRS defence levels (κ 0.639). The best shared-task system reached only macro-F1 0.42 (You Never Know a Person, You Only Know Their Defenses, arXiv 2512.15601, https://arxiv.org/abs/2512.15601, and PsyDefDetect overview, https://arxiv.org/abs/2605.24907, both **abstract**). If models cannot reliably tell defence levels apart in text, a 4B model cannot reliably produce a chosen one from a label. Defences should be authored as behaviours with example lines (minimising, intellectualising, displacing anger onto staff) and chosen by code triggers.
- **ICD-11 personality.** ICD-11 grades severity (personality difficulty, mild, moderate, severe) and adds optional trait-domain qualifiers: negative affectivity, detachment, dissociality, disinhibition and anankastia. There is also an optional borderline-pattern qualifier (5 of 9 features) (Application of the ICD-11 classification of personality disorders, Bach B, 2018, BMC Psychiatry, https://pmc.ncbi.nlm.nih.gov/articles/PMC6206910, **full**). Bach and First propose that severity guides treatment intensity and the traits guide the style of treatment. That is the split Rapport needs: severity drives how hard the station is, and traits drive *how* the patient talks. The DSM-5 PID-5 brief form (25 items) covers a parallel 5-domain model (APA, https://www.psychiatry.org/psychiatrists/practice/dsm/educational-resources/assessment-measures, **full page**).
- **Dissociality and disinhibition are the hard ones.** TRAIT finds prompting cannot produce high psychopathy or low conscientiousness. AgentClinic found aligned models refuse biased or uncooperative patient instructions (`agentclinic-2024` note). Expect Gemma to soften hostility and entitlement. Those presentations need authored example lines, a code-held agitation state, and a guard that refuses to let an apologetic utterance go out when the code state says "hostile".

### 1.5 Cultural and dialect factors (Indian, Bengaluru)

- LLM knowledge of Indian regional culture varies a lot by subculture (DOSA: A Dataset of Social Artifacts from Different Indian Geographical Subcultures, Seth A, 2024, https://arxiv.org/abs/2403.14651, **abstract**; 615 artefacts, 19 subcultures, 4 LLMs).
- Persona prompts based on socio-demographic identity cause stereotyped behaviour that the same model rejects when asked directly. For ChatGPT-3.5, 80% of personas showed bias, and prompt mitigations did not suffice (Bias Runs Deep: Implicit Reasoning Biases in Persona-Assigned LLMs, Gupta S, 2024, ICLR, https://arxiv.org/abs/2311.04892, **abstract**). Writing "Indian" or "Kannadiga" into a persona line invites caricature.
- The DSM-5-TR Cultural Formulation Interview (16 questions, plus an informant version) is the clinical frame for what is culturally relevant: explanatory model, idioms of distress, help-seeking and the family's role (APA page above).

**For Rapport:** do not ask the model to "be Indian". Author the culture as content: `explanatory_model` ("maybe it's work stress, everyone has stress, no?" is already in `mdd_01`), a short `idioms` list of everyday phrases the patient uses (code-mixed words such as "tension", "amma"), family roles in the facts, and the dialect line already in `brain.py`. Keep code-mixing to a fixed list, so the TTS and STT paths can be tested against it.

### 1.6 What one prompt can hold for a 4B model, and what code must enforce

| Aspect | Reliable in the prompt (4B) | Must be code |
|---|---|---|
| Conversational style | One PATIENT-Ψ label + 2 example lines, re-stated in the per-turn tail | Which styles a case allows; switching style only between sessions |
| Verbosity | A band ("1–2 short sentences") | Hard word or token cap by state (PSYCHE uses hard word counts; `r3-psyche-2025`) |
| Big Five / ICD-11 traits | Not as numbers. At most a two-word gloss ("cautious, self-critical") | Traits → parameters: trust start and step size, disclosure offsets, agitation gain, behaviour priors |
| Attachment | One plain line ("seeks reassurance, hides need") | Rule: unmet reassurance → trust step −1; validation → +1 |
| Defences | Example lines per defence behaviour | Trigger table: which doctor move or locked hit selects which defence behaviour |
| Hostility / entitlement / impulsivity | Example lines only | Agitation state, escalation thresholds, a guard against over-apologetic replies |
| Facts, risk, diagnosis | Nothing beyond recalled open facts | Everything (already built) |
| Culture / dialect | Dialect line + a fixed idiom list | Content in case JSON; no identity adjectives |

## 2. Randomized patients with consistent answer keys

### 2.1 Generation approaches

| Source | Read | Mechanism | Licence | Use |
|---|---|---|---|---|
| Synthea, Walonoski J, 2018, JAMIA 25(3), https://doi.org/10.1093/jamia/ocx079; repo https://github.com/synthetichealth/synthea | paper not read; LICENSE checked | Disease modules are JSON state machines (the Generic Module Framework). The simulator builds each patient's complete history first, then exporters render it | **Apache-2.0** | Pattern: build the full fact set from the template first, render the prompt and answer key from it. The code is Java and US-primary-care; take the pattern, not the code |
| Patient-Zero, Lai Y, 2025, https://arxiv.org/abs/2509.11078 | full (`r-patient-zero-2025`) | Staged synthesis (outline → baseline → symptoms → exam) with stratified attribute permutation; LLM verification per stage | unknown, ideas only | Stage order and "permute attributes within strata" |
| PSYCHE, Lee J, 2025, https://arxiv.org/abs/2501.01594 | full (`r3-psyche-2025`) | Diagnosis + age + sex → profile → history → MSE. Impulsivity and suicide-risk elements are **fixed per disorder** because GPT-4o under-rates risk | none | Never let a model pick the risk tier |
| AgentClinic, Schmidgall S, 2024, https://arxiv.org/abs/2405.07960 | full (`agentclinic-2024`) | MedQA/NEJM cases → structured JSON with private views per agent (patient, measurement, moderator) | MIT (confirm LICENSE) | Split of patient-visible vs examiner-only fields, which Rapport has |
| AIPatient, Yu H, 2024, https://arxiv.org/abs/2409.18924 | abstract (`aipatient-2024`) | EHR knowledge graph + 6 agents | unknown | Repeat-trial consistency check only |
| Simulating Diverse Patient Populations Using Vignettes, Denecke K, 2024, https://aclanthology.org/2024.cl4health-1.3.pdf | full (`vignette-patient-populations-2024`) | 16 vignette dimensions split into primary (clinical) and secondary (personality, style, literacy, SES…) | unknown | The primary/secondary split is the right axis for which slots may vary. Removing detail made containment fall from 64% to 9% |

### 2.2 How human SP programmes vary a case

- Several SPs playing one case: effects on case means and failure rates were negligible for total and written scores. SP checklist scores showed "more significant differences than would be expected by chance alone" (Effects of using two or more standardized patients to simulate the same case, Colliver JA, 1991, Acad Med 66(10):616, https://archive-ouverte.unige.ch/unige:26103, **abstract**). The same group reported that multiple SPs lowered the reliability of *ratings* by about 5 points, four to five times the effect on checklists (Colliver et al., cited in the same archive, **abstract**).
- The RCPsych CASC fixes each station's construct ("what constitutes a competent performance"), instructions and marksheet. Its role players are "thoroughly trained in the specifications of their roles". Station difficulty is absorbed by borderline regression *per station*: the domain scores are regressed onto the 6-point global judgement for that station, and high scores on some stations cannot compensate for low scores on others (Preparing for the CASC, RCPsych, https://www.rcpsych.ac.uk/training/exams/preparing-for-exams/preparing-for-the-casc, **full**).

**Reading for Rapport.** "Same case, different patient" is established practice. A changed person shifts the *process* scores (rapport, ratings) more than the *content* scores (checklist). So randomize demographics and neutral life details freely. Treat a personality-style change as a difficulty change that must be banded, and keep the fixed station construct the unit that is standard-set.

### 2.3 Seeded reproducibility

- The case generator should be a pure function `(template, seed, generator_version) → case`, using Python's `random.Random(seed)` and no LLM, so the same seed always yields the same case and answer key. Log the seed and generator version in every session, next to `brain_version`.
- The voice is not bit-reproducible. llama-server's `seed` fixes the sampler, but its docs warn that with `cache_prompt` (on by default) "logits are not guaranteed to be bit-for-bit identical for different batch sizes… enabling this option can cause nondeterministic results" (llama.cpp server README, https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md, **full**; **MIT**). Reproducibility claims should cover the case and the scoring, not the wording.

### 2.4 Fairness for assessment

- Equivalent difficulty means equal *required work under equal conditions*: the same required intents, the same number of required facts behind locks, similar trust thresholds, the same risk tier, and a style from the same difficulty band.
- Practice mode can sample anything valid. Assessment mode should draw from a small set of pre-generated, faculty-approved seeds per template, matching the `candidate`/`approved` split in `TWIN.md`, and standard-set per station as the CASC does.

## 3. Acute inpatient ward scenarios and unexpected events

### 3.1 What the examiner marks (RCPsych CASC)

The CASC has 16 stations of 7 minutes each: 5 history (including risk), 5 examination (physical and mental state, including capacity), and 6 management. Each station gets 3–5 domain scores from 1 to 5 and one 6-point global judgement (Excellent Pass … Severe Fail) (RCPsych page above, **full**). The marksheets list the descriptors (CASC History, Management and Examination marksheets, RCPsych, https://www.rcpsych.ac.uk/docs/default-source/training/examinations/exams-casc-history-marksheet.pdf and siblings, **full**):

- **History:** identify issues and priorities; recognise significance; explore relevant symptoms; risk assessment; physical health and the patient's views; psychological and social information.
- **Management:** formulate the problem; recognise significance of findings; a plan reflecting current best practice; physical health and views; a risk-management plan covering the risks of each option; psychological and social interventions.
- **Communication (all sheets):** structured consultation; not formulaic; attitude and behaviour; listening and response to cues; questioning style; language suited to the scenario.

These descriptors map directly onto Rapport's rubric layer, and they are voice-only by nature.

### 3.2 Presentations

| Presentation | Key guidance (read) | Voice-only? |
|---|---|---|
| Severe depression with risk | NICE NG225 Self-harm (2022) 1.6.1–1.6.4: "Do not use risk assessment tools and scales to predict future suicide or repetition of self-harm"; no low/medium/high stratification to decide treatment or discharge, https://www.nice.org.uk/guidance/ng225 **(full)** | Yes (Rapport's current case) |
| First-episode psychosis | NICE CG178 1.3.4.1: offer oral antipsychotic with family intervention and individual CBT; refer at-risk states to early intervention without delay, https://www.nice.org.uk/guidance/cg178 **(full)** | Yes |
| Mania | NICE CG185 Bipolar disorder (updated 2025), https://www.nice.org.uk/guidance/cg185 **(recommendations page retrieved, not detailed here)** | Yes; pressured speech suits voice. Code must cap tangent length |
| Personality-disorder crisis / self-harm on ward | NG225 (above); ICD-11 borderline pattern (Bach 2018) | Yes |
| Delirium vs psychosis | NICE CG103 1.3.2: watch for hypoactive delirium ("withdrawal, slow responses… worsened concentration and reduced appetite"); short-term haloperidol only if other measures fail, https://www.nice.org.uk/guidance/cg103 **(full)** | Partly: disorientation and fluctuation can be voiced; the exam router gives vitals |
| Alcohol withdrawal | NICE CG100 1.1.2: CIWA-Ar as an adjunct to judgement; offer admission if at high risk of seizures or delirium tremens; benzodiazepine or carbamazepine, https://www.nice.org.uk/guidance/cg100 **(full)** | Partly (history, orientation; tremor via exam router) |
| Postpartum psychosis | NICE CG192 1.5.12: sudden onset → specialist assessment "within 4 hours of referral", https://www.nice.org.uk/guidance/cg192 **(full)** | Yes, as history + management |
| Eating disorder medical risk | NICE NG69 1.11 refers to RCPsych MEED (CR233, 2022; replaces MARSIPAN; traffic-light risk across 11 areas; patients "may be high risk despite appearing well and having normal blood parameters"), https://www.nice.org.uk/guidance/ng69 **(full)**, https://www.rcpsych.ac.uk/cr233 **(abstract)** | Weak: the risk lives in obs and bloods. Possible only as a "results are in front of you" management station |
| Catatonia | BAP consensus guidelines on catatonia, Rogers JP, 2023, J Psychopharmacol 37(4):327, https://doi.org/10.1177/02698811231158232 **(abstract)**: Bush-Francis scale; lorazepam and/or ECT first line | Poor: mutism and posturing are visual. Better as an informant (nurse/relative) history station |

### 3.3 Unexpected events

| Event | Primary source (read) | What the candidate must do |
|---|---|---|
| Escalating agitation | NICE NG10 Violence and aggression (2015). 1.3.12: recognise early signs, avoid provocation. 1.3.15: handle "flashpoint" situations such as refusing a request without provoking. 1.3.17: respect and empathy at all stages. 1.3.18: "1 staff member should take the primary role", seek clarification, negotiate non-confrontationally. 1.3.20: a calm space, not routinely the seclusion room. 1.4.5: restrictive intervention only if de-escalation and p.r.n. fail. 1.4.45: after rapid tranquillisation, observe at least hourly, every 15 minutes in listed cases. https://www.nice.org.uk/guidance/ng10 **(full)** | Listen, name the grievance, offer choices, keep their own voice calm, set limits without threats, check safety, offer p.r.n. as a choice |
| Informal patient asks to leave (India) | Mental Healthcare Act 2017 s.86–88. s.88(1): discharge an independent patient "immediately on request". s.88(3): a mental health professional "may prevent discharge… for a period of twenty-four hours" to assess for supported admission, if the person cannot understand their decisions, has recently threatened or attempted self-harm, has been violent, or cannot care for themselves. s.88(4): then admit under s.89 or discharge. https://www.indiacode.nic.in/bitstream/123456789/2249/1/A2017-10.pdf **(full)** | Explore why, assess risk and capacity, explain rights and status honestly, least restrictive option, involve the nominated representative (s.14) |
| Same, UK framing | MHA 1983 s.5(2) doctor's holding power (up to 72 h) and s.5(4) nurse's (up to 6 h), https://www.legislation.gov.uk/ukpga/1983/20/section/5 **(not fetched: site blocked automated access; verify)**. The Mental Health Act 2025 received Royal Assent on 18 Dec 2025 and amends the 1983 Act in stages (law-firm summaries only; **verify on legislation.gov.uk**) | As above. Keep the UK framing as a footnote: the cases are Indian |
| Refusal of medication / capacity | MHCA s.4(1): capacity = ability to understand the relevant information, appreciate foreseeable consequences, communicate the decision. s.4(3): a decision "perceived by others as inappropriate or wrong" does not by itself mean incapacity (Act above, **full**) | Explore the reason (side effects, beliefs), test the s.4 elements, offer alternatives, no coercion |
| Emergency treatment | MHCA s.94: any registered medical practitioner, to prevent death or irreversible harm or serious harm to self or others; limited to 72 hours; no ECT (Act above, **full**) | Knowledge for the debrief, not a live station |
| Restraint | MHCA s.97: only to prevent imminent harm, authorised by the treating psychiatrist, recorded, never as punishment or because of staff shortage; inform the nominated representative (Act above, **full**) | Debrief point for the agitation station |
| Disclosure of abuse mid-interview | No single guideline was read this round; mark the content draft for faculty | Listen, do not promise secrecy, check current safety, explain next steps, document, escalate |
| Relative interrupts | MHCA s.14 nominated representative (Act above) | Confidentiality vs the representative's role; a separate station where the relative is the speaker |
| New confusion / intoxication / medical deterioration | NICE CG103, CG100 (above) | Think medical first, check orientation, ask for obs, escalate. Partly voice-only via the exam router |

## 4. Evaluation

### 4.1 Are personalities distinguishable and stable?

- **Do not use self-report questionnaires as the main test.** They are unreliable for LLMs: prompt and option-order effects (Gupta 2023), and history amplifies instability in small models (PERSIST). If a questionnaire is used anyway, use IPIP items, which are public domain ("permission has already been automatically granted", https://ipip.ori.org/newPermission.htm, **full**). Give them several times with shuffled order and paraphrases, and report the spread, not a single score. Avoid PsychoBench code (GPL-3.0, non-commercial).
- **Interview-based rating.** InCharacter interviews the role-playing agent and has a judge rate the answers on the scale, reaching 80.7% agreement with human-perceived personality (InCharacter, Wang X, 2024, ACL, https://arxiv.org/abs/2310.17976, **abstract**). For Rapport: run the simulated doctors from Phase E self-play, then have a non-Gemma judge rate each transcript on the six PATIENT-Ψ styles and the five ICD-11 domains. The target is that it recovers the assigned style.
- **Consistency metrics (Abdulhai 2025).** Prompt-to-line, line-to-line and Q&A, per session. Prompt-to-line is the one that catches drift in small models. Use the order-swapped, non-Gemma judging already planned in `insights.md` §5.
- **Faculty discrimination test.** Show faculty blind pairs of transcripts (same case, two styles) and ask which is "reserved" and which is "pleasing". Accuracy above chance per pair shows the styles are distinguishable. Patient-Zero's "indistinguishable from real" claim rests on two raters (`r-patient-zero-2025`). Plan for at least 3 raters and report agreement.

### 4.2 Does randomization break fidelity?

- **Generated-fact check.** Run the same atomic-fact contradiction check planned in `insights.md` row 12, but against the *generated* case. Any utterance that contradicts a generated slot (a sister's name, an occupation, a time course) or introduces an unlisted clinical fact counts as a fail. This matters more for generated cases, because the model has a canonical version of the base case and can fall back to it.
- **Answer-key replay.** For each generated case, a scripted ideal doctor asks every required intent at realistic trust. Every required fact must be reachable within the time limit, and the debrief must score the full transcript 100%. This is a code test, no LLM judge needed.
- **Severity recovery.** A judge reading generated sessions should recover the template's severity and risk tier within tolerance (TalkDep idea, `insights.md` row 20).
- **Repeat-trial consistency.** Same seed, 5 runs: answers to the Q&A probe questions must agree (AIPatient's repeat-trial idea, `aipatient-2024`).

## Recommendations for Rapport

| # | Idea | Twin component | Concrete change | Reliable for 4B? |
|---|---|---|---|---|
| R1 | Personality is code parameters plus one style label | case schema, `twin.py` | `personality: {style, icd11_traits, severity}` compiled by code into `trust_start`, `reaction_trust_unit` multiplier, disclosure offsets, `agitation_gain`, behaviour priors | Yes: the model sees only the label and example lines |
| R2 | Close the `style` field to PATIENT-Ψ's six values | case schema, `validate_data.py`, `behaviours.json` | Enum + one description and 2 example lines per style | Yes (single label + examples) |
| R3 | Re-state the persona every turn | `brain.style_reminder` | Keep it ≤ 25 words: style, length band, one idiom. Never grows with history | Yes. Counters drift within ~8 turns |
| R4 | Hard length caps by style and state | `brain.py` (`max_tokens`), guard | reserved: ~25 words; verbose/tangent: ~70 | Yes (code) |
| R5 | Defences and attachment become trigger rules | `twin.py` rubric table (insights row 7) | e.g. premature reassurance + anxious attachment → `minimises` behaviour, trust −1 | Yes (code chooses, model voices) |
| R6 | Hostile and impulsive styles need a guard | `brain.guard` | If code state is agitated and the reply contains apology or deference markers, swap in a case fallback line or regenerate offline | Partly: Gemma will soften these |
| R7 | Culture as content, not identity | case schema | `explanatory_model`, `idioms[]`, family facts; no identity adjectives in the prompt | Yes |
| R8 | Seeded generator, fixed answer key | new `tools/casegen/`, `validate_data.py` | Pure function, logged seed, invariants below, faculty-approved seeds for assessment | Yes (no LLM) |
| R9 | Scheduled and triggered events | case schema, `twin.py` | `events[]` fired by time, intent or state: inject an open fact, a state delta and a cue; the examiner marks the response | Yes (code) |
| R10 | Evaluation suite | `tests/llm-eval/` | Prompt-to-line, line-to-line and Q&A metrics; generated-fact check; answer-key replay; faculty blind style test | Judge must not be Gemma |

## Proposed design sketch

### (a) Personality layer

```json
"personality": {
  "style": "reserved",                       // one of plain|upset|verbose|reserved|tangent|pleasing
  "severity": "none",                        // none|difficulty|mild|moderate|severe (ICD-11)
  "traits": {"negative_affectivity": 2, "detachment": 1, "dissociality": 0,
             "disinhibition": 0, "anankastia": 1},   // 0–3, code-only, never in prompt
  "attachment": "anxious",                   // secure|anxious|avoidant|fearful
  "defences": ["minimising", "intellectualising"],   // behaviour ids in behaviours.json
  "gloss": "quiet, self-critical, hides how bad it is"  // ≤ 8 words, the only trait text the model sees
}
```

Code compiles this once at session start into parameters. Draft numbers, to be tuned:

| Input | Parameter it moves |
|---|---|
| style reserved / pleasing / upset | trust_start −5 / +5 / −10; word cap 25 / 40 / 40 |
| negative_affectivity | distress_start +5 per point; trust loss on invalidation ×(1 + 0.25·level) |
| detachment | engagement_start −5 per point; disclosure trust_min +3 per point for `kind: feeling` facts |
| dissociality | agitation gain on limit-setting; empathy lowers trust less |
| disinhibition | agitation decay slower; event `asks_to_leave` threshold lower |
| anankastia | corrects the doctor's paraphrases; `tangent` disallowed |
| attachment anxious | reassurance +1 trust, ignored cue −1; avoidant: closeness questions −1 early, +1 after trust 50 |
| defences | listed behaviours become eligible when a locked hit or a premature move happens |

Rules: the template lists which styles and trait ranges it allows. The model never sees trait numbers. `why` reports the parameter that fired, for example "Avoidant attachment: early closeness question, trust −1".

### (b) Seeded patient generator

A template is a normal case file plus a `slots` block. Generation picks values, renders `{slot}` placeholders in facts, the referral note and the background, and writes `generated: {template_id, seed, generator_version}` into the output.

```json
"slots": {
  "variant":    {"from": ["female", "male"]},                     // existing variants
  "age":        {"range": [22, 28]},
  "occupation": {"from": ["software test engineer", "bank clerk", "call-centre team lead"],
                 "requires": {"precipitant": "work_pressure"}},
  "home_town":  {"from": ["Mysuru", "Hubballi", "Mangaluru"]},
  "sibling":    {"from": [null, "younger sister", "younger brother"]},
  "hobby":      {"from": ["cricket", "drawing", "temple music"]},
  "style":      {"from_allowed": "personality.style_allowed"},
  "idioms":     {"sample": 2, "from": ["tension", "no?", "what to do", "amma"]}
},
"fixed": ["answer_key", "scales", "risk_tier", "facts[kind=risk]", "exam", "formulation.presenting"]
```

Invariants checked by `validate_data.py` on every generated case. A failure rejects the seed.

1. **Fixed means fixed.** `answer_key`, `scales`, the risk facts' text, `trust_min` and tags, `exam` findings and the risk tier are byte-identical to the template after rendering.
2. **Every required intent is answerable.** Each `required_intents` entry maps (via `intents.json`) to at least one fact whose `trust_min` is reachable: start trust plus the style offset plus the best-case trust gain over `time_limit_min` minus 3 minutes must be ≥ `trust_min`.
3. **No slot adds clinical content.** Slot values come from closed lists. A slot may not introduce a symptom, a substance, a diagnosis term, a banned word or a new risk factor. Lint the lists against `banned_words`, `diagnoses.json` and an extended list of clinical terms.
4. **Scales match facts.** PHQ-9 and GAD-7 item scores are fixed with the template, so no slot may touch sleep, appetite, energy or self-harm facts.
5. **Differentials are not changed.** No slot value may support an `acceptable_differentials` entry more than the template does (for example a slot that adds a past high-energy period would push toward bipolar).
6. **Difficulty band.** Let L be the sum of `max(0, trust_min − trust_start)` over required facts. L for the generated case must be within ±10% of the template's, and the style must be in the template's difficulty band. Assessment mode uses only approved seeds.
7. **Seeded and versioned.** The same `(template, seed, generator_version)` gives byte-identical output, checked by a unit test. Seed and version go in the session log and debrief.
8. **Answer-key replay passes** (section 4.2).

### (c) Ward station ideas

| # | Station (setting: acute ward, Bengaluru) | Twin mechanics | What is marked (CASC domains) |
|---|---|---|---|
| 1 | **"I want to go home."** Independent patient (MHCA s.86), day 3, depressed, recent self-harm thoughts, wants discharge | `events`: asks to leave at minute 1; trust-locked fact about a plan; agitation rises if the doctor is evasive about status | Explores reasons; risk assessment; capacity (s.4); explains rights and the s.88(3) 24-hour assessment honestly; least restrictive option; involves the nominated representative; communication under pressure |
| 2 | **Escalating agitation.** Manic patient refused a phone call by staff | Agitation state with NG10 rules in code: validation and choices lower it; threats, rushing and multiple voices raise it; hostility guard (R6) | One calm lead voice; names the grievance; offers choices; avoids provocation; sets limits safely; offers p.r.n. as a choice; safety awareness |
| 3 | **Refusing medication.** First-episode psychosis, refuses olanzapine because of weight gain and a belief it is poison | Facts split: side-effect worry (open) vs persecutory belief (locked at trust 40) | Explores reasons; tests understand/appreciate/communicate; separates side-effect concern from delusion; offers alternatives; no coercion |
| 4 | **Abuse disclosure mid-history.** Young woman with depression discloses partner violence once trust ≥ 50 | Event fires on trust; the patient asks "you won't tell anyone?" | Responds calmly; does not promise secrecy; checks current safety and children; explains next steps; documents; escalates |
| 5 | **Day-2 confusion.** Admitted for mania, now disoriented at night, sweating (alcohol withdrawal vs delirium) | Fluctuating orientation in code; exam router returns tremor, tachycardia and fever | Thinks medical first; orientation and attention; alcohol history; CIWA-Ar; Wernicke risk; escalates; does not label it "relapse" |
| 6 | **Self-harm on the ward.** Patient with a borderline pattern who cut after a cancelled leave | `upset` style; validation rule softens resistance; invalidation sharply drops trust | Needs-based psychosocial assessment (NG225), no risk-tool prediction; validates; collaborative safety plan |
| 7 | **The worried father.** Relative of a patient on the ward demands information and discharge | Relative is the speaker (a separate case); nominated-representative fact | Confidentiality vs the s.14 role; listens; explains what can be shared; addresses the carer's concerns |
| 8 | **Postnatal day 6.** New mother with sudden insomnia, odd beliefs about the baby | Partner present as informant via fact text; locked fact about thoughts of harming the baby | Recognises postpartum psychosis; asks about the baby's safety; urgent specialist assessment (CG192: within 4 hours); explains to the family |

Stations 1, 2 and 3 reuse the most existing machinery. Station 5 depends on the exam router. Catatonia and eating-disorder medical risk are left out of the voice station set (section 3.2).

## Gaps

- Many personality sources were read as abstracts only. The full PERSIST and Abdulhai papers carry the small-model evidence.
- No study tests prompted attachment or defence styles in a clinical interview, or any persona method on Gemma 4 specifically. Rapport's own evaluation (section 4) would be the first.
- The UK MHA s.5 text and the Mental Health Act 2025 changes were not fetched from legislation.gov.uk (blocked). The ASPE SP standards, MEED and the BAP catatonia guideline were read only as summaries or abstracts. Verify before any of them shapes a case.
- No primary guideline on handling abuse disclosure in Indian inpatient settings was read. That station is draft content for faculty to write.
