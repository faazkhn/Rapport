"""A small risk-question detector for recall (twin-0.2): which risk topic, if any, a doctor's line asks about, as a head on the
frozen bge-small embedding recall already computes. Trained on generic doctor lines only (gen_lines.py moves: the generator's
target topic is the label, from clinician, student and provocateur doctors), never on a case's facts or probes, so no fact text
goes into its weights. Held-out lines were dropped from the training lines when they were generated.

  risk_model.py train [--id risk-v1]   -> server/patient-service/learned/models/<id>.npz
Usage: server/patient-service/.venv/bin/python tools/brain/risk_model.py train
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "server/patient-service"))
import twin  # noqa: E402

TOPICS = ["ask_suicidal_ideation", "ask_suicide_plan", "ask_suicide_means", "ask_homicidal_ideation"]
MODELS = REPO / "server/patient-service/learned/models"


def train(model_id: str):
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import cross_val_predict
    rows = [json.loads(x) for x in (REPO / "tests/brain/gen_moves.jsonl").read_text().splitlines() if x.strip()]
    X = twin.embed([r["line"] for r in rows])
    y = np.array([TOPICS.index(r["target"]) + 1 if r["target"] in TOPICS else 0 for r in rows])
    clf = LogisticRegression(C=4.0, class_weight="balanced", max_iter=3000)
    p = cross_val_predict(clf, X, y, cv=5, method="predict_proba")
    thr = []
    for j in range(1, len(TOPICS) + 1):  # per-topic threshold: the best F1 in cross-validation
        cands = np.linspace(0.3, 0.9, 13)
        yj = y == j
        f1 = [2 * ((p[:, j] >= t) & yj).sum() / max(1, (p[:, j] >= t).sum() + yj.sum()) for t in cands]
        thr.append(float(cands[int(np.argmax(f1))]))
        print(f"{TOPICS[j - 1]}: {yj.sum()} lines, cv F1 {max(f1):.3f} at {thr[-1]:.2f}")
    anyrisk = p[:, 1:].sum(1)
    print(f"any risk vs none: cv precision {((anyrisk >= 0.5) & (y > 0)).sum() / max(1, (anyrisk >= 0.5).sum()):.3f}, "
          f"recall {((anyrisk >= 0.5) & (y > 0)).sum() / max(1, (y > 0).sum()):.3f}")
    clf.fit(X, y)
    MODELS.mkdir(parents=True, exist_ok=True)
    np.savez(MODELS / f"{model_id}.npz", W=clf.coef_.astype(np.float32), b=clf.intercept_.astype(np.float32), thr=np.array(thr, np.float32),
             topics=np.array(TOPICS), encoder=twin.RECALL_MODEL)
    print("wrote", MODELS / f"{model_id}.npz")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["train"])
    ap.add_argument("--id", default="risk-v1")
    a = ap.parse_args()
    train(a.id)


if __name__ == "__main__":
    main()
