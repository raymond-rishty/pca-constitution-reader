const assert = require('node:assert/strict');
const { test } = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const engine = require('../search-engine.js');

test('reader indexes corrected BCO topics alongside installed commentary', () => {
  const root = path.join(__dirname, '..');
  const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
  const context = vm.createContext({
    window: { BOOK_PACKS: [], BCO_COMMENTARIES: [{ corpus: 'bco', label: 'Example', entries: { '29-2': 'Distinctive commentary text' } }] },
    COMPONENTS: { bco: { abbr: 'BCO' } }, NOTES: {}, PcaConstitutionSearch: engine,
    document: { createElement: () => ({ set innerHTML(value) { this.textContent = value.replace(/<[^>]*>/g, ''); } }) },
  });
  for (const file of ['content/bco.js', 'content/bco-index.js']) {
    vm.runInContext(fs.readFileSync(path.join(root, file), 'utf8'), context);
  }
  context.BCO_DATA = context.window.BCO;
  vm.runInContext(html.slice(html.indexOf('function _plain('), html.indexOf('const BOOK_LABEL=')), context);
  const records = vm.runInContext('buildSearch()', context);
  const correct = records.find(r => r.book === 'bco' && r.ref === '29-2' && !r.packKind);
  const old = records.find(r => r.book === 'bco' && r.ref === '20-2' && !r.packKind);
  assert.ok(correct.topics.includes('Personal Offenses Defined'));
  assert.ok(!old.topics.includes('Personal Offenses Defined'));
  assert.ok(engine.search(records, '"personal offenses defined"').results.some(r => r.record.ref === '29-2'));
  assert.ok(engine.search(records, '"distinctive commentary text"').results.some(r => r.record.packLabel === 'Example'));
});
