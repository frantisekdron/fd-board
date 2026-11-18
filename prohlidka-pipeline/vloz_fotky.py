#!/usr/bin/env python3
"""Vloží hotové AI fotky do prohlídky: zmenší na fotky/foto-XX.jpg (1500 px) a fotky/mini-XX.jpg,
a do popisku fotky v tour.json doplní, že jde o AI vizualizaci.

    python3 vloz_fotky.py ai_vystup/ prohlidka/tours/demo/

ai_vystup/ obsahuje soubory pojmenované podle id fotky (foto-01.png, foto-02.jpg …).
Závislosti: pip install pillow
"""
import json, os, sys
from PIL import Image

src, dest = sys.argv[1], sys.argv[2]
os.makedirs(os.path.join(dest, "fotky"), exist_ok=True)
tp = os.path.join(dest, "tour.json")
tour = json.load(open(tp, encoding="utf-8"))
hotove = 0
for ph in tour["photos"]:
    kand = [f for f in os.listdir(src) if os.path.splitext(f)[0] == ph["id"]]
    if not kand:
        print("chybí", ph["id"]); continue
    im = Image.open(os.path.join(src, kand[0])).convert("RGB")
    n = ph["id"].split("-")[1]
    big = im.copy(); big.thumbnail((1500, 1000)); big.save(os.path.join(dest, "fotky", f"foto-{n}.jpg"), quality=84)
    mini = im.copy(); mini.thumbnail((240, 160)); mini.save(os.path.join(dest, "fotky", f"mini-{n}.jpg"), quality=75)
    ph["aspect"] = round(im.width / im.height, 4)
    if "AI vizualizace" not in ph.get("caption", ""):
        ph["caption"] = (ph.get("caption", "") + " (AI vizualizace podle 3D modelu)").strip()
    hotove += 1
json.dump(tour, open(tp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"Vloženo {hotove} z {len(tour['photos'])} fotek.")
