"""Exam action router: the doctor's words to ordered exam actions with slots, a relax, or an ask-back ("Which hand?").
Rules only (data/exam_router.json), no LLM call; well under 1 ms a call. Scored by tools/exam_router_eval.py (docs/exam-actions.md)."""
import functools
import re

import brain

_SIDE = re.compile(r"\b(left|right|both)\b")
_PALMS_UP = re.compile(r"\bpalms?\b(?: \w+)? up\b|\bface up\b|\b(?:show|see)\b.*\bpalms\b")
_PLURAL = re.compile(r"\b(?:hands|arms|forearms|sleeves|wrists|palms)\b")
_SINGULAR = re.compile(r"\b(hand|arm|forearm|sleeve)\b")
_SLOT_ONLY = re.compile(r"^(?:with )?(?:your |the )?(?:(?:left|right|both)\b|palms?\b|face (?:up|down)\b)")


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


def _slots(action: str, clause: str, lex: dict) -> dict:
    """Slots for a sided action; which is None when one limb is named without a side (asked back unless a later clause names it)."""
    if action not in lex["sided"]:
        return {}
    side = _SIDE.search(clause)
    one_limb = not side and not _PLURAL.search(clause) and _SINGULAR.search(clause)
    slots = {"which": None if one_limb else side[1] if side else "both"}
    if one_limb:
        noun = _SINGULAR.search(clause)[1]
        slots["_ask"] = "hand" if noun == "hand" else "arm"
    if action == "hold_out_hands":
        slots["palms"] = "up" if _PALMS_UP.search(clause) else "down"
    return slots


def route(text: str) -> dict:
    """{actions, ask_back, relax, asked}: asked is the action waiting for its side after an ask-back (see answer())."""
    lex = load()
    actions, relax = [], False
    for clause in _clauses(text, lex):
        if lex["question"].search(clause):
            continue
        hit = next((a for a, pats in lex["patterns"] if any(p.search(clause) for p in pats)), None)
        if hit is None:
            # "Put your right hand out, palm up" / "...your hand out, the left one": side and palm words refine the previous action
            if actions and _SLOT_ONLY.search(clause):
                prev = actions[-1]["slots"]
                if "palms" in prev and _PALMS_UP.search(clause):
                    prev["palms"] = "up"
                if "which" in prev and (m := _SIDE.search(clause)):
                    prev["which"] = m[1]
                    prev.pop("_ask", None)
            continue
        if hit == "relax":
            relax = True
            continue
        if not actions or actions[-1]["id"] != hit:  # "look at my finger and follow it" is one action
            actions.append({"id": hit, "slots": _slots(hit, clause, lex)})
    unsided = next((a for a in actions if a["slots"].get("which", "") is None), None)
    if unsided:
        actions.remove(unsided)  # the rest still run; this one waits for "the left one"
        ask = lex["ask_back"][unsided["slots"].pop("_ask")]
        return {"actions": actions, "ask_back": ask, "relax": relax, "asked": unsided}
    return {"actions": actions, "ask_back": None, "relax": relax, "asked": None}


def answer(text: str, asked: dict) -> dict | None:
    """The doctor's reply to "Which hand?" ("The left one", "Both"): the asked action with its side, else None."""
    m = _SIDE.search(text.lower())
    return {"id": asked["id"], "slots": {**asked["slots"], "which": m[1]}} if m else None
