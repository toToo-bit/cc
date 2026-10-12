// Le cerveau du plan d'ouverture.
//
// Recette (reprise des notes v3) : une icosphere tres dense, fusionnee, ecrasee
// en ellipsoide 0,80 / 0,70 / 1,0, creusee d'une scissure mediane, puis sillonnee
// par les lignes de niveau zero d'un bruit simplex deforme (frequence 2,6,
// largeur 0,14). Un attribut « groove » par sommet porte la profondeur du sillon :
// c'est lui qui allume la lueur bordeaux quand le cerveau « brule ».

import * as THREE from "three";
import { mergeVertices } from "three/addons/utils/BufferGeometryUtils.js";
import { makeNoise3D } from "./noise.js";

export const FREQ = 2.6;
export const WIDTH = 0.30;

export function buildBrainGeometry(detail = 112) {
  const noise = makeNoise3D(20261012);
  let geo = new THREE.IcosahedronGeometry(1, detail);
  geo = mergeVertices(geo, 1e-5);

  const pos = geo.attributes.position;
  const n = pos.count;
  const groove = new Float32Array(n);
  const v = new THREE.Vector3();

  const smoothstep = (x) => { const c = Math.min(1, Math.max(0, x)); return c * c * (3 - 2 * c); };

  for (let i = 0; i < n; i++) {
    v.fromBufferAttribute(pos, i);

    // --- forme generale ------------------------------------------------------
    const dir = v.clone().normalize();
    let r = 1.0;
    r += 0.030 * Math.sin(dir.y * 3.1) * Math.cos(dir.z * 2.2);   // bosses douces
    r -= 0.075 * Math.max(0, dir.z) ** 2;                         // front qui fuit
    r -= 0.055 * Math.max(0, -dir.y) * Math.max(0, dir.z);        // dessous avant

    // base aplatie : un cerveau pose, pas une bille
    const under = smoothstep((-dir.y - 0.45) / 0.55);
    r -= under * 0.085;

    // cervelet : un renflement arriere-bas
    const cz = dir.z + 0.72, cy = dir.y + 0.52;
    const cereb = Math.exp(-(cz * cz * 7.0 + cy * cy * 6.0));
    r += cereb * 0.085;

    // --- champ des sillons ---------------------------------------------------
    // Bruit deforme par un second bruit, avec une anisotropie : les sillons
    // s'etirent d'avant en arriere au lieu de craqueler comme de la terre seche.
    const AX = 1.00, AY = 1.55, AZ = 0.78;
    const wx = noise(dir.x * 1.9 + 11.3, dir.y * 1.9, dir.z * 1.9) * 0.55;
    const wy = noise(dir.x * 1.9, dir.y * 1.9 + 7.1, dir.z * 1.9) * 0.55;
    const wz = noise(dir.x * 1.9, dir.y * 1.9, dir.z * 1.9 + 3.9) * 0.55;

    let field = noise(
      dir.x * FREQ * AX + wx,
      dir.y * FREQ * AY + wy,
      dir.z * FREQ * AZ + wz,
    );
    // seconde octave : des circonvolutions dans les circonvolutions
    field += 0.18 * noise(
      dir.x * FREQ * AX * 2.3 + wx * 1.7 + 31.0,
      dir.y * FREQ * AY * 2.3 + wy * 1.7,
      dir.z * FREQ * AZ * 2.3 + wz * 1.7,
    );

    // Profil des circonvolutions : le sillon est la ligne de niveau zero,
    // la crete monte en arrondi de part et d'autre. h = 0 au fond, 1 en haut.
    const a = Math.min(1.0, Math.abs(field) / WIDTH);
    const h = Math.sqrt(a * (2 - a));          // quart de cercle : crete ronde
    let g = 1.0 - h;

    // --- scissure mediane ----------------------------------------------------
    const mid = 1.0 - Math.min(1.0, Math.abs(dir.x) / 0.075);
    const fissure = smoothstep(mid) * Math.max(0, dir.y * 0.9 + 0.35);
    g = Math.max(g, fissure);

    // les sillons se creusent moins sur le dessous, comme sur un vrai cerveau
    const depth = 0.075 * (1.0 - 0.45 * under);
    r -= g * depth;
    // la scissure, elle, tranche profond
    r -= fissure * 0.075;

    v.copy(dir).multiplyScalar(r);
    v.x *= 0.80;
    v.y *= 0.70;
    v.z *= 1.0;

    pos.setXYZ(i, v.x, v.y, v.z);
    groove[i] = Math.min(1, g + fissure * 0.6);
  }

  geo.setAttribute("groove", new THREE.BufferAttribute(groove, 1));
  geo.computeVertexNormals();
  return geo;
}

// Materiau argile mate, avec une lueur bordeaux injectee dans les sillons.
// On passe par onBeforeCompile pour garder l'eclairage physique de three
// tout en ajoutant notre terme d'emission.
export function makeBrainMaterial({ clay = 0x4a423c, ember = 0x6e2a24 } = {}) {
  const mat = new THREE.MeshPhysicalMaterial({
    color: new THREE.Color(clay),
    roughness: 0.86,
    metalness: 0.0,
    clearcoat: 0.10,
    clearcoatRoughness: 0.7,
    sheen: 0.35,
    sheenRoughness: 0.85,
    sheenColor: new THREE.Color(0x6b5c52),
  });

  mat.userData.uniforms = {
    uBurn: { value: 0.0 },      // 0 = eteint, 1 = sillons incandescents
    uEmber: { value: new THREE.Color(ember) },
    uGrooveShade: { value: 0.55 }, // assombrissement du fond des sillons
  };

  mat.onBeforeCompile = (shader) => {
    Object.assign(shader.uniforms, mat.userData.uniforms);

    shader.vertexShader = shader.vertexShader
      .replace("#include <common>", `#include <common>
        attribute float groove;
        varying float vGroove;`)
      .replace("#include <begin_vertex>", `#include <begin_vertex>
        vGroove = groove;`);

    shader.fragmentShader = shader.fragmentShader
      .replace("#include <common>", `#include <common>
        uniform float uBurn;
        uniform vec3 uEmber;
        uniform float uGrooveShade;
        varying float vGroove;`)
      // assombrir le fond des sillons : l'occlusion locale fait la sculpture
      .replace("#include <color_fragment>", `#include <color_fragment>
        diffuseColor.rgb *= mix(1.0, uGrooveShade, clamp(vGroove, 0.0, 1.0));`)
      // puis y injecter la braise
      .replace("#include <output_fragment>", `
        float ember = smoothstep(0.25, 1.0, vGroove) * uBurn;
        vec3 glow = uEmber * ember * 2.6;
        gl_FragColor = vec4(outgoingLight + glow, diffuseColor.a);
        #include <tonemapping_fragment>
        #include <colorspace_fragment>
      `)
      // three 0.169 utilise opaque_fragment ; on couvre les deux noms
      .replace("#include <opaque_fragment>", `
        float ember = smoothstep(0.25, 1.0, vGroove) * uBurn;
        vec3 glow = uEmber * ember * 2.6;
        gl_FragColor = vec4(outgoingLight + glow, diffuseColor.a);
      `);
  };

  return mat;
}
