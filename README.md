# 微纳米气泡课题组智能Agent系统

"小气" - 微纳米气泡课题组AI智能助手

## 功能特性

- **智能对话** - 支持文字/语音与Agent交互
- **任务管理** - 创建、分配、追踪任务，智能提醒
- **会议助手** - 自动旁听会议、实时转写、生成纪要
- **项目管理** - 课题管理、进度追踪、里程碑管理
- **知识库** - 文献管理、实验记录、AI问答
- **成员管理** - 课题组成员信息管理

## 技术栈

| 组件 | 技术 |
|------|------|
| 后端 | FastAPI + SQLAlchemy + PostgreSQL |
| 前端 | Vue 3 + Element Plus + Vite |
| AI | Claude API |
| 语音 | Whisper + Edge-TTS |
| 缓存 | Redis |
| 存储 | MinIO |
| 部署 | Docker Compose |

## 快速开始

### 1. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入你的配置
```

### 2. 启动服务

```bash
# 开发模式
docker-compose -f docker-compose.dev.yml up -d

# 生产模式
docker-compose up -d
```

### 3. 初始化数据库

```bash
docker-compose exec app python scripts/init_db.py
```

### 4. 访问系统

- Web界面: http://localhost
- API文档: http://localhost:8000/docs
- MinIO控制台: http://localhost:9001

## 项目结构

```
microbubble-agent/
├── app/                  # 后端应用
│   ├── agent/           # AI Agent核心
│   ├── api/             # API接口
│   ├── core/            # 核心模块
│   ├── models/          # 数据模型
│   ├── schemas/         # Pydantic模型
│   └── services/        # 业务服务
├── web/                 # 前端应用
│   └── src/
│       ├── views/       # 页面组件
│       ├── layouts/     # 布局组件
│       └── router/      # 路由配置
├── scripts/             # 脚本工具
├── docker-compose.yml   # Docker编排
└── .env.example         # 环境变量示例
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

- `POST /api/v1/chat` - 对话接口
- `GET/POST /api/v1/tasks` - 任务管理
- `GET/POST /api/v1/meetings` - 会议管理
- `GET/POST /api/v1/members` - 成员管理
- `GET/POST /api/v1/projects` - 项目管理
- `GET/POST /api/v1/knowledge` - 知识库

详细文档: http://localhost:8000/docs

## 许可证

MIT License
