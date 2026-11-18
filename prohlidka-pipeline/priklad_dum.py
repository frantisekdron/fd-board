#!/usr/bin/env python3
"""Ukázka: jednoduchý přízemní dům 10 × 8 m se sedlovou střechou, dvěma místnostmi,
zahradou, televizí s fotkami a dvěma pozicemi fotek. Spuštění:

    python3 priklad_dum.py tour.json

Skutečnou zakázku postav stejně: rozměry z půdorysu (v metrech v rámci domu),
obrys a natočení z katastr.py, fotky přes render_pozice.js + AI.
"""
import sys
from tour_lib import Tour, save

t = Tour(X0=10, Z0=20)
L = "1np"
# obvodové stěny (tloušťka 0,3 m), jih v = 0..0.3, sever v = 7.7..8
t.wall_u("jih", L, 0, 10, 0, 0.3, exterior=True, openings=[t.door(2.0, 3.0, "dv-zahrada", hi=2.2, glazed=True), t.win(6, 8, 0.5, 2.2)])
t.wall_u("sever", L, 0, 10, 7.7, 8.0, exterior=True, openings=[t.door(4.5, 5.5, "dv-vstup", hi=2.1, open=False, label="Vstupní dveře")])
t.wall_v("zapad", L, 0, 8, 0, 0.3, exterior=True, openings=[t.win(3, 5, 0.9, 2.2)])
t.wall_v("vychod", L, 0, 8, 9.7, 10, exterior=True, openings=[t.win(3, 4.5, 0.9, 2.2)])
t.wall_v("pricka", L, 0.3, 7.7, 6.0, 6.12, openings=[t.door(5.5, 6.3, "dv-loznice", swing=-1)])

t.room("obyvak", "Obývací pokoj s kuchyní", L, [(0.3, 0.3), (6.0, 0.3), (6.0, 7.7), (0.3, 7.7)], "oakGreige", 42.2,
       lights=[(3, 4)], wall="white", lightId="sw-obyvak")
t.room("loznice", "Ložnice", L, [(6.12, 0.3), (9.7, 0.3), (9.7, 7.7), (6.12, 7.7)], "oakGreige", 26.5, lights=[(8, 4)], wall="white")
t.room("zahrada", "Zahrada", L, [(-4, -10), (14, -10), (14, -0.01), (-4, -0.01)], "grass", 180, outdoor=True, wall="white")

t.item("kuchyn", "kitchenRun", "obyvak", 0.62, 4.0, "E", 2.4, 0.62, parts=["sink", "hob", "oven", "backsplash"])
t.item("sedacka", "sofa", "obyvak", 3.0, 2.0, "S", 2.4, 0.95, color="#6f8396")
t.item("komoda-tv", "panel", "obyvak", 3.0, 7.48, "S", 1.8, 0.42, h=0.45, y=0.0, variant="flat", color="#b98d5f", solid=True)
t.tv("tv-obyvak", "obyvak", 3.0, 7.69, "S")
t.item("postel", "bed", "loznice", 8.0, 6.6, "S", 1.6, 2.05, variant="upholstered")

t.gable_roof("strecha", 0, 10, 0, 8, eave_h=2.9, pitch=38, ridge_along="u")

t.shot("obyvak", 0, (5.5, 0.8), (0.8, 7.0), "Obývací pokoj", "Obývací pokoj s kuchyní.", waypoint=True)
t.shot("loznice", 0, (9.3, 0.8), (6.5, 7.0), "Ložnice", "Ložnice s oknem na východ.", waypoint=True)
t.info("hs-cisla", 3, 4, 1.6, "Dům v číslech", "Přízemní dům, užitná plocha 69 m², zahrada 180 m².")

tour = t.build(
    title="Ukázkový dům",
    levels=[{"id": L, "name": "Přízemí", "short": "1. NP", "elevation": 0, "wallHeight": 2.6}],
    listing={"headline": "Ukázkový dům", "facts": [{"label": "Dispozice", "value": "2+kk"}], "areaM2": 69,
             "description": "Ukázka struktury tour.json.", "hero": {"photo": "foto-01"},
             "gallery": [{"url": "galerie/inzerat-1.jpg", "thumb": "galerie/mini-inzerat-1.jpg", "title": "Skutečná fotka", "kind": "photo"}],
             "location": {"label": "Ukázková lokalita", "map": {"url": "lokalita/mapa.jpg", "credit": "© ČÚZK, ZTM10", "pin": [0.5, 0.5]}}},
    branding={"name": "FrantišekDron", "colors": {"primary": "#ff5a5f", "accent": "#f5b73d", "panel": "#0a0e12", "text": "#f4f2ea"},
              "radius": 10, "pageTitle": "Ukázkový dům · 3D prohlídka", "shortName": "FD"},
    backdrop={"url": "vyhled/vyhled.json"},
    north_deg=0,
)
save(tour, sys.argv[1] if len(sys.argv) > 1 else "tour.json")
print("rooms", len(t.rooms), "walls", len(t.walls), "photos", len(t.photos))
