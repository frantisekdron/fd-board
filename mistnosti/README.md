# FD Místnosti

Zápis místností při natáčení (telefon) + plugin pro DaVinci Resolve, který podle času natočení přiřadí
místnosti klipům. Samostatné vedle FD Studia: FD Studia se nedotýká, jen mu ukládá přiřazení
v jeho klíčích místností (`RoomType` ze `src/types/domain.ts` ve fd-reel-dashboard).

| Soubor | Co to je |
|---|---|
| `index.html`, `sw.js`, `manifest.json` | appka do telefonu (GitHub Pages, funguje i offline) |
| `navod.html` | návod pro natáčení a instalaci pluginu |
| `davinci/FD_Mistnosti.py` | plugin pro DaVinci (Workspace → Scripts → FD_Mistnosti), jeden soubor, Python 3.6+ |
| `testy/test_plugin.py` | testy pluginu bez DaVinci (simulace natáčení dvěma kamerami, náhradní Resolve API) |

Formáty:
- telefon → `FD-mistnosti_<zakázka>_<kamera>_<datum>_<id>.json`, `format: "fd-mistnosti/1"`, zápisy
  `{id, cas, ms, off, typ: "mistnost"|"zmetek", mistnost: <RoomType>, nazev, smazano?}`,
- plugin → `FD-mistnosti-prirazeni_<zakázka>.json` (`format: "fd-mistnosti-prirazeni/1"`) + `.csv`.

Párování: klip patří k prvnímu klepnutí po svém konci. Rozdíl hodin kamera × telefon se odhaduje zvlášť pro
každou kameru (hrubě z nejčastějších rozdílů, jemně tak, aby žádné klepnutí nepadlo doprostřed záběru a každé
zůstalo aspoň 1 s za svým záběrem). Kamera klipu se pozná z modelu v MP4/MOV (`DC-S5`, `DC-S1M2`), jinak ze
složky, jinak podle času.

Testy: `python3 -m pytest mistnosti/testy -q`
