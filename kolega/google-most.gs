// FD Kolega – most na Gmail a Drive (Google Apps Script).
// 1) script.google.com → Nový projekt → vlož tento kód.
// 2) Nahoře změň KLIC na stejný náhodný řetězec, jaký dáš do GitHub secretu GOOGLE_KEY.
// 3) Nasadit → Nové nasazení → Webová aplikace → Spustit jako: Já, Přístup: Kdokoli → Nasadit → povolit přístup.
// 4) Zkopírovanou URL (končí /exec) dej do GitHub secretu GOOGLE_URL.
const KLIC = "ZMEN_ME_NA_NAHODNY_RETEZEC";

function doPost(e) {
  try {
    const p = JSON.parse(e.postData.contents);
    if (p.key !== KLIC || KLIC.startsWith("ZMEN")) return out({ error: "unauthorized" });
    return out({ result: ACTIONS[p.action](p) });
  } catch (err) {
    return out({ error: String(err) });
  }
}

const ACTIONS = {
  gmail_search: (p) => GmailApp.search(p.query, 0, 8).map((t) => {
    const m = t.getMessages().pop();
    return { id: m.getId(), from: m.getFrom(), subject: m.getSubject(), date: m.getDate(), snippet: m.getPlainBody().slice(0, 200) };
  }),
  gmail_read: (p) => {
    const m = GmailApp.getMessageById(p.id);
    return { from: m.getFrom(), subject: m.getSubject(), date: m.getDate(), body: m.getPlainBody().slice(0, 4000) };
  },
  gmail_draft: (p) => { GmailApp.createDraft(p.to, p.subject, p.body); return "Koncept uložen v Gmailu."; },
  drive_search: (p) => {
    const it = DriveApp.searchFiles(`fullText contains '${p.query.replace(/'/g, "\\'")}' and trashed = false`);
    const res = [];
    while (it.hasNext() && res.length < 8) {
      const f = it.next();
      res.push({ name: f.getName(), modified: f.getLastUpdated(), url: f.getUrl() });
    }
    return res;
  },
};

function out(o) {
  return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON);
}
