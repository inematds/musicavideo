// Screenshot da aba atual do Chromium do Kling (CDP 9333), sem navegar.
import { chromium } from '/home/nmaldaner/projetos/inemaccbot/node_modules/playwright/index.mjs';
const [, , shot] = process.argv;
const browser = await chromium.connectOverCDP('http://127.0.0.1:9333');
const pages = browser.contexts()[0].pages();
const page = pages[pages.length - 1];
await page.screenshot({ path: shot });
console.log(pages.length, page.url());
process.exit(0);
