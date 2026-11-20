#!/usr/bin/env python3
"""Build the supplementary documents from the PCA's BCO pages."""

import html
import json
import re
import subprocess

from lxml import html as lxml_html

from build_rao import HERE, block, main as write_rao, text

BASE = "https://www.pcaac.org/book-of-church-order/"
DOCUMENTS = (
    ("omsjc", "OMSJC", "Operating Manual for Standing Judicial Commission",
     "operating-manual-for-standing-judicial-commission"),
    ("incorporation", "Certificate", "Certificate of Incorporation",
     "certificate-of-incorporation"),
    ("corporate-bylaws", "Bylaws", "Corporate Bylaws", "corporate-bylaws"),
    ("bco-subject-index", "BCO Index", "Book of Church Order Index", "index"),
    ("naparc", "NAPARC", "NAPARC Agreements", "naparc-agreements"),
)
MODULES = '//*[contains(concat(" ", @class, " "), " et_pb_text_inner ")]'


def chapter(title, rows, marker, prefix=""):
    sections = []
    for row in rows:
        value = text(row)
        if not value:
            continue
        match = re.match(marker, value)
        item = block(row)
        if match:
            sections.append({"ref": prefix + match[1], "blocks": []})
            # Use the reader's reference label for the printed section number.
            # Retain extra source wording such as "Section" and ordinal headings.
            if match.start(1) == 0 and prefix == "" and match[1][0].isdigit():
                item = ["p", item[1], value[match.end():].lstrip()]
        elif not sections:
            sections.append({"ref": prefix.rstrip(".") or title, "prose": True, "blocks": []})
        sections[-1]["blocks"].append(item)
    for section in sections:
        for item in section["blocks"]:
            item[-1] = html.escape(item[-1], quote=False)
    return {"title": title, "sections": sections}


def manual(modules):
    preface = next(m for m in modules if any(text(e) == "PREFACE" for e in m))
    children = list(preface)
    start = next(i for i, e in enumerate(children) if text(e) == "PREFACE")
    chapters = {"preface": chapter("Preface", children[start + 1:], r"(?!)")}
    for module in modules:
        match = re.fullmatch(r"OMSJC_(\d+)", module.getparent().get("id", ""))
        if match:
            number = match[1]
            title = text(module.xpath("./h4")[0])
            chapters[number] = chapter(title, module.xpath("./p|./ol|./ul|./h5|./h6"),
                                       rf"({number}\.\d+)\.?(?=\s|[A-Z]|$)")
    assert list(chapters)[1:] == [str(n) for n in range(1, 21)]
    return chapters


def articles(rows, heading, section):
    chapters = {}
    key, title, start = "preface", "Preface", 0
    for i, row in enumerate(rows):
        match = re.match(heading, text(row))
        if match:
            chapters[key] = chapter(title, rows[start:i], section, f"{key}.")
            key, title, start = match[1], text(row), i + 1
    chapters[key] = chapter(title, rows[start:], section, f"{key}.")
    return chapters


def build(doc, source):
    key, abbr, name, slug = doc
    modules = lxml_html.fromstring(source).xpath(MODULES)
    edition = next(text(e) for m in modules for e in m if "General Assembly" in text(e) and e.tag in ("h4", "h5"))
    if key == "bco-subject-index":
        content = next(m for m in modules if any(e.tag == "h2" and text(e) == "INDEX" for e in m))
        sections = []
        chapters = {"subjects": {"title": "Subject index", "sections": sections}}
        for row in content.xpath("./p"):
            value = text(row)
            if not value:
                continue
            item = block(row)
            if not sections or item[1] == 0:
                slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
                sections.append({"ref": slug, "blocks": [], "prose": True})
            item[-1] = html.escape(item[-1], quote=False)
            sections[-1]["blocks"].append(item)
    elif key == "omsjc":
        chapters = manual(modules)
    else:
        content = next(m for m in modules if any(e.tag == "h5" and text(e) == edition for e in m))
        rows = list(modules[modules.index(content) + 1])
        if key == "incorporation":
            chapters = {"certificate": chapter(name, rows, r"(FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH|EIGHTH)\.")}
        elif key == "corporate-bylaws":
            chapters = articles(rows, r"ARTICLE ([IVX]+)\.", r"(?:Section )?(\d+|[A-G])\.")
        else:
            comity = next(i for i, e in enumerate(rows) if text(e) == "NAPARC Golden Rule Comity Agreement")
            transfer = next(i for i, e in enumerate(rows) if text(e) == "NAPARC Agreement on Transfer of Members")
            chapters = {
                "note": chapter("General Assembly note", rows[:comity], r"(?!)"),
                "comity": chapter(text(rows[comity]), rows[comity + 1:transfer], r"(\d+)\.", "Comity."),
                "transfer": chapter(text(rows[transfer]), rows[transfer + 1:], r"(\d+)\.", "Transfer."),
            }
    for data in chapters.values():
        data["title"] = data["title"].upper()
        refs = [section["ref"] for section in data["sections"]]
        assert refs, (key, data["title"])
        seen = set()
        for section in data["sections"]:
            ref = section["ref"]
            while section["ref"] in seen:
                assert key == "bco-subject-index", (key, ref)
                section["ref"] += "-continued"
            seen.add(section["ref"])
    return {
        "format": "pca-constitution-pack", "version": 1, "kind": "book",
        "label": name,
        "notice": f"Official PCA source: {BASE}{slug}/",
        "component": {
            "key": key, "abbr": abbr, "name": name, "division": "supplemental",
            "icon": "scroll", "nonConstitutional": True,
            "tag": "Supplementary PCA material",
            "lede": "Published with the PCA Book of Church Order.",
            "meta": edition,
        },
        "order": list(chapters), "chapters": chapters,
    }


def main():
    write_rao()
    for doc in DOCUMENTS:
        source = subprocess.check_output(["curl", "-fsSL", "--max-time", "30", f"{BASE}{doc[3]}/"])
        pack = build(doc, source.decode("utf-8"))
        output = HERE / "content" / f"{pack['component']['key']}.js"
        output.write_text(
            "/* Generated by build_bco_supplements.py from official PCA sources. */\n"
            "window.BUNDLED_PACKS = window.BUNDLED_PACKS || [];\n"
            f"window.BUNDLED_PACKS.push({json.dumps(pack, ensure_ascii=False, indent=2)});\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
