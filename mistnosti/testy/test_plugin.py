# -*- coding: utf-8 -*-
"""Testy pluginu FD Místnosti bez DaVinci: čtení MP4, párování (simulace natáčení dvěma kamerami),
zápis do náhradního Resolve a přiřazení pro FD Studio.  Spuštění: python3 -m pytest mistnosti/testy -q
"""
import csv
import importlib.util
import io
import json
import os
import random
import struct
from datetime import datetime, timedelta

import pytest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location("FD_Mistnosti", os.path.join(KOREN, "davinci", "FD_Mistnosti.py"))
P = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(P)

EPOCHA_1904 = datetime(1904, 1, 1)
EPOCHA_1970 = datetime(1970, 1, 1)
OFF_MIN = 60  # SEČ


# ------------------------------------------------------------------------------------------
# výroba testovacích souborů
# ------------------------------------------------------------------------------------------

def box(typ, data):
    return struct.pack(">I4s", 8 + len(data), typ) + data


def mvhd(start, delka_s, verze=0, meritko=1000):
    vytvoreno = int((start - EPOCHA_1904).total_seconds())
    delka = int(round(delka_s * meritko))
    if verze == 1:
        hlava = struct.pack(">B3xQQIQ", 1, vytvoreno, vytvoreno, meritko, delka)
    else:
        hlava = struct.pack(">B3xIIII", 0, vytvoreno, vytvoreno, meritko, delka)
    return box(b"mvhd", hlava + b"\x00\x01\x00\x00" + b"\x01\x00" + b"\x00" * 70 + struct.pack(">I", 2))


def udelej_mp4(cesta, start, delka_s, model=None, moov_na_konci=True, verze=0):
    os.makedirs(os.path.dirname(cesta), exist_ok=True)
    udta = box(b"udta", box(b"PANA", b"\x00\x01" + model.encode("ascii") + b"\x00" * 10)) if model else b""
    moov = box(b"moov", mvhd(start, delka_s, verze) + box(b"trak", box(b"tkhd", b"\x00" * 84)) + udta)
    ftyp = box(b"ftyp", b"mp42\x00\x00\x00\x00mp42isom")
    mdat = box(b"mdat", os.urandom(2048))
    with open(cesta, "wb") as f:
        f.write(ftyp + (mdat + moov if moov_na_konci else moov + mdat))
    return cesta


def ms_telefonu(mistni):
    """Místní čas telefonu (naivní) → ms od epochy v UTC, jak je zapisuje stránka."""
    return int(round(((mistni - EPOCHA_1970).total_seconds() - OFF_MIN * 60) * 1000))


def zapis_telefonu(mistni, typ, mistnost, nazev, zid):
    return {"id": zid, "cas": mistni.strftime("%Y-%m-%dT%H:%M:%S.000+01:00"), "ms": ms_telefonu(mistni), "off": OFF_MIN,
            "typ": typ, "mistnost": mistnost, "nazev": nazev}


# ------------------------------------------------------------------------------------------
# náhradní DaVinci Resolve (jen volání, která plugin používá)
# ------------------------------------------------------------------------------------------

class FItem(object):
    def __init__(self, cesta):
        self.props = {"File Path": cesta, "File Name": os.path.basename(cesta)}
        self.meta = {}
        self.barva = None

    def GetClipProperty(self, k=None):
        return self.props.get(k, "") if k else dict(self.props)

    def GetMetadata(self, k=None):
        return self.meta.get(k, "") if k else dict(self.meta)

    def SetMetadata(self, k, v):
        self.meta[k] = v
        return True

    def SetClipColor(self, c):
        self.barva = c
        return True


class FFolder(object):
    def __init__(self, nazev):
        self.nazev, self.klipy, self.pod = nazev, [], []

    def GetName(self):
        return self.nazev

    def GetClipList(self):
        return list(self.klipy)

    def GetSubFolderList(self):
        return list(self.pod)


class FMediaPool(object):
    def __init__(self):
        self.koren = FFolder("Master")

    def GetRootFolder(self):
        return self.koren

    def AddSubFolder(self, rodic, nazev):
        f = FFolder(nazev)
        rodic.pod.append(f)
        return f

    def MoveClips(self, polozky, cil):
        def ven(f):
            for p in polozky:
                if p in f.klipy:
                    f.klipy.remove(p)
            for s in f.pod:
                ven(s)
        ven(self.koren)
        cil.klipy.extend(polozky)
        return True


class FTItem(object):
    def __init__(self, start, mpi):
        self.start, self.mpi = start, mpi

    def GetStart(self):
        return self.start

    def GetMediaPoolItem(self):
        return self.mpi


class FTimeline(object):
    def __init__(self, nazev="Klamovka v1", start=86400):
        self.nazev, self.start = nazev, start
        self.stopy = {1: []}
        self.markery = {}

    def GetName(self):
        return self.nazev

    def GetStartFrame(self):
        return self.start

    def GetTrackCount(self, typ):
        return len(self.stopy) if typ == "video" else 0

    def GetItemListInTrack(self, typ, i):
        return list(self.stopy.get(i, []))

    def AddMarker(self, ram, barva, jmeno, pozn, delka, data=""):
        if ram in self.markery:
            return False
        self.markery[ram] = {"barva": barva, "jmeno": jmeno, "pozn": pozn, "delka": delka, "data": data}
        return True

    def DeleteMarkerByCustomData(self, data):
        for ram in sorted(self.markery):
            if self.markery[ram]["data"] == data:
                del self.markery[ram]
                return True
        return False


class FProjekt(object):
    def __init__(self, nazev="Klamovka 2 – střih"):
        self.nazev, self.mp, self.tl = nazev, FMediaPool(), None

    def GetName(self):
        return self.nazev

    def GetMediaPool(self):
        return self.mp

    def GetCurrentTimeline(self):
        return self.tl


# ------------------------------------------------------------------------------------------
# simulace natáčení
# ------------------------------------------------------------------------------------------

POKOJE = [("hallway", "Vstup a chodba"), ("living_room", "Obývák"), ("kitchen", "Kuchyně"), ("bedroom", "Ložnice"),
          ("bathroom", "Koupelna"), ("bathroom", "WC"), ("kids_room", "Dětský pokoj"), ("terrace", "Terasa a balkon"),
          ("garden", "Zahrada"), ("facade", "Fasáda")]


def natoc(rng, kamera, zacatek, posun_hodin_s, slozka, model, n_mistnosti=8, mvhd_je_konec=False):
    """Jedna kamera: místnosti po sobě, 1–4 záběry, klepnutí po záběru (nebo jen po posledním v místnosti),
    občas zmetek a překlep vrácený tlačítkem Zpět. Vrací (klipy [(cesta, mistnost_nazev, zmetek)], log)."""
    t = zacatek
    klipy, zapisy = [], []
    cislo = rng.randint(100, 900)
    for m in range(n_mistnosti):
        klic, nazev = POKOJE[(m + (3 if kamera == "S1II" else 0)) % len(POKOJE)]
        jen_po_poslednim = rng.random() < 0.3
        pocet = rng.randint(1, 4)
        for i in range(pocet):
            delka = rng.uniform(4, 25)
            start_kamera = t + timedelta(seconds=posun_hodin_s)
            cislo += 1
            cesta = os.path.join(slozka, "P%07d.MP4" % (1000000 + cislo))
            udelej_mp4(cesta, (start_kamera + timedelta(seconds=delka)) if mvhd_je_konec else start_kamera,
                       delka, model, moov_na_konci=rng.random() < 0.7, verze=rng.choice([0, 1]))
            konec = t + timedelta(seconds=delka)
            t = konec + timedelta(seconds=rng.uniform(1, 8))
            zmetek = rng.random() < 0.08
            klipy.append((cesta, nazev, zmetek))
            if zmetek:
                zapisy.append(zapis_telefonu(t, "zmetek", None, "Zmetek", "z%d" % len(zapisy)))
                t += timedelta(seconds=rng.uniform(1, 4))
            if not jen_po_poslednim or i == pocet - 1:
                if rng.random() < 0.05:  # překlep, hned vrácený
                    zz = zapis_telefonu(t, "mistnost", "garage", "Garáž", "z%d" % len(zapisy))
                    zz["smazano"] = "x"
                    zapisy.append(zz)
                    t += timedelta(seconds=2)
                zapisy.append(zapis_telefonu(t, "mistnost", klic, nazev, "z%d" % len(zapisy)))
            t += timedelta(seconds=rng.uniform(2, 12))
        t += timedelta(seconds=rng.uniform(20, 90))  # přechod do další místnosti
    log = {"format": P.FORMAT_ZAPISU, "id": "s-" + kamera, "zakazka": "Klamovka 2", "kamera": kamera,
           "zalozeno": zacatek.strftime("%Y-%m-%dT%H:%M:%S"), "exportovano": t.strftime("%Y-%m-%dT%H:%M:%S"),
           "zapisy": zapisy}
    return klipy, log


def scena(tmp_path, seed, mvhd_je_konec=False):
    rng = random.Random(seed)
    den = datetime(2026, 10, 25, 13, 0, 0)
    klipy_s5, log_s5 = natoc(rng, "S5", den, 3600 + 37, str(tmp_path / "karta1" / "DCIM" / "100_PANA"), "DC-S5",
                             mvhd_je_konec=mvhd_je_konec)
    klipy_s1, log_s1 = natoc(rng, "S1II", den + timedelta(minutes=2), -12, str(tmp_path / "karta2" / "DCIM" / "101_PANA"),
                             "DC-S1M2", mvhd_je_konec=mvhd_je_konec)
    # cizí materiál v Media Poolu: dopolední natáčení stejnou S5 jinde, GH5 a dron bez modelu
    cizi = []
    for i in range(25):
        start = datetime(2026, 10, 25, 10, 40, 0) + timedelta(seconds=3600 + 37 + i * rng.uniform(30, 70))
        cizi.append(udelej_mp4(str(tmp_path / "rano" / ("P%07d.MP4" % (1200000 + i))), start, rng.uniform(5, 20), "DC-S5"))
    cizi.append(udelej_mp4(str(tmp_path / "gh5" / "P1300001.MP4"), den + timedelta(minutes=5), 10, "DC-GH5"))
    return klipy_s5 + klipy_s1, [log_s5, log_s1], cizi


def projekt_z(cesty):
    pr = FProjekt()
    bin_ = pr.mp.AddSubFolder(pr.mp.koren, "Karty")
    for c in cesty:
        bin_.klipy.append(FItem(c))
    return pr


def skupina_z(logy, tmp_path):
    slozka = tmp_path / "icloud"
    slozka.mkdir(exist_ok=True)
    for log in logy:
        with open(str(slozka / ("FD-mistnosti_klamovka-2_%s_20261025_%s.json" % (log["kamera"], log["id"]))), "w",
                  encoding="utf-8") as f:
            json.dump(log, f, ensure_ascii=False)
    skupiny, _ = P.nacti_skupiny([str(slozka)])
    assert len(skupiny) == 1
    return skupiny[0]


# ------------------------------------------------------------------------------------------
# testy
# ------------------------------------------------------------------------------------------

def test_cteni_mp4(tmp_path):
    start = datetime(2026, 10, 25, 14, 20, 10)
    for verze in (0, 1):
        for konec in (True, False):
            c = udelej_mp4(str(tmp_path / ("a%d%d.mp4" % (verze, konec))), start, 12.5, "DC-S1M2", konec, verze)
            info = P.precti_video(c)
            assert info["cas"] == start and info["zdroj"] == "mvhd"
            assert abs(info["delka_s"] - 12.5) < 0.01
            assert info["model"] == "DC-S1M2"
    # jiný formát: čas z poslední změny souboru, chápaný jako konec záběru
    c = tmp_path / "klip.mxf"
    c.write_bytes(b"\x06\x0e\x2b\x34" + os.urandom(100))
    info = P.precti_video(str(c))
    assert info["cas_je_konec"] and info["model"] is None
    assert P.precti_video(str(tmp_path / "neni.mp4")) is None


def test_kamera_z_modelu():
    assert P.kamera_z_modelu("DC-S5") == "S5"
    assert P.kamera_z_modelu("DC-S1M2") == "S1II"
    assert P.kamera_z_modelu("DC-S5M2X") == "S5IIX"
    assert P.kamera_z_modelu("DC-S1RM2") == "S1RII"
    assert P.kamera_z_modelu("DC-S1M2ES") == "S1IIE"
    assert P.kamera_z_modelu(None) is None


def test_kamera_z_cesty():
    k = ["S1II", "S5"]
    assert P.kamera_z_cesty("/Volumes/Raid/Klamovka/Karta S5/DCIM/P100.MP4", k) == "S5"
    assert P.kamera_z_cesty("/Volumes/Raid/Klamovka/S1II/P100.MP4", k) == "S1II"
    assert P.kamera_z_cesty("/Volumes/Raid/Klamovka/karta_s1/P100.MP4", k) == "S1II"
    assert P.kamera_z_cesty("/Volumes/LUMIX/DCIM/100_PANA/P100.MP4", k) is None


@pytest.mark.parametrize("seed", range(25))
def test_simulace_dve_kamery(tmp_path, seed):
    klipy_pravda, logy, cizi = scena(tmp_path, seed)
    skupina = skupina_z(logy, tmp_path)
    pr = projekt_z([c for c, _, _ in klipy_pravda] + cizi)
    klipy = P.klipy_z_projektu(pr)
    souhrn = P.sparuj(klipy, skupina["zapisy"])
    podle = {k.cesta: k for k in klipy}
    spatne = []
    for cesta, nazev, zmetek in klipy_pravda:
        k = podle[cesta]
        if P.popisek(k) != nazev or k.zmetek != zmetek:
            spatne.append((os.path.basename(cesta), nazev, P.popisek(k), zmetek, k.zmetek, k.mezera))
    assert not spatne, spatne
    for c in cizi:
        assert podle[c].zapis is None and not podle[c].zmetek, c
    assert podle[cizi[-1]].cizi  # GH5 v zápisech není
    assert abs(souhrn["S5"]["posun_s"] - (-3637)) < 10
    assert abs(souhrn["S1II"]["posun_s"] - 12) < 10


@pytest.mark.parametrize("seed", range(5))
def test_kamera_zapisuje_cas_konce(tmp_path, seed):
    """Některé kamery dávají do mvhd konec záběru: plugin si vybere hypotézu, která sedí."""
    klipy_pravda, logy, _ = scena(tmp_path, 100 + seed, mvhd_je_konec=True)
    skupina = skupina_z(logy, tmp_path)
    klipy = P.klipy_z_projektu(projekt_z([c for c, _, _ in klipy_pravda]))
    P.sparuj(klipy, skupina["zapisy"])
    podle = {k.cesta: k for k in klipy}
    assert all(P.popisek(podle[c]) == n for c, n, _ in klipy_pravda)


def test_kamera_bez_modelu_podle_slozky_a_casu(tmp_path):
    """Bez modelu v souboru rozhodne složka, a když ani ta ne, čas zápisu."""
    rng = random.Random(7)
    den = datetime(2026, 10, 25, 13, 0, 0)
    k5, l5 = natoc(rng, "S5", den, 3600, str(tmp_path / "Karta S5"), None)
    k1, l1 = natoc(rng, "S1II", den + timedelta(minutes=1), 5, str(tmp_path / "LUMIX" / "DCIM"), None)
    skupina = skupina_z([l5, l1], tmp_path)
    klipy = P.klipy_z_projektu(projekt_z([c for c, _, _ in k5 + k1]))
    P.sparuj(klipy, skupina["zapisy"])
    podle = {k.cesta: k for k in klipy}
    assert all(podle[c].kamera == "S5" and P.popisek(podle[c]) == n for c, n, _ in k5)
    spravne = sum(1 for c, n, _ in k1 if podle[c].kamera == "S1II" and P.popisek(podle[c]) == n)
    assert spravne >= len(k1) - 1  # podle času; souběžné záběry obou kamer mohou být nejednoznačné


def test_rucni_posun(tmp_path):
    klipy_pravda, logy, _ = scena(tmp_path, 3)
    skupina = skupina_z(logy, tmp_path)
    klipy = P.klipy_z_projektu(projekt_z([c for c, _, _ in klipy_pravda]))
    souhrn = P.sparuj(klipy, skupina["zapisy"], {"S5": -3640, "S1II": 10})
    assert souhrn["S5"]["rucne"] and souhrn["S5"]["posun_s"] == -3640
    podle = {k.cesta: k for k in klipy}
    assert all(P.popisek(podle[c]) == n for c, n, _ in klipy_pravda)


def test_sloucene_odeslani_a_smazani(tmp_path):
    den = datetime(2026, 10, 25, 14, 0, 0)
    a = {"format": P.FORMAT_ZAPISU, "id": "x", "zakazka": "Bauerova 5", "kamera": "S5", "exportovano": "2026-10-25T14:10",
         "zapisy": [zapis_telefonu(den, "mistnost", "kitchen", "Kuchyně", "1"),
                    zapis_telefonu(den + timedelta(minutes=1), "mistnost", "bedroom", "Ložnice", "2")]}
    b = json.loads(json.dumps(a))
    b["exportovano"] = "2026-10-25T14:30"
    b["zapisy"][1]["smazano"] = "2026-10-25T14:20"
    b["zapisy"].append(zapis_telefonu(den + timedelta(minutes=5), "mistnost", "garden", "Zahrada", "3"))
    c = dict(a, id="y", zakazka="Klamovka 2", kamera="S1II")
    skupiny = P.skupiny_zakazek([a, b, c])
    bauer = [g for g in skupiny if g["zakazka"] == "Bauerova 5"][0]
    assert [z.nazev for z in bauer["zapisy"]["S5"]] == ["Kuchyně", "Zahrada"]
    assert P.vyber_skupinu(skupiny, "BAUEROVA 5 střih v2")["zakazka"] == "Bauerova 5"
    assert P.vyber_skupinu(skupiny, "Něco úplně jiného")["zakazka"] == skupiny[0]["zakazka"]


def test_zapis_do_resolve_a_pro_fd_studio(tmp_path):
    klipy_pravda, logy, cizi = scena(tmp_path, 11)
    skupina = skupina_z(logy, tmp_path)
    pr = projekt_z([c for c, _, _ in klipy_pravda] + cizi)
    polozky = {it.props["File Path"]: it for it in pr.mp.koren.pod[0].klipy}
    polozky[klipy_pravda[0][0]].meta["Keywords"] = "dron, FD efekt"  # vlastní klíčová slova zůstanou
    # timeline: prvních 12 klipů kamery S5 za sebou + cizí klip; jeden vlastní marker uživatele
    tl = FTimeline()
    ram = tl.start
    vlastni_s5 = [c for c, _, _ in klipy_pravda if "karta1" in c][:12]
    for c in vlastni_s5 + [cizi[-1]]:
        tl.stopy[1].append(FTItem(ram, polozky[c]))
        ram += 100
    tl.markery[0] = {"barva": "Blue", "jmeno": "HOOK", "pozn": "", "delka": 1, "data": ""}
    pr.tl = tl

    volby = {"meta": True, "markery": True, "barvy": True, "biny": False, "studio": True, "posun": None}
    text = P.proved(pr, skupina, volby, zapsat=True)
    assert "Zapsáno do DaVinci" in text and "Přiřazení pro FD Studio" in text, text

    pravda = {c: (n, z) for c, n, z in klipy_pravda}
    prvni = polozky[klipy_pravda[0][0]]
    assert prvni.meta["Keywords"].split(", ")[:2] == ["dron", "FD efekt"]
    for c, (n, z) in pravda.items():
        kw = polozky[c].meta["Keywords"].split(", ")
        assert n in kw and ("Zmetek" in kw) == z
        assert polozky[c].meta["Scene"] == n
        assert polozky[c].barva is not None
    for c in cizi:
        assert "Keywords" not in polozky[c].meta

    # markery: vlastní zůstal, naše jen na změnách místnosti (zmetky vždy), vše s custom data
    assert tl.markery[0]["jmeno"] == "HOOK"
    nase = {r: m for r, m in tl.markery.items() if m["data"] == P.CUSTOM_DATA}
    ocekavane, minula = [], None
    for i, c in enumerate(vlastni_s5):
        n, z = pravda[c]
        if z:
            ocekavane.append("Zmetek")
        elif n != minula:
            ocekavane.append(n)
            minula = n
    assert [nase[r]["jmeno"] for r in sorted(nase)] == ocekavane
    assert 1 in nase or ocekavane[0] != pravda[vlastni_s5[0]][0]  # snímek 0 obsadil HOOK → posun o snímek

    # druhé spuštění: nic se nezdvojí
    P.proved(pr, skupina, volby, zapsat=True)
    nase2 = {r: m["jmeno"] for r, m in tl.markery.items() if m["data"] == P.CUSTOM_DATA}
    assert nase2 == {r: m["jmeno"] for r, m in nase.items()}
    kw = polozky[klipy_pravda[0][0]].meta["Keywords"].split(", ")
    assert len(kw) == len(set(kw))

    # přiřazení pro FD Studio: klíče RoomType a CSV pro Excel
    js = tmp_path / "icloud" / "FD-mistnosti-prirazeni_klamovka-2.json"
    data = json.loads(js.read_text(encoding="utf-8"))
    assert data["format"] == P.FORMAT_PRIRAZENI and data["zakazka"] == "Klamovka 2"
    assert set(data["kamery"]) == {"S5", "S1II"}
    kl = {os.path.basename(r["cesta"]) + r["kamera"]: r for r in data["klipy"]}
    for c, (n, z) in pravda.items():
        r = [x for x in data["klipy"] if x["cesta"] == c][0]
        assert r["mistnost_cs"] == n and r["mistnost"] in P.MISTNOSTI_CS and r["zmetek"] == z
    assert kl
    with io.open(str(tmp_path / "icloud" / "FD-mistnosti-prirazeni_klamovka-2.csv"), encoding="utf-8-sig") as f:
        radky = list(csv.reader(f, delimiter=";"))
    assert radky[0][0] == "soubor" and len(radky) == 1 + len(data["klipy"])


def test_biny(tmp_path):
    klipy_pravda, logy, _ = scena(tmp_path, 5)
    skupina = skupina_z(logy, tmp_path)
    pr = projekt_z([c for c, _, _ in klipy_pravda])
    P.proved(pr, skupina, {"meta": False, "markery": False, "biny": True, "studio": False}, zapsat=True)
    koren = [f for f in pr.mp.koren.pod if f.nazev == P.BIN_KOREN][0]
    nazvy = {f.nazev for f in koren.pod}
    assert {n for _, n, z in klipy_pravda if not z} <= nazvy
    assert sum(len(f.klipy) for f in koren.pod) == len(klipy_pravda)


def test_nahled_nic_nemeni(tmp_path):
    klipy_pravda, logy, _ = scena(tmp_path, 9)
    skupina = skupina_z(logy, tmp_path)
    pr = projekt_z([c for c, _, _ in klipy_pravda])
    text = P.proved(pr, skupina, {"meta": True, "markery": True}, zapsat=False)
    assert "Náhled" in text and "Kamera S5" in text and "Kamera S1II" in text
    assert all(not it.meta for it in pr.mp.koren.pod[0].klipy)
    assert not (tmp_path / "icloud" / "FD-mistnosti-prirazeni_klamovka-2.json").exists()
