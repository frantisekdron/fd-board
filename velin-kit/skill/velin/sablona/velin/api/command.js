import { guard, updateQueue, fire, body } from "./_lib.js";

const TYPY = new Set(["zprava", "nova", "presun"]);
const str = (v, n) => String(v || "").trim().slice(0, n);

// POST = nový pokyn do fronty Dispečera (stejný formát jako dosud) + okamžité spuštění Dispečera.
// DELETE = zrušení pokynu, který ještě nebyl doručen.
export default guard(async (req, res) => {
  const b = body(req);
  if (req.method === "DELETE") {
    const q = await updateQueue((q) => {
      const at = b.at || req.query.at;
      const i = q.commands.findIndex((c) => c.at === at);
      if (i < 0) return false;
      q.commands.splice(i, 1);
    }, "velín: zrušen pokyn");
    return res.status(200).json({ queue: q });
  }
  if (req.method !== "POST") return res.status(405).end();

  if (!TYPY.has(b.typ)) return res.status(400).json({ error: "neznámý typ pokynu" });
  const cmd = { typ: b.typ, text: str(b.text, 20000), at: new Date().toISOString(), od: "velin" };
  if (b.typ === "nova") Object.assign(cmd, { nazev: str(b.nazev, 120) || cmd.text.slice(0, 40), repo: str(b.repo, 120) });
  else cmd.session = str(b.session, 80);
  if (b.typ !== "presun" && !cmd.text) return res.status(400).json({ error: "prázdný pokyn" });
  if (b.typ !== "nova" && !/^session_\w+$/.test(cmd.session)) return res.status(400).json({ error: "chybí session" });

  const q = await updateQueue((q) => { q.commands.push(cmd); }, "velín: pokyn");
  const f = await fire(`Nový pokyn z dashboardu Velín (${cmd.typ}) – je v most/prikazy.json. Doruč ho hned.`);
  res.status(200).json({ queue: q, fired: f.ok, fireError: f.error });
});
