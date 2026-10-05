# Velín – jedno ovládání session (hlas + dashboard)

Stav: **návrh k odsouhlasení** + **fáze 1 připravená** (spoušť Dispečera přes Drive). Nic není nasazené naživo, dokud František nepotvrdí.

## Fáze 1 – spoušť Dispečera z hlasu (hotovo v kódu, čeká na 3 kroky Františka)

**Jak to funguje**
1. Hlas (projekt „Kolega") položí do složky FD Kolega soubor **„KOLEGA spusť"** (nebo obyčejný „KOLEGA pokyn – …").
2. **Google Apps Script** (zdarma, běží u Googlu, ne na kreditech Claude) se každou minutu podívá do složky. Když soubor najde, zavolá API rutiny **„Velín spoušť – Dispečer na vyžádání"** (`trig_01S8EN4VNjmEGNA6nSbUVqyE`).
3. Rutina probudí **stejnou** session CLAUDE VOICE CONTROL, ve které běží hodinový Dispečer → nikdy nepoběží dva Dispečeři naráz (zprávy se řadí za sebe). Dispečer doručí pokyny, obnoví „Kolega – přehled", pushne a **vždy** pošle notifikaci.
4. Apps Script spouštěcí soubor vyhodí do koše (žádná smyčka) a do dokumentu **„Velín – spoušť"** zapíše, kdy Dispečera spustil (hlas si to může přečíst).

Latence: do ~1 min se Dispečer spustí, za 3–5 min je nový přehled. Kredity: Apps Script nic nestojí; Claude běží jen když ho opravdu zavoláš. Hodinový běh 7–23 v :18 a notifikace zůstávají beze změny (fallback).
Pojistky: min. 2 min mezi spuštěními (co přijde mezitím, počká, neztratí se); limit API 30 spuštění/h na rutinu – při překročení Apps Script počká a zapíše chybu do „Velín – spoušť".
`AUTO_POKYN = true`: i každý nový „KOLEGA pokyn" se doručí hned, ne až v další hodinu. Lze vypnout (false).

**Co potřebuju od Františka (asi 10 min, jednou)**
1. **Token rutiny:** claude.ai/code/routines → otevři „Velín spoušť – Dispečer na vyžádání" → *Add another trigger* → **API** → *Generate token* → zkopíruj (ukáže se jen jednou). Token nikomu neposílej, ani mně.
2. **Apps Script:** script.google.com → Nový projekt „Velín spoušť" → vlož obsah `kolega/velin-spoust.gs` → ⚙ Nastavení projektu → *Vlastnosti skriptu* → přidej `ROUTINE_TOKEN` = token z kroku 1 → v editoru vyber funkci **nastav** → ▶ Spustit → povol přístup (Drive, Dokumenty, externí požadavky). Volitelně vyber **test** → ▶ (spustí Dispečera hned, přijde notifikace).
3. **Hlas:** v projektu „Kolega" nahraď instrukce novým `kolega/projekt-instrukce.md` (přibyla věta „nakopni Dispečera").

Kdyby rutina v UI neměla volbu API (vznikla z Claude Code, ne z formuláře), řekni – záloha: rutinu založíš ve formuláři claude.ai s konektorem Claude_Code_Remote; její malý běh jen pošle zprávu „spusť" do session Dispečera.

## Celkový návrh

**Jeden zdroj pravdy: `velin_state.json`**
- Kanonická kopie: soukromé repo `frantisekdron/fd-kolega`, soubor `most/velin_state.json` (git = zdarma historie každé změny). Dashboard ho už dnes umí číst.
- Zrcadlo na Drive: `velin_state.json` ve složce FD Kolega (jako Google Doc s JSON textem – Drive konektor hlasu jiné typy nepřečte) + lidský „Kolega – přehled". Obojí vzniká v **jednom** běhu Dispečera z **jednoho** objektu → data se nerozejdou. Apps Script může později držet obojí pod stálým ID (přepisovat obsah), takže odpadne mazání a vytváření nových souborů.
- Formát (verze 1):
```json
{
  "schema": 1,
  "updated_at": "2026-10-05T07:30:00+02:00",
  "dispatcher": {"last_run": "…", "mode": "hourly|on_demand", "next_hourly": "…"},
  "sessions": [{
    "id": "session_…", "title": "…", "kind": "cloud|mac", "online": true,
    "state": "working|blocked|review_ready|completed|failed",
    "summary": "1 věta česky", "waiting_for_me": "" ,
    "done": "co doběhlo", "failed": "",
    "repo": "frantisekdron/…", "branch": "…", "pr": {"number": 12, "url": "…", "ci": "green|red|pending"},
    "updated_at": "…"
  }],
  "commands": {"pending": 0, "delivered_last_run": 2},
  "events": [{"at": "…", "session": "…", "text": "…"}]
}
```

**Jak session zapisují stav:** nemusí nic. Dispečer stav čte sám z metadat session (stav, shrnutí, „čeká na tebe", repo/větev) – nulové náklady navíc v každé session. Kód session dál commitují a pushují do GitHubu jako dnes; PR a CI k tomu dashboard dotáhne přímo z GitHubu.

**Dispečer:** hodinový běh 7–23 zůstává; nově i na vyžádání (fáze 1). Fáze 2 doplní zápis `velin_state.json` a spoušť i z dashboardu: GitHub Action v `fd-kolega` při pushi do `most/prikazy.json` (nebo tlačítkem „Obnovit teď") zavolá tutéž rutinu → pokyny z dashboardu taky okamžitě. Token rutiny pak bude i v GitHub secretu, ne v kódu.

**Hlas:** čte „Kolega – přehled" / `velin_state.json`, posílá „KOLEGA pokyn", nově „KOLEGA spusť". GitHub nepotřebuje.

**Dashboard:** stávající PWA `frantisekdron.github.io/fd-board/kolega/` (telefon i PC, přidat na plochu), rozšířená o: seznam session s filtrem (čeká na mě / běží / chyba / hotovo / cloud / Mac), detail session (historie events, repo, větev, PR, CI), náhled commitů a diffů, akce „pošli pokyn" a „obnovit teď". Pokyny zapisuje do stejné fronty, jakou doručuje Dispečer.

**GitHub napojení (classic token, všechna repa, bez expirace):** token nesmí být v kódu ani v appce Claude. Doporučení: malý serverový proxy na **Vercel (zdarma)** napojený na repo přes GitHub (nasazuje se sám, z cloudových session se tam nesahá); token jako environment secret, přístup chráněný heslem. Levnější varianta bez serveru: token uložený jen v prohlížeči tvých zařízení (jako dnes) – jednodušší, ale klasický token s plným přístupem ke všem repům je v prohlížeči rizikovější. Rozhodnutí je na tobě.

## Kroky a odhad

| Fáze | Co | Moje práce | Od tebe |
|---|---|---|---|
| 1 | Spoušť přes Drive (hlas → Dispečer hned) | hotovo | token rutiny, Apps Script, instrukce hlasu (10 min) |
| 2 | `velin_state.json` (repo + Drive), spoušť z dashboardu přes GitHub Action, úprava Dispečera | ~2–3 h | schválit formát; token rutiny i do GitHub secretu |
| 3 | Dashboard: filtry, detail, historie, GitHub náhled kódu/PR/CI přes proxy | ~1 den | rozhodnout Vercel vs. prohlížeč; classic token |
| 4 | Doladění hlasu (krátké odpovědi z JSON, „co čeká") | ~1 h | vyzkoušet za jízdy |

**První milník:** fáze 1 v provozu – řekneš „nakopni Dispečera" a do ~5 min máš čerstvý přehled a notifikaci.

## Rozhodnutí pro Františka
1. Schvaluješ návrh (zdroj pravdy v repu fd-kolega + zrcadlo na Drive)?
2. AUTO_POKYN – doručovat hlasové pokyny hned (doporučuji ano)?
3. GitHub token pro dashboard: Vercel proxy (doporučeno) nebo jen v prohlížeči?
