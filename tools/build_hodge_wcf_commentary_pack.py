#!/usr/bin/env python3
"""Build an importable WCF commentary pack from the Internet Archive hOCR."""

from __future__ import annotations

import argparse
import json
import re
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = Path(r"C:\git\pca-reader-content-packs")
DEFAULT_CLEAN_PADDLE = ROOT / "content" / "hodge-wcf-paddle-ocr.clean.jsonl"
ROMAN = [
    "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X",
    "XI", "XII", "XIII", "XIV", "XV", "XVI", "XVII", "XVIII", "XIX",
    "XX", "XXI", "XXII", "XXIII", "XXIV", "XXV", "XXVI", "XXVII",
    "XXVIII", "XXIX", "XXX", "XXXI", "XXXII", "XXXIII",
]


class HocrParser(HTMLParser):
    """Read OCR paragraphs and lines while retaining page boundaries."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.pages: list[list[str]] = []
        self.page: list[str] | None = None
        self.paragraph: list[list[str]] | None = None
        self.line: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        classes = dict(attrs).get("class", "").split()
        if "ocr_page" in classes:
            self.page = []
            self.pages.append(self.page)
        if self.page is None:
            return
        if "ocr_par" in classes:
            self.paragraph = []
            self.page.append(self.paragraph)
            self.line = None
        if "ocr_line" in classes and self.paragraph is not None:
            self.line = []
            self.paragraph.append(self.line)

    def handle_endtag(self, tag: str) -> None:
        pass

    def handle_data(self, data: str) -> None:
        if self.line is None:
            return
        self.line.append(data)


def read_hocr(path: Path) -> list[list[str]]:
    parser = HocrParser()
    parser.feed(path.read_text(encoding="utf-8"))
    pages: list[list[str]] = []
    for page in parser.pages:
        paragraphs: list[str] = []
        for paragraph in page:
            lines = [" ".join(" ".join(line).split()) for line in paragraph]
            lines = [line for line in lines if line]
            text = join_ocr_lines(lines)
            if text:
                paragraphs.append(correct_ocr_words(text))
        pages.append(paragraphs)
    return pages


# Printed compounds whose hyphen is meaningful even when it falls at a line
# end. Everything else that forms a word across an OCR line break is joined.
KEEP_LINE_HYPHEN = {
    "all", "anti", "cross", "ever", "far", "first", "God", "good", "half",
    "ill", "long", "never", "self", "short", "well", "whole",
}


def join_ocr_lines(lines: list[str]) -> str:
    if not lines:
        return ""
    result = lines[0]
    for following in lines[1:]:
        match = re.search(r"([A-Za-z]+)-$", result)
        next_word = re.match(r"([a-z]+)\b", following)
        if match and next_word and match.group(1) not in KEEP_LINE_HYPHEN:
            result = result[:-1] + following
        else:
            result += " " + following
    return " ".join(result.split())


OCR_WORD_FIXES = {
    "makt": "make",
    "th at": "that",
    "tl/at": "that",
    "foil-owing": "following",
    "pei sons": "persons",
    "princ^les": "principles",
    "j^roprietor": "proprietor",
    "u>e": "use",
    "b^ing": "being",
    "at>": "as",
    "of*": "of",
    "of* the": "of the",
    "each of* the": "each of the",
    "diver* miracles": "divers miracles",
    "crea* tures": "creatures",
    "expe* rience": "experience",
    "impoverish* ing": "impoverishing",
    "submis* oion": "submission",
    "*Tontaineth": "containeth",
    "Ecclesias* ticus": "Ecclesiasticus",
    "a* h": "as his",
    "the* personal": "the personal",
    "the* saints": "the saints",
    "not* revealed": "not revealed",
    "a* hia": "as his",
    "a. their mediatorial Head": "as their mediatorial Head",
    "theirs, a. their": "theirs; as their",
    "be~ both": "be both",
    "new-crer/.ed": "new-created",
    "assli^ance": "assurance",
    "Unregeno^ate": "Unregenerate",
    "B,egeneration": "Regeneration",
    "Bajtrt^o)": "Baptizo",
    "Bcmxco": "Bapto",
    "Danzc^co": "Baptizo",
    "Banze^io": "Baptizo",
    "vcTiTto": "Nipto",
    "deco^": "aion",
    "auoieoz": "aionios",
    "diSioq": "aidios",
    "b^ing.": "being.",
    "b^ing,": "being,",
    "b^ing;": "being;",
    "^he": "the",
    "*he": "the",
    "Th*": "The",
    "^his": "this",
    "^meaning": "meaning",
    "^xxiii": "xxiii",
    "^ood": "good",
    "^he": "the",
    "h*": "he",
    "Chris*": "Christ",
    "oi*": "one of",
    "*all": "all",
    "*are": "are",
    ">ther": "other",
    "<k": "and",
    "i$": "is",
    "Tt has": "It has",
    "And unchangeable": "and unchangeable",
    "brin^": "bring",
    "woiks": "works",
    "sanctifieation": "sanctification",
    "sanctication": "sanctification",
    "unholincss": "unholiness",
    "lawfullyordained": "lawfully-ordained",
    "clrrist": "Christ",
    "helongs": "belongs",
    "inconfnsedly": "inconfusedly",
    "inconvsistent": "inconsistent",
    "natllre": "nature",
    "signifieancy": "significance",
    "tresspasses": "trespasses",
    "tsanctification": "sanctification",
    "wrorks": "works",
    "deeilrute": "destitute",
    "ecelesiastieus": "Ecclesiasticus",
    "ecclesias* ticus": "Ecclesiasticus",
    "argylfc": "Argyll",
    "calvinjst": "Calvinist",
    "presbvterianisw": "Presbyterianism",
    "churcl": "church",
    "glorjt": "glory",
    "glorjT": "glory",
    "agreee": "agree",
    "tilings": "things",
    "withdrawraent": "withdrawal",
    "pmishment": "punishment",
    "zommands": "commands",
    "righteousuess": "righteousness",
    "agerii": "agent",
    "doctiine": "doctrine",
    "iScjiptures": "Scriptures",
    "ivill-worsliiii": "will-worship",
    "sancti-l jfication": "sanctification",
    "anides": "abides",
    "Tesiament": "Testament",
    "Cbrict": "Christ",
    "(i. &.,": "(i.e.,",
    "thfe": "the",
    "hi our stead": "in our stead",
    "hi our stead": "in our stead",
    "first- born": "first-born",
    "(<?.)": "(c.)",
    "(<:?.)": "(c.)",
    "(6.)": "(b.)",
    "tliat": "that",
    "nearts": "hearts",
    "vitnesseth": "witnesseth",
    "of^ baptism": "of baptism",
    "^his": "this",
    "fch»s": "these",
    "ob»": "obligation",
    "la\\^": "law",
    "tru<»": "true",
    "na\xab": "nations",
    "\xbbfi": "in",
    "\xbbnan": "a man",
    "\xbb": "",
    "«": "",
    "�": "",
    "■": "",
    "�": "",
    "transient^": "transient,",
    "la\\\\^": "law",
    "wln^h": "which",
    "\\\\s": "is",
    "sJ'.^ce": "since",
    "ttJ-^": "the",
    "\xbbfi": "in",
    "\xbbnan": "a man",
    "na\xab": "nations",
    "an\xab other": "another",
    "between^": "between",
    "(>f": "of",
    "(2.^": "(2.)",
    "(\xab.)": "(a.)",
    "(\xab)": "(a)",
    "\xabiiat": "that",
    "\xab2": "§ 2",
    "\xa73:": "§ 3:",
    "\xa7\xa71,2": "§§ 1, 2",
    "th*": "the",
    "*t3": "the",
    "<: /": "(d.)",
    "(<:/.)": "(d.)",
    "(<:/.)": "(d.)",
    "(/.)": "(f.)",
    "CREATION. \\\\ 1 J": "CREATION.",
    "Rom. ix. 17, 22, 23 > Eph.": "Rom. ix. 17, 22, 23; Eph.",
    "new-cieate": "new-create",
    "oi* these": "one of these",
    "e.y": "e.g.",
    "e.t": "e.g.",
    "g.f": "e.g.",
}


def correct_ocr_words(text: str) -> str:
    for wrong, right in OCR_WORD_FIXES.items():
        # Allow punctuation or a footnote marker after a corrupted token, while
        # keeping replacements from matching inside ordinary words.
        text = re.sub(rf"(?<!\w){re.escape(wrong)}(?!\w)", right, text, flags=re.I)
    text = re.sub(r"\b(?:e\.y|e\.t|g\.f)\b", "e.g.", text, flags=re.I)
    text = text.translate(str.maketrans({"«": None, "»": None, "�": None, "■": None, "•": None}))
    text = re.sub(r"\(\s*<\??:\.?\s*\)", "(c.)", text)
    text = text.replace("(<?.)", "(c.)").replace("(<:?.)", "(c.)")
    return text


def roman_number(value: str) -> int:
    # OCR commonly reads the three final I strokes in XXVIII as `Ili`.
    if value.isdigit():
        return int(value)
    value = value.replace("T", "I").replace("t", "I")
    value = value.replace("l", "I").replace("L", "I").replace("]", "I").replace("J", "I").upper()
    total = 0
    previous = 0
    values = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}
    for char in reversed(value):
        amount = values[char]
        total += -amount if amount < previous else amount
        previous = max(previous, amount)
    return total


def is_page_furniture(text: str, first: bool, last: bool) -> bool:
    value = " ".join(text.split())
    if last and re.fullmatch(r"\d{1,4}", value):
        return True
    if len(value) < 70 and "CONFESSION" in value.upper() and "FAITH" in value.upper():
        return True
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 .,'-]{2,55}\. ?\d{1,4}", value):
        return True
    if len(value) < 8 and "�" in value:
        return True
    if first and (re.fullmatch(r"\d{1,4}\s+[^.]{1,55}\.?", value)
                  or re.fullmatch(r"[A-Z0-9][A-Z0-9 .,'-]{2,55}\.?\s+\d{1,4}", value)
                  or re.fullmatch(r"\d{1,4}\s+CONFESSION OF FAITH\.?", value, re.I)
                  or value.lower() in {"confession of faith", "confession of faith.", "holy scripture."}):
        return True
    return False


def load_wcf(wcf_path: Path) -> tuple[dict[str, list[str]], dict[int, str]]:
    source = wcf_path.read_text(encoding="utf-8")
    data = json.loads(source.split("=", 1)[1].strip().rstrip(";"))
    return ({
        chapter: [section["ref"] for section in chapter_data["sections"]]
        for chapter, chapter_data in data.items()
    }, {int(chapter): chapter_data["title"] for chapter, chapter_data in data.items()})


def chapter_ranges(
    pages: list[list[str]],
    titles: dict[int, str],
    section_counts: dict[int, int] | None = None,
) -> list[tuple[int, int, str]]:
    # Flatten paragraph text but retain start offsets for source chapter headings.
    cleaned: list[str] = []
    for page in pages:
        visible = [p for i, p in enumerate(page) if not is_page_furniture(p, True, True)]
        cleaned.extend(visible)
    text = "\n".join(cleaned)
    heading_re = re.compile(r"(?im)^\s*CHAPTER\s+([IVXLCil]+)[.:'’\"]*\s*$")
    starts: dict[int, int] = {}
    title_stop = {"of", "the", "and", "a", "an", "to", "in", "on", "with", "unto"}
    for match in heading_re.finditer(text):
        roman = match.group(1).replace("l", "I").upper()
        try:
            number = roman_number(roman)
        except KeyError:
            continue
        if not 1 <= number <= 33 or number in starts:
            continue
        context = text[match.end():match.end() + 180].lower()
        wanted = [w for w in re.findall(r"[a-z]+", titles[number].lower()) if w not in title_stop]
        found = sum(bool(re.search(rf"\b{re.escape(word[:5])}", context)) for word in wanted)
        min_hits = min(len(wanted), max(1, (len(wanted) + 1) // 2))
        # Some first sections include a long quoted confession, Scripture
        # proofs, and commentary before the section boundary is legible to OCR.
        has_printed_section = bool(SECTION_START.search(text, match.end(), match.end() + 6000))
        one_section_chapter = section_counts is not None and section_counts.get(number) == 1
        if wanted and found >= min_hits and (has_printed_section or one_section_chapter):
            starts[number] = match.start()
    # The introductory history chapters precede WCF chapter I. The first actual
    # chapter I heading is the one whose following text names Holy Scripture.
    candidates = [m for m in heading_re.finditer(text)
                  if roman_number(m.group(1)) == 1 and starts.get(1) == m.start()]
    if candidates:
        starts[1] = candidates[0].start()
    ranges: list[tuple[int, int, str]] = []
    previous = -1
    for n in range(1, 34):
        candidate = starts.get(n)
        if candidate is None or candidate <= previous:
            # Search forward for the next correctly numbered chapter heading.
            match = next(
                (m for m in heading_re.finditer(text, previous + 1)
                 if roman_number(m.group(1)) == n),
                None,
            )
            if match:
                candidate = match.start()
        if candidate is not None and candidate > previous:
            previous = candidate
            ranges.append((n, candidate, text))
        else:
            raise ValueError(f"Could not locate the source heading for WCF chapter {n}")
    result = []
    for index, (n, start, full_text) in enumerate(ranges):
        end = ranges[index + 1][1] if index + 1 < len(ranges) else len(full_text)
        result.append((start, end, full_text[start:end]))
    return result


COMMENTARY_START = re.compile(
    r"\b(?:This|These)\s+(?:Section|Sections|Chapter)\s+"
    r"[,;:]?\s*(?:teaches?|teach|affirms?|affirm|asserts?|assert|states?|state|are|taken|proceed|"
    r"particularize|shows?|show|following|the|what|as|sets?\s+forth|"
    r"contains?|necessarily|establishes?)\b",
    re.I,
)
SECTION_START = re.compile(
    r"\b(?:Section|S\w{2,8})"
    r"\s+([IVXLCil\]JTt]+|\d{1,2})\s*\.?\s*[—–-]",
    re.I,
)
QUESTIONS = re.compile(r"\bQUESTIONS\s*\.", re.I)


def proof_paragraph(text: str) -> bool:
    value = text.strip()
    reference_numbers = len(re.findall(r"\b\d{1,2}\b", value))
    return len(value) > 45 and reference_numbers >= 4 and value.count(";") >= 2


def commentary_after_proofs(text: str, start: int, end: int) -> int | None:
    paragraphs = list(re.finditer(r"[^\n]+", text[start:end]))
    for index, paragraph in enumerate(paragraphs):
        if not proof_paragraph(paragraph.group()):
            continue
        for following in paragraphs[index + 1:]:
            value = following.group().strip()
            if not value or proof_paragraph(value):
                continue
            if value.startswith("QUESTIONS"):
                return None
            return start + following.start()
    return None


def extract_chapter(chapter_text: str, refs: list[str]) -> tuple[dict[str, list[str]], list[str]]:
    marks = list(SECTION_START.finditer(chapter_text))
    mapped: dict[str, list[str]] = {ref: [] for ref in refs}
    assigned: set[str] = set()
    if not marks and len(refs) == 1:
        start = commentary_after_proofs(chapter_text, 0, len(chapter_text))
        if start is not None:
            block = chapter_text[start:]
            q = QUESTIONS.search(block)
            if q:
                block = block[:q.start()]
            paras = [" ".join(p.split()) for p in block.splitlines() if p.strip()]
            mapped[refs[0]] = paras
            if paras:
                assigned.add(refs[0])
        return mapped, [ref for ref in refs if ref not in assigned]
    pending: list[str] = []
    active_refs: list[str] = []
    active_start: int | None = None
    active_end = len(chapter_text)

    def flush(end: int) -> None:
        nonlocal active_start, active_refs
        if active_start is None or not active_refs:
            return
        block = chapter_text[active_start:end]
        q = QUESTIONS.search(block)
        if q:
            block = block[:q.start()]
        paras = [" ".join(p.split()) for p in block.splitlines()]
        paras = [p for p in paras if p and not re.fullmatch(r"\d{1,4}\s+[^.]{1,55}\.?", p)]
        paras = [p for p in paras if not re.fullmatch(r"\d{1,4}", p)]
        for ref in active_refs:
            mapped[ref].extend(paras)
            if paras:
                assigned.add(ref)
        active_start = None
        active_refs = []

    for i, mark in enumerate(marks):
        # Finish exposition for the preceding section group at the next printed
        # section heading. A chapter can print several sections before one joint
        # exposition, so collect their refs until an exposition marker appears.
        if active_start is not None:
            flush(mark.start())
        roman = mark.group(1).upper()
        try:
            section_no = roman_number(roman)
        except KeyError:
            continue
        if 1 <= section_no <= len(refs):
            pending.append(refs[section_no - 1])
        next_end = marks[i + 1].start() if i + 1 < len(marks) else len(chapter_text)
        cue = COMMENTARY_START.search(chapter_text, mark.end(), next_end)
        start = cue.start() if cue else commentary_after_proofs(chapter_text, mark.end(), next_end)
        if start is not None and pending:
            active_refs = list(dict.fromkeys(pending))
            pending.clear()
            active_start = start

    # Commentary after the last printed section can run to the end of chapter.
    if active_start is not None:
        flush(active_end)
    # Some closing exposition is introduced by a chapter level cue; attach it to
    # the final section when a chapter has no later printed section heading.
    if pending:
        tail = chapter_text[marks[-1].end():] if marks else ""
        cue = COMMENTARY_START.search(tail)
        if cue and refs:
            block = tail[cue.start():]
            q = QUESTIONS.search(block)
            if q:
                block = block[:q.start()]
            paras = [" ".join(p.split()) for p in block.splitlines() if p.strip()]
            mapped[refs[-1]].extend(paras)
            if paras:
                assigned.add(refs[-1])
    return mapped, [ref for ref in refs if ref not in assigned]


def read_clean_paddle_pages(path: Path) -> list[list[str]]:
    pages: list[list[str]] = []
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                record = json.loads(line)
                pages.append(record["paragraphs"])
    return pages


def build(source_dir: Path, output: Path, clean_paddle: Path = DEFAULT_CLEAN_PADDLE) -> tuple[int, list[str]]:
    if clean_paddle.exists():
        pages = read_clean_paddle_pages(clean_paddle)
    else:
        pages = read_hocr(source_dir / "commentaryonconf00hodg_hocr.html")
    section_refs, titles = load_wcf(ROOT / "content" / "wcf.js")
    section_counts = {int(chapter): len(refs) for chapter, refs in section_refs.items()}
    ranges = chapter_ranges(pages, titles, section_counts)
    entries: dict[str, list[str]] = {}
    missing: list[str] = []
    for index, (start, end, text) in enumerate(ranges, start=1):
        refs = section_refs[str(index)]
        chapter_entries, absent = extract_chapter(text, refs)
        entries.update(chapter_entries)
        missing.extend(absent)

    pack = {
        "format": "pca-constitution-pack",
        "version": 1,
        "kind": "commentary",
        "label": "A. A. Hodge — Commentary on the Westminster Confession",
        "notice": "Archibald Alexander Hodge, A Commentary on the Confession of Faith, with Questions for Theological Students and Bible Classes (Philadelphia, 1901), public domain. OCR generated from Internet Archive scan commentaryonconf00hodg.pdf with PaddleOCR 3.7.0 / PP-OCRv6 medium and PaddlePaddle 3.2.2 at 300 dpi; recurring running heads and folios removed. OCR has not been fully proofread against page images.",
        "corpus": "wcf",
        "entries": {key: value for key, value in entries.items() if value},
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(pack, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return len(pack["entries"]), missing


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--clean-paddle", type=Path, default=DEFAULT_CLEAN_PADDLE)
    parser.add_argument("--output", type=Path, default=ROOT / "content" / "hodge-wcf-commentary.pack.json")
    args = parser.parse_args()
    count, missing = build(args.source_dir, args.output, args.clean_paddle)
    print(f"Wrote {args.output}; {count} refs populated; {len(missing)} refs have no detected commentary.")
    if missing:
        print("Unmapped refs:", ", ".join(missing))


if __name__ == "__main__":
    main()
