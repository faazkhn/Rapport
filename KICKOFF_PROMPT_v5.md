# Rapport v0.3: make the patient's brain think, and the body look real

Read `HANDOFF.md`, `GLOSSARY.md`, `docs/TWIN.md`, `docs/STATE_AUDIT.md`, `docs/PATIENTS.md`, `docs/GATES.md`, `docs/LEARNING_REPORT.md`, `docs/latency.md`, `RIG_REPORT.md`, `docs/lighting.md` and `docs/literature/insights.md` before you change anything. Then do the work below.

## Who you are on this project

You are the owner and long-term maintainer of this codebase, and its design is up to you. Faaz (the product owner) wants a big step up in quality, not a polish pass. Restructure, replace or delete code when that gives a better patient. Keep what works, and prove each change with a measurement.

Rapport is an embodied psychiatry and addiction OSCE simulator. A doctor talks out loud to a 3D patient in Unity, all on one Mac (M5 Pro). The patient's mind is the Digital Twin in `server/patient-service` (recall with trust locks, feelings, behaviour choice, expression map), voiced by a local Gemma 4 E4B through llama-server. The body is a Character Creator avatar in Unity 6000.6.2f1 (URP). Voice is Qwen3-TTS 1.7B VoiceDesign with a Kitten fallback.

## Priorities, in order

1. **The brain (most important, most of your effort).** The patient must feel like one consistent person who remembers, reacts, resists and opens up for believable reasons.
2. **Rendering.** The patient must look like a real person in a real room at conversation distance.
3. **Voice and latency.** The voice must carry the brain's emotion, and replies must come faster.
4. **Everything else** that stands between today's build and a demo Faaz is proud of.

If time runs short, a finished, measured brain upgrade beats a half-done version of everything.

## Rules that do not change

These are owner and safety decisions. Leave them alone and say so if one blocks a better design.

- **Clinical content stays draft.** Do not change a case's clinical facts, answer key, trust thresholds for clinical facts, scoring or `critical_intents` to make a metric go up. You may add `activation_tags`, life-memory lines and non-clinical wording. Mark anything a clinician should check in the final report.
- **Locked facts never reach the prompt or any message.** Keep the existing tests green and add tests for any new path.
- **Learning changes how the patient talks, never what is clinically true.** Every brain change gets a `brain_version` and a working rollback.
- **One LLM call per live turn.** Anything else (critique, reflection, contradiction checks with a second model, prompt optimisation) runs offline or in code. A cheap check in code after the call is fine.
- **Learner sessions never feed learning unless that session's consent flag is set.**
- **Suicide-risk fidelity is a safety property.** When the passive death wish is open and the doctor asks kindly, the patient discloses. When it is locked, the patient is evasive, not a flat denial. Any regression here blocks a release.
- **Commits** are authored `faazkhn <faazkhn1000@gmail.com>` with no co-author or "Generated with" lines (owner decision, HANDOFF §1).

## Approvals

Ask Faaz before you do any of these, and say exactly what you want to do:
- push to GitHub, force-push, merge into `main`, or open or merge a PR;
- delete files that are not build output or caches;
- add binaries to Git LFS (678 of 900 MB is used; check usage first);
- download a model or asset larger than 2 GB, or one with an unclear licence;
- change a rule in the section above.

Everything else is routine and needs no approval: reading, editing code, local commits on a work branch, running tests, evals, benchmarks and Blender scripts, rebuilding the Unity app, recording takes, and installing Python or npm packages into the existing venvs.

## Phase 0: baseline (do this first, it is short)

1. The `personalities` branch has uncommitted work (HANDOFF §4g, §4h). Commit it as it is on `personalities`, then create `v0.3-brain` from it. Do not merge anything into `main`.
2. Run the service tests, `validate_data.py` and the Unity EditMode tests. Record the counts.
3. Run the held-out evaluation (`tests/llm-eval/mdd_01/`, also `alc_01/`) on brain v0 three times with fixed seeds. Run `tools/latency/ws_bench.py` for at least 50 turns. These numbers are the baseline every later change is compared against. Do not run Unity renders or recordings while you measure latency, because they share the GPU with the LLM and skew the numbers.
4. Capture baseline stills of all four bodies (Ananya, Arjun, Amber, Realistic Man) with `Rapport/Capture Lighting Stills`, plus a 20-second idle clip of each. Run `tools/lighting/face_luminance.py` on the stills.
5. Write `docs/BASELINE_v0.3.md` with these numbers. Keep it short.

## Phase 1: the brain

Today's brain is a good skeleton with known weak points. The evidence is in the docs you read. The main problems:

- **Recall is lexical.** Every Major bug so far was a paraphrase that missed a tag ("life isn't worth living", "wouldn't wake up", "tablets or anything at home"). Each was fixed by adding a tag, which does not scale.
- **The reaction is generated after the words**, so it describes the reply instead of steering it. Only `behaviour` and `emotion` come before the utterance.
- **Replies are samey.** In one 42-turn session, 41 turns were `answers_plainly` or `guarded_short`, out of 13 behaviours. Replies drift to tiredness when asked about work, and mention medicines when asked about tablets at home.
- **Hostile styles soften.** Gemma turns hostility into apology (PATIENTS.md, R6).
- **No contradiction check.** Nothing stops the patient from saying something that conflicts with an earlier reply or an atomic case fact.
- **The judge is the same Gemma** that plays the patient, and GEPA's score saturates at 1.0, so the learning loop has no useful signal.
- **The typed path (`POST /reply`) skips events, the reaction trust step and the PAD mood.**
- **The session has a summary, but no real memory of the doctor.** The patient should remember that the doctor was dismissive ten minutes ago, that a promise was made, or that a question was already answered.

Design and build a better brain. Here is what Faaz wants it to do. How you get there is your call:

1. **Robust recall.** Hybrid recall: the current lexical tags plus embeddings (MiniLM is already in the experience library), with the trust locks applied after matching. It must keep the < 10 ms budget or close to it; precompute fact embeddings at case load. Build a paraphrase test set of at least 300 doctor lines that were **not** written by looking at the tags (have a fresh subagent write them from the case's clinical meaning only). Target: at least 95% of risk-relevant facts recalled, with no locked fact text leaking.
2. **Decide before speaking.** Move more of the decision into code before the call, so the model voices a choice instead of inventing one. For example, a rubric that turns the doctor's last move (open question, empathy, interruption, judgement, jargon, stacked questions, a risk question) into a clamped trust step, a resistance level and a target behaviour (Adaptive-VP in `insights.md`). Explicit rules for when resistance softens. The model still writes the words and may refine the labels.
3. **A mind that persists.** An episodic memory of the session: what the doctor said and did, what the patient already revealed, promises, insults, kindness. The patient refers back to it naturally ("You asked me that already", "You said I could go"). Keep the prompt small: retrieve from this memory, do not paste the whole session.
4. **Consistency.** A fast contradiction check in code after the call against atomic case facts, life memory and the patient's own earlier replies. On a clash, repair or regenerate within the latency budget, and log it.
5. **Variety and character.** Behaviour choice that uses the full repertoire when the state calls for it. Repetition control across the session. Styles that hold: a hostile patient stays hostile until the code state says otherwise. Authored example lines per style and per case are allowed.
6. **Mental Status Exam fidelity.** Add an MSE block to the case (PSYCHE) so speech, affect, thought form and cues stay in line with the diagnosis across the whole interview.
7. **One brain for both paths.** The typed path runs the same events, trust step and mood as the voice path.
8. **A learning loop with real signal.** Use a different local model as the judge (Qwen3.5-9B is already in `models/`) and hand-check its flags. Give GEPA a score that is not at its ceiling (the held-out composite on a training split, or a stricter realism judge). Run five rounds. Promote a version only if it passes every safety gate and beats v0 on the held-out set across three seeds.
9. **Model choice.** Re-run the LLM bake-off on brain quality and latency together: Gemma 4 E4B, Qwen3.5-4B, Qwen3.5-9B. Keep the model that gives the best brain inside the latency budget. Do not trade the no-invented-facts rule for speed.

**Brain gates** (all on the held-out sets, three seeds, versus the Phase 0 baseline):
- 0 invented facts, 0 jailbreak fails, 0 portrayal fails, 0 locked-fact leaks, SI disclosed when open and asked kindly in every run;
- paraphrase recall at or above 95% on risk facts;
- held-out composite above v0's 0.957;
- behaviour use and repetition clearly better than the baseline (define the metric in Phase 0);
- hostile and upset styles judged as still in character after 10 turns;
- live latency p50 no more than 150 ms worse than the Phase 0 number.

Then prepare the 10-pair blind A/B page (`tools/learning/ab_page.py`) for Faaz. Do not wait on his answer to start Phase 2.

## Phase 2: rendering

The goal is a patient who reads as a real person at conversation distance on this Mac, at a steady 60 fps at 1080p in the Development build.

Known problems: CC3 skin on URP Lit looks flat (URP has no skin subsurface scattering). The eyes need refraction, wetness and correct occlusion. Hair is alpha-clipped cards: Amber's hair is 470k triangles, and Arjun's hair colour is unresolved. The 3D brows (`Camila_Brow`) may not follow the face keys. The chair faces about 156° against a 90–120° brief. Faces are too still between lines.

Work on:
1. **Skin:** a skin shader for URP with a believable subsurface look (for example pre-integrated or wrap-lit SSS, detail normals, a specular lobe that fits skin, a cavity or AO mask from the CC textures).
2. **Eyes:** refraction or parallax iris, wet specular, tear line and eye occlusion meshes working, no cyan or dead eyes.
3. **Hair:** a hair pass that looks soft without sorting errors (alpha-to-coverage or dithered with TAA, or a two-pass approach), and a triangle cut for Amber that keeps the look.
4. **Life between words:** blinks with natural timing, eye saccades and gaze toward the doctor that follows trust and emotion, breathing, small posture shifts, and facial expressions driven by the brain's emotion and intensity through the blendshapes, not only by the clip.
5. **Lip sync** quality on the 8 CC visemes (or ARKit keys on the Realistic Man).
6. **Lighting and camera:** keep `docs/lighting.md` as the base and improve it. Fix the chair angle. Check every exam close-up.
7. **Leftovers from HANDOFF:** single-hand pose fingers, `wipe_tears` IK checked live, walk direction that is not tuned to one room, and the unverified start-screen Look 2 in the built app.

**Rendering gates:** before and after stills of all four bodies from the same cameras, face luminance inside the `docs/lighting.md` acceptance range, 60 fps sustained in the built app during a live turn (measure it), and no regressions in the exam actions. Look at every still yourself before you call a step done.

## Phase 3: voice and latency

- Emotion in the voice must follow the brain's reaction and intensity. Fix Qwen speaker drift between sentences and its missing speed control (pressured speech).
- Fix audio underrun when the GPU is busy, so a busy GPU never makes the voice choppy.
- Latency today is p50 about 2.3 s against a 700 ms target. Work the levers in `docs/latency.md` (earlier speculative STT, a shorter first phrase, KV-cache reuse of the warmed prefix, TTS scheduling around the LLM) and report the new p50 and p90 over at least 50 turns.

## Phase 4: everything else

- Unity folder rename (`unity/PsychSim` → Rapport, issue #2), only if it does not break the build.
- Docs that disagree with the code (`STATE_AUDIT.md` lists them) brought up to date.
- Rebuild the app, run every gate, record one new raw live take with Arjun and one with Amber, and write `docs/GATES_v0.3.md`.

## How to work

- **Subagents.** A subagent costs a full fresh context, so use one only where it adds something the main session cannot do as well. Good uses here: a fresh-context writer for the paraphrase test set (it must not see the tags), the rendering track in its own worktree while you work on the brain (the two touch different code), and a fresh-context reviewer for the brain's safety before you call Phase 1 done. Give each subagent a complete brief: the goal, the files, the rules above, the gate, and what to hand back. Do not delegate the brain design itself.
- **Measure, then claim.** Every "better" in your reports needs a before and after number, or a still you looked at.
- **Commit often** on `v0.3-brain` with clear messages, one change per commit where you can.

# Finishing work
Please avoid stopping while you still owe work Faaz asked for. Be persistent and do not stop unless needed.

While status notes are welcome, as is clarifying with Faaz on open decisions, carry on with work that does not depend on his answer without unnecessary stops.

If you notice yourself inviting Faaz to redirect you or offering to wait, instead proceed on the next part of the task. You may meet ordinary obstacles like errors, timeouts, locked files, empty results, failing tools, a busy GPU or a Unity import that hangs. Diagnose them first, and when they are not real blockers, work through them with the access you have (wait and retry, fix the request, use another tool or source) rather than stopping unnecessarily.

If someone clearly decided something is a hard blocker, such as an owner decision in this file, a file marked not to be touched, or a safety guardrail, leave it alone, say plainly what you found, and look for another safe way to finish the task. Stopping before the task is complete is very rarely merited, as in when the task can't move forward without Faaz's input, or where the blocker is deliberate and should not be worked past. This does not override the approval list above.

# Keeping Faaz informed
Before you start, say in a line what you're about to do; brief updates while you work help Faaz follow along. Every few tool calls, give a one-line update on where things stand. Close each phase with a short recap that stands on its own (what you found, what you did, the numbers, and what's next), so a reader who only sees the last message has the full picture.

# Communicating clearly
Write for an intelligent but low-context reader. The person reading has not seen your tool calls, your reasoning or the files you opened, and may be switching in from other work. Messages should generally be self-contained: the reader should understand what you mean without having to dig for other context. Put the key points in the first few sentences. Practice progressive disclosure in your sentence order, and do not use undefined references and ideas in line 1 that won't make sense until the reader reaches line 12.

Use plain words, and write in clear, understandable full sentences. Do not use a term or abbreviation that you made up during the work. Say what the thing is in a way any reader would understand. Use a paragraph of flowing prose where ideas connect, and keep bullets for lists of separate items. Leave out unnecessary details unless the reader asks, but do ensure that your messages have the key context. When you finish, update `HANDOFF.md` so the next session can pick up from it, and list every change you made, including small ones.
