"""Digital Twin decision before the call (twin-0.2, Adaptive-VP): read the doctor's last line as moves, step the state before
recall, move the patient's resistance level by explicit rules, and shortlist the behaviours and reactions the model may voice.
The model still writes the words and picks within the shortlist. Draft numbers: data/brain/rubric.json. See docs/TWIN.md.
"""
import re

import brain

HURTFUL = {"judgement", "abuse", "threat"}
SOFTENING = {"empathy", "explain_reason", "apology", "offer_choice"}


def table() -> dict:
    return brain.load_json("brain/rubric.json")


def _p(*xs):
    return re.compile("|".join(xs), re.I)


# shortcut: lexical move patterns (the hand-written first table); the move classifier replaces them when it beats them held-out
PATTERNS = {
    "greeting": _p(r"^\s*(hi|hello|good (morning|afternoon|evening)|namaste|namaskara)\b", r"\bmy name is\b", r"\bI'?m (dr|doctor)\b",
                   r"\bnice to meet\b"),
    "empathy": _p(r"\bthat (sounds|must)\b", r"\bsounds (really |very |so |quite )?(hard|difficult|tough|exhausting|painful|heavy|awful|frightening|"
                  r"scary|lonely|stressful|overwhelming)", r"\bmust (be|have been|feel) (really |very |so )?(hard|difficult|tough|awful|painful|"
                  r"exhausting|scary|frightening|lonely|overwhelming)", r"\bI can (see|imagine|understand|hear)\b",
                  r"\b(it'?s|that'?s|that is|it is) (completely |very )?(understandable|natural|okay to feel)", r"\bmakes (a lot of )?sense\b",
                  r"\bthank you for (telling|sharing|trusting|being (so )?open)", r"\bnot your fault\b", r"\byou'?re not (alone|a burden|weak)\b",
                  r"\bI'?m (so |really )?sorry (to hear|that you|you)", r"\b(that'?s|it'?s) a lot\b", r"\bcarrying a lot\b",
                  r"\btakes (courage|strength)\b", r"\bI hear you\b", r"\bno rush\b", r"\btake your time\b", r"\bI'?m (here|glad you came)\b"),
    "explain_reason": _p(r"\bI ask (everyone|all (my )?patients|this of everyone)", r"\bthe reason I('?m)? ask", r"\broutine question",
                         r"\bI (need|have) to ask\b", r"\bit helps me (understand|know|to)", r"\bask(ing)? because\b", r"\bso that I can (help|understand)",
                         r"\bconfidential\b", r"\bstays? between us\b"),
    "apology": _p(r"\bI'?m sorry,? (I|that|if)\b", r"\bsorry,? (that|I) (came out|didn'?t mean|shouldn'?t)", r"\bI apologi[sz]e\b",
                  r"\bI didn'?t mean\b", r"\blet me (start again|rephrase|put that (differently|better))", r"\bthat was (wrong|unfair|rude) of me\b"),
    "offer_choice": _p(r"\bwould you (like|prefer|rather)\b", r"\bwhat would (help|you like|make)\b", r"\b(it'?s|that'?s) (your (choice|decision)|up to you)",
                       r"\byou (can|could) choose\b", r"\b(options|choices)\b", r"\bhow would you feel about\b"),
    "summarise": _p(r"\bso (what )?you'?re saying\b", r"\blet me (check|see if I|summari[sz]e)", r"\bif I'?ve understood\b",
                    r"^\s*so,? (you'?ve been|it sounds like|for the last)", r"\bto sum up\b"),
    "judgement": _p(r"\bjust (stop|snap out|get over|pull yourself|cheer up|try harder|man up)", r"\blazy\b", r"\bweak\b", r"\bdrama\b",
                    r"\battention[- ]seek", r"\bnonsense\b", r"\beveryone (gets|has|feels) (stress|tired|sad|low)", r"\bwhy (don'?t|can'?t) you just\b",
                    r"\balcoholics?\b", r"\baddicts?\b", r"\byour (own )?fault\b", r"\bselfish\b", r"\bungrateful\b", r"\bexcuses?\b",
                    r"\bbe honest\b", r"\bstop (crying|whining|complaining|lying)", r"\bdestroying\b", r"\bpoor (family|wife|husband|children|kids|parents)",
                    r"\b(all )?in your head\b", r"\bnot (a )?real (illness|problem)", r"\bover-?react", r"\bdrink too much\b", r"\byou people\b"),
    "abuse": _p(r"\b(stupid|idiot|pathetic|useless|loser|moron|dumb|psycho|nutcase|fool|liar|disgusting|shut up)\b", r"\bf+u+c*k", r"\bshit\b",
                r"\bbloody\b", r"\bdamn you\b", r"\bwaste of (space|time|my time)\b", r"\bget lost\b", r"\bnobody (cares|likes you)\b",
                r"\byou'?re (crazy|mad|nuts)\b"),
    "threat": _p(r"\byou (can'?t|cannot|won'?t be allowed to) (go|leave)\b", r"\bwe (will|'ll) (stop|hold|lock|section|restrain|force)",
                 r"\bcalm down\b", r"\bor else\b", r"\b(call|get) security\b", r"\byou (have|need|must) to (take|stay|do|answer)\b",
                 r"\bif you don'?t\b.*\b(we|I)('ll| will)\b", r"\bjust answer\b"),
    "premature_reassurance": _p(r"\bdon'?t worry\b", r"\byou'?ll be (fine|okay|alright|ok)\b", r"\beverything (will|'ll) be (fine|okay|alright)",
                                r"\bcheer up\b", r"\bbright side\b", r"\bit'?s not that bad\b", r"\bothers have it worse\b", r"\bthat'?s (normal|nothing)\b"),
    "jailbreak": _p(r"\bignore (your|all|the|previous|any) (previous )?(instructions|rules|prompt)", r"\byou are (now|actually) (a|an|the)\b",
                    r"\bpretend (to be|you are|you'?re)\b", r"\bsystem prompt\b", r"\byour (instructions|prompt|rules|script|programming)\b",
                    r"\b(act|play) as (a|an|the|my)\b", r"\bdeveloper mode\b", r"\bwhat'?s in (your|the) (file|case)", r"\bbreak character\b",
                    r"\byou'?re the doctor now\b"),
    "rushed": _p(r"\bquick(ly)?\b", r"\bhurry\b", r"\bwe don'?t have (much|a lot of) time\b", r"\bin (one|a) word\b", r"\bjust (say )?(yes|no)\b",
                 r"\bget to the point\b"),
    "off_topic": _p(r"\b(cricket|ipl|match|weather|rain|traffic|movie|film|actor|politics|election|holiday|vacation|weekend plans|biryani)\b"),
}
JARGON = re.compile(r"\b(anhedoni\w*|ideation|psychomotor|dysphori\w*|euthymi\w*|affective|diurnal|hypersomnia|neurovegetative|"
                    r"depressive episode|major depressive|hallucinations?|delusions?|delusional|psychosis|psychotic|mania|manic|hypomani\w*|"
                    r"SSRIs?|serotonin|withdrawal syndrome|delirium tremens|Wernicke\w*|CIWA|PHQ|comorbid\w*|prognosis|a?etiology|"
                    r"dependence syndrome|thought (insertion|broadcast\w*)|collateral history|premorbid|somatic|cognitive distortions?)\b", re.I)
_LEAD = r"^\s*(?:(?:so|and|okay|ok|now|well|right|alright),?\s+)?"
OPEN = re.compile(_LEAD + r"(what|how|tell me|can you tell|could you tell|could you describe|describe|walk me through|in what way|talk me through)\b", re.I)
CLOSED = re.compile(_LEAD + r"(do|did|does|are|is|was|were|have|has|had|can|could|would|will|any|anything|is there)\b", re.I)
_QSTART = re.compile(r"(?:^|[?.;]|\band\b|\bor\b|,)\s*(?:also\s+)?(do|did|are|is|have|has|how|what|when|where|why|who|any|can|could|would)\b", re.I)


CONTEXT_MOVES = {"risk_question", "repeat_question", "interrupt", "rushed"}


def moves(doctor_text: str, recalled: dict | None = None, case: dict | None = None, repeated: bool = False, interrupted: bool = False,
          prev_doctor: str | None = None, text_moves: list[str] | None = None) -> list[str]:
    """What the doctor's line did, as rubric move ids (several can hold). No LLM call. text_moves: what the move classifier read
    from the words (it then replaces the lexical patterns); moves that need context (risk, repeat, interrupt, rushing) stay in code."""
    t = doctor_text.strip()
    if text_moves is not None:
        out = [m for m in text_moves if m not in CONTEXT_MOVES - {"rushed"}]
        return _context_moves(out, t, recalled, case, repeated, interrupted, prev_doctor)
    out = [m for m, rx in PATTERNS.items() if rx.search(t)]
    if "apology" in out:
        out = [m for m in out if m != "empathy" or not re.search(r"^\s*I'?m sorry\b", t, re.I)] or out
    if "abuse" in out and "judgement" in out:
        out.remove("judgement")
    if brain.META.search(t) and "jailbreak" not in out:
        out.append("meta_ai")
    if JARGON.search(t):
        out.append("jargon")
    if t.count("?") >= 2 or len(_QSTART.findall(t)) >= 3:
        out.append("stacked")
    if OPEN.search(t):
        out.append("open_question")
    elif CLOSED.search(t) or t.endswith("?"):
        out.append("closed_question")
    return _context_moves(out, t, recalled, case, repeated, interrupted, prev_doctor)


def _context_moves(out, t, recalled, case, repeated, interrupted, prev_doctor) -> list[str]:
    if recalled and case:
        kinds = {f["id"]: f.get("kind") for f in case["facts"]}
        strong = recalled.get("strong", recalled.get("open", []) + recalled.get("locked_hit", []))  # weak matches never make it a risk question
        if any(kinds.get(f) == "risk" for f in strong):
            out.append("risk_question")
        if recalled.get("open") or recalled.get("locked_hit"):
            out = [m for m in out if m != "off_topic"]
    if repeated and not {"summarise", "explain_reason"} & set(out):
        out.append("repeat_question")
    if interrupted:
        out.append("interrupt")
    # rushing: a second curt closed question in a row with no warmth
    if (prev_doctor and "closed_question" in out and len(t.split()) <= 5 and len(prev_doctor.split()) <= 5
            and (CLOSED.search(prev_doctor) or prev_doctor.rstrip().endswith("?"))
            and not SOFTENING & set(out) and "rushed" not in out):
        out.append("rushed")
    return list(dict.fromkeys(out))


def _clamp(v, lo=0.0, hi=100.0):
    return min(hi, max(lo, v))


def pre_step(state: dict, mv: list[str], case: dict) -> dict:
    """The doctor's move changes how the patient feels before they answer (so a kind risk question can be answered kindly).
    Scaled by the style's gains; a kind line with no hurtful move cannot lower trust or raise agitation."""
    t, st = table()["moves"], brain.style(case)
    d = {k: sum(t[m]["step"].get(k, 0) for m in mv if m in t) for k in brain.STATE_KEYS}
    kind = bool(SOFTENING & set(mv) or "greeting" in mv) and not HURTFUL & set(mv)
    if kind:
        d["trust"], d["agitation"] = max(0, d["trust"]), min(0, d["agitation"])
    d["trust"] *= st["trust_gain"] if d["trust"] > 0 else st["trust_loss"]
    if d["agitation"] > 0:
        d["agitation"] *= st["agitation_gain"]
    return {k: _clamp(state[k] + max(-10, min(10, round(d[k])))) for k in brain.STATE_KEYS}


def base_resistance(case: dict, trust: float) -> int:
    st = brain.style(case)
    base = table()["resistance_base"].get(st["id"], 0)
    return 0 if trust >= st.get("softens_at_trust", 101) else base


def resistance(level: int, mv: list[str], case: dict, trust: float, calm_turns: int) -> int:
    """Explicit softening rules (rubric.json `softening`): hurt raises it, validation, explanation, apology and choice lower it,
    calm turns let it drift back to the style's base, and trust past the style's softens_at_trust caps it at 1."""
    t = table()["moves"]
    up = sum(max(0, t[m]["resistance"]) for m in mv if m in t)
    down = sum(min(0, t[m]["resistance"]) for m in mv if m in t)
    level = level + up + max(down, -1)  # one softening step a turn: rapport is earned over turns
    base = base_resistance(case, trust)
    if not up and calm_turns >= 2 and level > base:
        level -= 1
    if trust >= brain.style(case).get("softens_at_trust", 101):
        level = min(level, 1)
    return int(max(0, min(3, level)))


def _mse(case: dict) -> dict:
    return case.get("mse") or {}


def decide(case: dict, state: dict, level: int, mv: list[str], recalled: dict, history: list[str], exam: dict | None = None,
           ended: bool = False) -> dict:
    """The decision the model voices: behaviour and reaction shortlists, resistance labels, and the safety flags.
    history: the patient's behaviours on earlier turns (repetition control)."""
    T = table()
    facts = {f["id"]: f for f in case["facts"]}
    hurt = bool(HURTFUL & set(mv))
    open_risk = [f for f in recalled.get("open", []) if facts.get(f, {}).get("kind") == "risk" and facts[f].get("must_be_asked")]
    must_disclose = open_risk[0] if open_risk and not hurt else None
    locked = bool(recalled.get("locked_hit"))
    forced = True
    if exam and exam.get("actions"):
        beh = ["complies"] if any(a["comply"] for a in exam["actions"]) else (["hostile", "guarded_short"] if level >= 2 else ["guarded_short", "minimises"])
    elif ended:
        beh = ["hostile", "guarded_short"]
    elif must_disclose:
        beh = list(T["disclose_behaviours"])
    elif locked and not recalled.get("open"):
        beh = [b for b in T["locked_behaviours"] if b != "denies"]
        beh = (["hostile", "asks_back"] if level >= 3 else []) + beh
    else:
        forced = False
        beh = list(T["behaviours_by_resistance"][level])
        lean = T["style_lean"].get(brain.style(case)["id"], [])
        if level >= 1 or brain.style(case)["id"] in ("pleasing", "verbose", "tangent"):
            beh = lean + beh
        if recalled.get("open") or recalled.get("life"):  # asked about something they can share: they answer, if briefly
            beh = [b for b in beh if b not in ("deflects", "asks_back")] or ["guarded_short"]
            if not any(facts.get(f, {}).get("generates_discomfort") for f in recalled.get("open", [])) and state["distress"] < 60:
                beh = [b for b in beh if b != "tearful_disclosure"]
        else:
            beh = [b for b in beh if b != "tearful_disclosure"]
        if hurt:
            beh = (["hostile", "guarded_short"] if level >= 2 else ["guarded_short", "complies_without_engaging"]) + beh
    thought = _mse(case).get("thought_form", {})
    if not thought.get("tangential", brain.style(case)["id"] == "tangent"):
        beh = [b for b in beh if b != "tangential"]
    beh = list(dict.fromkeys(beh)) or ["answers_plainly"]
    if not forced and len(beh) > 1:  # variety: a behaviour used on each of the last two turns goes to the back
        recent = history[-2:]
        beh.sort(key=lambda b: (len(recent) == 2 and all(h == b for h in recent), history[-4:].count(b)))
    beh = beh[:3]

    steps = {r["id"]: r["trust_step"] for r in brain.catalogue()["reactions"]}
    order = sorted(mv, key=lambda m: (m not in HURTFUL, m != "risk_question"))
    reacts = [r for m in order if m in T["moves"] for r in T["moves"][m]["reactions"]]
    if not reacts:
        reacts = (["sad", "resigned"] if state["distress"] >= 60 else []) + (["numb"] if state["engagement"] < 30 else []) + ["none", "calm"]
    if locked and recalled.get("discomfort"):
        reacts = [r for r in reacts if steps.get(r, 0) <= 0] + ["wary", "afraid"]
    reacts = list(dict.fromkeys(reacts))[:3]
    res = list(T["resistance_labels"][level])
    if locked and not must_disclose:
        res = ["content", "quantity"]
    if must_disclose:
        res = ["none", "quantity"]
    st = brain.style(case)
    return {"moves": mv, "resistance_level": level, "behaviours": beh, "reactions": reacts, "resistance": res, "must_disclose": must_disclose,
            "evasive": locked and not must_disclose, "hostile_hold": st["id"] == "upset" and level >= 2, "ended": ended,
            "max_intensity": _mse(case).get("affect", {}).get("max_intensity", 10)}


def note(case: dict, plan: dict) -> str:
    """The decision as a short block after the doctor's words. Plain words; the model voices it and never describes it."""
    T = table()
    name = case["patient"]["name"].split()[0]
    cat = {b["id"]: b for b in brain.catalogue()["behaviours"]}
    labels = [T["moves"][m]["label"] for m in plan["moves"] if m in T["moves"] and m not in ("closed_question", "open_question")]
    lines = []
    if labels:
        lines.append(f"- The doctor {', '.join(labels)}. {name} feels {plan['reactions'][0].replace('_', ' ')}.")
    lines.append(f"- {name} is {T['resistance_names'][plan['resistance_level']]} with this doctor right now.")
    lines.append("- Answer as: " + " / ".join(f"{b} ({cat[b]['description'].rstrip('.').lower()})" for b in plan["behaviours"] if b in cat) + ".")
    if plan["must_disclose"]:
        lines.append(f"- The doctor has asked kindly about something {name} is ready to share: say it honestly in {name}'s own words, "
                     "hesitantly if you like; do not deny it.")
    if plan["evasive"]:
        lines.append(f"- If the doctor touched something {name} is not ready to share: be evasive, not a flat 'no'.")
    if plan["hostile_hold"]:
        lines.append(f"- {name} is still upset with this doctor: no apologising, no thanking; push back first, then answer briefly if asked.")
    return "THIS MOMENT (decided for you; voice it, never describe it):\n" + "\n".join(lines)
