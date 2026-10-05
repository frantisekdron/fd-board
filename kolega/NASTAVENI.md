# FD Kolega – zprovoznění z telefonu (cca 25 min, jednou)

Vše jde v mobilním prohlížeči. Kde je „tajemství", vlož ho do **GitHub → fd-board → Settings → Secrets and variables → Actions → New repository secret** (jméno přesně podle tučného textu).

## 1. Upozornění na zamčený telefon (2 min)
1. Nainstaluj appku **ntfy** (App Store / Google Play).
2. „+" → Subscribe → název kanálu vymysli dlouhý a tajný, např. `fd-kolega-7f3k9q2x`.
3. Tajemství **NTFY_TOPIC** = ten název.

## 2. Heslo do appky (30 s)
Tajemství **APP_TOKEN** = vymysli dlouhé heslo (např. 30 náhodných znaků). Ulož si ho, zadáš ho v appce.

## 3. Hlas – OpenAI (3 min)
platform.openai.com → přihlásit → Billing → dobít kredit (stačí $10) → API keys → Create → tajemství **OPENAI_API_KEY**.

## 4. Mozek pracovních agentů – Anthropic (3 min)
console.anthropic.com → přihlásit (tvůj Google) → Billing → kredit ($20) → API Keys → Create Key → tajemství **ANTHROPIC_API_KEY**.

## 5. GitHub (3 min)
1. github.com/new → název **fd-kolega**, **Private**, zaškrtni „Add a README" → Create.
2. github.com/settings/personal-access-tokens → Generate new token → Repository access: All repositories → Permissions: Contents **Read and write**, Pull requests **Read**, Metadata Read → Generate → tajemství **KOLEGA_GITHUB_TOKEN**.

## 6. Gmail + Drive (5 min, přepni prohlížeč na „verzi pro počítač")
1. script.google.com → Nový projekt → smaž vše a vlož obsah souboru `kolega/google-most.gs` (z tohoto repa).
2. Na 7. řádku nahraď `ZMEN_ME_NA_NAHODNY_RETEZEC` jiným dlouhým heslem → tajemství **GOOGLE_KEY** = totéž heslo.
3. Nasadit → Nové nasazení → ozubené kolo: Webová aplikace → Spustit jako **Já**, Přístup **Kdokoli** → Nasadit → Povolit přístup (Upřesnit → Přejít na projekt).
4. Zkopíruj URL webové aplikace (končí `/exec`) → tajemství **GOOGLE_URL**.

## 7. Cloudflare (4 min)
1. dash.cloudflare.com → vpravo nahoře profil → **API Tokens** → Create Token → šablona **Edit Cloudflare Workers** → Account Resources: tvůj účet → Continue → Create → tajemství **CLOUDFLARE_API_TOKEN**.
2. Na úvodní stránce dashboardu (Workers & Pages) vpravo **Account ID** → tajemství **CLOUDFLARE_ACCOUNT_ID**.
3. Workers & Pages → nahoře si poznamenej svoji subdoménu `<něco>.workers.dev`.

## 8. Nasazení (1 min)
GitHub → fd-board → **Actions** → **kolega-deploy** → Run workflow. Po zelené fajfce běží backend na `https://fd-kolega.<něco>.workers.dev`.

## 9. Dispečer – přehled a řízení VŠECH tvých Claude Code session (2 min)
claude.ai/code → Routines → najdi **FD Kolega – Dispečer** (je vypnutý) → uprav prompt: vlož celý obsah `kolega/dispecer-prompt.md` → zapni.
Běží každou hodinu (kratší interval Claude nepovolí): doručí pokyny, které jsi kolegovi nadiktoval, a zapíše přehled stavů. Hotové session ti pípnou přes ntfy.

## 10. Telefon
Otevři **https://frantisekdron.github.io/fd-board/kolega/** → Nastavení → adresa Workeru + APP_TOKEN → klepni na kruh.
Safari/Chrome → Sdílet → **Přidat na plochu**. V autě přes Bluetooth funguje jako hovor.

## Co mu můžeš říct
- „Co se děje v mých session?" · „Pošli do session s webem, ať opraví tlačítko." (Claude Code, přes Dispečera)
- „Založ agenta v repu fd-board a udělej…" · „Jak je na tom?" · „Zastav ho." (vlastní agenti – okamžitě)
- „Mám nové maily?" · „Přečti mi ten od…" · „Napiš mu odpověď, že…" (jen koncept)
- „Najdi na Drivu…" · „Jaké mám otevřené PR?"
