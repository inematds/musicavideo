// Submete Lip Sync no kling.ai para cada nn: ls2/v<nn>.mp4 + ls2/a<nn>.mp3. Confere o custo esperado antes de clicar.
// Uso: node kling_lote.mjs <dir> <nn:custo> [<nn:custo> ...]
import { chromium } from '/home/nmaldaner/projetos/inemaccbot/node_modules/playwright/index.mjs';
import { appendFileSync } from 'node:fs';
const [, , dir, ...itens] = process.argv;
const browser = await chromium.connectOverCDP('http://127.0.0.1:9333');
const ctx = browser.contexts()[0];
const page = ctx.pages()[ctx.pages().length - 1];
const log = (m) => { console.log(m); appendFileSync(`${dir}/lote.log`, new Date().toISOString() + ' ' + m + '\n'); };
for (const it of itens) {
  const [nn, custo] = it.split(':');
  await page.goto('https://kling.ai/app/lip-sync/new', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(8000);
  await page.setInputFiles("input[accept='.mp4,.mov']", `${dir}/v${nn}.mp4`);
  await page.waitForTimeout(30000);
  await page.setInputFiles("input[accept='.wav,.aac,.ogg,.flac,.mp3,.m4a']", `${dir}/a${nn}.mp3`);
  await page.waitForTimeout(15000);
  const txt = await page.evaluate(() => document.body.innerText);
  if (!txt.includes(`a${nn}.mp3`)) { log(`${nn} FALHA: audio nao apareceu`); await page.screenshot({ path: `${dir}/erro${nn}.png` }); continue; }
  const btn = await page.evaluate(() => {
    const b = [...document.querySelectorAll('button,div')].filter(e => /^\s*\d+\s*Generate\s*$/.test(e.innerText || '')).pop();
    if (!b) return null; const r = b.getBoundingClientRect(); return { t: b.innerText.trim(), x: r.x + r.width / 2, y: r.y + r.height / 2 };
  });
  if (!btn || !btn.t.startsWith(custo)) { log(`${nn} FALHA: botao ${JSON.stringify(btn)} esperado ${custo}`); await page.screenshot({ path: `${dir}/erro${nn}.png` }); continue; }
  await page.mouse.click(btn.x, btn.y);
  await page.waitForTimeout(5000);
  const prox = await page.evaluate(() => {
    const b = [...document.querySelectorAll('button')].find(e => e.innerText.trim() === 'Proceed');
    if (!b) return null; const r = b.getBoundingClientRect(); return { x: r.x + r.width / 2, y: r.y + r.height / 2 };
  });
  if (prox) { await page.mouse.click(prox.x, prox.y); await page.waitForTimeout(5000); }
  const ok = (await page.evaluate(() => document.body.innerText)).match(/Task submitted|queue|Queueing/);
  await page.screenshot({ path: `${dir}/sub${nn}.png` });
  log(`${nn} ${ok ? 'enviado' : 'SEM CONFIRMACAO'} custo=${btn.t} proceed=${!!prox}`);
}
process.exit(0);
