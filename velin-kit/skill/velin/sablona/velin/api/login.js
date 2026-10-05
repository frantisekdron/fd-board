import { checkHeslo, loginCookie, logoutCookie, body } from "./_lib.js";

export default async function handler(req, res) {
  if (req.method === "DELETE") {
    res.setHeader("Set-Cookie", logoutCookie);
    return res.status(200).json({ ok: true });
  }
  if (req.method !== "POST") return res.status(405).end();
  if (!checkHeslo(body(req).heslo)) {
    await new Promise((r) => setTimeout(r, 1500)); // brzda proti hádání hesla
    return res.status(401).json({ error: "Špatné heslo" });
  }
  res.setHeader("Set-Cookie", loginCookie());
  res.status(200).json({ ok: true });
}
