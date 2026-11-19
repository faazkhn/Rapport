# Citation check: the four Rapport papers

Method: [citation-check-skill](https://github.com/serenakeyitan/citation-check-skill) v2, search mode, two passes.
Date: 2026-11-14. Files: `pass1_claims.json` (pass 1: every sentence or table row that cites a source), `pass2_sources.json` (pass 2,
step 1: does the source exist and does the bibliography entry match it), `verify_sources.py` (the script for step 1).

## Summary

| | Count |
|---|---|
| Cited claims extracted (pass 1) | 72 (20 with numbers) |
| Distinct sources cited | 58 |
| Sources found, bibliography matches (title, first author, year) | 58 of 58 |
| Claims that misstated or over-stated their source (fixed) | 10 |
| Citations removed because the source did not support the claim | 1 |
| Unverified (no full text checked; kept, worded conservatively) | 4 |

**Existence** was checked against arXiv (45 sources), Crossref by DOI or by title (10), and the source's own web page (NICE NG225, NICE CG100,
llama.cpp, Brain/MINDS). DOIs were added to the 8 journal articles that had none. One year differs by convention only: Synthea is 2018 (volume
year) in the bibliography and 2017 (online) on Crossref.

**Support** was checked against the abstract fetched today and, where the paper was read in full during the literature review, against the
review notes in `docs/literature/` (37 papers read in full, 35 as abstracts).

## ✗ Misstated or over-stated (all fixed in the papers)

| # | Paper | Claim as written | What the source supports | Fix |
|---|---|---|---|---|
| 1 | P1 intro, P1 Table II | "Models invent symptoms ... more so when a case is thin" cited to Patient-Zero and TalkDep | The thin-case finding is from a vignette study not in the bibliography; Chen et al. 2023 found stronger style cues lowered fidelity; Patient-Zero's verifier cut hallucination | Re-cited to Chen 2023 (style cues) and Patient-Zero (fact checks) |
| 2 | P1 intro | "Small, safety-tuned models soften hostility into apology" cited to SimPatient and Bodonhelyi | Those papers report patients too agreeable / need for resistance; the apology finding is our own test | Split: literature claim cited to SimPatient and PSYCHE; apology stated as our own observation |
| 3 | P1 related work | "persona variables explain under 10% of the variance in what simulated people say" (Hu 2024) | Under 10% of *annotation* variance in human data | Re-worded to annotation variance |
| 4 | P1 related work | some traits "cannot be prompted reliably at all" (TRAIT) | Prompting is "not very effective" for high psychopathy / low conscientiousness | "are hard to elicit by prompting" |
| 5 | P1 Table II | "Learners value feedback more than the avatar" cited to SOPHIE, MedSimAI and Brügge | Only SOPHIE compared feedback with the avatar (4.68 vs 3.40) | SOPHIE for that comparison; MedSimAI (feedback actionable) and Brügge (better decisions, small trial) separately |
| 6 | P3 intro | Trust levels per memory attributed to PatientAct, PATIENT-Ψ and PSYCHE | Trust-gated memory is PatientAct's; the other two ground patients in cognitive models / MSE constructs | Split the citation |
| 7 | P4 Table I | "Faculty principles reduce awkward replies" (Roleplay-doh) | Principles written by experts (therapists), not faculty | "Expert-written principles" |
| 8 | P4 related work | "language-model 3D patients include Voigt et al." | Abstract: patients with "action spaces" beyond text; no mention of 3D | "patients that act beyond text or appear as a lifelike avatar" |
| 9 | P1, P4 | Brain/MINDS credited with the idea "trust changes when expectations are not met" | The page describes a mathematical brain model built from anatomical and physiological data; it does not state that idea | Brain/MINDS cited only for what it is; the idea is described as general computational neuroscience |
| 10 | P4 Table IV | NICE CG100: admit "if there is a risk of fits or delirium" | "high risk of withdrawal seizures or delirium tremens" | Added "high" |

**Removed citation.** P4 cited Karam et al. 2018 for "candidates could miss a critical item and still pass". Karam 2018 is a validity study of
a new medical school's OSCE; the critical-item finding came from a different study we could not retrieve. The sentence now states our design
rule without a citation.

**Not citations, but found during the check.** Two example questions in Paper 3 ("a peg or two", "What was it like growing up at home?") were not
in the benchmark. They were replaced with real benchmark lines.

## ⚠ Unverified (kept, worded to what the abstract says)

1. Hu 2024, TRAIT, Li 2024 (instruction drift), PersonaGym: supported by their abstracts; full text not read.
2. Mental Healthcare Act 2017: the Act exists (Act No. 10 of 2017); no URL was checked.
3. "Master Interview Rating Scale" is named in P4 without its own citation (the cited Calgary–Cambridge paper covers the other half of the
   sentence).
4. P4: "human standardised-patient programmes let several actors play one case while the case stays fixed" has no citation.

## ✓ Verified

All other extracted claims match their sources in meaning, and every number taken from a source matches exactly: Geathers 2025 (exact agreement
27–44%, within one point 67–87%), SOPHIE (feedback 4.68 vs avatar 3.40, reported as "above"), Tosato 2025 (score shift about 20% of the scale,
reported as "about a fifth"), Li 2024 (drift within eight rounds), PatientAct (about six calls per turn), and the guideline statements (NG225,
C-SSRS sequence, Stanley–Brown components, the Indian depression guideline).

## Limits of this check

- Pass 1 was not shown to the author for confirmation before pass 2, as the skill suggests, because the author asked for the check to run
  to completion.
- Claim support rests on abstracts and on the literature-review notes; no full paper was re-read for this check.
- Numbers that come from Rapport's own experiments are not citations, and were checked against the result files instead (`papers/analysis/`).
