"""录音存活心跳 — 区分"仍在录音的长会议"与"真孤儿会议"。

2026-09-15 P0 新增（听会 09-14 事故修复链 · 第 3 段）。

事故回顾
--------
会议 250（杜同贺 / iPhone）于 2026-09-14 19:38:34 创建并开始听会。
20:14:58 被 `orphan_meeting_cleanup` 判定「录音超过 30min 未 stop」并标记
`status='error'`，标题被改写成「听会记录（已清理 09-14 11:38）」。
但用户当时**仍在录音**，直到 21:18:28 才点"结束听会" —— 那一刻前端发出
162MB 的单次上传，被 nginx 50m 上限拒绝（413），浏览器只显示 "Network Error"。
用户最终只能改用手机自带录音机补录，1 小时 40 分钟的会议数据全丢。

根因
----
`orphan_meeting_cleanup` 的判定条件只有
`status='recording' AND recording_started_at < now - 30min`，
**完全不看前端是否还活着**。于是任何录音超过 30 分钟的会议都会被误杀
（桌面端也一样，只是桌面端往往在 30min 内就点停止，暴露得少）。

设计
----
录音页面每 60s 调一次 `POST /meetings/{id}/recording-heartbeat`，写一个
Redis key（TTL 300s，容忍 4 次丢包）：

    key = "meeting:recording:heartbeat:{meeting_id}"   value = unix ts   ttl = 300

`orphan_meeting_cleanup` 扫描到候选会议时先查这个 key：
- key 存在 → 前端还活着 → **跳过**，留给用户自己 stop
- key 不存在 → 前端已消失（刷新/关页面/断网），且超过阈值 → 按孤儿清理

真孤儿仍然会被清理，只是清理的条件从"时间到"变成"时间到 **且** 前端已消失"。
心跳 key 在 stop-recording / cancel-recording / merge 完成后由上层清掉，
避免残留导致真孤儿永远不清。
"""

from __future__ import annotations

import logging
import time

logger = logging.getLogger("microbubble.recording_heartbeat")

# 心跳 key 前缀
HEARTBEAT_KEY_TMPL = "meeting:recording:heartbeat:{meeting_id}"

# TTL(秒)。前端每 60s 上报一次，给 5 倍冗余：容忍 4 次连续丢包/抖动。
HEARTBEAT_TTL_SECONDS = 300


def heartbeat_key(meeting_id: int) -> str:
    return HEARTBEAT_KEY_TMPL.format(meeting_id=meeting_id)


async def _get_client():
    """独立短连接客户端（心跳是低频调用，不占用连接池配额）。"""
    import redis.asyncio as aioredis
    from app.config import settings
    return aioredis.from_url(settings.REDIS_URL, decode_responses=True)


async def touch_recording_heartbeat(meeting_id: int) -> bool:
    """上报一次录音心跳。失败不抛错（心跳是 best-effort，不能拖垮录音主流程）。"""
    client = None
    try:
        client = await _get_client()
        await client.set(heartbeat_key(meeting_id), str(int(time.time())), ex=HEARTBEAT_TTL_SECONDS)
        return True
    except Exception as e:  # noqa: BLE001 — 心跳失败不影响录音
        logger.warning(f"录音心跳写入失败 (会议 {meeting_id}): {e}")
        return False
    finally:
        if client is not None:
            try:
                await client.aclose()
            except Exception:  # noqa: BLE001
                pass


async def is_recording_alive(meeting_id: int, redis_client=None) -> bool:
    """查询会议是否有存活心跳。

    Args:
        meeting_id: 会议 ID
        redis_client: 可选的复用客户端（Celery 任务里已有连接，避免重复建连）。
                      不传则内部建临时连接。

    查询失败时**返回 True**（保守策略）—— 宁可漏清一个孤儿，也不误杀一场
    正在进行的真实会议。误杀的代价是丢失整场录音（09-14 事故），
    漏清的代价只是让一条 error 记录多留一会儿（可人工清理）。
    """
    own_client = False
    client = redis_client
    try:
        if client is None:
            client = await _get_client()
            own_client = True
        exists = await client.exists(heartbeat_key(meeting_id))
        return bool(exists)
    except Exception as e:  # noqa: BLE001 — 查询失败 → 保守判定为活着
        logger.warning(f"录音心跳查询失败 (会议 {meeting_id}), 保守判定为存活: {e}")
        return True
    finally:
        if own_client and client is not None:
            try:
                await client.aclose()
            except Exception:  # noqa: BLE001
                pass


async def clear_recording_heartbeat(meeting_id: int, redis_client=None) -> bool:
    """清除心跳 key（录音正常结束时调用，避免残留）。"""
    own_client = False
    client = redis_client
    try:
        if client is None:
            client = await _get_client()
            own_client = True
        deleted = await client.delete(heartbeat_key(meeting_id))
        return bool(deleted)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"录音心跳清除失败 (会议 {meeting_id}): {e}")
        return False
    finally:
        if own_client and client is not None:
            try:
                await client.aclose()
            except Exception:  # noqa: BLE001
                pass
