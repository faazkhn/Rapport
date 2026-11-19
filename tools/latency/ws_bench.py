"""Latency benchmark through the real WebSocket path (docs/latency.md). Never uses the microphone.

Doctor lines are synthesized with macOS `say` en_IN voices into a scratch dir, then streamed in real time as 16 kHz PCM16
frames (32 ms), followed by silence like an open mic. Lag = first patient audio frame received - last doctor speech sample
sent, minus the deliberate `slowed` pause. Also runs barge-in trials: doctor speech starts as the patient starts talking.
Usage: server/patient-service/.venv/bin/python tools/latency/ws_bench.py <scratch_dir> [--runs 2] [--barge 10] [--json out.json]
"""
import argparse
import asyncio
import json
import subprocess
import time
from pathlib import Path

import numpy as np
import soundfile as sf
import websockets

HERE = Path(__file__).parent
FRAME = 512
VOICES = ["Aman", "Rishi", "Tara"]


def synth(lines, scratch: Path):
    scratch.mkdir(parents=True, exist_ok=True)
    out = []
    for i, line in enumerate(lines):
        p = scratch / f"doc_{i:02d}.wav"
        if not p.exists():
            subprocess.run(["say", "-v", VOICES[i % 3], "-o", str(p), "--file-format=WAVE", "--data-format=LEI16@16000", line], check=True)
        a, _ = sf.read(p, dtype="int16")
        loud = np.nonzero(np.abs(a) > 300)[0]
        out.append(a[: loud[-1] + 1] if len(loud) else a)  # trim trailing silence: lag starts at the last speech sample
    return out


async def drain(q, quiet=5.0):
    """Read and drop events until the service has been quiet for `quiet` seconds (after an early endpoint)."""
    while True:
        try:
            await asyncio.wait_for(q.get(), quiet)
        except asyncio.TimeoutError:
            return


def pct(xs, p):
    return float(np.percentile(xs, p)) if xs else float("nan")


async def run(url, wavs, lines, variant, barge, results):
    async with websockets.connect(url, max_size=None) as ws:
        q: asyncio.Queue = asyncio.Queue()
        mic = {"buf": np.zeros(0, np.int16)}

        async def reader():
            async for m in ws:
                q.put_nowait((time.monotonic(), m))

        async def mic_task():  # an always-open mic: real-time 32 ms frames, silence unless speech is queued
            nxt = time.monotonic()
            while True:
                b = mic["buf"]
                frame, mic["buf"] = (b[:FRAME], b[FRAME:]) if len(b) else (np.zeros(FRAME, np.int16), b)
                if len(frame) < FRAME:
                    frame = np.pad(frame, (0, FRAME - len(frame)))
                await ws.send(frame.tobytes())
                if mic.get("end_at") is not None and len(mic["buf"]) == 0 and len(b):
                    mic["t_last_speech"] = time.monotonic()
                nxt += FRAME / 16000
                await asyncio.sleep(max(0, nxt - time.monotonic()))

        rt = asyncio.create_task(reader())
        await ws.send(json.dumps({"type": "start", "case_id": "mdd_01", "variant": variant}))
        mt = asyncio.create_task(mic_task())

        async def wait(kind, timeout=30):
            while True:
                ts, m = await asyncio.wait_for(q.get(), timeout)
                if isinstance(m, bytes):
                    if kind == "audio":
                        return ts, m
                    continue
                ev = json.loads(m)
                if ev["type"] == kind:
                    return ts, ev

        await wait("listening")
        await asyncio.sleep(3)  # let the session warm-up fill the KV cache
        for i, wav in enumerate(wavs):
            mic["t_last_speech"] = None
            mic["end_at"] = True
            mic["buf"] = wav.copy()
            t_audio, _ = await wait("audio")
            if mic["t_last_speech"] is None:  # the turn ended before the line was sent (early endpoint): no lag, resync
                while mic["t_last_speech"] is None:
                    await asyncio.sleep(0.05)
                mic["end_at"] = None
                results.setdefault("early_endpoint", []).append(i)
                print(f"{variant} {i:2d} early endpoint (reply started before the doctor's line ended); skipped")
                await drain(q)
                continue
            mic["end_at"] = None
            _, timing = await wait("timing")
            _, reply = (None, None)
            lag = (t_audio - mic["t_last_speech"]) * 1000 - timing["slowed_pause_ms"]
            results["turns"].append({"variant": variant, "line": i, "client_lag_ms": round(lag), **{k: v for k, v in timing.items() if k != "type"}})
            print(f"{variant} {i:2d} lag {lag:6.0f} ms | vad {timing['vad_endpoint_ms']} stt {timing['stt_ms']} ttft {timing['llm_ttft_ms']} "
                  f"sent1 {timing['llm_first_sentence_ms']} tts1 {timing['tts_first_chunk_ms']} srv {timing['audio_start_ms']} pause {timing['slowed_pause_ms']}")
            await wait("listening")
            await asyncio.sleep(0.5)
        # barge-in: the doctor starts talking as soon as patient audio arrives
        for j in range(barge):
            mic["buf"] = wavs[j % len(wavs)].copy()
            await wait("audio")
            t_talk = time.monotonic()
            mic["buf"] = wavs[(j + 1) % len(wavs)].copy()
            t_stop, ev = await wait("stop")
            results["barge"].append(round((t_stop - t_talk) * 1000))
            print(f"barge {j}: stop after {results['barge'][-1]} ms (from doctor speech onset, incl. VAD detection)")
            await wait("listening", 60)
            await asyncio.sleep(1.0)
            while not q.empty():
                q.get_nowait()
        mt.cancel()
        rt.cancel()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scratch")
    ap.add_argument("--url", default="ws://127.0.0.1:8765/session")
    ap.add_argument("--runs", type=int, default=2)
    ap.add_argument("--barge", type=int, default=10)
    ap.add_argument("--json")
    a = ap.parse_args()
    lines = [x.strip() for x in (HERE / "doctor_lines.txt").read_text().splitlines() if x.strip()]
    wavs = synth(lines, Path(a.scratch))
    results = {"turns": [], "barge": []}
    for r in range(a.runs):
        asyncio.run(run(a.url, wavs, lines, ["female", "male"][r % 2], a.barge if r == a.runs - 1 else 0, results))
    keys = ["vad_endpoint_ms", "stt_ms", "llm_ttft_ms", "llm_first_sentence_ms", "tts_first_chunk_ms", "audio_start_ms", "client_lag_ms", "slowed_pause_ms"]
    print(f"\n{len(results['turns'])} turns\n| Stage | p50 ms | p90 ms | max ms |\n|---|---|---|---|")
    for k in keys:
        xs = [t[k] for t in results["turns"] if t.get(k) is not None]
        print(f"| {k} | {pct(xs, 50):.0f} | {pct(xs, 90):.0f} | {max(xs):.0f} |")
    if results["barge"]:
        print(f"| barge_in stop (from speech onset) | {pct(results['barge'], 50):.0f} | {pct(results['barge'], 90):.0f} | {max(results['barge']):.0f} |")
    if a.json:
        Path(a.json).write_text(json.dumps(results, indent=1))


if __name__ == "__main__":
    main()
