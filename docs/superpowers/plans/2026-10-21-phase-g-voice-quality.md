# Phase G: Voice and Reply Quality Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix owner complaints (a)–(f) from `docs/STATE_AUDIT.md`: replies that sound real and varied, a designed emotional voice, fewer pauses and less lag.

**Architecture:** Reply realism is fixed in `brain.py` (prompt, length bands, recent-phrase avoidance) and in a code-side text pass (`voice.py`, new) that caps hesitations before text reaches TTS. A bake-off script measures candidate TTS models; the winner gets a streaming backend in `voice.py` that turns the reply's emotion and Twin labels into an instruction. Turn-taking gains Smart Turn on top of Silero, and STT runs speculatively while the doctor pauses.

**Tech Stack:** Python 3.12, mlx-audio 0.6.0 (MIT) for TTS candidates, KittenTTS (baseline), Smart Turn v3 ONNX (BSD-2), onnxruntime, Parakeet (parakeet-mlx).

**Spec:** `KICKOFF_PROMPT_v4.md` Phase G; root causes in `docs/STATE_AUDIT.md`.

## Global Constraints

- Everything local; downloads only from public, ungated Hugging Face repos with MIT/Apache/BSD/CC-BY licences; no accounts, no sign-ins, no licence click-throughs.
- Voices come from text descriptions only. Never clone a real person.
- Learning or tuning may change how the patient talks, never clinical facts, the answer key or scoring.
- Owner checkpoints are replaced by objective measures plus a listening page the owner can take later (owner instruction 2026-10-20: "go with the recommended solution, don't wait").
- Latency target: p50 ≤ 700 ms, p90 ≤ 1,000 ms (end of speech → first patient audio); barge-in ≤ 150 ms. If missed, report the breakdown; never trade away the no-invented-facts rule for speed.
- Safety metrics stay at zero: invented facts, jailbreak breaks, banned words spoken.
- Commits authored `faazkhn <faazkhn1000@gmail.com>`, no Claude attribution lines.
- After the phase: rebuild the macOS app and update `docs/LIVE_DEMO_GUIDE.md`.

## Review Focus

1. **A reply that is only hesitation** ("..."): after the hesitation cap it must not become empty or unspeakable; fall back to the original text minus dots. Pinned in Task 1.
2. **The new TTS backend fails to load or crashes mid-reply** (out of memory with Gemma loaded): the service falls back to KittenTTS for that session and keeps talking. Pinned in Task 4.
3. **Smart Turn says "not finished" forever** (a doctor who trails off): a hard cap ends the turn at the old 500 ms silence plus 700 ms. Pinned in Task 5.
4. **Speculative STT result is stale** (the doctor resumes talking): the stale transcript is discarded and the final one used. Pinned in Task 5.
5. **Emotion instruction for an unknown emotion or a missing Twin label:** falls back to the case's neutral voice description. Pinned in Task 4.

---

### Task 1: Reply realism and the hesitation cap

**Files:** Create `server/patient-service/voice.py`, `tools/llm_eval/reply_stats.py`, `docs/voice-quality.md`. Modify `server/patient-service/brain.py` (`REALISM_RULES`, `describe_state`, `turn_context`), `server/patient-service/session.py` (text to TTS), `unity/.../cases/mdd_01.json` (`patient.speech_style`). Test `tests/test_voice.py`, `tests/test_brain.py`.

**Interfaces — Produces:** `voice.speakable(text: str) -> str` (at most one "..." per reply, later ones become ", "; a leading "..." dropped; never returns empty when `text` has letters). `brain.recent_patient_lines(messages, n=3) -> list[str]`. `reply_stats.py <results.jsonl>` prints ellipsis rate, mean words, distinct behaviours, repeated-trigram rate (share of replies sharing a 3-word phrase with an earlier reply in the same conversation).

- [ ] Write failing tests: `test_speakable_caps_ellipses` ("I... I don't... know..." → "I... I don't, know"), `test_speakable_never_empty` ("..." → "", "... hm ..." → "hm"), `test_recent_lines_in_context` (the transient tail lists the last 3 patient lines under "DON'T REPEAT THESE PHRASES" and never in the system prompt).
- [ ] Run, see FAIL. Implement. Run, see PASS.
- [ ] Baseline: `run_eval.py --label g-before --runs 1` on the 9 scripted conversations; `reply_stats.py` on it; save numbers.
- [ ] Rewrite `REALISM_RULES` (keep every hard rule): hesitate at most once a reply; vary openings; answer the question asked with one concrete everyday detail when trust allows; widen length bands (low engagement ≤ 15 words, mid 1–2 sentences ≤ 30, high ≤ 4 sentences); behaviour guidance by trust band (low: guarded_short/minimises/deflects/vague_timeline; mid: answers_plainly/answers_different_question/asks_back; high: answers_plainly/tearful_disclosure). Edit `speech_style` to drop "pauses" emphasis. Add the recent-phrases block.
- [ ] After: same eval; gate: ellipsis rate ≤ 25%, distinct behaviours ≥ 5, repeated-trigram rate below baseline, `judge.py` invented facts 0 and no jailbreak break. Write before/after numbers and 6 paired transcript lines in `docs/voice-quality.md`.
- [ ] Commit `feat(voice): realistic varied replies, hesitation cap, phrase repetition control`.

### Task 2: Pause sources

**Files:** Modify `server/patient-service/brain.py` (`slowed_pause_s`), `server/patient-service/session.py` (`tts_speed`), `unity/.../cases/mdd_01.json` (`patient.voice_speed`), `unity/PsychSim/Assets/Scripts/Cues/SpeechTiming.cs` (mirror formula). Test `tests/test_session.py`, Unity `CoreLogicTests`.

**Interfaces — Produces:** `slowed_pause_s` = `0` if slowed < 0.1 else `0.4 + 0.8 * slowed` (max 1.2 s, was 3 s). `voice_speed` for mdd_01 0.9 → 1.0; slowed floor 0.85 → 0.9.

- [ ] Update `test_slowed_pause_formula_matches_unity` to the new formula first; run, FAIL; change Python and C#; run both suites, PASS.
- [ ] Commit `feat(voice): shorter clinically sized hesitation, natural base speed`.

### Task 3: TTS bake-off

**Files:** Create `tools/tts_lab/bakeoff.py`, `docs/tts-bakeoff.md`, `docs/listening/index.html` (+ `docs/listening/*.wav`, git-ignored except the page; the page is rebuilt by the script).

Candidates (each checked for licence before download; skip and record if gated or non-commercial): KittenTTS mini 0.8 (baseline), Kitten TTS 2, Kokoro-82M, Qwen3-TTS 1.7B VoiceDesign, Qwen3-TTS 0.6B CustomVoice, Chatterbox Turbo, Kyutai Pocket TTS.

Measures per model, with llama-server loaded: load time; time to first audio (streaming if supported); RTF; peak memory; Parakeet word accuracy on 8 lines; emotion following = mean absolute difference in median F0 (semitones) and RMS (dB) between "sad, tearful" and "anxious, fast" instructions on the same 4 sentences (0 for models without instructions).

Decision rule (stated in the doc before results): eligible = licence OK, word accuracy ≥ 0.93, streaming TTFA ≤ 450 ms, RTF ≤ 0.8 under load. Among eligible, highest emotion separation wins; ties → lower TTFA. If none is eligible, keep KittenTTS and record why.

- [ ] Write the script and the decision rule; run; write results table and the decision into `docs/tts-bakeoff.md`; generate the blind listening page (8 lines × candidates, shuffled labels, answer key in a collapsed section).
- [ ] Commit `feat(voice): TTS bake-off, decision and blind listening page`.

### Task 4: Winning TTS backend, streaming, emotion instructions

**Files:** Modify `server/patient-service/voice.py`, `session.py` (`synth`, `speak`), `requirements.txt`, `data/brain/expression_map.json` (add `voice` instruction strings), case `variants.*.voice_description`. Test `tests/test_voice.py`, `tests/test_session.py`.

**Interfaces — Produces:** `voice.instruction(case: dict, reply_or_labels: dict) -> str` (case voice description + "In this line: <expression voice for reaction/behaviour/emotion>"; unknown → description only). `voice.Backend` with `.stream(text, voice_id, speed, instruction) -> Iterator[np.ndarray]` at 24 kHz; `voice.load(name: str) -> Backend` for `kitten` and the winner; env `RAPPORT_TTS` (default = winner). Session falls back to `kitten` on load error or a synthesis exception and logs it once.

- [ ] Failing tests: instruction for `sad`/`tearful_disclosure` contains the expression text; unknown emotion → description only; a backend that raises mid-reply → session finishes the reply with the fallback backend (fake backends, no models).
- [ ] Implement; first chunk of each sentence goes out with its `sentence` message, later chunks as bare PCM (Unity already accepts PCM without a pending sentence).
- [ ] Live check: 4-turn run; `ws_bench.py --runs 1`; transcribe 5 replies back (≥ 0.93).
- [ ] Commit `feat(voice): <winner> streaming backend with Twin-driven emotion; Kitten fallback`.

### Task 5: Turn-taking: Smart Turn and speculative STT

**Files:** Modify `server/patient-service/stt.py` (`Vad`), `session.py` (`on_frame`, `end_speech`), `requirements.txt`. Create `docs/adr/0002-turn-detection-and-pipecat.md`. Test `tests/test_session.py`, `tests/test_stt.py` (new, fakes only).

**Interfaces — Produces:** `stt.SmartTurn.complete(audio16k: np.ndarray) -> float` (probability; ONNX `pipecat-ai/smart-turn-v3`, last 8 s). Endpoint rule: after ≥ 200 ms of silence, end the turn if `complete ≥ 0.5`; otherwise keep waiting; hard cap at 1,200 ms of silence. Speculative STT: start `transcribe` on the audio so far at 200 ms of silence; use it if no new speech arrived before the endpoint, else discard and re-run.

- [ ] Failing tests with a fake SmartTurn and fake STT: complete=0.9 ends at ~200 ms; complete=0.1 ends at the 1,200 ms cap; resumed speech discards the speculative transcript.
- [ ] Implement; download the ONNX model to `models/` (git-ignored) with its licence noted in `models/README.md`.
- [ ] `ws_bench.py --runs 1`: record the table in `docs/latency.md`; target p50 ≤ 700 ms. If missed, write the breakdown.
- [ ] ADR 0002: Smart Turn adopted; Pipecat (the framework) not adopted, reasons.
- [ ] Commit `feat(voice): Smart Turn endpointing and speculative STT`.

### Task 6: Phase close

- [ ] Full suites (service, Unity EditMode), `validate_data.py`.
- [ ] Rebuild the macOS app (Development build, `unity/PsychSim/Builds/`), launch it once, screenshot the start screen.
- [ ] Update `docs/LIVE_DEMO_GUIDE.md` (create it if missing) with the voice changes and new checks.
- [ ] Update `HANDOFF.md`; commit.
