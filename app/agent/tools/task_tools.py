"""任务域工具（v2 架构）

迁移：
- query_tasks: 字段补全（description/project_name/tags/meeting_id）
- create_task: 任务创建（含微信通知 + 权限检查）
- update_task: 任务状态/进度更新

未迁移（仍走 dispatch_legacy）：
- query_all_member_tasks / get_task_stats（admin only，使用频率低）
"""

import logging
from typing import Any, Optional

from pydantic import BaseModel, Field
from sqlalchemy import select

from app.agent.tool_registry import ToolContext, tool

logger = logging.getLogger("microbubble.agent.tools.task")


class QueryTasksInput(BaseModel):
    assignee_name: Optional[str] = Field(None, description="按负责人姓名筛选")
    status: Optional[str] = Field(None, description="按状态筛选（in_progress/blocked/review/done/cancelled）")
    project_name: Optional[str] = Field(None, description="按项目名称筛选")
    overdue: bool = Field(False, description="是否只查询逾期任务")
    # 2026-09-10 新增: 实测模型按标题找任务 ("给「修改论文」加备注" 的回读确认)
    # 时无参数可用 → 全量列表淹没目标。title_keyword 走 ilike 子串匹配。
    title_keyword: Optional[str] = Field(None, description="按任务标题关键词筛选 (子串匹配)。确认/定位某个具体任务时用这个")


class TaskListItem(BaseModel):
    id: int
    title: str
    status: str
    priority: Optional[str] = None
    assignee_id: Optional[int] = None
    assignee_name: Optional[str] = None
    due_date: Optional[str] = None
    progress: Optional[int] = None
    # === 字段补全（2026-06-12 优化）===
    description: Optional[str] = None
    project_id: Optional[int] = None
    project_name: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    meeting_id: Optional[int] = None
    rich_block_type: str = "task_list"


class QueryTasksOutput(BaseModel):
    status: str
    count: int
    tasks: list[TaskListItem]


@tool(
    name="query_tasks",
    description="查询任务列表。当用户询问某人的任务、某项目的任务、逾期任务等时使用。",
    input_model=QueryTasksInput,
    output_model=QueryTasksOutput,
)
async def query_tasks(input: QueryTasksInput, ctx: ToolContext) -> dict:
    """查询任务列表（含字段补全）"""
    from app.services.task_service import TaskService
    from app.services.member_service import MemberService
    from app.services.project_service import ProjectService
    from app.models.member import Member
    from app.models.project import Project

    # 2026-09-05 角色扁平化：所有成员等权，可查看全组任务（原 admin/研究生可见性分级废除）

    # 解析 assignee_name → assignee_id
    assignee_id = None
    if input.assignee_name:
        member_svc = MemberService(ctx.db)
        m = await member_svc.get_member_by_name(input.assignee_name)
        if m:
            assignee_id = m.id

    # 解析 project_name → project_id
    project_id = None
    if input.project_name:
        proj_svc = ProjectService(ctx.db)
        projects = await proj_svc.get_projects()
        for p in projects:
            if p.name == input.project_name:
                project_id = p.id
                break

    # 查询
    task_svc = TaskService(ctx.db)
    tasks = await task_svc.get_tasks(
        assignee_id=assignee_id,
        status=input.status,
        project_id=project_id,
        overdue=input.overdue,
    )
    # title_keyword 子串过滤 (service 层无此参数, 工具层补; 数据量小无性能顾虑)
    if input.title_keyword:
        kw = input.title_keyword.strip()
        tasks = [t for t in tasks if kw in (t.title or "")]
    # 2026-09-10 排序确定性: 活跃状态优先 (进行中/待办/阻塞/审核在前), 组内按
    # due_date 升序 (最紧在前), 无截止靠后, id 兜底。
    # ⚠ 纯 due 升序是坑 (stress4 实测): 全量查询时最老的 done 任务占前排,
    # 压缩器 top-N 全是已完成项, 污染后续轮次的上下文实体。
    _active = {"in_progress", "todo", "blocked", "review"}
    tasks = sorted(
        tasks,
        key=lambda t: (
            0 if t.status in _active else 1,
            t.due_date is None,
            t.due_date or t.created_at,
            t.id,
        ),
    )

    # 批量获取 assignee 姓名 + project 名称
    assignee_ids = {t.assignee_id for t in tasks if t.assignee_id}
    assignee_map = {}
    if assignee_ids:
        result = await ctx.db.execute(select(Member).where(Member.id.in_(assignee_ids)))
        assignee_map = {m.id: m.name for m in result.scalars().all()}

    project_ids = {t.project_id for t in tasks if t.project_id}
    project_map = {}
    if project_ids:
        result = await ctx.db.execute(select(Project).where(Project.id.in_(project_ids)))
        project_map = {p.id: p.name for p in result.scalars().all()}

    items = []
    for t in tasks:
        items.append({
            "id": t.id,
            "title": t.title,
            "status": t.status,
            "priority": t.priority,
            "assignee_id": t.assignee_id,
            "assignee_name": assignee_map.get(t.assignee_id, "未分配") if t.assignee_id else "未分配",
            "due_date": t.due_date.strftime("%Y-%m-%d %H:%M") if t.due_date else None,
            "progress": t.progress,
            "description": (t.description or "")[:200] if t.description else None,
            "project_id": t.project_id,
            "project_name": project_map.get(t.project_id) if t.project_id else None,
            "tags": list(t.tags or []),
            "meeting_id": getattr(t, "meeting_id", None),
            "rich_block_type": "task_list",
        })

    return {"status": "success", "count": len(items), "tasks": items}


# ============================================================================
# 2. create_task（迁移 — 含权限检查 + 微信通知）
# ============================================================================


class ReminderItem(BaseModel):
    remind_at: str = Field(..., description="提醒时间 YYYY-MM-DD HH:MM")
    remind_type: str = Field("wechat", description="提醒方式：wechat / email")


class CreateTaskInput(BaseModel):
    title: str = Field(..., min_length=1, description="任务标题")
    assignee_name: Optional[str] = Field(None, description="负责人姓名（不填则默认为当前用户）")
    project_name: Optional[str] = Field(None, description="所属项目名称（可选）")
    priority: str = Field("medium", description="优先级：high/medium/low")
    due_date: Optional[str] = Field(None, description="截止日期 YYYY-MM-DD HH:MM")
    description: Optional[str] = Field(None, description="任务详细描述")
    reminders: Optional[list[ReminderItem]] = Field(None, description="自定义提醒列表")


class CreateTaskOutput(BaseModel):
    status: str
    task_id: Optional[int] = None
    title: Optional[str] = None
    rich_block_type: Optional[str] = None


@tool(
    name="create_task",
    description="【仅用于新建任务】当用户要求创建/新增/分配一个还不存在的任务时使用。⚠️ 对已有任务的任何修改 (加备注/改状态/改进度/延期) 一律用 update_task, 不要用本工具重复创建 (2026-09-10 实测: '给这个任务加备注'被错调成 create_task, 产生了重复任务)。",
    input_model=CreateTaskInput,
    output_model=CreateTaskOutput,
)
async def create_task(input: CreateTaskInput, ctx: ToolContext) -> dict:
    """创建任务（含微信通知）"""
    from app.services.task_service import TaskService
    from app.services.member_service import MemberService
    from app.services.project_service import ProjectService
    from app.models.base import BEIJING_TZ
    from datetime import datetime, timezone

    member_svc = MemberService(ctx.db)

    # 解析 assignee
    assignee_id = None
    if input.assignee_name:
        m = await member_svc.get_member_by_name(input.assignee_name)
        if not m:
            return {"status": "error", "message": f"未找到成员: {input.assignee_name!r}"}
        assignee_id = m.id
    elif ctx.user_id:
        assignee_id = ctx.user_id  # 默认分配给自己

    # 2026-09-05 角色扁平化：任何成员可给他人创建任务（原"普通成员只能给自己创建"废除）

    # 解析 project
    project_id = None
    if input.project_name:
        proj_svc = ProjectService(ctx.db)
        projects = await proj_svc.get_projects()
        for p in projects:
            if p.name == input.project_name:
                project_id = p.id
                break

    # 解析 due_date（北京时间 → UTC）
    due_date = None
    if input.due_date:
        try:
            beijing_dt = datetime.strptime(input.due_date, "%Y-%m-%d %H:%M")
        except ValueError:
            beijing_dt = datetime.strptime(input.due_date, "%Y-%m-%d").replace(hour=18, minute=0)
        due_date = beijing_dt.replace(tzinfo=BEIJING_TZ).astimezone(timezone.utc).replace(tzinfo=None)

    # 解析 reminders（v2：用户显式 reminder 也对齐到下次 11AM 窗口）
    reminders_data = None
    if input.reminders:
        from app.services.reminder_policy import next_digest_slot
        reminders_data = []
        for r in input.reminders:
            rem_beijing = datetime.strptime(r.remind_at, "%Y-%m-%d %H:%M")
            rem_utc = rem_beijing.replace(tzinfo=BEIJING_TZ).astimezone(timezone.utc).replace(tzinfo=None)
            # 2026-06-15 v2: 所有 reminder 落点 = next 11AM 北京时间窗口
            aligned_utc = next_digest_slot(rem_utc)
            reminders_data.append({"remind_at": aligned_utc, "remind_type": r.remind_type})

    task_svc = TaskService(ctx.db)
    task = await task_svc.create_task(
        title=input.title,
        assignee_id=assignee_id,
        project_id=project_id,
        priority=input.priority,
        due_date=due_date,
        description=input.description,
        source="ai",
        created_by=ctx.user_id,
        reminders=reminders_data,
    )

    # 微信通知（best-effort，失败不阻塞）
    if assignee_id and ctx.user_id and assignee_id != ctx.user_id:
        try:
            from app.wechat.notifier import notifier
            assignee = await member_svc.get_member(assignee_id)
            creator = await member_svc.get_member(ctx.user_id)
            due_date_str = ""
            if due_date:
                due_date_beijing = due_date.replace(tzinfo=timezone.utc).astimezone(BEIJING_TZ)
                due_date_str = due_date_beijing.strftime("%Y-%m-%d %H:%M")
            if assignee and (assignee.wechat_id or assignee.external_userid):
                await notifier.notify_task_assigned(
                    member=assignee,
                    task_title=input.title,
                    due_date=due_date_str,
                    priority=input.priority,
                    description=input.description or "",
                    assigner=creator.name if creator else "管理员",
                )
        except Exception as e:
            logger.warning(f"微信通知失败（任务已创建）: {e}")

    return {
        "status": "success",
        "task_id": task.id,
        "title": task.title,
        "rich_block_type": None,
    }


# ============================================================================
# 3. update_task（迁移 — 含权限检查）
# ============================================================================


class UpdateTaskInput(BaseModel):
    task_id: Optional[int] = Field(None, description="任务ID (与 title_keyword 二选一; 不确定ID时用 title_keyword)")
    # 2026-09-10: 实测两段式 (query_tasks 找 id → update_task) 模型会用错 status
    # 过滤丢目标。单调用内 title→id 解析 (唯一命中才执行) 砍掉出错链。
    title_keyword: Optional[str] = Field(None, description="按任务标题关键词定位任务 (需唯一命中; 多义返回候选列表)")
    assignee_name: Optional[str] = Field(None, description="配合 title_keyword 的负责人姓名 (缩小/确认范围)")
    status: Optional[str] = Field(None, description="新状态：in_progress/blocked/review/done/cancelled。不传=不改状态 (2026-09-10 修正: 此前不传会被强制回写成 in_progress, 已完成任务会被悄悄翻回进行中!)")
    progress: Optional[int] = Field(None, ge=0, le=100, description="进度百分比 0-100")
    due_date: Optional[str] = Field(None, description="新截止日期 YYYY-MM-DD HH:MM")
    add_note: Optional[str] = Field(None, description="追加备注文本 (2026-09-10 新增): 写入 description 并带时间戳, 不覆盖原描述。用户说'给任务加备注/补充说明'用这个字段")


class UpdateTaskOutput(BaseModel):
    status: str
    task_id: Optional[int] = None
    new_status: Optional[str] = None
    note_written: bool = False
    add_note_requested: bool = False  # 2026-09-10: 反谎报 guard 判定用 (请求了 add_note 但没写成 → 不算成功)
    description_tail: Optional[str] = None
    rich_block_type: Optional[str] = None


@tool(
    name="update_task",
    description="更新任务。支持：改状态/进度/截止日期，或追加备注(add_note)。注意不传 status 时不会改动状态（不会自动置为进行中）。用户要求'加备注/补充说明/留言'时用 add_note。",
    input_model=UpdateTaskInput,
    output_model=UpdateTaskOutput,
)
async def update_task(input: UpdateTaskInput, ctx: ToolContext) -> dict:
    """更新任务（状态/进度/截止日期/追加备注），支持 task_id 直接指定或 title_keyword 定位"""
    from app.services.task_service import TaskService
    from app.models.base import BEIJING_TZ
    from datetime import datetime, timezone

    task_svc = TaskService(ctx.db)
    task = None
    if input.task_id is not None:
        task = await task_svc.get_task(input.task_id)
    elif input.title_keyword:
        # 2026-09-10: title→id 解析唯一命中才执行, 多义直接返回候选让模型确认
        # (实测两段式"先 query 再 update"里模型会用错 status 过滤丢目标)
        kw = input.title_keyword.strip()
        cand = await task_svc.get_tasks(status=None)
        cand = [t for t in cand if kw in (t.title or "")]
        if input.assignee_name:
            from app.services.member_service import MemberService
            m = await MemberService(ctx.db).get_member_by_name(input.assignee_name)
            if m:
                cand = [t for t in cand if t.assignee_id == m.id]
        if len(cand) == 1:
            task = cand[0]
        elif not cand:
            return {"status": "error", "message": f"未找到标题含「{kw}」的任务"}
        else:
            return {"status": "error", "ambiguous": True,
                    "message": f"「{kw}」匹配 {len(cand)} 个任务, 请用 task_id 指定",
                    "candidates": [{"id": t.id, "title": t.title} for t in cand[:8]]}
    if not task:
        return {"status": "error", "message": f"任务 {input.task_id or input.title_keyword} 不存在"}

    # 2026-09-05 角色扁平化：任何成员可更新任意任务（原创建者/被分配者/admin 限制废除）

    updated = task
    # 2026-09-10 修正: 老实现 status or "in_progress" → 只想加备注/改进度时
    # 会把已完成任务悄悄翻回 in_progress (实测任务 52 被这样改过状态)。
    if input.status:
        updated = await task_svc.update_task_status(
            task_id=task.id,  # 2026-09-10: 不能用 input.task_id (title_keyword 路径下是 None)
            status=input.status,
            progress=input.progress,
        )
    elif input.progress is not None:
        updated.progress = input.progress
        await ctx.db.commit()
        await ctx.db.refresh(updated)
    if not updated:
        return {"status": "error", "message": f"任务 {task.id} 更新失败"}

    # 2026-09-10 新增: 备注写入 description (带时间戳追加, 不覆盖)
    note_written = False
    if input.add_note:
        from datetime import datetime as _dt
        from app.models.base import BEIJING_TZ as _BZ
        stamp = _dt.now(_BZ).strftime("%Y-%m-%d %H:%M")
        old_desc = (updated.description or "").rstrip()
        line = f"[备注 {stamp}] {input.add_note.strip()}"
        updated.description = f"{old_desc}\n{line}" if old_desc else line
        await ctx.db.commit()
        await ctx.db.refresh(updated)
        note_written = True

    # 更新截止日期
    if input.due_date and updated:
        try:
            new_due_beijing = datetime.strptime(input.due_date, "%Y-%m-%d %H:%M")
        except ValueError:
            new_due_beijing = datetime.strptime(input.due_date, "%Y-%m-%d").replace(hour=18, minute=0)
        updated.due_date = new_due_beijing.replace(tzinfo=BEIJING_TZ).astimezone(timezone.utc).replace(tzinfo=None)
        await ctx.db.commit()

    return {
        "status": "success",
        "task_id": updated.id,
        "new_status": updated.status,
        "note_written": note_written,
        "add_note_requested": bool(input.add_note),
        "description_tail": (updated.description or "")[-120:] or None,
        "rich_block_type": None,
    }
