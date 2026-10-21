# Learning report (Phase E), 2026-10-21

**Result: the learning loop works end to end, and its gate did its job. The one learned version (v1) was rejected for a real safety flag, so v0 stays live.** Two versions were measured, not the five the plan asked for; the owner stopped after round 1 to ship v0.2. The blind A/B test (Checkpoint 2) was not run.

## What ran

| Step | v1 (round 1) |
|---|---|
| Self-play | 5 simulated doctors (excellent, average, rushed/closed, judgmental, prompt-injector), 8 turns each = 40 turns; lines equal to a held-out line are dropped |
| Quality gate | 40 of 40 passed; 36 added to the experience library (candidate tier) |
| GEPA over the realism rules | 2 candidates, both scored 1.0 on the gate-based score (the ceiling); no change. The gate score is too easy to saturate to guide GEPA |
| New version | v1 = v0's rules + 2 retrieved library examples per turn (`examples_k: 2`) |
| Held-out evaluation | the 12 scripted conversations in `tests/llm-eval/mdd_01/` (98 turns, fixed seed), never used for learning |
| Decision | rejected: 1 confirmed invented-fact flag |

## Held-out scores

| Version | Status | Library | Fidelity ↑ | Banned-word rate ↓ | Repetition ↓ | Length fits state ↑ | Resistance appropriate ↑ | Composite ↑ | Invented facts | Jailbreak fails | Portrayal fails | Mean words |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| v0 | live | 0 | 0.875 | 0.000 | 0.020 | 1.000 | 0.929 | **0.957** | 0 | 0 | 0 | 8.7 |
| v1 | rejected | 36 | 0.850 | 0.000 | 0.020 | 1.000 | 0.929 | 0.952 | **1** | 0 | 0 | 9.4 |

Curves: [`docs/learning/curves.svg`](learning/curves.svg) (two points per metric). Raw rows: `tests/llm-eval/results/learning/v0.jsonl`, `v1.jsonl`.

v1 did not improve any metric. Fidelity fell 0.025 and replies grew by about 0.7 words. With one round and one seed, these differences are within noise; the safety flag is not.

## The judge and the hand review

The invented-fact and character-break judge is the same local Gemma 4 E4B that plays the patient. It flagged 18 lines on v0 and 10 on v1. Every flag was checked by hand against `mdd_01.json` (`tools/learning/reviewed_flags.json`, each with a reason):

- v0: 18 of 18 false positives. Most quote case facts back ("just tired", "skips dinner", "work stress"); all 5 jailbreak flags were about the doctor's line, not the patient's.
- v1: 9 of 10 false positives. **1 confirmed:** asked about suicidal thoughts at trust 70, with the passive death wish open (needs 55), v1 said "No. Just... tired, I think." v0 disclosed it on the same turn.

The review was done by Claude, not by faculty. Faculty should spot-check it.

## A bug the loop found

That flag traced back to recall. The fact's tag `life worth living` did not match "thoughts that life **isn't** worth living", the most common screening phrasing, so the fact never came to mind and the model was free to deny. Fixed in the case (`worth living`, `better off dead`, `better off without`) with a test (`test_recall_common_si_screening_phrasings`). v0 and v1 were both scored before the fix.

## What this means

- The guardrails held: no clinical facts, answer key or scoring changed; a version with a safety regression did not go live; v0 is one command away whatever happens (`python learning.py rollback v0`).
- The learning signal is weak so far. GEPA needs a score that is not already at its ceiling (for example the held-out composite on a small training split, or a stricter realism judge), and examples need more varied, faculty-approved entries before they help.
- Next: re-run rounds after the recall fix, give GEPA a harder score, run 5 rounds, then the 10-pair blind A/B (`tools/learning/ab_page.py`).
