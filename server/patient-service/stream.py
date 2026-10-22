"""Streaming helpers for the voice loop: pull `utterance` out of a JSON reply while it is still being generated,
and cut it into sentences for TTS. Pure functions, no model code."""
import json
import re

_KEY = re.compile(r'"utterance"\s*:\s*"')
_ESC = {'"': '"', "\\": "\\", "/": "/", "b": "\b", "f": "\f", "n": " ", "r": " ", "t": " "}


class UtteranceStream:
    """Feed raw JSON chunks; returns newly decoded characters of the `utterance` string value."""

    def __init__(self):
        self.buf = ""
        self.pos = None  # index in buf just after the opening quote, once found
        self.done = False

    def feed(self, chunk: str) -> str:
        self.buf += chunk
        if self.done:
            return ""
        if self.pos is None:
            m = _KEY.search(self.buf)
            if not m:
                return ""
            self.pos = m.end()
        out, i, b = [], self.pos, self.buf
        while i < len(b):
            c = b[i]
            if c == '"':
                self.done = True
                i += 1
                break
            if c == "\\":
                if i + 1 >= len(b):
                    break  # wait for the rest of the escape
                e = b[i + 1]
                if e == "u":
                    if i + 6 > len(b):
                        break
                    out.append(chr(int(b[i + 2:i + 6], 16)))
                    i += 6
                    continue
                out.append(_ESC.get(e, e))
                i += 2
                continue
            out.append(c)
            i += 1
        self.pos = i
        return "".join(out)

    def full(self) -> dict:
        return json.loads(self.buf)


# end of sentence: . ! ? (or … / ...) followed by whitespace; the minimum length avoids speaking "I..." alone
_END = re.compile(r'(?<=[.!?…])["\')\]]*\s+')
MIN_CHARS = 12
_COMMA = re.compile(r'(?<=,)\s+')
FIRST_CLAUSE_CHARS = 30  # the reply's first clause may go to TTS at a comma, so a long first sentence doesn't hold back the voice


def split_sentences(text: str) -> list[str]:
    out, start = [], 0
    for m in _END.finditer(text):
        piece = text[start:m.start()].strip()
        if len(piece) >= MIN_CHARS:
            out.append(piece)
            start = m.end()
    tail = text[start:].strip()
    if tail:
        if out and len(tail) < MIN_CHARS:
            out[-1] += " " + tail
        else:
            out.append(tail)
    return out


class SentenceSplitter:
    """Feed text as it streams; get complete sentences back as soon as they end. flush() returns the rest."""

    def __init__(self, first_clause: bool = False):
        self.buf = ""
        self.first = first_clause  # still waiting for the reply's first piece

    def feed(self, text: str) -> list[str]:
        self.buf += text
        out, start = [], 0
        for m in _END.finditer(self.buf):
            piece = self.buf[start:m.start()].strip()
            if len(piece) >= MIN_CHARS:
                out.append(piece)
                start = m.end()
        self.buf = self.buf[start:]
        if self.first and not out:
            m = next((m for m in _COMMA.finditer(self.buf) if len(self.buf[:m.start()].strip()) >= FIRST_CLAUSE_CHARS), None)
            if m:
                out, self.buf = [self.buf[:m.start()].strip()], self.buf[m.end():]
        self.first = self.first and not out
        return out

    def flush(self) -> list[str]:
        rest, self.buf = self.buf.strip(), ""
        return [rest] if rest else []
