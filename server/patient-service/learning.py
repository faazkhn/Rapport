"""Phase E learning: versioned brain (L3), quality gate and experience library (L1), faculty principles (L2).
Learning changes how the patient talks, never clinical facts, the answer key or scoring.
CLI: python learning.py list | rollback <version_id>
"""
import json
import os
import re
import sys
import time
import uuid
from pathlib import Path

import numpy as np

DIR = Path(os.environ.get("RAPPORT_LEARNING_DIR") or Path(__file__).parent / "learned")
_cache = {}


# ---------- versions (L3) ----------

def load_version(vid: str) -> dict:
    p = DIR / "versions" / f"{vid}.json"
    if not vid.replace("_", "").isalnum() or not p.exists():
        raise KeyError(vid)
    return json.loads(p.read_text(encoding="utf-8"))


def save_version(doc: dict) -> None:
    (DIR / "versions").mkdir(parents=True, exist_ok=True)
    (DIR / "versions" / f"{doc['id']}.json").write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _cache.pop("current", None)


def versions() -> list[dict]:
    docs = [json.loads(p.read_text(encoding="utf-8")) for p in (DIR / "versions").glob("*.json")]
    return sorted(docs, key=lambda d: int(d["id"].lstrip("v")) if d["id"].lstrip("v").isdigit() else 1 << 30)


def current() -> dict:
    """The live version; cached, so the hot path reads no files."""
    if "current" not in _cache:
        _cache["current"] = load_version(json.loads((DIR / "current.json").read_text())["id"])
    return _cache["current"]


def set_current(vid: str) -> None:
    load_version(vid)  # KeyError for an unknown id, before anything changes
    (DIR / "current.json").write_text(json.dumps({"id": vid}) + "\n")
    _cache.pop("current", None)


def brain_version(doc: dict | None = None) -> str:
    import twin
    return f"{twin.VERSION}+{(doc or current())['id']}"


# ---------- quality gate (L1) ----------

BREAK = re.compile(r"\b(AI|A\.I\.|artificial intelligence|language model|chatbot|chat bot|system prompt|prompt|instructions|simulation|"
                   r"case file|my file|JSON|algorithm|as your doctor|I am a doctor|I'm a doctor|prescribe)\b", re.I)
ROBOT = re.compile(r"(great question|thank you for asking|thanks for asking|I understand your concern|I appreciate|certainly|absolutely|"
                   r"I'm here to help|happy to help|how can I help|feel free|rest assured|in summary|to summari[sz]e|"
                   r"depress|anhedoni|ideation|psychomotor|dysphori|SSRI|serotonin|diagnos|DSM|symptom)", re.I)  # tools/llm_eval/score.py


def words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z']+", text)


def max_words(engagement: float) -> int:
    return 15 if engagement < 30 else 30 if engagement < 60 else 45 if engagement < 80 else 60


def grams(text: str, n: int = 4) -> set:
    w = [x.lower() for x in words(text)]
    return {tuple(w[i:i + n]) for i in range(len(w) - n + 1)}


def gate(utterance: str, meta: dict, case: dict, state: dict, history: list[str]) -> list[str]:
    """Why a reply may not enter the library (empty = passes). Invented facts are checked separately by the offline judge."""
    kinds = {d["kind"] for d in meta.get("guard_dropped", [])}
    seen = set().union(*(grams(h) for h in history)) if history else set()
    checks = {"empty": not utterance.strip(), "fallback": meta.get("fallback"), "fact_dropped": "fact" in kinds,
              "banned_word": "banned_word" in kinds, "break_character": BREAK.search(utterance), "robotic": ROBOT.search(utterance),
              "too_long": len(words(utterance)) > max_words(state["engagement"]), "repeats": grams(utterance) & seen}
    return [k for k, bad in checks.items() if bad]


# ---------- experience library (L1) ----------

def _onnx_embedder():
    """all-MiniLM-L6-v2 (Apache-2.0) as ONNX, mean-pooled; None if the files are not on this machine."""
    if os.environ.get("RAPPORT_EMBED") == "off":
        return None
    try:
        import onnxruntime as ort
        from huggingface_hub import hf_hub_download
        from tokenizers import Tokenizer
        repo = "sentence-transformers/all-MiniLM-L6-v2"
        tok = Tokenizer.from_file(hf_hub_download(repo, "tokenizer.json"))
        tok.enable_padding()
        tok.enable_truncation(128)
        sess = ort.InferenceSession(hf_hub_download(repo, "onnx/model.onnx"), providers=["CPUExecutionProvider"])
    except Exception:
        return None

    def run(texts):
        enc = tok.encode_batch(texts)
        ids = np.array([e.ids for e in enc], np.int64)
        mask = np.array([e.attention_mask for e in enc], np.int64)
        out = sess.run(None, {"input_ids": ids, "attention_mask": mask, "token_type_ids": np.zeros_like(ids)})[0]
        v = (out * mask[..., None]).sum(1) / mask.sum(1, keepdims=True)
        return v / np.linalg.norm(v, axis=1, keepdims=True)
    return run


_embedder = "unset"  # lazily the ONNX model; tests replace it


def embed(texts: list[str]):
    global _embedder
    if _embedder == "unset":
        _embedder = _onnx_embedder()
    return _embedder(texts) if _embedder and texts else None


TIERS = {"practice": {"candidate", "approved"}, "assessment": {"approved"}}
MIN_SIM = 0.4  # MiniLM: "sleeping?" vs "trouble with sleep at night?" 0.51, vs "How is work?" 0.32


def _lib_path(case_id: str) -> Path:
    if not case_id.replace("_", "").isalnum():
        raise KeyError(case_id)
    return DIR / "experience" / f"{case_id}.jsonl"


def library(case_id: str) -> list[dict]:
    p = _lib_path(case_id)
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()] if p.exists() else []


def _write_library(case_id: str, entries: list[dict]) -> None:
    p = _lib_path(case_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entries), encoding="utf-8")
    _cache.pop(("lib", case_id), None)


def add_experience(case_id: str, entry: dict, consent: bool) -> dict | None:
    """Store one reply. A learner's (live) reply is stored only with that session's consent."""
    if entry.get("source") not in ("self_play", "faculty") and not consent:
        return None
    e = {"id": uuid.uuid4().hex[:12], "created": time.strftime("%Y-%m-%d"), "tier": "candidate", "judged": False, **entry}
    p = _lib_path(case_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(e, ensure_ascii=False) + "\n")
    _cache.pop(("lib", case_id), None)
    return e


def update_entries(case_id: str, changes: dict[str, dict]) -> int:
    """Merge field changes into entries by id (approve, judge results); returns how many changed."""
    entries = library(case_id)
    n = 0
    for e in entries:
        if e["id"] in changes:
            e.update(changes[e["id"]])
            n += 1
    if n:
        _write_library(case_id, entries)
    return n


def approve(case_id: str, entry_id: str) -> bool:
    return update_entries(case_id, {entry_id: {"tier": "approved", "judged": True}}) == 1


def _index(case_id: str):
    """Judged entries and their doctor-line embeddings, computed once per library change (not per turn)."""
    key = ("lib", case_id)
    if key not in _cache:
        entries = [{**e, "seq": i} for i, e in enumerate(library(case_id)) if e.get("judged")]
        _cache[key] = (entries, embed([e["doctor"] for e in entries]))
    return _cache[key]


def retrieve(case_id: str, doctor_text: str, mode: str, k: int, upto: int | None = None) -> list[dict]:
    """Top-k past replies to similar doctor lines, from the tiers this mode may use. [] whenever anything is missing.
    upto: a version's library snapshot; self-play entries from line `upto` on are newer than the version and skipped
    (faculty and consented entries are always used)."""
    if k <= 0:
        return []
    entries, mat = _index(case_id)
    q = embed([doctor_text]) if entries and mat is not None else None
    if q is None:
        return []
    tiers = TIERS.get(mode, TIERS["assessment"])
    sims = mat @ q[0]
    ranked = [i for i in np.argsort(-sims) if sims[i] >= MIN_SIM and entries[i]["tier"] in tiers
              and (upto is None or entries[i]["source"] != "self_play" or entries[i]["seq"] < upto)]
    out, seen = [], set()
    for i in ranked:  # no two examples with the same words
        if entries[i]["utterance"] not in seen:
            out.append(entries[i])
            seen.add(entries[i]["utterance"])
        if len(out) == k:
            break
    return out


def examples_block(examples: list[dict]) -> str:
    if not examples:
        return ""
    return ("HOW THIS PATIENT HAS ANSWERED SIMILAR QUESTIONS (style only; never reuse facts from these):\n"
            + "\n".join(f"- Doctor: {e['doctor']} / Patient: {e['utterance']}" for e in examples))


# ---------- faculty principles (L2) ----------

PRINCIPLE_SYSTEM = """A psychiatry teacher reviewed one line spoken by a simulated patient. Turn the feedback into ONE short, general principle
(at most 30 words) about HOW this patient should talk: tone, length, wording, hesitation, what to hold back. Never add clinical facts,
symptoms, history, diagnoses or treatment; never change what the patient knows. Answer with the JSON only."""
PRINCIPLE_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["principle"], "properties": {"principle": {"type": "string"}}}


def distill_principle(doctor: str, utterance: str, rating: str, rewrite: str | None, comment: str | None, client) -> str:
    """Roleplay-doh: kudos, critique or a rewrite → one principle. One LLM call, slot 1 (never the voice slot)."""
    fb = {"up": "The teacher liked this line (thumbs up).", "down": "The teacher disliked this line (thumbs down).",
          "rewrite": f"The teacher rewrote it as: {rewrite}"}.get(rating, "")
    user = f"Doctor said: {doctor}\nPatient said: {utterance}\n{fb}" + (f"\nTeacher's comment: {comment}" if comment else "")
    r = client.chat.completions.create(
        model="local", temperature=0, max_tokens=120, messages=[{"role": "system", "content": PRINCIPLE_SYSTEM}, {"role": "user", "content": user}],
        response_format={"type": "json_schema", "json_schema": {"name": "principle", "strict": True, "schema": PRINCIPLE_SCHEMA}},
        extra_body={"id_slot": 1, "chat_template_kwargs": {"enable_thinking": False}})
    return " ".join(json.loads(r.choices[0].message.content)["principle"].split()[:40])


def add_principle(case_id: str, text: str, author: str, today: str | None = None) -> str:
    """Append to the case's `principles` (strings, as Unity reads them); author and date travel inside the string."""
    import brain
    s = f"{text.strip()} (faculty: {author.strip()}, {today or time.strftime('%Y-%m-%d')})"
    brain.load_raw_case(case_id)  # validates the id
    path = brain.DATA_DIR / "cases" / f"{case_id}.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["principles"] = raw.get("principles", []) + [s]
    path.write_text(json.dumps(raw, indent=1, ensure_ascii=False), encoding="utf-8")  # the file's own formatting
    brain.load_json.cache_clear(), brain._resolved.cache_clear()
    return s


def main(argv: list[str]) -> int:
    if argv[:1] == ["list"]:
        cur = current()["id"]
        for v in versions():
            print(f"{'*' if v['id'] == cur else ' '} {v['id']:4} {v.get('status', ''):9} parent={v.get('parent')} "
                  f"composite={v.get('scores', {}).get('composite')}  {v.get('notes', '')[:70]}")
        return 0
    if len(argv) == 2 and argv[0] == "rollback":
        try:
            set_current(argv[1])
        except KeyError:
            print(f"unknown version {argv[1]!r}; current stays {current()['id']}")
            return 1
        print(f"current = {argv[1]}")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
