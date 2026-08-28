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
  await page.waitForTimeout(150);
  // Shipment-creating cases now open on the replacement row; these checks are
  // about the email, so switch to it.
  if (!(await page.isDisabled('#tab-email'))) {
    await page.click('#tab-email');
    await page.waitForTimeout(120);
  }
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
  await page.evaluate(() => [...document.querySelectorAll('.case')].find(c => c.textContent.includes('Reship')).click());
  await page.waitForTimeout(150);
  await page.click('#tab-email');          // a reship opens on the replacement row
  await page.waitForTimeout(150);
  await page.fill('#f-sender', 'Nica Jordan');
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

// The Replacements-tab row replaces the email for cases that create a shipment,
// and must stay unavailable for cases that ask the warehouse a question.
// Reproduces order 23280, which already exists in the live sheet.
{
  await page.click('#reset');
  await page.fill('#paste', `Shopify order #23280 from Fontana. Wrong item sent.
Customer Landon Beard needs WB2436LWOODPC x 2 replaced.`);
  await page.waitForTimeout(180);
  await page.evaluate(() => [...document.querySelectorAll('.case')].find(c => c.textContent.includes('Reship')).click());
  await page.waitForTimeout(150);

  console.log('\n=== Replacements sheet row ===');
  const problems = [];
  if (await page.isDisabled('#tab-csv')) problems.push('row tab disabled on a reship');

  // The replacement row is the default for a reship — no click needed to reach it.
  if (!(await page.isVisible('#pane-csv'))) problems.push('row pane is not the default view for a reship');
  if (await page.isVisible('#pane-email')) problems.push('email pane showing by default on a reship');
  const tabs = await page.evaluate(() => [...document.querySelectorAll('#tabs button')].map(b => b.textContent));
  if (tabs[0] !== 'Replacement row') problems.push('replacement row is not the first tab: ' + JSON.stringify(tabs));

  await page.click('#tab-csv');
  await page.waitForTimeout(150);
  if (!(await page.isDisabled('#copy-row'))) problems.push('copy enabled before the row was complete');
  if (await page.isVisible('#pane-email')) problems.push('email pane still visible in row mode');
  if (!(await page.isVisible('#pane-csv'))) problems.push('row pane not visible in row mode');

  for (const [sel, val] of [['#f-shipName', 'Landon Beard'], ['#f-address1', '17704 Knox Farm Rd'],
       ['#f-city', 'Edmond'], ['#f-stateRegion', 'OK'], ['#f-postal', '73012'],
       ['#f-phone', '501-281-0258'], ['#f-email', 'landon.k.beard@gmail.com']]) {
    await page.fill(sel, val);
    await page.waitForTimeout(60);
  }
  await page.selectOption('#f-channel', 'Shopify');
  await page.selectOption('#f-reason', 'Wrong Item Sent');
  await page.waitForTimeout(250);
  if (await page.isDisabled('#copy-row')) problems.push('copy still disabled with a complete row');

  const row = await page.evaluate(() => window.__row && window.__row.text);
  const cells = (row || '').split('\t');

  // The row must stop at Notes (column P). Writing past it would paste blanks
  // over the automation's own columns.
  if (cells.length !== 16) problems.push('expected 16 columns, stopping at Notes; got ' + cells.length);
  if (cells[0] !== '23280') problems.push('col 1 should be the original order #, got ' + cells[0]);
  if (cells[1] !== 'Shopify') problems.push('col 2 should be Channel, got ' + cells[1]);
  if (cells[3] !== 'WB2436LWOODPC') problems.push('col 4 should be SKU, got ' + cells[3]);
  if (cells[4] !== '2') problems.push('col 5 should be Qty, got ' + cells[4]);
  if (cells[10] !== 'OK') problems.push('col 11 should be State, got ' + cells[10]);
  if (cells[12] !== 'US') problems.push('col 13 should default Country to US, got ' + cells[12]);
  if (cells[15] === undefined) problems.push('Notes (col 16) missing');
  // Nothing may be emitted for Q onward — Status, SS Order #, Order Key,
  // Submitted By, Submitted At and Message are all the automation's.
  if (cells.length > 16) problems.push('emitted ' + (cells.length - 16) + ' cell(s) past Notes');

  // A stray tab or newline in any value would shift every later column.
  if (cells.some(c => /[\t\r\n]/.test(c))) problems.push('a value contains a tab or newline');

  // Underscored SKUs are real — LEDGE_BK14_3PK is in the live sheet — and must
  // survive the PASTE PARSER, not just a hand-filled field. An earlier version
  // dropped them silently, losing a line item from the replacement.
  await page.fill('#paste', `Shopify order #23280. Wrong item sent.
Landon Beard needs WB2436LWOODPC x 2 and LEDGE_BK14_3PK x 1 replaced.`);
  await page.waitForTimeout(250);
  const parsed = await page.inputValue('#f-skus');
  if (!/LEDGE_BK14_3PK/.test(parsed)) problems.push('parser dropped the underscored SKU: ' + JSON.stringify(parsed));
  if (!/WB2436LWOODPC/.test(parsed)) problems.push('parser dropped the plain SKU: ' + JSON.stringify(parsed));

  // A multi-SKU replacement is one row per SKU with the order fields repeated
  // (confirmed 2026-08-28), not one row with the items concatenated.
  await page.fill('#f-skus', 'WB2436LWOODPC x 2\nLEDGE_BK14_3PK x 1');
  await page.waitForTimeout(250);
  const multi = await page.evaluate(() => window.__row && window.__row.text);
  const rows2 = (multi || '').split('\n');
  if (rows2.length !== 2) problems.push('2 SKUs should emit 2 rows, got ' + rows2.length);
  else {
    const a = rows2[0].split('\t'), b = rows2[1].split('\t');
    if (a.length !== 16 || b.length !== 16) problems.push('multi-SKU rows are not 16 columns');
    if (a[3] !== 'WB2436LWOODPC' || a[4] !== '2') problems.push('row 1 SKU/Qty wrong: ' + a[3] + '/' + a[4]);
    if (b[3] !== 'LEDGE_BK14_3PK' || b[4] !== '1') problems.push('row 2 SKU/Qty wrong: ' + b[3] + '/' + b[4]);
    // Order-level fields must repeat, or the second row is orphaned.
    for (const [i, name] of [[0, 'Original Order #'], [1, 'Channel'], [5, 'Ship To Name'],
                             [7, 'Street 1'], [11, 'Postal Code'], [15, 'Notes']]) {
      if (a[i] !== b[i]) problems.push(name + ' should repeat on every row: ' + a[i] + ' vs ' + b[i]);
    }
    if (/;/.test(a[3])) problems.push('SKUs were concatenated instead of split across rows');
  }
  await page.fill('#f-skus', 'WB2436LWOODPC x 2');
  await page.waitForTimeout(150);

  // An investigative case cannot be a sheet row.
  await page.evaluate(() => [...document.querySelectorAll('.case')].find(c => c.textContent.includes('Missing units')).click());
  await page.waitForTimeout(200);
  if (!(await page.isDisabled('#tab-csv'))) problems.push('row offered for a missing-units investigation');
  if (!(await page.isVisible('#pane-email'))) problems.push('did not fall back to the email pane');

  if (problems.length) { fail++; console.log('!! ' + problems.join('\n!! ')); }
  else { pass++; console.log('   [ok] leads the tabs, stops at Notes, one row per SKU'); }
}

// Step 3 fills itself from the paste. Two shapes turn up in practice: a Shopify
// address block on separate lines, and a comma run typed into a ticket.
{
  const shapes = [
    ['comma run', `Shopify order #24235 damaged in transit. WB2436PBRASSPC x 1, loose unit.
Sarah Imler, 6126 Three Cedars Lane, Fredericksburg Virginia 22407, United States, +15408483483`,
     { shipName:'Sarah Imler', address1:'6126 Three Cedars Lane', city:'Fredericksburg',
       stateRegion:'VA', postal:'22407', country:'US', channel:'Shopify', reason:'Damaged in Transit' }],
    ['address block', `Order #23280 — wrong item sent, Shopify. WB2436LWOODPC x 2
Landon Beard
17704 Knox Farm Rd
Edmond OK 73012
United States
501-281-0258
landon.k.beard@gmail.com`,
     { shipName:'Landon Beard', address1:'17704 Knox Farm Rd', city:'Edmond', stateRegion:'OK',
       postal:'73012', country:'US', email:'landon.k.beard@gmail.com', channel:'Shopify',
       reason:'Wrong Item Sent' }],
    ['apartment line', `Shopify #22397, frame arrived broken. MW1114WH57 x 1
Sarah Whitfield
1842 Larkin St
Apt 4
San Francisco, CA 94109`,
     { shipName:'Sarah Whitfield', address1:'1842 Larkin St', address2:'Apt 4',
       city:'San Francisco', stateRegion:'CA', postal:'94109' }],
  ];

  console.log('\n=== Step 3 autofill ===');
  const problems = [];
  for (const [label, paste, want] of shapes) {
    await page.click('#reset');
    await page.fill('#paste', paste);
    await page.waitForTimeout(300);
    for (const [field, expected] of Object.entries(want)) {
      const got = await page.evaluate(f => {
        const e = document.getElementById('f-' + f);
        return e ? (e.value ?? '') : '(field not rendered)';
      }, field);
      if (got !== expected) problems.push(label + ': ' + field + ' = ' + JSON.stringify(got) + ', wanted ' + JSON.stringify(expected));
    }
  }

  // A hand edit must survive a re-parse, or corrections get clobbered.
  await page.fill('#f-city', 'Manassas');
  await page.waitForTimeout(120);
  await page.fill('#paste', 'Shopify order #24235. Sarah Imler, 6126 Three Cedars Lane, Fredericksburg Virginia 22407, US');
  await page.waitForTimeout(300);
  const city = await page.evaluate(() => document.getElementById('f-city').value);
  if (city !== 'Manassas') problems.push('a hand-edited field was overwritten by a re-parse: ' + city);

  if (problems.length) { fail++; console.log('!! ' + problems.join('\n!! ')); }
  else { pass++; console.log('   [ok] name, street, city, state, zip, country, phone, email, channel, reason'); }
}

console.log('\n\n==== ' + pass + ' passed, ' + fail + ' failed ====');
if (errors.length) console.log('JS ERRORS:\n' + errors.join('\n'));
else console.log('no JS errors');
await browser.close();
