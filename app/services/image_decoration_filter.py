"""模板装饰图（母版页眉/校徽/水印）识别 — 纯几何判据，供 OCR 前拦截用。

## 背景（2026-10-09 agent22 取证）

用第三方模板做的 PPT/报告，母版（slide master）里嵌了一张装饰横幅
（校徽 + 校名 + 校门照），在**每一页**重复出现。这张图本该被当版式丢掉，
却被当成正常内容图送去做 OCR + 视觉摘要，产生幻觉噪声：

- doc 2822《油田采出水处理工艺全景解析》（19 页）的母版横幅 1055×203 在
  第 1/2/3/7/17 页重复 5 次，实际内容是「清華大學 二校門」，视觉模型在 4 条
  记录上给出 3 个互不相同的说法（"台湾大学校门" / "台湾清华大学成功湖畔的
  纪念亭" / "疑似清华大学校门…可见'地质地震'字样"）。
- 全库 5446 张图里，`logo`/`publisher`/`cover` 三类装饰占 3164 张（58%）。

## 判据：两个信号取**交集**才判装饰

1. **极端宽高比** `width / height >= 5.0`（横幅条）
2. **同文档内尺寸完全相同的图出现在 >= 3 个不同页**（母版资产被复用）
3. 保险丝：`height <= 300`（横幅必须薄）—— 当前全库命中集最大高度 203px，
   这条永不收紧结果，只为未来数据兜底。

### 为什么不用 `figure_type`

`figure_type` 是 **LLM 输出**（`extract_figure_structured` 返回的 `figureType`
字段，见 `multimodal_extraction_service._apply_v28_structured_fields`），
不是真值。实测它在同一批装饰图上自相矛盾：

- doc 2822 里**同一张** 1055×203 横幅被分别标成 `cover` / `publisher` / `logo`
- 871×45 的校名条被标成 `figure` 且 `is_core_figure = t`
- 640×427 的校园建筑照（实为横幅里的裁切图）被标成 `experimental_setup`

拿它当判据等于让幻觉噪声决定自己的去留。

### 为什么"重复几何"不能单独用

doc 2384 / 2419 的**真实图表**在同文档内多页复用同一尺寸
（1979×1180 浊度折线图、1862×1320 叶绿素柱状图，AR≈1.4–1.7）。
单看重复会直接误伤真图 —— 这正是本任务最大的风险。
全库 AR ∈ [4.0, 5.0) 且重复的图**为 0 条**，说明 5.0 这条线正好落在
装饰（AR≥5.1）与真实宽图（AR≤2.2）之间的空档里。

### 判据取舍原则

宁可漏过滤，不可误伤。AR≈1.5 的校园建筑裁切图**不会**被这套判据拦下
（AR 不够极端），但它是"母版裁切图"而非独立内容，留着只是几条噪声，
远好过误杀真实实验装置图 / 图表 / 示意图。
"""

from __future__ import annotations

from typing import Dict, Iterable, Set, Tuple

# ── 判据阈值 ────────────────────────────────────────────────────────────
# AR ∈ [4.0, 5.0) 且重复的图全库为 0 条 → 5.0 落在装饰与真宽图之间的空档
MIN_ASPECT_RATIO = 5.0
# 母版资产至少要在 3 个不同页出现才算"复用"（单页出现的横幅无此特征）
MIN_REPEATED_PAGES = 3
# 保险丝：真正的横幅条都很薄。当前全库命中集最大高度 203px
MAX_BANNER_HEIGHT_PX = 300


def is_banner_shape(
    width: int | None,
    height: int | None,
    min_aspect_ratio: float = MIN_ASPECT_RATIO,
    max_height_px: int = MAX_BANNER_HEIGHT_PX,
) -> bool:
    """单张图是否具备"横幅条"的几何形状。

    缺尺寸（None / 0 / 负数）一律返回 False —— 判不出来时**不拦**，
    宁可让噪声漏过去，也不能误伤正常内容图。
    """
    if not width or not height:
        return False
    if width <= 0 or height <= 0:
        return False
    if height > max_height_px:
        return False
    return (width / height) >= min_aspect_ratio


def count_repeated_pages(
    images: Iterable,
    min_aspect_ratio: float = MIN_ASPECT_RATIO,
    max_height_px: int = MAX_BANNER_HEIGHT_PX,
) -> Dict[Tuple[int, int], int]:
    """统计每个"横幅尺寸组合"出现在多少个**不同页**上。

    ``images`` 只需具备 ``.width`` / ``.height`` / ``.page_number`` 属性
    （``KnowledgeImage`` ORM 对象或任何同形替身均可）。

    注意按 **distinct page_number** 计数而非图片条数：同一页里塞两张
    相同尺寸的图不算复用。``page_number`` 为 None 的（PDF 抽取常见）
    统一归到哨兵值 0，仍按同一页计，不会虚增。
    """
    pages_by_size: Dict[Tuple[int, int], Set] = {}
    for img in images:
        width = getattr(img, "width", None)
        height = getattr(img, "height", None)
        if not is_banner_shape(width, height, min_aspect_ratio, max_height_px):
            continue
        page = getattr(img, "page_number", None)
        pages_by_size.setdefault((width, height), set()).add(page if page is not None else 0)
    return {size: len(pages) for size, pages in pages_by_size.items()}


def find_banner_image_ids(
    images: Iterable,
    min_repeated_pages: int = MIN_REPEATED_PAGES,
    min_aspect_ratio: float = MIN_ASPECT_RATIO,
    max_height_px: int = MAX_BANNER_HEIGHT_PX,
) -> Set[int]:
    """返回同文档内"跨多页复用的横幅条"图片 id 集合（空集 = 全部保留）。

    两个信号取交集：既是极端宽高比，又在多页复用。任一信号单独使用都会
    误伤真实图表，详见模块 docstring。
    """
    images = list(images)
    repeated = count_repeated_pages(images, min_aspect_ratio, max_height_px)

    banner_ids: Set[int] = set()
    for img in images:
        width = getattr(img, "width", None)
        height = getattr(img, "height", None)
        if not is_banner_shape(width, height, min_aspect_ratio, max_height_px):
            continue
        if repeated.get((width, height), 0) >= min_repeated_pages:
            image_id = getattr(img, "id", None)
            if image_id is not None:
                banner_ids.add(image_id)
    return banner_ids


__all__ = [
    "MIN_ASPECT_RATIO",
    "MIN_REPEATED_PAGES",
    "MAX_BANNER_HEIGHT_PX",
    "is_banner_shape",
    "count_repeated_pages",
    "find_banner_image_ids",
]
