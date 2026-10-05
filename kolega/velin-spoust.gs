// Velín – spoušť Dispečera přes Google Drive (Google Apps Script, zdarma).
//
// Co dělá: každou minutu se podívá do složky „FD Kolega". Když tam najde
//   • soubor „KOLEGA spusť" (nebo cokoli s RUN_NOW v názvu) – hlas chce čerstvý běh hned,
//   • nový soubor „KOLEGA pokyn – …" (pokud AUTO_POKYN = true),
// napíše komentář VELIN_RUN do „schránky" – PR #1 v soukromém repu fd-kolega. Dispečer (session
// CLAUDE VOICE CONTROL) je k PR přihlášený, takže ho komentář do pár sekund probudí.
// Spouštěcí soubory pak přesune do podsložky FD Kolega/Archiv (žádná smyčka, nic se nemaže), pokyny nechá Dispečerovi.
// Stav posledního spuštění zapisuje do Google Docu „Velín – spoušť", aby si ho hlas mohl přečíst.
//
// Token NIKDY nedávej do kódu: Nastavení projektu (⚙) → Vlastnosti skriptu →
//   GITHUB_TOKEN = fine-grained token jen pro repo fd-kolega (Pull requests: Read and write)

const SLOZKA = "1NpVVdaZs2ylWy4NbkNfg6aKwL_Ic-czm"; // FD Kolega
const AUTO_POKYN = true;   // nový „KOLEGA pokyn" = spustit Dispečera hned (false = jen hodinový běh)
const PAUZA_MIN = 2;       // min. rozestup dvou spuštění; co přijde mezitím, počká na další minutu
const STAV_DOC = "Velín – spoušť";
const ARCHIV = "118uN-cQinflP9JAfbqXhNNq0EvV6ShQY"; // FD Kolega/Archiv – místo koše (František nechce nic mazat)
const SCHRANKA = "frantisekdron/fd-kolega/issues/1"; // PR #1 „Velín – schránka"

function hlidej() {
  const props = PropertiesService.getScriptProperties();
  const ted = Date.now();
  if (ted < Number(props.getProperty("dalsi_povoleno") || 0)) return;

  const spousti = [];
  const pokyny = [];
  const videne = JSON.parse(props.getProperty("videne_pokyny") || "{}");
  const it = DriveApp.searchFiles(
    `'${SLOZKA}' in parents and trashed = false and ` +
    `(title contains 'KOLEGA spusť' or title contains 'KOLEGA spust' or title contains 'RUN_NOW' or title contains 'KOLEGA pokyn')`
  );
  while (it.hasNext()) {
    const f = it.next();
    const n = f.getName();
    if (/KOLEGA spus|RUN_NOW/i.test(n)) spousti.push(f);
    else if (AUTO_POKYN && /^KOLEGA pokyn/i.test(n) && !videne[f.getId()]) pokyny.push(f);
  }
  if (!spousti.length && !pokyny.length) return;

  const posledni = Number(props.getProperty("posledni_spusteni") || 0);
  if (ted - posledni < PAUZA_MIN * 60000) return; // počká, nic se neztratí

  const duvod = [
    ...spousti.map((f) => "spoušť: " + f.getName()),
    ...pokyny.map((f) => "nový pokyn: " + f.getName()),
  ].join("\n");
  const r = spust(duvod);

  if (r.ok) {
    props.setProperty("posledni_spusteni", String(ted));
    spousti.forEach((f) => { f.setName(f.getName() + " · spuštěno " + cas(ted)); f.moveTo(DriveApp.getFolderById(ARCHIV)); });
    pokyny.forEach((f) => (videne[f.getId()] = ted));
    for (const id in videne) if (ted - videne[id] > 2 * 86400000) delete videne[id];
    props.setProperty("videne_pokyny", JSON.stringify(videne));
    zapisStav(`Dispečer spuštěn ${cas(ted)}. Důvod:\n${duvod}\nPřehled „Kolega – přehled" bude obnoven zhruba do 3–5 minut a přijde notifikace.\nKomentář: ${r.url || "-"}`);
  } else {
    if (r.retryAfter) props.setProperty("dalsi_povoleno", String(ted + r.retryAfter * 1000));
    // spouštěcí soubory zůstávají → zkusí se znovu příští minutu
    zapisStav(`CHYBA spuštění ${cas(ted)}: ${r.chyba}\nZkusím to znovu. Mezitím doběhne hodinový Dispečer (7–23 v :18).`);
  }
}

function spust(text) {
  const token = PropertiesService.getScriptProperties().getProperty("GITHUB_TOKEN");
  if (!token) return { ok: false, chyba: "chybí GITHUB_TOKEN ve Vlastnostech skriptu" };
  const res = UrlFetchApp.fetch(`https://api.github.com/repos/${SCHRANKA}/comments`, {
    method: "post",
    contentType: "application/json",
    headers: { Authorization: "Bearer " + token, Accept: "application/vnd.github+json" },
    payload: JSON.stringify({ body: "VELIN_RUN\nSpoušť z Google Drive (Velín):\n" + text }),
    muteHttpExceptions: true,
  });
  const kod = res.getResponseCode();
  if (kod === 201) return { ok: true, url: JSON.parse(res.getContentText()).html_url };
  return { ok: false, chyba: `GitHub HTTP ${kod} ${res.getContentText().slice(0, 300)}`, retryAfter: kod === 403 || kod === 429 ? 300 : 0 };
}

function zapisStav(text) {
  const props = PropertiesService.getScriptProperties();
  let id = props.getProperty("stav_doc");
  let doc;
  try { doc = id && DocumentApp.openById(id); } catch (e) { doc = null; }
  if (!doc) {
    doc = DocumentApp.create(STAV_DOC);
    DriveApp.getFileById(doc.getId()).moveTo(DriveApp.getFolderById(SLOZKA));
    props.setProperty("stav_doc", doc.getId());
  }
  doc.getBody().setText(`Velín – spoušť Dispečera (stav k ${cas(Date.now())})\n\n${text}`);
  doc.saveAndClose();
}

function cas(ms) {
  return Utilities.formatDate(new Date(ms), "Europe/Prague", "d. M. HH:mm");
}

// Spusť JEDNOU ručně (▶ Spustit → nastav): založí minutový časovač a stavový dokument.
function nastav() {
  ScriptApp.getProjectTriggers()
    .filter((t) => t.getHandlerFunction() === "hlidej")
    .forEach((t) => ScriptApp.deleteTrigger(t));
  ScriptApp.newTrigger("hlidej").timeBased().everyMinutes(1).create();
  zapisStav("Spoušť nastavena. Čekám na soubor „KOLEGA spusť“ nebo nový „KOLEGA pokyn“ ve složce FD Kolega.");
}

// Ruční test (▶ Spustit → test): zavolá Dispečera hned, bez souboru na Drivu.
function test() {
  const r = spust("ruční test z Apps Scriptu");
  Logger.log(JSON.stringify(r));
  zapisStav(r.ok ? `Test OK ${cas(Date.now())} – Dispečer spuštěn.\nKomentář: ${r.url || "-"}` : `Test SELHAL: ${r.chyba}`);
}

// Vypnutí spouště (hodinový Dispečer běží dál).
function vypni() {
  ScriptApp.getProjectTriggers().forEach((t) => ScriptApp.deleteTrigger(t));
  zapisStav("Spoušť VYPNUTA. Běží jen hodinový Dispečer 7–23.");
}
