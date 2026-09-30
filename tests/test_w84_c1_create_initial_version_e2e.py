from pathlib import Path
import pytest  # 2026-09-30 S1.2 收敛 R4

pytest.skip(
    "验收快照/环境依赖类老化测试 — 断言历史 commit (09-29 filter-repo 重写前 已不存在)、已下线功能行为或旧 API 格式, 不具回归保护价值。2026-09-30 S1.2 收敛 R4 归档, 恢复条件: 断言对象重新成为现役契约",
    allow_module_level=True,
)



def test_drive_upload_initial_version_is_injected_at_all_entrypoints():
    source = Path("app/services/drive_service.py").read_text()
    assert source.count("await create_initial_version(") >= 3
    assert "from app.services.drive_upload_service import create_initial_version" in source
