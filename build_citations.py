#!/usr/bin/env python3
"""Derive content/citations.js for the Constitution app from the GA-minutes
corpus search_index.json (the authoritative provision->action index).

Output: window.CITATIONS keyed "component|ref" matching the Constitution app's
own provision refs (bco "24-1", wcf "21.5", wlc/wsc "Q.158"), each value a list
of {t,ttl,sub,yr,disp,url} sorted newest-first. URLs point at the live GA site.
"""
import json, re, collections, sys, os, glob

SRC = "/workspace/dist/pca-ga/app/search_index.json"
CASES_DIR = "/workspace/dist/pca-ga/cases"
OUT = "/workspace/constitution-app/content/citations.js"
GA_BASE = "https://raymond-rishty.github.io/pca-ga/"

TYPE_CODE = {
    "Judicial case": "case",
    "Overture": "ov",
    "Constitutional inquiry": "inq",
    "RPR exception": "rpr",
    "Position paper": "pp",
}

SCRIPTURE = {"acts","hebrews","romans","ephesians","exodus","daniel","luke",
             "philippians","revelation","matthew","john","psalm","psalms",
             "genesis","corinthians","timothy","galatians","colossians",
             "peter","james","jude","isaiah","jeremiah","deuteronomy"}

def norm(prov):
    """Normalise one corpus provision string to (component, ref) or None.
    Rolls subsection letters/decimals up to chapter-section for BCO and to
    chapter.section for WCF. Returns None for out-of-scope refs (RAO, RONR,
    Scripture, chapter-only, garbage)."""
    p = prov.strip().strip("()[].,;: ")
    if not p:
        return None
    low = p.lower()
    # drop scripture book citations
    if low.split()[0].rstrip("0123456789:- ") in SCRIPTURE:
        return None
    # families we don't carry in the strict constitution
    if re.match(r'^(RAO|RONR|OMSJC|BOD|FG|RoD|DfW)\b', p, re.I):
        return None

    # Westminster ------------------------------------------------------------
    m = re.match(r'^WCF\s*([0-9]{1,2})\s*[-.]\s*([0-9]{1,2})', p, re.I)
    if m:
        return ("wcf", f"{int(m.group(1))}.{int(m.group(2))}")
    m = re.match(r'^(?:WLC|LC)\s*([0-9]{1,3})', p, re.I)
    if m:
        return ("wlc", f"Q.{int(m.group(1))}")
    m = re.match(r'^(?:WSC|SC)\s*([0-9]{1,3})', p, re.I)
    if m:
        return ("wsc", f"Q.{int(m.group(1))}")

    # BCO --------------------------------------------------------------------
    # accept "BCO 24-1", "BCO24-1", or a bare "24-1" (the corpus drops the
    # prefix when the OCR split it). Require chapter-section (a dash) so we
    # don't guess at chapter-only refs.
    m = re.match(r'^(?:BCO\s*)?([0-9]{1,2})\s*-\s*([0-9]{1,2})', p, re.I)
    if m:
        return ("bco", f"{int(m.group(1))}-{int(m.group(2))}")
    return None

# inline provision references inside a case body (the index doesn't tag cases)
INLINE_RE = re.compile(
    r'_?BCO_?\s*\d{1,2}-\d{1,2}[A-Za-z.]*'
    r'|WCF\s*\d{1,2}[-.]\d{1,2}'
    r'|(?:WLC|WSC|LC)\s*\d{1,3}', re.I)

def scan_cases(add):
    """Parse cases/*.md for header metadata + inline provision refs; feed each
    (provision -> case) into add(comp, ref, entry)."""
    n_files = n_refs = 0
    for path in sorted(glob.glob(os.path.join(CASES_DIR, "*.md"))):
        txt = open(path).read()
        mt = re.search(r'^#\s+(.+)', txt, re.M)
        title = mt.group(1).strip() if mt else os.path.basename(path)
        my = re.search(r'\*\*Assembly:\*\*[^()\n]*\((\d{4})\)', txt)
        year = int(my.group(1)) if my else None
        md = re.search(r'\*\*Disposition:\*\*\s*([^\n]+)', txt)
        disp = md.group(1).strip() if md else ""
        if len(disp) > 60:
            disp = disp[:57].rstrip() + "…"
        url = GA_BASE + "cases/" + re.sub(r'\.md$', '.html', os.path.basename(path))
        entry = {"t": "case", "ttl": title, "sub": "", "yr": year, "disp": disp, "url": url}
        provset = set()
        for m in INLINE_RE.finditer(txt):
            nr = norm(m.group(0).replace("_", " "))
            if nr:
                provset.add(nr)
        if provset:
            n_files += 1
        for comp, ref in provset:
            add(comp, ref, entry)
            n_refs += 1
    return n_files, n_refs

def main():
    data = json.load(open(SRC))
    table = collections.defaultdict(list)   # "comp|ref" -> [entry,...]
    seen = collections.defaultdict(set)      # dedupe (key, url)
    skipped = collections.Counter()
    kept_provstrings = set()

    def add(comp, ref, entry):
        key = f"{comp}|{ref}"
        if entry["url"] in seen[key]:
            return
        seen[key].add(entry["url"])
        table[key].append(entry)

    for r in data:
        provs = r.get("provisions") or []
        if not provs:
            continue
        t = TYPE_CODE.get(r.get("type"), None)
        if t is None:
            continue
        # overtures point at the verbatim minutes page with a #page anchor;
        # catalogue pages are clean .md — convert .md→.html in both shapes.
        url = GA_BASE + re.sub(r'\.md(#|$)', r'.html\1', r.get("url", ""))
        entry = {
            "t": t,
            "ttl": (r.get("title") or "").strip(),
            "sub": (r.get("sub") or "").strip(),
            "yr": r.get("year"),
            "disp": (r.get("disposition") or "").strip(),
            "url": url,
        }
        for prov in provs:
            nr = norm(prov)
            if nr is None:
                skipped[prov] += 1
                continue
            comp, ref = nr
            kept_provstrings.add(prov)
            add(comp, ref, entry)

    # judicial cases: not indexed by provision — harvest inline refs from bodies
    case_files, case_refs = scan_cases(add)
    print(f"scanned cases: {case_files} files contributed {case_refs} provision links")

    # sort each provision's actions newest-first, then by type
    torder = {"case":0,"ov":1,"inq":2,"rpr":3,"pp":4}
    for key, rows in table.items():
        rows.sort(key=lambda e: (-(e["yr"] or 0), torder.get(e["t"],9)))

    # emit
    keys = sorted(table)
    payload = "{\n" + ",\n".join(
        f'  {json.dumps(k)}: {json.dumps(table[k], ensure_ascii=False, separators=(",",":"))}'
        for k in keys
    ) + "\n}"
    js = (
        "/* citations.js — derived from the PCA GA-minutes corpus search_index.json.\n"
        "   Maps each Constitution provision to the real GA actions that cite it.\n"
        "   Links resolve to the live GA Minutes site. Regenerate with build_citations.py. */\n"
        f'window.GA_BASE = {json.dumps(GA_BASE)};\n'
        f"window.CITATIONS = {payload};\n"
    )
    open(OUT, "w").write(js)

    # report
    bycomp = collections.Counter(k.split("|")[0] for k in table)
    total_rows = sum(len(v) for v in table.values())
    print(f"wrote {OUT}")
    print(f"provisions with citations: {len(table)}  ({dict(bycomp)})")
    print(f"total citation rows: {total_rows}")
    print(f"distinct provision strings kept: {len(kept_provstrings)}")
    top_skips = skipped.most_common(15)
    print(f"skipped provision strings (distinct {len(skipped)}); top:")
    for s,c in top_skips:
        print(f"   {c:4d}  {s!r}")
    # spot-check a few
    for probe in ["bco|24-1","bco|13-6","wcf|21.5","wlc|Q.158","bco|31-2"]:
        rows = table.get(probe, [])
        print(f"  {probe}: {len(rows)} rows" + (f"  e.g. {rows[0]['yr']} {rows[0]['t']} — {rows[0]['ttl'][:50]}" if rows else ""))

if __name__ == "__main__":
    main()
