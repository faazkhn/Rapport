"""AI examiner notes for the debrief: formative comments on the doctor's verbal interview skills, each tied to a line they said.

docs/literature/evaluation-and-assessment.md: LLM raters agree with experts only to within a point on MIRS items (off-by-one 0.67-0.87,
Geathers 2025) and are poor on non-verbal items, so they are kept to verbal items, zero-shot at temperature 0 (the best general
method in that benchmark), never touch the score, and every quote is checked against the transcript in code (invented quotes dropped).
"""
import json
import re

import brain

ITEMS = {
    "opening": "introduces self and role, sets the scene",
    "open_questions": "open questions that let the patient tell their story",
    "empathy": "acknowledges feelings and the impact on the patient's life",
    "plain_language": "everyday words, no jargon",
    "one_question": "one question at a time, waits for the answer",
    "structure": "signposts and summarises",
    "risk_inquiry": "asks about risk directly and kindly",
    "closing": "checks understanding and agrees a shared plan",
}
MAX_TURNS = 80


def schema() -> dict:
    note = {"type": "object", "additionalProperties": False, "required": ["item", "quote", "comment"],
            "properties": {"item": {"type": "string", "enum": list(ITEMS)}, "quote": {"type": "string"}, "comment": {"type": "string"}}}
    return {"type": "object", "additionalProperties": False, "required": ["strengths", "improvements"],
            "properties": {"strengths": {"type": "array", "maxItems": 3, "items": note},
                           "improvements": {"type": "array", "maxItems": 3, "items": note}}}


def messages(case: dict, turns: list[dict]) -> list[dict]:
    items = "\n".join(f"- {k}: {v}" for k, v in ITEMS.items())
    lines = "\n".join(f"DOCTOR: {t['doctor']}\nPATIENT: {t.get('patient') or ''}" for t in turns[-MAX_TURNS:])
    return [{"role": "system", "content":
             "You are an experienced psychiatry OSCE examiner giving formative feedback to a medical student on a simulated interview. "
             f"The patient: {case['title']}. Judge only what the DOCTOR said, on these interview skills:\n{items}\n"
             "Give up to 3 strengths and up to 3 improvements. Each must quote one DOCTOR line exactly as written (copy the words, do not "
             "paraphrase) and say in one short sentence why it worked, or what to say instead. Plain, kind, specific. If the transcript is "
             "too short to judge, return fewer items."},
            {"role": "user", "content": f"Transcript:\n{lines}"}]


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", " ".join((s or "").lower().split()))


def grounded(notes: list[dict], turns: list[dict]) -> list[dict]:
    """Keep notes whose quote is (part of) something the doctor said; the model sometimes paraphrases or invents."""
    said = [_norm(t["doctor"]) for t in turns]
    out = []
    for n in notes:
        q = _norm(n.get("quote", ""))
        if n.get("item") in ITEMS and len(q) >= 8 and any(q in s for s in said):
            out.append({k: n[k] for k in ("item", "quote", "comment")})
    return out


def assess(case: dict, turns: list[dict], client=None, model: str | None = None) -> dict:
    model = model or brain.default_model()
    sch = schema()
    resp = (client or brain.get_client()).chat.completions.create(
        **{**brain.llm_kwargs(model, messages(case, turns), sch, "examiner_notes", 1), "temperature": 0, "max_tokens": 700})
    raw = json.loads(resp.choices[0].message.content or "{}")
    strengths, improvements = grounded(raw.get("strengths", []), turns), grounded(raw.get("improvements", []), turns)
    dropped = len(raw.get("strengths", [])) + len(raw.get("improvements", [])) - len(strengths) - len(improvements)
    return {"strengths": strengths, "improvements": improvements, "dropped_ungrounded": dropped, "model": model}
