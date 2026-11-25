"""Bundle BSB passages cited in the reader's built-in document text."""
import argparse
from collections import defaultdict
from html import unescape
from itertools import chain
import json
from pathlib import Path
import re

from build_content import BOOK, BSB_URL, fetch

CONTENT = Path(__file__).resolve().parent / "content"
SPANISH = {
    "Genesis": "Génesis Gen", "Numbers": "Números", "1 Chronicles": "1 Crónicas",
    "Psalm": "Salmo Salmos", "Proverbs": "Proverbios", "Ecclesiastes": "Eclesiastés",
    "Isaiah": "Isaías", "Matthew": "Mateo Mat", "Mark": "Marcos", "John": "Juan",
    "Acts": "Hechos", "Romans": "Romanos", "1 Corinthians": "1 Corintios",
    "2 Corinthians": "2 Corintios", "Galatians": "Gálatas", "Ephesians": "Efesios Ef",
    "Philippians": "Filipenses Fil", "1 Thessalonians": "1 Tesalonicenses",
    "1 Timothy": "1 Timoteo", "2 Timothy": "2 Timoteo", "Titus": "Tito",
    "Hebrews": "Hebreos", "1 Peter": "1 Pedro", "2 Peter": "2 Pedro", "Revelation": "Apocalipsis",
}
KOREAN = {
    "Genesis": "창 창세기", "Numbers": "민 민수기", "2 Samuel": "삼하 사무엘하",
    "1 Chronicles": "대상 역대상", "Job": "욥 욥기", "Psalm": "시 시편",
    "Proverbs": "잠 잠언", "Ecclesiastes": "전 전도서", "Isaiah": "사 이사야",
    "Matthew": "마 마태복음", "Mark": "막 마가복음", "John": "요 요한복음", "Acts": "행 사도행전",
    "Romans": "롬 로마서", "1 Corinthians": "고전 고린도전서", "2 Corinthians": "고후 고린도후서",
    "Galatians": "갈 갈라디아서", "Ephesians": "엡 에베소서", "Philippians": "빌 빌립보서",
    "Colossians": "골 골로새서", "1 Thessalonians": "살전 데살로니가전서",
    "1 Timothy": "딤전 디모데전서", "2 Timothy": "딤후 디모데후서", "Titus": "딛 디도서",
    "Hebrews": "히 히브리서", "1 Peter": "벧전 베드로전서", "Revelation": "계 계시록 요한계시록",
}


def book_aliases():
    aliases = dict(BOOK)
    for alias, canonical in BOOK.items():
        if alias[:2] in ("1 ", "2 ", "3 "):
            aliases[("i" * int(alias[0])) + alias[1:]] = canonical
    for canonical, names in SPANISH.items():
        for alias in re.findall(r"(?:[1-3] )?\S+", names):
            aliases[alias.lower()] = canonical
    for canonical, names in KOREAN.items():
        aliases.update(dict.fromkeys(names.split(), canonical))
    return aliases


def reading_text():
    decoder = json.JSONDecoder()
    for path in sorted(CONTENT.glob("*.js")) + sorted((CONTENT / "translations").glob("*.js")):
        src = path.read_text(encoding="utf-8")
        assignment = re.search(r"window\.(?:BCO|WCF|WLC|WSC)\s*=\s*|window\.BUNDLED_PACKS\.push\(\s*|const pack=", src)
        if not assignment:
            continue
        data, _ = decoder.raw_decode(src[assignment.end():])
        if isinstance(data, list):
            for question in data:
                yield question.get("q", "")
                yield question.get("a", "")
            continue
        if data.get("kind") == "book":
            data = data["chapters"]
        for chapter in data.values():
            if not isinstance(chapter, dict):
                continue
            yield from chapter.get("paras", [])
            for section in chapter.get("sections", []):
                if section.get("blocks"):
                    yield from (block[-1] for block in section["blocks"])
                else:
                    yield section.get("body", "")


def build(source):
    bible = defaultdict(list)
    for line in source.splitlines():
        ref, _, text = line.partition("\t")
        if match := re.fullmatch(r"(.+) (\d+):(\d+)", ref.strip()):
            bible[match[1]].append((int(match[2]), int(match[3]), text.strip()))
    if len(bible) != 66:
        raise ValueError(f"Expected 66 BSB books, found {len(bible)}")
    aliases = book_aliases()
    names = "|".join(re.escape(name).replace(r"\ ", r"\s+") for name in sorted(aliases, key=len, reverse=True))
    # An explicit book and chapter can stand alone or introduce an optional verse list.
    end = r"(?:\d+\s*:\s*)?\d+"
    verse_range = rf"\d+(?:\s*[-–—]\s*{end})?"
    citation = re.compile(
        rf"(?<!\w)({names})\.?\s*(\d+)(?:\s*:\s*({verse_range}(?:\s*,\s*{verse_range})*))?"
        r"(?![\w:]|\s*[:–—-]|\s*,\s*\d)", re.IGNORECASE,
    )
    korean_names = "|".join(sorted((alias for alias in aliases if re.search("[가-힣]", alias)), key=len, reverse=True))
    korean_citation = re.compile(
        rf"(?<!\w)({korean_names})\s*(\d+)\s*장(?:\s*({verse_range})\s*절|(?!\s*\d))"
    )
    references, verses = {}, {}
    for fragment in reading_text():
        text = unescape(re.sub(r"<[^>]*>", "", fragment))
        for match in chain(citation.finditer(text), korean_citation.finditer(text)):
            book = aliases[" ".join(match[1].lower().split())]
            chapter = int(match[2])
            chapter_rows = [row for row in bible[book] if row[0] == chapter]
            if not chapter_rows:
                continue
            verse_list = match[3]
            passages = [] if verse_list else [(chapter_rows[0][:2], chapter_rows[-1][:2])]
            for part in verse_list.split(",") if verse_list else ():
                first, *last = re.split(r"\s*[-–—]\s*", part.strip())
                start = (chapter, int(first))
                endpoint = tuple(map(int, last[0].split(":"))) if last else start
                if len(endpoint) == 1:
                    endpoint = (chapter, endpoint[0])
                passages.append((start, endpoint))
            keys = []
            for start, endpoint in passages:
                rows = [(c, v, verse) for c, v, verse in bible[book] if start <= (c, v) <= endpoint]
                if not rows or rows[0][:2] != start or rows[-1][:2] != endpoint:
                    keys = []
                    break
                for c, v, verse in rows:
                    key = f"{book} {c}:{v}"
                    keys.append(key)
                    verses[key] = verse
            if keys:
                references[" ".join(match[0].lower().split())] = list(dict.fromkeys(keys))
    return {"references": references, "verses": verses}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bsb", type=Path, help="Use a local copy of the BSB tab-separated text.")
    args = parser.parse_args()
    data = build(args.bsb.read_text(encoding="utf-8-sig") if args.bsb else fetch(BSB_URL))
    payload = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    (CONTENT / "inline-scripture.js").write_text(
        "/* Generated by build_inline_scripture.py. Berean Standard Bible (public domain). */\n"
        f"window.INLINE_SCRIPTURE = {payload};\n", encoding="utf-8",
    )
    print(f"Bundled {len(data['references'])} citation forms and {len(data['verses'])} verses.")
