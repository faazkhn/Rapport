"""Episodic memory of one consultation (twin-0.2): what the doctor asked and did, what the patient already said, promises,
permission to leave, hurt and kindness, and everyday backstory the patient made up on the spot. Built in code from each turn;
a few relevant lines are retrieved into the next prompt, never the whole session. Lives only in the session (and its local
Twin log); it never feeds learning or the case.
"""
import re

import brain
import rubric

PROMISE = re.compile(r"\b(I('ll| will| promise| am going to|'m going to)|we('ll| will| are going to|'re going to))\b", re.I)
RELATIONS = ("brother", "sister", "mother", "father", "amma", "appa", "wife", "husband", "daughter", "son", "friend", "flatmate", "roommate",
             "manager", "boss", "colleague", "uncle", "aunt", "cousin", "spouse", "neighbour", "neighbor", "grandmother", "grandfather",
             "teacher", "girlfriend", "boyfriend")
# relations a person has only one of; a second name for one of these is a contradiction
SINGLE = {"mother", "father", "amma", "appa", "wife", "husband", "manager", "boss", "flatmate", "roommate", "spouse"}
_REL = "|".join(RELATIONS)
NAMED = re.compile(rf"\b(?:[Mm]y|[Oo]ur)\s+(?:younger |elder |older |little |big |best |old |new |dear )?({_REL})\s*,?\s+([A-Z][a-z]{{2,}})\b")
NAMED_AFTER = re.compile(rf"\b([A-Z][a-z]{{2,}})\s*,?\s*\(?(?:my|her|his|their|{{their}})\s+(?:younger |elder |older |little |big |best )?({_REL})\b")
CLINICAL = re.compile(r"\b(drink|drank|drunk|alcohol|peg|beer|whisky|rum|smoke|cigarette|ganja|weed|drug|tablet|pill|medicine|doctor|hospital|"
                      r"psychiatr|counsel|sleep|appetite|weight|tired|sad|low|depress|anxi|panic|voices|suicid|die|dead|kill|hurt|harm|cry|"
                      r"burden|worthless|fit|seizure|shak)", re.I)
COMMON = {"Doctor", "Sir", "Madam", "Okay", "Yes", "No", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
          "English", "Kannada", "Hindi", "Tamil", "Telugu", "Malayalam", "India", "Indian", "Diwali", "Sankranti", "Ugadi", "Dasara", "Christmas",
          "Eid", "Holi", "Onam", "Pongal", "God", "Amma", "Appa", "Mummy", "Papa"}
MAX_EPISODES = 200
QUOTE_WORDS = 14


def new() -> dict:
    return {"episodes": [], "improvised": [], "names": {}}


def quote(text: str, n: int = QUOTE_WORDS) -> str:
    w = text.split()
    return " ".join(w[:n]) + ("..." if len(w) > n else "")


def case_names(case: dict) -> dict[str, str]:
    """relation -> name fixed by the case (background, life memories, facts): never overridden by anything improvised."""
    text = " ".join([case["patient"].get("background", ""), *(m["text"] for m in case.get("life", [])), *(f["text"] for f in case["facts"])])
    out = {}
    for rel, name in NAMED.findall(text.replace("{their}", "their")):
        out.setdefault(rel.lower(), name)
    for m in re.finditer(rf"\b(?:younger |elder |older )?({_REL})\s+([A-Z][a-z]{{2,}})\b", text):
        out.setdefault(m.group(1).lower(), m.group(2))
    return out


def known_names(case: dict) -> set[str]:
    """Every capitalised word the case itself uses (names and places), plus the patient's own name."""
    text = " ".join([case["patient"]["name"], case["patient"].get("background", ""), case.get("referral_note", ""),
                     *(m["text"] for m in case.get("life", [])), *(f["text"] for f in case["facts"])])
    return set(re.findall(r"\b[A-Z][a-z]{2,}\b", text))


def record(mem: dict, case: dict, turn: int, doctor: str, mv: list[str], recalled: dict, utterance: str, revealed: list[str],
           allowed_leave: bool) -> None:
    """Add this turn's episodes. revealed: facts the guard credited; facts recalled open and answered at some length count as
    discussed too (the model sometimes forgets to list what it said)."""
    eps = mem["episodes"]
    said = utterance.strip()
    discussed = list(dict.fromkeys(revealed + (recalled.get("open", []) if len(said.split()) >= 4 else [])))
    if discussed:
        eps.append({"t": turn, "kind": "told", "facts": discussed, "doctor": quote(doctor), "patient": quote(said)})
    if recalled.get("locked_hit"):
        eps.append({"t": turn, "kind": "asked_locked", "facts": list(recalled["locked_hit"]), "doctor": quote(doctor)})
    if rubric.HURTFUL & set(mv):
        eps.append({"t": turn, "kind": "hurt", "doctor": quote(doctor), "repaired": False})
    if "apology" in mv:
        for e in eps:
            if e["kind"] == "hurt" and not e["repaired"]:
                e["repaired"] = turn
    if {"empathy", "explain_reason", "offer_choice"} & set(mv):
        eps.append({"t": turn, "kind": "kind", "doctor": quote(doctor)})
    if allowed_leave:
        eps.append({"t": turn, "kind": "permission", "doctor": quote(doctor)})
    elif PROMISE.search(doctor) and not doctor.rstrip().endswith("?") and "threat" not in mv:
        eps.append({"t": turn, "kind": "promise", "doctor": quote(doctor)})
    del eps[:-MAX_EPISODES]


def record_improvised(mem: dict, case: dict, turn: int, utterance: str) -> list[str]:
    """Everyday backstory the patient made up (a name or concrete detail the case does not have, nothing clinical): kept so it
    stays true for the rest of the consultation. Returns the sentences stored."""
    import stream
    known, fixed, out = known_names(case), case_names(case), []
    for s in stream.split_sentences(utterance):
        if CLINICAL.search(s):
            continue
        for rel, name in NAMED.findall(s):
            rel = rel.lower()
            if rel not in fixed and rel in SINGLE:
                mem["names"].setdefault(rel, name)
        # capitalised words past the first (sentence starts are capitalised anyway) that the case never uses: a made-up name or place
        new_names = set(re.findall(r"\b[A-Z][a-z]{2,}\b", " ".join(s.split()[1:]))) - known - COMMON
        if new_names and len(s.split()) >= 4:
            mem["improvised"].append({"t": turn, "text": quote(s, 24)})
            out.append(s)
    del mem["improvised"][:-40]
    return out


def repeated(mem: dict, recalled: dict, turn: int) -> bool:
    """The doctor is asking again about something the patient already answered, two or more turns ago."""
    hit = set(recalled.get("open", []))
    return any(e["kind"] == "told" and e["t"] <= turn - 2 and hit & set(e["facts"]) for e in mem["episodes"])


def lines(mem: dict, case: dict, turn: int, recalled: dict, mv: list[str], doctor: str, limit: int = 3) -> list[str]:
    """The few memories that matter for this line, most important first."""
    name = case["patient"]["name"].split()[0]
    eps, out = mem["episodes"], []
    hit = set(recalled.get("open", []))
    told = next((e for e in reversed(eps) if e["kind"] == "told" and e["t"] <= turn - 2 and hit & set(e["facts"])), None)
    if told:
        out.append(f"The doctor already asked about this (turn {told['t']}) and {name} answered: \"{told['patient']}\". {name} may point "
                   f"that out (\"I told you...\") and must stay consistent with it.")
    hurt = next((e for e in reversed(eps) if e["kind"] == "hurt" and turn - e["t"] <= 10), None)
    if hurt and not hurt["repaired"]:
        out.append(f"Earlier (turn {hurt['t']}) the doctor said \"{hurt['doctor']}\"; it still hurts.")
    elif hurt and turn - hurt["repaired"] <= 4:
        out.append(f"The doctor said sorry for \"{hurt['doctor']}\".")
    for kind, text in (("permission", "The doctor said {name} could go: \"{q}\" (turn {t})."),
                       ("promise", "The doctor promised: \"{q}\" (turn {t}).")):
        e = next((e for e in reversed(eps) if e["kind"] == kind and turn - e["t"] <= 15), None)
        if e:
            out.append(text.format(name=name, q=e["doctor"], t=e["t"]))
    if "risk_question" in mv and not (hurt and not hurt["repaired"]):
        kind = next((e for e in reversed(eps) if e["kind"] == "kind"), None)
        if kind:
            out.append(f"This doctor has been kind: \"{kind['doctor']}\".")
    return out[:limit]


def improvised_lines(mem: dict, doctor: str, limit: int = 2) -> list[str]:
    """Made-up backstory that relates to this line (embedding similarity), so the patient repeats it the same way."""
    items = mem["improvised"]
    if not items:
        return []
    import twin
    vecs = twin.embed([doctor] + [i["text"] for i in items])
    if vecs is None:
        return [i["text"] for i in items[-limit:]]
    sims = vecs[1:] @ vecs[0]
    best = sorted(range(len(items)), key=lambda i: -sims[i])[:limit]
    return [items[i]["text"] for i in best if sims[i] >= 0.62]


def sanitize(mem) -> dict:
    """A memory blob that came back from a client (typed /reply): plain types and bounded sizes, or a fresh memory."""
    out = new()
    if not isinstance(mem, dict):
        return out
    for e in (mem.get("episodes") or [])[-MAX_EPISODES:]:
        if isinstance(e, dict) and isinstance(e.get("t"), int) and e.get("kind") in ("told", "asked_locked", "hurt", "kind", "permission", "promise"):
            ok = {k: e[k] for k in ("t", "kind", "repaired") if k in e}
            ok.update({k: str(e[k])[:200] for k in ("doctor", "patient") if k in e})
            ok["facts"] = [str(f)[:40] for f in e.get("facts", [])][:10] if isinstance(e.get("facts"), list) else []
            if e["kind"] == "hurt":
                ok["repaired"] = e.get("repaired") if isinstance(e.get("repaired"), int) and not isinstance(e.get("repaired"), bool) else False
            out["episodes"].append(ok)
    for i in (mem.get("improvised") or [])[-40:]:
        if isinstance(i, dict) and isinstance(i.get("t"), int) and isinstance(i.get("text"), str):
            out["improvised"].append({"t": i["t"], "text": i["text"][:200]})
    if isinstance(mem.get("names"), dict):
        out["names"] = {str(k)[:20]: str(v)[:30] for k, v in list(mem["names"].items())[:20] if str(k) in SINGLE}
    return out
