import { guard, gh, OWNER } from "./_lib.js";

// Čtecí proxy na GitHub: token zůstává na serveru, prohlížeč ho nikdy nevidí.
// Jen GET a jen repa Františka (+ seznam repozitářů a hledání PR).
const POVOLENO = new RegExp(`^/(repos/${OWNER}/[\\w.-]+(/[^?#]*)?|user/repos|search/issues)(\\?.*)?$`);
const MAX = 3_000_000;

export default guard(async (req, res) => {
  if (req.method !== "GET") return res.status(405).end();
  const p = String(req.query.p || "");
  if (!POVOLENO.test(p) || p.includes("..")) return res.status(403).json({ error: "nepovolená cesta" });
  const accept = req.query.diff ? "application/vnd.github.diff" : req.query.raw ? "application/vnd.github.raw" : undefined;
  const r = await gh(p, accept ? { accept } : {});
  const text = await r.text();
  res.setHeader("content-type", r.headers.get("content-type") || "application/json");
  res.status(r.status).send(text.length > MAX ? text.slice(0, MAX) + "\n…(zkráceno)" : text);
});
