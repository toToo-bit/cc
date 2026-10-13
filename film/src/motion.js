// Masterclass Compound Capital — version motion design 2D (« Le Trait »).
//
// Un monde papier : chaque idee est dessinee a l'encre, au rythme de la voix.
// Le film est une fonction pure du temps (renderAt(t)), comme la version 3D :
// meme harnais de rendu, mais ~15x plus rapide a calculer.

const Q = new URLSearchParams(location.search);
const W = 1080, H = 1920;
const FPS = +(Q.get("fps") || 30);
const VARIANT = Q.get("v") || "ig";          // ig = « Commente Capital », tt = lien en description

// garde-fou : les effets de rebond peuvent donner un rayon de -1e-14,
// que le canvas refuse en levant une exception (rendu interrompu)
{
  const P = CanvasRenderingContext2D.prototype, arc = P.arc, ell = P.ellipse;
  P.arc = function (x, y, r, ...rest) { return arc.call(this, x, y, Math.max(0, r), ...rest); };
  P.ellipse = function (x, y, rx, ry, ...rest) { return ell.call(this, x, y, Math.max(0, rx), Math.max(0, ry), ...rest); };
}
const cv = document.getElementById("stage");
cv.width = W; cv.height = H;
const ctx = cv.getContext("2d", { willReadFrequently: true });

// --- charte ----------------------------------------------------------------
const PAPER = "#F3EEE6", PAPER2 = "#EAE3D8", INK = "#14161A", GREY = "#8E877E",
      RULE = "#CEC6BA", RED = "#7A2C25", GOLD = "#A8812E", GOLD2 = "#C9A24E", NIGHT = "#121317";
const SERIF = '"Instrument Serif", serif', SANS = '"Inter", sans-serif';

// --- outils de temps -------------------------------------------------------
const cl = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const lerp = (a, b, k) => a + (b - a) * k;
const eo = (x) => 1 - Math.pow(1 - cl(x), 3);
const eio = (x) => { x = cl(x); return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2; };
const back = (x) => { x = cl(x); const c1 = 1.7, c3 = c1 + 1; return 1 + c3 * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2); };
const pr = (t, a, d) => cl((t - a) / d);

function rng(seed) {
  let s = seed >>> 0;
  return () => {
    s = (s + 0x6D2B79F5) >>> 0;
    let x = s;
    x = Math.imul(x ^ (x >>> 15), x | 1);
    x ^= x + Math.imul(x ^ (x >>> 7), x | 61);
    return ((x ^ (x >>> 14)) >>> 0) / 4294967296;
  };
}

// --- voix : phrases calees --------------------------------------------------
const DATA = await (await fetch(`/src/beats_${VARIANT}.json`)).json();
const BEATS = DATA.beats;
const DUR = DATA.duration;
const norm = (w) => w.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^a-z0-9'’-]/g, "");
const S = (i) => BEATS[i].start;
const E = (i) => BEATS[i].end;
/** instant ou le mot `w` est prononce dans la phrase i */
function T(i, w) {
  const n = norm(w);
  const hit = BEATS[i].words.find((x) => norm(x.w).startsWith(n));
  return hit ? hit.s : S(i);
}

// l'appel a l'action n'a pas de mots Scribe : on les cale sur ses pauses
{
  const cta = BEATS.find((b) => b.text === "CTA");
  const c0 = cta.start;
  const parts = VARIANT === "ig"
    ? [["L'historique", 0.0], ["et", 0.55], ["la", 0.75], ["FAQ", 0.95], ["t'attendent", 1.6], ["sur", 2.4], ["notre", 2.6], ["Telegram.", 2.9],
       ["Commente", 3.92], ["«\u202fCapital\u202f»", 4.3], ["et", 5.32], ["je", 5.45], ["t'envoie", 5.55], ["le", 5.8], ["lien.", 5.9]]
    : [["L'historique", 0.0], ["et", 0.55], ["la", 0.75], ["FAQ", 0.95], ["t'attendent", 1.6], ["sur", 2.4], ["notre", 2.6], ["Telegram.", 2.9],
       ["Lien", 3.88], ["en", 4.1], ["description.", 4.25]];
  cta.words = parts.map(([w, o]) => ({ w, s: c0 + o, e: c0 + o + 0.3 }));
}

// --- titres : groupes de phrases et mots en valeur ---------------------------
const GROUPS = [[0, 1], [2], [3, 4, 5], [6, 7], [8], [9, 10], [11], [12], [13, 14], [15], [16], [17], [18], [19], [20], [21],
  [22, 23], [24, 25], [26], [27], [28], [29], [30], [31], [32], [33], [34], [35], [36, 37], [38], [39], [40], [41], [42, 43],
  [44], [45], [46], [47, 48], [49, 50], [51], [52, 53], [54], [55, 56, 57], [58, 59], [60], [61, 62]];

// mot -> style : "i" italique, "r" bordeaux, "g" or
const EMPH = {
  0: { perdre: "i", de: "i", "l'argent": "i" }, 1: { expres: "ir" }, 2: { survivre: "i" },
  3: { danger: "i" }, 4: { groupe: "i" }, 5: { vite: "i" }, 6: { savane: "i" }, 7: { catastrophique: "ir" },
  9: { acheter: "i" }, 10: { haut: "ir" }, 11: { trop: "ir", longtemps: "ir" }, 12: { trop: "ir", tot: "ir" },
  13: { mises: "i" }, 14: { perds: "ir", plus: "ir" }, 15: { journee: "i" }, 16: { centaines: "i" }, 17: { epuise: "ir" },
  18: { trader: "i" }, 19: { meilleurs: "i" }, 20: { intelligents: "i" }, 21: { cerveau: "i" }, 22: { avant: "ig" },
  23: { froid: "i" }, 24: { "l'avance": "i" }, 25: { attend: "i" }, 26: { limite: "ir", perte: "ir" }, 27: { pros: "i" },
  28: { compound: "g", capital: "g" }, 29: { "l'euro-dollar": "i" }, 30: { seul: "i" }, 31: { chiffres: "i" }, 32: { emotion: "i" },
  33: { rien: "i", faire: "i" }, 35: { ton: "i", nom: "i" }, 36: { capital: "i" }, 37: { "l'acces": "i" }, 38: { automatiquement: "i" },
  39: { jamais: "i" }, 40: { arreter: "i" }, 42: { gains: "ig" }, 43: { commission: "i" }, 44: { progresse: "ig" },
  45: { promesse: "i" }, 46: { reel: "i", verifiable: "i" }, 48: { comprendre: "i" }, 49: { compris: "i" }, 50: { presses: "ir" },
  51: { imagine: "i" }, 53: { telephone: "i" }, 54: { regles: "ig" }, 55: { stress: "i" }, 56: { ecran: "i" }, 57: { toi: "ig" },
  58: { travail: "i" }, 59: { discipline: "ig" }, 60: { "capital": "ig", "«capital»": "ig", lien: "i", description: "i" }, 61: { compound: "g", capital: "g" },
  62: { decider: "i" },
};

function groupAt(t) {
  let g = GROUPS[0];
  for (const gr of GROUPS) if (t >= S(gr[0]) - 0.12) g = gr;
  return g;
}

// --- dessin : texte cinetique ---------------------------------------------
function wordFont(style, size) {
  return `${style.includes("i") ? "italic " : ""}${size}px ${SERIF}`;
}

function drawHeadline(t, dark) {
  const g = groupAt(t);
  const words = [];
  for (const bi of g) {
    for (const w of BEATS[bi].words) {
      const st = (EMPH[bi] || {})[norm(w.w)] || "";
      words.push({ ...w, st, first: bi === 0 });
    }
  }
  if (!words.length) return;

  // taille : la plus grande qui tient en 4 lignes
  const maxW = W - 2 * 92;
  let size = 104, lines;
  for (; size >= 58; size -= 4) {
    lines = [[]];
    let x = 0;
    for (const w of words) {
      ctx.font = wordFont(w.st, size);
      const ww = ctx.measureText(w.w).width, sp = size * 0.26;
      if (x > 0 && x + ww > maxW) { lines.push([]); x = 0; }
      lines[lines.length - 1].push({ ...w, x, ww });
      x += ww + sp;
    }
    if (lines.length <= 4) break;
  }

  const lh = size * 1.08;
  let y = 300;
  ctx.textBaseline = "alphabetic";
  for (const line of lines) {
    for (const w of line) {
      // le titre d'accroche est present des l'image 0 (c'est la miniature)
      const k = w.first ? 1 : eo((t - (w.s - 0.06)) / 0.32);
      if (k <= 0) continue;
      ctx.save();
      ctx.globalAlpha = k;
      ctx.font = wordFont(w.st, size);
      ctx.fillStyle = w.st.includes("r") ? (dark ? "#D3826F" : RED) : w.st.includes("g") ? (dark ? GOLD2 : GOLD) : (dark ? PAPER : INK);
      ctx.fillText(w.w, 92 + w.x, y + (1 - k) * size * 0.35);
      ctx.restore();
    }
    y += lh;
  }
}

// --- dessin : traits ---------------------------------------------------------
/** trace un trait jusqu'a la fraction p de sa longueur ; renvoie la pointe */
function line(pts, p = 1, { w = 6, c = INK, dash = null, nib = true } = {}) {
  if (p <= 0 || pts.length < 2) return null;
  let tot = 0;
  const L = [0];
  for (let i = 1; i < pts.length; i++) { tot += Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]); L.push(tot); }
  const lim = tot * cl(p);
  ctx.save();
  ctx.strokeStyle = c; ctx.lineWidth = w; ctx.lineCap = "round"; ctx.lineJoin = "round";
  if (dash) ctx.setLineDash(dash);
  ctx.beginPath();
  ctx.moveTo(pts[0][0], pts[0][1]);
  let tip = pts[0];
  for (let i = 1; i < pts.length; i++) {
    if (L[i] <= lim) { ctx.lineTo(pts[i][0], pts[i][1]); tip = pts[i]; }
    else {
      const f = (lim - L[i - 1]) / (L[i] - L[i - 1]);
      tip = [lerp(pts[i - 1][0], pts[i][0], f), lerp(pts[i - 1][1], pts[i][1], f)];
      ctx.lineTo(tip[0], tip[1]);
      break;
    }
  }
  ctx.stroke();
  // la pointe de la plume, tant que le trait se dessine
  if (nib && p < 1) { ctx.fillStyle = c; ctx.beginPath(); ctx.arc(tip[0], tip[1], w * 0.95, 0, 7); ctx.fill(); }
  ctx.restore();
  return tip;
}

function resample(pts, n) {
  let tot = 0; const L = [0];
  for (let i = 1; i < pts.length; i++) { tot += Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]); L.push(tot); }
  const out = []; let j = 1;
  for (let k = 0; k < n; k++) {
    const d = (tot * k) / (n - 1);
    while (j < L.length - 1 && L[j] < d) j++;
    const f = (d - L[j - 1]) / Math.max(1e-6, L[j] - L[j - 1]);
    out.push([lerp(pts[j - 1][0], pts[j][0], f), lerp(pts[j - 1][1], pts[j][1], f)]);
  }
  return out;
}
const morph = (a, b, k) => a.map((p, i) => [lerp(p[0], b[i][0], k), lerp(p[1], b[i][1], k)]);

function text(s, x, y, { size = 34, font = SANS, weight = 600, c = INK, align = "center", italic = false, a = 1, track = 0 } = {}) {
  if (a <= 0) return;
  ctx.save();
  ctx.globalAlpha *= a;
  ctx.font = `${italic ? "italic " : ""}${font === SANS ? weight + " " : ""}${size}px ${font}`;
  ctx.fillStyle = c; ctx.textAlign = align; ctx.textBaseline = "middle";
  if (track) ctx.letterSpacing = `${track}px`;
  ctx.fillText(s, x, y);
  ctx.restore();
}

function rrect(x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath();
}

function card(x, y, w, h, { fill = PAPER, stroke = INK, lw = 4, r = 22, a = 1, shadow = true } = {}) {
  if (a <= 0) return;
  ctx.save(); ctx.globalAlpha *= a;
  if (shadow) { ctx.fillStyle = "rgba(20,22,26,0.10)"; rrect(x + 8, y + 10, w, h, r); ctx.fill(); }
  ctx.fillStyle = fill; rrect(x, y, w, h, r); ctx.fill();
  if (stroke) { ctx.strokeStyle = stroke; ctx.lineWidth = lw; rrect(x, y, w, h, r); ctx.stroke(); }
  ctx.restore();
}

function pill(s, x, y, { fill = INK, c = PAPER, size = 30, a = 1, k = 1 } = {}) {
  if (a <= 0 || k <= 0) return;
  ctx.save(); ctx.globalAlpha *= a;
  ctx.font = `700 ${size}px ${SANS}`; ctx.letterSpacing = "2px";
  const w = ctx.measureText(s).width + size * 1.4, h = size * 1.9;
  ctx.translate(x, y); ctx.scale(k, k);
  ctx.fillStyle = fill; rrect(-w / 2, -h / 2, w, h, h / 2); ctx.fill();
  ctx.fillStyle = c; ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.fillText(s, 0, 2);
  ctx.restore();
}

/** un pion d'echecs ; x,y = centre de la base */
function pawn(x, y, s = 1, { fill = INK, stroke = INK, ring = false, a = 1, rot = 0 } = {}) {
  if (a <= 0) return;
  ctx.save(); ctx.globalAlpha *= a;
  ctx.translate(x, y); ctx.rotate(rot); ctx.scale(s, s);
  ctx.lineWidth = 4 / s; ctx.strokeStyle = stroke; ctx.fillStyle = fill; ctx.lineJoin = "round";
  ctx.beginPath();
  ctx.moveTo(-36, 0); ctx.lineTo(36, 0); ctx.lineTo(34, -14); ctx.lineTo(22, -18);
  ctx.bezierCurveTo(12, -40, 10, -58, 14, -72); ctx.lineTo(-14, -72);
  ctx.bezierCurveTo(-10, -58, -12, -40, -22, -18); ctx.lineTo(-34, -14); ctx.closePath();
  ctx.fill(); ctx.stroke();
  ctx.beginPath(); ctx.ellipse(0, -74, 24, 7, 0, 0, 7); ctx.fill(); ctx.stroke();
  ctx.beginPath(); ctx.arc(0, -102, 22, 0, 7); ctx.fill(); ctx.stroke();
  if (ring) { ctx.strokeStyle = GOLD; ctx.lineWidth = 7 / s; ctx.beginPath(); ctx.ellipse(0, -74, 25, 8, 0, 0, Math.PI); ctx.stroke(); }
  ctx.restore();
}
const me = (x, y, s = 1, o = {}) => pawn(x, y, s, { fill: PAPER, ring: true, ...o });   // « toi »

function coin(x, y, r = 34, spin = 0, a = 1) {
  if (a <= 0) return;
  ctx.save(); ctx.globalAlpha *= a; ctx.translate(x, y);
  const sx = Math.max(0.12, Math.abs(Math.cos(spin)));
  ctx.scale(sx, 1);
  ctx.fillStyle = GOLD; ctx.beginPath(); ctx.arc(0, 0, r, 0, 7); ctx.fill();
  ctx.fillStyle = GOLD2; ctx.beginPath(); ctx.arc(0, 0, r * 0.78, 0, 7); ctx.fill();
  ctx.strokeStyle = GOLD; ctx.lineWidth = 3; ctx.beginPath(); ctx.arc(0, 0, r * 0.55, 0, 7); ctx.stroke();
  ctx.restore();
}

function check(x, y, s, p, c = GOLD) { line([[x - s, y], [x - s * 0.3, y + s * 0.7], [x + s, y - s * 0.8]], p, { w: s * 0.22, c, nib: false }); }
function cross(x, y, s, p, c = RED) {
  line([[x - s, y - s], [x + s, y + s]], cl(p * 2), { w: s * 0.2, c, nib: false });
  line([[x + s, y - s], [x - s, y + s]], cl(p * 2 - 1), { w: s * 0.2, c, nib: false });
}

// --- formes construites une fois --------------------------------------------
const R0 = rng(7);

// cerveau d'un seul trait : contour lobe + circonvolutions
const BX = 540, BY = 1190;
const BRAIN_OUT = [];
for (let i = 0; i <= 420; i++) {
  const a = (i / 420) * Math.PI * 2 - Math.PI / 2;
  let r = 1 + 0.045 * Math.sin(9 * a) + 0.022 * Math.sin(17 * a + 0.7);
  const x = BX + Math.cos(a) * 330 * r, y = BY + Math.sin(a) * 250 * r * (Math.sin(a) > 0 ? 0.92 : 1);
  BRAIN_OUT.push([x, y]);
}
const GYRI = [];
for (let j = 0; j < 8; j++) {
  const y0 = BY - 175 + j * 50;
  const half = Math.sqrt(Math.max(0, 1 - ((y0 - BY) / 245) ** 2)) * 300;
  for (const side of [-1, 1]) {
    const pts = [];
    for (let k = 0; k <= 60; k++) {
      const u = k / 60, x = BX + side * (22 + u * (half - 50));
      pts.push([x, y0 + 15 * Math.sin(x * 0.042 + j * 1.7) + 8 * Math.sin(x * 0.11 + j * 2.3)]);
    }
    GYRI.push(pts);
  }
}
const FISSURE = Array.from({ length: 40 }, (_, k) => [BX + 5 * Math.sin(k * 0.6), BY - 250 + k * 9]);

// la courbe des pieges : montee, sommet, chute, remontee
const CH = { x0: 120, x1: 960, y0: 1520, y1: 880 };
function trapPrice(u) {
  // u dans [0,1] -> prix dans [0,1]
  const base = u < 0.34 ? eio(u / 0.34) * 0.92
    : u < 0.58 ? 0.92 - eio((u - 0.34) / 0.24) * 0.62
    : 0.30 + eio((u - 0.58) / 0.42) * 0.62;
  return base + 0.025 * Math.sin(u * 61) + 0.015 * Math.sin(u * 137);
}
const TRAP = Array.from({ length: 300 }, (_, k) => {
  const u = k / 299;
  return [lerp(CH.x0, CH.x1, u), lerp(CH.y0, CH.y1, trapPrice(u))];
});

// horizon de la savane, puis le meme trait devenu graphique de prix
const HORIZON = Array.from({ length: 240 }, (_, k) => {
  const x = lerp(40, 1040, k / 239);
  return [x, 1420 - 26 * Math.sin(x * 0.006) - 14 * Math.sin(x * 0.017 + 1)];
});
const MARKET = (() => {
  const r = rng(99); let y = 0; const out = [];
  for (let k = 0; k < 240; k++) { y += (r() - 0.5) * 34; y *= 0.985; out.push([lerp(40, 1040, k / 239), 1260 + y - (k > 150 ? (k - 150) * 3.2 : 0)]); }
  return out;
})();

// un historique reel : monte, avec des creux
const HIST = (() => {
  const r = rng(2026); let v = 0; const out = [];
  for (let k = 0; k < 200; k++) {
    v += 0.42 + (r() - 0.5) * 2.4;
    if (k === 52 || k === 118 || k === 160) v -= 7;
    out.push(v);
  }
  const mn = Math.min(...out), mx = Math.max(...out);
  return out.map((v, k) => [lerp(130, 950, k / 199), lerp(1500, 980, (v - mn) / (mx - mn))]);
})();

// eclats de la capture d'ecran
const SHARDS = (() => {
  const r = rng(5), out = [];
  const cx = 540, cy = 1150, w = 520, h = 380;
  for (let i = 0; i < 18; i++) {
    const a0 = (i / 18) * Math.PI * 2, a1 = ((i + 1) / 18) * Math.PI * 2;
    const p = (a) => [cx + Math.cos(a) * w, cy + Math.sin(a) * h];
    out.push({ pts: [[cx + (r() - 0.5) * 30, cy + (r() - 0.5) * 30], p(a0), p(a1)], vx: (r() - 0.5) * 900, vy: -200 - r() * 500, vr: (r() - 0.5) * 6 });
  }
  return out;
})();

// --- fond -------------------------------------------------------------------
const grain = document.createElement("canvas");
grain.width = grain.height = 512;
{
  const g = grain.getContext("2d"), img = g.createImageData(512, 512), r = rng(11);
  for (let i = 0; i < img.data.length; i += 4) {
    const v = 110 + r() * 145;
    img.data[i] = img.data[i + 1] = img.data[i + 2] = v; img.data[i + 3] = 255;
  }
  g.putImageData(img, 0, 0);
}

function background(dark) {
  ctx.fillStyle = dark ? NIGHT : PAPER;
  ctx.fillRect(0, 0, W, H);
}

function finish(t, dark) {
  // grain anime (decale a chaque image, mais de facon deterministe)
  const f = Math.floor(t * FPS), r = rng(1000 + f);
  ctx.save();
  ctx.globalAlpha = dark ? 0.05 : 0.07;
  ctx.globalCompositeOperation = dark ? "screen" : "multiply";
  const ox = -Math.floor(r() * 512), oy = -Math.floor(r() * 512);
  for (let x = ox; x < W; x += 512) for (let y = oy; y < H; y += 512) ctx.drawImage(grain, x, y);
  ctx.restore();
  // vignette douce
  const g = ctx.createRadialGradient(W / 2, H * 0.48, H * 0.3, W / 2, H * 0.5, H * 0.75);
  g.addColorStop(0, "rgba(0,0,0,0)"); g.addColorStop(1, dark ? "rgba(0,0,0,0.45)" : "rgba(60,45,30,0.16)");
  ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
}

// --- en-tete : marque, chapitre, progression ---------------------------------
const CHAPTERS = [
  [0, "Ton cerveau"], [S(15) - 0.3, "Ta journée"], [S(19) - 0.3, "La méthode"], [S(27) - 0.3, "Compound Capital"],
  [S(34) - 0.3, "Concrètement"], [S(45) - 0.3, "La preuve"], [S(51) - 0.3, "Imagine"],
];
function header(t, dark) {
  let ci = 0;
  CHAPTERS.forEach((c, i) => { if (t >= c[0]) ci = i; });
  const fg = dark ? PAPER : INK, sub = dark ? "#8C8880" : GREY;
  text("COMPOUND CAPITAL", 92, 118, { size: 24, weight: 700, c: fg, align: "left", track: 3 });
  text(`${String(ci + 1).padStart(2, "0")} · ${CHAPTERS[ci][1].toUpperCase()}`, W - 92, 118, { size: 24, weight: 600, c: sub, align: "right", track: 2 });
  ctx.fillStyle = dark ? "#34353a" : RULE; ctx.fillRect(92, 150, W - 184, 2);
  ctx.fillStyle = dark ? GOLD2 : GOLD; ctx.fillRect(92, 149, (W - 184) * cl(t / DUR), 4);
}

// ============================================================================
// SCENES — chacune dessine la zone d'illustration (y 760 → 1700)
// ============================================================================
const SC = [];
const scene = (from, draw, opts = {}) => SC.push({ from, draw, ...opts });

// 1 · le cerveau, d'un seul trait ------------------------------------------
scene(0, (t) => {
  const p = 1;   // contour complet des l'image 0 (miniature) ; les sillons se dessinent
  const burn = pr(t, T(1, "expres") - 0.1, 0.5);
  const c = burn > 0 ? RED : INK;
  line(BRAIN_OUT, p, { w: 7 });
  line(FISSURE, 1, { w: 6, c });
  GYRI.forEach((g, i) => line(g, 0.3 + 0.7 * eio(pr(t, 0.05 + (i % 8) * 0.09, 0.9)), { w: 5, c: burn > (i % 4) / 4 ? RED : INK }));
  // l'argent qui s'echappe
  for (let i = 0; i < 9; i++) {
    const t0 = 0.4 + i * 0.32, k = t - t0;
    if (k < 0) continue;
    coin(BX - 200 + i * 52, BY + 230 + k * k * 520, 30, k * 5 + i, 1 - pr(k, 1.2, 0.4));
  }
});

// 2 · la savane ------------------------------------------------------------
scene(2, (t, g) => {
  const t0 = S(2);
  const toMarket = eio(pr(g, S(7) - 0.1, 0.9));
  const pts = morph(HORIZON, MARKET, toMarket);
  // soleil d'aube, puis couchant
  const sunY = lerp(1440, 980, eo(pr(g, t0, 3))) + lerp(0, 380, eio(pr(g, S(6), 1.8)));
  ctx.save(); ctx.beginPath(); ctx.rect(0, 700, W, 720 - 0); ctx.clip();
  ctx.fillStyle = GOLD2; ctx.globalAlpha = 0.85 * (1 - toMarket); ctx.beginPath(); ctx.arc(760, sunY, 90, 0, 7); ctx.fill();
  ctx.restore();
  line(pts, eio(pr(g, t0, 1.2)), { w: 7, c: toMarket > 0.5 ? RED : INK });
  // herbes
  for (let i = 0; i < 26; i++) {
    const x = 70 + i * 38, base = HORIZON[Math.round((x - 40) / 1000 * 239)][1];
    const h = 22 + (i * 37 % 19);
    line([[x, base], [x - 6, base - h]], pr(g, t0 + 0.6 + i * 0.03, 0.3) * (1 - toMarket), { w: 4, nib: false });
  }
  // les pions
  const fuir = eo(pr(g, S(3), 0.6)), groupe = eo(pr(g, S(4), 0.6)), vite = pr(g, S(5), 0.5);
  const a = 1 - toMarket;
  if (a > 0) {
    const shake = vite > 0 && vite < 1 ? Math.sin(g * 90) * 6 : 0;
    me(540 - fuir * 160 - groupe * 60 + shake, 1408, 1, { a });
    for (let i = 0; i < 4; i++) pawn(700 - i * 90 - groupe * (140 + i * 10) + shake, 1408, 0.85, { a: a * groupe });
    // le danger : deux yeux dans les herbes
    const eyes = pr(g, S(3) - 0.2, 0.3) * (1 - pr(g, S(4), 0.3));
    ctx.fillStyle = GOLD; ctx.globalAlpha = eyes;
    for (const ex of [880, 920]) { ctx.beginPath(); ctx.ellipse(ex, 1370, 12, 7, 0, 0, 7); ctx.fill(); }
    ctx.globalAlpha = 1;
    // agir vite : lignes de vitesse
    for (let i = 0; i < 5; i++) line([[620 + i * 30, 1250 + i * 32], [760 + i * 30, 1250 + i * 32]], vite * (1 - pr(g, S(5) + 0.6, 0.3)), { w: 4, nib: false });
  }
  // verdict
  check(870, 900, 46, eo(pr(g, T(6, "savane"), 0.4)) * (1 - toMarket));
  cross(870, 900, 46, eo(pr(g, T(7, "catastrophique"), 0.4)));
});

// 3 · les pieges -------------------------------------------------------------
scene(8, (t, g) => {
  const at = (u) => TRAP[Math.round(cl(u) * 299)];
  // axes
  line([[CH.x0, CH.y1 - 40], [CH.x0, CH.y0 + 20], [CH.x1 + 20, CH.y0 + 20]], eo(pr(g, S(8), 0.6)), { w: 3, c: GREY, nib: false });
  // la courbe se trace avec l'histoire
  const u = g < S(11) ? 0.34 * eio(pr(g, S(9), E(10) - S(9)))
    : g < S(12) ? 0.34 + 0.24 * eio(pr(g, S(11), 2.6))
    : 0.58 + 0.42 * eio(pr(g, S(12), 2.4));
  line(TRAP, u, { w: 7 });
  // toi, pousse par la foule jusqu'au sommet
  const up = eio(pr(g, S(9), E(10) - S(9)));
  const exitU = 0.58 + 0.42 * 0.18;            // revente trop tot
  let uMe = u < 0.58 ? u : Math.min(u, exitU);
  const p = at(uMe);
  const jump = pr(g, T(12, "revends"), 0.5);
  me(p[0], p[1] - 4 - Math.sin(jump * Math.PI) * 90, 0.9, { a: 1 - pr(g, S(13) - 0.2, 0.3) });
  for (let i = 0; i < 4; i++) {
    const q = at(Math.max(0, up * 0.34 - 0.05 - i * 0.03));
    pawn(q[0] - 30, q[1], 0.75, { a: (1 - pr(g, S(11), 0.4)) * pr(g, S(9) + i * 0.1, 0.3) });
  }
  // ACHAT au sommet
  const top = at(0.34);
  pill("ACHAT", top[0], top[1] - 190, { fill: INK, k: back(pr(g, T(10, "haut"), 0.4)), a: 1 - pr(g, S(13) - 0.2, 0.3) });
  // la perte gardee trop longtemps
  const lossA = pr(g, S(11), 0.5) * (1 - pr(g, S(13) - 0.2, 0.3));
  if (lossA > 0) {
    ctx.save(); ctx.globalAlpha = 0.18 * lossA; ctx.fillStyle = RED;
    ctx.beginPath(); ctx.moveTo(top[0], top[1]);
    for (let k = 102; k <= Math.round(Math.min(u, 0.58) * 299); k++) ctx.lineTo(TRAP[k][0], TRAP[k][1]);
    ctx.lineTo(TRAP[Math.round(Math.min(u, 0.58) * 299)][0], top[1]); ctx.closePath(); ctx.fill(); ctx.restore();
    line([[top[0], top[1]], [CH.x1, top[1]]], lossA, { w: 3, c: RED, dash: [10, 12], nib: false });
  }
  // revendu trop tot : le gain manque, en pointilles or
  const missA = pr(g, T(12, "tot"), 0.5) * (1 - pr(g, S(13) - 0.2, 0.3));
  if (missA > 0) {
    const e = at(exitU);
    pill("VENTE", e[0], e[1] + 80, { fill: PAPER, c: INK, k: back(pr(g, T(12, "revends"), 0.4)) });
    ctx.save(); ctx.globalAlpha = missA; line(TRAP.slice(Math.round(exitU * 299)), 1, { w: 8, c: GOLD, dash: [2, 16] }); ctx.restore();
  }
  // la vengeance : la pile monte, puis tombe
  const stackIn = pr(g, S(13), 0.2);
  if (stackIn > 0) {
    ctx.save(); ctx.fillStyle = PAPER; ctx.globalAlpha = 0.92 * stackIn; ctx.fillRect(80, 780, 920, 900); ctx.restore();
    const n = Math.round(lerp(2, 14, eo(pr(g, T(13, "mises"), 1.2))));
    const fall = pr(g, T(14, "perds"), 0.9);
    for (let i = 0; i < n; i++) {
      const y = 1500 - i * 30, x = 540 + Math.sin(i * 0.9) * 6;
      const k = cl(fall * 1.6 - i * 0.04);
      coin(x + k * k * 300 * (i % 2 ? 1 : -1) * (0.4 + i * 0.05), y + k * k * 900, 70, Math.PI / 2 - 0.12 + k * 4, stackIn * (1 - k));
    }
    // sol qui s'ouvre sous la pile
    line([[300, 1540], [780, 1540]], 1 - fall, { w: 5, nib: false });
  }
});

// 4 · la journee --------------------------------------------------------------
scene(15, (t, g) => {
  const night = eio(pr(g, S(18) - 0.15, 0.4));
  const items = [["Réunion", "reunions"], ["Mails", "mails"], ["Trajet", "trajets"], ["Réunion", null], ["Mails", null], ["Réunion", null], ["Trajet", null]];
  items.forEach(([lab, w], i) => {
    const ts = w ? T(15, w) : T(15, "trajets") + 0.25 + i * 0.12;
    const k = back(pr(g, ts - 0.05, 0.35));
    if (k <= 0) return;
    const y = 1580 - i * 100;
    ctx.save(); ctx.translate(540, y); ctx.scale(k, k);
    card(-300, -42, 600, 84, { r: 16, lw: 3, fill: i % 3 === 0 ? PAPER2 : PAPER, a: 1 - pr(g, S(16), 0.4) * 0.65 });
    text(lab, -260, 0, { size: 34, align: "left", a: 1 - pr(g, S(16), 0.4) * 0.65 });
    text(["9:00", "10:30", "12:15", "14:00", "15:30", "17:00", "18:30"][i], 260, 0, { size: 28, weight: 500, c: GREY, align: "right", a: 1 - pr(g, S(16), 0.4) * 0.65 });
    ctx.restore();
  });
  // le compteur de decisions
  const n = Math.round(lerp(0, 347, eio(pr(g, T(16, "deja"), 1.9))));
  const ca = pr(g, S(16), 0.3) * (1 - night);
  if (ca > 0) {
    ctx.save(); ctx.globalAlpha = ca; ctx.fillStyle = PAPER; ctx.fillRect(220, 1000, 640, 300); ctx.restore();
    text(String(n), 540, 1120, { size: 210, font: SERIF, c: INK, a: ca });
    text("DÉCISIONS AUJOURD'HUI", 540, 1250, { size: 28, weight: 700, c: GREY, track: 3, a: ca });
  }
  // la batterie qui se vide
  const ba = pr(g, S(17) - 0.1, 0.3) * (1 - night);
  if (ba > 0) {
    const lvl = 1 - eio(pr(g, S(17), 0.8)) * 0.9;
    ctx.save(); ctx.globalAlpha = ba;
    card(380, 1360, 280, 120, { r: 18, lw: 5, shadow: false });
    ctx.fillStyle = INK; ctx.fillRect(660, 1395, 18, 50);
    ctx.fillStyle = lvl < 0.3 ? RED : INK; ctx.fillRect(396, 1376, 248 * lvl, 88);
    ctx.restore();
  }
  // le soir : seul le telephone eclaire
  if (night > 0) {
    ctx.save(); ctx.globalAlpha = night;
    const gl = ctx.createRadialGradient(540, 1250, 20, 540, 1250, 520);
    gl.addColorStop(0, "rgba(201,162,78,0.35)"); gl.addColorStop(1, "rgba(201,162,78,0)");
    ctx.fillStyle = gl; ctx.fillRect(0, 700, W, 1100);
    card(400, 1000, 280, 520, { fill: "#1d1f24", stroke: "#3a3c42", r: 34, lw: 5, shadow: false });
    const mini = TRAP.map(([x, y]) => [lerp(430, 650, (x - CH.x0) / (CH.x1 - CH.x0)), lerp(1400, 1120, (CH.y0 - y) / (CH.y0 - CH.y1))]);
    line(mini, eio(pr(g, S(18), 1.2)), { w: 4, c: "#D3826F" });
    text("?", 540, 1620, { size: 120, font: SERIF, italic: true, c: GOLD2, a: pr(g, T(18, "trader"), 0.3) });
    ctx.restore();
  }
}, { dark: (g) => g >= S(18) - 0.15 });

// 5 · les meilleurs : la methode ---------------------------------------------
scene(19, (t, g) => {
  // galerie : les pros en or, toi a la meme hauteur
  const ga = 1 - pr(g, S(21) - 0.2, 0.3);
  if (ga > 0) {
    const level = 1330;
    [[250, 0], [430, 0.1], [610, 0.2], [820, 0.35]].forEach(([x, d], i) => {
      const k = back(pr(g, S(19) + d, 0.45));
      ctx.save(); ctx.globalAlpha = ga;
      card(x - 70, level, 140, 200 + (i === 3 ? 0 : 0), { r: 10, lw: 4, fill: i === 3 ? PAPER2 : PAPER, shadow: false });
      ctx.restore();
      if (i < 3) pawn(x, level, 1.05 * k, { fill: GOLD2, stroke: GOLD, a: ga });
      else me(x, level, 1.05 * back(pr(g, T(20, "toi") - 0.3, 0.45)), { a: ga });
    });
    line([[150, 1100], [930, 1100]], pr(g, T(20, "pas"), 0.6) * ga, { w: 3, c: GOLD, dash: [8, 12], nib: false });
  }
  // l'equation dont le cerveau tombe
  const eqA = pr(g, S(21) - 0.2, 0.3) * (1 - pr(g, S(22) - 0.2, 0.3));
  if (eqA > 0) {
    const drop = eio(pr(g, T(21, "retire"), 0.8));
    const slide = eio(pr(g, T(21, "l'equation"), 0.6));
    text("décision", 540, 1000, { size: 96, font: SERIF, a: eqA });
    text("=", 540, 1110, { size: 80, font: SERIF, a: eqA });
    ctx.save(); ctx.translate(0, drop * drop * 700); ctx.rotate(drop * 0.15);
    text("cerveau +", lerp(370, 370, slide), 1230, { size: 96, font: SERIF, italic: true, c: RED, a: eqA * (1 - pr(drop, 0.8, 0.2)) });
    ctx.restore();
    text("règle", lerp(730, 540, slide), lerp(1230, 1230, slide), { size: 96, font: SERIF, c: GOLD, a: eqA });
    line([[220, 1240], [530, 1240]], pr(g, T(21, "retire") - 0.3, 0.3) * (1 - drop), { w: 6, c: RED, nib: false });
  }
  // decider avant, a froid : la fiche de regles
  const rA = pr(g, S(22) - 0.2, 0.3);
  if (rA > 0) {
    const frost = eo(pr(g, S(23), 0.6));
    card(170, 860, 740, 640, { a: rA, fill: frost > 0 ? `rgb(${lerp(243, 230, frost)},${lerp(238, 236, frost)},${lerp(230, 240, frost)})` : PAPER });
    text("LUNDI · 8 H 00", 230, 930, { size: 26, weight: 700, c: GREY, align: "left", track: 3, a: rA });
    text("Règles écrites avant", 230, 1000, { size: 54, font: SERIF, align: "left", a: rA });
    // givre aux coins
    for (const [cx, cy, s] of [[180, 870, 1], [900, 870, -1]]) {
      for (let k = 0; k < 5; k++) {
        const ang = (k / 5) * Math.PI / 2;
        line([[cx, cy], [cx + s * Math.cos(ang) * 90, cy + Math.sin(ang) * 90]], frost, { w: 3, c: "#7d8ea0", nib: false });
      }
    }
    // conditions
    const conds = [["Tendance confirmée", T(24, "tout")], ["Zone de prix atteinte", T(24, "reuni") ], ["Risque calculé", T(24, "agit") - 0.2]];
    conds.forEach(([lab, ts], i) => {
      const y = 1110 + i * 92;
      const ok = !(i === 2 && g >= S(25));
      ctx.save(); ctx.globalAlpha = rA * pr(g, S(24) + i * 0.15, 0.3);
      ctx.strokeStyle = INK; ctx.lineWidth = 3; ctx.strokeRect(232, y - 24, 48, 48);
      ctx.restore();
      text(lab, 310, y, { size: 38, weight: 500, align: "left", a: rA * pr(g, S(24) + i * 0.15, 0.3) });
      if (ok) check(256, y, 20, eo(pr(g, ts, 0.35)));
      else cross(256, y, 16, eo(pr(g, S(25), 0.35)));
    });
    // verdict
    const go = pr(g, T(24, "agit"), 0.3) * (1 - pr(g, S(25), 0.2));
    const wait = pr(g, S(25), 0.3) * (1 - pr(g, S(26) - 0.2, 0.2));
    pill("ON AGIT", 540, 1420, { fill: GOLD, k: back(go), a: go });
    pill("ON ATTEND", 540, 1420, { fill: INK, k: back(wait), a: wait });
    // la limite de perte, posee avant l'entree
    const sl = pr(g, S(26) - 0.1, 0.4);
    if (sl > 0) {
      ctx.save(); ctx.globalAlpha = sl; ctx.fillStyle = PAPER; ctx.fillRect(180, 1360, 720, 130); ctx.restore();
      line([[230, 1380], [850, 1380]], eo(pr(g, T(26, "limite"), 0.6)), { w: 4, c: INK, dash: [14, 10], nib: false });
      text("entrée", 230, 1352, { size: 28, weight: 600, align: "left", c: GREY, a: sl });
      line([[230, 1460], [850, 1460]], eo(pr(g, T(26, "posee"), 0.6)), { w: 6, c: RED, nib: false });
      text("limite de perte", 230, 1430, { size: 30, weight: 700, align: "left", c: RED, a: pr(g, T(26, "posee"), 0.4) });
    }
  }
});

// 6 · Compound Capital ---------------------------------------------------------
scene(27, (t, g) => {
  // le cordon « reserve aux pros »
  const cordA = 1 - pr(g, S(28) - 0.1, 0.25);
  if (cordA > 0) {
    const drop = eio(pr(g, T(27, "pros") + 0.2, 0.7));
    ctx.save(); ctx.globalAlpha = cordA;
    for (const x of [240, 840]) { ctx.fillStyle = GOLD; ctx.fillRect(x - 10, 1150, 20, 360); ctx.beginPath(); ctx.arc(x, 1150, 24, 0, 7); ctx.fill(); ctx.fillRect(x - 50, 1500, 100, 16); }
    const rope = Array.from({ length: 50 }, (_, k) => { const u = k / 49; return [lerp(240, 840 - drop * 300, u), 1180 + Math.sin(u * Math.PI) * 90 + drop * u * 330]; });
    line(rope, 1, { w: 14, c: RED, nib: false });
    card(400, 1240 + drop * 260, 280, 90, { r: 12, lw: 3, shadow: false });
    text("RÉSERVÉ AUX PROS", 540, 1285 + drop * 260, { size: 24, weight: 700, track: 2 });
    ctx.restore();
  }
  // la revelation
  const rv = pr(g, T(28, "compound") - 0.15, 0.4) * (1 - pr(g, S(29) - 0.15, 0.3));
  if (rv > 0) {
    const gl = ctx.createRadialGradient(540, 1180, 10, 540, 1180, 460);
    gl.addColorStop(0, `rgba(201,162,78,${0.35 * rv})`); gl.addColorStop(1, "rgba(201,162,78,0)");
    ctx.fillStyle = gl; ctx.fillRect(0, 700, W, 1000);
    text("Compound", 540, 1110, { size: 150, font: SERIF, a: rv });
    text("Capital", 540, 1250, { size: 150, font: SERIF, italic: true, c: GOLD, a: pr(g, T(28, "capital"), 0.3) * rv });
    line([[300, 1350], [780, 1350]], eo(pr(g, T(28, "construit"), 0.6)) * rv, { w: 4, c: GOLD });
  }
  // l'euro-dollar
  const fx = pr(g, S(29) - 0.15, 0.3) * (1 - pr(g, S(31) - 0.15, 0.3));
  if (fx > 0) {
    const others = ["GBP/JPY", "BITCOIN", "OR", "CAC 40", "PÉTROLE", "NASDAQ"];
    const gone = eio(pr(g, T(30, "seul"), 0.7));
    others.forEach((o, i) => {
      const a = (i / others.length) * Math.PI * 2 + g * 0.25;
      const r = 330 + gone * 260;
      pill(o, 540 + Math.cos(a) * r, 1200 + Math.sin(a) * r * 0.7, { fill: PAPER2, c: GREY, size: 24, a: fx * (1 - gone) });
    });
    coin(540, 1200, 170 * back(pr(g, S(29) - 0.1, 0.5)), 0, fx);
    text("€ / $", 540, 1204, { size: 92, font: SERIF, c: INK, a: fx });
    text("EUR / USD · LE MARCHÉ LE PLUS ÉCHANGÉ AU MONDE", 540, 1470, { size: 24, weight: 700, c: GREY, track: 2, a: fx * pr(g, T(29, "marche"), 0.4) });
  }
  // les chiffres entrent, les rumeurs rebondissent
  const ch = pr(g, S(31) - 0.15, 0.3) * (1 - pr(g, S(32) - 0.15, 0.3));
  if (ch > 0) {
    card(390, 1060, 300, 300, { fill: INK, stroke: null, r: 30, a: ch });
    text("RÈGLES", 540, 1210, { size: 34, weight: 800, c: PAPER, track: 4, a: ch });
    ["1.0842", "1.0857", "1.0839", "1.0861"].forEach((n, i) => {
      const k = pr(g, T(31, "chiffres") - 0.3 + i * 0.22, 0.7);
      text(n, lerp(130, 470, eio(k)), 1000 + i * 90 + eio(k) * (1210 - 1000 - i * 90), { size: 34, weight: 600, c: INK, a: ch * (1 - pr(k, 0.85, 0.15)) });
    });
    ["« ça va monter »", "« fonce »", "« info exclusive »"].forEach((s, i) => {
      const k = pr(g, T(31, "rumeurs") - 0.4 + i * 0.2, 0.9);
      const x = lerp(1060, 850, Math.min(1, k * 2)) + Math.max(0, k * 2 - 1) * 160;
      const y = 990 + i * 150 - Math.sin(Math.max(0, k * 2 - 1) * Math.PI) * 80;
      card(x - 150, y - 40, 300, 80, { r: 40, lw: 3, a: ch * pr(k, 0, 0.1) * (1 - pr(k, 0.85, 0.15)), shadow: false });
      text(s, x, y, { size: 28, font: SERIF, italic: true, c: RED, a: ch * pr(k, 0, 0.1) * (1 - pr(k, 0.85, 0.15)) });
    });
  }
  // lundi au vendredi, comme un metronome
  const mt = pr(g, S(32) - 0.15, 0.3) * (1 - pr(g, S(33) - 0.15, 0.3));
  if (mt > 0) {
    ["L", "M", "M", "J", "V"].forEach((d, i) => {
      const beat = pr(g, T(32, "lundi") + i * 0.2, 0.25);
      const x = 220 + i * 160, h = 120 + back(beat) * 200;
      ctx.save(); ctx.globalAlpha = mt; ctx.fillStyle = i === Math.floor(cl((g - T(32, "lundi")) / 0.2, 0, 4)) ? GOLD : INK;
      rrect(x - 50, 1480 - h, 100, h, 14); ctx.fill(); ctx.restore();
      text(d, x, 1530, { size: 44, font: SERIF, a: mt });
    });
    text("SANS ÉMOTION", 540, 1060, { size: 30, weight: 800, c: GREY, track: 6, a: mt * pr(g, T(32, "emotion"), 0.3) });
  }
  // rien a faire
  const nt = pr(g, S(33) - 0.15, 0.3);
  if (nt > 0) {
    me(540, 1520, 1.3, { a: nt });
    const icons = [["graphique", 250], ["signal", 540], ["cliquer", 830]];
    icons.forEach(([w, x], i) => {
      const a = nt * pr(g, T(33, w) - 0.4, 0.3);
      card(x - 95, 960, 190, 190, { r: 28, lw: 4, a, shadow: false });
      ctx.save(); ctx.globalAlpha = a;
      if (i === 0) line([[x - 60, 1100], [x - 25, 1040], [x + 5, 1070], [x + 60, 1000]], 1, { w: 6, nib: false });
      if (i === 1) { ctx.strokeStyle = INK; ctx.lineWidth = 6; ctx.beginPath(); ctx.arc(x, 1050, 40, Math.PI, 0); ctx.lineTo(x + 50, 1095); ctx.lineTo(x - 50, 1095); ctx.closePath(); ctx.stroke(); }
      if (i === 2) { ctx.fillStyle = INK; ctx.beginPath(); ctx.moveTo(x - 30, 1000); ctx.lineTo(x + 40, 1060); ctx.lineTo(x + 5, 1065); ctx.lineTo(x + 25, 1105); ctx.lineTo(x + 10, 1112); ctx.lineTo(x - 10, 1072); ctx.lineTo(x - 30, 1095); ctx.closePath(); ctx.fill(); }
      ctx.restore();
      cross(x, 1055, 70, eo(pr(g, T(33, w), 0.35)));
    });
  }
});

// 7 · concretement : le telephone -----------------------------------------
function phone(x, y, s, a, inner) {
  ctx.save(); ctx.globalAlpha *= a; ctx.translate(x, y); ctx.scale(s, s);
  card(-230, -440, 460, 880, { fill: INK, stroke: null, r: 60 });
  ctx.fillStyle = PAPER; rrect(-212, -422, 424, 844, 46); ctx.fill();
  ctx.fillStyle = INK; rrect(-60, -408, 120, 26, 13); ctx.fill();
  inner();
  ctx.restore();
}
scene(34, (t, g) => {
  const ph = eo(pr(g, S(34) - 0.1, 0.6));
  const step = g < S(36) ? 0 : g < S(37) ? 1 : g < S(38) ? 2 : g < S(39) ? 3 : g < S(40) ? 4 : 5;
  const px = 540 + (step === 3 ? 150 : 0) * eio(pr(g, S(38), 0.5)) - (step >= 4 ? 150 * (1 - eio(pr(g, S(39), 0.5))) : 0);
  phone(px, 1230 + (1 - ph) * 600, 0.92, 1, () => {
    text("Mon compte", -170, -330, { size: 44, font: SERIF, align: "left" });
    // compte a ton nom
    card(-180, -270, 360, 150, { r: 20, lw: 3, shadow: false, a: pr(g, S(35), 0.4) });
    text("TITULAIRE", -150, -232, { size: 20, weight: 700, c: GREY, align: "left", track: 2, a: pr(g, S(35), 0.4) });
    text("Ton nom", -150, -180, { size: 40, font: SERIF, italic: true, align: "left", a: pr(g, T(35, "nom"), 0.3) });
    text("Courtier partenaire · régulé", -150, -140, { size: 20, weight: 500, c: GREY, align: "left", a: pr(g, T(35, "courtier"), 0.3) });
    // depot
    const dep = eio(pr(g, S(36), 0.9));
    text("CAPITAL", -150, -70, { size: 20, weight: 700, c: GREY, align: "left", track: 2, a: pr(g, S(36), 0.3) });
    ctx.fillStyle = RULE; ctx.globalAlpha = pr(g, S(36), 0.3); rrect(-150, -45, 300, 18, 9); ctx.fill();
    ctx.fillStyle = GOLD; rrect(-150, -45, 300 * dep, 18, 9); ctx.fill(); ctx.globalAlpha = 1;
    // demander l'acces
    const press = pr(g, T(37, "l'acces"), 0.25);
    const bk = 1 - Math.sin(press * Math.PI) * 0.06;
    ctx.save(); ctx.translate(0, 40); ctx.scale(bk, bk);
    ctx.globalAlpha = pr(g, S(37) - 0.2, 0.3);
    ctx.fillStyle = press >= 1 ? GOLD : INK; rrect(-170, -38, 340, 76, 38); ctx.fill();
    text(press >= 1 ? "Accès demandé ✓" : "Demander l'accès", 0, 0, { size: 30, weight: 700, c: PAPER });
    ctx.restore();
    if (press > 0 && press < 1) { ctx.strokeStyle = GOLD; ctx.lineWidth = 4; ctx.globalAlpha = 1 - press; ctx.beginPath(); ctx.arc(60, 40, 20 + press * 90, 0, 7); ctx.stroke(); ctx.globalAlpha = 1; }
    // positions copiees
    text("POSITIONS", -150, 130, { size: 20, weight: 700, c: GREY, align: "left", track: 2, a: pr(g, S(38), 0.3) });
    for (let i = 0; i < 2; i++) {
      const k = eio(pr(g, T(38, "copie") + i * 0.5, 0.6));
      if (k <= 0) continue;
      ctx.save(); ctx.globalAlpha = k; ctx.translate((1 - k) * -420, 0);
      card(-180, 160 + i * 100, 360, 80, { r: 16, lw: 3, shadow: false });
      text("EUR/USD", -150, 200 + i * 100, { size: 28, weight: 700, align: "left" });
      text(i ? "copiée" : "copiée", 150, 200 + i * 100, { size: 24, weight: 600, c: GOLD, align: "right" });
      ctx.restore();
    }
    // le cadenas
    const lk = back(pr(g, S(39), 0.5));
    if (step >= 4 && lk > 0) {
      ctx.save(); ctx.fillStyle = "rgba(243,238,230,0.86)"; rrect(-212, -422, 424, 844, 46); ctx.fill();
      ctx.translate(0, -40); ctx.scale(lk, lk);
      ctx.strokeStyle = GOLD; ctx.lineWidth = 18; ctx.beginPath(); ctx.arc(0, -60, 70, Math.PI, 0); ctx.stroke();
      ctx.fillStyle = GOLD; rrect(-110, -60, 220, 170, 24); ctx.fill();
      ctx.fillStyle = PAPER; ctx.beginPath(); ctx.arc(0, 10, 20, 0, 7); ctx.fill(); ctx.fillRect(-7, 10, 14, 50);
      ctx.restore();
      text("Retrait : toi seul", 0, 200, { size: 40, font: SERIF, italic: true, a: pr(g, T(39, "personne"), 0.3) });
    }
    // l'interrupteur
    const sw = pr(g, S(40) - 0.1, 0.3);
    if (sw > 0) {
      ctx.save(); ctx.fillStyle = PAPER; ctx.globalAlpha = sw; rrect(-212, -422, 424, 844, 46); ctx.fill();
      const off = eio(pr(g, T(40, "arreter"), 0.35));
      ctx.fillStyle = off > 0.5 ? RULE : GOLD; rrect(-130, -70, 260, 140, 70); ctx.fill();
      ctx.fillStyle = PAPER; ctx.beginPath(); ctx.arc(lerp(60, -60, off), 0, 56, 0, 7); ctx.fill();
      ctx.restore();
      text(off > 0.5 ? "ARRÊTÉ" : "ACTIF", 0, 150, { size: 30, weight: 800, track: 4, c: off > 0.5 ? GREY : GOLD, a: sw });
      text("quand tu veux", 0, 210, { size: 40, font: SERIF, italic: true, a: pr(g, T(40, "quand"), 0.3) });
    }
  });
  // la strategie, d'ou partent les copies (copie carbone)
  const st = pr(g, S(38) - 0.1, 0.4) * (1 - pr(g, S(39), 0.3));
  if (st > 0) {
    card(60, 1040, 240, 240, { fill: INK, stroke: null, r: 28, a: st });
    text("STRATÉGIE", 180, 1130, { size: 24, weight: 800, c: PAPER, track: 3, a: st });
    text("Compound", 180, 1185, { size: 36, font: SERIF, c: GOLD2, a: st });
    line([[310, 1160], [470, 1160]], eo(pr(g, T(38, "copie"), 0.5)) * st, { w: 5, c: GOLD, dash: [10, 10] });
  }
});

// 8 · paye sur les gains : l'escalier ---------------------------------------------
scene(41, (t, g) => {
  const steps = [0, 1, 1, 2, 1, 3, 3, 4];     // hauteur du compte, semaine apres semaine
  const n = Math.round(lerp(1, steps.length, eio(pr(g, S(41), 2.2))));
  const x0 = 120, sw = 105, base = 1580, sh = 110;
  for (let i = 0; i < n; i++) {
    const h = 120 + steps[i] * sh, x = x0 + i * sw;
    const up = i > 0 && steps[i] > Math.max(...steps.slice(0, i));
    ctx.fillStyle = up ? PAPER2 : PAPER; ctx.strokeStyle = INK; ctx.lineWidth = 4;
    ctx.fillRect(x, base - h, sw - 8, h); ctx.strokeRect(x, base - h, sw - 8, h);
    // la commission : une fine tranche d'or, seulement sur un nouveau sommet
    if (up) {
      const k = eo(pr(g, T(42, "gains") + i * 0.12, 0.5));
      const lift = eo(pr(g, S(43), 0.6)) * 70;
      ctx.fillStyle = GOLD; ctx.globalAlpha = k; ctx.fillRect(x, base - h - 14 - lift, sw - 8, 14); ctx.globalAlpha = 1;
    } else if (i > 0) {
      text("0 €", x + (sw - 8) / 2, base - h - 34, { size: 30, weight: 700, c: GREY, a: pr(g, T(43, "pas") + i * 0.06, 0.3) });
    }
  }
  text("commission = une part des gains seulement", 540, 900, { size: 30, weight: 600, c: GOLD, a: pr(g, S(43), 0.4) });
  // notre interet
  const ia = pr(g, S(44) - 0.1, 0.3);
  line([[150, 1500], [420, 1300], [640, 1340], [940, 1000]], eo(pr(g, T(44, "progresse") - 0.4, 0.8)) * ia, { w: 8, c: GOLD });
});

// 9 · la preuve ------------------------------------------------------------------
scene(45, (t, g) => {
  // la promesse qui creve, la capture qui vole en eclats
  const pa = 1 - pr(g, S(46) - 0.15, 0.2);
  if (pa > 0) {
    const pop = pr(g, T(45, "l'air") - 0.1, 0.25);
    if (pop < 1) {
      ctx.save(); ctx.translate(540, 980); ctx.scale(1 + pop * 0.3, 1 + pop * 0.3); ctx.globalAlpha = 1 - pop;
      card(-260, -80, 520, 160, { r: 80, lw: 4, shadow: false });
      text("+300 % garanti !", 0, 0, { size: 56, font: SERIF, italic: true, c: RED });
      ctx.restore();
    }
    const sh = pr(g, T(45, "capture") + 0.1, 1.2);
    SHARDS.forEach((s) => {
      ctx.save();
      ctx.translate(s.vx * sh * 0.4, s.vy * sh * 0.5 + 1600 * sh * sh);
      ctx.translate(540, 1300); ctx.rotate(s.vr * sh); ctx.translate(-540, -1300);
      ctx.globalAlpha = pa * pr(g, S(45) + 0.6, 0.3) * (1 - pr(sh, 0.7, 0.3));
      ctx.beginPath(); ctx.moveTo(s.pts[0][0], s.pts[0][1] + 150); s.pts.slice(1).forEach((p) => ctx.lineTo(lerp(540, p[0], 0.62), lerp(1300, p[1] + 150, 0.62)));
      ctx.closePath(); ctx.fillStyle = PAPER2; ctx.fill(); ctx.strokeStyle = INK; ctx.lineWidth = 2; ctx.stroke();
      ctx.restore();
    });
    if (sh <= 0) text("capture d'écran", 540, 1300, { size: 30, weight: 600, c: GREY, a: pr(g, S(45) + 0.6, 0.3) });
  }
  // l'historique reel
  const ha = pr(g, S(46) - 0.15, 0.3) * (1 - pr(g, S(49) - 0.15, 0.3));
  if (ha > 0) {
    ctx.save(); ctx.globalAlpha = ha;
    line([[130, 1530], [960, 1530]], 1, { w: 3, c: RULE, nib: false });
    line(HIST, eio(pr(g, S(46), 2.6)), { w: 6 });
    // les creux, assumes
    [52, 118, 160].forEach((k, i) => {
      const a = pr(g, S(46) + 1.0 + i * 0.4, 0.3);
      ctx.strokeStyle = RED; ctx.lineWidth = 3; ctx.globalAlpha = ha * a; ctx.beginPath(); ctx.arc(HIST[k + 2][0], HIST[k + 2][1], 34, 0, 7); ctx.stroke();
    });
    ctx.globalAlpha = ha;
    pill("ARGENT RÉEL", 300, 900, { fill: INK, size: 24, k: back(pr(g, T(46, "reel"), 0.4)) });
    pill("VÉRIFIABLE", 560, 900, { fill: PAPER2, c: INK, size: 24, k: back(pr(g, T(46, "verifiable"), 0.4)) });
    pill("MYFXBOOK", 800, 900, { fill: GOLD, size: 24, k: back(pr(g, T(46, "myfxbook"), 0.4)) });
    ctx.restore();
    // la loupe
    const lp = pr(g, S(47) - 0.2, 0.4);
    if (lp > 0) {
      const u = lerp(0.2, 0.75, eio(pr(g, S(47), E(48) - S(47))));
      const p = HIST[Math.round(u * 199)];
      ctx.save(); ctx.globalAlpha = ha * lp;
      ctx.beginPath(); ctx.arc(p[0], p[1], 120, 0, 7); ctx.fillStyle = "rgba(243,238,230,0.6)"; ctx.fill();
      ctx.save(); ctx.clip(); ctx.translate(p[0], p[1]); ctx.scale(1.8, 1.8); ctx.translate(-p[0], -p[1]); line(HIST, 1, { w: 5, nib: false }); ctx.restore();
      ctx.strokeStyle = INK; ctx.lineWidth = 10; ctx.beginPath(); ctx.arc(p[0], p[1], 120, 0, 7); ctx.stroke();
      ctx.lineWidth = 22; ctx.lineCap = "round"; ctx.beginPath(); ctx.moveTo(p[0] + 90, p[1] + 90); ctx.lineTo(p[0] + 180, p[1] + 180); ctx.stroke();
      ctx.restore();
    }
  }
  // la porte : sur demande
  const da = pr(g, S(49) - 0.15, 0.3);
  if (da > 0) {
    ctx.save(); ctx.globalAlpha = da;
    ctx.fillStyle = INK; ctx.fillRect(600, 940, 260, 560);
    ctx.fillStyle = GOLD2; ctx.fillRect(612, 952, 236, 548);
    ctx.fillStyle = PAPER; ctx.fillRect(624, 964, 212, 536);
    ctx.restore();
    text("SUR DEMANDE", 730, 900, { size: 26, weight: 800, track: 4, c: GOLD, a: da });
    // ceux qui ont compris entrent
    for (let i = 0; i < 3; i++) {
      const k = eio(pr(g, T(49, "compris") - 0.6 + i * 0.35, 1.1));
      if (k > 0 && k < 1) me(lerp(160 + i * 60, 730, k), 1495, 0.9, { a: da * (1 - pr(k, 0.85, 0.15)) });
      else if (k <= 0) me(160 + i * 60 + 10, 1495, 0.9, { a: da });
    }
    // le presse rebondit
    const r = pr(g, T(50, "presses") - 0.5, 0.9);
    const x = r < 0.45 ? lerp(-80, 570, r / 0.45) : 570 - (r - 0.45) / 0.55 * 400;
    const y = 1495 - (r > 0.45 ? Math.sin((r - 0.45) / 0.55 * Math.PI) * 160 : 0);
    if (r > 0) {
      pawn(x, y, 0.9, { rot: r > 0.45 ? -(r - 0.45) * 4 : 0.15, a: da });
      if (r < 0.45) for (let i = 0; i < 3; i++) line([[x - 70 - i * 10, y - 60 - i * 26], [x - 150 - i * 10, y - 60 - i * 26]], 1, { w: 4, nib: false });
    }
  }
});

// 10 · imagine ----------------------------------------------------------------------
scene(51, (t, g) => {
  // la sortie de reunion : une porte de salle qui s'ouvre sur un couloir clair
  const ph = eo(pr(g, T(53, "ouvres") - 0.2, 0.6)) * (1 - pr(g, S(55) - 0.15, 0.3));
  const door = 1 - pr(g, T(53, "ouvres"), 0.3);
  if (door > 0) {
    ctx.save(); ctx.globalAlpha = door;
    card(330, 900, 420, 640, { r: 10, lw: 5, fill: PAPER2, shadow: false });
    text("SALLE 4 · RÉUNION", 540, 960, { size: 22, weight: 700, c: GREY, track: 2 });
    const open = eio(pr(g, S(52), 0.7));
    ctx.fillStyle = PAPER; ctx.fillRect(345, 1000, 390 * open, 525);
    me(lerp(540, 860, eio(pr(g, T(52, "reunion"), 0.8))), 1530, 1, {});
    ctx.restore();
  }
  if (ph > 0) {
    phone(540, 1250 + (1 - ph) * 300, 0.82, ph, () => {
      text("Aujourd'hui", -170, -320, { size: 46, font: SERIF, align: "left" });
      const n = eo(pr(g, S(54), 0.5));
      ctx.save(); ctx.translate(0, (1 - n) * -120); ctx.globalAlpha = n;
      card(-190, -250, 380, 230, { r: 26, lw: 3 });
      text("COMPOUND CAPITAL", -160, -205, { size: 18, weight: 800, c: GOLD, align: "left", track: 2 });
      text("Ta stratégie a suivi", -160, -150, { size: 36, font: SERIF, align: "left" });
      text("ses règles.", -160, -105, { size: 36, font: SERIF, italic: true, align: "left" });
      text("Sans intervention de ta part.", -160, -55, { size: 20, weight: 500, c: GREY, align: "left" });
      ctx.restore();
      line(HIST.slice(120).map(([x, y]) => [lerp(-170, 170, (x - HIST[120][0]) / (950 - HIST[120][0])), lerp(220, 40, (1500 - y) / 520)]),
        eio(pr(g, T(54, "suivi"), 1.0)), { w: 5, c: GOLD });
    });
  }
  // sans stress, sans ecran, sans toi
  const sa = pr(g, S(55) - 0.15, 0.25) * (1 - pr(g, S(58) - 0.15, 0.25));
  if (sa > 0) {
    [[55, "stress"], [56, "ecran"], [57, "toi"]].forEach(([bi, w], i) => {
      const k = back(pr(g, T(bi, w) - 0.15, 0.4));
      const x = 220 + i * 320;
      ctx.save(); ctx.globalAlpha = sa; ctx.translate(x, 1200); ctx.scale(k, k);
      ctx.strokeStyle = INK; ctx.lineWidth = 6; ctx.beginPath(); ctx.arc(0, 0, 110, 0, 7); ctx.stroke();
      if (i === 0) line([[-70, 0], [-30, 0], [-15, -40], [10, 40], [25, 0], [70, 0]], 1, { w: 6, nib: false });
      if (i === 1) { ctx.strokeRect(-60, -40, 120, 80); ctx.beginPath(); ctx.moveTo(-20, 60); ctx.lineTo(20, 60); ctx.stroke(); }
      if (i === 2) me(0, 50, 0.75, { a: 0.25 });
      ctx.restore();
      cross(x, 1200, 80 * k, eo(pr(g, T(bi, w) + 0.1, 0.3)), i === 2 ? GOLD : RED);
    });
  }
  // tu gardes ton travail, elle garde la discipline
  const sp = pr(g, S(58) - 0.15, 0.3);
  if (sp > 0) {
    line([[540, 900], [540, 1560]], eo(pr(g, S(58), 0.5)), { w: 4, c: GOLD });
    ctx.save(); ctx.globalAlpha = sp;
    // la mallette
    ctx.strokeStyle = INK; ctx.lineWidth = 7; ctx.fillStyle = PAPER2;
    rrect(170, 1130, 220, 160, 18); ctx.fill(); ctx.stroke();
    rrect(235, 1095, 90, 40, 12); ctx.stroke();
    ctx.restore();
    text("ton travail", 280, 1380, { size: 52, font: SERIF, italic: true, a: sp });
    const dp = pr(g, S(59) - 0.1, 0.3);
    card(690, 1090, 210, 240, { r: 18, a: dp, shadow: false });
    for (let i = 0; i < 3; i++) check(745, 1150 + i * 60, 14, eo(pr(g, S(59) + i * 0.12, 0.3)));
    for (let i = 0; i < 3; i++) line([[780, 1150 + i * 60], [870, 1150 + i * 60]], eo(pr(g, S(59) + i * 0.12, 0.3)), { w: 5, nib: false });
    text("sa discipline", 800, 1380, { size: 52, font: SERIF, italic: true, c: GOLD, a: dp });
  }
});

// 11 · appel a l'action et fin -------------------------------------------------------
scene(60, (t, g) => {
  const c0 = S(60);
  const end = eio(pr(g, S(61) - 0.2, 0.5));
  if (end < 1) {
    ctx.save(); ctx.globalAlpha = 1 - end;
    if (VARIANT === "ig") {
      // un champ de commentaire generique, qui s'ecrit tout seul
      card(110, 1080, 860, 130, { r: 65, lw: 4 });
      const typed = "Capital".slice(0, Math.round(lerp(0, 7, pr(g, c0 + 4.2, 0.7))));
      text(typed || "Ajouter un commentaire…", 170, 1145, { size: 44, font: typed ? SANS : SANS, weight: typed ? 700 : 400, c: typed ? INK : GREY, align: "left" });
      if (typed.length && typed.length < 7 && Math.floor(g * 4) % 2) ctx.fillRect(175 + ctx.measureText(typed).width, 1120, 3, 50);
      ctx.fillStyle = GOLD; ctx.beginPath(); ctx.arc(890, 1145, 46, 0, 7); ctx.fill();
      line([[870, 1145], [910, 1145]], 1, { w: 6, c: PAPER, nib: false }); line([[895, 1128], [912, 1145], [895, 1162]], 1, { w: 6, c: PAPER, nib: false });
      // la reponse : le lien en message
      const dm = back(pr(g, c0 + 5.3, 0.45));
      ctx.save(); ctx.translate(560, 1370); ctx.scale(dm, dm);
      card(-340, -80, 680, 160, { r: 40, fill: INK, stroke: null });
      text("Voici le lien du Telegram ✈", 0, 0, { size: 38, weight: 600, c: PAPER });
      ctx.restore();
    } else {
      card(170, 1100, 740, 220, { r: 30, lw: 4 });
      text("Lien en description", 540, 1210, { size: 64, font: SERIF, italic: true, a: pr(g, c0 + 3.85, 0.3) });
    }
    // l'avion en papier, fait des questions pliees
    const fl = pr(g, c0 + 0.2, 3.4);
    const px = lerp(-100, 1180, eio(fl)), py = 960 - Math.sin(fl * Math.PI) * 120;
    ctx.save(); ctx.translate(px, py); ctx.rotate(-0.18);
    ctx.fillStyle = PAPER; ctx.strokeStyle = INK; ctx.lineWidth = 4;
    ctx.beginPath(); ctx.moveTo(70, 0); ctx.lineTo(-60, -40); ctx.lineTo(-30, 0); ctx.lineTo(-60, 40); ctx.closePath(); ctx.fill(); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(70, 0); ctx.lineTo(-30, 0); ctx.stroke();
    ctx.restore();
    const trail = Array.from({ length: 40 }, (_, k) => { const f = fl * k / 39; return [lerp(-100, 1180, eio(f)) - 60, 960 - Math.sin(f * Math.PI) * 120 + 6]; });
    line(trail, 1, { w: 3, c: GREY, dash: [6, 12], nib: false });
    ctx.restore();
  }
  // la carte de fin
  if (end > 0) {
    ctx.save(); ctx.globalAlpha = end;
    ctx.fillStyle = PAPER; ctx.fillRect(0, 160, W, H);
    text("Compound", 540, 820, { size: 170, font: SERIF });
    text("Capital", 540, 980, { size: 170, font: SERIF, italic: true, c: GOLD });
    line([[260, 1090], [820, 1090]], eo(pr(g, S(61) + 0.3, 0.6)), { w: 3, c: INK });
    text("Comprendre avant de décider.", 540, 1170, { size: 58, font: SERIF, italic: true, a: pr(g, T(62, "comprendre") - 0.1, 0.4) });
    pill(VARIANT === "ig" ? "COMMENTE « CAPITAL »" : "REJOINS LE TELEGRAM", 540, 1340, { fill: INK, size: 30, k: back(pr(g, S(61) + 0.2, 0.5)) });
    if (VARIANT === "tt") text("LIEN EN DESCRIPTION", 540, 1430, { size: 24, weight: 700, c: GREY, track: 3 });
    text("Le trading comporte un risque de perte en capital.", 540, 1600, { size: 24, weight: 500, c: GREY });
    text("Les performances passées ne garantissent pas les résultats futurs.", 540, 1640, { size: 24, weight: 500, c: GREY });
    ctx.restore();
  }
}, { noHeadline: (g) => g >= S(61) - 0.2 });

// ============================================================================
// composition
// ============================================================================
const START = SC.map((s, i) => (i === 0 ? 0 : S(s.from) - 0.22));

export function renderAt(t) {
  let si = 0;
  for (let i = 0; i < SC.length; i++) if (t >= START[i]) si = i;
  const sc = SC[si];
  const dark = sc.dark ? sc.dark(t) : false;

  background(dark);
  header(t, dark);

  // entree de scene : glissement court, comme une coupe montee sur la voix
  const local = t - START[si];
  const enter = si === 0 ? 1 : eo(local / 0.38);
  ctx.save();
  ctx.translate(0, (1 - enter) * 90);
  ctx.globalAlpha = enter;
  // lente poussee de camera dans la scene
  const push = 1.14 * (1 + 0.035 * cl(local / 8));
  ctx.translate(540, 1200); ctx.scale(push, push); ctx.translate(-540, -1230);
  sc.draw(local, t);
  ctx.restore();

  if (!(sc.noHeadline && sc.noHeadline(t))) drawHeadline(t, dark);
  finish(t, dark);
}

async function runRange(from, to) {
  for (let f = from; f <= to; f++) {
    renderAt(f / FPS);
    const img = ctx.getImageData(0, 0, W, H);
    await fetch(`/frame/${f}`, { method: "POST", body: img.data });
  }
}

await Promise.all([
  document.fonts.load('100px "Instrument Serif"'),
  document.fonts.load('italic 100px "Instrument Serif"'),
  document.fonts.load('600 100px "Inter"'),
]);
window.FILM = { W, H, FPS, DUR, renderAt, runRange, ready: Promise.resolve() };
