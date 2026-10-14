#!/usr/bin/env python3
"""Construit les consignes de patch2.py a partir des reperes OCR (scan_telegram.py).

  python3 -I build_patch_specs.py hits.json [hits2.json ...] DOSSIER_SORTIE
"""
import json
import re
import sys
from pathlib import Path

# (motif OCR, texte d'origine exact, nouveau texte, police, graisse)
RULES = [
    (r"Rejoins le", "Rejoins le Telegram.", "Lien en description.", "serif", None),
    (r"envoie le lien du", "Je t’envoie le lien du Telegram en message.", "Je t’envoie le lien en message.", "sans", None),
    (r"historique Compound", "L’historique Compound Capital est sur le Telegram.",
     "L’historique Compound Capital est dans le lien.", "serif_i", None),
    (r"gestion du risque", "Notre gestion du risque, expliquée sur le Telegram.",
     "Notre gestion du risque, expliquée via le lien.", "sans", None),
    (r"gles qui le contournent", "Les règles qui le contournent : sur le Telegram.",
     "Les règles qui le contournent : dans le lien.", "sans", None),
    (r"mesure exactement", "Ce qu’il mesure exactement : sur le Telegram.",
     "Ce qu’il mesure exactement : dans le lien.", "sans", None),
    (r"tre est publi", "Le nôtre est publié sur le Telegram.", "Le nôtre est publié, voir le lien.", "sans", None),
    (r"on les d", "on les détaille sur le Telegram.", "on les détaille dans le lien.", "sans", 460),
    (r"une par une", "une par une, sur le Telegram.", "une par une, dans le lien.", "sans", 460),
    (r"^\W*sur le", "sur le Telegram", "dans le lien", "sans", 500),
]

LABEL = {"t_from_end": 6.0, "box": [98, 1056, 610, 1080], "old": "POUR RECEVOIR LE LIEN DU TELEGRAM",
         "keep": "POUR RECEVOIR LE LIEN", "m": [6, 4, 20, 4]}
LABEL_VIDEOS = ("07_Jeu15_12h30_Note03_Backtest_IG", "10_Ven16_19h30_Note02_Verifier_IG", "13_Dim18_12h30_Note04_Demonte_IG")


def groups(hits):
    gs = []
    for h in hits:
        g = next((g for g in gs if abs(g["box"][1] - h["box"][1]) < 25 and abs(h["t"] - g["t1"]) <= 1.0), None)
        if g:
            g["t1"] = h["t"]
            g["texts"].append(h["text"])
            g["box"] = [min(g["box"][0], h["box"][0]), min(g["box"][1], h["box"][1]),
                        max(g["box"][2], h["box"][2]), max(g["box"][3], h["box"][3])]
        else:
            gs.append({"t0": h["t"], "t1": h["t"], "box": list(h["box"]), "texts": [h["text"]]})
    return gs


def main(args):
    out = Path(args[-1])
    out.mkdir(parents=True, exist_ok=True)
    for hp in args[:-1]:
        for v in json.loads(Path(hp).read_text(encoding="utf-8")):
            name = Path(v["file"]).stem
            lines = []
            for g in groups(v["hits"]):
                txt = max(g["texts"], key=len)
                rule = next((r for r in RULES if re.search(r[0], txt)), None)
                if not rule:
                    sys.exit(f"{name} : aucune regle pour « {txt} »")
                _, old, new, fnt, wgt = rule
                L = {"t": [g["t0"], g["t1"]], "box": g["box"], "old": old, "new": new, "font": fnt}
                if wgt:
                    L["weight"] = wgt
                lines.append(L)
            # fusion des doublons (meme regle, fenetres qui se touchent)
            merged = []
            for L in sorted(lines, key=lambda x: x["t"][0]):
                m = next((M for M in merged if M["old"] == L["old"] and L["t"][0] <= M["t"][1] + 1.5
                          and abs(M["box"][1] - L["box"][1]) < 60), None)
                if m:
                    m["t"][1] = max(m["t"][1], L["t"][1])
                    m["box"] = [min(m["box"][0], L["box"][0]), min(m["box"][1], L["box"][1]),
                                max(m["box"][2], L["box"][2]), max(m["box"][3], L["box"][3])]
                else:
                    merged.append(L)
            lines = merged
            if name in LABEL_VIDEOS:
                d = v["duration"]
                lines.append({"t": [d - LABEL["t_from_end"], d], "box": LABEL["box"], "old": LABEL["old"],
                              "keep": LABEL["keep"], "m": LABEL["m"]})
            (out / f"{name}.json").write_text(json.dumps({"lines": lines}, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"{name} : {len(lines)} ligne(s)")


if __name__ == "__main__":
    main(sys.argv[1:])
