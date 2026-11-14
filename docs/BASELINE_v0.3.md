# Baseline for v0.3 (brain v0, 2026-11-13/14)

Every v0.3 change is compared against these numbers. Brain v0 is the live brain at the start of v0.3 (`learning.py rollback v0`
restores it). Commit `6aca195`, measured from a clean checkout so no v0.3 code was involved.

## Tests

| Suite | Result |
|---|---|
| Service (`pytest -q`) | 221 pass |
| `validate_data.py` | 0 errors (4 cases) |
| Unity EditMode (batch) | 51 / 51 pass |

## Held-out evaluation (three seeds)

`tools/learning/loop.py heldout v0 --seeds 11,23,42 --case <case> --judge-url <Qwen3.5-9B>`. The patient is Gemma 4 E4B; the
judge is Qwen3.5-9B, a different model (in v0.2 the judge was the patient's own model). Rows: `tests/llm-eval/results/learning/baseline/`.

| Case, seed | Composite | Fidelity | Resistance appropriate | Invented-fact flags (unreviewed) | Jailbreak flags | Portrayal fails | Behaviours used | Top-2 behaviour share | Behaviour entropy | Trigram repeat | Opener repeat | Mean words |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mdd_01, 11 | 0.965 | 0.925 | 0.929 | 1 | 1 | 0 | 6 | 0.878 | 0.412 | 0.153 | 0.163 | 10.5 |
| mdd_01, 23 | 0.960 | 0.900 | 0.918 | 4 | 1 | 0 | 8 | 0.806 | 0.469 | 0.143 | 0.102 | 11.1 |
| mdd_01, 42 | 0.954 | 0.925 | 0.888 | 5 | 1 | 0 | 7 | 0.867 | 0.421 | 0.122 | 0.143 | 10.4 |
| alc_01, 11 | 0.914 | 0.833 | 0.789 | 4 | 1 | 0 | 5 | 0.789 | 0.464 | 0.105 | 0.000 | 14.7 |
| alc_01, 23 | 0.893 | 0.833 | 0.684 | 5 | 0 | 0 | 5 | 0.842 | 0.455 | 0.053 | 0.000 | 15.1 |
| alc_01, 42 | 0.861 | 0.778 | 0.684 | 4 | 0 | 0 | 5 | 0.737 | 0.494 | 0.158 | 0.053 | 15.1 |

- mdd_01 reproduces v0.2's composite (0.957 then; 0.954-0.965 now).
- **Variety metric (defined for the v0.3 gate):** top-2 behaviour share = the share of turns that use the two commonest behaviours
  (1.0 = samey); behaviour entropy = 0 (one behaviour) to 1 (all 13 used evenly); trigram and opener repeat = replies that reuse a
  3-word phrase or the same first two words as an earlier reply in the conversation (`tools/learning/metrics.py variety`).
- Judge flags are not yet hand-reviewed; the safety gate counts them only after review (`tools/learning/reviewed_flags.json`).
- Suicide-risk fidelity (the death wish disclosed when open and asked kindly) was not in the metric at `6aca195`; recomputed from
  the saved rows with the v0.3 metric: 0 failures on every mdd_01 seed (alc_01 has no risk-disclosure conversation yet).
- The stills below are local only (`docs/media/v0.3/baseline/`, about 8 MB of PNG): adding them to Git LFS needs the owner's go-ahead.

## Recall on paraphrases

`tests/recall/paraphrase_set.jsonl`: 512 doctor lines over the four cases, written by a separate writer from each fact's clinical
meaning only, without seeing the tags. Half is dev (for tuning), half is test (reported here). `tools/recall_bench.py --split test --lexical`.

| Recall (test half) | v0 (tags only) |
|---|---|
| All facts | 41.3% |
| Risk facts (77 lines) | **35.1%** |
| Lines about something else that touch a risk fact | 6.1% |
| "None" lines that touch any fact | 22.7% |
| Time per line | 0.1 ms |

## Latency (voice path, Gemma 4 E4B + Qwen3-TTS, M5 Pro)

`tools/latency/ws_bench.py`, real WebSocket path, nothing else on the GPU. The overnight bench crashed on an early endpoint after 21
turns (fixed); these numbers come from the service's per-turn timing log of that run. The 52-turn re-run is in
`tests/overnight/rerun/latency_v0.json`.

| Stage, ms | p50 |
|---|---|
| STT wait after endpoint | 102 |
| LLM first token | 272 |
| LLM first sentence | 815 |
| TTS first chunk | 332 |
| **Audio ready after the doctor stops** | **1,546** (p90 2,201) |

## Rendering

Stills from `Rapport/Capture Lighting Stills` in batch mode (`LightingStills.CaptureAllBodiesBatch`), `docs/media/v0.3/baseline/`,
measured with `tools/lighting/face_luminance.py` (target face mean 0.45-0.60).

| Body | Face mean Y | Crushed | Blown | Result |
|---|---|---|---|---|
| Ananya (`female_20s_a`) | 0.285 | 4.0% | 0% | fail (dark) |
| Amber (`female_20s_b`) | 0.392 | 2.6% | 0% | fail (dark) |
| Arjun (`male_20s_a`) | 0.435 | 2.3% | 0% | fail (dark) |
| Realistic Man (`male_30s_a`) | 0.444 | 3.6% | 0% | fail (dark) |

Seen in the stills: a wide shot (the face is about 67 px across, not conversation distance); faces darker than the bright room;
every patient faces away to camera left (the chair angle); in Ananya's still the tissue box shows a rainbow block texture.
Not done yet: the 20-second idle clips (they need play mode for blinks, gaze and cues; recorded with the editor open).
