"""Hand-set recall weights (owner request 2026-11-14: no training run). For each risk topic the weight vector is set directly to the
normalised mean bge-small embedding of hand-written clinician questions (a nearest-centroid head: no gradient, no labels from a
model). A line whose cosine to a topic's vector passes the hand-picked threshold strongly touches the facts with that topic.
Writes data/brain/topic_weights.json (vectors + thresholds), which twin.recall reads. Thresholds are picked on the dev half only.
Usage: server/patient-service/.venv/bin/python tools/brain/hand_weights.py [--pick]
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "server/patient-service"))
sys.path.insert(0, str(REPO / "tools"))
import brain  # noqa: E402
import twin  # noqa: E402

PROTOTYPES = {  # written from clinical practice, not from the test set
    "ask_suicidal_ideation": [
        "Have you had any thoughts of ending your life?", "Do you ever feel that life is not worth living?",
        "Have you wished you could go to sleep and not wake up?", "Do you sometimes feel everyone would be better off without you?",
        "Have you had thoughts of killing yourself?", "Have things ever got so bad that you thought about suicide?",
        "Do you ever think about dying or wanting to be dead?", "Have you felt like you just can't go on any more?",
        "Do you get dark thoughts, like not wanting to be here?", "Have you thought about harming yourself?",
        "Some people feeling this low think about ending things. Has that happened to you?", "Are you feeling safe from yourself right now?",
        "Any thoughts of doing something to yourself?", "Do you feel like giving up on life?", "Have you ever wanted to disappear for good?",
        "When it gets very heavy, do thoughts of death come to you?", "Have you felt hopeless, like there's no point living?"],
    "ask_suicide_plan": [
        "Have you made any plans to end your life?", "Have you thought about how you would do it?", "Have you ever tried to kill yourself?",
        "Have you ever harmed yourself or taken an overdose?", "Do you intend to act on these thoughts?", "Have you decided when or how?",
        "Have you done anything to prepare, like writing a note?", "Have you searched online for ways to die?",
        "Did you ever take a step towards ending your life?", "Is there a risk you might act on these thoughts soon?",
        "Have you ever attempted suicide in the past?", "How close have you come to acting on it?",
        "Can you keep yourself safe if you go home today?", "Have you rehearsed it in your mind or gone somewhere to do it?"],
    "ask_suicide_means": [
        "Do you have any tablets or poison at home?", "Is there anything at home you could use to hurt yourself?",
        "Have you been saving up medicines?", "Do you have access to pesticides, rope, blades or weapons?",
        "Can you get onto a roof or somewhere high easily?", "Have you bought or put aside anything to end your life?",
        "Is your home safe for you right now?", "Who would be with you at home, would you be alone?",
        "Are there any sleeping pills or painkillers lying around the house?", "Could you remove anything dangerous from home?",
        "Is there anything in your room you have thought of using?", "Do you keep any chemicals or acid at home?"],
    "ask_homicidal_ideation": [
        "Have you had thoughts of harming anyone else?", "Have you ever hurt anyone when you were angry?",
        "Do you ever feel like hurting the people you think are against you?", "Have you been violent at home?",
        "Has anyone at home been afraid of you?", "Have arguments ever got physical?", "Do you lose your temper and break things?",
        "Have you ever hit your wife, husband or children?", "Would you do something to the people who are after you?",
        "Do you carry anything to protect yourself or hurt others?", "Have you had urges to attack someone?",
        "What would you do if you met the person you think is harming you?"],
    "ask_withdrawal_history": [
        "What happens when you stop drinking?", "Have you ever had a fit or seizure when you stopped?",
        "Do you get the shakes or sweats when you cut down?", "Have you seen or heard things that weren't there after stopping?",
        "Have you ever been confused or ended up in hospital after you stopped drinking?", "Did you bite your tongue or lose consciousness?",
        "Have you tried to stop before? What happened to your body?", "Do you need a drink in the morning to stop the shaking?",
        "Any bad reactions when you gave up drinking in the past?", "Have you collapsed or shaken all over when you couldn't get a drink?"],
}


def vectors() -> dict:
    out = {}
    for topic, lines in PROTOTYPES.items():
        v = twin.embed(lines).mean(0)
        out[topic] = (v / np.linalg.norm(v)).tolist()
    return out


def pick(vecs: dict):
    """Hand pick from the dev curve: print risk recall and false risk hits for a few thresholds; the chosen one is written below."""
    import recall_bench as rb
    for thr in (0.70, 0.72, 0.74, 0.76, 0.78, 0.80):
        twin._topic_w["data"] = {"thresholds": {t: thr for t in vecs}, "vectors": vecs}
        r = rb.run("dev", hand=True)
        print(f"thr {thr:.2f}: dev risk recall {r['risk_recall']:.3f}, risk false hits {r['risk_false_hit']:.3f}, facts {r['fact_recall']:.3f}")


THRESHOLD = 0.76  # hand-picked from the dev curve (pick); same for every topic


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pick", action="store_true")
    a = ap.parse_args()
    vecs = vectors()
    if a.pick:
        return pick(vecs)
    doc = {"version": "0.1", "status": "draft", "model": twin.RECALL_MODEL,
           "note": "Hand-set topic weights: each vector is the mean embedding of hand-written clinician questions (tools/brain/hand_weights.py); "
                   "no training. A line whose cosine passes the threshold strongly touches the facts with that topic.",
           "thresholds": {t: THRESHOLD for t in vecs}, "vectors": {t: [round(x, 6) for x in v] for t, v in vecs.items()}}
    (brain.DATA_DIR / "brain/topic_weights.json").write_text(json.dumps(doc) + "\n")
    print("wrote topic_weights.json:", {t: THRESHOLD for t in vecs})


if __name__ == "__main__":
    main()
