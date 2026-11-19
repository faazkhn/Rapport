"""Citation check, pass 2 step 1: does each cited source exist, and does the bibliography match it (title, first author, year)?"""
import json, re, sys, time, urllib.request, urllib.parse
import xml.etree.ElementTree as ET
from difflib import SequenceMatcher
from pathlib import Path

bib = Path("shared/refs.bib").read_text()
claims = json.loads(Path("citecheck/pass1_claims.json").read_text())
keys = sorted({k for c in claims for k in c["keys"]})
entries = {}
for m in re.finditer(r"@(\w+)\{([^,]+),(.*?)\n\}", bib, re.S):
    f = dict((k.lower(), " ".join(v.replace("{", "").replace("}", "").split())) for k, v in re.findall(r"(\w+)\s*=\s*\{(.*?)\}\s*,?\s*(?=\n\s*\w+\s*=|\n?$)", m.group(3) + "\n", re.S))
    entries[m.group(2).strip()] = f
sim = lambda a, b: SequenceMatcher(None, re.sub(r"\W", "", a.lower()), re.sub(r"\W", "", b.lower())).ratio()
def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "citation-check (mailto:faazkhn1000@gmail.com)"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read().decode("utf8", "replace"), r.status
out = {}
arx = {k: re.search(r"arXiv:(\d{4}\.\d{4,5})", e.get("howpublished", "") + e.get("note", "")) for k, e in entries.items() if k in keys}
ids = {k: m.group(1) for k, m in arx.items() if m}
if ids:
    x, _ = get("https://export.arxiv.org/api/query?max_results=100&id_list=" + ",".join(ids.values()))
    ns = {"a": "http://www.w3.org/2005/Atom"}
    found = {}
    for e in ET.fromstring(x).findall("a:entry", ns):
        if e.find("a:title", ns) is None: continue
        i = e.find("a:id", ns).text.split("/abs/")[-1].split("v")[0]
        found[i] = (" ".join(e.find("a:title", ns).text.split()), e.find("a:author/a:name", ns).text, e.find("a:published", ns).text[:4])
    for k, i in ids.items():
        e = entries[k]
        if i not in found:
            out[k] = {"status": "Citation Not Found", "where": f"arXiv:{i}"}; continue
        t, a, y = found[i]
        ok_t, ok_a, ok_y = sim(t, e.get("title", "")) > 0.9, a.split()[-1].lower() in e.get("author", "").lower(), y == e.get("year")
        out[k] = {"status": "Exists" if ok_t and ok_a else "Bib mismatch", "where": f"arXiv:{i}", "title_match": ok_t, "first_author": a,
                  "year_source": y, "year_bib": e.get("year")}
for k in keys:
    if k in out: continue
    e = entries.get(k, {})
    if e.get("doi"):
        try:
            m = json.loads(get("https://api.crossref.org/works/" + urllib.parse.quote(e["doi"]))[0])["message"]
            t = m["title"][0]; a = m.get("author", [{}])[0].get("family", "")
            out[k] = {"status": "Exists" if sim(t, e.get("title", "")) > 0.85 else "Bib mismatch", "where": "doi:" + e["doi"],
                      "first_author": a, "year_source": str(m["issued"]["date-parts"][0][0]), "year_bib": e.get("year")}
        except Exception as ex:
            out[k] = {"status": "Check by hand", "where": "doi:" + e["doi"], "error": str(ex)[:80]}
    else:
        url = re.search(r"\\url\{([^}]*)\}|https?://\S+", " ".join(e.values()))
        u = (url.group(1) or url.group(0)) if url else None
        if u:
            try:
                _, st = get(u.rstrip("}.,"))
                out[k] = {"status": "Exists (URL resolves)", "where": u, "http": st}
            except Exception as ex:
                out[k] = {"status": "Check by hand", "where": u, "error": str(ex)[:80]}
        else:
            out[k] = {"status": "Check by hand", "where": "no DOI, arXiv id or URL", "title": e.get("title", "")[:90]}
    time.sleep(0.3)
Path("citecheck/pass2_sources.json").write_text(json.dumps(out, indent=1))
from collections import Counter
print(Counter(v["status"] for v in out.values()))
for k, v in out.items():
    if v["status"] != "Exists" or v.get("year_source") != v.get("year_bib"):
        print(k, v)
