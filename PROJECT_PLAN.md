# 微纳米气泡课题组智能Agent系统 - 完整规划文档

## 一、项目概述

### 1.1 项目背景

微纳米气泡课题组现有20余名成员，涵盖多个研究方向（气泡生成、水处理应用、农业应用等）。日常管理面临以下痛点：

- 文献阅读效率低，知识难以共享
- 实验记录分散，数据管理混乱
- 任务分配靠口头，进度难以追踪
- 会议记录靠人工，容易遗漏关键信息
- 新人上手慢，知识传承困难

### 1.2 项目目标

构建一个**课题组专属智能Agent系统**，实现：

1. **智能对话** — 支持文字/语音与Agent交互，随时查询信息
2. **任务管理** — 自动分配任务、智能提醒、进度追踪
3. **会议助手** — 自动旁听会议、实时转写、生成纪要、提取任务
4. **知识管理** — 文献管理、实验记录、知识库沉淀
5. **数据分析** — 实验数据处理、可视化、统计分析
6. **自动规划** — 根据会议内容自动生成项目计划

### 1.3 目标用户

| 角色 | 使用场景 |
|------|---------|
| 导师 | 查看整体进度、分配任务、审阅会议纪要 |
| 博士生 | 课题管理、文献调研、数据分析 |
| 硕士生 | 实验记录、任务提醒、知识学习 |
| 本科生 | 毕设管理、基础知识查询 |

---

## 二、系统架构

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                          用户交互层                                  │
│                                                                     │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────────┐   │
│  │  微信小程序 │  │  Web 界面  │  │  语音通话   │  │ 腾讯会议接入  │   │
│  │  (主入口)   │  │ (管理后台)  │  │ (实时对话)  │  │ (会议旁听)   │   │
│  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘  └──────┬────────┘   │
└────────┼───────────────┼───────────────┼───────────────┼────────────┘
         │               │               │               │
         └───────────────┴───────┬───────┴───────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────────┐
│                          API 网关层                                  │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    Nginx (反向代理 + SSL)                     │   │
│  │                    WebSocket 支持                            │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────────┐
│                          业务服务层                                  │
│                                                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                │
│  │  对话服务    │  │  任务服务    │  │  会议服务    │                │
│  │  ChatService │  │  TaskService │  │ MeetingSvc  │                │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                │
│         │                │                │                        │
│  ┌──────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐                │
│  │  语音服务    │  │  知识服务    │  │  规划服务    │                │
│  │  VoiceService│  │  KnowledgeSvc│  │  PlannerSvc │                │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                │
└─────────┼────────────────┼────────────────┼────────────────────────┘
          │                │                │
┌─────────▼────────────────▼────────────────▼────────────────────────┐
│                          核心引擎层                                  │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                      Claude API Agent                        │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │   │
│  │  │ 对话理解  │  │ 任务规划  │  │ 会议分析  │  │ 知识检索  │   │   │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │
│  │ Whisper ASR   │  │   TTS 引擎   │  │ 说话人识别    │             │
│  │ (语音识别)     │  │ (语音合成)    │  │ (Speaker ID) │             │
│  └──────────────┘  └──────────────┘  └──────────────┘             │
└─────────────────────────────────────────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────────┐
│                          数据存储层                                  │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │
│  │  PostgreSQL   │  │    Redis      │  │    MinIO      │             │
│  │  (主数据库)    │  │  (缓存+队列)  │  │ (文件存储)    │             │
│  └──────────────┘  └──────────────┘  └──────────────┘             │
└─────────────────────────────────────────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────────┐
│                          外部服务层                                  │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │
│  │ Claude API    │  │ 腾讯会议API  │  │ 企业微信API   │             │
│  └──────────────┘  └──────────────┘  └──────────────┘             │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 技术栈选型

| 层级 | 技术选型 | 版本 | 选型理由 |
|------|---------|------|---------|
| **后端框架** | FastAPI | 0.104+ | 异步高性能、自动API文档、类型安全 |
| **Agent核心** | Claude API (Sonnet 4) | - | 中文理解强、长文本支持、工具调用 |
| **语音识别** | faster-whisper | 1.0+ | 比原版快4倍、支持GPU加速 |
| **语音合成** | Edge-TTS | 6.1+ | 免费、中文效果好、多种音色 |
| **说话人识别** | pyannote-audio | 3.1+ | 业界领先、支持多人识别 |
| **数据库** | PostgreSQL | 16+ | 稳定、支持JSON、全文搜索 |
| **缓存** | Redis | 7+ | 消息队列、会话缓存、定时任务 |
| **对象存储** | MinIO | Latest | S3兼容、自托管、文件管理 |
| **任务队列** | Celery | 5.3+ | 异步任务、定时任务、可靠 |
| **容器化** | Docker Compose | 2.23+ | 一键部署、环境隔离 |
| **前端框架** | Vue 3 + Element Plus | - | 组件丰富、中文友好 |
| **内网穿透** | frp | 0.52+ | 稳定、高性能、开源 |

### 2.3 项目结构

```
microbubble-agent/
│
├── docker-compose.yml              # Docker编排
├── docker-compose.dev.yml          # 开发环境编排
├── Dockerfile                      # 应用镜像
├── .env.example                    # 环境变量示例
├── .env                            # 环境变量(不提交)
├── requirements.txt                # Python依赖
├── pyproject.toml                  # 项目配置
│
├── app/                            # 主应用目录
│   ├── __init__.py
│   ├── main.py                     # FastAPI入口
│   ├── config.py                   # 配置管理
│   ├── dependencies.py             # 依赖注入
│   │
│   ├── api/                        # API路由
│   │   ├── __init__.py
│   │   ├── v1/                     # API版本1
│   │   │   ├── __init__.py
│   │   │   ├── chat.py             # 对话接口
│   │   │   ├── task.py             # 任务接口
│   │   │   ├── meeting.py          # 会议接口
│   │   │   ├── member.py           # 成员接口
│   │   │   ├── project.py          # 项目接口
│   │   │   ├── knowledge.py        # 知识库接口
│   │   │   └── voice.py            # 语音接口
│   │   └── websocket.py            # WebSocket接口
│   │
│   ├── agent/                      # Agent核心
│   │   ├── __init__.py
│   │   ├── core.py                 # Agent主类
│   │   ├── prompts.py              # 提示词模板
│   │   ├── tools.py                # 工具定义
│   │   ├── memory.py               # 会话记忆
│   │   └── chains.py               # 处理链
│   │
│   ├── services/                   # 业务服务
│   │   ├── __init__.py
│   │   ├── chat_service.py         # 对话服务
│   │   ├── task_service.py         # 任务服务
│   │   ├── meeting_service.py      # 会议服务
│   │   ├── member_service.py       # 成员服务
│   │   ├── project_service.py      # 项目服务
│   │   ├── knowledge_service.py    # 知识库服务
│   │   ├── reminder_service.py     # 提醒服务
│   │   ├── planner_service.py      # 规划服务
│   │   └── voice_service.py        # 语音服务
│   │
│   ├── models/                     # 数据模型
│   │   ├── __init__.py
│   │   ├── base.py                 # 基础模型
│   │   ├── member.py               # 成员模型
│   │   ├── task.py                 # 任务模型
│   │   ├── meeting.py              # 会议模型
│   │   ├── project.py              # 项目模型
│   │   ├── knowledge.py            # 知识库模型
│   │   └── reminder.py             # 提醒模型
│   │
│   ├── schemas/                    # Pydantic模型
│   │   ├── __init__.py
│   │   ├── chat.py
│   │   ├── task.py
│   │   ├── meeting.py
│   │   ├── member.py
│   │   ├── project.py
│   │   └── knowledge.py
│   │
│   ├── core/                       # 核心模块
│   │   ├── __init__.py
│   │   ├── database.py             # 数据库连接
│   │   ├── redis.py                # Redis连接
│   │   ├── minio.py                # MinIO连接
│   │   ├── security.py             # 安全认证
│   │   └── exceptions.py           # 自定义异常
│   │
│   ├── voice/                      # 语音模块
│   │   ├── __init__.py
│   │   ├── asr.py                  # 语音识别
│   │   ├── tts.py                  # 语音合成
│   │   ├── speaker.py              # 说话人识别
│   │   └── recorder.py             # 录音模块
│   │
│   ├── meeting/                    # 会议模块
│   │   ├── __init__.py
│   │   ├── tencent.py              # 腾讯会议接入
│   │   ├── recorder.py             # 会议录制
│   │   ├── transcriber.py          # 实时转写
│   │   └── summarizer.py           # 会议总结
│   │
│   ├── wechat/                     # 微信模块
│   │   ├── __init__.py
│   │   ├── bot.py                  # 微信机器人
│   │   ├── message.py              # 消息处理
│   │   └── push.py                 # 消息推送
│   │
│   └── utils/                      # 工具函数
│       ├── __init__.py
│       ├── datetime.py             # 日期时间
│       ├── validators.py           # 数据验证
│       └── helpers.py              # 辅助函数
│
├── web/                            # 前端
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── index.html
│   ├── public/
│   └── src/
│       ├── main.ts
│       ├── App.vue
│       ├── router/
│       ├── stores/
│       ├── views/
│       │   ├── Dashboard.vue       # 仪表盘
│       │   ├── ChatView.vue        # 对话界面
│       │   ├── TaskView.vue        # 任务管理
│       │   ├── MeetingView.vue     # 会议管理
│       │   ├── MemberView.vue      # 成员管理
│       │   ├── ProjectView.vue     # 项目管理
│       │   └── KnowledgeView.vue   # 知识库
│       ├── components/
│       └── assets/
│
├── scripts/                        # 脚本
│   ├── init_db.py                  # 初始化数据库
│   ├── seed_data.py                # 填充测试数据
│   ├── start.sh                    # 启动脚本
│   └── backup.sh                   # 备份脚本
│
├── tests/                          # 测试
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_chat.py
│   ├── test_task.py
│   ├── test_meeting.py
│   └── test_voice.py
│
├── docs/                           # 文档
│   ├── api.md                      # API文档
│   ├── deploy.md                   # 部署文档
│   └── user_guide.md               # 用户指南
│
└── .github/                        # GitHub配置
    └── workflows/
        └── ci.yml                  # CI/CD
```

---

## 三、功能模块详细设计

### 3.1 智能对话模块

#### 3.1.1 功能描述

用户可以通过文字或语音与Agent进行自然语言对话，Agent能够理解上下文、调用工具完成任务。

#### 3.1.2 对话能力

```
┌─────────────────────────────────────────────────────────────┐
│                     Agent 对话能力                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  信息查询                                                    │
│  ├── "张三这周有什么任务？"                                  │
│  ├── "水处理课题进度怎么样了？"                              │
│  ├── "最近有什么会议纪要？"                                  │
│  └── "帮我查一下关于气泡稳定性的文献"                        │
│                                                             │
│  任务操作                                                    │
│  ├── "帮我创建一个任务，让李四下周前完成实验"                │
│  ├── "把张三的任务延期到月底"                                │
│  ├── "标记王五的任务为已完成"                                │
│  └── "查看所有逾期任务"                                      │
│                                                             │
│  会议相关                                                    │
│  ├── "帮我预约明天下午的组会"                                │
│  ├── "生成上周组会的纪要"                                    │
│  └── "查看本月所有会议记录"                                  │
│                                                             │
│  知识问答                                                    │
│  ├── "微纳米气泡的生成方法有哪些？"                          │
│  ├── "NTA和DLS测粒径有什么区别？"                            │
│  └── "气泡不稳定的原因有哪些？"                              │
│                                                             │
│  数据分析                                                    │
│  ├── "帮我分析这组NTA数据"                                   │
│  ├── "画一张气泡尺寸分布图"                                  │
│  └── "对比两组实验数据的差异"                                │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

#### 3.1.3 Agent工具定义

```python
# agent/tools.py

tools = [
    # 任务相关
    {
        "name": "create_task",
        "description": "创建新任务",
        "parameters": {
            "title": "任务标题",
            "assignee": "负责人ID",
            "project_id": "所属项目ID",
            "priority": "优先级(high/medium/low)",
            "due_date": "截止日期(YYYY-MM-DD)",
            "description": "任务描述",
            "dependencies": "依赖的任务ID列表"
        }
    },
    {
        "name": "query_tasks",
        "description": "查询任务列表",
        "parameters": {
            "assignee": "负责人(可选)",
            "status": "状态(可选)",
            "project_id": "项目ID(可选)",
            "due_before": "截止日期之前(可选)"
        }
    },
    {
        "name": "update_task",
        "description": "更新任务状态",
        "parameters": {
            "task_id": "任务ID",
            "status": "新状态",
            "progress": "进度说明"
        }
    },
    
    # 成员相关
    {
        "name": "query_members",
        "description": "查询成员信息",
        "parameters": {
            "name": "成员姓名(可选)",
            "research_area": "研究方向(可选)"
        }
    },
    
    # 会议相关
    {
        "name": "query_meetings",
        "description": "查询会议记录",
        "parameters": {
            "date_from": "开始日期",
            "date_to": "结束日期",
            "keyword": "关键词搜索"
        }
    },
    {
        "name": "create_meeting",
        "description": "创建会议",
        "parameters": {
            "title": "会议主题",
            "time": "会议时间",
            "participants": "参与者列表",
            "agenda": "会议议程"
        }
    },
    
    # 知识库相关
    {
        "name": "search_knowledge",
        "description": "搜索知识库",
        "parameters": {
            "query": "搜索关键词",
            "category": "分类(文献/实验/方法)"
        }
    },
    
    # 项目相关
    {
        "name": "query_projects",
        "description": "查询项目信息",
        "parameters": {
            "status": "项目状态(可选)"
        }
    },
    {
        "name": "generate_project_plan",
        "description": "生成项目计划",
        "parameters": {
            "project_name": "项目名称",
            "duration": "预计时长(月)",
            "team_size": "团队人数"
        }
    }
]
```

#### 3.1.4 提示词设计

```python
# agent/prompts.py

SYSTEM_PROMPT = """
你是"小气"，微纳米气泡课题组的AI智能助手。

## 你的身份
- 你服务于一个20多人的微纳米气泡研究课题组
- 你熟悉微纳米气泡的基本理论、生成方法、表征技术和应用场景
-你能够帮助管理任务、会议、项目和知识库

## 你的能力
1. 任务管理：创建、查询、更新任务，设置提醒
2. 会议助手：查询会议记录，生成会议纪要，提取待办事项
3. 项目管理：查看项目进度，生成项目计划
4. 知识问答：回答微纳米气泡相关问题，检索知识库
5. 数据分析：处理实验数据，生成图表

## 回复规范
- 使用中文回复
- 简洁明了，避免冗长
- 涉及专业问题时，给出准确的技术解释
- 操作类请求确认后再执行
- 不确定的信息要明确说明

## 微纳米气泡基础知识
微纳米气泡是指直径在微米到纳米级别的气泡，具有以下特点：
- 尺寸小：通常1μm-100μm（微米级）或<1μm（纳米级）
- 比表面积大：传质效率高
- 带负电：Zeta电位通常为负值
- 稳定性好：可在液体中长时间存在
- 崩溃时产生自由基：可用于氧化反应

常见生成方法：
- 加压溶气法
- 旋流法
- 电解法
- 膜法
- 超声法
- 文丘里管法

常见表征方法：
- NTA（纳米颗粒追踪分析）
- DLS（动态光散射）
- 高速摄像
- 电导法
- 激光衍射法

应用场景：
- 水处理（增氧、去除污染物）
- 农业（促进植物生长、农药增效）
- 生物医学（药物递送、超声造影）
- 清洗（半导体清洗、精密清洗）
- 食品工业（发泡、乳化）
"""

MEETING_ANALYSIS_PROMPT = """
请分析以下会议转写内容，生成结构化的会议纪要。

要求输出以下内容：
1. **会议摘要**（3-5句话概括会议主要内容）
2. **讨论要点**（分点列出讨论的主要议题）
3. **决议事项**（会议中达成的决定）
4. **待办任务**（JSON格式，包含task、assignee、deadline、priority）
5. **下次会议建议**（建议的议题和时间）

会议转写内容：
{transcript}
"""

TASK_EXTRACTION_PROMPT = """
请从以下会议纪要中提取所有待办任务。

输出JSON数组格式：
[
    {
        "task": "任务描述",
        "assignee": "负责人姓名",
        "deadline": "截止日期(YYYY-MM-DD格式，如果原文没有明确日期则根据任务难度估算)",
        "priority": "high/medium/low",
        "dependencies": ["依赖的其他任务描述"]
    }
]

会议纪要：
{minutes}
"""

PROJECT_PLAN_PROMPT = """
请为以下课题生成一份详细的项目计划。

课题信息：
- 课题名称：{project_name}
- 预计时长：{duration}个月
- 团队人数：{team_size}人
- 研究方向：{research_area}

要求：
1. 分为若干阶段（文献调研、方案设计、预实验、正式实验、数据分析、论文撰写）
2. 每个阶段包含具体任务
3. 标注任务负责人建议（根据任务类型）
4. 标注里程碑节点
5. 考虑任务依赖关系
6. 识别可能的风险点

输出JSON格式的项目计划。
"""
```

### 3.2 任务管理模块

#### 3.2.1 数据模型

```python
# models/task.py

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Text
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

class TaskStatus(str, enum.Enum):
    TODO = "todo"              # 待办
    IN_PROGRESS = "in_progress" # 进行中
    BLOCKED = "blocked"        # 阻塞
    REVIEW = "review"          # 待审核
    DONE = "done"              # 已完成
    CANCELLED = "cancelled"    # 已取消

class TaskPriority(str, enum.Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class Task(Base):
    __tablename__ = "tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    
    # 关联信息
    assignee_id = Column(Integer, ForeignKey("members.id"))
    project_id = Column(Integer, ForeignKey("projects.id"))
    created_by = Column(Integer, ForeignKey("members.id"))
    
    # 状态信息
    status = Column(Enum(TaskStatus), default=TaskStatus.TODO)
    priority = Column(Enum(TaskPriority), default=TaskPriority.MEDIUM)
    progress = Column(Integer, default=0)  # 0-100
    
    # 时间信息
    due_date = Column(DateTime)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 来源信息
    source = Column(String(50))  # manual/meeting/ai
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=True)
    
    # 关系
    assignee = relationship("Member", foreign_keys=[assignee_id])
    creator = relationship("Member", foreign_keys=[created_by])
    project = relationship("Project", back_populates="tasks")
    dependencies = relationship("TaskDependency", back_populates="task")
    reminders = relationship("Reminder", back_populates="task")

class TaskDependency(Base):
    __tablename__ = "task_dependencies"
    
    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey("tasks.id"))
    depends_on_id = Column(Integer, ForeignKey("tasks.id"))
    
    task = relationship("Task", foreign_keys=[task_id], back_populates="dependencies")
    depends_on = relationship("Task", foreign_keys=[depends_on_id])
```

#### 3.2.2 任务提醒机制

```python
# services/reminder_service.py

class ReminderService:
    """任务提醒服务"""
    
    async def create_reminder(self, task_id: int, remind_at: datetime, 
                              remind_type: str = "wechat"):
        """创建提醒"""
        reminder = Reminder(
            task_id=task_id,
            remind_at=remind_at,
            remind_type=remind_type,
            status="pending"
        )
        self.db.add(reminder)
        await self.db.commit()
        return reminder
    
    async def check_and_send_reminders(self):
        """检查并发送到期提醒"""
        now = datetime.utcnow()
        reminders = await self.db.query(Reminder).filter(
            Reminder.remind_at <= now,
            Reminder.status == "pending"
        ).all()
        
        for reminder in reminders:
            task = await self.db.get(Task, reminder.task_id)
            member = await self.db.get(Member, task.assignee_id)
            
            # 发送提醒
            message = self.format_reminder_message(task)
            await self.wechat_service.send_message(member.wechat_id, message)
            
            # 更新状态
            reminder.status = "sent"
            reminder.sent_at = now
        
        await self.db.commit()
    
    def format_reminder_message(self, task):
        """格式化提醒消息"""
        days_left = (task.due_date - datetime.utcnow()).days
        
        if days_left < 0:
            emoji = "⚠️"
            status = f"已逾期{abs(days_left)}天"
        elif days_left == 0:
            emoji = "🔔"
            status = "今天到期"
        elif days_left <= 2:
            emoji = "⏰"
            status = f"还有{days_left}天到期"
        else:
            emoji = "📋"
            status = f"还有{days_left}天到期"
        
        return f"""
{emoji} 任务提醒

任务：{task.title}
状态：{status}
截止：{task.due_date.strftime('%Y-%m-%d')}
项目：{task.project.name if task.project else '未分配'}

请及时处理！
"""
```

### 3.3 会议助手模块

#### 3.3.1 会议旁听流程

```python
# meeting/tencent.py

class TencentMeetingService:
    """腾讯会议接入服务"""
    
    def __init__(self):
        self.app_id = config.TENCENT_MEETING_APP_ID
        self.app_secret = config.TENCENT_MEETING_APP_SECRET
    
    async def join_meeting(self, meeting_id: str, meeting_password: str = None):
        """加入会议"""
        # 1. 获取会议信息
        meeting_info = await self.get_meeting_info(meeting_id)
        
        # 2. 创建录制任务
        recording = await self.start_recording(meeting_id)
        
        # 3. 建立音频流连接
        audio_stream = await self.connect_audio_stream(meeting_id)
        
        return {
            "meeting_info": meeting_info,
            "recording": recording,
            "audio_stream": audio_stream
        }
    
    async def connect_audio_stream(self, meeting_id: str):
        """连接会议音频流"""
        # WebSocket连接获取实时音频
        ws_url = await self.get_audio_ws_url(meeting_id)
        
        async with websockets.connect(ws_url) as ws:
            async for message in ws:
                # 音频数据
                yield message
```

#### 3.3.2 实时转写服务

```python
# meeting/transcriber.py

from faster_whisper import WhisperModel
import asyncio

class RealtimeTranscriber:
    """实时转写服务"""
    
    def __init__(self):
        # 加载Whisper模型（GPU加速）
        self.model = WhisperModel(
            "large-v3",
            device="cuda",
            compute_type="float16"
        )
        self.speaker_detector = SpeakerDetector()
    
    async def transcribe_stream(self, audio_stream):
        """流式转写"""
        buffer = []
        transcript = []
        
        async for audio_chunk in audio_stream:
            buffer.append(audio_chunk)
            
            # 每5秒处理一次
            if len(buffer) >= 50:  # 假设每块100ms
                audio_data = self.concat_audio(buffer)
                
                # 语音识别
                segments, _ = self.model.transcribe(
                    audio_data,
                    language="zh",
                    beam_size=5
                )
                
                # 说话人识别
                speaker = await self.speaker_detector.identify(audio_data)
                
                for segment in segments:
                    entry = {
                        "start": segment.start,
                        "end": segment.end,
                        "text": segment.text,
                        "speaker": speaker
                    }
                    transcript.append(entry)
                    
                    # 实时推送
                    yield entry
                
                buffer = []
        
        return transcript
```

#### 3.3.3 会议纪要生成

```python
# meeting/summarizer.py

class MeetingSummarizer:
    """会议纪要生成器"""
    
    def __init__(self, agent):
        self.agent = agent
    
    async def generate_minutes(self, transcript: list) -> dict:
        """生成会议纪要"""
        # 格式化转写内容
        formatted_transcript = self.format_transcript(transcript)
        
        # 调用Agent生成纪要
        prompt = MEETING_ANALYSIS_PROMPT.format(
            transcript=formatted_transcript
        )
        
        result = await self.agent.chat(prompt)
        
        return {
            "summary": result["summary"],
            "key_points": result["key_points"],
            "decisions": result["decisions"],
            "action_items": result["action_items"],
            "next_meeting": result["next_meeting"]
        }
    
    def format_transcript(self, transcript: list) -> str:
        """格式化转写内容"""
        lines = []
        for entry in transcript:
            time_str = self.format_time(entry["start"])
            lines.append(f"[{time_str}] {entry['speaker']}：{entry['text']}")
        return "\n".join(lines)
    
    async def extract_tasks(self, minutes: dict) -> list:
        """从纪要中提取任务"""
        prompt = TASK_EXTRACTION_PROMPT.format(
            minutes=json.dumps(minutes, ensure_ascii=False)
        )
        
        tasks = await self.agent.chat(prompt)
        return tasks
```

### 3.4 自动规划模块

#### 3.4.1 项目规划生成

```python
# services/planner_service.py

class PlannerService:
    """自动规划服务"""
    
    async def generate_project_plan(self, project_info: dict) -> dict:
        """生成项目计划"""
        prompt = PROJECT_PLAN_PROMPT.format(**project_info)
        plan = await self.agent.chat(prompt)
        
        # 解析并存储
        plan_data = json.loads(plan)
        
        # 创建项目
        project = await self.create_project(plan_data)
        
        # 创建里程碑
        for milestone in plan_data["milestones"]:
            await self.create_milestone(project.id, milestone)
        
        # 创建任务
        for task_info in plan_data["tasks"]:
            await self.task_service.create_task(task_info)
        
        return plan_data
    
    async def auto_schedule_tasks(self, project_id: int):
        """自动排期任务"""
        tasks = await self.get_project_tasks(project_id)
        
        # 拓扑排序（考虑依赖关系）
        sorted_tasks = self.topological_sort(tasks)
        
        # 计算每个任务的开始和结束时间
        current_date = datetime.utcnow()
        for task in sorted_tasks:
            if task.dependencies:
                # 有依赖，等待依赖完成
                latest_dep = max(
                    dep.completed_at or dep.due_date 
                    for dep in task.dependencies
                )
                task.start_date = latest_dep
            else:
                task.start_date = current_date
            
            # 根据任务复杂度估算时长
            duration = self.estimate_duration(task)
            task.due_date = task.start_date + timedelta(days=duration)
            
            current_date = task.due_date
        
        await self.db.commit()
        return sorted_tasks
    
    def estimate_duration(self, task) -> int:
        """估算任务时长（天）"""
        # 根据任务类型和复杂度估算
        duration_map = {
            "文献调研": 14,
            "方案设计": 7,
            "预实验": 21,
            "正式实验": 60,
            "数据分析": 30,
            "论文撰写": 30,
        }
        
        for keyword, days in duration_map.items():
            if keyword in task.title:
                return days
        
        return 7  # 默认1周
```

#### 3.4.2 资源冲突检测

```python
# services/planner_service.py

class ResourceConflictDetector:
    """资源冲突检测"""
    
    async def detect_conflicts(self, start_date: datetime, end_date: datetime):
        """检测资源冲突"""
        conflicts = []
        
        # 1. 检测设备使用冲突
        equipment_conflicts = await self.check_equipment_conflicts(
            start_date, end_date
        )
        conflicts.extend(equipment_conflicts)
        
        # 2. 检测人员工作量过载
        overload_conflicts = await self.check_member_overload(
            start_date, end_date
        )
        conflicts.extend(overload_conflicts)
        
        # 3. 检测导师审阅时间冲突
        review_conflicts = await self.check_review_conflicts(
            start_date, end_date
        )
        conflicts.extend(review_conflicts)
        
        return conflicts
    
    async def check_equipment_conflicts(self, start_date, end_date):
        """检测设备使用冲突"""
        # 查询时间段内的设备使用记录
        bookings = await self.db.query(EquipmentBooking).filter(
            EquipmentBooking.start_time < end_date,
            EquipmentBooking.end_time > start_date
        ).all()
        
        # 按设备分组，检测重叠
        equipment_bookings = {}
        for booking in bookings:
            if booking.equipment_id not in equipment_bookings:
                equipment_bookings[booking.equipment_id] = []
            equipment_bookings[booking.equipment_id].append(booking)
        
        conflicts = []
        for equipment_id, bookings in equipment_bookings.items():
            bookings.sort(key=lambda x: x.start_time)
            for i in range(len(bookings) - 1):
                if bookings[i].end_time > bookings[i+1].start_time:
                    conflicts.append({
                        "type": "equipment",
                        "equipment_id": equipment_id,
                        "booking1": bookings[i],
                        "booking2": bookings[i+1]
                    })
        
        return conflicts
```

### 3.5 知识管理模块

#### 3.5.1 知识库结构

```
知识库
├── 文献库
│   ├── 气泡生成
│   │   ├── 加压溶气法
│   │   ├── 旋流法
│   │   └── ...
│   ├── 气泡表征
│   └── 应用领域
│       ├── 水处理
│       ├── 农业
│       └── 生物医学
│
├── 实验记录
│   ├── 按项目分类
│   └── 按日期分类
│
├── 方法库
│   ├── 实验方法SOP
│   ├── 数据分析方法
│   └── 仪器操作规程
│
└── 问题库
    ├── 常见问题FAQ
    └── 故障排除
```

#### 3.5.2 RAG检索实现

```python
# services/knowledge_service.py

from langchain.vectorstores import Chroma
from langchain.embeddings import HuggingFaceEmbeddings

class KnowledgeService:
    """知识库服务"""
    
    def __init__(self):
        self.embeddings = HuggingFaceEmbeddings(
            model_name="shibing624/text2vec-base-chinese"
        )
        self.vectorstore = Chroma(
            persist_directory="./data/chroma",
            embedding_function=self.embeddings
        )
    
    async def add_document(self, content: str, metadata: dict):
        """添加文档到知识库"""
        # 文本分块
        chunks = self.text_splitter.split_text(content)
        
        # 添加到向量数据库
        self.vectorstore.add_texts(
            texts=chunks,
            metadatas=[metadata] * len(chunks)
        )
    
    async def search(self, query: str, top_k: int = 5) -> list:
        """语义搜索"""
        results = self.vectorstore.similarity_search_with_score(
            query, k=top_k
        )
        
        return [
            {
                "content": doc.page_content,
                "metadata": doc.metadata,
                "score": score
            }
            for doc, score in results
        ]
    
    async def search_and_format(self, query: str) -> str:
        """搜索并格式化结果"""
        results = await self.search(query)
        
        formatted = []
        for i, result in enumerate(results, 1):
            formatted.append(f"""
【结果{i}】(相似度: {result['score']:.2f})
来源: {result['metadata'].get('source', '未知')}
内容: {result['content'][:500]}...
""")
        
        return "\n".join(formatted)
```

---

## 四、数据库设计

### 4.1 ER图

```
┌─────────────┐       ┌─────────────┐       ┌─────────────┐
│   Member    │       │    Task     │       │   Project   │
├─────────────┤       ├─────────────┤       ├─────────────┤
│ id          │◄──┐   │ id          │   ┌──►│ id          │
│ name        │   │   │ title       │   │   │ name        │
│ grade       │   │   │ description │   │   │ description │
│ research_   │   ├───│ assignee_id │   │   │ status      │
│   area      │   │   │ project_id │───┘   │ start_date  │
│ skills      │   │   │ created_by │───┐   │ end_date    │
│ wechat_id   │   │   │ status     │   │   │ created_by  │
│ email       │   │   │ priority   │   │   └─────────────┘
│ phone       │   │   │ due_date   │   │
│ avatar      │   │   │ source     │   │   ┌─────────────┐
│ is_active   │   │   │ meeting_id │   │   │  Meeting    │
└─────────────┘   │   └─────────────┘   │   ├─────────────┤
                  │                     │   │ id          │
                  │   ┌─────────────┐   │   │ title       │
                  │   │  Reminder   │   │   │ start_time  │
                  │   ├─────────────┤   │   │ end_time    │
                  │   │ id          │   │   │ transcript  │
                  │   │ task_id     │───┘   │ summary     │
                  │   │ remind_at   │       │ created_by  │
                  │   │ type        │       └─────────────┘
                  │   │ status      │
                  │   └─────────────┘       ┌─────────────┐
                  │                         │  Knowledge  │
                  │   ┌─────────────┐       ├─────────────┤
                  │   │ Milestone   │       │ id          │
                  │   ├─────────────┤       │ title       │
                  │   │ id          │       │ content     │
                  │   │ project_id  │       │ category    │
                  │   │ name        │       │ tags        │
                  │   │ due_date    │       │ embedding   │
                  │   │ status      │       │ created_by  │
                  │   └─────────────┘       └─────────────┘
                  │
                  │   ┌─────────────┐
                  │   │Equipment    │
                  │   │  Booking    │
                  │   ├─────────────┤
                  └───│ member_id   │
                      │ equipment   │
                      │ start_time  │
                      │ end_time    │
                      └─────────────┘
```

### 4.2 核心表结构

```sql
-- 成员表
CREATE TABLE members (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    grade VARCHAR(20),
    research_area VARCHAR(100),
    skills TEXT[],
    wechat_id VARCHAR(100),
    email VARCHAR(100),
    phone VARCHAR(20),
    avatar VARCHAR(500),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 项目表
CREATE TABLE projects (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    status VARCHAR(20) DEFAULT 'active',
    start_date DATE,
    end_date DATE,
    created_by INTEGER REFERENCES members(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 任务表
CREATE TABLE tasks (
    id SERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    assignee_id INTEGER REFERENCES members(id),
    project_id INTEGER REFERENCES projects(id),
    created_by INTEGER REFERENCES members(id),
    status VARCHAR(20) DEFAULT 'todo',
    priority VARCHAR(10) DEFAULT 'medium',
    progress INTEGER DEFAULT 0,
    due_date TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    source VARCHAR(50),
    meeting_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 任务依赖表
CREATE TABLE task_dependencies (
    id SERIAL PRIMARY KEY,
    task_id INTEGER REFERENCES tasks(id),
    depends_on_id INTEGER REFERENCES tasks(id),
    UNIQUE(task_id, depends_on_id)
);

-- 会议表
CREATE TABLE meetings (
    id SERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    location VARCHAR(200),
    meeting_url VARCHAR(500),
    transcript JSONB,
    summary TEXT,
    key_points TEXT[],
    decisions TEXT[],
    created_by INTEGER REFERENCES members(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 会议参与者表
CREATE TABLE meeting_participants (
    id SERIAL PRIMARY KEY,
    meeting_id INTEGER REFERENCES meetings(id),
    member_id INTEGER REFERENCES members(id),
    role VARCHAR(20) DEFAULT 'participant',
    UNIQUE(meeting_id, member_id)
);

-- 提醒表
CREATE TABLE reminders (
    id SERIAL PRIMARY KEY,
    task_id INTEGER REFERENCES tasks(id),
    remind_at TIMESTAMP NOT NULL,
    remind_type VARCHAR(20) DEFAULT 'wechat',
    status VARCHAR(20) DEFAULT 'pending',
    sent_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 知识库表
CREATE TABLE knowledge (
    id SERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    content TEXT NOT NULL,
    category VARCHAR(50),
    tags TEXT[],
    source VARCHAR(500),
    embedding VECTOR(768),
    created_by INTEGER REFERENCES members(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 里程碑表
CREATE TABLE milestones (
    id SERIAL PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id),
    name VARCHAR(200) NOT NULL,
    description TEXT,
    due_date DATE,
    status VARCHAR(20) DEFAULT 'pending',
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 设备预约表
CREATE TABLE equipment_bookings (
    id SERIAL PRIMARY KEY,
    equipment_name VARCHAR(100) NOT NULL,
    member_id INTEGER REFERENCES members(id),
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    purpose VARCHAR(200),
    status VARCHAR(20) DEFAULT 'confirmed',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 索引
CREATE INDEX idx_tasks_assignee ON tasks(assignee_id);
CREATE INDEX idx_tasks_project ON tasks(project_id);
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_due_date ON tasks(due_date);
CREATE INDEX idx_meetings_start_time ON meetings(start_time);
CREATE INDEX idx_reminders_remind_at ON reminders(remind_at);
CREATE INDEX idx_reminders_status ON reminders(status);
```

---

## 五、API设计

### 5.1 对话API

```yaml
# WebSocket - 实时对话
ws://localhost:8000/ws/chat/{user_id}

# 发送消息
{
    "type": "text",
    "content": "帮我查一下张三的任务",
    "session_id": "optional_session_id"
}

# 接收回复
{
    "type": "text",
    "content": "张三目前有3个任务...",
    "timestamp": "2026-05-16T10:30:00Z"
}

# 语音消息
{
    "type": "voice",
    "audio": "base64_encoded_audio",
    "format": "wav"
}
```

### 5.2 任务API

```yaml
# 创建任务
POST /api/v1/tasks
{
    "title": "完成NTA测试",
    "assignee_id": 1,
    "project_id": 1,
    "priority": "high",
    "due_date": "2026-05-22",
    "description": "对水处理样品进行NTA测试"
}

# 查询任务列表
GET /api/v1/tasks?assignee_id=1&status=in_progress&project_id=1

# 更新任务
PUT /api/v1/tasks/{task_id}
{
    "status": "done",
    "progress": 100
}

# 获取任务统计
GET /api/v1/tasks/stats
{
    "total": 45,
    "todo": 12,
    "in_progress": 18,
    "done": 15,
    "overdue": 3
}
```

### 5.3 会议API

```yaml
# 创建会议
POST /api/v1/meetings
{
    "title": "周组会",
    "start_time": "2026-05-16T14:00:00",
    "participants": [1, 2, 3, 4],
    "agenda": ["实验进展汇报", "问题讨论", "下周计划"]
}

# 获取会议记录
GET /api/v1/meetings?start_date=2026-05-01&end_date=2026-05-31

# 获取会议纪要
GET /api/v1/meetings/{meeting_id}/minutes

# 会议实时转写（WebSocket）
ws://localhost:8000/ws/meeting/{meeting_id}/transcript
```

### 5.4 知识库API

```yaml
# 搜索知识库
GET /api/v1/knowledge/search?query=气泡稳定性&category=文献

# 添加文档
POST /api/v1/knowledge
{
    "title": "微纳米气泡稳定性研究进展",
    "content": "...",
    "category": "文献",
    "tags": ["气泡", "稳定性", "综述"]
}
```

---

## 六、开发计划

### 6.1 阶段划分

```
┌─────────────────────────────────────────────────────────────────┐
│                        开发阶段规划                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  第一阶段：基础框架（2周）                                        │
│  ├── 项目初始化                                                  │
│  ├── 数据库设计与实现                                            │
│  ├── 基础API框架                                                │
│  ├── 用户认证                                                  │
│  └── 基础前端框架                                                │
│                                                                 │
│  第二阶段：核心功能（3周）                                        │
│  ├── Agent核心实现                                              │
│  ├── 对话功能（文字）                                            │
│  ├── 任务管理CRUD                                               │
│  ├── 成员管理                                                  │
│  └── 基础提醒功能                                                │
│                                                                 │
│  第三阶段：语音功能（2周）                                        │
│  ├── 语音识别集成                                                │
│  ├── 语音合成集成                                                │
│  ├── 语音对话功能                                                │
│  └── 微信接入                                                  │
│                                                                 │
│  第四阶段：会议功能（3周）                                        │
│  ├── 腾讯会议接入                                                │
│  ├── 实时转写功能                                                │
│  ├── 会议纪要生成                                                │
│  ├── 任务自动提取                                                │
│  └── 会议管理界面                                                │
│                                                                 │
│  第五阶段：高级功能（2周）                                        │
│  ├── 项目管理                                                  │
│  ├── 自动规划功能                                                │
│  ├── 知识库RAG                                                  │
│  ├── 数据分析功能                                                │
│  └── 进度可视化                                                │
│                                                                 │
│  第六阶段：优化完善（2周）                                        │
│  ├── 性能优化                                                  │
│  ├── UI/UX优化                                                 │
│  ├── 测试完善                                                  │
│  ├── 文档编写                                                  │
│  └── 部署上线                                                  │
│                                                                 │
│  总计：约14周（3.5个月）                                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 6.2 详细时间表

| 阶段 | 周数 | 任务 | 产出 |
|------|------|------|------|
| **第一阶段** | W1-W2 | 项目初始化、数据库设计 | 基础框架可运行 |
| | W1 | Docker环境搭建、项目结构 | 开发环境就绪 |
| | W2 | 数据库模型、基础API | 数据库可访问 |
| **第二阶段** | W3-W5 | 核心功能开发 | MVP可用 |
| | W3 | Claude API集成、对话功能 | 文字对话可用 |
| | W4 | 任务管理、成员管理 | 任务CRUD可用 |
| | W5 | 提醒功能、前端基础 | 基础功能完整 |
| **第三阶段** | W6-W7 | 语音功能 | 语音对话可用 |
| | W6 | Whisper集成、语音识别 | 语音转文字可用 |
| | W7 | TTS集成、语音对话 | 完整语音交互 |
| **第四阶段** | W8-W10 | 会议功能 | 会议助手可用 |
| | W8 | 腾讯会议API接入 | 可加入会议 |
| | W9 | 实时转写、纪要生成 | 会议记录可用 |
| | W10 | 任务提取、会议管理 | 会议功能完整 |
| **第五阶段** | W11-W12 | 高级功能 | 全功能可用 |
| | W11 | 项目管理、自动规划 | 管理功能完整 |
| | W12 | 知识库、数据分析 | 知识功能可用 |
| **第六阶段** | W13-W14 | 优化上线 | 生产可用 |
| | W13 | 测试、优化 | 质量达标 |
| | W14 | 部署、文档 | 上线运行 |

---

## 七、部署方案

### 7.1 Docker Compose配置

```yaml
# docker-compose.yml

version: '3.8'

services:
  # 主应用
  app:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    environment:
      - DATABASE_URL=postgresql://postgres:password@db:5432/microbubble
      - REDIS_URL=redis://redis:6379/0
      - MINIO_ENDPOINT=minio:9000
      - CLAUDE_API_KEY=${CLAUDE_API_KEY}
      - TENCENT_MEETING_APP_ID=${TENCENT_MEETING_APP_ID}
      - TENCENT_MEETING_APP_SECRET=${TENCENT_MEETING_APP_SECRET}
    depends_on:
      - db
      - redis
      - minio
    restart: unless-stopped

  # PostgreSQL数据库
  db:
    image: postgres:16-alpine
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      - POSTGRES_DB=microbubble
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=password
    ports:
      - "5432:5432"
    restart: unless-stopped

  # Redis缓存
  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"
    restart: unless-stopped

  # MinIO对象存储
  minio:
    image: minio/minio
    volumes:
      - minio_data:/data
    ports:
      - "9000:9000"
      - "9001:9001"
    environment:
      - MINIO_ROOT_USER=minioadmin
      - MINIO_ROOT_PASSWORD=minioadmin
    command: server /data --console-address ":9001"
    restart: unless-stopped

  # Whisper语音识别服务
  whisper:
    build:
      context: .
      dockerfile: Dockerfile.whisper
    volumes:
      - ./models:/app/models
    environment:
      - MODEL_SIZE=large-v3
      - DEVICE=cuda
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    restart: unless-stopped

  # Celery Worker
  celery-worker:
    build: .
    command: celery -A app.core.celery worker --loglevel=info
    volumes:
      - ./data:/app/data
    environment:
      - DATABASE_URL=postgresql://postgres:password@db:5432/microbubble
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - db
      - redis
    restart: unless-stopped

  # Celery Beat（定时任务）
  celery-beat:
    build: .
    command: celery -A app.core.celery beat --loglevel=info
    volumes:
      - ./data:/app/data
    environment:
      - DATABASE_URL=postgresql://postgres:password@db:5432/microbubble
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - db
      - redis
    restart: unless-stopped

  # 前端
  web:
    build:
      context: ./web
      dockerfile: Dockerfile
    ports:
      - "80:80"
    depends_on:
      - app
    restart: unless-stopped

  # Nginx反向代理
  nginx:
    image: nginx:alpine
    ports:
      - "443:443"
      - "80:80"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf
      - ./nginx/ssl:/etc/nginx/ssl
    depends_on:
      - app
      - web
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
  minio_data:
```

### 7.2 启动脚本

```bash
#!/bin/bash
# scripts/start.sh

set -e

echo "=== 微纳米气泡课题组Agent系统启动 ==="

# 检查环境变量
if [ ! -f .env ]; then
    echo "错误：.env文件不存在"
    echo "请复制.env.example为.env并配置相应参数"
    exit 1
fi

# 创建必要目录
mkdir -p data/{postgres,redis,minio,chroma}
mkdir -p logs
mkdir -p models

# 构建镜像
echo "构建Docker镜像..."
docker-compose build

# 启动服务
echo "启动服务..."
docker-compose up -d

# 等待服务就绪
echo "等待服务就绪..."
sleep 10

# 初始化数据库
echo "初始化数据库..."
docker-compose exec app python scripts/init_db.py

echo "=== 启动完成 ==="
echo "访问地址: https://localhost"
echo "API文档: https://localhost/docs"
```

---

## 八、测试策略

### 8.1 测试类型

| 测试类型 | 覆盖范围 | 工具 |
|---------|---------|------|
| 单元测试 | 业务逻辑、工具函数 | pytest |
| 集成测试 | API接口、数据库操作 | pytest + httpx |
| 端到端测试 | 完整用户流程 | Playwright |
| 性能测试 | 并发、响应时间 | locust |
| 语音测试 | 识别准确率 | 自定义测试集 |

### 8.2 测试用例示例

```python
# tests/test_task.py

import pytest
from httpx import AsyncClient

class TestTaskAPI:
    async def test_create_task(self, client: AsyncClient, auth_headers):
        """测试创建任务"""
        response = await client.post("/api/v1/tasks", json={
            "title": "测试任务",
            "assignee_id": 1,
            "priority": "high",
            "due_date": "2026-05-22"
        }, headers=auth_headers)
        
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "测试任务"
        assert data["status"] == "todo"
    
    async def test_query_tasks(self, client: AsyncClient, auth_headers):
        """测试查询任务"""
        response = await client.get(
            "/api/v1/tasks",
            params={"status": "in_progress"},
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["items"], list)
    
    async def test_update_task_status(self, client: AsyncClient, auth_headers):
        """测试更新任务状态"""
        # 先创建任务
        create_resp = await client.post("/api/v1/tasks", json={
            "title": "待更新任务",
            "assignee_id": 1
        }, headers=auth_headers)
        task_id = create_resp.json()["id"]
        
        # 更新状态
        response = await client.put(f"/api/v1/tasks/{task_id}", json={
            "status": "done",
            "progress": 100
        }, headers=auth_headers)
        
        assert response.status_code == 200
        assert response.json()["status"] == "done"
```

---

## 九、安全设计

### 9.1 认证与授权

```python
# core/security.py

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """验证用户身份"""
    try:
        payload = jwt.decode(
            credentials.credentials,
            config.SECRET_KEY,
            algorithms=["HS256"]
        )
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401)
        return user_id
    except jwt.PyJWTError:
        raise HTTPException(status_code=401)

def require_role(role: str):
    """角色权限检查"""
    async def role_checker(current_user = Depends(get_current_user)):
        user = await get_user(current_user)
        if user.role != role:
            raise HTTPException(status_code=403)
        return user
    return role_checker
```

### 9.2 数据安全

- 所有API通信使用HTTPS
- 敏感信息（API Key等）存储在环境变量
- 数据库密码定期更换
- 定期备份数据
- 操作日志审计

---

## 十、维护与扩展

### 10.1 日常维护

| 任务 | 频率 | 说明 |
|------|------|------|
| 数据库备份 | 每天 | 自动备份到MinIO |
| 日志清理 | 每周 | 保留30天日志 |
| 系统监控 | 实时 | CPU、内存、磁盘 |
| 安全更新 | 每月 | 系统和依赖更新 |

### 10.2 扩展方向

1. **功能扩展**
   - 支持更多会议软件（Zoom、飞书）
   - 移动端App
   - 邮件集成
   - 日历同步

2. **AI能力扩展**
   - 多模态理解（图片、表格）
   - 更精准的说话人识别
   - 自动摘要生成
   - 智能实验方案推荐

3. **集成扩展**
   - 与实验室LIMS系统集成
   - 与论文管理系统集成
   - 与财务系统集成（科研经费管理）

---

## 附录

### A. 环境变量配置

```bash
# .env.example

# 应用配置
APP_NAME=MicroBubble Agent
APP_ENV=development
APP_DEBUG=true
SECRET_KEY=your-secret-key-here

# 数据库
DATABASE_URL=postgresql://postgres:password@localhost:5432/microbubble

# Redis
REDIS_URL=redis://localhost:6379/0

# MinIO
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=microbubble

# Claude API
CLAUDE_API_KEY=your-claude-api-key

# 腾讯会议
TENCENT_MEETING_APP_ID=your-app-id
TENCENT_MEETING_APP_SECRET=your-app-secret

# 企业微信
WECHAT_CORP_ID=your-corp-id
WECHAT_AGENT_ID=your-agent-id
WECHAT_SECRET=your-secret

# Whisper
WHISPER_MODEL_SIZE=large-v3
WHISPER_DEVICE=cuda
```

### B. 常用命令

```bash
# 启动服务
docker-compose up -d

# 停止服务
docker-compose down

# 查看日志
docker-compose logs -f app

# 进入容器
docker-compose exec app bash

# 数据库迁移
docker-compose exec app alembic upgrade head

# 运行测试
docker-compose exec app pytest

# 备份数据库
docker-compose exec db pg_dump -U postgres microbubble > backup.sql
```

---

**文档版本**: v1.0
**最后更新**: 2026-05-16
**作者**: AI Agent
