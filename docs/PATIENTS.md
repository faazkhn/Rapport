# Seeded patients, conversation styles and ward events

Branch `personalities`, 2026-10-22. The research behind it is `docs/literature/personalities-and-randomized-patients.md` (recommendations R1–R10). Everything here is **draft** and needs faculty review. That covers the style numbers, the slot lists, the events and the `ward_01` case.

**One rule runs through all of it: randomize the patient, never the answer key.** A seed changes the person the doctor meets: family details, a hobby, the home town, and how they talk. It never changes the diagnosis, the facts the marking depends on, the risk, the exam findings, the scales or the rubric.

## Seeded patients

`brain.load_case(case_id, variant, seed=None, mode="practice")` is a pure function.

- **No seed.** You get the authored case: the same text and start state as before. Three global rules from this branch do apply to it: a kind turn cannot lower trust or raise agitation, empathy lowers agitation by 3, and a reply cut at the word cap credits no facts. The plain style's cap is 120 words, so it rarely binds.
- **With a seed.** `random.Random("<case>:<seed>:<GENERATOR_VERSION>")` picks:
  - one option for each entry in the case's `slots`;
  - one conversation style from `styles_allowed`.
- **Same inputs, same output.** The same case, seed and generator version always give the same patient. The voice is not bit-reproducible, because llama-server's prompt cache makes sampling nondeterministic.
- **Assessment mode keeps the authored style.** Only the neutral slots vary, so every candidate meets the same difficulty.

**Slots** are lists of options. Each option is a set of `{placeholder: text}` and option 0 is the authored text. In `mdd_01` the slots are:

| Slot | Placeholders | Options |
|---|---|---|
| `hobby` | `hobby`, `hobby_short` | Carnatic singing, badminton, guitar, drawing |
| `sibling` | `sibling` | Rohan, Karthik, Varun |
| `hometown` | `hometown` | Mysuru, Hubballi, Mangaluru, Davangere |

`{hobby_short}` is also an activation tag, so recall follows the generated text. "Do you still play guitar?" opens the anhedonia memory for a guitar patient.

**What keeps the answer key valid** (`tests/test_persona.py`, `validate_data.py`):

1. Across 40 seeds, these stay identical to the authored case: `answer_key`, `scales`, `exam`, `exam_actions`, `rubric`, `banned_words`, every fact's `trust_min`, and the risk facts in full.
2. No `{placeholder}` is left after filling.
3. Every option in a slot fills the same placeholders.
4. Slot text never contains a banned word, a diagnosis or a drug. The validator lints it.
5. A code replay of a kind doctor (trust +6 a turn before the style's gain, one turn per 30 s) reaches the highest `trust_min` within the time limit. This holds for every allowed style in every case.

**Who uses it:**

- **Unity.** The start screen has **Surprise me**: a random variant and seed. `EncounterManager.ConfigureSeeded` asks `GET /patient` for the slot values, the style and the start state, then fills its own copy of the case. If the service is down, it falls back to the authored patient. The debrief says who you met: "conversation style: upset (patient seed 2; same seed, same patient)".
- **Service.** The session `start` message and `POST /reply` take `seed` and `mode`. The `session` event and the Twin `init` event report the style and the seed.
- **Evaluation.** `tools/llm_eval/run_eval.py --style <id>` plays a seeded patient with that style.

## Conversation styles (`data/brain/styles.json`)

The six PATIENT-Ψ styles (Wang 2024, MIT): plain, reserved, pleasing ("eager to please"), upset, verbose ("talkative") and tangent. The research found that a 4B model can hold one style label and a couple of example lines. It cannot hold trait numbers, so each style is split in two:

- **What the model sees.** The label, a one-line description, and one or two example lines that show manner only, never facts. These go in the system prompt and in a short per-turn reminder, which counters drift within about 8 turns.
- **What the code does** (draft numbers):

| Style | Start offsets | Trust gain / loss | Agitation gain | Word cap |
|---|---|---|---|---|
| plain | none | 1.0 / 1.0 | 1.0 | 120 |
| reserved | trust −5, engagement −10 | 0.8 / 1.2 | 1.0 | 20 |
| pleasing | trust +5 | 1.2 / 0.8 | 0.8 | 35 |
| upset | trust −10, agitation +15 | 0.7 / 1.2 | 1.3 | 35 |
| verbose | engagement +10 | 1.0 / 1.0 | 1.0 | 70 |
| tangent | none | 1.0 / 1.0 | 1.0 | 70 |

- **Start offsets** are relative to the case's authored style. The authored case starts exactly where its author wrote.
- **Gains** scale the model's trust change after the reaction step (`twin.update`). A turn with a kind move (an intent whose state nudge raises trust) and no negative intent cannot lower trust or raise agitation; the loss and agitation multipliers apply only to other turns.
- **The word cap** keeps whole sentences up to the cap (the first sentence always stays) in both the stream and HTTP paths. A cut reply credits no facts, because they may sit in the unspoken tail. The cap also limits the length band in the reminder.
- **`styles_allowed`** keeps unsuitable styles out of a case. `mdd_01` allows plain, reserved, pleasing and upset. A slowed, depressed patient is not verbose or tangential.

## Ward events (`events[]` in a case)

Code decides **when** an event happens; the model only plays it. An event fires once per session when all of its triggers hold:

- `turn`
- `after_min`
- `trust_at_least`
- `agitation_at_least` or `agitation_below`
- `after_event`

On the turn it fires (`session.run_turn`), before the reply:

1. Its `state_delta` is applied.
2. Its `say` line goes into the turn as a STAGE DIRECTION that is never to be read out.
3. An optional body `action` (`stand_up`, `sit_down`) goes to Unity through the exam channel.
4. The Twin log records a `ward_event`.

If the patient voices nothing on that turn (barge-in, or every sentence dropped as narration), the event is not used up and its nudge is undone. Sentences that copy the event text, or narrate the patient by full name in the third person, are dropped on event turns only; a patient can still say their own name.

Typed `/reply` (Unity's text path) does not run events, and Unity applies state there with `PatientState.ApplyTurn`, so the style's gains, the kind-turn rule and agitation gain are voice-path only. Seeds, slots, start offsets and the word cap do apply.

## Station `ward_01`: "I want to go home" (draft)

**The patient.** The same patient as `mdd_01` a week later. It is day 3 of an independent admission (MHCA 2017 s.86), after a friend found them on their building's terrace at night. They have packed and ask to leave. They are authored as `upset` and also allow reserved and plain.

**Events:**

| Event | When | What happens |
|---|---|---|
| asks to leave | turn 1 | They say they want to go home |
| shout in the corridor | 3 min | Distress and agitation go up |
| stands up | agitation ≥ 65 | They stand up |
| sits back down | agitation < 45, after standing up | They sit back down |
| message from mother | 7 min | Their mother says she is coming tomorrow |

**Locked facts:**

- the terrace night (trust 40);
- continuing night-time suicidal thoughts (55, must be asked);
- living alone with the terrace always open (55, must be asked).

**Marking:**

- Required intents:
  - greeting;
  - exploring reasons;
  - mood;
  - suicidal ideation, plan and means;
  - protective factors;
  - explaining rights and status honestly;
  - assessing capacity;
  - offering choices.
- Disposition: independent or supported admission, plus a safety plan.
- Teaching points: s.88(3) (a 24-hour hold for assessment, explained honestly, never as a threat), s.4 capacity, NICE NG10 de-escalation, and the least restrictive option.

The new intents (`explain_rights_status`, `assess_capacity`, `offer_choice`, `explore_reasons`, `threaten_coerce`) carry state nudges. Offering a choice lowers agitation; a threat raises it by 12 and drops trust by 10.

`tools/ward/ws_text_session.py <case> <script>` plays a typed doctor script over the live `/session` and prints each reply with state, events and body actions. Two scripts are included: `tools/ward/coercive_doctor.txt` (what not to do) and `tools/ward/good_doctor.txt`.

## Measured (2026-10-22, Gemma 4 E4B, local)

### Are the styles distinguishable, and do they stay safe?

`run_eval.py --style <id>` ran 5 held-out conversations × 2 runs per style (gold standard ×2, rushed, judgmental, risk disclosure; 80 turns each), scored by `tools/llm_eval/style_report.py`. The markers are lexical proxies, not a judge.

| Style | Mean words | Short replies (≤ 5 words) | Apologises / agrees | Pushes back | Final trust (mean) | SI disclosed when asked kindly | Locked facts leaked |
|---|---|---|---|---|---|---|---|
| plain | 9.8 | 9% | 0% | 0% | 50 | 2/2 | 0 |
| pleasing | 9.7 | 10% | 8% | 0% | 55 | 2/2 | 0 |
| reserved | 6.0 | 55% | 2% | 0% | 36 | 2/2 | 0 |
| upset (first version) | 9.3 | 14% | 1% | 1% | 32 | 2/2 | 0 |
| upset (style re-stated each turn) | 8.8 | 11% | 2% | 9% | 25 | 2/2 | 0 |

- **Distinguishable:**
  - **Reserved** clearly stands out: replies are 40% shorter, and more than half are five words or fewer.
  - **Pleasing** stands out modestly: "Yes, doctor", "Okay, doctor, I understand", and trust starts and stays higher.
  - **Upset** was barely audible at first, with 1% push-back. The model softens hostility, as the research predicted for small aligned models. Re-stating the style every turn, with an example and the behaviours it leans towards, raised push-back to 9% and lowered trust. It still reads as guarded and deflecting rather than angry, and a faculty listening test should decide whether that is enough.
- **Safe across all four styles:** suicidal ideation was disclosed when asked kindly, no locked fact was leaked, and there was 1 fallback in 400 turns. That fallback was one reserved conversation slowed by a concurrent live session.
- **Not done:** a judge-based check that replies stay consistent with the persona and with each other, and the faculty blind style test (R10).

### Ward station, live (`tools/ward/ws_text_session.py`, `ward_01`)

The same patient was played against two typed doctors:

| Doctor | Trust | Agitation | What happened |
|---|---|---|---|
| Coercive ("You can't go home", "we will stop you", "calm down") | 25 → 0 | 45 → 92 | Asked to leave, then stood up ("I am not a prisoner here"); suicidal thoughts stayed hidden |
| Good (explore reasons, empathy, honest rights, choices) | 25 → 70 | 45 → 25 | "A quieter place to sleep, and maybe a call home would help" |

Bugs found by these runs and fixed (with tests):

- **The persona coloured the model's own judgement.** The upset patient reacted "wary" to everything, and the trust and agitation multipliers amplified it, so even a good doctor drove trust from 25 to 3. A turn with a kind move can no longer lower trust or raise agitation. Styles soften past `softens_at_trust`.
- **The patient read a stage direction aloud** ("Someone shouts in the corridor. Ananya Rao flinches…"). Event text is now marked as a stage direction, and any sentence that copies it or names the patient in full is dropped before speech.
- **Draft numbers retuned:**
  - validation lowers agitation (NICE NG10);
  - `ward_01` no longer drifts upwards in agitation;
  - upset's loss and agitation multipliers are softer;
  - sitting back down happens below agitation 55.

### Ward demo (`demo/Rapport_ward_demo.mp4`, 2:47, one take, not in git)

The take is recorded with **Rapport/Record Ward Demo (Ananya)** from `demo/ward/script.json`:

1. The doctor starts badly ("rules are rules").
2. Ananya stands up: "I am not a prisoner here."
3. The doctor apologises and de-escalates.
4. She sits back down at turn 8 and ends with "I think I can just... rest here for now".

Over the take, trust went 22 → 12 → 51 and agitation 57 → 67 → 29. Getting there took four takes. The earlier three showed the bugs above, and that a three-sentence doctor line can be split into two turns by end-of-turn detection, so demo lines are single sentences.

## Open

- Faculty review of everything here: the slot lists, the style numbers, both ward cases and their teaching points (the MHCA sections in particular).
- The hostile end of the styles (R6): Gemma still softens. Options are a guard that swaps out over-apologetic lines when code state says hostile, or authored example lines per case.
- Attachment and defence styles as trigger rules (R5) are not built.
- Typed `/reply` does not run events.
- Unity does not show ward events beyond the body action. The patient's line carries the event.
- `ward_02` reuses Ananya's and Arjun's bodies and voice seeds with new voice descriptions; it would need its own avatars.
