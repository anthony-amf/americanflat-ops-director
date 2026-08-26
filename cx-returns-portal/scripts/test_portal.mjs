// Browser test for the generated portal. Needs: npm install playwright-core
import { chromium } from 'playwright-core';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const FILE = pathToFileURL(resolve(HERE, '..', 'portal', 'cx-returns-portal.html')).href;
const browser = await chromium.launch(
  process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {});
const page = await browser.newPage();
const errors = [];
page.on('pageerror', e => errors.push('PAGEERROR: ' + e.message));
page.on('console', m => { if (m.type() === 'error') errors.push('CONSOLE: ' + m.text()); });
await page.goto(FILE);

const cases = [
  {
    name: 'Shopify short-ship (the real 22397 case)',
    paste: `Customer Sarah Whitfield, Shopify order #22397, says she is missing
MW0808WH44 x 1 and MW1114WH57 x 2. Tracking 525499496652.
Her email is sarah.whitfield@gmail.com and phone 415-555-0182.`,
    expectCase: 'missing', expectLabel: 'missing units',
  },
  {
    name: 'NJ damaged with RS order',
    paste: `AME*25162 Liam Ohea — Shopify. Frame arrived damaged, glass shattered.
PS1114BK5PK x 1. Replacement placed as 25162RS. Tracking 1Z999AA10123456784.`,
    expectCase: 'damaged', expectLabel: 'damaged on arrival',
  },
  {
    name: 'SC tracking invalid',
    paste: `AMS*24124 — customer cannot track, FedEx says tracking 420100119998 invalid.
South Carolina shipped this one.`,
    expectCase: 'tracking', expectLabel: 'tracking verification',
  },
  {
    name: 'NL return, unknown barcode',
    paste: `Yusen NL Moerdijk received a return by DHL, tracking JJD000090254000063071944,
8 pcs of item 810029117517. They cannot identify it.`,
    expectCase: 'return', expectLabel: 'return disposition',
  },
  {
    name: 'Cancel replacement',
    paste: `Customer found the original package. Please cancel replacement 24074RS at South Carolina.`,
    expectCase: 'cancel', expectLabel: 'cancel replacement',
  },
];

let pass = 0, fail = 0;
for (const c of cases) {
  await page.click('#reset');
  await page.fill('#paste', c.paste);
  await page.waitForTimeout(120);
  await page.fill('#f-sender', 'Nica Jordan');
  await page.waitForTimeout(120);

  const out = await page.evaluate(() => ({
    to: document.getElementById('m-to').textContent,
    cc: document.getElementById('m-cc').textContent,
    subject: document.getElementById('m-subject').textContent,
    body: document.getElementById('m-body').textContent,
    active: [...document.querySelectorAll('.case')].find(b => b.getAttribute('aria-pressed') === 'true')?.textContent,
    readout: document.getElementById('readout').textContent.trim(),
    gaps: document.getElementById('gaps').textContent.trim(),
  }));

  const problems = [];
  const whKnown = out.to !== '\u2014';
  if (whKnown && !out.subject.startsWith('AMF x')) problems.push('subject not in house format: ' + out.subject);
  if (whKnown && !out.cc.includes('NYC_Ops@americanflat.com')) problems.push('NYC_Ops missing from Cc');
  if (!whKnown && !out.gaps.includes('Pick a warehouse')) problems.push('unknown warehouse not flagged');
  if (c.expectCase && !(out.active||'').toLowerCase().includes(c.expectLabel||c.expectCase)) problems.push('classified as: ' + out.active);
  if (out.body.includes('undefined') || out.subject.includes('undefined')) problems.push('undefined leaked into output');
  if (/gmail\.com|415-555/.test(out.body)) problems.push('customer PII leaked into email body');
  

  console.log('\n=== ' + c.name + ' ===');
  console.log('case chip : ' + (out.active || 'NONE'));
  console.log('readout   : ' + out.readout);
  console.log('To        : ' + out.to);
  console.log('Cc        : ' + out.cc);
  console.log('Subject   : ' + out.subject);
  console.log('Gaps      : ' + (out.gaps || '(none)'));
  console.log('--- body ---\n' + out.body);
  if (problems.length) { fail++; console.log('!! ' + problems.join('\n!! ')); }
  else { pass++; console.log('   [ok]'); }
}

// A shortage on a PARTIALLY FULFILLED order is not a short-ship: the balance was
// never released. Routing it to the missing-units investigation sends the warehouse
// hunting a discrepancy that does not exist. Mirrors the 23290 screenshot walkthrough.
{
  await page.click('#reset');
  await page.fill('#paste', `Shopify order #23290 from Fontana, Partially fulfilled: Fulfilled (2), Unfulfilled (6).
Customer Sarah Whitfield ordered 8 x MW1114WH57 and only received 2. Tracking 525499496652.
Zendesk #48213 - she needs the rest by Saturday 8/29.`);
  await page.waitForTimeout(120);
  await page.fill('#f-sender', 'Nica Jordan');
  await page.waitForTimeout(150);

  const out = await page.evaluate(() => ({
    active: [...document.querySelectorAll('.case')].find(b => b.getAttribute('aria-pressed') === 'true')?.textContent || '',
    subject: document.getElementById('m-subject').textContent,
    body: document.getElementById('m-body').textContent,
  }));

  console.log('\n=== Partially fulfilled -> balance chase ===');
  console.log('case chip : ' + out.active.split('.')[0]);
  console.log('Subject   : ' + out.subject);
  console.log('--- body ---\n' + out.body);

  const problems = [];
  if (!/Unshipped balance/i.test(out.active)) problems.push('did not classify as an unshipped balance: ' + out.active);
  if (!/Unshipped Balance/.test(out.subject)) problems.push('wrong subject: ' + out.subject);
  if (/not received in full|physically shipped for each SKU/.test(out.body)) problems.push('sent the short-ship investigation instead');
  if (/48213/.test(out.body) || /48213/.test(out.subject)) problems.push('Zendesk ticket number leaked to the warehouse');
  if (problems.length) { fail++; console.log('!! ' + problems.join('\n!! ')); }
  else { pass++; console.log('   [ok]'); }
}

// A reship ships either as a sealed master carton or as loose units. The wrong
// instruction is followed literally by the warehouse, so both must hold.
{
  await page.click('#reset');
  await page.fill('#paste', `Fontana Shopify order #22562. Customer got one broken frame out of a set order.
Replacement 22562RS placed. Needs MW1114WH57 x 1 only.`);
  await page.waitForTimeout(120);
  await page.fill('#f-sender', 'Nica Jordan');
  await page.waitForTimeout(120);
  await page.evaluate(() => [...document.querySelectorAll('.case')].find(c => c.textContent.includes('Reship')).click());
  await page.waitForTimeout(120);

  const read = () => page.evaluate(() => ({
    body: document.getElementById('m-body').textContent,
    gaps: document.getElementById('gaps').textContent.trim(),
  }));

  console.log('\n=== Reship pick mode ===');
  await page.selectOption('#f-packMode', 'carton');
  await page.waitForTimeout(150);
  const carton = await read();
  await page.selectOption('#f-packMode', 'units');
  await page.waitForTimeout(150);
  const units = await read();
  await page.fill('#f-skus', '');
  await page.waitForTimeout(150);
  const bare = await read();

  const problems = [];
  if (!/must ship as one full master carton/.test(carton.body)) problems.push('carton mode lost its instruction');
  if (/piece-pick/.test(units.body)) problems.push('loose pick still says do-not-piece-pick');
  if (!/loose-unit pick/.test(units.body)) problems.push('loose pick missing its instruction');
  if (!/MW1114WH57 x 1/.test(units.body)) problems.push('loose pick does not list the units');
  if (!/SKU and quantity/.test(bare.gaps)) problems.push('loose pick with no SKUs was not blocked');

  if (problems.length) { fail++; console.log('!! ' + problems.join('\n!! ')); }
  else { pass++; console.log('   [ok] carton and loose-unit variants both correct'); }
}

console.log('\n\n==== ' + pass + ' passed, ' + fail + ' failed ====');
if (errors.length) console.log('JS ERRORS:\n' + errors.join('\n'));
else console.log('no JS errors');
await browser.close();
