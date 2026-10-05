# FD Kolega – jen na předplatném Claude (bez dalších plateb), ~10 min

Hlas = hlasový režim v appce Claude · Mozek = Claude projekt · Session = Claude Code · Notifikace = appka Claude.

## 1. Repo pro most (1 min)
github.com/new → název **fd-kolega** → **Private** → zaškrtni „Add a README" → Create.

## 2. Dispečer (3 min)
Appka Claude / claude.ai/code → **Routines** → **FD Kolega – Dispečer** (je vypnutý):
1. Prompt nahraď celým obsahem `kolega/dispecer-prompt.md`.
2. Zapni **notifikace (push)**.
3. Zapni rutinu a jednou klepni **Run now** – vytvoří první přehled.

## 3. Projekt „Kolega" (3 min)
claude.ai → Projects → New project „Kolega" → Instructions: vlož obsah `kolega/projekt-instrukce.md`.
Konektory (Settings → Connectors): **GitHub** (s přístupem k fd-kolega), **Gmail**, **Google Drive** – zapnuté.

## 4. V autě
Appka Claude → projekt Kolega → nový chat → ikona **hlasového režimu** (zvuková vlna) → mluv.
- „Co se děje v mých session?"
- „Pošli do session s webem, ať opraví tlačítko."
- „Založ novou session v repu fd-board: …"
- „Mám nové maily? Přečti mi ten od…"

## Omezení (dané předplatným)
- Dispečer běží max. 1× za hodinu (Claude kratší interval nepovolí); na spěch „Run now".
- Session na claude.ai/code nemají veřejné API, proto jde řízení přes Dispečera, ne napřímo.

Složka `worker/` a stránka `kolega/index.html` jsou starší varianta s placenými API (rychlejší, real-time). Nepoužívá se; dá se zapnout kdykoli později.
