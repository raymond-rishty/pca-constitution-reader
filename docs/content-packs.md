# Content pack format

The Constitution Reader can import portable JSON **content packs**. Packs let the reader store notes, attach commentary to an existing corpus, or add an entire paged document such as presbytery rules, bylaws, or supplementary PCA material.

This document describes the format currently consumed by the reader. The format identifier is:

```json
{
  "format": "pca-constitution-pack",
  "version": 1
}
```

The current importer requires `format` to equal `"pca-constitution-pack"`. Version 1 is the documented contract; the importer currently does not reject another `version` value, so producers should still emit `version: 1` for compatibility.

## Common fields

All packs are JSON objects.

| Field | Required | Description |
| --- | --- | --- |
| `format` | yes | Must be `"pca-constitution-pack"`. |
| `version` | yes for v1 producers | Use `1`. |
| `kind` | yes | `"notes"`, `"commentary"`, or `"book"`. |
| `label` | recommended | Human-readable pack name. |
| `notice` | optional | Short status/source/copyright note shown in the pack manager for bundled packs. |

Unknown fields are currently ignored.

## Notes packs

Notes packs merge user-authored notes into the reader.

```json
{
  "format": "pca-constitution-pack",
  "version": 1,
  "kind": "notes",
  "label": "My notes",
  "entries": {
    "24-1": [
      {
        "who": "You",
        "when": "Sep 2026",
        "text": "Compare this provision with BCO 21."
      }
    ]
  }
}
```

### `entries`

`entries` is an object keyed by provision reference. Each value is an array of note objects.

The reader uses `text` as the note contents. `who` and `when` are display metadata and should be strings when supplied.

Import is non-destructive. Existing notes remain in place, and imported notes are de-duplicated by exact `text` value within each provision.

## Commentary packs

Commentary packs attach one or more paragraphs to provisions in an existing corpus.

```json
{
  "format": "pca-constitution-pack",
  "version": 1,
  "kind": "commentary",
  "label": "Example Commentary",
  "corpus": "bco",
  "entries": {
    "31-2": [
      "First paragraph of commentary.",
      "Second paragraph of commentary."
    ]
  }
}
```

| Field | Required | Description |
| --- | --- | --- |
| `label` | recommended | Commentary name. Defaults to `"Commentary"`. |
| `corpus` | optional | Component key to which the references belong. Defaults to `"bco"`. |
| `entries` | yes in practice | Object keyed by provision reference; each value is an array of commentary paragraphs. |

Re-importing a commentary pack with the same `label` replaces the prior pack of that name.

## Book packs

A book pack adds a complete paged corpus to the reader.

```json
{
  "format": "pca-constitution-pack",
  "version": 1,
  "kind": "book",
  "label": "Example Rules",
  "component": {
    "key": "example-rules",
    "abbr": "ER",
    "name": "Example Rules",
    "division": "local",
    "icon": "scroll",
    "tag": "Rules of the Example body.",
    "lede": "A short description for the landing page.",
    "meta": "12 chapters · adopted 2026"
  },
  "order": ["1", "2"],
  "chapters": {
    "1": {
      "title": "Organization",
      "sections": [
        {
          "ref": "1-1",
          "body": "The body shall meet annually."
        }
      ]
    },
    "2": {
      "title": "Officers",
      "sections": [
        {
          "ref": "2-1",
          "blocks": [
            ["p", 0, "The officers shall be:"],
            ["i", 1, "a.", "a Moderator"],
            ["i", 1, "b.", "a Clerk"]
          ]
        }
      ]
    }
  }
}
```

### `component`

`component.key` is the only book metadata field the importer currently hard-requires. A practical book pack should provide the rest of the display metadata as well.

| Field | Recommended | Description |
| --- | --- | --- |
| `key` | required | Stable, URL-safe identifier for the book. It becomes the hash-route prefix, e.g. `#example-rules/2`. Do not reuse a built-in key such as `bco`, `wcf`, `wlc`, or `wsc`. |
| `abbr` | yes | Short label used in navigation and citations. |
| `name` | yes | Full document name. |
| `division` | yes | Landing-page grouping. Supported values are `doctrinal`, `order`, `local`, and `supplemental`; unknown values fall back visually to the local grouping. |
| `icon` | optional | Named built-in icon, emoji/text glyph, or inline SVG. Named icons currently include `book`, `scroll`, `gavel`, `scales`, `church`, `building`, `people`, and `shield`. |
| `nonConstitutional` | optional | Boolean metadata used by supplementary material. |
| `tag` | optional | Short description shown on the home page. |
| `lede` | optional | Longer component introduction. |
| `meta` | optional | Compact edition/status line. |

The reader supplies `mode: "paged"` and `custom: true` internally; pack authors do not need to set them.

### `order` and `chapters`

`order` is an array of chapter IDs in display/navigation order. Every ID should have a matching key in `chapters`.

Each chapter has:

```json
{
  "title": "Chapter title",
  "sections": []
}
```

A section may use either a simple HTML-capable body string:

```json
{
  "ref": "3-2",
  "body": "Section text."
}
```

or structured blocks:

```json
{
  "ref": "3-2",
  "blocks": [
    ["p", 0, "Opening paragraph."],
    ["p", 1, "Indented paragraph."],
    ["i", 2, "a.", "Lettered item."]
  ]
}
```

Block tuples have these shapes:

- `["p", depth, text]` — paragraph.
- `["i", depth, marker, text]` — indented/list item.

`depth` is rendered as a nesting/indentation level. For a normal numbered section, if the first block is `["p", 0, ...]`, its text is rendered on the same lead paragraph as the section reference.

A section may also set `"prose": true` for unnumbered or essay-style material. Such sections are omitted from the chapter's section rail. A prose section may still carry a `ref`, which is useful when footnotes need an anchor.

### Optional book annotations

Book packs may include their own footnotes and bundled commentary:

```json
{
  "footnotes": {
    "2-1": [
      "Footnote text."
    ]
  },
  "commentary": {
    "2-1": [
      "Commentary paragraph."
    ]
  },
  "commentaryLabel": "Editor's Notes",
  "commentaryAttribution": "Notes supplied with this document."
}
```

`footnotes` and `commentary` are keyed by section reference. Values are arrays of strings.

## HTML and trust

Section bodies, block text, notes, commentary, and metadata are rendered by the reader as supplied in several places. Packs should therefore be treated as **trusted local content**, not as a safe interchange format for arbitrary untrusted input. Do not import packs from a source you do not trust.

## Persistence and replacement behavior

Imported notes, commentaries, and books are stored in browser `localStorage`.

- Notes merge into existing notes.
- A commentary with the same `label` replaces that commentary pack.
- A book with the same `component.key` replaces that book pack.
- Removing a pack from the pack manager removes the locally stored copy; it does not alter a source JSON file.

## Bundled packs

A pack distributed with the reader is ordinary v1 pack data pushed into `window.BUNDLED_PACKS`. For example:

```js
window.BUNDLED_PACKS = window.BUNDLED_PACKS || [];
window.BUNDLED_PACKS.push({ /* v1 pack object */ });
```

The bundled Rules of Assembly Operations pack in `content/rao.js` is the canonical in-repository example of a book pack. `content/ramsay.js` is the canonical bundled commentary example.

## Minimal validation performed today

The current importer intentionally remains permissive:

- all packs: `format === "pca-constitution-pack"`;
- supported `kind`: `notes`, `commentary`, or `book`;
- book packs: `component.key` must exist.

It does not currently perform JSON Schema validation, enforce `version === 1`, validate reference syntax, or verify that every `order` entry has a corresponding chapter. Producers should follow this specification even where the current reader is more forgiving.
