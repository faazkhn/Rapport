# Release gates, v0.3 (2026-11-14)

**Submitted at the owner's 12:00 deadline, after one overnight run and one morning.** This report says what shipped, what was
measured against the Phase 0 baseline (`docs/BASELINE_v0.3.md`), which gates are met, which are not, and what is left. Clinical
content is still draft: nothing here replaces faculty review.

<!-- SUMMARY -->

## What changed (brain twin-0.2)

The patient's mind moved from "the model decides, code checks" towards "code decides, the model voices it" (`docs/TWIN.md`, section
twin-0.2). One pipeline (`mind.py`) now serves both the voice session and typed `/reply`.

- **Recall by meaning:** tags plus a small embedding model (bge-small-en-v1.5, 33 M parameters, CPU, about 2 ms a line), matched
  against authored probe questions and about 50 generated doctor lines per fact. Trust locks are applied after matching.
- **Decision before the call:** a hand-written rubric reads the doctor's move, steps trust before recall, moves a resistance level
  by explicit softening rules and shortlists the behaviours and reactions the reply may use (the schema enforces the shortlist).
- **Episodic memory:** what was already asked and answered, hurt and repair, kindness, promises, permission to leave, and everyday
  backstory the patient makes up (owner request): kept consistent, never clinical, never against the case.
- **Consistency in code before speech:** wrong numbers, age and relatives' names are corrected; the death wish is never spoken when
  locked or unasked; an open, kindly asked death wish is never flatly denied; an upset patient does not apologise.
- **Mental Status Exam block** per case (emotions allowed, intensity cap, no tangents) and risk `disclosure_line`s.
- **The patient can end the interview** after repeated abuse.
- **Voice:** one TTS instruction per reply (fixes speaker drift between sentences), the decided reaction in the voice from the first
  word, pace words and a pitch-preserving stretch for speed.
- **Safety review:** a fresh-context reviewer found 10 problems in the first version (six against owner rules, e.g. the raw text of
  a reply whose sentences were all dropped still reached the client). All 10 were fixed, re-probed with the reviewer's own scripts
  and turned into tests before the final measurements.
- **Rollback:** features switch on per brain version. `v2` has them all, `v0` none: `python learning.py rollback v0`.

<!-- BRAIN GATES -->

<!-- TABLES -->

## Not done (and why)

- **Paraphrase recall at 95% on risk facts.** Measured honestly on a test half nobody tuned on. More probes and thresholds tuned on
  the dev half did not carry over to the test half; hand-set topic weights (owner's no-training request) added about 5 points at
  more false hits and were left off. Next lever: hand-checked labels, then a fine-tuned small model (the code is in
  `tools/brain/finetune.py`; the labelling run was cancelled for the deadline).
- **Learning rounds (5) and the blind A/B decision.** The overnight rounds were not evaluated (a bug, fixed); there was no time to
  re-run them. The A/B page is built for the owner.
- **Move/intent classifier.** Trained on judge labels that turned out to be noisy (the judge agreed with the generator's topic on
  half the lines); not better than the keyword rubric held out; not live. The debrief keeps the LLM intent tagger.
- **Model bake-off:** done overnight; Gemma 4 E4B stays (Qwen3.5-4B/9B as the patient: 53-62 judge invented-fact flags, slower).
- **Rendering beyond the quick wins** (skin, eye and hair shaders, Amber's hair cut, lip sync, the leftovers): not done.
- **Live takes with Arjun and Amber, idle clips:** they need the editor in play mode; not recorded.
- **Hand review of the judge's invented-fact flags.** Not done; the counts below are unreviewed flags, not confirmed failures.

## For the clinicians (draft content added in v0.3)

- `mse` blocks in `mdd_01`, `alc_01`, `ward_01`, `ward_02` (emotions allowed, intensity cap, insight, thought form).
- `disclosure_line` on must-ask risk facts (`mdd_01` passive death wish, no plan, no means; `alc_01` passive thought, withdrawal fit,
  no plan or means; `ward_01` current thoughts): the patient's own words, the same meaning as the fact.
- `data/brain/rubric.json`: the trust steps, resistance rules and the end-the-interview rule.
- `topics` per fact (which clinical questions recall a memory).
