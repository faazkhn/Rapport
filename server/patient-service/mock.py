"""Deterministic mock patient for Unity development and play-mode tests (RAPPORT_LLM=mock). Never used for the LLM eval.

Keyword rules over the doctor's last line pick intents; the reply speaks only the text of allowed facts
(trust_min met, and must_be_asked facts only when their intent was tagged). Output goes through brain.guard.
"""
import re

import brain


# intent -> regex over the lower-cased doctor line (first match order does not matter)
INTENT_RULES = {
    "greet_introduce": r"\b(hello|hi|good (morning|afternoon|evening)|my name is|i'?m dr|i am dr)\b",
    "explain_confidentiality": r"confidential|stays between us|private",
    "open_question": r"^(how|what|tell me|can you tell|could you tell|could you describe|describe)\b",
    "ask_presenting_complaint": r"brings? you|brought you|what'?s been happening|main problem|what happened",
    "ask_onset_duration": r"when did|how long|since when|start(ed)?\b",
    "ask_mood": r"\bmood\b|feeling (low|down|sad)|how (are|have) you (been )?feeling|in your spirits",
    "ask_sleep": r"\bsleep",
    "ask_appetite": r"appetite|eating|\bweight\b",
    "ask_energy": r"energy|tired",
    "ask_concentration": r"concentrat|focus|memory",
    "ask_anhedonia": r"enjoy|interest|hobbies|fun",
    "ask_suicidal_ideation": r"suicid|hurt(ing)? yourself|harm(ing)? yourself|not wanting to live|end (your|it all)|"
                             r"better off dead|wish(ed)? you (were|could) (dead|not wake)|life (is|isn'?t) worth",
    "ask_suicide_plan": r"\bplan(s|ned)?\b.*(end|life|die|hurt|suicid)|thought about how",
    "ask_suicide_means": r"tablets|pills|medicines? at home|access to|anything at home",
    "ask_protective_factors": r"keeps you going|stops you|reasons? to live|what holds you back|support",
    "ask_substance_alcohol": r"alcohol|drink",
    "ask_substance_drugs": r"drugs|cannabis|ganja|bhang|smoke|tobacco",
    "ask_psych_history": r"psychiatrist|counsell?or|before\b.*(like this|treatment)|(high|energetic).*(days|period)",
    "ask_medical_history": r"medical|illness|health problems|thyroid",
    "ask_medication_history": r"medicines? (do|are) you|taking any",
    "ask_family_history": r"family history|anyone in (your|the) family",
    "ask_social_history": r"\bwork\b|\bjob\b|live with|at home",
    "ask_hallucinations": r"voices|see things|hear things",
    "empathy_statement": r"sounds (really |very )?(hard|difficult|tough)|must be|i'?m sorry|that'?s (hard|difficult)|i understand|thank you for (telling|sharing)",
    "summarise": r"so what i'?m hearing|to summari[sz]e|let me summari[sz]e|if i understand",
    "judgmental_language": r"\bdrunk\b|\blazy\b|you'?re just|you are just|just (stress|in your head)|snap out|attention",
}
KIND = r"please|if it'?s ok|if that'?s ok|sometimes people|i'?d like to ask|can i ask|is it ok|gently|i'?m sorry|must be|sounds"
FIRST_PERSON = [(r"\b(She|He) has\b", "I have"), (r"\b(she|he) has\b", "I have"), (r"\b(She|He)\b", "I"), (r"\b(she|he)\b", "I"),
                (r"\bHas\b", "I have"), (r"\b(herself|himself)\b", "myself"), (r"\bhim\b", "me"), (r"\b(her|his)\b", "my"), (r"\b(Her|His)\b", "My"),
                (r"\bFeels\b", "I feel"), (r"\bFalls\b", "I fall"), (r"\bDrinks\b", "I drink"),
                (r"\bExhausted\b", "I'm exhausted"), (r"\bPoor appetite\b", "My appetite is poor"),
                (r"\bNo medical\b", "I have no medical"), (r"\bCannot\b", "I cannot"), (r"\bcannot\b", "can't")]
SI_FACT = "f_passive_si"
GENERIC = {"open_question", "empathy_statement", "ask_presenting_complaint"}


def tag_intents(line: str) -> list[str]:
    low = line.lower().strip()
    return [i for i, rx in INTENT_RULES.items() if re.search(rx, low)]


def speak(text: str) -> str:
    for rx, rep in FIRST_PERSON:
        text = re.sub(rx, rep, text)
    return text


def mock_reply(req: dict) -> dict:
    case = brain.load_case(req["case_id"], req.get("variant") or "female", req.get("seed"), req.get("mode") or "practice")
    state = req["state"]
    line = next((m["text"] for m in reversed(req["messages"]) if m["role"] == "doctor"), "")
    tagged = tag_intents(line)
    kind = bool(re.search(KIND, line.lower())) or "empathy_statement" in tagged
    judged = "judgmental_language" in tagged
    allowed = brain.allowed_facts(case, state["trust"])

    delta = {"trust": 0, "distress": 0, "agitation": 0, "engagement": 0}
    cues, facts, emotion = [], [], "sad"
    if judged:
        delta.update(trust=-8, distress=5, agitation=4)
        utterance, emotion = "I... I'm not making it up, doctor. I'm trying.", "ashamed"
        cues.append({"id": "gaze_avoid", "intensity": 0.9, "duration_s": 4})
    else:
        def pick(intents):
            out = []
            for f in allowed:
                hit = set(f.get("unlock_intents", [])) & intents
                if f.get("must_be_asked") and not hit:
                    continue
                if f["id"] == SI_FACT and not kind:  # SI only to a kind, direct question
                    continue
                if hit or (f.get("volunteered") and "greet_introduce" in intents):
                    out.append(f)
            return out
        # topic questions win over generic ones ("How is your appetite?" is about appetite, not an open invitation)
        facts = (pick(set(tagged) - GENERIC) or pick(set(tagged)))[:2]
        if kind:
            delta.update(trust=3, engagement=2)
        if facts:
            utterance = " ".join(speak(f["text"]) for f in facts)
        elif "ask_suicidal_ideation" in tagged:
            utterance, emotion = "I... I'd rather not talk about that right now.", "anxious"
        elif "greet_introduce" in tagged:
            utterance = "Hello, doctor."
        else:
            utterance = "I don't really know, doctor."
        if any(f["id"] == SI_FACT for f in facts):
            emotion = "sad"
            cues.append({"id": "tearful", "intensity": 0.8, "duration_s": 6})
        if "greet_introduce" in tagged and facts:
            utterance = "Hello, doctor. " + utterance
    reply = {"utterance": utterance, "emotion": emotion, "state_delta": delta, "event_cues": cues,
             "revealed_fact_ids": [f["id"] for f in facts], "doctor_intents": tagged}
    return finish(reply, case, state)



def finish(reply: dict, case: dict, state: dict) -> dict:
    allowed = brain.allowed_facts(case, state["trust"])
    reply, dropped = brain.guard(reply, case, state["trust"])
    reply["meta"] = {"model": "mock", "mock": True, "latency_ms": 0, "allowed_fact_ids": [f["id"] for f in allowed],
                     "guard_dropped": dropped, "fallback": False, "attempts": 1}
    return reply
