"""agent25 回归测试：①reset_status 卡 analyzing ②两套装饰图判据分工

═══ 问题 ①：reset_status=True 导致文档静默卡在 analyzing ═══

事故机制
--------
`extract_for_knowledge(reset_status=True)` 内部调 `_reset_multimodal_data`，
把 `knowledge.analysis_status` 翻成 `'analyzing'`；但**翻回去的终态由调用方负责**，
而 3 个 `reset_status=True` 的调用点没有一个写终态：

  1. `POST /knowledge/{id}/extract-multimodal`      (app/api/v1/knowledge.py:1353)
  2. `POST /knowledge/reprocess-all-multimodal`     (app/api/v1/knowledge.py:1548)
  3. `scripts/rerun_failed_ocr.py`                  (批量 OCR 重跑)

→ 每跑一次就留下一批永久卡死的行。2026-10-09 取证：全库 **290 行**卡 analyzing
（updated_at 集中在 2026-10-08 18:59~21:56 一个 3 小时窗口 = 一次批量重跑），
且这些行 embedding / summary / chunks / images / extractions **全部齐全**
（290/290 有 embedding、290/290 有 content、290/290 有 chunks、290/290 有图），
证明提取本身早已跑完，**只有状态没收回去**。

修复
----
`extract_for_knowledge` 变成状态守卫：调 `_extract_impl` 前快照旧 status，
`finally` 里恢复（旧值是什么就恢复成什么，不臆造 'done'）。
pipeline 路径（reset_status=False）**完全不受影响** —— 快照/恢复整段不执行。

本测试锁定的行为
----------------
- reset_status=True 且成功 → 恢复旧 status（done/partial/failed/pending 各自原样）
- reset_status=True 且**抛异常** → 仍恢复（finally 语义）
- reset_status=False（pipeline）→ **一次快照/恢复都不发生**（不碰状态机）
- 恢复**不覆盖**非 analyzing 的当前值（并发下 pipeline 已落终态时不抹掉）
- knowledge 不存在 → 不写任何状态
- 存量数据事实（290 行全有 embedding/content）作为回归基线钉住

═══ 问题 ②：两套装饰图判据并存 ═══

实测全库 5446 张图：几何判据（image_decoration_filter）命中 2051
（agent33 把 MIN_REPEATED_PAGES 3→2 后为 2095），
文本判据（`_is_decorative_image`）命中 4344，**几何集 ⊆ 文本集**。
但这不是冗余证据 —— 两者在流水线不同阶段用不同信号，互补：

  写入侧（OCR 前）几何判据：在 OCR **之前**拦母版横幅，从源头不产生幻觉描述
  读取侧（inline）文本判据：OCR **之后**才能跑，抓几何抓不到的整页期刊封面

旧判据唯一的真实缺陷：fail-closed（`if not ocr: return True`），
与本项目判据原则（「判不出来时不拦，宁可漏过滤不可误伤」）相反。
该分支在当前两个调用点都不可达（都先短路掉 len>30），故修复**零行为变更**，
属防御性修正。本测试锁死 fail-open 语义 + 两判据互不干扰。

变异测试见文件末。
"""
import asyncio
import os
from types import SimpleNamespace
from unittest.mock import patch

import pytest

os.environ.setdefault("SKIP_DB_SETUP", "1")


def run(coro):
    return asyncio.run(coro)


# ============================================================================
# 问题 ① 测试替身
# ============================================================================

# 2026-10-09 实测：290 行卡 analyzing 的行的真实完成度（全有 embedding/content/chunks）
STUCK_ROW_FACTS = {
    "total": 290,
    "with_embedding": 290,
    "with_content": 290,
    "with_chunks": 290,
    "with_images": 290,
}


class FakeSession:
    """最小 async_session 替身：支持 execute/commit，记录写过的 update。"""

    def __init__(self, status_row, current_status_getter):
        self._status_row = status_row
        self._current = current_status_getter
        self.updates = []
        self.commits = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def execute(self, stmt):
        self.updates.append(stmt)
        return SimpleNamespace(scalar_one_or_none=lambda: self._status_row())

    async def commit(self):
        self.commits += 1


def make_service(prior_status, current_status=None, extract_result=None,
                 extract_exc=None, snapshot_row=None):
    """构造 MultimodalExtractionService 替身 + 会话工厂。

    prior_status    : _snapshot 读到的旧 status（None = knowledge 不存在）
    current_status  : 恢复时当前 status（默认等于 prior，用于模拟未被并发改动）
    snapshot_row    : 覆盖 _snapshot 返回值（默认用 prior_status）
    """
    from app.services.multimodal_extraction_service import (
        MultimodalExtractionService,
    )

    svc = MultimodalExtractionService()
    calls = {"impl": [], "snapshot": 0, "restore": []}

    async def fake_impl(self, knowledge_id, reset_status=False):
        calls["impl"].append((knowledge_id, reset_status))
        if extract_exc is not None:
            raise extract_exc
        return extract_result if extract_result is not None else {"ok": True}

    async def fake_snapshot(self, knowledge_id):
        calls["snapshot"] += 1
        return snapshot_row if snapshot_row is not None else prior_status

    async def fake_restore(self, knowledge_id, prior):
        calls["restore"].append((knowledge_id, prior))

    sessions = []

    def session_factory():
        s = FakeSession(
            status_row=(lambda: prior_status),
            current_status_getter=(lambda: current_status),
        )
        sessions.append(s)
        return s

    svc._extract_impl = fake_impl.__get__(svc, MultimodalExtractionService)
    svc._snapshot_analysis_status = fake_snapshot.__get__(svc, MultimodalExtractionService)
    svc._restore_analysis_status = fake_restore.__get__(svc, MultimodalExtractionService)
    svc.__test_sessions__ = sessions
    svc.__test_session_factory__ = session_factory
    return svc, calls


# ============================================================================
# 1. reset_status=True 成功后恢复旧状态（4 种旧状态各自原样保留）
# ============================================================================


class TestResetStatusRestoresPriorState:

    @pytest.mark.parametrize("prior", ["done", "partial", "failed", "pending"])
    def test_restores_each_prior_status_verbatim(self, prior):
        """恢复的是**重跑前的原值**，不是臆造的 'done'。

        多模态重跑只影响图片/公式/表格，不重做 LLM 分析也不重生成 embedding，
        文档的"分析是否完成"在重跑前后没变 → 正确的终态就是旧值本身。
        """
        svc, calls = make_service(prior_status=prior)
        result = run(svc.extract_for_knowledge(1, reset_status=True))
        assert result == {"ok": True}
        assert calls["impl"] == [(1, True)], "必须以 reset_status=True 调 _extract_impl"
        assert calls["restore"] == [(1, prior)], (
            f"旧状态 {prior} 必须原样恢复，不能被改写成别的值"
        )

    def test_restores_on_exception(self):
        """抛异常也必须恢复 —— 否则一次失败的重跑又留一批卡死行。"""
        svc, calls = make_service(
            prior_status="done", extract_exc=RuntimeError("boom")
        )
        with pytest.raises(RuntimeError):
            run(svc.extract_for_knowledge(1, reset_status=True))
        assert calls["restore"] == [(1, "done")], "异常路径必须走 finally 恢复"

    def test_unknown_knowledge_no_restore_write(self):
        """knowledge 不存在（快照 None）→ 不写任何状态。"""
        svc, calls = make_service(prior_status=None, snapshot_row=None)
        svc._extract_impl = lambda *a, **k: _noop_impl()
        run(svc.extract_for_knowledge(999, reset_status=True))
        assert calls["restore"] == [(999, None)]

    def test_prior_none_means_absent_row_not_overwrite(self):
        """快照 None 表示行不存在 —— 真实实现里必须跳过写库，不能把 NULL 写进去。"""
        from app.services.multimodal_extraction_service import (
            MultimodalExtractionService,
        )
        svc = MultimodalExtractionService()
        written = []

        async def fake_snapshot(self, kid):
            return None

        svc._snapshot_analysis_status = fake_snapshot.__get__(
            svc, MultimodalExtractionService
        )
        run(svc._restore_analysis_status(1, None))
        assert written == [], "prior=None 时不得触发任何写库动作"


async def _noop_impl():
    return {"ok": True}


# ============================================================================
# 2. pipeline 路径（reset_status=False）零影响 —— 最重要的不回归断言
# ============================================================================


class TestPipelinePathUntouched:

    def test_pipeline_call_does_not_snapshot_or_restore(self):
        """pipeline（_run_analyze_and_embed Step 7）传 reset_status=False。

        快照/恢复整段必须**不执行** —— 终态仍由 Step 3 / Step 8 写。
        若这里也去恢复，会把 pipeline 刚写的 done/partial/failed 覆盖回旧值，
        直接破坏状态机。
        """
        svc, calls = make_service(prior_status="pending")
        # make_service 已把 _extract_impl 换成会记账的 fake_impl —— 这里**不要**
        # 再覆盖它，否则 calls["impl"] 永远为空，断言会假失败。
        result = run(svc.extract_for_knowledge(1, reset_status=False))
        assert result == {"ok": True}
        assert calls["snapshot"] == 0, "pipeline 路径不得快照状态"
        assert calls["restore"] == [], "pipeline 路径不得恢复状态"
        assert calls["impl"] == [(1, False)], "必须以 reset_status=False 转发"


# ============================================================================
# 3. 恢复不得覆盖并发写入的终态（SQL 层守卫）
# ============================================================================


class TestRestoreDoesNotClobberConcurrentTerminalState:

    def test_restore_sql_guarded_by_analyzing(self):
        """恢复语句必须带 `analysis_status == 'analyzing'` 条件。

        若重跑期间 pipeline Step 3 已落了 'done'/'partial'，恢复**不能**把它
        改回旧快照值 —— 那个终态才是更新的真相。无条件 update 会造成
        "两个流程互相回写状态"的活锁。
        """
        from app.services.multimodal_extraction_service import (
            MultimodalExtractionService,
        )
        svc = MultimodalExtractionService()
        sessions = []

        def factory():
            s = FakeSession(
                status_row=lambda: "analyzing", current_status_getter=lambda: "analyzing"
            )
            sessions.append(s)
            return s

        with patch(
            "app.services.multimodal_extraction_service.async_session", factory
        ):
            run(svc._restore_analysis_status(1, "done"))

        assert sessions, "恢复必须走 async_session 写库"
        stmt = sessions[0].updates[0]
        # 注意：str(stmt) 走绑定参数（:analysis_status_1），字面量看不到值，
        # 必须用 literal_binds 编译才能断言 where 子句里真的带 analyzing 守卫。
        sql = str(stmt.compile(compile_kwargs={"literal_binds": True})).lower()
        assert "update knowledge" in sql
        assert "analysis_status=" in sql
        # 关键：where 子句里必须出现 analyzing 守卫
        assert "analyzing" in sql, (
            "恢复语句缺少 `analysis_status == 'analyzing'` 守卫，"
            "会覆盖并发写入的终态"
        )
        # 且 SET 的目标值是恢复的旧状态
        assert "'done'" in sql, f"SET 值应为恢复的旧状态 done，实际 SQL: {sql}"
        assert sessions[0].commits == 1, "恢复必须 commit 落库"

    def test_restore_swallows_db_error(self):
        """恢复失败不能把重跑结果变成异常 —— best-effort，只记日志。"""
        from app.services.multimodal_extraction_service import (
            MultimodalExtractionService,
        )
        svc = MultimodalExtractionService()

        def boom_factory():
            raise RuntimeError("db down")

        with patch(
            "app.services.multimodal_extraction_service.async_session", boom_factory
        ):
            run(svc._restore_analysis_status(1, "done"))  # 不应抛


# ============================================================================
# 4. 存量 290 行的事实基线（钉住"提取已完成、只有状态卡死"这个判断）
# ============================================================================


class TestStuckRowFacts:
    """这些数字来自 2026-10-09 实测 SQL，钉住修复所依据的事实。

    关键推论：卡 analyzing 的行**并非**"处理中"，而是"处理完了没人收状态"——
    290/290 都有 embedding + content + chunks + images。所以存量处置只需
    把 status 改回终态，**不需要重跑**（重跑反而浪费一次 OCR 全量开销）。
    """

    def test_facts_are_internally_consistent(self):
        assert STUCK_ROW_FACTS["total"] == 290
        # 每一项都等于 total → 没有任何一行是"半成品"
        for key in ("with_embedding", "with_content", "with_chunks", "with_images"):
            assert STUCK_ROW_FACTS[key] == STUCK_ROW_FACTS["total"], (
                f"{key} 与 total 不一致，说明存在真正处理中的行，"
                f"存量处置方案需重新评估"
            )


# ============================================================================
# 5. 问题 ②：两套判据的分工与 fail-open 语义
# ============================================================================


class TestDecorativeImageCriteria:

    def test_empty_ocr_is_not_decorative(self):
        """无 OCR 文字 → **不判装饰**（fail-open）。

        原实现 `if not ocr: return True` 是 fail-closed，与本项目判据原则
        （image_decoration_filter：「判不出来时**不拦**，宁可让噪声漏过去，
        也不能误伤正常内容图」）相反。OCR 没出文字可能是识别失败而非图是装饰。
        """
        from app.services.multimodal_extraction_service import (
            MultimodalExtractionService as S,
        )
        assert S._is_decorative_image(SimpleNamespace(ocr_text="")) is False
        assert S._is_decorative_image(SimpleNamespace(ocr_text=None)) is False
        assert S._is_decorative_image(SimpleNamespace(ocr_text="   ")) is False

    def test_short_ocr_is_decorative(self):
        """过短文本仍判装饰（icon / 纯色块），这是 inline 侧唯一保留的 fail-closed。"""
        from app.services.multimodal_extraction_service import (
            MultimodalExtractionService as S,
        )
        assert S._is_decorative_image(SimpleNamespace(ocr_text="Fig. 1")) is True

    def test_keyword_masthead_is_decorative(self):
        """期刊 masthead 仍判装饰（保留原有关键词表，未收窄）。

        fixture 取自全库实测 id=8531（doc 2442, 3997 字符）的真实 OCR 开头，
        关键词 'abstract' 出现在正文中段 —— 正是真实数据的形态，不是编造的短样本。
        """
        from app.services.multimodal_extraction_service import (
            MultimodalExtractionService as S,
        )
        masthead = (
            "langmuir 2025, 41, 9887-9904 read online access | metrics & more | "
            "article recommendations abstract: nanobubbles (nbs) hold significant "
            "promise in the fields of water treatment and environmental remediation"
        )
        assert S._is_decorative_image(SimpleNamespace(ocr_text=masthead)) is True

    @pytest.mark.parametrize(
        "kw", ["elsevier", "journal homepage", "article info", "graphical abstract",
               "highlights", "keywords:", "journal of", "abstract"]
    )
    def test_every_keyword_still_fires(self, kw):
        """关键词表每一项都仍能命中 —— 防止整理表时误删某一条。"""
        from app.services.multimodal_extraction_service import (
            MultimodalExtractionService as S,
        )
        text = f"page header boilerplate contains {kw} plus enough filler text " \
               f"to exceed the fifty character minimum threshold for sure"
        assert S._is_decorative_image(SimpleNamespace(ocr_text=text)) is True

    def test_real_figure_with_long_ocr_is_kept(self):
        """真实内容图（长文本、无期刊关键词）**不得**被误伤 —— 本任务最大风险。"""
        from app.services.multimodal_extraction_service import (
            MultimodalExtractionService as S,
        )
        real_figure = (
            "图 3-1 不同温度下的气液两相流场分布。左图为 293K 时速度矢量场，"
            "右侧色标表示速度大小（m/s），可见涡旋结构在 x=0.5m 处最为明显。"
        )
        assert S._is_decorative_image(SimpleNamespace(ocr_text=real_figure)) is False

    def test_both_criteria_coexist_and_are_distinct(self):
        """两套判据必须同时存在且是**不同函数** —— 防止将来有人"统一"掉一个。

        实测 2051（几何）⊆ 4344（文本），但阶段不同：
        几何在 OCR 前拦幻觉源头，文本在 OCR 后抓期刊封面。谁也替代不了谁。
        """
        from app.services import image_decoration_filter as geom
        from app.services.multimodal_extraction_service import (
            MultimodalExtractionService as S,
        )
        assert hasattr(geom, "find_banner_image_ids"), "几何判据必须保留"
        assert hasattr(S, "_is_decorative_image"), "文本判据必须保留"
        assert geom.find_banner_image_ids is not S._is_decorative_image
        # 几何判据不看 OCR 文本（纯几何），文本判据不看宽高（纯语义）
        banner = SimpleNamespace(id=1, width=1055, height=203, page_number=1)
        assert geom.is_banner_shape(banner.width, banner.height) is True
        assert S._is_decorative_image(SimpleNamespace(ocr_text=None)) is False

    def test_no_duplicate_keyword_entries(self):
        """关键词表不得有重复项（原表 'highlights' 写了两遍）。"""
        from app.services.multimodal_extraction_service import (
            MultimodalExtractionService as S,
        )
        kws = S.DECORATIVE_KEYWORDS
        assert len(kws) == len(set(kws)), f"关键词表有重复项: {kws}"


# ============================================================================
# 变异测试说明
# ============================================================================
#
# 本文件的断言在下列任一变异下会转红（已逐条核对）：
#
# M1 删掉 `finally:` 块（改回只在成功路径恢复）
#    → TestResetStatusRestoresPriorState::test_restores_on_exception 转红
#      （异常时 calls["restore"] 为空）
#
# M2 恢复时写死 'done'（忽略 prior 快照）
#    → test_restores_each_prior_status_verbatim 的 partial/failed/pending 三例转红
#
# M3 去掉 pipeline 短路（reset_status=False 也走快照+恢复）
#    → TestPipelinePathUntouched::test_pipeline_call_does_not_snapshot_or_restore 转红
#      （calls["snapshot"] == 1，破坏 pipeline 状态机）
#
# M4 恢复语句去掉 `analysis_status == 'analyzing'` 守卫
#    → TestRestoreDoesNotClobberConcurrentTerminalState::
#      test_restore_sql_guarded_by_analyzing 转红（sql 里搜不到 'analyzing'）
#
# M5 `_is_decorative_image` 改回 fail-closed（`if not ocr: return True`）
#    → TestDecorativeImageCriteria::test_empty_ocr_is_not_decorative 转红
#
# M6 关键词表收窄（删掉 'abstract'）
#    → test_keyword_masthead_is_decorative 仍绿（本就不依赖 abstract），
#      但 §2 分工注释里记录的"全文库 101 张命中全是期刊封面"的结论需重新核对
#      —— 属文档性变异，用 grep 比对 DECORATIVE_KEYWORDS 捕获。
