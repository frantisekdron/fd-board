#!/usr/bin/env python3
"""Podklady o pozemku z katastru ČÚZK pro 3D prohlídku.

Podle adresy stáhne z RÚIAN adresní bod, budovu, parcely v okolí a osy ulic,
k tomu ortofoto a Základní topografickou mapu (ZTM10). Výstup je v lokálním
souřadném systému domu (osa u podél nejdelší hrany budovy, v kolmo, metry).

Použití:
    python3 katastr.py --ulice "Název ulice" --cislo 17 --out ./podklady
    python3 katastr.py --ulice "Název ulice" --cislo 17 --domovni 1051 --out ./podklady

Výstupy v --out:
    site.json      parcely, sousední budovy, ulice, obrys domu, pozemek (parcely s adresním bodem
                   nebo zadané přes --parcely), úhel natočení domu, umístění ortofota
    orto.jpg       ortofoto 120 × 120 m kolem adresy (sever nahoře, S-JTSK)
    mapa.jpg       ZTM10 1200 × 900 m, adresa uprostřed (pro lokalitu v prohlídce)

Závislosti: pip install shapely  (a curl v systému)
"""
import argparse, json, math, os, subprocess, sys, urllib.parse

RUIAN = "https://ags.cuzk.cz/arcgis/rest/services/RUIAN/MapServer"
ORTO = "https://ags.cuzk.cz/arcgis1/rest/services/ORTOFOTO/MapServer/export"
ZTM = "https://ags.cuzk.cz/arcgis1/rest/services/ZTM/ZTM10/MapServer/export"
L_ADRESA, L_BUDOVA, L_ULICE, L_PARCELA = 1, 3, 4, 5


def get(url, params, out=None):
    q = url + "?" + urllib.parse.urlencode(params)
    cmd = ["curl", "-sS", "-m", "90", q] + (["-o", out] if out else [])
    r = subprocess.run(cmd, capture_output=True, check=True)
    return None if out else json.loads(r.stdout)


def query(layer, **kw):
    p = {"outFields": "*", "returnGeometry": "true", "f": "json"}
    p.update(kw)
    d = get(f"{RUIAN}/{layer}/query", p)
    if "error" in d:
        sys.exit(f"RÚIAN vrátil chybu: {d['error']}")
    return d.get("features", [])


def envelope(x, y, r):
    return {"geometry": f"{x - r},{y - r},{x + r},{y + r}", "geometryType": "esriGeometryEnvelope",
            "spatialRel": "esriSpatialRelIntersects", "inSR": 5514}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ulice", required=True)
    ap.add_argument("--cislo", type=int, help="číslo orientační")
    ap.add_argument("--domovni", type=int, help="číslo popisné (když orientační nestačí)")
    ap.add_argument("--parcely", help="čísla parcel pozemku oddělená čárkou, např. 1532/62,1532/152")
    ap.add_argument("--okoli", type=float, default=60, help="poloměr okolí v metrech")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    from shapely.geometry import Polygon, Point
    from shapely.ops import unary_union
    os.makedirs(a.out, exist_ok=True)

    ulice = query(L_ULICE, where=f"nazev='{a.ulice}'", returnGeometry="false")
    if not ulice:
        sys.exit("Ulici jsem v RÚIAN nenašel.")
    kody = ",".join(str(u["attributes"]["kod"]) for u in ulice)
    w = f"ulice in ({kody})"
    if a.cislo is not None:
        w += f" and cisloorientacni={a.cislo}"
    if a.domovni is not None:
        w += f" and cislodomovni={a.domovni}"
    adresy = query(L_ADRESA, where=w)
    if len(adresy) != 1:
        for f in adresy:
            print("  ", f["attributes"]["adresa"])
        sys.exit(f"Adresa není jednoznačná ({len(adresy)} výsledků). Upřesni --domovni.")
    ad = adresy[0]
    X, Y = ad["geometry"]["x"], ad["geometry"]["y"]
    print("Adresa:", ad["attributes"]["adresa"])

    budovy = query(L_BUDOVA, **envelope(X, Y, a.okoli))
    parcely = query(L_PARCELA, **envelope(X, Y, a.okoli))
    ulice_geo = query(L_ULICE, **envelope(X, Y, a.okoli))
    bod = Point(X, Y)
    dum = next((b for b in budovy if b["attributes"].get("kod") == ad["attributes"]["stavebniobjekt"]), None)
    if dum is None:
        dum = min(budovy, key=lambda b: Polygon(b["geometry"]["rings"][0]).distance(bod))
    ring = dum["geometry"]["rings"][0]

    # natočení domu podle nejdelší hrany obrysu
    best = max(range(len(ring) - 1), key=lambda i: math.dist(ring[i], ring[i + 1]))
    (ax, ay), (bx, by) = ring[best], ring[best + 1]
    ang = math.atan2(by - ay, bx - ax)
    ang = (ang + math.pi / 4) % (math.pi / 2) - math.pi / 4   # nejbližší ±45° k ose východ
    c, s = math.cos(ang), math.sin(ang)
    to_h = lambda x, y: ((x * c + y * s), (-x * s + y * c))
    hu = [to_h(x, y) for x, y in ring]
    u0, v0 = min(p[0] for p in hu), min(p[1] for p in hu)
    ox, oy = u0 * c - v0 * s, u0 * s + v0 * c                  # počátek = JZ roh obrysu v rámci domu

    def H(p):
        u, v = to_h(p[0], p[1])
        return [round(u - u0, 3), round(v - v0, 3)]

    def Lw(p):
        return [round(p[0] - ox, 3), round(p[1] - oy, 3)]

    if a.parcely:
        chci = {x.strip() for x in a.parcely.split(",")}
        pozemek = [Polygon(f["geometry"]["rings"][0]) for f in parcely if f["attributes"]["cisloparcely"] in chci]
    else:
        pozemek = [Polygon(f["geometry"]["rings"][0]) for f in parcely if Polygon(f["geometry"]["rings"][0]).contains(bod)]
    poz = unary_union(pozemek).simplify(0.05)
    poz_ring = list(poz.exterior.coords)

    site = {
        "adresa": ad["attributes"]["adresa"],
        "angle": ang, "origin": [ox, oy], "addr": Lw((X, Y)),
        "ortho": {"cx": X - ox, "cy": Y - oy, "R": 60},
        "budova": {"attrs": {k: dum["attributes"].get(k) for k in ("cisladomovni", "zastavenaplocha", "podlahovaplocha", "pocetpodlazi", "dokonceni")},
                   "world": [Lw(p) for p in ring], "house": [H(p) for p in ring]},
        "plot": [Lw(p) for p in poz_ring], "plotHouse": [H(p) for p in poz_ring],
        "plotArea": round(poz.area, 1),
        "plotEdges": [round(math.dist(poz_ring[i], poz_ring[i + 1]), 2) for i in range(len(poz_ring) - 1)],
        "parcels": [{"c": f["attributes"]["cisloparcely"], "a": f["attributes"]["vymeraparcely"],
                     "r": [Lw(p) for p in f["geometry"]["rings"][0]]} for f in parcely],
        "neighbors": [{"r": [Lw(p) for p in f["geometry"]["rings"][0]], "fl": f["attributes"].get("pocetpodlazi") or 2}
                      for f in budovy if f is not dum],
        "streets": [{"n": f["attributes"]["nazev"], "p": [Lw(p) for p in f["geometry"]["paths"][0]]} for f in ulice_geo],
    }
    json.dump(site, open(os.path.join(a.out, "site.json"), "w"), ensure_ascii=False, indent=1)

    R = 60
    get(ORTO, {"bbox": f"{X - R},{Y - R},{X + R},{Y + R}", "bboxSR": 5514, "imageSR": 5514, "size": "2048,2048",
               "format": "jpg", "f": "image"}, os.path.join(a.out, "orto.jpg"))
    get(ZTM, {"bbox": f"{X - 600},{Y - 450},{X + 600},{Y + 450}", "bboxSR": 5514, "imageSR": 5514, "size": "1600,1200",
              "format": "jpg", "f": "image"}, os.path.join(a.out, "mapa.jpg"))
    print(f"Pozemek {site['plotArea']} m², hrany {site['plotEdges']}")
    print(f"Natočení domu {math.degrees(ang):.1f}°, obrys v rámci domu: {site['budova']['house']}")
    print("Hotovo:", a.out)


if __name__ == "__main__":
    main()
