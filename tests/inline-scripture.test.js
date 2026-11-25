const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const { test } = require('node:test');
const vm = require('node:vm');

const root = join(__dirname, '..');
const context = vm.createContext({ window: {} });
vm.runInContext(readFileSync(join(root, 'content/inline-scripture.js'), 'utf8'), context);
const html = readFileSync(join(root, 'index.html'), 'utf8');
const patternCode = html.slice(html.indexOf('const inlineScripture='), html.indexOf('function linkScriptureReferences('));
const pattern = vm.runInContext(patternCode + '\nscripturePattern', context);
const { references, verses } = context.window.INLINE_SCRIPTURE;

test('BCO 24-1 links both whole chapters and the cited verse ranges', () => {
  const text = '1 Timothy 3 and Titus 1 (1 Timothy 3:1-7 and Titus 1:6-9)';
  assert.deepEqual(Array.from(text.matchAll(pattern), match => match[0]), [
    '1 Timothy 3', 'Titus 1', '1 Timothy 3:1-7', 'Titus 1:6-9',
  ]);
  assert.deepEqual(Array.from(references['1 timothy 3']), Array.from({ length: 16 }, (_, i) => `1 Timothy 3:${i + 1}`));
  assert.equal(references['titus 1'].length, 16);
  assert.equal(references['1 timothy 3:1-7'].at(-1), '1 Timothy 3:7');
  assert.equal(Array.from('1 Timothy 3 :999'.matchAll(pattern)).length, 0);
});

test('the Preface links Isaiah 9:6-7 to both bundled verses', () => {
  assert.equal(Array.from('(Isaiah 9:6-7)'.matchAll(pattern), match => match[0])[0], 'Isaiah 9:6-7');
  const keys = Array.from(references['isaiah 9:6-7']);
  assert.deepEqual(keys, ['Isaiah 9:6', 'Isaiah 9:7']);
  assert.ok(keys.every(key => verses[key]?.trim()));
});

test('a Korean chapter citation can be followed by a grammatical particle', () => {
  assert.equal(Array.from('디모데전서 3 장과'.matchAll(pattern), match => match[0])[0], '디모데전서 3 장');
});
