/* Digital Twin 3D: the same brain state as the 2D map, drawn as a glass brain with a graph inside it. Metaphor, not neuroscience.
   twin.js calls twin3d.frame(t, ctx) from draw(t), so everything moves as a function of t like the rest of the page.
   Zoom sets the detail: close = memory labels, middle = live cards per zone, far = zone names with activity. */
import * as THREE from "three";
import { OrbitControls } from "./vendor/OrbitControls.js";
import { CSS2DRenderer, CSS2DObject } from "./vendor/CSS2DRenderer.js";
import { GLTFLoader } from "./vendor/GLTFLoader.js";

const M = window.Motion;
const REDUCED = matchMedia("(prefers-reduced-motion: reduce)").matches;
const clamp = (v, a = 0, b = 1) => Math.max(a, Math.min(b, v));
const human = (s) => (s || "").replace(/_/g, " ");
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const cut = (s, n) => (s = s || "", s.length > n ? s.slice(0, n - 1) + "…" : s);
const css = (k) => getComputedStyle(document.documentElement).getPropertyValue(k).trim();

// Front of the brain is -x (the 2D side view faces left), up is +y, the viewer's side is +z.
const ZONES = [
  { id: "pfc", name: "Prefrontal", sub: "choice · resistance", c: "--pfc", p: [-1.05, .55, .45], r: .5, lo: [-.25, .55] },
  { id: "broca", name: "Broca", sub: "speaking", c: "--lang", p: [-.68, .05, .85], r: .24, lo: [-.6, -.15] },
  { id: "wern", name: "Wernicke", sub: "listening", c: "--lang", p: [.45, .15, .85], r: .26, lo: [.55, .45] },
  { id: "ins", name: "Insula", sub: "body state", c: "--body", p: [-.2, .15, .6], r: .24, lo: [-.05, .7] },
  { id: "amy", name: "Amygdala", sub: "reaction", c: "--amy", p: [-.35, -.2, .45], r: .17, lo: [-.55, -.6] },
  { id: "hip", name: "Hippocampus", sub: "memory recall", c: "--mem", p: [.05, -.15, .45], r: .28, lo: [.35, -.65] },
  { id: "stem", name: "Brainstem", sub: "arousal · breath", c: "--stem", p: [.25, -.75, 0], r: .22, lo: [.6, -.35] },
];
const ZP = Object.fromEntries(ZONES.map((z) => [z.id, new THREE.Vector3(...z.p)]));
const CONCEPTS = [  // live cards outside the brain, each on a leader line from its zone
  { id: "behaviour", zone: "pfc", lab: "Behaviour", p: [-1.35, .95, .6] },
  { id: "resistance", zone: "pfc", lab: "Resistance", p: [-1.45, .25, .6] },
  { id: "says", zone: "broca", lab: "Says", p: [-1.35, -.5, .7] },
  { id: "reaction", zone: "amy", lab: "Reaction", p: [-.6, -1.2, .6] },
  { id: "body", zone: "ins", lab: "Body", p: [-.55, 1.18, .5] },
  { id: "mood", zone: null, lab: "Mood", p: [.5, 1.18, .4] },
  { id: "heard", zone: "wern", lab: "Heard", p: [1.35, .85, .6] },
  { id: "arousal", zone: "stem", lab: "Arousal", p: [1.2, -.95, .3] },
];
const FRONT_TURN = -Math.PI / 2;  // model +z (front) -> -x
const LOD = [{ max: 3.1, name: "Detail" }, { max: 5.6, name: "Regions" }, { max: Infinity, name: "Zones" }];
const SVG_LOCK = '<svg viewBox="0 0 12 12" aria-hidden="true"><rect x="2.5" y="5.5" width="7" height="5" rx="1"/><path d="M4 5.5V4a2 2 0 0 1 4 0v1.5"/></svg>';

function glassMaterial(fill, edge, light) {
  return new THREE.ShaderMaterial({
    transparent: true, depthWrite: false, side: THREE.FrontSide,
    uniforms: { fill: { value: fill }, edge: { value: edge }, base: { value: light ? .1 : .06 }, rim: { value: light ? .55 : .75 } },
    vertexShader: "varying vec3 vN; varying vec3 vV; void main(){ vec4 mv = modelViewMatrix * vec4(position,1.); vN = normalize(normalMatrix*normal); vV = -mv.xyz; gl_Position = projectionMatrix*mv; }",
    fragmentShader: "uniform vec3 fill; uniform vec3 edge; uniform float base; uniform float rim; varying vec3 vN; varying vec3 vV; void main(){ float f = pow(1.-abs(dot(normalize(vN), normalize(vV))), 2.2); gl_FragColor = vec4(mix(fill, edge, f), base + rim*f); }",
  });
}

function glowTexture() {
  const c = document.createElement("canvas"); c.width = c.height = 128;
  const g = c.getContext("2d"), r = g.createRadialGradient(64, 64, 0, 64, 64, 64);
  r.addColorStop(0, "rgba(255,255,255,1)"); r.addColorStop(.35, "rgba(255,255,255,.45)"); r.addColorStop(1, "rgba(255,255,255,0)");
  g.fillStyle = r; g.fillRect(0, 0, 128, 128);
  return new THREE.CanvasTexture(c);
}

function create(card) {
  let renderer;
  try { renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true }); } catch (_) { return null; }
  if (!renderer.getContext()) return null;
  const host = document.createElement("div"); host.className = "b3"; host.innerHTML = `
    <div class="b3-tools">
      <span class="b3-hint">Drag to turn · scroll to zoom · click a node</span>
      <span class="b3-lod" aria-live="polite"></span>
      <button type="button" data-act="rotate" aria-pressed="false" title="Auto-rotate">Rotate</button>
      <button type="button" data-act="reset" title="Reset view">Reset</button>
      <button type="button" data-act="expand" aria-pressed="false" title="Expand">Expand</button>
      <button type="button" data-act="flat" title="Show the 2D map">2D</button>
    </div>
    <div class="b3-view"><div class="b3-stage"></div>
      <aside class="b3-detail" role="dialog" aria-label="Details" hidden><button type="button" class="b3-x" aria-label="Close details">×</button><div class="b3-body"></div></aside></div>
    <nav class="b3-zones" aria-label="Brain zones"></nav>`;
  card.insertBefore(host, card.querySelector(".brain-cap"));
  const stage = host.querySelector(".b3-stage");
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  stage.appendChild(renderer.domElement);
  const labels = new CSS2DRenderer(); labels.domElement.className = "b3-labels"; stage.appendChild(labels.domElement);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(38, 1, .05, 50);
  const HOME = new THREE.Vector3(.3, .35, 4.6);
  camera.position.copy(HOME);
  const controls = new OrbitControls(camera, labels.domElement);
  Object.assign(controls, { enableDamping: !REDUCED, dampingFactor: .08, minDistance: 1.6, maxDistance: 6.8, enablePan: false, rotateSpeed: .7, autoRotateSpeed: .6 });

  const brain = new THREE.Group(); scene.add(brain);
  const tex = glowTexture();
  const light = () => document.documentElement.dataset.theme === "light" || (!document.documentElement.dataset.theme && matchMedia("(prefers-color-scheme: light)").matches);
  const glass = glassMaterial(new THREE.Color(), new THREE.Color(), false);
  const dotsMat = new THREE.PointsMaterial({ size: 1.2, sizeAttenuation: false, transparent: true, opacity: .18, depthWrite: false });
  // assets/brain.glb: the owner's Brain_Model.obj, decimated to 51k faces in Blender. Its z axis runs front to back; it is turned so
  // the front faces -x, centred, and scaled to 2.76 units front to back to match the zone positions below.
  new GLTFLoader().load("assets/brain.glb", (gltf) => {
    gltf.scene.traverse((o) => {
      if (!o.isMesh) return;
      const g = o.geometry; g.computeBoundingBox();
      const box = g.boundingBox, c = box.getCenter(new THREE.Vector3()), k = 2.76 / (box.max.z - box.min.z);
      g.translate(-c.x, -c.y, -c.z); g.scale(k, k, k); g.rotateY(FRONT_TURN);
      if (!g.attributes.normal) g.computeVertexNormals();
      const m = new THREE.Mesh(g, glass); m.renderOrder = 2; brain.add(m);
      const p = g.attributes.position, pts = [];
      for (let i = 0; i < p.count; i += 6) pts.push(p.getX(i), p.getY(i), p.getZ(i));
      brain.add(new THREE.Points(new THREE.BufferGeometry().setAttribute("position", new THREE.Float32BufferAttribute(pts, 3)), dotsMat));
    });
  });

  // zones: a soft glow you see from afar, a small core you can click
  const zones = {};
  for (const z of ZONES) {
    const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }));
    sp.position.copy(ZP[z.id]); sp.renderOrder = 3; brain.add(sp);
    const core = new THREE.Mesh(new THREE.SphereGeometry(.045, 20, 14), new THREE.MeshBasicMaterial({ transparent: true }));
    core.position.copy(ZP[z.id]); core.userData = { kind: "zone", id: z.id }; brain.add(core);
    const el = document.createElement("div"); el.className = "b3-zl";
    el.innerHTML = `<b>${z.name}</b><span>${z.sub}</span><i><s></s></i>`;
    const lab = new CSS2DObject(el); lab.position.copy(ZP[z.id]).add(new THREE.Vector3(z.lo[0], z.lo[1], .3)); brain.add(lab);
    const lead = new THREE.Line(new THREE.BufferGeometry().setFromPoints([ZP[z.id], lab.position]), new THREE.LineBasicMaterial({ transparent: true, opacity: 0 }));
    brain.add(lead);
    zones[z.id] = { ...z, sp, core, el, lead, bar: el.querySelector("s"), v: 0 };
  }

  // live concept cards
  const concepts = {};
  for (const c of CONCEPTS) {
    const at = new THREE.Vector3(...c.p);
    const node = new THREE.Mesh(new THREE.OctahedronGeometry(.04), new THREE.MeshBasicMaterial({ transparent: true }));
    node.position.copy(at); node.userData = { kind: "concept", id: c.id }; brain.add(node);
    const el = document.createElement("div"); el.className = "b3-card"; el.innerHTML = `<small>${c.lab}</small><span></span>`;
    const lab = new CSS2DObject(el); lab.position.copy(at); lab.center.set(c.p[0] < 0 ? 1.05 : -.05, .5); brain.add(lab);
    let line = null;
    if (c.zone) { line = new THREE.Line(new THREE.BufferGeometry().setFromPoints([ZP[c.zone], at]), new THREE.LineBasicMaterial({ transparent: true, opacity: .35 })); brain.add(line); }
    concepts[c.id] = { ...c, at, node, el, val: el.querySelector("span"), line, text: "" };
  }

  // memory items: along the medial temporal arc, deeper (toward the midline) the more trust they need
  let mem = [], memKey = "";
  const memGroup = new THREE.Group(); brain.add(memGroup);
  function buildMemory(items) {
    memGroup.clear(); mem = [];
    const sorted = items.slice().sort((a, b) => a.trust_min - b.trust_min), n = Math.max(1, sorted.length);
    sorted.forEach((m, i) => {
      const a = (i + .5) / n, depth = clamp(m.trust_min / 80), row = i % 3;  // three staggered rows along the limbic arc
      const at = new THREE.Vector3(-.8 + 1.7 * a, -.5 + .3 * row + .25 * Math.sin(a * Math.PI), 1.02 - .65 * depth);
      const node = new THREE.Mesh(new THREE.SphereGeometry(.022, 18, 12), new THREE.MeshBasicMaterial({ transparent: true }));
      node.position.copy(at); node.userData = { kind: "memory", id: m.id }; memGroup.add(node);
      const halo = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }));
      halo.position.copy(at); memGroup.add(halo);
      const tether = new THREE.Line(new THREE.BufferGeometry().setFromPoints([ZP.hip, at]), new THREE.LineBasicMaterial({ transparent: true, opacity: .14 }));
      memGroup.add(tether);
      const el = document.createElement("div"); el.className = "b3-mem";
      el.innerHTML = `<i></i><span>${esc(cut(m.label || m.id, 34))}</span><em>${m.trust_min}</em>`;
      const lab = new CSS2DObject(el); lab.position.copy(at); lab.center.set(-.06, .5); memGroup.add(lab);
      mem.push({ m, at, node, halo, tether, el, cls: "" });
    });
  }

  // the thought path of the current turn: heard -> recalled memories -> behaviour -> says (locked hits route to the amygdala)
  const pathGroup = new THREE.Group(); brain.add(pathGroup);
  let pathKey = "", paths = [];
  const pulseGeo = new THREE.SphereGeometry(.022, 12, 8);
  function curve(a, b, lift = .25) {
    const mid = a.clone().add(b).multiplyScalar(.5); mid.z += lift; mid.y += lift * .4;
    return new THREE.QuadraticBezierCurve3(a.clone(), mid, b.clone());
  }
  function buildPath(snap) {
    pathGroup.clear(); paths = [];
    if (!snap) return;
    const at = (id) => mem.find((x) => x.m.id === id)?.at;
    const segs = [];
    const rec = (snap.recalled || []).map(at).filter(Boolean), locked = (snap.locked_hit || []).map(at).filter(Boolean);
    for (const p of rec) segs.push([concepts.heard.at, p, "--mem", 0], [p, concepts.behaviour.at, "--pfc", .35]);
    if (!rec.length) segs.push([concepts.heard.at, concepts.behaviour.at, "--pfc", 0]);
    for (const p of locked) segs.push([concepts.heard.at, p, "--red", 0], [p, concepts.reaction.at, "--red", .35]);
    segs.push([concepts.behaviour.at, concepts.says.at, "--lang", .7]);
    for (const [a, b, c, delay] of segs) {
      const cv = curve(a, b), col = new THREE.Color(css(c) || "#fff");
      const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints(cv.getPoints(40)), new THREE.LineBasicMaterial({ color: col, transparent: true, opacity: 0 }));
      const pulse = new THREE.Mesh(pulseGeo, new THREE.MeshBasicMaterial({ color: col, transparent: true, opacity: 0 }));
      pathGroup.add(line, pulse); paths.push({ cv, line, pulse, delay });
    }
  }

  // ---------- theme ----------
  function theme() {
    const L = light();
    glass.uniforms.fill.value.set(css("--brain-fill0") || "#18222e"); glass.uniforms.edge.value.set(css("--brain-edge") || "#3a4a5c");
    glass.uniforms.base.value = L ? .08 : .07; glass.uniforms.rim.value = L ? .8 : 1;
    glass.uniforms.edge.value.set(css(L ? "--brain-edge" : "--muted") || "#8593a3");
    dotsMat.color.set(css("--brain-edge") || "#3a4a5c");
    const blend = L ? THREE.NormalBlending : THREE.AdditiveBlending;
    for (const z of Object.values(zones)) { const c = new THREE.Color(css(z.c) || "#fff"); z.color = c; z.sp.material.color.copy(c); z.sp.material.blending = blend; z.core.material.color.copy(c); z.el.style.setProperty("--c", `var(${z.c})`); }
    for (const c of Object.values(concepts)) { const zc = c.zone ? zones[c.zone].c : "--trust"; c.node.material.color.set(css(zc) || "#fff"); if (c.line) c.line.material.color.set(css(zc) || "#fff"); c.el.style.setProperty("--c", `var(${zc})`); }
    for (const x of mem) { x.halo.material.blending = blend; x.tether.material.color.set(css("--mem")); }
    pathKey = "";
  }
  matchMedia("(prefers-color-scheme: light)").addEventListener("change", theme);

  // ---------- HUD ----------
  const nav = host.querySelector(".b3-zones");
  nav.innerHTML = ZONES.map((z) => `<button type="button" data-zone="${z.id}" style="--c:var(${z.c})"><i></i><span><b>${z.name}</b><small>${z.sub}</small></span><em><s></s></em></button>`).join("");
  const navBars = Object.fromEntries(ZONES.map((z) => [z.id, nav.querySelector(`[data-zone="${z.id}"] s`)]));
  if (M && !REDUCED) M.animate(nav.querySelectorAll("button"), { opacity: [0, 1], x: [-12, 0] }, { delay: M.stagger(.04), type: "spring", stiffness: 260, damping: 24 });

  const tools = host.querySelector(".b3-tools"), lodEl = host.querySelector(".b3-lod");
  const fly = (to, target = new THREE.Vector3()) => {
    const from = camera.position.clone(), t0 = controls.target.clone();
    if (!M || REDUCED) { camera.position.copy(to); controls.target.copy(target); return; }
    M.animate(0, 1, { type: "spring", stiffness: 70, damping: 18, onUpdate: (k) => { camera.position.lerpVectors(from, to, k); controls.target.lerpVectors(t0, target, k); } });
  };
  const flyZone = (id) => { const p = ZP[id].clone(); fly(p.clone().add(new THREE.Vector3(.2, .25, 2.2)), p); };
  nav.addEventListener("click", (e) => { const b = e.target.closest("[data-zone]"); if (b) { flyZone(b.dataset.zone); showDetail({ kind: "zone", id: b.dataset.zone }); } });
  tools.addEventListener("click", (e) => {
    const b = e.target.closest("button"); if (!b) return;
    const act = b.dataset.act;
    if (act === "reset") fly(HOME);
    if (act === "rotate") { controls.autoRotate = !controls.autoRotate; b.setAttribute("aria-pressed", controls.autoRotate); }
    if (act === "flat") setMode(false);
    if (act === "expand") {
      const on = !card.classList.contains("b3-expanded"); card.classList.toggle("b3-expanded", on); b.setAttribute("aria-pressed", on); b.textContent = on ? "Close" : "Expand";
      if (M && !REDUCED) M.animate(card, { opacity: [.4, 1], scale: [on ? .97 : 1.02, 1] }, { type: "spring", stiffness: 300, damping: 28 });
      resize();
    }
  });
  addEventListener("keydown", (e) => { if (e.key === "Escape") { if (!detail.hidden) hideDetail(); else if (card.classList.contains("b3-expanded")) tools.querySelector('[data-act="expand"]').click(); } });

  // ---------- details ----------
  const detail = host.querySelector(".b3-detail"), dBody = detail.querySelector(".b3-body");
  let sel = null, last = null;
  detail.querySelector(".b3-x").onclick = () => hideDetail();
  function hideDetail() {
    sel = null;
    if (M && !REDUCED) M.animate(detail, { opacity: 0, y: 8 }, { duration: .14 }).then(() => { detail.hidden = true; });
    else detail.hidden = true;
  }
  function showDetail(s) {
    const was = detail.hidden; sel = s; detail.hidden = false; fillDetail();
    if (M && !REDUCED && was) M.animate(detail, { opacity: [0, 1], y: [12, 0], scale: [.98, 1] }, { type: "spring", stiffness: 380, damping: 30 });
  }
  function fillDetail() {
    if (!sel || !last) return;
    const { snap, S } = last;
    let h = "";
    if (sel.kind === "memory") {
      const x = mem.find((y) => y.m.id === sel.id); if (!x) return;
      const m = x.m, st = { told: "Told the doctor", open: "Open: will share if asked", gated: "Open: needs the right question", locked: "Locked: needs more trust" }[x.cls];
      h = `<small>Memory · hippocampus</small><h3>${esc(m.label || m.id)}</h3><p class="b3-st b3-${x.cls}">${st}</p>
        <dl><dt>Trust needed</dt><dd>${m.trust_min}</dd><dt>Trust now</dt><dd>${Math.round(S.trust)}</dd><dt>Recalled</dt><dd>${m.recalls.filter((r) => r <= last.t).length}×</dd><dt>Locked hits</dt><dd>${m.lockedHits.filter((r) => r <= last.t).length}×</dd></dl>`;
    } else if (sel.kind === "zone") {
      const z = zones[sel.id];
      h = `<small>Zone</small><h3>${z.name}</h3><p>${z.sub}</p><div class="b3-meter" style="--c:var(${z.c})"><s style="width:${Math.round(z.v * 100)}%"></s></div><p class="dim">Activity ${Math.round(z.v * 100)}%</p>`;
    } else {
      const c = concepts[sel.id];
      h = `<small>${c.zone ? zones[c.zone].name : "Whole brain"}</small><h3>${c.lab}</h3><p>${esc(c.full || c.text || "—")}</p>${snap?.why && /behaviour|resistance|reaction/.test(c.id) ? `<p class="dim">${esc(snap.why)}</p>` : ""}`;
    }
    if (dBody.dataset.h !== h) { dBody.innerHTML = h; dBody.dataset.h = h; }
  }

  // ---------- picking ----------
  const ray = new THREE.Raycaster(), ptr = new THREE.Vector2();
  const pickables = () => [...Object.values(zones).map((z) => z.core), ...Object.values(concepts).map((c) => c.node), ...mem.map((x) => x.node)];
  const hit = (e) => {
    const b = renderer.domElement.getBoundingClientRect();
    ptr.set(((e.clientX - b.left) / b.width) * 2 - 1, -((e.clientY - b.top) / b.height) * 2 + 1);
    ray.setFromCamera(ptr, camera); ray.params.Points = { threshold: 0 };
    return ray.intersectObjects(pickables(), false)[0]?.object.userData;
  };
  let down = null;
  labels.domElement.addEventListener("pointerdown", (e) => { down = [e.clientX, e.clientY]; });
  labels.domElement.addEventListener("pointermove", (e) => { labels.domElement.style.cursor = hit(e) ? "pointer" : "grab"; });
  labels.domElement.addEventListener("pointerup", (e) => {
    if (!down || Math.hypot(e.clientX - down[0], e.clientY - down[1]) > 5) return;  // a drag turns the brain, a click picks
    const u = hit(e); if (u) showDetail(u); else if (!detail.hidden) hideDetail();
  });

  // ---------- size, mode ----------
  function resize() {
    const w = stage.clientWidth, h = stage.clientHeight; if (!w || !h) return;
    renderer.setSize(w, h, false); labels.setSize(w, h); camera.aspect = w / h; camera.updateProjectionMatrix();
  }
  new ResizeObserver(resize).observe(stage);
  function setMode(on) {
    card.classList.toggle("b3-on", on);
    if (on) { resize(); if (M && !REDUCED) M.animate(stage, { opacity: [0, 1], scale: [.96, 1] }, { type: "spring", stiffness: 200, damping: 26 }); }
    try { localStorage.setItem("twin3d", on ? "1" : "0"); } catch (_) { /* storage blocked */ }
  }
  const flatBtn = document.createElement("button"); flatBtn.type = "button"; flatBtn.className = "b3-to3d"; flatBtn.textContent = "3D view"; flatBtn.onclick = () => setMode(true);
  card.appendChild(flatBtn);
  let on = true; try { on = localStorage.getItem("twin3d") !== "0"; } catch (_) { /* storage blocked */ }
  setMode(on); theme();

  // ---------- frame(t) ----------
  let lod = -1;
  function frame(t, ctx) {
    last = { ...ctx, t };
    if (!card.classList.contains("b3-on")) return;
    const { Z, snap, S, mood, items } = ctx;
    const key = items.map((m) => m.id).join("|");
    if (key !== memKey) { memKey = key; buildMemory(items); theme(); }
    const pk = (snap ? snap.t : "") + (light() ? "L" : "D");
    if (pk !== pathKey) { pathKey = pk; buildPath(snap); }

    const d = camera.position.distanceTo(controls.target), k = clamp(d / 4.6, .35, 1.4);  // nodes keep a steady size on screen
    // zones
    const vals = { pfc: Z.pfc, broca: Z.broca, wern: Z.wern, ins: Z.ins, amy: Z.amy, hip: Math.max(Z.hip, Z.hipRed), stem: Z.stem };
    for (const z of Object.values(zones)) {
      const v = clamp(vals[z.id]); z.v = v;
      if (z.id === "hip") z.sp.material.color.copy(Z.hipRed > Z.hip ? new THREE.Color(css("--red")) : z.color);
      z.sp.material.opacity = .08 + .92 * v; z.sp.scale.setScalar(z.r * 2 * (.7 + .9 * v));
      z.core.material.opacity = .35 + .65 * v; z.core.scale.setScalar((.8 + .9 * v) * k);
      z.bar.style.width = navBars[z.id].style.width = (v * 100).toFixed(1) + "%";
      z.el.classList.toggle("hot", v > .45); z.lead.material.color.copy(z.color); z.lead.material.opacity = lod === 2 ? .45 : 0;
    }

    // concept cards
    const cues = (snap?.cues || []).map((c) => human(c.id));
    const vals2 = {
      heard: snap?.doctor || ctx.turn?.doctor || "—", reaction: snap ? `${human(snap.reaction)} · ${snap.intensity ?? 0}/10` : "—",
      behaviour: human(snap?.behaviour) || "—", resistance: human(snap?.resistance) || "—", says: snap?.utterance || "—",
      body: cues.join(", ") || "resting", arousal: `agitation ${Math.round(S.agitation)} · distress ${Math.round(S.distress)}`,
      mood: `P ${mood.p.toFixed(2)} · A ${mood.a.toFixed(2)} · D ${mood.d.toFixed(2)}`,
    };
    const act = { heard: Z.wern, reaction: Z.amy, behaviour: Z.pfc, resistance: Z.pfc, says: Z.broca, body: Z.ins, arousal: Z.stem, mood: .6 };
    for (const c of Object.values(concepts)) {
      c.full = vals2[c.id]; const s = cut(c.full, c.id === "says" || c.id === "heard" ? 52 : 34);
      if (s !== c.text) { c.text = s; c.val.textContent = s; if (M && !REDUCED && t > .5) M.animate(c.el, { scale: [1.06, 1] }, { type: "spring", stiffness: 500, damping: 20 }); }
      const a = clamp(act[c.id]); c.node.material.opacity = .4 + .6 * a; c.node.rotation.y = t * .8; c.node.scale.setScalar((.8 + .6 * a) * k);
      c.el.style.setProperty("--a", a.toFixed(3)); if (c.line) c.line.material.opacity = .15 + .4 * a;
    }

    // memory nodes
    for (const x of mem) {
      const m = x.m;
      if (m.cls !== x.cls) { x.cls = m.cls || "locked"; x.el.className = "b3-mem b3-" + x.cls; x.el.querySelector("i").innerHTML = x.cls === "locked" ? SVG_LOCK : ""; }
      const col = css(x.cls === "locked" ? "--faint" : x.cls === "gated" ? "--agit" : "--mem");
      const f = m.f || 0, u = m.u || 0, r = m.r || 0;
      x.node.material.color.set(r > .05 ? css("--red") : col);
      x.node.scale.setScalar((x.cls === "told" ? 1.3 : 1) * (1 + .6 * Math.max(f, u, r)) * k);
      x.node.material.opacity = x.cls === "locked" ? .55 + .45 * r : 1;
      x.halo.material.color.set(r > f ? css("--red") : col);
      x.halo.material.opacity = Math.max(f, u, r) * .9 + (x.cls === "told" ? .18 : 0);
      x.halo.scale.setScalar((.08 + .22 * Math.max(f, u, r)) * k);
      x.tether.material.opacity = .08 + .5 * f;
      x.el.style.setProperty("--f", Math.max(f, u, r).toFixed(3));
    }

    // thought path: lines draw in, then pulses travel along them
    const since = snap ? t - snap.t : 1e9, fade = clamp(1 - (since - 6) / 2);
    for (const p of paths) {
      const kk = clamp((since - p.delay) / .6);
      p.line.material.opacity = .75 * kk * fade;
      const s = REDUCED ? 1 : ((since - p.delay) * .7) % 1;
      p.pulse.position.copy(p.cv.getPoint(clamp(s))); p.pulse.material.opacity = kk * fade;
    }

    // level of detail by distance
    const L = LOD.findIndex((l) => d < l.max);
    if (L !== lod) { lod = L; host.dataset.lod = LOD[L].name.toLowerCase(); lodEl.textContent = LOD[L].name; if (M && !REDUCED) M.animate(lodEl, { opacity: [0, 1], y: [-4, 0] }, { duration: .25 }); }

    fillDetail();
    controls.update();
    renderer.render(scene, camera); labels.render(scene, camera);
  }
  return { frame };
}

const card = document.querySelector(".card.brain");
if (card && new URLSearchParams(location.search).get("render") !== "1") {  // video render mode keeps the deterministic 2D map
  const api = create(card);
  if (api) window.twin3d = api;
}
