"""What the patient's voice says and how: the hesitation cap for TTS text, emotion instructions, and the TTS backends."""
import re

_DOTS = re.compile(r"\s*(?:\.{3,}|…)")


def speakable(text: str, keep_first: bool = True) -> str:
    """At most one hesitation ("...") per reply: later ones become commas (a final one a full stop), and a leading one is dropped.
    Each "..." is a long pause in TTS, so a reply full of them sounds broken rather than sad. The splitter cuts sentences after
    "...", so a piece's trailing "..." can be the reply's one allowed hesitation and is kept when keep_first."""
    s = _DOTS.sub("...", text.strip())
    s = re.sub(r"^(?:\.\.\.\s*)+", "", s)
    head, sep, tail = s.partition("...") if keep_first else ("", "", s)
    tail = re.sub(r",\s*$", ".", _DOTS.sub(",", tail))
    s = (head + sep + tail).strip()
    return s if re.search(r"\w", s) else ""


_LABEL = re.compile(r'"(behaviour|emotion|reaction)"\s*:\s*"([a-z_]+)"')


def labels_so_far(buf: str) -> dict:
    """Twin labels already complete in a reply JSON that is still streaming (behaviour and emotion come before the utterance)."""
    return {k: v for k, v in _LABEL.findall(buf)}


def instruction(case: dict, labels: dict) -> str:
    """The case's voice description plus how this line sounds, from the expression map; unknown labels add nothing."""
    import brain
    m = brain.load_json("brain/expression_map.json")
    parts = [m.get("emotions", {}).get(labels.get("emotion"))]
    parts += [(m[g].get(labels.get(k)) or {}).get("voice") for g, k in (("behaviours", "behaviour"), ("reactions", "reaction"))]
    desc = case["patient"].get("voice_description", "")
    parts = [p for p in parts if p]
    return f"{desc} In this line: {'; '.join(parts)}." if parts else desc


class FnBackend:
    """Wraps a whole-sentence TTS function (KittenTTS, test fakes): one chunk per sentence, no instructions."""

    def __init__(self, fn):
        self.fn = fn

    def stream(self, text, voice_id, speed, instruction=""):
        yield self.fn(text, voice_id, speed)


class QwenDesign:
    """Qwen3-TTS 1.7B VoiceDesign (Apache-2.0) via mlx-audio: the voice comes from the text instruction, streamed in ~0.4 s chunks.
    The sampling seed is fixed per variant so every sentence keeps the same speaker (the bake-off measured drift without it)."""
    REPO = "mlx-community/Qwen3-TTS-12Hz-1.7B-VoiceDesign-bf16"
    SEEDS = {"female": 1234, "male": 4321}

    def __init__(self):
        from mlx_audio.tts.utils import load_model
        self.model = load_model(self.REPO)
        self.seed = 1234

    def stream(self, text, voice_id, speed, instruction=""):
        # shortcut: speed is ignored (no speed control); pace comes from the instruction. Resample if pressured speech needs it.
        import mlx.core as mx
        import numpy as np
        mx.random.seed(self.seed)
        for r in self.model.generate(text=text, instruct=instruction or "A natural, calm adult voice.", lang_code="english", stream=True, streaming_interval=0.4):
            yield np.asarray(r.audio, dtype=np.float32).reshape(-1)


def load(name: str, kitten_fn):
    """`kitten` or `qwen3-design`; raises if the model cannot load (the caller falls back to kitten)."""
    return QwenDesign() if name == "qwen3-design" else FnBackend(kitten_fn)
