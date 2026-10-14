#!/usr/bin/env python3
"""Monte la piste voix definitive et produit l'horloge du film.

La prise Kenzy est livree d'un bloc. Deux operations la transforment en piste
de montage :

  1. des respirations sont inserees apres certains mots, pour poser le rythme ;
  2. l'appel a l'action generique (« … sur notre Telegram. Lien en bio. ») est
     retire et remplace par celui de la plateforme, avant de reprendre sur la
     signature « Compound Capital. Comprendre avant de decider. ».

Sortie : la piste WAV, et un JSON qui donne pour chaque mot sa place sur la
timeline finale. C'est ce JSON qui cale l'image, les sous-titres et les plans.
"""
import json
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ASSETS = HERE.parent / "assets"
SR = 48000

# Respirations : (mot concerne, occurrence, duree ajoutee apres ce mot)
RESPIRATIONS = [
    ("expres.", 0, 0.60),
    ("marches.", 0, 0.30),
    ("plus.", 0, 0.50),
    ("trader", 0, 0.60),
    ("l'equation.", 0, 0.30),
    ("d'entrer.", 0, 0.40),
    ("pros.", 0, 0.30),
    ("toi.", 0, 0.50),      # « … construit pour toi. »
    ("cliquer.", 0, 0.40),
    ("veux.", 0, 0.40),
    ("progresse.", 0, 0.40),
    ("presses.", 0, 0.60),
    ("toi.", 2, 0.40),      # « Sans toi. »
    ("discipline.", 0, 0.35),
]

# Coupe de l'appel a l'action generique.
CTA_IN = "L'historique,"     # premier mot retire
CTA_OUT = "Compound"         # reprise sur la signature (2e occurrence)


def decode(path: Path) -> np.ndarray:
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-f", "s16le",
         "-acodec", "pcm_s16le", "-ar", str(SR), "-ac", "1", "-"],
        capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


def write_wav(path: Path, data: np.ndarray):
    clipped = np.clip(data, -1.0, 1.0)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((clipped * 32767).astype("<i2").tobytes())


def speech_bounds(x, thr=0.02):
    """debut et fin de la parole (enveloppe lissee sur 10 ms, seuil a 6 % du maximum)."""
    env = np.convolve(np.abs(x), np.ones(480) / 480, mode="same")
    idx = np.where(env > 0.06 * env.max())[0]
    return idx[0] / SR, idx[-1] / SR


def main(variant="ig"):
    # version « algorithme » (6 phrases reenregistrees) si elle existe
    algo = (ASSETS / "voix_main_algo.wav").exists() and (HERE / "words_scribe_algo.json").exists()
    meta = json.loads((HERE / ("words_scribe_algo.json" if algo else "words_scribe.json")).read_text(encoding="utf-8"))
    words = [{"w": w, "start": s, "end": e} for w, s, e in meta["words"]]

    main_a = decode(ASSETS / ("voix_main_algo.wav" if algo else "voix_main.mp3"))
    cta_file = "voix_cta_a.mp3" if variant == "ig" else "voix_cta_b.mp3"
    if (ASSETS / f"voix_cta2_{variant}.mp3").exists():      # fin concise (14/10)
        cta_file = f"voix_cta2_{variant}.mp3"
    cta_a = decode(ASSETS / cta_file)

    # --- reperer les mots cles -------------------------------------------
    def nth(word, n):
        hits = [i for i, x in enumerate(words) if x["w"] == word]
        if len(hits) <= n:
            sys.exit(f"mot introuvable : {word} (occurrence {n})")
        return hits[n]

    cut_in = nth(CTA_IN, 0)            # premier mot du CTA generique
    cut_out = nth(CTA_OUT, 1)          # « Compound » de la signature finale

    # point de coupe : au milieu du silence qui precede chaque borne
    def gap_mid(i):
        return (words[i - 1]["end"] + words[i]["start"]) / 2

    t_cut_in = gap_mid(cut_in)         # fin de « … la discipline. » + release
    t_cut_out = words[cut_out]["start"] - 0.22   # attaque reelle, avec elan

    # --- respirations, converties en insertions datees --------------------
    inserts = []
    for word, occ, dur in RESPIRATIONS:
        i = nth(word, occ)
        if words[i]["end"] >= t_cut_in:
            continue  # au-dela de la coupe : gere par le raccord
        t = gap_mid(i + 1) if i + 1 < len(words) else words[i]["end"] + 0.1
        inserts.append((t, dur))
    inserts.sort()

    # --- montage ----------------------------------------------------------
    pieces = []          # (type, payload)
    mapping = []         # (t_source_debut, t_source_fin, decalage)
    out_t = 0.0
    src_t = 0.0

    def push_audio(a, b):
        nonlocal out_t, src_t
        seg = main_a[int(a * SR):int(b * SR)]
        pieces.append(seg)
        mapping.append((a, b, out_t - a))
        out_t += len(seg) / SR
        src_t = b

    def push_silence(d):
        nonlocal out_t
        pieces.append(np.zeros(int(d * SR), dtype=np.float32))
        out_t += d

    for t, dur in inserts:
        push_audio(src_t, t)
        push_silence(dur)
    push_audio(src_t, t_cut_in)

    # respiration de raccord, puis CTA de la plateforme
    push_silence(0.35)
    cta_start = out_t
    pieces.append(cta_a)
    out_t += len(cta_a) / SR
    push_silence(0.28)

    # signature finale, reprise dans la prise d'origine
    sig_start = out_t
    push_audio(t_cut_out, len(main_a) / SR)

    track = np.concatenate(pieces)
    out_wav = ASSETS / f"voix_{variant}.wav"
    write_wav(out_wav, track)

    # --- horloge finale ----------------------------------------------------
    def to_final(t):
        for a, b, off in mapping:
            if a - 1e-6 <= t <= b + 1e-6:
                return t + off
        return None

    final_words = []
    for w in words:
        if words.index(w) >= cut_in and words.index(w) < cut_out:
            continue  # mots du CTA generique, retires
        ft = to_final(w["start"])
        fe = to_final(w["end"])
        if ft is None:
            continue
        final_words.append({"w": w["w"], "start": round(ft, 3), "end": round(fe, 3)})

    clock = {
        "variant": variant,
        "duration": round(len(track) / SR, 3),
        "cta": {"start": round(cta_start, 3), "end": round(cta_start + len(cta_a) / SR, 3),
                "source": cta_file,
                # bornes de la parole dans la phrase (hors silences de tete et de queue)
                "speech": [round(cta_start + x, 3) for x in speech_bounds(cta_a)]},
        "signature_start": round(sig_start, 3),
        "words": final_words,
    }
    (HERE / f"horloge_{variant}.json").write_text(
        json.dumps(clock, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"{out_wav.name} : {clock['duration']:.2f}s "
          f"(CTA {clock['cta']['start']:.2f}-{clock['cta']['end']:.2f}, "
          f"signature a {sig_start:.2f})")
    return clock


if __name__ == "__main__":
    for v in ("ig", "tt"):
        main(v)
