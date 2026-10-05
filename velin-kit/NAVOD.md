# Velín – návod krok za krokem

Velín je tvoje hlasové ovládací centrum pro Claude Code. Řekneš do telefonu „co na mě čeká?" nebo „pošli do session Web, ať opraví menu" a Velín to zařídí. Na počítači nebo mobilu máš navíc přehledný web (dashboard) se všemi session, historií a náhledem do kódu.

Funguje i při vypnutém počítači – všechno běží v cloudu (Claude, Google, GitHub, Vercel).

**Čas:** asi 45 minut, jednou. Nejpohodlnější na počítači, ale jde to i na telefonu v prohlížeči.
**Cena:** nic navíc kromě předplatného Claude. Google Apps Script, GitHub a Vercel (Hobby) jsou zdarma. Dispečer čerpá limit předplatného Claude jako běžná session (krátký běh každou hodinu 7–23 a když ho zavoláš).

> 🔒 **Tokeny a hesla nikomu neposílej** – ani Claudovi do chatu, ani kolegovi. Vkládáš je jen tam, kde to návod říká. Co je osobní a tajné, najdeš v [OSOBNI-UDAJE.md](OSOBNI-UDAJE.md).

---

## Co budeš potřebovat
- Předplatné **Claude Pro nebo Max** (kvůli Claude Code na webu: claude.ai/code).
- Účet na **GitHubu** (zdarma, github.com).
- Účet **Google** (Google Drive).
- Účet na **Vercelu** – založíš ho v kroku 7 přihlášením přes GitHub.

---

## Krok 1 – Připoj Claude ke Google Drive a GitHubu (5 min)
1. Otevři **claude.ai** → vlevo dole své jméno → **Nastavení** → **Konektory**.
2. U **Google Drive** klikni na **Připojit** a povol přístup svým Google účtem.
3. Otevři **claude.ai/code**. Pokud tě vyzve k připojení GitHubu, připoj ho (povol přístup ke všem repozitářům nebo aspoň k repu `velin`, které založíš v dalším kroku).

## Krok 2 – Založ si soukromé repo `velin` (2 min)
Repo je „složka na GitHubu", kam Velín ukládá stav a kde bude kód dashboardu.
1. Na **github.com** vpravo nahoře **+** → **New repository**.
2. **Repository name:** `velin`
3. Zvol **Private** (soukromé – je tam přehled tvé práce).
4. Zaškrtni **Add a README file**.
5. **Create repository**.

## Krok 3 – (nepovinné) Nahraj skill Velín do Claude
Pomůže Claudovi, ale není nutný – krok 4 funguje i bez něj.
1. Stáhni soubor [velin-skill.zip](velin-skill.zip) (na stránce souboru tlačítko **Download raw file**).
2. claude.ai → **Nastavení** → **Možnosti (Capabilities)** → **Skills** → **Nahrát skill** → vyber `velin-skill.zip`.

## Krok 4 – Nech Clauda postavit Dispečera (10 min)
Dispečer je jedna cloudová session, která hlídá všechny ostatní. Claude ji nastaví sám.
1. Otevři **claude.ai/code** → nová session → jako repo vyber **velin** → prostředí nech výchozí.
2. Vlož tuhle zprávu (doplň jméno) a odešli:

```
Nasaď mi Velín. Postup a šablony jsou ve veřejném repu frantisekdron/fd-board, složka velin-kit/skill/velin (začni souborem SKILL.md). Jmenuji se ______. Souhlasím se založením schránky (draft pull requestu) v mém repu velin.
```

3. Claude si případně ještě něco ověří a pak sám:
   - založí na tvém Google Drive složku **Velín**,
   - nahraje do repa `velin` dashboard a stav,
   - založí „schránku" (pull request, který se nikdy neslučuje),
   - nastaví hodinový běh (7–23),
   - připraví na Drive dva dokumenty: **„Velín – instrukce pro hlas"** a **„Velín – kód Apps Scriptu"**.
4. Tuhle session si přejmenuje na **„Velín – Dispečer (NEARCHIVOVAT)"**. **Nikdy ji nearchivuj ani nemaž** – to je srdce Velínu.

## Krok 5 – Hlasové ovládání (3 min)
1. claude.ai → **Projekty** → **Nový projekt** → název **Velín**.
2. V projektu otevři **Instrukce** (Project instructions) a vlož celý text z dokumentu **„Velín – instrukce pro hlas"** (najdeš ho na Google Drive ve složce Velín).
3. V projektu zapni konektor **Google Drive** (ikona konektorů u pole pro psaní).
4. Na telefonu v aplikaci Claude otevři projekt **Velín** a mluv (ikona sluchátek / hlasový režim).

## Krok 6 – Okamžitá spoušť (Google Apps Script) (10 min)
Bez tohohle kroku se pokyny doručují jen jednou za hodinu. S ním do pár minut.

**A. GitHub token jen pro spoušť**
1. Otevři **github.com/settings/personal-access-tokens** → **Generate new token** (fine-grained).
2. **Token name:** `Velín spoušť`, **Expiration:** co nejdelší (nebo No expiration, pokud je v nabídce).
3. **Repository access:** **Only select repositories** → vyber **velin**.
4. **Permissions** → **Add permissions** → **Pull requests** → **Read and write**. Nic dalšího.
5. **Generate token** → zkopíruj (začíná `github_pat_`).

**B. Skript**
1. Otevři **script.google.com** (stejný Google účet jako Drive) → **Nový projekt**.
2. Nahoře klikni na „Projekt bez názvu" a přejmenuj na **Velín spoušť**.
3. V souboru **Kód.gs** smaž všechno a vlož celý text z dokumentu **„Velín – kód Apps Scriptu"** z Drive. Ulož (Cmd+S / Ctrl+S).
4. Vlevo **⚙ Nastavení projektu** → dole **Vlastnosti skriptu** → **Přidat vlastnost skriptu**: název `GITHUB_TOKEN`, hodnota = token z bodu A → **Uložit vlastnosti skriptu**.
5. Vlevo **< > Editor**. Nahoře vedle tlačítek **▶ Spustit** a **Ladit** je rozbalovací seznam funkcí → vyber **nastav** → **▶ Spustit**.
6. Google se zeptá na povolení: **Zkontrolovat oprávnění** → tvůj účet → „Google tuto aplikaci neověřil" → **Rozšířené** → **Přejít na Velín spoušť (nebezpečné)** → **Povolit**. (Je to tvůj vlastní skript, je to v pořádku.)
7. V seznamu funkcí vyber **test** → **▶ Spustit**. Dole v protokolu má být `"ok":true`. Do pár minut ti přijde notifikace od Dispečera.

## Krok 7 – Dashboard na Vercelu (10 min)
**A. GitHub token pro dashboard**
1. Otevři přesně **github.com/settings/tokens/new** (nadpis „New personal access token (classic)").
2. **Note:** `Velín dashboard`, **Expiration:** No expiration, zaškrtni **repo** (celý řádek).
3. **Generate token** → zkopíruj (začíná `ghp_`).

**B. Vercel**
1. Otevři **vercel.com/new** → **Continue with GitHub** (zdarma, plán Hobby).
2. U repa **velin** klikni **Import**. Když ho nevidíš: **Adjust GitHub App Permissions** → povol repo `velin` → vrať se → **Import**.
3. **Framework Preset:** **Other**. **Root Directory:** **Edit** → vyber složku **velin** → **Continue**.
4. Rozbal **Environment Variables** a přidej tři:
   - `GITHUB_TOKEN` = token `ghp_…` z bodu A,
   - `VELIN_HESLO` = heslo, kterým se budeš do dashboardu přihlašovat (vymysli si),
   - `VELIN_SECRET` = náhodně namačkaných ~40 písmen a číslic (pamatovat si ho nemusíš).
5. **Deploy** → počkej na „Congratulations".
6. **Continue to Dashboard** → v části **Domains** je tvoje adresa (např. `velin-xyz.vercel.app`). Otevři ji, přihlas se heslem.
7. Na telefonu: Safari → **Sdílet** → **Přidat na plochu**.

---

## Ověř, že všechno jede
1. **Hlas:** v projektu Velín řekni „co na mě čeká?" – odpoví z přehledu.
2. **Spoušť:** řekni „nakopni Dispečera" – do 5 minut přijde notifikace a přehled je čerstvý.
3. **Dashboard:** vidíš svoje session; klikni na žluté **⚡ Obnovit teď** – tlačítko zezelená („Dispečer běží").

## Jak to používat
- **Hlas (telefon, auto):** „Co čeká?", „Pošli do session X, ať…", „Nová session: …", „Nakopni Dispečera".
- **Dashboard (detaily):** filtry, detail session (pull requesty, CI, změny v kódu), všechna repa, historie, ⚡.
- Hodinový běh 7–23 jede sám jako záloha.

## Nikdy nemaž ani nearchivuj
- session **„Velín – Dispečer (NEARCHIVOVAT)"**,
- pull request **„Velín – schránka"** v repu `velin` (neslučovat, nezavírat),
- Apps Script **„Velín spoušť"**,
- složku **Velín** na Google Drive.

## Když něco nefunguje
- **Dashboard hlásí „GitHub 403 … nemá přístup":** ve Vercelu je špatný token. Musí to být classic `ghp_…` se scope `repo`. Oprava: Vercel → projekt → **Settings → Environment Variables** → `GITHUB_TOKEN` → Edit → Save → **Deployments → ⋯ → Redeploy**.
- **Po změně proměnné se nic nestalo:** změny ve Vercelu platí až po **Redeploy**.
- **Hlas tvrdí, že něco nejde, ale funguje to:** hlas čte dokumenty na Drive; řekni „nakopni Dispečera" a zeptej se znovu za 5 minut.
- **Spoušť nereaguje:** script.google.com → projekt → vlevo **Spuštění**: běží `hlidej` každou minutu? Dokument „Velín – spoušť" na Drive ukáže poslední chybu.
- **Dispečer mlčí:** otevři v claude.ai/code session „Velín – Dispečer" a napiš jí, co se děje – opraví se sama.
