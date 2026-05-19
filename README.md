# 微纳米气泡课题组智能Agent系统

"小气" - 微纳米气泡课题组AI智能助手（约20人研究实验室）

## 功能特性

- **智能对话** - 支持文字/语音/图片/文件与Agent交互，多模态识别，拖拽上传
- **联网搜索** - 搜狗微信+必应双引擎并发搜索，自动获取最新信息
- **任务管理** - 创建、分配、追踪任务，智能提醒
- **会议助手** - 自动旁听会议、实时转写、生成纪要、自动分析要点
- **项目管理** - 课题管理、进度追踪、里程碑管理
- **知识库** - 文献管理、实验记录、语义搜索（pgvector），AI 自动分类标签，对话知识自动入库
- **长期记忆** - 用户偏好记忆、对话摘要、知识图谱构建
- **成员管理** - 课题组成员信息管理
- **企业微信集成** - 群机器人对话、任务派发、进度回复、主动提醒
- **微信插件支持** - 通过微信插件在普通微信内与机器人对话（需一次性注册企业微信）
- **腾讯会议集成** - 自动创建线上会议、Webhook 回调、转写分析
- **文件管理** - MinIO 文件上传，支持会议附件和对话文件
- **自动部署** - GitHub Webhook 触发，push 后自动构建部署

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

✅ **已上线运行** - 核心功能全部完成，生产环境部署成功

- Phase 1-6 代码全部完成
- 云服务器部署成功（https://agent.mnb-lab.cn）
- GitHub Webhook 自动部署已配置
- 前端支持图片/文件上传、拖拽上传
- 知识库支持 AI 自动分类标签、对话知识自动入库
- 长期记忆系统已上线（用户偏好/对话摘要/知识图谱）
- 微信互通功能暂不需要（当前使用微信插件方案）
- 腾讯会议待配置 API 凭据

详见 [ROADMAP.md](ROADMAP.md)

## 许可证

MIT License
