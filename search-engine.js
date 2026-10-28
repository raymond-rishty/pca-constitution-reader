(function (root, factory) {
  const MiniSearch = typeof module === 'object' && module.exports
    ? require('minisearch')
    : root.MiniSearch;
  const api = factory(MiniSearch);
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.PcaConstitutionSearch = api;
}(typeof globalThis !== 'undefined' ? globalThis : this, function (MiniSearch) {
  'use strict';

  const SEARCH_FIELDS = ['reference', 'aliases', 'title', 'topics', 'text'];
  const FIELD_WEIGHTS = { reference: 16, aliases: 16, title: 5, topics: 4, text: 1 };
  const INDEX_CACHE = new WeakMap();

  function normalize(value) {
    return String(value || '')
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .toLowerCase()
      .replace(/&/g, ' and ')
      .replace(/[’']/g, '')
      .replace(/[^\p{L}\p{N}]+/gu, ' ')
      .trim()
      .replace(/\s+/g, ' ');
  }

  function tokenize(value) {
    return normalize(value).match(/[\p{L}\p{N}]+/gu) || [];
  }

  function words(value) {
    return tokenize(value);
  }

  function contentText(content) {
    if (typeof content === 'string' || typeof content === 'number') return String(content);
    if (Array.isArray(content)) return content.map(contentText).filter(Boolean).join(' ');
    if (!content || typeof content !== 'object') return '';
    if (Array.isArray(content.blocks) && content.blocks.length) {
      return content.blocks.map((block) => {
        if (!Array.isArray(block)) return '';
        return block[0] === 'i' ? `${block[2] || ''} ${block[3] || ''}` : String(block[2] || '');
      }).filter(Boolean).join(' ');
    }
    return Array.isArray(content.paragraphs) ? content.paragraphs.map(contentText).filter(Boolean).join(' ') : '';
  }

  function distance(a, b, limit) {
    if (a === b) return 0;
    if (!a || !b || Math.abs(a.length - b.length) > limit) return limit + 1;
    let previous = Array.from({ length: b.length + 1 }, (_, i) => i);
    for (let i = 1; i <= a.length; i += 1) {
      const current = [i];
      let rowMin = i;
      for (let j = 1; j <= b.length; j += 1) {
        current[j] = Math.min(
          current[j - 1] + 1,
          previous[j] + 1,
          previous[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1),
        );
        rowMin = Math.min(rowMin, current[j]);
      }
      if (rowMin > limit) return limit + 1;
      previous = current;
    }
    return previous[b.length];
  }

  function parseQuery(query) {
    const source = String(query || '').trim();
    const phrases = [];
    const terms = [];
    const pattern = /"([^"\n]+)"|([^\s]+)/g;
    let match;
    while ((match = pattern.exec(source))) {
      const value = normalize(match[1] || match[2]);
      if (!value) continue;
      if (match[1]) phrases.push(value);
      else terms.push(value);
    }
    return { source, phrases, terms };
  }

  function queryLooksLikeReference(parsed) {
    if (parsed.phrases.length || !parsed.terms.length) return false;
    const compact = normalize(parsed.source);
    if (/^(bco|book of church order)\s+(appendix\s+[a-z]|preface|preliminary principles|the constitution defined|constitution defined)$/.test(compact)) return true;
    if (parsed.terms.length > 3) return false;
    return /^(wcf|confession|wlc|larger|wsc|shorter|bco|book of church order|rao)?\s*q?\s*\d+(?:\s+[a-z0-9]+)*$/.test(compact);
  }

  function referenceValues(record) {
    return [record.reference || record.ref, ...(record.aliases || [])].filter(Boolean).map(normalize);
  }

  function searchableValues(record) {
    return {
      reference: [record.reference || record.ref].filter(Boolean),
      aliases: (record.aliases || []).filter(Boolean),
      title: [record.title || record.sub].filter(Boolean),
      topics: (record.topics || []).filter(Boolean),
      text: [record.text || record.txt].filter(Boolean),
    };
  }

  function createIndex(records) {
    const existing = INDEX_CACHE.get(records);
    if (existing) return existing;
    if (!MiniSearch) throw new Error('MiniSearch is required to build the reader search index.');
    const docs = records.map((record, id) => {
      const fields = searchableValues(record);
      return {
        id,
        book: record.book,
        ref: record.ref,
        reference: fields.reference.join(' '),
        aliases: fields.aliases.join(' '),
        title: fields.title.join(' '),
        topics: fields.topics.join(' '),
        text: fields.text.join(' '),
      };
    });
    const index = new MiniSearch({
      fields: SEARCH_FIELDS,
      storeFields: ['id'],
      tokenize,
      processTerm: (term) => normalize(term),
      searchOptions: { boost: FIELD_WEIGHTS, combineWith: 'OR' },
    });
    index.addAll(docs);
    const built = { index };
    INDEX_CACHE.set(records, built);
    return built;
  }

  function indexFor(records) {
    return createIndex(records);
  }

  function hasPhrase(record, phrase) {
    return Object.values(searchableValues(record)).some((values) =>
      values.some((value) => normalize(value).includes(phrase)));
  }

  function matchFields(hit) {
    const fields = new Set();
    for (const matched of Object.values(hit.match || {})) matched.forEach((field) => fields.add(field));
    return fields;
  }

  function fuzzyLimit(term) {
    if (term.length >= 8) return 2;
    if (term.length >= 4) return 1;
    return 0;
  }

  function bestField(fields) {
    return [...fields].sort((a, b) => (FIELD_WEIGHTS[b] || 0) - (FIELD_WEIGHTS[a] || 0))[0] || 'text';
  }

  function search(records, query, options = {}) {
    const parsed = parseQuery(query);
    const selectedBooks = options.books && options.books.size ? options.books : null;
    if (!parsed.source) return { query: parsed, total: 0, results: [], fuzzy: false };

    const referenceQuery = queryLooksLikeReference(parsed);
    const normalizedQuery = normalize(parsed.source);
    const rows = [];
    const terms = [...parsed.terms, ...parsed.phrases.flatMap(words)];
    const queryText = [...new Set(terms)].join(' ');
    const { index } = indexFor(records);
    const settings = {
      combineWith: 'OR',
      prefix: (term) => term.length >= 3,
      fuzzy: (term) => term.length >= 8 ? 0.2 : (term.length >= 4 ? 0.15 : false),
    };
    const hits = queryText ? index.search(queryText, settings) : [];
    const hitById = new Map(hits.map((hit) => [hit.id, hit]));
    const allowed = (record) => !selectedBooks || selectedBooks.has(record.book);

    records.forEach((record, id) => {
      if (!allowed(record)) return;
      const refs = referenceValues(record);
      const exactReference = refs.includes(normalizedQuery);
      const referenceMatch = refs.some((value) => value === normalizedQuery || value.startsWith(`${normalizedQuery} `));
      if (referenceQuery && !referenceMatch) return;

      const hit = hitById.get(id);
      const recordFields = searchableValues(record);
      const phraseFields = parsed.phrases.length
        ? Object.keys(recordFields).filter((field) =>
          recordFields[field].some((value) => parsed.phrases.every((phrase) => normalize(value).includes(phrase))))
        : [];
      if (parsed.phrases.some((phrase) => !hasPhrase(record, phrase))) return;
      if (!hit && !exactReference) return;

      const fields = matchFields(hit || {});
      phraseFields.forEach((field) => fields.add(field));
      const matchedTerms = terms.filter((term) => hit && (hit.terms || []).some((matched) => {
        const normalized = normalize(matched);
        const limit = fuzzyLimit(term);
        return normalized === term || normalized.startsWith(term) || (limit && distance(term, normalized, limit) <= limit);
      })).length;
      const fuzzy = Boolean(hit && terms.some((term) => {
        const limit = fuzzyLimit(term);
        return limit > 0 && (hit.terms || []).some((matched) => {
          const normalized = normalize(matched);
          return !normalized.startsWith(term) && distance(term, normalized, limit) <= limit;
        });
      }));
      const tokens = [...parsed.terms, ...parsed.phrases];
      rows.push({
        record,
        score: (exactReference ? 1e9 : 0) + (hit ? hit.score : 0) + matchedTerms * matchedTerms * 0.01,
        matchedTerms,
        fuzzy,
        bestField: bestField(fields),
        bestToken: tokens[0] || normalizedQuery,
        exactReference,
      });
    });

    rows.sort((a, b) => b.score - a.score
      || b.matchedTerms - a.matchedTerms
      || String(a.record.reference || a.record.ref).localeCompare(String(b.record.reference || b.record.ref), undefined, { numeric: true }));
    return {
      query: parsed,
      total: rows.length,
      results: rows,
      fuzzy: rows.some((row) => row.fuzzy),
    };
  }

  function excerpt(value, token, length = 180) {
    const source = String(value || '').replace(/\s+/g, ' ').trim();
    if (source.length <= length) return source;
    const needle = String(token || '').toLowerCase();
    let at = needle ? source.toLowerCase().indexOf(needle) : -1;
    if (at < 0) at = 0;
    const start = Math.max(0, at - Math.floor(length * 0.38));
    const end = Math.min(source.length, start + length);
    const left = start ? source.indexOf(' ', start) + 1 : 0;
    const rightSpace = end < source.length ? source.lastIndexOf(' ', end) : source.length;
    const right = rightSpace > left ? rightSpace : end;
    return `${left ? '…' : ''}${source.slice(left, right).trim()}${right < source.length ? '…' : ''}`;
  }

  return { normalize, tokenize, parseQuery, distance, contentText, createIndex, search, excerpt };
}));
