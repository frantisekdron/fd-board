# Velín – balíček k předání

Hlasové ovládací centrum pro Claude Code session: **hlas** (projekt v aplikaci Claude) + **dashboard** (web na telefonu i počítači) + **Dispečer** (cloudová session, která čte a řídí ostatní session). Funguje i při vypnutém počítači.

## Jak to předat kolegovi
Pošli mu odkaz na tuhle složku:
**https://github.com/frantisekdron/fd-board/tree/main/velin-kit**
a ať postupuje podle [NAVOD.md](NAVOD.md). Víc nepotřebuje – nasazení za něj z velké části udělá Claude.

## Co je uvnitř
| Soubor | Pro koho | Co to je |
|---|---|---|
| [NAVOD.md](NAVOD.md) | kolega | návod od nuly, krok za krokem, pro netechnického člověka |
| [OSOBNI-UDAJE.md](OSOBNI-UDAJE.md) | kolega | co je tajné (tokeny, hesla) a co osobní (ID složky, repo…) |
| [velin-skill.zip](velin-skill.zip) | Claude | skill k nahrání do claude.ai (nepovinné) |
| [skill/velin/SKILL.md](skill/velin/SKILL.md) | Claude | postup, podle kterého Claude Velín nasadí |
| `skill/velin/sablona/` | Claude | obsah datového repa: dashboard (`velin/`), stav (`most/`), postup Dispečera (`dispecer/postup.md`) |
| `skill/velin/hlas/` | Claude | šablona instrukcí hlasového projektu |
| `skill/velin/apps-script/` | Claude | šablona Apps Script spouště |
| `skill/velin/schranka/` | Claude | soubor „schránky" (pull request, který probouzí Dispečera) |

Balíček neobsahuje žádné tokeny ani osobní ID – hodnoty `{{…}}` vyplní Claude u každého zvlášť.

## Jak to funguje
```
hlas (projekt Velín) ──► soubor na Google Drive ──► Apps Script (každou minutu)
                                                      │ komentář VELIN_RUN
dashboard (Vercel) ──────────────────────────────────►┤
                                                      ▼
                            „schránka" = draft PR v soukromém repu velin
                                                      │ GitHub probudí
                                                      ▼
            Dispečer (cloudová Claude Code session, + každou hodinu 7–23)
              ├─ doručí pokyny do session / založí nové
              ├─ zapíše most/velin_state.json (jediný zdroj pravdy) → dashboard
              └─ „Velín – přehled" + velin_state.json na Drive → hlas, + notifikace
```
