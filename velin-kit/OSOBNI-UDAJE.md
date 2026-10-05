# Velín – co je osobní a tajné

Balíček `velin-kit` **neobsahuje žádné osobní údaje ani tokeny** – všude jsou jen zástupné hodnoty `{{…}}`, které při nasazení vyplní Claude za každého zvlášť. Každý si zakládá všechno svoje. Nic z cizího Velínu nekopíruj.

## 🔴 Tajné – nikdy nesdílej (ani Claudovi do chatu, ani na screenshotu)
| Co | Kde leží | Proč |
|---|---|---|
| GitHub token **classic** `ghp_…` | jen ve Vercelu → `GITHUB_TOKEN` | plný přístup ke všem tvým repům |
| GitHub token **fine-grained** `github_pat_…` | jen v Apps Scriptu → Vlastnosti skriptu → `GITHUB_TOKEN` | smí komentovat schránku |
| `VELIN_HESLO` | jen ve Vercelu | heslo do dashboardu |
| `VELIN_SECRET` | jen ve Vercelu | podpis přihlášení |

Při podezření na únik: token na GitHubu smaž (Settings → Developer settings → tokeny → Delete), vytvoř nový a vlož ho na stejné místo (u Vercelu pak Redeploy).

## 🟡 Osobní – každý má svoje, nepřebírej cizí
| Co | Odkud se vezme |
|---|---|
| ID složky **Velín** na Google Drive | založí Claude v kroku 4 (je i v adrese složky) |
| Datové repo `uzivatel/velin` | založíš v kroku 2 |
| Číslo PR „Velín – schránka" | založí Claude v kroku 4 |
| Session „Velín – Dispečer" | ta, ve které proběhl krok 4 |
| Adresa dashboardu `….vercel.app` | ukáže Vercel po nasazení |
| Instrukce hlasu a kód Apps Scriptu | Claude je vyplní tvými hodnotami a uloží na tvůj Drive |

Tyhle hodnoty nejsou hesla, ale patří jen k tvému účtu – když bys použil cizí, posílal bys pokyny do cizího Velínu (nebo by nic nefungovalo).

## Při předávání dál
- Posílej jen odkaz na balíček `velin-kit` (nebo `velin-skill.zip`) – ne své dokumenty z Drive, ne svůj Apps Script a ne screenshoty z Vercelu nebo GitHub tokenů.
- Datové repo `velin` nech **soukromé**.
