"""Phase E learning: versioned brain (L3), quality gate and experience library (L1), faculty principles (L2).
Learning changes how the patient talks, never clinical facts, the answer key or scoring.
CLI: python learning.py list | rollback <version_id>
"""
import json
import os
import sys
from pathlib import Path

DIR = Path(os.environ.get("RAPPORT_LEARNING_DIR") or Path(__file__).parent / "learned")
_cache = {}


# ---------- versions (L3) ----------

def load_version(vid: str) -> dict:
    p = DIR / "versions" / f"{vid}.json"
    if not vid.replace("_", "").isalnum() or not p.exists():
        raise KeyError(vid)
    return json.loads(p.read_text(encoding="utf-8"))


def save_version(doc: dict) -> None:
    (DIR / "versions").mkdir(parents=True, exist_ok=True)
    (DIR / "versions" / f"{doc['id']}.json").write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _cache.pop("current", None)


def versions() -> list[dict]:
    docs = [json.loads(p.read_text(encoding="utf-8")) for p in (DIR / "versions").glob("*.json")]
    return sorted(docs, key=lambda d: int(d["id"].lstrip("v")) if d["id"].lstrip("v").isdigit() else 1 << 30)


def current() -> dict:
    """The live version; cached, so the hot path reads no files."""
    if "current" not in _cache:
        _cache["current"] = load_version(json.loads((DIR / "current.json").read_text())["id"])
    return _cache["current"]


def set_current(vid: str) -> None:
    load_version(vid)  # KeyError for an unknown id, before anything changes
    (DIR / "current.json").write_text(json.dumps({"id": vid}) + "\n")
    _cache.pop("current", None)


def brain_version(doc: dict | None = None) -> str:
    import twin
    return f"{twin.VERSION}+{(doc or current())['id']}"


def main(argv: list[str]) -> int:
    if argv[:1] == ["list"]:
        cur = current()["id"]
        for v in versions():
            print(f"{'*' if v['id'] == cur else ' '} {v['id']:4} {v.get('status', ''):9} parent={v.get('parent')} "
                  f"composite={v.get('scores', {}).get('composite')}  {v.get('notes', '')[:70]}")
        return 0
    if len(argv) == 2 and argv[0] == "rollback":
        try:
            set_current(argv[1])
        except KeyError:
            print(f"unknown version {argv[1]!r}; current stays {current()['id']}")
            return 1
        print(f"current = {argv[1]}")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
