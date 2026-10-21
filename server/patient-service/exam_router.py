"""Exam action router: the doctor's words to ordered exam actions with slots, a relax, or an ask-back ("Which hand?").
Rules only (data/exam_router.json), no LLM call; well under 1 ms a call. Scored by tools/exam_router_eval.py (docs/exam-actions.md)."""
import functools
import re

import brain

_SIDE = re.compile(r"\b(left|right|both)\b")
_PALMS_UP = re.compile(r"\bpalms?\b(?: \w+)? up\b|\bface up\b|\b(?:show|see)\b.*\bpalms\b")
_PLURAL = re.compile(r"\b(?:hands|arms|forearms|sleeves|wrists|palms)\b")
_SINGULAR = re.compile(r"\b(hand|arm|forearm|sleeve)\b")
_SLOT_ONLY = re.compile(r"^(?:with )?(?:your )?(?:(?:left|right|both)\b|palms?\b|face (?:up|down)\b)")


@functools.cache
def load() -> dict:
    lex = brain.load_json("exam_router.json")
    c = {k: re.compile(lex[k]) for k in ("split", "lead_filler", "any_filler", "question")}
    c["patterns"] = [(a, [re.compile(p) for p in lex["patterns"][a]]) for a in lex["order"]]
    c["contractions"], c["sided"], c["ask_back"] = lex["contractions"], lex["sided"], lex["ask_back"]
    return c


def _clauses(text: str, lex: dict) -> list[str]:
    t = text.lower().replace("’", "'")
    for k, v in lex["contractions"].items():
        t = t.replace(k, v)
    out = []
    for c in lex["split"].split(t):
        c = lex["any_filler"].sub(" ", c)
        c = re.sub(r"\s+", " ", lex["lead_filler"].sub("", c.strip())).strip()
        if c:
            out.append(c)
    return out


def _slots(action: str, clause: str, lex: dict) -> dict | str:
    """Slots for a sided action, or the ask-back noun ('hand'/'arm') when one limb is named without a side."""
    if action not in lex["sided"]:
        return {}
    side = _SIDE.search(clause)
    if not side and not _PLURAL.search(clause) and _SINGULAR.search(clause):
        return lex["sided"][action] if _SINGULAR.search(clause)[1] == "hand" or action != "hold_out_hands" else "arm"
    slots = {"which": side[1] if side else "both"}
    if action == "hold_out_hands":
        slots["palms"] = "up" if _PALMS_UP.search(clause) else "down"
    return slots


def route(text: str) -> dict:
    lex = load()
    actions, ask, relax = [], None, False
    for clause in _clauses(text, lex):
        if lex["question"].search(clause):
            continue
        hit = next((a for a, pats in lex["patterns"] if any(p.search(clause) for p in pats)), None)
        if hit is None:
            # "Put your right hand out, palm up": a clause of only side/palm words refines the previous action
            if actions and _SLOT_ONLY.search(clause):
                prev = actions[-1]["slots"]
                if "palms" in prev and _PALMS_UP.search(clause):
                    prev["palms"] = "up"
                if "which" in prev and (m := _SIDE.search(clause)):
                    prev["which"] = m[1]
            continue
        if hit == "relax":
            relax = True
            continue
        slots = _slots(hit, clause, lex)
        if isinstance(slots, str):
            ask = lex["ask_back"][slots]
            continue
        if not actions or actions[-1]["id"] != hit:  # "look at my finger and follow it" is one action
            actions.append({"id": hit, "slots": slots})
    if ask:
        return {"actions": [], "ask_back": ask, "relax": relax}
    return {"actions": actions, "ask_back": None, "relax": relax}
