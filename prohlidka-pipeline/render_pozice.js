#!/usr/bin/env node
// Vyrenderuje pohled z 3D prohlídky přesně z místa každé fotky v tour.json.
// Výsledek je podklad pro AI fotku (Nano Banana 2 / img2img), která pak v prohlídce
// sedí na 3D pohled. Nejde o Blender: je to váš webový engine puštěný v Chromiu
// bez okna (Playwright). Na Macu jede přes GPU (Metal), snímek trvá pár sekund.
//
// Použití (prohlídka musí běžet na lokálním serveru, např. `python3 -m http.server 8766` ve složce prohlídky):
//   node render_pozice.js --url http://localhost:8766/index.html --out ./rendery [--only foto-01,foto-02] [--w 1200]
//
// Skript si tour.json při načtení upraví (bez fotek, značek a hotspotů), aby v renderu nebyly kroužky ani UI.
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const arg = (k, d) => { const i = process.argv.indexOf('--' + k); return i > 0 ? process.argv[i + 1] : d; };
const url = arg('url'); const out = arg('out', './rendery'); const only = arg('only') ? arg('only').split(',') : null;
const W = Number(arg('w', 1200));
if (!url) { console.error('Chybí --url'); process.exit(1); }
fs.mkdirSync(out, { recursive: true });

(async () => {
  const b = await chromium.launch(process.platform === 'linux' ? { args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] } : {});
  let tour = null;
  const ctx = await b.newContext({ viewport: { width: W, height: Math.round(W / 1.5) } });
  await ctx.route('**/tours/demo/tour.json', async (route) => {
    const r = await route.fetch(); tour = await r.json();
    const clean = { ...tour, photos: [], hotspots: [], waypoints: [] };
    if (clean.listing) { clean.listing = { ...clean.listing }; delete clean.listing.hero; }
    await route.fulfill({ response: r, json: clean });
  });
  const p = await ctx.newPage();
  p.on('pageerror', (e) => console.error('chyba stránky:', e.message));
  await p.goto(url + (url.includes('?') ? '&' : '?') + 'debug=1');
  await p.waitForFunction(() => window.__tour && window.__tourDebug, null, { timeout: 120000 });
  await p.evaluate(() => window.__tour.ready);
  await p.waitForTimeout(3000);
  await p.addStyleTag({ content: 'body *{visibility:hidden!important} canvas{visibility:visible!important}' });
  await p.evaluate(() => { const cs = [...document.querySelectorAll('canvas')]; const big = cs.sort((a, c) => c.width * c.height - a.width * a.height)[0]; cs.forEach((c) => { if (c !== big) c.style.display = 'none'; }); });
  for (const ph of tour.photos) {
    if (only && !only.includes(ph.id)) continue;
    const ok = await p.evaluate((ph) => window.__tour.setPose({ position: ph.position, yaw: ph.yaw, pitch: ph.pitch ?? 0, hfov: ph.hfov, frameAspect: ph.aspect ?? 1.5 }), ph);
    await p.waitForTimeout(process.platform === 'linux' ? 3500 : 1200);
    const f = path.join(out, `${ph.id}.png`);
    await p.screenshot({ path: f, timeout: 120000 });
    console.log(ph.id, ok ? 'ok' : 'pozici nešlo nastavit', '→', f);
  }
  await b.close();
})();
