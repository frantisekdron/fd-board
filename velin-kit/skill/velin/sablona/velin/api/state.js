import { guard, readJson, OWNER } from "./_lib.js";

// Jeden zdroj pravdy: most/velin_state.json (zapisuje Dispečer). Starší most/prehled.json jako záloha.
export default guard(async (req, res) => {
  const [v, q] = await Promise.all([readJson("most/velin_state.json"), readJson("most/prikazy.json")]);
  const state = v.json || (await readJson("most/prehled.json")).json || { sessions: [] };
  res.status(200).json({ state, queue: q.json || { commands: [] }, spoust: Boolean(process.env.GITHUB_TOKEN), owner: OWNER });
});
