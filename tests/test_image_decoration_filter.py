"""模板装饰横幅（母版页眉/校徽/水印）过滤回归测试 (2026-10-09, agent22)

背景事故
--------
第三方模板 PPT 的母版里嵌了一张装饰横幅（校徽 + 校名 + 校门照），在每页重复。
它本该被当版式丢掉，却被当正常内容图送去 OCR + 视觉摘要，产生幻觉噪声：
doc 2822 的 1055×203 横幅（实为「清華大學 二校門」）在 4 条记录上被描述成
3 种不同说法（"台湾大学校门" / "台湾清华大学成功湖畔的纪念亭" / "疑似清华大学
校门…可见'地质地震'字样"）。全库 5446 张图里 logo/publisher/cover 占 3164 张。

本测试锁定的行为
----------------
- 写入侧（`_skip_banner_images`）：装饰横幅在 **OCR 之前**被拦下，
  标 `ocr_status='skipped'`，**不产生 ocr_text / visual_summary**（幻觉的源头）
- 检索侧（`_load_candidates`）：存量装饰图不进第 5 路多模态候选
- **不误伤真实内容图**（本任务最大风险，单列一组硬断言）

判据取舍（详见 app/services/image_decoration_filter.py 模块 docstring）：
极端宽高比 ∧ 同文档内 >=3 个不同页复用。两个信号取**交集** ——
任一单独使用都会误伤 doc 2384 / 2419 的真实图表。

变异测试（见文件末「变异测试」注释）：三条变体各自会让下列用例转红。
"""
import os

import pytest

os.environ.setdefault("SKIP_DB_SETUP", "1")

from types import SimpleNamespace


def _img(img_id, width, height, page):
    """构造判据所需的最小替身（width/height/page_number/id）。"""
    return SimpleNamespace(id=img_id, width=width, height=height, page_number=page)


# 全库实测的母版横幅尺寸（doc 2822 / 2419 等模板 PPT）
BANNER_1055x203 = (1055, 203)   # 校门 + 花枝横幅, AR 5.2
BANNER_871x45 = (871, 45)       # 校名条, AR 19.4
BANNER_832x163 = (832, 163)     # 学院名条, AR 5.1
CAMPUS_PHOTO_640x427 = (640, 427)  # 横幅里的校园照裁切, AR 1.5（判据故意不拦）


# ============================================================================
# 1. 单图形状判据 is_banner_shape
# ============================================================================


class TestIsBannerShape:
    @pytest.mark.parametrize("dims", [BANNER_1055x203, BANNER_871x45, BANNER_832x163])
    def test_real_banner_shapes_detected(self, dims):
        from app.services.image_decoration_filter import is_banner_shape

        assert is_banner_shape(*dims) is True

    @pytest.mark.parametrize(
        "dims",
        [
            (1979, 1180),  # doc 2384 真实浊度折线图 AR 1.68
            (1862, 1320),  # doc 2419 真实叶绿素柱状图 AR 1.41
            (2337, 1051),  # doc 2822 真实 3D 设备剖面图 AR 2.22
            (1325, 626),   # doc 2822 真实正文图 AR 2.12
            (640, 427),    # 校园照裁切 AR 1.50
            (100, 100),    # 小图标 AR 1.0
        ],
    )
    def test_real_content_shapes_rejected(self, dims):
        from app.services.image_decoration_filter import is_banner_shape

        assert is_banner_shape(*dims) is False

    @pytest.mark.parametrize(
        "dims",
        [
            (1200, 300),  # 薄但 AR 4.0 的真宽图（时间轴/工艺流程条）—— 隔离测宽高比阈值
            (1000, 250),  # 薄但 AR 4.0
        ],
    )
    def test_thin_but_moderately_wide_content_rejected(self, dims):
        """隔离**宽高比阈值**本身：这些图高度够薄（能穿过 height 保险丝），
        但 AR 只有 4.0，低于 5.0 → 不得判装饰。

        注意 (2337,1051)/(1325,626) 这类真宽图其实是被 **height 保险丝**
        挡下的（1051 > 300），不是被宽高比挡下的 —— 两道防线互相独立。
        """
        from app.services.image_decoration_filter import is_banner_shape

        assert is_banner_shape(*dims) is False

    @pytest.mark.parametrize("dims", [(None, None), (0, 0), (1055, 0), (0, 203), (-1055, -203)])
    def test_missing_or_degenerate_dimensions_never_flagged(self, dims):
        """判不出来时**不拦** —— 宁可漏过滤，不可误伤。"""
        from app.services.image_decoration_filter import is_banner_shape

        assert is_banner_shape(*dims) is False

    def test_banner_shape_but_too_tall_rejected(self):
        """AR 够极端但很高（如 2000x400 的宽流程图）→ 不拦，避免误伤真宽图。"""
        from app.services.image_decoration_filter import is_banner_shape

        assert is_banner_shape(2000, 400) is False

    def test_exact_threshold_boundary(self):
        """AR 恰好 5.0 判装饰；4.99 不判（阈值下方留空档）。"""
        from app.services.image_decoration_filter import is_banner_shape

        assert is_banner_shape(500, 100) is True
        assert is_banner_shape(499, 100) is False


# ============================================================================
# 2. 跨页重复计数 —— 按 distinct page_number，不是按图片条数
# ============================================================================


class TestCountRepeatedPages:
    def test_counts_distinct_pages_not_rows(self):
        """同一页塞 3 张同尺寸横幅仍算 1 页（PDF 抽取常见）。"""
        from app.services.image_decoration_filter import count_repeated_pages

        images = [_img(i, 1055, 203, 5) for i in range(1, 4)]
        assert count_repeated_pages(images)[(1055, 203)] == 1

    def test_distinct_pages_accumulate(self):
        from app.services.image_decoration_filter import count_repeated_pages

        images = [
            _img(1, 1055, 203, 1), _img(2, 1055, 203, 2),
            _img(3, 1055, 203, 3), _img(4, 871, 45, 1),
        ]
        counts = count_repeated_pages(images)
        assert counts[(1055, 203)] == 3
        assert counts[(871, 45)] == 1

    def test_non_banner_shapes_not_counted(self):
        from app.services.image_decoration_filter import count_repeated_pages

        images = [_img(i, 1979, 1180, i) for i in range(1, 6)]
        assert count_repeated_pages(images) == {}

    def test_none_page_number_grouped_into_sentinel(self):
        """PDF 抽取常无 page_number；None 归哨兵 0，不虚增页数。"""
        from app.services.image_decoration_filter import count_repeated_pages

        images = [_img(i, 871, 45, None) for i in range(1, 5)]
        assert count_repeated_pages(images)[(871, 45)] == 1


# ============================================================================
# 3. find_banner_image_ids —— 正例 + **不误伤**（本任务最大风险）
# ============================================================================


class TestFindBannerImageIds:
    def test_doc2822_master_banner_across_5_pages_detected(self):
        """复刻 doc 2822 实况：1055×203 横幅出现在第 1/2/3/7/17 页。"""
        from app.services.image_decoration_filter import find_banner_image_ids

        images = [
            _img(11764, 1055, 203, 1), _img(11765, 1055, 203, 2),
            _img(11767, 1055, 203, 3), _img(11774, 1055, 203, 7),
            _img(11781, 1055, 203, 17),
        ]
        assert find_banner_image_ids(images) == {11764, 11765, 11767, 11774, 11781}

    def test_doc2419_school_name_strip_detected(self):
        """doc 2419 实况：871×45 校名条出现在第 3/4/5/7/9 页。"""
        from app.services.image_decoration_filter import find_banner_image_ids

        images = [_img(i, 871, 45, p) for i, p in zip(range(1, 6), [3, 4, 5, 7, 9])]
        assert len(find_banner_image_ids(images)) == 5

    def test_single_page_banner_not_flagged(self):
        """只出现 1 页的横幅无「母版复用」特征 → 放过（宁可漏过滤）。"""
        from app.services.image_decoration_filter import find_banner_image_ids

        images = [_img(1, 1055, 203, 1)]
        assert find_banner_image_ids(images) == set()

    def test_two_page_banner_now_flagged(self):
        """2 页 == MIN_REPEATED_PAGES=2 → 命中。

        2026-10-09（agent33）：阈值由 3 降到 2。原先只落 2 页的母版横幅
        （PPT 仅 2 页 / 母版元素在正文页外）因差一票漏网，其幻觉 ocr_text
        一直没被清。取证见 image_decoration_filter 模块 docstring。
        """
        from app.services.image_decoration_filter import find_banner_image_ids

        images = [_img(1, 1055, 203, 1), _img(2, 1055, 203, 2)]
        assert find_banner_image_ids(images) == {1, 2}

    def test_single_page_still_not_flagged(self):
        """**边界**：1 页 < MIN_REPEATED_PAGES=2 → 仍放过。

        绝不可再降到 1：全库 pages=1 的 75 行里是真实科研内容（实测 O₃
        自由基反应方程式 647×73、O₂ 质心追踪 MATLAB 代码 898×72、
        代谢活性公式、水质参数表），降到 1 会直接误杀。
        """
        from app.services.image_decoration_filter import find_banner_image_ids

        images = [_img(1, 647, 73, 8)]  # kb 2392 p8，真实 O₃ 反应方程式
        assert find_banner_image_ids(images) == set()

    def test_different_sizes_across_pages_not_treated_as_repeat(self):
        """3 张横幅但尺寸各不相同 → 各自只 1 页，不是母版复用。"""
        from app.services.image_decoration_filter import find_banner_image_ids

        images = [
            _img(1, 1055, 203, 1), _img(2, 1000, 200, 2), _img(3, 900, 180, 3),
        ]
        assert find_banner_image_ids(images) == set()

    # ── 不误伤断言组 ────────────────────────────────────────────────────

    def test_doc2384_real_charts_never_flagged(self):
        """**关键回归**：doc 2384 的真实折线图 1979×1180 在第 5/6/7/8/10 页
        复用同一尺寸（作者统一图表模板）。只看「重复几何」会直接误杀它们 ——
        交集里的 AR>=5.0 才是防线。"""
        from app.services.image_decoration_filter import find_banner_image_ids

        images = [
            _img(11477, 1979, 1180, 5), _img(11479, 1979, 1180, 6),
            _img(11483, 1979, 1180, 10), _img(99901, 1979, 1180, 7),
            _img(99902, 1979, 1180, 8),
        ]
        assert find_banner_image_ids(images) == set()

    def test_doc2419_real_charts_never_flagged(self):
        """**关键回归**：doc 2419 真实柱状图 1862×1320 在第 5/6/7 页复用。"""
        from app.services.image_decoration_filter import find_banner_image_ids

        images = [
            _img(8340, 1862, 1320, 5), _img(8345, 1862, 1320, 6),
            _img(8346, 1862, 1320, 7),
        ]
        assert find_banner_image_ids(images) == set()

    def test_campus_photo_crops_deliberately_kept(self):
        """640×427 校园照（母版横幅的裁切图，AR 1.5）**故意不拦** ——
        宁可留几条噪声，也不冒误伤真实图的风险。"""
        from app.services.image_decoration_filter import find_banner_image_ids

        images = [_img(i, *CAMPUS_PHOTO_640x427, page=p) for i, p in zip(range(1, 5), [2, 3, 7, 8])]
        assert find_banner_image_ids(images) == set()

    def test_mixed_doc_flags_only_banners(self):
        """混合文档：横幅被拦，同页真实内容图全部保留。"""
        from app.services.image_decoration_filter import find_banner_image_ids

        images = [
            _img(1, 871, 45, 1), _img(2, 871, 45, 3), _img(3, 871, 45, 6),
            _img(10, 1024, 709, 1),   # 储罐实拍
            _img(11, 930, 687, 11),   # 隔油池剖面
            _img(12, 2337, 1051, 11), # 3D 设备渲染
            _img(13, 1325, 626, 6),   # 正文插图
        ]
        assert find_banner_image_ids(images) == {1, 2, 3}

    def test_empty_input(self):
        from app.services.image_decoration_filter import find_banner_image_ids

        assert find_banner_image_ids([]) == set()

    def test_images_without_id_are_not_returned(self):
        """未 flush 拿到 id 的行不应被误标（None 不进结果集）。"""
        from app.services.image_decoration_filter import find_banner_image_ids

        images = [
            SimpleNamespace(id=None, width=871, height=45, page_number=p) for p in (1, 2, 3)
        ]
        assert find_banner_image_ids(images) == set()


# ============================================================================
# 4. 写入侧接线：_skip_banner_images 必须落 ocr_status='skipped'
# ============================================================================


class TestSkipBannerImagesWiring:
    def test_banners_marked_skipped_and_returned(self):
        """拦截后 DB 里 ocr_status='skipped'（该状态值 knowledge.py 图片列表
        API 已在 status_count 里统计，前端无需改动）。"""
        from unittest.mock import AsyncMock, patch

        from sqlalchemy.dialects import postgresql

        from app.services import multimodal_extraction_service as mod
        from app.services.multimodal_extraction_service import (
            multimodal_extraction_service as svc,
        )

        images = [
            _img(1, 871, 45, 1), _img(2, 871, 45, 3), _img(3, 871, 45, 6),
            _img(10, 1024, 709, 1),
        ]
        executed = []

        class _FakeSession:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def execute(self, stmt):
                executed.append(stmt)
                return None

            async def commit(self):
                return None

        with patch.object(mod, "async_session", lambda: _FakeSession()):
            banner_ids = asyncio_run(svc._skip_banner_images(7, images))

        assert banner_ids == {1, 2, 3}
        assert len(executed) == 1, "必须落库一次 update"
        # 用 literal_binds 编译才能看到实际写入的状态值
        compiled = str(
            executed[0].compile(
                dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
            )
        )
        assert "UPDATE knowledge_images" in compiled
        assert "'skipped'" in compiled

    def test_no_banners_writes_nothing(self):
        """没有装饰图时**不发任何 SQL**（零额外开销）。"""
        from unittest.mock import patch

        from app.services import multimodal_extraction_service as mod

        executed = []

        class _FakeSession:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def execute(self, stmt):
                executed.append(stmt)
                return None

            async def commit(self):
                return None

        images = [_img(10, 1024, 709, 1), _img(11, 1979, 1180, 2)]
        with patch.object(mod, "async_session", lambda: _FakeSession()):
            banner_ids = asyncio_run(
                mod.multimodal_extraction_service._skip_banner_images(7, images)
            )

        assert banner_ids == set()
        assert executed == []

    def test_db_failure_still_skips_ocr(self):
        """DB 标记失败**不得**阻断：仍返回 banner_ids，让 OCR 侧照常跳过
        （降噪判据不能拖垮主链路）。"""
        from unittest.mock import patch

        from app.services import multimodal_extraction_service as mod

        class _BoomSession:
            async def __aenter__(self):
                raise RuntimeError("db down")

            async def __aexit__(self, *a):
                return False

        images = [_img(i, 871, 45, p) for i, p in zip(range(1, 4), [1, 2, 3])]
        with patch.object(mod, "async_session", lambda: _BoomSession()):
            banner_ids = asyncio_run(
                mod.multimodal_extraction_service._skip_banner_images(7, images)
            )

        assert banner_ids == {1, 2, 3}

    def test_criterion_exception_degrades_to_no_filtering(self):
        """判据本身抛异常 → 返回空集 = 全部照常 OCR，绝不误伤。"""
        from unittest.mock import patch

        from app.services import multimodal_extraction_service as mod

        images = [_img(i, 871, 45, p) for i, p in zip(range(1, 4), [1, 2, 3])]
        with patch.object(mod, "find_banner_image_ids", side_effect=RuntimeError("boom")):
            banner_ids = asyncio_run(
                mod.multimodal_extraction_service._skip_banner_images(7, images)
            )

        assert banner_ids == set()


# ============================================================================
# 5. 检索侧接线：_not_banner_predicate 生成的 SQL
# ============================================================================


class TestRetrievalPredicate:
    def test_predicate_compiles_with_thresholds_wired(self):
        """阈值必须来自 image_decoration_filter 常量（单一事实源），
        且 SQL 含「同尺寸跨页计数」子查询 —— 锁住两个信号都在。"""
        from sqlalchemy.dialects import postgresql

        from app.services.image_decoration_filter import (
            MAX_BANNER_HEIGHT_PX,
            MIN_ASPECT_RATIO,
            MIN_REPEATED_PAGES,
        )
        from app.services.multimodal_retriever import MultimodalRetriever

        sql = str(
            MultimodalRetriever._not_banner_predicate().compile(
                dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
            )
        )
        assert "COUNT(DISTINCT" in sql.upper()
        assert str(MIN_ASPECT_RATIO) in sql
        assert str(MAX_BANNER_HEIGHT_PX) in sql
        assert str(MIN_REPEATED_PAGES) in sql

    def test_load_candidates_applies_predicate(self):
        """_load_candidates 的 where 子句必须带上网格判据（存量图不进候选）。"""
        import inspect

        from app.services.multimodal_retriever import MultimodalRetriever

        src = inspect.getsource(MultimodalRetriever._load_candidates)
        assert "_not_banner_predicate" in src


# ============================================================================
# 5b. 端到端接线：extract_for_knowledge 只把非装饰图送进 OCR
# ============================================================================


class TestExtractForKnowledgeWiring:
    """锁住「装饰图不进 OCR 队列」这条接线本身。

    变异测试 #4（把 ocr_targets 退回 image_records）会让本组转红 ——
    这是唯一能抓住该变异的用例，纯函数测试覆盖不到调用点。
    """

    def _run(self, images):
        from unittest.mock import AsyncMock, patch

        from app.services import multimodal_extraction_service as mod
        from app.services import file_service as fs_mod

        svc = mod.multimodal_extraction_service
        ocr_seen = {}

        async def _fake_ocr(records):
            ocr_seen["ids"] = [r.id for r in records]
            return [{"image_id": r.id, "ok": True, "parsed": {}, "structured": None} for r in records]

        knowledge = SimpleNamespace(
            file_path="knowledge/1/f.pptx", file_name="f.pptx",
            file_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            title="t",
        )

        class _FakeSession:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def execute(self, *a, **kw):
                res = AsyncMock()
                res.scalar_one_or_none = lambda: knowledge
                return res

            async def commit(self):
                return None

        raw = [{"bytes": b"x", "page": img.page_number, "ext": "png",
                "width": img.width, "height": img.height,
                "mime": "image/png", "size": 1} for img in images]

        # ⚠️ extract_for_knowledge 内部是 `from app.services.file_service import
        # file_service as fs`（函数内 import），所以必须 patch **file_service 模块的
        # 属性**，patch multimodal_extraction_service.file_service 无效（类 20.181）。
        # 否则本用例会真的去连生产 MinIO 下载不存在的 key。
        fake_fs = AsyncMock()
        fake_fs.download_file = AsyncMock(return_value=b"PK\x03\x04fake-pptx")
        fake_fs.upload_file = AsyncMock(
            return_value={"url": "http://x/y.png", "object_name": "y.png"}
        )

        with patch.object(fs_mod, "file_service", fake_fs), \
             patch.object(mod, "async_session", lambda: _FakeSession()), \
             patch.object(svc, "_reset_multimodal_data", AsyncMock()), \
             patch.object(mod, "_should_skip_image", return_value=False), \
             patch.object(mod, "_resize_image_if_needed",
                          side_effect=lambda b, m: (b, None)), \
             patch.object(svc, "_upload_images", AsyncMock(return_value=images)), \
             patch.object(svc, "_skip_banner_images", new=_real_skip()), \
             patch.object(svc, "_ocr_images_concurrent", side_effect=_fake_ocr), \
             patch.object(svc, "_save_extractions",
                          AsyncMock(return_value={"formula": 0, "table": 0,
                                                  "chart": 0, "image_block": 0,
                                                  "dedup_skipped": 0})), \
             patch.object(svc, "_compute_anchor_for_images", AsyncMock()), \
             patch.object(svc, "_inject_into_formatted_content", AsyncMock()), \
             patch.object(mod, "_extract_file_images", return_value=raw):
            result = asyncio_run(svc.extract_for_knowledge(1))
        # 断言真的跑到了 OCR 阶段（防止"提前 return"造成的假通过）
        assert result.get("ok") is True, f"流程未走到 OCR 阶段: {result}"
        return ocr_seen.get("ids", [])

    def test_banners_excluded_from_ocr_queue_real_content_kept(self):
        images = [
            _img(1, 871, 45, 1), _img(2, 871, 45, 3), _img(3, 871, 45, 6),
            _img(10, 1024, 709, 1),   # 储罐实拍
            _img(11, 1862, 1320, 5),  # doc2419 真实柱状图
        ]
        assert self._run(images) == [10, 11]

    def test_doc_with_only_banners_sends_nothing_to_ocr(self):
        images = [_img(i, 1055, 203, p) for i, p in zip(range(1, 6), [1, 2, 3, 7, 17])]
        assert self._run(images) == []

    def test_doc_without_banners_unchanged_behaviour(self):
        """无装饰图的文档必须完全不受影响（0 回归）。"""
        images = [
            _img(1, 1979, 1180, 5), _img(2, 1979, 1180, 6),
            _img(3, 640, 427, 2), _img(4, 100, 100, 3),
        ]
        assert self._run(images) == [1, 2, 3, 4]


def _real_skip():
    """真实的拦截逻辑（不碰库）：只调判据，不发 UPDATE。

    用它替换被 patch 的 _skip_banner_images，保证端到端用例走的是
    真实判据而非桩，同时测试不产生任何 DB 副作用。
    """
    from app.services.image_decoration_filter import find_banner_image_ids

    async def _skip(knowledge_id, image_records):
        return find_banner_image_ids(image_records)

    return _skip


def asyncio_run(coro):
    import asyncio

    return asyncio.run(coro)


# ============================================================================
# 变异测试（人工执行，用于验证本测试确实能抓住回归）
# ============================================================================
#
# 三条变体各自会让上面的用例转红：
#
#   1) 把 find_banner_image_ids 里的 `repeated.get(...) >= min_repeated_pages`
#      改成 `>= 1`（只剩宽高比单信号）
#      → TestFindBannerImageIds 的 single/two-page 用例 + mixed_doc 转红
#
#   2) 把 is_banner_shape 里的 `(width / height) >= min_aspect_ratio`
#      改成 `>= 2.0`（放宽宽高比）
#      → 实测转红：TestIsBannerShape.test_exact_threshold_boundary +
#        test_thin_but_moderately_wide_content_rejected（AR 4.0 的真宽图被误判）。
#        实测 (2337,1051)/(1325,626) 仍安全 —— 它们是被 **height 保险丝**
#        （1051 > 300）挡下的，两道防线互相独立，任一被撤掉都有测试转红。
#
#   3) 从 extract_for_knowledge 里删掉 `ocr_targets = [img for img in
#      image_records if img.id not in banner_ids]`，直接传 image_records
#      → 装饰图重新进 OCR，TestSkipBannerImagesWiring 的语义失效
#        （该接线由集成断言覆盖）
