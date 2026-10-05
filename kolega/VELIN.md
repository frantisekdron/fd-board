# Velín – jedno ovládání session (hlas + dashboard)

Stav: návrh **schválen** 5. 10. (AUTO_POKYN ano, GitHub token na Vercelu). Fáze 1–3 hotové v kódu; čeká se na tokeny a nastavení od Františka.
Dashboard Velín: kód v soukromém repu `fd-kolega`, složka `velin/` – návod k nasazení na Vercel je v `velin/README.md` tamtéž.

## Fáze 1 – spoušť Dispečera z hlasu

**Jak to funguje**
1. Hlas (projekt „Kolega") položí do složky FD Kolega soubor **„KOLEGA spusť"** (nebo obyčejný „KOLEGA pokyn – …").
2. **Google Apps Script** (zdarma, běží u Googlu) se každou minutu podívá do složky. Když soubor najde, napíše komentář `VELIN_RUN` do **schránky** – PR #1 „Velín – schránka" v soukromém repu fd-kolega.
3. Session CLAUDE VOICE CONTROL (Dispečer) je k PR přihlášená, GitHub ji do pár sekund probudí. Dispečer doručí pokyny, obnoví stav i přehled a vždy pošle notifikaci. Nikdy nepoběží dva Dispečeři naráz.
4. Apps Script spouštěcí soubor vyhodí do koše a do dokumentu **„Velín – spoušť"** zapíše, kdy Dispečera spustil.
Dashboard Velín spouští Dispečera stejně (komentář do schránky).

Proč schránka: rutiny založené z Claude Code se v claude.ai nezobrazují (nejde k nim API token) a rutina založená ve formuláři běží v čerstvé session bez Františkova schválení, takže jinou session spustit odmítne. Schránka probouzí přímo session Dispečera, kde schválení je. Souhlas se schránkou dal František 5. 10. 2026.

**Co potřebuju od Františka**
1. **GitHub token pro Apps Script:** github.com/settings/personal-access-tokens → Generate new token → Repository access *Only select* → **fd-kolega** → Permissions: **Pull requests: Read and write** → Generate.
2. **Apps Script:** script.google.com → Nový projekt „Velín spoušť" → vlož `kolega/velin-spoust.gs` → ⚙ Vlastnosti skriptu: `GITHUB_TOKEN` → funkce **nastav** → ▶ Spustit → povol přístup → funkce **test**.
3. **Hlas:** v projektu „Kolega" nahraď instrukce novým `kolega/projekt-instrukce.md`.
4. Rutinu „Velín spínač" v claude.ai můžeš smazat.

## Celkový návrh

**Jeden zdroj pravdy: `velin_state.json`**
- Kanonická kopie: soukromé repo `frantisekdron/fd-kolega`, soubor `most/velin_state.json` (git = zdarma historie každé změny). Dashboard ho už dnes umí číst.
- Zrcadlo na Drive: `velin_state.json` ve složce FD Kolega (jako Google Doc s JSON textem – Drive konektor hlasu jiné typy nepřečte) + lidský „Kolega – přehled". Obojí vzniká v **jednom** běhu Dispečera z **jednoho** objektu → data se nerozejdou. Apps Script může později držet obojí pod stálým ID (přepisovat obsah), takže odpadne mazání a vytváření nových souborů.
- Formát (verze 1, klíče navazují na dosavadní prehled.json, takže starý dashboard funguje dál):
```json
{
  "schema": 1,
  "updated_at": "2026-10-05T05:30:00Z", "updated_praha": "05. 10. 2026 07:30",
  "dispecer": {"rezim": "hodinovy|na_vyzadani", "doruceno": 2},
  "mac": "…", "velin": "…",
  "sessions": [{
    "id": "session_…", "title": "…", "typ": "cloud|mac", "online": true,
    "stav": "working|blocked|review_ready|completed|failed",
    "shrnuti": "1 věta česky", "ceka": "co čeká na Františka",
    "repo": "frantisekdron/…", "vetev": "…", "updated": "…"
  }],
  "events": [{"at": "…", "session": "session_…", "title": "…", "text": "…"}]
}
```
PR a CI se do stavu nezapisují – dashboard je k session dotáhne živě z GitHubu podle repa a větve.

**Jak session zapisují stav:** nemusí nic. Dispečer stav čte sám z metadat session (stav, shrnutí, „čeká na tebe", repo/větev) – nulové náklady navíc v každé session. Kód session dál commitují a pushují do GitHubu jako dnes; PR a CI k tomu dashboard dotáhne přímo z GitHubu.

**Dispečer:** hodinový běh 7–23 zůstává; nově i na vyžádání (fáze 1). Dispečer zapisuje `velin_state.json`; dashboard (pokyn nebo „Obnovit teď") ho spouští stejnou schránkou.

**Hlas:** čte „Kolega – přehled" / `velin_state.json`, posílá „KOLEGA pokyn", nově „KOLEGA spusť". GitHub nepotřebuje.

**Dashboard:** stávající PWA `frantisekdron.github.io/fd-board/kolega/` (telefon i PC, přidat na plochu), rozšířená o: seznam session s filtrem (čeká na mě / běží / chyba / hotovo / cloud / Mac), detail session (historie events, repo, větev, PR, CI), náhled commitů a diffů, akce „pošli pokyn" a „obnovit teď". Pokyny zapisuje do stejné fronty, jakou doručuje Dispečer.

**GitHub napojení (classic token, všechna repa, bez expirace):** token nesmí být v kódu ani v appce Claude. Doporučení: malý serverový proxy na **Vercel (zdarma)** napojený na repo přes GitHub (nasazuje se sám, z cloudových session se tam nesahá); token jako environment secret, přístup chráněný heslem. Levnější varianta bez serveru: token uložený jen v prohlížeči tvých zařízení (jako dnes) – jednodušší, ale klasický token s plným přístupem ke všem repům je v prohlížeči rizikovější. Rozhodnutí je na tobě.

## Kroky a odhad

| Fáze | Co | Moje práce | Od tebe |
|---|---|---|---|
| 1 | Spoušť přes Drive (hlas → Dispečer hned) | hotovo | GitHub token pro fd-kolega, Apps Script, instrukce hlasu (10 min) |
| 2 | `velin_state.json` (repo + Drive), spoušť z dashboardu přes schránku, úprava Dispečera | hotovo | – |
| 3 | Dashboard: filtry, detail, historie, GitHub náhled kódu/PR/CI přes proxy | ~1 den | rozhodnout Vercel vs. prohlížeč; classic token |
| 4 | Doladění hlasu (krátké odpovědi z JSON, „co čeká") | ~1 h | vyzkoušet za jízdy |

**První milník:** fáze 1 v provozu – řekneš „nakopni Dispečera" a do ~5 min máš čerstvý přehled a notifikaci.

## Rozhodnutí pro Františka
1. Schvaluješ návrh (zdroj pravdy v repu fd-kolega + zrcadlo na Drive)?
2. AUTO_POKYN – doručovat hlasové pokyny hned (doporučuji ano)?
3. GitHub token pro dashboard: Vercel proxy (doporučeno) nebo jen v prohlížeči?
