#!/usr/bin/env python3
"""Emit wsc_proofs.json {Q.n:{ans,groups}} from the validated bbox parser."""
import json, re
import bbox_parse as B

markers, footnotes, answers = B.parse_catechism('pca_sc.pdf')
fn_refs = [B.extract_refs(f['text']) for f in footnotes]

# group assignment: k-th marker <-> k-th footnote
q_groups = {}
n = min(len(markers), len(footnotes))
for k in range(n):
    letter, q = markers[k]
    q_groups.setdefault(q, []).append([footnotes[k]['label'], ', '.join(fn_refs[k])])

def rejoin(s):
    return re.sub(r'(\w)- (\w)', r'\1\2', s)

def build_ans(tokens):
    # tokens: list of ('w',word)/('m',letter); take after the 'A.' answer marker
    out = []
    started = False
    for kind, t in tokens:
        if not started:
            if kind == 'w' and re.fullmatch(r'A\.?', t):
                started = True
            continue
        if kind == 'w':
            out.append(('w', t))
        else:
            out.append(('m', t))
    # assemble: words space-joined, markers glued to preceding
    s = ''
    for kind, t in out:
        if kind == 'w':
            s += (' ' if s and not s.endswith(' ') else '') + t
        else:
            s = s.rstrip() + f'<sup>{t}</sup>'
    return rejoin(s.strip())

result = {}
for q, toks in answers.items():
    result[q] = {'ans': build_ans(toks), 'groups': q_groups.get(q, [])}

# order by question number
result = {f'Q.{i}': result[f'Q.{i}'] for i in range(1, 108) if f'Q.{i}' in result}
json.dump(result, open('wsc_proofs.json', 'w'), ensure_ascii=False, indent=0)
print('WSC questions:', len(result))
print('Q.1:', json.dumps(result['Q.1'], ensure_ascii=False))
print('Q.26:', json.dumps(result['Q.26'], ensure_ascii=False))
# sanity: every grouped Q has <sup>; count groups
nosup = [q for q,v in result.items() if v['groups'] and '<sup>' not in v['ans']]
print('grouped-but-no-sup:', nosup)
print('total groups:', sum(len(v['groups']) for v in result.values()))
