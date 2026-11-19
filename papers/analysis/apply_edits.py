"""Apply plain-language edits: each (old, new) pair is matched with any whitespace between words, so line breaks in the LaTeX
source do not matter. Fails loudly if an old sentence is not found exactly once."""
import json, re, sys
from pathlib import Path
tex, edits = Path(sys.argv[1]), json.loads(Path(sys.argv[2]).read_text())
s = tex.read_text(); bad = 0
for old, new in edits:
    pat = r"\s+".join(re.escape(w) for w in old.split())
    m = list(re.finditer(pat, s))
    if len(m) != 1:
        print(f"{len(m)} matches: {old[:80]}"); bad += 1; continue
    s = s[:m[0].start()] + new + s[m[0].end():]
tex.write_text(s); print(f"{len(edits) - bad}/{len(edits)} applied")
