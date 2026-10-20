"""Digital Twin: the patient's mind for one live turn. Recall with trust locks (no LLM), label checks and the code-built reason,
the slow-path state and mood update, the expression map, and the brain_snapshot. See docs/TWIN.md.
"""
import re

_WORD = re.compile(r"[a-z']+")
_SUFFIX = re.compile(r"(ing|ed|es|s)$")


def _stem(w: str) -> str:
    return _SUFFIX.sub("", w) if len(w) > 4 else w


def _words(text: str) -> list[str]:
    return _WORD.findall(text.lower())


def recall(case: dict, trust: float, doctor_text: str, limit: int = 3) -> dict:
    """Memory items the doctor's words touch. Open ones (trust_min <= trust) come best first, at most `limit`; locked ones are
    only reported as hits, never their content."""
    # shortcut: lexical tags only, no embeddings; upgrade when an embedding model is chosen (Phase D2)
    words = _words(doctor_text)
    stems, phrase = {_stem(w) for w in words}, " " + " ".join(words) + " "
    scored = []
    for f in case["facts"]:
        score = 0
        for tag in f.get("activation_tags", []):
            tw = _words(tag)
            if len(tw) > 1:
                score += 2 * (" " + " ".join(tw) + " " in phrase)
            elif tw:
                score += _stem(tw[0]) in stems
        if score:
            scored.append((score, f))
    scored.sort(key=lambda x: -x[0])
    open_ = [f["id"] for _, f in scored if f["trust_min"] <= trust][:limit]
    locked = [f["id"] for _, f in scored if f["trust_min"] > trust]
    hot = any(f.get("generates_discomfort") for _, f in scored if f["id"] in open_)
    return {"open": open_, "locked_hit": locked, "discomfort": bool(locked) or hot}


def _topic(fact_id: str) -> str:
    return fact_id.removeprefix("f_").replace("_", " ")


def why(recalled: dict, reply: dict, trust: float, case: dict) -> str:
    """One plain sentence for the examiner: what came to mind, what stayed locked, and how the patient chose to answer."""
    mins = {f["id"]: f["trust_min"] for f in case["facts"]}
    parts = []
    if recalled.get("open"):
        top = recalled["open"][0]
        parts.append(f"{_topic(top).capitalize()} memory open (trust {trust:.0f} ≥ {mins[top]:.0f}).")
    if recalled.get("locked_hit"):
        need = min(mins[i] for i in recalled["locked_hit"])
        parts.append(f"Touched something locked (needs trust {need:.0f}); showed discomfort.")
    behaviour = reply.get("behaviour", "answers_plainly").replace("_", " ")
    parts.append(f"Reaction {reply.get('reaction', 'none').replace('_', ' ')}, {behaviour}.")
    return " ".join(parts)
