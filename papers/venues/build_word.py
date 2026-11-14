"""Word copies of papers 2 and 4 for the medical-education journals: each venue's title page, structured abstract headings, reference
style and statements, Times New Roman 12 pt, double spacing. Straight copies of the paper text: where a venue's word or figure limit
is exceeded, the report says so; the text is not condensed.

  server/patient-service/.venv/bin/python papers/venues/build_word.py
"""
import re
import shutil
import subprocess
import zipfile
from pathlib import Path

import fitz

from build import AFFIL, AUTHOR, EMAIL, PAPERS, T, parse

HERE = Path(__file__).resolve().parent
FIG = HERE / "_png"

ABSTRACT = {
    "p4_system": {
        "background": "Students learn psychiatric interviewing with standardised patients, who are scarce and hard to keep consistent; "
                      "AI patient simulators are mostly text chats that run in the cloud and do not track trust or mood.",
        "methods": "We built Rapport, a spoken 3D standardised patient that runs on one laptop. A Digital Twin decides in code how the "
                   "patient reacts to each doctor turn, and one local language-model call puts the decision into words that are checked "
                   "before they are spoken. Four draft stations were evaluated with 14 held-out scripted conversations (three seeds each, "
                   "marked by a different AI model and checked by hand), a blind 512-question memory benchmark, timing measurements and "
                   "an independent safety review.",
        "results": "The patient started speaking a median 1.82 s after the student stopped. It had no jailbreak or portrayal failures and "
                   "disclosed suicidal thoughts every time they were unlocked and asked about kindly, with accuracy equal to the previous "
                   "version. Examination requests were recognised on all 385 test sentences. Recall of risk questions asked in new words "
                   "was 72.7%, below the 95% target.",
        "conclusions": "A private, embodied psychiatric standardised patient with an inspectable patient mind is feasible on one laptop. "
                       "Faculty ratings of realism and a student pilot are the next steps.",
    },
    "p2_architecture": {
        "background": "A simulated psychiatric patient that students talk to out loud must hear, decide, speak and move within the pause "
                      "of a real patient, privately and on hardware a school owns.",
        "methods": "We describe the architecture of Rapport: a Unity client, a patient service and a local language model on one "
                   "laptop, with one patient model shared by typed and spoken turns, patients defined as data files, seeded "
                   "conversation styles and timed ward events. We measured each stage of a spoken turn, face brightness and framing, and "
                   "recorded the failures found during testing.",
        "results": "The median time from the student stopping to the patient's first audio was 1.82 s (90th percentile 2.96 s), "
                   "against 3.05 s before optimisation. The body, voice and examiner view follow one decision per turn, and examination "
                   "requests were recognised on all 385 test sentences.",
        "conclusions": "An embodied, spoken psychiatric patient can run privately on one laptop if the patient is data, code makes the "
                       "decisions and the body reads the same decision as the voice.",
    },
}

VENUES = {
    # name: paper, csl, abstract heading labels, article type, limits (words, displays, refs), extra statements
    "cmej_p4": ("p4_system", "nlm-citation-sequence", ("Background", "Methods", "Results", "Conclusions"), "Original Research", (4500, 5, None)),
    "hpe_p4": ("p4_system", "american-medical-association", ("Purpose", "Method", "Results", "Discussion"), "Original Research", (None, None, None)),
    "jeehp_p4": ("p4_system", "nlm-citation-sequence", ("Purpose", "Methods", "Results", "Conclusion"), "Software report", (2500, 10, 15)),
    "taps_p4": ("p4_system", "apa", ("Introduction", "Methods", "Results", "Conclusion"), "Original Article", (4000, 5, None)),
    "cmej_p2": ("p2_architecture", "nlm-citation-sequence", ("Background", "Methods", "Results", "Conclusions"), "Original Research", (4500, 5, None)),
}

STATEMENTS = (
    "\\section*{Ethics}\nNo human participants, patient data or human-originated material were involved; all evaluations used "
    "scripted conversations and automated measurements, so institutional review was not required. Any study with students or faculty "
    "will seek ethics approval first.\n\n"
    "\\section*{Funding}\nNone.\n\n\\section*{Conflicts of interest}\nNone declared.\n\n"
    "\\section*{Data availability}\nThe case files, scripted conversations, benchmark, result files and analysis scripts are held in the "
    "project repository and will be shared on request until a public release.\n\n"
)


def pngs():
    FIG.mkdir(exist_ok=True)
    for f in (PAPERS / "figures").glob("*.pdf"):
        out = FIG / (f.stem + ".png")
        if not out.exists() or out.stat().st_mtime < f.stat().st_mtime:
            fitz.open(f)[0].get_pixmap(dpi=220).save(out)


def word_tex(paper, venue):
    p = parse(paper)
    _, csl, heads, kind, _ = VENUES[venue]
    body = p["body"] + ("\n\\section*{Appendix}\n" + p["appendix"].replace("\\section{", "\\subsection*{") if p["appendix"] else "")
    # TikZ diagrams have no Word equivalent: leave a marked placeholder with the caption, to be pasted from the PDF.
    body = re.sub(r"\\begin\{tikzpicture\}.*?\\end\{tikzpicture\}", "[Diagram: insert from the PDF version]", body, flags=re.S)
    body = re.sub(r"\\includegraphics(\[[^]]*\])?\{([^}]*?)(\.pdf|\.jpg)?\}",
                  lambda m: f"\\includegraphics{{{Path(m.group(2)).stem}.png}}" if "docs/media" not in m.group(2)
                  else f"\\includegraphics{{{(PAPERS / m.group(2).replace('../../', '../')).resolve()}{m.group(3) or ''}}}", body)
    body = body.replace("figure*", "figure").replace("table*", "table")
    # pandoc drops tabularx: make them plain tabulars with left-aligned columns
    body = re.sub(r"\\begin\{tabularx\}\{[^}]*\}\{([^\n]*)\}\n",
                  lambda m: "\\begin{tabular}{" + re.sub(r">\{[^}]*\}|@\{[^}]*\}", "", m.group(1)).replace("Y", "l").replace("X", "l").replace("p{2.3cm}", "l").replace("p{4.4cm}", "l").replace("p{2.9cm}", "l") + "}\n", body)
    body = body.replace("\\end{tabularx}", "\\end{tabular}")
    body = re.sub(r"\\setlength\{\\tabcolsep\}\{[^}]*\}", "", body)
    a = ABSTRACT[paper]
    abstract = "\n\n".join(f"\\textbf{{{h}:}} {a[k]}" for h, k in zip(heads, ("background", "methods", "results", "conclusions")))
    title_page = (f"\\textbf{{Article type:}} {kind}\n\n\\textbf{{Title:}} {p['title']}\n\n\\textbf{{Author:}} {AUTHOR}, {AFFIL}\n\n"
                  f"\\textbf{{Corresponding author:}} {AUTHOR}, {EMAIL}\n\n\\textbf{{Keywords:}} {p['keywords']}\n\n")
    ai = p["ai"]
    return (f"\\documentclass{{article}}\n\\title{{{p['title']}}}\n\\begin{{document}}\n\\maketitle\n{title_page}"
            f"\\section*{{Abstract}}\n{abstract}\n\n{body}\n\n{STATEMENTS}\\section*{{Acknowledgements and use of AI}}\n{ai}\n\n"
            "\\section*{References}\n\\end{document}\n")


def restyle(docx):
    """Times New Roman 12 pt, double spaced, as these journals ask."""
    tmp = docx.with_suffix(".tmp")
    with zipfile.ZipFile(docx) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "word/styles.xml":
                s = data.decode()
                s = re.sub(r'w:ascii="[^"]*"', 'w:ascii="Times New Roman"', s)
                s = re.sub(r'w:hAnsi="[^"]*"', 'w:hAnsi="Times New Roman"', s)
                s = s.replace("<w:rPrDefault><w:rPr>", '<w:rPrDefault><w:rPr><w:sz w:val="24"/><w:szCs w:val="24"/>', 1)
                s = re.sub(r"<w:pPrDefault>.*?</w:pPrDefault>",
                           '<w:pPrDefault><w:pPr><w:spacing w:after="0" w:line="480" w:lineRule="auto"/></w:pPr></w:pPrDefault>', s, 1, re.S)
                data = s.encode()
            zout.writestr(item, data)
    tmp.replace(docx)


def words(docx):
    text = subprocess.run(["pandoc", str(docx), "-t", "plain"], capture_output=True, text=True).stdout
    main = text.split("Abstract", 1)[-1]
    main = re.split(r"\n\s*(Ethics|Acknowledgements and use of AI)\s*\n", main)[0]
    return len(main.split())


def main():
    pngs()
    for v, (paper, csl, *_rest) in VENUES.items():
        out = HERE / v
        out.mkdir(exist_ok=True)
        src = out / "manuscript.tex"
        src.write_text(word_tex(paper, v))
        docx = out / f"{v}_manuscript.docx"
        r = subprocess.run(["pandoc", src.name, "-f", "latex", "-o", docx.name, "--citeproc",
                            f"--bibliography={PAPERS / 'shared' / 'refs.bib'}", f"--csl={T / 'csl' / (csl + '.csl')}",
                            f"--resource-path=.:{FIG}:{PAPERS / 'figures'}"], cwd=out, capture_output=True, text=True)
        restyle(docx)
        limit = VENUES[v][4]
        n = words(docx)
        print(f"{v}: {'ok' if r.returncode == 0 else r.stderr[-400:]} ~{n} words incl. abstract, tables and captions; "
              f"limits: words {limit[0] or 'none stated'}, figures+tables {limit[1] or 'none stated'}, references {limit[2] or 'none stated'}")


if __name__ == "__main__":
    main()
