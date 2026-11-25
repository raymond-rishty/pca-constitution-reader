# Manual site build

The reader is currently served as static files. Run the manual build harness after editing diagram sources:

```sh
npm run build
```

The authoritative Appendix H sources are the SVG files in `diagrams/source/`. The harness checks their XML and copies them verbatim to `diagrams/`, where the reader and content packs load them. They have fixed shapes, connector paths, and lettering; a graph layout engine does not rearrange them. The build can also run directly with `python build_site.py`.

The built-in BCO Appendix H page embeds the active edition's SVG as an in-page image. The English chart follows the appendix text in the 2026 print order. The Spanish and Korean charts follow the opening paragraph.

The English SVG preserves the original PDF's boxes, connectors, shadows, and arrowheads. All three SVGs use editable whole-line `<text>` or `<tspan>` elements. The English line positions and widths retain the printed layout; a single `textLength` per line preserves its width while the browser lays out the characters. The sources contain no individually placed PDF glyphs or glyph-outline definitions.

English uses Arimo (compatible with Arial's metrics) and Tinos (compatible with Times New Roman's metrics). Spanish uses Carlito Bold with Tinos headings, and Korean uses Noto Serif KR. WOFF2 subsets are embedded so the lettering renders consistently without installed fonts or network requests. These substitute typefaces keep the text editable. Their SIL Open Font License notices are in `diagrams/source/fonts/`.

The Spanish and Korean PDF charts are raster images. Their SVG reconstructions use box boundaries and connector positions measured from those images, with the printed line breaks.

The PNGs in `diagrams/reference/` are visual references rendered from the cited PCA publications at 300 dpi: English, 2022 BCO, p. 221; Spanish, 2025 LDO, p. 372; Korean, 2026 BCO, p. 367. They are not build inputs.

The earlier `diagrams/*.dot` approximations remain for reference. For a diagram that has no authored SVG, the harness renders its DOT source with the headless WebAssembly Graphviz CLI (`neato -n2`). Install this optional renderer with `npm ci`. It is pinned in `package-lock.json` to `@hpcc-js/wasm-graphviz-cli` 1.11.3. Its CLI and WASM package are Apache-2.0 licensed; the bundled Graphviz implementation is under the Eclipse Public License 2.0. Neither requires a paid license. These packages are build dependencies and are not bundled with the reader.

## Language variants

Use the language tag before `.svg`:

- `diagrams/source/appendix-h.svg` — English
- `diagrams/source/appendix-h.ko.svg` — Korean
- `diagrams/source/appendix-h.es.svg` — Spanish

Each source publishes to the same filename in `diagrams/`. An authored SVG takes precedence over a DOT file with the same name. Spanish retains the printed wording and repeated appellant-record step. The embedded font subsets cover the chart's current characters; adding new text may require updating those subsets.

## Inline Scripture previews

After changing built-in text or its Scripture citations, run `python build_inline_scripture.py` to refresh `content/inline-scripture.js`. The script downloads the public-domain Berean Standard Bible, or accepts a local tab-separated copy with `--bsb`.

## Android debug APK

The Android preview bundles the reader, the checked-in BCO translations, and
the Appendix H diagrams. It uses the app ID `org.pcareader.preview`. The
build requires Node.js 24, Python 3.12, JDK 21, and Android SDK Platform 36.

From the repository root on Windows, with the toolchain on PATH and
`JAVA_HOME` and `ANDROID_HOME` set:

```powershell
npm ci
npm run build
npm run android:sync
Push-Location android
.\gradlew.bat assembleDebug
Pop-Location
```

The debug APK is at `android/app/build/outputs/apk/debug/app-debug.apk`. Run
the site build and sync again after changing the reader or its assets.

GitHub Actions builds and verifies a debug APK for each commit added directly
to `main`, including multiple commits in one push. The citation-refresh
workflow also builds the commit it pushes to `main`. Open the run in GitHub
Actions and download `pca-reader-debug-<commit SHA>` under **Artifacts**.
Artifacts are available for 14 days.
