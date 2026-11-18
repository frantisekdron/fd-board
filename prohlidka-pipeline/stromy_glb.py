#!/usr/bin/env python3
"""Low-poly stromy a keře pro FD prohlídky jako .glb (položky "kind": "model").

Pozor: engine načítá .glb modely jen z vrstvy apartment.furnishing.items (přepínač Prázdný / Zařízený),
z apartment.furniture je ignoruje. Stromy proto patří do furnishing, např.
"furnishing": {"items": [...stromy...], "label": "Zeleň na zahradě"}; aby byla vrstva zapnutá hned,
otevře se prohlídka s ?zarizeni=1 (nebo to index.html nastaví do localStorage, viz Horšovská).

    python3 stromy_glb.py vystupni_slozka/

Vytvoří listnaty.glb, jehlicnan.glb a ker.glb. Každý model je normovaný do krabice
1 × 1 × 1 (x, z ∈ ⟨-0,5; 0,5⟩, y ∈ ⟨0; 1⟩), takže v tour.json se velikost nastaví přes
w, d, h s "fit": "stretch". Materiály se jmenují "listi" a "kmen", barva se dá
přebarvit přes model.tint ({"match": "listi", "color": "#4f7a37", "mode": "replace"}).

Artefakty pouští jen běžné webové typy, proto se .glb v prohlídce nahrává jako .webm
(stejně jako modely v prohlídkách Mezonet a Jahodnice); engine typ pozná podle obsahu.
"""
import json, math, os, random, struct, sys


def icosphere(level=1):
    t = (1 + 5 ** 0.5) / 2
    v = [(-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0), (0, -1, t), (0, 1, t), (0, -1, -t), (0, 1, -t),
         (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1)]
    v = [tuple(c / math.sqrt(sum(x * x for x in p)) for c in p) for p in v]
    f = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6), (7, 1, 8),
         (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9), (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1)]
    for _ in range(level):
        cache, nf = {}, []
        def mid(a, b):
            k = (min(a, b), max(a, b))
            if k not in cache:
                p = [(v[a][i] + v[b][i]) / 2 for i in range(3)]; l = math.sqrt(sum(x * x for x in p))
                v.append(tuple(x / l for x in p)); cache[k] = len(v) - 1
            return cache[k]
        for a, b, c in f:
            ab, bc, ca = mid(a, b), mid(b, c), mid(c, a)
            nf += [(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)]
        f = nf
    return v, f


def blob(cx, cy, cz, rx, ry, rz, rnd, jitter=0.12):
    v, f = icosphere(1)
    out = []
    for x, y, z in v:
        k = 1 + rnd.uniform(-jitter, jitter)
        out.append((cx + x * rx * k, cy + y * ry * k, cz + z * rz * k))
    return out, f


def cone(cx, y0, y1, r, seg=9):
    v = [(cx + r * math.cos(2 * math.pi * i / seg), y0, r * math.sin(2 * math.pi * i / seg)) for i in range(seg)]
    v.append((cx, y1, 0)); v.append((cx, y0, 0))
    top, bot = seg, seg + 1
    f = [(i, top, (i + 1) % seg) for i in range(seg)] + [((i + 1) % seg, bot, i) for i in range(seg)]
    return v, f


def cylinder(r0, r1, y0, y1, seg=8):
    v = []
    for i in range(seg):
        a = 2 * math.pi * i / seg
        v.append((r0 * math.cos(a), y0, r0 * math.sin(a))); v.append((r1 * math.cos(a), y1, r1 * math.sin(a)))
    f = []
    for i in range(seg):
        a, b, c, d = 2 * i, 2 * i + 1, (2 * i + 2) % (2 * seg), (2 * i + 3) % (2 * seg)
        f += [(a, b, c), (c, b, d)]
    return v, f


def merge(parts):
    V, F = [], []
    for v, f in parts:
        o = len(V); V += v; F += [(a + o, b + o, c + o) for a, b, c in f]
    return V, F


def flat(V, F):
    """Plochy se samostatnými normálami (low-poly vzhled), trojúhelníky otočené ven."""
    P, N, I = [], [], []
    cx = sum(p[0] for p in V) / len(V); cz = sum(p[2] for p in V) / len(V)
    for a, b, c in F:
        A, B, C = V[a], V[b], V[c]
        u = [B[i] - A[i] for i in range(3)]; w = [C[i] - A[i] for i in range(3)]
        n = [u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0]]
        l = math.sqrt(sum(x * x for x in n)) or 1; n = [x / l for x in n]
        m = [(A[i] + B[i] + C[i]) / 3 for i in range(3)]
        if n[0] * (m[0] - cx) + n[2] * (m[2] - cz) + n[1] * 0.2 < 0:
            B, C = C, B; n = [-x for x in n]
        k = len(P); P += [A, B, C]; N += [n, n, n]; I += [k, k + 1, k + 2]
    return P, N, I


def normalize(parts):
    allv = [p for v, _ in parts for p in v]
    mnx, mxx = min(p[0] for p in allv), max(p[0] for p in allv)
    mny, mxy = min(p[1] for p in allv), max(p[1] for p in allv)
    mnz, mxz = min(p[2] for p in allv), max(p[2] for p in allv)
    sx, sy, sz = mxx - mnx, mxy - mny, mxz - mnz; cx, cz = (mnx + mxx) / 2, (mnz + mxz) / 2
    return [([((x - cx) / sx, (y - mny) / sy, (z - cz) / sz) for x, y, z in v], f) for v, f in parts]


def write_glb(path, prims):
    """prims: [(name, rgba, (P, N, I))]"""
    bin_, views, accs, gprims, mats = b"", [], [], [], []
    def add(data, target):
        nonlocal bin_
        while len(bin_) % 4: bin_ += b"\0"
        views.append({"buffer": 0, "byteOffset": len(bin_), "byteLength": len(data), "target": target}); bin_ += data
        return len(views) - 1
    for name, rgba, (P, N, I) in prims:
        pv = add(struct.pack(f"<{3 * len(P)}f", *[c for p in P for c in p]), 34962)
        nv = add(struct.pack(f"<{3 * len(N)}f", *[c for n in N for c in n]), 34962)
        iv = add(struct.pack(f"<{len(I)}I", *I), 34963)
        accs.append({"bufferView": pv, "componentType": 5126, "count": len(P), "type": "VEC3",
                     "min": [min(p[i] for p in P) for i in range(3)], "max": [max(p[i] for p in P) for i in range(3)]})
        accs.append({"bufferView": nv, "componentType": 5126, "count": len(N), "type": "VEC3"})
        accs.append({"bufferView": iv, "componentType": 5125, "count": len(I), "type": "SCALAR"})
        mats.append({"name": name, "pbrMetallicRoughness": {"baseColorFactor": rgba, "metallicFactor": 0, "roughnessFactor": 0.95}})
        k = len(accs) - 3
        gprims.append({"attributes": {"POSITION": k, "NORMAL": k + 1}, "indices": k + 2, "material": len(mats) - 1})
    while len(bin_) % 4: bin_ += b"\0"
    gltf = {"asset": {"version": "2.0", "generator": "FD stromy_glb.py"}, "scene": 0, "scenes": [{"nodes": [0]}],
            "nodes": [{"mesh": 0, "name": os.path.splitext(os.path.basename(path))[0]}], "meshes": [{"primitives": gprims}],
            "materials": mats, "accessors": accs, "bufferViews": views, "buffers": [{"byteLength": len(bin_)}]}
    js = json.dumps(gltf, separators=(",", ":")).encode()
    while len(js) % 4: js += b" "
    glb = struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(bin_))
    glb += struct.pack("<II", len(js), 0x4E4F534A) + js + struct.pack("<II", len(bin_), 0x004E4942) + bin_
    open(path, "wb").write(glb)


LISTI, KMEN = [0.30, 0.47, 0.22, 1], [0.36, 0.26, 0.18, 1]


def strom_listnaty(rnd):
    kmen = cylinder(0.07, 0.05, 0.0, 0.5)
    kor = [blob(0, 0.68, 0, 0.36, 0.30, 0.36, rnd), blob(0.18, 0.78, 0.08, 0.26, 0.24, 0.26, rnd),
           blob(-0.17, 0.74, -0.1, 0.27, 0.24, 0.27, rnd), blob(0.02, 0.9, -0.02, 0.22, 0.18, 0.22, rnd),
           blob(-0.05, 0.6, 0.2, 0.24, 0.2, 0.24, rnd)]
    return kmen, merge(kor)


def strom_jehlicnan(rnd):
    kmen = cylinder(0.05, 0.04, 0.0, 0.18)
    kor = merge([cone(0, 0.08, 0.62, 0.5), cone(0, 0.32, 0.86, 0.38), cone(0, 0.58, 1.0, 0.25)])
    return kmen, kor


def ker(rnd):
    kmen = cylinder(0.04, 0.03, 0.0, 0.12)
    kor = merge([blob(0, 0.5, 0, 0.5, 0.45, 0.5, rnd, 0.15), blob(0.25, 0.42, 0.15, 0.32, 0.32, 0.32, rnd, 0.15),
                 blob(-0.25, 0.4, -0.12, 0.32, 0.3, 0.32, rnd, 0.15)])
    return kmen, kor


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "."
    os.makedirs(out, exist_ok=True)
    for name, fn in (("listnaty", strom_listnaty), ("jehlicnan", strom_jehlicnan), ("ker", ker)):
        kmen, kor = normalize(list(fn(random.Random(7))))
        write_glb(os.path.join(out, name + ".glb"), [("kmen", KMEN, flat(*kmen)), ("listi", LISTI, flat(*kor))])
        print("hotovo", name)
