(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.PcaConstitutionSearch = api;
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  const FIELD_WEIGHTS = { reference: 900, title: 180, text: 40 };

  function normalize(value) {
    return String(value || '')
      .normalize('NFKD')
      .replace(/[\u0300-\u036f]/g, '')
      .toLowerCase()
      .replace(/&/g, ' and ')
      .replace(/[’']/g, '')
      .replace(/[^a-z0-9]+/g, ' ')
      .trim()
      .replace(/\s+/g, ' ');
  }

  function words(value) {
    return normalize(value).split(' ').filter(Boolean);
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

  function fuzzyLimit(term) {
    if (term.length >= 8) return 2;
    if (term.length >= 4) return 1;
    return 0;
  }

  function bestTermMatch(term, fieldValue) {
    const value = normalize(fieldValue);
    if (!value) return null;
    const tokens = value.split(' ');
    if (tokens.includes(term)) return { kind: 'exact', token: term, score: 80 };
    if (value.includes(term)) return { kind: 'substring', token: term, score: 60 };
    if (term.length >= 3) {
      const prefix = tokens.find((token) => token.startsWith(term));
      if (prefix) return { kind: 'prefix', token: prefix, score: 48 };
    }
    const limit = fuzzyLimit(term);
    if (!limit) return null;
    let best = null;
    for (const token of tokens) {
      if (token.length < 3 || Math.abs(token.length - term.length) > limit) continue;
      const edits = distance(term, token, limit);
      if (edits <= limit && (!best || edits < best.edits)) best = { edits, token };
    }
    return best ? { kind: 'fuzzy', token: best.token, score: 30 - (best.edits * 6) } : null;
  }

  function fieldValues(record) {
    return {
      reference: [record.reference || record.ref, ...(record.aliases || [])],
      title: [record.title || record.sub],
      text: [record.text || record.txt],
    };
  }

  function queryLooksLikeReference(parsed) {
    if (parsed.phrases.length || !parsed.terms.length) return false;
    const compact = normalize(parsed.source);
    if (/^(bco|book of church order)\s+(appendix\s+[a-z]|preface|preliminary principles|the constitution defined|constitution defined)$/.test(compact)) return true;
    if (parsed.terms.length > 3) return false;
    return /^(wcf|confession|wlc|larger|wsc|shorter|bco|book of church order|rao)?\s*q?\s*\d+(?:\s+[a-z0-9]+)*$/.test(compact);
  }

  function search(records, query, options = {}) {
    const parsed = parseQuery(query);
    const selectedBooks = options.books && options.books.size ? options.books : null;
    const pool = selectedBooks ? records.filter((record) => selectedBooks.has(record.book)) : records;
    if (!parsed.source) return { query: parsed, total: 0, results: [], fuzzy: false };
    const referenceQuery = queryLooksLikeReference(parsed);
    const rows = [];

    for (const record of pool) {
      const fields = fieldValues(record);
      const normalizedFields = Object.fromEntries(Object.entries(fields).map(([field, values]) => [
        field, values.filter(Boolean).map((raw) => ({ raw: String(raw), normalized: normalize(raw) })),
      ]));
      const normalizedQuery = normalize(parsed.source);
      const referenceMatch = normalizedFields.reference.some((value) =>
        value.normalized === normalizedQuery || value.normalized.startsWith(`${normalizedQuery} `));
      if (referenceQuery && !referenceMatch) continue;
      let score = 0;
      let matchedTerms = 0;
      let fuzzy = false;
      let bestField = 'text';
      let bestToken = '';
      let bestContribution = -1;
      let rejected = false;

      for (const phrase of parsed.phrases) {
        let phraseField = null;
        for (const field of Object.keys(normalizedFields)) {
          if (normalizedFields[field].some((value) => value.normalized.includes(phrase))) {
            phraseField = field;
            break;
          }
        }
        if (!phraseField) { rejected = true; break; }
        const contribution = 500 + FIELD_WEIGHTS[phraseField];
        score += contribution;
        if (contribution > bestContribution) {
          bestContribution = contribution;
          bestField = phraseField;
          bestToken = phrase;
        }
      }
      if (rejected) continue;

      for (const term of parsed.terms) {
        let termBest = null;
        for (const [field, values] of Object.entries(normalizedFields)) {
          for (const value of values) {
            const hit = bestTermMatch(term, value.normalized);
            if (!hit) continue;
            const contribution = hit.score + FIELD_WEIGHTS[field];
            if (!termBest || contribution > termBest.contribution) termBest = { ...hit, field, contribution };
          }
        }
        if (!termBest) continue;
        matchedTerms += 1;
        score += termBest.contribution;
        fuzzy = fuzzy || termBest.kind === 'fuzzy';
        if (termBest.contribution > bestContribution) {
          bestContribution = termBest.contribution;
          bestField = termBest.field;
          bestToken = termBest.token;
        }
      }

      if (!parsed.phrases.length && !matchedTerms) continue;
      const exactReference = normalizedFields.reference.some((value) => value.normalized === normalizedQuery);
      if (exactReference) score += 5000;
      score += matchedTerms * matchedTerms * 35;
      rows.push({ record, score, matchedTerms, fuzzy, bestField, bestToken, exactReference });
    }

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

  return { normalize, parseQuery, distance, search, excerpt };
}));
