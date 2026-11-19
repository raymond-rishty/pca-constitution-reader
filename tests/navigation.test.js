const assert = require('node:assert/strict');
const { test } = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const html = fs.readFileSync(path.join(__dirname, '../index.html'), 'utf8');
const historyCode = html.slice(html.indexOf('let visit=null'), html.indexOf('function displayVisit('));
const matchCode = html.slice(html.indexOf('function passageRoute('), html.indexOf('function renderMatchNav('));

// Exercise the reader's transitions against the browser's push/replace/traverse contract.
function reader() {
  const entries = [null];
  let cursor = 0;
  const history = {
    replaceState(state) { entries[cursor] = structuredClone(state); },
    pushState(state) { entries.splice(++cursor, Infinity, structuredClone(state)); },
    back() { traverse(-1); },
  };
  const context = vm.createContext({
    history, crypto: require('node:crypto').webcrypto,
    location: { hash: '#bco/12', pathname: '/', search: '' },
    document: {
      activeElement: { id: '', dataset: {} },
      getElementById(id) { return id === 'palInput' ? { value: 'ordination' } : { scrollTop: 90, querySelector: () => null }; },
    },
    window: { scrollY: 320 }, COMPONENTS: { bco: { abbr: 'BCO' } },
    current: 'bco', cur: {}, view: 'read',
  });
  const run = code => vm.runInContext(code, context);
  function traverse(offset) {
    cursor += offset;
    assert.ok(cursor >= 0 && cursor < entries.length);
    context.destination = structuredClone(entries[cursor]);
    run('restoreVisit(destination)');
  }
  run(historyCode + matchCode + `
    const palBooks=new Set(['bco']);
    let palSel=0, drawerRef=null, dTab='cit', dFilter='all', dSort='desc', dCommSel=0, dFnSel=null;
    const palResults=['12-1','14-2','17-3'].map(ref=>({book:'bco',ref,open:{ch:ref.split('-')[0]}}));
    function pagedRoute(book,ref){ return {ch:ref.split('-')[0]}; }
    function displayVisit(){
      drawerRef=visit.drawer?.ref;
      window.scrollY=visit.y||0;
    }
    restoreVisit(null);
  `);
  return { run, entries, traverse };
}

test('a chapter jump preserves the departing position and branching replaces the forward trail', () => {
  const { run, entries, traverse } = reader();
  assert.equal(run('visit.back'), false);
  run("window.scrollY=380; navigatePage('bco/20'); window.scrollY=150; readerBack()");
  assert.equal(run('visit.route'), 'bco/12');
  assert.equal(run('window.scrollY'), 380);
  traverse(1);
  assert.equal(run('window.scrollY'), 150);
  run("readerBack(); navigatePage('about')");
  assert.deepEqual(entries.map(e => e.route), ['bco/12', 'about']);
});

test('stepping between matches keeps results one Back away and Forward reopens the last match', () => {
  const { run, entries, traverse } = reader();
  run("openPanel('search'); palGo(1); palGo(2)");
  assert.equal(entries.length, 3);
  assert.equal(run('visit.route'), 'bco/17-3');
  run('readerBack()');
  assert.equal(run('visit.panel'), 'search');
  assert.deepEqual(JSON.parse(run('JSON.stringify(visit.search)')), {
    query: 'ordination', books: ['bco'], index: 2, top: 90,
  });
  traverse(1);
  assert.equal(run('drawerRef'), '17-3');
  run('dismissPanel()');
  assert.equal(run('visit.panel'), null);
  run('readerBack(); readerBack()');
  assert.equal(run('visit.route'), 'bco/12');
});

test('matches within a provision retain their source and destination tab', () => {
  const { run } = reader();
  run(`Object.assign(palResults[0], {packKind:'notes', noteIndex:2});
    Object.assign(palResults[1], {packKind:'commentary', packLabel:'Hodge', commentarySectionId:'section-4'});
    Object.assign(palResults[2], {packKind:'footnotes'});
    openPanel('search'); palGo(0);`);
  assert.equal(run('visit.drawer.tab'), 'notes');
  assert.equal(run('visit.drawer.noteIndex'), 2);
  run('palGo(1)');
  assert.equal(run('visit.drawer.tab'), 'comm');
  assert.equal(run('visit.drawer.packLabel'), 'Hodge');
  assert.equal(run('visit.drawer.commentarySectionId'), 'section-4');
  run('palGo(2)');
  assert.equal(run('visit.drawer.tab'), 'fn');
});
