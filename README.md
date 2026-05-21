# 微纳米气泡课题组智能Agent系统

"小气" - 微纳米气泡课题组AI智能助手（约20人研究实验室）

## 功能特性

- **智能对话** - 支持文字/语音/图片/文件与Agent交互，多模态识别，拖拽上传
- **联网搜索** - 搜狗微信+必应双引擎并发搜索，自动获取最新信息
- **任务管理** - 创建、分配、追踪任务，自定义提醒时间，角色权限控制（管理员可分配给任何人，普通成员只能管理自己的任务）
- **主动提醒** - 自动检查即将到期、已逾期、未确认的任务，通过企业微信主动提醒成员（每15分钟检查，Redis 去重24小时不重复，北京时间显示）
- **知识库** - 文献管理、语义搜索（pgvector），AI 自动分类标签，对话知识自动入库
- **长期记忆** - 用户偏好记忆、对话摘要、知识图谱构建
- **项目管理** - 课题管理、进度追踪、里程碑管理
- **成员管理** - 课题组成员信息管理
- **语音交互** - 语音输入自动转文字（faster-whisper GPU large-v3），领域术语提示词优化，AI 回复可语音播报（Edge-TTS）
- **企业微信集成** - 群机器人对话、任务派发通知、到期/逾期提醒、进度回复（消息格式兼容微信插件端）
- **微信插件支持** - 通过微信插件在普通微信内与机器人对话（需一次性注册企业微信）
- **文件管理** - MinIO 文件上传，支持对话文件
- **自动部署** - GitHub Webhook 触发，push 后自动构建部署

### 待实现功能

- **文件问答** - 支持上传 PDF/Word/Excel 直接进行内容问答
- **会议助手** - 自动旁听会议、实时语音转写（GPU Whisper）、会后自动生成摘要/要点/决定，自动创建关联任务
- **腾讯会议集成** - 自动创建线上会议、Webhook 回调、转写分析（待配置 API 凭据）

## 开发工具

- **Claude Code 任务通知** - 任务完成时语音提醒（Edge-TTS），音量最大，语速适中

## 技术栈

| 组件 | 技术 |
|------|------|
| 后端 | Python 3.11 + FastAPI + SQLAlchemy + PostgreSQL |
| 前端 | Vue 3 + Element Plus + Vite + Pinia |
| AI | Claude API (支持代理地址) + mimo-v2.5 多模态 |
| 语音 | faster-whisper (GPU) + Edge-TTS |
| 向量搜索 | pgvector + text2vec-base-chinese |
| 缓存 | Redis (Session + 微信状态) |
| 存储 | MinIO |
| 任务队列 | Celery + Redis |
| 部署 | Docker Compose + FRP 内网穿透 |

## 部署架构

采用 **云服务器 + 本地电脑 FRP 穿透** 方案：

```
用户 → 云服务器 (Nginx + SSL + FRP 服务端) → FRP 隧道 → 本地电脑 (全部 Docker 服务 + GPU Whisper)
```

- **云服务器**（2核 2G）：只运行 Nginx 反向代理 + FRP 服务端，轻量无压力
- **本地电脑**（有 GPU）：运行全部应用服务（app、PostgreSQL、Redis、MinIO、Whisper GPU、Celery）
- **FRP 隧道**：本地 8000 端口穿透到云服务器，用户通过 `https://agent.mnb-lab.cn` 访问

## 快速开始

### 1. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入你的配置
# 必填项：CLAUDE_API_KEY、SECRET_KEY、数据库密码等
```

### 2. 本地电脑部署（一键脚本）

```bash
# Windows
start.bat   # 启动所有服务
stop.bat    # 停止所有服务
status.bat  # 查看服务状态

# 或手动启动
docker compose up -d

# 开发模式（热重载，改代码自动重启）
docker compose -f docker-compose.dev.yml up -d
```

### 3. 云服务器部署

```bash
# 首次部署
sudo bash scripts/deploy-cloud.sh

# 配置自动部署（GitHub Webhook）
cp scripts/webhook.service /etc/systemd/system/
systemctl daemon-reload && systemctl enable webhook && systemctl start webhook
# 然后在 GitHub 仓库 Settings → Webhooks 添加:
# URL: http://<服务器IP>:9000/webhook
# Secret: microbubble-deploy-2026
# Events: Just the push event
```

配置完成后，每次 `git push` 到 main 分支会自动部署。

### 4. FRP 穿透配置

```bash
# 本地电脑启动 FRP 客户端
cd frp
./frpc.exe -c frpc.toml
```

### 5. 访问系统

- **生产环境**: https://agent.mnb-lab.cn
- **本地开发**: http://localhost:5173 (前端) / http://localhost:8000 (API)
- **API文档**: https://agent.mnb-lab.cn/docs
- **MinIO控制台**: http://localhost:9001

## 项目结构

```
microbubble-agent/
├── app/                     # 后端应用
│   ├── agent/              # AI Agent核心（工具调用、对话管理）
│   ├── api/                # API接口（31个端点，全部带认证）
│   │   └── v1/            # 版本化API
│   ├── core/               # 核心模块（安全、Redis、Celery、日志、限流）
│   ├── models/             # SQLAlchemy数据模型
│   ├── schemas/            # Pydantic验证模型
│   ├── services/           # 业务服务层（10个服务）
│   ├── voice/              # 语音服务（ASR、TTS）
│   └── wechat/             # 企业微信模块（消息、身份、分析、调度）
├── web/                     # 前端应用
│   └── src/
│       ├── views/          # 页面组件（含ChatView图片识别）
│       ├── layouts/        # 布局组件
│       ├── stores/         # Pinia状态管理
│       └── router/         # 路由配置
├── scripts/                 # 部署和工具脚本
├── frp/                     # FRP内网穿透配置
├── docker-compose.yml       # Docker编排（7个服务）
├── Dockerfile.whisper       # Whisper GPU镜像
├── alembic/                 # 数据库迁移
└── .env.example             # 环境变量示例
```

## 开发指南

### 后端开发

```bash
# 安装依赖
pip install -r requirements.txt

# 运行开发服务器
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 前端开发

```bash
cd web

# 安装依赖
npm install

# 运行开发服务器
npm run dev
```

## API接口

所有接口均需 JWT 认证（除登录外）。

### 核心模块
- `POST /api/v1/chat` - 智能对话（支持工具调用）
- `POST /api/v1/chat/image` - 图片识别对话
- `POST /api/v1/chat/file` - 文件对话（PDF/Word/Excel）
- `WebSocket /api/v1/chat/ws` - 流式对话

### 业务模块
- `GET/POST /api/v1/tasks` - 任务管理（CRUD + 统计 + Dashboard）
- `GET/POST /api/v1/meetings` - 会议管理（含转写分析）
- `GET/POST /api/v1/members` - 成员管理
- `GET/POST /api/v1/projects` - 项目管理（含里程碑）
- `GET/POST /api/v1/knowledge` - 知识库（语义搜索 + 文件上传）
- `GET/POST /api/v1/memory` - 长期记忆管理

### 集成模块
- `POST /api/v1/wechat/callback` - 企业微信回调
- `POST /api/v1/tencent-meeting/webhook` - 腾讯会议回调
- `POST /api/v1/upload` - 文件上传

### Agent 工具（14个）
- `create_task` / `query_tasks` / `update_task` - 任务管理
- `create_meeting` / `query_meetings` - 会议管理
- `query_members` - 成员查询
- `query_projects` / `generate_project_plan` - 项目管理
- `search_knowledge` / `save_conversation_knowledge` - 知识库
- `web_search` - 联网搜索
- `save_memory` / `search_memory` / `forget_memory` - 长期记忆

详细文档: https://agent.mnb-lab.cn/docs

## 当前状态

✅ **已上线运行** - 核心功能已完成，生产环境部署成功

- 云服务器部署成功（https://agent.mnb-lab.cn）
- GitHub Webhook 自动部署已配置
- 前端支持图片上传、拖拽上传
- 知识库支持 AI 自动分类标签、对话知识自动入库
- 长期记忆系统已上线（用户偏好/对话摘要/知识图谱）
- 企业微信集成已上线（支持私聊/群聊@机器人，微信插件在普通微信内对话）
- 企业微信通知已可靠化（任务分配/到期提醒/逾期通知均可送达，消息格式兼容微信插件端）
- 任务双向通知（创建任务和即将到期时同时通知管理员和负责人）
- 语音识别准确性全面优化（修复 SILK 采样率 bug、领域提示词、beam_size 优化、结果后处理）
- 主动提醒已上线（Redis 精确调度 + Celery 10秒轮询，秒级精度，24小时内不重复提醒）
- 时间精度全面升级（分钟级截止日期、精确逾期判断、系统提示词实时注入当前时间）
- 任务权限控制已上线（管理员可分配任务给任何人，普通成员可编辑自己创建或被分配的任务）
- 自定义提醒已上线（创建任务时可设置多个自定义提醒时间点，支持"5分钟后提醒我"等自然语言）
- 微信插件身份识别已升级（多信号识别、重名消歧、验证缓存失效、插件用户 UserId 自动绑定）
- 联网搜索已上线（搜狗微信+必应双引擎并发搜索）
- 管理员身份感知（系统提示词注入当前用户姓名和角色，Agent 知道谁是管理员）
- Agent 回答准确性优化（query_tasks 返回真实负责人姓名，禁止编造人名）
- Agent 回复完整性优化（系统提示词强制完整输出 + max_tokens 提升至 8192 + 截断自动续写机制）
- 代码质量优化第一批（清理 25 处无效代码 + 9 个未使用依赖，净减 118 行）
- 代码质量优化第二批（提取 7 处后端重复逻辑 + 7 处前端重复逻辑，新建 3 个共享模块，净减 57 行）
- 开发环境 Docker 配置（docker-compose.dev.yml，热重载，轻量化）
- GitHub Actions CI 流水线（语法检查 + Docker 构建测试）
- 部署文档已完善（docs/deploy.md），生产环境已加固（Docker 健康检查+资源限制、Nginx 限流、JSON 日志、数据库备份脚本）
- 文件问答、会议助手等功能待实现（见"待实现功能"）

### 待解决问题

- 9 位成员未在企业微信通讯录中，无法接收提醒推送（需在企业微信管理后台添加成员）
- 腾讯会议 API 凭据待配置

详见 [ROADMAP.md](ROADMAP.md)

## 许可证

MIT License
