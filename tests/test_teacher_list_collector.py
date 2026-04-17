import sys
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from teacher_extractors.thu import extract_thu_cs_h2_anchor_names
from teacher_list_core import clean_teacher_names, fetch_html


class _FakeResponse:
    def __init__(self, content: bytes, encoding: str, apparent_encoding: str):
        self.content = content
        self.encoding = encoding
        self.apparent_encoding = apparent_encoding

    def raise_for_status(self) -> None:
        return None

    @property
    def text(self) -> str:
        return self.content.decode(self.encoding, errors="replace")


class TestTeacherListCollectorRules(unittest.TestCase):
    def test_extract_thu_cs_h2_anchor_names(self) -> None:
        html = """
        <div class=\"text\"><h2><a href=\"/a.htm\" title=\"冯建华\">冯建华</a></h2></div>
        <div class=\"text\"><h2><a href=\"/b.htm\" title=\"李涓子\">李涓子</a></h2></div>
        <div class=\"text\"><h2><a href=\"/c.htm\" title=\"周强\">周强</a></h2></div>
        """

        names = extract_thu_cs_h2_anchor_names(html)

        self.assertEqual(names, ["冯建华", "李涓子", "周强"])

    def test_clean_teacher_names_filters_non_name_noise(self) -> None:
        raw = ["首页", "冯建华", "冯建华", "Minghua CHEN", " 周强 ", "下页", "李涓子"]

        cleaned = clean_teacher_names(raw)

        self.assertEqual(cleaned, ["冯建华", "周强", "李涓子"])

    def test_fetch_html_uses_apparent_encoding_when_default_is_iso88591(self) -> None:
        html = "<h2><a href='/a.htm'>冯建华</a></h2>"
        response = _FakeResponse(content=html.encode("utf-8"), encoding="ISO-8859-1", apparent_encoding="utf-8")

        with patch("teacher_list_core.requests.get", return_value=response):
            decoded = fetch_html("https://example.com", timeout=30)

        self.assertIn("冯建华", decoded)


if __name__ == "__main__":
    unittest.main()
