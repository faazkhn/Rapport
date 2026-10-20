"""What the patient's voice says and how: the hesitation cap for TTS text, emotion instructions, and the TTS backends."""
import re

_DOTS = re.compile(r"\s*(?:\.{3,}|…)")


def speakable(text: str, keep_first: bool = True) -> str:
    """At most one hesitation ("...") per reply; later ones become commas, and a leading or trailing one is dropped. Each "..." is
    a long pause in TTS, so a reply full of them sounds broken rather than sad."""
    s = _DOTS.sub("...", text.strip())
    s = re.sub(r"^(?:\.\.\.\s*)+", "", s)
    s = re.sub(r"(?:\s*\.\.\.)+$", "", s).strip()
    head, sep, tail = s.partition("...")
    s = head + sep + _DOTS.sub(",", tail) if keep_first else _DOTS.sub(",", s)
    return s if re.search(r"[A-Za-z]", s) else ""
