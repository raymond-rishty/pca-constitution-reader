"""Regression checks for the authority-index-only citation feed."""
import importlib.util
import json
import re
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "build_citations.py"
FIXTURE = ROOT / "tests" / "fixtures" / "authority-index-scopes.json"
spec = importlib.util.spec_from_file_location("reader_build_citations", BUILDER)
assert spec and spec.loader
citations = importlib.util.module_from_spec(spec)
spec.loader.exec_module(citations)


class BuildCitationsTests(unittest.TestCase):
    def test_empty_authority_index_cannot_erase_existing_citation_assets(self):
        with tempfile.TemporaryDirectory() as folder:
            temp = Path(folder)
            content = temp / "content"
            cit_dir = content / "cit"
            cit_dir.mkdir(parents=True)
            (content / "bco.js").write_text('{"ref":"43-1"}', encoding="utf-8")
            (content / "wcf.js").write_text('{"ref":"21.5"}', encoding="utf-8")
            (content / "wlc.js").write_text('{"n":65}', encoding="utf-8")
            (content / "wsc.js").write_text('{"n":95}', encoding="utf-8")
            source = temp / "authority_index.json"
            source.write_text("[]", encoding="utf-8")
            counts = content / "citations-counts.js"
            chunk = cit_dir / "bco-43.js"
            counts.write_text("preserve counts", encoding="utf-8")
            chunk.write_text("preserve chunk", encoding="utf-8")
            previous = citations.DIST, citations.AUTHORITY_INDEX, citations.CONTENT, citations.CIT_DIR
            try:
                citations.DIST = str(temp)
                citations.AUTHORITY_INDEX = str(source)
                citations.CONTENT = str(content)
                citations.CIT_DIR = str(cit_dir)
                with self.assertRaisesRegex(ValueError, "existing citation assets were left untouched"):
                    citations.main()
            finally:
                citations.DIST, citations.AUTHORITY_INDEX, citations.CONTENT, citations.CIT_DIR = previous
            self.assertEqual(counts.read_text(encoding="utf-8"), "preserve counts")
            self.assertEqual(chunk.read_text(encoding="utf-8"), "preserve chunk")

    def test_supported_record_types_are_projected_across_reader_scopes(self):
        with tempfile.TemporaryDirectory() as folder:
            temp = Path(folder)
            content = temp / "content"
            (content / "cit").mkdir(parents=True)
            (content / "bco.js").write_text(
                '{"ref":"43-1"},{"ref":"11-3"},{"ref":"11-4"},{"ref":"PP-1"}', encoding="utf-8")
            (content / "wcf.js").write_text('{"ref":"21.5"}', encoding="utf-8")
            (content / "wlc.js").write_text('{"n":65},{"n":66}', encoding="utf-8")
            (content / "wsc.js").write_text('{"n":95}', encoding="utf-8")
            source = temp / "authority_index.json"
            source.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
            previous = citations.DIST, citations.AUTHORITY_INDEX, citations.CONTENT, citations.CIT_DIR
            try:
                citations.DIST = str(temp)
                citations.AUTHORITY_INDEX = str(source)
                citations.CONTENT = str(content)
                citations.CIT_DIR = str(content / "cit")
                citations.main()
                manifest = (content / "citations-counts.js").read_text(encoding="utf-8")
                payload = json.loads(re.search(r"window\.CIT_COUNTS = (\{.*\});", manifest).group(1))
                bco_rows = (content / "cit" / "bco-43.js").read_text(encoding="utf-8")
                scope_rows = (content / "cit" / "bco-11.js").read_text(encoding="utf-8")
                pp_rows = (content / "cit" / "bco-PP.js").read_text(encoding="utf-8")
                wlc_rows = (content / "cit" / "wlc.js").read_text(encoding="utf-8")
                wsc_rows = (content / "cit" / "wsc.js").read_text(encoding="utf-8")
                all_citation_data = "\n".join(path.read_text(encoding="utf-8")
                                                for path in (content / "cit").glob("*.js"))
            finally:
                citations.DIST, citations.AUTHORITY_INDEX, citations.CONTENT, citations.CIT_DIR = previous

        self.assertEqual(payload["bco|43-1"], 1)
        self.assertEqual(payload["bco|PP-1"], 1)
        self.assertEqual(payload["wlc|Q.65"], 1)
        self.assertEqual(payload["wlc|Q.66"], 1)
        self.assertEqual(payload["wsc|Q.95"], 1)
        self.assertEqual(payload["bco|11-3"], 1)
        self.assertEqual(payload["bco|11-4"], 1)
        self.assertNotIn("bco|PP-174", payload)
        self.assertIn("RE J. Lance Acree", bco_rows)
        self.assertIn('"scope":"candidate"', scope_rows)
        self.assertIn('"scope":"contextual"', scope_rows)
        self.assertIn('"t":"ccb"', scope_rows)
        self.assertIn('"scopes":["primary","candidate"]', pp_rows)
        self.assertIn("ga51-p1277", all_citation_data)
        self.assertNotIn("ga51-p1278", all_citation_data)
        self.assertIn('"Q.65"', wlc_rows)
        self.assertIn('"Q.66"', wlc_rows)
        self.assertIn('"Q.95"', wsc_rows)


if __name__ == "__main__":
    unittest.main()
