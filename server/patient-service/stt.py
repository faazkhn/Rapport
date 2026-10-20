"""Speech to text for the voice loop: Silero VAD end-pointing + Parakeet (parakeet-mlx) or Whisper (mlx-whisper).
Audio is a float32 numpy array at 16 kHz and stays in memory; nothing is written to disk."""
import os

import numpy as np

SR = 16000
FRAME = 512  # Silero VAD window at 16 kHz (32 ms)
SILENCE_MS = int(os.environ.get("VAD_SILENCE_MS", "450"))
VAD_THRESHOLD = float(os.environ.get("VAD_THRESHOLD", "0.5"))
STT_MODEL = os.environ.get("STT_MODEL", "mlx-community/parakeet-tdt-0.6b-v2")
WHISPER = "mlx-community/whisper-large-v3-turbo"

_vad_model = None
_stt = {}


def vad_model():
    global _vad_model
    if _vad_model is None:
        from silero_vad import load_silero_vad
        _vad_model = load_silero_vad()
    return _vad_model


class Vad:
    """Per-session end-pointer. feed() takes exactly FRAME float32 samples and returns 'start', 'end' or None.
    end_sample is the sample index where speech actually stopped (before the trailing silence)."""

    def __init__(self, silence_ms: int = SILENCE_MS):
        from silero_vad import VADIterator
        self.it = VADIterator(vad_model(), threshold=VAD_THRESHOLD, sampling_rate=SR,
                              min_silence_duration_ms=silence_ms, speech_pad_ms=0)
        self.samples = 0
        self.end_sample = None

    def feed(self, frame: np.ndarray):
        import torch
        self.samples += len(frame)
        ev = self.it(torch.from_numpy(frame))
        if not ev:
            return None
        if "start" in ev:
            return "start"
        self.end_sample = ev["end"]
        return "end"

    def reset(self):
        self.it.reset_states()
        self.samples, self.end_sample = 0, None  # the iterator's sample count restarts too


def load(model: str = STT_MODEL):
    if model not in _stt:
        if "parakeet" in model:
            from parakeet_mlx import from_pretrained
            _stt[model] = from_pretrained(model)
        else:
            import mlx_whisper  # loads lazily on first transcribe; warm it here
            mlx_whisper.transcribe(np.zeros(SR, dtype=np.float32), path_or_hf_repo=model)
            _stt[model] = model
    return _stt[model]


def transcribe(audio: np.ndarray, model: str = STT_MODEL) -> str:
    m = load(model)
    if "parakeet" in model:
        import mlx.core as mx
        from parakeet_mlx.audio import get_logmel
        if len(audio) < SR // 4:
            audio = np.pad(audio, (0, SR // 4 - len(audio)))
        mel = get_logmel(mx.array(audio, dtype=mx.float32), m.preprocessor_config)
        return m.generate(mel)[0].text.strip()
    import mlx_whisper
    return mlx_whisper.transcribe(audio, path_or_hf_repo=m, language="en")["text"].strip()


def pcm16_to_float(b: bytes) -> np.ndarray:
    return np.frombuffer(b, dtype="<i2").astype(np.float32) / 32768.0


def float_to_pcm16(a: np.ndarray) -> bytes:
    return (np.clip(a, -1, 1) * 32767).astype("<i2").tobytes()
