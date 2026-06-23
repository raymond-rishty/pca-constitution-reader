#!/usr/bin/env python3
"""Read wsc/wlc/wcf_proofs.json, tokenize each group's ref-string against BSB,
emit verses store + refmap. Extended for cross-chapter ranges, ff, See/With, Ex/Est.
Tests resolution rate before final integration."""
import json, re, html, glob

# ---- BSB index + chapter sizes ----
BSB = {}; CHMAX = {}
for line in open('bsb.txt', encoding='utf-8-sig'):
    if '\t' not in line: continue
    ref, text = line.split('\t', 1)
    m = re.match(r'^(.+?)\s+(\d+):(\d+)$', ref.strip())
    if m:
        b, c, v = m.group(1).strip(), int(m.group(2)), int(m.group(3))
        BSB[f'{b} {c}:{v}'] = text.strip()
        CHMAX[(b, c)] = max(CHMAX.get((b, c), 0), v)

BOOK = {}
def _bk(c, *al):
    BOOK[c.lower()] = c
    for a in al: BOOK[a.lower().rstrip('.')] = c
for c, al in {'Genesis':['Gen'],'Exodus':['Exod','Ex'],'Leviticus':['Lev'],'Numbers':['Num','Numb'],'Deuteronomy':['Deut'],'Joshua':['Josh'],'Judges':['Judg'],'Ruth':[],'1 Samuel':['1 Sam'],'2 Samuel':['2 Sam'],'1 Kings':['1 Kgs'],'2 Kings':['2 Kgs'],'1 Chronicles':['1 Chron','1 Chr'],'2 Chronicles':['2 Chron','2 Chr'],'Ezra':[],'Nehemiah':['Neh'],'Esther':['Esth','Est'],'Job':[],'Psalm':['Ps','Psa','Psalms'],'Proverbs':['Prov'],'Ecclesiastes':['Eccl','Eccles','Ecc'],'Song of Solomon':['Cant','Song'],'Isaiah':['Isa'],'Jeremiah':['Jer'],'Lamentations':['Lam'],'Ezekiel':['Ezek'],'Daniel':['Dan'],'Hosea':['Hos'],'Joel':[],'Amos':[],'Obadiah':['Obad'],'Jonah':[],'Micah':['Mic'],'Nahum':['Nah'],'Habakkuk':['Hab'],'Zephaniah':['Zeph'],'Haggai':['Hag'],'Zechariah':['Zech'],'Malachi':['Mal'],'Matthew':['Matt','Mt'],'Mark':[],'Luke':[],'John':[],'Acts':['Act'],'Romans':['Rom'],'1 Corinthians':['1 Cor'],'2 Corinthians':['2 Cor'],'Galatians':['Gal','Ga'],'Ephesians':['Eph'],'Philippians':['Phil','Philip'],'Colossians':['Col'],'1 Thessalonians':['1 Thess'],'2 Thessalonians':['2 Thess'],'1 Timothy':['1 Tim'],'2 Timothy':['2 Tim'],'Titus':['Tit'],'Philemon':['Philem','Phlm'],'Hebrews':['Heb'],'James':['Jas'],'1 Peter':['1 Pet'],'2 Peter':['2 Pet'],'1 John':[],'2 John':[],'3 John':[],'Jude':[],'Revelation':['Rev']}.items(): _bk(c, *al)

def norm_book(raw):
    if not raw: return None
    s = raw.strip().rstrip('.').lower()
    s = re.sub(r'^iii\s+','3 ',s); s = re.sub(r'^ii\s+','2 ',s); s = re.sub(r'^i\s+','1 ',s)
    return BOOK.get(s)

_BOOKTOK = r'(?:(?:[1-3]|I{1,3})\s+)?[A-Z][a-z]+\.?'
_VNUM = r'\d+(?!\d)(?!\s*:)(?!\s+[A-Za-z])'
_RANGE = rf'{_VNUM}(?:\s*[–—-]\s*\d+)?'
_CLIST = rf'(?:\s*,\s*{_RANGE})*'
# groups: 1=book 2=chap 3=verse 4=cross-chapter-end-chap 5=range-end-verse 6=comma-list
TOK_RE = re.compile(rf'(?:({_BOOKTOK})\s*)?(\d+):\s*(\d+)(?:\s*[–—-]\s*(?:(\d+):)?(\d+))?({_CLIST})')

def _prenorm(g):
    g = re.sub(r'(\d)\s*;\s*(\d)', r'\1:\2', g)
    g = re.sub(r'\b((?:[23]\s*John|Jude|Obadiah|Obad\.|Philemon|Philem\.|Phlm\.))\s+(?=\d)', r'\1 1:', g)
    return g

def expand_versepart(part):
    out = []
    for chunk in (part or '').replace('—','–').split(','):
        chunk = chunk.strip()
        if not chunk: continue
        if '–' in chunk or '-' in chunk:
            sep = '–' if '–' in chunk else '-'
            a,_,b = chunk.partition(sep)
            if a.strip().isdigit() and b.strip().isdigit(): out += range(int(a),int(b)+1)
            elif a.strip().isdigit(): out.append(int(a))
        elif chunk.isdigit(): out.append(int(chunk))
    return out

def tokenize(group, verses, total, resolved, unresolved):
    """Return anchored HTML for a ref-string; update verse store + counters (lists)."""
    group = _prenorm(group)
    state = {'book': None}
    def repl(m):
        b = norm_book(m.group(1))
        if b: state['book'] = b
        book = b or state['book']
        if not book: return m.group(0)
        c1 = int(m.group(2)); v1 = int(m.group(3))
        keyset = []
        if m.group(5):                       # a range end is present
            rend = int(m.group(5))
            if m.group(4):                   # cross-chapter range c1:v1 – c2:rend
                c2 = int(m.group(4))
                for v in range(v1, CHMAX.get((book, c1), v1) + 1): keyset.append(f'{book} {c1}:{v}')
                for cc in range(c1+1, c2):
                    for v in range(1, CHMAX.get((book, cc), 0)+1): keyset.append(f'{book} {cc}:{v}')
                for v in range(1, rend + 1): keyset.append(f'{book} {c2}:{v}')
            else:                            # same-chapter range v1–rend
                for v in range(v1, rend + 1): keyset.append(f'{book} {c1}:{v}')
        else:
            keyset.append(f'{book} {c1}:{v1}')
        # comma-list continuation (verses/ranges in chapter c1)
        keyset += [f'{book} {c1}:{v}' for v in expand_versepart(m.group(6))]
        ok = []
        for k in keyset:
            total[0] += 1
            if k in BSB:
                resolved[0] += 1; ok.append(k); verses[k] = BSB[k]
            else:
                unresolved.append(k)
        if not ok: return m.group(0)
        return f'<a class="vref" role="button" tabindex="0" data-v="{html.escape("|".join(dict.fromkeys(ok)), quote=True)}">{m.group(0)}</a>'
    return TOK_RE.sub(repl, group)

# ---- run over available JSONs ----
verses = {}; refmap = {}; total=[0]; resolved=[0]; unresolved=[]
proofs = {}
for f in sorted(glob.glob('w??_proofs.json')):
    corpus = f[:3]  # wsc/wlc/wcf
    data = json.load(open(f, encoding='utf-8'))
    proofs[corpus] = data
    for pid, entry in data.items():
        for g in entry['groups']:
            rs = g[1]
            if rs and rs not in refmap:
                refmap[rs] = tokenize(rs, verses, total, resolved, unresolved)
pct = 100*resolved[0]/total[0] if total[0] else 0
print(f'corpora: {sorted(proofs)}')
print(f'verse-refs total={total[0]} resolved={resolved[0]} ({pct:.1f}%)  distinct verses={len(verses)}  ref-strings={len(refmap)}')
from collections import Counter
uc = Counter(unresolved)
print(f'unresolved unique={len(uc)}; top:', uc.most_common(15))

# ---- write content files into the repo's content/ dir ----
import os
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'content')
KEYMAP = {'wsc':'WSC','wlc':'WLC','wcf':'WCF'}
with open(os.path.join(OUT,'proofs.js'),'w') as f:
    f.write("/* PCA Constitution — official Scripture proof texts (pcaac.org), footnote-style {ans,groups}. */\n")
    for c in ('wcf','wlc','wsc'):
        if c in proofs:
            f.write(f"window.{KEYMAP[c]}_PROOFS = "+json.dumps(proofs[c],ensure_ascii=False,separators=(',',':'))+";\n")
with open(os.path.join(OUT,'verses.js'),'w') as f:
    f.write("/* Scripture verse text for tappable proofs — Berean Standard Bible (public domain, CC0; bereanbible.com). Only proof-cited verses bundled. */\n")
    f.write("window.VERSES = "+json.dumps(verses,ensure_ascii=False,separators=(',',':'))+";\n")
    f.write("window.PROOF_REFMAP = "+json.dumps(refmap,ensure_ascii=False,separators=(',',':'))+";\n")
print('wrote proofs.js + verses.js for', sorted(KEYMAP[c] for c in proofs))
