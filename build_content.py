#!/usr/bin/env python3
"""
build_content.py — source the PCA Constitution's doctrinal standards into the
app's content files. Public-domain Westminster texts only (WCF/WLC/WSC); the
BCO is handled separately and kept private (not published).

Output: planning/content/<name>.js  — each defines a global the reader loads via
a <script src> tag (works from file://, unlike fetch()).

Sources (OPC edition = the same standard the PCA has adopted):
  WSC  https://www.opc.org/sc.html
  WLC  https://www.opc.org/lc.html      (added later)
  WCF  https://www.opc.org/wcf.html     (added later)

Usage:  python3 build_content.py wsc
"""
import difflib, html, json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "content")
SOURCES = {
    "wsc": "https://www.opc.org/sc.html",
    "wlc": "https://www.opc.org/lc.html",
    "wcf": "https://www.opc.org/wcf.html",
}
# BCO (personal use only — © PCA, do NOT publish). HTML base text from pcaac.org per-part pages.
BCO_PARTS = [
    ("fog", "Form of Government",              "https://www.pcaac.org/book-of-church-order/part-1-the-form-of-government/"),
    ("rod", "Rules of Discipline",             "https://www.pcaac.org/book-of-church-order/part-2-the-rules-of-discipline/"),
    ("dow", "Directory for the Worship of God","https://www.pcaac.org/book-of-church-order/part-3-the-directory-for-the-worship-of-god/"),
]
# Directory authority (BCO Preface / 3rd-GA statement): binding = chapters 56-58 + section 59-3; rest advisory.
def bco_binding(part, ch, ref):
    return part == "dow" and (ch in ("56", "57", "58") or ref == "59-3")

def fetch(url):
    # curl works in this sandbox where Python's urllib rejects the proxy cert
    r = subprocess.run(["curl", "-sS", "-m", "30", "-A", "constitution-reader/0.1 (personal study)", url],
                       capture_output=True)
    if r.returncode != 0:
        sys.exit(f"fetch failed ({url}): {r.stderr.decode('utf-8', 'replace').strip()}")
    try:
        return r.stdout.decode("utf-8")
    except UnicodeDecodeError:
        return r.stdout.decode("cp1252", "replace")   # pcahistory pages are Windows-1252

def clean(s):
    s = re.sub(r"<br\s*/?>", " ", s)
    s = re.sub(r"<[^>]+>", "", s)          # strip any stray tags
    s = html.unescape(s).replace("’", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", s).strip()

def strip_tags(s): return re.sub(r"<[^>]+>", "", s)

def _balance(s):
    """Drop orphan </b>/</i> (no matching open) and any unclosed open — e.g. a heading's
    bold that got cut by a section slice leaves a stray </b>."""
    out=[]; opens=[]
    for tok in re.split(r"(</?[bi]>)", s):
        if tok in ("<b>","<i>"): opens.append(len(out)); out.append(tok)
        elif tok in ("</b>","</i>"):
            want="<"+tok[2]+">"
            for k in range(len(opens)-1,-1,-1):
                if out[opens[k]]==want: out.append(tok); del opens[k]; break
            # else: orphan close -> drop
        else: out.append(tok)
    for k in opens: out[k]=""                     # remove unclosed opens
    return "".join(out)

def clean_fmt(s):
    """Like clean(), but keep inline emphasis: <strong>/<b> -> <b>, <em>/<i> -> <i>."""
    s = re.sub(r"<br\s*/?>", " ", s)
    s = re.sub(r"</?(?:strong|b)\b[^>]*>", lambda m: "</b>" if m.group(0)[1]=="/" else "<b>", s, flags=re.I)
    s = re.sub(r"</?(?:em|i)\b[^>]*>",     lambda m: "</i>" if m.group(0)[1]=="/" else "<i>", s, flags=re.I)
    s = re.sub(r"<(?!/?[bi]>)[^>]*>", "", s)                 # strip every tag except <b></b><i></i>
    s = html.unescape(s).replace("’", "'").replace("“", '"').replace("”", '"')
    s = re.sub(r"\s+", " ", s)
    for _ in range(4):                                       # merge split emphasis, drop empties (keep inner whitespace)
        s2 = s.replace("</b><b>", "").replace("</i><i>", "")
        s2 = re.sub(r"<([bi])>(\s*)</\1>", r"\2", s2)
        if s2 == s: break
        s = s2
    return _balance(s).strip()

def build_catechism(name):
    src = fetch(SOURCES[name])
    # question marker: <p>Q. N. <i>question</i><br />.  The answer is everything up to the next
    # question (WLC answers can span multiple <p>/lists, so we slice rather than match one <p>).
    qpat = re.compile(r"<p>\s*Q\.\s*(\d+)\.\s*(.*?)<br\s*/?>", re.S)   # question = up to first <br>, tags stripped later
    marks = list(qpat.finditer(src))
    assert marks and int(marks[0].group(1)) == 1, "parse failed: no Q.1"
    items = []
    for i, m in enumerate(marks):
        n = int(m.group(1))
        if i + 1 < len(marks):
            end = marks[i + 1].start()
        else:  # last answer: stop at the close of the content block, not the page footer
            d = src.find("</div>", m.end()); end = d if d != -1 else len(src)
        a = re.sub(r"^A\.\s*", "", clean(src[m.end():end]))
        items.append({"id": f"{name}/{n}", "n": n, "q": clean(m.group(2)), "a": a})
    nums = [it["n"] for it in items]
    missing = [x for x in range(1, len(items) + 1) if x not in set(nums)]
    assert nums == list(range(1, len(items) + 1)), f"non-contiguous Q numbers; missing {missing[:8]}"
    return items

def build_wcf():
    src = fetch(SOURCES["wcf"])
    # chapter heading: <h3><a name="Chapter_21"></a>CHAPTER 21<br /><i>Title</i></h3>
    chap = re.compile(r'<h3[^>]*><a name="Chapter_(\d+)"></a>CHAPTER\s+\d+<br\s*/?>\s*<i>(.*?)</i>\s*</h3>', re.S)
    marks = list(chap.finditer(src))
    assert marks, "parse failed: no chapter headings"
    sec = re.compile(r"<p>(\d+)\.\s*(.*?)</p>", re.S)   # numbered sections within a chapter
    out = {}
    for i, m in enumerate(marks):
        ch = int(m.group(1)); title = clean(m.group(2))
        end = marks[i+1].start() if i+1 < len(marks) else len(src)
        sections = [{"ref": f"{ch}.{int(s.group(1))}", "n": int(s.group(1)), "body": clean(s.group(2))}
                    for s in sec.finditer(src[m.end():end])]
        assert sections, f"chapter {ch} has no sections"
        out[str(ch)] = {"title": title, "sections": sections}
    assert len(out) == 33, f"expected 33 chapters, got {len(out)}"
    return out

_ONES = "ZERO ONE TWO THREE FOUR FIVE SIX SEVEN EIGHT NINE TEN ELEVEN TWELVE THIRTEEN FOURTEEN FIFTEEN SIXTEEN SEVENTEEN EIGHTEEN NINETEEN".split()
_TENS = {"TWENTY": 20, "THIRTY": 30, "FORTY": 40, "FIFTY": 50, "SIXTY": 60}
def w2n(words):
    w = words.strip().upper().replace("–", "-")
    if w in _ONES:
        return _ONES.index(w)
    p = w.split("-")
    if p[0] in _TENS:
        return _TENS[p[0]] + (_ONES.index(p[1]) if len(p) > 1 else 0)
    raise ValueError(f"unparseable chapter number: {words!r}")

def build_bco():
    # tokens in document order: chapter heading (registers the chapter, incl. vacated ones),
    # chapter title (<h4><i>…</i>), or a numbered section start (<b>NN-S</b>).
    # tokens: chapter heading (spelled number); chapter title (<h4> inner, tags stripped);
    # section = a <p> that BEGINS with "NN-S." (number may be wrapped in any mix of <b>/<strong>/<span>).
    # A section opener may live in a <p> OR an <h4> (chapter-opening sections like
    # 27-1 are styled as headings), and the number itself may have stray spaces or
    # tags inside it ("35- 5 ."). Try the section pattern before the generic <h4>
    # title so heading-styled sections aren't swallowed as titles.
    _gap = r'(?:\s|<[^>]+>|&nbsp;)*'
    tok = re.compile(
        r'<h2[^>]*>\s*CHAPTER\s+([A-Z–\-]+)\s*</h2>'                          # 1: chapter heading
        rf'|<(?:p|h4)[^>]*>{_gap}(\d+){_gap}-{_gap}(\d+[A-Za-z]?){_gap}\.'    # 2,3: section NN-S
        r'|<h4[^>]*>(.*?)</h4>',                                              # 4: chapter title
        re.S | re.I)
    chapters = {}
    for part, _name, url in BCO_PARTS:
        src = fetch(url)
        marks = list(tok.finditer(src))
        cur = None
        for i, m in enumerate(marks):
            if m.group(1) is not None:                                  # chapter heading
                cur = w2n(m.group(1))
                chapters.setdefault(str(cur), {"part": part, "title": "", "sections": []})
                continue
            if m.group(4) is not None:                                  # chapter title
                t = clean(m.group(4))
                if cur and not chapters[str(cur)]["title"] and t:
                    chapters[str(cur)]["title"] = t
                continue
            ch = int(m.group(2))                                        # numbered section
            if ch != cur:
                continue                                                # cross-reference, not a section header
            ref = f"{ch}-{m.group(3)}"
            end = marks[i + 1].start() if i + 1 < len(marks) else len(src)
            body = clean(src[m.end():end]).strip()
            sec = {"ref": ref, "body": body}
            if part == "dow":
                sec["binding"] = bco_binding(part, str(ch), ref)
            chapters[str(cur)]["sections"].append(sec)
    for k, c in chapters.items():
        if not c["sections"] and not c["title"]:
            c["title"] = "(Vacated)"
        c["vacated"] = not c["sections"]
    nums = sorted(int(k) for k in chapters)
    assert nums == list(range(1, 64)), f"BCO chapters not 1..63: {len(nums)} found ({nums[:3]}…{nums[-3:]})"
    # completeness guard: within a chapter, sections run 1..N with no holes. An
    # interior gap means a section was dropped during extraction (e.g. an <h4>
    # opener or a number rendered as "35- 5 ."). Fail loudly so it can't ship.
    gaps = []
    for k, c in chapters.items():
        secn = sorted({int(re.match(r'\d+-(\d+)', s["ref"]).group(1)) for s in c["sections"]})
        missing = [i for i in range(1, secn[-1] + 1) if i not in secn] if secn else []
        if missing:
            gaps.append(f"BCO {k} missing {missing}")
    assert not gaps, "BCO section gaps (incomplete extraction): " + "; ".join(gaps)
    return chapters

PREFACE_URL = "https://www.pcaac.org/book-of-church-order/preface/"
APPENDICES_URL = "https://www.pcaac.org/book-of-church-order/appendices/"

def _paras(frag):
    out = []
    for p in re.split(r'</p>', frag, flags=re.I):
        t = clean_fmt(p)                                   # keep bold/italic in front-matter & appendix prose
        if t and not re.fullmatch(r'(I{1,3}|IV)\.?', strip_tags(t)):   # skip stray roman-numeral-only fragments
            out.append(t)
    return out

def build_bco_front():
    src = fetch(PREFACE_URL)
    h1 = re.search(r'<h1[^>]*>\s*Preface\s*</h1>', src, re.I)
    m2 = re.search(r'<p[^>]*>\s*<b>\s*II\.(?:\s|<[^>]+>|&[^;]+;)*PRELIMINARY PRINCIPLES', src, re.I)
    m3 = re.search(r'<p[^>]*>\s*<b>\s*III\.(?:\s|<[^>]+>|&[^;]+;)*THE CONSTITUTION DEFINED', src, re.I)
    foot = re.search(r'Get In Touch', src, re.I)
    assert h1 and m2 and m3, "preface markers not found"
    end = foot.start() if foot else len(src)
    # II. Preliminary Principles: intro prose + 8 numbered principles
    pp = src[m2.end():m3.start()]
    pnum = re.compile(r'<p[^>]*>(?:\s|<[^>]+>)*([1-8])\.\s')
    pmarks = list(pnum.finditer(pp))
    assert len(pmarks) == 8, f"expected 8 preliminary principles, got {len(pmarks)}"
    principles = []
    for i, m in enumerate(pmarks):
        e = pmarks[i + 1].start() if i + 1 < len(pmarks) else len(pp)
        body = re.sub(r'^\s*[1-8]\.\s*', '', clean_fmt(pp[m.start():e]))
        principles.append({"ref": f"PP-{m.group(1)}", "body": body})
    pp_intro = _paras(pp[:pmarks[0].start()])
    return [
        {"id": "pref-1", "part": "front", "title": "Preface", "paras": _paras(src[h1.end():m2.start()])},
        {"id": "pref-2", "part": "front", "title": "Preliminary Principles", "paras": pp_intro, "sections": principles},
        {"id": "pref-3", "part": "front", "title": "The Constitution Defined", "paras": _paras(src[m3.end():end])},
    ]

def build_bco_appendices():
    src = fetch(APPENDICES_URL)
    titles = {}
    for m in re.finditer(r'<a href="#App_([A-Z])"[^>]*>\s*APPENDIX\s+[A-Z]\s*</a>\s*([^<]*)', src, re.I):
        titles[m.group(1).upper()] = clean(m.group(2))
    # tolerate empty trailing inline tags before </h2> (some headings render "APPENDIX A<b></b>")
    heads = list(re.finditer(r'<h2[^>]*>\s*APPENDIX\s+([A-Z])\s*(?:<[^>]*>\s*)*</h2>', src, re.I))
    assert heads, "no appendix headings found"
    assert len(heads) >= 10, f"expected 10 appendices (A-J), got {len(heads)}: {[m.group(1) for m in heads]}"
    out = []
    for i, m in enumerate(heads):
        L = m.group(1).upper()
        e = heads[i + 1].start() if i + 1 < len(heads) else len(src)
        foot = src.find("Get In Touch", m.end())
        if foot != -1 and foot < e:
            e = foot
        t = titles.get(L, "")
        title = f"Appendix {L}" + (f" — {t.title().replace(chr(39)+'S', chr(39)+'s')}" if t else "")
        out.append({"id": f"app{L}", "part": "appx", "title": title, "paras": _paras(src[m.end():e])})
    return out

# Morton H. Smith, Commentary on the BCO, 6th ed. (2007) — PERSONAL USE ONLY (© GPTS/Presbyterian Press).
COMMENTARY_PDF = "/workspaces/personal/inbox/Commentary+on+the+book+of+CO.pdf"
# hand-set commentary start for sections where the auto-strip can't cleanly find the boundary
# (real commentary that the algorithm left after a quote sentence). Value = phrase the comment opens with.
COMMENTARY_OVERRIDES = {
    "26-6": "Provision is made to continue the voting",
    "35-2": "The rights of the husband or wife",
}
def _cut_at(block, phrase):
    bn = re.sub(r"[^a-z0-9]", "", phrase.lower())
    kn, kmap = [], []
    for i, ch in enumerate(block):
        if ch.isalnum():
            kn.append(ch.lower()); kmap.append(i)
    i = "".join(kn).find(bn)
    return block if i == -1 else block[kmap[i]:].lstrip(" .,;:­\n")
def _bco_bodies():
    """section ref -> verbatim BCO text, read from the already-built content/bco.js."""
    path = os.path.join(OUT, "bco.js")
    if not os.path.exists(path):
        return {}
    m = re.search(r"window\.BCO\s*=\s*(\{.*?\});\s*\nwindow\.BCO_ORDER", open(path).read(), re.S)
    B = json.loads(m.group(1)) if m else {}
    return {s["ref"]: s["body"] for v in B.values() for s in (v.get("sections") or [])}

def _strip_quote(block, body):
    """Smith quotes the provision before commenting; remove that leading quote via char-level
    prefix alignment (ignores spaces/punct, so OCR 'o f' splits don't matter). Never over-cuts."""
    bn = re.sub(r"[^a-z0-9]", "", body.lower())
    if len(bn) < 15:
        return block
    kn, kmap = [], []
    for idx, ch in enumerate(block):
        if ch.isalnum():
            kn.append(ch.lower()); kmap.append(idx)
    kn = "".join(kn)
    bl = [bk for bk in difflib.SequenceMatcher(None, kn, bn, autojunk=False).get_matching_blocks() if bk.size >= 3]
    if not bl or bl[0].a > 12 or bl[0].b > 12:
        return block                                       # doesn't open with the provision -> nothing to strip
    # the quote tracks the body: block-pos and body-pos advance together. When commentary begins,
    # the block races ahead of the body (offset jumps). Cut at the end of that synchronized run.
    base = bl[0].a - bl[0].b
    qend, matched = bl[0].a + bl[0].size, bl[0].size
    for bk in bl[1:]:
        if (bk.a - bk.b) - base > 60:
            break
        qend, matched = bk.a + bk.size, matched + bk.size
    if matched < 30:
        return block
    cut = kmap[qend - 1] + 1 if qend - 1 < len(kmap) else len(block)
    while cut < len(block) and block[cut] not in " \n\t":  # snap to a word boundary (never mid-word)
        cut += 1
    rest = block[cut:].lstrip(" .,;:­\n")
    return rest if len(rest) > 20 else block

def _desplit(s):
    """Rejoin the handful of OCR word-splits that are never valid unsplit (o f -> of, etc.).
    Restricted to bigrams whose split form is never a real token, so this can't merge words
    across a legitimate boundary. 'o f' alone accounts for ~3700 occurrences."""
    s = re.sub(r"\bo f\b", "of", s)
    s = re.sub(r"(?<=[.!?] )O f\b", "Of", s)   # sentence-initial -> keep the capital
    s = re.sub(r"\bO f\b", "of", s)            # "Word O f God" -> "Word of God"
    s = re.sub(r"\bI f\b", "If", s)            # sentence-initial "If" (~110x)
    s = re.sub(r"\bi f\b", "if", s)
    s = re.sub(r"\bfo r\b", "for", s)
    s = re.sub(r"\bi t\b", "it", s)
    s = re.sub(r"\bM r\b", "Mr", s)
    return s

def _clean_para(p):
    p = re.sub(r"­\s*", "", p)                  # rejoin soft-hyphen line breaks
    p = re.sub(r"\s+", " ", p).strip()
    return _desplit(re.sub(r"^[.\s]+", "", p))

# Running page-heads the OCR interleaved into the prose. Anchored full-line so a head is dropped
# whether it stands alone (its own paragraph) or got joined onto adjacent text by the para builder;
# never matches the same words inside a real sentence.
_HEADS = (r"FORM OF GOVER+NMENT|RULES OF DISCIPLINE|RULES FOR ASSEMBLY OPERATIONS?|"
          r"OPERATING MANUAL FOR STANDING JUDICIAL COMMISSION|DIRECTORY FOR THE WORSHIP OF GOD|"
          r"CORPORATE BYLAWS|PROCEDURES FOR PRESBYTERY JUDICIAL COMMISSIONS|"
          r"SUGGESTED FORMS FOR (?:USE IN CONNECTION WITH THE )?RULES OF DISCIPLINE|"
          r"BIBLICAL CONFLICT RESOLUTION|PRELIMINARY PRINCIPLES|CONSTITUTION DEFINED")
COMMENTARY_SKIP = re.compile(
    r"(^§?\s*[0-9lIO]+\s*[-–]\s*[0-9lIO]+\s*$)|(^\d{1,3}$)|(^(PART|CHAPTER)\b)|"
    r"(COMMENTARY O[NF] THE BOOK)|(^(?:" + _HEADS + r")\s*$)", re.I)

def build_front_commentary(txt, bodies):
    """Smith comments on the Preface before Chapter 1, but the chapter parser starts at the first
    'l-l.' marker and drops everything before it. Recover the Preliminary Principles: the section
    intro (origins) -> pref-2, and each numbered principle's commentary -> PP-1..PP-8 (quoted
    provision stripped exactly as for chapter sections)."""
    lines = txt.splitlines()
    def find(pred, start=0):
        for i in range(start, len(lines)):
            if pred(lines[i]):
                return i
        return -1
    head = lambda l: l.strip() == "PREFACE TO THE BOOK OF CHURCH ORDER"
    s0 = find(head, find(head) + 1)                                 # body heading (1st hit is the TOC)
    s2 = find(lambda l: l.strip() == "II. PRELIMINARY PRINCIPLES", s0) if s0 >= 0 else -1
    s3 = find(lambda l: l.strip() == "III. THE CONSTITUTION DEFINED", s2) if s2 >= 0 else -1
    if s2 < 0 or s3 < 0:
        return {}
    sec2 = lines[s2 + 1:s3]
    def paras_of(seg):
        out, para = [], []
        for ln in seg:
            t = ln.strip()
            if not t:
                if para: out.append(" ".join(para)); para = []
                continue
            if COMMENTARY_SKIP.search(t): continue
            para.append(t)
        if para: out.append(" ".join(para))
        return [c for c in (_clean_para(p) for p in out) if len(c) > 1]
    mk = re.compile(r"^\s*([1-8])\.(?:\s|$)")
    marks, expect = [], 1
    for i, ln in enumerate(sec2):
        m = mk.match(ln)
        if m and int(m.group(1)) == expect:
            marks.append((expect, i)); expect += 1
    if len(marks) != 8:
        return {}
    out = {}
    intro = " ".join(paras_of(sec2[:marks[0][1]]))                  # origins prose (one OCR paragraph)
    intro = re.split(r"\s+The Presbyterian Church in America, in setting forth the form", intro)[0].strip()
    if len(intro) > 20:
        out["pref-2"] = [intro]
    for j, (n, i) in enumerate(marks):
        nxt = marks[j + 1][1] if j + 1 < len(marks) else len(sec2)
        full = "\n\n".join(paras_of(sec2[i:nxt]))
        joined = _strip_quote(full, bodies.get(f"PP-{n}", ""))
        cps = [p.strip() for p in joined.split("\n\n") if len(p.strip()) > 1]
        if cps:
            out[f"PP-{n}"] = cps
    return out

def build_commentary():
    txt = subprocess.run(["pdftotext", COMMENTARY_PDF, "-"], capture_output=True, text=True).stdout
    norm = lambda t: t.replace("l", "1").replace("I", "1").replace("O", "0")
    mark = re.compile(r"^\s*([0-9lIO]{1,2})\s*[-–]\s*([0-9lIO]{1,2})\s*\.+")   # marker may sit alone on its line
    skip = COMMENTARY_SKIP
    comm, cur, lastC, lastS, paras, para = {}, None, 0, 0, [], []
    def end_para():
        if para: paras.append(" ".join(para)); para.clear()
    def flush():
        end_para()
        if cur and paras: comm.setdefault(cur, list(paras))
    for ln in txt.splitlines():
        m = mark.match(ln); ok = False
        if m:
            try: c, s = int(norm(m.group(1))), int(norm(m.group(2)))
            except ValueError: c = s = -1
            if 1 <= c <= 63 and 1 <= s <= 40 and (c > lastC or (c == lastC and s > lastS)) and c <= lastC + 2:
                ok = True
        if ok:
            flush(); cur = f"{c}-{s}"; lastC, lastS = c, s; paras = []; para = [ln[m.end():].strip()]
            continue
        if cur is None: continue
        t = ln.strip()
        if not t: end_para(); continue
        if skip.search(t): continue
        para.append(t)
    flush()
    bodies = _bco_bodies()
    clean = _clean_para
    out = dict(build_front_commentary(txt, bodies))   # Preface (Preliminary Principles) before Chapter 1
    for r, ps in comm.items():
        body = bodies.get(r, "")
        full = "\n\n".join(clean(p) for p in ps)
        joined = _cut_at(full, COMMENTARY_OVERRIDES[r]) if r in COMMENTARY_OVERRIDES else _strip_quote(full, body)
        joined = re.sub(r"\s*THE [A-Z][A-Z ]+ ENDS\.?\s*$", "", joined)   # drop leaked part-end markers
        cps = [p.strip() for p in joined.split("\n\n") if len(p.strip()) > 1]
        if not cps:
            continue
        # skip entries that are essentially just the provision/form restated (no real commentary):
        # show no Commentary tab there rather than a redundant restatement. (overrides are trusted.)
        if r not in COMMENTARY_OVERRIDES and body and _coverage(" ".join(cps), body) >= 0.8:
            continue
        out[r] = cps
    return out

def _coverage(text, body):
    """fraction of `text` that is provision (BCO) text — high => it's a restatement, not commentary."""
    tn = re.sub(r"[^a-z0-9]", "", text.lower()); bn = re.sub(r"[^a-z0-9]", "", body.lower())
    if len(tn) < 5 or len(bn) < 5:
        return 0.0
    matched = sum(b.size for b in difflib.SequenceMatcher(None, tn, bn, autojunk=False).get_matching_blocks())
    return matched / len(tn)

# F. P. Ramsay, An Exposition of the Form of Government and the Rules of Discipline (1898) — PUBLIC DOMAIN.
# Sourced from the PCA Historical Center's "Historical Development of the BCO" project, which reprints the
# pertinent Ramsay section under each PCA paragraph (already mapped to current PCA chapter/paragraph numbers).
RAMSAY_BASE = "https://www.pcahistory.org/bco/"
_RAMSAY_ATTRIB = re.compile(r"F\.?\s*P\.?\s*Ramsay,.*Exposition", re.I)
# Each page stacks several sources under "COMMENTARY" headers (Ramsay first, then the *copyrighted* Smith,
# then Hodge, Scott's Digest, GA minutes…). Cut Ramsay's block at the next author/section so we take only his.
_RAMSAY_END = re.compile(r"^(Morton\s+H\.?\s*Smith|Charles\s+Hodge|Thomas\s+E\.?\s*Peck"
                         r"|Samuel\s+Miller|Scott,?\s*E\.?\s*C\.?|.*\bA\s+Digest\s+of\s+the\s+Acts"
                         r"|Return to Index)", re.I)
# Each page stacks sources under ALL-CAPS section headers (COMMENTARY:, CONSTITUTIONAL INQUIRY:,
# OVERTURES AND AMENDMENTS:, DIGEST:, OTHER COMPARISONS:). The next such header ends Ramsay's block.
_RAMSAY_CAPHEAD = re.compile(r"^[A-Z][A-Z0-9 ,.&'\-]{3,}:\s*$")     # NOT re.I — must be genuinely all-caps
_RAMSAY_QUOTE = re.compile(r"^§?\s*\d+\s*[.—–-]+\s*[IVXLC0-9][IVXLC0-9-]*\s*[.:]")  # re-quoted provision line
_RAMSAY_HEADING = re.compile(r"^(Section|Chapter|CHAPTER)\s+[IVXLC0-9]+\b.{0,70}$")
_RAMSAY_DROP = re.compile(r"^(\[|\(Cf\.|\d{4}\b|\".{0,3}$)")        # placeholders, bare cross-refs/years, stray fragments

def _ramsay_paras(htmltext):
    """Pull only F. P. Ramsay's exposition out of a BCO-project page; None if the page has none."""
    c = htmltext.find('name="Page Content"')
    region = htmltext[c:] if c >= 0 else htmltext
    region = re.sub(r"<br\s*/?>", "\n", region)
    region = re.sub(r"<[^>]+>", "", region)
    region = html.unescape(region).replace("’", "'").replace("“", '"').replace("”", '"')
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in region.split("\n")]
    ai = next((i for i, ln in enumerate(lines) if _RAMSAY_ATTRIB.search(ln)), None)
    if ai is None:
        return None
    out = []
    for ln in lines[ai + 1:]:
        if _RAMSAY_END.match(ln) or _RAMSAY_CAPHEAD.match(ln):
            break
        if len(ln) <= 1 or _RAMSAY_QUOTE.match(ln) or _RAMSAY_HEADING.match(ln) or _RAMSAY_DROP.match(ln):
            continue
        out.append(ln)
    # ignore pages where nothing of substance survived (a stray header/fragment, no real exposition)
    return out if sum(len(p) for p in out) >= 15 else None

def build_ramsay():
    """Ramsay covers only the Form of Government (ch. 1-26) and Rules of Discipline (ch. 27-46); the
    Directory for Worship he reserved for a separate volume, so those pages carry no Ramsay text."""
    path = os.path.join(OUT, "bco.js")
    B = json.loads(re.search(r"window\.BCO\s*=\s*(\{.*?\});\s*\nwindow\.BCO_ORDER", open(path).read(), re.S).group(1))
    refs = []
    for v in B.values():
        for s in (v.get("sections") or []):
            m = re.match(r"^(\d+)-(\d+)$", s["ref"])
            if m and 1 <= int(m.group(1)) <= 46:
                refs.append((int(m.group(1)), int(m.group(2)), s["ref"]))
    def soft(url):
        try: return fetch(url)
        except SystemExit: return ""        # one flaky page shouldn't sink a 340-page crawl
    out, miss = {}, 0
    for n, m, ref in refs:
        sub = "fog" if n <= 26 else "rod"
        ps = _ramsay_paras(soft(f"{RAMSAY_BASE}{sub}/{n:02d}/{m:02d}.html"))
        if ps:
            out[ref] = ps
        else:
            miss += 1
    # Preface: King & Head (Ramsay's FoG ch. 2 §1) -> pref-1; Constitution Defined -> pref-3.
    for ref, slug, count in (("pref-1", "preface/king", 6), ("pref-3", "preface/constitution", 2)):
        acc = []
        for i in range(1, count + 1):
            acc += _ramsay_paras(soft(f"{RAMSAY_BASE}{slug}/{i:02d}.html")) or []
        if acc:
            out[ref] = acc
    print(f"  Ramsay: {len(out)} sections with text, {miss} BCO paragraphs with no Ramsay equivalent")
    return out

# Scripture proof texts (clause-tied references) from westminsterstandards.org — public-domain Westminster
# proofs. References only (no verse text), inline at each clause: "...glorify God, (Rom. 11:36, 1 Cor. 10:31)".
PROOFS_SOURCES = {
    "wcf": "https://westminsterstandards.org/westminster-confession-of-faith/",
    "wlc": "https://westminsterstandards.org/westminster-larger-catechism/",
    "wsc": "https://westminsterstandards.org/westminster-shorter-catechism/",
}
def _proof_clean(s):
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s).replace("’ ", "'").replace("’", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", s).strip()

def build_proofs():
    out = {"wcf": {}, "wlc": {}, "wsc": {}}
    for name in ("wlc", "wsc"):                      # catechisms: <p>Question N<br/><i>q</i><br/>answer (refs)</p>
        src = fetch(PROOFS_SOURCES[name])
        for m in re.finditer(r"<p>\s*Question\s+(\d+)\s*<br\s*/?>(.*?)</p>", src, re.S | re.I):
            ans = re.sub(r"^.*?</i>\s*<br\s*/?>", "", m.group(2), flags=re.S | re.I)
            t = _proof_clean(ans)
            if "(" in t:
                out[name][f"Q.{m.group(1)}"] = t
    src = fetch(PROOFS_SOURCES["wcf"])               # confession: <h2 id="wcfN"> then <p>M. text (refs)</p>
    chaps = list(re.finditer(r'<h2 id="wcf(?:chapter)?(\d+)"', src))
    for i, c in enumerate(chaps):
        ch = c.group(1)
        seg = src[c.end(): chaps[i + 1].start() if i + 1 < len(chaps) else len(src)]
        for sm in re.finditer(r"<p>\s*(\d+)\.\s*(.*?)</p>", seg, re.S):
            t = _proof_clean(sm.group(2))
            if "(" in t:
                out["wcf"][f"{ch}.{sm.group(1)}"] = t
    return out

# ── Scripture verse text for tappable proofs ──────────────────────────────
# Berean Standard Bible (public domain, CC0). Only the verses the proofs cite
# are bundled. The proof refs (clause-tied) are tokenized into tappable anchors;
# all the fiddly normalization lives here (one place) so the reader stays dumb.
BSB_URL = "https://bereanbible.com/bsb.txt"

BOOK = {}
def _bk(canon, *aliases):
    BOOK[canon.lower()] = canon
    for a in aliases:
        BOOK[a.lower().rstrip('.')] = canon
_bk('Genesis','Gen'); _bk('Exodus','Exod','Ex'); _bk('Leviticus','Lev'); _bk('Numbers','Num','Numb')
_bk('Deuteronomy','Deut'); _bk('Joshua','Josh'); _bk('Judges','Judg'); _bk('Ruth')
_bk('1 Samuel','1 Sam'); _bk('2 Samuel','2 Sam'); _bk('1 Kings','1 Kgs'); _bk('2 Kings','2 Kgs')
_bk('1 Chronicles','1 Chron','1 Chr'); _bk('2 Chronicles','2 Chron','2 Chr')
_bk('Ezra'); _bk('Nehemiah','Neh'); _bk('Esther','Esth'); _bk('Job')
_bk('Psalm','Ps','Psa','Psalms'); _bk('Proverbs','Prov'); _bk('Ecclesiastes','Eccl','Eccles','Ecc')
_bk('Song of Solomon','Cant','Song'); _bk('Isaiah','Isa'); _bk('Jeremiah','Jer'); _bk('Lamentations','Lam')
_bk('Ezekiel','Ezek'); _bk('Daniel','Dan'); _bk('Hosea','Hos'); _bk('Joel'); _bk('Amos'); _bk('Obadiah','Obad')
_bk('Jonah'); _bk('Micah','Mic'); _bk('Nahum','Nah'); _bk('Habakkuk','Hab'); _bk('Zephaniah','Zeph')
_bk('Haggai','Hag'); _bk('Zechariah','Zech'); _bk('Malachi','Mal')
_bk('Matthew','Matt','Mt'); _bk('Mark'); _bk('Luke'); _bk('John'); _bk('Acts','Act')
_bk('Romans','Rom'); _bk('1 Corinthians','1 Cor'); _bk('2 Corinthians','2 Cor')
_bk('Galatians','Gal','Ga'); _bk('Ephesians','Eph'); _bk('Philippians','Phil','Philip')
_bk('Colossians','Col'); _bk('1 Thessalonians','1 Thess'); _bk('2 Thessalonians','2 Thess')
_bk('1 Timothy','1 Tim'); _bk('2 Timothy','2 Tim'); _bk('Titus','Tit','1 Tit')
_bk('Philemon','Philem','Phlm'); _bk('Hebrews','Heb'); _bk('James','Jas')
_bk('1 Peter','1 Pet'); _bk('2 Peter','2 Pet'); _bk('1 John'); _bk('2 John'); _bk('3 John')
_bk('Jude'); _bk('Revelation','Rev')

def norm_book(raw):
    if not raw: return None
    s = raw.strip().rstrip('.').lower()
    s = re.sub(r'^iii\s+', '3 ', s); s = re.sub(r'^ii\s+', '2 ', s); s = re.sub(r'^i\s+', '1 ', s)
    return BOOK.get(s)

# A verse number must be whole ((?!\d)), not a chapter ((?!\s*:)), and not a book
# ordinal — the "1" of "1 John" ((?!\s+[A-Za-z])) — so refs never bleed into each other.
_BOOKTOK = r'(?:(?:[1-3]|I{1,3})\s+)?[A-Z][a-z]+\.?'
_VNUM  = r'\d+(?!\d)(?!\s*:)(?!\s+[A-Za-z])'
_RANGE = rf'{_VNUM}(?:\s*[–—-]\s*\d+)?'
_VLIST = rf'{_RANGE}(?:\s*,\s*{_RANGE})*'
TOK_RE = re.compile(rf'(?:({_BOOKTOK})\s*)?(\d+):\s*({_VLIST})')

def _expand_verses(part):
    out = []
    for chunk in part.replace('—', '–').split(','):
        chunk = chunk.strip()
        if not chunk: continue
        if '–' in chunk or '-' in chunk:
            sep = '–' if '–' in chunk else '-'
            a, _, b = chunk.partition(sep); a, b = a.strip(), b.strip()
            if a.isdigit() and b.isdigit(): out.extend(range(int(a), int(b) + 1))
            elif a.isdigit(): out.append(int(a))
        elif chunk.isdigit():
            out.append(int(chunk))
    return out

def load_bsb():
    idx = {}
    for line in fetch(BSB_URL).splitlines():
        if '\t' not in line: continue
        ref, text = line.split('\t', 1)
        m = re.match(r'^(.+?)\s+(\d+):(\d+)$', ref.strip())
        if m:
            idx[f"{m.group(1).strip()} {int(m.group(2))}:{int(m.group(3))}"] = text.strip()
    return idx

def _read_proofs_js():
    """Parse the existing content/proofs.js back into {corpus: {ref: text}}."""
    src = open(os.path.join(OUT, "proofs.js"), encoding="utf-8").read()
    out = {}
    for m in re.finditer(r'window\.(WCF|WLC|WSC)_PROOFS\s*=\s*(\{.*?\});', src, re.S):
        out[m.group(1).lower()] = json.loads(m.group(2))
    return out

# Single-chapter books are cited "Jude 6" / "3 John 12" (no chapter); rewrite to
# "Book 1:N" so they resolve. Also fix the occasional "65;2" semicolon-for-colon typo.
_SINGLE_CH = r'(?:[23]\s*John|Jude|Obadiah|Obad\.|Philemon|Philem\.|Phlm\.)'
def _prenorm(g):
    g = re.sub(r'(\d)\s*;\s*(\d)', r'\1:\2', g)
    g = re.sub(rf'\b({_SINGLE_CH})\s+(?=\d)', r'\1 1:', g)
    return g

def build_verses():
    """Returns (verses {key:text}, refmap {parenthetical-inner: anchored-html}, stats)."""
    bsb = load_bsb()
    proofs = _read_proofs_js()
    verses, refmap = {}, {}
    total = resolved = chapter_only = 0
    unresolved = []
    def anchor(group):
        nonlocal total, resolved, chapter_only
        group = _prenorm(group)
        # whole-chapter citations ("Acts 15", "Ps. 83") have a book+number but no ':' — left as plain text
        chapter_only += len(re.findall(rf'{_BOOKTOK}\s*\d+(?!\s*:)(?!\d)', group))
        state = {"book": None}
        def repl(m):
            nonlocal total, resolved
            b = norm_book(m.group(1))
            if b: state["book"] = b
            book = b or state["book"]
            if not book: return m.group(0)
            ch, vs = int(m.group(2)), _expand_verses(m.group(3))
            keys = [f"{book} {ch}:{v}" for v in vs]
            ok = []
            for k in keys:
                total += 1
                if k in bsb:
                    resolved += 1; ok.append(k); verses[k] = bsb[k]
                else:
                    unresolved.append(k)
            if not ok: return m.group(0)              # unresolved → plain (still shown)
            return (f'<a class="vref" role="button" tabindex="0" '
                    f'data-v="{html.escape("|".join(ok), quote=True)}">{m.group(0)}</a>')
        return f'<span class="pref">({TOK_RE.sub(repl, group)})</span>'
    for corpus in proofs.values():
        for text in corpus.values():
            for g in re.findall(r'\(([^()]*)\)', text):
                if g not in refmap:
                    refmap[g] = anchor(g)
    stats = {"total": total, "resolved": resolved, "unresolved": sorted(set(unresolved)),
             "verses": len(verses), "groups": len(refmap), "chapter_only": chapter_only}
    return verses, refmap, stats

def write(name, items):
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"{name}.js")
    with open(path, "w") as f:
        f.write(f"/* {name.upper()} — generated by build_content.py from {SOURCES.get(name,'')}. */\n")
        f.write(f"window.{name.upper()} = {json.dumps(items, ensure_ascii=False, indent=0)};\n")
    return path, len(items)

def do(name):
    if name in ("wsc", "wlc"):
        items = build_catechism(name)
        path, n = write(name, items)
        print(f"{name.upper()}: {n} Q&A → {path}")
    elif name == "wcf":
        ch = build_wcf()
        path, n = write("wcf", ch)
        print(f"WCF: {n} chapters, {sum(len(c['sections']) for c in ch.values())} sections → {path}")
    elif name == "bco":
        ch = build_bco()
        front = build_bco_front()
        appx = build_bco_appendices()
        entries, order = {}, []
        for e in front:
            entries[e["id"]] = e; order.append(e["id"])
        for n in sorted(int(k) for k in ch):
            entries[str(n)] = ch[str(n)]; order.append(str(n))
        for e in appx:
            entries[e["id"]] = e; order.append(e["id"])
        os.makedirs(OUT, exist_ok=True)
        path = os.path.join(OUT, "bco.js")
        with open(path, "w") as f:
            f.write("/* BCO — personal use only (© PCA, do not publish). HTML base + 2025-verified. */\n")
            f.write("window.BCO = " + json.dumps(entries, ensure_ascii=False, indent=0) + ";\n")
            f.write("window.BCO_ORDER = " + json.dumps(order) + ";\n")
        nsec = sum(len(c.get('sections', [])) for c in ch.values())
        print(f"BCO: {len(ch)} chapters / {nsec} sections + {len(front)} front + {len(appx)} appendices → {path}")
    elif name == "commentary":
        comm = build_commentary()
        # emit as an IMPORT-ONLY content pack (copyrighted — NOT bundled into the app)
        os.makedirs(os.path.join(OUT, "packs"), exist_ok=True)
        path = os.path.join(OUT, "packs", "commentary-smith.pack.json")
        pack = {
            "format": "pca-constitution-pack", "version": 1, "kind": "commentary",
            "label": "Morton H. Smith — Commentary on the BCO (6th ed., 2007)",
            "attribution": ("Morton H. Smith, Commentary on the Book of Church Order of the PCA, 6th ed. (2007), "
                            "Greenville Presbyterian Theological Seminary. Personal use only — do not redistribute."),
            "corpus": "bco",
            "entries": comm,
        }
        with open(path, "w") as f:
            json.dump(pack, f, ensure_ascii=False, indent=0)
        print(f"Commentary pack: {len(comm)} sections → {path}")
    elif name == "ramsay":
        comm = build_ramsay()
        os.makedirs(os.path.join(OUT, "packs"), exist_ok=True)
        path = os.path.join(OUT, "packs", "commentary-ramsay.pack.json")
        pack = {
            "format": "pca-constitution-pack", "version": 1, "kind": "commentary",
            "label": "F. P. Ramsay — Exposition of the BCO (1898)",
            "attribution": ("F. P. Ramsay, An Exposition of the Form of Government and the Rules of Discipline "
                            "of the Presbyterian Church in the United States (Richmond: Presbyterian Committee of "
                            "Publication, 1898). Public domain. Section text via the PCA Historical Center BCO "
                            "project (pcahistory.org/bco), mapped to current PCA paragraphs."),
            "corpus": "bco",
            "entries": comm,
        }
        with open(path, "w") as f:                              # portable pack (export/share, gitignored)
            json.dump(pack, f, ensure_ascii=False, indent=0)
        # Ramsay is public domain, so also ship it bundled: a <script>-loaded global the app can
        # add with one tap (precached by the service worker, works offline + from file://).
        jspath = os.path.join(OUT, "ramsay.js")
        with open(jspath, "w") as f:
            f.write("/* F. P. Ramsay — Exposition of the BCO (1898), public domain. Bundled commentary pack "
                    "(one-tap add in the app). Generated by build_content.py from pcahistory.org/bco. */\n")
            f.write("window.BUNDLED_PACKS = (window.BUNDLED_PACKS || []).concat(["
                    + json.dumps(pack, ensure_ascii=False) + "]);\n")
        print(f"Ramsay pack: {len(comm)} sections → {path} + {jspath}")
    elif name in ("proofs", "verses"):
        # SUPERSEDED: proofs.js + verses.js now carry the PCA's OFFICIAL proof texts
        # (pcaac.org), built by build_proofs/build.sh. The old westminsterstandards.org
        # parse here produced the *classic* Westminster proof set (wrong selection for a
        # PCA app, e.g. WSC Q26) — do NOT regenerate from it or it will clobber the data.
        sys.exit("'proofs'/'verses' are built by build_proofs/build.sh now — see build_proofs/README.md")
    else:
        sys.exit(f"unknown target: {name}")

if __name__ == "__main__":
    targets = sys.argv[1:] or ["wsc"]
    if targets == ["all"]:
        targets = ["wsc", "wlc", "wcf", "bco", "commentary", "ramsay"]  # proofs/verses: build_proofs/build.sh
    for t in targets:
        do(t)
