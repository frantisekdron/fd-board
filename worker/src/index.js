// FD Kolega – backend (Cloudflare Worker)
// Drží všechny klíče. Telefon si tu vyzvedne krátkodobý hlasový token a volá nástroje.
//
// Secrets (wrangler secret put …):
//   APP_TOKEN            – tvoje heslo do appky (libovolný dlouhý řetězec)
//   OPENAI_API_KEY       – realtime hlas
//   ANTHROPIC_API_KEY    – Managed Agents (pracovní session)
//   GITHUB_TOKEN         – fine-grained token na tvoje repa
//   GOOGLE_URL / GOOGLE_KEY – Apps Script most na Gmail + Drive (kolega/google-most.gs)
//   NTFY_TOPIC           – tajný název kanálu v appce ntfy (upozornění na zamčený telefon)
// KV binding: STATE. Cron každou minutu hlídá dokončené session a posílá upozornění.
// Most k Claude Code session (claude.ai/code): soukromé repo BRIDGE_REPO, soubory most/*.json,
// které čte a zapisuje Routine „Dispečer" (běží v Claude Code a má přístup ke všem session).

const AGENT_MODEL = "claude-opus-5-5";
const VOICE_MODEL = "gpt-realtime";
const GH_OWNER = "frantisekdron";

const INSTRUCTIONS = `Jsi Kolega – hlasový asistent a parťák Františka (studio FrantišekDron: drony, video, 3D vizualizace, nabídky pro makléře a developery).
Mluvíš česky, stručně a přirozeně, jako kolega v autě: krátké věty, žádné seznamy, žádné odkazy ani ID nahlas (ID si pamatuj a používej v nástrojích).
František často řídí – odpovídej do pár vět, podrobnosti jen na vyžádání.
Máš nástroje: Claude Code session Františka (cc_overview, cc_command – přehled a pokyny do všech jeho rozjetých session), vlastní pracovní session (create_session atd. – agenti, které zakládáš ty), GitHub, Gmail a Drive.
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
  fn("cc_overview", "Přehled VŠECH Claude Code session (i těch, které František spustil ručně na claude.ai/code). Data obnovuje Dispečer – řekni, jak jsou stará.", {}),
  fn("cc_command", "Pošle pokyn do existující Claude Code session (claude.ai/code). Doručí ho Dispečer při příštím běhu.", {
    session: str("ID nebo název session z cc_overview"), message: str("Pokyn pro session"),
  }, ["session", "message"]),
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
  async scheduled(_ev, env) { await patrol(env); },
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
      if (pathname === "/api/feed") return json(await feed(env, Number(new URL(req.url).searchParams.get("since") || 0)));
      if (pathname === "/api/health") return json(await health(env));
      return json({ error: "not found" }, 404);
    } catch (e) {
      return json({ error: String(e.message || e) }, 500);
    }
  },
};

// ---------- hlídač (cron) ----------
async function patrol(env) {
  const news = [];
  // 1) vlastní pracovní session (Managed Agents)
  if (env.ANTHROPIC_API_KEY) {
    const now = await listSessions(env).catch(() => []);
    const prev = (await env.STATE.get("statuses", "json")) || {};
    for (const s of now) {
      if (prev[s.id] === "running" && s.status !== "running") {
        news.push({ title: s.title || s.id, text: (await lastAgentText(env, s.id)).slice(0, 400) || `stav ${s.status}` });
      }
    }
    if (now.length) await env.STATE.put("statuses", JSON.stringify(Object.fromEntries(now.map((s) => [s.id, s.status]))));
  }
  // 2) Claude Code session – události zapsané Dispečerem
  const ov = await bridgeRead(env, "most/prehled.json").catch(() => null);
  if (ov?.data?.events) {
    const seen = Number((await env.STATE.get("cc_seen")) || 0);
    for (const e of ov.data.events) if (Date.parse(e.at) > seen) news.push({ title: e.title, text: e.text });
    const max = Math.max(seen, ...ov.data.events.map((e) => Date.parse(e.at) || 0));
    await env.STATE.put("cc_seen", String(max));
  }
  if (!news.length) return;
  const list = (await env.STATE.get("feed", "json")) || [];
  const at = Date.now();
  for (const n of news) {
    list.push({ ...n, at });
    await notify(env, `Hotovo: ${n.title}`, n.text);
  }
  await env.STATE.put("feed", JSON.stringify(list.slice(-30)));
}

async function notify(env, title, text) {
  if (!env.NTFY_TOPIC) return;
  await fetch("https://ntfy.sh/", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ topic: env.NTFY_TOPIC, title, message: text || title, click: env.APP_URL, tags: ["white_check_mark"] }),
  }).catch(() => {});
}

async function feed(env, since) {
  const list = (await env.STATE.get("feed", "json")) || [];
  return { items: list.filter((x) => x.at > since), now: Date.now() };
}

// ---------- most k Claude Code (soukromé repo) ----------
async function bridgeRead(env, path) {
  const d = await gh(env, `/repos/${env.BRIDGE_REPO}/contents/${path}`);
  const text = new TextDecoder().decode(Uint8Array.from(atob(d.content.replace(/\n/g, "")), (c) => c.charCodeAt(0)));
  return { data: JSON.parse(text), sha: d.sha };
}
async function ccOverview(env) {
  const { data } = await bridgeRead(env, "most/prehled.json");
  const ageMin = Math.round((Date.now() - Date.parse(data.updated_at)) / 60000);
  return { stari_dat_minut: ageMin, sessions: data.sessions };
}
async function ccCommand(env, { session, message }) {
  let cur = { data: { commands: [] }, sha: undefined };
  try { cur = await bridgeRead(env, "most/prikazy.json"); } catch {}
  cur.data.commands.push({ session, message, at: new Date().toISOString() });
  const r = await fetch(`https://api.github.com/repos/${env.BRIDGE_REPO}/contents/most/prikazy.json`, {
    method: "PUT",
    headers: { authorization: `Bearer ${env.GITHUB_TOKEN}`, accept: "application/vnd.github+json", "user-agent": "fd-kolega" },
    body: JSON.stringify({ message: "kolega: nový pokyn", content: b64(JSON.stringify(cur.data, null, 2)), sha: cur.sha }),
  });
  if (!r.ok) throw new Error(`Most ${r.status}`);
  return "Pokyn zařazen, Dispečer ho doručí při příštím běhu.";
}

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
    case "cc_overview": return ccOverview(env);
    case "cc_command": return ccCommand(env, a);
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

// ---------- Google (Apps Script most, kolega/google-most.gs) ----------
async function gas(env, action, params) {
  const r = await fetch(env.GOOGLE_URL, {
    method: "POST",
    headers: { "content-type": "text/plain" },
    body: JSON.stringify({ key: env.GOOGLE_KEY, action, ...params }),
    redirect: "follow",
  });
  const d = await r.json();
  if (d.error) throw new Error(d.error);
  return d.result;
}
const gmailSearch = (env, query) => gas(env, "gmail_search", { query });
const gmailRead = (env, id) => gas(env, "gmail_read", { id });
const gmailDraft = (env, a) => gas(env, "gmail_draft", a);
const driveSearch = (env, query) => gas(env, "drive_search", { query });
function b64(s) {
  const bytes = new TextEncoder().encode(s);
  let bin = "";
  for (const b of bytes) bin += String.fromCharCode(b);
  return btoa(bin);
}

async function health(env) {
  const has = (k) => Boolean(env[k]);
  return {
    openai: has("OPENAI_API_KEY"), anthropic: has("ANTHROPIC_API_KEY"), github: has("GITHUB_TOKEN"),
    google: has("GOOGLE_URL"), ntfy: has("NTFY_TOPIC"), bridge: has("BRIDGE_REPO"), kv: Boolean(env.STATE),
  };
}
