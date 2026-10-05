# Rutina „Velín spínač" (založí František v claude.ai)

Proč: rutiny založené z Claude Code se v claude.ai/code/routines nezobrazují, takže k nim nejde vygenerovat API token.
Spínač proto založíš ve formuláři ty. Jeho jediná práce: když ho zavolá Apps Script (hlas) nebo dashboard Velín,
přepošle povel rutině „Velín spoušť – Dispečer na vyžádání" (trig_01S8EN4VNjmEGNA6nSbUVqyE), která probudí Dispečera
v session CLAUDE VOICE CONTROL. Běh spínače je krátký (jedno volání nástroje), takže stojí minimum.

## Založení (claude.ai/code/routines → New routine)
- **Název:** Velín spínač
- **Prompt:** zkopíruj blok níže.
- **Repo:** žádné (když formulář nějaké vyžaduje, dej fd-kolega).
- **Konektory:** jen **Claude_Code_Remote** (ostatní odeber).
- **Model:** nejlevnější nabízený (Haiku).
- **Trigger:** žádný rozvrh. *Add another trigger* → **API** → *Generate token* → zkopíruj token a URL (obsahuje trig_… = ROUTINE_ID).
- Notifikace z běhů spínače vypni (notifikaci posílá Dispečer).

## Prompt
```
Jsi jen spínač Velínu, nic jiného nedělej: nic nečti, neklonuj, neodpovídej obšírně.
1) Zavolej nástroj fire_trigger (konektor Claude_Code_Remote; když není vidět, načti ho přes ToolSearch dotazem "fire_trigger")
   s trigger_id "trig_01S8EN4VNjmEGNA6nSbUVqyE" a text = celý text, který ti přišel navíc k tomuto promptu (důvod spuštění).
2) Když fire_trigger chybí nebo selže, zavolej send_message do session "session_01GQs4bbhoQyLfa19GjXP4PE" se zprávou:
   "Běh Dispečera NA VYŽÁDÁNÍ (Velín spínač). Proveď postup z /home/user/fd-board/kolega/dispecer-prompt.md a na konci vždy pošli Františkovi push notifikaci." + důvod spuštění.
3) Odpověz jedním slovem: Hotovo (nebo Chyba: <důvod>).
```

## Kam token patří
- Apps Script „Velín spoušť": Vlastnosti skriptu `ROUTINE_ID` = trig_… spínače, `ROUTINE_TOKEN` = token.
- Vercel (dashboard Velín): proměnné `ROUTINE_ID` a `ROUTINE_TOKEN` – stejné hodnoty.
Nový token starý zruší, takže ho generuj jen jednou a vlož na obě místa.

## Když spínač nebude mít nástroje Claude_Code_Remote
Řekni mi – záloha je „schránka" přes GitHub: soukromý PR v repu fd-kolega, ke kterému je Dispečer přihlášený;
Apps Script a dashboard do něj napíšou komentář a ten Dispečera okamžitě probudí (bez tokenu Anthropic).
Založit takový PR smím jen s tvým výslovným souhlasem.
