#!/usr/bin/env python3
"""Generer app-ikonene fra originalen.

    python3 assets/lag-ikoner.py

Skriver icon-180/192/512.png til garasjeport_web/.

Hvorfor fullflate: apple-touch-icon skal IKKE ha runde hjørner selv. iOS
legger på sin egen squircle-maske, så et ikon med gjennomsiktige hjørner blir
rundet to ganger og får mørke kanter. Originalen har runde hjørner bakt inn,
så vi fyller hjørnene med bakgrunnsfargen.
"""
import os
from collections import Counter

from PIL import Image

HER = os.path.dirname(os.path.abspath(__file__))
KILDE = os.path.join(HER, "garasje-original.png")
UT = os.path.join(os.path.dirname(HER), "garasjeport_web")
STORRELSER = (180, 192, 512)


def bakgrunnsfarge(im):
    """Vanligste ugjennomsiktige farge i kantbeltet = det flate feltet."""
    w, h = im.size
    px = im.load()
    b = int(w * 0.09)
    c = Counter()
    for x in range(w):
        for y in range(h):
            if (x < b or x >= w - b or y < b or y >= h - b) and px[x, y][3] > 250:
                c[px[x, y][:3]] += 1
    return c.most_common(1)[0][0]


def main():
    src = Image.open(KILDE).convert("RGBA")
    bg = bakgrunnsfarge(src)
    print("bakgrunnsfarge: #%02x%02x%02x" % bg)
    flat = Image.new("RGB", src.size, bg)
    flat.paste(src, (0, 0), src)
    for px_size in STORRELSER:
        sti = os.path.join(UT, "icon-%d.png" % px_size)
        flat.resize((px_size, px_size), Image.LANCZOS).save(sti)
        print("skrev", os.path.relpath(sti, os.path.dirname(HER)))
    print("\nHusk: manifest.background_color i app.py bør matche "
          "bakgrunnsfargen over.")


if __name__ == "__main__":
    main()
