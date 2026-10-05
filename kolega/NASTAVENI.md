# FD Kolega – zprovoznění (cca 20 min, jednorázově)

Appka: `https://frantisekdron.github.io/fd-board/kolega/` (po sloučení do main).
Backend: Cloudflare Worker ve složce `worker/`.

## 1. Klíče
| Co | Kde |
|---|---|
| `OPENAI_API_KEY` | platform.openai.com → API keys (realtime hlas) |
| `ANTHROPIC_API_KEY` | console.anthropic.com → API keys (pracovní agenti) |
| `GITHUB_TOKEN` | github.com/settings/personal-access-tokens → fine-grained, repa frantisekdron, Contents + Pull requests: Read & write |
| `APP_TOKEN` | vymysli dlouhé heslo – zadáš ho v appce |
| `GOOGLE_*` | viz krok 3 |

## 2. Nasazení Workeru (na počítači, jednou)
```bash
cd worker
npx wrangler login                       # přihlásí se přes váš Google účet do Cloudflare
npx wrangler kv namespace create STATE   # vypsané id vlož do wrangler.toml
for k in APP_TOKEN OPENAI_API_KEY ANTHROPIC_API_KEY GITHUB_TOKEN GOOGLE_CLIENT_ID GOOGLE_CLIENT_SECRET GOOGLE_REFRESH_TOKEN; do npx wrangler secret put $k; done
npx wrangler deploy                      # vypíše adresu https://fd-kolega.<něco>.workers.dev
```

## 3. Google (Gmail + Drive)
1. console.cloud.google.com → nový projekt → zapnout **Gmail API** a **Google Drive API**.
2. OAuth consent screen → External, přidat sebe jako test usera.
3. Credentials → OAuth client ID → typ *Web application*, redirect URI `https://developers.google.com/oauthplayground`.
4. developers.google.com/oauthplayground → ozubené kolo → „Use your own OAuth credentials" → vlož client ID/secret →
   scopes `https://www.googleapis.com/auth/gmail.modify` a `https://www.googleapis.com/auth/drive.readonly` → Authorize → Exchange → zkopíruj **refresh token**.
5. Pozn.: v režimu „Testing" refresh token po 7 dnech vyprší – v consent screen přepni na „In production" (pro vlastní použití stačí bez ověření).

## 4. Telefon
Otevři appku → Nastavení → adresa Workeru + APP_TOKEN → klepni na kruh. V prohlížeči „Přidat na plochu".
Kontrola backendu: `curl -H "Authorization: Bearer $APP_TOKEN" https://…workers.dev/api/health`.

## Co umí
- „Co dělají moje session?" / „Založ session v repu fd-board a oprav…" / „Jak je na tom ta session?" / „Zastav ji."
- „Mám nové maily?" / „Přečti mi ten od…" / „Napiš mu odpověď, že…" (uloží koncept, neodesílá)
- „Najdi na Drivu nabídku pro…" / „Jaké mám otevřené PR?"
- Když pracovní session doběhne, kolega se sám ozve (dokud je appka otevřená).

## Náklady (orientačně)
Hlas ~0,5–1 Kč/min hovoru. Pracovní session dle práce; strop na jednu session je `SESSION_BUDGET_CENTS` ve `wrangler.toml` ($10).

## Omezení
- Session na claude.ai/code (ty, které spouštíš ručně) nemají veřejné API – kolega řídí vlastní session přes Anthropic Managed Agents.
- Upozornění chodí, jen když je appka otevřená (displej drží zapnutý). Push na zamčený telefon = další krok.
