#!/usr/bin/env python3
"""Geometry-aware WCF proof parser.
Separates body text / footnotes / markers by font height.

Height bands (WCF-specific — different from Catechisms!):
  11.5-11.6pt = body section text
   8.0-8.1pt  = superscript markers (a, b, c...) within body lines
   9.0-9.3pt  = footnote labels (a., b.) + footnote verse text
                  ALSO running headers (CHAPTER N, THE CONFESSION OF FAITH, page nums) — skip these
  13.0-14.0pt = chapter headings (Chapter 1 ... Chapter 33) — extract chapter number
   6.5pt      = 'ord'/'od' artifacts from 'Lord' rendering — ignore
"""
import re, html as H, subprocess, sys, json

# ---- helpers from bbox_parse.py ----
WORD = re.compile(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">([^<]*)</word>')
LET = 'abcdefghiklmnopqrstuwxyz'   # skip j and v
PRIMES = "´ʹ′'ʼ"

def band(h):
    """Classify word height into band."""
    if 11.3 <= h <= 11.7: return 'body'
    if  7.9 <= h <=  8.2: return 'mark'   # superscript marker letter in body text
    if  9.0 <= h <=  9.4: return 'foot'   # footnote text/labels + running headers
    if 13.0 <= h <= 14.0: return 'head'   # chapter headings (Chapter N)
    return 'other'

def bbox_xml(pdf):
    return subprocess.run(['pdftotext', '-bbox-layout', pdf, '-'],
                          capture_output=True, text=True).stdout

# Running header patterns at 9.0-9.3pt to skip
HEADER = re.compile(r'CONFESSION OF FAITH|^CHAPTER\s+\d+$|^THE\s+CONFESSION|^\d+$')
CHAPTER_HEAD = re.compile(r'^Chapter\s+(\d+)$')  # 13.5pt chapter heading

BOOKS = (r'Gen|Exod|Ex|Lev|Num|Deut|Josh|Judg|Ruth|1 Sam|2 Sam|1 Kings|2 Kings'
         r'|1 Chron|2 Chron|Ezra|Neh|Esth|Est|Job|Ps|Prov|Eccl|Cant|Isa|Jer|Lam'
         r'|Ezek|Dan|Hos|Joel|Amos|Obad|Jonah|Mic|Nah|Hab|Zeph|Hag|Zech|Mal'
         r'|Matt|Mark|Luke|John|Acts|Rom|1 Cor|2 Cor|Gal|Eph|Phil|Col'
         r'|1 Thess|2 Thess|1 Tim|2 Tim|Titus|Philem|Heb|James|1 Pet|2 Pet'
         r'|1 John|2 John|3 John|Jude|Rev')
REF = re.compile(rf'\b({BOOKS})\.?\s+(\d+:\d+(?:[–-]\d+(?::\d+)?)?(?:,\s*\d+(?:[–-]\d+)?)*)')

def extract_refs(text):
    """Extract Bible references, preserving 'See' and 'With' prefixes."""
    flat = re.sub(r'\s+', ' ', text)
    flat = re.sub(r'(\d)\s*[–-]\s*(\d)', r'\1–\2', flat)   # tighten ranges
    flat = re.sub(r'(\d):\s+(\d)', r'\1:\2', flat)          # "3: 16" -> "3:16"
    refs = []
    for m in REF.finditer(flat):
        start = m.start()
        # Look back up to 15 chars for 'See' or 'With' prefix
        prefix_text = flat[max(0, start - 15):start]
        prefix = ''
        if re.search(r'\bSee\s*$', prefix_text):
            prefix = 'See '
        elif re.search(r'\bWith\s*$', prefix_text):
            prefix = 'With '
        refs.append(f'{prefix}{m.group(1)} {m.group(2)}')
    return refs


def lines_in_order(xml):
    """
    Yield per line: list of (band, text, is_line_first) triples.
    Also yields ('chapter_head', N) tuples for 13.5pt Chapter N lines.
    Running headers in 'foot' band are yielded as ('header', text).
    """
    out = []
    for lm in re.finditer(r'<line[^>]*>(.*?)</line>', xml, re.S):
        ws = [(band(float(m.group(4)) - float(m.group(2))), H.unescape(m.group(5)))
              for m in WORD.finditer(lm.group(1))]
        if not ws:
            continue
        # Detect 13.5pt chapter heading
        if ws[0][0] == 'head':
            text = ' '.join(w for _, w in ws)
            cm = CHAPTER_HEAD.match(text)
            if cm:
                out.append(('chapter_head', int(cm.group(1))))
            # skip other head lines (chapter titles like "Of the Holy Scripture")
            continue
        # Detect running header in foot band
        if ws[0][0] == 'foot':
            text = ' '.join(w for _, w in ws)
            if HEADER.search(text):
                out.append(('header', text))
                continue
        # Normal content line: attach is_line_first flag
        out.append(('line', [(b, t, j == 0) for j, (b, t) in enumerate(ws)]))
    return out


def parse_wcf(pdf):
    """
    Parse WCF PDF. Returns:
      sections: dict keyed by "chap.sec" -> {'ans_tokens': [...], 'markers': [...]}
      footnotes: list of {'label': str, 'text': str}
      markers: list of (letter, "chap.sec") in reading order
    """
    xml = bbox_xml(pdf)
    events = lines_in_order(xml)

    LABEL = re.compile(rf'^([{LET}][{PRIMES}]*)\.$')
    SEC_START = re.compile(r'^(\d+)\.$')

    cur_chap = 0
    cur_sec = None
    sections = {}   # "chap.sec" -> list of ('w'|'m', text)
    markers = []    # [(letter, "chap.sec"), ...]

    # --- Pass 1: extract body tokens + markers, track chapters + sections ---
    for ev in events:
        if ev[0] == 'chapter_head':
            cur_chap = ev[1]
            cur_sec = None
            continue
        if ev[0] == 'header':
            # Extract chapter number from running header if present (backup)
            hm = re.search(r'CHAPTER\s+(\d+)', ev[1])
            if hm and cur_chap == 0:
                cur_chap = int(hm.group(1))
            continue
        if ev[0] != 'line':
            continue
        ws = ev[1]  # list of (band, text, is_line_first)

        for b, t, first in ws:
            if b == 'body':
                # Check if this is a section start: first word of line is "N."
                if first and SEC_START.match(t):
                    sec_n = int(SEC_START.match(t).group(1))
                    cur_sec = f'{cur_chap}.{sec_n}'
                    sections.setdefault(cur_sec, [])
                if cur_sec:
                    sections[cur_sec].append(('w', t))
            elif b == 'mark':
                # Superscript marker in body text
                if re.fullmatch(rf'[{LET}][{PRIMES}]*', t):
                    markers.append((t, cur_sec))
                    if cur_sec:
                        sections[cur_sec].append(('m', t))

    # --- Pass 2: extract footnotes, segmented by line-first labels, guided by marker sequence ---
    expected = [lt for lt, _ in markers]
    footnotes = []
    fi = 0

    for ev in events:
        if ev[0] != 'line':
            continue
        ws = ev[1]
        for b, t, first in ws:
            if b != 'foot':
                continue
            lm = LABEL.match(t)
            if lm and first and fi < len(expected) and lm.group(1) == expected[fi]:
                footnotes.append({'label': lm.group(1), 'text': ''})
                fi += 1
            elif footnotes:
                footnotes[-1]['text'] += ' ' + t

    return markers, footnotes, sections


def build_ans(tokens, sec_id):
    """
    Reconstruct answer text from token list.
    - Strip leading section number 'N.'
    - Insert <sup>letter</sup> markers glued to preceding word (no space before)
    - Rejoin soft-hyphen breaks: word- nextword -> wordnextword
    """
    parts = []
    first_word = True
    for kind, t in tokens:
        if kind == 'w':
            if first_word and re.match(r'^\d+\.$', t):
                # Strip leading section number
                first_word = False
                continue
            first_word = False
            parts.append(t)
        elif kind == 'm':
            sup = f'<sup>{t}</sup>'
            if parts:
                parts[-1] = parts[-1] + sup
            else:
                parts.append(sup)

    # Join with spaces
    ans = ' '.join(parts)
    # Rejoin soft-hyphen line breaks: "word- nextword" -> "wordnextword"
    ans = re.sub(r'(\w)-\s+(\w)', r'\1\2', ans)
    return ans


def build_groups(markers, footnotes, sections):
    """
    Zip markers <-> footnotes (k-th <-> k-th).
    Return per-section groups list: [["a", "ref1, ref2"], ...]
    """
    fn_refs = []
    for fn in footnotes:
        refs = extract_refs(fn['text'])
        # Preserve 'See ' and 'With ' prefixes from footnote text
        # build ref string: comma-joined
        fn_refs.append(refs)

    sec_groups = {}  # "chap.sec" -> list of [label, ref_str]
    n = min(len(markers), len(footnotes))
    for k in range(n):
        letter, sec = markers[k]
        refs = fn_refs[k]
        ref_str = ', '.join(refs) if refs else ''
        if sec not in sec_groups:
            sec_groups[sec] = []
        sec_groups[sec].append([letter, ref_str])
    return sec_groups


def build_output(pdf_path):
    markers, footnotes, sections = parse_wcf(pdf_path)

    sec_groups = build_groups(markers, footnotes, sections)

    result = {}
    for sec_id, tokens in sections.items():
        ans = build_ans(tokens, sec_id)
        groups = sec_groups.get(sec_id, [])
        result[sec_id] = {'ans': ans, 'groups': groups}

    return result, markers, footnotes, sections


# ---- Validation ----
def validate(result, markers, footnotes, sections):
    print("=== WCF VALIDATION ===\n")

    # 1. Chapter and section structure
    chap_secs = {}
    for k in result:
        c, s = k.split('.')
        chap_secs.setdefault(int(c), []).append(int(s))

    chapters = sorted(chap_secs.keys())
    print(f"1. Chapter count: {len(chapters)} (expected 33)")
    anomalies = []
    for c in chapters:
        secs = sorted(chap_secs[c])
        expected_seq = list(range(1, len(secs) + 1))
        if secs != expected_seq:
            anomalies.append(f"Ch.{c}: got {secs}, expected {expected_seq}")
    if anomalies:
        print(f"   ANOMALIES: {anomalies}")
    else:
        print(f"   All chapters have sequential sections (no anomalies)")
    print(f"   Total sections: {sum(len(v) for v in chap_secs.values())}")

    # 2. Markers vs footnotes
    nm = len(markers)
    nf = len(footnotes)
    print(f"\n2. Markers: {nm}, Footnotes: {nf} (match={nm==nf})")
    # Check label sequence
    seq_breaks = []
    fi = 0
    for k, (mlabel, msec) in enumerate(markers):
        if fi < len(footnotes):
            flabel = footnotes[fi]['label']
            if mlabel != flabel:
                seq_breaks.append(f"  k={k}: marker[{mlabel}]@{msec} vs footnote[{flabel}]")
            fi += 1
    if seq_breaks:
        print(f"   SEQUENCE BREAKS:\n" + '\n'.join(seq_breaks[:10]))
    else:
        print(f"   Label sequence: all {nm} agree perfectly")

    # 3. Zero-ref footnotes
    zero_ref = []
    for k, fn in enumerate(footnotes):
        refs = extract_refs(fn['text'])
        if not refs:
            zero_ref.append(f"  fn[{k}] label={fn['label']} text={fn['text'][:60]!r}")
    if zero_ref:
        print(f"\n3. Zero-ref footnotes ({len(zero_ref)}):")
        for z in zero_ref:
            print(z)
    else:
        print(f"\n3. All {nf} footnotes have ≥1 ref")

    # 4. Spot-checks
    print("\n4. SPOT-CHECKS:")
    for spot in ['1.1', '1.2', '21.1']:
        if spot in result:
            r = result[spot]
            print(f"\n--- {spot} ---")
            print(f"ANS: {r['ans'][:300]}")
            print(f"GROUPS ({len(r['groups'])}):")
            for g in r['groups']:
                print(f"  [{g[0]}] {g[1]}")
        else:
            print(f"\n--- {spot} NOT FOUND ---")

    # Find last section of ch.33
    ch33_secs = sorted([int(s) for s in chap_secs.get(33, [])])
    if ch33_secs:
        last_sec = f"33.{ch33_secs[-1]}"
        r = result.get(last_sec, {})
        print(f"\n--- {last_sec} (last section of ch.33) ---")
        print(f"ANS: {r.get('ans','NOT FOUND')[:300]}")
        print(f"GROUPS ({len(r.get('groups',[]))}):")
        for g in r.get('groups', []):
            print(f"  [{g[0]}] {g[1]}")

    # 5. Sections with 0 markers
    zero_mark = [sid for sid, r in result.items() if not r['groups']]
    print(f"\n5. Sections with 0 markers: {len(zero_mark)}")
    if zero_mark:
        for z in sorted(zero_mark, key=lambda x: (int(x.split('.')[0]), int(x.split('.')[1]))):
            print(f"   {z}")

    print(f"\nTotal section count: {len(result)}")


if __name__ == '__main__':
    pdf = 'pca_wcf.pdf'
    print(f"Parsing {pdf}...")
    result, markers, footnotes, sections = build_output(pdf)

    out_path = 'wcf_proofs.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"Written {out_path} ({len(result)} sections)\n")

    validate(result, markers, footnotes, sections)
