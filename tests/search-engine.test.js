const assert = require('node:assert/strict');
const { test } = require('node:test');
const engine = require('../search-engine.js');

const records = [
  {
    book: 'wsc', ref: 'Q.1', reference: 'WSC Q.1',
    aliases: ['WSC Q.1', 'Shorter Catechism Q 1'],
    title: 'What is the chief end of man?',
    text: "Man's chief end is to glorify God, and to enjoy him for ever.",
  },
  {
    book: 'wcf', ref: '21.5', reference: 'WCF 21.5',
    aliases: ['WCF 21.5', 'Confession 21.5'],
    title: 'Of Religious Worship, and the Sabbath Day',
    text: 'The reading of the Scriptures with godly fear; the sound preaching, and conscionable hearing of the Word.',
  },
  {
    book: 'bco', ref: '24-1', reference: 'BCO 24-1',
    aliases: ['BCO 24-1', 'Book of Church Order 24-1', '24-1'],
    title: 'Election, Ordination and Installation of Ruling Elders and Deacons',
    text: 'Every church shall elect persons to the offices of ruling elder and deacon.',
  },
];

test('normalizes punctuation, apostrophes, case, and accents', () => {
  assert.equal(engine.normalize('Man’s chief—end'), 'mans chief end');
  assert.equal(engine.normalize('Café'), 'cafe');
});

test('ranks an exact reference ahead of incidental matches', () => {
  const result = engine.search(records, 'BCO 24.1');
  assert.equal(result.total, 1);
  assert.equal(result.results[0].record.ref, '24-1');
  assert.equal(result.results[0].exactReference, true);
});

test('recognizes multi-part provision references as exact lookups', () => {
  const extended = records.concat({
    book: 'bco', ref: '35-8-a', reference: 'BCO 35-8-a',
    aliases: ['BCO 35-8-a', '35-8-a'], title: 'Evidence', text: 'Testimony is received.',
  });
  const result = engine.search(extended, 'BCO 35.8.a');
  assert.equal(result.total, 1);
  assert.equal(result.results[0].record.ref, '35-8-a');
});

test('recognizes BCO front matter and appendix labels as references', () => {
  const extended = records.concat({
    book: 'bco', ref: 'Appendix I', reference: 'BCO Appendix I',
    aliases: ['BCO Appendix I', 'Appendix I'], title: 'Biblical Conflict Resolution', text: 'Peacemaking.',
  });
  const result = engine.search(extended, 'BCO Appendix I');
  assert.equal(result.total, 1);
  assert.equal(result.results[0].record.ref, 'Appendix I');
});

test('searches question, answer, title, and provision text', () => {
  assert.equal(engine.search(records, 'chief end').results[0].record.ref, 'Q.1');
  assert.equal(engine.search(records, 'conscionable').results[0].record.ref, '21.5');
  assert.equal(engine.search(records, 'Ordination').results[0].record.ref, '24-1');
});

test('tolerates minor misspellings without matching very short words fuzzily', () => {
  const result = engine.search(records, 'conscienable');
  assert.equal(result.results[0].record.ref, '21.5');
  assert.equal(result.results[0].fuzzy, true);
  assert.equal(engine.search(records, 'zz').total, 0);
});

test('requires quoted phrases', () => {
  assert.equal(engine.search(records, '"sound preaching"').total, 1);
  assert.equal(engine.search(records, '"preaching sound"').total, 0);
});

test('filters by document and creates a centered excerpt', () => {
  assert.equal(engine.search(records, 'chief', { books: new Set(['bco']) }).total, 0);
  const passage = `Before ${'word '.repeat(40)}needle ${'after '.repeat(40)}`;
  const excerpt = engine.excerpt(passage, 'needle', 80);
  assert.match(excerpt, /needle/);
  assert.ok(excerpt.startsWith('…'));
});
