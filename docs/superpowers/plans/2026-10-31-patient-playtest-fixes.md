# Patient playtest fixes: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the four problems from the owner's 2026-10-26 playtest:
1. Patients withhold what they are allowed to share and fall back on "Why do you want to know that?".
2. After "OK, you can go", the patient loops back to "I want to go home".
3. Start screen Look 2 is broken in every case.
4. The new bodies (Amber `female_20s_b`, Realistic Man `male_30s_a`) are not really in use.

**Architecture:**
- Service side: four prompt and data fixes in `brain.py` and `styles.json`.
- One session bug: a barge-in after the utterance is complete must not cancel the reply.
- One new event trigger, `doctor_allows_leave`, detected lexically before the LLM call, plus a `then` note that stays in later turns.
- Unity side: the hair is rebuilt without collapse-decimation, mesh Read/Write is enabled for the app build, `ward_02` gets the new bodies, then the app is rebuilt and checked.

**Tech Stack:** Python 3 (FastAPI service, pytest), Unity 6000.6.2f1 (C#, EditMode tests), Blender 4 headless.

**Spec:** the owner's message of 2026-10-31 plus the evidence below. There is no separate spec doc.

## Evidence (what the playtest logs show)

Sources:
- `logs/twin/20261026_113900_ward_01.jsonl` (Arjun, 89 turns);
- `logs/twin/20261026_112010_ward_02.jsonl` (Priya, 96 turns);
- `~/Library/Logs/PsychSim/Rapport/Player.log`.

- **E1. Unlocked facts are dodged.** At T2, "Why do you want to go home?", `f_reasons_ward` (trust_min 5) was recalled at trust 29. The reply was "I feel better now". The causes:
  - the `upset` style re-states its first example, "Why do you need to know that?", every turn;
  - `upset` leans towards asks_back, deflects and hostile until trust reaches 40;
  - the trust band below 30 says "deflects personal questions";
  - the recall block lists the fact but never says the doctor just asked about it.
- **E2. Background is withheld.** The background says the father is a retired teacher, but at T24 the patient said "I don't know much about him". Hard rule 3 makes anything that is not a listed fact "answer vaguely".
- **E3. Late barge-ins cancel replies.** `Session.is_speaking()` stays true until the LLM finishes the JSON tail after the utterance. A doctor who speaks then cancels the turn, and the JSON fails to parse. The result is a fallback with a zero state change and no facts credited, with "..." appended. This happened on about half of all turns in both sessions (the "...", "None" and `answers_plainly/none` rows).
- **E4. "You can go" is forgotten.** T44 to T89: "You can go" got "Are you serious?", then "I just want to go home" again. Nothing records that leave was granted. Intents are tagged after the reply, so an intent cannot trigger anything before the reply.
- **E5. Amber's hair is shredded.** All four hair meshes were collapse-decimated from about 110–122k to 40k triangles (`cc_rebuild.py reduce_other`), so in play she looks almost bald.
- **E6. Meshes are not readable in the app.** All four body FBX files import with `isReadable: 0`, so `SleeveRoller` logs "Not allowed to access vertices" and sleeves never roll in the app. In the editor they do.
- **E7. Look 2 in the editor.** Every look spawns and plays the entrance in all cases (checked over MCP on 2026-10-31). The build is checked in Task 5.

## Global Constraints

- Commits are authored `faazkhn <faazkhn1000@gmail.com>` with no Claude co-author or "Generated with" lines (owner rule, memory).
- Product name Rapport, brain "Digital Twin". Clinical content stays draft.
- "Randomize the patient, never the answer key": no change to `answer_key`, `trust_min`, risk facts, rubric.
- No new dependencies. Service tests: `cd server/patient-service && .venv/bin/python -m pytest -q`; Unity EditMode via MCP `run_tests`.
- LFS budget (~220 MB left): the rebuilt Amber FBX may grow; keep textures as they are.

## Review Focus

1. A doctor who says "Why do you want to go home?" or "You can go home when you're better" must NOT trigger leave-granted (questions, conditionals, negations). Pinned by the Task 3 lexical tests.
2. A barge-in while audio is still playing must still cut the reply (real interruption). Pinned by the existing `test_barge_in_snapshot` plus a Task 1 test.
3. Locked facts must stay locked after the "answer what was asked" wording. Pinned by the existing `test_locked_facts_never_reach_the_model` and the live eval in Task 2.
4. The `then` note must not repeat the STAGE DIRECTION on the turn the event fires. Pinned in Task 3.
5. Unity's `JsonSchemaLite` must accept the new event keys: the case schema is updated and the Unity EditMode content tests run in Task 5.

---

### Task 1: A late barge-in no longer throws the reply away (E3)

**Files:**
- Modify: `server/patient-service/session.py`:
  - `is_speaking`;
  - `run_turn`: set `self.said_all`.
- Test: `server/patient-service/tests/test_session.py`

**Interfaces:**
- Produces: `Session.said_all: bool`. It is True once the utterance string has closed and every sentence has been sent to TTS. `is_speaking()` is `playing_until > now or (turn running and not said_all)`.

- [ ] Write `test_speaking_after_the_reply_is_said_keeps_the_reply`:
  - `FakeLLM(delay=0.01)` and a 0.0 s TTS clip;
  - wait until `s.said_all`, then `await s.on_speech_start()`;
  - assert the reply has no "...", `revealed_fact_ids == ["f_sleep"]`, trust 33, and no `stop` event.
- [ ] Run it: FAIL (the reply is cancelled).
- [ ] Implement:
  - `self.said_all = False` at the start of `run_turn`;
  - set it True after the flush in which `parser.done` (and after the final flush loop);
  - `is_speaking` as above.
- [ ] Run `test_session.py`: PASS. `test_barge_in*` still pass, because a mid-audio barge-in still cuts.
- [ ] Commit `fix(session): a barge-in after the reply is said no longer discards its state and facts`.

### Task 2: Patients answer what they may share (E1, E2)

**Files:**
- Modify `server/patient-service/brain.py`:
  - `describe_state`, the trust < 30 band;
  - `HARD_RULES` rule 3;
  - `recall_block`.
- Modify `unity/PsychSim/Assets/StreamingAssets/data/brain/styles.json`, the `upset` and `reserved` examples.
- Test: `server/patient-service/tests/test_brain.py`

Exact wording to use:
- **Trust < 30 band:** "guarded; answers what is asked in a few words, without extra detail; vague only about things not listed as shareable."
- **Hard rule 3 (append):** "Everyday details in the Background (family, work, home town, routine) are not secrets: share them plainly when asked, keep them consistent, and never contradict them."
- **`recall_block` first line:** "WHAT COMES TO MIND (the doctor's question touches these; answer with them now, in your own words and your style; a guarded patient gives a short or partial answer but does not dodge):".
- **`upset` examples (they answer while pushing back):**
  - "I already told the other doctor... fine. It's been bad, okay?"
  - "Why does that matter? ...Alright. Not really, no."
- **`reserved` examples:**
  - "Fine. ...Not much sleep."
  - "I don't know. Maybe."

- [ ] Test `test_recall_block_tells_the_patient_to_answer`: the recall block for an open fact contains "answer with them now". Test `test_low_trust_band_does_not_say_deflect`: `describe_state` at trust 10 contains no "deflects".
- [ ] Run: FAIL. Implement. Run the brain, persona and session tests: PASS.
- [ ] Live check (needs llama-server):
  - replay the owner's first 12 ward_01 doctor lines through `tools/ward/ws_text_session.py`;
  - count the replies that dodge a question whose fact was recalled open;
  - target: fewer than in the log (T2, T4, T8, T13 and T14 dodged);
  - record the before and after counts in `docs/PATIENTS.md`.
- [ ] Commit `fix(brain): patients answer what they are allowed to share`.

### Task 3: "You can go" sticks (E4)

**Files:**
- Modify:
  - `server/patient-service/twin.py`: `allows_leave(text) -> bool`, the `due_events(..., doctor_text="")` trigger, and `ongoing_notes(case, fired, now_ids) -> list[str]`;
  - `server/patient-service/session.py`: pass the text and the notes;
  - `server/patient-service/brain.py`: `build_messages(..., ongoing=None)`.
- Modify: `unity/PsychSim/Assets/StreamingAssets/data/schemas/case.schema.json`. Add `when.doctor_allows_leave: boolean` and the event field `then: string (<=300)`.
- Modify: `cases/{mdd_01,alc_01,ward_01,ward_02}.json`. Add the event `leave_granted`.
- Test: `server/patient-service/tests/test_events.py` and `tests/test_session.py`.

`allows_leave` is true when any sentence that is not a question matches a leave grant and has no negation or conditional. The two patterns:

```
grant: you (can|may|could|are free to|'re free to) (now )?(go|leave)|you('re| are) (free to go|discharged|good to go)|
       (go|get) (back )?(to your )?home|(go|leave) now|leave (my|the|this) (room|cabin|office)|get out|
       i('ll| will|'m going to| am going to) (let you go|discharge you|send you home)|we('re| are) done|
       (appointment|consultation) is (done|over|finished)
block: can't|cannot|can not|not|won't|don't|unless|until|if|when|once|after|before|want to|wanna
```

`leave_granted` in each case:
- **when:** `{"doctor_allows_leave": true}`, action `stand_up`, state_delta `{"agitation": -10}`.
- **say:** "The doctor has just said {name} can go. {name} is taken aback, then relieved, picks up {their} things and stands to leave; {they} may ask what happens next."
- **then:** "The doctor has already said {name} can go; {they} is getting ready to leave and does not ask to leave again."
- `mdd_01` and `alc_01` use the same lines without the bag. `ward_*` mention the packed bag.

- [ ] Tests:
  - **`test_allows_leave`** is true for: "You can go.", "Yes, you may leave.", "Okay, go home now. Your appointment is done.", "Go, go to your home.", "Leave my room.", "Doctor, you have to go home right now.".
  - It is false for: "Why? Why do you want to go home?", "So if I allow you to go home, will you go?", "You can't leave yet.", "You can go home when you feel better.", "I just wanna go home and get sleep.", "Let's just sit down and then we'll talk.".
  - **`test_leave_event_fires_on_the_doctors_words`**: `due_events` with `doctor_text="You can go."` fires `leave_granted`; with "How are you?" it does not.
  - **`test_then_note_persists_after_the_event`** (session): turn 1 "You can go." gives the STAGE DIRECTION; turn 2's prompt has "ALREADY HAPPENED" plus the `then` text and no STAGE DIRECTION.
- [ ] Run: FAIL. Implement. Run the full service suite plus `validate_data.py`: PASS.
- [ ] Commit `feat(ward): the patient remembers being told they can go`.

### Task 4: New bodies render and are used (E5, E6)

**Files:**
- Modify `tools/blender/cc_rebuild.py`, `reduce_other`: a mesh whose materials include `Hair` or `Brow` is kept whole, because hair cards do not survive collapse decimation.
- Regenerate `art/Amber/Amber.Fbx` and run `tools/blender/stage_patient.py` to produce `unity/PsychSim/Assets/Art/Patients/female_20s_b/female_20s_b.fbx`.
- Modify `Editor/PatientImport.cs`: `mi.isReadable = true`. Set the 4 `*.fbx.meta` files to `isReadable: 1` (SleeveRoller in the app).
- Modify `cases/ward_02.json`: Priya → `female_20s_b`, Rahul → `male_30s_a` (PATIENTS.md: "ward_02 ... would need its own avatars").

- [ ] Rebuild Amber in Blender (command in the script docstring), then stage it and reimport in Unity. Prefab and material GUIDs are kept: re-run only the FBX copy and reimport.
- [ ] Check: Amber's hair meshes have their source triangle counts, and a play-mode screenshot shows full hair.
- [ ] Commit `fix(art): Amber's hair kept whole; meshes readable for sleeve rolling in builds; ward_02 wears the new bodies`.

### Task 5: Rebuild the app, verify Look 2 in the real build, docs

- [ ] Run Unity EditMode tests: all pass.
- [ ] Rebuild via the **Rapport > Build macOS (Development)** menu.
- [ ] Launch `Builds/Rapport.app`. Click Look 2 with `cliclick` for each case and screenshot the patient. Check Player.log for exceptions and for no "Not allowed to access vertices".
- [ ] If Look 2 still fails in the build, diagnose from Player.log and fix in this task.
- [ ] Update `docs/PATIENTS.md` (leave event, measured dodge counts, new bodies on ward_02) and `HANDOFF.md` §4h.
- [ ] Commit `docs: playtest fixes 2026-10-31`.

### Task 6: A detailed life memory for every patient (owner, 2026-10-31, mid-session)

"Give each patient a vast detailed memory about their life, make them as human as possible."

**Files:**
- Create `data/life/{rao,nair,gowda}.json`, each `{id, status, note, memories: [{id: "l_*", activation_tags, text, variant?, trust_min?}]}`. `rao` is shared by `mdd_01` and `ward_01` (the same person a week apart).
- Modify the cases (`"life": "<id>"`) and `case.schema.json` (`life`: string).
- Modify `brain._resolved`: attach the memories, fill placeholders and slots, filter by variant.
- Modify `twin.recall`: up to two `life` ids, scored like facts, never locked or credited.
- Modify `brain.recall_block`: `- (memory) …` lines.
- Modify hard rule 3: Background and memory details are shareable. Anything clinical follows the facts even if the Background mentions it (`alc_01`'s background names the father's drinking, a fact locked until trust 30).
- Modify `validate_data.py`: unique `l_` ids, known placeholders, no clinical word (banned words, diagnoses, drugs).

**Content rule:** everyday life only. Nothing may restate or contradict a trust-gated fact. Rao never mentions the terrace or the manager; Nair never mentions the uncle or the business; Gowda never mentions drinking, the father's death, the car or arguments.

- [x] Tests:
  - `test_life_memories_come_to_mind_and_are_never_facts`;
  - `test_life_follows_variant_and_slots`;
  - a validator lint check with an injected clinical word and an unknown placeholder (manual).
- [x] Live check: everyday questions per case get specific, consistent answers, and locked facts stay locked.
