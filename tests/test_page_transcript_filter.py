"""PPT/文档整页视觉转写结果净化 —— 回归测试 (2026-10-09, agent40)

背景事故
--------
1. **拍到别人电脑屏幕**：标定页 1537 p35 是会场后排拍到的一台笔记本屏幕，
   画面里是另一位研究者（清华 章鹏超/陈昌盛/冯牧野）的**未发表课件**。
   1815 字转写里只有 138 字属于本 deck，其余是 WPS ribbon + 任务栏。
   直接入库 = 把别人的未发表成果塞进我们的检索池。
2. **GUI 截图噪声**：1254 p10 是 MATLAB GUI 截图，1029 字里绝大部分是界面
   文案。agent35 的词表只有中文 Office/WPS，英文 GUI 全漏。
3. **模型违反"不要总结"指令**：约 3% 的页末尾被追加
   ``核心文字内容（幻灯片正文）：`` + 一串 ``- 标题：… / - 作者：…`` 摘要，
   这段不是幻灯片原文。

本测试锁定的行为
----------------
- chrome 剔除（功能区 / GUI 控件 / 任务栏 / 未激活水印）
- 拍摄屏幕拦截（``chrome_ratio`` 判据，**建议**转人工，不是自动丢弃）
- 尾随总结段切除
- **不误伤真实科研内容**（本任务最大风险，单独成组硬断言）

实测基线（agent40，349 页真实转写 / 355 份文本）
------------------------------------------------
- chrome_ratio 非零页 9/355，阈值 15% 命中 5 份（1254p10 x2 / 1537p35 /
  1268p20 / 1540p12），非命中页最高 8.0%
- 剔除 2451 / 143539 字符（1.7%），逐行人工核对 **无一条科研内容**
- 尾随总结检出 1/355

变异测试（见文件末「变异测试」注释）
"""
import os

import pytest

os.environ.setdefault("SKIP_DB_SETUP", "1")


# ============================================================================
# 0. 真实样本（取自 agent35/agent37 实测转写，删节但保留关键结构）
# ============================================================================

#: 1537 p35 —— 拍别人笔记本屏幕。WPS ribbon + 标题栏 + 任务栏 + 别人的课件 + 模型追加总结。
SCREEN_PHOTO_PAGE = """天津大学

WPS Office 共49页8个窗体

第一届未来颗粒前沿论坛 - 主讲.pdf

视觉设计

开始

插入

设计

切换

动画

放映工具

超链接

字体颜色

字符底纹

删除格式

新建幻灯片

表格

图片

形状

屏幕录制

幻灯片编号

对象

选择窗格

页面大小

网格线

保护文档

清华大学_仿模拟OH...

清华大学 Tsinghua University

采用机器学习势模拟 OH· 和 H· 对体相纳米气泡动态行为的影响

章鹏超 陈昌盛 冯牧野 孙  超* 许雪飞*

燃烧能源中心

能源与动力工程系

清华大学

中国·西安 2025年4月19日

文件夹

文件资源管理器

搜索

以上幻灯片内容已按阅读顺序原样输出。

核心文字内容（幻灯片正文）：

- 标题：采用机器学习势模拟 OH· 和 H· 对体相纳米气泡动态行为的影响
- 作者：章鹏超 陈昌盛 冯牧野 孙  超* 许雪飞*
- 单位：燃烧能源中心 / 能源与动力工程系 / 清华大学
- 会议：第二届未来颗粒前沿论坛
- 地点与时间：中国·西安 2025年4月19日
- 页眉 LOGO：天津大学"""

#: 1254 p10 —— MATLAB GUI 截图。真实 slide 标题 + 母版校名必须活着。
MATLAB_GUI_PAGE = """气泡统计

天津大学环境科学与工程学院
SCHOOL OF ENVIRONMENTAL SCIENCE&ENGINEERING,TIANJIN UNIVERSITY

File Window Help

Folder    Calibration    Bubble detection and filtering    Results

Step 1: Pixel resolution calibration

Image name

波纹图片_2024.1

Confirm

or:

Select other image for resolution calibration

Preview

0

px/mm

Confirm

Step 2: Background correction image

<< Back

Confirm, or modify accordingly, the images for resolution calibration

Next >>

Step 1: Select image processing algorithm

● Using default parameters

○ Choosing my own parameters

Confirm parameters

Sample image

Processed image

< Prev img

Next img >

Choose an image processing algorithm from the dropdown menu.

Batch process images

GUI_Bubb..."""

#: 一页普通科研 slide（本组气泡方向）
NORMAL_SCIENCE_PAGE = """臭氧微纳米气泡的传质特性

臭氧在水中的溶解度随温度升高而降低
气泡半径越小比表面积越大，传质速率越快
实验采用 300 W 臭氧发生器，接触时间 60 s

结论：粒径控制是提升传质效率的关键
展望：下一步开展长期稳定性研究"""


# ============================================================================
# 1. 单行分类 —— 三档设计的核心
# ============================================================================


class TestClassifyLine:
    def test_strong_ui_terms_need_no_run(self):
        """STRONG 档：UI 术语单独成行就成立。"""
        from app.services.page_transcript_filter import classify_line

        for line in ("新建幻灯片", "文件资源管理器", "幻灯片编号",
                     "File Window Help", "Confirm parameters"):
            cat, rule = classify_line(line)
            assert cat == "strong", (line, cat, rule)

    def test_weak_terms_are_weak(self):
        """WEAK 档：普通词，需要 run 上下文。"""
        from app.services.page_transcript_filter import classify_line

        for line in ("插入", "设计", "表格", "Confirm", "Preview", "默认"):
            assert classify_line(line)[0] == "weak", line

    def test_normal_science_lines_not_chrome(self):
        from app.services.page_transcript_filter import classify_line

        for line in (
            "实验设计",
            "气泡半径越小比表面积越大，传质速率越快",
            "•界面水分子排列高度有序",
            "·OH：香豆素 (3-CCA)",
        ):
            assert classify_line(line)[0] is None, line

    # ── 回归：agent40 开发期抓到的三类误伤 ──────────────────────────

    def test_bullet_markers_are_never_chrome(self):
        """``•``/``·`` 是中文 slide 的普通项目符号，绝不能当 chrome。

        开发期初版 `_RADIO_RE` 含 ``•·`` 且判 STRONG，实测把
        ``• O₃ nanobubbles maintain good stability…`` 整条正文删了。
        """
        from app.services.page_transcript_filter import classify_line

        for line in (
            "•界面水分子排列高度有序",
            "• O₃ nanobubbles maintain good stability during stirring",
            "·OH在气泡收缩破裂时于气液",
            "·Blank",
            "●pH=5",
        ):
            assert classify_line(line)[0] is None, line

    def test_bare_numbers_are_not_chrome(self):
        """图表刻度（500 / 400 / 0.05…）是真内容，绝不能当 chrome。

        初版 `_MEASURE_RE` 写成 ``^\\d+(\\.\\d+)?$``，实测把 1066p17 /
        1126p10 等页的全部坐标轴刻度删光。
        """
        from app.services.page_transcript_filter import classify_line

        for line in ("500", "0", "0.05", "2018", "1/42", "30%"):
            assert classify_line(line)[0] is None, line

    def test_watermark_only_matches_whole_line(self):
        """``激活 Windows`` 出现在句子中间是正文，不是水印。

        初版用 ``search``，实测把
        ``实验室工作站均已激活 Windows 10 专业版`` 整行删了。
        """
        from app.services.page_transcript_filter import classify_line

        assert classify_line("激活 Windows")[0] == "strong"
        assert classify_line('转到"设置"以激活 Windows。')[0] == "strong"
        assert classify_line("实验室工作站均已激活 Windows 10 专业版")[0] is None
        assert classify_line("正版授权号由信息中心统一管理")[0] is None

    def test_gui_phrases_are_strong(self):
        """多词 GUI 固定搭配是 substring 安全的。"""
        from app.services.page_transcript_filter import classify_line

        assert classify_line("Step 1: Pixel resolution calibration")[0] == "strong"
        assert classify_line(
            "Choose an image processing algorithm from the dropdown menu."
        )[0] == "strong"

    def test_office_filename_in_title_bar(self):
        from app.services.page_transcript_filter import classify_line

        assert classify_line("百度智能云0.19.pptx")[0] == "strong"
        assert classify_line("第一届未来颗粒前沿论坛 - 主讲.pdf")[0] == "strong"
        # 科学正文里的数字不是文件名
        assert classify_line("臭氧浓度为 0.19 ppm")[0] is None


# ============================================================================
# 2. run 规则 —— 「讲 PPT 制作的教学内容」不被误伤的核心
# ============================================================================


class TestRunRule:
    def test_lone_common_word_kept(self):
        """孤立的普通词保留（某页标题就叫《设计》）。"""
        from app.services.page_transcript_filter import filter_page_transcript

        r = filter_page_transcript("设计\n\n三因素正交\n显著性 p<0.05")
        assert r.removed_lines == ()
        assert r.text == "设计\n\n三因素正交\n显著性 p<0.05"

    def test_three_weak_words_with_strong_neighbour_removed(self):
        """含 STRONG 项的 run 到 :data:`MIN_CHROME_RUN` 即整块剔除。"""
        from app.services.page_transcript_filter import filter_page_transcript

        r = filter_page_transcript(
            "气泡统计\n\n新建幻灯片\n表格\n图片\n形状\nSmartArt\n\n结论：传质效率提升 42%"
        )
        assert r.removed_chars > 0
        assert "新建幻灯片" not in r.text
        assert "传质效率提升 42%" in r.text

    def test_all_weak_run_below_threshold_kept(self):
        """纯弱词连排不到 :data:`MIN_ALL_WEAK_RUN` **不删**。

        实测探针：讲 PPT 模板的正文里 ``表格 / 图片 / 公式`` 正好 3 行弱词
        连排，开发期初版（无本规则）把它整段删了。
        """
        from app.services.page_transcript_filter import filter_page_transcript

        r = filter_page_transcript("本组统一模板要求\n\n表格\n\n图片\n\n公式\n\n统一用思源黑体")
        assert r.removed_lines == ()

    def test_long_all_weak_run_removed(self):
        """纯弱词连排够长仍是 chrome（WPS 主题名栏实测 12+ 行连排）。"""
        from app.services.page_transcript_filter import (
            MIN_ALL_WEAK_RUN, filter_page_transcript,
        )

        page = "气泡统计\n\n" + "\n".join(
            ["所有主题", "彩色", "灰度", "全新", "经典", "平面"][:MIN_ALL_WEAK_RUN]
        ) + "\n\n臭氧传质效率提升 42%"
        r = filter_page_transcript(page)
        assert r.chrome_chars > 0
        assert "臭氧传质效率提升 42%" in r.text
        assert "复古" not in r.text

    def test_blank_lines_do_not_break_run(self):
        """模型爱在功能区中间插空行，语义上仍是同一块。"""
        from app.services.page_transcript_filter import filter_page_transcript

        r = filter_page_transcript(
            "标题\n\n新建幻灯片\n\n表格\n\n图片\n\n\n结论：有效"
        )
        assert "表格" not in r.text
        assert "结论：有效" in r.text

    def test_tab_bar_row_detected(self):
        """选项卡栏靠 **2+ 连续空格** 分栏判别。

        ⚠️ 这条判据的入参一旦被空白归一（``\\s+ -> " "``），2+ 空格消失，
        规则**静默失效**、不报任何错、ratio 只是悄悄变低 —— 开发期真踩过。
        本用例就是钉死它的。
        """
        from app.services.page_transcript_filter import classify_line

        line = "Folder    Calibration    Bubble detection and filtering    Results"
        assert classify_line(line) == ("strong", "tab_bar")

    def test_plain_data_table_row_not_tab_bar(self):
        """合取保险：纯数据行拆出来各段都不命中 chrome -> 保留。"""
        from app.services.page_transcript_filter import classify_line

        assert classify_line("0.3    0.5    0.8    0.2") is None or \
            classify_line("0.3    0.5    0.8    0.2")[0] is None
        assert classify_line("工况    压力    温度") == (None, None)


# ============================================================================
# 3. chrome_ratio 与拦截判定
# ============================================================================


class TestBlockDecision:
    def test_screen_photo_page_blocked(self):
        """1537 p35 —— 拍别人屏幕，必须被建议转人工。"""
        from app.services.page_transcript_filter import (
            CHROME_BLOCK_RATIO, filter_page_transcript,
        )

        r = filter_page_transcript(SCREEN_PHOTO_PAGE)
        assert r.blocked is True
        assert r.should_auto_ingest is False
        assert r.chrome_ratio >= CHROME_BLOCK_RATIO
        assert any("chrome_ratio" in x for x in r.block_reasons)

    def test_matlab_gui_page_blocked(self):
        from app.services.page_transcript_filter import (
            CHROME_BLOCK_RATIO, filter_page_transcript,
        )

        r = filter_page_transcript(MATLAB_GUI_PAGE)
        assert r.blocked is True
        assert r.chrome_ratio >= CHROME_BLOCK_RATIO

    def test_matlab_gui_page_chrome_ratio_pinned(self):
        """钉死真实样本的 chrome 占比，防止规则被悄悄削弱。

        实测基线 87%（355 页真实转写里最高的一页）。任何让 tab_bar / 词表
        退化的改动都会把这条压下去 —— tab_bar 静默失效时掉到 68%。
        """
        from app.services.page_transcript_filter import filter_page_transcript

        assert filter_page_transcript(MATLAB_GUI_PAGE).chrome_ratio > 0.80

    def test_screen_photo_page_chrome_ratio_pinned(self):
        """实测基线 33.2%（agent37 在同页独立测得 32.2%，口径一致）。"""
        from app.services.page_transcript_filter import filter_page_transcript

        r = filter_page_transcript(SCREEN_PHOTO_PAGE)
        assert 0.25 < r.chrome_ratio < 0.45

    @pytest.mark.parametrize(
        "text, keep",
        [
            (SCREEN_PHOTO_PAGE, ["章鹏超 陈昌盛 冯牧野", "中国·西安 2025年4月19日"]),
            (MATLAB_GUI_PAGE, ["气泡统计", "SCHOOL OF ENVIRONMENTAL SCIENCE"]),
        ],
    )
    def test_science_content_survives_even_when_blocked(self, text, keep):
        """⚠️ blocked **不等于**删除。被拦的页里真实科研内容必须还在。"""
        from app.services.page_transcript_filter import filter_page_transcript

        r = filter_page_transcript(text)
        assert r.blocked is True
        for k in keep:
            assert k in r.text, k

    def test_normal_science_page_untouched(self):
        from app.services.page_transcript_filter import filter_page_transcript

        r = filter_page_transcript(NORMAL_SCIENCE_PAGE)
        assert r.blocked is False
        assert r.should_auto_ingest is True
        assert r.chrome_ratio == 0.0
        assert r.text == NORMAL_SCIENCE_PAGE

    def test_ratio_boundary(self):
        """阈值是"含"而不是"超"：ratio 恰等于阈值时拦，略低则不拦。

        24 行 chrome(5 字符) + 85 行正文(8 字符) = 120/800 = 15.00% 恰好卡线。
        """
        from app.services.page_transcript_filter import filter_page_transcript

        at = filter_page_transcript(
            "\n".join(["新建幻灯片"] * 24 + ["正文内容甲乙丙丁"] * 85)
        )
        assert at.chrome_ratio == pytest.approx(0.15)
        assert at.blocked is True

        below = filter_page_transcript(
            "\n".join(["新建幻灯片"] * 23 + ["正文内容甲乙丙丁"] * 85)
        )
        assert below.chrome_ratio < 0.15
        assert below.blocked is False

    def test_tiny_page_not_blocked_on_few_chars(self):
        """极短页（<40 字符）不因比例拦 —— 比例在样本太小时没意义。"""
        from app.services.page_transcript_filter import filter_page_transcript

        assert filter_page_transcript("新建幻灯片\n表格").blocked is False

    def test_watermark_alone_sets_flag_without_blocking(self):
        """单页一条水印 + 大量正文：剔水印，但**不拦**。

        一条水印只说明"拍了电脑屏幕"，很可能是主讲人自己那台 —— 不足以
        推断"拍的是别人未发表的研究"。实测 1268p28（970 字符 / 1 条水印）即属此列。
        """
        from app.services.page_transcript_filter import filter_page_transcript

        page = "臭氧传质特性研究\n\n" + "\n".join(
            ["气泡半径越小传质越快"] * 30
        ) + "\n\n激活 Windows"
        r = filter_page_transcript(page)
        assert "激活 Windows" not in r.text
        assert r.watermark_lines == ("激活 Windows",)
        assert r.blocked is False
        assert r.should_auto_ingest is True

    def test_two_watermarks_block(self):
        """同一页 >= 2 条水印 -> 拦（真·桌面截屏会把两条一起框进来）。"""
        from app.services.page_transcript_filter import filter_page_transcript

        page = "臭氧传质特性研究\n\n" + "\n".join(
            ["气泡半径越小传质越快"] * 30
        ) + "\n\n激活 Windows\n转到\"设置\"以激活 Windows。"
        r = filter_page_transcript(page)
        assert r.blocked is True
        assert any("watermark" in x for x in r.block_reasons)
        assert "激活 Windows" not in r.text
        assert "气泡半径越小传质越快" in r.text

    def test_watermark_flooded_page_blocked(self):
        """整页被未激活水印淹没 -> 拦。"""
        from app.services.page_transcript_filter import filter_page_transcript

        page = "\n".join(
            ["臭氧传质特性研究"] * 40 + ["激活 Windows"] * 8
        )
        r = filter_page_transcript(page)
        assert r.blocked is True
        assert any("watermark" in x for x in r.block_reasons)

    def test_watermark_rule_guarded_by_min_page_chars(self):
        """页长 < :data:`WATERMARK_MIN_PAGE_CHARS` 时水印规则不参与判定。

        实测 1268p12 全页仅 125 字符，其中 2 条水印占 16% —— 比例没意义。
        注意 **chrome_ratio 规则是独立的**，该页仍可能因 chrome 占比被拦；
        拦的是"转人工", 不会删内容。
        """
        from app.services.page_transcript_filter import (
            WATERMARK_MIN_PAGE_CHARS, filter_page_transcript,
        )

        r = filter_page_transcript(
            "臭氧发生器\n臭氧浓度 40 mg/h\n激活 Windows\n转到\"设置\"以激活 Windows。"
        )
        assert r.total_chars < WATERMARK_MIN_PAGE_CHARS
        assert not any("watermark" in x for x in r.block_reasons)
        assert "臭氧发生器" in r.text          # 内容一行没少

    def test_single_watermark_on_moderate_page_not_blocked(self):
        from app.services.page_transcript_filter import filter_page_transcript

        page = (
            "臭氧微纳气泡发生器参数标定\n\n"
            "臭氧浓度 40 mg/h\n产气量 2 L/min\n气泡粒径 80 nm\n"
            "接触时间 60 s\n进气压力 0.3 MPa\n出口温度 25 ℃\n\n激活 Windows"
        )
        r = filter_page_transcript(page)
        assert r.watermark_lines == ("激活 Windows",)
        assert r.blocked is False
        assert r.should_auto_ingest is True

    def test_empty_and_bad_input(self):
        from app.services.page_transcript_filter import filter_page_transcript

        assert filter_page_transcript("").text == ""
        assert filter_page_transcript("").blocked is False
        assert filter_page_transcript(None).text == ""        # type: ignore[arg-type]
        with pytest.raises(TypeError):
            filter_page_transcript(123)                      # type: ignore[arg-type]


# ============================================================================
# 4. 尾随总结段切除
# ============================================================================


class TestTrailingSummary:
    def test_hard_marker_cut(self):
        """``核心文字内容（幻灯片正文）：`` 之后的整段被切掉。"""
        from app.services.page_transcript_filter import filter_page_transcript

        r = filter_page_transcript(SCREEN_PHOTO_PAGE)
        assert r.truncation_marker is not None
        assert r.truncated_tail.startswith("以上幻灯片内容已按阅读顺序原样输出。")
        assert "核心文字内容（幻灯片正文）" not in r.text
        assert "章鹏超 陈昌盛 冯牧野" in r.text   # 原文仍在

    def test_schema_tail_without_header(self):
        """无表头变体：尾部 4 条以上 ``- 标题：…`` 摘要 bullet 被切。"""
        from app.services.page_transcript_filter import filter_page_transcript

        page = (
            "臭氧微纳米气泡稳定性\n\n粒径控制在 100 nm 附近\n传质效率提升 42%\n"
            "长期稳定性仍待考察\n\n"
            "- 标题：臭氧微纳米气泡稳定性\n- 作者：张三\n- 单位：天津大学\n"
            "- 会议：全国气泡学术会议\n- 地点与时间：天津 2025"
        )
        r = filter_page_transcript(page)
        assert r.truncation_marker is not None
        assert "粒径控制在 100 nm 附近" in r.text
        assert "- 作者：张三" not in r.text

    @pytest.mark.parametrize(
        "page",
        [
            # 真·总结页（科研 slide 常见）—— 一个字都不能切
            "总结\n综上所述，本研究建立了制备与表征方法\n要点如下\n- 提升 42%",
            # 标题页的作者/单位 bullet 只有 2 条 -> 不触发 schema 规则
            "臭氧微纳气泡研究\n- 作者：张三\n- 单位：天津大学环境学院",
            # 正文里提到「幻灯片正文」但不在行首
            "本模板的幻灯片正文区域建议字号不小于 18 pt",
            # 只有 3 条 schema bullet -> 不足 MIN_SCHEMA_TAIL_RUN
            "研究结论\n粒径稳定\n- 标题：A\n- 作者：B\n- 单位：C",
        ],
    )
    def test_real_conclusion_pages_never_truncated(self, page):
        from app.services.page_transcript_filter import filter_page_transcript

        r = filter_page_transcript(page)
        assert r.truncated_tail == ""
        assert r.truncation_marker is None
        assert r.text == page

    def test_marker_inside_sentence_does_not_truncate(self):
        from app.services.page_transcript_filter import filter_page_transcript

        page = "结论\n如以上幻灯片内容所示，臭氧显著提升了传质效率"
        assert filter_page_transcript(page).truncated_tail == ""

    def test_truncated_tail_is_recoverable(self):
        """切掉的内容必须原样留在返回值里，可审计可回滚。"""
        from app.services.page_transcript_filter import filter_page_transcript

        r = filter_page_transcript(SCREEN_PHOTO_PAGE)
        assert "- 页眉 LOGO：天津大学" in r.truncated_tail


# ============================================================================
# 5. 通用不变量
# ============================================================================


class TestInvariants:
    def test_output_is_subsequence_of_input(self):
        """过滤只会**删行**，不重排、不改写任何保留下来的行。"""
        from app.services.page_transcript_filter import filter_page_transcript

        for page in (SCREEN_PHOTO_PAGE, MATLAB_GUI_PAGE, NORMAL_SCIENCE_PAGE):
            before = [l.strip() for l in page.splitlines() if l.strip()]
            after = [l.strip() for l in filter_page_transcript(page).text.splitlines() if l.strip()]
            it = iter(before)
            assert all(any(a == b for b in it) for a in after)

    def test_idempotent(self):
        from app.services.page_transcript_filter import filter_page_transcript

        for page in (SCREEN_PHOTO_PAGE, MATLAB_GUI_PAGE, NORMAL_SCIENCE_PAGE):
            once = filter_page_transcript(page).text
            assert filter_page_transcript(once).text == once

    def test_never_empties_a_page_with_content(self):
        from app.services.page_transcript_filter import filter_page_transcript

        for page in (SCREEN_PHOTO_PAGE, MATLAB_GUI_PAGE, NORMAL_SCIENCE_PAGE):
            assert filter_page_transcript(page).text.strip()

    def test_removed_chars_accounting(self):
        from app.services.page_transcript_filter import filter_page_transcript

        r = filter_page_transcript(SCREEN_PHOTO_PAGE)
        assert r.chrome_chars == sum(len(rl.text) for rl in r.removed_lines)
        assert r.removed_chars >= r.chrome_chars
        assert r.total_chars > r.chrome_chars

    def test_removed_lines_carry_audit_trail(self):
        from app.services.page_transcript_filter import filter_page_transcript

        r = filter_page_transcript(MATLAB_GUI_PAGE)
        assert r.removed_lines
        for rl in r.removed_lines:
            assert rl.category in ("strong", "weak_in_run")
            assert rl.rule and rl.line_no >= 0

    def test_line_numbers_point_at_original_text(self):
        """RemovedLine.line_no 必须能直接索引回原始文本。"""
        from app.services.page_transcript_filter import filter_page_transcript

        lines = SCREEN_PHOTO_PAGE.splitlines()
        for rl in filter_page_transcript(SCREEN_PHOTO_PAGE).removed_lines:
            assert lines[rl.line_no].strip() == rl.text

    def test_no_external_org_name_rule(self):
        """⚠️ 有意**不实现**「含外部机构名」判据 —— 该组 deck 本身就在
        未来颗粒前沿研讨会语境里，合法引用清华/中科院分区会造成高假阳。"""
        from app.services.page_transcript_filter import filter_page_transcript

        page = (
            "国外研究现状\n清华大学 Zhang 等 2023 报道了类似结论\n"
            "该工作发表于 Nature（中科院一区）\n本组前期已复现其主要结论"
        )
        r = filter_page_transcript(page)
        assert r.blocked is False
        assert r.chrome_ratio == 0.0
        assert r.text == page

    def test_module_is_pure(self):
        """零 IO：模块只依赖标准库，不碰 DB / 网络 / 文件系统。"""
        import ast
        import pathlib

        src = pathlib.Path("app/services/page_transcript_filter.py").read_text(
            encoding="utf-8"
        )
        tree = ast.parse(src)
        imported: set = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        assert not (imported & {
            "os", "sys", "requests", "httpx", "sqlalchemy", "asyncio",
            "openpyxl", "anthropic", "redis", "celery",
        }), imported
        assert imported <= {"re", "dataclasses", "typing", "__future__"}, imported


# ============================================================================
# 变异测试（人工执行，用于验证本测试确实能抓住回归）
# ============================================================================
#
# 六条变体**已逐条实测**，每条都让上面的用例转红（agent40，46 passed 基线）：
#
#   1) `_RADIO_RE` 改回 `^[●○◉◦•·]\s*\S` 且 cat 改回 "strong"
#      → TestClassifyLine.test_bullet_markers_are_never_chrome 转红 **+**
#        TestClassifyLine.test_normal_science_lines_not_chrome 转红（2 red）
#        （实测：1173p2 的三条 O₃ nanobubbles 英文正文被整段删掉）
#
#   2) `_MEASURE_RE` 放宽回 `^\d+(?:\.\d+)?\s*(?:%|px)?$`
#      → TestClassifyLine.test_bare_numbers_are_not_chrome 转红
#        （实测：1066p17 / 1126p10 全部坐标轴刻度被删）
#
#   3) `_WATERMARK_RE.fullmatch` 改回 `.search`
#      → TestClassifyLine.test_watermark_only_matches_whole_line 转红
#        （实测：「实验室工作站均已激活 Windows 10 专业版」被删）
#
#   4) `_scan` 里删掉 `need = ... max(min_run, min_all_weak)`，直接用 `seg_len >= min_run`
#      → TestRunRule.test_all_weak_run_below_threshold_kept 转红
#        （实测：讲 PPT 模板页的「表格/图片/公式」3 行被删）
#
#   5) `_TAIL_META_MARKERS` 加上「总结」「综上所述」「要点如下」
#      → TestTrailingSummary.test_real_conclusion_pages_never_truncated 转红
#        （科研 slide 的真·总结页会被整页切空 —— 最危险的一种误伤）
#
#   6) `_is_tab_bar` 的入参改成空白归一后的串（`_WS_RE.sub(" ", line).strip()`）
#      → **首轮实测存活**（42 passed，无人察觉）—— 规则静默失效、不报错、
#        只是 ratio 悄悄从 87% 掉到 68%。补了
#        TestRunRule.test_tab_bar_row_detected +
#        TestBlockDecision.test_matlab_gui_page_chrome_ratio_pinned 两条钉死后转红
#        （2 red）。**教训：静默失效的规则必须有一条直接钉住其输出的用例，
#        靠"最终 ratio 仍超阈值"的间接断言抓不住。**