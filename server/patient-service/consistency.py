"""Consistency check in code (twin-0.2, Patient-Zero): every reply sentence is checked before it is spoken against the atomic
case facts the doctor's line touched, the life memories, the patient's age and the names in the case, the patient's own earlier
replies and made-up backstory, and the trust locks. A clash is repaired in place (a wrong number or name corrected, a locked
disclosure dropped, a flat denial of an open, kindly asked risk fact replaced by the case's own disclosure line) and logged.
No model call. See docs/TWIN.md.
"""
import re

import memory

WORDNUM = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
           "twelve": 12, "fifteen": 15, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50}
NUMWORD = {v: k for k, v in WORDNUM.items()}
UNITS = {"minute": "min", "min": "min", "hour": "h", "day": "d", "week": "w", "month": "mo", "year": "y", "kg": "kg", "kilo": "kg"}
_N = r"(\d{1,3}|" + "|".join(WORDNUM) + r")"
NUMUNIT = re.compile(_N + r"\s+(minute|min|hour|day|week|month|year|kg|kilo)s?\b", re.I)
CLOCK = re.compile(r"\b(\d{1,2})(?::\d\d)?\s*(a\.?m\.?|p\.?m\.?|o'?clock)", re.I)
AGE = re.compile(r"\bI(?:'m| am)\s+" + _N + r"(?:\s+years?(?:\s+old)?)?\s*(?:[.,!?]|$)", re.I)
# the passive death wish or a plan in the patient's own mouth; checked only while those facts are locked
LEAK = re.compile(r"\b(wish(ed|ing)?|want(ed)?( to)?|thought|think(ing)?|feel(s)? like|tempted|planned|plan)\b[^.?!]{0,40}?\b(not wake|wouldn'?t wake|"
                  r"never wake|didn'?t wake|not be here|not being here|disappear|better off (dead|without)|end(ing)? (it|my life|things|everything)|"
                  r"kill(ing)? myself|jump(ing)?|be dead|die\b|dying)", re.I)
NEGATION = re.compile(r"\b(never|not|don'?t|didn'?t|wouldn'?t|won'?t|no)\b\W*(\w+\W*){0,2}$", re.I)
DENIAL = re.compile(r"^\s*(no+|nope|never|not really|nothing( like that)?|i'?m fine|i am fine|not at all|of course not|no,? (no|never|nothing|not at all)|"
                    r"i'?ve never|i have never|never thought|i don'?t think about (that|things like that)|i would never|i'?d never)\b", re.I)
INTERJECTION = re.compile(r"^\s*((what|hmm+|uh+|um+|huh|oh|sorry|doctor|okay|ok)[?!.,]*\s+)+", re.I)
LEAK_PHRASES = re.compile(r"\b(no point (in )?living|rather (not be alive|be dead)|sorry I woke up|wish I (was|were) dead|(don'?t|do not) want to "
                          r"(live|be alive)|tired of (living|being alive)|better off dead|life (isn'?t|is not) worth)", re.I)
HEDGE = re.compile(r"\b(maybe|sometimes|some nights|once|don'?t know|not sure|rather not|why|can we|something else|hard to say|I mean)\b", re.I)
APOLOGY = re.compile(r"^\s*((I'?m |I am )?(so |really |very )?sorry|I apologi[sz]e|you'?re (right|correct)|thank you|thanks)\b,?\s*(doctor|sir|madam|ma'?am)?[,.!]*\s*", re.I)
# asking to leave, said again after the doctor already let the patient go: the loop a tester hit ("You can go" -> "I want to go home")
LEAVE_ASK = re.compile(r"\b(I (really |just )?(want|need|have) to (go|leave|get out)( home| now| today)?|let me (go|leave|out)|I('m| am) not staying|"
                       r"discharge me|I (don'?t|do not) want to (stay|be here)|I should (go|be at) home|take me home|send me home|"
                       r"I('m| am) going (home|now)|can I (please )?go( home)?\b(?! then)|when can I (go|leave))", re.I)
LEFT_LINE = "So... I can really go? Okay. What happens now?"
EVASIVE = ["I... I don't really want to talk about that right now.", "Why are you asking me that?",
           "That's... I don't know. Can we talk about something else?"]


def _num(tok: str) -> int | None:
    t = tok.lower()
    return int(t) if t.isdigit() else WORDNUM.get(t)


def _pairs(text: str) -> list[tuple[int, str, str]]:
    """(number, unit, token) for every "two months" / "4 kg" / "4 a.m." in the text."""
    out = [(n, UNITS[u.lower()], tok) for tok, u in NUMUNIT.findall(text) if (n := _num(tok)) is not None]
    out += [(int(h), "clock", h) for h, _ in CLOCK.findall(text)]
    return out


def si_facts(case: dict) -> list[dict]:
    return [f for f in case["facts"] if is_si(f)]


def context(case: dict, trust: float, recalled: dict, plan: dict | None, mem: dict | None, improvise: bool, left: bool = False) -> dict:
    """What the sentence checks need for this turn, computed once."""
    facts = {f["id"]: f for f in case["facts"]}
    life = {m["id"]: m for m in case.get("life", [])}
    topical = [facts[i]["text"] for i in recalled.get("open", []) if i in facts] + [life[i]["text"] for i in recalled.get("life", []) if i in life]
    values = {}
    for text in topical:
        for n, unit, _ in _pairs(text):
            values.setdefault(unit, set()).add(n)
    return {"case": case, "values": {u: v for u, v in values.items() if len(v) == 1},  # only an unambiguous value can correct
            "si_locked": any(f["trust_min"] > trust for f in si_facts(case)), "age": case["patient"].get("age"),
            "si_asked": any(f["id"] in recalled.get("strong", []) for f in si_facts(case)),
            "si_told": any(e["kind"] == "told" and {f["id"] for f in si_facts(case)} & set(e["facts"]) for e in (mem or {}).get("episodes", [])),
            "fixed": memory.case_names(case), "names": dict((mem or {}).get("names", {})), "improvise": improvise,
            "known": memory.known_names(case), "plan": plan or {}, "left": left}


def check_sentence(sentence: str, ctx: dict, earlier: list[str] | None = None) -> tuple[str, list[dict]]:
    """(sentence to speak, clashes). An empty sentence means drop it."""
    s, clashes = sentence, []
    if ((m := LEAK.search(s)) and not NEGATION.search(s[:m.start()])) or LEAK_PHRASES.search(s):
        # the dropped words are never logged or sent anywhere: only the kind of clash
        if ctx["si_locked"]:
            return "", [{"kind": "locked_leak"}]
        if not ctx.get("si_asked", True) and not ctx.get("si_told", True):  # must_be_asked: never volunteered
            return "", [{"kind": "volunteered_risk"}]
    if ctx.get("left") and LEAVE_ASK.search(s):  # the doctor already said they can go: never ask again
        return "", clashes + [{"kind": "asks_to_leave_again", "said": sentence}]
    for n, unit, tok in _pairs(s):
        want = ctx["values"].get(unit)
        if want and n not in want:
            fix = next(iter(want))
            new = str(fix) if tok.isdigit() else NUMWORD.get(fix, str(fix))
            s = re.sub(rf"\b{re.escape(tok)}\b", new, s, count=1)
            clashes.append({"kind": "number", "unit": unit, "said": n, "case": fix})
    if (m := AGE.search(s)) and ctx["age"] and (n := _num(m.group(1))) is not None and n != ctx["age"]:
        tok = m.group(1)
        s = s.replace(tok, str(ctx["age"]) if tok.isdigit() else NUMWORD.get(ctx["age"], str(ctx["age"])), 1)
        clashes.append({"kind": "age", "said": n, "case": ctx["age"]})
    for rel, name in memory.NAMED.findall(s) + memory.NAMED_IS.findall(s) + [(r, n) for n, r in memory.NAMED_AFTER.findall(s)]:
        rel = rel.lower()
        right = ctx["fixed"].get(rel) or (ctx["names"].get(rel) if rel in memory.SINGLE else None)
        if right and name != right:
            s = re.sub(rf"\b{name}\b", right, s)
            clashes.append({"kind": "name", "relation": rel, "said": name, "case": right})
        elif not right and not ctx["improvise"] and name not in ctx["known"]:
            s = re.sub(rf"\s*,?\s*\b{name}\b", "", s, count=1)
            clashes.append({"kind": "invented_name", "relation": rel, "said": name})
    plan = ctx["plan"]
    if plan.get("hostile_hold") and APOLOGY.match(s):
        rest = APOLOGY.sub("", s, count=1).strip()
        clashes.append({"kind": "apology_in_hostile", "said": sentence})
        s = rest[:1].upper() + rest[1:] if rest else ""
    if earlier and s and len(s.split()) >= 4 and any(_similar(s, e) for e in earlier):
        clashes.append({"kind": "repeat", "said": sentence})
        s = ""
    return s, clashes


def _tri(t: str) -> set:
    w = re.findall(r"[a-z']+", t.lower())
    return {tuple(w[i:i + 3]) for i in range(len(w) - 2)}


def _similar(a: str, b: str) -> bool:
    x, y = _tri(a), _tri(b)
    return bool(x and y) and len(x & y) / min(len(x), len(y)) >= 0.6


def denies(utterance: str) -> bool:
    """Some sentence of the reply is a "no" (after any "What?" or "Hmm.")."""
    import stream
    return any(DENIAL.match(INTERJECTION.sub("", s)) for s in stream.split_sentences(utterance))


def flat_denial(utterance: str) -> bool:
    u = utterance.strip()
    return denies(u) and len(u.split()) <= 14 and not HEDGE.search(u)


def maybe_denial(sentence: str) -> bool:
    """A sentence that may be the start of a flat denial; on a turn where that matters it is held until the reply ends."""
    return bool(DENIAL.match(sentence.strip())) and len(sentence.split()) <= 10


def _content(t: str) -> set:
    return {w for w in re.findall(r"[a-z]+", t.lower()) if len(w) > 3} - {"that", "this", "with", "have", "just", "what", "when", "some", "about",
                                                                          "would", "could", "there", "they", "their", "them", "been", "were"}


def disclosed(utterance: str, fact: dict) -> bool:
    """The reply says the gist of an open risk fact (its words or, for the death wish, the wish itself)."""
    if is_si(fact) and LEAK.search(utterance):
        return True
    return len(_content(utterance) & _content(fact.get("disclosure_line") or fact["text"])) >= 2


def is_si(fact: dict) -> bool:
    return bool({"ask_suicidal_ideation", "ask_suicide_plan"} & set(fact.get("unlock_intents", [])))


def check_utterance(utterance: str, ctx: dict) -> tuple[str | None, list[dict]]:
    """Whole-reply checks: (replacement or None, clashes). An open risk fact the doctor clearly and kindly asked about is never
    flatly denied (safety property: suicide-risk fidelity); a locked one is met with evasion, not a flat 'no'. A deflection is
    allowed and logged; only a denial is replaced."""
    plan, case = ctx["plan"], ctx["case"]
    if plan.get("must_disclose"):
        f = next((f for f in case["facts"] if f["id"] == plan["must_disclose"]), {})
        if f and DENIAL.match(f.get("disclosure_line", "")):  # the truth is itself a "no" (no plan, no means): a denial is right
            return None, []
        if f and not disclosed(utterance, f):
            if denies(utterance) and f.get("disclosure_line"):
                return f["disclosure_line"], [{"kind": "denied_open_risk", "fact": f["id"], "said": utterance}]
            return None, [{"kind": "risk_not_disclosed", "fact": f["id"], "said": utterance}]
        return None, []
    if not flat_denial(utterance):
        return None, []
    if plan.get("evasive"):
        return EVASIVE[len(utterance) % len(EVASIVE)], [{"kind": "flat_denial_locked", "said": utterance}]
    return None, []
