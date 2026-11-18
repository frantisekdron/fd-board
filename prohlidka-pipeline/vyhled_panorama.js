#!/usr/bin/env node
// Panorama pro výhled z oken (vyhled.json → cylinder). Postaví jednoduchou scénu okolí
// z katastr.py (sousední budovy z RÚIAN se sedlovou střechou + ortofoto jako zem),
// vyrenderuje ji z oka ve středu domu do N úzkých výsečí a slepí je do válce
// ve stejné orientaci, jakou používá engine (sloupec u ↔ směr (sin(π+2πu), cos(π+2πu)) v plánu).
//
//   node vyhled_panorama.js --site podklady/site.json --orto podklady/orto.jpg --out vyhled/vyhled-valec.jpg \
//        --stred 12.6 9.0 --X0 7 --Z0 14 [--R 45 --dole -0.1 --nahore 25 --oko 2.5 --vyseci 64 --sirka 8192]
//
// Závislosti: npm i playwright three
const { chromium } = require('playwright');
const fs = require('fs');

const argv = process.argv;
const arg = (k, d) => { const i = argv.indexOf('--' + k); return i > 0 ? argv[i + 1] : d; };
const site = JSON.parse(fs.readFileSync(arg('site'), 'utf8'));
const orto = fs.readFileSync(arg('orto'));
const i = argv.indexOf('--stred'); const cxE = Number(argv[i + 1]), czE = Number(argv[i + 2]);
const cfg = { cxE, czE, X0: Number(arg('X0')), Z0: Number(arg('Z0')), R: Number(arg('R', 45)), bottom: Number(arg('dole', -0.1)),
  top: Number(arg('nahore', 25)), eye: Number(arg('oko', 2.5)), N: Number(arg('vyseci', 64)), W: Number(arg('sirka', 8192)) };
const three = fs.readFileSync(require('path').join(require('path').dirname(require.resolve('three')), 'three.module.js'));

const PAGE = `<!doctype html><html><body style="margin:0"><canvas id="c"></canvas>
<script type="importmap">{"imports":{"three":"http://fdp.local/three.js"}}</script>
<script type="module">
import * as THREE from 'three';
const site = await (await fetch('http://fdp.local/site.json')).json();
const cfg = await (await fetch('http://fdp.local/cfg.json')).json();
const c = Math.cos(site.angle), s = Math.sin(site.angle);
const sliceW = Math.round(cfg.W / cfg.N), H = Math.round(cfg.W * (cfg.top - cfg.bottom) / (2 * Math.PI * cfg.R));
const renderer = new THREE.WebGLRenderer({ canvas: document.getElementById('c'), antialias: true, preserveDrawingBuffer: true });
renderer.setSize(sliceW, H, false); renderer.outputColorSpace = THREE.SRGBColorSpace;
const scene = new THREE.Scene(); const sky = new THREE.Color('#cbd9e3'); scene.background = sky; scene.fog = new THREE.Fog(sky, 120, 420);
scene.add(new THREE.HemisphereLight('#e9f0f6', '#a39d86', 1.4), new THREE.AmbientLight('#fff', 0.4));
const sun = new THREE.DirectionalLight('#fff1dc', 2.2); sun.position.set(-30, 45, 25); scene.add(sun);
const tex = await new THREE.TextureLoader().loadAsync('http://fdp.local/orto.jpg'); tex.colorSpace = THREE.SRGBColorSpace;
const R = site.ortho.R, g = new THREE.Mesh(new THREE.PlaneGeometry(2 * R, 2 * R).rotateX(-Math.PI / 2), new THREE.MeshStandardMaterial({ map: tex, roughness: 1 }));
g.position.set(site.ortho.cx, 0, -site.ortho.cy); scene.add(g);
const far = new THREE.Mesh(new THREE.PlaneGeometry(1200, 1200).rotateX(-Math.PI / 2), new THREE.MeshStandardMaterial({ color: '#8d9567' }));
far.position.set(site.ortho.cx, -0.03, -site.ortho.cy); scene.add(far);
const roofs = ['#8d4b3a', '#6c4a3e', '#7b3f33', '#5f5a56', '#946049'];
function obb(pts) { let best = null; for (let i = 0; i < pts.length - 1; i++) { const a = Math.atan2(pts[i + 1][1] - pts[i][1], pts[i + 1][0] - pts[i][0]), cc = Math.cos(a), ss = Math.sin(a);
  let x0 = 1e9, x1 = -1e9, y0 = 1e9, y1 = -1e9; pts.forEach(([x, y]) => { const px = x * cc + y * ss, py = -x * ss + y * cc; x0 = Math.min(x0, px); x1 = Math.max(x1, px); y0 = Math.min(y0, py); y1 = Math.max(y1, py); });
  const ar = (x1 - x0) * (y1 - y0); if (!best || ar < best.ar) best = { ar, a, x0, x1, y0, y1 }; } return best; }
site.neighbors.forEach((nb, k) => {
  const pts = nb.r, h = nb.fl >= 2 ? 5.3 : 3.0;
  const geo = new THREE.ExtrudeGeometry(new THREE.Shape(pts.map(([e, n]) => new THREE.Vector2(e, n))), { depth: h, bevelEnabled: false }); geo.rotateX(-Math.PI / 2);
  scene.add(new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ color: '#e7dccb' })));
  const b = obb(pts), ov = 0.45, L0 = b.x0 - ov, L1 = b.x1 + ov, D0 = b.y0 - ov, D1 = b.y1 + ov, along = (L1 - L0) >= (D1 - D0);
  const half = along ? (D1 - D0) / 2 : (L1 - L0) / 2, rise = Math.min(half * Math.tan(38 * Math.PI / 180), 3.6), cc = Math.cos(b.a), ss = Math.sin(b.a);
  const P = (px, py, y) => new THREE.Vector3(px * cc - py * ss, y, -(px * ss + py * cc)); let v;
  if (along) { const m = (D0 + D1) / 2; const q = [P(L0, D0, h - .3), P(L1, D0, h - .3), P(L1, m, h + rise), P(L0, m, h + rise), P(L0, D1, h - .3), P(L1, D1, h - .3)];
    v = [q[0], q[1], q[2], q[0], q[2], q[3], q[3], q[2], q[5], q[3], q[5], q[4], q[0], q[3], q[4], q[1], q[5], q[2]]; }
  else { const m = (L0 + L1) / 2; const q = [P(L0, D0, h - .3), P(m, D0, h + rise), P(m, D1, h + rise), P(L0, D1, h - .3), P(L1, D0, h - .3), P(L1, D1, h - .3)];
    v = [q[0], q[1], q[2], q[0], q[2], q[3], q[1], q[4], q[5], q[1], q[5], q[2], q[0], q[4], q[1], q[3], q[2], q[5]]; }
  const rg = new THREE.BufferGeometry().setFromPoints(v); rg.computeVertexNormals();
  scene.add(new THREE.Mesh(rg, new THREE.MeshStandardMaterial({ color: roofs[k % roofs.length], side: THREE.DoubleSide })));
});
// engine plan (x, z) → svět (e, n): u = x - X0, v = Z0 - z, e = u c - v s, n = u s + v c; three: (e, -n)
const W3 = (x, z) => { const u = x - cfg.X0, v = cfg.Z0 - z; return [u * c - v * s, -(u * s + v * c)]; };
const out = document.createElement('canvas'); out.width = sliceW * cfg.N; out.height = H; const ox = out.getContext('2d');
const cam = new THREE.PerspectiveCamera(); const [ex, ez] = W3(cfg.cxE, cfg.czE);
for (let k = 0; k < cfg.N; k++) {
  const th = Math.PI + 2 * Math.PI * (k + 0.5) / cfg.N; const [tx, tz] = W3(cfg.cxE + Math.sin(th), cfg.czE + Math.cos(th));
  cam.position.set(ex, cfg.eye, ez); cam.lookAt(tx, cfg.eye, tz);
  const near = 0.5, hw = Math.tan(Math.PI / cfg.N) * near;
  cam.projectionMatrix.makePerspective(-hw, hw, (cfg.top - cfg.eye) / cfg.R * near, (cfg.bottom - cfg.eye) / cfg.R * near, near, 1500);
  cam.projectionMatrixInverse.copy(cam.projectionMatrix).invert(); cam.updateMatrixWorld();
  renderer.render(scene, cam);
  ox.save(); ox.translate((k + 1) * sliceW, 0); ox.scale(-1, 1); ox.drawImage(renderer.domElement, 0, 0); ox.restore();  // zrcadlit výseč
}
window.__panorama = out.toDataURL('image/jpeg', 0.86);
</script></body></html>`;

(async () => {
  const b = await chromium.launch(process.platform === 'linux' ? { args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] } : {});
  const p = await b.newPage();
  p.on('pageerror', (e) => console.error('chyba stránky:', e.message));
  await p.route('http://fdp.local/**', (route) => {
    const u = route.request().url();
    if (u.endsWith('/three.js')) return route.fulfill({ body: three, contentType: 'text/javascript' });
    if (u.endsWith('/site.json')) return route.fulfill({ json: site });
    if (u.endsWith('/cfg.json')) return route.fulfill({ json: cfg });
    if (u.endsWith('/orto.jpg')) return route.fulfill({ body: orto, contentType: 'image/jpeg' });
    return route.fulfill({ body: PAGE, contentType: 'text/html' });
  });
  await p.goto('http://fdp.local/');
  await p.waitForFunction(() => window.__panorama, null, { timeout: 600000 });
  const data = await p.evaluate(() => window.__panorama);
  fs.writeFileSync(arg('out'), Buffer.from(data.split(',')[1], 'base64'));
  console.log('Hotovo:', arg('out'));
  console.log(JSON.stringify({ cylinder: { url: 'vyhled-valec.jpg', center: [cfg.cxE, cfg.czE], radius: cfg.R, bottom: cfg.bottom, top: cfg.top, sectors: [[0, 360]] } }));
  await b.close();
})();
