#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FD Místnosti – plugin pro DaVinci Resolve (Workspace → Scripts → FD_Mistnosti).

Na place se po každém záběru klepne v telefonu místnost (stránka fd-board/mistnosti). Telefon uloží zápisy
(čas + místnost + kamera) do souboru FD-mistnosti_*.json, ten se uloží do iCloud Drive → FD Místnosti.
Tenhle skript zápisy načte, ke každému klipu z Media Poolu přečte z MP4/MOV čas natočení a model kamery a
klipu přiřadí místnost podle prvního zápisu po konci záběru. Rozdíl hodin kamera × telefon dopočítá sám.

Co zapisuje (nic nemaže, jen vlastní značky):
* Media Pool: klíčové slovo a Scéna = místnost (např. „Kuchyně“), u zmetku klíčové slovo „Zmetek“,
* aktuální timeline: marker na začátku každé místnosti (barva Mint, custom data „fd-mistnosti“; při dalším
  spuštění se staré markery pluginu smažou a vloží znovu, cizí markery zůstanou),
* volitelně barva klipu a biny „FD Místnosti / <místnost>“,
* přiřazení pro FD Studio: FD-mistnosti-prirazeni_<zakázka>.json + .csv vedle zápisů. Místnosti jsou
  v klíčích FD Studia (kitchen, living_room, … = RoomType v src/types/domain.ts).

Instalace (Mac): soubor zkopírovat do
  ~/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Edit/
Bez okna (DaVinci bez UI Manageru) poběží s výchozím nastavením a zprávu vypíše do Workspace → Console.
"""
from __future__ import print_function

import bisect
import csv
import io
import json
import math
import os
import re
import struct
import subprocess
import sys
import traceback
import unicodedata
from collections import Counter
from datetime import datetime, timedelta

VERZE = "1.0"
FORMAT_ZAPISU = "fd-mistnosti/1"
FORMAT_PRIRAZENI = "fd-mistnosti-prirazeni/1"
CUSTOM_DATA = "fd-mistnosti"
MARKER_BARVA = "Mint"
MARKER_ZMETEK = "Red"
BIN_KOREN = "FD Místnosti"

#: Klíče místností = RoomType z FD Studia, popisky jako v LABELS_CS.room.
MISTNOSTI_CS = {
    "living_room": "Obývák",
    "kitchen": "Kuchyně",
    "dining_room": "Jídelna",
    "bedroom": "Ložnice",
    "kids_room": "Dětský pokoj",
    "bathroom": "Koupelna",
    "office": "Pracovna",
    "hallway": "Chodba a hala",
    "stairs": "Schodiště",
    "basement": "Suterén",
    "technical": "Technická místnost",
    "garage": "Garáž",
    "terrace": "Terasa",
    "garden": "Zahrada",
    "pool": "Bazén",
    "facade": "Fasáda",
    "aerial": "Letecký pohled",
    "view": "Výhled",
    "other": "Jiné",
}

#: Barvy klipů v Media Poolu (jen s volbou „Obarvit klipy“). Resolve má 16 barev, některé místnosti se dělí.
BARVY_KLIPU = {
    "living_room": "Orange",
    "kitchen": "Yellow",
    "dining_room": "Apricot",
    "bedroom": "Purple",
    "kids_room": "Pink",
    "bathroom": "Teal",
    "office": "Navy",
    "hallway": "Tan",
    "stairs": "Beige",
    "basement": "Brown",
    "technical": "Brown",
    "garage": "Brown",
    "terrace": "Lime",
    "garden": "Green",
    "pool": "Blue",
    "facade": "Olive",
    "aerial": "Violet",
    "view": "Violet",
    "other": "Beige",
}
BARVA_ZMETEK = "Chocolate"

#: Párování (sekundy). Klip patří k prvnímu zápisu po svém konci.
PRED_S = 0.5  # zápis smí být nejvýš o tolik dřív než odhadnutý konec záběru (zaokrouhlení časů)
JISTE_S = 120.0  # zápis do 2 min po záběru = jistá shoda
DLOUHO_S = 20 * 60.0  # zápis do 20 min = shoda k ověření (víc záběrů, klepnuto po posledním)
OPRAVA_S = 20.0  # druhé klepnutí do 20 s bez záběru mezi nimi = oprava překlepu, platí to pozdější
OKOLI_S = 2 * 3600.0  # klipy dál než 2 h od zápisů nejsou z tohohle natáčení
MAX_POSUN_S = 14 * 3600.0  # rozdíl hodin kamera × telefon (pásma, zapomenutý letní čas…)
REAKCE_S = 1.0

VIDEO_PRIPONY = {".mp4", ".mov", ".m4v", ".mxf", ".avi", ".mts", ".m2ts", ".3gp", ".insv", ".lrv"}

_EPOCHA_1904 = datetime(1904, 1, 1)
_EPOCHA_1970 = datetime(1970, 1, 1)


# =============================================================================================
# Drobnosti
# =============================================================================================

def fold(s):
    """Bez diakritiky, malými písmeny („Místnosti“ → „mistnosti“)."""
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(ch for ch in s if not unicodedata.combining(ch)).lower()


def slug(s, limit=40):
    out = re.sub(r"[^A-Za-z0-9]+", "-", fold(s)).strip("-")[:limit]
    return out or "zakazka"


def norm_kamera(s):
    return re.sub(r"[^A-Z0-9]", "", fold(s).upper())


def sekundy(dt):
    """Naivní datum → sekundy na ose „místní čas, jako by byl UTC“ (stejná osa jako zápisy z telefonu)."""
    return (dt - _EPOCHA_1970).total_seconds()


def z_sekund(s):
    return _EPOCHA_1970 + timedelta(seconds=s)


def hms(s):
    return z_sekund(s).strftime("%H:%M:%S")


def popis_posunu(p):
    znak = "+" if p >= 0 else "−"
    p = abs(int(round(p)))
    h, zb = divmod(p, 3600)
    m, s = divmod(zb, 60)
    if h:
        return "%s%d h %d min %d s" % (znak, h, m, s)
    if m:
        return "%s%d min %d s" % (znak, m, s)
    return "%s%d s" % (znak, s)


# =============================================================================================
# Čtení MP4 / MOV: čas natočení (mvhd), délka a model kamery
# =============================================================================================

def _boxy(f, zacatek, konec):
    """Boxy ISO BMFF v rozsahu souboru: (typ, začátek obsahu, konec boxu)."""
    pos = zacatek
    while pos + 8 <= konec:
        f.seek(pos)
        hlava = f.read(8)
        if len(hlava) < 8:
            return
        velikost, typ = struct.unpack(">I4s", hlava)
        hlen = 8
        if velikost == 1:
            velka = f.read(8)
            if len(velka) < 8:
                return
            velikost = struct.unpack(">Q", velka)[0]
            hlen = 16
        elif velikost == 0:
            velikost = konec - pos
        if velikost < hlen:
            return
        yield typ, pos + hlen, min(pos + velikost, konec)
        pos += velikost


_MODEL_RE = re.compile(rb"(?:DC|DMC)-[A-Z0-9]{2,12}")


def kamera_z_modelu(model):
    """„DC-S5“ → „S5“, „DC-S1M2“ → „S1II“, „DC-S5M2X“ → „S5IIX“, „DC-S1M2ES“ → „S1IIE“."""
    if not model:
        return None
    m = model.upper()
    for pref in ("DMC-", "DC-"):
        if m.startswith(pref):
            m = m[len(pref):]
    zvlast = {"S1M2ES": "S1IIE"}
    if m in zvlast:
        return zvlast[m]
    m = re.sub(r"M2(?=[A-Z]?$)", "II", m)
    return m


def precti_video(cesta):
    """Čas, délka a model z hlavičky videa. Vrací dict nebo None, když soubor nejde otevřít.

    cas      – naivní datetime z mvhd (u Panasonicu začátek záběru; pásmo neznámé, posun dorovná párování),
               bez mvhd poslední změna souboru (= konec záběru, `cas_je_konec`),
    delka_s  – délka záběru v sekundách (0, když není známá),
    model    – např. „DC-S5“, nebo None.
    """
    try:
        st = os.stat(cesta)
    except OSError:
        return None
    vysledek = {"cas": None, "delka_s": 0.0, "model": None, "cas_je_konec": False, "zdroj": "soubor"}
    try:
        with open(cesta, "rb") as f:
            hlavicka = f.read(256 * 1024)
            moov = None
            for typ, od, do in _boxy(f, 0, st.st_size):
                if typ == b"moov":
                    f.seek(od)
                    moov = f.read(min(do - od, 32 * 1024 * 1024))
                    break
            if moov is not None:
                mvhd = _najdi_box(moov, b"mvhd")
                if mvhd is not None and len(mvhd) >= 20:
                    verze = mvhd[0]
                    if verze == 1 and len(mvhd) >= 32:
                        vytvoreno, _zmena, meritko, delka = struct.unpack(">QQIQ", mvhd[4:32])
                    else:
                        vytvoreno, _zmena, meritko, delka = struct.unpack(">IIII", mvhd[4:20])
                    if meritko:
                        vysledek["delka_s"] = delka / float(meritko)
                    if vytvoreno > 0:
                        cas = _EPOCHA_1904 + timedelta(seconds=vytvoreno)
                        if 2000 <= cas.year <= 2100:
                            vysledek["cas"] = cas
                            vysledek["zdroj"] = "mvhd"
            for blok in (moov or b"", hlavicka):
                m = _MODEL_RE.search(blok)
                if m:
                    vysledek["model"] = m.group(0).decode("ascii")
                    break
    except (OSError, struct.error, ValueError, OverflowError):
        pass
    if vysledek["cas"] is None:
        vysledek["cas"] = datetime.fromtimestamp(st.st_mtime)
        vysledek["cas_je_konec"] = True
    return vysledek


def _najdi_box(data, hledany, hloubka=0):
    """Obsah prvního boxu daného typu uvnitř bajtů (rekurzivně přes kontejnery)."""
    kontejnery = {b"moov", b"trak", b"mdia", b"minf", b"stbl", b"udta", b"edts"}
    pos = 0
    while pos + 8 <= len(data):
        velikost, typ = struct.unpack(">I4s", data[pos:pos + 8])
        hlen = 8
        if velikost == 1 and pos + 16 <= len(data):
            velikost = struct.unpack(">Q", data[pos + 8:pos + 16])[0]
            hlen = 16
        elif velikost == 0:
            velikost = len(data) - pos
        if velikost < hlen:
            return None
        if typ == hledany:
            return data[pos + hlen:pos + velikost]
        if typ in kontejnery and hloubka < 6:
            uvnitr = _najdi_box(data[pos + hlen:pos + velikost], hledany, hloubka + 1)
            if uvnitr is not None:
                return uvnitr
        pos += velikost
    return None


# =============================================================================================
# Zápisy z telefonu
# =============================================================================================

def _je_soubor_zapisu(nazev):
    n = fold(nazev)
    return n.startswith("fd-mistnosti_") and n.endswith(".json")


def vychozi_slozky():
    """Kde plugin hledá zápisy: iCloud Drive / FD Místnosti, Stažené, Plocha, Dokumenty, Google Disk."""
    home = os.path.expanduser("~")
    slozky = []
    env = os.environ.get("FD_MISTNOSTI_DIR")
    if env:
        slozky.extend(p for p in env.split(os.pathsep) if p)
    icloud = os.path.join(home, "Library", "Mobile Documents", "com~apple~CloudDocs")
    for zaklad in (icloud, os.path.join(home, "Documents"), home):
        for jmeno in ("FD Místnosti", "FD Mistnosti"):
            slozky.append(os.path.join(zaklad, jmeno))
    cloud = os.path.join(home, "Library", "CloudStorage")
    try:
        for ucet in sorted(os.listdir(cloud)):
            if ucet.startswith("GoogleDrive"):
                for disk in ("My Drive", "Můj disk"):
                    for jmeno in ("FD Místnosti", "FD Mistnosti"):
                        slozky.append(os.path.join(cloud, ucet, disk, jmeno))
    except OSError:
        pass
    slozky.extend([os.path.join(home, "Downloads"), os.path.join(home, "Desktop")])
    vysledek, videno = [], set()
    for s in slozky:
        klic = fold(os.path.normpath(s))
        if klic not in videno and os.path.isdir(s):
            videno.add(klic)
            vysledek.append(s)
    return vysledek


def najdi_soubory_zapisu(slozky):
    soubory = []
    for s in slozky:
        try:
            jmena = os.listdir(s)
        except OSError:
            continue
        for j in jmena:
            if _je_soubor_zapisu(j):
                soubory.append(os.path.join(s, j))
    return soubory


def nacti_zapis(cesta):
    """Načte a ověří jeden soubor z telefonu. Vrací dict nebo None (cizí / poškozený soubor)."""
    try:
        with io.open(cesta, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("format") != FORMAT_ZAPISU:
        return None
    if not isinstance(data.get("zapisy"), list) or not data.get("kamera"):
        return None
    data["_cesta"] = cesta
    return data


def _cas_zapisu(z):
    """Zápis → sekundy na ose místního času telefonu (ms od epochy + posun pásma v minutách)."""
    ms = z.get("ms")
    off = z.get("off")
    if isinstance(ms, (int, float)) and isinstance(off, (int, float)):
        return ms / 1000.0 + off * 60.0
    cas = str(z.get("cas") or "")
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d+))?", cas)
    if not m:
        return None
    dt = datetime(*[int(x) for x in m.groups()[:6]])
    zlomek = float("0." + m.group(7)) if m.group(7) else 0.0
    return sekundy(dt) + zlomek


class Zapis(object):
    __slots__ = ("id", "t", "typ", "mistnost", "nazev", "kamera")

    def __init__(self, id_, t, typ, mistnost, nazev, kamera):
        self.id, self.t, self.typ, self.mistnost, self.nazev, self.kamera = id_, t, typ, mistnost, nazev, kamera


def skupiny_zakazek(logy):
    """Zápisy seskupené podle zakázky: [{zakazka, klic, logy, kamery, posledni}] od nejnovější."""
    sk = {}
    for log in logy:
        klic = fold(str(log.get("zakazka") or "")).strip()
        g = sk.setdefault(klic, {"zakazka": str(log.get("zakazka") or "Bez názvu"), "klic": klic, "logy": [],
                                 "posledni": ""})
        g["logy"].append(log)
        g["posledni"] = max(g["posledni"], str(log.get("exportovano") or log.get("zalozeno") or ""))
    out = []
    for g in sk.values():
        zapisy = sluc_zapisy(g["logy"])
        g["kamery"] = {k: len(v) for k, v in zapisy.items()}
        g["zapisy"] = zapisy
        out.append(g)
    out.sort(key=lambda g: g["posledni"], reverse=True)
    return out


def sluc_zapisy(logy):
    """Zápisy podle kamery. Stejný zápis z víc odeslání se bere jednou; smazaný v kterémkoli souboru = smazaný."""
    podle_id = {}
    smazane = set()
    for log in logy:
        kamera = str(log.get("kamera"))
        for z in log.get("zapisy") or []:
            if not isinstance(z, dict):
                continue
            zid = "%s:%s" % (kamera, z.get("id") or "%s:%s:%s" % (log.get("id"), z.get("ms"), z.get("nazev")))
            if z.get("smazano"):
                smazane.add(zid)
                continue
            t = _cas_zapisu(z)
            typ = z.get("typ") if z.get("typ") in ("mistnost", "zmetek") else None
            if t is None or typ is None:
                continue
            mistnost = z.get("mistnost") if z.get("mistnost") in MISTNOSTI_CS else "other"
            nazev = str(z.get("nazev") or MISTNOSTI_CS[mistnost])[:40]
            podle_id[zid] = Zapis(zid, t, typ, mistnost if typ == "mistnost" else None, nazev, kamera)
    out = {}
    for zid, z in podle_id.items():
        if zid not in smazane:
            out.setdefault(z.kamera, []).append(z)
    for v in out.values():
        v.sort(key=lambda z: z.t)
    return out


def vyber_skupinu(skupiny, nazev_projektu):
    """Zakázka, která se nejvíc podobá názvu projektu v DaVinci; jinak nejnovější."""
    if not skupiny:
        return None
    slova = set(re.findall(r"[a-z0-9]+", fold(nazev_projektu or "")))
    nejlepsi, skore = None, 0
    for g in skupiny:
        sz = set(re.findall(r"[a-z0-9]+", g["klic"]))
        s = len(slova & sz)
        if s > skore:
            nejlepsi, skore = g, s
    return nejlepsi or skupiny[0]


# =============================================================================================
# Párování klipů se zápisy
# =============================================================================================

class Klip(object):
    """Jeden soubor z Media Poolu. `konec` = konec záběru na ose kamery (sekundy) podle zvolené hypotézy."""

    def __init__(self, klic, cesta, nazev, info, polozka=None):
        self.klic = klic
        self.cesta = cesta
        self.nazev = nazev
        self.polozka = polozka
        self.cas = sekundy(info["cas"])
        self.delka = float(info.get("delka_s") or 0.0)
        self.cas_je_konec = bool(info.get("cas_je_konec"))
        self.model = info.get("model")
        self.kamera = None
        self.kamera_jak = None
        self.cizi = False
        # výsledek
        self.zapis = None
        self.jistota = 0.0
        self.mezera = None
        self.zmetek = False
        self.konec_telefon = None

    def konec(self, cas_je_zacatek=True):
        if self.cas_je_konec or not cas_je_zacatek:
            return self.cas
        return self.cas + self.delka


def _prvni_po(casy, x):
    j = bisect.bisect_left(casy, x - PRED_S)
    if j < len(casy):
        return j, casy[j] - x
    return None, None


def _vaha(r):
    """Věrohodnost mezery klepnutí po záběru: do 10 s plně (bez odměny za kratší), pak klesá."""
    return 1.0 if r <= 10.0 else math.exp(-(r - 10.0) / 8.0)


def skore_posunu(konce, casy, posun):
    """(počet jistých shod klipů, skóre zápisů).

    Skóre zápisů: ke každému klepnutí nejbližší konec záběru před ním a váha podle mezery (`_vaha`).
    Skutečný posun dá skoro každému zápisu záběr pár sekund před ním; cizí klipy (jiné natáčení stejnou
    kamerou) dají mezery rozházené a jejich počet skóre nezvedne – každý zápis počítá jen jeden záběr.
    """
    dobre = 0
    for e in konce:
        j, g = _prvni_po(casy, e + posun)
        if j is not None and g <= JISTE_S:
            dobre += 1
    return dobre, sum(_vaha(r) for r in _mezery_zapisu(konce, casy, posun))


def _parovani_zapisu(serazene, casy, posun):
    """[(index záběru, mezera)] pro zápisy, před kterými nějaký záběr je; `serazene` = seřazené konce."""
    out = []
    for t in casy:
        j = bisect.bisect_right(serazene, t - posun) - 1
        if j >= 0:
            out.append((j, t - (serazene[j] + posun)))
    return out


def _mezery_zapisu(konce, casy, posun):
    """Pro každý zápis mezera od konce posledního záběru před ním (zápisy bez záběru vynechá)."""
    return [r for _j, r in _parovani_zapisu(sorted(konce), casy, posun)]


def tesnost(konce, casy, posun):
    """Ostré skóre e^(−mezera/8 s): rozliší hypotézy, které mají stejné (ploché) skóre zápisů."""
    return sum(math.exp(-r / 8.0) for r in _mezery_zapisu(konce, casy, posun))


def _blizko_prioru(p):
    """Hodiny kamery bývají přesné na minuty, nebo posunuté o celé hodiny (pásmo, letní čas)."""
    h = int(round(p / 3600.0))
    return abs(h) <= 2 and abs(p - h * 3600.0) <= 15 * 60.0


def _v_zaberu(useky, casy, posun):
    """Kolik klepnutí by padlo doprostřed natáčení (rezerva 0,3 s na zaokrouhlení času v souboru).
    `useky` = [(začátek, konec)] seřazené podle začátku. Při natáčení se do telefonu neklepe."""
    zacatky = [u[0] for u in useky]
    n = 0
    for t in casy:
        x = t - posun
        j = bisect.bisect_right(zacatky, x - 0.3) - 1
        if j >= 0 and useky[j][1] - 0.3 > x:
            n += 1
    return n


def odhadni_posun(konce, casy, delky=None):
    """Rozdíl hodin telefon − kamera (sekundy), aby každý záběr skončil chvíli před „svým“ zápisem.

    1. Hrubě: kandidáti z nejčastějších rozdílů zápis − konec klipu (po 5 s), vyhrává nejvyšší skóre
       zápisů; posun daleko od nuly a celých hodin musí být výrazně lepší (1,5×) než nejlepší blízký.
    2. Jemně: v okolí −60 až +30 s se přiřazení zápis → poslední záběr před ním mění jen ve „zlomech“
       (posun = zápis − konec záběru). Mezi zlomy je přiřazení stejné. Vybere se úsek, kde nejméně
       klepnutí padne doprostřed natáčení (`delky` = délky záběrů ve stejném pořadí jako `konce`; při
       natáčení se do telefonu neklepe), pak s nejvyšším skóre, pak s nejvíc zápisy, které mají vlastní
       záběr, při shodě ten nejníž (přestřelený posun posílá záběr k zápisu další místnosti). Posun je
       1 s pod horní hranou úseku: každý zápis zůstane aspoň 1 s za svým záběrem.
    Vrací (posun, počet jistých shod, skóre zápisů).
    """
    if not konce or not casy:
        return 0.0, 0, 0.0
    hist = Counter()
    for e in konce:
        for t in casy:
            d = t - e
            if -MAX_POSUN_S <= d <= MAX_POSUN_S:
                hist[int(d // 5)] += 1
    kandidati = {0.0}
    for b, _ in hist.most_common(150):
        kandidati.add(b * 5.0)  # spodní hrana koše: záběr zůstane před zápisem
    skore = {p: skore_posunu(konce, casy, p) for p in kandidati}

    def klic(p):
        # počet shod klipů sem nepatří (cizí klipy by ho nafoukly); při shodě blíž celé hodině a pak nejnižší
        # posun – vyšší posun se stejným skóre je typicky přestřelený (zápis spárovaný s dřívějším záběrem)
        return (round(skore[p][1], 6), -abs(int(round(p / 3600.0))), -p)

    vse = max(kandidati, key=klic)
    blizke = max((p for p in kandidati if _blizko_prioru(p)), key=klic)
    hrubo = vse if skore[vse][1] > 1.5 * skore[blizke][1] else blizke

    zlomy = sorted({t - e for e in konce for t in casy if -60.0 <= t - e - hrubo <= 30.0} | {hrubo - 60.0, hrubo + 30.0})
    serazene = sorted(konce)
    useky = sorted((e - d, e) for e, d in zip(konce, delky)) if delky else []
    nejlepsi = None
    for dole, nahore in zip(zlomy, zlomy[1:]):
        if nahore - dole < 1e-3:
            continue
        horni = nahore - 1e-3  # těsně pod zlomem: přiřazení úseku, nejmenší mezery
        mezery = _parovani_zapisu(serazene, casy, horni)
        sk = round(sum(_vaha(r) for _j, r in mezery), 6)
        # zápisy, které mají „svůj“ záběr (nesdílený se sousedním zápisem): podstřelený posun spáruje
        # zápis se záběrem, který patří až dalšímu zápisu
        vlastni = sum(1 for i, (j, _r) in enumerate(mezery) if (i == 0 or mezery[i - 1][0] != j))
        bod = max(dole + 1e-3, nahore - REAKCE_S)
        klic_useku = (-_v_zaberu(useky, casy, bod) if useky else 0, sk, vlastni)
        if nejlepsi is None or klic_useku > nejlepsi[0]:
            nejlepsi = (klic_useku, dole, nahore)
    _k, dole, nahore = nejlepsi
    posun = max(nahore - REAKCE_S, (dole + nahore) / 2.0)
    return (posun,) + skore_posunu(konce, casy, posun)


def kamera_z_cesty(cesta, kamery):
    """Kamera podle složky („Karta S5/…“, „S1II_karta/…“). Vrací název kamery ze zápisů nebo None."""
    useky = [norm_kamera(u) for u in re.split(r"[\\/]", cesta or "") if u]
    silne, slabe = {}, {}
    for k in kamery:
        n = norm_kamera(k)
        if not n:
            continue
        silne[k] = {n}
        if n.endswith("II"):
            silne[k].add(n[:-2] + "M2")
            slabe[k] = {n[:-2]}
    nalezene = [k for k, al in silne.items() if any(a in u for a in al for u in useky)]
    if len(nalezene) == 1:
        return nalezene[0]
    if len(nalezene) > 1:  # „S5“ je i v „S5II“: vyhrává nejdelší shoda
        nalezene.sort(key=lambda k: -len(norm_kamera(k)))
        return nalezene[0]
    nalezene = [k for k, al in slabe.items() if any(u == a or u.endswith(a) for a in al for u in useky)]
    return nalezene[0] if len(nalezene) == 1 else None


def urci_kamery(klipy, kamery):
    """Klipu přiřadí kameru ze zápisů: model v souboru → složka → jediná kamera v zápisech.

    Klip s modelem, který v zápisech není (a složka ho neurčí), je cizí: k zápisům se nepáruje vůbec.
    Klip bez modelu i bez složky zůstane s kamerou None a dostane ji později podle času.
    """
    podle_normy = {norm_kamera(k): k for k in kamery}
    for k in klipy:
        km = kamera_z_modelu(k.model)
        if km and norm_kamera(km) in podle_normy:
            k.kamera, k.kamera_jak = podle_normy[norm_kamera(km)], "model %s" % k.model
            continue
        kc = kamera_z_cesty(k.cesta, kamery)
        if kc:
            k.kamera, k.kamera_jak = kc, "složka"
        elif km:
            k.cizi, k.kamera_jak = True, "model %s není v zápisech" % k.model
        elif len(kamery) == 1:
            k.kamera, k.kamera_jak = list(kamery)[0], "jediná kamera v zápisech"


def sparuj(klipy, zapisy, rucni_posun=None):
    """Přiřadí klipům místnosti. `zapisy` = {kamera: [Zapis]}. Vrací souhrn po kamerách.

    rucni_posun – sekundy, nebo {kamera: sekundy}; None = automaticky.
    """
    kamery = list(zapisy.keys())
    urci_kamery(klipy, kamery)
    souhrn = {}
    for kam in kamery:
        mistnosti = [z for z in zapisy[kam] if z.typ == "mistnost"]
        casy = [z.t for z in mistnosti]
        # posun se odhaduje ze všech klepnutí: i „Zmetek“ padá hned po záběru (a bývá těsnější než místnost)
        casy_vse = [z.t for z in zapisy[kam]]
        vlastni = [k for k in klipy if k.kamera == kam]
        nezname = [k for k in klipy if k.kamera is None and not k.cizi]
        vzorek = vlastni if len(vlastni) >= 3 else vlastni + nezname
        rp = rucni_posun.get(kam) if isinstance(rucni_posun, dict) else rucni_posun
        nejlepsi = None
        for hypoteza in (True, False):
            konce = [k.konec(hypoteza) for k in vzorek]
            if rp is not None:
                posun = float(rp)
                dobre, mekke = skore_posunu(konce, casy_vse, posun)
            else:
                posun, dobre, mekke = odhadni_posun(konce, casy_vse, [k.delka for k in vzorek])
            # čas začátku i konce dá podobné skóre, ale jen ten správný těsné mezery
            klic = (round(mekke, 6), round(tesnost(konce, casy_vse, posun), 6), dobre)
            if nejlepsi is None or klic > nejlepsi[1]:
                nejlepsi = (posun, klic, hypoteza)
        posun, _skore, hypoteza = nejlepsi
        souhrn[kam] = {"posun_s": posun, "cas_je_zacatek": hypoteza, "zapisu": len(zapisy[kam]),
                       "mistnosti": mistnosti, "casy": casy, "rucne": rp is not None}

    # klipy bez kamery: ke kameře, jejíž zápis po konci klipu je nejblíž
    for k in klipy:
        if k.kamera is not None or k.cizi or not souhrn:
            continue
        kandidati = []
        for kam, s in souhrn.items():
            j, g = _prvni_po(s["casy"], k.konec(s["cas_je_zacatek"]) + s["posun_s"])
            if j is not None and g <= JISTE_S:
                kandidati.append((g, kam))
        if kandidati:
            kandidati.sort()
            k.kamera, k.kamera_jak = kandidati[0][1], "podle času (model ani složka kameru neurčily)"
            if len(kandidati) > 1:
                k.kamera_jak += ", nejisté"

    for kam, s in souhrn.items():
        vlastni = [k for k in klipy if k.kamera == kam]
        prvni = s["casy"][0] if s["casy"] else None
        posledni = s["casy"][-1] if s["casy"] else None
        for k in vlastni:
            k.konec_telefon = k.konec(s["cas_je_zacatek"]) + s["posun_s"]
        konce_tel = sorted(k.konec_telefon for k in vlastni)
        for k in vlastni:
            x = k.konec_telefon
            if prvni is None or x < prvni - OKOLI_S or x > posledni + OKOLI_S:
                continue
            j, g = _prvni_po(s["casy"], x)
            if j is None or g > DLOUHO_S:
                continue
            # překlep opravený dalším klepnutím (bez Zpět): mezi klepnutími nevznikl žádný záběr
            while (j + 1 < len(s["casy"]) and s["casy"][j + 1] - s["casy"][j] <= OPRAVA_S
                   and bisect.bisect_right(konce_tel, s["casy"][j + 1]) == bisect.bisect_right(konce_tel, s["casy"][j])):
                j += 1
                g = s["casy"][j] - x
            k.zapis, k.mezera = s["mistnosti"][j], g
            k.jistota = 0.95 if g <= JISTE_S else 0.6
            if "nejisté" in (k.kamera_jak or ""):
                k.jistota = min(k.jistota, 0.6)
        # zmetek = poslední záběr této kamery před klepnutím na „Zmetek“
        serazene = sorted((k for k in vlastni if k.konec_telefon is not None), key=lambda k: k.konec_telefon)
        konce = [k.konec_telefon for k in serazene]
        for z in zapisy[kam]:
            if z.typ != "zmetek":
                continue
            j = bisect.bisect_right(konce, z.t + PRED_S) - 1
            if j >= 0 and z.t - konce[j] <= DLOUHO_S:
                serazene[j].zmetek = True
        v_okoli = [k for k in vlastni if k.konec_telefon is not None and prvni is not None
                   and prvni - OKOLI_S <= k.konec_telefon <= posledni + OKOLI_S]
        s["klipu"] = len(v_okoli)
        s["jiste"] = sum(1 for k in v_okoli if k.zapis and k.jistota >= 0.9)
        s["overit"] = sum(1 for k in v_okoli if k.zapis and k.jistota < 0.9)
        s["bez"] = [k for k in v_okoli if not k.zapis and not k.zmetek]
        s["zmetky"] = sum(1 for k in v_okoli if k.zmetek)
    return souhrn


def popisek(k):
    if k.zapis is None:
        return None
    return k.zapis.nazev or MISTNOSTI_CS.get(k.zapis.mistnost, "Jiné")


# =============================================================================================
# DaVinci Resolve
# =============================================================================================

def _prostredi():
    """(resolve, fusion, bmd) z prostředí skriptu v DaVinci; mimo DaVinci (None, None, None)."""
    g = globals()
    bmd = g.get("bmd")
    resolve = g.get("resolve")
    if resolve is None and g.get("app") is not None:
        try:
            resolve = g["app"].GetResolve()
        except Exception:  # noqa: BLE001
            resolve = None
    if resolve is None and bmd is not None:
        try:
            resolve = bmd.scriptapp("Resolve")
        except Exception:  # noqa: BLE001
            resolve = None
    if resolve is None:
        try:
            import DaVinciResolveScript as dvr  # type: ignore
            resolve = dvr.scriptapp("Resolve")
            bmd = bmd or dvr
        except Exception:  # noqa: BLE001
            resolve = None
    fusion = None
    if resolve is not None:
        try:
            fusion = resolve.Fusion()
        except Exception:  # noqa: BLE001
            fusion = None
    return resolve, fusion, bmd


def _vsechny_polozky(slozka):
    for c in slozka.GetClipList() or []:
        yield c
    for s in slozka.GetSubFolderList() or []:
        for c in _vsechny_polozky(s):
            yield c


def klipy_z_projektu(projekt, cache=None):
    """Videoklipy z Media Poolu (bez timeline, compoundů a fotek) s časem a modelem z hlavičky souboru."""
    mp = projekt.GetMediaPool()
    cache = {} if cache is None else cache
    klipy, videno = [], set()
    for it in _vsechny_polozky(mp.GetRootFolder()):
        try:
            cesta = it.GetClipProperty("File Path") or ""
        except Exception:  # noqa: BLE001
            continue
        if not cesta or os.path.splitext(cesta)[1].lower() not in VIDEO_PRIPONY:
            continue
        klic = os.path.normpath(cesta)
        if klic in videno:  # stejný soubor ve dvou binech: značky stejně dostanou obě položky
            klipy.append(Klip(klic, cesta, os.path.basename(cesta), cache[klic], it))
            continue
        info = cache.get(klic) or precti_video(cesta)
        if not info:
            continue
        cache[klic] = info
        videno.add(klic)
        klipy.append(Klip(klic, cesta, os.path.basename(cesta), info, it))
    return klipy


def _klicova_slova(text):
    return [s.strip() for s in re.split(r"[,;]", text or "") if s.strip()]


def _nase_slova(zapisy):
    nase = set(MISTNOSTI_CS.values()) | {"Zmetek"}
    for seznam in zapisy.values():
        for z in seznam:
            if z.nazev:
                nase.add(z.nazev)
    return nase


def _metadata(it, klic):
    try:
        v = it.GetMetadata(klic)
    except Exception:  # noqa: BLE001
        return ""
    return v if isinstance(v, str) else ""


def zapis_do_resolve(projekt, klipy, zapisy, volby):
    """Zapíše výsledek párování do projektu. Vrací (počty, varování)."""
    pocty = {"meta": 0, "barvy": 0, "biny": 0, "markery": 0, "timeline": None}
    varovani = []
    nase = _nase_slova(zapisy)
    mp = projekt.GetMediaPool()

    if volby.get("meta", True):
        for k in klipy:
            it = k.polozka
            if it is None or (k.zapis is None and not k.zmetek):
                continue
            stara = _klicova_slova(_metadata(it, "Keywords"))
            nova = [s for s in stara if s not in nase]
            if k.zapis is not None:
                nova.append(popisek(k))
            if k.zmetek:
                nova.append("Zmetek")
            try:
                ok = it.SetMetadata("Keywords", ", ".join(nova))
                scena = _metadata(it, "Scene")
                if k.zapis is not None and (not scena or scena in nase):
                    it.SetMetadata("Scene", popisek(k))
                if ok:
                    pocty["meta"] += 1
            except Exception as exc:  # noqa: BLE001
                varovani.append("Metadata %s: %s" % (k.nazev, exc))

    if volby.get("barvy"):
        for k in klipy:
            if k.polozka is None or (k.zapis is None and not k.zmetek):
                continue
            barva = BARVA_ZMETEK if k.zmetek else BARVY_KLIPU.get(k.zapis.mistnost, "Beige")
            try:
                if k.polozka.SetClipColor(barva):
                    pocty["barvy"] += 1
            except Exception as exc:  # noqa: BLE001
                varovani.append("Barva %s: %s" % (k.nazev, exc))

    if volby.get("biny"):
        try:
            koren = _bin(mp, mp.GetRootFolder(), BIN_KOREN)
            podle = {}
            for k in klipy:
                if k.polozka is not None and k.zapis is not None:
                    podle.setdefault("Zmetky" if k.zmetek else popisek(k), []).append(k.polozka)
            for nazev, polozky in sorted(podle.items()):
                if mp.MoveClips(polozky, _bin(mp, koren, nazev[:60])):
                    pocty["biny"] += len(polozky)
                else:
                    varovani.append("Bin %s: DaVinci klipy nepřesunul." % nazev)
        except Exception as exc:  # noqa: BLE001
            varovani.append("Biny: %s" % exc)

    if volby.get("markery", True):
        tl = projekt.GetCurrentTimeline()
        if not tl:
            varovani.append("Není otevřená žádná timeline, markery jsem nevložil.")
        else:
            try:
                pocty["markery"] = _markery(tl, klipy)
                pocty["timeline"] = tl.GetName()
            except Exception as exc:  # noqa: BLE001
                varovani.append("Markery: %s" % exc)
    return pocty, varovani


def _bin(mp, rodic, nazev):
    for sub in rodic.GetSubFolderList() or []:
        if sub.GetName() == nazev:
            return sub
    nova = mp.AddSubFolder(rodic, nazev)
    if not nova:
        raise RuntimeError("DaVinci nezaložil bin %s." % nazev)
    return nova


def _markery(tl, klipy):
    """Smaže staré markery pluginu a vloží marker na začátek každé místnosti (a na každý zmetek)."""
    for _ in range(10000):
        if not tl.DeleteMarkerByCustomData(CUSTOM_DATA):
            break
    podle_cesty = {}
    for k in klipy:
        if k.zapis is not None or k.zmetek:
            podle_cesty[k.klic] = k
    start = int(tl.GetStartFrame() or 0)
    polozky = []
    for stopa in range(1, int(tl.GetTrackCount("video") or 0) + 1):
        for it in tl.GetItemListInTrack("video", stopa) or []:
            mpi = it.GetMediaPoolItem()
            if mpi is None:
                continue
            try:
                cesta = mpi.GetClipProperty("File Path") or ""
            except Exception:  # noqa: BLE001
                continue
            k = podle_cesty.get(os.path.normpath(cesta)) if cesta else None
            if k is not None:
                polozky.append((int(it.GetStart()), stopa, k))
    polozky.sort(key=lambda p: (p[0], p[1]))
    vlozeno, minula, posledni_ram = 0, None, None
    for ram, _stopa, k in polozky:
        if ram == posledni_ram:  # stejné místo na víc stopách: platí nižší stopa
            continue
        if k.zmetek:
            jmeno, barva = "Zmetek", MARKER_ZMETEK
            pozn = "%s · %s · zápis Zmetek" % (k.kamera or "?", k.nazev)
        else:
            jmeno, barva = popisek(k), MARKER_BARVA
            if jmeno == minula:
                continue
            pozn = "%s · %s · zápis %s%s" % (k.kamera or "?", k.nazev, hms(k.zapis.t),
                                             "" if k.jistota >= 0.9 else " · ověřit")
        for posun in range(4):  # na snímku už může být cizí marker
            if tl.AddMarker(ram - start + posun, barva, jmeno, pozn, 1, CUSTOM_DATA):
                vlozeno += 1
                break
        posledni_ram = ram
        if not k.zmetek:
            minula = jmeno
    return vlozeno


# =============================================================================================
# Přiřazení pro FD Studio
# =============================================================================================

def prirazeni(skupina, klipy, souhrn, projekt_nazev):
    radky = []
    for k in sorted(klipy, key=lambda k: (k.kamera or "", k.konec_telefon or k.cas)):
        if k.zapis is None and not k.zmetek:
            continue
        radky.append({
            "soubor": k.nazev,
            "cesta": k.cesta,
            "kamera": k.kamera,
            "konec_zaberu": z_sekund(k.konec_telefon).strftime("%Y-%m-%dT%H:%M:%S") if k.konec_telefon else None,
            "delka_s": round(k.delka, 2),
            "mistnost": k.zapis.mistnost if k.zapis else None,
            "mistnost_cs": popisek(k),
            "jistota": round(k.jistota, 2),
            "zmetek": k.zmetek,
            "zapis": z_sekund(k.zapis.t).strftime("%Y-%m-%dT%H:%M:%S") if k.zapis else None,
        })
    return {
        "format": FORMAT_PRIRAZENI,
        "plugin": "FD Místnosti %s" % VERZE,
        "zakazka": skupina["zakazka"],
        "projekt_davinci": projekt_nazev,
        "vytvoreno": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "pozn": "mistnost = RoomType FD Studia; časy jsou místní čas telefonu",
        "kamery": {kam: {"posun_hodin_s": round(s["posun_s"], 1), "zapisu": s["zapisu"], "klipu": s.get("klipu", 0),
                         "jiste": s.get("jiste", 0), "overit": s.get("overit", 0), "zmetky": s.get("zmetky", 0)}
                   for kam, s in souhrn.items()},
        "klipy": radky,
    }


def uloz_prirazeni(data, slozka):
    zaklad = os.path.join(slozka, "FD-mistnosti-prirazeni_%s" % slug(data["zakazka"]))
    with io.open(zaklad + ".json", "w", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False, indent=1))
    with io.open(zaklad + ".csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["soubor", "kamera", "konec záběru", "místnost", "klíč FD Studia", "jistota", "zmetek", "cesta"])
        for r in data["klipy"]:
            w.writerow([r["soubor"], r["kamera"] or "", (r["konec_zaberu"] or "").replace("T", " "),
                        r["mistnost_cs"] or "", r["mistnost"] or "", str(r["jistota"]).replace(".", ","),
                        "ano" if r["zmetek"] else "", r["cesta"]])
    return zaklad + ".json"


# =============================================================================================
# Zpráva
# =============================================================================================

def zprava(skupina, klipy, souhrn, projekt_nazev, pocty=None, varovani=None, soubor=None):
    r = []
    r.append("FD Místnosti · %s · projekt „%s“" % (skupina["zakazka"], projekt_nazev))
    r.append("Zápisy: " + ", ".join("%s %d" % (k, n) for k, n in sorted(skupina["kamery"].items())))
    r.append("")
    for kam, s in sorted(souhrn.items()):
        r.append("Kamera %s: %d klipů z natáčení, posun hodin %s%s, jistě %d, ověřit %d, zmetky %d, bez zápisu %d"
                 % (kam, s.get("klipu", 0), popis_posunu(s["posun_s"]), " (ručně)" if s["rucne"] else "",
                    s.get("jiste", 0), s.get("overit", 0), s.get("zmetky", 0), len(s.get("bez", []))))
    for kam, s in sorted(souhrn.items()):
        if s.get("klipu", 0) >= 3 and s.get("jiste", 0) < 0.5 * s["klipu"]:
            r.append("Pozor: u kamery %s sedí málo záběrů na zápisy. Zkontroluj hodiny v kameře (datum, čas) "
                     "a případně zadej posun ručně." % kam)
        if s.get("klipu", 0) == 0 and s["zapisu"]:
            r.append("Pozor: k zápisům kamery %s jsem v Media Poolu nenašel žádné klipy z doby natáčení." % kam)
    bez_kamery = [k for k in klipy if k.cizi]
    if bez_kamery:
        r.append("Klipy z kamery, která v zápisech není: %d (např. %s, %s)"
                 % (len(bez_kamery), bez_kamery[0].nazev, bez_kamery[0].model))
    r.append("")
    vypis = [k for k in klipy if k.zapis is not None or k.zmetek or (k.kamera in souhrn and k in souhrn[k.kamera].get("bez", []))]
    vypis.sort(key=lambda k: (k.kamera or "", k.konec_telefon or 0))
    if vypis:
        r.append("Klipy (čas konce záběru podle telefonu):")
    for k in vypis:
        cas = hms(k.konec_telefon) if k.konec_telefon else "--:--:--"
        if k.zmetek and k.zapis is None:
            cil = "ZMETEK"
        elif k.zapis is None:
            cil = "— bez zápisu"
        else:
            cil = "→ " + popisek(k) + (" · ZMETEK" if k.zmetek else "")
            if k.jistota < 0.9:
                cil += "  (ověřit: zápis o %s později)" % popis_posunu(k.mezera or 0).lstrip("+")
        r.append("  %-5s %-16s %s  %s" % (k.kamera or "?", k.nazev[:16], cas, cil))
    if pocty is not None:
        r.append("")
        casti = ["klíčová slova u %d klipů" % pocty["meta"]]
        if pocty.get("markery") or pocty.get("timeline"):
            casti.append("%d markerů na timeline „%s“" % (pocty["markery"], pocty.get("timeline") or ""))
        if pocty.get("barvy"):
            casti.append("barva u %d klipů" % pocty["barvy"])
        if pocty.get("biny"):
            casti.append("%d klipů v binech %s" % (pocty["biny"], BIN_KOREN))
        r.append("Zapsáno do DaVinci: " + ", ".join(casti) + ".")
    if soubor:
        r.append("Přiřazení pro FD Studio: %s (+ .csv)" % soubor)
    for v in varovani or []:
        r.append("Pozor: " + v)
    return "\n".join(r)


# =============================================================================================
# Běh
# =============================================================================================

def proved(projekt, skupina, volby, zapsat, cache=None):
    """Náhled (zapsat=False) nebo zápis. Vrací text zprávy."""
    klipy = klipy_z_projektu(projekt, cache)
    souhrn = sparuj(klipy, skupina["zapisy"], volby.get("posun"))
    nazev = projekt.GetName()
    if not zapsat:
        return zprava(skupina, klipy, souhrn, nazev) + "\n\nNáhled – v DaVinci se zatím nic nezměnilo."
    pocty, varovani = zapis_do_resolve(projekt, klipy, skupina["zapisy"], volby)
    soubor = None
    if volby.get("studio", True):
        try:
            slozka = os.path.dirname(skupina["logy"][0]["_cesta"])
            soubor = uloz_prirazeni(prirazeni(skupina, klipy, souhrn, nazev), slozka)
        except (OSError, IndexError, KeyError) as exc:
            varovani.append("Přiřazení pro FD Studio se nepodařilo uložit: %s" % exc)
    return zprava(skupina, klipy, souhrn, nazev, pocty, varovani, soubor)


def nacti_skupiny(slozky=None):
    slozky = vychozi_slozky() if slozky is None else slozky
    logy = [l for l in (nacti_zapis(c) for c in najdi_soubory_zapisu(slozky)) if l]
    return skupiny_zakazek(logy), slozky


def _posun_z_textu(text):
    t = (text or "").strip().replace(",", ".")
    if not t:
        return None
    try:
        return float(t)
    except ValueError:
        return None


def spust_okno(resolve, fusion, bmd, projekt):
    ui = fusion.UIManager
    disp = bmd.UIDispatcher(ui)
    win = disp.AddWindow({"ID": "FDMistnosti", "WindowTitle": "FD Místnosti %s" % VERZE,
                          "Geometry": [120, 100, 760, 680]}, [
        ui.VGroup({"Spacing": 8}, [
            ui.Label({"ID": "Hlavicka", "WordWrap": True, "Weight": 0,
                      "Text": "Přiřadí klipům místnosti ze zápisů z telefonu (FD-mistnosti_*.json)."}),
            ui.HGroup({"Weight": 0}, [
                ui.Label({"Text": "Zakázka:", "Weight": 0}),
                ui.ComboBox({"ID": "Zakazka", "Weight": 1}),
                ui.Button({"ID": "Obnovit", "Text": "Načíst znovu", "Weight": 0}),
                ui.Button({"ID": "Slozka", "Text": "Otevřít složku", "Weight": 0}),
            ]),
            ui.CheckBox({"ID": "Meta", "Text": "Klíčová slova a Scéna u klipů v Media Poolu", "Checked": True, "Weight": 0}),
            ui.CheckBox({"ID": "Markery", "Text": "Markery místností na aktuální timeline", "Checked": True, "Weight": 0}),
            ui.CheckBox({"ID": "Barvy", "Text": "Obarvit klipy podle místnosti", "Checked": False, "Weight": 0}),
            ui.CheckBox({"ID": "Biny", "Text": "Přesunout klipy do binů FD Místnosti / <místnost>", "Checked": False, "Weight": 0}),
            ui.CheckBox({"ID": "Studio", "Text": "Uložit přiřazení pro FD Studio (JSON + CSV vedle zápisů)", "Checked": True, "Weight": 0}),
            ui.HGroup({"Weight": 0}, [
                ui.Label({"Text": "Posun hodin kamery v sekundách (prázdné = automaticky):", "Weight": 0}),
                ui.LineEdit({"ID": "Posun", "PlaceholderText": "auto", "Weight": 1}),
            ]),
            ui.HGroup({"Weight": 0}, [
                ui.Button({"ID": "Nahled", "Text": "Náhled"}),
                ui.Button({"ID": "Zapsat", "Text": "Zapsat do DaVinci"}),
                ui.Button({"ID": "Zavrit", "Text": "Zavřít"}),
            ]),
            ui.TextEdit({"ID": "Zprava", "ReadOnly": True, "Weight": 1}),
        ]),
    ])
    itm = win.GetItems()
    stav = {"skupiny": [], "slozky": [], "cache": {}}

    def napis(text):
        itm["Zprava"].PlainText = text

    def nacti(_ev=None):
        stav["skupiny"], stav["slozky"] = nacti_skupiny()
        itm["Zakazka"].Clear()
        for g in stav["skupiny"]:
            kam = ", ".join("%s %d" % (k, n) for k, n in sorted(g["kamery"].items()))
            itm["Zakazka"].AddItem("%s  (%s)" % (g["zakazka"], kam))
        if not stav["skupiny"]:
            napis("Nenašel jsem žádné zápisy z telefonu.\n\nUlož soubor FD-mistnosti_….json do iCloud Drive → "
                  "složka FD Místnosti (nebo do Stažených souborů) a klikni Načíst znovu.\n\nProhledané složky:\n  "
                  + "\n  ".join(stav["slozky"] or ["(žádná neexistuje)"]))
            return
        vybrana = vyber_skupinu(stav["skupiny"], projekt.GetName())
        itm["Zakazka"].CurrentIndex = stav["skupiny"].index(vybrana)
        napis("Načteno %d zakázek. Vyber zakázku a klikni Náhled." % len(stav["skupiny"]))

    def volby():
        return {"meta": itm["Meta"].Checked, "markery": itm["Markery"].Checked, "barvy": itm["Barvy"].Checked,
                "biny": itm["Biny"].Checked, "studio": itm["Studio"].Checked,
                "posun": _posun_z_textu(itm["Posun"].Text)}

    def bez(zapsat):
        def obsluha(_ev):
            i = int(itm["Zakazka"].CurrentIndex)
            if i < 0 or i >= len(stav["skupiny"]):
                napis("Nejdřív vyber zakázku.")
                return
            napis("Pracuji…")
            try:
                napis(proved(projekt, stav["skupiny"][i], volby(), zapsat, stav["cache"]))
            except Exception:  # noqa: BLE001
                napis("Chyba:\n" + traceback.format_exc())
        return obsluha

    def otevri(_ev):
        cil = stav["slozky"][0] if stav["slozky"] else os.path.expanduser("~")
        try:
            subprocess.Popen(["open", cil] if sys.platform == "darwin" else ["xdg-open", cil])
        except OSError:
            napis("Složka: " + cil)

    def zavri(_ev):
        disp.ExitLoop()

    win.On.FDMistnosti.Close = zavri
    win.On.Zavrit.Clicked = zavri
    win.On.Obnovit.Clicked = nacti
    win.On.Slozka.Clicked = otevri
    win.On.Nahled.Clicked = bez(False)
    win.On.Zapsat.Clicked = bez(True)
    nacti()
    win.Show()
    disp.RunLoop()
    win.Hide()


def spust_bez_okna(projekt):
    skupiny, slozky = nacti_skupiny()
    if not skupiny:
        print("FD Místnosti: žádné zápisy z telefonu v: " + ", ".join(slozky))
        return
    skupina = vyber_skupinu(skupiny, projekt.GetName())
    print(proved(projekt, skupina, {"meta": True, "markery": True, "studio": True}, True))


def main():
    resolve, fusion, bmd = _prostredi()
    if resolve is None:
        print("FD Místnosti: spusť mě z DaVinci Resolve (Workspace → Scripts → FD_Mistnosti).")
        return
    projekt = resolve.GetProjectManager().GetCurrentProject()
    if not projekt:
        print("FD Místnosti: otevři v DaVinci projekt a zkus to znovu.")
        return
    ui_ok = fusion is not None and bmd is not None and hasattr(bmd, "UIDispatcher")
    if ui_ok:
        try:
            fusion.UIManager  # noqa: B018 – DaVinci bez UI Manageru tady spadne
        except Exception:  # noqa: BLE001
            ui_ok = False
    if ui_ok:
        try:
            spust_okno(resolve, fusion, bmd, projekt)
            return
        except Exception:  # noqa: BLE001
            print("FD Místnosti: okno se nepodařilo otevřít, běžím bez něj.\n" + traceback.format_exc())
    spust_bez_okna(projekt)


if __name__ == "__main__" or globals().get("resolve") is not None:
    main()
