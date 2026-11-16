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
from typing import Any, Optional

logger = logging.getLogger("microbubble.recording_heartbeat")

# 心跳 key 前缀
HEARTBEAT_KEY_TMPL = "meeting:recording:heartbeat:{meeting_id}"

# TTL(秒)。前端每 60s 上报一次，给 5 倍冗余：容忍 4 次连续丢包/抖动。
HEARTBEAT_TTL_SECONDS = 300

# 上传收尾宽限窗口。心跳 key 自身 TTL 仍是 300s；这里额外允许 600s 是为了覆盖
# 「前端停止计时 → 分片持续上传 → 触发 merge」这段可能超过 TTL 的时间。
UPLOAD_FINALIZING_GRACE_SECONDS = 600
_FINALIZING_PHASES = frozenset({"finalizing", "uploading"})


def heartbeat_key(meeting_id: int) -> str:
    return HEARTBEAT_KEY_TMPL.format(meeting_id=meeting_id)


async def _get_client():
    """独立短连接客户端（心跳是低频调用，不占用连接池配额）。"""
    import redis.asyncio as aioredis
    from app.config import settings
    return aioredis.from_url(settings.REDIS_URL, decode_responses=True)


def _parse_heartbeat_value(raw: Any) -> Optional[dict]:
    """解析 Redis value，兼容旧版纯时间戳字符串。"""
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None

    session_id = ""
    phase = ""
    ts_text = text
    if "|" in text:
        parts = text.split("|", 2)
        ts_text = parts[0].strip()
        session_id = parts[1].strip() if len(parts) > 1 else ""
        phase = parts[2].strip() if len(parts) > 2 else ""

    try:
        ts = float(ts_text)
    except (TypeError, ValueError):
        return None
    return {
        "ts": ts,
        "session_id": session_id,
        "phase": phase,
        "raw": text,
    }


async def touch_recording_heartbeat(
    meeting_id: int,
    session_id: Optional[str] = None,
    phase: Optional[str] = None,
) -> bool:
    """上报一次录音心跳。失败不抛错（心跳是 best-effort，不能拖垮录音主流程）。

    Redis value 使用 `ts|session_id|phase`（旧版纯 ts 可读但不再写出）。
    phase=recording 时 TTL 300s（前端每 60s 一次，容忍 4 次丢包）；
    phase=finalizing/uploading 时 TTL 用 UPLOAD_FINALIZING_GRACE_SECONDS(600)，
    这样 key 本身就能撑过"停止计时 → 分片继续上传 → merge"的收尾期，
    `is_upload_finalizing` 再按同一个 600s 新鲜窗口判孤儿清理宽限。
    """
    client = None
    try:
        value = f"{int(time.time())}|{session_id or ''}|{phase or ''}"
        ttl = (
            UPLOAD_FINALIZING_GRACE_SECONDS
            if phase in _FINALIZING_PHASES
            else HEARTBEAT_TTL_SECONDS
        )
        client = await _get_client()
        await client.set(heartbeat_key(meeting_id), value, ex=ttl)
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


async def _get_client_if_needed(redis_client=None):
    """返回 (client, owns_client)；调用方负责关闭 own client。"""
    if redis_client is not None:
        return redis_client, False
    return await _get_client(), True


async def read_recording_heartbeat(meeting_id: int, redis_client=None) -> Optional[dict]:
    """读取并解析心跳。任何读取/解析失败都返回 None（调用方自行决定保守策略）。"""
    client = None
    own_client = False
    try:
        client, own_client = await _get_client_if_needed(redis_client)
        raw = await client.get(heartbeat_key(meeting_id))
        return _parse_heartbeat_value(raw)
    except Exception as e:  # noqa: BLE001 — 查询失败与"没有心跳"都返回 None
        logger.warning(f"录音心跳读取失败 (会议 {meeting_id}): {e}")
        return None
    finally:
        if own_client and client is not None:
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
        try:
            raw = await client.get(heartbeat_key(meeting_id))
        except TypeError:
            # 兼容只实现了 exists 的旧版/测试 stub：get 不可用时退回旧判据。
            # 真实 aioredis 客户端不会走这里。
            exists = await client.exists(heartbeat_key(meeting_id))
            return bool(exists)
        hb = _parse_heartbeat_value(raw)
        if hb is None:
            return False
        phase = hb["phase"] or "recording"
        session_id = hb["session_id"]
        # 窗口按 phase 分档：收尾心跳用 600s，普通录音心跳用 300s。
        # 只 exists 会把"值已过期但 key 还没被 Redis 回收"误判成活着。
        fresh_window = (
            UPLOAD_FINALIZING_GRACE_SECONDS
            if phase in _FINALIZING_PHASES
            else HEARTBEAT_TTL_SECONDS
        )
        age = time.time() - hb["ts"]
        alive = hb["ts"] > 0 and -1 <= age <= fresh_window
        logger.debug(
            "录音心跳判活 会议=%s alive=%s phase=%s session_id=%s age=%.1fs window=%ss",
            meeting_id, alive, phase, session_id, age, fresh_window,
        )
        return alive
    except Exception as e:  # noqa: BLE001 — 查询失败 → 保守判定为活着
        logger.warning(f"录音心跳查询失败 (会议 {meeting_id}), 保守判定为存活: {e}")
        return True
    finally:
        if own_client and client is not None:
            try:
                await client.aclose()
            except Exception:  # noqa: BLE001
                pass


async def is_upload_finalizing(meeting_id: int, redis_client=None) -> bool:
    """心跳 phase 为 finalizing/uploading 且时间戳在 600s 内时返回 True。

    用于孤儿清理的额外宽限：上传/合并尚未收尾时绝不判死。
    Redis 异常时返回 False（由 `is_recording_alive` 的保守 True 继续兜底）。
    """
    hb = await read_recording_heartbeat(meeting_id, redis_client=redis_client)
    if not hb:
        return False
    if hb["phase"] not in _FINALIZING_PHASES:
        return False
    if hb["ts"] <= 0 or (time.time() - hb["ts"]) > UPLOAD_FINALIZING_GRACE_SECONDS:
        return False
    return True


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
