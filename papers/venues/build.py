"""Build venue-formatted copies of the papers from their IEEE sources, so a change to a paper is one rebuild away in every venue.

  python3 papers/venues/build.py            # build and compile every LaTeX venue
  python3 papers/venues/build.py tmlr_p1    # one venue

Each venue folder holds main.tex (generated: do not edit by hand; edit the IEEE paper or the venue settings here), the venue's
class or style files, and main.pdf. Word venues are built by build_word.py.
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PAPERS = HERE.parent
T = HERE / "_templates"
AUTHOR = "Faaz Khan Mohammad"
EMAIL = "faazkhn1000@gmail.com"
AFFIL = "Rapport project"

EXTRA = {
    "p1_brain": {
        "impact": (
            "This work is meant to widen access to practice in psychiatric interviewing, which today depends on scarce standardised-patient "
            "actors. A simulated patient that behaves unrealistically could teach students the wrong habits, and one that mishandles "
            "suicide risk could teach unsafe practice, so the design treats faithful suicide-risk behaviour as a safety property with "
            "automatic gates. The patient is not a model of any real person and no patient data is used. All clinical content is a "
            "draft until psychiatrists review it, and the system is not intended for clinical decision making or for use with patients. "
            "Learner sessions are used for learning only with consent, and everything runs on one device, so student audio does not "
            "leave it."),
        "structured": [
            ("Background", "Simulated psychiatric patients built on large language models invent facts, are too agreeable, and are "
             "unpredictable about suicide risk when the model is trusted with the patient's mind."),
            ("Objectives", "To test whether moving the patient's decisions into explicit code, with one model call per turn that only "
             "voices the decision, keeps the patient faithful and safe while making its behaviour fit the doctor it faces."),
            ("Methods", "We built a Digital Twin that reads the doctor's move, updates trust and resistance by fixed rules, recalls "
             "trust-locked memories by meaning, restricts the model to a shortlist of behaviours, and checks every sentence before it "
             "is spoken. We compared it with the previous version on 14 held-out scripted conversations, three seeds each, marked by a "
             "judge model from another family with every flag checked by hand, plus targeted probes, feature ablations and an "
             "independent safety review."),
            ("Results", "The new version had no jailbreak or portrayal failures and disclosed suicidal thoughts every time they were "
             "unlocked and asked about kindly, with accuracy equal to the previous version. Its behaviour varied more with the kind of "
             "doctor it faced, though a single conversation was no more varied. Recall of risk questions in new words rose from 35.1\\% "
             "to 72.7\\%, short of the 95\\% target, and an angry patient did not stay angry."),
            ("Conclusions", "Governing a simulated patient with inspectable code turns safety into checks anyone can run, and turns the "
             "remaining gaps into measurable targets."),
        ],
    },
    "p3_recall": {
        "impact": (
            "Matching a student's question to a simulated patient's memories decides whether the patient discloses suicidal thoughts. "
            "Missing a risk question can suppress a disclosure the case requires, and wrongly matching an ordinary question can make the "
            "patient talk about suicide when asked about sleep; we show the second failure happening when recall is tuned alone, and we "
            "report wrong matches next to recall for that reason. The benchmark contains no patient data: it was written by an AI agent "
            "from short descriptions of fictional cases. The system is a teaching tool, not a screening instrument, and its recall is not "
            "good enough for any clinical use."),
    },
}


def braced(s, start):
    """Text inside the brace group that opens at s[start] == '{'."""
    depth = 0
    for i in range(start, len(s)):
        depth += {"{": 1, "}": -1}.get(s[i], 0)
        if depth == 0:
            return s[start + 1:i], i + 1
    raise ValueError("unbalanced braces")


def parse(paper):
    s = (PAPERS / paper / f"{paper}.tex").read_text()
    title, _ = braced(s, s.index("\\title{") + len("\\title"))
    abstract = s[s.index("\\begin{abstract}") + 16:s.index("\\end{abstract}")].strip()
    kw = s[s.index("\\begin{IEEEkeywords}") + 20:s.index("\\end{IEEEkeywords}")].strip()
    rest = s[s.index("\\end{IEEEkeywords}") + 18:s.index("\\bibliographystyle")]
    ack = ""
    if "\\section*{Acknowledgment}" in rest:
        rest, ack = rest.split("\\section*{Acknowledgment}")
    body, app = (rest.split("\\appendices") + [""])[:2]
    ack = re.sub(r"^\s*\\textbf\{Use of AI tools\.\}\s*", "", ack.strip())
    return {"title": " ".join(title.split()), "abstract": abstract, "keywords": " ".join(kw.split()), "body": body.strip(),
            "appendix": app.strip(), "ai": ack}


def adapt(text, cite, onecol, anonymous):
    text = text.replace("\\cite{", f"\\{cite}{{") if cite != "cite" else text
    if onecol:
        for env in ("figure", "table"):
            text = text.replace(f"\\begin{{{env}*}}", f"\\begin{{{env}}}").replace(f"\\end{{{env}*}}", f"\\end{{{env}}}")
    if anonymous:
        text = text.replace("the developer's own", "the developers' own").replace("by the developer", "by the developers")
    return text


STYLE = r"""\usepackage{booktabs,tabularx,array}
\usepackage{tikz}
\usetikzlibrary{arrows.meta,positioning,fit,backgrounds,calc,shapes.geometric,shapes.misc}
\graphicspath{{../../figures/}}
\tikzset{>={Stealth[length=1.8mm]},
  box/.style={draw, rounded corners=2pt, align=center, font=\scriptsize, minimum height=7mm, inner sep=2pt, fill=#1}, box/.default=cyan!8,
  decision/.style={draw, diamond, aspect=2.2, align=center, font=\scriptsize, inner sep=1pt, fill=yellow!12},
  state/.style={draw, circle, align=center, font=\scriptsize, minimum size=12mm, fill=#1}, state/.default=cyan!8,
  lab/.style={font=\tiny, align=center}}
\newcolumntype{Y}{>{\raggedright\arraybackslash}X}
"""


def ai_section(p, anonymous, heading="Use of AI tools"):
    ai = p["ai"].replace("the author's direction", "the authors' direction" if anonymous else "the author's direction")
    if anonymous:
        ai = ai.replace("The author takes full responsibility", "The authors take full responsibility")
    return f"\\section*{{{heading}}}\n{ai}\n"


def tmlr(paper, out):
    p = parse(paper)
    for f in ("tmlr.sty", "tmlr.bst", "fancyhdr.sty"):
        shutil.copy(T / "tmlr" / f, out)
    body = adapt(p["body"], "citep", True, True)
    app = adapt(p["appendix"], "citep", True, True)
    tex = f"""\\documentclass[10pt]{{article}}
\\usepackage{{tmlr}}  % anonymous submission; use [accepted] for the camera-ready version
\\usepackage{{amsmath,amssymb}}
\\usepackage{{hyperref}}
\\usepackage{{url}}
{STYLE}
\\title{{{p['title']}}}
\\author{{\\name Anonymous authors\\\\ Paper under double-blind review}}
\\def\\month{{MM}}
\\def\\year{{YYYY}}
\\def\\openreview{{\\url{{https://openreview.net/forum?id=XXXX}}}}
\\begin{{document}}
\\maketitle
\\begin{{abstract}}
{p['abstract']}
\\end{{abstract}}

{body}

\\subsubsection*{{Broader Impact Statement}}
{EXTRA[paper]['impact']}

{ai_section(p, True).replace('section*', 'subsubsection*')}
\\bibliography{{../../shared/refs}}
\\bibliographystyle{{tmlr}}
{('\\appendix' + chr(10) + app) if app else ''}
\\end{{document}}
"""
    return tex


def dmlr(paper, out):
    p = parse(paper)
    shutil.copy(T / "dmlr" / "dmlr2e.sty", out)
    body = adapt(p["body"], "citep", True, False)
    app = adapt(p["appendix"], "citep", True, False)
    short = {"p3_recall": "Recall Under Paraphrase for Trust-Locked Patient Memory"}.get(paper, p["title"][:60])
    return f"""\\documentclass[twoside,11pt]{{article}}
\\usepackage[preprint]{{dmlr2e}}  % submission; drop [preprint] and fill \\dmlrheading for the camera-ready version
\\usepackage{{amsmath}}
\\usepackage{{lastpage}}
{STYLE}
\\def\\openreview{{\\url{{https://openreview.net/forum?id=XXXX}}}}
\\ShortHeadings{{{short}}}{{Mohammad}}
\\firstpageno{{1}}
\\begin{{document}}
\\title{{{p['title']}}}
\\author{{\\name {AUTHOR} \\email {EMAIL} \\\\ \\addr {AFFIL}}}
\\editor{{}}
\\maketitle
\\begin{{abstract}}%
{p['abstract']}
\\end{{abstract}}
\\begin{{keywords}}
{p['keywords']}
\\end{{keywords}}

{body}

\\impact{{{EXTRA[paper]['impact']}}}

\\acks{{{p['ai']} No funding was received for this work, and the author declares no competing interests.}}

\\vskip 0.2in
\\bibliography{{../../shared/refs}}
{('\\appendix' + chr(10) + app) if app else ''}
\\end{{document}}
"""


def tacl(paper, out):
    p = parse(paper)
    for f in ("tacl2021v1.sty", "acl_natbib.bst"):
        shutil.copy(T / "tacl" / f, out)
    body = adapt(p["body"], "citep", False, True)
    app = adapt(p["appendix"], "citep", False, True)
    return f"""\\documentclass[11pt,a4paper]{{article}}
\\usepackage{{times,latexsym}}
\\usepackage{{url}}
\\usepackage[T1]{{fontenc}}
\\usepackage[]{{tacl2021v1}}  % submission: anonymous, line numbers, confidential header; [acceptedWithA] for the final version
\\usepackage{{amsmath,amssymb}}
{STYLE}
\\title{{{p['title']}}}
\\author{{Anonymous TACL submission}}
\\date{{}}
\\begin{{document}}
\\maketitle
\\begin{{abstract}}
{p['abstract']}
\\end{{abstract}}

{body}

\\section*{{Software and data release}}
The benchmark, its split, the matching code, the probes and the cut-off file will be released under an open licence with the final
version.

{ai_section(p, True)}
\\bibliography{{../../shared/refs}}
\\bibliographystyle{{acl_natbib}}
{('\\appendix' + chr(10) + app) if app else ''}
\\end{{document}}
"""


def jair(paper, out):
    p = parse(paper)
    kit = T / "jair" / "JAIR AuthorKit" / "JAIR_Example_Template"
    for f in ("jair.cls", "acmart.cls"):
        shutil.copy(kit / f, out)
    shutil.copy(PAPERS / "shared" / "refs.bib", out)
    body = adapt(p["body"], "citep", True, False)
    app = adapt(p["appendix"], "citep", True, False)
    abstract = "\n\n".join(f"{{\\bf {k}:}} {v}" for k, v in EXTRA[paper]["structured"])
    return f"""\\documentclass[manuscript, screen, review]{{jair}}
\\setcopyright{{cc}}
\\acmDOI{{10.1613/jair.1.xxxxx}}
\\JAIRAE{{Insert JAIR AE Name}}
\\JAIRTrack{{}}
\\acmVolume{{1}}  % placeholders: JAIR assigns volume, article and month on acceptance
\\acmArticle{{1}}
\\acmMonth{{1}}
\\acmYear{{2026}}
\\usepackage[authoryear,round]{{natbib}}  % jair.cls expects biblatex+biber, which Tectonic cannot match here; natbib gives the same author-year look
{STYLE}
\\begin{{document}}
\\title{{{p['title']}}}
\\author{{{AUTHOR}}}
\\email{{{EMAIL}}}
\\affiliation{{\\institution{{{AFFIL}}} \\country{{India}}}}
\\renewcommand{{\\shortauthors}}{{Mohammad}}
\\begin{{abstract}}
{abstract}
\\end{{abstract}}
\\keywords{{{p['keywords']}}}
\\maketitle

{body}

\\begin{{acks}}
{p['ai']}
\\end{{acks}}

\\bibliographystyle{{ACM-Reference-Format}}
\\bibliography{{refs}}
{('\\appendix' + chr(10) + app) if app else ''}
\\end{{document}}
"""


def dnd(paper, out):
    p = parse(paper)
    shutil.copy(T / "dnd" / "DnD-LaTeX" / "dnd.sty", out)
    body = adapt(p["body"], "citep", True, False)
    app = adapt(p["appendix"], "citep", True, False)
    return f"""\\documentclass[twoside,11pt]{{article}}
\\usepackage{{dnd}}
\\usepackage{{times}}
\\usepackage{{amsmath}}
\\usepackage[hidelinks]{{hyperref}}
{STYLE}
\\dndheading{{}}{{}}{{}}{{{AUTHOR}}}{{}}
\\ShortHeadings{{Decide, Then Voice}}{{Mohammad}}
\\firstpageno{{1}}
\\begin{{document}}
\\title{{{p['title']}}}
\\author{{\\name {AUTHOR} \\email {EMAIL} \\\\ \\addr {AFFIL}}}
\\editor{{}}
\\submitted{{}}{{}}{{}}
\\maketitle
\\begin{{abstract}}%
{p['abstract']}
\\end{{abstract}}
\\begin{{keywords}}
{p['keywords']}
\\end{{keywords}}

{body}

{ai_section(p, False, 'Acknowledgments')}
\\bibliography{{../../shared/refs}}
{('\\appendix' + chr(10) + app) if app else ''}
\\end{{document}}
"""


VENUES = {"tmlr_p1": ("p1_brain", tmlr), "jair_p1": ("p1_brain", jair), "dnd_p1": ("p1_brain", dnd),
          "dmlr_p3": ("p3_recall", dmlr), "tacl_p3": ("p3_recall", tacl), "tmlr_p3": ("p3_recall", tmlr)}


def compile_(out, biber=False):
    """Tectonic runs BibTeX or biber itself as needed."""
    r = subprocess.run(["tectonic", "-X", "compile", "--keep-logs", "main.tex"], cwd=out, capture_output=True, text=True)
    errs = [l for l in (r.stdout + r.stderr).splitlines() if "error" in l.lower()]
    return r.returncode, errs[:8]


def main():
    want = sys.argv[1:] or list(VENUES)
    for v in want:
        paper, fn = VENUES[v]
        out = HERE / v
        out.mkdir(exist_ok=True)
        (out / "main.tex").write_text(fn(paper, out))
        rc, errs = compile_(out, biber=fn is jair)
        pages = "?"
        try:
            import fitz
            pages = fitz.open(out / "main.pdf").page_count
        except Exception:
            pass
        print(f"{v}: rc={rc} pages={pages}", *errs, sep="\n  ")


if __name__ == "__main__":
    main()
