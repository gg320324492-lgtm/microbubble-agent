"""Drive v2 PR10 — @ Mention 解析器 (2026-07-24)

W68 第 4 批 drive-pr9-permissions 报告留 "PR10 评论 mention 提醒 (TODO F-1):
不在 DrivePermissionService 范围, 留给 WS notification PR". 本模块补齐.

职责:
- 解析 comment content 文本里的 @username (同 PR6 comment_service 的 regex)
- 查 members 表, 用 3 路匹配 (username / wechat_id / name) 拿到 user_id
  (与 PR6 comment_service.create_comment 步骤 3 一致, 防 username 大小写歧义)
- 返回 user_id list (去重, 不含 author 自己)

复用现有 utilities:
- app.services.notification_service._MENTION_PATTERN (复用, 不重写)
- app.services.notification_service.parse_mentions_from_text (复用, 但**不**用它的 DB 解析)
  — 我们需要自己的 DB 查询 (复用 caller 的 db session)

调用方 (drive_comment_service.create_comment):
```python
from app.services.mention_parser import parse_mentions

mentioned_ids = await parse_mentions(self.db, content, exclude_user_id=author_id)
# mentioned_ids: List[int] (去重 + 排除 author)
for uid in mentioned_ids:
    payload = {...}
    await publish_comment_mention(db, comment, uid, author_id, snippet=payload["snippet"])
```

设计要点 (锚点范式:
- W68 第 5 批 drive-v2-pr9-mention 第 63 守恒):
1. **复用 _MENTION_PATTERN** — 避免 regex 分叉 (前端的 markdown 解析 + 后端提取
   都应一致), 用 notification_service 的 _MENTION_PATTERN 常量。
2. **3 路匹配大小写不敏感** — username / wechat_id 取 .lower(), name 用精确匹配
   (中文名特殊). 与 PR6 comment_service 一致.
3. **不阻塞主流程** — 解析在 commit 之前跑 (mentions ARRAY 字段入库), WS 推送
   在 commit 之后 (best-effort, 失败 swallow + logger.error).
4. **去重 + 排除 self** — 同一用户多次 @ 走 dedup; @自己的也跳过 (PR6 已建, 本模块继承).
5. **复用 caller db session** — 不新开 session (跨 event loop 安全, 与 PR9 一致).

边界:
- 不持久化 file_mention 表 (留给 PR6 notification_service.create_bulk_mentions 走老路径)
- **不**直接 push WS (交给 drive_event_publisher.publish_comment_mention 集中管理)
- 解析失败 (DB 查询抛错) → 返 [], 不阻塞 comment 创建 (与 PR6 防御性一致)
"""
from __future__ import annotations

import logging
import re
from typing import List

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.member import Member
from app.services.notification_service import _MENTION_PATTERN

logger = logging.getLogger("microbubble.mention_parser")


# Matches the exact regex used in PR6 comment_service — single source of truth
# so the front-end markdown rendering and backend extraction never disagree.
# _MENTION_PATTERN is imported from notification_service at module level to
# guarantee a single definition across the codebase.


async def parse_mentions(
    db: AsyncSession,
    text: str,
    *,
    exclude_user_id: int | None = None,
) -> List[int]:
    """解析 @username 字符串 → user_id 列表 (去重, 不含 author 自己)

    Args:
        db: caller 的 AsyncSession (复用, 不新开)
        text: comment content (Markdown 原文)
        exclude_user_id: 要排除的 user_id (通常是 author, 防止自 @)

    Returns:
        List[int]: 提到的 user_id 列表 (按出现在 text 中的顺序去重)

    设计:
    1. regex 提取 raw mentions → List[str] (e.g. ["Alice", "张三", "nuyoah."])
    2. 一次性 SELECT Member.id, Member.username, Member.wechat_id, Member.name
       WHERE 三路匹配 (lower() for ASCII, 精确 for 中文 name).
       — 走 caller 的 db session, 1 次 SQL 查询.
    3. dict 遍历 usernames → user_id (按 username/wechat_id/name 三路优先级).
    4. 去重 + 排除 exclude_user_id + 排除 0.

    错误处理:
    - 空 text → 返 []
    - regex 无命中 → 返 []
    - DB 查询抛错 → logger.warning + 返 [] (与 PR6 防御性一致, 不阻塞 comment 创建)
    """
    if not text or not text.strip():
        return []

    # 1) regex 提取
    raw_usernames = list(set(_MENTION_PATTERN.findall(text)))
    if not raw_usernames:
        return []

    # 2) 一次性查 members (3 路匹配)
    #    与 PR6 comment_service.create_comment 步骤 3 完全一致的 lookup 策略
    try:
        # lower() usernames for case-insensitive match; 中文名走精确 (原样)
        # 这意味着 Pydantic 校验层应确保不会传 raw usernames 太长攻击 (regex 上限 32 char 防御)
        lowered = [u.lower() for u in raw_usernames]
        # Build OR condition: lower(username) IN lowered OR lower(wechat_id) IN lowered OR name IN raw
        # 注意: username/wechat_id 是 String(50)/(100), name 是 String(50), 支持中英文
        stmt = select(
            Member.id, Member.username, Member.wechat_id, Member.name
        ).where(
            or_(
                # username 走 lowercase 比较 (PostgreSQL `lower()` 函数)
                func.lower(Member.username).in_(lowered),
                # wechat_id 走 lowercase 比较 (与 alembic 054 唯一索引保持一致)
                func.lower(Member.wechat_id).in_(lowered),
                # name 精确匹配 (中英文混合, case-sensitive for Chinese chars)
                Member.name.in_(raw_usernames),
            )
        )
        rows = (await db.execute(stmt)).all()
    except Exception as e:
        logger.warning(
            f"[MentionParser] DB 查询失败, 返 [] (defensive, 不阻塞 comment): {e!r}",
            exc_info=True,
        )
        return []

    # 3) build dict (优先级: username > wechat_id > name — 与 PR6 一致)
    id_by_username: dict[str, int] = {}
    id_by_wechat_id: dict[str, int] = {}
    id_by_name: dict[str, int] = {}
    for member_id, username, wechat_id, name in rows:
        if username:
            id_by_username[username.lower()] = member_id
        if wechat_id:
            id_by_wechat_id[wechat_id.lower()] = member_id
        if name:
            id_by_name[name] = member_id

    # 4) 顺序遍历 raw_usernames (按出现顺序去重), 用 username > wechat_id > name 优先级
    seen: set[int] = set()
    result: List[int] = []
    for username in raw_usernames:
        uid = (
            id_by_username.get(username.lower())
            or id_by_wechat_id.get(username.lower())
            or id_by_name.get(username)
        )
        if uid is None:
            continue
        if uid in seen:
            continue
        if exclude_user_id is not None and uid == exclude_user_id:
            continue  # 自 @
        seen.add(uid)
        result.append(uid)

    return result


def extract_snippet(text: str, *, max_chars: int = 80) -> str:
    """提取 comment content 摘要 (供 push payload 用)

    Args:
        text: comment content
        max_chars: 最大字符数 (默认 80, 与 push 卡片宽度匹配)

    Returns:
        str: 截取后的纯文本 (保留换行, 但去掉多余空白)

    用途:
    - drive_event_publisher.publish_comment_mention 的 `snippet` 字段
    - 前端 NotificationBell 卡片 2 行省略号
    """
    if not text:
        return ""
    # 去除首尾空白 + 多余换行折叠
    cleaned = re.sub(r"\s+", " ", text.strip())
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[:max_chars] + "..."


__all__ = [
    "parse_mentions",
    "extract_snippet",
]
