#!/usr/bin/env python3
"""Geometry-aware PCA proof parser. Separates answer/footnote/marker by font
height (immune to layout interleaving). Validates WSC against wsc-pca.html truth."""
import re, html as H, subprocess, sys

# height bands (pts)
def band(h):
    if 8.4 <= h <= 10.0: return 'body'
    if 7.0 <= h < 8.0:   return 'foot'
    if 5.8 <= h < 7.0:   return 'mark'   # superscript marker/label
    return 'other'

WORD = re.compile(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">([^<]*)</word>')
LET = 'abcdefghiklmnopqrstuwxyz'
PRIMES = "´ʹ′'ʼ"

def bbox_xml(pdf):
    return subprocess.run(['pdftotext','-bbox-layout',pdf,'-'],capture_output=True,text=True).stdout

HEADER=re.compile(r'SHORTER CATECHISM|LARGER CATECHISM|CONFESSION OF FAITH')
def lines_in_order(xml):
    """Yield per line: list of (band, text) words, in reading order. Skip running headers."""
    out=[]
    for lm in re.finditer(r'<line[^>]*>(.*?)</line>', xml, re.S):
        ws=[(band(float(m.group(4))-float(m.group(2))), H.unescape(m.group(5))) for m in WORD.finditer(lm.group(1))]
        if not ws: continue
        if HEADER.search(' '.join(w for _,w in ws)): continue
        if re.fullmatch(r'\d{1,4}', ''.join(w for _,w in ws).strip()): continue  # bare page-number line
        out.append(ws)
    return out

BOOKS=r'Gen|Exod|Ex|Lev|Num|Deut|Josh|Judg|Ruth|1 Sam|2 Sam|1 Kings|2 Kings|1 Chron|2 Chron|Ezra|Neh|Esth|Est|Job|Ps|Prov|Eccl|Cant|Isa|Jer|Lam|Ezek|Dan|Hos|Joel|Amos|Obad|Jonah|Mic|Nah|Hab|Zeph|Hag|Zech|Mal|Matt|Mark|Luke|John|Acts|Rom|1 Cor|2 Cor|Gal|Eph|Phil|Col|1 Thess|2 Thess|1 Tim|2 Tim|Titus|Philem|Heb|James|1 Pet|2 Pet|1 John|2 John|3 John|Jude|Rev'
REF=re.compile(rf'\b({BOOKS})\.?\s+(\d+:\d+(?:[–-]\d+(?::\d+)?)?(?:,\s*\d+(?:[–-]\d+)?)*)')
def extract_refs(text):
    flat=re.sub(r'\s+',' ',text)
    flat=re.sub(r'(\d)\s*[–-]\s*(\d)', r'\1–\2', flat)   # tighten ranges split by bbox words
    flat=re.sub(r'(\d):\s+(\d)', r'\1:\2', flat)          # "3: 16" -> "3:16"
    return [f'{m.group(1)} {m.group(2)}' for m in REF.finditer(flat)]

def parse_catechism(pdf):
    lines=lines_in_order(bbox_xml(pdf))
    LABEL=re.compile(rf'^([{LET}][{PRIMES}]*)\.$')
    # Pass 1: markers in reading order (with question), and body answer tokens.
    markers=[]; answers={}; cur_q=None
    flat=[]   # flattened (band, text, is_line_first)
    for ws in lines:
        for j,(b,t) in enumerate(ws):
            flat.append((b,t,j==0))
    n=len(flat)
    for k,(b,t,first) in enumerate(flat):
        if b=='body':
            if re.fullmatch(r'Q\.?',t) and k+1<n:
                mn=re.match(r'(\d+)\.?',flat[k+1][1])
                if mn: cur_q=f'Q.{mn.group(1)}'; answers.setdefault(cur_q,[])
            if cur_q: answers[cur_q].append(('w',t))
        elif b=='mark' and re.fullmatch(rf'[{LET}][{PRIMES}]*',t):
            markers.append((t,cur_q))
            if cur_q: answers[cur_q].append(('m',t))
    # Pass 2: footnotes, segmented by line-first label words, sequence-guided by markers.
    expected=[lt for lt,_ in markers]
    footnotes=[]; fi=0
    for ws in lines:
        for j,(b,t) in enumerate(ws):
            if b!='foot': continue
            m=LABEL.match(t)
            if m and j==0 and fi<len(expected) and m.group(1)==expected[fi]:
                footnotes.append({'label':m.group(1),'text':''}); fi+=1
            elif footnotes:
                footnotes[-1]['text']+=' '+t
    return markers, footnotes, answers

# ---- ground truth from wsc-pca.html ----
def wsc_truth(path):
    h=open(path,encoding='utf-8').read()
    out={}
    blocks=re.split(r'<div id=question-(\d+)', h)
    for i in range(1,len(blocks),2):
        qn=blocks[i]; body=blocks[i+1]
        groups=[]
        ul=re.search(r'<ul class=footnotes>(.*?)</ul>', body, re.S)
        if ul:
            for li in re.finditer(r'<li>(.*?)</li>', ul.group(1), re.S):
                disps=re.findall(r'<a title="([^"]+)"[^>]*class=bibleref', li.group(1))
                if disps: groups.append([H.unescape(d).strip() for d in disps])
        out[f'Q.{qn}']=groups
    return out

# canonical first-verse keys for comparison
BOOK={}
def _bk(c,*al):
    BOOK[c.lower()]=c
    for a in al: BOOK[a.lower().rstrip('.')]=c
for c,al in {'Genesis':['Gen'],'Exodus':['Exod','Ex'],'Leviticus':['Lev'],'Numbers':['Num','Numb'],'Deuteronomy':['Deut'],'Joshua':['Josh'],'Judges':['Judg'],'Ruth':[],'1 Samuel':['1 Sam'],'2 Samuel':['2 Sam'],'1 Kings':['1 Kgs'],'2 Kings':['2 Kgs'],'1 Chronicles':['1 Chron','1 Chr'],'2 Chronicles':['2 Chron','2 Chr'],'Ezra':[],'Nehemiah':['Neh'],'Esther':['Esth','Est'],'Job':[],'Psalm':['Ps','Psa'],'Proverbs':['Prov'],'Ecclesiastes':['Eccl','Eccles'],'Song of Solomon':['Cant','Song'],'Isaiah':['Isa'],'Jeremiah':['Jer'],'Lamentations':['Lam'],'Ezekiel':['Ezek'],'Daniel':['Dan'],'Hosea':['Hos'],'Joel':[],'Amos':[],'Obadiah':['Obad'],'Jonah':[],'Micah':['Mic'],'Nahum':['Nah'],'Habakkuk':['Hab'],'Zephaniah':['Zeph'],'Haggai':['Hag'],'Zechariah':['Zech'],'Malachi':['Mal'],'Matthew':['Matt'],'Mark':[],'Luke':[],'John':[],'Acts':['Act'],'Romans':['Rom'],'1 Corinthians':['1 Cor'],'2 Corinthians':['2 Cor'],'Galatians':['Gal'],'Ephesians':['Eph'],'Philippians':['Phil'],'Colossians':['Col'],'1 Thessalonians':['1 Thess'],'2 Thessalonians':['2 Thess'],'1 Timothy':['1 Tim'],'2 Timothy':['2 Tim'],'Titus':['Tit'],'Philemon':['Philem'],'Hebrews':['Heb'],'James':[],'1 Peter':['1 Pet'],'2 Peter':['2 Pet'],'1 John':[],'2 John':[],'3 John':[],'Jude':[],'Revelation':['Rev']}.items(): _bk(c,*al)
# chapter sizes for cross-chapter range expansion (from bsb.txt)
CHMAX={}
for _l in open('bsb.txt',encoding='utf-8-sig'):
    _m=re.match(r'^(.+?)\s+(\d+):(\d+)\t',_l)
    if _m:
        k=(_m.group(1).strip(),int(_m.group(2))); CHMAX[k]=max(CHMAX.get(k,0),int(_m.group(3)))
def _nb(raw):
    s=raw.strip().rstrip('.').lower()
    s=re.sub(r'^iii\s+','3 ',s);s=re.sub(r'^ii\s+','2 ',s);s=re.sub(r'^i\s+','1 ',s)
    return BOOK.get(s)
def keys(refstrs):
    """Expand to full set of 'Book ch:v' keys (lists, ranges, cross-chapter, single-chapter books)."""
    s=set()
    for r in refstrs:
        r=re.sub(r'(\d)\s*;\s*(\d)',r'\1:\2',r)
        r=re.sub(r'\b((?:[23]\s*John|Jude|Obadiah|Obad\.|Philemon|Philem\.|Phlm\.))\s+(?=\d)',r'\1 1:',r)
        for m in re.finditer(r'((?:[1-3]\s)?[A-Z][a-z]+)\.?\s+(\d+):(\d+)(?:[–-](\d+)(?::(\d+))?)?((?:,\s*\d+(?:[–-]\d+)?)*)',r):
            b=_nb(m.group(1))
            if not b: continue
            c1,v1=int(m.group(2)),int(m.group(3))
            if m.group(5):                       # cross-chapter range c1:v1 – c2:v2
                c2,v2=int(m.group(4)),int(m.group(5))
                for v in range(v1,CHMAX.get((b,c1),v1)+1): s.add(f'{b} {c1}:{v}')
                for v in range(1,v2+1): s.add(f'{b} {c2}:{v}')
            elif m.group(4):                     # same-chapter range
                for v in range(v1,int(m.group(4))+1): s.add(f'{b} {c1}:{v}')
            else:
                s.add(f'{b} {c1}:{v1}')
            for chunk in re.findall(r'\d+(?:[–-]\d+)?', m.group(6) or ''):
                if '–' in chunk or '-' in chunk:
                    a,_,z=chunk.partition('–' if '–' in chunk else '-')
                    for v in range(int(a),int(z)+1): s.add(f'{b} {c1}:{v}')
                else: s.add(f'{b} {c1}:{int(chunk)}')
    return s

if __name__=='__main__':
    markers,footnotes,answers=parse_catechism('pca_sc.pdf')
    print(f'markers={len(markers)}  footnotes={len(footnotes)}  questions={len(answers)}')
    # zip markers<->footnotes; assign refs to marker's question
    fn_refs=[extract_refs(f['text']) for f in footnotes]
    qgroups={}
    n=min(len(markers),len(footnotes))
    for k in range(n):
        letter,q=markers[k]
        qgroups.setdefault(q,[]).append(fn_refs[k])
    # label-agreement check
    agree=sum(1 for k in range(n) if markers[k][0]==footnotes[k]['label'])
    print(f'marker/footnote label agreement: {agree}/{n}')
    truth=wsc_truth('wscpca.html')
    ok=bad=0; ex=[]
    for q in sorted(truth,key=lambda x:int(x[2:])):
        tk=keys(sum(truth[q],[])); pk=keys(sum(qgroups.get(q,[]),[]))
        if tk==pk and len(truth[q])==len(qgroups.get(q,[])): ok+=1
        else:
            bad+=1
            if len(ex)<8: ex.append((q,len(truth[q]),len(qgroups.get(q,[])),sorted(tk-pk)[:3],sorted(pk-tk)[:3]))
    print(f'WSC questions exactly matching truth: {ok}/{len(truth)}  mismatch:{bad}')
    for q,lt,lp,miss,extra in ex:
        print(f'  {q}: groups t={lt} p={lp}  miss={miss} extra={extra}')
