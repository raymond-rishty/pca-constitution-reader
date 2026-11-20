#!/usr/bin/env python3
"""Compare the bundled English BCO with the official 2026 PDF."""

import argparse
import difflib
import hashlib
import html
import importlib.util
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUOTES = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"'})


def visible(text):
    # Explicit HTML list values preserve the printed item numbers in Appendix H.
    text = re.sub(r'<li value="(\d+)">', r'\1. ', text)
    return " ".join(html.unescape(re.sub(r"<[^>]+>", "", text)).split())


def comparable(text):
    text = visible(text).translate(QUOTES)
    text = re.sub(r"\s*[-–—]+\s*", "-", text)
    return text.replace("…", "...").replace("appellant/ complainant", "appellant/complainant")


def assignment(script, name):
    return json.JSONDecoder().raw_decode(script.split(f"window.{name} = ", 1)[1])[0]


def sections(entries):
    return {item["ref"]: item for entry in entries.values() for item in entry.get("sections", [])}


def move_note(provisions, source_ref, target_ref, pattern, number=None):
    source = provisions[source_ref]
    body = source["body"]
    match = re.search(pattern, body)
    if not match:
        raise ValueError(f"{source_ref}: missing note in the PDF extraction")
    source["body"] = " ".join((body[:match.start()] + body[match.end():]).split())
    target = provisions[target_ref]
    if number:
        target["body"] = re.sub(rf"(Ordination|Congregation|Installation|proceedings\.)\s+{number}\b",
                                rf"\g<1>{number}", target["body"])
    prefix = f"{number} " if number else ""
    target["body"] += " " + prefix + match.group(1)


def arrange_pdf(entries, text):
    """Account for page furniture, footnotes, and multi-column reading order."""
    provisions = sections(entries)
    for key in ("23", "34", "39"):
        entry = entries[key]
        entry["title"] += " " + entry.pop("paras")[0]
    for key in ("5", "19", "24", "56"):
        entries[key]["sections"][0]["heading"] = entries[key].pop("paras")[0]
    for source_ref, target_ref in (("5-8", "5-9"), ("19-6", "19-7"), ("24-5", "24-6")):
        body, heading = re.split(r" (?=(?:B\. (?:The Organization|Internship)|Ordination and Installation))",
                                 provisions[source_ref]["body"])
        provisions[source_ref]["body"] = body
        provisions[target_ref]["heading"] = heading
    for key in ("pref-1", "pref-2", "pref-3"):
        entry = entries[key]
        entry["paras"][0] = entry["paras"][0].upper()
    move_note(provisions, "13-10", "13-9", r'\s+(\* Editor\x27s note: "Issue" means "[^"]+")')
    move_note(provisions, "14-6", "14-6", r'\s+(\* Editor\x27s note: [^*]+?case"\.)')
    move_note(provisions, "15-5", "15-5", r'\s+(\*NOTE: .*? \b41-1\.)')
    for number, source_ref, target_ref in (
        (1, "21-5", "21-5"), (2, "21-7", "21-5"), (3, "21-10", "21-7"),
        (4, "21-10", "21-8"), (5, "21-10", "21-9"),
    ):
        move_note(provisions, source_ref, target_ref,
                  rf"\s+{number}\s*(For (?:an )?assistant minister[^.]+\.)", number)
    provisions["58-4"]["body"] = provisions["58-4"]["body"].replace("Corin-thians", "Corinthians")
    body, appendices_note = provisions["63-6"]["body"].split(" APPENDICES Appendices ", 1)
    provisions["63-6"]["body"] = body
    entries["appA"]["paras"].insert(0, appendices_note)
    for letter, title in re.findall(r"^\s*Appendix ([A-J]): ([^\n]+)$", text, re.M):
        entries[f"app{letter}"]["title"] = f"Appendix {letter} — {title.strip()}"
    app_g = entries["appG"]["paras"]
    # The extractor treats the continuation of Appendix G's title as a running head.
    app_g[0] += " RULES OF DISCIPLINE"
    entries["appG"]["paras"] = [p + "." if re.fullmatch(r"I|II|III|IV|V|VI", p) else p for p in app_g]
    chart = entries["appH"]["paras"]
    chart_start = next(i for i, p in enumerate(chart) if p.startswith("Pres bytery A ppoints"))
    del chart[chart_start:]  # Page 231 is a figure, checked against the SVG visually.
    app_j = entries["appJ"]["paras"]
    row = next(i for i, p in enumerate(app_j) if p.startswith("Minister's Salary "))
    columns = re.fullmatch(
        r"(Minister's Salary) (Taxable Salary) (Housing Allowance \(Partially Taxable Salary\)) "
        r"• (Taxable for Self-Employment Tax purposes) • (Taxable only for Self-Employment Tax) "
        r"• (Taxable for Federal Income Tax purposes) (purposes)", app_j[row])
    title, taxable, housing, employment, housing_employment, federal, continuation = columns.groups()
    app_j[row:row + 1] = [title, taxable, employment, federal, housing, housing_employment + " " + continuation]


def compare(reader, reader_order, source, source_order, amendments):
    problems = []

    def check(label, actual, expected):
        if actual == expected:
            return
        delta = difflib.ndiff(actual.split(), expected.split())
        changes = " ".join(token for token in delta if token.startswith(("- ", "+ ")))
        problems.append(f"{label}: {changes}")

    check("entry order", " ".join(reader_order), " ".join(source_order))
    check("entry keys", " ".join(sorted(reader)), " ".join(sorted(source)))
    for key in source_order:
        if key not in reader:
            problems.append(f"{key}: missing entry")
            continue
        actual, expected = reader[key], source[key]
        check(f"{key} part", actual["part"], expected["part"])
        check(f"{key} vacated", str(bool(actual.get("vacated"))), str(bool(expected.get("vacated"))))
        a, b = (comparable(entry["title"]) for entry in (actual, expected))
        if actual["part"] == "appx":
            a, b = a.casefold(), b.casefold()
        check(f"{key} title", a, b)
        a = comparable(" ".join(actual.get("paras", [])))
        b = comparable(" ".join(expected.get("paras", [])))
        if key == "appI":  # Poppler collapses and interleaves the signature columns.
            b = re.sub(r"(Name)( Parent's or Guardian's Signature) \(for minors\)", r"\1 (for minors)\2", b)
            a, b = (re.sub(r" +,", ",", re.sub(r"\s*_+\s*", " ", value)) for value in (a, b))
        check(f"{key} prose", a, b)
        a, b = (" ".join(p["ref"] for p in entry.get("sections", [])) for entry in (actual, expected))
        check(f"{key} provision order", a, b)
    actual_sections, expected_sections = sections(reader), sections(source)
    for ref, expected in expected_sections.items():
        actual = actual_sections.get(ref)
        if not actual:
            continue
        check(f"{ref} heading", comparable(actual.get("heading", "")), comparable(expected.get("heading", "")))
        check(ref, comparable(actual["body"]), comparable(expected["body"]))
        if "blocks" in actual:
            block_text = " ".join(" ".join(block[2:]) for block in actual["blocks"])
            check(f"{ref} blocks", visible(block_text), visible(actual["body"]))
    if missing := set(amendments) - expected_sections.keys():
        problems.append(f"Amendments missing from the extraction: {sorted(missing)}")
    return problems


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--builder", type=Path, required=True,
                        help="Path to pca-reader-content-packs/tools/build_bco_edition.py")
    parser.add_argument("--reader", type=Path, default=ROOT / "content/bco.js")
    args = parser.parse_args()
    script = args.reader.read_text(encoding="utf-8")
    metadata = assignment(script, "BCO_ENGLISH_EDITION")
    digest = hashlib.sha256(args.pdf.read_bytes()).hexdigest()
    if metadata["year"] != 2026 or digest != metadata["sha256"]:
        raise SystemExit(f"Expected the audited 2026 PDF. Received SHA-256 {digest}.")

    spec = importlib.util.spec_from_file_location("edition_builder", args.builder.resolve())
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    text = builder.extract_text(args.pdf)
    assembly = re.search(r"Includes all amendments approved up to and including\s+the (\d+\w+ General Assembly)", text)
    if not assembly or assembly.group(1) != metadata["assembly"]:
        raise SystemExit("The English BCO assembly metadata disagrees with the PDF cover.")
    amendments = re.search(r"^2026\s+–\s+BCO (.*?)\s*; RAO\b", text, re.M | re.S)
    amendment_refs = re.findall(r"\b\d+-\d+\b", amendments.group(1))
    # The printed 56-6 opener has no period. Preserve the separate provision.
    source, order, _ = builder.chapter_records(re.sub(r"^(56-6)(\s+Then the minister)", r"\1.\2", text, flags=re.M))
    arrange_pdf(source, text)
    reader = assignment(script, "BCO")
    problems = compare(reader, assignment(script, "BCO_ORDER"), source, order, amendment_refs)
    if problems:
        raise SystemExit("\n".join(problems))
    print(f"Matched {len(order)} ordered entries and {len(sections(source))} numbered provisions.")
    print("2026 amendment references:", ", ".join(amendment_refs))


if __name__ == "__main__":
    main()
