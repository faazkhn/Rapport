"""Text and voice helpers: hesitation cap, emotion instructions, backend fallback. No models loaded."""
import voice


def test_speakable_caps_ellipses():
    assert voice.speakable("I... I don't... know...") == "I... I don't, know"


def test_speakable_never_empty():
    assert voice.speakable("...") == ""
    assert voice.speakable("... hm ...") == "hm"
    assert voice.speakable("Okay.") == "Okay."


def test_speakable_without_hesitation():
    assert voice.speakable("Well... I guess... so.", keep_first=False) == "Well, I guess, so."
