#!/usr/bin/env python3
"""Run page-preserving PaddleOCR over the Hodge commentary PDF."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import fitz
import numpy as np
from paddleocr import PaddleOCR


DEFAULT_PDF = Path(r"C:\git\pca-reader-content-packs\commentaryonconf00hodg.pdf")
DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "content" / "hodge-wcf-paddle-ocr.pages.jsonl"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def completed_pages(path: Path) -> set[int]:
    if not path.exists():
        return set()
    pages: set[int] = set()
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                pages.add(int(json.loads(line)["page"]))
    return pages


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--dpi", type=int, default=300)
    parser.add_argument("--device", default="gpu:0")
    parser.add_argument("--start-page", type=int, default=1, help="1-based inclusive")
    parser.add_argument("--end-page", type=int, help="1-based inclusive; defaults to the last PDF page")
    parser.add_argument("--resume", action="store_true", help="Skip pages already in the JSONL output")
    args = parser.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    already_done = completed_pages(args.output) if args.resume else set()
    mode = "a" if args.resume else "w"
    scale = args.dpi / 72
    doc = fitz.open(args.pdf)
    end_page = args.end_page or len(doc)
    if args.start_page < 1 or end_page > len(doc) or args.start_page > end_page:
        raise ValueError(f"Page range {args.start_page}–{end_page} is outside this {len(doc)}-page PDF")

    print(f"Source SHA-256: {sha256(args.pdf)}", flush=True)
    print(f"PaddleOCR 3.7.0 / PP-OCRv6 medium; PaddlePaddle 3.2.2; device={args.device}; dpi={args.dpi}", flush=True)
    print(f"Pages {args.start_page}–{end_page} of {len(doc)} -> {args.output}", flush=True)
    ocr = PaddleOCR(
        lang="en",
        device=args.device,
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
    )

    done_now = 0
    with args.output.open(mode, encoding="utf-8", newline="\n") as output:
        for page_number in range(args.start_page, end_page + 1):
            if page_number in already_done:
                continue
            page = doc[page_number - 1]
            pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False, colorspace=fitz.csRGB)
            image = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
            prediction = next(iter(ocr.predict(image)))
            data = prediction.get("res", prediction)
            texts = list(data.get("rec_texts", []))
            scores = list(data.get("rec_scores", []))
            boxes = list(data.get("rec_boxes", []))
            if not (len(texts) == len(scores) == len(boxes)):
                raise ValueError(f"Unequal OCR arrays on PDF page {page_number}")
            lines = []
            for text, score, box in zip(texts, scores, boxes):
                coords = box.tolist() if hasattr(box, "tolist") else list(box)
                lines.append({
                    "text": str(text),
                    "score": float(score),
                    "box": [int(round(float(value))) for value in coords],
                })
            record = {
                "page": page_number,
                "width": pix.width,
                "height": pix.height,
                "lines": lines,
            }
            output.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
            output.flush()
            done_now += 1
            if done_now % 10 == 0 or page_number == end_page:
                print(f"OCR complete through PDF page {page_number} ({done_now} new pages this run)", flush=True)

    print(f"Finished {done_now} new pages.", flush=True)


if __name__ == "__main__":
    main()
