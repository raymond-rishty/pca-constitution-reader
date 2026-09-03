# PCA Constitution Reader

A personal study reader for the Presbyterian Church in America (PCA) constitutional texts: the Westminster Confession of Faith, Westminster Larger Catechism, Westminster Shorter Catechism, and Book of Church Order (BCO).

The deployed reader is a single-page application. Its compact agent map is [`llms.txt`](llms.txt); this guide carries the longer usage and authority notes that do not belong in that index.

## Scope and authority

- The Westminster Confession and Catechisms are the American revision received by the PCA in 1788, presented with Scripture proof references and supporting verse text.
- The BCO is the PCA church-order text presented by the reader. Check [About & Sources](https://raymond-rishty.github.io/pca-constitution-reader/#about) for the displayed edition and source notes.
- The [official current PCA BCO](https://www.pcaac.org/book-of-church-order/) controls questions about present wording. Historical Minutes and Assembly actions are separate evidence.
- The Directory for the Worship of God has mixed authority: provisions marked binding are constitutional, while other portions are approved guidance. Do not treat every sentence as equally binding.
- Optional packs such as the Rules of Assembly Operations and commentary are supplementary material, not part of the PCA Constitution, unless a source expressly establishes their authority.

## Public routes

The reader uses URL fragments after `#`:

- Westminster Confession: `#wcf/<chapter>` or `#wcf/<chapter>.<section>`, for example [WCF 21.1](https://raymond-rishty.github.io/pca-constitution-reader/#wcf/21.1).
- Westminster Larger Catechism: `#wlc/Q.<number>`, for example [WLC Q.1](https://raymond-rishty.github.io/pca-constitution-reader/#wlc/Q.1).
- Westminster Shorter Catechism: `#wsc/Q.<number>`, for example [WSC Q.1](https://raymond-rishty.github.io/pca-constitution-reader/#wsc/Q.1).
- BCO: `#bco/<chapter>` or `#bco/<chapter>-<section>`. Form of Government is chapters 1–26; Rules of Discipline is chapters 27–46; Directory for Worship is chapters 47–63. Examples: [BCO 17-3](https://raymond-rishty.github.io/pca-constitution-reader/#bco/17-3), [BCO 34-10](https://raymond-rishty.github.io/pca-constitution-reader/#bco/34-10), [BCO 38-1](https://raymond-rishty.github.io/pca-constitution-reader/#bco/38-1), and [BCO 24](https://raymond-rishty.github.io/pca-constitution-reader/#bco/24).

## Agent retrieval workflow

1. Use the hash routes to open the exact book, chapter, question, or BCO provision.
2. Quote or paraphrase the constitutional text from the reader, identifying the book and provision.
3. For interpretation, application, amendment, or historical development, follow the link to the [PCA General Assembly Records map](https://raymond-rishty.github.io/pca-ga/llms.txt) and search its relevant catalogues and underlying Minutes.
4. Distinguish constitutional text from a judicial holding, CCB advice, RPR exception, committee recommendation, overture, study report, or other historical record. Check predecessor provision numbers when the historical source uses older numbering.

## Machine-readable assets

The page loads static JavaScript data files. They are useful for retrieval or parsing, but the public hash routes are better user-facing citations:

- [`content/wsc.js`](content/wsc.js) assigns the `WSC` question-and-answer array.
- [`content/wlc.js`](content/wlc.js) assigns the `WLC` question-and-answer array.
- [`content/wcf.js`](content/wcf.js) assigns the `WCF` chapter/section object.
- [`content/bco.js`](content/bco.js) assigns the `BCO` provision object and `BCO_ORDER` chapter list.
- [`content/proofs.js`](content/proofs.js) and [`content/verses.js`](content/verses.js) provide supporting Scripture data.

These files are JavaScript assignments rather than standalone JSON. Parse the relevant global and preserve the displayed reference identifiers.
