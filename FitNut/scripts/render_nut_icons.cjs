// Redraws static/nuts/*.png from static/nuts.js. Run only after changing the 3D models.
// Usage: node scripts/render_nut_icons.cjs  (needs Playwright with Chromium)
const { chromium } = require('playwright');
const fs = require('node:fs');
const path = require('node:path');

const statics = path.resolve(__dirname, '..', 'static');
const species = ['pistachio', 'hazelnut', 'acorn', 'walnut', 'pecan', 'ghost', 'almond', 'pebble0', 'pebble1', 'pebble2', 'pebble3', 'pebble4'];

(async () => {
  const browser = await chromium.launch({ headless: true, args: ['--headless=new', '--enable-webgl', '--ignore-gpu-blocklist', '--use-angle=d3d11'],
    ...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE } : {}) });
  const page = await browser.newPage();
  await page.addScriptTag({ path: path.join(statics, 'vendor', 'three.min.js') });
  await page.addScriptTag({ path: path.join(statics, 'nuts.js') });
  fs.mkdirSync(path.join(statics, 'nuts'), { recursive: true });
  for (const name of species) {
    const url = await page.evaluate(which => window.FitNutNuts.renderIcon(which), name);
    fs.writeFileSync(path.join(statics, 'nuts', `${name}.png`), Buffer.from(url.split(',')[1], 'base64'));
  }
  await browser.close();
  console.log(`Wrote ${species.length} icons.`);
})().catch(error => { console.error(error); process.exit(1); });
