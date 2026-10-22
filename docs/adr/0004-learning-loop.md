# 4. Learning loop: experience library, faculty principles, GEPA-gated brain versions

Date: 2026-10-21 · Status: accepted

## Context

Phase E asks the Digital Twin to get better at *how* it talks with use, without ever changing clinical facts, the answer key or scoring, fully locally, and without slowing the live voice (budget: about +50 ms p50). Learning must be provable on data it never saw and reversible.

## Decision

- **L1 experience library (EvoPatient pattern).** A reply enters `server/patient-service/learned/experience/<case>.jsonl` only after the rule gate (`learning.gate`: no fallback, no guard fact drop, no banned word, no character break or assistant/jargon phrase, length within the engagement band, no repeated 4-word run) and, for self-play, the invented-fact judge. Retrieval embeds only the doctor's line with all-MiniLM-L6-v2 (Apache-2.0, ONNX on CPU, about 1 ms); library embeddings are computed once per library change. Top 2 examples go into the per-turn tail, after the cached prefix. Tiers: `candidate` (Practice) and `approved` (faculty 👍; the only tier Assessment uses).
- **Consent.** A learner's (live) turn is stored only when the session's `learning_consent` is true (default false), and then only as an unjudged candidate that retrieval ignores until judged or approved.
- **L2 faculty principles (Roleplay-doh).** `POST /learning/feedback` turns 👍/👎/rewrite into one principle with one LLM call and appends it to the case's `principles` as `"<text> (faculty: <author>, <date>)"`. Strings, not objects, because Unity's `Models.cs` reads `List<string>`. The principle check is an LLM call, so it runs in evaluation only (it cannot meet the 50 ms live budget).
- **L3 brain versions with GEPA.** A version (`learned/versions/v<n>.json`) holds the realism-rules text, `examples_k` and `library_upto` (the self-play library snapshot it may use). GEPA (MIT) evolves only the realism-rules text, reflecting with the local Gemma on self-play replies that failed the rule checks. `HARD_RULES`, facts, intents, state rules and scoring are not components. A version goes live only if its held-out composite beats the live version and it has 0 invented-fact flags (after hand review), 0 jailbreak failures and no more portrayal failures. `learning.py rollback <vid>` switches back; `brain_version` (`twin-0.1+v<n>`) is in every `brain_snapshot` (so in Unity's SessionLog) and in `/reply` meta.
- **Held-out evaluation.** The scripted `tests/llm-eval/mdd_01/*.yaml` conversations, never used by learning; self-play doctor lines identical to a held-out line are dropped. Evaluations use a fixed sampling seed.
- **L4 fine-tuning** is out of scope (GitHub issue).

## Consequences

- The live path gains one 1 ms embedding and about 70 prompt tokens in the tail.
- Judges are the same local Gemma as the patient, so their flags are reviewed by hand (`tools/learning/reviewed_flags.json`); a single judge is a known weakness.
- Self-play doctors are the same model too, so the library reflects one model's idea of doctors.

## Alternatives rejected

- DSPy: heavier, and GEPA alone covers single-text optimisation.
- Faculty approval before any library use: safest, but nothing could be learned before faculty exist; candidates are Practice-only instead.
- Examples in the system prompt: would break the KV-cache prefix on every turn.
