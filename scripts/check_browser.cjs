// Pixel-level regression for the Skia/CoreText path used by Electron apps.
// Usage: node scripts/check_browser.cjs FONT OUTPUT.png [--local]
const assert = require('node:assert/strict');
const fs = require('node:fs');
const http = require('node:http');
const {chromium} = require('playwright');

async function main() {
  assert(process.argv.length === 4 || process.argv[4] === '--local', 'Expected font path and output PNG');
  const useLocal = process.argv[4] === '--local';
  const data = useLocal ? null : fs.readFileSync(process.argv[2]);
  const server = http.createServer((req, res) => {
    if (req.url === '/font') {
      res.setHeader('Content-Type', 'font/ttf');
      res.end(data);
    } else {
      res.setHeader('Content-Type', 'text/html; charset=utf-8');
      res.end('<!doctype html><canvas width="800" height="600"></canvas>');
    }
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  let browser;
  try {
    browser = await chromium.launch({headless: true});
    const page = await browser.newPage();
    await page.goto(`http://127.0.0.1:${server.address().port}`);
    const observations = await page.evaluate(async (useLocal) => {
      const face = new FontFace('RenderingRegression', useLocal
        ? 'local("Fluent3DCommunity03-Regular")' : 'url(/font)');
      document.fonts.add(await face.load());
      const cases = ['😀', '🕵🏽‍♀️', '😍', '🥲', '👩🏻‍💻', '🏳️‍🌈', '1️⃣', '❤️', '🌚', '🫪'];
      const results = [];
      const output = document.querySelector('canvas').getContext('2d');
      output.fillStyle = '#fff';
      output.fillRect(0, 0, 800, 600);
      for (const size of [16, 32, 64, 128, 256]) {
        for (const text of cases) {
          const canvas = document.createElement('canvas');
          canvas.width = canvas.height = 512;
          const ctx = canvas.getContext('2d');
          ctx.font = `${size}px RenderingRegression`;
          ctx.fillText(text, 32, 320);
          const rgba = ctx.getImageData(0, 0, 512, 512).data;
          let painted = 0, coloured = 0;
          for (let i = 0; i < rgba.length; i += 4) {
            if (rgba[i + 3] > 10) {
              painted++;
              if (Math.max(rgba[i], rgba[i + 1], rgba[i + 2])
                  - Math.min(rgba[i], rgba[i + 1], rgba[i + 2]) > 20) coloured++;
            }
          }
          const metrics = ctx.measureText(text);
          results.push({text, size, painted, coloured,
                        ascent: metrics.actualBoundingBoxAscent,
                        descent: metrics.actualBoundingBoxDescent});
          if (size === 64) {
            const index = cases.indexOf(text);
            output.font = '64px RenderingRegression';
            output.fillText(text, 24 + (index % 8) * 92, 110 + Math.floor(index / 8) * 110);
          }
        }
      }
      return results;
    }, useLocal);
    for (const result of observations) {
      assert(result.ascent + result.descent > 0, `Empty glyph bounds: ${JSON.stringify(result)}`);
      assert(result.coloured > result.size, `No colour image: ${JSON.stringify(result)}`);
    }
    await page.locator('canvas').screenshot({path: process.argv[3]});
    console.log(`Chromium: ${observations.length} colour-pixel checks passed`);
  } finally {
    if (browser) await browser.close();
    await new Promise(resolve => server.close(resolve));
  }
}

main().catch(error => { console.error(error); process.exitCode = 1; });
