# Papers (IEEE conference format), sole author Faaz Khan Mohammad

| # | Title | PDF | Source |
|---|---|---|---|
| 1 | Decide, Then Voice: A Code-Governed Digital Twin for Simulated Psychiatric Patients, with Three-Seed Held-Out Validation | `p1_brain/p1_brain.pdf` | `p1_brain/p1_brain.tex` |
| 2 | An Integrated, On-Device Architecture for Patient-Specific Embodied Psychiatric Simulation | `p2_architecture/p2_architecture.pdf` | `p2_architecture/p2_architecture.tex` |
| 3 | Recall Under Paraphrase for Trust-Locked Patient Memory: A Blind Benchmark, Hybrid Lexical-Embedding Matching and Training-Free Hand-Set Heads | `p3_recall/p3_recall.pdf` | `p3_recall/p3_recall.tex` |
| 4 | Rapport: An Embodied, On-Device Psychiatric Standardised Patient Driven by a Research-Grounded Digital Twin (the Claude Docs "Rapport paper draft", updated with v0.3 results) | `p4_system/p4_system.pdf` | `p4_system/p4_system.tex` |

- Build: `tectonic -X compile <paper>.tex` inside its folder (Tectonic 0.17, IEEEtran).
- Figures: `server/patient-service/.venv/bin/python papers/figures/make_figures.py` draws every chart from the measured results in
  this repo (held-out rows, recall results, service timing logs; the stills from the local `docs/media/v0.3/`).
- References: `shared/refs.bib`. arXiv entries come from the arXiv API (`source/arxiv_meta.json`); the journal entries were checked
  against Crossref or NCBI, except two classics cited from memory (Harden et al. 1975, the OSCE; Mehrabian 1996, PAD).
- Every number comes from `docs/GATES_v0.3.md`, `docs/BASELINE_v0.3.md` or the result files they cite. No human-subject result is
  claimed: faculty ratings and a learner pilot are pending, as each paper says.
- Before submission: add an affiliation (currently "Rapport project"), check each venue's page limit, and have faculty review the
  clinical statements.
