#!/usr/bin/env python3
"""Zem pro výhled z oken (vyhled.json → ground): ortofoto z katastr.py přepočtené
do souřadnic enginu (dům zarovnaný s osami, x = u + X0, z = Z0 - v).

    python3 zem_ortofoto.py podklady/site.json podklady/orto.jpg vyhled/vyhled-zem.jpg \
        --stred 12.6 9.0 --velikost 100 --X0 7 --Z0 14

Vypíše "rect" pro vyhled.json. Závislosti: pip install numpy pillow
"""
import argparse, json, math
import numpy as np
from PIL import Image

ap = argparse.ArgumentParser()
ap.add_argument("site"); ap.add_argument("orto"); ap.add_argument("out")
ap.add_argument("--stred", nargs=2, type=float, required=True, help="střed čtverce v souřadnicích enginu (x z)")
ap.add_argument("--velikost", type=float, default=100)
ap.add_argument("--px", type=int, default=2048)
ap.add_argument("--X0", type=float, required=True); ap.add_argument("--Z0", type=float, required=True)
a = ap.parse_args()

d = json.load(open(a.site)); th = d["angle"]; c, s = math.cos(th), math.sin(th)
O = np.asarray(Image.open(a.orto).convert("RGB")).astype(np.float32); H, W = O.shape[:2]
R = d["ortho"]["R"]; ocx, ocy = d["ortho"]["cx"], d["ortho"]["cy"]
cx, cz = a.stred; size, res = a.velikost, a.px
x0, z0 = cx - size / 2, cz - size / 2
i = (np.arange(res) + 0.5) / res * size
X, Z = np.meshgrid(x0 + i, z0 + i)                 # řádky = z (sever nahoře), sloupce = x
u, v = X - a.X0, a.Z0 - Z
e = u * c - v * s; n = u * s + v * c               # rámec domu → S-JTSK relativně k počátku
px = (e - (ocx - R)) / (2 * R) * W; py = ((ocy + R) - n) / (2 * R) * H
inside = (px >= 0) & (px < W - 1) & (py >= 0) & (py < H - 1)
px = np.clip(px, 0, W - 1.001); py = np.clip(py, 0, H - 1.001)
xi, yi = px.astype(int), py.astype(int); fx, fy = (px - xi)[..., None], (py - yi)[..., None]
img = O[yi, xi] * (1 - fx) * (1 - fy) + O[yi, xi + 1] * fx * (1 - fy) + O[yi + 1, xi] * (1 - fx) * fy + O[yi + 1, xi + 1] * fx * fy
img[~inside] = (118, 128, 92)
Image.fromarray(img.clip(0, 255).astype(np.uint8)).save(a.out, quality=86)
print(json.dumps({"rect": [round(x0, 3), round(z0, 3), size, size]}))
