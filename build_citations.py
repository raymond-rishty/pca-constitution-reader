#!/usr/bin/env python3
"""Derive citations from the GA repository's curated authority projection.

The generated ``index/authority_index.json`` is the only relationship source.
For BCO provisions, only matches at or above the high-confidence threshold
pass the display cutoff; other constitutional books retain all scopes. Scope
and evidence metadata remain in the derived rows for provenance, but BCO pages
do not display scope labels.
This builder does not scan record bodies or reinterpret provision references.

Output (split for lazy loading; see the app's loader):
  content/citations-counts.js   window.CIT_COUNTS = { "comp|ref": <total>, ... }  (tiny, eager)
  content/cit/bco-<NN>.js       window.CIT["bco-<NN>"] = { "<ref>": [rows], ... } (one per BCO chapter)
  content/cit/{wcf,wlc,wsc}.js  window.CIT["<comp>"]   = { "<ref>": [rows], ... }
Each row carries record, scope, and evidence metadata and is sorted newest-first.
URLs point at the live GA site.
"""
import json, re, collections, os
from pathlib import Path

# The Pages build mounts the GA repository at /workspace/dist/pca-ga.  Keeping
# the root configurable makes the generator reproducible locally as well as in
# CI, while all derived citation assets still live in this repository.
DIST = os.environ.get("PCA_GA_DIST", "/workspace/dist/pca-ga")
AUTHORITY_INDEX = os.path.join(DIST, "index", "authority_index.json")
ROOT = os.path.dirname(os.path.abspath(__file__))   # repo root (works in a worktree too)
CONTENT = os.path.join(ROOT, "content")
CIT_DIR = os.path.join(CONTENT, "cit")
GA_BASE = "https://raymond-rishty.github.io/pca-ga/"

def valid_refs():
    """The set of provision refs the app can actually display, keyed by
    component. Citations to anything outside this set (phantom keys from OCR
    noise or RAO refs) are dropped so they never inflate counts."""
    v = {"bco": set(), "wcf": set(), "wlc": set(), "wsc": set()}
    bco = Path(CONTENT, "bco.js").read_text(encoding="utf-8")
    v["bco"] = set(re.findall(r'"ref":\s*"((?:\d+-\d+|PP-\d+))"', bco))
    wcf = Path(CONTENT, "wcf.js").read_text(encoding="utf-8")
    v["wcf"] = set(re.findall(r'"ref":\s*"(\d+\.\d+)"', wcf))
    for comp, fn in (("wlc", "wlc.js"), ("wsc", "wsc.js")):
        txt = Path(CONTENT, fn).read_text(encoding="utf-8")
        v[comp] = {f"Q.{n}" for n in re.findall(r'"n":\s*(\d+)', txt)}
    return v

TYPE_CODE = {
    "Judicial case": "case",
    "Overture": "ov",
    "Constitutional inquiry": "inq",
    "CCB advice": "ccb",
    "RPR exception": "rpr",
}

MATCH_CONFIDENCE_RANK = {"low": 0, "medium": 1, "high": 2}
BCO_MATCH_CONFIDENCE_THRESHOLD = "high"

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
    m = re.match(r'^(?:WLC|LC)\s*(?:Q\.?\s*)?([0-9]{1,3})', p, re.I)
    if m:
        return ("wlc", f"Q.{int(m.group(1))}")
    m = re.match(r'^(?:WSC|SC)\s*(?:Q\.?\s*)?([0-9]{1,3})', p, re.I)
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


# The GA case-provision index preserves the wording found in the source, so a
# Westminster Larger Catechism reference may be a single question, a range,
# or a question with a letter suffix (e.g. WLC 166B).  The Constitution Reader
# has one route per question; normalize those forms at this boundary.
WLC_INDEX_RE = re.compile(
    r"^\s*WLC\s+(?:Q\.?\s*)?(?P<start>\d{1,3})(?:[A-Za-z])?"
    r"(?:\s*[-–]\s*(?P<end>\d{1,3})(?:[A-Za-z])?)?\s*$",
    re.I,
)


def index_wlc_refs(value):
    """Return Constitution Reader WLC routes represented by an index value.

    Letter suffixes identify a variant of the same question (166B -> Q.166).
    Ranges are expanded, including abbreviated endings such as 65-6 -> 65-66.
    """
    match = WLC_INDEX_RE.fullmatch(str(value or ""))
    if not match:
        return []
    start = int(match.group("start"))
    end_text = match.group("end")
    if not end_text:
        end = start
    else:
        end = int(end_text)
        if end < start:
            # Interpret an abbreviated ending using the same digit place as
            # the ending token: 65-6 => 66, 170-5 => 175.
            place = 10 ** len(end_text)
            end = (start // place) * place + end
            while end < start:
                end += place
    # A malformed OCR range should not explode into an enormous citation set.
    if end - start > 32:
        return [f"Q.{start}"]
    return [f"Q.{number}" for number in range(start, end + 1)]


def ga_url(value):
    """Convert a GA-relative Markdown path to its stable public HTML URL."""
    path = str(value or "").replace("\\", "/")
    if path.startswith("http://") or path.startswith("https://"):
        return re.sub(r"\.md(#|$)", r".html\1", path)
    return GA_BASE + re.sub(r"\.md(#|$)", r".html\1", path.lstrip("./"))


def display_case_number(value):
    value = str(value or "").strip()
    match = re.fullmatch(r"(\d{4})-(\d+)", value)
    if match:
        return f"{match.group(1)}-{int(match.group(2)):02d}"
    return value


def case_title(row):
    title = (row.get("title") or "").strip()
    numbers = [display_case_number(n) for n in (row.get("case_numbers") or []) if str(n).strip()]
    label = "/".join(numbers)
    if label and title and not title.startswith(label):
        return f"{label} — {title}"
    return title or label or "Judicial case"


def reader_occurrence(row):
    """Select a source location matching the relationship's displayed scope."""
    occurrences = [item for item in (row.get("occurrences") or []) if item.get("url")]
    if not occurrences:
        return None
    preferred_scope = row.get("reader_scope")
    scoped = [item for item in occurrences if item.get("reader_scope") == preferred_scope]
    pool = scoped or occurrences
    scope_rank = {"primary": 0, "contextual": 1, "candidate": 2}
    kind_rank = {"proposal_target": 0, "explicit_citation": 1,
                 "structured_exception_tag": 2, "structured_provision_tag": 3,
                 "structured_case_reference": 4, "body_mention": 5}
    return min(pool, key=lambda item: (
        scope_rank.get(item.get("reader_scope"), 9),
        kind_rank.get(item.get("relationship_kind"), 9),
        str(item.get("url") or ""),
        int((item.get("locator") or {}).get("line") or 0),
    ))


def load_authority_rows():
    if not os.path.exists(AUTHORITY_INDEX):
        raise FileNotFoundError(f"Missing generated GA authority index: {AUTHORITY_INDEX}")
    with open(AUTHORITY_INDEX, encoding="utf-8") as source:
        return json.load(source)

def main():
    data = load_authority_rows()
    table = collections.defaultdict(list)   # "comp|ref" -> [entry,...]
    seen = collections.defaultdict(dict)     # dedupe records while merging their evidence scopes
    skipped = collections.Counter()
    kept_provstrings = set()
    VALID = valid_refs()
    dropped_invalid = collections.Counter()

    def add(comp, ref, entry, identity=None):
        if ref not in VALID.get(comp, ()):    # phantom key (OCR noise / RAO) — not a real provision
            dropped_invalid[f"{comp}|{ref}"] += 1
            return
        key = f"{comp}|{ref}"
        identity = identity or entry["url"]
        previous = seen[key].get(identity)
        if previous:
            scope_order = {"primary": 0, "contextual": 1, "candidate": 2}
            previous["scopes"] = sorted(set(previous.get("scopes", [])) | set(entry.get("scopes", [])),
                                        key=lambda scope: scope_order.get(scope, 9))
            for field in ("relationship_kinds", "evidence_bases", "match_methods", "match_confidences"):
                previous[field] = sorted(set(previous.get(field, [])) | set(entry.get(field, [])))
            if scope_order.get(entry.get("scope"), 9) < scope_order.get(previous.get("scope"), 9):
                for field in ("scope", "url", "relationship_kind", "evidence_basis", "match_method", "match_confidence"):
                    previous[field] = entry.get(field)
            return
        seen[key][identity] = entry
        table[key].append(entry)

    for row in data:
        type_code = TYPE_CODE.get(row.get("type"))
        if type_code is None:
            continue
        provision = str(row.get("provision") or "")
        if not provision:
            continue
        if re.match(r"^\s*WLC\b", provision, re.I):
            refs = [("wlc", ref) for ref in index_wlc_refs(provision)]
        else:
            normalized = norm(provision)
            refs = [normalized] if normalized else []
        if not refs:
            skipped[provision] += 1
            continue
        occurrences = row.get("occurrences") or []
        occurrence = reader_occurrence(row)
        if occurrences and occurrence is None:
            continue
        url_value = (occurrence or {}).get("url") or row.get("url") or ""
        record_id = str(row.get("record_id") or row.get("relationship_id") or url_value)
        scope = row.get("reader_scope") or (occurrence or {}).get("reader_scope") or "candidate"
        scope_order = {"primary": 0, "contextual": 1, "candidate": 2}
        scopes = set(row.get("scopes") or [scope])
        scopes.update(item.get("reader_scope") for item in occurrences if item.get("reader_scope"))
        scopes = sorted(scopes, key=lambda value: scope_order.get(value, 9))
        relationship_kind = (occurrence or {}).get("relationship_kind") or row.get("relationship_kind") or ""
        evidence_basis = (occurrence or {}).get("evidence_basis") or row.get("evidence_basis") or ""
        match_method = (occurrence or {}).get("match_method") or row.get("match_method") or ""
        match_confidence = (occurrence or {}).get("match_confidence") or row.get("match_confidence") or ""
        entry = {
            "t": type_code,
            "ttl": case_title(row) if row.get("type") == "Judicial case" else (row.get("title") or "").strip(),
            "yr": row.get("year"),
            "disp": (row.get("disposition") or "").strip(),
            "url": ga_url(url_value),
            "scope": scope,
            "scopes": scopes,
            "relationship_kind": relationship_kind,
            "relationship_kinds": list(row.get("relationship_kinds") or ([relationship_kind] if relationship_kind else [])),
            "evidence_basis": evidence_basis,
            "evidence_bases": list(row.get("evidence_bases") or ([evidence_basis] if evidence_basis else [])),
            "match_method": match_method,
            "match_methods": list(row.get("match_methods") or ([match_method] if match_method else [])),
            "match_confidence": match_confidence,
            "match_confidences": [match_confidence] if match_confidence else [],
        }
        for comp, ref in refs:
            if comp == "bco" and MATCH_CONFIDENCE_RANK.get(match_confidence, -1) < MATCH_CONFIDENCE_RANK[BCO_MATCH_CONFIDENCE_THRESHOLD]:
                continue
            kept_provstrings.add(provision)
            add(comp, ref, entry, record_id)

    if not table:
        raise ValueError(
            "No supported authority-index records map to displayed provisions; "
            "existing citation assets were left untouched."
        )

    # sort each provision's actions newest-first, then by type
    torder = {"case":0,"ov":1,"inq":2,"ccb":3,"rpr":4}
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
    with open(os.path.join(CONTENT, "citations-counts.js"), "w", encoding="utf-8") as output:
        output.write(
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
        with open(os.path.join(CIT_DIR, f"{fid}.js"), "w", encoding="utf-8") as output:
            output.write(f'window.CIT=window.CIT||{{}};window.CIT[{json.dumps(fid)}]={body};\n')

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
