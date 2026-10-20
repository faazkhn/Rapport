"""In-process feed of Digital Twin events to Twin view viewers (/twin/ws). Publishing never waits: a viewer that falls more than
MAX_QUEUED events behind loses the newest ones. The current session's events are kept so a late viewer can catch up."""
import asyncio

MAX_QUEUED = 200
_subs: list[asyncio.Queue] = []
_history: list[dict] = []


def publish(event: dict) -> None:
    if event.get("type") == "init":
        _history.clear()
    _history.append(event)
    for q in _subs:
        if q.qsize() < MAX_QUEUED:
            q.put_nowait(event)


def subscribe() -> asyncio.Queue:
    q = asyncio.Queue()
    h = _history if len(_history) <= MAX_QUEUED else _history[:1] + _history[1 - MAX_QUEUED:]  # keep init first
    for e in h:
        q.put_nowait(e)
    _subs.append(q)
    return q


def unsubscribe(q: asyncio.Queue) -> None:
    if q in _subs:
        _subs.remove(q)
