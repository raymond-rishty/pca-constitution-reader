/* Public constitutional text only: no notes, bookmarks, or reading history. */
(() => {
  const context = document.modelContext;
  if (typeof context?.registerTool !== 'function') return;
  // Registration can reject when browser permissions or duplicate names prevent it.
  function registerTool(name, description, inputSchema, execute) {
    Promise.resolve().then(() => context.registerTool({
      name, description, inputSchema, annotations: { readOnlyHint: true },
      execute: async (args) => execute(args)
    })).catch(error => console.warn(`WebMCP tool ${name} could not be registered`, error));
  }
  const result = value => ({ content: [{ type: 'text', text: JSON.stringify(value) }] });
  // The Ask page and both sites share the Assembly site's published prompt.
  const promptURL = new URL('https://raymond-rishty.github.io/pca-ga/assets/pca-research-prompt.txt');
  let researchPrompt;
  async function loadResearchPrompt() {
    if (!researchPrompt) researchPrompt = fetch(promptURL).then(async response => {
      if (!response.ok) throw new Error('Research prompt unavailable; open https://raymond-rishty.github.io/pca-ga/ask.html or retry');
      const template = await response.text();
      if (!template.trimEnd().endsWith('[INSERT YOUR QUESTION HERE]')) throw new Error('Research prompt format is invalid');
      return template;
    }).catch(error => { researchPrompt = null; throw error; });
    return researchPrompt;
  }
  registerTool('prepare_pca_research', 'Primary entry point for a PCA Constitution or General Assembly research question. Call this first with the user question to receive the Ask page research prompt, source routes, authority distinctions, and citation requirements. Then retrieve and verify the evidence using the search and reading tools or the linked sources; this tool does not answer the question.', {
    type: 'object', properties: {
      question: { type: 'string', minLength: 1, description: 'The full user question, including any provision, case, date, or scope requested' }
    }, required: ['question'], additionalProperties: false
  }, async (args = {}) => {
    if (typeof args.question !== 'string' || !args.question.trim()) throw new Error('A nonempty question is required');
    const template = await loadResearchPrompt();
    const marker = template.lastIndexOf('[INSERT YOUR QUESTION HERE]');
    return result({
      question: args.question.trim(),
      prompt: template.slice(0, marker) + args.question.trim() + '\n'
    });
  });
  const schema = { type: 'object', properties: {
    query: { type: 'string', description: 'Reference, topic, keywords, or quoted phrase' },
    limit: { type: 'integer', minimum: 1, maximum: 50, default: 10 }
  }, required: ['query'], additionalProperties: false };
  registerTool('search_constitution', 'Search PCA constitutional provisions and installed public book packs. Returns public citation URLs and text; supplementary books are not constitutional authority.', schema, (args = {}) => {
    if (typeof args.query !== 'string' || !args.query.trim()) throw new Error('A nonempty query is required');
    if (args.limit !== undefined && (!Number.isInteger(args.limit) || args.limit < 1 || args.limit > 50)) throw new Error('limit must be an integer from 1 to 50');
    const found = PcaConstitutionSearch.search(buildSearch(), args.query);
    return result({ total: found.total, results: found.results.slice(0, args.limit ?? 10).map(({ record }) => ({
      book: record.book, reference: record.reference, title: record.title, text: record.text,
      url: appURL() + '#' + record.book + '/' + (record.noDrawer ? record.open.ch : record.ref)
    })) });
  });
  registerTool('read_current_provision', 'Read public text currently displayed in the Constitution Reader. Excludes personal notes and history.', { type: 'object', properties: {}, additionalProperties: false }, () =>
    result({ url: location.href, text: document.getElementById('doc')?.innerText || '', authority: 'Personal study reader. Verify current BCO wording against the official PCA BCO; supplementary packs are separate evidence.' }));
})();
