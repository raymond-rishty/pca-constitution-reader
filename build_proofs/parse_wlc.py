#!/usr/bin/env python3
"""Geometry-aware WLC proof parser.
Extends bbox_parse.py technique to the Westminster Larger Catechism (196 Qs),
split across pca_lc.pdf (Q1-115) and lc2.pdf (Q114-196).

Design notes:
- POSITIONAL matching: k-th marker in PDF = k-th footnote in PDF.
  The strict sequence-guided check from bbox_parse.py fails because lc2.pdf
  has one footnote labeled 'j.' (body marker 'i') at position 81 — a PDF defect.
- Primed markers (a´, b´, ...) appear when a single question exceeds 24 footnotes.
  They are single bbox words in the mark-band (h≈6.46pt), the same band as unprimed.
- The label sequence is GLOBAL and continuous across all questions within each PDF,
  but the specific letter used at any position depends on where the global counter
  stands when that question starts. Questions that need >24 markers continue with
  primed versions of whatever comes next (not necessarily a').
- Footnote labels are per-page; the PDF uses lowercase letter + dot as label openers.
  We allow any lowercase letter (not just LET) to tolerate the 'j.' defect.
"""
import re, html as H, subprocess, json

# ── height bands (same as bbox_parse.py) ─────────────────────────────────────
def band(h):
    if 8.4 <= h <= 10.0: return 'body'
    if 7.0 <= h < 8.0:   return 'foot'
    if 5.8 <= h < 7.0:   return 'mark'
    return 'other'

WORD = re.compile(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">([^<]*)</word>')

# Valid marker letters: a..z skip j,v, plus optional prime chars
LET    = 'abcdefghiklmnopqrstuwxyz'
PRIMES = "´ʹ′'ʼ"
MARKER_RE = re.compile(rf'^([{LET}][{PRIMES}]*)$')

# Footnote label: any lowercase letter + optional primes + required dot.
# (Any lowercase letter, not just LET, to tolerate the 'j.' defect in lc2.pdf)
LABEL_RE = re.compile(rf'^[a-z][{PRIMES}]*\.')

def bbox_xml(pdf):
    return subprocess.run(['pdftotext', '-bbox-layout', pdf, '-'],
                          capture_output=True, text=True).stdout

HEADER = re.compile(r'LARGER CATECHISM|SHORTER CATECHISM|CONFESSION OF FAITH')

def is_section_heading(ws):
    """Detect WLC section headings like 'WHAT MAN OUGHT TO BELIEVE CONCERNING GOD'.
    These are rendered in small-caps: first letter of each word is body-band, rest mark-band.
    Detection: all body-band tokens are single uppercase letters, and there are at least 2."""
    body_tokens = [t for b, t, _ in ws if b == 'body']
    return (len(body_tokens) >= 2 and
            all(len(t) == 1 and t.isupper() for t in body_tokens))

def lines_in_order(xml):
    """Return per-line list of (band, text, is_line_first). Skip running headers and
    WLC section headings."""
    out = []
    for lm in re.finditer(r'<line[^>]*>(.*?)</line>', xml, re.S):
        ws = []
        for j, m in enumerate(WORD.finditer(lm.group(1))):
            h = float(m.group(4)) - float(m.group(2))
            t = H.unescape(m.group(5))
            ws.append((band(h), t, j == 0))
        if not ws:
            continue
        if HEADER.search(' '.join(t for _, t, _ in ws)):
            continue
        if re.fullmatch(r'\d{1,4}', ''.join(t for _, t, _ in ws).strip()):
            continue   # bare page-number line (running-header page number on its own bbox line)
        if is_section_heading(ws):
            continue
        out.append(ws)
    return out

# ── reference extraction ──────────────────────────────────────────────────────
BOOKS = (r'Gen|Exod|Ex|Lev|Num|Deut|Josh|Judg|Ruth|1 Sam|2 Sam|1 Kings|2 Kings'
         r'|1 Chron|2 Chron|Ezra|Neh|Esth|Est|Job|Ps|Prov|Eccl|Cant|Isa|Jer|Lam'
         r'|Ezek|Dan|Hos|Joel|Amos|Obad|Jonah|Mic|Nah|Hab|Zeph|Hag|Zech|Mal'
         r'|Matt|Mark|Luke|John|Acts|Rom|1 Cor|2 Cor|Gal|Eph|Phil|Col'
         r'|1 Thess|2 Thess|1 Tim|2 Tim|Titus|Philem|Heb|James|1 Pet|2 Pet'
         r'|1 John|2 John|3 John|Jude|Rev')
REF = re.compile(rf'\b({BOOKS})\.?\s+(\d+:\d+(?:[–-]\d+(?::\d+)?)?(?:,\s*\d+(?:[–-]\d+)?)*(?:ff)?)')

# Single-chapter books cited as 'Book verse' (no chapter notation): 3 John 12 -> 3 John 1:12
SINGLE_CHAP_RE = re.compile(rf'\b(Obad|Philem|Jude|2 John|3 John)\.?\s+(\d+(?:[–-]\d+)?(?:,\s*\d+)*)')

# Whole psalm reference: 'Ps. 145' (no verse) -> 'Ps 145:1'
# Negative lookahead for digit prevents 'Ps. 86' matching in 'Ps. 86:9'
PS_WHOLE_RE = re.compile(r'\bPs\.?\s+(\d+)(?!\d)(?!\s*:)')

def extract_refs(text):
    flat = re.sub(r'\s+', ' ', text)
    flat = re.sub(r'(\d)\s*[–-]\s*(\d)', r'\1–\2', flat)
    flat = re.sub(r'(\d):\s+(\d)', r'\1:\2', flat)
    refs = [f'{m.group(1)} {m.group(2)}' for m in REF.finditer(flat)]
    # Single-chapter books without chapter prefix
    for m in SINGLE_CHAP_RE.finditer(flat):
        r = f'{m.group(1)} 1:{m.group(2)}'
        if r not in refs:
            refs.append(r)
    # Whole psalm citations (no verse number)
    for m in PS_WHOLE_RE.finditer(flat):
        r = f'Ps {m.group(1)}:1'
        if r not in refs:
            refs.append(r)
    return refs


# ── core parser ───────────────────────────────────────────────────────────────
def parse_catechism(pdf):
    """
    Returns:
        markers   : list of (letter, question_key) — in reading order
        footnotes : list of {'label': str, 'text': str}
        answers   : dict question_key -> list of ('w', word) | ('m', letter)

    Footnotes are POSITIONALLY matched (k-th footnote = k-th marker), not by label.
    This is robust to the single 'j' label defect in lc2.pdf pos 81.
    """
    lines = lines_in_order(bbox_xml(pdf))

    # Pass 1: body/mark scan
    markers = []
    answers = {}
    cur_q = None
    flat = [(b, t, first) for ws in lines for b, t, first in ws]
    n = len(flat)
    for k, (b, t, first) in enumerate(flat):
        if b == 'body':
            if re.fullmatch(r'Q\.?', t) and k + 1 < n:
                mn = re.match(r'(\d+)\.?', flat[k + 1][1])
                if mn:
                    cur_q = f'Q.{mn.group(1)}'
                    answers.setdefault(cur_q, [])
            if cur_q:
                answers[cur_q].append(('w', t))
        elif b == 'mark' and MARKER_RE.match(t):
            markers.append((t, cur_q))
            if cur_q:
                answers[cur_q].append(('m', t))

    # Pass 2: positional footnote collection.
    # New footnote: line whose FIRST word is foot-band AND matches label pattern.
    # Continuation lines: accumulate foot-band words into current footnote.
    footnotes = []
    for ws in lines:
        b0, t0, _ = ws[0]
        if b0 == 'foot' and LABEL_RE.match(t0):
            lbl = t0.rstrip('.')
            text = ' '.join(ti for bi, ti, _ in ws[1:] if bi == 'foot')
            footnotes.append({'label': lbl, 'text': text})
        else:
            if footnotes:
                for bi, ti, _ in ws:
                    if bi == 'foot':
                        footnotes[-1]['text'] += ' ' + ti

    return markers, footnotes, answers


# ── sequence validation ───────────────────────────────────────────────────────
LET_LIST = list(LET)
PRIMES_CHARS = list(PRIMES)

def letter_idx(lbl):
    base = lbl.rstrip(''.join(PRIMES_CHARS))
    primes = lbl[len(base):]
    bi = LET_LIST.index(base) if base in LET_LIST else -1
    return (len(primes), bi)

def check_q_sequences(q_markers_dict, name):
    """Check per-question marker ordering. Returns list of error strings."""
    errors = []
    for q in sorted(q_markers_dict.keys(), key=lambda x: int(x[2:])):
        mlist = q_markers_dict[q]
        if len(mlist) < 2:
            continue
        for i in range(1, len(mlist)):
            prev_pl, prev_li = letter_idx(mlist[i-1])
            curr_pl, curr_li = letter_idx(mlist[i])
            ok = False
            if curr_pl == prev_pl:
                # Same prime level, consecutive
                if curr_li == prev_li + 1:
                    ok = True
                # Same prime level, wrap z->a
                elif prev_li == len(LET_LIST) - 1 and curr_li == 0:
                    ok = True
            elif curr_pl == prev_pl + 1:
                # Overflow to next prime level: same base letter advances
                if curr_li == (prev_li + 1) % len(LET_LIST):
                    ok = True
            elif curr_pl == prev_pl - 1:
                # Return from primed to unprimed (can happen between questions' boundaries
                # due to cross-page layout; not an error per se)
                ok = True
            if not ok:
                errors.append(f'  {q} pos {i}: {mlist[i-1]!r} -> {mlist[i]!r}')
    return errors


# ── answer reconstruction ─────────────────────────────────────────────────────
def build_answer(tokens):
    """Build answer string. Skip everything before 'A.', then:
    - words separated by spaces
    - markers glued to preceding word as <sup>LETTER</sup>
    """
    result = []
    found_a = False
    for kind, text in tokens:
        if not found_a:
            if kind == 'w' and re.fullmatch(r'A\.?', text):
                found_a = True
            continue  # skip Q. N. ...? prefix
        result.append((kind, text))

    out = ''
    for kind, text in result:
        if kind == 'w':
            if out:
                out += ' '
            out += text
        else:
            out += f'<sup>{text}</sup>'
    return out.strip()


# ── main ──────────────────────────────────────────────────────────────────────
def main():
    PART1_PDF = 'pca_lc.pdf'  # Q1–115 (Q114 overlaps)
    PART2_PDF = 'lc2.pdf'     # Q114–196 (Q113-115 overlaps)

    print('=== Parsing part1 (pca_lc.pdf) ===')
    m1, f1, a1 = parse_catechism(PART1_PDF)
    print(f'  markers={len(m1)}  footnotes={len(f1)}  questions={len(a1)}')

    print('=== Parsing part2 (lc2.pdf) ===')
    m2, f2, a2 = parse_catechism(PART2_PDF)
    print(f'  markers={len(m2)}  footnotes={len(f2)}  questions={len(a2)}')

    # ── count checks ──────────────────────────────────────────────────────
    print(f'\nPart1: markers={len(m1)}, footnotes={len(f1)}, delta={len(m1)-len(f1)}')
    print(f'Part2: markers={len(m2)}, footnotes={len(f2)}, delta={len(m2)-len(f2)}')

    # ── label/marker agreement (positional) ───────────────────────────────
    agree1 = sum(1 for k in range(min(len(m1), len(f1))) if m1[k][0] == f1[k]['label'])
    agree2 = sum(1 for k in range(min(len(m2), len(f2))) if m2[k][0] == f2[k]['label'])
    n1p = min(len(m1), len(f1)); n2p = min(len(m2), len(f2))
    print(f'\nPart1 label/marker positional agreement: {agree1}/{n1p}')
    print(f'Part2 label/marker positional agreement: {agree2}/{n2p}')
    if agree2 < n2p:
        print(f'  Part2 mismatches:')
        for k in range(n2p):
            if m2[k][0] != f2[k]['label']:
                print(f'    pos {k}: marker={m2[k][0]!r} label={f2[k]["label"]!r} q={m2[k][1]}')

    # ── per-question sequence check ───────────────────────────────────────
    from collections import defaultdict
    def q_marker_dict(markers):
        d = defaultdict(list)
        for ml, q in markers:
            if q:
                d[q].append(ml)
        return d

    qm1 = q_marker_dict(m1)
    qm2 = q_marker_dict(m2)

    print('\n=== Per-question marker sequence ===')
    se1 = check_q_sequences(qm1, PART1_PDF)
    se2 = check_q_sequences(qm2, PART2_PDF)
    if se1:
        print(f'Part1 sequence breaks ({len(se1)}):')
        for e in se1: print(e)
    else:
        print(f'Part1: no per-question sequence breaks')
    if se2:
        print(f'Part2 sequence breaks ({len(se2)}):')
        for e in se2: print(e)
    else:
        print(f'Part2: no per-question sequence breaks')

    # ── ref extraction ────────────────────────────────────────────────────
    refs1 = [extract_refs(f['text']) for f in f1]
    refs2 = [extract_refs(f['text']) for f in f2]

    zero1 = [(k, f1[k]['label'], f1[k]['text'][:70].strip()) for k in range(len(f1)) if not refs1[k]]
    zero2 = [(k, f2[k]['label'], f2[k]['text'][:70].strip()) for k in range(len(f2)) if not refs2[k]]
    print(f'\nPart1 zero-ref footnotes: {len(zero1)}')
    for k, lbl, txt in zero1:
        print(f'  [{k}] {lbl!r}: {txt!r}')
    print(f'Part2 zero-ref footnotes: {len(zero2)}')
    for k, lbl, txt in zero2:
        print(f'  [{k}] {lbl!r}: {txt!r}')

    # ── build per-question groups ─────────────────────────────────────────
    def build_qgroups(markers, refs):
        qgroups = {}
        for k in range(min(len(markers), len(refs))):
            letter, q = markers[k]
            if q:
                qgroups.setdefault(q, []).append([letter, ', '.join(refs[k])])
        return qgroups

    qg1 = build_qgroups(m1, refs1)
    qg2 = build_qgroups(m2, refs2)

    # ── merge: part1 Q1–113, part2 Q114–196 ──────────────────────────────
    result = {}
    for q, tokens in a1.items():
        if int(q[2:]) <= 113:
            result[q] = {'ans': build_answer(tokens), 'groups': qg1.get(q, [])}
    for q, tokens in a2.items():
        if int(q[2:]) >= 114:
            result[q] = {'ans': build_answer(tokens), 'groups': qg2.get(q, [])}

    # ── validation: question count & gaps ────────────────────────────────
    print('\n=== Final merged result ===')
    q_nums = sorted(int(q[2:]) for q in result)
    print(f'Total questions: {len(result)}')
    missing = sorted(set(range(1, 197)) - set(q_nums))
    extra   = sorted(set(q_nums) - set(range(1, 197)))
    if missing:
        print(f'MISSING: {missing}')
    else:
        print('No missing questions (Q.1–Q.196 complete).')
    if extra:
        print(f'EXTRA: {extra}')

    # ── questions with 0 markers ──────────────────────────────────────────
    no_mark = [q for q in sorted(result, key=lambda x: int(x[2:])) if not result[q]['groups']]
    print(f'\nQuestions with 0 proof groups: {len(no_mark)}')
    for q in no_mark:
        print(f'  {q}')

    # ── spot checks ───────────────────────────────────────────────────────
    print('\n=== Spot checks ===')
    for qk in ['Q.1', 'Q.5', 'Q.50', 'Q.150', 'Q.196']:
        if qk not in result:
            print(f'\n{qk}: MISSING')
            continue
        d = result[qk]
        ans_disp = d['ans'][:180] + ('...' if len(d['ans']) > 180 else '')
        print(f'\n{qk}:')
        print(f'  ans: {ans_disp}')
        print(f'  groups ({len(d["groups"])}):')
        for g in d['groups']:
            print(f'    {g[0]}: {g[1]}')

    # ── write output ──────────────────────────────────────────────────────
    out_path = 'wlc_proofs.json'
    with open(out_path, 'w', encoding='utf-8') as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)
    print(f'\nWrote {out_path}')
    total_groups = sum(len(d['groups']) for d in result.values())
    print(f'Part1 groups: {sum(len(v) for v in qg1.values())}')
    print(f'Part2 groups: {sum(len(v) for v in qg2.values())}')
    print(f'Total groups across all 196 Qs: {total_groups}')


if __name__ == '__main__':
    main()
