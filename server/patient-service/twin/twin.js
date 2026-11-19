/* Digital Twin. Everything drawn is a pure function of time t (seconds) and the timeline, so render mode is deterministic.
   Modes: live (default over http, or ?live=1), replay (?timeline=url, or ?live=0 for the bundled demo_timeline.js), render (&render=1). See README.md. */
(() => {
  "use strict";
  const Q = new URLSearchParams(location.search);
  const RENDER = Q.get("render") === "1";
  // served by the patient service, the plain link is the live session; ?live=0 plays the bundled demo
  const LIVE = Q.get("live") === "1" || (Q.get("live") !== "0" && !RENDER && !Q.has("timeline") && location.protocol.startsWith("http"));
  const theme = Q.get("theme") || (RENDER ? "dark" : null);
  if (theme) document.documentElement.dataset.theme = theme;
  if (RENDER) document.body.classList.add("render");

  const KEYS = [["trust", "Trust", "--trust"], ["distress", "Distress", "--distress"], ["agitation", "Agitation", "--agit"], ["engagement", "Engagement", "--engage"]];
  const GLOW_S = 0.6, GAUGE_S = 0.8;
  const $ = (id) => document.getElementById(id);
  const clamp = (v, a = 0, b = 1) => Math.max(a, Math.min(b, v));
  const ease = (x) => { x = clamp(x); return x < .5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2; };
  const lerp = (a, b, k) => a + (b - a) * k;
  const human = (s) => (s || "").replace(/_/g, " ");
  const fmtT = (t) => { t = Math.max(0, Math.floor(t)); return String(Math.floor(t / 60)).padStart(2, "0") + ":" + String(t % 60).padStart(2, "0"); };

  // Tween a value through a step series [{t, v}] (series[0].t = -Infinity). Pure: restarts from the in-flight value.
  function tween(series, t, dur, get) {
    let from = get(series[0].v), to = from, t0 = -1e9;
    for (let i = 1; i < series.length && series[i].t <= t; i++) {
      from = lerp(from, to, ease((series[i].t - t0) / dur)); to = get(series[i].v); t0 = series[i].t;
    }
    return lerp(from, to, ease((t - t0) / dur));
  }
  // Pulse envelope: rise `a` s, hold `h` s, fall `r` s.
  function env(t, t0, a = .25, h = 1, r = GLOW_S) {
    const d = t - t0;
    if (d < 0) return 0;
    if (d < a) return ease(d / a);
    if (d < a + h) return 1;
    return 1 - ease((d - a - h) / r);
  }
  // Window with fade in/out of GLOW_S around [a, b].
  const win = (t, a, b, fin = .3) => (b == null || a == null) ? 0 : clamp(Math.min(ease((t - a) / fin), 1 - ease((t - b) / GLOW_S)));

  // ---------- model ----------
  let TL = null, M = null;
  function prepare(tl) {
    tl.events = (tl.events || []).slice().sort((a, b) => a.t - b.t);
    const st0 = tl.state_start || { trust: 30, distress: 50, agitation: 20, engagement: 40 };
    const snaps = tl.events.filter((e) => e.type === "snapshot");
    const turns = new Map();
    const T = (n) => { if (!turns.has(n)) turns.set(n, { n }); return turns.get(n); };
    for (const e of tl.events) {
      const r = T(e.turn ?? 0);
      if (e.type === "doctor_start") { r.ds = e.t; r.doctor = e.doctor ?? r.doctor; }
      else if (e.type === "doctor_end") r.de = e.t;
      else if (e.type === "patient_start") r.ps = e.t;
      else if (e.type === "patient_end") r.pe = e.t;
      else if (e.type === "snapshot") { r.snap = e; r.doctor = r.doctor ?? e.doctor; }
      else if (e.type === "ward_event") (r.ward ||= []).push(e);
    }
    for (const r of turns.values()) {
      r.start = r.ds ?? r.de ?? r.snap?.t ?? r.ps ?? 0;
      if (r.ps == null && r.snap) r.ps = r.snap.t;
      if (r.pe == null && r.ps != null && r.snap) r.pe = r.ps + Math.max(1.2, (r.snap.utterance || "").split(/\s+/).length * .33);
      r.end = Math.max(r.pe ?? 0, r.ps ?? 0, r.de ?? 0, r.start);
    }
    const st = [{ t: -Infinity, v: st0 }, ...snaps.map((s) => ({ t: s.t, v: s.state || st0 }))];
    const md = [{ t: -Infinity, v: padFrom(st0) }, ...snaps.map((s) => ({ t: s.t, v: s.mood || padFrom(s.state || st0) }))];
    const sn = (f, v0) => [{ t: -Infinity, v: v0 }, ...snaps.map((s) => ({ t: s.t, v: f(s) }))];
    const ctrl = (s) => ({ none: .2, quantity: .7 }[s.resistance] ?? (s.resistance ? .8 : .2));
    const items = (tl.memory_items || []).map((m) => ({ ...m, recalls: snaps.filter((s) => (s.recalled || []).includes(m.id)).map((s) => s.t),
      lockedHits: snaps.filter((s) => (s.locked_hit || []).includes(m.id)).map((s) => s.t) }));
    for (const m of items) m.unlockAt = crossing(st, m.trust_min);
    const tl_end = Math.max(0, ...tl.events.map((e) => e.t), ...[...turns.values()].map((r) => r.end));
    M = { snaps, turns: [...turns.values()].filter((r) => r.n).sort((a, b) => a.start - b.start), st, md, items,
      amy: sn((s) => .12 + .88 * clamp((s.intensity ?? 0) / 10), .12), pfc: sn(ctrl, .2), end: tl_end };
  }
  // State-only PAD fallback for live snapshots without `mood` (same formula as staged_timeline.py).
  function padFrom(s) {
    const t = s.trust, d = s.distress, a = s.agitation, e = s.engagement;
    return { p: clamp(((t - 50) * .35 + (e - 50) * .35 - (d - 50) * .9) / 45, -1, 1),
      a: clamp(((a - 30) + (d - 50) * .5 + (e - 50) * .2) / 40, -1, 1),
      d: clamp(((t - 50) * .5 + (e - 50) * .5 - (d - 50) * .6 - (a - 30) * .4) / 50, -1, 1) };
  }
  // First time the displayed (tweened) trust reaches `min`, by bisection on the pure tween.
  function crossing(st, min) {
    if (st[0].v.trust >= min) return -Infinity;
    for (let i = 1; i < st.length; i++) {
      const hi0 = st[i].t + GAUGE_S + .01;
      if (tween(st, hi0, GAUGE_S, (v) => v.trust) < min) continue;
      let lo = st[i].t, hi = hi0;
      for (let k = 0; k < 30; k++) { const mid = (lo + hi) / 2; if (tween(st, mid, GAUGE_S, (v) => v.trust) >= min) hi = mid; else lo = mid; }
      return hi;
    }
    return Infinity;
  }
  const lastBefore = (arr, t) => { let r = null; for (const x of arr) { if (x.t <= t) r = x; else break; } return r; };

  // ---------- static DOM ----------
  const gaugeEls = {};
  function buildStatic() {
    const meta = TL.meta || {};
    $("who").innerHTML = meta.patient ? `<b>${esc(meta.patient)}</b>${meta.age ? ", " + meta.age : ""} · ${esc(meta.case_id || "")}${meta.title ? " · " + esc(meta.title) : ""}${meta.style ? " · style " + esc(meta.style) : ""}${meta.seed != null ? " · seed " + esc(String(meta.seed)) : ""}` : (LIVE ? "Live · waiting for session" : "—");
    $("tPatName").textContent = meta.patient ? meta.patient.split(" ")[0] : "Patient";
    const gl = document.querySelector(".glist"); gl.innerHTML = "";
    for (const [k, label, c] of KEYS) {
      const d = document.createElement("div"); d.className = "g"; d.style.setProperty("--c", `var(${c})`);
      d.innerHTML = `<span class="gl">${label}</span><span class="gv">0</span><svg viewBox="0 0 100 30" preserveAspectRatio="none"><line class="base" x1="0" x2="100" y1="0" y2="0"/><path class="area"/><path class="spark"/><circle class="end" r="2.2"/></svg><div class="bar"><i></i></div>`;
      gl.appendChild(d);
      gaugeEls[k] = { v: d.querySelector(".gv"), bar: d.querySelector(".bar i"), spark: d.querySelector(".spark"), area: d.querySelector(".area"), end: d.querySelector(".end"), base: d.querySelector(".base") };
    }
    // memory ladder: one row per trust threshold, lowest at the bottom
    const lad = $("ladder"); lad.querySelectorAll(".row").forEach((r) => r.remove());
    const ths = [...new Set(M.items.map((m) => m.trust_min))].sort((a, b) => a - b);
    M.rows = ths.map((th) => {
      const row = document.createElement("div"); row.className = "row";
      row.innerHTML = `<span class="th">${th}</span><div class="chips"></div>`;
      for (const m of M.items.filter((x) => x.trust_min === th)) {
        const c = document.createElement("span"); c.className = "chip locked"; c.title = m.id;
        c.innerHTML = `<svg class="ic" viewBox="0 0 12 12"></svg><span>${esc(m.label || m.id)}</span>`;
        row.querySelector(".chips").appendChild(c); m.el = c; m.ic = c.querySelector(".ic"); m.cls = "";
      }
      lad.insertBefore(row, $("trustLine"));
      return { th, el: row };
    });
    measure();
    const fp = TL.formulation || {};
    $("fpsStatus").textContent = fp.status || "Draft — not faculty-validated";
    $("fpList").innerHTML = ["presenting", "predisposing", "precipitating", "perpetuating", "protective"].filter((k) => fp[k])
      .map((k) => `<dt>${k}</dt><dd>${esc(fp[k])}</dd>`).join("") || `<dd class="dim">No formulation in timeline.</dd>`;
    buildStrip();
  }
  function measure() {
    if (!M?.rows) return;
    const lad = $("ladder").getBoundingClientRect();
    for (const r of M.rows) { const b = r.el.getBoundingClientRect(); r.y = b.top - lad.top + b.height / 2; r.top = b.top - lad.top; r.bot = b.bottom - lad.top; }
    M.ladH = lad.height;
  }
  function buildStrip() {
    const box = $("turns"); box.querySelectorAll(".seg").forEach((s) => s.remove());
    const span = Math.max(M.end, 1);
    for (const r of M.turns) {
      const s = document.createElement("div"); s.className = "seg";
      const L = r.start / span * 100, W = Math.max(.6, (r.end - r.start) / span * 100);
      s.style.left = L + "%"; s.style.width = `calc(${W}% - 3px)`;
      const rel = (a, b) => (a == null || b == null) ? "" : `left:${(a - r.start) / (r.end - r.start || 1) * 100}%;width:${(b - a) / (r.end - r.start || 1) * 100}%`;
      s.innerHTML = `<span class="d" style="${rel(r.ds, r.de)}"></span><span class="p" style="${rel(r.ps, r.pe)}"></span><span><span class="lbn">T</span>${r.n}</span>${r.snap?.exam_action ? '<span class="ex" title="exam action"></span>' : ""}`;
      s.dataset.t = r.start; box.appendChild(s); r.el = s;
    }
  }
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const LOCK = '<rect x="2.5" y="5.5" width="7" height="5" rx="1"/><path d="M4 5.5V4a2 2 0 0 1 4 0v1.5"/>';
  const KEY = '<circle cx="4" cy="6" r="2.2"/><path d="M6.2 6H11M9.5 6v2"/>';
  const OPEN = '<circle cx="6" cy="6" r="3.2"/>';
  const TOLD = '<path d="M2.5 6.5l2.3 2.3L9.5 3.5"/>';

  // ---------- draw(t) ----------
  let lastKey = {};
  const setText = (el, s) => { if (el.textContent !== s) el.textContent = s; };
  const setHTML = (el, s, k) => { if (lastKey[k] !== s) { el.innerHTML = s; lastKey[k] = s; } };
  const op = (id, v) => { $(id).style.opacity = (clamp(v) * getGlowOp()).toFixed(3); };
  let glowOp = null; const getGlowOp = () => glowOp ?? (glowOp = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--glow-op")) || 1);

  function draw(t) {
    if (!M) return;
    const snap = lastBefore(M.snaps, t);
    const turn = (() => { let r = null; for (const x of M.turns) if (x.start <= t + 1e-6) r = x; return r; })();
    const S = {}; for (const [k] of KEYS) S[k] = tween(M.st, t, GAUGE_S, (v) => v[k]);
    const mood = { p: tween(M.md, t, GAUGE_S, (v) => v.p), a: tween(M.md, t, GAUGE_S, (v) => v.a), d: tween(M.md, t, GAUGE_S, (v) => v.d) };

    // phase
    let phase = ["Waiting", "var(--faint)"];
    if (turn) {
      if (turn.ds != null && t >= turn.ds && (turn.de == null || t < turn.de)) phase = ["Doctor speaking", "var(--engage)"];
      else if (turn.de != null && t >= turn.de && (turn.ps == null || t < turn.ps)) phase = ["Patient thinking", "var(--pfc)"];
      else if (turn.ps != null && t >= turn.ps && t < turn.pe) phase = ["Patient speaking", "var(--lang)"];
      else phase = ["Listening", "var(--trust)"];
    }
    const ph = $("phase"); setText(ph.lastElementChild, phase[0]);
    const dot = ph.firstElementChild; dot.style.background = phase[1];
    dot.style.boxShadow = `0 0 ${(6 + 4 * Math.sin(t * 5)).toFixed(1)}px ${phase[1]}`;
    setText($("clock"), fmtT(t));

    // brain
    const recallE = Math.max(0, ...M.snaps.filter((s) => s.recalled?.length).map((s) => env(t, s.t, .3, 1.6, .9)));
    const lockedE = Math.max(0, ...M.snaps.filter((s) => s.locked_hit?.length).map((s) => env(t, s.t, .2, .5, .6) * (.6 + .4 * Math.sin((t - s.t) * 14))));
    const speakP = turn ? win(t, turn.ps, turn.pe) : 0, speakD = turn ? win(t, turn.ds, turn.de) : 0;
    const think = turn ? win(t, turn.de, turn.ps == null ? null : turn.ps + .4, .2) : 0;
    const flick = (f) => .8 + .2 * Math.sin(t * f) * Math.sin(t * f * .37 + 1);
    const cueLvl = Math.max(0, ...M.snaps.flatMap((s) => (s.cues || []).map((c) => (c.intensity ?? .5) * win(t, s.t, s.t + (c.duration_s ?? 4)))));
    const nonv = Math.max(0, ...M.snaps.filter((s) => s.expression?.nonverbal).map((s) => env(t, s.t - .5, .3, .5, .9)));
    const Z = { hip: .12 + .88 * recallE, hipRed: lockedE, amy: tween(M.amy, t, GLOW_S, (v) => v) * (.85 + .15 * speakP),
      pfc: .1 + .45 * tween(M.pfc, t, GLOW_S, (v) => v) + .45 * think, broca: .06 + .9 * speakP * flick(11),
      wern: .06 + .85 * speakD * flick(9) + .25 * speakP, ins: .08 + .35 * clamp((mood.a + 1) / 2) + .5 * cueLvl,
      stem: .1 + .5 * clamp(S.agitation / 60) + .55 * nonv };
    for (const k in Z) op("g_" + k, Z[k]);
    const lab = { l_pfc: .1 + .9 * think + .4 * tween(M.pfc, t, GLOW_S, (v) => v), l_broca: speakP, l_wern: speakD, l_hip: recallE, l_amy: tween(M.amy, t, GLOW_S, (v) => v), l_ins: cueLvl, l_stem: nonv };
    for (const k in lab) $(k).style.opacity = (.55 + .45 * clamp(lab[k])).toFixed(3);
    const recalling = snap && snap.recalled?.length && recallE > .02 ? snap.recalled.map((id) => M.items.find((m) => m.id === id)?.label || id) : null;
    const rc = $("recallCap"); setText(rc, recalling ? "Recalling · " + recalling.join(" · ") : ""); rc.style.opacity = recallE.toFixed(3);

    // gauges + sparklines
    const done = M.snaps.filter((s) => s.t <= t), n = Math.max(M.snaps.length, 12);
    for (const [k] of KEYS) {
      const g = gaugeEls[k], v = S[k];
      setText(g.v, String(Math.round(v))); g.bar.style.width = v.toFixed(2) + "%";
      const pts = [[0, M.st[0].v[k]], ...done.map((s, i) => [(i + 1) / n * 100, s.state[k]])];
      pts[pts.length - 1][1] = v;
      const xy = pts.map(([x, y]) => [x, 28 - y / 100 * 26]);
      const d = "M" + xy.map((p) => p[0].toFixed(2) + " " + p[1].toFixed(2)).join("L");
      g.spark.setAttribute("d", d);
      g.area.setAttribute("d", d + `L${xy[xy.length - 1][0].toFixed(2)} 30L0 30Z`);
      g.end.setAttribute("cx", xy[xy.length - 1][0]); g.end.setAttribute("cy", xy[xy.length - 1][1]);
      const y0 = (28 - M.st[0].v[k] / 100 * 26).toFixed(2); g.base.setAttribute("y1", y0); g.base.setAttribute("y2", y0);
    }

    // mood PAD
    const px = (p) => 100 + p * 82, py = (a) => 100 - a * 82;
    const trail = [M.md[0].v, ...done.map((s) => s.mood || padFrom(s.state))];
    trail[trail.length - 1] = mood;
    $("padTrail").setAttribute("points", trail.map((m) => px(m.p).toFixed(1) + "," + py(m.a).toFixed(1)).join(" "));
    setHTML($("padDots"), trail.slice(0, -1).map((m) => `<circle cx="${px(m.p).toFixed(1)}" cy="${py(m.a).toFixed(1)}" r="2.2"/>`).join(""), "pad");
    const r = 5 + 6 * (mood.d + 1) / 2;
    for (const id of ["padDot", "padHalo"]) { $(id).setAttribute("cx", px(mood.p).toFixed(2)); $(id).setAttribute("cy", py(mood.a).toFixed(2)); }
    $("padDot").setAttribute("r", r.toFixed(2)); $("padHalo").setAttribute("r", (r * 2.1 + 2 * Math.sin(t * 2)).toFixed(2));
    setHTML($("padVals"), `<span>P <b>${sg(mood.p)}</b></span><span>A <b>${sg(mood.a)}</b></span><span>D <b>${sg(mood.d)}</b></span><span class="padq">${quad(mood)}</span>`, "padv");

    // now card
    if (snap) {
      setText($("nReact"), human(snap.reaction)); setText($("nBeh"), human(snap.behaviour)); setText($("nRes"), human(snap.resistance));
      const ward = (M.turns.find((x) => x.n === snap.turn)?.ward || []).map((w) => "Event: " + w.say).join(" ");
      setText($("nWhy"), (ward ? ward + " " : "") + (snap.why || "")); setText($("nowTurn"), "turn " + snap.turn);
      setHTML($("nInt"), Array.from({ length: 10 }, (_, i) => `<i class="${i < (snap.intensity ?? 0) ? "on" : ""}"></i>`).join(""), "int");
    } else { setText($("nReact"), "—"); setText($("nWhy"), "Waiting for the first turn."); setHTML($("nInt"), Array.from({ length: 10 }, () => "<i></i>").join(""), "int"); }
    const fresh = snap ? env(t, snap.t, .35, 1e6, 0) : 1;
    $("nReact").style.opacity = $("nWhy").style.opacity = (.25 + .75 * fresh).toFixed(3);

    // expression
    const x = snap?.expression || {};
    setText($("xFace"), x.face || "—"); $("xFace").className = "pill" + (snap && (snap.intensity ?? 0) >= 6 ? " hot" : "");
    setText($("xGaze"), x.gaze || "—"); setText($("xVoice"), x.voice || "—");
    setHTML($("xSound"), x.nonverbal ? `<span class="pill">${esc(human(x.nonverbal))}</span>` : '<span class="dim">none</span>', "snd");
    setHTML($("xExam"), snap?.exam_action ? `<span class="pill exam">${esc(snap.exam_action)}</span>` : '<span class="dim">none</span>', "exam");
    const cues = snap?.cues || [];
    $("xBody").innerHTML = cues.length ? cues.map((c) => {
      const lv = (c.intensity ?? .5) * win(t, snap.t, snap.t + (c.duration_s ?? 4));
      return `<span class="cue">${esc(human(c.id))}<i><b style="width:${(lv * 100).toFixed(1)}%"></b></i></span>`;
    }).join("") : '<span class="dim">resting</span>';

    setHTML($("xLine"), snap ? [`<span class="pill${(snap.intensity ?? 0) >= 6 ? " hot" : ""}">${esc(x.face || "face_neutral")}</span>`,
      ...cues.filter((c) => win(t, snap.t, snap.t + (c.duration_s ?? 4)) > .05).map((c) => `<span class="cue">${esc(human(c.id))}</span>`),
      x.nonverbal ? `<span class="pill">${esc(human(x.nonverbal))}</span>` : "", snap.exam_action ? `<span class="pill exam">exam · ${esc(human(snap.exam_action))}</span>` : ""].join("") : "", "xline");
    // transcript
    if (turn) {
      setHTML($("tDoc"), reveal(turn.doctor || "", turn.ds, turn.de, t), "doc");
      setHTML($("tPat"), t < (turn.ps ?? Infinity) ? (t >= (turn.de ?? Infinity) ? '<span class="ghost">…</span>' : "") : reveal(turn.snap?.utterance || "", turn.ps, turn.pe, t), "pat");
      setText($("tLat"), turn.snap && t >= turn.snap.t && turn.snap.latency_ms != null ? `reply latency ${turn.snap.latency_ms} ms` : "");
    } else { setHTML($("tDoc"), "", "doc"); setHTML($("tPat"), "", "pat"); setText($("tLat"), ""); }
    document.querySelector(".doc .who-l").style.setProperty("--sp", speakD.toFixed(3));
    document.querySelector(".pat .who-l").style.setProperty("--sp", speakP.toFixed(3));

    // memory ladder
    for (const m of M.items) {
      const unlocked = S.trust >= m.trust_min - 1e-6;
      const told = m.recalls.some((rt) => rt <= t);
      const cls = told ? "told" : !unlocked ? "locked" : m.gated ? "gated" : "open";
      if (cls !== m.cls) { m.el.className = "chip " + cls; m.ic.innerHTML = { told: TOLD, locked: LOCK, gated: KEY, open: OPEN }[cls]; m.cls = cls; }
      m.f = Math.max(0, ...m.recalls.map((rt) => env(t, rt, .3, 1.6, 1.2)));
      m.u = env(t, m.unlockAt, .2, .5, 1.2);
      m.r = Math.max(0, ...m.lockedHits.map((rt) => env(t, rt, .2, .6, .8)));
      m.el.style.setProperty("--f", m.f.toFixed(3));
      m.el.style.setProperty("--u", m.u.toFixed(3));
      m.el.style.setProperty("--r", m.r.toFixed(3));
    }
    if (M.rows?.length) {
      // Line sits just above row k when trust == th_k and slides to above row k+1 as trust reaches th_{k+1}.
      const rows = M.rows, gap = (k) => k < rows.length - 1 ? (rows[k].top + rows[k + 1].bot) / 2 : Math.max(2, rows[k].top - 6);
      let i = 0; while (i < rows.length - 1 && S.trust >= rows[i + 1].th) i++;
      const y = i >= rows.length - 1 ? gap(i) : lerp(gap(i), gap(i + 1), clamp((S.trust - rows[i].th) / (rows[i + 1].th - rows[i].th)));
      $("trustLine").style.transform = `translateY(${y.toFixed(2)}px)`;
      setText($("trustLab"), `trust ${Math.round(S.trust)}`);
    }

    // timeline strip
    const span = Math.max(M.end, 1);
    $("playhead").style.left = clamp(t / span * 100, 0, 100) + "%";
    for (const r of M.turns) if (r.el) { const c = turn === r ? "seg cur" : r.end < t ? "seg past" : "seg"; if (r.el.className !== c) r.el.className = c; }

    window.twin3d?.frame(t, { Z, snap, turn, S, mood, items: M.items });
  }
  const quad = (m) => Math.hypot(m.p, m.a) < .12 ? "neutral" : m.p < 0 ? (m.a >= 0 ? "tense" : "low, withdrawn") : (m.a >= 0 ? "elated" : "calm");
  const sg = (v) => (v >= 0 ? "+" : "−") + Math.abs(v).toFixed(2);
  function reveal(text, a, b, t) {
    if (!text) return "";
    const w = text.split(/(\s+)/); const words = w.filter((s) => s.trim()).length;
    const k = (a == null || b == null) ? 1 : clamp((t - a) / Math.max(.1, b - a));
    const shown = Math.ceil(k * words); let c = 0, out = "", rest = "";
    for (const s of w) { if (!s.trim()) { (c <= shown ? (out += s) : (rest += s)); continue; } c++; if (c <= shown) out += s; else rest += s; }
    return esc(out) + (rest ? `<span class="ghost">${esc(rest)}</span>` : "");
  }

  // ---------- clock, controls ----------
  let T = 0, playing = false, wall0 = 0, t0 = 0;
  const now = () => performance.now() / 1000;
  function setTime(s) { T = +s || 0; playing = false; draw(T); updIcon(); return T; }
  function updIcon() { $("playIcon").setAttribute("d", playing ? "M4 2.5h3v11H4zM9 2.5h3v11H9z" : "M4 2.5v11l9-5.5z"); }
  function loop() {
    if (!RENDER) {
      if (LIVE) T = now() - liveT0;
      else if (playing) { T = t0 + (now() - wall0); if (T >= M.end + 2) { T = M.end + 2; playing = false; updIcon(); } }
      draw(T);
    }
    requestAnimationFrame(loop);
  }
  function toggle() { if (LIVE) return; playing = !playing; if (playing) { if (T >= M.end + 1.9) T = 0; wall0 = now(); t0 = T; } updIcon(); }
  function seekX(e) { const b = $("turns").getBoundingClientRect(); T = clamp((e.clientX - b.left) / b.width) * Math.max(M.end, 1); wall0 = now(); t0 = T; draw(T); }
  function wire() {
    $("play").onclick = toggle;
    let drag = false; const tb = $("turns");
    tb.addEventListener("pointerdown", (e) => { if (RENDER || LIVE) return; const seg = e.target.closest(".seg"); drag = true; tb.setPointerCapture(e.pointerId);
      if (seg && !e.shiftKey) { T = +seg.dataset.t; wall0 = now(); t0 = T; draw(T); } else seekX(e); });
    tb.addEventListener("pointermove", (e) => { if (drag) seekX(e); });
    tb.addEventListener("pointerup", () => { drag = false; });
    addEventListener("keydown", (e) => {
      if (RENDER || LIVE) return;
      if (e.code === "Space") { e.preventDefault(); toggle(); }
      if (e.code === "ArrowRight" || e.code === "ArrowLeft") { T = clamp(T + (e.code === "ArrowRight" ? 5 : -5), 0, M.end + 2); wall0 = now(); t0 = T; draw(T); }
    });
    addEventListener("resize", () => { measure(); draw(T); });
  }

  // ---------- live ----------
  let liveT0 = now(), liveTurn = 0;
  const EVT = new Set(["doctor_start", "doctor_end", "patient_start", "patient_end", "snapshot", "ward_event"]);
  function push(o) {
    if (!o || typeof o !== "object") return;
    if (o.type === "init") { TL = { meta: o.meta || {}, memory_items: o.memory_items || [], formulation: o.formulation || {}, state_start: o.state_start, events: [] }; liveT0 = now() - (o.t ?? 0); liveTurn = 0; prepare(TL); buildStatic(); return; }
    if (!TL) { TL = { meta: {}, memory_items: [], formulation: {}, events: [] }; prepare(TL); buildStatic(); }
    const e = { ...o, type: EVT.has(o.type) ? o.type : "snapshot", t: LIVE ? (o.t ?? now() - liveT0) : (o.t ?? T) };  // the service stamps t (s since session start); a late viewer replays it in place
    if (LIVE && o.t != null && o.t > now() - liveT0) liveT0 = now() - o.t;  // a late viewer's clock catches up with the session
    if (e.type === "doctor_start" && e.turn == null) e.turn = ++liveTurn;
    if (e.turn == null) e.turn = liveTurn || 1; else liveTurn = Math.max(liveTurn, e.turn);
    if (e.type === "snapshot" && !e.mood && e.state) e.mood = padFrom(e.state);
    TL.events.push(e); prepare(TL); buildStatic();
    draw(LIVE ? now() - liveT0 : T);
  }

  // ---------- load ----------
  function load(tl) { TL = tl; prepare(TL); buildStatic(); draw(T); return TL; }
  function fetchTimeline(url) {
    return new Promise((res, rej) => {
      if (/\.js(\?|$)/.test(url)) { const s = document.createElement("script"); s.src = url; s.onload = () => res(window.TWIN_TIMELINE); s.onerror = () => rej(new Error("cannot load " + url)); document.head.appendChild(s); return; }
      const x = new XMLHttpRequest(); x.open("GET", url); x.overrideMimeType("application/json");
      x.onload = () => { try { res(JSON.parse(x.responseText)); } catch (e) { rej(e); } }; x.onerror = () => rej(new Error("cannot load " + url + (location.protocol === "file:" ? " (file:// needs Chrome --allow-file-access-from-files, or pass a .js timeline)" : "")));
      x.send();
    });
  }
  const ready = (async () => {
    const url = Q.get("timeline");
    let tl;
    if (LIVE) tl = { meta: {}, memory_items: [], formulation: {}, events: [] };
    else if (url) tl = await fetchTimeline(url);
    else tl = window.TWIN_TIMELINE;
    if (!tl) throw new Error("no timeline: pass ?timeline=<url> or ?live=1");
    if (document.fonts?.ready) await document.fonts.ready;
    load(tl);
    if (Q.has("t")) setTime(+Q.get("t"));
    if (LIVE) {
      try { new BroadcastChannel("digital-twin").onmessage = (m) => push(m.data); } catch (_) { /* BroadcastChannel missing on old file:// contexts */ }
      addEventListener("message", (m) => { if (m.data && m.data.twin) push(m.data.twin); });
      const wsUrl = Q.get("ws") || (location.protocol.startsWith("http") ? `ws://${location.host}/twin/ws` : null);
      const connect = () => { const ws = new WebSocket(wsUrl); ws.onmessage = (m) => push(JSON.parse(m.data)); ws.onclose = () => setTimeout(connect, 2000); };
      if (wsUrl) connect();
      document.body.classList.add("render");
    }
    wire(); updIcon(); requestAnimationFrame(loop);
    return true;
  })().catch((e) => { document.body.insertAdjacentHTML("afterbegin", `<div style="position:fixed;inset:auto 1rem 1rem auto;background:#400;color:#fff;padding:.6rem 1rem;border-radius:.5rem;z-index:9">${esc(e.message)}</div>`); throw e; });

  window.twin = { push, load, setTime, ready, get time() { return T; }, get duration() { return M ? M.end : 0; }, play: () => { if (!playing) toggle(); }, pause: () => { if (playing) toggle(); } };
})();
