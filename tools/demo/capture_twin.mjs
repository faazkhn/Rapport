#!/usr/bin/env node
// Deterministic frame capture of the Chitta Twin into an H.264 mp4 (or PNG stills).
// Loads twin/index.html?timeline=...&render=1 in headless Chrome, calls twin.setTime(t) per frame, pipes PNGs to ffmpeg.
//
// Setup (once): cd tools/demo && npm install
// Usage (from Med/):
//   node tools/demo/capture_twin.mjs --timeline server/patient-service/twin/demo_timeline.json --start 0 --end 10 -o demo/staged/twin.mp4
//   node tools/demo/capture_twin.mjs --timeline ... --still 40.5 -o shot.png [--width 1920 --height 1080 --theme light]
// Options: --width 1200 --height 2160 (the 600x1080 side panel at 2x) --scale 1 (deviceScaleFactor) --fps 30
//          --start 0 --end <timeline end> --theme dark|light --crf 16 --downscale 2 (ffmpeg output = viewport / downscale; 1 keeps size)
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import puppeteer from "puppeteer-core";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, "../..");
const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";

const argv = process.argv.slice(2), A = {};
for (let i = 0; i < argv.length; i++) {
  const k = argv[i].replace(/^-+/, "");
  if (k === "o") A.out = argv[++i]; else A[k] = argv[i + 1]?.startsWith("--") || i + 1 >= argv.length ? true : argv[++i];
}
if (A.h || A.help || !A.out) { console.log(readHelp()); process.exit(A.out ? 0 : 1); }
const W = +(A.width ?? 1200), H = +(A.height ?? 2160), DSF = +(A.scale ?? 1), FPS = +(A.fps ?? 30);
const DOWN = +(A.downscale ?? (W === 1200 && H === 2160 ? 2 : 1));
const timeline = path.resolve(A.timeline ?? path.join(ROOT, "server/patient-service/twin/demo_timeline.json"));
const page_url = pathToFileURL(path.join(ROOT, "server/patient-service/twin/index.html")).href
  + `?timeline=${encodeURIComponent(pathToFileURL(timeline).href)}&render=1&theme=${A.theme ?? "dark"}`;
if (!existsSync(timeline)) { console.error("timeline not found: " + timeline); process.exit(1); }

const browser = await puppeteer.launch({
  executablePath: CHROME, headless: true,
  // file:// XHR for the timeline; fixed colour profile and no GPU variance so frames are reproducible.
  args: ["--allow-file-access-from-files", "--force-color-profile=srgb", "--disable-gpu", "--hide-scrollbars", "--font-render-hinting=none", "--disable-lcd-text"],
  defaultViewport: { width: W, height: H, deviceScaleFactor: DSF },
});
try {
  const page = await browser.newPage();
  page.on("pageerror", (e) => console.error("page error:", e.message));
  await page.goto(page_url, { waitUntil: "load" });
  await page.evaluate(() => window.twin.ready);
  const dur = await page.evaluate(() => window.twin.duration);
  const shot = async (t) => { await page.evaluate((t) => window.twin.setTime(t), t); return page.screenshot({ type: "png", optimizeForSpeed: true }); };

  if (A.still != null) {
    await page.evaluate((t) => window.twin.setTime(t), +A.still);
    await page.screenshot({ path: path.resolve(A.out), type: "png" });
    console.log(`wrote ${A.out} (t=${A.still}s, ${W}x${H}@${DSF})`);
  } else {
    const start = +(A.start ?? 0), end = +(A.end ?? dur + 1), n = Math.max(1, Math.round((end - start) * FPS));
    const ow = Math.round(W * DSF / DOWN / 2) * 2, oh = Math.round(H * DSF / DOWN / 2) * 2;
    const ff = spawn("ffmpeg", ["-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", String(FPS), "-c:v", "png", "-i", "-",
      "-vf", `scale=${ow}:${oh}:flags=lanczos`, "-c:v", "libx264", "-preset", "medium", "-crf", String(A.crf ?? 16),
      "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-r", String(FPS), path.resolve(A.out)], { stdio: ["pipe", "inherit", "inherit"] });
    const done = new Promise((res, rej) => ff.on("close", (c) => (c === 0 ? res() : rej(new Error("ffmpeg exit " + c)))));
    const t0 = Date.now();
    for (let i = 0; i < n; i++) {
      const buf = await shot(start + i / FPS);
      if (!ff.stdin.write(buf)) await new Promise((r) => ff.stdin.once("drain", r));
      if (i % FPS === 0 || i === n - 1) {
        const el = (Date.now() - t0) / 1000;
        process.stdout.write(`\rframe ${i + 1}/${n}  t=${(start + i / FPS).toFixed(2)}s  ${((i + 1) / el).toFixed(1)} fps   `);
      }
    }
    ff.stdin.end(); await done;
    const el = (Date.now() - t0) / 1000;
    console.log(`\nwrote ${A.out}: ${n} frames ${ow}x${oh} @${FPS} fps in ${el.toFixed(1)} s (${(n / el).toFixed(1)} frames/s)`);
  }
} finally { await browser.close(); }

function readHelp() {
  return `capture_twin.mjs --timeline <json> -o <out.mp4|out.png> [--still t] [--start s] [--end s] [--fps 30]
  [--width 1200 --height 2160 --scale 1] [--downscale 2 for 1200x2160, else 1] [--theme dark|light] [--crf 16]`;
}
