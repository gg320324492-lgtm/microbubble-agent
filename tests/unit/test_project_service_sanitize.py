"""
test_project_service_sanitize.py — 测试 project_service 入库前 description 清洗 (2026-07-15)

覆盖场景:
  1. create_project 接收 LLM 套路 description → 自动清洗
  2. create_project 接收短干净 description → pass-through
  3. update_project 修改 description → 同样清洗
  4. None / 空 description 不动
"""
import pytest

from app.services.project_service import ProjectService
from app.utils.text_sanitize import sanitize_project_description


class TestCreateProjectSanitize:
    """create_project 入库前 description 清洗"""

    @pytest.mark.asyncio
    async def test_llm_preamble_cleaned_at_create(self, db, test_member):
        svc = ProjectService(db)
        llm_dirty = (
            "好的，非常荣幸能为您规划这份研究项目计划。本计划旨在充分利用6个月时间。\n\n"
            "### **项目总览**\n"
            "*   **项目名称：** 微纳米气泡对典型抗生素的降解效能与机理研究\n"
            "*   **总时长：** 6个月"
        )
        project = await svc.create_project(
            name="测试LLM清洗",
            description=llm_dirty,
            created_by=test_member.id,
        )
        # 不应包含 LLM 元信息
        assert "好的" not in project.description
        assert "非常荣幸" not in project.description
        assert "**" not in project.description
        assert "本计划" not in project.description
        assert "6个月" not in project.description
        # 字段抽取命中
        assert "微纳米气泡对典型抗生素" in project.description
        # 长度合理
        assert 6 <= len(project.description) <= 280

    @pytest.mark.asyncio
    async def test_short_clean_passthrough(self, db, test_member):
        svc = ProjectService(db)
        clean = "研究臭氧微纳米气泡对黑臭水体底泥及上覆水中污染物去除机制。"
        project = await svc.create_project(
            name="测试短干净",
            description=clean,
            created_by=test_member.id,
        )
        # 短干净描述不应被改坏
        assert "臭氧微纳米气泡" in project.description
        assert "黑臭水体" in project.description

    @pytest.mark.asyncio
    async def test_none_description_unaffected(self, db, test_member):
        svc = ProjectService(db)
        project = await svc.create_project(
            name="测试无描述",
            description=None,
            created_by=test_member.id,
        )
        assert project.description is None

    @pytest.mark.asyncio
    async def test_empty_description_unaffected(self, db, test_member):
        svc = ProjectService(db)
        project = await svc.create_project(
            name="测试空描述",
            description="",
            created_by=test_member.id,
        )
        # sanitize 返空字符串, 仍然入库为 ""
        assert project.description == ""


class TestUpdateProjectSanitize:
    """update_project 修改 description 同样清洗"""

    @pytest.mark.asyncio
    async def test_update_description_sanitize(self, db, test_member):
        svc = ProjectService(db)
        # 先创建干净 project
        project = await svc.create_project(
            name="测试update清洗",
            description="原始干净描述",
            created_by=test_member.id,
        )
        # 再 update 灌脏描述
        llm_dirty = (
            "好的，非常荣幸。\n\n"
            "### **项目总览**\n"
            "*   **项目名称：** 微纳米气泡技术在黑臭水体治理中的机理与效能研究"
        )
        updated = await svc.update_project(
            project.id,
            description=llm_dirty,
        )
        assert updated is not None
        assert "好的" not in updated.description
        assert "非常荣幸" not in updated.description
        assert "**" not in updated.description
        assert "微纳米气泡技术在黑臭水体治理" in updated.description


class TestSanitizeFunctionPerformance:
    """sanitize 性能 (P0: 1000 次调用 < 500ms)"""

    def test_sanitize_1000_calls_under_500ms(self):
        import time
        raw = (
            "好的，非常荣幸。\n\n"
            "### **项目总览**\n"
            "*   **项目名称：** 微纳米气泡技术在黑臭水体治理中的机理与效能研究"
        )
        start = time.perf_counter()
        for _ in range(1000):
            sanitize_project_description(raw)
        elapsed = time.perf_counter() - start
        assert elapsed < 0.5, f"sanitize too slow: {elapsed:.3f}s for 1000 calls"
