# Scripture-proof build pipeline

Regenerates `content/proofs.js` and `content/verses.js` — the PCA Constitution's
**official Scripture proof texts** (footnote-style) plus the verse text shown when a
reference is tapped.

## Run

```sh
./build.sh        # fetches inputs, parses, emits ../content/{proofs,verses}.js
```

Requires `curl`, `pdftotext` (poppler-utils), `python3`. Output is deterministic.

## Sources

- **Proof references**: the PCA's official PDFs at pcaac.org — Shorter Catechism,
  Larger Catechism (two parts: `…Proofs1.pdf` = Q1–115, `03-LCLayout2.pdf` = Q114–196),
  and the Confession. These are the PCA's *own* proof selection (e.g. WSC Q26 cites
  Ps 110:3 / Matt 28:18–20 / John 17:2 / Col 1:13, **not** the classic Westminster
  Isaiah proofs). © PCA — the PDFs are fetched at build time, never committed.
- **Verse text**: Berean Standard Bible (`bereanbible.com/bsb.txt`), public-domain CC0.
  Only the ~4.7k proof-cited verses are bundled.

## How it works (geometry-aware PDF parsing)

`pdftotext`'s plain text mangles these PDFs (page-spanning footnotes interleave with
answers). Instead we parse `pdftotext -bbox-layout` and classify every word by **font
height**: section/answer text, footnote verse text, and superscript marker letters each
sit at a distinct point size. That cleanly separates them regardless of page layout, so
the superscript markers (a, b, c… skipping j/v, Latin style) align 1:1 with the lettered
footnotes. Marker↔footnote pairing is by document order.

Height bands differ per document (the Confession is typeset larger than the Catechisms),
so each parser sets its own bands:

| script | standard | notes |
|---|---|---|
| `bbox_parse.py` + `emit_wsc.py` | WSC | validated 101/107 exact vs reformedstandards.com (the 6 diffs are reformedstandards errors or `ff` notation — our parse is faithful to the PDF) |
| `parse_wlc.py` | WLC | two PDF parts merged; primed marker letters (`a´ b´…`) past `z` |
| `parse_wcf.py` | WCF | chapters from 13.5pt headings; 33 ch / 171 sections |
| `build_pca.py` | all | tokenizes each footnote's refs against the BSB, emits `proofs.js` + `verses.js` |

## Output format

`content/proofs.js`: `window.{WSC,WLC,WCF}_PROOFS = { "<id>": { ans, groups } }`
where `id` is `Q.1` (catechisms) or `1.1` (confession chapter.section), `ans` is the
answer/section text with `<sup>letter</sup>` markers, and `groups` is an ordered list of
`[letter, "ref, ref, …"]`.

`content/verses.js`: `window.VERSES` (BSB text keyed `"Book ch:v"`) and
`window.PROOF_REFMAP` (each ref-string → HTML with tappable `<a class="vref" data-v="…">`).

Validation: every cited verse resolves against the BSB (the build asserts 100%); any
parse artifact (e.g. a leaked page number) surfaces as an unresolved verse.
