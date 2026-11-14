"""Raw LaTeX sentences longer than N words in running prose (outside tables, figures and maths), for the plain-language pass."""
import re, sys
from pathlib import Path
d, n = sys.argv[1], int(sys.argv[2])
t = Path(f"{d}/{d}.tex").read_text()
t = t[t.index("\\begin{abstract}"):t.index("\\appendices") if "\\appendices" in t else t.index("\\bibliographystyle")]
t = re.sub(r"\\begin\{(table\*?|figure\*?|tikzpicture|equation)\}.*?\\end\{\1\}", "\n\n", t, flags=re.S)
for para in re.split(r"\n\s*\n", t):
    p = " ".join(para.split())
    for s in re.split(r"(?<=[.?!])\s+(?=[A-Z\\])", p):
        w = len(re.sub(r"\\cite\{[^}]*\}|\\ref\{[^}]*\}", "", s).split())
        if w > n:
            print(f"[{w}] {s}\n")
