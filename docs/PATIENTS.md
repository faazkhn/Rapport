# Seeded patients, conversation styles and ward events

Branch `personalities`, 2026-10-22. The research behind it is `docs/literature/personalities-and-randomized-patients.md` (recommendations R1–R10). Everything here is **draft** and needs faculty review. That covers the style numbers, the slot lists, the events and the `ward_01` case.

**One rule runs through all of it: randomize the patient, never the answer key.** A seed changes the person the doctor meets: family details, a hobby, the home town, and how they talk. It never changes the diagnosis, the facts the marking depends on, the risk, the exam findings, the scales or the rubric.

## Seeded patients

`brain.load_case(case_id, variant, seed=None, mode="practice")` is a pure function.

- **No seed.** You get the authored case, exactly as before.
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
| plain | none | 1.0 / 1.0 | 1.0 | 60 |
| reserved | trust −5, engagement −10 | 0.8 / 1.2 | 1.0 | 20 |
| pleasing | trust +5 | 1.2 / 0.8 | 0.8 | 35 |
| upset | trust −10, agitation +15 | 0.7 / 1.2 | 1.3 | 35 |
| verbose | engagement +10 | 1.0 / 1.0 | 1.0 | 70 |
| tangent | none | 1.0 / 1.0 | 1.0 | 70 |

- **Start offsets** are relative to the case's authored style. The authored case starts exactly where its author wrote.
- **Gains** scale the model's trust change after the reaction step (`twin.update`).
- **The word cap** stops speech at the first sentence end past the cap, in both the stream and HTTP paths. It also caps the length band in the reminder.
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
2. Its `say` line goes into the turn as "WHAT HAPPENS NOW".
3. An optional body `action` (`stand_up`, `sit_down`) goes to Unity through the exam channel.
4. The Twin log records a `ward_event`.

Typed `/reply` does not run events yet, because it is stateless.

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

## Measured

See the results section below.
