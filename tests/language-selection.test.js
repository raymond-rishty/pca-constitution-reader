const assert = require('node:assert/strict');
const { test } = require('node:test');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const html = fs.readFileSync(path.join(__dirname, '../index.html'), 'utf8');
const selection = html.slice(html.indexOf('function bcoTranslations()'), html.indexOf('const LOREM'));
const switchLanguage = html.slice(html.indexOf('function setBcoLanguage('), html.indexOf('const languageSelect='));

function reader({ languages = ['en-US'], saved, blockedStorage = false } = {}) {
  const stored = new Map(saved ? [['pcacon.bcoLanguage', saved]] : []);
  const context = vm.createContext({
    window: {}, navigator: { languages },
    localStorage: {
      getItem(key) { if (blockedStorage) throw Error('Storage blocked'); return stored.get(key); },
      setItem(key, value) { if (blockedStorage) throw Error('Storage blocked'); stored.set(key, value); },
      removeItem(key) { if (blockedStorage) throw Error('Storage blocked'); stored.delete(key); },
    },
  });
  for (const file of ['content/bco.js', 'content/translations/bco-2025-es.js', 'content/translations/bco-2026-ko.js']) {
    vm.runInContext(fs.readFileSync(path.join(__dirname, '..', file), 'utf8'), context);
  }
  vm.runInContext(selection, context);
  return { context, stored, run: code => vm.runInContext(code, context) };
}

test('browser default honors language priority, regional tags, and English fallback', () => {
  for (const [languages, expected] of [
    [['es-MX', 'en'], 'es'], [['ko-KR'], 'ko'], [['en-US', 'es'], 'en'],
    [['fr', 'ko'], 'ko'], [['fr'], 'en'], [[], 'en'],
  ]) {
    assert.equal(reader({ languages }).run('BCO_EDITION.lang'), expected);
  }
});

test('saved explicit choice overrides browser locale, including explicit English', () => {
  for (const saved of ['en', 'es', 'ko']) {
    const r = reader({ languages: ['ko-KR'], saved });
    assert.equal(r.run('BCO_EDITION.lang'), saved);
  }
  assert.equal(reader({ saved: 'unknown' }).run('BCO_EDITION.lang'), 'en');
});

test('switching refreshes BCO content, metadata, navigation and search; auto clears the override', () => {
  const r = reader({ languages: ['es-MX'], saved: 'en' });
  const componentStart = html.indexOf('function bcoComponent()');
  const componentEnd = html.indexOf('/* WCF chapter titles', componentStart);
  r.run(html.slice(componentStart, componentEnd));
  r.run('const COMPONENTS={}; const SPINE={}; let SEARCH={stale:true}; let renders=0; function applyRoute(){renders++;}');
  r.run(switchLanguage);
  for (const lang of ['es', 'ko', 'en']) {
    r.run(`setBcoLanguage('${lang}')`);
    assert.equal(r.run('BCO_EDITION.lang'), lang);
    assert.equal(r.run('BCO_DATA["24"].title'), r.run('SPINE.bco.find(x=>x.ch==="24").title'));
    assert.equal(r.run('COMPONENTS.bco.name'), r.run('bcoComponent().name'));
    assert.equal(r.run('SEARCH'), null);
    assert.equal(r.stored.get('pcacon.bcoLanguage'), lang);
  }
  r.run("setBcoLanguage('auto')");
  assert.equal(r.stored.has('pcacon.bcoLanguage'), false);
  assert.equal(r.run('BCO_EDITION.lang'), 'es');
  assert.equal(r.run('renders'), 4);
});

test('language choice still works when browser storage is unavailable', () => {
  const r = reader({ blockedStorage: true });
  assert.equal(r.run('BCO_EDITION.lang'), 'en');
  r.run('const COMPONENTS={}; const SPINE={}; let SEARCH=null; function bcoComponent(){return {};} function applyRoute(){}');
  r.run(switchLanguage);
  r.run("setBcoLanguage('ko')");
  assert.equal(r.run('BCO_EDITION.lang'), 'ko');
});
