import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from teacher_extractors.thu import (
    extract_thu_ai_fulltime_pi_names,
    extract_thu_au_bdmd_names,
    extract_thu_cs_h2_anchor_names,
    extract_thu_ee_zh_names,
    extract_thu_insc_names,
    extract_thu_iiis_fulltime_and_research_names,
    extract_thu_sigs_cs_names,
    extract_thu_thss_faculty_profiles,
    extract_thu_thss_faculty_names,
)
from teacher_list_core import clean_teacher_names, fetch_html
from teacher_list_core import Rule, SourceRecord, collect_teachers, export_jsonl, extract_name_from_anchor_text


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

    def test_clean_teacher_names_filters_section_keywords(self) -> None:
        raw = ["院系概况", "新闻动态", "研究生招", "姚期智", "段路明", "校友风采"]

        cleaned = clean_teacher_names(raw)

        self.assertEqual(cleaned, ["姚期智", "段路明"])

    def test_clean_teacher_names_filters_software_college_noise(self) -> None:
        raw = ["谷歌", "火狐", "教师名录", "特殊聘任", "教务教学", "张三", "李四"]

        cleaned = clean_teacher_names(raw)

        self.assertEqual(cleaned, ["张三", "李四"])

    def test_extract_name_from_anchor_text_does_not_slice_long_section_text(self) -> None:
        self.assertIsNone(extract_name_from_anchor_text("在运行机构"))
        self.assertIsNone(extract_name_from_anchor_text("历史运行情况"))
        self.assertEqual(extract_name_from_anchor_text("姚期智教授"), "姚期智")

    def test_fetch_html_uses_apparent_encoding_when_default_is_iso88591(self) -> None:
        html = "<h2><a href='/a.htm'>冯建华</a></h2>"
        response = _FakeResponse(content=html.encode("utf-8"), encoding="ISO-8859-1", apparent_encoding="utf-8")

        with patch("teacher_list_core.requests.get", return_value=response):
            decoded = fetch_html("https://example.com", timeout=30)

        self.assertIn("冯建华", decoded)

    def test_extract_thu_thss_faculty_names(self) -> None:
        html = """
        <a href="../faculty/sunjiaguang.htm">孙家广</a>
        <a href="../faculty/guming.htm">顾明</a>
        <a href="../news/a.htm">新闻</a>
        """

        names = extract_thu_thss_faculty_names(html)

        self.assertEqual(names, ["孙家广", "顾明"])

    def test_extract_thu_thss_faculty_profiles(self) -> None:
        html = """
        <a href="../faculty/sunjiaguang.htm">孙家广</a>
        <a href="../faculty/guming.htm">顾明</a>
        <a href="../news/a.htm">新闻</a>
        """

        profiles = extract_thu_thss_faculty_profiles(html, source_url="https://www.thss.tsinghua.edu.cn/szdw/jsml.htm")

        self.assertEqual([p.name for p in profiles], ["孙家广", "顾明"])
        self.assertEqual(profiles[0].profile_url, "../faculty/sunjiaguang.htm")

    def test_extract_thu_ai_fulltime_pi_names_only_between_sz2_and_sz3(self) -> None:
        html = """
        <a name="sz2"></a>
        <h4>董胤蓬</h4>
        <h4>李欣阳</h4>
        <a name="sz3"></a>
        <h4>兼聘老师A</h4>
        """

        names = extract_thu_ai_fulltime_pi_names(html)

        self.assertEqual(names, ["董胤蓬", "李欣阳"])

    def test_extract_thu_iiis_fulltime_and_research_names(self) -> None:
        html = """
        <a name="sz1"></a>
        <h4>姚期智</h4>
        <h4>段路明</h4>
        <a name="sz8"></a>
        <h4>研究员甲</h4>
        <a name="sz4"></a>
        <h4>博士后A</h4>
        """

        names = extract_thu_iiis_fulltime_and_research_names(html)

        self.assertEqual(names, ["姚期智", "段路明", "研究员甲"])

    def test_extract_thu_insc_names_between_keywords(self) -> None:
        html = """
        <a href="/n1.htm">导航A</a>
        学术带头人
        <a href="/t1.htm">吴建平</a>
        <a href="/t2.htm">李星</a>
        <a href="#sec1">教授</a>
        友情链接
        <a href="/n2.htm">底部导航</a>
        """

        names = extract_thu_insc_names(html)

        self.assertEqual(names, ["吴建平", "李星"])

    def test_extract_thu_au_bdmd_names_from_h4s1(self) -> None:
        html = """
        <h4 class="h4s1">周东华</h4>
        <h4 class="h4s1">叶昊</h4>
        <h4>栏目标题</h4>
        """

        names = extract_thu_au_bdmd_names(html)

        self.assertEqual(names, ["周东华", "叶昊"])

    def test_extract_thu_ee_zh_names_from_showtitle(self) -> None:
        html = """
        {"showTitle":"陈明华"}
        {"showTitle":"黄翊东"}
        {"showTitle":"Minghua CHEN"}
        """

        names = extract_thu_ee_zh_names(html)

        self.assertEqual(names, ["陈明华", "黄翊东", "Minghua CHEN"])

    def test_extract_thu_sigs_cs_names_with_keyword_filter(self) -> None:
        items = [
            {"title": "夏树涛", "exField5": "计算机科学与技术"},
            {"title": "郑海涛", "exField5": "信息与通信工程"},
            {"title": "杨余久", "exField5": "人工智能，大数据，Open FIESTA"},
            {"title": "候选A", "exField5": "仪器科学与技术"},
        ]

        with patch("teacher_extractors.thu._fetch_sigs_teacher_home_items", return_value=items):
            names = extract_thu_sigs_cs_names("<html></html>")

        self.assertEqual(names, ["夏树涛", "郑海涛", "杨余久"])

    def test_collect_teachers_outputs_teacher_profiles_contract(self) -> None:
        html = """
        <a href="/faculty/zhangsan.htm">
            <h4>张三</h4>
            <p>副教授</p>
            <h4 class="l2 h4s2">机器学习、计算机视觉</h4>
            <p>zhangsan@mail.tsinghua.edu.cn</p>
        </a>
        <a href="/faculty/lisi.htm">
            <h4>李四</h4>
            <p>教授</p>
        </a>
        """
        response = _FakeResponse(content=html.encode("utf-8"), encoding="utf-8", apparent_encoding="utf-8")
        record = SourceRecord(school="清华大学", college="软件学院", url="https://www.thss.tsinghua.edu.cn/szdw/jsml.htm")

        with patch("teacher_list_core.requests.get", return_value=response):
            payload = collect_teachers(record, timeout=30, rules=[], logger=self)

        self.assertEqual(payload["teachers"], ["张三", "李四"])
        profiles = payload.get("teacher_profiles", [])
        self.assertEqual(len(profiles), 2)
        required_keys = {"name", "profile_url", "email", "interests", "title", "source_url"}
        self.assertTrue(all(required_keys.issubset(set(item.keys())) for item in profiles))
        self.assertTrue(any(item.get("email") for item in profiles))
        self.assertTrue(any(item.get("interests") for item in profiles))

    def test_collect_teachers_fallback_to_rule_when_auto_empty(self) -> None:
        html = """
        <div><h4>王五</h4></div>
        <div><h4>赵六</h4></div>
        """
        response = _FakeResponse(content=html.encode("utf-8"), encoding="utf-8", apparent_encoding="utf-8")
        record = SourceRecord(school="清华大学", college="人工智能学院", url="https://collegeai.tsinghua.edu.cn/rydw.htm")
        rule = Rule(name="fallback_rule", matcher=lambda _: True, extractor=lambda _: ["王五", "赵六"])

        with patch("teacher_list_core.requests.get", return_value=response):
            payload = collect_teachers(record, timeout=30, rules=[rule], logger=self)

        self.assertEqual(payload["teachers"], ["王五", "赵六"])
        self.assertEqual(len(payload.get("teacher_profiles", [])), 2)

    def test_collect_teachers_auto_ignores_navigation_like_names(self) -> None:
        html = """
        <a href="/yxgk/yxjj.htm">院系概况</a>
        <a href="/xwdt/yxdt.htm">新闻动态</a>
        <a href="/faculty/yaoqizhi.htm">姚期智</a>
        <a href="/faculty/duanluming.htm">段路明</a>
        """
        response = _FakeResponse(content=html.encode("utf-8"), encoding="utf-8", apparent_encoding="utf-8")
        record = SourceRecord(school="清华大学", college="交叉信息研究院", url="https://iiis.tsinghua.edu.cn/rydw.htm")

        with patch("teacher_list_core.requests.get", return_value=response):
            payload = collect_teachers(record, timeout=30, rules=[], logger=self)

        self.assertEqual(payload["teachers"], ["姚期智", "段路明"])

    def test_export_jsonl_includes_profile_url(self) -> None:
        result = {
            "school": "清华大学",
            "college": "软件学院",
            "url": "https://www.thss.tsinghua.edu.cn/szdw/jsml.htm",
            "teachers": ["张三"],
            "teacher_profiles": [
                {
                    "name": "张三",
                    "profile_url": "https://www.thss.tsinghua.edu.cn/faculty/zhangsan.htm",
                    "email": "zhangsan@mail.tsinghua.edu.cn",
                    "interests": ["机器学习"],
                    "title": "副教授",
                    "source_url": "https://www.thss.tsinghua.edu.cn/szdw/jsml.htm",
                }
            ],
        }

        with TemporaryDirectory() as temp_dir:
            export_path = Path(temp_dir) / "all_teachers.jsonl"
            export_jsonl(export_path, [result])
            line = export_path.read_text(encoding="utf-8").strip()
            row = json.loads(line)

        self.assertEqual(row["school"], "清华大学")
        self.assertEqual(row["teacher"], "张三")
        self.assertEqual(row["profile_url"], "https://www.thss.tsinghua.edu.cn/faculty/zhangsan.htm")

    def info(self, *_args, **_kwargs) -> None:
        return None


if __name__ == "__main__":
    unittest.main()
