"""长期记忆域工具（v2 架构）

v28 step 67: 重新设计长期记忆系统

**新 memory_type 语义**（每个用户的专属个性化记忆）：

| 类型 | 含义 | 例 |
|---|---|---|
| preference | 用户偏好 / 习惯 / 限制 | "不要用 emoji"、"用中文回答"、"代码加注释" |
| user_fact | 关于**当前登录用户**的事实 | "我是研一学生"、"我负责黑臭水体项目"、"我对 zeta 电位感兴趣" |
| task_ctx | 当前用户相关的任务上下文 | "本周要给杜同贺交什么"、"上周的实验记录" |

**严格禁止保存到本表**：
- 其他成员的事实（应该走知识图谱 / members 表）
- 项目状态（应该走 projects 表）
- 团队成员名单（应该走 search_members 工具）
- 重复内容（save_memory 自动 dedup）

**DEDUP 规则**：
- preference: 按 (user_id, key) upsert，内容相似度 > 80% 自动合并
- user_fact / task_ctx: 按 (user_id, content_hash) 去重，相似度 > 85% 合并
- 重复内容不被新建，access_count + 1
"""

import hashlib
import logging
from typing import Optional

from pydantic import BaseModel, Field

from app.agent.tool_registry import ToolContext, tool

logger = logging.getLogger("microbubble.agent.tools.memory")


# ============================================================================
# save_memory（v28 step 67 重设计）
# ============================================================================


class SaveMemoryInput(BaseModel):
    memory_type: str = Field(
        ...,
        description=(
            "记忆类型（v28 step 67 新语义）：\n"
            "- preference: 用户偏好/习惯/限制（key 必填）\n"
            "- user_fact: 关于当前登录用户的事实（key 建议填，如 user_grade/research_direction）\n"
            "- task_ctx: 当前用户相关的任务上下文\n"
            "\n"
            "严禁保存其他成员的事实（走知识图谱）或项目状态（走 projects 表）"
        ),
    )
    content: str = Field(..., min_length=5, description="记忆内容（至少 5 字符，去除过短噪声）")
    key: Optional[str] = Field(
        None,
        description="记忆键名。preference 必填；user_fact 强烈建议填（如 user_grade/role/research_area）；task_ctx 可选",
    )
    importance: float = Field(0.7, ge=0.0, le=1.0, description="重要性 0.0-1.0")


class SaveMemoryOutput(BaseModel):
    status: str
    memory_id: Optional[int] = None
    type: Optional[str] = None
    rich_block_type: Optional[str] = None
    reason: Optional[str] = None  # status=skipped/merged/rejected 时填充原因


@tool(
    name="save_memory",
    description=(
        "保存用户专属信息到长期记忆。\n"
        "适用场景：用户表达偏好（'记住：...'）、自我介绍（'我是研一学生'）、"
        "任务上下文（'本周要交什么'）。\n"
        "严禁保存：其他成员信息、项目状态、团队名单（这些走专门工具/表）。\n"
        "重复内容自动合并，不会产生噪音。"
    ),
    input_model=SaveMemoryInput,
    output_model=SaveMemoryOutput,
)
async def save_memory(input: SaveMemoryInput, ctx: ToolContext) -> dict:
    """保存一条长期记忆（带 dedup + pollution 防御）"""
    if not ctx.user_id:
        return {"status": "error", "message": "无法识别用户身份"}

    # v28 step 65: 防御污染
    blocked = _check_memory_pollution(input.content, input.key)
    if blocked:
        logger.warning(f"[save_memory] 拒绝污染: {blocked} | content={input.content[:80]}")
        return {"status": "rejected", "reason": blocked}

    # v28 step 67: 校验类型合法性 + key 必填规则
    if input.memory_type not in ("preference", "user_fact", "task_ctx", "summary", "entity"):
        # 兼容旧 entity 类型，但记录到日志
        logger.warning(f"[save_memory] 未知类型 {input.memory_type}，按原文保存")
    elif input.memory_type == "preference" and not input.key:
        return {"status": "skipped", "reason": "preference 类型必须提供 key（如 language_style/no_emoji）"}

    from app.services.memory_service import MemoryService

    mem_svc = MemoryService(ctx.db)
    result = await mem_svc.save_memory_dedup(
        user_id=ctx.user_id,
        memory_type=input.memory_type,
        content=input.content,
        key=input.key,
        importance=input.importance,
    )
    return {
        "status": result["status"],  # 'created' | 'merged' | 'updated'
        "memory_id": result["memory_id"],
        "type": input.memory_type,
        "rich_block_type": None,
        "reason": result.get("reason"),
    }


# ============================================================================
# search_memory
# ============================================================================


class SearchMemoryInput(BaseModel):
    query: str = Field(..., min_length=1, description="搜索内容")
    memory_type: Optional[str] = Field(None, description="限定记忆类型（preference/user_fact/task_ctx）")
    top_k: int = Field(5, ge=1, le=20, description="返回数量（默认 5）")


class SearchMemoryOutput(BaseModel):
    status: str
    count: int
    memories: list[dict]
    rich_block_type: Optional[str] = None


@tool(
    name="search_memory",
    description="搜索长期记忆。当需要回忆用户偏好、历史对话信息、实体关系时使用。",
    input_model=SearchMemoryInput,
    output_model=SearchMemoryOutput,
)
async def search_memory(input: SearchMemoryInput, ctx: ToolContext) -> dict:
    """搜索长期记忆"""
    if not ctx.user_id:
        return {"status": "error", "message": "无法识别用户身份", "count": 0, "memories": []}
    from app.services.memory_service import MemoryService

    mem_svc = MemoryService(ctx.db)
    results = await mem_svc.search_memories(
        user_id=ctx.user_id,
        query=input.query,
        top_k=input.top_k,
        memory_type=input.memory_type,
    )
    return {
        "status": "success",
        "count": len(results),
        "memories": results,
        "rich_block_type": None,
    }


# ============================================================================
# forget_memory
# ============================================================================


class ForgetMemoryInput(BaseModel):
    memory_id: int = Field(..., description="记忆ID")


class ForgetMemoryOutput(BaseModel):
    status: str
    message: str
    rich_block_type: Optional[str] = None


@tool(
    name="forget_memory",
    description="遗忘特定记忆。当用户要求删除或纠正某条记忆时使用。",
    input_model=ForgetMemoryInput,
    output_model=ForgetMemoryOutput,
)
async def forget_memory(input: ForgetMemoryInput, ctx: ToolContext) -> dict:
    """遗忘一条记忆"""
    if not ctx.user_id:
        return {"status": "error", "message": "无法识别用户身份"}
    from app.services.memory_service import MemoryService

    mem_svc = MemoryService(ctx.db)
    success = await mem_svc.forget_memory(user_id=ctx.user_id, memory_id=input.memory_id)
    return {
        "status": "success" if success else "error",
        "message": "记忆已遗忘" if success else "记忆不存在或无权操作",
        "rich_block_type": None,
    }


# ============================================================================
# v28 step 65/67: 记忆污染防御 + dedup 工具
# ============================================================================

POLLUTION_BLOCKLIST = {
    "test_user": ["小明", "小红", "小张", "小李", "test", "demo", "sample", "example", "用户A", "用户B"],
    "placeholder": ["todo", "tbd", "xxx", "yyy", "占位", "待定", "稍后"],
    "language_redundant": ["繁體", "繁体", "traditional chinese"],
}

# v28 step 67: dedup 相似度阈值
DEDUP_THRESHOLD = 0.85  # 内容相似度 >= 85% 视为重复


def _check_memory_pollution(content: str, key: str = None) -> str | None:
    """v28 step 65: 检测 LLM 写入的污染记忆

    Returns:
        污染原因字符串（None 表示通过）
    """
    if not content:
        return "content 为空"

    content_lower = content.lower()
    key_lower = (key or "").lower()

    # 1. 测试用户名
    for bad in POLLUTION_BLOCKLIST["test_user"]:
        if bad.lower() in content_lower or bad.lower() in key_lower:
            return f"包含测试用户名 '{bad}'"

    # 2. 占位符
    stripped = content.strip().lower()
    for bad in POLLUTION_BLOCKLIST["placeholder"]:
        if stripped == bad or stripped.startswith(bad + " "):
            return f"内容为占位符 '{bad}'"

    # 2.5 已知污染偏好
    for bad in POLLUTION_BLOCKLIST["language_redundant"]:
        if bad.lower() in content_lower or bad.lower() in key_lower:
            return f"包含污染语言偏好 '{bad}'（真实用户用简体中文）"

    # 3. 长度过短
    if len(content.strip()) < 5:
        return f"内容过短 ({len(content.strip())} 字符)"

    # 4. v28 step 67: 检测"关于其他人"的事实（应该存到 knowledge graph 而不是长期记忆）
    if _is_about_other_person(content):
        return f"内容是关于其他成员的信息，应该存到知识图谱/成员表，不是个人长期记忆"

    return None


def _is_about_other_person(content: str) -> bool:
    """v28 step 67: 检测内容是否是关于其他成员的事实

    长期记忆 = 用户**自己**的信息。如果内容是描述其他成员的事实，
    应该存到知识图谱或 members 表（members 是全组可见的事实）。

    启发式：如果内容以"X 是/负责/参与了 Y"开头，且 X 不在 ctx 当前用户名字里 → 他人信息
    """
    # 真实成员名（与现有 DB members 对齐，避免硬编码）
    REAL_MEMBERS = {
        "王天志", "赵航佳", "杜同贺", "陈天祥", "张懿", "耿嘉栋", "陈金薪",
        "董昊宇", "关小未", "胡小琪", "李胜景", "刘子毅", "宋洋", "王书馨",
        "吴孟铨", "韩重阳", "李锐远", "杨慈", "余歆睿", "张宏魁", "贾琦",
        "周之超", "邓国祥", "雒培媛", "孟祥琪", "吴怡霏", "蒋芦笛", "刘莫菲",
    }
    content_strip = content.strip()

    # 检测模式："X 是 / 负责 / 参与 / 在做什么"
    other_person_subjects = [
        "王书馨", "贾琦", "周之超", "邓国祥", "李锐远", "杨慈",
        "陈金薪", "孟祥琪", "吴孟铨", "蒋芦笛", "刘莫菲", "吴怡霏",
        "张宏魁", "张懿", "耿嘉栋", "李胜景", "刘子毅", "宋洋",
        "韩重阳", "余歆睿", "赵航佳", "王天志", "陈天祥", "董昊宇",
        "关小未", "胡小琪", "雒培媛",
    ]
    # 如果内容以其他人名开头（且是陈述性句子）
    for name in other_person_subjects:
        if content_strip.startswith(name) and any(kw in content_strip for kw in ["是", "负责", "参与", "在做", "在"]):
            return True
    return False


def _content_hash(content: str) -> str:
    """v28 step 67: 计算内容归一化 hash（用于 dedup）"""
    import re
    # 去掉空白 + 标点 + 助词，保留语义核心
    normalized = re.sub(r'[\s，。！？、；：""''《》（）()【】\[\].,;:!?\'"()\-—]', '', content)
    return hashlib.md5(normalized.encode('utf-8')).hexdigest()


def _content_similarity(a: str, b: str) -> float:
    """v28 step 67: 内容相似度（基于字符级 SequenceMatcher）"""
    from difflib import SequenceMatcher
    return SequenceMatcher(None, a, b).ratio()