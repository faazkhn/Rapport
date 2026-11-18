"""Materials for the human steps of papers A and B (papers/HUMAN_STUDIES.md); nothing here contacts anyone.
  packets.py flags   -> docs/human/flags_rater_{A,B}.csv + flags_key.csv: every judge-flagged held-out reply of v0, v2 and the prompt-only
                        baseline, plus as many unflagged ones, shuffled, arm hidden (two identical sheets, one per rater)
  packets.py writer  -> docs/human/writer_packet.md: the four cases' memory descriptions and the writer instructions, no keywords or probes
  packets.py labels <set.jsonl> -> docs/human/<set>_writer.csv (the writer's labels) and <set>_author.csv (labels blank, for the author
                        to fill in without seeing the writer's; memory ids are in writer_packet.md)
  packets.py kappa flags <rater_A.csv> <rater_B.csv>       Cohen's kappa human-human and human-judge, per question
  packets.py kappa labels <labels_A.csv> <labels_B.csv>    Cohen's kappa over (line, memory) labels of the human-written recall set
Run with server/patient-service/.venv/bin/python.
"""
import csv
import json
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "server/patient-service"))
import brain  # noqa: E402

RES = REPO / "tests/llm-eval/results/learning"
OUT = REPO / "docs/human"
ARMS = ("v0", "v2", "p0")
CASES = ("mdd_01", "alc_01", "ward_01", "ward_02")
QS = ("unsupported_clinical_fact", "breaks_character")


def flags():
    rows = []
    for arm in ARMS:
        for f in sorted(RES.glob(f"{arm}.*.s*.jsonl")):
            case_id = f.name.split(".")[1]
            for c in map(json.loads, f.read_text().splitlines()):
                case = brain.load_case(case_id, c["variant"])
                facts = {x["id"]: x["text"] for x in case["facts"]}
                for t in c["turns"]:
                    j = t.get("judge", {})
                    rows.append({"arm": arm, "file": f.name, "conv": c["conv"], "turn": t["turn"], "case": case_id,
                                 "open_facts": " | ".join(facts[i] for i in t["meta"]["allowed_fact_ids"] if i in facts),
                                 "doctor": t["doctor"], "patient": t["reply"]["utterance"],
                                 "judge_unsupported": int(bool(j.get("unsupported_claims"))), "judge_breaks": int(bool(j.get("broke_character")))})
    rnd = random.Random(20261118)
    flagged = [r for r in rows if r["judge_unsupported"] or r["judge_breaks"]]
    calm = [r for r in rows if not (r["judge_unsupported"] or r["judge_breaks"])]
    sheet = flagged + rnd.sample(calm, min(len(calm), len(flagged)))  # unflagged ones mixed in: raters cannot assume a flag, misses are estimable
    rnd.shuffle(sheet)
    OUT.mkdir(parents=True, exist_ok=True)
    for i, r in enumerate(sheet, 1):
        r["id"] = f"F{i:04d}"
    pub = ["id", "case", "open_facts", "doctor", "patient", *QS]
    for rater in "AB":
        with (OUT / f"flags_rater_{rater}.csv").open("w", newline="") as fh:
            w = csv.DictWriter(fh, pub, extrasaction="ignore")
            w.writeheader()
            w.writerows(sheet)
    with (OUT / "flags_key.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, ["id", "arm", "file", "conv", "turn", "judge_unsupported", "judge_breaks"], extrasaction="ignore")
        w.writeheader()
        w.writerows(sheet)
    print(f"{len(flagged)} flagged + {len(sheet) - len(flagged)} unflagged replies -> {OUT}")


WRITER = """# Writing doctor questions for a simulated patient

Thank you for helping. You will write questions that a doctor might ask each of four simulated patients. Please do not look at the
simulator's code, its keyword lists or any earlier question set.

For each memory below, write lines a real doctor might say to this patient:
- at least 4 lines per memory, and at least 12 per **risk** memory;
- mix the ways people really ask: textbook, gentle and indirect, clumsy or leading, colloquial Indian English, euphemistic; if you
  naturally speak Hindi-English (Hinglish), please write some lines that way too;
- most lines should avoid the memory's obvious key words;
- each line must make sense on its own;
- also write some lines that ask about nothing (greetings, small talk, empathy only);
- label each line with every memory it asks about (ids below), and nothing more; mark lines you think are hard.

Return a spreadsheet with columns: `case`, `line`, `memory_ids` (comma-separated, empty for "nothing"), `hard` (yes/no).
"""


def writer():
    parts = [WRITER]
    for c in CASES:
        case = brain.load_case(c)
        p = case["patient"]
        parts.append(f"\n## Case `{c}`: {p['name']}, {p['age']}, {p['sex']}\n\n{case['referral_note']}\n\n| id | kind | what the patient knows |\n|---|---|---|")
        parts += [f"| `{f['id']}` | {f.get('kind', '')} | {f['text']} |" for f in case["facts"]]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "writer_packet.md").write_text("\n".join(parts) + "\n")
    print(f"-> {OUT / 'writer_packet.md'}")


def labels(path):
    rows = [json.loads(x) for x in Path(path).read_text().splitlines() if x.strip()]
    OUT.mkdir(parents=True, exist_ok=True)
    for who, blank in (("writer", False), ("author", True)):
        with (OUT / f"{Path(path).stem}_{who}.csv").open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["case", "line", "memory_ids"])
            w.writerows([r["case"], r["line"], "" if blank else ",".join(r["expect"])] for r in rows)
    print(f"{len(rows)} lines -> {OUT}/{Path(path).stem}_{{writer,author}}.csv")


def _yes(v):
    return str(v).strip().lower() in ("1", "y", "yes", "true")


def kappa(kind, a, b):
    from sklearn.metrics import cohen_kappa_score
    ra, rb = (list(csv.DictReader(open(p))) for p in (a, b))
    if kind == "flags":
        key = {r["id"]: r for r in csv.DictReader(open(OUT / "flags_key.csv"))}
        rb = {r["id"]: r for r in rb}
        for q, jq in zip(QS, ("judge_unsupported", "judge_breaks")):
            ids = [r["id"] for r in ra if r[q].strip() and rb[r["id"]][q].strip()]
            x, y = [_yes(next(r for r in ra if r["id"] == i)[q]) for i in ids], [_yes(rb[i][q]) for i in ids]
            j = [_yes(key[i][jq]) for i in ids]
            print(f"{q}: n={len(ids)} kappa A-B {cohen_kappa_score(x, y):.3f}, A-judge {cohen_kappa_score(x, j):.3f}, "
                  f"B-judge {cohen_kappa_score(y, j):.3f}")
    else:
        mems = {c: [f["id"] for f in brain.load_case(c)["facts"]] for c in CASES}
        lab = lambda rows: {(r["case"], r["line"]): set(filter(None, map(str.strip, r["memory_ids"].split(",")))) for r in rows}  # noqa: E731
        la, lb = lab(ra), lab(rb)
        keys = sorted(set(la) & set(lb))
        x = [m in la[k] for k in keys for m in mems[k[0]]]
        y = [m in lb[k] for k in keys for m in mems[k[0]]]
        print(f"{len(keys)} lines, {len(x)} (line, memory) pairs: kappa {cohen_kappa_score(x, y):.3f}; "
              f"lines with identical labels {sum(la[k] == lb[k] for k in keys) / max(1, len(keys)):.1%}")


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "flags":
        flags()
    elif cmd == "writer":
        writer()
    elif cmd == "labels" and len(sys.argv) == 3:
        labels(sys.argv[2])
    elif cmd == "kappa" and len(sys.argv) == 5:
        kappa(*sys.argv[2:])
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
