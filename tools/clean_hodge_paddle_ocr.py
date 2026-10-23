#!/usr/bin/env python3
"""Remove recurring page furniture and make readable text from Hodge Paddle OCR."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

from build_hodge_wcf_commentary_pack import correct_ocr_words


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "content" / "hodge-wcf-paddle-ocr.pages.jsonl"
DEFAULT_JSONL = ROOT / "content" / "hodge-wcf-paddle-ocr.clean.jsonl"
DEFAULT_TEXT = ROOT / "content" / "hodge-wcf-paddle-ocr.clean.txt"
PAGE_LABELS = {"page", "pagb", "pagc"}
KEEP_LINE_HYPHEN = {
    "all", "anti", "cross", "ever", "far", "first", "God", "good", "half",
    "ill", "long", "never", "self", "short", "well", "whole",
}


def normalized_header(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def normalize_chapter_heading(text: str) -> str:
    match = re.fullmatch(
        r"C\s*H\s*A\s*P\s*T\s*E\s*R[_\s]*([IVXLC\s]+)[.:'’\"]*",
        text.strip(),
        re.I,
    )
    if match:
        roman = re.sub(r"\s+", "", match.group(1)).upper()
        if roman:
            return f"CHAPTER {roman}."
    return text


def load_pages(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def find_recurring_headers(pages: list[dict]) -> set[str]:
    counts: Counter[str] = Counter()
    for page in pages:
        height = page["height"]
        for line in page["lines"]:
            text = line["text"].strip()
            x0, y0, x1, y1 = line["box"]
            normalized = normalized_header(text)
            if not normalized or len(text) > 90 or y1 / height > 0.28:
                continue
            if text.isupper() and not re.fullmatch(r"\d{1,4}", text):
                counts[normalized] += 1
    return {text for text, count in counts.items() if count >= 3}


def is_furniture(line: dict, page: dict, recurring: set[str]) -> str | None:
    text = line["text"].strip()
    x0, y0, x1, y1 = line["box"]
    height = page["height"]
    normalized = normalized_header(text)
    chapter_text = normalize_chapter_heading(text)
    if re.fullmatch(r"CHAPTER\s+[IVXLC]+[.:'’\"]*", chapter_text, re.I):
        # Keep genuine chapter-opening headings even if the OCR also sees the
        # same short string in contents or as a running head elsewhere.
        has_title_below = any(
            other is not line
            and 0 <= other["box"][1] - y1 <= height * 0.12
            and re.match(r"^(?:OF|THE)\s+[A-Z]", other["text"].strip(), re.I)
            for other in page["lines"]
        )
        if has_title_below:
            return None
    if re.fullmatch(r"\d{1,4}", text) and (y1 / height <= 0.12 or y0 / height >= 0.90):
        return "folio"
    if normalized in PAGE_LABELS and y1 / height <= 0.28:
        return "page-column-label"
    if normalized in recurring and text.isupper() and y1 / height <= 0.28:
        return "repeated-running-head"
    return None


def join_lines(lines: list[dict]) -> str:
    if not lines:
        return ""
    text = lines[0]["text"].strip()
    for line in lines[1:]:
        following = line["text"].strip()
        match = re.search(r"([A-Za-z]+)-$", text)
        next_word = re.match(r"([a-z]+)\b", following)
        if match and next_word and match.group(1) not in KEEP_LINE_HYPHEN:
            text = text[:-1] + following
        else:
            text += " " + following
    text = correct_ocr_words(" ".join(text.split()))
    text = normalize_chapter_heading(text)
    text = re.sub(r"\bCHAPTER[_\s]*(?=[IVXLC]+\b)", "CHAPTER ", text, flags=re.I)
    text = re.sub(r"\bS\w{2,8}\b(?=\s+[IVXLC1l]+\s*[.\-—–])", "Section", text, flags=re.I)
    return text


def page_paragraphs(page: dict, recurring: set[str]) -> tuple[list[str], list[dict]]:
    ordered = sorted(page["lines"], key=lambda item: (item["box"][1], item["box"][0]))
    kept: list[dict] = []
    removed: list[dict] = []
    for line in ordered:
        reason = is_furniture(line, page, recurring)
        if reason:
            removed.append({"text": line["text"], "box": line["box"], "reason": reason})
        elif line["text"].strip():
            kept.append(line)

    if not kept:
        return [], removed
    width = page["width"]
    # The first quartile approximates the left text edge without being pulled
    # toward centered chapter headings or indented first lines.
    left_edges = sorted(line["box"][0] for line in kept)
    body_left = left_edges[max(0, (len(left_edges) - 1) // 4)]
    indent_limit = body_left + max(20, int(width * 0.018))
    line_heights = [max(1, line["box"][3] - line["box"][1]) for line in kept]
    normal_height = sorted(line_heights)[len(line_heights) // 2]

    groups: list[list[dict]] = []
    current: list[dict] = []
    for line in kept:
        x0, y0, _x1, _y1 = line["box"]
        starts_item = bool(re.match(
            r"^(?:Section\s|QUESTIONS\b|\(?\d{1,2}(?:st|nd|rd|th)?[.)]|\([a-z][.)])",
            line["text"].strip(), re.I,
        ))
        new_paragraph = False
        if current:
            previous = current[-1]
            gap = y0 - previous["box"][3]
            new_paragraph = (
                x0 > indent_limit
                or gap > normal_height * 0.7
                or (starts_item and line["text"].strip() != current[0]["text"].strip())
            )
        if new_paragraph:
            groups.append(current)
            current = []
        current.append(line)
    if current:
        groups.append(current)
    paragraphs = [joined for group in groups if (joined := join_lines(group))]
    return paragraphs, removed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--jsonl", type=Path, default=DEFAULT_JSONL)
    parser.add_argument("--text", type=Path, default=DEFAULT_TEXT)
    args = parser.parse_args()

    pages = load_pages(args.input)
    recurring = find_recurring_headers(pages)
    args.jsonl.parent.mkdir(parents=True, exist_ok=True)
    args.text.parent.mkdir(parents=True, exist_ok=True)
    removed_counts: Counter[str] = Counter()
    with args.jsonl.open("w", encoding="utf-8", newline="\n") as jsonl, \
            args.text.open("w", encoding="utf-8", newline="\n") as text_file:
        for page in pages:
            paragraphs, removed = page_paragraphs(page, recurring)
            for item in removed:
                removed_counts[item["reason"]] += 1
            jsonl.write(json.dumps({
                "page": page["page"],
                "paragraphs": paragraphs,
                "removed": removed,
            }, ensure_ascii=False, separators=(",", ":")) + "\n")
            text_file.write(f"\n\n[PDF page {page['page']}]\n")
            for paragraph in paragraphs:
                text_file.write(paragraph + "\n\n")

    print(f"Cleaned {len(pages)} OCR pages; recurring headers: {len(recurring)}")
    print("Removed line counts:", json.dumps(dict(removed_counts), sort_keys=True))
    print("Running heads:", "; ".join(sorted(recurring)))
    print(f"Wrote {args.jsonl} and {args.text}")


if __name__ == "__main__":
    main()
