import { guard, fire } from "./_lib.js";

// Tlačítko „Obnovit teď": spustí Dispečera hned (doručí frontu, obnoví stav i přehled na Drive).
export default guard(async (req, res) => {
  if (req.method !== "POST") return res.status(405).end();
  const f = await fire("Obnovit teď – tlačítko v dashboardu Velín.");
  res.status(f.ok ? 200 : 502).json(f);
});
