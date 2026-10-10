// Clica em (x,y) na aba atual do Chromium do Kling (CDP 9333), espera e tira screenshot.
import { chromium } from '/home/nmaldaner/projetos/inemaccbot/node_modules/playwright/index.mjs';
const [, , x, y, shot, wait = '8000'] = process.argv;
const browser = await chromium.connectOverCDP('http://127.0.0.1:9333');
const pages = browser.contexts()[0].pages();
const page = pages[pages.length - 1];
await page.mouse.click(Number(x), Number(y));
await page.waitForTimeout(Number(wait));
await page.screenshot({ path: shot });
console.log('clicked', x, y, page.url());
process.exit(0);
