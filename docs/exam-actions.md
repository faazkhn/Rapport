# Exam action router

`server/patient-service/exam_router.py` turns the doctor's words into ordered exam actions with slots, a relax, or an ask-back ("Which hand?"). Rules only, no LLM call. The phrase lists are in `data/exam_router.json`. Embeddings are not used: no model was available offline, and the rules meet the gate. Add an embedding fallback if accuracy on new phrasings drops.

Test set: `tests/exam-router/utterances.yaml`, 367 utterances (45 negatives), written before the router.

| Measure | Result | Gate |
|---|---|---|
| Accuracy (exact actions, slots, ask-back, relax) | 100.0% | ≥ 95% |
| False triggers on negatives | 0.0% | ≤ 1% |
| Time per call p50 / max | 0.01 / 0.03 ms | ≤ 30 ms |

Actions: `hold_out_hands{which, palms}`, `show_forearms{which}`, `roll_up_sleeves{which}`, `look_at_light`, `follow_finger`, `open_mouth`, `stick_out_tongue`, `stand_up`, `sit_down`, `walk_few_steps`, and `relax`.

**Caveat:** the same author wrote the test set and the router, so 100% is an optimistic estimate. The set was written before the router existed. Three negatives were added after the first run (doctor announcing a later exam) and are marked in the file. A held-out set written by someone else (the owner, faculty) is the honest check.

## Misses

None.
