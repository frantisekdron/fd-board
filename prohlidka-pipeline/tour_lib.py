"""Pomocné funkce pro stavbu tour.json pro FD 3D prohlídku (engine z „Mezonet 4+kk 3D“).

Kreslí se v rámci domu: u = metry na východ podél fasády, v = metry na sever,
počátek v JZ rohu obrysu (stejně jako katastr.py). Engine má plán x doprava,
z dolů (sever nahoře), převod je x = u + X0, z = Z0 - v.

Výšky otvorů (sill, hi) se zadávají od podlahy daného podlaží.
Otvory: offset v enginu = střed otvoru měřený od bodu a stěny.

Příklad použití je v priklad_dum.py.
"""
import json, math


class Tour:
    def __init__(self, X0=10.0, Z0=20.0):
        self.X0, self.Z0 = X0, Z0
        self.rooms, self.walls, self.furniture, self.railings = [], [], [], []
        self.stairs, self.photos, self.waypoints, self.hotspots = [], [], [], []
        self.roof_planes, self.roof_windows, self.screens = [], [], []

    # ---------- souřadnice ----------
    def P(self, u, v):
        return [round(u + self.X0, 3), round(self.Z0 - v, 3)]

    def poly(self, pts):
        return [self.P(u, v) for u, v in pts]

    # ---------- místnosti ----------
    def room(self, id, name, level, pts, floor, area=None, lights=(), **kw):
        r = {"id": id, "name": name, "level": level, "polygon": self.poly(pts), "floor": floor}
        if area:
            r["areaM2"] = area
        if lights:
            r["lights"] = [self.light(*l) for l in lights]
        r.update(kw)
        self.rooms.append(r)

    def light(self, u, v, y=2.45, intensity=8, distance=5, fixture="ceiling"):
        x, z = self.P(u, v)
        return {"x": x, "z": z, "y": y, "intensity": intensity, "distance": distance, "fixture": fixture}

    # ---------- stěny ----------
    @staticmethod
    def win(a, b, sill, hi):
        return (a, b, sill, hi, "window", None)

    @staticmethod
    def door(a, b, id, hi=2.02, hinge="a", swing=1, open=True, **extra):
        return (a, b, 0, hi, "door", {"id": id, "hinge": hinge, "swing": swing, "open": open, **extra})

    @staticmethod
    def passage(a, b, hi=2.05):
        return (a, b, 0, hi, "passage", {"frame": False})

    def _openings(self, items, center):
        out = []
        for a, b, lo, hi, kind, extra in items:
            o = {"offset": round(center(a, b), 3), "width": round(b - a, 3), "sill": round(lo, 3), "height": round(hi - lo, 3), "kind": kind}
            o.update(extra or {})
            out.append(o)
        return out

    def wall_u(self, id, level, u0, u1, v0, v1, openings=(), exterior=False, height=None):
        """Stěna podél osy u (v rozsahu tloušťky v0..v1). Otvory v souřadnici u."""
        vc = (v0 + v1) / 2
        w = {"id": id, "level": level, "a": self.P(u0, vc), "b": self.P(u1, vc), "thickness": round(v1 - v0, 3),
             "exterior": exterior, "openings": self._openings(openings, lambda a, b: (a + b) / 2 - u0)}
        if height:
            w["height"] = height
        self.walls.append(w)

    def wall_v(self, id, level, v0, v1, u0, u1, openings=(), exterior=False, height=None):
        """Stěna podél osy v (v rozsahu tloušťky u0..u1). Otvory v souřadnici v. Bod a = severní konec."""
        uc = (u0 + u1) / 2
        w = {"id": id, "level": level, "a": self.P(uc, v1), "b": self.P(uc, v0), "thickness": round(u1 - u0, 3),
             "exterior": exterior, "openings": self._openings(openings, lambda a, b: v1 - (a + b) / 2)}
        if height:
            w["height"] = height
        self.walls.append(w)

    def rail(self, level, a, b, h=1.0, style="bars", color="#f2f2f0"):
        self.railings.append({"level": level, "a": self.P(*a), "b": self.P(*b), "h": h, "style": style, "color": color})

    # ---------- nábytek ----------
    def item(self, id, kind, roomId, u, v, facing, w, d, **kw):
        """facing = kam míří čelo: N (k ulici na sever), S, E, W v rámci domu."""
        x, z = self.P(u, v)
        it = {"id": id, "kind": kind, "roomId": roomId, "x": x, "z": z, "facing": facing, "w": w, "d": d}
        it.update(kw)
        self.furniture.append(it)

    def tv(self, id, roomId, u, v, facing, size=65, y=0.95, title="Fotky a informace", slideSeconds=6):
        """Televize s kanálem fotek, informací z inzerátu, půdorysu a mapy lokality (program mix)."""
        x, z = self.P(u, v)
        self.screens.append({"id": id, "roomId": roomId, "x": x, "z": z, "facing": facing, "y": y, "size": size,
                             "title": title, "program": "mix", "slideSeconds": slideSeconds})

    # ---------- schody ----------
    def straight_flight(self, u0, u1, v_start, run, steps, direction=+1):
        """Rovné rameno: vrátí seznam stupňů (polygonů) od spodního. direction +1 = stoupá na sever."""
        out = []
        for i in range(steps):
            a, b = v_start + direction * run * i, v_start + direction * run * (i + 1)
            lo, hi = min(a, b), max(a, b)
            out.append(self.poly([(u0, lo), (u1, lo), (u1, hi), (u0, hi)]))
        return out

    def stair(self, id, frm, to, room_from, room_to, treads, risers, opening, **kw):
        s = {"id": id, "from": frm, "to": to, "roomFrom": room_from, "roomTo": room_to, "treads": treads,
             "risers": risers, "opening": self.poly(opening), "finish": "oakGreige"}
        s.update(kw)
        self.stairs.append(s)

    # ---------- střecha ----------
    def roof_plane(self, id, ridge_a, ridge_b, ridge_h, pitch, toward, polygon):
        """Rovina střechy: hřeben (u,v)–(u,v) ve výšce ridge_h od podlahy 1.NP, toward = bod na straně okapu."""
        self.roof_planes.append({"id": id, "line": [self.P(*ridge_a), self.P(*ridge_b)], "height": round(ridge_h, 3),
                                 "pitchDeg": pitch, "toward": self.P(*toward), "polygon": self.poly(polygon)})

    def gable_roof(self, prefix, u0, u1, v0, v1, eave_h, pitch, overhang=0.5, ridge_along="v"):
        """Sedlová střecha nad obdélníkem (hřeben podél v nebo u)."""
        t = math.tan(math.radians(pitch))
        if ridge_along == "v":
            um = (u0 + u1) / 2; h = eave_h + (um - u0) * t
            V0, V1 = v0 - overhang, v1 + overhang
            self.roof_plane(f"{prefix}-zapad", (um, V0), (um, V1), h, pitch, (u0, (v0 + v1) / 2), [(u0 - overhang, V0), (um, V0), (um, V1), (u0 - overhang, V1)])
            self.roof_plane(f"{prefix}-vychod", (um, V0), (um, V1), h, pitch, (u1, (v0 + v1) / 2), [(um, V0), (u1 + overhang, V0), (u1 + overhang, V1), (um, V1)])
        else:
            vm = (v0 + v1) / 2; h = eave_h + (vm - v0) * t
            U0, U1 = u0 - overhang, u1 + overhang
            self.roof_plane(f"{prefix}-jih", (U0, vm), (U1, vm), h, pitch, ((u0 + u1) / 2, v0), [(U0, v0 - overhang), (U1, v0 - overhang), (U1, vm), (U0, vm)])
            self.roof_plane(f"{prefix}-sever", (U0, vm), (U1, vm), h, pitch, ((u0 + u1) / 2, v1), [(U0, vm), (U1, vm), (U1, v1 + overhang), (U0, v1 + overhang)])

    # ---------- fotky a průvodce ----------
    def shot(self, room_id, elevation, pos, target, title, caption, eye=1.5, hfov=90, aspect=1.5, waypoint=False, doors=None):
        """Pozice fotky = pozice kamery pro render i pro AI fotku. Vrací id fotky."""
        n = len(self.photos) + 1
        pid = f"foto-{n:02d}"
        x, z = self.P(*pos); tx, tz = self.P(*target)
        yaw = round(math.degrees(math.atan2(-(tx - x), -(tz - z))), 2)
        ph = {"id": pid, "url": f"fotky/{pid}.jpg", "thumb": f"fotky/mini-{n:02d}.jpg", "roomId": room_id,
              "position": [x, round(elevation + eye, 3), z], "yaw": yaw, "pitch": -3, "hfov": hfov, "aspect": aspect,
              "title": title, "caption": caption}
        if doors:
            ph["doors"] = doors
        self.photos.append(ph)
        if waypoint:
            self.waypoints.append({"id": f"wp-{n:02d}", "position": [x, elevation, z], "yaw": yaw, "pitch": -3,
                                   "roomId": room_id, "caption": caption, "dwellS": 5, "photoId": pid})
        return pid

    def info(self, id, u, v, y, title, text):
        x, z = self.P(u, v)
        self.hotspots.append({"id": id, "position": [x, y, z], "title": title, "text": text, "kind": "info"})

    # ---------- výstup ----------
    def build(self, title, levels, listing, branding, floor_plan=None, backdrop=None, north_deg=0, surroundings="none",
              street_side="N", roof_color="#6b4536", extra_apartment=None):
        ap = {"kind": "house", "wallHeight": levels[0].get("wallHeight", 2.6), "railingHeight": 1,
              "rooms": self.rooms, "walls": self.walls, "railings": self.railings, "stairs": self.stairs,
              "northDeg": north_deg, "surroundings": surroundings, "streetSide": street_side,
              "furniture": self.furniture}
        if len(levels) >= 2:          # engine chce 2–4 podlaží, přízemní dům je bez "levels"
            ap["levels"] = levels
        else:                         # a pak nesmí mít ani klíč "level" u místností a stěn
            for coll in (ap["rooms"], ap["walls"], ap["railings"]):
                for x in coll:
                    x.pop("level", None)
        if self.screens:
            ap["screens"] = self.screens
        if self.roof_planes:
            ap["roof"] = {"planes": self.roof_planes, "thickness": 0.3, "color": roof_color, "overhang": 0, "headroom": 1.6}
        if self.roof_windows:
            ap["roofWindows"] = self.roof_windows
        ap.update(extra_apartment or {})
        first = self.photos[0] if self.photos else {"position": [self.X0, 1.5, self.Z0], "yaw": 0}
        t = {"version": 1, "title": title, "source": "demo", "units": "m",
             "spawn": {"position": [first["position"][0], 0, first["position"][2]], "yaw": first["yaw"], "pitch": -3},
             "settings": {"eyeHeight": 1.65, "walkSpeed": 1.4, "runMultiplier": 2.2},
             "waypoints": self.waypoints, "hotspots": self.hotspots, "apartment": ap, "photos": self.photos,
             "listing": listing, "branding": branding}
        if floor_plan:
            t["floorPlan"] = floor_plan
        if backdrop:
            t["backdrop"] = backdrop
        return t

    def plan_overlay(self, level_id, url, img_center_px, ref_px, ref_uv, m_per_px, rotation_deg=0):
        """Podklad půdorysu: ref_px = pixel v obrázku, který odpovídá bodu ref_uv (u,v) v domě.
        Pro výkres otočený o 180° (jih nahoře) zadej rotation_deg=180."""
        cx, cy = img_center_px; rx, ry = ref_px
        dx, dy = (cx - rx) * m_per_px, (cy - ry) * m_per_px
        if rotation_deg == 180:
            du, dv = -dx, dy
        else:
            du, dv = dx, -dy
        u, v = ref_uv[0] + du, ref_uv[1] + dv
        return {"id": level_id, "image": {"url": url}, "imageTransform": {"position": self.P(u, v), "rotationDeg": rotation_deg, "scale": m_per_px}}


def save(tour, path):
    json.dump(tour, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
