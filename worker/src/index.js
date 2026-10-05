// FD Kolega – backend (Cloudflare Worker)
// Drží všechny klíče. Telefon si tu vyzvedne krátkodobý hlasový token a volá nástroje.
//
// Secrets (wrangler secret put …):
//   APP_TOKEN            – tvoje heslo do appky (libovolný dlouhý řetězec)
//   OPENAI_API_KEY       – realtime hlas
//   ANTHROPIC_API_KEY    – Managed Agents (pracovní session)
//   GITHUB_TOKEN         – fine-grained token na tvoje repa
//   GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET / GOOGLE_REFRESH_TOKEN – Gmail + Drive
// KV binding: STATE (id agenta/prostředí, poslední stavy session pro notifikace)

const AGENT_MODEL = "claude-opus-5-5";
const VOICE_MODEL = "gpt-realtime";
const GH_OWNER = "frantisekdron";

const INSTRUCTIONS = `Jsi Kolega – hlasový asistent a parťák Františka (studio FrantišekDron: drony, video, 3D vizualizace, nabídky pro makléře a developery).
Mluvíš česky, stručně a přirozeně, jako kolega v autě: krátké věty, žádné seznamy, žádné odkazy ani ID nahlas (ID si pamatuj a používej v nástrojích).
František často řídí – odpovídej do pár vět, podrobnosti jen na vyžádání.
Máš nástroje: pracovní session (agenti Claude, kteří umí programovat a pracovat v repozitářích), GitHub, Gmail a Drive.
Než něco odešleš nebo založíš, jednou krátce zopakuj, co uděláš, a počkej na "jo"/"pošli". E-maily jen ukládáš jako koncepty, neodesíláš.
Když nástroj selže, řekni to jednou větou a navrhni další krok.`;

// ---------- definice nástrojů pro hlasový model ----------
const TOOLS = [
  fn("list_sessions", "Seznam posledních pracovních session (agentů) a jejich stav.", {}),
  fn("session_status", "Stav jedné session a její poslední odpovědi.", { session_id: str("ID session") }, ["session_id"]),
  fn("create_session", "Založí novou pracovní session s úkolem. Volitelně připojí GitHub repo.", {
    title: str("Krátký název"),
    task: str("Zadání úkolu pro agenta, podrobně"),
    repo: str("Název repa pod frantisekdron, např. fd-board (volitelné)"),
  }, ["title", "task"]),
  fn("send_to_session", "Pošle zprávu / další pokyn do existující session.", { session_id: str("ID"), message: str("Text") }, ["session_id", "message"]),
  fn("stop_session", "Přeruší běžící session.", { session_id: str("ID") }, ["session_id"]),
  fn("github_overview", "Přehled: naposledy upravená repa a otevřené pull requesty.", {}),
  fn("github_repo", "Detail repa: poslední commity a otevřené PR.", { repo: str("Název repa") }, ["repo"]),
  fn("gmail_search", "Hledá e-maily (Gmail syntax, např. 'is:unread newer_than:1d').", { query: str("Dotaz") }, ["query"]),
  fn("gmail_read", "Přečte jeden e-mail.", { id: str("ID zprávy") }, ["id"]),
  fn("gmail_draft", "Uloží koncept e-mailu (neodesílá).", { to: str("Adresát"), subject: str("Předmět"), body: str("Text") }, ["to", "subject", "body"]),
  fn("drive_search", "Hledá soubory na Google Drive podle názvu nebo obsahu.", { query: str("Hledaný text") }, ["query"]),
];
function fn(name, description, properties, required = []) {
  return { type: "function", name, description, parameters: { type: "object", properties, required } };
}
function str(description) { return { type: "string", description }; }

// ---------- router ----------
export default {
  async fetch(req, env) {
    const cors = {
      "Access-Control-Allow-Origin": env.ALLOWED_ORIGIN || "*",
      "Access-Control-Allow-Headers": "content-type, authorization",
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    };
    if (req.method === "OPTIONS") return new Response(null, { headers: cors });
    const json = (data, status = 200) =>
      new Response(JSON.stringify(data), { status, headers: { ...cors, "content-type": "application/json" } });

    const auth = req.headers.get("authorization") || "";
    if (!env.APP_TOKEN || auth !== `Bearer ${env.APP_TOKEN}`) return json({ error: "unauthorized" }, 401);

    const { pathname } = new URL(req.url);
    try {
      if (pathname === "/api/voice-token") return json(await voiceToken(env));
      if (pathname === "/api/tool" && req.method === "POST") {
        const { name, args } = await req.json();
        return json({ result: await runTool(env, name, args || {}) });
      }
      if (pathname === "/api/watch") return json(await watch(env));
      if (pathname === "/api/health") return json(await health(env));
      return json({ error: "not found" }, 404);
    } catch (e) {
      return json({ error: String(e.message || e) }, 500);
    }
  },
};

// ---------- hlas ----------
async function voiceToken(env) {
  const r = await fetch("https://api.openai.com/v1/realtime/client_secrets", {
    method: "POST",
    headers: { authorization: `Bearer ${env.OPENAI_API_KEY}`, "content-type": "application/json" },
    body: JSON.stringify({
      session: {
        type: "realtime",
        model: VOICE_MODEL,
        instructions: INSTRUCTIONS,
        tools: TOOLS,
        audio: {
          input: { transcription: { model: "gpt-4o-transcribe", language: "cs" }, turn_detection: { type: "semantic_vad" } },
          output: { voice: env.VOICE || "marin" },
        },
      },
    }),
  });
  if (!r.ok) throw new Error(`OpenAI ${r.status}: ${await r.text()}`);
  const d = await r.json();
  return { token: d.value, model: VOICE_MODEL };
}

async function runTool(env, name, a) {
  switch (name) {
    case "list_sessions": return listSessions(env);
    case "session_status": return sessionStatus(env, a.session_id);
    case "create_session": return createSession(env, a);
    case "send_to_session": return sendMessage(env, a.session_id, a.message);
    case "stop_session": return ant(env, `/v1/sessions/${a.session_id}/events`, { events: [{ type: "user.interrupt" }] }).then(() => "Přerušeno.");
    case "github_overview": return githubOverview(env);
    case "github_repo": return githubRepo(env, a.repo);
    case "gmail_search": return gmailSearch(env, a.query);
    case "gmail_read": return gmailRead(env, a.id);
    case "gmail_draft": return gmailDraft(env, a);
    case "drive_search": return driveSearch(env, a.query);
    default: throw new Error(`Neznámý nástroj ${name}`);
  }
}

// ---------- Managed Agents ----------
async function ant(env, path, body, method) {
  const r = await fetch(`https://api.anthropic.com${path}`, {
    method: method || (body ? "POST" : "GET"),
    headers: {
      "x-api-key": env.ANTHROPIC_API_KEY,
      "anthropic-version": "2023-06-01",
      "anthropic-beta": "managed-agents-2026-04-01",
      "content-type": "application/json",
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) throw new Error(`Anthropic ${r.status}: ${(await r.text()).slice(0, 300)}`);
  return r.json();
}

// Agent a prostředí se zakládají jednou a ID se drží v KV.
async function ensureAgent(env) {
  let ids = await env.STATE.get("agent", "json");
  if (ids) return ids;
  const envObj = await ant(env, "/v1/environments", {
    name: "fd-kolega-env",
    config: { type: "cloud", networking: { type: "limited", allow_package_managers: true, allow_mcp_servers: true } },
  });
  const agent = await ant(env, "/v1/agents", {
    name: "FD Kolega – pracant",
    model: AGENT_MODEL,
    system: "Pracuješ pro Františka (studio FrantišekDron). Dotahuj úkoly samostatně do konce. Na konci napiš 2–3 věty česky: co je hotovo a co případně potřebuje jeho rozhodnutí – bude se to předčítat nahlas.",
    tools: [{ type: "agent_toolset_20260401" }],
  });
  ids = { agent_id: agent.id, agent_version: agent.version, environment_id: envObj.id };
  await env.STATE.put("agent", JSON.stringify(ids));
  return ids;
}

async function listSessions(env) {
  const d = await ant(env, "/v1/sessions?limit=10");
  return (d.data || []).map((s) => ({ id: s.id, title: s.title, status: s.status, updated: s.updated_at }));
}

async function lastAgentText(env, id) {
  const ev = await ant(env, `/v1/sessions/${id}/events?limit=100`).catch(() => ({ data: [] }));
  const msgs = (ev.data || []).filter((e) => e.type === "agent.message");
  const pick = msgs.length ? msgs[msgs.length - 1] : null;
  return pick ? pick.content.filter((c) => c.type === "text").map((c) => c.text).join("\n").slice(0, 1500) : "";
}

async function sessionStatus(env, id) {
  const s = await ant(env, `/v1/sessions/${id}`);
  return { id, title: s.title, status: s.status, last_reply: await lastAgentText(env, id) };
}

async function createSession(env, { title, task, repo }) {
  const ids = await ensureAgent(env);
  const body = {
    agent: { type: "agent", id: ids.agent_id },
    environment_id: ids.environment_id,
    title,
    budget: { type: "limit", max_list_cost: { amount: env.SESSION_BUDGET_CENTS || "1000", currency: "USD" } },
  };
  if (repo) {
    body.resources = [{
      type: "github_repository",
      url: `https://github.com/${repo.includes("/") ? repo : `${GH_OWNER}/${repo}`}`,
      mount_path: "/workspace/repo",
      authorization_token: env.GITHUB_TOKEN,
    }];
  }
  const s = await ant(env, "/v1/sessions", body);
  await sendMessage(env, s.id, task);
  return { id: s.id, title, started: true };
}

async function sendMessage(env, id, text) {
  await ant(env, `/v1/sessions/${id}/events`, {
    events: [{ type: "user.message", content: [{ type: "text", text }] }],
  });
  return "Odesláno.";
}

// Pro notifikace: vrátí session, které od minula přešly z běhu do klidu.
async function watch(env) {
  const now = await listSessions(env);
  const prev = (await env.STATE.get("statuses", "json")) || {};
  const done = [];
  for (const s of now) {
    if (prev[s.id] === "running" && s.status !== "running") {
      done.push({ id: s.id, title: s.title, status: s.status, last_reply: await lastAgentText(env, s.id) });
    }
  }
  await env.STATE.put("statuses", JSON.stringify(Object.fromEntries(now.map((s) => [s.id, s.status]))));
  return { done, sessions: now };
}

// ---------- GitHub ----------
async function gh(env, path) {
  const r = await fetch(`https://api.github.com${path}`, {
    headers: { authorization: `Bearer ${env.GITHUB_TOKEN}`, accept: "application/vnd.github+json", "user-agent": "fd-kolega" },
  });
  if (!r.ok) throw new Error(`GitHub ${r.status}`);
  return r.json();
}
async function githubOverview(env) {
  const [repos, prs] = await Promise.all([
    gh(env, "/user/repos?sort=pushed&per_page=6"),
    gh(env, `/search/issues?q=${encodeURIComponent(`is:pr is:open user:${GH_OWNER}`)}&per_page=10`),
  ]);
  return {
    recent_repos: repos.map((r) => ({ name: r.name, pushed: r.pushed_at })),
    open_prs: prs.items.map((p) => ({ repo: p.repository_url.split("/").pop(), number: p.number, title: p.title })),
  };
}
async function githubRepo(env, repo) {
  const full = repo.includes("/") ? repo : `${GH_OWNER}/${repo}`;
  const [commits, pulls] = await Promise.all([
    gh(env, `/repos/${full}/commits?per_page=5`),
    gh(env, `/repos/${full}/pulls?state=open&per_page=10`),
  ]);
  return {
    commits: commits.map((c) => ({ msg: c.commit.message.split("\n")[0], date: c.commit.author.date })),
    open_prs: pulls.map((p) => ({ number: p.number, title: p.title })),
  };
}

// ---------- Google ----------
async function googleToken(env) {
  const cached = await env.STATE.get("gtoken");
  if (cached) return cached;
  const r = await fetch("https://oauth2.googleapis.com/token", {
    method: "POST",
    body: new URLSearchParams({
      client_id: env.GOOGLE_CLIENT_ID,
      client_secret: env.GOOGLE_CLIENT_SECRET,
      refresh_token: env.GOOGLE_REFRESH_TOKEN,
      grant_type: "refresh_token",
    }),
  });
  if (!r.ok) throw new Error(`Google auth ${r.status}`);
  const d = await r.json();
  await env.STATE.put("gtoken", d.access_token, { expirationTtl: Math.max(60, d.expires_in - 120) });
  return d.access_token;
}
async function google(env, url, init = {}) {
  const r = await fetch(url, { ...init, headers: { ...(init.headers || {}), authorization: `Bearer ${await googleToken(env)}` } });
  if (!r.ok) throw new Error(`Google ${r.status}: ${(await r.text()).slice(0, 200)}`);
  return r.json();
}
const GM = "https://gmail.googleapis.com/gmail/v1/users/me";
async function gmailSearch(env, q) {
  const list = await google(env, `${GM}/messages?maxResults=8&q=${encodeURIComponent(q)}`);
  const out = [];
  for (const m of list.messages || []) {
    const d = await google(env, `${GM}/messages/${m.id}?format=metadata&metadataHeaders=From&metadataHeaders=Subject&metadataHeaders=Date`);
    const h = Object.fromEntries(d.payload.headers.map((x) => [x.name, x.value]));
    out.push({ id: m.id, from: h.From, subject: h.Subject, date: h.Date, snippet: d.snippet });
  }
  return out;
}
async function gmailRead(env, id) {
  const d = await google(env, `${GM}/messages/${id}?format=full`);
  const h = Object.fromEntries(d.payload.headers.map((x) => [x.name, x.value]));
  const findText = (p) => {
    if (p.mimeType === "text/plain" && p.body?.data) return p.body.data;
    for (const c of p.parts || []) { const t = findText(c); if (t) return t; }
    return null;
  };
  const raw = findText(d.payload);
  const body = raw ? new TextDecoder().decode(Uint8Array.from(atob(raw.replace(/-/g, "+").replace(/_/g, "/")), (c) => c.charCodeAt(0))) : d.snippet;
  return { from: h.From, subject: h.Subject, date: h.Date, body: body.slice(0, 4000) };
}
async function gmailDraft(env, { to, subject, body }) {
  const mime = `To: ${to}\r\nSubject: =?UTF-8?B?${b64(subject)}?=\r\nContent-Type: text/plain; charset=UTF-8\r\nContent-Transfer-Encoding: base64\r\n\r\n${b64(body)}`;
  const raw = b64(mime).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  await google(env, `${GM}/drafts`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ message: { raw } }) });
  return "Koncept uložen v Gmailu.";
}
function b64(s) {
  const bytes = new TextEncoder().encode(s);
  let bin = "";
  for (const b of bytes) bin += String.fromCharCode(b);
  return btoa(bin);
}
async function driveSearch(env, q) {
  const esc = q.replace(/'/g, "\\'");
  const d = await google(env, `https://www.googleapis.com/drive/v3/files?pageSize=8&orderBy=modifiedTime desc&fields=files(id,name,modifiedTime,webViewLink)&q=${encodeURIComponent(`fullText contains '${esc}' and trashed = false`)}`);
  return d.files;
}

async function health(env) {
  const has = (k) => Boolean(env[k]);
  return {
    openai: has("OPENAI_API_KEY"), anthropic: has("ANTHROPIC_API_KEY"), github: has("GITHUB_TOKEN"),
    google: has("GOOGLE_REFRESH_TOKEN"), kv: Boolean(env.STATE),
  };
}
