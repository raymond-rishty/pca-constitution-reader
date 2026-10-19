# Manual site build

The reader is currently served as static files. Run the manual build harness after editing diagram sources:

```sh
npm run build
```

The authoritative Appendix H sources are the SVG files in `diagrams/source/`. The harness checks their XML and copies them verbatim to `diagrams/`, where the reader and content packs load them. They have fixed shapes, connector paths, and lettering; a graph layout engine does not rearrange them. The build can also run directly with `python build_site.py`.

The built-in BCO Appendix H page embeds the active edition's SVG directly after the opening paragraph. The reader loads the local SVG as an in-page image.

The English SVG preserves the vector artwork and outlined lettering from the original PDF page, including its shadows, line breaks, and arrowheads. The Spanish and Korean PDF charts are raster images. Their SVG reconstructions use box boundaries and connector positions measured from those images, with editable text and the printed line breaks. Spanish uses Carlito Bold and Korean uses Noto Serif KR, embedded as WOFF2 subsets so the lettering renders consistently without installed fonts or network requests. These are substitute typefaces for the scanned lettering. Their SIL Open Font License notices are in `diagrams/source/fonts/`.

The PNGs in `diagrams/reference/` are visual references rendered from the cited PCA publications at 300 dpi: English, 2022 BCO, p. 221; Spanish, 2025 LDO, p. 372; Korean, 2026 BCO, p. 367. They are not build inputs.

The earlier `diagrams/*.dot` approximations remain for reference. For a diagram that has no authored SVG, the harness renders its DOT source with the headless WebAssembly Graphviz CLI (`neato -n2`). Install this optional renderer with `npm ci`. It is pinned in `package-lock.json` to `@hpcc-js/wasm-graphviz-cli` 1.11.3. Its CLI and WASM package are Apache-2.0 licensed; the bundled Graphviz implementation is under the Eclipse Public License 2.0. Neither requires a paid license. These packages are build dependencies and are not bundled with the reader.

## Language variants

Use the language tag before `.svg`:

- `diagrams/source/appendix-h.svg` — English
- `diagrams/source/appendix-h.ko.svg` — Korean
- `diagrams/source/appendix-h.es.svg` — Spanish

Each source publishes to the same filename in `diagrams/`. An authored SVG takes precedence over a DOT file with the same name. Spanish retains the printed wording and repeated appellant-record step. The embedded font subsets cover the chart's current characters; adding new text may require updating those subsets.

This script is the manual build entry point and can host future static asset generation steps. It is intentionally not connected to GitHub Actions yet.
