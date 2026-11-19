"""Re-times the staged Digital Twin timeline to the 4K showcase take, so the Twin panel in the film follows her speech.

  python3 tools/demo/showcase_twin_timeline.py   ->  demo/staged/showcase/timeline_take.json

Speech boundaries come from silencedetect on demo/raw/Rapport_showcase_4k.mp4 (2026-11-15 take), checked against the
Whisper transcript. Timeline turns 9-10 (plans and means) are not in the showcase script and are dropped.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# timeline turn -> (doctor start, doctor end, patient start, patient end) in take seconds
TAKE = {1: (20.05, 24.02, 25.15, 34.34), 2: (34.71, 38.35, 39.52, 50.97), 3: (51.71, 57.30, 58.73, 61.16),
        4: (61.51, 64.31, 65.52, 76.93), 5: (77.31, 80.40, 81.54, 92.02), 6: (92.64, 95.73, 97.10, 108.03),
        7: (108.03, 111.52, 113.15, 119.50), 8: (119.90, 127.21, 127.21, 139.90), 11: (140.30, 141.94, 143.15, 150.90),
        12: (151.10, 155.77, 155.77, 161.44)}
FIELD = {"doctor_start": 0, "doctor_end": 1, "snapshot": 2, "patient_start": 2, "patient_end": 3}

d = json.loads((ROOT / "server/patient-service/twin/demo_timeline.json").read_text())
d["events"] = [dict(e, t=TAKE[e["turn"]][FIELD[e["type"]]]) for e in d["events"] if e["turn"] in TAKE]
d["meta"]["note"] = "Re-timed to demo/raw/Rapport_showcase_4k.mp4"
out = ROOT / "demo/staged/showcase/timeline_take.json"
out.write_text(json.dumps(d, indent=1, ensure_ascii=False))
print(f"{len(d['events'])} events -> {out}")
