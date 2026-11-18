"""Readability of each paper's prose (tables, figures, maths, references removed): mean words per sentence, share of sentences over
30 words, Flesch reading ease (higher is easier; 30-50 is typical of academic writing). --worst N lists the longest sentences."""
import re
import sys
from pathlib import Path

def prose(tex):
    t = tex[tex.index("\\begin{abstract}"):tex.index("\\bibliographystyle")]
    t = re.sub(r"(?<!\\)%.*", "", t)
    t = re.sub(r"\\begin\{(table\*?|figure\*?|tikzpicture|equation|tabularx|tabular)\}.*?\\end\{\1\}", " ", t, flags=re.S)
    t = re.sub(r"\$[^$]*\$", " X ", t)
    t = re.sub(r"\\(cite|ref|label|includegraphics)\{[^}]*\}", "", t)
    t = re.sub(r"\\(textbf|emph|textit|texttt|section\*?|subsection|paragraph)\{([^}]*)\}", r"\2. " if False else r"\2", t)
    t = re.sub(r"\\[a-zA-Z]+\*?(\[[^]]*\])?", " ", t).replace("{", " ").replace("}", " ").replace("~", " ").replace("``", '"').replace("''", '"')
    return " ".join(t.split())

def syl(w):
    w = w.lower().strip(".,;:!?\"'()")
    if not w: return 0
    n = len(re.findall(r"[aeiouy]+", w)) - (w.endswith("e") and not w.endswith("le"))
    return max(1, n)

def stats(text):
    sents = [s for s in re.split(r"(?<=[.!?])\s+(?=[A-Z\"(])", text) if len(s.split()) > 2]
    words = [w for s in sents for w in s.split()]
    wps = len(words) / len(sents)
    spw = sum(syl(w) for w in words) / len(words)
    return sents, {"sentences": len(sents), "words_per_sentence": round(wps, 1),
                   "over_30_words": round(sum(len(s.split()) > 30 for s in sents) / len(sents), 3),
                   "flesch": round(206.835 - 1.015 * wps - 84.6 * spw, 1)}

if __name__ == "__main__":
    worst = int(sys.argv[sys.argv.index("--worst") + 1]) if "--worst" in sys.argv else 0
    for d, f in [(d, d) for d in ("p1_brain", "p2_architecture", "p3_recall", "p4_system")] + [
            ("p1_brain", "p1_brain_conf"), ("p4_system", "p4_system_conf"), ("p5_combined", "p5_combined")]:
        sents, st = stats(prose((Path(__file__).parents[1] / d / f"{f}.tex").read_text()))
        print(f, st)
        for s in sorted(sents, key=lambda s: -len(s.split()))[:worst]:
            print("   ", len(s.split()), s[:200])
