---
name: velin
description: Nasadí „Velín" – hlasové ovládací centrum Claude Code session (hlas v projektu na claude.ai přes Google Drive, Dispečer v cloudové session, okamžitá spoušť přes Apps Script a GitHub schránku, dashboard na Vercelu) na účet nového uživatele. Použij, když uživatel řekne „nasaď Velín", „nastav mi Velín", „chci hlasové ovládání session jako má František" nebo pošle odkaz na velin-kit.
---

# Velín – nasazení pro nového uživatele

Velín = jeden přehled a ovládání všech Claude Code session uživatele:
- **Hlas** – projekt v aplikaci Claude (jen Google Drive konektor): čte přehled, posílá pokyny, „nakopne Dispečera".
- **Dispečer** – TAHLE cloudová session. Má nástroje claude-code-remote (list_sessions, send_message, create_session…), takže umí číst a řídit ostatní session. Běží každou hodinu 7–23 a na vyžádání.
- **Spoušť** – Google Apps Script hlídá Drive složku; při novém pokynu napíše komentář `VELIN_RUN` do „schránky" (draft PR v datovém repu), ke které je Dispečer přihlášený → probudí se do pár sekund.
- **Dashboard** – web na Vercelu z datového repa (složka `velin/`), GitHub token jen na serveru.
- **Jeden zdroj pravdy** – `most/velin_state.json` v soukromém datovém repu; na Drive jeho zrcadlo a lidský „Velín – přehled".

Soubory v tomhle skillu:
- `sablona/` – obsah datového repa (dashboard `velin/`, `most/`, `dispecer/postup.md`).
- `schranka/SCHRANKA.md` – jediný soubor PR „schránky".
- `hlas/instrukce-projektu.md` – instrukce pro hlasový projekt.
- `apps-script/velin-spoust.gs` – Apps Script spoušť.
Zástupné hodnoty `{{…}}` vyplníš za uživatele. Nikdy do nich nedávej tokeny.

Proč ne rutina s API tokenem: rutiny založené z Claude Code se v claude.ai/code/routines nezobrazují (nejde k nim token) a rutina založená ve formuláři běží v čerstvé session bez uživatelova schválení, takže jinou session spustit odmítne. Schránka probouzí přímo session Dispečera.

## Předpoklady (ověř hned, jinak skonči a vysvětli, co chybí)
1. Běžíš v **cloudové** Claude Code session (claude.ai/code), ne lokálně – Dispečer musí běžet i při vypnutém počítači.
2. Máš nástroje `claude-code-remote` (list_sessions, send_message, create_session, create_trigger, subscribe_pr_activity) – ověř ToolSearch.
3. Máš konektor **Google Drive** (ToolSearch „Google_Drive"). Když chybí: uživatel ho připojí na claude.ai → Nastavení → Konektory a založí novou session.
4. V session je připojené uživatelovo **soukromé datové repo** (doporučený název `velin`) s právem push. Když není, požádej ho, ať ho na GitHubu založí (New repository → Private → Add README) a spustí novou session s tímto repem.

## Co zjistit od uživatele (zeptej se jednou, najednou)
- Jméno nebo přezdívka (do notifikací a hlasu).
- Souhlas se založením **schránky** = draft pull request v datovém repu, který se nikdy neslučuje. Bez výslovného souhlasu PR nezakládej.
Vše ostatní zjistíš sám: GitHub uživatel a repo z připojeného repa (`git remote`), Drive složku založíš.

## Postup nasazení
1. **Drive složka:** přes Google Drive `create_file` založ složku „Velín" (mimeType `application/vnd.google-apps.folder`) a zapamatuj si její id = `SLOZKA_ID`. Když složka „Velín" už existuje (search `title = 'Velín' and mimeType = 'application/vnd.google-apps.folder' and owner = 'me'`), zeptej se, jestli ji použít.
2. **Datové repo:** zkopíruj obsah `sablona/` do kořene repa. V `dispecer/postup.md` nahraď `{{JMENO}}`, `{{DATA_REPO}}` (uzivatel/repo), `{{REPO_NAME}}`, `{{GITHUB_USER}}`, `{{SLOZKA_ID}}`, `{{SCHRANKA_PR}}` (číslo PR doplníš po kroku 3; do té doby nech a pak druhým commitem doplň). Commit „Velín: založení", push do `main`.
   Pozor: kdyby repo mělo GitHub Action, která maže nebo přepisuje větve `claude/*`, pracuj ve větvích bez prefixu `claude/`.
3. **Schránka** (jen se souhlasem): větev `velin/schranka` z `main` se souborem `SCHRANKA.md` (ze `schranka/`), push, **draft** PR do `main` s názvem „Velín – schránka (NESLUČOVAT, NEZAVÍRAT)". Číslo PR = `SCHRANKA_PR`. Doplň ho do `dispecer/postup.md` (commit, push).
4. **Přihlas se ke schránce:** `subscribe_pr_activity(owner, repo, SCHRANKA_PR)`. Tím se z téhle session stává Dispečer.
5. **Hodinový běh:** `create_trigger` bez `persistent_session_id` a bez `create_new_session_on_fire` (váže se na tuhle session), `cron_expression` = `CRON_TZ=Europe/Prague 18 7-23 * * *`, `initiation` = `human_request`, název „Velín – Dispečer (hodinově)", prompt:
   „Běh Dispečera Velínu (schválil(a) <jméno> při nasazení). Proveď přesně postup z /home/user/<repo>/dispecer/postup.md (nejdřív git pull). Nic jiného nedělej."
   Upozorni uživatele, že rutinu v claude.ai nemusí vidět – je to v pořádku.
6. **Přejmenuj session** (`set_session_title`) na „Velín – Dispečer (NEARCHIVOVAT)".
7. **Vyplň zbylé šablony** (`{{JMENO}}`, `{{SLOZKA_ID}}`, `{{SLOZKA_NAZEV}}` = „Velín", `{{DATA_REPO}}`, `{{SCHRANKA_PR}}`):
   - `hlas/instrukce-projektu.md` → ulož do repa jako `nastaveni/instrukce-projektu.md` a zároveň na Drive do složky jako dokument „Velín – instrukce pro hlas" (create_file, text/plain).
   - `apps-script/velin-spoust.gs` → ulož do repa jako `nastaveni/velin-spoust.gs` a na Drive jako „Velín – kód Apps Scriptu".
   Commit, push.
8. **První běh:** proveď hned postup z `dispecer/postup.md`. Ověř, že vznikl `most/velin_state.json` s jeho session a na Drive „Velín – přehled".
9. **Předej zbytek uživateli** – krátce a česky, krok za krokem (podrobnosti má v NAVOD.md, kroky 5–7):
   a) Hlas: claude.ai → Projekty → nový projekt „Velín" → Instrukce = text z dokumentu „Velín – instrukce pro hlas"; v projektu zapnout konektor Google Drive.
   b) Apps Script: script.google.com → nový projekt „Velín spoušť" → vložit kód z „Velín – kód Apps Scriptu" → Vlastnost skriptu `GITHUB_TOKEN` = fine-grained token jen pro datové repo s oprávněním **Pull requests: Read and write** → funkce `nastav` → povolit → funkce `test`.
   c) Dashboard: classic GitHub token (scope `repo`, bez expirace) → vercel.com → import datového repa → Root Directory `velin`, Framework Other → proměnné `GITHUB_TOKEN`, `VELIN_HESLO`, `VELIN_SECRET` → Deploy.
   Ať ti po kroku b) napíše – ověř, že do schránky dorazil komentář `VELIN_RUN` a že ses probudil(a).

## Pravidla pro Dispečera po nasazení
- Při každém probuzení (hodinová rutina nebo komentář `VELIN_RUN` od uživatele ve schránce) proveď `dispecer/postup.md`.
- Schránku nikdy neslučuj, nezavírej, nepushuj do ní a nekomentuj; nejsi její majitel v tom smyslu, že bys ji měl dotahovat do zelena – nemá CI ani nic k opravě.
- Session nearchivuj a nepřerušuj. Tokeny nikdy nečti, nežádej ani nezapisuj – patří jen do Apps Scriptu a Vercelu.
