# Manual site build

The reader is currently served as static files. Install the locked npm build dependency once, then run the repository build harness manually when diagram sources change:

```sh
npm ci
npm run build
```

The harness discovers every `diagrams/*.dot` source and renders its matching SVG with the headless WebAssembly Graphviz CLI. The DOT files use Neato's fixed-position mode: every node has a `pos` in points, and `neato -n2` preserves those positions while routing edges. Small invisible point nodes define the rails and edge bends. The harness adds a light offset shadow to boxes and ovals to match the printed diagrams. To change the composition, edit node coordinates and routing points in the DOT source, then run `npm run build`.

The PNGs in `diagrams/reference/` are visual references rendered from the cited PCA publications at 300 dpi: English, 2022 BCO, p. 221; Spanish, 2025 LDO, p. 372; Korean, 2026 BCO, p. 367. They are not build inputs.

The build dependency is pinned in `package-lock.json` to `@hpcc-js/wasm-graphviz-cli` 1.11.3. Its CLI and WASM package are Apache-2.0 licensed; the bundled Graphviz implementation is under the Eclipse Public License 2.0. Neither requires a paid license for this use. These packages are build dependencies and are not bundled with the reader. Keep the versions in the lockfile fixed when regenerating assets so layout and SVG output remain consistent.

## Language variants

Use the language tag before `.dot`:

- `diagrams/appendix-h.dot` — default English source
- `diagrams/appendix-h.ko.dot` — Korean
- `diagrams/appendix-h.es.dot` — Spanish

Each source generates a correspondingly named `.svg`. The harness processes all present variants; it does not require every language file to exist. The DOT transcriptions retain the Spanish diagram's wording and repeated appellant-record step. Coordinates are tuned per language because label lengths and printed layouts differ.

This script is the manual build entry point and can host future static asset generation steps. It is intentionally not connected to GitHub Actions yet.
