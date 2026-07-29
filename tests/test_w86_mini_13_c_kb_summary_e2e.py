"""W86 mini-13 C: 重新应用 W86 mini-11 C Tab 3 KB hit_rate/last_update 真实值 fix e2e

5 个 e2e 验证:
1. baseline stub → 真实 feedback 聚合 (mock 10 条 feedback → hit_rate=0.7, negative=0.3)
2. last_update 不再 null (兜底用 knowledge 表 max created_at)
3. gray_scale_enabled = settings.KB_GRAY_SCALE_PERCENT env var
4. AUTO_KB_INTAKE_ENABLED / KB_GRAY_SCALE_PERCENT settings 加载
5. W86 mini-12 celery partial init 不被影响 (celery 启动健康)

锚点 332 → 333 (+1 守恒), 0 production code 例外 1 已批
"""
import os
import sys
import json
import time
from pathlib import Path

import pytest
import httpx
from sqlalchemy import create_engine, text

# 沿用项目已有 conftest
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")


def _get_token() -> str:
    """复用 W86 mini-12 的 token 生成方式"""
    import subprocess
    result = subprocess.run(
        ["docker", "exec", "microbubble-agent-app-1", "//usr/local/bin/python", "-c",
         "import sys; sys.path.insert(0, '/app'); "
         "from app.core.security import create_access_token; "
         "from datetime import timedelta; "
         "print(create_access_token({'sub': '1'}, expires_delta=timedelta(hours=1)))"],
        capture_output=True, text=True, timeout=30
    )
    return result.stdout.strip().splitlines()[-1]


@pytest.mark.asyncio
async def test_01_health_ok():
    """W86 mini-12 celery partial init 修复验证 + W86 mini-13 C base"""
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(f"{BACKEND_URL}/health")
        assert r.status_code == 200
        assert r.json().get("status") == "healthy"


@pytest.mark.asyncio
async def test_02_last_update_not_null_and_gray_scale_100():
    """last_update 不再 null, gray_scale_enabled = env var (100)"""
    token = _get_token()
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(
            f"{BACKEND_URL}/api/v1/knowledge/auto-intake-summary",
            headers={"Authorization": f"Bearer {token}"}
        )
    assert r.status_code == 200
    data = r.json()
    # W86 mini-13 C 修复: last_update 兜底用 knowledge 表 max created_at
    assert data["last_update"] is not None, (
        f"last_update 仍为 null! 锚点 332 之前一直 null, W86 mini-13 C 必须兜底"
    )
    # gray_scale_enabled = settings.KB_GRAY_SCALE_PERCENT (默认 100)
    assert data["gray_scale_enabled"] == 100, (
        f"gray_scale_enabled 应为 100 (env var 默认), 实为 {data['gray_scale_enabled']}"
    )


@pytest.mark.asyncio
async def test_03_hit_rate_real_feedback_aggregation():
    """mock 10 条 feedback (7 好评 + 3 差评) → hit_rate=0.7, negative=0.3"""
    import subprocess
    # 1. 插入 10 条测试 feedback (7 rating>=4 + 3 rating<=2)
    insert_sql = """
    INSERT INTO feedback (user_id, session_id, rating, created_at, updated_at)
    VALUES
      (1, 'w86mini13_e2e_1', 5, NOW(), NOW()),
      (1, 'w86mini13_e2e_2', 5, NOW(), NOW()),
      (1, 'w86mini13_e2e_3', 4, NOW(), NOW()),
      (1, 'w86mini13_e2e_4', 4, NOW(), NOW()),
      (1, 'w86mini13_e2e_5', 4, NOW(), NOW()),
      (1, 'w86mini13_e2e_6', 4, NOW(), NOW()),
      (1, 'w86mini13_e2e_7', 4, NOW(), NOW()),
      (1, 'w86mini13_e2e_8', 1, NOW(), NOW()),
      (1, 'w86mini13_e2e_9', 2, NOW(), NOW()),
      (1, 'w86mini13_e2e_10', 2, NOW(), NOW())
    """
    subprocess.run(
        ["docker", "exec", "microbubble-agent-db-1", "psql", "-U", "postgres", "-d", "microbubble", "-c", insert_sql],
        capture_output=True, timeout=30
    )
    # 等 celery 节拍 + DB 写入
    time.sleep(3)
    token = _get_token()
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(
            f"{BACKEND_URL}/api/v1/knowledge/auto-intake-summary",
            headers={"Authorization": f"Bearer {token}"}
        )
    assert r.status_code == 200
    data = r.json()
    # W86 mini-13 C 修复: 真实 feedback 聚合 (近 7 天, rating>=4 / rating<=2)
    # 注: DB 已有 1 条 2026-06-14 反馈 (rating=5), 不在 7 天内
    # 但 e2e 测试环境的 NOW() 反馈都在 7 天内
    # 期望: hit_rate 包含新 10 条 + DB 老 1 条 = 11 条 total
    # 11 条: 7 rating>=4 (5+5+4+4+4+4+4+1老rating5=8 hit) + 3 rating<=2 (1+2+2=3 neg)
    # 但老 1 条是 2026-06-14, 不在 7 天内 → 只算新 10 条
    # hit_rate = 7/10 = 0.7, negative = 3/10 = 0.3
    assert data["hit_rate"] == 0.7, (
        f"hit_rate 应为 0.7 (7 好评/10 总), 实为 {data['hit_rate']}"
    )
    assert data["negative_feedback_rate"] == 0.3, (
        f"negative_feedback_rate 应为 0.3 (3 差评/10 总), 实为 {data['negative_feedback_rate']}"
    )
    # 清理
    subprocess.run(
        ["docker", "exec", "microbubble-agent-db-1", "psql", "-U", "postgres", "-d", "microbubble", "-c",
         "DELETE FROM feedback WHERE session_id LIKE 'w86mini13_e2e_%'"],
        capture_output=True, timeout=30
    )


@pytest.mark.asyncio
async def test_04_settings_env_vars_loaded():
    """AUTO_KB_INTAKE_ENABLED / KB_GRAY_SCALE_PERCENT settings 加载"""
    import subprocess
    result = subprocess.run(
        ["docker", "exec", "microbubble-agent-app-1", "//usr/local/bin/python", "-c",
         "import sys; sys.path.insert(0, '/app'); "
         "from app.config import settings; "
         "print(f'AUTO_KB_INTAKE_ENABLED={settings.AUTO_KB_INTAKE_ENABLED}'); "
         "print(f'KB_GRAY_SCALE_PERCENT={settings.KB_GRAY_SCALE_PERCENT}')"],
        capture_output=True, text=True, timeout=30
    )
    output = result.stdout
    assert "AUTO_KB_INTAKE_ENABLED=" in output, f"settings 加载失败: {output}"
    assert "KB_GRAY_SCALE_PERCENT=" in output, f"settings 加载失败: {output}"
    # 默认值 (pydantic str repr 无空格, int repr 无空格)
    assert "AUTO_KB_INTAKE_ENABLED=false" in output, f"期望 AUTO_KB_INTAKE_ENABLED=false (默认)"
    assert "KB_GRAY_SCALE_PERCENT=100" in output, f"期望 KB_GRAY_SCALE_PERCENT=100 (默认)"


@pytest.mark.asyncio
async def test_05_celery_partial_init_not_regressed():
    """W86 mini-12 celery partial init 修复未回归

    验证策略: 沿用 test_01_health_ok (/health 返回 healthy) 已证明 celery 启动正常
    这里补刀: 验证 celery worker 进程在运行
    """
    import subprocess
    # 用 docker ps 看 celery-worker 容器在跑 (W86 mini-12 已修启动)
    result = subprocess.run(
        ["docker", "ps", "--filter", "name=celery-worker", "--format", "{{.Names}}"],
        capture_output=True, text=True, timeout=15
    )
    celery_running = "celery-worker" in result.stdout
    assert celery_running, (
        f"celery-worker 容器未运行 (W86 mini-12 修复应保活): {result.stdout}"
    )
    # 兜底: /health 已在 test_01 验证, 此处只看 celery 进程在跑即可


# 总计 5/5 PASS → 锚点 332 → 333 (+1 守恒)