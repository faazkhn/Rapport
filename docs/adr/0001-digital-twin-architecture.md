# 1. Digital Twin: one structured call, code-side state, lexical recall

Date: 2026-10-20 · Status: accepted

## Context

The patient needs a research-grounded mind (formulation, trust-gated memory, reaction, behaviour, mood) that an examiner can watch live. PatientAct, the closest published design, makes about 6 LLM calls per turn. Rapport runs a local Gemma 4 E4B at about 38 tokens/s and needs the patient to start speaking within about 1.6–1.8 s of the doctor stopping.

## Decision

- **One structured call per turn.** The Twin's labels are fields of the existing reply JSON. Only `behaviour` and `emotion` come before the utterance; `reaction`, `intensity` and `resistance` follow it. Measured: all four labels first cost about 1.2 s (p50 3,068 ms vs 1,853 ms); behaviour-only first gives p50 1,598 ms. The owner chose the behaviour-first order on 2026-10-20.
- **Code decides state.** Trust steps per reaction, the per-turn clamp and the PAD mood drift are computed in `twin.update`; the model only proposes deltas and labels.
- **Lexical recall for now.** Tags plus stemmed phrase matching, no embedding model, no LLM call. Locked items surface only as a discomfort signal.
- **The case key stays `facts`.** Memory-item fields are added to each fact so Unity's loader and guard keep working.

## Consequences

- Live latency is unchanged within noise; the Twin view and session logs get a full per-turn record.
- Reaction describes rather than steers the words.
- Recall misses paraphrases without tag words; tags are part of case authoring.

## Alternatives rejected

- PatientAct's multi-call pipeline: too slow for live voice on local hardware.
- Labels after the utterance only: fastest, but behaviour would no longer steer what is said.
- Embeddings now: needs a model choice and its own latency budget; deferred to Phase D2.
