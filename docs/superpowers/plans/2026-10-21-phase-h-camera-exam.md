# Phase H: Camera and Exam Commands Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The doctor can ask for any common exam action in their own words ("Kindly hold out your hands", "Show me your tongue", "Stand up and walk a few steps"). The patient does it in order, holds until told to relax, and the camera cuts to a close-up. A rule-based router makes the decision in ≤ 30 ms without calling the LLM.

**Architecture:** A rule-based router in the service, `exam_router.py`, turns the doctor's final transcript into ordered actions with slots, an ask-back question, or a relax. Data lives in `data/exam_router.json`. The service gates each action on trust and agitation, sends an `exam` message to Unity before the LLM call, and tells the Digital Twin what was asked so the patient's spoken acknowledgement or refusal fits. The router replaces the LLM's `exam_action` choice. In Unity, `ExamController`:
- plays the actions from a pure-C# `ExamQueue`;
- presents the hands with humanoid IK;
- drives the face (mouth, tongue) and gaze for actions that have no clip;
- triggers Cinemachine close-ups through `CameraDirector`.

New body clips (stand up, standing idle) come from the existing Blender clip generator.

**Tech Stack:** Python 3.12 (service, pytest), Unity 6000.6.2f1 (C#, Cinemachine 6.6.0, humanoid `OnAnimatorIK`, NUnit EditMode), Blender 5 headless (`tools/blender/make_clips.py`).

**Spec:** `KICKOFF_PROMPT_v4.md` Phase H; complaints (g) and (h) in `docs/STATE_AUDIT.md`.

## Global Constraints

- Router: "embeddings plus rules (≤ 30 ms, no LLM call)". Test set ≥ 300 utterances (≥ 20 negatives): accuracy ≥ 95%, false triggers ≤ 1%, results in `docs/exam-actions.md`.
- Actions and slots, verbatim: `hold_out_hands{palms, which}`, `show_forearms` / `roll_up_sleeves{which}`, `look_at_light`, `follow_finger`, `open_mouth`, `stick_out_tongue`, `stand_up`, `sit_down`, `walk_few_steps`, `relax`.
- "Paraphrases and Indian-English phrasings; several commands in one sentence, run in order. Ask back when ambiguous ('Which hand?')."
- "Compliance gated by trust and agitation, with the verbal acknowledgement coming from Digital Twin."
- "IK presents the hands toward the doctor; the patient holds until told to relax, and cues stay visible during the hold. The IK also fixes `cue_wipe_tears`. Author missing clips for both bodies."
- Camera: "seated eye height about 1.20 m, 40–45° vertical FOV, eyes in the upper third; smooth, limited mouse-look, plus an optional 'lean in'; Cinemachine close-ups per exam action (hands, forearms, eyes, face or tongue, full body for gait), then return; the patient looks at the doctor by default; gaze cues override it; separate cinematic cameras for demos; one still per camera state in `docs/camera.md`."
- Everything local, with no new downloads (the Mac is offline, 2026-10-21). Clinical content stays draft. New `trust_min` values are draft.
- Commits are authored `faazkhn <faazkhn1000@gmail.com>` with no Claude attribution lines. The owner said not to wait for checkpoints (2026-10-20).

## Review Focus

1. **A history question that uses exam words** ("Do your hands shake?", "Have you had trouble standing up?", "Did anyone tell you to relax?") triggers no action. Pinned by the negatives in Task 1's test set.
2. **The doctor never says "relax":** the hold ends by itself after 30 s and the hands return to the lap. Pinned in Task 4 (`ExamQueue` test).
3. **A new command arrives while the patient is holding or mid-action:** the current hold is released, then the new action plays. The queue never stalls or runs two actions at once. Pinned in Task 4.
4. **A refused action** (trust below `trust_min`, or agitation ≥ 70): no animation and no close-up, and the patient refuses in words. Pinned in Task 2 (service) and Task 4 (Unity ignores `comply: false`).
5. **A seated-only action while standing** (`roll_up_sleeves`, `show_forearms` after `stand_up`): the patient sits down first, then does it. Pinned in Task 4.

---

### Task 1: Exam router and its test set

**Files:** Create `server/patient-service/exam_router.py`, `unity/PsychSim/Assets/StreamingAssets/data/exam_router.json` (lexicon), `tests/exam-router/utterances.yaml`, `tools/exam_router_eval.py`, `docs/exam-actions.md`. Test `server/patient-service/tests/test_exam_router.py`.

**Interfaces — Produces:** `exam_router.route(text: str) -> dict` returning `{"actions": [{"id": str, "slots": dict}], "ask_back": str | None, "relax": bool}`.
- Action ids are exactly the spec list, minus `relax`, which sets `"relax": True` instead.
- Slots: `which` ∈ `left|right|both`; `palms` ∈ `up|down` (default `down`).
- `show_forearms` and `roll_up_sleeves` are separate ids that share one clip in Unity.
- `ask_back` is set and `actions` is empty when a sided action has a singular object and no side ("Hold out your hand", "Roll up your sleeve"). The value is `"Which hand?"` or `"Which arm?"`.
- Plural or none means `which: "both"`.
- `exam_router.load()` reads the lexicon once and caches it.

`tools/exam_router_eval.py <yaml> [--md docs/exam-actions.md]` prints accuracy (exact match of actions + slots + ask_back + relax), false triggers (negatives with any action or relax / number of negatives), and p50/max ms per call. With `--md` it writes the table and every miss.

**Approach (decided):** no embeddings. Ruling: no embedding model is cached and the Mac is offline. The spec's ≤ 30 ms is met by rules. The ledger records this, and the doc says embeddings are a fallback to add if accuracy on new phrasings drops.
1. Normalise: lowercase; expand contractions; strip filler ("kindly", "please", "once", "just", "for me", "can you", "could you", "would you", "will you", "i want you to", "i'd like you to", "do one thing", "now", "okay", "alright").
2. Split into clauses on `and then|then|and|after that|,|;` and run the clauses in order.
3. A clause is a command only if it is imperative after normalisation. Questions about history are rejected: a clause starting with `do you|did you|have you|has|does|is|are|when|how long|why|what` (after filler removal), or a third-person subject.
4. Match `(verb set) … (object set)` patterns from the lexicon per action. Slots come from `left|right|both|either|palms? (up|down)|face (up|down)`.

- [ ] Write `tests/exam-router/utterances.yaml` first: **≥ 300 items**, each `{text, expect: {actions: [...], ask_back, relax}}`.
  - At least 25 per action plus 15 relax phrasings.
  - At least 20 multi-command lines.
  - At least 15 ask-backs.
  - **At least 30 negatives:** history questions that use exam words, the patient's own words, small talk, "stand up for yourself".
  - Indian-English forms: "Kindly put your hands forward", "Show tongue once", "Do one thing, stand up", "Put out your hands straight".
- [ ] Write the failing unit tests in `test_exam_router.py`:
  - `route("Kindly hold out both your hands, palms down")["actions"] == [{"id": "hold_out_hands", "slots": {"which": "both", "palms": "down"}}]`
  - `route("Hold out your hand")` gives `ask_back == "Which hand?"` and `actions == []`.
  - `route("Stand up and walk a few steps for me")` gives the ids `["stand_up", "walk_few_steps"]`, in order.
  - `route("Do your hands shake?")` and `route("Have you had trouble standing up?")` give no actions and `relax` False.
  - `route("Okay, you can relax now")["relax"] is True`.
  - `route("Show me your tongue")` gives `stick_out_tongue`.
  - `test_eval_set_meets_gate`: runs the eval over the YAML and asserts accuracy ≥ 0.95, false trigger rate ≤ 0.01, max ms ≤ 30.
- [ ] Run: `cd server/patient-service && .venv/bin/python -m pytest -q tests/test_exam_router.py`. Expected: FAIL (`No module named 'exam_router'`).
- [ ] Implement the lexicon and the router. Run again. Expected: PASS. Run `tools/exam_router_eval.py tests/exam-router/utterances.yaml --md docs/exam-actions.md`. Expected: the doc is written and the gate is met.
- [ ] Commit `feat(exam): rule-based exam action router with 300+ utterance test set`.

### Task 2: Service integration: compliance, Twin acknowledgement, the exam message

**Files:** Modify `server/patient-service/session.py` (`run_turn`), `brain.py` (`build_messages` tail, `build_reply_schema`, `guard`), `unity/.../cases/mdd_01.json` (`exam_actions` for every new id), `unity/.../data/state_rules.json` (+ schema) with `exam_refuse_agitation: 70`. Test `tests/test_session.py`, `tests/test_brain.py`.

**Interfaces:**
- Consumes `exam_router.route`.
- Produces the WebSocket message `{"type": "exam", "turn": int, "actions": [{"id", "slots", "comply": bool}], "relax": bool}`. It is sent right after `transcript` and before `thinking` whenever there are actions or `relax`.
- Produces `brain.exam_gate(case, state, actions) -> list[dict]` (adds `comply` and, when refused, `reason` ∈ `trust|agitation|unknown`).
- `brain.build_messages(..., exam=None)`: when given, the transient tail gets a line. For compliance: `The doctor asked you to: <ids>. You are doing it now: acknowledge briefly in your own words.` For a refusal: `... You will not do <id>: refuse in your own words` + the case's `refusal_line` as an example.
- For ask-back: `The doctor's request was unclear; ask them: "<ask_back>"`.
- The reply schema's `exam_action` becomes `{"type": "null"}`. The service sets `reply["exam_action"]` to the first complied id, so logs and scoring keep working.
- A turn whose transcript is only exam commands still gets an LLM reply (the acknowledgement).

**Draft `trust_min` (mdd_01):** `hold_out_hands` 10, `look_at_light` 10, `follow_finger` 10, `open_mouth` 15, `stick_out_tongue` 15, `show_forearms` 30, `roll_up_sleeves` 30 (keep its refusal line), `stand_up` 5, `sit_down` 0, `walk_few_steps` 10.

- [ ] Failing tests (FakeLLM):
  - `test_exam_message_precedes_thinking`: at trust 40, "Hold out your hands" makes the event order `transcript`, `exam`, `thinking`, with `comply` True.
  - `test_exam_refused_low_trust`: at trust 5, "Roll up your sleeves" gives `comply` False with reason `trust`. The patient prompt tail contains `will not do roll_up_sleeves`.
  - `test_exam_refused_agitated`: agitation 80 gives reason `agitation`.
  - `test_ask_back_goes_to_twin`: "Hold out your hand" gives no `exam` message, and the tail contains `Which hand?`.
  - `test_relax_message`: "You can relax" gives `exam` with `relax` True.
  - `test_llm_exam_action_ignored`: the FakeLLM reply has `exam_action: "hold_out_hands"` and the doctor asked nothing. The reply's `exam_action` is None.
- [ ] Run: FAIL. Implement. Run the service suite: PASS. Run `validate_data.py`: 0 errors.
- [ ] Commit `feat(exam): router-driven exam actions with trust/agitation gating and Twin acknowledgement`.

### Task 3: Missing clips for both bodies

**Files:** Modify `tools/blender/make_clips.py` (new clips `stand_up`, `stand_idle`), `art/Animations/ANIMATIONS.md`, `unity/PsychSim/Assets/Scripts/Editor/PatientAnimatorBuilder.cs` (states and layers). Output `art/Animations/stand_up.fbx`, `stand_idle.fbx` (and copies wherever the builder imports clips from).

**Decided:**
- `stand_up` is the time reverse of `sit_down`. Its last frame is `stand_pose` and its first frame equals `base_sit_neutral` frame 0.
- `stand_idle` is an 8 s loop: `stand_pose` with breathing and a small weight shift.
- `walk_few_steps` reuses `walk_in` (root motion) in code (Task 4): turn, walk about 2 m, turn, walk back, turn to face. Ruling: no turn clip; the turn is a procedural yaw over 1.0 s on `stand_idle`, accepting slight foot slide.
- `open_mouth`, `stick_out_tongue` and `follow_finger` need no body clip (Task 4).

- [ ] Run `make_clips.py` (build, then `verify`, then `model art/Matt/Matt.Fbx ... matt stand_up stand_idle`). Expected: verify passes; on Matt the feet stay flat (no hover > 2 cm, read from the script's contact report).
- [ ] Builder: add the states `stand_up`, `stand_idle`, `walk_segment` (the `walk_in` clip) with triggers `StandUp`, `SitDown`, `Walk`. Set IK Pass on the base layer and the Arms layer. Rebuild both controllers via the menu item. EditMode suite stays green.
- [ ] Commit `feat(anim): stand_up and stand_idle clips for both bodies; animator states and IK pass`.

### Task 4: ExamController: queue, hold, IK, face and gaze actions

**Files:** Create `unity/PsychSim/Assets/Scripts/Cues/ExamQueue.cs` (pure C#), `ExamController.cs` (MonoBehaviour). Modify `Speech/VoiceSession.cs` (parse `exam`, raise `ExamReceived`), `Core/EncounterManager.cs` (wire `ExamReceived` to `ExamController`; stop calling `PlayExamAction` from `reply.exam_action`), `Cues/CueDriver.cs` (wipe_tears IK hook), `Cues/GazeController.cs` (external target override). Test `Assets/Tests/EditMode/CoreLogicTests.cs`.

**Interfaces — Produces:**
- `ExamQueue`:
  - `Enqueue(IEnumerable<ExamStep>)`, `Relax()`, `Tick(float now) -> ExamStep current`, `bool Holding`.
  - `ExamStep { string id; string which; string palms; float holdUntil; }`.
  - Constants `HoldCapS = 30f` and a seated-only set `{roll_up_sleeves, show_forearms}`.
  - Enqueueing while holding releases the hold first.
  - A seated-only step while standing inserts `sit_down` before it.
  - `comply == false` steps are dropped.
- `ExamController.Play(ExamStep)` per id:
  - `hold_out_hands`: arms clip into IK. Targets 0.42 m in front of the chest, toward the camera, at shoulder height − 0.08 m. `which` decides one or both hands; palms rotate by `palms`. Weight 1 during the hold; `TremorController` still applies.
  - `show_forearms` / `roll_up_sleeves`: the existing clip, held at its hold pose until relax.
  - `look_at_light`: the existing clip + `face_squint`, with the gaze on the camera.
  - `follow_finger`: a gaze target moves in an H pattern 0.5 m in front of the camera over 6 s.
  - `open_mouth`: `Jaw_Open` 60 + jaw bone (`CC_Base_JawRoot`) rotation of 12°.
  - `stick_out_tongue`: `open_mouth` + `Tongue_Out` 100 on the tongue mesh.
  - `stand_up`: the `StandUp` trigger, then `stand_idle`.
  - `sit_down`: the `SitDown` trigger.
  - `walk_few_steps`: as Task 3 decided.
  - Each one raises `ExamStarted(id)` and `ExamEnded(id)` for the camera.
- `cue_wipe_tears`: during 0.8–1.5 s of the clip, IK places the right index fingertip 1.5 cm below and 1.0 cm in front of the right eye bone, with a weight curve (0.6–0.8 s up, 1.5–1.7 s down). Re-enable `CueDriver.WipeTears` for live (non-staged) sessions.

- [ ] Failing EditMode tests:
  - `ExamQueue_HoldsUntilRelax`
  - `ExamQueue_HoldCapsAt30s`
  - `ExamQueue_NewCommandReleasesHold`
  - `ExamQueue_RunsInOrder`
  - `ExamQueue_SeatedOnlyInsertsSitDown`
  - `ExamQueue_DropsRefused`
  - `VoiceSession_ParsesExamMessage` (JSON → steps)
- [ ] Run (batchmode `-runTests -testPlatform EditMode`): FAIL. Implement. Run: PASS.
- [ ] Live check in the editor (the MCP bridge or Play mode) for each action on both bodies: screenshot the hold pose. The hands are in front of the chest and visible from the doctor's camera, and the tongue is visible.
- [ ] Commit `feat(exam): ExamController with ordered queue, hold-until-relax, hand IK, face and gaze actions; IK wipe_tears`.

### Task 5: Camera

**Files:** Create `unity/PsychSim/Assets/Scripts/Platform/CameraDirector.cs`, `Editor/CameraStills.cs`, `docs/camera.md`. Modify `Platform/DesktopRig.cs` (lean-in, eye height), `Editor/EncounterSceneBuilder.cs` (Brain + virtual cameras), `UI/DemoDirector.cs` (use the demo cameras).

**Decided:**
- **Brain:** a `CinemachineBrain` on Main Camera with a default blend of EaseInOut 0.6 s.
- **Doctor camera:** a `CinemachineCamera` on the `DesktopRig` transform, priority 10, vertical FOV 42. DesktopRig keeps its own mouse-look and limits, and its head stays at 1.20 m above the floor. Holding `Space` (or the scroll wheel) leans in 0.25 m toward the patient over 0.4 s, and FOV narrows to 38.
- **Close-ups, priority 20 while active, each aimed at its bone:**
  - Hands: hands midpoint, 0.6 m, FOV 30.
  - Forearms: forearms, 0.7 m, FOV 32.
  - Eyes: head, 0.45 m, FOV 22.
  - Face/tongue: jaw, 0.5 m, FOV 24.
  - Full body (gait): hips, 3.2 m, FOV 45.
- `CameraDirector` maps an exam id to a close-up on `ExamStarted` and drops back on `ExamEnded`, or on relax plus 0.5 s.
- **Demo:** two cinematic cameras, an over-the-shoulder and a wide room shot, selected only by `DemoDirector`.
- **Gaze:** the patient looks at the doctor camera unless a gaze cue (`gaze_avoid`, an exam gaze) is active. Check this in `GazeController` and add it only if missing.

- [ ] Failing EditMode test `CameraDirector_MapsActionsToCloseUps`: every exam id maps to the right close-up. Unknown ids map to none.
- [ ] Implement; rebuild the scene via the builder menu; check in Play mode.
- [ ] `PsychSim/Camera Stills` writes `docs/media/camera_<state>.png` (720p) for doctor, lean-in, hands, forearms, eyes, face, full body, demo OTS and demo wide. `docs/camera.md` lists each state with its still and settings.
- [ ] Commit `feat(camera): Cinemachine doctor camera with lean-in, exam close-ups, demo cameras; stills`.

### Task 6: Phase close

- [ ] Service suite, Unity EditMode, `validate_data.py`, router eval gate.
- [ ] Live: service + editor Play mode. Type and say "Hold out your hands" → hold + close-up → "Okay, relax" → return. Check "Stand up and walk a few steps", then "Sit down".
- [ ] Rebuild the macOS app (`PsychSim > Build macOS (Development)`) and launch it once.
- [ ] Update `docs/LIVE_DEMO_GUIDE.md` (the exam section and the script table with the new commands) and `HANDOFF.md`; commit.
