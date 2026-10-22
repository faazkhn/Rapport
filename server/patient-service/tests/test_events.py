import twin

CASE = {"events": [
    {"id": "asks_to_leave", "when": {"turn": 1}, "say": "asks to go home"},
    {"id": "phone", "when": {"after_min": 5}, "say": "phone buzzes", "state_delta": {"distress": 5}},
    {"id": "stands", "when": {"agitation_at_least": 60}, "say": "stands up", "action": "stand_up"},
    {"id": "sits", "when": {"agitation_below": 40, "after_event": "stands"}, "say": "sits back down", "action": "sit_down"},
]}
CALM = {"trust": 30, "distress": 50, "agitation": 20, "engagement": 40}


def ids(evs):
    return [e["id"] for e in evs]


def test_events_fire_once_on_their_trigger():
    fired = set()
    assert ids(twin.due_events(CASE, CALM, 1, 0.5, fired)) == ["asks_to_leave"]
    assert ids(twin.due_events(CASE, CALM, 2, 1.0, fired)) == []
    assert ids(twin.due_events(CASE, CALM, 3, 5.2, fired)) == ["phone"]
    assert ids(twin.due_events(CASE, CALM, 4, 6.0, fired)) == []


def test_state_triggers_and_ordering():
    fired = {"asks_to_leave", "phone"}
    assert ids(twin.due_events(CASE, {**CALM, "agitation": 30}, 5, 7, fired)) == []  # sits needs stands first
    assert ids(twin.due_events(CASE, {**CALM, "agitation": 65}, 6, 8, fired)) == ["stands"]
    assert ids(twin.due_events(CASE, {**CALM, "agitation": 50}, 7, 9, fired)) == []
    assert ids(twin.due_events(CASE, {**CALM, "agitation": 35}, 8, 10, fired)) == ["sits"]


def test_no_events_in_a_case_without_them():
    assert twin.due_events({}, CALM, 1, 0, set()) == []


def test_apply_event_deltas_clamped():
    s = twin.apply_event_deltas({**CALM, "distress": 98}, [{"id": "x", "state_delta": {"distress": 5, "trust": -3}}])
    assert s["distress"] == 100 and s["trust"] == 27


def test_after_event_waits_for_a_later_turn():
    case = {"events": [{"id": "a", "when": {"turn": 1}, "say": "a"}, {"id": "b", "when": {"after_event": "a"}, "say": "b"}]}
    fired = set()
    assert ids(twin.due_events(case, CALM, 1, 0, fired)) == ["a"]
    assert ids(twin.due_events(case, CALM, 2, 0, fired)) == ["b"]
