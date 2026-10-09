"""agent42 补充：防护 D/E/F/G 的测试（2026-10-10）。

⚠️ 本文件**追加**在 agent40 的测试之后，不改动他的任何一条断言。
四组新防护的实测基线全部来自 a41 随机抽检的 269 页真实转写
（容器内 `/tmp/a41/transcripts.json`），下面的 fixture 是**从真实转写里
逐字摘出来的片段**（只删节，不改写、不编造）。

四组防护与实测命中数
--------------------
=====  ==========================================  =====
防护    内容                                      命中页
=====  ==========================================  =====
D       整页第三方论文 / 期刊网页截图（只标不删）      6 / 269
E       非 Office 科学软件 GUI（OVITO 等）           1 / 269
F       目录页 / 致谢页模板样板（只标不删）          13 / 269
G       坐标轴刻度梯（删 790 字符 / 14 页）          14 / 269
=====  ==========================================  =====

最大风险仍是**误伤**。本组用三类断言钉死它：
1. 真实科研页**一个字都不能少**（:class:`TestNoFalsePositive`）；
2. D/F 只标不删（``r.text`` 必须等于原文）；
3. G 的每一条删除都必须落在**单调纯数字**上（逐行断言）。
"""

import os

import pytest

os.environ.setdefault("SKIP_DB_SETUP", "1")


# ============================================================================
# 6. 真实样本 fixture（逐字摘自 a41 269 页样本）
# ============================================================================

#: 1208 p4 —— Nature Communications **网页截图**整页。
#: 主指挥点名要求必须识别。特征：Springer 导航条 + nature 面包屑 +
#: Open access / Altmetric 角标 + 一整段英文 Abstract。
NATURE_WEB_PAGE = """以下是该幻灯片上按阅读顺序提取的所有文字：

---

**天津大学**
Tianjin University

nature communications

Explore content    About the journal    Publish with us

nature > nature communications > articles > article

Article    Open access    Published: 03 October 2025

**Probing catalyst-free hydroxyl radical generation at microbubble interfaces**

Si-Yu Yang, Wei Wang, Jie-Jie Chen, Joseph S. Francisco & Xian-Wei Liu

*Nature Communications* 16, Article number: 8835 (2025)    |    Cite this article

2918 Accesses    |    7 Altmetric    |    Metrics

**Abstract**

Gas-liquid interfaces at the micro- and nanoscale are emerging hotspots for unique chemical reactivity, yet the reactivity of individual microbubbles remains largely unexplored. Here, we visualize the catalyst-free generation of reactive oxygen species, particularly hydroxyl radicals, at the gas-liquid interface of microbubbles. In-situ chemiluminescence imaging, together with spectroscopic analyses, and multiscale computational simulations shows that the enrichment of hydroxide ions at the microbubble surface, coupled with the interfacial electric field, drives the catalyst-free generation of hydroxyl radicals.

2025年，中国科学技术大学

**Nature Communications：JCR Q1 15.7**"""

#: 1101 p2 —— Science 系期刊 The Innovation 的 NEWS 栏整页截图（native=0）。
SCIENCE_NEWS_PAGE = """NEWS & BUZZ

**Breakthrough in enclosed aquatic ecosystems in space: Supporting zebrafish survival for 43 days**

Maobin Xie,1,2,4,5,6 Qing Tian,1,6 Gaohong Wang,3 Weibo Zheng,1,5,* and Shaowei Wang2,4,*
1Shanghai Institute of Technical Physics, Chinese Academy of Sciences, Shanghai 200083, China
2State Key Laboratory of Precision Spectroscopy, East China Normal University, Shanghai 200241, China
6These authors contributed equally
*Correspondence: weibo_zheng@sina.com (W.Z.); swwang@lps.ecnu.edu.cn (S.W.)
Received: August 14, 2024; Accepted: October 4, 2024; Published Online: October 5, 2024; https://doi.org/10.1016/j.xinn.2024.100711
Citation: Xie M, Tian Q, Wang G., et al., (2024). Breakthrough in enclosed aquatic ecosystems in space: Supporting zebrafish survival for 43 days. The Innovation 5(6), 100711.

　　In June 2024, the China space station's closed aquatic ecosystem (CSS's CAES) achieved a remarkable feat: zebrafish completed their life stages, from growth to development and reproduction, in 43 days, setting a new record for space ecological experiments. This milestone not only means progress in China's space ecosystem technology but also provides valuable data and technical support for closed-loop ecosystems in space missions.

The Innovation"""

#: 1072 p2 —— Elsevier / ScienceDirect 论文首页（PDF 转图）。
ELSEVIER_PDF_PAGE = """Water Research 275 (2025) 123216

Contents lists available at ScienceDirect

**Water Research**

journal homepage: www.elsevier.com/locate/watres

ELSEVIER

Ceramic membrane fouling caused by recycling biological activated carbon filter backwash water: Effective backwash with ozone micro-nano bubbles

Wei Liu a,b, Tao Lin a,b,*, Xiaoshu Yan a,b

a Ministry of Education Key Laboratory of Integrated Regulation and Resource Development on Shallow Lakes, Hohai University, Nanjing 210098, PR China

ARTICLE INFO

Keywords:
Water treatment

ABSTRACT

The widespread use of ceramic membranes in wastewater recycling is still hampered by membrane fouling problems. Frequent chemical cleaning increases operating and maintenance costs. This work proposes ozone micro-nano bubble (O3-MNB) backwash as a new backwashing method to control the ceramic membrane fouling. Activated carbon filter backwash water (ACFBW) was used as feed water for the ceramic membrane and the effect of O3-MNB backwash was compared with tap water backwash."""

#: 1059 p6 —— OVITO Basic 窗口截图（分子可视化软件 GUI）。
#: ⚠️ 注意 brief 里写的页号是 p2，但 ``Directory: C:/Users/TJU/Desktop``
#: 与 ``Layer (3).cif`` 实际在 **p6**；p2 是 DeepSeek 对话页（真内容）。
OVITO_GUI_PAGE = """OVITO Basic (Open Visualization Tool) *
File Edit Help
Quick command search (Ctrl+P)
Pipelines:
Layer (3).cif [CIF]

Top
Front

Particles
Simulation cell

Visual elements
Add modification...

Layer (3).cif [CIF]
Particle types
Simulation cell

拖拽至此上传
External file
Data source
Current file:        Layer (3).cif
Directory:           C:/Users/TJU/Desktop
File sequence
Search pattern:     Layer (3).cif
auto-generate   Found 1 matching file
Current frame:
Playback ratio:        1 / 1         Change...

Left

Perspective

Status
Number of atoms: 561

CIF reader
Options
Center simulation box on coordinate origin

Particles   Global Attributes

OVITO Basic (Open Visualization Tool) *"""

#: 886 p3 —— 目录页。
#: ⚠️ 这里放的是**视觉转写原文**（过滤器实际收到的输入），不是 pptx 原生文本。
#: 根因说明：原生文本是 ``/CONTENTS\n目录\n1\n2\n3\n研究背景…``，
#: 转写把数字和标题合成了一行（``1 研究背景``），4-gram dedup 对不上，
#: 于是整页被当成"新增内容"计进 A。
TOC_PAGE = """目录

1 研究背景
2 材料与方法
3 结果与讨论
4 结论"""

#: 1198 p3 —— 目录页的另一形态：页头是母版占位符 ``/CONTENTS``，
#: 且夹着 ``天津大学`` / ``Tianjin University`` 两行校名（故 ``other == 2``）。
TOC_PAGE_2 = """天津大学
Tianjin University

目录
/CONTENTS

1 研究背景

2 研究方法

3 研究结果"""

#: 1161 p19 —— 臭氧产率 vs 放电电压，四联图（a)-(d)，**全是坐标轴刻度**。
#: 真实研究页：标题和结论必须活着，刻度梯必须被剔。
CHART_YIELD_PAGE = """产率与放电电压的关系

(a) 400 Hz 臭氧产率与流量的关系

30
28
26
24
22
20
18
16
14
12

V (kV)

4L/min
6L/min
8L/min
10L/min

(b) 600 Hz 臭氧产率与流量的关系

36
34
32
30
28
26
24
22
20
18

2.0
2.5
3.0
3.5
4.0

产率 (g/kWh)

不同频率和不同流量下臭氧产率随放电电压的变化趋势基本相同，都是先增大后缓慢减小。存在最佳放电电压和最佳流量使臭氧产率最大。"""

#: 1193 p19 —— ¹O₂ 降解 BPA 的四条热力学路径图。
#: ⚠️ **本组最危险的一页**：里面的 ``-237.06`` / ``-159.56`` 是**真实能垒**，
#: ``BPA`` / ``TSa1`` / ``Pathway 1`` 是**真实的路径节点名**。
#: agent42 首版「连续短标签行 → 全删」把它们全删光了（真误伤）。
#: 单调刻度梯版必须**一个字符都不动**。
THERMO_PATHWAY_PAGE = """天津大学
Tianjin University

¹O₂ 作用于双酚 A(BPA) 的降解途径

有 4 条可能路径（P1-P4），大多数步骤在热力学上是有利的（ΔG<0），且起始步的能垒不高，说明这些路径都可能发生。

难点：过渡态计算（TS 优化 + 频率分析确认唯一虚频）

(a)
[Benzene]
CO₂
H₂O
BPA

(b)
BPA
TSa1
TSB1
0.0
20.33
B1
-8.37
B5
16.87
B7
-16.87
-24.97
B3
-99.09
B6
-159.56
-184.85
-237.06
-254.41
-271.90
B10
-311.39
B8
-367.68
B2
-423.29
Pathway 1
Pathway 2
Pathway 3
Pathway 4"""

#: 1215 p9 —— 冷冻水室温沉积 AFM 图，**真实时间点** 143 min / 179 min。
#: 与 THERMO_PATHWAY_PAGE 同为「非单调短标签」的误伤探针。
AFM_TIMELINE_PAGE = """天津大学
Tianjin University

流体层、有序域和表面纳米气泡（冷冻水室温沉积）

(a)
(a) 4
(d)
143 min
(b)

96 min
147 min
98 min
179 min
(e)
(b)
(c)
(e)
(f)
147 min

Height (nm)
179min
151min
156min
147min

Width (μm)

表面纳米气泡：薄层逐渐后退，露出其流动性，而突起在横向和垂直维度上都有所增长。"""


# ============================================================================
# 7. 防护 D —— 整页第三方论文（只标不删）
# ============================================================================


class TestThirdPartyPaper:
    def test_nature_web_screenshot_blocked(self):
        """1208p4 —— Nature Communications 网页截图整页。"""
        from app.services.page_transcript_filter import filter_page_transcript

        r = filter_page_transcript(NATURE_WEB_PAGE)
        assert r.third_party_paper is True
        assert r.blocked is True
        assert r.should_auto_ingest is False
        assert any("third_party_paper_page" in x for x in r.block_reasons)

    def test_science_news_page_blocked(self):
        """1101p2 —— Science 系期刊 NEWS 栏整页（native=0）。"""
        from app.services.page_transcript_filter import filter_page_transcript

        r = filter_page_transcript(SCIENCE_NEWS_PAGE)
        assert r.third_party_paper is True
        assert "masthead" in r.paper_families
        assert "editorial" in r.paper_families

    def test_elsevier_pdf_page_blocked(self):
        """1072p2 —— Elsevier / ScienceDirect 论文首页。"""
        from app.services.page_transcript_filter import filter_page_transcript

        r = filter_page_transcript(ELSEVIER_PDF_PAGE)
        assert r.third_party_paper is True
        assert "nav" in r.paper_families

    def test_content_is_never_deleted(self):
        """⚠️ **本防护只标不删** —— 无法从纯文本区分「论文正文」与
        「用户摘抄的论文段落」，删了就可能删掉真引用。"""
        from app.services.page_transcript_filter import filter_page_transcript

        for page in (NATURE_WEB_PAGE, SCIENCE_NEWS_PAGE, ELSEVIER_PDF_PAGE):
            r = filter_page_transcript(page)
            assert r.third_party_paper is True
            assert r.text == page.strip(), "论文页必须一字不删"
            assert r.removed_chars == 0, "论文页不应有任何删字符计入"

    def test_masthead_alone_is_not_enough(self):
        """⚠️ 单个期刊名**不足以**判污染 —— 合组会 PPT 合法引用 Nature。"""
        from app.services.page_transcript_filter import detect_third_party_paper

        page = "本组参考了 Nature Communications 上的相关工作\n我们据此改进了实验装置"
        hit, fams, _ = detect_third_party_paper(page)
        assert hit is False
        assert fams == ()

    def test_legitimate_citation_page_never_blocked(self):
        """1101p5 / 1250p2 —— 本组合法引用页，**不得**被拦。

        1101p5 有 3 个族（Elsevier 刊头 + ``Get rights and content`` + DOI），
        仅靠族数会误伤；1250p2 有一行 ``Cite This: Acc. Chem. Res. 2019, 52,
        1196−1205``。二者都靠「外文正文规模 + 长行」两道保险被放行。
        """
        from app.services.page_transcript_filter import detect_third_party_paper

        cite_1101 = (
            "背景\n\n2024年6月，中国空间站的密闭水生生态系统（CAES）取得了显著的成就，"
            "斑马鱼在43天内完成了生命阶段。\n\n"
            "Advances in Space Research\nVolume 30, Issue 4, 2002, Pages 843-847\nELSEVIER\n\n"
            "Microgravity influences synapse formation in a vestibular nucleus of fish brain\n\n"
            "R.H. Anken, M. Ibsch, H. Rahmann\n\nShow more\n+ Add to Mendeley  Share  Cite\n\n"
            "https://doi.org/10.1016/S0273-1177(01)00643-3\n\nGet rights and content\n\n"
            "神舟八号微型生态系统（2011年）"
        )
        assert detect_third_party_paper(cite_1101)[0] is False

        cite_1250 = (
            "Article\nACCOUNTS of chemical research\n"
            "Cite This: Acc. Chem. Res. 2019, 52, 1196-1205\npubs.acs.org/accounts\n\n"
            "Nanobubble Technologies Offer Opportunities To Improve Water Treatment\n\n"
            "Published as part of the Accounts of Chemical Research special issue.\n\n"
            "Ariel J. Atkinson, Onur G. Apul, Orren Schneider, Sergi Garcia-Segura, "
            "and Paul Westerhoff\n\n纳米气泡技术为改善水处理提供了机会"
        )
        assert detect_third_party_paper(cite_1250)[0] is False

    def test_long_english_prose_without_publisher_furniture_not_blocked(self):
        """英文长文但**没有出版社版面信号** -> 不是论文截图。

        本组做「英文 poster / 英文摘要讲稿」时会出现这种页。
        """
        from app.services.page_transcript_filter import detect_third_party_paper

        page = (
            "Our group focuses on micro-nano bubble enhanced ozonation for advanced "
            "wastewater treatment, and this slide summarises the three main mechanisms "
            "that we have quantified over the past two years of experimental work in "
            "the laboratory, including mass transfer intensification, radical yield "
            "enhancement, and the resulting degradation kinetics of micropollutants."
        )
        assert detect_third_party_paper(page)[0] is False

    def test_foreign_line_length_gate(self):
        """只有导航碎片、没有 >=150 字符长行 -> 不拦（单行引用 vs 整段正文）。"""
        from app.services.page_transcript_filter import (
            PAPER_FOREIGN_MIN_LINE,
            foreign_prose_stats,
        )

        chars, long_lines = foreign_prose_stats(NATURE_WEB_PAGE)
        assert chars >= 250
        assert long_lines >= 1, "Nature 页应有一段 >=150 字符的外文正文"

        # 同一页去掉长行后, 外文规模掉到阈值下 -> 不再命中
        stripped = "\n".join(
            ln for ln in NATURE_WEB_PAGE.splitlines() if len(ln) < PAPER_FOREIGN_MIN_LINE
        )
        assert _foreign_gate(stripped) is False

    def test_paper_families_are_orthogonal(self):
        """族判定：同一页最多给每个族记一次。"""
        from app.services.page_transcript_filter import paper_families

        fams = paper_families(ELSEVIER_PDF_PAGE)
        assert len(fams) == len(set(fams))
        assert {"nav", "masthead", "bodyhdr"} <= set(fams)

    def test_foreign_min_line_gate_is_pinned(self):
        """⚠️ 回归钉子：外文正文行的**长度门槛 40** 有独立判别力。

        英文 Abstract 讲稿页往往有 ``Abstract`` 页头（bodyhdr 族）+ 一段
        正文，但没有 masthead/nav。判据必须靠「族数 < 2」而非「外文规模」
        把它放行 —— 所以本测试用**两族 + 大量短行**的组合：
        若 :data:`PAPER_FOREIGN_MIN_LINE` 被下调到 5，
        这些短导航行会被算进外文规模，从而误伤。
        """
        from app.services.page_transcript_filter import (
            PAPER_FOREIGN_MIN_LINE,
            detect_third_party_paper,
            foreign_prose_stats,
        )

        assert PAPER_FOREIGN_MIN_LINE == 40
        # 两族齐备（masthead + bodyhdr），但整页**没有一段长正文**
        page = (
            "Abstract\n\nwater research\n\n"
            "Keywords:\n\nWater treatment\n\nCeramic membrane\n\n"
            "ABSTRACT\n\nARTICLE INFO\n\nKeywords:\n\nOzone\n\n"
            "Micro-nano bubbles\n\n"
            + "\n".join(f"line {i}" for i in range(40))     # 大量 <40 字符的碎片
        )
        chars, long_lines = foreign_prose_stats(page)
        assert long_lines == 0, "本探针刻意不含 >=150 字符的长行"
        assert chars < 250, "按 40 字符门槛, 碎片行不该计入外文正文"
        assert detect_third_party_paper(page)[0] is False

    def test_foreign_size_gate_is_pinned(self):
        """⚠️ 回归钉子：外文规模阈值 250 有独立判别力。

        构造「两族 + 一段 160 字符正文 + 一堆导航碎片」的页：
        规模落到 ~200（低于 250）-> 必须放行；
        若阈值被下调到 50，碎片行会把规模顶过阈值从而误伤。
        """
        from app.services.page_transcript_filter import (
            PAPER_MIN_FOREIGN_CHARS,
            detect_third_party_paper,
            foreign_prose_stats,
        )

        body = (
            "Gas-liquid interfaces at the micro- and nanoscale are emerging hotspots "
            "for unique chemical reactivity, yet the reactivity of individual "
            "microbubbles remains largely unexplored in most reactor designs."
        )
        page = (
            "water research\n\nARTICLE INFO\n\n"
            f"{body}\n\n"
            + "\n".join(["Keyword fragment %d" % i for i in range(20)])
        )
        chars, long_lines = foreign_prose_stats(page)
        assert long_lines == 1
        assert chars < PAPER_MIN_FOREIGN_CHARS, (
            f"探针外文规模 {chars} 应低于阈值 {PAPER_MIN_FOREIGN_CHARS}"
        )
        assert detect_third_party_paper(page)[0] is False


def _foreign_gate(text):
    """测试辅助：只看防护 D 的**规模**条件（族条件由别处单独断言）。"""
    from app.services.page_transcript_filter import (
        PAPER_MIN_FOREIGN_CHARS,
        foreign_prose_stats,
    )

    chars, long_lines = foreign_prose_stats(text)
    return chars >= PAPER_MIN_FOREIGN_CHARS and long_lines >= 1


# ============================================================================
# 8. 防护 E —— 非 Office 科学软件 GUI
# ============================================================================


class TestScientificGui:
    def test_ovito_page_crosses_block_threshold(self):
        """1059p6 —— OVITO 窗口。agent40 的词表下 chrome 只有 2.3%,
        补科学 GUI 词表后必须顶过 15% 阈值。"""
        from app.services.page_transcript_filter import filter_page_transcript

        r = filter_page_transcript(OVITO_GUI_PAGE)
        assert r.chrome_ratio >= 0.15, f"实测 {r.chrome_ratio:.1%} —— 应超过 15%"
        assert r.blocked is True

    def test_ovito_titlebar_and_controls_removed(self):
        from app.services.page_transcript_filter import filter_page_transcript

        r = filter_page_transcript(OVITO_GUI_PAGE)
        removed = {rl.text for rl in r.removed_lines}
        assert "Visual elements" in removed
        assert "Particle types" in removed
        assert "Simulation cell" in removed
        assert "拖拽至此上传" in removed
        # ⚠️ RemovedLine.text 是**空白归一后**的串（与模块其余部分一致）
        assert "Directory: C:/Users/TJU/Desktop" in removed
        assert "C:/Users/TJU/Desktop" not in r.text

    def test_userdir_path_is_strong(self):
        """``C:/Users/...`` 是本机用户目录，正文绝不会出现 -> 独立成行也成立。"""
        from app.services.page_transcript_filter import classify_line

        # 带引导词也行（用 search 而非 match），本机用户目录路径本身是判据
        assert classify_line("Read from C:/Users/TJU/Desktop/data.lmp") == (
            "strong", "sci_gui_userdir",
        )
        assert classify_line(r"Load from C:\Users\TJU\Desktop\layer.cif") == (
            "strong", "sci_gui_userdir",
        )
        # OVITO 原句：userdir 判定先跑，所以 rule 记的是 sci_gui_userdir
        assert classify_line("Directory:           C:/Users/TJU/Desktop")[0] == "strong"

    def test_relative_path_in_prose_is_not_chrome(self):
        """⚠️ 正文引用数据文件的**相对路径**不能被当成 GUI 路径。"""
        from app.services.page_transcript_filter import classify_line

        assert classify_line("力场参数取自 clayff.data 文件") == (None, None)
        assert classify_line("数据文件为 data.lmp") == (None, None)
        assert classify_line(r"结构文件见 runs\lammps\data.lmp") == (None, None)
        assert classify_line("Simulation cell") == ("strong", "sci_gui_en")

    def test_gui_field_labels_are_strong(self):
        """GUI 的 ``标签: 值`` 字段行独立成行也成立（对齐取值的形状）。"""
        from app.services.page_transcript_filter import classify_line

        assert classify_line("Number of atoms: 561") == ("strong", "sci_gui_field")
        assert classify_line("Playback ratio:        1 / 1") == (
            "strong", "sci_gui_field",
        )
        # ⚠️ 正文写句子不用这种对齐形状
        assert classify_line("体系内的原子数量随温度升高而增加") == (None, None)
        assert classify_line("Current frame 切换到下一帧") == (None, None)

    def test_science_gui_terms_not_weaken_real_prose(self):
        """⚠️ 「simulation cell」「particle types」在**成串出现**时才算，
        单独出现在正文里必须保留。"""
        from app.services.page_transcript_filter import classify_line

        # 面板标题 -> STRONG（独立成行也成立，因为它是软件的固定控件名）
        assert classify_line("Simulation cell")[0] == "strong"
        # 但中文讲稿里的同义表述不受影响
        assert classify_line("我们构建了 2×2×2 的模拟盒子")[0] is None

    def test_sci_gui_wordlist_covering_is_pinned(self):
        """⚠️ 回归钉子：OVITO 页的**每一个**面板名都被词表覆盖。

        agent40 的教训（变异测试 #6）：靠"最终 ratio 仍超阈值"的**间接**
        断言抓不住词表被掏空 —— 少了几个词，剩下几个仍能把 ratio 顶过阈值，
        测试照样绿。所以这里**逐个词**钉死覆盖率。
        """
        from app.services.page_transcript_filter import (
            SCI_GUI_STRONG_EN,
            classify_line,
        )

        # 1059p6 实测 OVITO 面板名（去掉大小写后逐个断言）
        for term in (
            "simulation cell", "visual elements", "particle types",
            "cif reader", "global attributes", "number of atoms",
            "current file", "directory", "search pattern", "file sequence",
            "playback ratio", "current frame", "external file", "data source",
            "auto-generate", "change...", "add modification...",
        ):
            assert term in SCI_GUI_STRONG_EN, f"词表丢了 {term!r}"
            assert classify_line(term)[0] == "strong", f"{term!r} 未被识别为 chrome"

    def test_real_md_prose_page_not_touched(self):
        from app.services.page_transcript_filter import filter_page_transcript

        md_page = """Deepseek 应用
天津大学环境科学与工程学院

3.2. 分子动力学模拟

基于多粒子系统的经典力学的全原子 MD 模拟用于估计 PFOA 阴离子在改性黏土上的吸附行为。首先创建 C24 膨润土超胞，然后使用 Materials Studio 6.0 导入 1 或 4 个 PFOA 阴离子。通过 298 K 的规范 NVT 系统平衡 800 ps，时间步长为 1fs。

# LAMMPS input script for PFOA adsorption on modified clay
units       real
boundary    p p p
atom_style  full
pair_style    hybrid/overlay lj/cut/coul/long 12.0
fix           nvt all nvt temp 298.0 298.0 100.0 tchain 1"""
        r = filter_page_transcript(md_page)
        assert r.text == md_page.strip(), "MD 讲稿必须一字不删"
        assert r.blocked is False


# ============================================================================
# 9. 防护 F —— 目录页 / 致谢页（只标不删）
# ============================================================================


class TestTemplatePage:
    def test_toc_page_flagged(self):
        from app.services.page_transcript_filter import (
            detect_template_page,
            filter_page_transcript,
        )

        assert detect_template_page(TOC_PAGE) == (True, "toc")
        assert detect_template_page(TOC_PAGE_2) == (True, "toc")
        r = filter_page_transcript(TOC_PAGE)
        assert r.template_page is True
        assert r.blocked is True

    def test_toc_page_content_not_deleted(self):
        """⚠️ 只标不删 —— 删不删是调用方的入库策略，不是净化问题。"""
        from app.services.page_transcript_filter import filter_page_transcript

        r = filter_page_transcript(TOC_PAGE)
        assert r.text == TOC_PAGE.strip()

    def test_page_named_toc_with_real_content_not_flagged(self):
        """⚠️ **误伤探针**：一篇真研究页恰好以「目录」开头但有真实正文。

        实测本组语料里「目录页上顺手写了结论」的最长观测行是 91 字符；
        真模板页最长单行只有 20 字符。阈值 60 卡在两者之间。
        """
        from app.services.page_transcript_filter import (
            TEMPLATE_MAX_LINE_CHARS,
            detect_template_page,
        )

        page = (
            "目录\n\n1 研究背景\n2 材料与方法\n\n"
            "本工作的核心创新在于把微纳米气泡引入曝气单元，并通过 CFD 模拟验证了"
            "气液两相的传质增强效果。实验在天津大学环境学院完成，连续运行 30 天。"
            "结果表明臭氧传质系数提升了 42%，目标污染物去除率从 61% 提升到 89%。"
        )
        longest = max(len(ln.strip()) for ln in page.splitlines() if ln.strip())
        assert longest > TEMPLATE_MAX_LINE_CHARS, "探针本身必须长过阈值才有意义"
        assert detect_template_page(page) == (False, "")

    @pytest.mark.parametrize(
        "page,kind",
        [
            ("谢谢！\n\n产品区\n\n废液专区", "thanks"),
            ("谢谢\n\n感谢聆听\n\n汇报人：张三", "thanks"),
            ("Thank you\n\nQ & A", "thanks"),
        ],
    )
    def test_thanks_pages(self, page, kind):
        from app.services.page_transcript_filter import detect_template_page

        assert detect_template_page(page) == (True, kind)

    def test_thanks_page_with_real_content_not_flagged(self):
        """⚠️ 误伤探针：致谢页后面还写了长段正文 -> 不是纯尾页。"""
        from app.services.page_transcript_filter import detect_template_page

        page = (
            "谢谢！\n\n"
            + "本组感谢国家自然科学基金面上项目（编号 22378042）对臭氧微纳米气泡"
            "界面传质机理的资助，感谢天津市生态环境监测中心在为期六周的现场"
            "采样中的大力支持，感谢课题组同学在长期稳定性实验中夜以继日的付出。"
        )
        assert detect_template_page(page)[0] is False

    def test_real_template_page_bounds_are_pinned(self):
        """回归钉子：实测真模板页的极值仍被识别。

        a41 样本里最长的真模板页是 1220p2（68 字符）、最长单行是
        1220p12（20 字符）。这两条把「阈值别被调过头」钉死。
        """
        from app.services.page_transcript_filter import (
            TEMPLATE_MAX_LINE_CHARS,
            TEMPLATE_MAX_PAGE_CHARS,
            detect_template_page,
        )

        page_1220_2 = (
            "目录\n\n◆一、微纳米气泡定义及其发生方法\n\n◆二、微纳米气泡中·OH的产生"
            "\n\n◆三、微纳米气泡中·OH的表征方法\n\n◆四、影响微纳米气泡中·OH形成的因素"
        )
        page_1220_12 = (
            "目录\n\n◆一、微纳米气泡及其发生方法\n\n◆二、微纳米气泡中·OH 的产生"
            "\n\n◆三、微纳米气泡中·OH 的表征方法\n\n◆四、影响微纳米气泡中·OH 形成的因素\n\n9"
        )
        longest = max(
            len(ln.strip()) for p in (page_1220_2, page_1220_12)
            for ln in p.splitlines() if ln.strip()
        )
        total = max(
            sum(len(ln.strip()) for ln in p.splitlines() if ln.strip())
            for p in (page_1220_2, page_1220_12)
        )
        assert total < TEMPLATE_MAX_PAGE_CHARS
        assert longest < TEMPLATE_MAX_LINE_CHARS
        assert detect_template_page(page_1220_2)[0] is True
        assert detect_template_page(page_1220_12)[0] is True

    def test_section_divider_page_flagged(self):
        """1145p3 —— 章节分隔页（``01 研究背景``），内容极少。"""
        from app.services.page_transcript_filter import detect_template_page

        page = "天津大学\nTianjin University\n01 研究背景"
        # 不是目录页也不是致谢页 -> 不命中（本防护不覆盖章节分隔页，
        # 它们 native_chars 本来就极低，A 贡献可忽略）
        assert detect_template_page(page)[0] is False


# ============================================================================
# 10. 防护 G —— 坐标轴刻度梯（删行）
# ============================================================================


class TestChartLadder:
    def test_monotone_axis_removed(self):
        """1161p19 —— 四联图全是刻度。"""
        from app.services.page_transcript_filter import filter_page_transcript

        r = filter_page_transcript(CHART_YIELD_PAGE)
        assert r.chart_ladder_chars > 0
        # 标题与结论必须活着
        assert "产率与放电电压的关系" in r.text
        assert "都是先增大后缓慢减小" in r.text

    def test_every_removed_line_is_a_number(self):
        """逐行断言：被删的**全部**是纯数字（刻度），无一例外。"""
        from app.services.page_transcript_filter import filter_page_transcript

        r = filter_page_transcript(CHART_YIELD_PAGE)
        ladder = [rl for rl in r.removed_lines if rl.category == "chart_ladder"]
        assert ladder, "本应命中刻度梯"
        for rl in ladder:
            float(rl.text)          # 解析失败即证明不是纯数字
            assert rl.rule == "monotone_numeric_run"

    def test_real_thermo_values_never_removed(self):
        """⚠️⚠️ **本组最重要的误伤断言**。

        1193p19 的 ``-237.06`` / ``-159.56`` 是**真实相对能垒**，
        ``BPA`` / ``TSa1`` / ``Pathway 1`` 是**真实路径节点名**。
        agent42 首版把它们全删了。单调判据必须一个字符都不动。
        """
        from app.services.page_transcript_filter import filter_page_transcript

        r = filter_page_transcript(THERMO_PATHWAY_PAGE)
        assert r.chart_ladder_chars == 0
        assert r.text == THERMO_PATHWAY_PAGE.strip()
        for keep in ("-237.06", "-159.56", "-423.29", "TSa1", "TSB1", "Pathway 1"):
            assert keep in r.text, f"{keep} 是真实科研内容，被误删了"

    def test_non_monotone_energy_series_of_full_run_length_kept(self):
        """⚠️⚠️ **单调性判据的直接钉子** —— 长度必须够 min_run 才算数。

        agent42 首版（无单调性）的真实误伤是 ``1193p19`` 的能垒序列，
        但那个 fixture 里掺了 ``TSa1``/``BPA`` 等非数字行，
        把数字 run 切短了，单调性失效也删不到它 ——
        **fixture 掩盖了判据的失效**。
        本测试给出**长度足够、但非单调**的 8 连真实数据，且整页垫足正文
        使删除比例低于 :data:`CHART_LADDER_MAX_PAGE_RATIO`
        （否则会被页比例闸先拦下，测不到单调性）：
        单调判据在，才安全；单调判据被删掉（M1），立刻转红。
        """
        from app.services.page_transcript_filter import (
            CHART_LADDER_MAX_PAGE_RATIO,
            CHART_LADDER_MIN_RUN,
            filter_page_transcript,
        )

        # 8 个真实实验测量值：非单调、无序 —— 绝不是坐标轴刻度
        readings = ["0.0", "20.33", "-8.37", "16.87", "-16.87", "-99.09", "43.2", "-237.06"]
        assert len(readings) >= CHART_LADDER_MIN_RUN
        # 垫足正文, 确保「若删则超页比例闸」—— 即让单调性成为唯一拦阻
        filler = (
            "本工作系统考察了四条降解路径的相对能垒分布，发现所有路径在热力学上"
            "均可自发进行，且起始步的活化能垒均低于 25 kJ/mol，因此这些路径在实验"
            "条件下都有可能实际发生。过渡态计算进一步确认了各路径中唯一的虚频。"
        )
        page = "各路径相对能垒 (kJ/mol)\n\n" + filler + "\n\n" \
            + "\n".join(readings) + "\n\n" + filler + "\n\n" + filler
        assert r_ratio_ok(readings, page)
        r = filter_page_transcript(page)
        assert r.chart_ladder_chars == 0, "非单调的 8 连真实数据被当成刻度删了"
        for v in readings:
            assert v in r.text

    def test_partially_monotone_series_is_kept(self):
        """⚠️ 误伤断言：只要**不严格单调**就不删（哪怕大部分递减）。

        真实验数据序列常常是「先降后升」（有极小值），这与坐标轴刻度
        无法从形状上区分 —— 单调判据要求**严格**单调正是为了不误伤它们。
        """
        from app.services.page_transcript_filter import find_chart_ladders

        filler = "本实验考察了不同放电电压下的臭氧产率变化趋势，发现最佳工作点。\n\n"
        series = ["-5.2", "-12.8", "-18.1", "-16.4", "-9.7", "-3.3", "1.2", "4.6", "7.9"]
        page = "能垒\n\n" + filler + "\n\n".join(series) + "\n\n" + filler
        assert find_chart_ladders(page) == []


def m_num(s):
    """测试辅助：确认一串文本是纯数字行（模块内部 ``_chart_num`` 的公开替身）。"""
    import re

    return float(s) if re.match(r"^[+\-−–]?\d{1,7}(?:\.\d+)?$", s.strip()) else None


def r_ratio_ok(readings, page):
    """断言：若把 ``readings`` 全删，删除比例仍低于页比例闸 ——
    保证测试真正落在「单调性」这一条判据上，而不是被页比例闸提前拦下。"""
    import app.services.page_transcript_filter as m

    total = sum(len(m._WS_RE.sub(" ", l).strip()) for l in page.splitlines() if l.strip())
    rem = sum(len(m._WS_RE.sub(" ", v).strip()) for v in readings)
    assert rem / total <= m.CHART_LADDER_MAX_PAGE_RATIO, (
        f"探针删除比例 {rem/total:.1%} 超过页比例闸 {m.CHART_LADDER_MAX_PAGE_RATIO:.0%}，"
        "测不到单调性判据"
    )
    return True


class TestChartLadderTail:
    """（承接 TestChartLadder 的后半段；因模块级 helper 夹在中间而单列）"""

    def test_real_timepoints_never_removed(self):
        """⚠️ 误伤断言：1215p9 的 ``143 min`` / ``179 min`` 是真实时间点。"""
        from app.services.page_transcript_filter import filter_page_transcript

        r = filter_page_transcript(AFM_TIMELINE_PAGE)
        assert r.chart_ladder_chars == 0
        for keep in ("143 min", "179 min", "151min", "Height (nm)"):
            assert keep in r.text

    def test_non_monotone_short_run_kept(self):
        """⚠️ 误伤断言：``0.0 20.33 -8.37`` 只有 3 连且非单调 -> 保留。"""
        from app.services.page_transcript_filter import find_chart_ladders

        page = "能垒\n\n0.0\n20.33\n-8.37\n16.87\n-16.87\n-24.97\n-99.09\n-159.56\n-237.06"
        assert find_chart_ladders(page) == []

    def test_short_run_below_threshold_kept(self):
        """⚠️ 误伤断言：单页里只有 1-2 个短标签行时**必须保留**。

        这是 brief 明确要求的方向 —— 「单页里 1-2 个短标签行应当保留
        （可能是真有价值的轴标签）」。
        """
        from app.services.page_transcript_filter import find_chart_ladders

        page = "实验条件：pH 7.2\n\nRemoval Rate (%)\n\n藻密度\n\n结论：传质效率提升 42%"
        assert find_chart_ladders(page) == []

    def test_run_length_gate_is_not_lowered(self):
        """⚠️ 回归钉子：7 个单调刻度**不删**（min_run=8）。

        下调到 4 会让 1193p19 的 ``0.0 20.33 -8.37`` 真数据被当刻度。
        """
        from app.services.page_transcript_filter import (
            CHART_LADDER_MIN_RUN,
            find_chart_ladders,
        )

        assert CHART_LADDER_MIN_RUN == 8
        page = "能垒图\n\n" + "\n".join(str(v) for v in (0.0, 20.33, -8.37, 16.87, -16.87, -24.97, -99.09))
        assert find_chart_ladders(page) == []

    def test_blank_lines_do_not_break_the_run(self):
        """模型爱在刻度中间插空行 —— 与 chrome run 规则同理，空行不切断。"""
        from app.services.page_transcript_filter import find_chart_ladders

        # 前后各垫一段真内容, 让删除比例低于 CHART_LADDER_MAX_PAGE_RATIO
        filler = "本实验考察了不同放电电压下的臭氧产率变化趋势，发现最佳工作点。\n\n"
        page = filler + "\n\n".join(str(v) for v in range(20, 0, -2)) + "\n\n" + filler
        idx = find_chart_ladders(page)
        assert len(idx) == 10

    def test_real_content_between_ticks_blocks_the_run(self):
        """⚠️ 回归钉子：**真内容行**夹在刻度中间会把 run 切断。

        agent40 的教训：``_scan`` 的 run 规则必须用「原始行号是否相邻」
        判断，不能只看「都进了候选表」。若把 :func:`_contiguous` 短路掉
        （M14），两段被正文隔开的刻度会被拼成一条假梯删掉。
        """
        from app.services.page_transcript_filter import find_chart_ladders

        filler = "本实验考察了不同放电电压下的臭氧产率变化趋势，发现最佳工作点。\n\n"
        # 上半段递减 + 中间真内容 + 下半段递减 —— 两段各自不足 8 连
        page = (
            filler
            + "\n".join(str(v) for v in (40, 38, 36, 34))
            + "\n\n产率显著提升，主要源于臭氧浓度的增加。\n\n"
            + "\n".join(str(v) for v in (32, 30, 28, 26))
            + "\n\n" + filler
        )
        assert find_chart_ladders(page) == []

    def test_non_contiguous_runs_are_not_glued(self):
        """同上：真正的回归钉子 —— 间隔 5 行以上的两段刻度不得被合并。"""
        from app.services.page_transcript_filter import find_chart_ladders

        filler = "本实验考察了不同放电电压下的臭氧产率变化趋势，发现最佳工作点。\n\n"
        page = (
            filler
            + "\n".join(str(v) for v in (40, 38, 36, 34))
            + "\n\n" + filler * 3
            + "\n".join(str(v) for v in (32, 30, 28, 26))
            + "\n\n" + filler
        )
        assert find_chart_ladders(page) == []

    def test_line_length_gate_blocks_long_numeric_runs(self):
        """⚠️ 回归钉子：单行 **<= 12 字符**是独立判据（M13）。

        放宽到 200 会把「高精度长数字」也当刻度 —— 真实数据里 10 位以上
        的有效数字（高精度计算输出的常数）**严格单调**是可能的。
        探针必须满足三条：①纯 ASCII 无中文（否则被更强的中文闸先拦）
        ②严格单调（否则被单调闸先拦）③删掉后不超页比例闸。
        三条更弱的判据全排除后，才真正落在行长闸上。
        """
        from app.services.page_transcript_filter import (
            CHART_LADDER_MAX_LINE,
            find_chart_ladders,
        )

        assert CHART_LADDER_MAX_LINE == 12
        # 高精度热力学常数：15-16 字符、纯数字、严格递减
        long_nums = [f"{i}.{i:09d}0000" for i in range(20, 0, -1)]
        assert all(len(t) > CHART_LADDER_MAX_LINE for t in long_nums)
        assert all(m_num(t) is not None for t in long_nums)
        # 垫**足够多**正文：同时排除中文闸、单调闸与页比例闸，
        # 让行长闸成为唯一拦阻
        filler = (
            "本实验考察了不同温度下的反应速率常数变化，发现其严格遵循阿伦尼乌斯方程，"
            "活化能取 42.6 kJ/mol。拟合优度 R² 达到 0.997，说明该动力学模型在"
            "本实验的温度区间内具有良好的适用性，可用于外推预测更高温度下的"
            "反应行为。整个测试过程中体系体积保持恒定，pH 未见明显漂移。"
        )
        page = filler + "\n\n" + "\n".join(long_nums) + "\n\n" + filler * 6
        assert r_ratio_ok(long_nums, page)
        assert find_chart_ladders(page) == [], "高精度长数字被当成坐标轴刻度删了"

    def test_page_ratio_cap_protects_whole_chart_page(self):
        """⚠️ 一页几乎全是刻度时**整页不删**（转人工而非净化）。

        1193p19 的纯图表版本：90% 以上都是刻度，删掉等于删整页。
        """
        from app.services.page_transcript_filter import find_chart_ladders

        page = "气泡半径分布\n\n" + "\n".join(str(v) for v in range(400, 0, -2))
        assert find_chart_ladders(page) == []

    def test_cjk_axis_title_never_removed(self):
        """⚠️ 误伤断言：``Removal Rate (%)`` 含中文/较长 -> 永不删。

        brief 明确点名了这几类（``Removal Rate (%)`` /
        ``藻密度/×10⁷ cell·ml⁻¹`` / ``O₂ MNBs``）。
        """
        from app.services.page_transcript_filter import find_chart_ladders

        page = "产率\n\n" + "\n".join(str(v) for v in range(40, 0, -2)) \
            + "\n\n产率 (g/kWh)\n\n结论：先增大后缓慢减小"
        r = filter_text(page)
        assert "产率 (g/kWh)" in r.text

    def test_removed_lines_are_recoverable(self):
        """刻度必须原样留在 removed_lines 里，可审计可回滚。"""
        from app.services.page_transcript_filter import filter_page_transcript

        r = filter_page_transcript(CHART_YIELD_PAGE)
        ladder = [rl for rl in r.removed_lines if rl.category == "chart_ladder"]
        assert {rl.text for rl in ladder} <= set(
            ln.strip() for ln in CHART_YIELD_PAGE.splitlines() if ln.strip()
        )


def filter_text(text):
    from app.services.page_transcript_filter import filter_page_transcript

    return filter_page_transcript(text)


# ============================================================================
# 11. 误伤总纲 —— 真实科研页一个字都不能少
# ============================================================================


class TestNoFalsePositive:
    @pytest.mark.parametrize(
        "page",
        [
            THERMO_PATHWAY_PAGE,
            AFM_TIMELINE_PAGE,
            NATURE_WEB_PAGE,
            SCIENCE_NEWS_PAGE,
            ELSEVIER_PDF_PAGE,
            TOC_PAGE,
        ],
        ids=["thermo", "afm", "nature", "science_news", "elsevier", "toc"],
    )
    def test_flagged_pages_keep_every_non_ladder_line(self, page):
        """被标 blocked 的页，**除刻度梯外一行都不能少**。"""
        from app.services.page_transcript_filter import filter_page_transcript

        r = filter_page_transcript(page)
        dropped = {
            ln.strip() for ln in r.raw_text.splitlines()
            if ln.strip() and ln.strip() not in {x.strip() for x in r.text.splitlines()}
        }
        ladder_only = {
            rl.text for rl in r.removed_lines if rl.category == "chart_ladder"
        }
        for line in dropped:
            assert line in ladder_only, f"非刻度行被删了: {line!r}"

    def test_normal_science_page_untouched(self):
        """agent40 的普通科研页必须**完全不受新防护影响**。"""
        from app.services.page_transcript_filter import filter_page_transcript

        page = (
            "臭氧微纳米气泡的传质特性\n\n"
            "臭氧在水中的溶解度随温度升高而降低\n"
            "气泡半径越小比表面积越大，传质速率越快\n"
            "实验采用 300 W 臭氧发生器，接触时间 60 s\n\n"
            "结论：粒径控制是提升传质效率的关键\n"
            "展望：下一步开展长期稳定性研究"
        )
        r = filter_page_transcript(page)
        assert r.text == page
        assert r.blocked is False
        assert r.third_party_paper is False
        assert r.template_page is False
        assert r.chart_ladder_chars == 0

    def test_english_abstract_slide_untouched(self):
        """⚠️ 误伤探针：本组做英文汇报时的 Abstract 页。"""
        from app.services.page_transcript_filter import filter_page_transcript

        page = (
            "Abstract\n\n"
            "Micro-nano bubbles have been widely applied to enhance ozonation for "
            "advanced wastewater treatment, yet the interfacial hydroxyl radical "
            "generation mechanism remains poorly understood. In this work we combined "
            "in-situ chemiluminescence imaging with molecular dynamics simulations "
            "to reveal the enrichment of hydroxide ions at the gas-liquid interface."
        )
        r = filter_page_transcript(page)
        assert r.text == page
        assert r.third_party_paper is False
        assert r.blocked is False

    def test_paper_title_on_own_slide_kept(self):
        """⚠️ 误伤探针：正文里引用论文标题 + 期刊名 + DOI 的研究页。"""
        from app.services.page_transcript_filter import filter_page_transcript

        page = (
            "参考工作\n\n"
            "Y. Zhang et al., Science of the Total Environment 2024, 912, 168940\n\n"
            "该文报道了微纳米气泡对盐碱土的修复作用，我们进一步考察了其中的氧化机理。"
        )
        r = filter_page_transcript(page)
        assert r.text == page
        assert r.third_party_paper is False
        assert r.blocked is False

    def test_data_table_page_never_truncated(self):
        """⚠️ 误伤探针：正文数据表（数字多但不连续/非单调）必须完整保留。"""
        from app.services.page_transcript_filter import filter_page_transcript

        page = (
            "实验数据汇总\n\n"
            "样品编号\t去除率\t产率\n"
            "A1\t87.3\t0.42\n"
            "A2\t79.1\t0.38\n"
            "A3\t91.5\t0.51\n"
            "A4\t68.2\t0.29\n"
            "A5\t83.7\t0.44\n\n"
            "重复性良好，标准偏差小于 5%。"
        )
        r = filter_page_transcript(page)
        assert r.text == page
        assert r.chart_ladder_chars == 0

    def test_idempotent_with_new_rules(self):
        """新防护也必须幂等 —— 尤其刻度梯（跑两次结果相同）。"""
        from app.services.page_transcript_filter import filter_page_transcript

        for page in (CHART_YIELD_PAGE, THERMO_PATHWAY_PAGE, NATURE_WEB_PAGE, TOC_PAGE):
            once = filter_page_transcript(page).text
            assert filter_page_transcript(once).text == once

    def test_never_empties_a_page_with_content(self):
        """刻度梯不得把有内容的页清空。"""
        from app.services.page_transcript_filter import filter_page_transcript

        for page in (CHART_YIELD_PAGE, THERMO_PATHWAY_PAGE, AFM_TIMELINE_PAGE,
                     NATURE_WEB_PAGE, SCIENCE_NEWS_PAGE, ELSEVIER_PDF_PAGE, TOC_PAGE):
            assert filter_page_transcript(page).text.strip(), "整页被清空了"