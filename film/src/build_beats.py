#!/usr/bin/env python3
"""Phrases calees sur la voix montee : beats_<v>.json (lu par motion.js, sfx.py, score.py)."""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
NB = " "
CTA_TEXT = {
    "ig": "Si tu souhaites y accéder, commente « Capital ».",
    "tt": "Si tu souhaites accéder à l'algorithme, le lien est en description.",
}
SKIP = {"Rien ne presse.", "L'historique, la FAQ et les conditions t'attendent sur notre Telegram.", "Lien en bio."}


def toks(p):
    out, pre = [], ""
    for t in p.split():
        if t == "«":                 # guillemet ouvrant : colle au mot SUIVANT
            pre = t + NB
        elif re.search(r"\w", t):
            out.append(pre + t); pre = ""
        elif out:
            out[-1] += NB + t        # « : », « ? », « » » colles au mot precedent
    return out


def build(v):
    H = json.loads((HERE / f"horloge_{v}.json").read_text(encoding="utf-8"))
    words = H["words"]
    phr = [l.strip() for l in (HERE / "voix_texte.txt").read_text(encoding="utf-8").splitlines()
           if l.strip() and l.strip() not in SKIP]
    i, beats = 0, []
    for p in phr:
        tk = toks(p)
        ws = words[i:i + len(tk)]
        i += len(tk)
        beats.append({"text": p, "start": ws[0]["start"], "end": ws[-1]["end"],
                      "words": [{"w": t, "s": w["start"], "e": w["end"]} for t, w in zip(tk, ws)]})
    if i != len(words):
        sys.exit(f"{v} : {i} mots dans le script, {len(words)} dans la voix")
    cta = H["cta"]
    ctext = CTA_TEXT[v]
    a, b = cta.get("speech", [cta["start"], cta["end"]])
    tk = toks(ctext)
    wts = [max(1, len(re.sub(r"[^\w]", "", t))) + 1.5 for t in tk]   # +1,5 : poids de l'articulation
    tot, acc, cw = sum(wts), a, []
    for t, w in zip(tk, wts):
        d = (b - a) * w / tot
        cw.append({"w": t, "s": round(acc, 3), "e": round(acc + d, 3)})
        acc += d
    beats.insert(len(beats) - 2, {"text": "CTA", "start": cta["start"], "end": cta["end"], "words": cw,
                                  "speech_end": b})
    (HERE / f"beats_{v}.json").write_text(json.dumps({"duration": H["duration"], "beats": beats}, ensure_ascii=False),
                                          encoding="utf-8")
    print(f"beats_{v}.json : {len(beats)} phrases, {i} mots")


if __name__ == "__main__":
    for v in sys.argv[1:] or ["ig", "tt"]:
        build(v)
