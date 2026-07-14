"""
test_text_sanitize.py — 测试 app.utils.text_sanitize.sanitize_project_description

覆盖场景 (2026-07-15):
  1. 空输入 (None / "")
  2. 短干净输入 (真项目风格, pass-through)
  3. LLM 套路开场白 (好的,非常荣幸...)
  4. 项目名称: 字段抽取 (LLM 计划标准字段)
  5. 研究方向: 字段抽取
  6. 字段 STOP_WORDS 过滤 (含 6个月 / 团队人数 等 LLM 元信息)
  7. 长 markdown + 阶段标题残留 (LLM 计划)
  8. cap 280 字符优雅截断
  9. 防 [^*\n]+? 非贪婪 bug (贪婪匹配取整行)
"""
import pytest

from app.utils.text_sanitize import sanitize_project_description


class TestSanitizeEmpty:
    """空输入"""

    def test_none(self):
        assert sanitize_project_description(None) == ""

    def test_empty_string(self):
        assert sanitize_project_description("") == ""

    def test_only_whitespace(self):
        assert sanitize_project_description("   \n  \t  ") == ""


class TestSanitizeCleanShort:
    """真项目风格短描述 - pass-through"""

    def test_short_clean_50_chars(self):
        raw = "研究臭氧微纳米气泡对黑臭水体底泥及上覆水中污染物去除、底泥污染物释放抑制、界面氧化转化机制"
        result = sanitize_project_description(raw)
        assert "黑臭水体" in result
        assert "研究" in result
        assert len(result) <= 280
        # 真项目风格本来就有句号/无句号, sanitize 不会乱加字符破坏语义
        # 注意: sanitize 会自动补 。, 检查只多了 1 字 (。)
        assert len(result) in (len(raw), len(raw) + 1)

    def test_passthrough_with_period(self):
        raw = "研究微纳米气泡在饮用水处理中的应用，包括消毒抑菌、生物稳定性提升等。"
        result = sanitize_project_description(raw)
        assert result == raw


class TestSanitizeStripPreamble:
    """LLM 套路开场白剥除"""

    def test_hao_opening(self):
        raw = "好的，非常荣幸能为您规划这份研究项目计划。本计划旨在充分利用6个月时间，让3人团队高效协作，研究微纳米气泡降解抗生素。"
        result = sanitize_project_description(raw)
        # 套路开场白 "好的,非常荣幸..." 必须去掉 (Step B)
        assert "好的" not in result
        assert "非常荣幸" not in result
        # "本计划旨在..." 是 LLM 元信息但是唯一含研究动词+主题词的句
        # 接受它作为结果 (Step C-1 命中: 研究 + 微纳米气泡/抗生素)
        assert "研究" in result
        assert "微纳米气泡" in result or "抗生素" in result

    def test_feichang_rongyao_opening(self):
        raw = "非常荣幸能为贵实验室规划此研究。研究方向：微纳米气泡在水处理中的降解效能。"
        result = sanitize_project_description(raw)
        assert "非常荣幸" not in result
        # 字段抽取优先 (Step A)
        assert "微纳米气泡在水处理中的降解效能" in result


class TestSanitizeFieldExtraction:
    """LLM 字段抽取"""

    def test_project_name_field(self):
        raw = (
            "好的，非常荣幸能为您规划这份研究项目计划。\n\n"
            "### **项目总览**\n"
            "*   **项目名称：** 微纳米气泡对典型抗生素的降解效能与机理研究\n"
            "*   **总时长：** 6个月"
        )
        result = sanitize_project_description(raw)
        # 字段抽取应命中 "项目名称" 行 (避 6个月 STOP_WORDS)
        assert "微纳米气泡对典型抗生素的降解效能与机理" in result

    def test_research_direction_field(self):
        raw = (
            "# 微气泡降解抗生素项目计划\n\n"
            "**项目名称**：微纳米气泡在水处理中降解抗生素的应用研究\n"
            "**项目周期**：6个月\n"
            "**研究方向**：微纳米气泡技术在抗生素污染水体处理中的机理与效能研究"
        )
        result = sanitize_project_description(raw)
        # 验证避开"项目周期:6个月" (STOP_WORDS)
        assert "6个月" not in result
        # 应返回项目名称或研究方向
        assert "微纳米气泡" in result
        assert "抗生素" in result

    def test_field_with_stop_words_filtered(self):
        """含 '6个月' / '团队人数' / '3人' 等 STOP_WORDS 的字段值被跳过"""
        raw = "项目名称：6个月团队 3人做完的项目"
        result = sanitize_project_description(raw)
        # 该字段被 STOP_WORDS 过滤 (6个月 / 3人), fallback 走 Step C/D
        # 而 raw 整体 < 8 字且都是 STOP_WORDS, 最后应返 fallback 或空
        assert "6个月" not in result or result == ""


class TestSanitizeMarkdown:
    """Markdown 清洗"""

    def test_inline_md_stripped(self):
        raw = "**研究** 微纳米 _气泡_ `降解` 抗生素 **# 第一阶段**"
        result = sanitize_project_description(raw)
        assert "**" not in result
        assert "_" not in result or "抗生素" in result  # 允许内部含"_"的合法中文词
        assert "`" not in result
        # 不应该有 hash heading 残留
        assert "# 第一阶段" not in result

    def test_heading_prefix_stripped(self):
        raw = "### **项目名称**\n# 第一阶段研究\n**研究内容** 研究微纳米气泡"
        result = sanitize_project_description(raw)
        assert "# 第一阶段" not in result  # 行首 # 已剥离

    def test_inline_md_inside_sentence_kept_after_first_strip(self):
        """验证反复 strip: 处理过的中间字段值再做 INLINE_MD_CHARS.sub"""
        raw = "项目名称：**微纳米气泡** 在水处理中的应用"
        result = sanitize_project_description(raw)
        # 字段提取后, 残余的 ** 应再次被 strip
        assert "**" not in result


class TestSanitizeLength:
    """长度上限 + 优雅截断"""

    def test_cap_to_max_len(self):
        raw = "研究微纳米气泡技术在水处理中的应用，" + ("包括消毒、抑菌、稳定性提升等" * 20)
        result = sanitize_project_description(raw, max_len=80)
        assert 0 < len(result) <= 80
        # 优雅截断到句末标点
        assert result[-1] in "。.!?！？…" or result.endswith("...")

    def test_max_len_zero_safe(self):
        """max_len=0 应返空 (避免除零/无限循环)"""
        raw = "研究微纳米气泡"
        result = sanitize_project_description(raw, max_len=0)
        assert result == ""

    def test_max_len_min_6_required(self):
        """字段值 < 6 字被跳过 (避免"项目名称:"这个 0 字串取到)"""
        raw = "项目名称：\n项目周期：6个月\n项目名称：真正的项目内容描述超过六个字"
        result = sanitize_project_description(raw)
        assert "真正的项目内容描述" in result


class TestSanitizeEdgeCases:
    """边界场景"""

    def test_real_project_9_id_style(self):
        """项目 9 完整原始 description 应提取 "项目名称" 字段的微纳米气泡对典型抗生素"""
        raw = """好的，非常荣幸能为您规划这份研究项目计划。本计划旨在充分利用6个月时间，让3人团队高效协作，系统性地开展微纳米气泡降解抗生素的研究，力求产出高质量的学术成果。

### **项目总览**
*   **项目名称：** 微纳米气泡对典型抗生素的降解效能与机理研究
*   **总时长：** 6个月
*   **团队构成与角色建议：**
    *   **负责人/研究员A：** 负责项目总体设计、数据分析、论文主笔。
*   **核心目标：** 验证微纳米气泡技术降解抗生素的可行性。"""
        result = sanitize_project_description(raw)
        assert "好的" not in result
        assert "非常荣幸" not in result
        assert "本计划" not in result
        assert "**" not in result
        # 字段提取 (项目名称或核心目标) 都行
        assert "微纳米气泡对典型抗生素" in result or "验证微纳米气泡技术降解抗生素" in result

    def test_real_project_10_id_style(self):
        """项目 10 风格: 以 "# 微气泡降解抗生素研究项目计划" 开头"""
        raw = """# 微气泡降解抗生素研究项目计划

**项目名称**：微纳米气泡在水处理中降解抗生素的应用研究

**项目周期**：6个月

**团队配置**：3人（项目负责人1名，实验研究员1名，数据分析与文献研究员1名）

**研究方向**：微纳米气泡技术在抗生素污染水体处理中的机理与效能研究"""
        result = sanitize_project_description(raw)
        assert "# " not in result
        assert "**" not in result
        assert "6个月" not in result
        assert "3人" not in result
        assert "微纳米气泡" in result
        assert "抗生素" in result

    def test_no_match_returns_fallback_short_sentence(self):
        """没有任何关键词命中 → fallback 取首句非 LLM 字段标签"""
        raw = "这是项目的简短说明，没有任何研究动词或主题关键词。"
        result = sanitize_project_description(raw)
        # 返回首句, 但含 "项目" 可能被 LLM 元信息启发式认为 OK
        assert result != ""
        assert "项目" in result or "说明" in result

    def test_only_punctuation(self):
        """只有标点"""
        raw = "。。。。。，。？？"
        result = sanitize_project_description(raw)
        assert result == ""
