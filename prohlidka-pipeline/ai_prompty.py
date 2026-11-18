#!/usr/bin/env python3
"""Zadání AI fotek pro každou pozici v tour.json.

Z tour.json a souboru se styly místností vytvoří ai_zadani.json: pro každou fotku
render (podklad kompozice), volitelnou skutečnou fotku (podklad stylu) a prompt.
Generuje se v Higgsfieldu modelem Nano Banana 2 (1k, 3:2, asi 1,5 kreditu za fotku):
obrázek 1 = render z render_pozice.js, obrázek 2 = skutečná fotka z inzerátu.

    python3 ai_prompty.py tour.json styly.json rendery/ > ai_zadani.json

styly.json (klíč = roomId z tour.json, "*" = výchozí):
{
  "*":       {"popis": "light oak laminate floor, white walls, white PVC windows"},
  "obyvak":  {"popis": "blue-grey velvet sofa, oak wood-panelled TV wall", "reference": "inzerat/obyvak.jpg"},
  "koupelna-1np": {"popis": "large-format light grey porcelain tiles, glass shower, chrome"}
}
"""
import json, os, sys

tour = json.load(open(sys.argv[1], encoding="utf-8"))
styly = json.load(open(sys.argv[2], encoding="utf-8"))
rendery = sys.argv[3]
rooms = {r["id"]: r["name"] for r in tour["apartment"]["rooms"]}

SABLONA = ("Turn image 1 (a 3D render of {mistnost} in a Czech family house) into a professional real-estate photograph. "
           "Keep exactly the camera angle, room shape, walls, sloped ceilings, windows, doors and furniture placement of image 1. "
           "{styl_ref}Interior: {popis}. Bright natural daylight, high dynamic range, wide-angle 16 mm lens, straight verticals, "
           "realistic textures, tidy staged look. No people, no text, no watermark, no round UI markers.")

out = []
for ph in tour["photos"]:
    st = {**styly.get("*", {}), **styly.get(ph["roomId"], {})}
    ref = st.get("reference")
    out.append({
        "id": ph["id"],
        "render": os.path.join(rendery, ph["id"] + ".png"),
        "reference": ref,
        "model": "nano_banana_2", "resolution": "1k", "aspect_ratio": "3:2",
        "prompt": SABLONA.format(mistnost=f"the room '{rooms.get(ph['roomId'], ph['roomId'])}' ({ph.get('title', '')})",
                                 styl_ref="Match the materials and style of image 2, a real photo from the same house. " if ref else "",
                                 popis=st.get("popis", "light oak floor, white walls")),
    })
json.dump(out, sys.stdout, ensure_ascii=False, indent=1)
