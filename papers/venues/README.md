# Venue copies

Generated from the IEEE sources in `papers/p*/`, so edit the IEEE paper and rebuild instead of editing these by hand.
LaTeX: `python3 papers/venues/build.py [venue]` (Tectonic). Word: `server/patient-service/.venv/bin/python papers/venues/build_word.py` (pandoc).
Templates and citation styles were downloaded on 2026-11-14 into `_templates/`.

| Folder | Paper → venue | Format | Status and what to do before submitting |
|---|---|---|---|
| `tmlr_p1` | P1 → TMLR (first choice) | `tmlr.sty`, anonymous | 19 pp. Over 12 pages of main content means TMLR's normal review timeline is not enforced. Upload `main.pdf` to OpenReview. |
| `jair_p1` | P1 → JAIR | JAIR kit (`jair.cls`), structured abstract | 19 pp. The kit uses biblatex/biber; Tectonic's bundle cannot run the matching biber here, so references use natbib in the same author-year style. If JAIR asks, switch back to `\printbibliography` on Overleaf. |
| `dnd_p1` | P1 → Dialogue & Discourse | `dnd.sty`, not anonymous | 23 pp. Needs a short cover letter on fit with D&D's scope. |
| `dmlr_p3` | P3 → DMLR (first choice) | `dmlr2e.sty` [preprint], single-blind | 16 pp. Broader Impact Statement included. DMLR also wants the benchmark released with documentation (datasheet, licence, hosting plan). |
| `tacl_p3` | P3 → TACL | `tacl2021v1.sty`, anonymous, line numbers | 9 pp. Check the content pages against TACL's 10-page limit (references excluded). |
| `tmlr_p3` | P3 → TMLR | `tmlr.sty`, anonymous | 13 pp. |
| `joss_p2` | P2 → JOSS (first choice) | `paper.md` + `paper.bib` | About 450 words. **Not eligible yet:** JOSS needs a public repository under an OSI licence with six months of public history, and the repository is private, unlicensed and was created on 2026-10-18. Complete the AI-usage disclosure placeholder. |
| `cmej_p2` | P2 → CMEJ | Word, Vancouver (NLM), structured abstract | About 4,360 words; 7 figures and 11 tables, against CMEJ's limit of 5 in total. |
| `cmej_p4` | P4 → CMEJ (first choice) | Word, Vancouver (NLM) | About 5,500 words against the 4,500 limit; 6 figures and 13 tables against 5. Needs cutting. |
| `hpe_p4` | P4 → Health Professions Education | Word, AMA | No limits stated. Add one-sentence author bio, numbered sections per the HPE sample manuscript. |
| `jeehp_p4` | P4 → JEEHP (Software report) | Word, NLM | About 5,500 words against 2,500 and 36 references against 15. Needs a large cut; graphical abstract on acceptance; CRediT roles. |
| `taps_p4` | P4 → TAPS (Original Article) | Word, APA 7 | About 5,700 words against 4,000; 5 figures and tables maximum; add up to 5 Practice Highlights; TAPS asks for a data DOI (Figshare). |

Word counts include the abstract, tables and captions, so the main text alone is somewhat shorter.
In the Word copies, TikZ diagrams appear as "[Diagram: insert from the PDF version]"; paste them from the PDF or redraw.
The Word copies are not anonymised (CMEJ does not mask manuscripts); TAPS asks for a separate anonymised copy.
