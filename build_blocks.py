#!/usr/bin/env python3
"""Augment content/bco.js with structured `blocks` (paragraphs + nested lists),
re-derived from the pcaac.org source markup. Depth is inferred from marker-style
transitions (a. -> (1) -> (a)), not absolute indentation, because the source's
padding-left baseline varies per section.

Non-destructive: only attaches blocks to sections whose scraped text matches the
committed body (reconciliation). Sections whose committed body merely has trailing
junk (page footer, or text that over-ran into the next section in the old build)
are CORRECTED to the clean scraped text. Any genuine drift aborts the write.

Usage:  python3 build_blocks.py [--write]
"""
import re, html, json, os, sys, subprocess

REPO = os.path.dirname(os.path.abspath(__file__))
CACHE = os.environ.get('CLAUDE_JOB_DIR', REPO) + "/tmp"
PARTS = {
    "fog": ("fog.html", "https://www.pcaac.org/book-of-church-order/part-1-the-form-of-government/"),
    "rod": ("part-2-the-rules-of-discipline.html", "https://www.pcaac.org/book-of-church-order/part-2-the-rules-of-discipline/"),
    "dow": ("part-3-the-directory-for-the-worship-of-god.html", "https://www.pcaac.org/book-of-church-order/part-3-the-directory-for-the-worship-of-god/"),
}
def fetch(part):
    fn, url = PARTS[part]
    p = os.path.join(CACHE, fn)
    if os.path.exists(p):
        return open(p, encoding='utf-8', errors='replace').read()
    r = subprocess.run(["curl","-sS","-m","40","-A","constitution-reader/0.1 (personal study)",url],
                       capture_output=True, text=True)
    if r.returncode: sys.exit(f"fetch failed: {part}")
    os.makedirs(CACHE, exist_ok=True); open(p,"w").write(r.stdout)
    return r.stdout

def clean(s):
    s = re.sub(r"<br\s*/?>", " ", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s).replace("’","'").replace("“",'"').replace("”",'"')
    return re.sub(r"\s+", " ", s).strip()

def strip_tags(s): return re.sub(r"<[^>]+>", "", s)

def clean_fmt(s):
    """Like clean(), but keep inline emphasis: <strong>/<b> -> <b>, <em>/<i> -> <i>."""
    s = re.sub(r"<br\s*/?>", " ", s)
    s = re.sub(r"</?(?:strong|b)\b[^>]*>", lambda m: "</b>" if m.group(0)[1]=="/" else "<b>", s, flags=re.I)
    s = re.sub(r"</?(?:em|i)\b[^>]*>",     lambda m: "</i>" if m.group(0)[1]=="/" else "<i>", s, flags=re.I)
    s = re.sub(r"<(?!/?[bi]>)[^>]*>", "", s)                 # strip every tag except <b></b><i></i>
    s = html.unescape(s).replace("’","'").replace("“",'"').replace("”",'"')
    s = re.sub(r"\s+", " ", s)
    for _ in range(4):                                       # merge split emphasis (<b>35-</b><b>5</b>) and
        s2 = s.replace("</b><b>","").replace("</i><i>","")   # drop empties, KEEPING any inner whitespace
        s2 = re.sub(r"<([bi])>(\s*)</\1>", r"\2", s2)
        if s2==s: break
        s=s2
    return s.strip()

_gap = r'(?:\s|<[^>]+>|&nbsp;)*'
tok = re.compile(
    r'<h2[^>]*>\s*CHAPTER\s+([A-Z–\-]+)\s*</h2>'
    rf'|<(?:p|h4)[^>]*>{_gap}(\d+){_gap}-{_gap}(\d+[A-Za-z]?){_gap}\.'
    r'|<h4[^>]*>(.*?)</h4>', re.S | re.I)

MARK = [
    (re.compile(r'^([a-z])\.\s+(.*)$', re.S), 'alpha',  lambda g: f'{g}.'),
    (re.compile(r'^\((\d+)\)\s*(.*)$', re.S), 'pnum',   lambda g: f'({g})'),
    (re.compile(r'^\(([a-z])\)\s*(.*)$', re.S),'palpha', lambda g: f'({g})'),
    (re.compile(r'^(\d+)\.\s+(.*)$', re.S),   'num',    lambda g: f'{g}.'),
]
def parse_section(frag):
    cut = re.search(r'Copyright\s*©|Get In Touch', frag)
    if cut: frag = frag[:cut.start()]
    bq = [(m.start(), m.end()) for m in re.finditer(r'<blockquote\b.*?</blockquote>', frag, re.S|re.I)]
    in_bq = lambda pos: any(a <= pos < b for a, b in bq)
    raw=[]; first=True
    for m0 in re.finditer(r'<(p|h4)\b([^>]*)>(.*?)</\1>', frag, re.S|re.I):
        tag, attrs, inner = m0.group(1), m0.group(2), m0.group(3)
        pm = re.search(r'padding-left:\s*(\d+)', attrs)
        pad = int(pm.group(1)) if pm else 0
        quote = in_bq(m0.start())
        txt = clean_fmt(inner)
        if not txt: continue
        if first:
            first=False
            txt = re.sub(r'^\s*(?:<b>\s*)?\d+\s*[–-]\s*\d+[A-Za-z]?(?:\s*</b>)?\s*\.\s*(?:</b>)?\s*', '', txt)
            if txt: raw.append(('p', 0, None, txt, None, False))
            continue
        if quote:                                            # blockquote -> indented quote paragraph
            raw.append(('p', pad, None, txt, None, True)); continue
        for rx, style, disp in MARK:
            m = rx.match(txt)                                # markers are plain at the start; match on formatted text
            if m:
                raw.append(('i', pad, disp(m.group(1)), m.group(2).strip(), style, False)); break
        else:
            raw.append(('p', pad, None, txt, None, False))
    # depth via style-transition stack
    blocks=[]; levels=[]; cur=0
    for kind, pad, marker, text, style, quote in raw:
        if kind=='p':
            if quote:
                blocks.append(['p', min(cur+1, 4), text])    # indent the quote relative to its context
            else:
                if pad==0: levels=[]; cur=0
                blocks.append(['p', cur, text])
        else:
            if style in levels:
                idx=levels.index(style); del levels[idx+1:]; d=idx+1
            else:
                levels.append(style); d=len(levels)
            cur=d
            blocks.append(['i', d, marker, text])
    return blocks

def sections_from(part):
    src = fetch(part)
    marks=list(tok.finditer(src)); out={}
    for i,m in enumerate(marks):
        if m.group(1) is not None or m.group(4) is not None: continue
        ref=f"{int(m.group(2))}-{m.group(3)}"
        end=marks[i+1].start() if i+1<len(marks) else len(src)
        out[ref]=parse_section(src[m.start():end])
    return out

def flatten(b):
    return re.sub(r'\s+',' ',' '.join(x[2] if x[0]=='p' else x[2]+' '+x[3] for x in b)).strip()
def norm(t): return re.sub(r'\s+',' ',t).strip()
def has_structure(b): return len(b)>1 or any(x[0]=='i' for x in b)

PARSED={}
for p in PARTS: PARSED.update(sections_from(p))

bcojs = os.path.join(REPO,"content","bco.js")
raw = open(bcojs, encoding='utf-8').read()
i=raw.index("window.BCO ="); j=raw.index("window.BCO_ORDER")
bco = json.loads(raw[raw.index("{",i):j].rstrip().rstrip(";"))
order = json.loads(raw[raw.index("[",j):raw.rindex("]")+1])

FOOTER=re.compile(r'(Get In Touch|Copyright ©|Office of the Stated Clerk)')
SECMARK=re.compile(r'^\d+\s*[–-]\s*\d+[A-Za-z]?\s*\.')
stats={'match':0,'corrected':0,'drift':0,'nostruct':0}
drift=[]; fixes=[]
for k,ch in bco.items():
    if not k.isdigit(): continue
    for sec in ch['sections']:
        ref=sec.get('ref')
        if not ref or 'body' not in sec: continue
        nb=PARSED.get(ref)
        if nb is None: stats['drift']+=1; drift.append((ref,'NOT IN SCRAPE')); continue
        fmt = norm(flatten(nb))                              # formatted (keeps <b>/<i>)
        nn  = norm(strip_tags(fmt))                          # plain, for drift comparison
        no  = norm(strip_tags(sec['body']))
        if nn==no:
            stats['match']+=1
            sec['body']=fmt                                  # add inline emphasis to the body
            if has_structure(nb): sec['blocks']=nb
            else: stats['nostruct']+=1
        elif no.startswith(nn) and (SECMARK.match(no[len(nn):].lstrip()) or FOOTER.search(no[len(nn):])):
            stats['corrected']+=1; fixes.append(ref)
            sec['body']=fmt
            if has_structure(nb): sec['blocks']=nb
        else:
            stats['drift']+=1; drift.append((ref, f"old={len(no)} new={len(nn)} startswith={no.startswith(nn)}"))

print("RECONCILE:", stats)
print("corrected (footer/over-capture):", fixes)
print("REAL DRIFT:", drift[:40])
nblk=sum(1 for ch in bco.values() if isinstance(ch,dict) for s in ch.get('sections',[]) if 'blocks' in s)
print("sections receiving blocks:", nblk)

if '--write' in sys.argv:
    if drift:
        print("REFUSING TO WRITE: real drift present — vet first"); sys.exit(1)
    with open(bcojs,"w") as f:
        f.write("/* BCO — personal use only (© PCA, do not publish). HTML base + 2025-verified. */\n")
        f.write("window.BCO = " + json.dumps(bco, ensure_ascii=False, indent=0) + ";\n")
        f.write("window.BCO_ORDER = " + json.dumps(order) + ";\n")
    print("WROTE", bcojs)
