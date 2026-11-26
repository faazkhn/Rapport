# Rapport

**Rapport** is a spoken, embodied simulated psychiatric patient for practising psychiatry interviews (OSCE stations) that runs entirely
on one laptop. A student talks out loud to a 3D patient, who answers with a synthetic voice, a face and body language. The patient's mind,
the **Digital Twin**, is ordinary code: it decides what the patient remembers, what stays locked until there is enough trust, how guarded
the patient is and which behaviours are allowed. A local language model only puts that decision into words, and every sentence is checked
before it is spoken. No audio or text leaves the device.

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.24367080.svg)](https://doi.org/10.5281/zenodo.24367080)

> **Draft clinical content. For education and research only.** Not reviewed by a psychiatrist, not a medical device. See
> [Disclaimer](#disclaimer).

[![Rapport demo film on YouTube](https://img.youtube.com/vi/G7NP5U4vXLs/maxresdefault.jpg)](https://www.youtube.com/watch?v=G7NP5U4vXLs)

*Demo film (YouTube). In this film the patient's replies are pre-scripted (staged mode) so that the take could be filmed; the doctor's lines
use the author's own voice, cloned with the author's consent. Live, unscripted replies are what the papers evaluate.*

## Research

The repository holds two papers built on the same system. Sources, PDFs and supplements are in [`papers/`](papers/).

| | Paper | Target journal | Source |
|---|---|---|---|
| A | *Decide in Code, Voice with the Model: A Code-Governed Patient Model for an On-Device Psychiatric Standardised Patient, Compared with a Prompt-Only Baseline* | Journal of Medical Systems | [`papers/paperA_jms/`](papers/paperA_jms/) |
| B | *Recognising Reworded Risk Questions in a Simulated Psychiatric Patient: A Blind Benchmark, Small Encoders, BM25 and a Zero-Shot Language Model* | Journal of Healthcare Informatics Research | [`papers/paperB/`](papers/paperB/) |

**Paper A** asks whether a patient whose decisions are made in code is safer than the same language model given the whole case file and
told how to behave (a prompt-only baseline). On 14 held-out scripted conversations, each run with three seeds and judged by a model from a
different family:

- **Accuracy:** no detectable difference. The per-conversation composite was 0.970 for the code-governed Twin (v2) and 0.978 for the
  prompt-only baseline (paired difference −0.008, 95% CI −0.022 to +0.004).
- **Safety:** the Twin failed no jailbreak attempts and always disclosed the death wish when it was due; the baseline failed 6 jailbreak
  attempts and once withheld the death wish when it should have disclosed it.
- **What the gates miss:** asked 77 reworded risk questions at sufficient trust (three seeds), the Twin failed to disclose in 36.8% of cases,
  the earlier Twin in 43.3% and the prompt-only baseline in 55.8%. The Twin missed 70% of questions its memory matching did not recognise, and
  often answered plan or means questions it did recognise with the death wish instead.

**Paper B** studies that matching step on a blind benchmark of 512 doctor questions (`tests/recall/paraphrase_set.jsonl`) with a strict
tuning/test split:

- The deployed hybrid (keyword tags + a 33M-parameter sentence encoder, ~2 ms on the CPU) found 72.7% of reworded risk questions on the test
  half; keyword tags alone found 35.1%.
- Five small encoders and BM25 over the same example questions ranked about equally well (risk AUROC 0.86–0.91), so the encoder is not the
  bottleneck; deciding where to cut is.
- The patient's own 4B language model, asked zero-shot, found 94.8% at a median of ~0.4 s per question. On two further test sets written
  by other local models (Qwen3.5-4B and Gemma 4 E2B), it found 87.7% and 91.5%, while the deployed rules found 58.9% and 47.5%.
- Tuning cut-offs for recall alone was unsafe, and a classifier trained on model-generated labels lost to simple rules.

What was **not** done: no psychiatrist reviewed the cases, and no clinician or student rated replies, wrote questions or used the system in
a study. The only human judgements are the author's own ([`papers/HUMAN_STUDIES.md`](papers/HUMAN_STUDIES.md)).

## Installation

Requirements: an Apple Silicon Mac (measured on an M5 Pro with 24 GB), Python 3.12 with [uv](https://docs.astral.sh/uv/),
[llama.cpp](https://github.com/ggml-org/llama.cpp) (`llama-server` on the PATH), and, for the 3D client, Unity 6000.6.2f1. The papers build
with [Tectonic](https://tectonic-typesetting.github.io/).

```bash
git clone https://github.com/faazkhn/Rapport.git && cd Rapport
cd server/patient-service
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r requirements.txt
cd ../..
```

Models are not in git. Download the GGUF files listed in [`models/README.md`](models/README.md) into `models/` (the patient model is
Gemma 4 E4B, Q4_K_M; the judge is Qwen3.5-9B; the second-writer and bake-off models are Qwen3.5-4B and Gemma 4 E2B). The speech, voice and
sentence-encoder models download themselves into the Hugging Face cache on first use; after that nothing needs the internet.

**Run the patient:**

```bash
cd server/patient-service && ./run.sh        # starts llama-server on :8080 if needed and serves on :8765
curl -s http://127.0.0.1:8765/health
```

Then open `unity/PsychSim` in Unity, load `Assets/Scenes/Encounter.unity` and press Play, or build with **Rapport > Build macOS
(Development)**. The examiner's live view of the Twin is at `http://127.0.0.1:8765/twin/?live=1`. More in
[`server/patient-service/README.md`](server/patient-service/README.md) and [`docs/LIVE_DEMO_GUIDE.md`](docs/LIVE_DEMO_GUIDE.md).

**Tests:**

```bash
cd server/patient-service && .venv/bin/python -m pytest -q    # 245 pass
.venv/bin/python validate_data.py                              # case files against their schemas
```

## Reproducing the results

Every number in the papers comes from files in this repository; the scripts below regenerate them. Use
`server/patient-service/.venv/bin/python` as `PY`. Runs that call a model need the patient model on port 8080 and, for judging, the judge on
8081:

```bash
tools/llm_eval/serve.sh models/gemma-4-E4B-it-Q4_K_M.gguf 8080
tools/llm_eval/serve.sh models/Qwen3.5-9B-Q4_K_M.gguf 8081
```

| What | Command | Output |
|---|---|---|
| Held-out runs of one brain version (`v0`, `v2`, the prompt-only baseline `p0`, ablations `v2n*`) | `$PY tools/learning/loop.py heldout v2 --case mdd_01 --seeds 11,23,42 --judge-url http://127.0.0.1:8081/v1` | `tests/llm-eval/results/learning/` |
| Missed risk inside conversations (paper A) | `$PY tools/learning/risk_probe.py run v2 --seeds 11,23,42 --judge-url http://127.0.0.1:8081/v1`, then `report` | `tests/overnight/riskprobe/` |
| Disclosure judge on saved runs, and the single-fact re-check | `$PY tools/learning/judge_disclosure.py <runs>`; `$PY tools/learning/recheck.py` | in place |
| Recall benchmark, deployed rules | `$PY tools/recall_bench.py --split test` (`--lexical`: tags only; `--hand`: hand-set heads) | stdout / `--json` |
| Recall baselines: tags, BM25, five encoders, AUROC/AUPRC (paper B) | `$PY tools/recall_baselines.py cpu` | `tests/overnight/recall_baselines.json` |
| Zero-shot LLM classifier and cascade (paper B) | `$PY tools/recall_baselines.py llm` | `tests/overnight/recall_llm.json` |
| Second-writer test sets (paper B) | `$PY tools/recall_writer.py tests/recall/writer_qwen4b.jsonl --url <writer server>`, then `RECALL_TEST_SET=<set> $PY tools/recall_baselines.py cpu` (and `llm`) | `tests/recall/`, `tests/overnight/*_writer_*.json` |
| Tables and numbers for both papers | `$PY papers/analysis/new_results.py` (earlier analyses: `papers/analysis/analyses.py`) | `papers/paper*/gen/` |
| Figures | `$PY papers/figures/make_figures.py` | `papers/figures/` |
| Papers and supplements | `tectonic -X compile` on each `.tex` in `papers/paperA_jms/` and `papers/paperB/` | PDFs |

The whole overnight sequence used for the papers is `tools/overnight/queue5.sh` → `queue6.sh` → `queue7.sh` → `queue8.sh` (each step's log
and exit code in `tests/overnight/papers/status.md`). Sampling seeds are fixed, but llama.cpp on a different machine or build can still give
slightly different replies; latency depends on the hardware.

## How the patient works

Every turn: code reads the doctor's move (21 types, word patterns), changes trust, distress, agitation and engagement, recalls the memories
the words touch (keyword tags plus sentence embeddings, with trust locks applied after matching), and builds a short list of allowed
behaviours. One structured call to the language model writes the reply, choosing only from that list; every sentence is then checked against
the case before speech. Locked memory text never enters the prompt. Each patient is a JSON case file
(`unity/PsychSim/Assets/StreamingAssets/data/cases/`), so a new station is a new file. Specification: [`docs/TWIN.md`](docs/TWIN.md);
decisions: [`docs/adr/`](docs/adr/).

| Part | Model / tool | Licence |
|---|---|---|
| Patient language model | Gemma 4 E4B (Q4_K_M) on llama.cpp | Gemma terms |
| Judge (evaluation only) | Qwen3.5-9B (Q4_K_M) | as published |
| Speech to text | Parakeet TDT 0.6B v2 | CC-BY-4.0 |
| Voice activity, turn end | Silero VAD; Smart Turn v3 | MIT; BSD-2-Clause |
| Patient voice | Qwen3-TTS 1.7B VoiceDesign (fallback KittenTTS mini 0.8) | Apache-2.0 |
| Memory matching | bge-small-en-v1.5 (ONNX, CPU) | MIT |

## Repository layout

| Path | What |
|---|---|
| `server/patient-service/` | The patient service: the Twin (`mind.py`, `brain.py`, `twin.py`, `rubric.py`, `memory.py`, `consistency.py`), speech, voice, brain versions (`learned/versions/`) |
| `unity/PsychSim/` | The Unity client: room, bodies, cues, examination, tablet and debrief |
| `tools/` | Evaluation, learning loop, recall benchmark and baselines, latency, overnight queues |
| `tests/` | Held-out scripts (`llm-eval/`), recall benchmark (`recall/`), saved runs and logs |
| `papers/` | Papers A and B with their supplements, the analyses and figures behind them |
| `docs/` | Design, decisions, measurements, literature review |

## Licence

Rapport's own code, data, case files and papers are licensed under the [Apache License 2.0](LICENSE) (see also [NOTICE](NOTICE)).

**Third-party assets** keep their own licences and are not relicensed by this repository: the language, speech and voice models
([`models/README.md`](models/README.md)), vendored web libraries (`server/patient-service/twin/vendor/`), LaTeX journal templates
(the Springer Nature class in `papers/paperA_jms/` and `papers/paperB/`), and the 3D characters (Reallusion Character Creator exports), animations and environment models under
`unity/PsychSim/Assets/Art/`. These are used under licences that permit this use; check each source's terms before reusing them
elsewhere.

## Citation

If you use Rapport, the patient model or the recall benchmark, please cite the Zenodo archive,
[doi:10.5281/zenodo.24367080](https://doi.org/10.5281/zenodo.24367080) (version 0.3.0: 10.5281/zenodo.24367081). GitHub's **Cite this
repository** button reads [`CITATION.cff`](CITATION.cff).

## Disclaimer

Rapport is a research and teaching prototype. All clinical content (cases, rules, rubric, answer key) is an AI-assisted draft that has not
been reviewed by a psychiatrist. It is for education and research only. It is not a medical device, not for diagnosis or treatment, and not a
substitute for supervised clinical training. Release builds refuse case files still marked draft. The patients are fictional, and their
voices are designed from text descriptions, not cloned from anyone. The cases include thoughts of death and suicide.

## Acknowledgements

Built by Faaz Khan Mohammad (MIT World Peace University, Pune), with an AI assistant (Claude, Anthropic) used throughout for code, analysis
and writing, as each paper states.
