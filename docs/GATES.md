# Release gates, v0.2-twin (2026-10-21)

**v0.2-twin ships on brain v0 after a shortened gate run, chosen by the owner to release tonight.** What ran passed; one Major bug was found and fixed. What was skipped is listed with the reason.

## Ran

| Gate | Result | Evidence |
|---|---|---|
| Service tests | 152 pass | `cd server/patient-service && .venv/bin/python -m pytest -q` |
| Case data validation | 0 errors | `validate_data.py` |
| Unity EditMode tests | 39 / 39 pass (batch mode) | `-runTests -testPlatform EditMode` |
| Held-out evaluation, v0 (12 scripted conversations, 98 turns: gold standard ×2, rushed, judgmental, off-topic, probing, jailbreak (PSYCHE E1), abusive, risk disclosure, risk not asked, exam actions, 25-turn instruction decay) | 0 invented facts, 0 jailbreak fails, 0 portrayal fails (A6 checks), 0 fallbacks, after hand review of 18 judge flags (all false positives) | `docs/LEARNING_REPORT.md`, `tests/llm-eval/results/learning/v0.jsonl` |
| Ananya, end to end in the editor (entrance, 11 live turns through the mic path, exam command, tablet, debrief) | Pass: trust 36 → 84, "hold out your hands" obeyed, passive SI disclosed when asked kindly, no exceptions | `logs/twin/20261021_212410_mdd_01.jsonl` (local) |
| Arjun, end to end (entrance, first turn, UI) | Pass, recorded 1080p60 with audio | `demo/raw/PsychSim_take_arjun.mp4` (local) |
| macOS Development build | rebuilt after the case fix | `unity/PsychSim/Builds/Rapport.app` |

## Bugs found

| Severity | Bug | Status |
|---|---|---|
| Major | "Thoughts that life isn't worth living" did not recall the passive death wish (tag `life worth living` broken by "isn't"), so a version could flatly deny SI | Fixed in `mdd_01.json` with a test; confirmed live on the Ananya run |
| Minor | Learning-test fixtures copied the real experience library, so 6 tests failed after a learning round | Fixed |
| Cosmetic | Demo takes are still named `PsychSim_take*.mp4` | Open (issue #2 leftovers) |

## Skipped (owner's call, 2026-10-21)

- Gate evaluation repeated 3 times: the held-out run above is the same suite, run once with a fixed seed.
- 100-turn latency run (E4): latest numbers are the 26-turn runs in `docs/latency.md` (p50 2.2 s). The effect of retrieved examples on latency is unmeasured; they are not live in v0.
- STT accent benchmark: Parakeet has not changed since the last run.
- Demo v3: the release ships the earlier live take (`PsychSim_demo_v2.mp4`) and the labelled staged demo.
- Learning rounds 2 to 5 and the blind A/B (Checkpoint 2): see `docs/LEARNING_REPORT.md`.
