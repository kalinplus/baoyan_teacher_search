import sys
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from scholar_client import ScholarAuthorClient


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self._payload


class TestScholarClientPublicationsTruncated(unittest.TestCase):
    def test_publications_truncated_true_when_next_page_exists(self) -> None:
        payload = {
            "author": {"name": "A"},
            "articles": [{"year": "2026"}, {"year": "2025"}],
            "serpapi_pagination": {"next": "https://serpapi.com/search.json?..."},
        }
        client = ScholarAuthorClient(serpapi_key="test-key", timeout=1)

        with patch("scholar_client.requests.get", return_value=_FakeResponse(payload)):
            profile = client.query_structured_info(author_id="abc")

        self.assertTrue(profile["publications_truncated"])

    def test_publications_truncated_false_when_no_next_page(self) -> None:
        payload = {
            "author": {"name": "A"},
            "articles": [{"year": "2026"}],
            "serpapi_pagination": {},
        }
        client = ScholarAuthorClient(serpapi_key="test-key", timeout=1)

        with patch("scholar_client.requests.get", return_value=_FakeResponse(payload)):
            profile = client.query_structured_info(author_id="abc")

        self.assertFalse(profile["publications_truncated"])


if __name__ == "__main__":
    unittest.main()
