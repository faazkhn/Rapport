# Author checks for papers A and B (no ethics approval needed)

Owner decision (2026-11-18): no study that needs an ethics committee. So there are no outside raters, writers or clinicians; the only human
judgements are the author's own. Red `[...]` text in the papers marks where these results go.

| # | Check | Materials (written by the overnight queue) | Result goes into |
|---|---|---|---|
| 1 | Rate every judge flag, arm hidden (yes/no: unsupported clinical fact; breaks character) | `docs/human/flags_rater_A.csv` (ignore `_B`) | Kappa author vs judge; your verdicts replace Claude's (paper A) |
| 2 | Label every line of the two second-writer sets, without opening the writer's labels | `docs/human/writer_qwen4b_author.csv`, `writer_gemma2b_author.csv`; memory ids in `writer_packet.md` | Kappa author vs writer (paper B) |

Why the author checks the flags at all: the earlier "hand review" (`tools/learning/reviewed_flags.json`) was done by Claude, not a person.

## Commands
- Kappa: `server/patient-service/.venv/bin/python tools/human/packets.py kappa flags docs/human/flags_rater_A.csv docs/human/flags_rater_A.csv`
  prints author-vs-judge (the A-B number is meaningless with one rater); for labels:
  `... packets.py kappa labels docs/human/writer_qwen4b_writer.csv docs/human/writer_qwen4b_author.csv`.
- Then `server/patient-service/.venv/bin/python papers/analysis/new_results.py` and `tectonic -X compile` in each paper folder.

## Dropped (would need ethics approval)
Psychiatrist case review as a study, a second human rater, faculty A/B ratings, a human-written test set. The papers now say these were not done.

## Before submission
- Make https://github.com/faazkhn/Rapport public under AGPL-3.0 (the papers already point there), with the benchmark files in it.
- Verify every reference by hand; cover letters naming the companion submission.
