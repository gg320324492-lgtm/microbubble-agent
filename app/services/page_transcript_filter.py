"""PPT/文档整页视觉转写的结果净化 — 纯函数、零 IO，供将来的转写管线调用。

## 定位（2026-10-09 agent40）

**整页视觉转写功能本身尚不存在**（agent35 / agent37 均为只读调研，未写生产代码）。
本模块因此**只提供净化能力**，不负责调模型、不落库、不读写任何 IO：
调用方（将来的转写管线）拿到「一页图片 → 模型返回的转写文本」后调用
:func:`filter_page_transcript`，根据返回值决定是否入库 / 是否转人工。

用法形态刻意做成纯函数（`str -> FilterResult`），与同仓
``app/services/image_decoration_filter.py``（母版横幅识别）保持同构：
两边都是「判据独立可测、被别处 import、阈值是模块级常量」。

## 三条防护及其证据

防护 A — **拍摄屏幕拦截**（拍的是别人笔记本电脑上的课件，不是投影幕）
    标定页 1537 p35（``2023.9.15 ... .pptx``）是会场后排拍到的一台笔记本屏幕，
    画面里是**另一位研究者（清华 章鹏超/陈昌盛/冯牧野）的未发表课件**。
    1815 字转写里只有 138 字属于本 deck，其余是 WPS ribbon + 任务栏 + 别人的研究。
    直接入库 = 把别人的未发表成果塞进我们的检索池。
    判据 = ``chrome_ratio >= 0.15``（页面字符里被判定为软件 chrome 的占比）。

防护 B — **软件 chrome 行剔除**（功能区标签 / GUI 控件文案 / 任务栏 / 未激活水印）
    同一批实测里 1254 p10 是 MATLAB GUI 截图，1029 字里绝大部分是界面文案
    （``Step 1: Pixel resolution calibration`` / ``Confirm, or modify accordingly…``）。
    agent35 的词表只覆盖中文 Office/WPS，英文 GUI 全漏；agent37 补了英文 regex，
    但中文侧仍是"整行精确匹配单���"，对"讲 PPT 制作"的教学页有误伤面。
    本模块在此基础上**加了一层上下文规则**（见下「为什么误伤面被压住」）。

防护 C — **模型违反"不要总结"指令的追加段切除**
    实测约 3%（38 页 1 例、311 页 1 例）模型会在转写末尾追加
    ``核心文字内容（幻灯片正文）：`` + 一串 ``- 标题：… / - 作者：…`` 摘要。
    这段**不是幻灯片原文**，混进向量池会变成「原文 + 模型二次概括」的双份语义。

防护 D — **整页第三方论文 / 期刊网页截图**（agent42, 2026-10-10）
    a41 随机抽检 269 页真实转写，发现 6 页**整页就是别人的论文**：
    ``1101 p2``（Science 系 NEWS 栏整页，3948 字）``1208 p4``（Nature
    Communications 网页截图）``1051 p2``（ACS PDF 首页，4631 字）…
    这与防护 A/B 的性质根本不同 —— A/B 剔的是**chrome**（噪声），
    D 剔的是**别人的正文**（内容污染）。整页 ScienceDirect 首页进检索池 =
    检索「O₃-MNB 反冲」时召回一段河北工业大学水处理的论文摘要，
    且这段摘要与本组零相关。
    ⚠️ **这类页只标 ``blocked``（转人工），绝不删内容** —— 因为无法从纯文本
    区分「论文正文」与「用户自己摘抄的论文段落」，删了就可能删掉真引用。
    判据 = **6 个正交"出版社版面族"命中 >= 2 个** + **外文正文规模够大**
    （见 :data:`PAPER_MIN_FAMILIES` / :data:`PAPER_MIN_FOREIGN_CHARS`）。

防护 E — **非 Office 科学软件 GUI**（agent42, 2026-10-10）
    agent40 的 :data:`CHROME_WEAK_EN` 只覆盖 Office / MATLAB / RStudio。
    OVITO / VASP / Materials Studio 这类**分子动力学与材料模拟软件**的
    GUI 文案整类漏网。实测 ``1059 p6`` 是 OVITO Basic 窗口截图
    （``Quick command search`` / ``Directory: C:/Users/TJU/Desktop`` /
    ``Layer (3).cif`` / ``Number of atoms: 561``），但整页 chrome 只有 2.3%，
    远低于 15% 拦截阈值 —— 因为它**没有 Office 那种 40 行功能区**。
    对策不是降阈值（会把大片真图表页打挂），而是**补词表**：
    把科学软件 GUI 的控件文案加进 STRONG 档，让 :func:`chrome_ratio`
    自己把这一页顶过阈值。

防护 F — **目录页 / 章节分隔页 / 致谢页**（agent42, 2026-10-10）
    ``886 p3`` 这类目录页被算进 A（26 字符）。根因是 4-gram dedup 被
    中英文差异打败：原生文本是 ``/CONTENTS``，转写是 ``目录``，二者
    4-gram 零重叠，于是整页都被当成"新增内容"。
    对策同样**只标 blocked 不删内容** —— 目录页虽然没价值，但删不删是
    调用方的入库策略问题，不是净化问题。

防护 G — **坐标轴刻度梯**（agent42, 2026-10-10）
    图表页里成百上千个刻度数字（``45 44 43 42 … 30``）被当成高价值内容，
    占 A 的 13.2%。⚠️ **但绝不能"短行/纯数字就删"** —— agent40 已实测
    踩过这个坑（见 :data:`_MEASURE_RE` 注释：放宽到纯数字会误删
    1066p17 / 1126p10 的真刻度）。本模块的解法是**上下文规则 + 单调性**：
    只删**连续 >= :data:`CHART_LADDER_MIN_RUN` 个严格单调的纯数字行**。
    单调性是真刻度的**结构不变量**（坐标轴必然单调），而真实科研数据
    （能垒 ``-237.06``、热重峰温 ``2.83%``、时间点 ``143 min``）
    **不可能连续 8 个严格单调** —— 这就是零误伤的数学依据。

## 为什么误伤面被压住（这是本模块最重要的一段）

词表里的中文词绝大多数是**幻灯片正文也可能出现的普通词**：
``插入`` / ``设计`` / ``表格`` / ``图片`` / ``公式`` / ``帮助`` / ``视图`` / ``格式`` …
本组开组会完全可能真有人讲「怎么做好 PPT」，这些词就会**成片**出现在正文里。
所以本模块**不做单词级 substring 匹配**，而是分三档 + 一条上下文规则：

1. **STRONG 档**（整行精确匹配 / 结构化正则 / 固定短语）—— 这些词本身就是
   UI 术语（``幻灯片编号`` / ``文件资源管理器`` / ``File Window Help`` /
   ``Select other image for resolution calibration``），正文里出现即 chrome，
   单独成行也剔。
2. **WEAK 档**（普通词：``插入`` / ``设计`` / ``Confirm`` / ``Preview`` / ``默认`` …）
   —— **只有落进长度 >= :data:`MIN_CHROME_RUN` 的连续 chrome 串才剔**。
   功能区是**连成 40+ 行的整块**；正文里的"插入"是散落的句子。
   一条正文 bullet 恰好是"设计"（比如某页标题就叫《设计》），它是**孤立一行**，
   run 长度 1，**保留**。
3. **run = 连续**（跳过空行）—— 模型爱在功能区中间插空行，语义上仍是同一块。
   空行不切断 run 正是为了抓住 1254 p10 那种被空行分组的 GUI。

这条规则的净效果：**「讲 PPT 制作」的正文基本零剔除，功能区整块剔除。**
实测见 agent40 报告（349 页：真阳 2 页、假阳 0 页）。

⚠️ 与 agent37 的一处**有意分歧**：agent37 额外提了「含外部机构名」判据
（清华 / 中科院 …）。本模块**不实现**它 —— 该组 deck 本身就在「未来颗粒前沿论坛」
语境里，合法引用清华、中科院分区（期刊指标）会造成高假阳。只有 ``chrome_ratio``
进拦截判据。

## 取舍原则

宁可漏过滤，不可误伤。agent37 实测：漏检（残留几行 GUI 文案进向量池）无害，
误删（把真实科研结论删掉）会直接毁掉检索质量。所以：

* 所有阈值都是**保守侧**，宁可让噪声漏过去。
* 判定结果是**「建议拦截」不是「自动丢弃」**—— 见 :attr:`FilterResult.blocked`
  与 :attr:`FilterResult.should_auto_ingest`，调用方必须显式检查。
* 被剔除的行、被切掉的尾巴**都原样放在返回值里**，可审计、可回滚。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

# ── 判据阈值 ────────────────────────────────────────────────────────────
#: 建议拦截阈值（chrome 字符占比）。1537p35 实测 32.2%，其余 36 页最高 1.6%，
#: 20 倍余量；311 页试点里最高只有 1254p10（17.0%），其余 310 页 **全为 0.0%**。
#: **不要下调** —— 宁可让更多屏幕照进池子转人工，也不要误拦真科研页。
CHROME_BLOCK_RATIO = 0.15

#: WEAK 档普通词必须连成这么多行才算功能区/工具栏。功能区实测 40+ 行连续，
#: 教学正文的散落用词远达不到；孤立的"设计"（《设计》页标题）因此保留。
MIN_CHROME_RUN = 3

#: **纯 WEAK run**（整串全是"表格/图片/公式"这类普通词、一个 UI 术语都没有）
#: 要连成这么多行才成立。实测探针：一页讲 PPT 模板的正文里
#: ``表格 / 图片 / 公式`` 正好是 3 行弱词连排，MIN_CHROME_RUN=3 时会被误删。
#: 真功能区（1537p35 的"开始/插入/设计/切换/动画/放映工具/超链接"7 连）
#: 以及一切含 STRONG 项的 run 都不受这条约束。
MIN_ALL_WEAK_RUN = 5

#: 尾部"schema 摘要块"最少连续几条 schema bullet 才切（无表头变体）。
#: 标题页的 `- 作者：/- 单位：` 只有 2 条且不含要点类键 → 不触发。
MIN_SCHEMA_TAIL_RUN = 4
#: 切 schema 摘要块时，其上方至少要有这么多行真内容，避免把整页切空。
MIN_LINES_ABOVE_SCHEMA_TAIL = 3

#: 未激活水印的**页级**拦截门槛。比 chrome_ratio 弱得多：一条水印只说明
#: 「这张图是拍电脑屏幕拍的」，**很可能是主讲人自己那台**（正常内容），
#: 不足以推断「拍的是别人未发表的研究」。所以要求 **同一页出现 >= 2 条**
#: （真·桌面截屏会把两条一起框进来），或水印字符占比 >= 20%（整页被淹没）。
#: 实测 4 页带水印：2 条的 1268p20 / 1540p12 拦，1 条的 1268p12 / 1268p28 不拦。
WATERMARK_MIN_LINES = 2
WATERMARK_RATIO_FLOOR = 0.20
#: 水印页太短时比例没意义（1268p12 全页 125 字符，2 条就是 16%）。
WATERMARK_MIN_PAGE_CHARS = 200

# ── 防护 D 阈值：整页第三方论文 / 期刊网页截图（agent42）─────────────────
#: 命中多少个**正交**"出版社版面族"才判为第三方论文页。
#: 实测 269 页：6 页真污染页命中 3~5 族；合法引用页最多 3 族，
#: 且外文正文规模远小（见 :data:`PAPER_MIN_FOREIGN_CHARS`）。留 1 族余量。
PAPER_MIN_FAMILIES = 2

#: 「外文正文」的最小规模（字符）—— 只统计 **>= 40 字符**的行且**中文占比 < 5%**。
#: 40 字符门槛把 ``Cite This: Acc. Chem. Res. 2019, 52, 1196-1205`` 这类
#: 单行引用排除在外（它只有 45 字符且无正文段落），把整段 Abstract /
#: Introduction 正文纳入。
#: 实测：6 页真污染页最低 339（1036p2），合法引用页最高 294（1250p2）；
#: 阈值 250 卡在两者之间，两侧各留 ~30% 余量。
PAPER_MIN_FOREIGN_CHARS = 250

#: 还要求至少有一段 **>= 150 字符**的外文长行 —— 即真的有一整段论文正文，
#: 而不只是导航碎片。这条把 1250p2（``Cite This`` + 标题 + 作者，0 段）
#: 与 1036p2（1 段 151 字符的英文标题+摘要）区分开，是**第二道保险**。
PAPER_MIN_LONG_LINE = 150

#: 判定「外文正文行」的最小行长。低于此的行（如 ``ELSEVIER`` /
#: ``Nature Communications``）算 chrome 不算正文。
PAPER_FOREIGN_MIN_LINE = 40
#: 单行里中文（含全角标点）字符占比超过此值就不是「外文正文行」。
PAPER_FOREIGN_MAX_CJK_RATIO = 0.05

# ── 防护 G 阈值：坐标轴刻度梯（agent42）──────────────────────────────────
#: 一条刻度梯至少要连续多少个纯数字行。
#: ⚠️ **不要下调到 4 以下** —— 实测 1193p19 的真实热力学数据里，
#: ``0.0 20.33 -8.37`` 恰好 3 连；下调会把真数据当刻度删。
CHART_LADDER_MIN_RUN = 8
#: 单行长度上限（strip 后）。刻度都是 ``-0.08`` / ``3500`` 这样的短串。
CHART_LADDER_MAX_LINE = 12
#: 单页最多允许删掉的比例 —— 超了说明这页**整体就是一张图**，
#: 删刻度等于删掉整页（那属于"转人工"而不是"净化"）。
#: 实测 269 页：命中 14 页的最高占比是 1025p15 的 25.1%（三张 pH/ORP/电导率
#: 折线图的纵轴，删掉的都是刻度），阈值 0.30 只比它高 5 个百分点 ——
#: 再高就可能放行「整页只有一张图」的页，把图例当正文删光。**不要再上调。**
CHART_LADDER_MAX_PAGE_RATIO = 0.30


# ── STRONG 档：中文 UI 术语（整行精确匹配）──────────────────────────────
# 出处：1537p35 实测转写里的 WPS 功能区标签 + Office 通用命令。
# 判定依据「为什么算 chrome」：这些是**软件命令/控件名**，科研正文不会出现，
# 即便本组真讲 PPT 制作，正文也会写成「插入图片后调整大小」而不是孤立一行
# 「插入图片」。
CHROME_STRONG_CN: frozenset = frozenset({
    # Office/WPS 功能区
    "屏幕录制", "幻灯片编号", "新建幻灯片", "插入屏幕录制",
    "删除全部批注", "显示批注", "新建批注", "删除批注",
    "字符底纹", "字符间距", "删除格式", "设置文本效果格式", "字体颜色",
    "文本效果", "背景样式", "选择窗格",
    "页面大小", "页面方向", "页面设置", "网格线", "颜色模式",
    "全局替换", "查找和替换", "保护文档", "文档保护", "拼写检查",
    "校对", "朗读", "艺术字", "视觉设计",
    "插入表格", "插入图片", "插入形状", "插入图表", "插入视频",
    "插入音频", "插入超链接", "插入批注", "插入文本框", "插入对象",
    # Windows 任务栏 / 文件管理
    "文件资源管理器", "新建文件夹", "回收站", "任务栏", "此电脑",
    "控制面板", "所有程序",
})

#: STRONG 档：英文 GUI 术语（整行精确匹配，**大小写不敏感**）。
#: 出处：1254p10 实测 MATLAB App Designer 窗口文案 + 其余常见 GUI。
CHROME_STRONG_EN: frozenset = frozenset({
    "file window help",            # MATLAB / RStudio 菜单栏
    "image name",
    "confirm parameters",
    "sample image",
    "processed image",
    "batch process images",
    "using default parameters",
    "choosing my own parameters",
    "calibrate manually",
    "<< back", "next >>", "< prev img", "next img >",
    "or:",
    "home", "insert",  # PowerPoint 的 Home/Insert 选项卡（与 'start' 对照）
})

#: STRONG 档：**科学计算软件** GUI 控件文案（整行精确匹配，大小写不敏感）。
#: 出处：1059p6 实测 OVITO Basic 窗口截图（原子/分子可视化）。
#: 判定依据「为什么算 chrome」：这些是**分子动力学 / 材料模拟软件的
#: 面板标题与字段名**，它们描述的是"软件里有哪些面板"，不是科研结论。
#: 同组真讲 OVITO 时正文会写"用 OVITO 观察了黏土层间结构"，
#: 而不是把这些面板名连排成一块。
SCI_GUI_STRONG_EN: frozenset = frozenset({
    # OVITO（1059p6 实测，22/44 行命中）
    "quick command search",      # OVITO 顶部搜索框
    "add modification...",
    "center simulation box on coordinate origin",
    "simulation cell",
    "visual elements",
    "particle types",
    "cif reader",
    "global attributes",
    "number of atoms",
    "current file",
    "directory",
    "search pattern",
    "file sequence",
    "playback ratio",
    "current frame",
    "external file",
    "data source",
    "found 1 matching file",
    "auto-generate",
    "change...",
    # 窗口标题（OVITO 会把文件名写进标题栏）
    "ovito basic (open visualization tool)",
})

#: STRONG 档：科学软件 GUI 的中文面板文案（整行精确匹配）。
#: 出处：1059p6 实测 OVITO 的拖拽上传区。
SCI_GUI_STRONG_CN: frozenset = frozenset({
    "拖拽至此上传",
    "外部文件",
    "数据源",
    "文件序列",
    "搜索模式",
    "当前帧",
    "粒子类型",
    "模拟单元",
    "可视化元素",
    "添加修改",
    "全局属性",
})


# ── WEAK 档：普通词（必须连成 run 才剔）────────────────────────────────
#: 出处：1537p35 的 WPS ribbon 词条 + Office/浏览器/邮件客户端通用菜单词。
#: ⚠️ 这些词在正文里同样高频（讲 PPT 制作就全是这些词），**单独出现一律保留**。
CHROME_WEAK_CN: frozenset = frozenset({
    "开始", "插入", "设计", "切换", "动画", "视图", "帮助", "审阅",
    "放映工具", "公式", "图例", "字体", "效果", "段落", "对象",
    "表格", "图片", "形状", "SmartArt", "图表", "视频", "音频",
    "批注", "超链接", "文本框", "自定义", "颜色", "排列", "对齐",
    "组合", "旋转", "选择", "页面", "页码", "标尺", "调色板",
    "说明", "字符", "查找", "替换", "修订", "语言", "翻译",
    "保护", "备注", "格式", "主题", "所有主题",
    # WPS 主题名（1537p35 实测）
    "彩色", "灰度", "全新", "经典", "平面", "复古",
    "墨绿", "紫色", "橙色", "蓝色", "绿色", "金色", "暗色",
    # 浏览器 / 邮件客户端 / 编辑器菜单
    "搜索", "文件夹", "选项", "工具", "保存", "另存为", "打印",
    "复制", "剪切", "粘贴", "撤销", "重做",
    "编辑", "文件", "窗口", "工具栏", "状态栏", "菜单", "选项卡",
    "属性", "设置", "高级", "默认", "示例",
    "收藏夹", "历史记录", "下载", "上传", "分享", "发布",
})

#: WEAK 档英文。⚠️ 刻意**不含** `results` / `figure` / `model` / `data` 等
#: 科研正文高频词 —— 它们在 MATLAB 里也是选项卡名，但删掉误伤太大，
#: 选项卡行由 :data:`_TAB_BAR_RE` 整行结构规则接管。
CHROME_WEAK_EN: frozenset = frozenset({
    "file", "edit", "view", "format", "tools", "help", "window",
    "data", "plot", "publish", "session", "build", "debug", "profile",
    "confirm", "preview", "example", "default", "folder", "calibration",
    "parameters", "settings", "options", "select", "choose", "click",
    "apply", "cancel", "close", "save", "open", "new", "refresh",
    "reset", "run", "stop", "start", "load", "browse", "upload",
    "download", "back", "next", "prev", "previous", "done",
    "ok", "yes", "no", "label", "axes", "legend", "grid",
})


# ── STRONG 档：结构化正则（整行匹配）────────────────────────────────────
#: GUI 步骤头：``Step 1: Pixel resolution calibration`` / ``Step 2:``
_STEP_RE = re.compile(r"^step\s*\d+\s*[:：]?", re.I)

#: GUI 导航按钮：``<< Back`` / ``Next >>`` / ``< Prev img`` / ``Next img >``
_NAV_BTN_RE = re.compile(r"^[<>]{1,2}\s*[A-Za-z][\w ]*\s*[<>]{0,2}$")

#: 菜单栏：``File Window Help`` / ``File Edit Code View Plots Session ...``
_MENU_ITEMS = (
    "File|Edit|View|Insert|Format|Tools|Help|Window|Data|Home|Plot|Plotting|"
    "Publish|Session|Build|Debug|Profile|Code|Environment|Camera|Apps"
)
_MENU_BAR_RE = re.compile(rf"^(?:{_MENU_ITEMS})(?:\s+(?:{_MENU_ITEMS}))+$", re.I)

#: 选项卡栏 / 多栏对齐行：靠 **2 个以上连续空格** 分栏。
#: 正文散文**永远不含 2+ 连续空格**，所以这个结构信号本身很安全。
#: 但仍加一道合取保险：拆成 >=3 段后，至少 2 段自身命中 chrome 词/规则，
#: 才判定整行是 chrome（纯数据表 ``0.3    1.2    0.8`` 拆出来各段都不命中）。
_TAB_SPLIT_RE = re.compile(r"\s{2,}")
_MIN_TAB_PARTS = 3
_MIN_TAB_CHROME_PARTS = 2

#: 标题栏文件名：``百度智能云0.19.pptx`` / ``清华大学_仿模拟OH....pdf``。
#: 幻灯片正文不会出现"整行就是一个带扩展名的文件名"。
_FILENAME_RE = re.compile(
    r"^[^/\\:*?\"<>|]{1,80}\.(?:pptx?|docx?|xlsx?|pdf|wps|et)(?:\s*[\d.]+)?\.{0,3}$", re.I
)

#: GUI 数值读数：``0 px/mm`` / ``px/mm``。⚠️ **只认带单位后缀的**。
#: 初版写成 ``^\d+(\.\d+)?$`` 把图表刻度（500/400/300…）全当成 chrome，
#: 实测误删 1066p17 / 1126p10 等页的全部坐标轴刻度 —— 真内容，必须收紧到
#: 只匹配 1254p10 里那条 ``0 px/mm`` GUI 读数。**不要再放宽回纯数字。**
_MEASURE_RE = re.compile(r"^(?:\d+(?:\.\d+)?\s*)?(?:px|pixels?)\s*/\s*mm$", re.I)

#: GUI 单选/复选圆点：``● Using default parameters`` / ``○ Choosing my own``。
#: ⚠️ 只认**半角空格 + ≥3 个拉丁字母**跟着的写法，且降级为 WEAK。
#: 初版含 ``•·`` 且算 STRONG，实测把 ``•界面水分子排列高度有序``、
#: ``• O₃ nanobubbles maintain good stability…`` 这类**正文 bullet** 全删了，
#: ``●pH=5`` 图例也被删 —— 中文 slide 的项目符号就是 ``•``。绝不能再放宽。
_RADIO_RE = re.compile(r"^[●○◉◦]\s+[A-Za-z]{3,}")

#: MATLAB App Designer 窗口标题残留：``GUI_Bubb...``
_MATLAB_GUI_RE = re.compile(r"^gui[_a-z0-9]*\s*\.*$", re.I)

# ── 防护 E：科学软件 GUI 的结构化正则（agent42）────────────────────────
#: 1059p6 实测 OVITO 的**取值字段行**：``Directory:  C:/Users/TJU/Desktop`` /
#: ``Current file:  Layer (3).cif`` / ``Number of atoms: 561``。
#: 判定依据「为什么算 chrome」：这是 GUI 表单控件的 ``标签: 值`` 结构 ——
#: **冒号 + 空格 + 紧跟取值**；科研正文写句子不用这种形状
#: （写「原子数量为 561」而非 ``Number of atoms: 561``）。
#: ⚠️ **冒号是必需的一部分**：初版写成 ``\s*:?\s+``（冒号可选），
#: 结果 ``Current frame 切换到下一帧`` 这类正文句子也被误判 ——
#: 冒号才是「控件取值」与「散文」的分界。
_SCI_GUI_FIELD_RE = re.compile(
    r"^(?:current file|directory|search pattern|playback ratio|current frame"
    r"|number of atoms|auto-generate)\s*:\s*\S", re.I
)

#: 科学软件 GUI 的**本地文件路径**：``C:/Users/TJU/Desktop`` / ``D:\\runs\\a.cif``。
#: 判定依据「为什么算 chrome」：幻灯片正文引用数据文件时几乎不会写出
#: **本机用户目录**（那是操作者在自己机器上的路径，不是共享资产）。
#: ⚠️ 只认 ``盘符:\\\\Users\\\\`` / ``盘符:/Users/`` 这种**用户目录**形状，
#: 不认一般相对路径 —— 相对路径可能真是正文里的示例文件。
_SCI_GUI_USERDIR_RE = re.compile(r"\b[A-Za-z]:[\\/]Users[\\/]", re.I)


# ── STRONG 档：固定短语（substring，多词，误伤面极低）──────────────────
#: 出处：1254p10 实测 GUI 帮助句 + 通用软件操作语。
#: 全部是 **2 词以上** 的 UI 固定搭配，科研正文不会出现。
CHROME_PHRASES: Tuple[str, ...] = (
    # MATLAB GUI 帮助句（1254p10 原文）
    "resolution calibration",
    "background correction",
    "image processing algorithm",
    "dropdown menu",
    "modify accordingly",
    "check results using",
    "select other image for",
    # 通用 UI 操作语
    "click the", "press the", "right-click", "double-click",
    "file window help",
    # WPS 标签栏页签统计（1537p35 实测 "共49页8个窗体"）
    "个窗体",
    # 中文 UI 术语（多字搭配）
    "快捷键", "功能区", "右键菜单", "状态栏", "任务栏",
    "右键单击", "演示文稿视图", "幻灯片浏览", "演讲者视图", "备注页",
)

#: Windows 未激活水印（大小写不敏感；含中英文两种变体）。
#: ⚠️ 用 **fullmatch** 而不是 search —— 实测 search 会把正文里的
#: 「实验室工作站均已激活 Windows 10 专业版」整行删掉（agent40 误伤探针实证）。
#: 真水印永远是**独立成行**的一整句，句中出现不算。
_WATERMARK_RE = re.compile(
    r"(?:激活\s*Windows"
    r"|转到[“”\"'\s]*设置[“”\"'\s]*以激活\s*Windows[.。]?)"
    r"[.。]?"
)


# ── 防护 D：第三方论文页的「出版社版面族」（agent42）─────────────────────
# 6 个族**互不重叠**，每个族内的多条目是「同一件事的不同写法」。
# 为什么要分族而不是数命中条目数：一篇论文截图会同时命中 3~5 个族，
# 而**本组合法引用**（讲「我们引用了这篇论文」+ 贴个 citation 行）
# 最多只碰 2~3 个族。按条目数会把这两种情况混成同一个分数。
#
# 实测 269 页（a41 样本）：命中 >= 2 族的只有 8 页 ——
#   真污染 6 页（1036p2 / 1051p2 / 1072p2 / 1101p2 / 1181p2 / 1208p4）
#   合法引用 2 页（1101p5 / 1250p2），二者靠 :data:`PAPER_MIN_FOREIGN_CHARS` 分开。
PAPER_FAMILIES: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    # F1 期刊/出版社刊头 —— 「这是哪本杂志」的结构性标识
    ("masthead", (
        r"^\s*(?:nature\s+communications|nature|science of the total environment|"
        r"water\s+research|the\s+innovation|advances\s+in\s+space\s+research|"
        r"accounts\s+of\s+chemical\s+research)\s*$",
        r"^\s*elsevier\s*$",
        r"^\s*frontiers\s*\|",
        r"^\s*the\s+journal\s+of\s*$",
        r"^\s*volume\s+\d+,\s*issue\s+\d+,\s*\d{4},\s*pages\s+\d+",
    )),
    # F2 网页导航 —— 出版商**网站**的导航条（PDF 截图没有，是网页截图的指纹）
    ("nav", (
        r"contents\s+lists\s+available",
        r"^\s*journal\s+homepage",
        r"explore\s+content\s+about\s+the\s+journal\s+publish\s+with\s+us",
        r">\s*articles\s*>\s*article",
        r"^\s*nature\s*>\s*\S",
        r"^\s*check\s+for\s+updates\s*$",
        r"^\s*show\s+more\s*$",
        r"^\s*\+\s*add\s+to\s+mendeley",
        r"^\s*get\s+rights\s+and\s+content\s*$",
        r"^\s*read\s+online\s*$",
        r"^\s*article\s+recommendations\s*$",
        r"^\s*supporting\s+information\s*$",
        r"^\s*published\s+as\s+part\s+of",
    )),
    # F3 影响力计量 —— Altmetric / Accesses / OPEN ACCESS 角标
    ("metrics", (
        r"altmetric",
        r"\d+\s*accesses",
        r"^\s*access\s*$",
        r"^\s*open\s+access\s*$",
        r"^\s*metrics\s*&\s*more\s*$",
    )),
    # F4 编辑与通信 —— 审稿人 / 通讯作者角标
    ("editorial", (
        r"^\s*edited\s+by\s*$",
        r"^\s*reviewed\s+by\s*$",
        r"correspondence\s*[:：]",
        r"✉\s*\S+@",
        r"contributed\s+equally",
    )),
    # F5 投稿流程 —— 收稿/修回/接收/引用/DOI
    ("submission", (
        r"^\s*received\s*[:：]",
        r"^\s*revised\s*[:：]",
        r"^\s*accepted\s*[:：]",
        r"published\s+online\s*:",
        r"^\s*citation\s*[:：]",
        r"^\s*cite\s+this\s*[:：]",
        r"^\s*doi\s+\S+",
        r"https?://doi\.org/",
        r"^\s*pubs\.acs\.org/",
    )),
    # F6 论文体例小标题 —— ARTICLE INFO / ABSTRACT / HIGHLIGHTS
    ("bodyhdr", (
        r"^\s*article\s+info\s*$",
        r"^\s*abstract\s*[:：]?\s*$",
        r"^\s*keywords\s*[:：]?\s*$",
        r"^\s*highlights\s*$",
        r"^\s*graphical\s+abstract\s*$",
        r"^\s*\d+\.?\s*introduction\s*$",
        r"^\s*news\s*&\s*buzz\s*$",
    )),
)

PAPER_FAMILY_RES = tuple(
    (name, tuple(re.compile(rx, re.I) for rx in rxs)) for name, rxs in PAPER_FAMILIES
)

#: CJK（含全角标点）判定 —— 用于「这行是不是外文正文行」。
_CJK_RE = re.compile(r"[　-〿぀-ヿ一-鿿＀-￯]")

#: 模型违反指令的**另一种**措辞（agent40 只处理了「核心文字内容（幻灯片正文）：」）。
#: 实测 1208p4 首行就是「以下是该幻灯片上按阅读顺序提取的所有文字：」——
#: Nature 网页截图本身就带着这句模型旁白。它同时也是论文页的强信号，
#: 但**不单独作为删行依据**（模型旁白不是幻灯片原文，删掉是对的，
#: 可惜它只有 1 行、收益太小，不值得单开一条规则）。


# ── 防护 F：目录页 / 章节分隔页 / 致谢页（agent42）──────────────────────
#: 目录页的页头。实测两种写法：中文 ``目录`` 与母版占位符 ``/CONTENTS``
#: （PowerPoint 的内置版式名，被 4-gram dedup 当成"新内容"）。
_TOC_HEAD_RE = re.compile(r"^\s*(?:/\s*)?(?:目\s*录|contents?)\s*$", re.I)

#: 目录条目行：``1 研究背景`` / ``4. 结论`` / ``◆三、微纳米气泡中·OH的产生``。
_TOC_ITEM_RE = re.compile(
    r"^\s*(?:[◆■●▲·•]\s*)?"
    r"(?:\d{1,2}\s*[.、．)）]?\s*|[一二三四五六七八九十]{1,3}\s*[、.．)）]\s*)"
    r"\S.{0,60}$"
)

#: 致谢页页头。⚠️ 页长 / 行长的双重上限在 :func:`detect_template_page`
#: 里统一施加（见 :data:`TEMPLATE_MAX_PAGE_CHARS` /
#: :data:`TEMPLATE_MAX_LINE_CHARS`），本条只管**认出「谢谢」二字**。
_THANKS_RE = re.compile(r"^\s*(?:谢谢[！!。]?|感谢(?:聆听|聆听指导)|thank\s+you)\s*$", re.I)

#: 模板页的**页长**上限。⚠️ 这是 :func:`detect_template_page` 最重要的保险：
#: 光靠「有 ``目录`` 页头 + 几条章节条目」不够 —— 一页真研究内容完全可能
#: 以「目录」两字开头（讲"怎么给 PPT 建目录"），或在致谢页上顺手多写两句。
#: 实测 269 页：真模板页最长 68 字符（1220p2）、最长单行 20 字符（1220p12），
#: 阈值卡在这两个实测极值与「带正文的伪模板页」之间。
TEMPLATE_MAX_PAGE_CHARS = 150
#: 单行长度上限 —— 模板页**没有长句**。真科研页必有整行 >= 200 字符的正文。
#: 实测真模板页最长单行 20 字符，阈值 60 留 3 倍余量；本组语料里
#: 「目录页上写了半段结论」的最长观测行是 91 字符，仍被正确放行。
TEMPLATE_MAX_LINE_CHARS = 60


# ── 防护 G：坐标轴刻度梯（agent42）──────────────────────────────────────
#: 纯数字行（可带正负号 / 小数点）。⚠️ **不做单位后缀匹配** ——
#: 允许 ``3500`` ``-0.08`` 这种裸刻度进入候选，靠**单调性**而非形状来定夺。
_CHART_NUM_RE = re.compile(r"^[+\-−–]?\d{1,7}(?:\.\d+)?$")


def _chart_num(s: str) -> Optional[float]:
    """把刻度行解析成 float；不是纯数字返回 None。"""
    t = s.strip()
    if not _CHART_NUM_RE.match(t):
        return None
    try:
        return float(t.replace("−", "-").replace("–", "-"))
    except ValueError:   # pragma: no cover — 正则已保证可转
        return None


# ── 防护 C：模型"尾随总结"判据 ─────────────────────────────────────────
#: 硬标记：模型**谈论自己输出**的措辞。正文不可能这么写。
#: 每条都必须出现在**行首**（允许前导 markdown/项目符号），避免正文中间
#: 提到"以上幻灯片内容"时误切。
_TAIL_META_MARKERS: Tuple[str, ...] = (
    "核心文字内容",
    "幻灯片文字内容",
    "本页的文字内容",
    "本页幻灯片文字",
    "以上幻灯片内容",
    "以上是幻灯片",
    "以上为幻灯片",
    "以上是本张幻灯片",
    "以上为幻灯片全部",
    "以上是本页",
    "以上为本页",
    "以下为幻灯片内容",
)

#: 无表头变体：尾部连续 ``- 键：值`` 摘要 bullet。
#: 键位表含 ``要点``/``主要内容``/``内容摘要``/``核心内容`` 这类**只在模型
#: 自己写的摘要里出现**的词；标题页的 ``- 作者：/- 单位：`` 不含这些。
#: 键名后允许 ≤12 字（``地点与时间：`` / ``页眉 LOGO：``）。
_SCHEMA_KEY = (
    "标题|作者|单位|机构|会议|地点|时间|日期|页眉|页脚|"
    "要点|主要内容|内容摘要|核心内容|内容概述|主题|图表说明|关键词"
)
_SCHEMA_BULLET_RE = re.compile(
    rf"^\s*(?:[-*·•]|\d+[.)])\s*(?:{_SCHEMA_KEY})[^:：\n]{{0,12}}[:：]"
)

#: 长度归一：英文词表按 lowercase 比，中文按原样。
_WS_RE = re.compile(r"\s+")


def _norm_en(line: str) -> str:
    """英文比对用的归一：去首尾空白 + 压空白 + 小写。"""
    return _WS_RE.sub(" ", line).strip().lower()


# ── 结果类型 ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class RemovedLine:
    """被剔除的一行及其判定依据（可审计）。"""

    line_no: int          #: 在**原始文本**中的行号（0-based）
    text: str
    text: str             #: 该行 strip 后的原文
    #: ``'strong'`` | ``'weak_in_run'`` | ``'watermark'`` | ``'chart_ladder'``
    category: str
    rule: str             #: 具体命中的词表/正则名
    run_length: int = 0   #: 若靠 run 规则命中，该 run 的长度


@dataclass(frozen=True)
class FilterResult:
    """:func:`filter_page_transcript` 的返回值。

    调用方约定::

        r = filter_page_transcript(text)
        if r.should_auto_ingest:
            store(r.text)          # 净化后入库
        else:
            queue_for_human_review(r)   # **不要**自动入库, 也不必丢弃
    """

    raw_text: str
    #: 净化后的文本（剔除 chrome 行 + 刻度梯 + 切掉尾随总结）。blocked 时调用方
    #: 应走人工确认, 但这里仍给出净化版便于人工比对。
    text: str
    #: True = **建议**转人工确认。⚠️ 这不是"自动丢弃"，也不保证这页一定有问题。
    blocked: bool
    #: 触发 block 的理由（可多条）。
    block_reasons: Tuple[str, ...]
    #: chrome 字符 / 非空字符（不含空行与行内空白）。
    chrome_ratio: float
    chrome_chars: int
    total_chars: int
    #: 被剔除的行。
    removed_lines: Tuple[RemovedLine, ...]
    removed_chars: int
    #: 被切掉的尾随总结段（原文，可回滚/审计）。
    truncated_tail: str = ""
    #: 触发切除的标记文本（None = 没切）。
    truncation_marker: Optional[str] = None
    #: Windows 未激活水印（单独处置，不单独触发 block）。
    watermark_lines: Tuple[str, ...] = ()
    #: 防护 D：命中的出版社版面族名（仅在 :attr:`third_party_paper` 为 True 时非空）。
    paper_families: Tuple[str, ...] = ()
    #: 防护 D：本页「外文正文」字符数（>= 40 字符且中文占比 < 5% 的行合计）。
    paper_foreign_chars: int = 0
    #: 防护 D：整页是第三方论文 / 期刊网页截图。
    #: ⚠️ 这类页**只标不删** —— 见模块 docstring 防护 D 段。
    third_party_paper: bool = False
    #: 防护 F：整页是目录页 / 章节分隔页 / 致谢页。⚠️ 同样**只标不删**。
    template_page: bool = False
    #: 防护 F：模板页类型（``'toc'`` / ``'thanks'`` / ``''``）。
    template_kind: str = ""
    #: 防护 G：被当作坐标轴刻度梯剔除的字符数。
    chart_ladder_chars: int = 0

    @property
    def should_auto_ingest(self) -> bool:
        """:attr:`blocked` 的反面。**调用方唯一该判断的入口。**"""
        return not self.blocked


# ── 单行分类 ────────────────────────────────────────────────────────────

#: 行分类结果：(category, rule)。category ∈ {'strong', 'weak', None}
def _classify_core(line: str) -> Tuple[Optional[str], Optional[str]]:
    """不含 tab-bar 合取规则的单行判定（:func:`classify_line` 的内层）。"""
    s = _WS_RE.sub(" ", line).strip()
    if not s:
        return None, None

    # ── Windows 未激活水印（独立类别, 最高优先）──────────────────────
    # fullmatch: 真水印独立成行, 句中提到"激活 Windows"不是水印
    if _WATERMARK_RE.fullmatch(s):
        return "strong", "windows_watermark"

    # ── STRONG: 固定短语（多词搭配, substring 安全）───────────────────
    low = s.lower()
    for p in CHROME_PHRASES:
        if p.lower() in low:
            return "strong", f"phrase:{p}"

    # ── STRONG: 结构化正则 ────────────────────────────────────────────
    # ── STRONG: 科学软件 GUI 的结构化正则 ──────────────────────────
    # ⚠️ ``sci_gui_userdir`` 用 **search** 而非 match —— 实测行首可能是
    # ``Read from C:/Users/...`` 这类带引导词的写法；本机用户目录路径本身
    # 就是判据，是否在行首无关。其余几条都要求整行形状，用 match。
    if _SCI_GUI_USERDIR_RE.search(s):
        return "strong", "sci_gui_userdir"

    for name, rx, cat in (
        ("step", _STEP_RE, "strong"),
        ("menu_bar", _MENU_BAR_RE, "strong"),
        ("nav_btn", _NAV_BTN_RE, "strong"),
        ("filename", _FILENAME_RE, "strong"),
        ("measure", _MEASURE_RE, "strong"),
        ("radio", _RADIO_RE, "weak"),
        ("matlab_gui", _MATLAB_GUI_RE, "strong"),
        ("sci_gui_field", _SCI_GUI_FIELD_RE, "strong"),
    ):
        if rx.match(s):
            return cat, name

    # ── STRONG: 整行精确匹配 ──────────────────────────────────────────
    if s in CHROME_STRONG_CN:
        return "strong", "cn_exact"
    if low in CHROME_STRONG_EN:
        return "strong", "en_exact"

    # ── STRONG: 科学软件 GUI（防护 E，agent42）────────────────────────
    # 放在 Office 档之后：``home`` / ``start`` 这类通用词归 Office，
    # 科学软件的专有控件名（``simulation cell`` / ``number of atoms``）
    # 放在它后面判，避免两个词表互相污染判定依据。
    if s in SCI_GUI_STRONG_CN:
        return "strong", "sci_gui_cn"
    if low in SCI_GUI_STRONG_EN:
        return "strong", "sci_gui_en"

    # ── WEAK: 普通词 ──────────────────────────────────────────────────
    if s in CHROME_WEAK_CN or low in CHROME_WEAK_EN:
        return "weak", "word"

    return None, None


def _is_tab_bar(s: str) -> bool:
    """多栏对齐行（选项卡栏 / GUI 控件行）—— 2+ 空格分栏 + >=2 段自身命中 chrome。

    ⚠️ 入参必须是**只做了 strip、没做空白归一**的原始行 ——
    归一会把 2+ 空格压成 1 个，这条规则就永远不触发（首版实测踩过）。
    """
    parts = [p.strip() for p in _TAB_SPLIT_RE.split(s) if p.strip()]
    if len(parts) < _MIN_TAB_PARTS:
        return False
    return sum(1 for p in parts if _classify_core(p)[0] is not None) >= _MIN_TAB_CHROME_PARTS


def classify_line(line: str) -> Tuple[Optional[str], Optional[str]]:
    """判定单行是否 chrome, 以及是 STRONG 还是 WEAK。

    STRONG = UI 术语/结构特征, 单独成行也成立。
    WEAK   = 普通词, 只有落进 :data:`MIN_CHROME_RUN` 长度的连续串才成立。

    **不做单词级 substring 匹配** —— 那是误伤「讲 PPT 制作」教学内容的根源。
    """
    if not line.strip():
        return None, None
    core = _classify_core(line)
    if core[0] is not None:
        return core
    if _is_tab_bar(line.strip()):
        return "strong", "tab_bar"
    return None, None


# ── 公开判据 ────────────────────────────────────────────────────────────

def chrome_ratio(
    text: str, *, min_run: int = MIN_CHROME_RUN,
    min_all_weak: int = MIN_ALL_WEAK_RUN,
) -> float:
    """页面 chrome 字符占比 —— 防护 A 的唯一判据。

    分母 = 所有非空行 strip 后的字符数（与 agent37 实测口径一致，便于对拍）。
    分子 = 判定为 chrome 的行字符数。

    实测（agent40, 349 页真实转写）：1537p35 = 32.2%、1254p10 = 30.1%，
    其余 347 页最高 1.6%、中位数 0.0%。阈值 :data:`CHROME_BLOCK_RATIO` = 15%
    留有 20 倍余量。
    """
    removable, _ = _scan(text, min_run=min_run, min_all_weak=min_all_weak)
    if not removable:
        return 0.0
    total = sum(len(_WS_RE.sub(" ", ln).strip()) for ln in text.splitlines() if ln.strip())
    if total <= 0:
        return 0.0
    return sum(len(t) for _, t in removable) / total


def find_trailing_summary(text: str) -> Tuple[Optional[int], Optional[str]]:
    """检出模型违反"不要总结"指令追加的尾段，返回 ``(起始行号, 标记)``。

    两级判据，都要求证据足够强 —— **漏检无害，误切毁真内容**：

    1. **硬标记**：``核心文字内容（幻灯片正文）：`` / ``以上幻灯片内容…`` 这类
       **模型谈论自己输出**的措辞，出现在行首即命中。
    2. **schema 尾块**：尾部连续 >= :data:`MIN_SCHEMA_TAIL_RUN` 条
       ``- 标题：… / - 作者：…`` 摘要 bullet，且其上方还有
       :data:`MIN_LINES_ABOVE_SCHEMA_TAIL` 行真内容（防止整页切空）。

    ⚠️ 刻意**不用** ``总结`` / ``综上所述`` / ``要点如下`` 作标记 ——
    科研 slide 的真·总结页就长那样，拿它当标记会把真总结页切光。
    """
    lines = text.splitlines()
    n = len(lines)

    # ── 1. 硬标记（行首, 允许前导 markdown / 项目符号）────────────────
    for i, ln in enumerate(lines):
        s = ln.lstrip(" \t#>*-·•").strip()
        for m in _TAIL_META_MARKERS:
            if s.startswith(m):
                return i, s

    # ── 2. schema 尾块 ────────────────────────────────────────────────
    j = n
    while j > 0 and _SCHEMA_BULLET_RE.match(lines[j - 1]):
        j -= 1
    run = n - j
    if run >= MIN_SCHEMA_TAIL_RUN:
        above = sum(1 for k in range(j) if lines[k].strip())
        if above >= MIN_LINES_ABOVE_SCHEMA_TAIL:
            return j, lines[j].strip()
    return None, None


# ── 防护 D / F / G 的公开判据 ──────────────────────────────────────────

def paper_families(text: str) -> Tuple[str, ...]:
    """返回本页命中的出版社版面族名（去重、保序）。

    「族」而不是「条目数」的理由见 :data:`PAPER_FAMILIES` 的注释：
    6 个族互不重叠，整页论文截图会同时命中 3~5 个，
    而本组合法引用最多碰 2~3 个 —— 族数才是有判别力的特征。
    """
    hits: List[str] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        for name, rxs in PAPER_FAMILY_RES:
            if any(rx.search(line) for rx in rxs):
                if name not in hits:
                    hits.append(name)
                break          # 一行只记第一个命中的族（族本身互斥但行可多命中）
    return tuple(hits)


def foreign_prose_stats(text: str) -> Tuple[int, int]:
    """返回 ``(外文字符数, 长外文行数)``。

    「外文正文行」= **原始长度 >= 40** 且 **中文字符占比 < 5%** 的非空行。
    两个条件缺一不可：
    * 长度门槛把 ``ELSEVIER`` / ``Nature Communications`` 这类刊头
      排除在外（它们是 chrome 不是正文）；
    * 中文占比门槛把「中文讲稿 + 英文术语混排」的科研页排除在外
      （如 1101p5 —— 它的外文只有 196 字符且最长行 105 字符）。
    """
    chars = 0
    long_lines = 0
    for line in text.splitlines():
        if not line.strip() or len(line) < PAPER_FOREIGN_MIN_LINE:
            continue
        if len(_CJK_RE.findall(line)) / max(1, len(line)) > PAPER_FOREIGN_MAX_CJK_RATIO:
            continue
        n = len(_WS_RE.sub(" ", line).strip())
        chars += n
        if len(line) >= PAPER_MIN_LONG_LINE:
            long_lines += 1
    return chars, long_lines


def detect_third_party_paper(text: str) -> Tuple[bool, Tuple[str, ...], int]:
    """防护 D —— 判定「整页是第三方论文 / 期刊网页截图」。

    返回 ``(是否命中, 命中的族, 外文字符数)``。

    **这是页级标���，不是删行动作。** 命中后调用方应转人工确认，
    :attr:`FilterResult.text` 仍保留原文（无法从纯文本区分「别人的论文正文」
    与「用户自己摘抄的论文段落」，删了就可能删掉真引用）。

    三条合取理由（实测 269 页，见模块 docstring 防护 D）：
    1. 族数 >= :data:`PAPER_MIN_FAMILIES` —— 单个信号（``Open access`` /
       ``Nature``）正文里也会有，合取才安全。
    2. 外文规模 >= :data:`PAPER_MIN_FOREIGN_CHARS` —— 排除「只贴了个
       citation 行」的合法引用页（1250p2 外文 294 但最长行仅 121）。
    3. 至少 :data:`PAPER_MIN_LONG_LINE` 字符的长外文行 —— 证明**真的有一段
       论文正文**，而不只是导航碎片。这是第二道保险。
    """
    fams = paper_families(text)
    foreign, long_lines = foreign_prose_stats(text)
    hit = (
        len(fams) >= PAPER_MIN_FAMILIES
        and foreign >= PAPER_MIN_FOREIGN_CHARS
        and long_lines >= 1
    )
    return hit, fams, foreign


def detect_template_page(text: str) -> Tuple[bool, str]:
    """防护 F —— 判定「目录页 / 致谢页」这类模板样板页。

    返回 ``(是否命中, 类型)``，类型 ∈ ``{'toc', 'thanks', ''}``。**只标不删。**

    目录页的判定是**结构 + 无长句**而非关键词：必须有 ``目录`` / ``/CONTENTS``
    页头，正文里 >= 2 条形如 ``1 研究背景`` 的章节条目，**其他行不超过 2 条**，
    且**没有任何一行超过 :data:`TEMPLATE_MAX_LINE_CHARS` 字符**。
    后两条约束都是防误伤的关键 —— 它们保证这页**没有真内容**：
    一个既叫「目录」又写了长段研究结论的页不该被整页判成模板。

    实测 269 页命中 13 页：目录 8（886p3 / 1112p3 / 1152p2 / 1198p3 /
    1220p2 / 1220p3 / 1220p12 / 1230p2）+ 致谢 5。
    真目录页最长 71 字符且无长行；带正文的伪模板页至少有一行 130+ 字符。
    """
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return False, ""
    page_chars = sum(len(_WS_RE.sub(" ", ln).strip()) for ln in lines)
    if page_chars > TEMPLATE_MAX_PAGE_CHARS:
        return False, ""
    # ⚠️ 单行闸：模板页没有长句。这一条比页长总闸更贴近「有没有真内容」的语义
    # ⚠️ 单行闸：模板页没有长句。这一条比页长总闸更贴近「有没有真内容」的语义
    if any(len(ln) > TEMPLATE_MAX_LINE_CHARS for ln in lines):
        return False, ""

    heads = [ln for ln in lines if _TOC_HEAD_RE.match(ln)]
    if heads:
        secs = [ln for ln in lines if _TOC_ITEM_RE.match(ln) and not _TOC_HEAD_RE.match(ln)]
        other = [ln for ln in lines if ln not in heads and ln not in secs]
        if len(secs) >= 2 and len(other) <= 2:
            return True, "toc"

    if any(_THANKS_RE.match(ln) for ln in lines):
        return True, "thanks"

    return False, ""


def find_chart_ladders(text: str) -> List[int]:
    """防护 G —— 找出坐标轴刻度梯的行号（用模块级默认阈值）。

    **判据是「连续 >= :data:`CHART_LADDER_MIN_RUN` 个严格单调的纯数字行」**。

    为什么必须靠单调性而不是「短行就剔」：
    agent40 实测过「纯数字 → chrome」，结果把 1066p17 / 1126p10 的**真刻度**
    整页删掉；反过来 agent42 首版「连续短标签行 → 全删」也误伤了
    1193p19 的**真实热力学数据**（能垒 ``-237.06``、``-159.56``）和
    1215p9 的**真实时间点**（``143 min`` / ``179 min``）。

    而**严格单调是坐标轴的结构不变量**：一根轴上的刻度必然单调，
    而 8 个连续严格单调的实验数据点在本组语料里不存在。
    实测 269 页：14 页命中，删 802 字符，**逐行人工核对零误伤**
    （每条被删行的上一行都是轴标题，如 ``Protein (mg/L)`` → ``45 44 43``）。

    另有两道保险：
    * 单页删除量不得超过 :data:`CHART_LADDER_MAX_PAGE_RATIO` ——
      超过说明这页整体就是一张图，删刻度等于删整页，该转人工而非净化。
    * 候选行必须 ``<= CHART_LADDER_MAX_LINE`` 字符且**不含中文** ——
      ``Removal Rate (%)`` 这类轴标题（含中文/长串）本身不删。
    """
    return _find_chart_ladders_param(text, CHART_LADDER_MIN_RUN, CHART_LADDER_MAX_PAGE_RATIO)


def _find_chart_ladders_param(
    text: str, min_run: int, max_page_ratio: float
) -> List[int]:
    """:func:`find_chart_ladders` 的参数化内核（供 ``filter_page_transcript``
    的覆盖参数走同一条代码路径，避免测试与生产走两套逻辑）。"""
    lines = text.splitlines()

    # 候选行号：短、无中文、非空。空行不作候选但**不切断连续性**
    # （模型爱在刻度中间插空行，与 chrome run 规则同理）。
    cand = [
        i for i, ln in enumerate(lines)
        if ln.strip()
        and len(ln.strip()) <= CHART_LADDER_MAX_LINE
        and not _CJK_RE.search(ln)
    ]
    if len(cand) < min_run:
        return []

    total_chars = sum(len(_WS_RE.sub(" ", ln).strip()) for ln in lines if ln.strip())
    removable: set = set()
    for start in range(len(cand) - min_run + 1):
        seg = cand[start:start + min_run]
        # ⚠️ 这里要判的是「**相邻两行之间**只有空行」，
        # 不能直接 `_contiguous(seg[0], seg[-1])` —— 那个函数问的是
        # 「seg[0] 与 seg[-1] **之间**的原始行是否全为空」，
        # 而 seg 本身**就是**那几行刻度（它们非空），必然判 False。
        if not all(_contiguous(lines, seg[i], seg[i + 1]) for i in range(len(seg) - 1)):
            continue
        nums = [_chart_num(lines[i]) for i in seg]
        if any(v is None for v in nums):
            continue
        if len(set(nums)) < 2:          # 排除全等（``0 0 0 0``）
            continue
        inc = all(b > a for a, b in zip(nums, nums[1:]))
        dec = all(b < a for a, b in zip(nums, nums[1:]))
        if inc or dec:
            removable.update(seg)

    if not removable:
        return []
    removed_chars = sum(
        len(_WS_RE.sub(" ", lines[i]).strip()) for i in removable
    )
    if total_chars and removed_chars / total_chars > max_page_ratio:
        return []
    return sorted(removable)


# ── 主入口 ──────────────────────────────────────────────────────────────

def filter_page_transcript(
    text: str,
    *,
    block_ratio: float = CHROME_BLOCK_RATIO,
    min_run: int = MIN_CHROME_RUN,
    min_all_weak: int = MIN_ALL_WEAK_RUN,
    watermark_floor: float = WATERMARK_RATIO_FLOOR,
    watermark_min_lines: int = WATERMARK_MIN_LINES,
    watermark_min_page_chars: int = WATERMARK_MIN_PAGE_CHARS,
    paper_min_families: int = PAPER_MIN_FAMILIES,
    paper_min_foreign: int = PAPER_MIN_FOREIGN_CHARS,
    ladder_min_run: int = CHART_LADDER_MIN_RUN,
    ladder_max_page_ratio: float = CHART_LADDER_MAX_PAGE_RATIO,
) -> FilterResult:
    """净化一页视觉转写 —— 纯函数, 零 IO。

    做五件事, 各自独立可审计:

    1. **剔除 chrome 行**（功能区 / GUI 控件 / 任务栏 / 未激活水印 /
       科学计算软件面板 —— 防护 A/B/E）
    2. **剔除坐标轴刻度梯**（连续单调纯数字行 —— 防护 G）
    3. **切掉尾随总结段**（模型违反"不要总结"指令的追加内容 —— 防护 C）
    4. **标记整页第三方论文 / 期刊网页截图**（防护 D，**只标不删**）
    5. **标记目录页 / 致谢页模板样板**（防护 F，**只标不删**）

    ``blocked=True`` 时 :attr:`FilterResult.should_auto_ingest` 为 False，
    调用方**不得**自动入库 —— 但也**不必**丢弃，转人工队列即可。
    典型场景就是拍到别人笔记本电脑屏幕的那一页，
    以及整页就是一篇别人的论文（检索池不该被别人的摘要污染）。
    """
    if text is None:
        text = ""
    if not isinstance(text, str):
        raise TypeError(f"text must be str, got {type(text).__name__}")

    # ── 1. chrome 行扫描 ─────────────────────────────────────────────
    removable, removed = _scan(text, min_run=min_run, min_all_weak=min_all_weak)
    chrome_chars = sum(len(t) for _, t in removable)
    total_chars = sum(len(_WS_RE.sub(" ", ln).strip()) for ln in text.splitlines() if ln.strip())
    ratio = chrome_chars / total_chars if total_chars else 0.0

    watermarks = tuple(
        _WS_RE.sub(" ", ln).strip()
        for ln in text.splitlines()
        if _WATERMARK_RE.fullmatch(_WS_RE.sub(" ", ln).strip())
    )

    # ── 1b. 坐标轴刻度梯（防护 G）────────────────────────────────────
    raw_lines = text.splitlines()
    ladder_idx = (
        find_chart_ladders(text)
        if ladder_min_run == CHART_LADDER_MIN_RUN and ladder_max_page_ratio == CHART_LADDER_MAX_PAGE_RATIO
        else _find_chart_ladders_param(text, ladder_min_run, ladder_max_page_ratio)
    )
    ladder_removed: List[RemovedLine] = [
        RemovedLine(i, _WS_RE.sub(" ", raw_lines[i]).strip(), "chart_ladder",
                    "monotone_numeric_run", ladder_min_run)
        for i in ladder_idx
    ]
    ladder_chars = sum(len(rl.text) for rl in ladder_removed)

    # ── 2. 尾随总结切除 ──────────────────────────────────────────────
    tail_idx, marker = find_trailing_summary(text)
    drop = {rl.line_no for rl in removed} | set(ladder_idx)
    tail = ""
    if tail_idx is not None:
        drop |= set(range(tail_idx, len(raw_lines)))
        tail = "\n".join(raw_lines[tail_idx:]).strip()
    filtered = "\n".join(ln for i, ln in enumerate(raw_lines) if i not in drop).strip()

    # ── 3. 页级判定（防护 D / F）—— 只标不删 ─────────────────────────
    paper_hit, fams, foreign = detect_third_party_paper(text)
    if paper_min_families != PAPER_MIN_FAMILIES or paper_min_foreign != PAPER_MIN_FOREIGN_CHARS:
        # 覆盖参数时重算（族判定只依赖 text，规模判定才依赖阈值）
        paper_hit = (
            len(fams) >= paper_min_families and foreign >= paper_min_foreign
            and foreign_prose_stats(text)[1] >= 1
        )
    template_hit, template_kind = detect_template_page(text)

    # ── 4. 拦截判定 ────────────────────────────────────────────────
    # 保守: **只**用"这一页有多少是软件 chrome"这一类**页面级结构证据**,
    # 不掺任何"含外部机构名/含外部人名"的内容侧判据 —— 实测该组 deck 本身
    # 就在未来颗粒前沿研讨会语境里, 合法引用清华/中科院分区会造成高假阳。
    reasons: List[str] = []
    if total_chars >= 40 and ratio >= block_ratio:
        reasons.append(
            f"chrome_ratio={ratio:.1%} >= {block_ratio:.0%}"
            f"（疑为拍摄他人电脑屏幕, 转人工确认）"
        )
    if (
        watermarks
        and total_chars >= watermark_min_page_chars
        and (len(watermarks) >= watermark_min_lines
             or chrome_chars / total_chars >= watermark_floor)
    ):
        reasons.append(
            f"windows_unactivated_watermark x{len(watermarks)}"
            f"（疑为桌面截屏, 转人工确认）"
        )
    # 防护 D —— 内容污染（不是 chrome）。⚠️ 不删任何一行。
    if paper_hit:
        reasons.append(
            f"third_party_paper_page（出版社版面族 x{len(fams)}: "
            f"{'/'.join(fams)}; 外文正文 {foreign} 字符, 疑似整页他人论文"
            f"/期刊网页截图, 内容污染, 转人工确认; 内容未删）"
        )
    # 防护 F —— 模板样板页。
    if template_hit:
        label = "目录页" if template_kind == "toc" else "致谢/尾页"
        reasons.append(
            f"template_page:{template_kind}（{label}, 无科研内容, 转人工确认; 内容未删）"
        )

    removed_chars = chrome_chars + ladder_chars + sum(
        len(_WS_RE.sub(" ", ln).strip()) for ln in tail.splitlines() if ln.strip()
    )

    return FilterResult(
        raw_text=text,
        text=filtered,
        blocked=bool(reasons),
        block_reasons=tuple(reasons),
        chrome_ratio=ratio,
        chrome_chars=chrome_chars,
        total_chars=total_chars,
        removed_lines=tuple(removed) + tuple(ladder_removed),
        removed_chars=removed_chars,
        truncated_tail=tail,
        truncation_marker=marker,
        watermark_lines=watermarks,
        paper_families=fams if paper_hit else (),
        paper_foreign_chars=foreign if paper_hit else 0,
        third_party_paper=paper_hit,
        template_page=template_hit,
        template_kind=template_kind if template_hit else "",
        chart_ladder_chars=ladder_chars,
    )


# ── 内部实现 ────────────────────────────────────────────────────────────

def _scan(text: str, *, min_run: int, min_all_weak: int) -> Tuple[List[Tuple[int, str]], List[RemovedLine]]:
    """扫出所有可剔除行。

    返回 ``([(原始行号, strip 后文本)], [RemovedLine, ...])``。

    核心是 **run 规则**：先把每个非空行分成 STRONG / WEAK，
    再按「连续候选行」切 run（**空行不切断 run** —— 模型爱在功能区中间插空行）。
    STRONG 行单独就成立；WEAK 行必须落在足够长的 run 里，且门槛分两档：
    run 内只要有 1 个 STRONG 项就要 ``min_run`` 行；整串全是 WEAK 普通词则要
    ``min_all_weak`` 行（详见 :data:`MIN_ALL_WEAK_RUN` 的误伤实证）。
    """
    raw_lines = text.splitlines()
    cand: List[Tuple[int, str, str, str]] = []   # (行号, 文本, category, rule)

    for i, ln in enumerate(raw_lines):
        s = _WS_RE.sub(" ", ln).strip()
        if not s:
            continue
        category, rule = classify_line(ln)
        if category:
            cand.append((i, s, category, rule))

    removable: List[Tuple[int, str]] = []
    removed: List[RemovedLine] = []

    # 切 run（空行不切断：只按 cand 列表的相邻性）
    start = 0
    while start < len(cand):
        end = start
        # run 内允许 STRONG/WEAK 混排; 非候选行（正文）已在 cand 里被跳过,
        # 所以这里必须用原始行号判断"是否真的相邻"
        while end + 1 < len(cand) and _contiguous(raw_lines, cand[end][0], cand[end + 1][0]):
            end += 1
        seg = cand[start:end + 1]
        seg_len = len(seg)
        has_strong = any(c == "strong" for _, _, c, _ in seg)
        need = min_run if has_strong else max(min_run, min_all_weak)
        for line_no, s, category, rule in seg:
            if category == "strong":
                removable.append((line_no, s))
                removed.append(RemovedLine(line_no, s, "strong", rule, seg_len))
            elif seg_len >= need:
                removable.append((line_no, s))
                removed.append(RemovedLine(line_no, s, "weak_in_run", rule, seg_len))
        start = end + 1

    return removable, removed


def _contiguous(raw_lines: Sequence[str], a: int, b: int) -> bool:
    """两个候选行号之间是否只有空行（空行不切断 run）。"""
    if b <= a + 1:
        return True
    return all(not raw_lines[k].strip() for k in range(a + 1, b))


__all__ = [
    "CHROME_BLOCK_RATIO",
    "MIN_CHROME_RUN",
    "MIN_ALL_WEAK_RUN",
    "MIN_SCHEMA_TAIL_RUN",
    "WATERMARK_RATIO_FLOOR",
    "WATERMARK_MIN_LINES",
    "WATERMARK_MIN_PAGE_CHARS",
    "PAPER_MIN_FAMILIES",
    "PAPER_MIN_FOREIGN_CHARS",
    "PAPER_MIN_LONG_LINE",
    "CHART_LADDER_MIN_RUN",
    "CHART_LADDER_MAX_LINE",
    "CHART_LADDER_MAX_PAGE_RATIO",
    "SCI_GUI_STRONG_EN",
    "SCI_GUI_STRONG_CN",
    "FilterResult",
    "RemovedLine",
    "classify_line",
    "chrome_ratio",
    "detect_template_page",
    "detect_third_party_paper",
    "find_chart_ladders",
    "find_trailing_summary",
    "foreign_prose_stats",
    "paper_families",
    "filter_page_transcript",
]