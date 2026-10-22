import json

import stream


def test_utterance_stream_any_chunking():
    reply = {"emotion": "sad", "utterance": 'I "think"... it\'s work.\nMaybe. Café \\ ok', "state_delta": {}}
    raw = json.dumps(reply)
    for size in (1, 2, 3, 7, len(raw)):
        p, got = stream.UtteranceStream(), ""
        for i in range(0, len(raw), size):
            got += p.feed(raw[i:i + size])
        assert got == reply["utterance"].replace("\n", " ")
        assert p.done and p.full() == reply


def test_utterance_stream_unicode_escape_split():
    p = stream.UtteranceStream()
    out = "".join(p.feed(c) for c in ['{"emotion":"sad","utterance":"a\\u00', 'e9 b"}'])
    assert out == "aé b"


def test_split_sentences_keeps_short_fragments_together():
    assert stream.split_sentences("I... I don't know. It's been hard, doctor! Why? I can't say.") == \
        ["I... I don't know.", "It's been hard, doctor!", "Why? I can't say."]
    assert stream.split_sentences("Hmm.") == ["Hmm."]
    assert stream.split_sentences("") == []


def test_sentence_splitter_streams_like_batch():
    text = "I wake at four. Then I just lie there, thinking. No. Not really, doctor."
    s, out = stream.SentenceSplitter(), []
    for ch in text:
        out += s.feed(ch)
    out += s.flush()
    assert out == ["I wake at four.", "Then I just lie there, thinking.", "No. Not really, doctor."]
    # a sentence is released as soon as the next one starts, not at the end
    s2 = stream.SentenceSplitter()
    assert s2.feed("I wake at four. ") == ["I wake at four."]


def test_utterance_stream_after_twin_labels():
    reply = {"reaction": "sad", "intensity": 6, "behaviour": "tearful_disclosure", "resistance": "none", "emotion": "sad",
             "utterance": "Some nights I wish I wouldn't wake up.", "state_delta": {}}
    raw = json.dumps(reply)
    p, got = stream.UtteranceStream(), ""
    for i in range(0, len(raw), 3):
        got += p.feed(raw[i:i + 3])
    assert got == reply["utterance"] and p.full() == reply


def test_first_clause_goes_out_early():
    s = stream.SentenceSplitter(first_clause=True)
    assert s.feed("Honestly, I don't know, ") == []  # too short to stand alone
    assert s.feed("it started after the project changed, and then") == ["Honestly, I don't know, it started after the project changed,"]
    assert s.feed(" I stopped sleeping well, really. Then more") == ["and then I stopped sleeping well, really."]  # commas only for the first piece
    assert s.flush() == ["Then more"]
