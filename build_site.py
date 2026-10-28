#!/usr/bin/env python3
"""Run the repository's manual static-site build steps."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DIAGRAM_DIR = ROOT / "diagrams"
MINISEARCH_PACKAGE = ROOT / "node_modules" / "minisearch"
VENDOR_DIR = ROOT / "vendor"


def publish_minisearch() -> None:
    package_json = MINISEARCH_PACKAGE / "package.json"
    if not package_json.is_file():
        raise SystemExit("MiniSearch is not installed. Run 'npm ci' before building the site.")
    package = json.loads(package_json.read_text(encoding="utf-8"))
    if package.get("version") != "7.2.0":
        raise SystemExit("The vendored reader build requires MiniSearch 7.2.0.")
    VENDOR_DIR.mkdir(exist_ok=True)
    for source, destination in (
        (MINISEARCH_PACKAGE / "dist" / "umd" / "index.js", VENDOR_DIR / "minisearch.js"),
        (MINISEARCH_PACKAGE / "LICENSE.txt", VENDOR_DIR / "MiniSearch-LICENSE.txt"),
    ):
        contents = source.read_bytes()
        if destination.is_file():
            existing = destination.read_bytes()
            if existing.replace(b"\r\n", b"\n") == contents.replace(b"\r\n", b"\n"):
                continue
        destination.write_bytes(contents)


def build_diagrams() -> None:
    authored = sorted((DIAGRAM_DIR / "source").glob("*.svg"))
    for source in authored:
        # Validate the authored vector source before publishing it. Copying it
        # verbatim preserves its type, geometry, and embedded font subsets.
        ET.parse(source)
        output = DIAGRAM_DIR / source.name
        shutil.copyfile(source, output)
        print(f"Publishing {source.relative_to(ROOT)} -> {output.relative_to(ROOT)}")

    authored_names = {source.name for source in authored}
    sources = sorted(
        source for source in DIAGRAM_DIR.glob("*.dot")
        if source.with_suffix(".svg").name not in authored_names
    )
    if not sources:
        return

    node = shutil.which("node")
    renderer = ROOT / "node_modules" / "@hpcc-js" / "wasm-graphviz-cli" / "bin" / "index.js"
    if node is None or not renderer.is_file():
        raise SystemExit(
            "The WASM Graphviz CLI is not installed. Run 'npm ci' and ensure "
            "Node.js is on PATH. See docs/site-build.md."
        )

    for source in sources:
        output = source.with_suffix(".svg")
        print(f"Rendering {source.relative_to(ROOT)} -> {output.relative_to(ROOT)}")
        result = subprocess.run(
            [node, str(renderer), "-K", "neato", "-n", "2", "-Tsvg", str(source)],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        svg = result.stdout.replace(
            ">\n<g id=\"graph0\"",
            ">\n<style>.node polygon, .node ellipse { filter: drop-shadow(1.1px 1.1px 0 #888); }</style>\n<g id=\"graph0\"",
            1,
        )
        output.write_text(svg.rstrip() + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    try:
        publish_minisearch()
        build_diagrams()
    except subprocess.CalledProcessError as exc:
        print(f"Graphviz failed while rendering a diagram (exit {exc.returncode}).", file=sys.stderr)
        if exc.stderr:
            print(exc.stderr, file=sys.stderr, end="" if exc.stderr.endswith("\n") else "\n")
        return exc.returncode or 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
