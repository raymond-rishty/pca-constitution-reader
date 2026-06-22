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
                       capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"fetch failed ({url}): {r.stderr.strip()}")
    return r.stdout

def clean(s):
    s = re.sub(r"<br\s*/?>", " ", s)
    s = re.sub(r"<[^>]+>", "", s)          # strip any stray tags
    s = html.unescape(s).replace("’", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", s).strip()

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
    tok = re.compile(
        r'<h2[^>]*>\s*CHAPTER\s+([A-Z–\-]+)\s*</h2>'
        r'|<h4[^>]*>(.*?)</h4>'
        r'|<p[^>]*>(?:\s|<[^>]+>)*(\d+)-(\d+[A-Za-z]?)(?:\s|<[^>]+>)*\.',
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
            if m.group(2) is not None:                                  # chapter title
                t = clean(m.group(2))
                if cur and not chapters[str(cur)]["title"] and t:
                    chapters[str(cur)]["title"] = t
                continue
            ch = int(m.group(3))                                        # numbered section
            if ch != cur:
                continue                                                # cross-reference, not a section header
            ref = f"{ch}-{m.group(4)}"
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
    return chapters

PREFACE_URL = "https://www.pcaac.org/book-of-church-order/preface/"
APPENDICES_URL = "https://www.pcaac.org/book-of-church-order/appendices/"

def _paras(frag):
    out = []
    for p in re.split(r'</p>', frag, flags=re.I):
        t = clean(p)
        if t and not re.fullmatch(r'(I{1,3}|IV)\.?', t):   # skip stray roman-numeral-only fragments
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
        body = re.sub(r'^\s*[1-8]\.\s*', '', clean(pp[m.start():e]))
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
    heads = list(re.finditer(r'<h2[^>]*>\s*APPENDIX\s+([A-Z])\s*</h2>', src, re.I))
    assert heads, "no appendix headings found"
    out = []
    for i, m in enumerate(heads):
        L = m.group(1).upper()
        e = heads[i + 1].start() if i + 1 < len(heads) else len(src)
        foot = src.find("Get In Touch", m.end())
        if foot != -1 and foot < e:
            e = foot
        t = titles.get(L, "")
        title = f"Appendix {L}" + (f" — {t.title()}" if t else "")
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

def build_commentary():
    txt = subprocess.run(["pdftotext", COMMENTARY_PDF, "-"], capture_output=True, text=True).stdout
    norm = lambda t: t.replace("l", "1").replace("I", "1").replace("O", "0")
    mark = re.compile(r"^\s*([0-9lIO]{1,2})\s*[-–]\s*([0-9lIO]{1,2})\s*\.+")   # marker may sit alone on its line
    skip = re.compile(r"(^§?\s*[0-9lIO]+\s*[-–]\s*[0-9lIO]+\s*$)|(^\d{1,3}$)|(^(PART|CHAPTER)\b)|(COMMENTARY ON THE BOOK)", re.I)
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
    clean = lambda p: re.sub(r"^[.\s]+", "", re.sub(r"\s+", " ", re.sub(r"­\s*", "", p)).strip())
    out = {}
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
    elif name == "proofs":
        P = build_proofs()
        os.makedirs(OUT, exist_ok=True)
        path = os.path.join(OUT, "proofs.js")
        with open(path, "w") as f:
            f.write("/* Scripture proof texts (clause-tied refs) from westminsterstandards.org (public domain). */\n")
            for k in ("wcf", "wlc", "wsc"):
                f.write(f"window.{k.upper()}_PROOFS = " + json.dumps(P[k], ensure_ascii=False, indent=0) + ";\n")
        print(f"Proofs: WCF {len(P['wcf'])}, WLC {len(P['wlc'])}, WSC {len(P['wsc'])} → {path}")
    else:
        sys.exit(f"unknown target: {name}")

if __name__ == "__main__":
    targets = sys.argv[1:] or ["wsc"]
    if targets == ["all"]:
        targets = ["wsc", "wlc", "wcf", "bco", "commentary", "proofs"]
    for t in targets:
        do(t)
