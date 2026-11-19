"""Text and voice helpers: hesitation cap, emotion instructions, backend fallback. No models loaded."""
import voice


def test_speakable_caps_ellipses():
    assert voice.speakable("I... I don't... know...") == "I... I don't, know."


def test_speakable_never_empty():
    assert voice.speakable("...") == ""
    assert voice.speakable("... hm ...") == "hm..."
    assert voice.speakable("Okay.") == "Okay."


def test_speakable_without_hesitation():
    assert voice.speakable("Well... I guess... so.", keep_first=False) == "Well, I guess, so."


def _case():
    import brain
    return brain.load_case("mdd_01", "female")


def test_instruction_uses_expression_voice():
    import brain
    case, m = _case(), brain.load_json("brain/expression_map.json")
    ins = voice.instruction(case, {"behaviour": "tearful_disclosure", "emotion": "sad"})
    assert ins.startswith(case["patient"]["voice_description"])
    assert m["emotions"]["sad"] in ins and m["behaviours"]["tearful_disclosure"]["voice"] in ins


def test_instruction_unknown_is_description_only():
    case = _case()
    assert case["patient"]["voice_description"]
    assert voice.instruction(case, {"behaviour": "nope", "emotion": "zzz"}) == case["patient"]["voice_description"]
    assert voice.instruction(case, {}) == case["patient"]["voice_description"]


def test_labels_so_far_reads_partial_json():
    buf = '{"behaviour": "deflects", "emotion": "sad", "utterance": "I'
    assert voice.labels_so_far(buf) == {"behaviour": "deflects", "emotion": "sad"}
    assert voice.labels_so_far('{"behav') == {}


def test_speakable_keeps_digits_only_reply():
    assert voice.speakable("34.") == "34."
    assert voice.speakable("2019...") == "2019..."


def test_speakable_keeps_the_hesitation_at_a_sentence_cut():
    # the splitter cuts after "..."; that piece's trailing hesitation is the reply's one allowed pause
    assert voice.speakable("I don't know...") == "I don't know..."
    assert voice.speakable("I don't know...", keep_first=False) == "I don't know."


def test_ready_to_play_holds_only_when_generation_is_slow():
    s = "It's an IT services company. I test software."  # ~3.5 s of speech
    assert voice.ready_to_play(s, 0.4, 0.21)  # idle (RTF 0.53): the first chunk starts it
    assert not voice.ready_to_play(s, 0.4, 0.45)  # LLM busy (RTF ~1.1): wait for more audio
    assert voice.ready_to_play(s, 1.2, 1.25)
    assert voice.ready_to_play(s, 0.4, 0.45, queued_s=2.0)  # the previous sentence is still playing on the client
    assert not voice.ready_to_play(s, 0.0, 0.1)


def test_instruction_strength_and_pace():
    import brain
    case = brain.load_case("mdd_01")
    ins = voice.instruction(case, {"emotion": "sad"}, 0.8, 0.85)
    assert "very sad" in ins and "slowly" in ins
    assert "fast" in voice.instruction(case, {"emotion": "anxious"}, 0.2, 1.2) and "a little" in voice.instruction(case, {"emotion": "anxious"}, 0.2)


def test_stretch_changes_length_not_when_near_one():
    import numpy as np
    a = np.sin(np.linspace(0, 400, 24000)).astype(np.float32)
    assert len(voice.stretch(a, 1.02)) == len(a)
    assert abs(len(voice.stretch(a, 1.25)) - len(a) / 1.25) < 600
