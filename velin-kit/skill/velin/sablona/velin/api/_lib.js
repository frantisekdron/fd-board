// Sdílené pomůcky serveru Velínu. Soubory s „_" na začátku nejsou samostatné endpointy.
// Tajné hodnoty jen z prostředí Vercelu (Settings → Environment Variables), nikdy v kódu:
//   VELIN_HESLO    – heslo do dashboardu
//   VELIN_SECRET   – náhodný řetězec na podpis přihlašovací cookie
//   GITHUB_TOKEN   – classic token (scope repo), všechna repa
import crypto from "node:crypto";

// Datové repo = repo, ze kterého Vercel dashboard nasadil (systémové proměnné Vercelu).
// Jde přepsat proměnnou VELIN_REPO ve tvaru „uzivatel/repo".
export const KOLEGA = process.env.VELIN_REPO || `${process.env.VERCEL_GIT_REPO_OWNER}/${process.env.VERCEL_GIT_REPO_SLUG}`;
export const OWNER = KOLEGA.split("/")[0];
const DNY = 90;

const secret = () => process.env.VELIN_SECRET || "";
const hmac = (s) => crypto.createHmac("sha256", secret()).update(s).digest("hex");
const same = (a, b) => {
  const x = crypto.createHash("sha256").update(String(a)).digest();
  const y = crypto.createHash("sha256").update(String(b)).digest();
  return crypto.timingSafeEqual(x, y);
};

export function checkHeslo(h) {
  const ok = process.env.VELIN_HESLO && secret();
  return Boolean(ok) && same(h || "", process.env.VELIN_HESLO);
}
export function loginCookie() {
  const exp = Date.now() + DNY * 86400000;
  return `velin=${exp}.${hmac(String(exp))}; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=${DNY * 86400}`;
}
export const logoutCookie = "velin=; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=0";

function authed(req) {
  if (!secret()) return false;
  const m = /(?:^|;\s*)velin=(\d+)\.([0-9a-f]{64})/.exec(req.headers.cookie || "");
  return Boolean(m) && Date.now() < Number(m[1]) && same(m[2], hmac(m[1]));
}

// Obal endpointu: přihlášení + jednotné chyby.
export const guard = (fn) => async (req, res) => {
  if (!authed(req)) return res.status(401).json({ error: "login" });
  try {
    await fn(req, res);
  } catch (e) {
    res.status(500).json({ error: String(e?.message || e) });
  }
};

export function gh(path, { method = "GET", body, accept = "application/vnd.github+json" } = {}) {
  return fetch("https://api.github.com" + path, {
    method,
    headers: {
      authorization: "Bearer " + process.env.GITHUB_TOKEN,
      accept,
      "x-github-api-version": "2022-11-28",
      "user-agent": "fd-velin",
      ...(body ? { "content-type": "application/json" } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
}

export async function readJson(path) {
  const r = await gh(`/repos/${KOLEGA}/contents/${path}`);
  if (r.status === 404) return { json: null, sha: null };
  if (!r.ok) {
    const msg = (await r.json().catch(() => ({}))).message || "";
    const rada = r.status === 401 ? " – neplatný GITHUB_TOKEN" : r.status === 403 ? " – GITHUB_TOKEN nemá přístup (je potřeba classic token se scope repo)" : "";
    throw new Error(`GitHub ${r.status} (${path})${rada}${msg ? ": " + msg : ""}`);
  }
  const d = await r.json();
  return { json: JSON.parse(Buffer.from(d.content, "base64").toString("utf8")), sha: d.sha };
}

export function writeJson(path, json, sha, message) {
  return gh(`/repos/${KOLEGA}/contents/${path}`, {
    method: "PUT",
    body: { message, content: Buffer.from(JSON.stringify(json, null, 1)).toString("base64"), sha: sha || undefined },
  });
}

// Úprava fronty pokynů s opakováním při souběhu s Dispečerem (409/422 = někdo zapsal mezitím).
export async function updateQueue(change, message) {
  for (let i = 0; i < 4; i++) {
    const { json, sha } = await readJson("most/prikazy.json");
    const q = json && Array.isArray(json.commands) ? json : { commands: [] };
    if (change(q) === false) return q;
    const r = await writeJson("most/prikazy.json", q, sha, message);
    if (r.ok) return q;
    if (r.status !== 409 && r.status !== 422) throw new Error("Zápis fronty selhal: GitHub " + r.status);
  }
  throw new Error("Zápis fronty selhal (souběh), zkus to znovu");
}

// Okamžité spuštění Dispečera: komentář VELIN_RUN do „schránky" (PR v datovém repu), ke které je
// Dispečer přihlášený – GitHub ho do pár sekund probudí. Když to selže, pokyn doručí hodinový běh.
export const SCHRANKA_PR = Number(process.env.VELIN_SCHRANKA_PR || 1);
export async function fire(text) {
  try {
    const r = await gh(`/repos/${KOLEGA}/issues/${SCHRANKA_PR}/comments`, {
      method: "POST",
      body: { body: "VELIN_RUN\n" + text.slice(0, 2000) },
    });
    if (r.ok) return { ok: true };
    return { ok: false, error: `schránka: GitHub ${r.status} – doručí hodinový běh` };
  } catch (e) {
    return { ok: false, error: String(e?.message || e) };
  }
}

export const body = (req) => (typeof req.body === "string" ? JSON.parse(req.body || "{}") : req.body || {});
