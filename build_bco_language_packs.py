#!/usr/bin/env python3
"""Prepare private Spanish and Korean BCO packs for the reader's bundled-pack loader."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DEFAULT_SOURCE_DIR = ROOT.parent / "pca-reader-content-packs"
PACKS = (
    ("bco-2025-es.content-pack.json", "es", "bco-2025-es.js"),
    ("bco-2026-ko.content-pack.json", "ko", "bco-2026-ko.js"),
)


def reader_order() -> list[str]:
    source = (ROOT / "content" / "bco.js").read_text(encoding="utf-8")
    match = re.search(r"window\.BCO_ORDER\s*=\s*(\[.*?\]);", source, re.S)
    if not match:
        raise ValueError("Could not read window.BCO_ORDER from content/bco.js")
    return json.loads(match.group(1))


def prepare_pack(source_path: Path, language: str, order: list[str]) -> dict:
    pack = json.loads(source_path.read_text(encoding="utf-8"))
    if pack.get("format") != "pca-constitution-pack" or pack.get("kind") != "book":
        raise ValueError(f"{source_path.name} is not a v1 book content pack")
    if pack.get("order") != order:
        raise ValueError(f"{source_path.name} chapter order does not match content/bco.js")
    if set(pack.get("chapters", {})) != set(order):
        raise ValueError(f"{source_path.name} chapter keys do not match its order")

    component = pack["component"]
    component["language"] = language
    component["translationOf"] = "bco"
    if language == "es":
        component.update(
            noticeLabel="Nota de edición",
            vacatedText="Este capítulo ha sido vacado.",
            parts={
                "front": "Prefacio y principios",
                "fog": "Forma de gobierno",
                "rod": "Reglas de disciplina",
                "dow": "Directorio para la adoración",
                "appx": "Apéndices",
            },
        )
    else:
        component.update(noticeLabel="판본 안내", vacatedText="이 장은 폐지되었습니다.")
        qualifier = "The Korean text is a study transcription; independent line-by-line proofreading remains outstanding."
        if qualifier not in pack.get("notice", ""):
            pack["notice"] = (pack.get("notice", "").rstrip() + " " + qualifier).strip()
    return pack


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR,
                        help="pca-reader-content-packs checkout (default: sibling checkout)")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "content" / "packs",
                        help="private generated output directory (default: content/packs)")
    args = parser.parse_args()

    order = reader_order()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for source_name, language, output_name in PACKS:
        source_path = args.source_dir / source_name
        pack = prepare_pack(source_path, language, order)
        payload = json.dumps(pack, ensure_ascii=False, separators=(",", ":"))
        script = (
            f"/* Private personal-use translation pack. Source: {source_path.name} */\n"
            "(function(){const pack=" + payload + ";"
            "window.BUNDLED_PACKS=window.BUNDLED_PACKS||[];"
            "window.BUNDLED_PACKS.push(pack);})();\n"
        )
        output_path = args.output_dir / output_name
        output_path.write_text(script, encoding="utf-8", newline="\n")
        print(f"Prepared {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
