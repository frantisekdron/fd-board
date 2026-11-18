# Pipeline pro FD 3D prohlídky

Z adresy, půdorysu a fotek z inzerátu udělá podklady pro 3D prohlídku v našem enginu
(stejný build jako „Mezonet 4+kk 3D“): `tour.json`, pozemek z katastru, výhled z oken,
mapu lokality a AI fotky místností, které v prohlídce sedí přesně na 3D pohled.

Data konkrétních nemovitostí (adresy, fotky, kontakty) do tohohle repozitáře nepatří,
repozitář je veřejný. Drž je ve vlastní složce zakázky mimo repo.

## Co je potřeba

```
pip install shapely numpy pillow
npm install            # v téhle složce: playwright + three
npx playwright install chromium
```

Žádná speciální GPU není potřeba. Rendery dělá Chromium bez okna; na Macu jede přes Metal
(pár sekund na snímek), v cloudu bez grafiky softwarově (asi minuta na snímek).

## Postup

1. **Katastr a mapy**

   ```
   python3 katastr.py --ulice "Název ulice" --cislo 17 --out zakazka/podklady
   ```

   Stáhne z RÚIAN (ČÚZK) adresní bod, obrys budovy, parcely, sousední budovy a osy ulic,
   ortofoto 120 × 120 m a mapu ZTM10. Vypíše výměru pozemku, délky hran a obrys domu
   v rámci domu (u na východ podél fasády, v na sever, počátek v JZ rohu). Podle obrysu
   zkalibruj půdorys: rozměry z výkresu musí sedět na obrys z katastru.

2. **tour.json**

   Napiš skript zakázky podle `priklad_dum.py` s pomocí `tour_lib.py`: stěny s okny a dveřmi,
   místnosti, schody, střecha, nábytek, pozice fotek (`shot`), televize (`tv`), hotspoty,
   listing a branding. Engine si `tour.json` při načtení sám zkontroluje a chyby vypíše česky
   přímo v prohlídce, takže stačí prohlídku otevřít.

   Na co si dát pozor:
   - První stupeň schodiště musí mít volný nástup na straně, odkud se přichází
     (engine bere jako nástup hranu odvrácenou od druhého stupně). Stupeň aspoň 25 cm hluboký.
   - Skříně, obrazy a zrcadla nedávej na stěnu přes dveře (`offset` dveří je střed otvoru).
   - Přízemní dům je bez `levels` a bez klíče `level` (knihovna to řeší sama).

3. **Výhled z oken**

   ```
   python3 zem_ortofoto.py zakazka/podklady/site.json zakazka/podklady/orto.jpg prohlidka/tours/demo/vyhled/vyhled-zem.jpg --stred X Z --X0 10 --Z0 20
   node vyhled_panorama.js --site zakazka/podklady/site.json --orto zakazka/podklady/orto.jpg --out prohlidka/tours/demo/vyhled/vyhled-valec.jpg --stred X Z --X0 10 --Z0 20
   ```

   `X Z` je střed domu v souřadnicích enginu. Oba skripty vypíšou kousky pro `vyhled.json`
   (`ground.rect`, `cylinder`). Do `tour.json` pak `"backdrop": {"url": "vyhled/vyhled.json"}`
   a `"surroundings": "none"`, aby se nemíchaly vymyšlené vily se skutečným okolím.

4. **Rendery pozic fotek**

   Spusť prohlídku lokálně (`python3 -m http.server 8766` ve složce prohlídky) a:

   ```
   node render_pozice.js --url http://localhost:8766/index.html --out zakazka/rendery
   ```

   Skript otevře prohlídku s `?debug=1`, kamerou skočí přes `window.__tour.setPose(...)` přesně
   na místo každé fotky z `tour.json` (pozice, směr, zorný úhel) a uloží snímek. Značky a UI
   v renderu nejsou. Když kamera skončí ve zdi nebo ve skříni, uprav pozici v `shot(...)`.

5. **AI fotky**

   ```
   python3 ai_prompty.py prohlidka/tours/demo/tour.json styly.json zakazka/rendery > zakazka/ai_zadani.json
   ```

   Pro každou fotku vznikne zadání: render (kompozice), volitelně skutečná fotka z inzerátu
   (styl) a prompt. Generuje se v Higgsfieldu modelem Nano Banana 2 (1k, 3:2), asi 1,5 kreditu
   za fotku, například přes Clauda s konektorem Higgsfield. Výsledky ulož jako `foto-01.png` …

   ```
   python3 vloz_fotky.py zakazka/ai_vystup prohlidka/tours/demo
   ```

   Fotky se zmenší, vloží do `fotky/` a popisky dostanou „AI vizualizace podle 3D modelu“.

6. **Televize, informace, půdorys, mapa**

   Televize (`tv(...)`) pouští kanál z fotek místností, galerie (`listing.gallery`, sem patří
   skutečné fotky z inzerátu s `"kind": "photo"`), informací z `listing`, půdorysů
   (`floorPlan`) a mapy lokality (`listing.location.map`, z `katastr.py` je `mapa.jpg`).

## Soubory

| soubor | co dělá |
| --- | --- |
| `katastr.py` | adresa → parcely, budovy, ulice, ortofoto, mapa ZTM10 |
| `tour_lib.py` | stavba `tour.json` v rámci domu (stěny, otvory, místnosti, schody, střecha, fotky) |
| `priklad_dum.py` | ukázkový dům, ověřený v enginu |
| `zem_ortofoto.py` | ortofoto do souřadnic enginu (zem výhledu) |
| `vyhled_panorama.js` | panorama okolí z katastru (válec výhledu) |
| `render_pozice.js` | rendery z enginu na pozicích fotek (podklad pro AI) |
| `ai_prompty.py` | zadání AI fotek pro každou pozici |
| `vloz_fotky.py` | vložení hotových AI fotek do prohlídky |
