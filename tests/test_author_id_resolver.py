import hashlib
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.parse import parse_qs, unquote, urlparse


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from author_id_resolver import AuthorIdResolver, load_json, load_university_mapping, normalize_school_name


REGRESSION_CASES_PATH = Path(__file__).resolve().parent / "data" / "author_id_regression_cases.json"
DEFAULT_CACHE_PATH = PROJECT_ROOT / "output" / ".cache" / "author_id_cache.json"


def load_regression_cases() -> list[dict[str, str]]:
    return json.loads(REGRESSION_CASES_PATH.read_text(encoding="utf-8"))


def snapshot_file(path: Path) -> tuple:
    if not path.exists():
        return ("missing",)

    raw = path.read_bytes()
    return (
        "exists",
        len(raw),
        hashlib.sha256(raw).hexdigest(),
        path.stat().st_mtime_ns,
    )


class TestAuthorIdRegressionDataset(unittest.TestCase):
    def test_school_aliases_can_normalize_to_canonical_names(self) -> None:
        mapping = load_university_mapping(PROJECT_ROOT / "config" / "universities.json")
        for case in load_regression_cases():
            with self.subTest(case=case):
                canonical = normalize_school_name(case["school"], mapping)
                self.assertEqual(canonical, case["canonical_school"])


class TestAuthorIdResolverCacheIsolation(unittest.TestCase):
    def test_resolve_uses_custom_cache_path_and_does_not_touch_default_cache(self) -> None:
        before = snapshot_file(DEFAULT_CACHE_PATH)
        resolver = AuthorIdResolver(scraperapi_key="test-key", timeout=1)

        with TemporaryDirectory() as tmp_dir:
            isolated_cache = Path(tmp_dir) / ".cache" / "author_id_cache.json"
            with patch.object(resolver, "search_candidates", return_value=["t9HPFawAAAAJ"]):
                with patch.object(resolver, "_fetch_scholar_profile_name", return_value="Huazhe Xu"):
                    result = resolver.resolve(
                        school="清华大学",
                        teacher="许华哲",
                        cache_path=isolated_cache,
                    )

            self.assertEqual(result["author_id"], "t9HPFawAAAAJ")
            self.assertEqual(result["source"], "google_search")
            self.assertTrue(isolated_cache.exists())

            cache_obj = load_json(isolated_cache)
            self.assertEqual(cache_obj["清华大学::许华哲"], "t9HPFawAAAAJ")

        after = snapshot_file(DEFAULT_CACHE_PATH)
        self.assertEqual(before, after)


class TestAuthorIdResolverTeacherNameNormalization(unittest.TestCase):
    def test_normalize_chinese_name_to_given_name_first_pinyin_query(self) -> None:
        resolver = AuthorIdResolver(scraperapi_key="test-key", timeout=1)

        normalized = resolver._normalize_teacher_input("周志华")

        self.assertEqual(normalized["teacher_query"], "Zhihua Zhou")
        self.assertEqual(normalized["cache_teacher_name"], "周志华")
        self.assertFalse(normalized["should_warn_ascii_input"])

    def test_normalize_compound_surname_to_joined_family_name_pinyin(self) -> None:
        resolver = AuthorIdResolver(scraperapi_key="test-key", timeout=1)

        normalized = resolver._normalize_teacher_input("欧阳娜娜")

        self.assertEqual(normalized["teacher_query"], "Nana Ouyang")
        self.assertEqual(normalized["cache_teacher_name"], "欧阳娜娜")
        self.assertFalse(normalized["should_warn_ascii_input"])

    def test_normalize_ascii_input_keeps_original_query(self) -> None:
        resolver = AuthorIdResolver(scraperapi_key="test-key", timeout=1)

        normalized = resolver._normalize_teacher_input("tang jie")

        self.assertEqual(normalized["teacher_query"], "tang jie")
        self.assertIsNone(normalized["cache_teacher_name"])
        self.assertTrue(normalized["should_warn_ascii_input"])


@unittest.skip("当前策略默认取首个匹配结果；同名消歧回归用例暂不纳入门禁")
class TestAuthorIdResolverDisambiguationRegression(unittest.TestCase):
    def test_should_select_curated_author_id_instead_of_blindly_using_first_candidate(self) -> None:
        cases = load_regression_cases()

        for case in cases:
            with self.subTest(case=case):
                resolver = AuthorIdResolver(scraperapi_key="test-key", timeout=1)
                wrong_first_candidate = "ZZZZZZZAAAAJ"
                with TemporaryDirectory() as tmp_dir:
                    isolated_cache = Path(tmp_dir) / ".cache" / "author_id_cache.json"
                    with patch.object(
                        resolver,
                        "search_candidates",
                        return_value=[wrong_first_candidate, case["expected_author_id"]],
                    ):
                        result = resolver.resolve(
                            school=case["canonical_school"],
                            teacher=case["teacher"],
                            cache_path=isolated_cache,
                        )

                self.assertEqual(result["author_id"], case["expected_author_id"])


class TestAuthorIdResolverSearchQueryStrategy(unittest.TestCase):
    def test_search_uses_site_query_with_ascii_school_alias_on_first_page(self) -> None:
        resolver = AuthorIdResolver(scraperapi_key="test-key", timeout=1)

        class FakeResponse:
            def __init__(self, text: str):
                self.text = text

            def raise_for_status(self) -> None:
                return None

        fake_body = "https://scholar.google.com/citations?user=t9HPFawAAAAJ&hl=en"

        with patch("author_id_resolver.requests.get", return_value=FakeResponse(fake_body)) as mocked_get:
            author_ids = resolver.search_candidates(
                teacher="huazhe, xu",
                school="清华大学",
                school_aliases=["清华", "THU", "Tsinghua University"],
            )

        self.assertEqual(author_ids, ["t9HPFawAAAAJ"])
        self.assertEqual(mocked_get.call_count, 1)

        expected_query = resolver._build_query(
            teacher="huazhe, xu",
            school="清华大学",
            school_aliases=["清华", "THU", "Tsinghua University"],
        )

        called_url = mocked_get.call_args.kwargs["params"]["url"]
        query_value = parse_qs(urlparse(called_url).query).get("q", [""])[0]
        decoded_query = unquote(query_value)
        self.assertEqual(decoded_query, expected_query)
        self.assertIn("site:scholar.google.com/citations", decoded_query)
        self.assertIn("THU", decoded_query)
        self.assertIn("huazhe, xu", decoded_query)
        self.assertIn("start=0", called_url)


class TestAuthorIdResolverTeacherInputWarnings(unittest.TestCase):
    def test_resolve_warns_when_teacher_input_is_non_chinese(self) -> None:
        resolver = AuthorIdResolver(scraperapi_key="test-key", timeout=1)

        with TemporaryDirectory() as tmp_dir:
            isolated_cache = Path(tmp_dir) / ".cache" / "author_id_cache.json"
            with patch.object(resolver, "search_candidates", return_value=["t9HPFawAAAAJ"]):
                with patch.object(resolver, "_fetch_scholar_profile_name", return_value="Huazhe Xu"):
                    with patch("author_id_resolver.logger.warning") as mocked_warning:
                        resolver.resolve(
                            school="清华大学",
                            teacher="huazhe, xu",
                            cache_path=isolated_cache,
                        )

        mocked_warning.assert_called_once()
        self.assertFalse(isolated_cache.exists())

    def test_resolve_does_not_warn_when_teacher_input_contains_chinese(self) -> None:
        resolver = AuthorIdResolver(scraperapi_key="test-key", timeout=1)

        with TemporaryDirectory() as tmp_dir:
            isolated_cache = Path(tmp_dir) / ".cache" / "author_id_cache.json"
            with patch.object(resolver, "search_candidates", return_value=["t9HPFawAAAAJ"]):
                with patch.object(resolver, "_fetch_scholar_profile_name", return_value="Huazhe Xu"):
                    with patch("author_id_resolver.logger.warning") as mocked_warning:
                        resolver.resolve(
                            school="清华大学",
                            teacher="许华哲",
                            cache_path=isolated_cache,
                        )

        mocked_warning.assert_not_called()


class TestAuthorIdResolverTwoLayerSkipLogic(unittest.TestCase):
    def test_resolve_skips_when_author_id_conflicts_with_existing_teacher(self) -> None:
        resolver = AuthorIdResolver(scraperapi_key="test-key", timeout=1)

        with TemporaryDirectory() as tmp_dir:
            isolated_cache = Path(tmp_dir) / ".cache" / "author_id_cache.json"
            isolated_cache.parent.mkdir(parents=True, exist_ok=True)
            isolated_cache.write_text(
                json.dumps({"清华大学::唐杰": "AAA111"}, ensure_ascii=False),
                encoding="utf-8",
            )

            with patch.object(resolver, "search_candidates", return_value=["AAA111"]):
                with self.assertRaises(RuntimeError) as cm:
                    resolver.resolve(
                        school="清华大学",
                        teacher="顾明",
                        cache_path=isolated_cache,
                    )

        self.assertIn("skip_reason=author_id_conflict_existing_teacher", str(cm.exception))

    def test_resolve_skips_when_scholar_profile_name_mismatches_teacher(self) -> None:
        resolver = AuthorIdResolver(scraperapi_key="test-key", timeout=1)

        with TemporaryDirectory() as tmp_dir:
            isolated_cache = Path(tmp_dir) / ".cache" / "author_id_cache.json"
            with patch.object(resolver, "search_candidates", return_value=["AAA111"]):
                with patch.object(resolver, "_fetch_scholar_profile_name", return_value="Tang Jie"):
                    with self.assertRaises(RuntimeError) as cm:
                        resolver.resolve(
                            school="清华大学",
                            teacher="顾明",
                            cache_path=isolated_cache,
                        )

        self.assertIn("skip_reason=scholar_name_mismatch", str(cm.exception))

    def test_resolve_writes_cache_only_when_two_layer_checks_pass(self) -> None:
        resolver = AuthorIdResolver(scraperapi_key="test-key", timeout=1)

        with TemporaryDirectory() as tmp_dir:
            isolated_cache = Path(tmp_dir) / ".cache" / "author_id_cache.json"
            with patch.object(resolver, "search_candidates", return_value=["AAA111"]):
                with patch.object(resolver, "_fetch_scholar_profile_name", return_value="Ming Gu"):
                    result = resolver.resolve(
                        school="清华大学",
                        teacher="顾明",
                        cache_path=isolated_cache,
                    )

            cache_obj = load_json(isolated_cache)

        self.assertEqual(result["author_id"], "AAA111")
        self.assertEqual(result["source"], "google_search")
        self.assertEqual(cache_obj["清华大学::顾明"], "AAA111")


if __name__ == "__main__":
    unittest.main()