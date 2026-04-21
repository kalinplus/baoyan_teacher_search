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
from teacher_extractors.sjtu import (
    extract_sjtu_cs_main_profiles,
    extract_sjtu_cse_people_profiles,
    extract_sjtu_gc_profiles,
    extract_sjtu_gift_profiles,
    extract_sjtu_soai_spkz_profiles,
    extract_sjtu_soai_zzjs_profiles,
)
from teacher_list_core import clean_teacher_names, fetch_html
from teacher_list_core import (
    Rule,
    SourceRecord,
    TeacherProfile,
    collect_teachers,
    extract_name_from_anchor_text,
)
from teacher_list_io import export_jsonl
from teacher_list_prescreen import parse_keyword_csv, run_offline_prescreen


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


class _FakeJsonResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self.payload


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

    def test_extract_sjtu_soai_profiles_filters_navigation_links(self) -> None:
        html = """
        <a href="/cn/article/dsj">大事记</a>
        <a href="/cn/list/sydh">生涯导航</a>
        <a href="/cn/facultydetails/zzjs/caoqinxiang">曹钦翔</a>
        <div>副教授</div>
        <div>caoqinxiang@sjtu.edu.cn</div>
        """

        profiles = extract_sjtu_soai_zzjs_profiles(html, source_url="https://soai.sjtu.edu.cn/cn/faculty/zzjs")

        self.assertEqual([p.name for p in profiles], ["曹钦翔"])
        self.assertEqual(profiles[0].profile_url, "/cn/facultydetails/zzjs/caoqinxiang")
        self.assertEqual(profiles[0].title, "副教授")
        self.assertEqual(profiles[0].email, "caoqinxiang@sjtu.edu.cn")

    def test_extract_sjtu_cse_people_profiles(self) -> None:
        html = """
        <div class="PeopleList">
            <ul>
                <li>
                    <div class="w130 fr">
                        <h2>刘雨桐</h2>
                        <p>研究领域：无线感知，多模态融合，态势感知</p>
                        <span><a href="PeopleDetail.aspx?id=466">了 解更多</a></span>
                    </div>
                </li>
                <li>
                    <div class="w130 fr">
                        <h2>赵涵</h2>
                        <p>研究领域：云计算，计算机系统，并行分布式计算</p>
                        <span><a href="PeopleDetail.aspx?id=465">了 解更多</a></span>
                    </div>
                </li>
            </ul>
        </div>
        """

        profiles = extract_sjtu_cse_people_profiles(html, source_url="https://cs.sjtu.edu.cn/cse/People.aspx?id=9")

        self.assertEqual([p.name for p in profiles], ["刘雨桐", "赵涵"])
        self.assertEqual(profiles[0].profile_url, "PeopleDetail.aspx?id=466")
        self.assertIn("无线感知", profiles[0].interests)

    def test_extract_sjtu_cs_main_profiles_uses_ajax_content(self) -> None:
        ajax_content = """
        <div class="rc-item">
            <div class="tit">
                <div class="name">并行与分布式系统研究所</div>
            </div>
            <div class="dt">
                <p>所长：<a href="https://www.cs.sjtu.edu.cn/jiaoshiml/zangbinyu.html">臧斌宇</a></p>
                <p>副所长：<a>John Edward Hopcroft</a></p>
            </div>
            <div class="name-list">
                <span><a href="https://www.cs.sjtu.edu.cn/jiaoshiml/chenhaibo.html">陈海波</a></span>
                <span>孟 魁</span>
            </div>
        </div>
        """
        fake_response = _FakeJsonResponse(payload={"content": ajax_content, "tab_html": ""})

        with patch("teacher_extractors.sjtu.requests.post", return_value=fake_response), patch(
            "teacher_extractors.sjtu.fetch_html",
            side_effect=AssertionError("Fallback page should not be used when ajax has data"),
        ):
            profiles = extract_sjtu_cs_main_profiles(
                "<html></html>",
                source_url="https://www.cs.sjtu.edu.cn/jiaoshiml.html",
            )

        names = [profile.name for profile in profiles]
        self.assertIn("臧斌宇", names)
        self.assertIn("陈海波", names)
        self.assertIn("John Edward Hopcroft", names)
        self.assertIn("孟魁", names)

        profile_map = {profile.name: profile for profile in profiles}
        self.assertEqual(
            profile_map["臧斌宇"].profile_url,
            "https://www.cs.sjtu.edu.cn/jiaoshiml/zangbinyu.html",
        )
        self.assertIsNone(profile_map["John Edward Hopcroft"].profile_url)
        self.assertEqual(profile_map["陈海波"].interests, ["并行与分布式系统研究所"])

    def test_extract_sjtu_soai_spkz_profiles_from_show_cards(self) -> None:
        html = """
        <div class="teamList" id="divresult">
            <ul>
                <li>
                    <a href="/cn/show/369" target="_blank" class="pd">
                        <div class="text">
                            <div class="h3">糜泽羽</div>
                            <div class="p">职称：副教授<br />邮箱：yzmizeyu@sjtu.edu.cn<br /></div>
                        </div>
                    </a>
                </li>
            </ul>
        </div>
        <a href="http://www.echaoweb.com/">上海屹超</a>
        """

        profiles = extract_sjtu_soai_spkz_profiles(html, source_url="https://soai.sjtu.edu.cn/cn/teacher/spkz")

        self.assertEqual([p.name for p in profiles], ["糜泽羽"])
        self.assertEqual(profiles[0].profile_url, "/cn/show/369")
        self.assertEqual(profiles[0].email, "yzmizeyu@sjtu.edu.cn")

    def test_extract_sjtu_gift_profiles_filters_non_teacher_links(self) -> None:
        html = """
        <a href="/joinus">加入我们</a>
        <a href="/faculty?category=双聘/客座">双聘</a>
        <a href="/faculty/40842">鲍华</a>
        <div>教授</div>
        <div>hua.bao@sjtu.edu.cn</div>
        """

        profiles = extract_sjtu_gift_profiles(html, source_url="https://gift.sjtu.edu.cn/faculty")

        self.assertEqual([p.name for p in profiles], ["鲍华"])
        self.assertEqual(profiles[0].profile_url, "/faculty/40842")
        self.assertEqual(profiles[0].email, "hua.bao@sjtu.edu.cn")

    def test_extract_sjtu_gc_profiles_filters_non_teacher_links(self) -> None:
        html = """
        <a href="/about/job-opportunities/">Job Opportunities</a>
        <a href="/about/faculty-staff/faculty-directory/faculty-detail/24">Youyi Bi</a>
        <div>youyi.bi@sjtu.edu.cn</div>
        <a href="/about/faculty-staff/faculty-directory/">Meet Us</a>
        """

        profiles = extract_sjtu_gc_profiles(
            html,
            source_url="https://gc.sjtu.edu.cn/about/faculty-staff/faculty-directory/",
        )

        self.assertEqual([p.name for p in profiles], ["Youyi Bi"])
        self.assertEqual(profiles[0].profile_url, "/about/faculty-staff/faculty-directory/faculty-detail/24")
        self.assertEqual(profiles[0].email, "youyi.bi@sjtu.edu.cn")

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

    def test_collect_teachers_prefers_higher_quality_fallback(self) -> None:
        html = """
        <a href="/cn/article/dsj">大事记</a>
        <a href="/cn/list/sydh">生涯导航</a>
        """
        response = _FakeResponse(content=html.encode("utf-8"), encoding="utf-8", apparent_encoding="utf-8")
        record = SourceRecord(school="上海交通大学", college="人工智能学院", url="https://soai.sjtu.edu.cn/cn/faculty/zzjs")
        fallback_profiles = [
            TeacherProfile(
                name="曹钦翔",
                profile_url="/cn/facultydetails/zzjs/caoqinxiang",
                email="caoqinxiang@sjtu.edu.cn",
                interests=["机器学习"],
                title="副教授",
                source_url=record.url,
            )
        ]
        rule = Rule(
            name="quality_fallback_rule",
            matcher=lambda _: True,
            extractor=lambda _: [],
            profile_extractor=lambda _html, _url: fallback_profiles,
        )

        with patch("teacher_list_core.requests.get", return_value=response):
            payload = collect_teachers(record, timeout=30, rules=[rule], logger=self)

        self.assertEqual(payload["teachers"], ["曹钦翔"])
        self.assertEqual(payload["teacher_profiles"][0]["profile_url"], "https://soai.sjtu.edu.cn/cn/facultydetails/zzjs/caoqinxiang")

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


class TestTeacherOfflinePrescreen(unittest.TestCase):
    def test_parse_keyword_csv_dedup_and_strip(self) -> None:
        keywords = parse_keyword_csv(" 机器学习,计算机视觉,机器学习 ,, ")

        self.assertEqual(keywords, ["机器学习", "计算机视觉"])

    def test_run_offline_prescreen_skips_contacted_and_negative_evidence(self) -> None:
        payload = {
            "school": "清华大学",
            "college": "软件学院",
            "url": "https://www.thss.tsinghua.edu.cn/szdw/jsml.htm",
            "teacher_profiles": [
                {
                    "name": "张三",
                    "profile_url": "https://example.com/faculty/zhangsan",
                    "email": "zhangsan@tsinghua.edu.cn",
                    "interests": ["机器学习"],
                    "title": "教授",
                    "source_url": "https://www.thss.tsinghua.edu.cn/szdw/jsml.htm",
                },
                {
                    "name": "李四",
                    "profile_url": "https://example.com/faculty/lisi",
                    "email": "lisi@tsinghua.edu.cn",
                    "interests": ["计算机视觉", "机器学习"],
                    "title": "副教授",
                    "source_url": "https://www.thss.tsinghua.edu.cn/szdw/jsml.htm",
                },
                {
                    "name": "王五",
                    "profile_url": "https://example.com/faculty/wangwu",
                    "email": None,
                    "interests": [],
                    "title": "教授",
                    "source_url": "https://www.thss.tsinghua.edu.cn/szdw/jsml.htm",
                    "homepage_text": "2026年暂停招生，请勿来信",
                },
            ],
        }

        result = run_offline_prescreen(
            payload,
            top_n=5,
            budget=5,
            keywords=["机器学习"],
            contacted_teachers={"清华大学": {"张三"}},
        )

        self.assertEqual([item["name"] for item in result["top_candidates"]], ["李四"])
        skip_map = {item["name"]: item["skip_reason"] for item in result["skipped"]}
        self.assertEqual(skip_map["张三"], "already_contacted")
        self.assertEqual(skip_map["王五"], "negative_signal_evidence")

    def test_run_offline_prescreen_marks_over_budget(self) -> None:
        payload = {
            "school": "清华大学",
            "college": "软件学院",
            "url": "https://www.thss.tsinghua.edu.cn/szdw/jsml.htm",
            "teacher_profiles": [
                {
                    "name": "甲",
                    "profile_url": "https://example.com/faculty/a",
                    "email": "a@tsinghua.edu.cn",
                    "interests": ["机器学习"],
                    "title": "教授",
                    "source_url": "https://www.thss.tsinghua.edu.cn/szdw/jsml.htm",
                },
                {
                    "name": "乙",
                    "profile_url": "https://example.com/faculty/b",
                    "email": "b@tsinghua.edu.cn",
                    "interests": ["计算机视觉"],
                    "title": "副教授",
                    "source_url": "https://www.thss.tsinghua.edu.cn/szdw/jsml.htm",
                },
                {
                    "name": "丙",
                    "profile_url": None,
                    "email": None,
                    "interests": [],
                    "title": None,
                    "source_url": "https://www.thss.tsinghua.edu.cn/szdw/jsml.htm",
                },
            ],
        }

        result = run_offline_prescreen(
            payload,
            top_n=2,
            budget=1,
            keywords=["机器学习"],
            contacted_teachers={},
        )

        self.assertEqual(len(result["top_candidates"]), 1)
        skipped_names = {item["name"] for item in result["skipped"] if item["skip_reason"] == "over_budget"}
        self.assertTrue({"乙", "丙"}.issubset(skipped_names))
        self.assertEqual(result["stats"]["over_budget_skipped"], 2)

    def test_run_offline_prescreen_fail_fast_on_invalid_profile(self) -> None:
        payload = {
            "school": "清华大学",
            "college": "软件学院",
            "url": "https://www.thss.tsinghua.edu.cn/szdw/jsml.htm",
            "teacher_profiles": [{"profile_url": "https://example.com/faculty/a"}],
        }

        with self.assertRaises(ValueError):
            run_offline_prescreen(
                payload,
                top_n=10,
                budget=10,
                keywords=[],
                contacted_teachers={},
            )

    def test_run_offline_prescreen_uses_external_scoring_config(self) -> None:
        payload = {
            "school": "清华大学",
            "college": "软件学院",
            "url": "https://www.thss.tsinghua.edu.cn/szdw/jsml.htm",
            "teacher_profiles": [
                {
                    "name": "甲",
                    "profile_url": "https://example.com/faculty/a",
                    "email": "a@tsinghua.edu.cn",
                    "interests": ["机器学习"],
                    "title": "教授",
                    "source_url": "https://www.thss.tsinghua.edu.cn/szdw/jsml.htm",
                }
            ],
        }

        custom_config = {
            "negative_signal_keywords": ["暂停招生"],
            "negative_interest_keywords": ["艺术"],
            "evidence_fields": ["homepage_text"],
            "title_keywords": {
                "senior": ["教授"],
                "mid": ["副教授"],
            },
            "weights": {
                "profile_url_bonus": 1,
                "profile_url_person_like_bonus": 0,
                "missing_profile_url_penalty": 0,
                "has_email_bonus": 1,
                "missing_email_penalty": 0,
                "senior_title_bonus": 1,
                "mid_title_bonus": 0,
                "other_title_bonus": 0,
                "has_interests_bonus": 1,
                "missing_interests_penalty": 0,
                "keyword_match_per_hit_bonus": 1,
                "keyword_match_bonus_cap": 1,
                "negative_keyword_match_per_hit_penalty": 2,
                "negative_keyword_match_penalty_cap": 4,
                "neutral_penalty": 1,
            },
            "thresholds": {
                "score_min": 0,
                "score_max": 100,
                "tier_a_min": 90,
                "tier_b_min": 50,
            },
        }

        with TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "prescreen_scoring.json"
            config_path.write_text(json.dumps(custom_config, ensure_ascii=False), encoding="utf-8")

            result = run_offline_prescreen(
                payload,
                top_n=5,
                budget=5,
                keywords=["机器学习"],
                contacted_teachers={},
                scoring_config_path=config_path,
            )

        self.assertEqual(result["top_candidates"][0]["score"], 5)
        self.assertEqual(result["top_candidates"][0]["tier"], "C")

    def test_keyword_whole_word_match_avoids_substring(self) -> None:
        payload = {
            "school": "清华大学",
            "college": "软件学院",
            "url": "https://www.thss.tsinghua.edu.cn/szdw/jsml.htm",
            "teacher_profiles": [
                {
                    "name": "甲",
                    "profile_url": "https://example.com/faculty/a",
                    "email": "a@tsinghua.edu.cn",
                    "interests": ["EMAIL security", "FAIL analysis"],
                    "title": "教授",
                    "source_url": "https://www.thss.tsinghua.edu.cn/szdw/jsml.htm",
                }
            ],
        }

        result = run_offline_prescreen(
            payload,
            top_n=5,
            budget=5,
            keywords=["AI"],
            contacted_teachers={},
        )

        self.assertEqual(result["top_candidates"][0]["matched_keywords"], [])
        self.assertNotIn("keyword_match:AI", result["top_candidates"][0]["reasons"])

    def test_negative_keyword_penalty(self) -> None:
        payload = {
            "school": "清华大学",
            "college": "软件学院",
            "url": "https://www.thss.tsinghua.edu.cn/szdw/jsml.htm",
            "teacher_profiles": [
                {
                    "name": "甲",
                    "profile_url": "https://example.com/faculty/a",
                    "email": "a@tsinghua.edu.cn",
                    "interests": ["艺术设计", "机器学习"],
                    "title": "教授",
                    "source_url": "https://www.thss.tsinghua.edu.cn/szdw/jsml.htm",
                }
            ],
        }

        result = run_offline_prescreen(
            payload,
            top_n=5,
            budget=5,
            keywords=["机器学习"],
            negative_keywords=["艺术"],
            contacted_teachers={},
        )

        candidate = result["top_candidates"][0]
        self.assertIn("艺术", candidate["matched_negative_keywords"])
        self.assertIn("negative_keyword_match:艺术", candidate["reasons"])
        # profile_url 30 + person_like 8 + email 25 + senior_title 10 + has_interests 10
        # + keyword_match(机器学习) 4 - negative_keyword_match(艺术) 5 = 82
        self.assertEqual(candidate["score"], 82)

    def test_neutral_penalty_when_no_match(self) -> None:
        payload = {
            "school": "清华大学",
            "college": "软件学院",
            "url": "https://www.thss.tsinghua.edu.cn/szdw/jsml.htm",
            "teacher_profiles": [
                {
                    "name": "甲",
                    "profile_url": "https://example.com/faculty/a",
                    "email": "a@tsinghua.edu.cn",
                    "interests": ["数据库", "网络安全"],
                    "title": "教授",
                    "source_url": "https://www.thss.tsinghua.edu.cn/szdw/jsml.htm",
                }
            ],
        }

        result = run_offline_prescreen(
            payload,
            top_n=5,
            budget=5,
            keywords=["NLP"],
            negative_keywords=["艺术"],
            contacted_teachers={},
        )

        candidate = result["top_candidates"][0]
        self.assertIn("neutral_penalty", candidate["reasons"])
        # profile_url 30 + person_like 8 + email 25 + senior_title 10 + has_interests 10
        # - neutral_penalty 1 = 82
        self.assertEqual(candidate["score"], 82)


if __name__ == "__main__":
    unittest.main()
