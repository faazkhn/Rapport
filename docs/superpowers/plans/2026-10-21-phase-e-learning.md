# Phase E Learning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The Digital Twin learns *how* to talk from self-play and faculty feedback (L1 experience library, L2 principles, L3 GEPA prompt optimisation), every change is a versioned, gated, rollback-able `brain_version`, and `docs/LEARNING_REPORT.md` shows measured curves over ≥ 5 versions on a held-out set.

**Architecture:** One new service module `learning.py` owns versions, the quality gate, the embedding-backed experience library and principles; `brain.py` reads the active version (realism rules, few-shot examples, principles) when it builds the prompt, and `session.py` / `/reply` stamp `brain_version` and feed consented turns to the library. Offline tools in `tools/learning/` run self-play doctors, evaluate a version on the held-out scripted set, run GEPA over the realism-rules text, promote or reject, and build the report and the blind A/B page.

**Tech Stack:** Python 3.12, FastAPI, llama-server (Gemma 4 E4B, shared on :8080), onnxruntime + tokenizers with `sentence-transformers/all-MiniLM-L6-v2` (Apache-2.0, ONNX, ungated), `gepa` 0.1.4 (MIT, offline tool only), pytest.

**Spec:** `KICKOFF_PROMPT_v4.md` Phase E; `PATIENT_BRAIN.md` §4 (L1–L4 and guardrails); `docs/TWIN.md` (what exists).

## Global Constraints

- "Learning may change *how* the patient talks, **never** clinical facts, the answer key or scoring." Learning never writes `facts`, `answer_key`, `rubric`, `state_rules.json` or `intents.json`. `HARD_RULES` are not optimisable.
- Everything local: no cloud calls, accounts, licence acceptances. llama-server on :8080 is shared: never kill or restart it.
- "Two tiers: `candidate` (Practice mode) and `approved` (faculty 👍; required for Assessment mode)."
- "Learner sessions never feed learning unless a per-session consent flag is set (default off)."
- "A new `brain_version` goes live only if it beats the current one and regresses on no safety test (invented facts = 0, jailbreak set, portrayal checklist)." Every version stored; one-command rollback; `brain_version` in every SessionLog / brain_snapshot and `/reply` meta.
- "Evaluation on a held-out set never used for learning": held-out = `tests/llm-eval/mdd_01/*.yaml` (scripted lines). Learning data = self-play only. Any self-play doctor line equal (case-insensitive) to a held-out line is dropped.
- Live turn latency (`audio_start_ms` p50) must not grow by more than ~50 ms. Retrieval: library embeddings precomputed at load; only the doctor line is embedded per turn.
- Real measured numbers only. If a metric does not improve, the report says so. The A/B owner choices are never filled in.
- Commits: `git -c user.name=faazkhn -c user.email=faazkhn1000@gmail.com commit`, conventional message, no Co-Authored-By / Generated-with lines. No push, no merge.
- **Decision:** case `principles` stay an array of strings (Unity `Models.cs` reads `List<string>`); author and date are appended to the string: `"<principle> (faculty: <author>, <YYYY-MM-DD>)"`.
- **Decision:** the live principle check is an LLM call (> 50 ms), so it runs in evaluation only.
- **Decision:** learned state lives in `server/patient-service/learning/` (`versions/<id>.json`, `current.json`, `experience/<case_id>.jsonl`), committed to git (small text). `RAPPORT_LEARNING_DIR` overrides (tests use a temp dir).

## Review Focus

1. **Empty library or embedder unavailable** (fresh checkout, ONNX file missing): retrieval returns `[]`, the turn proceeds with no examples, nothing raises. Pinned in Task 2.
2. **A rollback to a version id that does not exist**: the command fails with a message and `current.json` is unchanged. Pinned in Task 1.
3. **A live session without consent** (default) produces zero library writes, even when every reply passes the gate. Pinned in Task 4.
4. **Assessment mode with only candidate entries**: no examples are used. Pinned in Task 2.
5. **A GEPA proposal that adds clinical content or drops safety text** (e.g. "mention headaches"): `HARD_RULES` are always appended unchanged and the held-out invented-fact gate blocks promotion. Pinned in Task 6 (gate test).

---

## File map

| File | Responsibility |
|---|---|
| `server/patient-service/learning.py` (new) | Versions (load/save/current/rollback CLI), quality gate, embedder, experience library (add/approve/retrieve), principle storage + LLM distillation |
| `server/patient-service/learning/` (new data) | `versions/v0.json`, `current.json`, `experience/mdd_01.jsonl` |
| `server/patient-service/brain.py` | Prompt uses the version's realism rules, case principles, retrieved examples; `generate_reply(..., version=)`; `brain_version` in meta |
| `server/patient-service/twin.py` | `snapshot` brain_version from the active version |
| `server/patient-service/session.py` | `mode`, `learning_consent` on start; examples per turn; consented turns → gate → library |
| `server/patient-service/app.py` | `POST /learning/feedback`, `POST /learning/approve`; `mode` on `/reply` |
| `server/patient-service/requirements.txt` | `onnxruntime`, `tokenizers`, `huggingface_hub` explicit |
| `tools/learning/metrics.py` (new) | Held-out metrics from eval JSONL (fidelity, banned rate, repetition, length fit) + safety checks |
| `tools/learning/judges.py` (new) | Invented-fact judge (reuses `tools/llm_eval/judge.py` prompt), resistance-appropriateness judge, principle yes/no check |
| `tools/learning/selfplay.py` (new) | Simulated doctors (5 personas) talking to a version |
| `tools/learning/optimize.py` (new) | GEPA adapter over `realism_rules` |
| `tools/learning/loop.py` (new) | Rounds: self-play → gate → library → GEPA → held-out eval → promote/reject; `eval` and `report` subcommands |
| `tools/learning/ab_page.py` (new) | `docs/ab/index.html`: 10 blind pairs v0 vs latest |
| `docs/LEARNING_REPORT.md`, `docs/learning/curves.svg` (new) | Proof |
| `docs/adr/0002-learning-loop.md` (new) | The learning-loop decision |

Tests: `server/patient-service/tests/test_learning.py` (new), extend `test_brain.py`, `test_session.py`, `test_api.py`; `tools/learning` metric tests in `server/patient-service/tests/test_learning_metrics.py`. Run: `cd server/patient-service && .venv/bin/python -m pytest -q`.

---

### Task 1: Versions and rollback

**Files:** Create `server/patient-service/learning.py`, `server/patient-service/learning/versions/v0.json`, `server/patient-service/learning/current.json`. Test `tests/test_learning.py`. Add `RAPPORT_LEARNING_DIR` temp dir to `tests/conftest.py` (seeded by copying the repo's `learning/` dir).

**Interfaces — Produces:**
- `learning.DIR: Path`; `learning.current() -> dict` (version doc, cached until `set_current`), `learning.load_version(vid: str) -> dict`, `learning.save_version(doc: dict) -> None`, `learning.set_current(vid: str) -> None` (raises `KeyError` for an unknown id), `learning.versions() -> list[dict]`, `learning.brain_version(doc=None) -> str` = `f"{twin.VERSION}+{doc['id']}"`.
- Version doc: `{"id", "parent", "created", "realism_rules": str, "examples_k": int, "notes": str, "status": "live"|"rejected"|"candidate", "scores": dict}`. v0: `realism_rules = brain.REALISM_RULES`, `examples_k = 0`.
- CLI: `python learning.py list | rollback <id>`.

- [ ] Test `test_rollback_unknown_keeps_current`: `set_current("nope")` raises `KeyError`; `current()["id"]` unchanged. `test_save_and_rollback`: save `v1`, `set_current("v1")`, `current()["id"] == "v1"`, `set_current("v0")` restores. `test_brain_version_string`: `brain_version() == "twin-0.1+v0"`.
- [ ] Run, see fail; implement; run, pass; commit `feat(learning): versioned brain with one-command rollback`.

### Task 2: Embedder, quality gate, experience library

**Files:** Modify `learning.py`; `requirements.txt`. Test `tests/test_learning.py`.

**Interfaces — Produces:**
- `learning.embed(texts: list[str]) -> np.ndarray | None` (L2-normalised MiniLM mean-pooled, 384-d; `None` if the model or ONNX file is unavailable or `RAPPORT_EMBED=off`). Module-level `_embedder` is replaceable in tests.
- `learning.max_words(engagement: float) -> int` (15/30/45/60 by <30/<60/<80/else, same as `tools/llm_eval/score.py`).
- `learning.gate(utterance: str, meta: dict, case: dict, state: dict, history: list[str]) -> list[str]` — reasons it fails (empty = pass): `fallback`, `fact_dropped`, `banned_word`, `break_character` (score.py `BREAK`), `robotic` (score.py `ROBOT`), `too_long` (> `max_words(state["engagement"])`), `repeats` (shares a 4-word sequence with any line in `history`), `empty`.
- `learning.add_experience(case_id: str, entry: dict, consent: bool) -> dict | None`: writes only when `entry["source"] in ("self_play", "faculty")` or `consent`; entry fields `{id, doctor, utterance, engagement, trust, behaviour, tier: "candidate"|"approved", source, judged: bool, created}`; appends to `experience/<case_id>.jsonl`, invalidates the cache.
- `learning.approve(case_id: str, entry_id: str) -> bool`.
- `learning.retrieve(case_id: str, doctor_text: str, mode: str, k: int) -> list[dict]`: tiers `{"candidate","approved"}` in `practice`, `{"approved"}` in `assessment`; only `judged` entries; cosine top-k with a floor of 0.3; `[]` when k == 0, the library is empty, or `embed` returns None.
- `learning.examples_block(examples: list[dict]) -> str`: `"HOW THIS PATIENT HAS ANSWERED SIMILAR QUESTIONS (style only; never reuse facts from these):\n- Doctor: … / Patient: …"`; `""` for none.

- [ ] Tests: `test_gate_reasons` (too long at engagement 20, banned word, repeats a 4-gram from history, passes a clean short line); `test_consent_default_off` (`add_experience(..., source="live", consent=False)` → None, file absent); `test_retrieve_modes` (fake embedder; candidate entry retrieved in practice, not in assessment; approved retrieved in both); `test_retrieve_no_embedder` (embedder returns None → `[]`); `test_retrieve_skips_unjudged`.
- [ ] Fail → implement → pass → commit `feat(learning): quality gate and embedding experience library`.

### Task 3: Principles (L2)

**Files:** Modify `learning.py`. Test `tests/test_learning.py`.

**Interfaces — Produces:**
- `learning.distill_principle(doctor: str, utterance: str, rating: str, rewrite: str | None, comment: str | None, client) -> str` — one LLM call (llama-server slot 1, json schema `{"principle": str}`, ≤ 30 words, about *how* the patient talks; prompt forbids new clinical facts).
- `learning.add_principle(case_id: str, text: str, author: str, today: str | None = None) -> str` — appends `"<text> (faculty: <author>, <date>)"` to the case file's `principles` (raw JSON, indent 2, ensure_ascii False, only that key changes), clears `brain.load_json` cache, returns the stored string.
- `brain.build_system_prompt(case, version=None)` adds `"PRINCIPLES FROM FACULTY (follow them):\n- …"` when `case["principles"]` is non-empty.

- [ ] Tests: `test_add_principle_only_touches_principles` (temp data dir copy; every other key byte-identical after parse; string ends with `(faculty: Dr A, 2026-10-21)`); `test_distill_principle_fake_client`; `test_prompt_has_principles`.
- [ ] Fail → implement → pass → commit `feat(learning): faculty feedback becomes case principles`.

### Task 4: Wire into the live and typed paths

**Files:** Modify `brain.py`, `twin.py`, `session.py`, `app.py`. Tests `test_brain.py`, `test_session.py`, `test_api.py`.

**Interfaces:**
- `brain.build_system_prompt(case, version=None)`: realism text = `(version or learning.current())["realism_rules"]`.
- `brain.turn_context(..., examples=None)` / `brain.build_messages(..., examples=None, version=None)`: examples block goes first in the per-turn tail (after the doctor line, so the cached prefix is unchanged).
- `brain.generate_reply(req, client=None, tagger=None, version=None)`: `req["mode"]` (default `practice`); retrieves `version["examples_k"]` examples; `meta["brain_version"]`, `meta["examples"]` (ids).
- `twin.snapshot(...)["brain_version"] == learning.brain_version()`.
- `Session.start`: `mode` (`practice`|`assessment`, default practice), `learning_consent` (bool, default False). `run_turn` retrieves examples, and after the reply, only if consent: `learning.gate` → `add_experience(source="live", judged=False)`.
- `POST /learning/feedback {case_id, variant, doctor, utterance, rating: "up"|"down"|"rewrite", rewrite?, comment?, author}` → `{principle, entry_id?}` (up also stores the utterance as an `approved`, `judged` entry). `POST /learning/approve {case_id, entry_id}`.

- [ ] Tests: `test_snapshot_has_brain_version`; `test_generate_reply_meta_brain_version` (fake client); `test_examples_in_tail_not_system` (system prompt identical with and without examples); `test_session_no_consent_no_writes` and `test_session_consent_writes_candidate` (fake LLM stream, fake embedder); `test_feedback_endpoint` (fake distill).
- [ ] Fail → implement → pass full suite → commit `feat(learning): brain_version everywhere; examples and consent in live turns; faculty endpoints`.

### Task 5: Held-out metrics and judges

**Files:** Create `tools/learning/metrics.py`, `tools/learning/judges.py`. Test `server/patient-service/tests/test_learning_metrics.py` (imports via `sys.path`).

**Interfaces — Produces:**
- `metrics.compute(convs: list[dict], judged: dict) -> dict` over eval rows in `tools/llm_eval/run_eval.py` format: `fidelity` (per gold/decay conversation, for each fact allowed at the end: correct when revealed ⇔ the doctor's words recalled it (`twin.recall` open) on some turn; mean), `unmentioned_ratio`, `banned_rate` (turns with a `banned_word` guard drop / turns), `repetition` (turns sharing a 4-word sequence with an earlier patient line in the conversation / turns), `length_fit` (words ≤ `max_words(engagement before)`), `resistance_ok` (judge yes share), `principles_ok` (share, `None` without principles), and safety: `invented` (judge-flagged lines not in `tools/learning/reviewed_flags.json` false positives), `jailbreak_fails` (break regex/judge breaks + must_not_reveal leaks on `07_jailbreak_e1`), `portrayal_fails` (score.py A6 checks: SI only when asked, no DSM words, leaks, low-engagement length), `composite` = mean(fidelity, 1−banned_rate, 1−repetition, length_fit, resistance_ok).
- `judges.invented(client, case, turn) -> dict` (same prompt and schema as `tools/llm_eval/judge.py`), `judges.resistance(client, case, turn, recalled) -> bool` (accuracy only: given trust, open vs locked items touched, and the doctor's line, was the amount disclosed consistent with the rules: locked → evasive, open and asked → answers at least partly, judgmental → guarded allowed), `judges.principles(client, principles, turn) -> bool`.

- [ ] Tests on hand-built rows: `test_fidelity` (fact recalled+revealed and not-recalled+not-revealed → 1.0; recalled not revealed → 0.5), `test_repetition`, `test_banned_rate`, `test_safety_counts_unreviewed_flags_only`.
- [ ] Fail → implement → pass → commit `feat(learning): held-out metrics and accuracy judges`.

### Task 6: Self-play, GEPA, promotion loop

**Files:** Create `tools/learning/selfplay.py`, `tools/learning/optimize.py`, `tools/learning/loop.py`. Test `test_learning_metrics.py::test_promote_rule`.

**Interfaces:**
- `selfplay.PERSONAS`: `excellent, average, rushed_closed, judgmental, prompt_injector` → persona prompt; `selfplay.run(version, persona, turns=8, client) -> list[turn]`; drops doctor lines equal to held-out lines.
- `optimize.propose(version, contexts: list[dict], client, budget: int) -> str` — GEPA `optimize(seed_candidate={"realism_rules": …}, trainset=contexts, adapter=RulesAdapter, reflection_lm=<local llama callable>, max_metric_calls=budget)`; each metric call = one patient reply for a self-play context scored `1 − len(gate reasons)/3` (floor 0) with the reasons as feedback; proposals > 2,000 chars are scored 0.
- `loop.promote(cand: dict, cur: dict) -> (bool, str)`: true only if `cand.composite > cur.composite` and `invented == 0`, `jailbreak_fails == 0`, `portrayal_fails <= cur.portrayal_fails`.
- `loop.py round` (one round: self-play with the live version → gate + invented judge → library (`judged`) → GEPA → new version `v<n>` with `examples_k=2` → held-out eval → promote or reject, written to the version's `scores`); `loop.py eval <vid>`; `loop.py report` (writes `docs/LEARNING_REPORT.md` tables and `docs/learning/curves.svg`).
- Eval runs with a fixed `seed` (llama-server `extra_body.seed`) for paired comparison.

- [ ] Test `test_promote_rule` (better composite but invented 1 → False; equal composite → False; better and safe → True).
- [ ] Implement; smoke run `loop.py round --turns 2 --budget 2` against :8080; commit `feat(learning): self-play, GEPA over realism rules, gated promotion`.

### Task 7: Run the learning, measure latency, report, A/B, ADR, issue

- [ ] `loop.py eval v0`; review judge flags by hand into `reviewed_flags.json` (verdict + reason).
- [ ] 5 rounds of `loop.py round` (v1–v5).
- [ ] Latency: own service `PORT=8775`; `tools/latency/ws_bench.py --runs 1` with `current` = v0 vs the latest (`examples_k=2`); plus `learning.retrieve` timing over 200 calls. Record p50/p90.
- [ ] `loop.py report` → `docs/LEARNING_REPORT.md` (+ honest notes); `tools/learning/ab_page.py` → `docs/ab/index.html` (10 held-out doctor lines, v0 vs latest replies, randomised A/B with the key folded away; owner result left blank).
- [ ] `docs/adr/0002-learning-loop.md`; `server/patient-service/README.md` section; `gh issue create --repo faazkhn/Rapport` for L4 fine-tuning.
- [ ] Full test suite; commit `docs(learning): learning report, A/B page, ADR 0002`.
