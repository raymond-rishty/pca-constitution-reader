const assert = require('node:assert/strict');
const { createHash, webcrypto } = require('node:crypto');
const { execFileSync } = require('node:child_process');
const { mkdtempSync, readFileSync, rmSync } = require('node:fs');
const { tmpdir } = require('node:os');
const path = require('node:path');
const { describe, it, after } = require('node:test');
const vm = require('node:vm');
const { parseSnapshot } = require('../android-content-update.js');

const root = path.resolve(__dirname, '..');
const directory = mkdtempSync(path.join(tmpdir(), 'pca-android-content-'));
after(() => rmSync(directory, { recursive: true, force: true }));
execFileSync(process.execPath, ['tools/build_android_content.cjs', directory], { cwd: root });
const baseline = JSON.parse(readFileSync(path.join(directory, 'manifest-v1.json'), 'utf8'));
const original = readFileSync(path.join(directory, 'content-v1.json'), 'utf8');
const updater = readFileSync(path.join(root, 'android-content-update.js'), 'utf8');
const notes = { 'bco|1-1': 'A local draft' };

function revisedContent(verseText = 'An updated verse preview') {
  const data = JSON.parse(original);
  data.content.BCO['1'].sections[0].blocks = [['p', 0, '<b>Revised text</b>']];
  data.content.INLINE_SCRIPTURE.references['john 3:16'] = ['jn.3.16'];
  data.content.INLINE_SCRIPTURE.verses['jn.3.16'] = verseText;
  const snapshot = JSON.stringify(data);
  const manifest = {
    ...baseline,
    timestamp: baseline.timestamp + 1,
    sha256: createHash('sha256').update(snapshot).digest('hex'),
  };
  return { manifest, snapshot };
}

async function launch({ saved = null, fetch, put = () => assert.fail('unexpected cache write') } = {}) {
  const window = { NOTES: { ...notes } };
  let onStart;
  const started = new Promise(resolve => { onStart = resolve; });
  const document = {
    querySelector: () => ({ content: JSON.stringify(baseline) }),
    createElement: () => ({}),
    head: { appendChild(script) { onStart(script.src); } },
  };
  const cache = {
    match: async () => saved && new Response(JSON.stringify(saved)),
    put: async (key, response) => put(await response.json()),
  };
  vm.runInNewContext(updater, {
    window, document, URL, location: { href: 'https://localhost/' },
    caches: { open: async () => cache },
    Response, TextEncoder, crypto: webcrypto, fetch: fetch || (() => Promise.reject(new Error('Offline'))),
    console: { warn() {}, debug() {} },
  });
  assert.equal(await started, 'android-reader.js');
  return window;
}

describe('Android content refresh', () => {
  it('exports and validates the bundled corpus', async () => {
    const content = await parseSnapshot(baseline, original);
    assert.ok(content.BCO['1']);
    assert.ok(Object.keys(content.INLINE_SCRIPTURE.references).length);
    assert.ok(Object.keys(content.CIT['bco-1']).length);
  });

  it('makes a verified update available on the next launch without changing notes', async () => {
    const update = revisedContent();
    let onWrite;
    const written = new Promise(resolve => { onWrite = resolve; });
    const first = await launch({
      fetch: async url => url.endsWith('manifest-v1.json')
        ? new Response(JSON.stringify(update.manifest))
        : new Response(update.snapshot),
      put: onWrite,
    });
    assert.equal(first.BCO, undefined);
    const saved = await written;
    const reopened = await launch({ saved });
    assert.equal(reopened.BCO['1'].sections[0].blocks[0][2], '<b>Revised text</b>');
    assert.equal(reopened.INLINE_SCRIPTURE.references['john 3:16'][0], 'jn.3.16');
    assert.equal(reopened.INLINE_SCRIPTURE.verses['jn.3.16'], 'An updated verse preview');
    assert.deepEqual(reopened.NOTES, notes);
  });

  it('rejects invalid Scripture data even when its checksum matches', async () => {
    const invalid = revisedContent(['Invalid verse']);
    await assert.rejects(parseSnapshot(invalid.manifest, invalid.snapshot), /Invalid Android reader Scripture reference/);
  });

  it('falls back to the bundled assets if cached data is corrupt or predates the APK', async () => {
    const update = revisedContent();
    const corrupt = await launch({ saved: { ...update, snapshot: original } });
    const stale = await launch({
      saved: { ...update, manifest: { ...update.manifest, timestamp: baseline.timestamp - 1 } },
    });
    assert.equal(corrupt.BCO, undefined);
    assert.equal(stale.BCO, undefined);
    await assert.rejects(parseSnapshot(update.manifest, original), /checksum mismatch/);
  });
});
