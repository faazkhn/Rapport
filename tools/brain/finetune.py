"""Fine-tune the Digital Twin's small text model (bge-small-en-v1.5, MIT) on CPU: one shared encoder with two heads, the clinical
TOPIC a doctor's line asks about (the debrief's intents) and the MANNER (rubric moves). Trained on tests/brain/train2.jsonl (judge
labels that agree with the generator's target, plus local session lines), never on a case's facts, so no fact text goes into the
weights. Exported to ONNX for the live path (a few ms a turn on CPU).

  finetune.py train [--id tm-v1] [--epochs 4]   -> server/patient-service/learned/models/<id>.onnx + <id>.json (labels, thresholds)
  finetune.py eval  [--id tm-v1]                -> F1 on tests/brain/gold2.jsonl vs the lexical rubric (manner) and the LLM tagger (topics)
Usage: server/patient-service/.venv/bin/python tools/brain/finetune.py train|eval
"""
import argparse
import json
import random
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "server/patient-service"))
sys.path.insert(0, str(REPO / "tools/brain"))
OUT = REPO / "tests/brain"
MODELS = REPO / "server/patient-service/learned/models"
BASE = "BAAI/bge-small-en-v1.5"
MAX_LEN = 48


def rows(name):
    return [json.loads(x) for x in (OUT / name).read_text().splitlines() if x.strip()]


def train(model_id: str, epochs: int, seed: int = 0):
    import torch
    from transformers import AutoModel, AutoTokenizer
    import moves_model
    torch.manual_seed(seed)
    random.seed(seed)
    topics, manner = moves_model.topic_ids(), moves_model.MANNER
    data = rows("train2.jsonl")
    random.shuffle(data)
    n_val = max(50, len(data) // 10)
    val, tr = data[:n_val], data[n_val:]
    tok, enc = AutoTokenizer.from_pretrained(BASE), AutoModel.from_pretrained(BASE)

    class Net(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.enc = enc
            self.head = torch.nn.Linear(enc.config.hidden_size, len(topics) + len(manner))

        def forward(self, input_ids, attention_mask):
            h = self.enc(input_ids=input_ids, attention_mask=attention_mask).last_hidden_state[:, 0]
            return self.head(torch.nn.functional.normalize(h, dim=-1) * 10)

    net = Net()
    labs = topics + manner
    y = lambda rs: torch.tensor([[float(lab in r["topics"] or lab in r["manner"]) for lab in labs] for r in rs])  # noqa: E731
    pos = y(tr).sum(0)
    weight = ((len(tr) - pos) / pos.clamp(min=1)).clamp(max=20)
    loss_fn = torch.nn.BCEWithLogitsLoss(pos_weight=weight)
    opt = torch.optim.AdamW([{"params": net.enc.parameters(), "lr": 3e-5}, {"params": net.head.parameters(), "lr": 1e-3}], weight_decay=0.01)
    for ep in range(epochs):
        net.train()
        random.shuffle(tr)
        tot = 0.0
        for i in range(0, len(tr), 32):
            b = tr[i:i + 32]
            t = tok([r["line"] for r in b], padding=True, truncation=True, max_length=MAX_LEN, return_tensors="pt")
            loss = loss_fn(net(t["input_ids"], t["attention_mask"]), y(b))
            opt.zero_grad()
            loss.backward()
            opt.step()
            tot += loss.item() * len(b)
        print(f"epoch {ep + 1}: loss {tot / len(tr):.4f}", flush=True)
    net.eval()
    with torch.no_grad():
        t = tok([r["line"] for r in val], padding=True, truncation=True, max_length=MAX_LEN, return_tensors="pt")
        p = torch.sigmoid(net(t["input_ids"], t["attention_mask"])).numpy()
    yv = y(val).numpy()
    thr = []
    for j in range(len(labs)):  # per-label threshold on the validation split (0.5 when a label is too rare to tune)
        if yv[:, j].sum() < 3:
            thr.append(0.5)
            continue
        cands = np.linspace(0.2, 0.9, 15)
        f1 = [2 * ((p[:, j] >= c) & (yv[:, j] == 1)).sum() / max(1, (p[:, j] >= c).sum() + yv[:, j].sum()) for c in cands]
        thr.append(float(cands[int(np.argmax(f1))]))
    MODELS.mkdir(parents=True, exist_ok=True)
    dummy = tok(["How have you been sleeping?"], return_tensors="pt")
    torch.onnx.export(net, (dummy["input_ids"], dummy["attention_mask"]), MODELS / f"{model_id}.onnx", input_names=["input_ids", "attention_mask"],
                      output_names=["logits"], dynamic_axes={"input_ids": {0: "b", 1: "t"}, "attention_mask": {0: "b", 1: "t"}, "logits": {0: "b"}},
                      opset_version=17, dynamo=False)
    tok.save_pretrained(MODELS / f"{model_id}-tokenizer")
    (MODELS / f"{model_id}.json").write_text(json.dumps({"id": model_id, "base": BASE, "topics": topics, "manner": manner, "thresholds": thr,
                                                         "train_lines": len(tr), "val_lines": len(val), "epochs": epochs}, indent=1))
    print(f"wrote {model_id}: {len(tr)} train / {len(val)} val lines")


def eval_(model_id: str, tagger_url: str | None):
    import brain
    import mind
    import moves_model
    import rubric
    from openai import OpenAI
    gold = rows("gold2.jsonl")
    m = mind.text_model(model_id)
    pred = [mind.read_line(m, r["line"]) for r in gold]
    gt, gm = [set(r["topics"]) for r in gold], [set(r["manner"]) for r in gold]
    topics, manner = moves_model.topic_ids(), moves_model.MANNER
    out = {"lines": len(gold),
           "topics_model": moves_model.f1([set(p["topics"]) for p in pred], gt, topics),
           "manner_model": moves_model.f1([set(p["manner"]) for p in pred], gm, manner),
           "manner_lexical": moves_model.f1([set(rubric.moves(r["line"])) & set(manner) for r in gold], gm, manner)}
    if tagger_url:
        c = OpenAI(base_url=tagger_url, api_key="local", timeout=120, max_retries=1)
        out["topics_llm_tagger"] = moves_model.f1([set(brain.tag_intents(r["line"], None, c, "local")) & set(topics) for r in gold], gt, topics)
    (OUT / f"eval_{model_id}.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: ({kk: vv for kk, vv in v.items() if kk != "per_label"} if isinstance(v, dict) else v) for k, v in out.items()}, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["train", "eval"])
    ap.add_argument("--id", default="tm-v1")
    ap.add_argument("--epochs", type=int, default=4)
    ap.add_argument("--tagger-url", default="http://127.0.0.1:8080/v1")
    a = ap.parse_args()
    train(a.id, a.epochs) if a.cmd == "train" else eval_(a.id, a.tagger_url)


if __name__ == "__main__":
    main()
