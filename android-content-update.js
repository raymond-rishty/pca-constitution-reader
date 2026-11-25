(function () {
  'use strict';

  const arrays = ['WSC', 'WLC', 'BCO_ORDER', 'BUNDLED_PACKS'];
  const objects = [
    'BCO', 'BCO_ENGLISH_EDITION', 'BCO_INDEX_TOPICS', 'WCF', 'WCF_PROOFS',
    'WLC_PROOFS', 'WSC_PROOFS', 'VERSES', 'PROOF_REFMAP', 'INLINE_SCRIPTURE',
    'CIT_COUNTS', 'CIT',
  ];
  const fields = [...arrays, ...objects, 'GA_BASE'];
  const isRecord = value => value !== null && typeof value === 'object' && !Array.isArray(value);

  function validateContent(content) {
    if (!isRecord(content) ||
        arrays.some(key => !Array.isArray(content[key])) ||
        objects.some(key => !isRecord(content[key])) ||
        typeof content.GA_BASE !== 'string' || !/^https:\/\//.test(content.GA_BASE) ||
        !content.BCO_ORDER.length ||
        content.BCO_ORDER.some(id => typeof id !== 'string' || !Object.hasOwn(content.BCO, id) || !isRecord(content.BCO[id])) ||
        !isRecord(content.INLINE_SCRIPTURE.references) ||
        !isRecord(content.INLINE_SCRIPTURE.verses) ||
        content.BUNDLED_PACKS.some(pack => !isRecord(pack) || typeof pack.kind !== 'string')) {
      throw new Error('Invalid Android reader content');
    }
    const scripture = content.INLINE_SCRIPTURE;
    for (const verses of Object.values(scripture.references)) {
      if (!Array.isArray(verses) || !verses.length ||
          verses.some(verse => typeof verse !== 'string' ||
            !Object.hasOwn(scripture.verses, verse) || typeof scripture.verses[verse] !== 'string')) {
        throw new Error('Invalid Android reader Scripture reference');
      }
    }
    for (const [key, count] of Object.entries(content.CIT_COUNTS)) {
      const [book, ref] = key.split('|');
      const file = book === 'bco' ? 'bco-' + ref?.split('-')[0] : book;
      const rows = content.CIT[file]?.[ref];
      if (!ref || !Number.isSafeInteger(count) || count < 0 ||
          (count && (!Array.isArray(rows) || rows.length !== count))) {
        throw new Error('Invalid Android reader citation counts');
      }
    }
  }

  function isManifest(value) {
    return value?.schema === 1 && Number.isSafeInteger(value.timestamp) && value.timestamp > 0 &&
      typeof value.sha256 === 'string' && /^[a-f0-9]{64}$/.test(value.sha256);
  }

  async function parseSnapshot(manifest, snapshot) {
    if (!isManifest(manifest) || typeof snapshot !== 'string' || snapshot.length > 16 * 1024 * 1024) {
      throw new Error('Invalid Android content manifest or snapshot size');
    }
    const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(snapshot));
    const hash = Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, '0')).join('');
    if (hash !== manifest.sha256) throw new Error('Android content checksum mismatch');
    const parsed = JSON.parse(snapshot);
    if (parsed.schema !== 1) throw new Error('Unsupported Android content schema');
    validateContent(parsed.content);
    return parsed.content;
  }

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { validateContent, parseSnapshot };
    return;
  }

  const feed = 'https://raw.githubusercontent.com/raymond-rishty/pca-constitution-reader/android-content-feed/';
  const cacheName = 'pca-android-reader-content-v1';
  const cacheKey = new URL('downloaded-content-v1.json', location.href);

  async function checkForUpdate(cache, active) {
    const options = { cache: 'no-cache', credentials: 'omit', redirect: 'error' };
    const response = await fetch(feed + 'manifest-v1.json', options);
    if (!response.ok) return;
    const manifest = await response.json();
    if (!isManifest(manifest) || manifest.timestamp < active.timestamp || manifest.sha256 === active.sha256) return;
    const download = await fetch(feed + 'content-v1.json', options);
    if (!download.ok) return;
    const snapshot = await download.text();
    await parseSnapshot(manifest, snapshot);
    await cache.put(cacheKey, new Response(JSON.stringify({ manifest, snapshot })));
  }

  async function start() {
    let cache;
    let active;
    try {
      active = JSON.parse(document.querySelector('meta[name="reader-content-baseline"]').content);
      cache = await caches.open(cacheName);
      const saved = await cache.match(cacheKey);
      if (saved) {
        const { manifest, snapshot } = await saved.json();
        if (isManifest(manifest) && manifest.timestamp >= active.timestamp && manifest.sha256 !== active.sha256) {
          const content = await parseSnapshot(manifest, snapshot);
          for (const field of fields) window[field] = content[field];
          active = manifest;
        }
      }
    } catch (error) {
      console.warn('Using bundled reader content', error);
    }

    const reader = document.createElement('script');
    reader.src = 'android-reader.js';
    document.head.appendChild(reader);
    if (cache && isManifest(active)) {
      checkForUpdate(cache, active).catch(error => console.debug('Reader content check failed', error));
    }
  }

  void start();
}());
