# Papers

Two papers in the Springer Nature `sn-jnl` template, each in its journal's reference style (Paper A: `sn-basic`, numbered; Paper B:
`sn-mathphys-num`). Authors: Faaz Khan Mohammad and Sanket Salvi, Department of Computer Engineering and Technology, Dr. Vishwanath Karad MIT World
Peace University, Pune.

| | Paper | Journal | Source | Supplement |
|---|---|---|---|---|
| A | Decide in Code, Voice with the Model: a code-governed patient model, compared with a prompt-only baseline | Journal of Medical Systems | `paperA_jms/paperA.tex` | `paperA_jms/supplementA.tex` |
| B | Recognising Reworded Risk Questions: blind benchmark, small encoders, BM25 and a zero-shot language model | Journal of Healthcare Informatics Research | `paperB_jhir/paperB.tex` | `paperB_jhir/supplementB.tex` |

- **Build:** `tectonic -X compile <file>.tex` inside each paper's folder. The first line of each main paper skips `breakurl` and
  `shared/sn_preamble.tex` redefines `\doi`, because Tectonic runs XeTeX and the class expects pdfTeX/dvips.
- **Numbers:** `server/patient-service/.venv/bin/python papers/analysis/new_results.py` writes the generated tables and values into each
  paper's `gen/` folder from the saved runs (red `[pending]` if a result file is missing). Earlier analyses (intervals, ablations, recall
  breakdowns): `analysis/analyses.py`, `ablation_table.py`, `recall_extra.py`, `recall_sensitivity.py`.
- **Figures:** `server/patient-service/.venv/bin/python papers/figures/make_figures.py`; `fig_pr_curves.pdf` comes from `new_results.py`.
- **References:** `shared/refs.bib`. **Author checks** still to do: `HUMAN_STUDIES.md`. **Journals:** `JOURNALS.md`.
- Each paper's Declarations state the use of AI tools; no human-participant study was run.
