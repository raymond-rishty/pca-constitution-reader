#!/usr/bin/env bash
# Regenerate content/proofs.js + content/verses.js from the PCA official proof PDFs
# (pcaac.org) + the Berean Standard Bible. Run from this directory: ./build.sh
# Requires: curl, pdftotext (poppler-utils), python3.
set -euo pipefail
cd "$(dirname "$0")"

UA='constitution-reader/0.1 (personal study)'
fetch() { [ -f "$2" ] || curl -sSL -A "$UA" "$1" -o "$2"; }

echo "1/5  fetching inputs (PDFs + BSB)…"
fetch "https://www.pcaac.org/wp-content/uploads/2019/11/ShorterCatechismwithScriptureProofs.pdf" pca_sc.pdf
fetch "https://www.pcaac.org/wp-content/uploads/2019/11/LargerCatechismwithScriptureProofs1.pdf"  pca_lc.pdf   # WLC Q1-115
fetch "https://www.pcaac.org/wp-content/uploads/2024/02/03-LCLayout2.pdf"                          lc2.pdf      # WLC Q114-196
fetch "https://www.pcaac.org/wp-content/uploads/2022/04/WCFScripureProofs2022.pdf"                 pca_wcf.pdf
fetch "https://bereanbible.com/bsb.txt"                                                            bsb.txt

echo "2/5  WSC  → wsc_proofs.json";  python3 emit_wsc.py  | tail -1
echo "3/5  WLC  → wlc_proofs.json";  python3 parse_wlc.py | tail -1
echo "4/5  WCF  → wcf_proofs.json";  python3 parse_wcf.py | tail -1
echo "5/5  tokenize + emit content/proofs.js + content/verses.js";  python3 build_pca.py | tail -3
echo "done."
