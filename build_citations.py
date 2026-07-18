#!/usr/bin/env python3
"""Derive the Constitution app's citation data from the GA-minutes corpus
search_index.json (the authoritative provision->action index).

Output (split for lazy loading; see the app's loader):
  content/citations-counts.js   window.CIT_COUNTS = { "comp|ref": <total>, ... }  (tiny, eager)
  content/cit/bco-<NN>.js       window.CIT["bco-<NN>"] = { "<ref>": [rows], ... } (one per BCO chapter)
  content/cit/{wcf,wlc,wsc}.js  window.CIT["<comp>"]   = { "<ref>": [rows], ... }
Each row is {t,ttl,yr,disp,url}, sorted newest-first. URLs point at the live GA site.
"""
import json, re, collections, sys, os, glob

SRC = "/workspace/dist/pca-ga/app/search_index.json"
CASES_DIR = "/workspace/dist/pca-ga/cases"
ROOT = os.path.dirname(os.path.abspath(__file__))   # repo root (works in a worktree too)
CONTENT = os.path.join(ROOT, "content")
CIT_DIR = os.path.join(CONTENT, "cit")
GA_BASE = "https://raymond-rishty.github.io/pca-ga/"

def valid_refs():
    """The set of provision refs the app can actually display, keyed by
    component. Citations to anything outside this set (phantom keys from OCR
    noise or RAO refs) are dropped so they never inflate counts."""
    v = {"bco": set(), "wcf": set(), "wlc": set(), "wsc": set()}
    bco = open(f"{CONTENT}/bco.js").read()
    v["bco"] = set(re.findall(r'"ref":\s*"(?:\d+-\d+|PP-\d+)"', bco))
    wcf = open(f"{CONTENT}/wcf.js").read()
    v["wcf"] = set(re.findall(r'"ref":\s*"(\d+\.\d+)"', wcf))
    for comp, fn in (("wlc", "wlc.js"), ("wsc", "wsc.js")):
        txt = open(f"{CONTENT}/{fn}").read()
        v[comp] = {f"Q.{n}" for n in re.findall(r'"n":\s*(\d+)', txt)}
    return v

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

    # Preliminary Principles (front matter in the BCO) -----------------------
    m = re.match(r'^(?:BCO\s*)?(?:PP|P\.P\.|Preliminary\s+Principles?)\s*'
                 r'(?:#|-|\.)?\s*(?:II\.)?([1-8])\b', p, re.I)
    if m:
        return ("bco", f"PP-{int(m.group(1))}")

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
    m = re.match(r'^(BCO\s*)?([0-9]{1,2})\s*-\s*([0-9]{1,2})(.*)', p, re.I)
    if m:
        had_prefix = bool(m.group(1))
        rest = m.group(4)
        # Prefix-less refs are ambiguous: RAO/RONR use deeper numbering like
        # "16-3.e.5" or "14-9g". A real BCO section is just NN-S, so when there
        # is no explicit BCO prefix, reject a trailing letter or third level.
        if not had_prefix and re.match(r'\s*[.\-]?[a-z]|\s*\.[0-9]', rest, re.I):
            return None
        return ("bco", f"{int(m.group(2))}-{int(m.group(3))}")
    return None

DIST = "/workspace/dist/pca-ga"

# Inline reference patterns for document bodies. The corpus index barely tags
# Westminster refs (3 WSC strings in all of search_index), yet the prose cites
# the Confession and Catechisms inline under many spellings — so we mine bodies.
BCO_INLINE = re.compile(r'_?BCO_?\s*(\d{1,2})-(\d{1,2})[A-Za-z.]*', re.I)
WCF_INLINE = re.compile(
    r'(?:WCF|W\.C\.F\.|(?:Westminster )?Confession(?: of Faith)?)[,\s]*'
    r'(?:ch(?:apter)?\.?\s*)?(\d{1,2})\s*[-.]\s*(\d{1,2})', re.I)
WLC_INLINE = re.compile(
    r'(?:WLC|W\.L\.C\.|Larger Catechism)[,\s]*(?:Q(?:uestion)?s?\.?\s*)?(\d{1,3})', re.I)
WSC_INLINE = re.compile(
    r'(?:WSC|W\.S\.C\.|Shorter Catechism)[,\s]*(?:Q(?:uestion)?s?\.?\s*)?(\d{1,3})', re.I)
PP_INLINE = re.compile(
    r'(?:_?Preliminary_?\s+_?Principles?_?|PP|P\.P\.?)\s*(?:#|-|\.)?\s*(?:II\.)?\d'
    r'(?:\s*(?:,|&|and)\s*(?:II\.)?\d)*', re.I)

def inline_refs(txt, westminster_only):
    """Yield (comp, ref) for every Constitution reference found in a body."""
    for m in WCF_INLINE.finditer(txt):
        yield ("wcf", f"{int(m.group(1))}.{int(m.group(2))}")
    for m in WLC_INLINE.finditer(txt):
        yield ("wlc", f"Q.{int(m.group(1))}")
    for m in WSC_INLINE.finditer(txt):
        yield ("wsc", f"Q.{int(m.group(1))}")
    # Preliminary Principles are BCO front matter and may occur in any corpus
    # body, including RPR exceptions (which otherwise use Westminster-only scans).
    for m in PP_INLINE.finditer(txt):
        for n in re.findall(r'\d+', m.group(0)):
            yield ("bco", f"PP-{int(n)}")
    if not westminster_only:
        for m in BCO_INLINE.finditer(txt):
            nr = norm(f"BCO {m.group(1)}-{m.group(2)}")
            if nr:
                yield nr

def scan_dir(add, subdir, type_code, westminster_only):
    """Parse a catalogue dir (cases/overtures/inquiries/rpr/studies) for header
    metadata + inline refs; link each to the catalogue page. For the indexed
    types we take Westminster refs only (BCO already comes from the index, with
    its canonical URLs) to avoid double-counting."""
    n_files = n_refs = 0
    for path in sorted(glob.glob(os.path.join(DIST, subdir, "*.md"))):
        txt = open(path).read()
        head = txt[:800]
        mt = re.search(r'^#\s+(.+)', txt, re.M)
        title = mt.group(1).strip() if mt else os.path.basename(path)
        my = re.search(r'\((\d{4})\)', head)                       # Assembly/First-raised year
        year = int(my.group(1)) if my else None
        md = re.search(r'\*\*(?:Final [Dd]isposition|Disposition)\:\*\*\s*([^\n·]+)', head)
        disp = md.group(1).strip() if md else ""
        if len(disp) > 60:
            disp = disp[:57].rstrip() + "…"
        rel = os.path.relpath(path, DIST)
        url = GA_BASE + re.sub(r'\.md$', '.html', rel)
        entry = {"t": type_code, "ttl": title, "yr": year, "disp": disp, "url": url}
        provset = set(inline_refs(txt, westminster_only))
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
    VALID = valid_refs()
    dropped_invalid = collections.Counter()

    def add(comp, ref, entry):
        if ref not in VALID.get(comp, ()):    # phantom key (OCR noise / RAO) — not a real provision
            dropped_invalid[f"{comp}|{ref}"] += 1
            return
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

    # Body scans. Cases aren't in the index at all → take all refs (BCO + WS).
    # The other types ARE indexed for BCO, but their Westminster references are
    # almost entirely untagged, so we harvest those from the bodies.
    cf, cr = scan_dir(add, "cases", "case", westminster_only=False)
    print(f"scanned cases: {cf} files, {cr} provision links (BCO + Westminster)")
    for subdir, code in (("overtures","ov"), ("inquiries","inq"), ("rpr/exc","rpr"), ("studies","pp")):
        f, r = scan_dir(add, subdir, code, westminster_only=True)
        print(f"scanned {subdir}: {f} files, {r} Westminster links")

    # sort each provision's actions newest-first, then by type
    torder = {"case":0,"ov":1,"inq":2,"rpr":3,"pp":4}
    for key, rows in table.items():
        rows.sort(key=lambda e: (-(e["yr"] or 0), torder.get(e["t"],9)))

    # ---- emit: a tiny eager counts manifest + lazy per-file row data ----
    def fileid(comp, ref):
        return f"bco-{ref.split('-')[0]}" if comp == "bco" else comp

    # group rows into files; build the counts manifest
    files = collections.defaultdict(dict)   # fileid -> { ref: [rows] }
    counts = {}                             # "comp|ref" -> total
    for key, rows in table.items():
        comp, ref = key.split("|", 1)
        counts[key] = len(rows)
        files[fileid(comp, ref)][ref] = rows

    # counts manifest (eager): powers reading-view badges + "has citations" checks
    cnt_payload = "{" + ",".join(
        f'{json.dumps(k)}:{counts[k]}' for k in sorted(counts)) + "}"
    open(os.path.join(CONTENT, "citations-counts.js"), "w").write(
        "/* citations-counts.js — per-provision GA-citation totals (eager; powers badges).\n"
        "   Row data is split into content/cit/*.js, loaded on demand. Regenerate with build_citations.py. */\n"
        f"window.GA_BASE = {json.dumps(GA_BASE)};\n"
        f"window.CIT_COUNTS = {cnt_payload};\n")

    # per-file row data (lazy): bco-<chapter>.js (including bco-PP.js),
    # wcf.js, wlc.js, wsc.js
    os.makedirs(CIT_DIR, exist_ok=True)
    for f in os.listdir(CIT_DIR):           # clear stale files so nothing orphans
        if f.endswith(".js"):
            os.remove(os.path.join(CIT_DIR, f))
    for fid, refs in files.items():
        body = "{" + ",".join(
            f'{json.dumps(r)}:{json.dumps(refs[r], ensure_ascii=False, separators=(",",":"))}'
            for r in sorted(refs)) + "}"
        open(os.path.join(CIT_DIR, f"{fid}.js"), "w").write(
            f'window.CIT=window.CIT||{{}};window.CIT[{json.dumps(fid)}]={body};\n')

    # drop the obsolete monolithic file if present
    old = os.path.join(CONTENT, "citations.js")
    if os.path.exists(old):
        os.remove(old)

    # report
    bycomp = collections.Counter(k.split("|")[0] for k in table)
    total_rows = sum(len(v) for v in table.values())
    print(f"wrote citations-counts.js + {len(files)} cit/*.js files")
    print(f"provisions with citations: {len(table)}  ({dict(bycomp)})")
    print(f"total citation rows: {total_rows}")
    print(f"dropped phantom keys (not real provisions): {len(dropped_invalid)} distinct, "
          f"{sum(dropped_invalid.values())} occurrences; e.g. "
          f"{[k for k,_ in dropped_invalid.most_common(8)]}")
    print(f"distinct provision strings kept: {len(kept_provstrings)}")
    top_skips = skipped.most_common(15)
    print(f"skipped provision strings (distinct {len(skipped)}); top:")
    for s,c in top_skips:
        print(f"   {c:4d}  {s!r}")
    # spot-check a few
    for probe in ["bco|PP-1","bco|24-1","bco|13-6","wcf|21.5","wlc|Q.158"]:
        rows = table.get(probe, [])
        print(f"  {probe}: {len(rows)} rows" + (f"  e.g. {rows[0]['yr']} {rows[0]['t']} — {rows[0]['ttl'][:50]}" if rows else ""))

if __name__ == "__main__":
    main()
