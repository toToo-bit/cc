// Masterclass v3 — moteur du film.
//
// Le film est une fonction pure du temps : renderAt(t) doit toujours produire
// la meme image pour le meme t. Aucune animation ne depend de l'horloge reelle,
// ce qui permet de rendre en desordre, de reprendre un rendu interrompu, et de
// sortir une planche-contact a n'importe quel instant.

import * as THREE from "three";
import { buildBrainGeometry, makeBrainMaterial } from "./engine/brain.js";

const Q = new URLSearchParams(location.search);
const W = +(Q.get("w") || 1080);
const H = +(Q.get("h") || 1920);
const DETAIL = +(Q.get("detail") || 112);
const FPS = +(Q.get("fps") || 30);

// --- charte -----------------------------------------------------------------
export const PALETTE = {
  papier: "#F3EEE6",
  encre: "#14161A",
  gris: "#9A938A",
  filet: "#CEC6BA",
  bordeaux: "#6E2A24",
  or: "#C8A24A",
};

const stage = document.getElementById("stage");
stage.width = W; stage.height = H;
const ctx = stage.getContext("2d", { willReadFrequently: true });

const glCanvas = document.getElementById("gl");
const renderer = new THREE.WebGLRenderer({
  canvas: glCanvas, antialias: true, alpha: false, preserveDrawingBuffer: true,
});
renderer.setPixelRatio(1);
renderer.setSize(W, H, false);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.0;
renderer.shadowMap.enabled = false;

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x07060a);

// Environnement studio : sans lui, un metal parfait n'a rien a refleter et
// les pieces d'or sortent noires.
{
  const { RoomEnvironment } = await import("three/addons/environments/RoomEnvironment.js");
  const pmrem = new THREE.PMREMGenerator(renderer);
  // attache aux seuls materiaux qui en ont besoin : scene.environment
  // s'appliquerait aussi au cerveau, qui sortirait en platre.
  window.__ENV = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
  pmrem.dispose();
}

const camera = new THREE.PerspectiveCamera(30, W / H, 0.1, 100);

// --- utilitaires de temps ----------------------------------------------------
const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const smooth = (x) => { x = clamp(x); return x * x * (3 - 2 * x); };
/** rampe de a vers b entre les instants t0 et t1 */
const ramp = (t, t0, t1) => smooth((t - t0) / Math.max(1e-6, t1 - t0));
/** amortissement type ressort, pour les arrivees de texte */
const ease = (x) => 1 - Math.pow(1 - clamp(x), 3);

// --- plan 1 : le cerveau -----------------------------------------------------
const brain = new THREE.Group();
const brainGeo = buildBrainGeometry(DETAIL);
const brainMat = makeBrainMaterial();
const brainMesh = new THREE.Mesh(brainGeo, brainMat);
brain.add(brainMesh);
brain.position.set(0, -0.30, 0);
brain.scale.setScalar(0.92);
scene.add(brain);

// Eclairage studio. Une cle chaude rasante : c'est l'incidence faible qui
// sculpte les sillons, un eclairage frontal les effacerait.
const key = new THREE.DirectionalLight(0xffe2bb, 3.2);
key.position.set(2.6, 2.4, 1.6);
scene.add(key);

const fill = new THREE.DirectionalLight(0x7d8cae, 0.85);
fill.position.set(-3.0, -0.4, 1.8);
scene.add(fill);

// contre-jour : detache le cerveau du noir
const rim = new THREE.DirectionalLight(0xffd3a0, 2.4);
rim.position.set(-1.8, 1.0, -2.6);
scene.add(rim);

const rim2 = new THREE.DirectionalLight(0x9fb4d8, 1.1);
rim2.position.set(1.6, -0.8, -2.2);
scene.add(rim2);

scene.add(new THREE.AmbientLight(0x2a2d38, 1.3));

// pieces d'or qui tombent
const coinGeo = new THREE.CylinderGeometry(0.075, 0.075, 0.012, 40);
const coinMat = new THREE.MeshPhysicalMaterial({
  color: new THREE.Color(PALETTE.or), metalness: 1.0, roughness: 0.22,
  envMap: window.__ENV,
  envMapIntensity: 1.4,
});
const COINS = 14;
const coins = new THREE.InstancedMesh(coinGeo, coinMat, COINS);
coins.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
scene.add(coins);

// Generateur deterministe : jamais Math.random() dans le film, sinon deux
// rendus du meme instant different et une reprise de rendu fait un raccord.
export function rng(seed) {
  let s = seed >>> 0;
  return () => {
    s = (s + 0x6D2B79F5) >>> 0;
    let x = s;
    x = Math.imul(x ^ (x >>> 15), x | 1);
    x ^= x + Math.imul(x ^ (x >>> 7), x | 61);
    return ((x ^ (x >>> 14)) >>> 0) / 4294967296;
  };
}

const rnd = rng(4242);
const coinSeed = [];
for (let i = 0; i < COINS; i++) {
  coinSeed.push({
    x: (rnd() * 2 - 1) * 1.25,
    z: (rnd() * 2 - 1) * 0.9 - 0.2,
    y0: 1.7 + rnd() * 2.4,
    spin: (rnd() * 2 - 1) * 2.4,
    tilt: rnd() * Math.PI,
    speed: 0.85 + rnd() * 0.5,
    delay: rnd() * 1.4,
  });
}

const dummy = new THREE.Object3D();
function updateCoins(t) {
  for (let i = 0; i < COINS; i++) {
    const c = coinSeed[i];
    const tt = Math.max(0, t - c.delay);
    dummy.position.set(c.x, c.y0 - tt * c.speed * 1.9, c.z);
    dummy.rotation.set(c.tilt + tt * 0.7, tt * c.spin, Math.PI / 2.4);
    dummy.updateMatrix();
    coins.setMatrixAt(i, dummy.matrix);
  }
  coins.instanceMatrix.needsUpdate = true;
}

// --- texte 2D ----------------------------------------------------------------
function drawTitle(t) {
  // « Ton cerveau te fait perdre de l'argent. » — present des l'image 0,
  // « perdre de l'argent » en italique, c'est l'accroche qui arrete le pouce.
  // Opaque des l'image 0 : sur un fil, la premiere image EST la miniature.
  // Seul un leger glissement vertical anime l'entree.
  const appear = 1;
  const rise = 1 - ease(t / 0.6);

  const margin = Math.round(W * 0.095);
  const maxW = W - margin * 2;
  const size = Math.round(W * 0.108);
  const lh = Math.round(size * 1.12);

  ctx.save();
  ctx.globalAlpha = appear;
  ctx.textBaseline = "alphabetic";
  ctx.fillStyle = PALETTE.papier;

  // mise en lignes manuelle : la coupe est une decision de design, pas un hasard
  const lines = [
    [{ s: "Ton cerveau", i: false }],
    [{ s: "te fait ", i: false }, { s: "perdre", i: true }],
    [{ s: "de l'argent.", i: true }],
  ];

  let y = Math.round(H * 0.175) + rise * Math.round(H * 0.012);
  for (const line of lines) {
    let x = margin;
    for (const part of line) {
      ctx.font = `${part.i ? "italic " : ""}${size}px "Instrument Serif", serif`;
      ctx.fillStyle = part.i ? PALETTE.papier : PALETTE.papier;
      ctx.fillText(part.s, x, y);
      x += ctx.measureText(part.s).width;
    }
    y += lh;
  }
  ctx.restore();
  void maxW;
}

// --- composition -------------------------------------------------------------
export function renderAt(t) {
  // --- mise en scene du plan 1
  // le cerveau tourne tres lentement : il est sculpte, pas anime
  brain.rotation.y = -0.35 + t * 0.085;
  brain.rotation.x = 0.06 * Math.sin(t * 0.5);

  // Cadrage : cerveau dans la moitie basse, titre en haut. La camera vise
  // au-dessus du cerveau pour le faire descendre dans l'image.
  // Elle s'approche doucement, puis plonge dans la scissure sur « expres ».
  const approach = ramp(t, 0.0, 3.0);
  const dive = ramp(t, 3.05, 4.40);
  const plunge = Math.pow(ramp(t, 3.7, 4.40), 2.2);   // derniere acceleration

  // point vise : le haut de la scissure, la ou la braise est la plus vive
  const fx = 0, fy = 0.30, fz = 0.10;
  const dist = 6.2 - 1.0 * approach - 2.0 * dive - 2.75 * plunge;
  const lookY = 0.55 - 0.85 * dive + (fy - (0.55 - 0.85)) * plunge;
  camera.position.set(
    fx,
    0.35 + (fy + 0.55 - 0.35) * dive,
    fz + dist,
  );
  camera.lookAt(fx, lookY, fz);

  // les sillons s'allument sur « expres »
  const burn = ramp(t, 2.72, 3.30) + 0.8 * plunge;
  brainMat.userData.uniforms.uBurn.value = burn;
  scene.background.setHex(0x07060a).lerp(new THREE.Color(0x2a0b0b), dive * 0.9);

  updateCoins(t);
  renderer.render(scene, camera);

  // --- composition 2D
  ctx.clearRect(0, 0, W, H);
  ctx.drawImage(glCanvas, 0, 0);

  // On finit englouti dans le rouge sombre du sillon : c'est le raccord
  // (en coupe) vers la savane a l'aube, pas un fondu.
  const sink = ramp(t, 4.05, 4.40);
  if (sink > 0) {
    const g = ctx.createRadialGradient(W / 2, H * 0.52, 0, W / 2, H * 0.52, H * (0.25 + 0.75 * sink));
    g.addColorStop(0, `rgba(110,42,36,${0.85 * sink})`);
    g.addColorStop(0.55, `rgba(58,14,12,${0.95 * sink})`);
    g.addColorStop(1, `rgba(26,6,6,${sink})`);
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, W, H);
  }

  drawTitle(t);
}

// --- boucle de rendu ---------------------------------------------------------
async function runRange(from, to) {
  for (let f = from; f <= to; f++) {
    renderAt(f / FPS);
    const img = ctx.getImageData(0, 0, W, H);
    await fetch(`/frame/${f}`, { method: "POST", body: img.data });
  }
}

window.FILM = {
  W, H, FPS,
  renderAt,
  runRange,
  // Charger explicitement chaque police : document.fonts.ready seul se resout
  // avant qu'une police jamais demandee ne soit telechargee, et l'image 0
  // sortait alors en police de secours.
  ready: (async () => {
    await Promise.all([
      document.fonts.load('100px "Instrument Serif"'),
      document.fonts.load('italic 100px "Instrument Serif"'),
      document.fonts.load('600 100px "Inter"'),
      document.fonts.load('400 100px "Inter"'),
    ]);
    await document.fonts.ready;
  })(),
};
