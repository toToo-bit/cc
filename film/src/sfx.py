#!/usr/bin/env python3
"""Design sonore synthetise (0 credit) : effets cales sur l'animation.

Chaque effet est place sur le meme instant que l'animation qu'il accompagne
dans motion.js (memes reperes : S(i) = debut de la phrase i, T(i, mot) =
instant ou le mot est prononce). Sortie : assets/sfx_<variante>.wav (stereo).

Trois couches :
  - nappes d'ambiance (vent de la savane, tic-tac de la journee, tension) ;
  - ponctuations (impacts, montees, souffles de transition) ;
  - bruitages d'interface (pops, cliquetis, pieces, verre, notifications).
"""
import json
import sys
import unicodedata
import wave
from pathlib import Path

import numpy as np
from scipy.signal import butter, sosfilt

HERE = Path(__file__).resolve().parent
SR = 48000
RNG = np.random.default_rng(2610)


# ---------------------------------------------------------------- outils DSP
def tt(d):
    return np.arange(int(d * SR)) / SR


def bp(x, lo, hi, order=2):
    return sosfilt(butter(order, [lo, hi], btype="band", fs=SR, output="sos"), x)


def lp(x, f, order=2):
    return sosfilt(butter(order, f, btype="low", fs=SR, output="sos"), x)


def hp(x, f, order=2):
    return sosfilt(butter(order, f, btype="high", fs=SR, output="sos"), x)


def norm(x, peak=1.0):
    m = np.abs(x).max()
    return x / m * peak if m > 0 else x


def sweep(f0, f1, d, curve=1.0):
    t = tt(d)
    f = f0 + (f1 - f0) * (t / d) ** curve
    return np.sin(2 * np.pi * np.cumsum(f) / SR)


def env_ad(n, a, d_tau):
    """attaque lineaire (s) puis decroissance exponentielle (constante d_tau)."""
    t = np.arange(n) / SR
    e = np.minimum(1, t / max(a, 1e-4)) * np.exp(-np.maximum(0, t - a) / d_tau)
    return e


# ---------------------------------------------------------------- les sons
def s_pop(f=520):
    d = 0.16
    x = sweep(f * 1.8, f, d, 0.3) * env_ad(int(d * SR), 0.002, 0.035)
    x += 0.3 * hp(RNG.standard_normal(len(x)), 2000) * env_ad(len(x), 0.0005, 0.006)
    return norm(x, 0.8)


def s_tick(f=1900):
    d = 0.08
    t = tt(d)
    x = np.sin(2 * np.pi * f * t) * env_ad(len(t), 0.0005, 0.012)
    x += 0.5 * bp(RNG.standard_normal(len(t)), 2500, 7000) * env_ad(len(t), 0.0002, 0.004)
    return norm(x, 0.6)


def s_wood(f=900):
    d = 0.18
    t = tt(d)
    x = (np.sin(2 * np.pi * f * t) + 0.4 * np.sin(2 * np.pi * f * 2.7 * t)) * env_ad(len(t), 0.0005, 0.03)
    return norm(x, 0.7)


def s_ding(f=1320, d=1.6):
    t = tt(d)
    x = (np.sin(2 * np.pi * f * t) * np.exp(-t / 0.5)
         + 0.45 * np.sin(2 * np.pi * f * 2.76 * t) * np.exp(-t / 0.22)
         + 0.2 * np.sin(2 * np.pi * f * 5.4 * t) * np.exp(-t / 0.09))
    x *= np.minimum(1, t / 0.002)
    return norm(x, 0.55)


def s_coin():
    d = 0.9
    t = tt(d)
    x = np.zeros_like(t)
    for f in RNG.uniform(2600, 7600, 6):
        x += np.sin(2 * np.pi * f * t + RNG.uniform(0, 6)) * np.exp(-t / RNG.uniform(0.08, 0.35))
    x *= np.minimum(1, t / 0.0006)
    return norm(x, 0.45)


def s_whoosh(d=0.6, lo=300, hi=4500):
    n = int(d * SR)
    noise = RNG.standard_normal(n)
    # balayage du filtre : quatre bandes fondues pour simuler un passe-bande mobile
    out = np.zeros(n)
    bands = np.geomspace(lo, hi, 7)
    pos = np.linspace(0, 1, n)
    for i in range(len(bands) - 1):
        b = bp(noise, bands[i], bands[i + 1])
        c = i / (len(bands) - 2)
        w = np.exp(-((pos - c) ** 2) / 0.04)
        out += b * w
    out *= np.sin(np.pi * pos) ** 1.6
    return norm(out, 0.7)


def s_impact(f=52, d=1.6):
    t = tt(d)
    body = sweep(f * 2.2, f, d, 0.15) * np.exp(-t / 0.45)
    hit = lp(RNG.standard_normal(len(t)), 900) * np.exp(-t / 0.05)
    tail = lp(RNG.standard_normal(len(t)), 300) * np.exp(-t / 0.6) * 0.25
    x = body + 0.7 * hit + tail
    x *= np.minimum(1, t / 0.002)
    return norm(x, 0.42)   # souligne le mot cle sans le masquer


def s_thud():
    d = 0.4
    t = tt(d)
    x = sweep(160, 60, d, 0.4) * np.exp(-t / 0.07) + 0.4 * lp(RNG.standard_normal(len(t)), 500) * np.exp(-t / 0.03)
    return norm(x, 0.9)


def s_riser(d=1.6):
    t = tt(d)
    noise = hp(RNG.standard_normal(len(t)), 800)
    tone = sweep(180, 900, d, 2.0)
    e = (t / d) ** 2.2
    x = (0.6 * noise + 0.5 * tone) * e
    return norm(x, 0.7)


def s_shimmer(d=2.2, base=1760):
    t = tt(d)
    x = np.zeros_like(t)
    for k, mul in enumerate([1, 1.5, 2, 2.5, 3, 4]):
        f = base * mul * (1 + RNG.uniform(-0.004, 0.004))
        x += np.sin(2 * np.pi * f * t + RNG.uniform(0, 6)) * (0.8 ** k)
    x *= np.minimum(1, t / 0.25) * np.exp(-t / 0.9)
    x *= 1 + 0.3 * np.sin(2 * np.pi * 7 * t)
    return norm(x, 0.35)


def s_heart():
    d = 0.9
    t = tt(d)
    def beat(t0, a):
        u = np.maximum(0, t - t0)
        return a * np.sin(2 * np.pi * 55 * u) * np.exp(-u / 0.06) * (t >= t0)
    return norm(beat(0, 1) + beat(0.24, 0.7), 0.9)


def s_shatter():
    d = 1.2
    t = tt(d)
    x = hp(RNG.standard_normal(len(t)), 3000) * np.exp(-t / 0.12)
    for _ in range(40):
        t0 = RNG.uniform(0, 0.7) ** 1.6
        f = RNG.uniform(3000, 9000)
        u = np.maximum(0, t - t0)
        x += 0.5 * np.sin(2 * np.pi * f * u) * np.exp(-u / RNG.uniform(0.02, 0.08)) * (t >= t0)
    return norm(x, 0.7)


def s_bubble():
    d = 0.12
    x = sweep(300, 1400, d, 0.6) * env_ad(int(d * SR), 0.001, 0.03)
    return norm(x, 0.7)


def s_boing():
    d = 0.5
    t = tt(d)
    f = 260 + 120 * np.exp(-t / 0.15) * np.sin(2 * np.pi * 14 * t)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.18)
    return norm(x, 0.6)


def s_click():
    d = 0.05
    t = tt(d)
    x = bp(RNG.standard_normal(len(t)), 1500, 6000) * np.exp(-t / 0.006) + 0.6 * np.sin(2 * np.pi * 3200 * t) * np.exp(-t / 0.004)
    return norm(x, 0.6)


def s_key():
    d = 0.07
    t = tt(d)
    x = bp(RNG.standard_normal(len(t)), 900, 5000) * np.exp(-t / 0.01)
    return norm(x, 0.45)


def s_scratch(d=1.0):
    """plume sur papier : bruit filtre module par des micro-gestes."""
    t = tt(d)
    x = bp(RNG.standard_normal(len(t)), 2500, 8000)
    gest = 0.5 + 0.5 * np.sin(2 * np.pi * RNG.uniform(5, 9) * t + RNG.uniform(0, 6))
    gest *= 0.6 + 0.4 * np.abs(np.sin(2 * np.pi * 2.3 * t))
    x *= gest * np.minimum(1, t / 0.05) * np.minimum(1, (d - t) / 0.08)
    return norm(x, 0.35)


def s_fall(d=0.9):
    """glissando descendant un peu sale : le marche qui chute."""
    t = tt(d)
    x = sweep(700, 90, d, 0.7)
    x = np.round(x * 6) / 6  # leger effet numerique
    x *= np.exp(-t / 0.6) * np.minimum(1, t / 0.01)
    return norm(lp(x, 3000), 0.6)


def s_lock():
    a = s_click()
    b = s_thud() * 0.5
    out = np.zeros(int(0.45 * SR))
    out[: len(a)] += a
    k = int(0.07 * SR)
    out[k: k + len(b)] += b[: len(out) - k]
    return norm(out, 0.7)


def s_notif():
    a, b = s_ding(1568, 0.9), s_ding(2093, 1.0)
    out = np.zeros(int(1.3 * SR))
    out[: len(a)] += a
    k = int(0.13 * SR)
    out[k: k + len(b)] += b
    return norm(out, 0.55)


def s_chord_good():
    d = 1.3
    t = tt(d)
    x = sum(np.sin(2 * np.pi * f * t) for f in (523.3, 659.3, 784.0)) * np.exp(-t / 0.45) * np.minimum(1, t / 0.01)
    return norm(x, 0.45)


def s_chord_bad():
    d = 0.9
    t = tt(d)
    x = sum(np.sin(2 * np.pi * f * t) for f in (233.1, 246.9)) * np.exp(-t / 0.3) * np.minimum(1, t / 0.005)
    return norm(lp(x, 1500), 0.55)


# ---------------------------------------------------------------- nappes
def bed_wind(d):
    t = tt(d)
    x = lp(RNG.standard_normal(len(t)), 700)
    x *= 0.6 + 0.4 * np.sin(2 * np.pi * 0.23 * t) * np.sin(2 * np.pi * 0.11 * t + 1)
    x *= np.minimum(1, t / 1.0) * np.minimum(1, (d - t) / 0.8)
    return norm(x, 0.4)


def bed_drone(d, f=55):
    t = tt(d)
    x = np.sin(2 * np.pi * f * t) + 0.6 * np.sin(2 * np.pi * f * 1.007 * t) + 0.3 * np.sin(2 * np.pi * f * 2.01 * t)
    x *= np.minimum(1, t / 1.2) * np.minimum(1, (d - t) / 1.0)
    return norm(x, 0.5)


def bed_clock(d, period=0.5):
    out = np.zeros(int(d * SR))
    k = 0.0
    i = 0
    while k < d - 0.1:
        s = s_wood(1400 if i % 2 else 1150) * 0.5
        a = int(k * SR)
        out[a: a + len(s)] += s[: len(out) - a]
        k += period
        i += 1
    return out


# ---------------------------------------------------------------- cue sheet
def build(variant):
    data = json.loads((HERE / f"beats_{variant}.json").read_text(encoding="utf-8"))
    B, dur = data["beats"], data["duration"] + 1.5

    def nrm(w):
        w = unicodedata.normalize("NFD", w.lower())
        w = "".join(c for c in w if unicodedata.category(c) != "Mn")
        return "".join(c for c in w if c.isalnum() or c in "'’-")

    S = lambda i: B[i]["start"]
    E = lambda i: B[i]["end"]

    def T(i, w):
        n = nrm(w)
        for x in B[i]["words"]:
            if nrm(x["w"]).startswith(n):
                return x["s"]
        return S(i)

    cta = next(b for b in B if b["text"] == "CTA")
    c0 = cta["start"]

    cues = []  # (instant, son, gain, pan -1..1)

    def cue(t, snd, g=1.0, pan=0.0):
        cues.append((t, snd, g, pan))

    # transitions entre scenes (souffle juste avant la coupe)
    for i in [2, 8, 15, 19, 27, 34, 41, 45, 51, 60]:
        cue(S(i) - 0.5, s_whoosh(0.6), 0.55, RNG.uniform(-0.3, 0.3))

    # 1 · cerveau
    cue(0.0, s_impact(48, 2.0), 0.9)
    cue(0.05, s_scratch(1.3), 0.7)
    for i in range(9):
        cue(0.4 + i * 0.32 + 0.35, s_coin(), 0.45, (i - 4) / 6)
    cue(T(1, "expres") - 0.08, s_impact(42, 2.2), 1.0)
    cue(T(1, "expres") - 0.08, s_fall(1.0), 0.35)

    # 2 · savane
    cues.append((S(2), bed_wind(E(7) - S(2) + 0.6), 0.5, 0.0))
    cue(S(2), s_scratch(1.1), 0.6)
    cue(S(3) - 0.2, s_heart(), 0.8)
    for k in range(6):
        cue(S(4) + k * 0.11, s_thud(), 0.35, -0.2)
    cue(S(5), s_whoosh(0.35, 800, 7000), 0.8, 0.4)
    cue(T(6, "savane"), s_chord_good(), 0.7)
    cue(S(7) - 0.1, s_fall(1.2), 0.45)
    cue(T(7, "catastrophique"), s_thud(), 0.6)

    # 3 · pieges
    cue(S(8), s_tick(), 0.8)
    cue(S(9), s_riser(E(10) - S(9)), 0.55)
    for k in range(4):
        cue(S(9) + k * 0.1, s_pop(380 + k * 40), 0.35)
    cue(T(10, "haut"), s_pop(720), 1.0)
    cue(T(10, "haut"), s_impact(60, 1.0), 0.5)
    cue(S(11), s_fall(2.6), 0.45)
    cues.append((S(11), bed_drone(E(11) - S(11) + 0.6, 49), 0.45, 0.0))
    for k in range(3):
        cue(S(11) + 0.6 + k * 0.95, s_heart(), 0.7)
    cue(T(12, "revends"), s_pop(640), 0.9)
    cue(T(12, "revends") + 0.05, s_whoosh(0.3, 900, 6000), 0.5)
    cue(T(12, "tot"), s_shimmer(1.4, 1320), 0.6)
    for k in range(12):
        cue(T(13, "mises") + k * 0.1, s_coin(), 0.35, RNG.uniform(-0.4, 0.4))
    cue(T(14, "perds"), s_impact(45, 1.8), 1.0)
    for k in range(10):
        cue(T(14, "perds") + 0.15 + k * 0.07, s_coin(), 0.18, RNG.uniform(-0.8, 0.8))

    # 4 · journee
    cues.append((S(15) - 0.2, bed_clock(E(17) - S(15) + 0.4, 0.5), 0.35, 0.0))
    for w in ["reunions", "mails", "trajets"]:
        cue(T(15, w) - 0.05, s_pop(560), 0.8)
    for k in range(4):
        cue(T(15, "trajets") + 0.25 + (k + 3) * 0.12, s_pop(600 + k * 30), 0.5)
    for k in range(26):
        u = k / 25
        cue(T(16, "deja") + 1.9 * (1 - (1 - u) ** 2), s_tick(2200), 0.25)
    for k in range(4):
        cue(S(17) + k * 0.2, s_wood(700 - k * 110), 0.6)
    cues.append((S(18) - 0.15, bed_drone(E(18) - S(18) + 1.2, 41), 0.6, 0.0))
    cue(T(18, "trader"), s_impact(58, 1.2), 0.55)

    # 5 · la methode
    for k, d in enumerate([0, 0.1, 0.2]):
        cue(S(19) + d, s_pop(480 + k * 60), 0.6)
    cue(S(19) + 0.1, s_shimmer(1.8, 1760), 0.45)
    cue(T(20, "toi") - 0.3, s_pop(700), 0.8)
    cue(T(20, "pas"), s_whoosh(0.5, 1500, 7000), 0.35)
    cue(T(21, "retire") - 0.3, s_scratch(0.35), 0.8)
    cue(T(21, "retire"), s_whoosh(0.7, 200, 2500), 0.6)
    cue(T(21, "retire") + 0.55, s_thud(), 0.8)
    cue(T(22, "avant") - 0.05, s_impact(65, 1.4), 0.75)
    cue(S(23), s_shimmer(2.2, 2637), 0.7)
    for w in ["tout", "reuni"]:
        cue(T(24, w), s_ding(1760, 0.8), 0.45)
    cue(T(24, "agit") - 0.2, s_ding(1760, 0.8), 0.45)
    cue(T(24, "agit"), s_chord_good(), 0.6)
    cue(S(25), s_chord_bad(), 0.6)
    cue(T(26, "limite"), s_scratch(0.6), 0.6)
    cue(T(26, "posee"), s_thud(), 0.6)

    # 6 · Compound Capital
    cue(T(27, "pros") + 0.2, s_whoosh(0.5, 200, 1500), 0.5)
    cue(T(27, "pros") + 0.8, s_thud(), 0.7)
    cue(T(28, "compound") - 1.5, s_riser(1.5), 0.6)
    cue(T(28, "compound") - 0.12, s_impact(55, 2.4), 0.9)
    cue(T(28, "compound") - 0.12, s_shimmer(2.8, 1318), 0.7)
    cue(S(29) - 0.05, s_coin(), 0.7)
    cue(S(29) - 0.05, s_ding(1318, 1.4), 0.4)
    cue(T(30, "seul"), s_whoosh(0.7, 500, 6000), 0.6)
    for k in range(4):
        cue(T(31, "chiffres") - 0.3 + k * 0.22 + 0.6, s_tick(1600 + 200 * k), 0.5, -0.4)
    for k in range(3):
        cue(T(31, "rumeurs") - 0.4 + k * 0.2 + 0.45, s_boing(), 0.45, 0.5)
    for k in range(5):
        cue(T(32, "lundi") + k * 0.2, s_wood(1250 if k < 4 else 1700), 0.75, (k - 2) / 3)
    for w in ["graphique", "signal", "cliquer"]:
        cue(T(33, w) - 0.4, s_pop(520), 0.5)
        cue(T(33, w), s_scratch(0.25), 0.7)

    # 7 · concretement
    cue(S(34) - 0.1, s_whoosh(0.6, 300, 3000), 0.6)
    cue(S(35), s_pop(600), 0.6)
    cue(S(36), s_riser(0.9) * 0.6, 0.5)
    cue(T(37, "l'acces"), s_click(), 1.0)
    cue(T(37, "l'acces") + 0.25, s_ding(2093, 0.9), 0.5)
    for k in range(2):
        cue(T(38, "copie") + k * 0.5, s_whoosh(0.45, 1000, 7000), 0.5, -0.5 + k * 0.3)
        cue(T(38, "copie") + k * 0.5 + 0.4, s_pop(820), 0.6)
    cue(S(39) + 0.2, s_lock(), 0.9)
    cue(T(40, "arreter"), s_click(), 0.9)
    cue(T(40, "arreter") + 0.02, s_wood(600), 0.5)

    # 8 · l'escalier
    steps = [0, 1, 1, 2, 1, 3, 3, 4]
    for i in range(1, len(steps) + 1):
        # instant ou la i-ieme marche apparait (n = round(lerp(1, 8, eio(..))))
        for k in range(2000):
            tk = S(41) + 2.2 * k / 1999
            x = (tk - S(41)) / 2.2
            e = 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2
            if round(1 + (len(steps) - 1) * e) >= i:
                cue(tk, s_wood(520 + 80 * steps[i - 1]), 0.6)
                break
    for i, s in enumerate(steps):
        if i > 0 and s > max(steps[:i]):
            cue(T(42, "gains") + i * 0.12, s_coin(), 0.5)
    cue(T(44, "progresse") - 0.4, s_riser(0.8), 0.45)
    cue(T(44, "progresse") + 0.4, s_chord_good(), 0.55)

    # 9 · la preuve
    cue(S(45) + 0.2, s_bubble(), 0.5)
    cue(T(45, "l'air") + 0.05, s_pop(900), 1.0)
    cue(T(45, "capture") + 0.1, s_shatter(), 0.9)
    cue(S(46), s_scratch(2.6), 0.6)
    for i in range(3):
        cue(S(46) + 1.0 + i * 0.4, s_pop(420), 0.5)
    for w in ["reel", "verifiable", "myfxbook"]:
        cue(T(46, w), s_pop(700), 0.6)
    cue(S(47) - 0.2, s_whoosh(0.8, 400, 3000), 0.4)
    for i in range(3):
        for k in range(4):
            cue(T(49, "compris") - 0.6 + i * 0.35 + k * 0.27, s_thud(), 0.18, -0.3)
    cue(T(50, "presses") - 0.5 + 0.4, s_thud(), 0.5)
    cue(T(50, "presses") - 0.5 + 0.42, s_boing(), 0.4)

    # 10 · imagine
    cues.append((S(51) - 0.2, bed_drone(E(53) - S(51) + 0.8, 65), 0.3, 0.0))
    cue(S(52), s_whoosh(0.7, 200, 1800), 0.5)
    cue(T(53, "ouvres"), s_whoosh(0.5, 600, 4000), 0.5)
    cue(S(54), s_notif(), 0.8)
    for bi, w in [(55, "stress"), (56, "ecran"), (57, "toi")]:
        cue(T(bi, w) - 0.15, s_pop(560), 0.6)
        cue(T(bi, w) + 0.1, s_scratch(0.25), 0.6)
    cue(S(58), s_scratch(0.5), 0.5)
    for i in range(3):
        cue(S(59) + i * 0.12, s_ding(1760 + i * 220, 0.7), 0.35)

    # 11 · appel a l'action et fin
    c_end = cta.get("speech_end", cta["end"])
    cue(c0 + 0.2, s_whoosh(max(2.4, c_end - c0), 300, 2500), 0.4)
    if variant == "ig":
        for k in range(7):
            cue(T(60, "capital") + k * 0.1, s_key(), 0.8)
        cue(T(60, "capital") + 0.75, s_click(), 0.8)
        cue(c_end + 0.1, s_notif(), 0.8)
    else:
        cue(T(60, "lien") - 0.1, s_pop(700), 0.7)
    cue(S(61) - 0.2, s_impact(50, 2.6), 0.8)
    cue(S(61) - 0.2, s_shimmer(3.0, 1318), 0.6)
    cue(S(61) + 0.2, s_pop(640), 0.6)

    # -------- mixage des cues
    n = int(dur * SR)
    L, R = np.zeros(n), np.zeros(n)
    for t0, snd, g, pan in cues:
        a = int(max(0, t0) * SR)
        if a >= n:
            continue
        s = snd[: n - a] * g
        L[a: a + len(s)] += s * np.sqrt((1 - pan) / 2) * 1.41
        R[a: a + len(s)] += s * np.sqrt((1 + pan) / 2) * 1.41
    st = np.stack([L, R], axis=1)
    st = norm(st, 0.9)

    out = HERE.parent / "assets" / f"sfx_{variant}.wav"
    with wave.open(str(out), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((st * 32767).astype("<i2").tobytes())
    print(f"{out.name} : {len(cues)} effets, {n/SR:.1f}s")


if __name__ == "__main__":
    for v in sys.argv[1:] or ["ig", "tt"]:
        build(v)
