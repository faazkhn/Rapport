"""Export a paper's LaTeX as plain text for rewriting by hand: numbers filled in, tables and figures as one-line placeholders, citations
and cross-references kept as [cite: key] and [ref: label] markers so the rewritten text can be put back into the LaTeX.
Usage: python3 papers/export_text.py <paper.tex> <out.txt>   (run from the repository root or papers/)
"""
import re
import sys
from pathlib import Path


def numbers(tex_path: Path) -> dict:
    p = tex_path.parent / "gen" / "numbers.tex"
    if not p.exists():
        return {}
    return {m.group(1): m.group(2) for m in re.finditer(r"\\newcommand\{\\(num\w+)\}\{(.*)\}", p.read_text())}


def braced(s: str, i: int) -> int:
    """Index just past the brace group that opens at s[i] == '{'."""
    depth = 0
    for j in range(i, len(s)):
        depth += {"{": 1, "}": -1}.get(s[j], 0)
        if depth == 0:
            return j + 1
    raise ValueError("unbalanced braces")


def unwrap(s: str, cmd: str, fmt: str) -> str:
    """Replace \\cmd{...} (nested braces allowed) with fmt % inner."""
    out, i, key = [], 0, "\\" + cmd + "{"
    while (k := s.find(key, i)) >= 0:
        e = braced(s, k + len(key) - 1)
        out += [s[i:k], fmt % s[k + len(key):e - 1]]
        i = e
    return "".join(out) + s[i:]


def floats(s: str) -> str:
    def one(m):
        kind = "TABLE" if m.group(1).startswith("table") else "FIGURE"
        c = m.group(0).find("\\caption{")
        cap = m.group(0)[c + 9:braced(m.group(0), c + 8) - 1] if c >= 0 else ""
        lab = re.search(r"\\label\{([^}]*)\}", m.group(0))
        return f"\n[{kind} {lab.group(1) if lab else ''}: {cap} (unchanged)]\n"
    return re.sub(r"\\begin\{(table\*?|figure\*?)\}.*?\\end\{\1\}", one, s, flags=re.S)


def convert(tex: Path) -> str:
    s = tex.read_text()
    for k, v in sorted(numbers(tex).items(), key=lambda kv: -len(kv[0])):
        s = s.replace("\\" + k + "{}", v).replace("\\" + k, v)
    s = s[s.index("\\begin{document}") + 16:s.index("\\bibliography")]
    s = re.sub(r"(?m)(?<!\\)%.*$", "", s)  # comments, but not \\% (a literal percent sign)
    s = floats(s)
    s = re.sub(r"\\begin\{(equation|align)\}(.*?)\\end\{\1\}", lambda m: f"\n[EQUATION (unchanged): {m.group(2).strip()}]\n", s, flags=re.S)
    s = unwrap(s, "abstract", "\n# Abstract\n%s\n")
    s = unwrap(s, "keywords", "\nKeywords: %s\n")
    s = re.sub(r"\\title\[[^]]*\]", r"\\title", s)
    s = unwrap(s, "title", "# Title: %s\n")
    s = re.sub(r"\\(author\*?|affil\*?)(\[[^]]*\])?\{.*", "", s)
    s = re.sub(r"\\email\{[^}]*\}", "", s)
    for cmd, fmt in (("section*", "\n# %s\n"), ("section", "\n# %s\n"), ("subsection", "\n## %s\n"), ("bmhead", "\n## %s\n"),
                     ("textbf", "%s"), ("emph", "%s"), ("texttt", "%s"), ("url", "%s"), ("humanpending", "[TO DO: %s]"),
                     ("pending", "[pending]")):
        s = unwrap(s, cmd, fmt)
    s = re.sub(r"\\cite\{([^}]*)\}", lambda m: "[cite: " + m.group(1).replace(",", ", ") + "]", s)
    s = re.sub(r"\\ref\{([^}]*)\}", r"[ref: \1]", s)
    s = re.sub(r"\\label\{[^}]*\}", "", s)
    s = re.sub(r"\\item\s*", "- ", s)
    s = re.sub(r"\\(begin|end)\{(itemize|enumerate|appendices)\}", "", s)
    for a, b in (("``", '"'), ("''", '"'), ("---", "—"), ("--", "–"), ("\\,", " "), ("~", " "), ("\\%", "%"), ("\\&", "&"),
                 ("\\ldots", "..."), ("\\ ", " "), ("$\\times$", "×"), ("$\\ge$", "≥"), ("\\_", "_"), ("$", "")):
        s = s.replace(a, b)
    s = re.sub(r"\\(maketitle|backmatter|noindent|centering|par)\b", "", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    lines = [ln.strip() for ln in s.splitlines()]
    paras, cur = [], []
    for ln in lines + [""]:  # join wrapped source lines into one line per paragraph
        if not ln or ln.startswith(("#", "- ", "[TABLE", "[FIGURE", "[EQUATION", "Keywords:")):
            if cur:
                paras.append(" ".join(cur))
                cur = []
            if ln.startswith("- "):  # a list item may wrap onto following lines
                cur = [ln]
            elif ln:
                paras.append(ln)
            elif paras and paras[-1] != "":
                paras.append("")
        else:
            cur.append(ln)
    head = ("Rewrite the prose freely. Keep every [cite: ...] and [ref: ...] marker next to the claim it supports, keep the numbers as they\n"
            "are, and leave the [TABLE ...], [FIGURE ...] and [EQUATION ...] lines alone; they are put back unchanged.\n\n")
    return head + "\n".join(paras).strip() + "\n"


if __name__ == "__main__":
    Path(sys.argv[2]).write_text(convert(Path(sys.argv[1])))
    print("wrote", sys.argv[2])
