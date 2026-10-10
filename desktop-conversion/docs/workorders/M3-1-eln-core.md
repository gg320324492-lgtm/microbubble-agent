# 工单 M3-1：实验记录本 ELN 本地核心（迁移 008 + 全文检索 + 附件）

> 签发：总指挥 · 2026-09-17
> 上游：M2-2 已验收关闭（`f7aea2986` + 缩放加固 `9d8755570`）；测试基线 **144** 条全绿
> 里程碑：M3 第 1 张（M2-3 已裁决后移，见 DECISIONS.md 2026-09-17 裁决条目）

## 你的任务背景

侧边栏「实验 ELN」是最后一个占位页（稿件也是占位，但属 M3-2）。本工单把它转正为**本地实验记录本**：实验条目（标题/编号/状态/标签）、Markdown 实验记录、附件文件、全文检索——全部本地、断网全功能（D5 底线）。与知识库/会议档案同构，本单应显著快于前两单。

直接复用的成熟资产：
- `src/main/db/fts.ts` 共享 helper（ftsSyncRow / ftsDeleteRow）+ `cjk-bigram` / `buildExcerpt`（检索三件套）
- `trashItem` / `openPath` 注入模式（ipc.ts 装配时注入，服务与测试零 Electron import）
- 目录约定：`userData/files/experiments/<experimentId>/<name>`（与 knowledge/meetings 同级同风格）
- 迁移模式：MIGRATIONS 数组追加 008，勿动 001-007

技术栈约束同前：主进程 better-sqlite3；测试 node:sqlite（`openNodeSqlite` 模式），绝不 import 依赖 Electron ABI 的模块。

## 常设红线（违反任一直接打回）

1. 保护路径零改动：`app/`、`web/`、`alembic/`、`nginx/`、`docker-compose*`、`.env`、`desktop-conversion/` 一律不碰；交付时贴 `git status --short` 自证
2. 禁止 `git add -A`；只提交：`git commit -- apps/desktop`；遇 `.git/index.lock` 等待重试，禁止删锁
3. 禁止新增任何 npm 依赖
4. 完成门禁：`pnpm test` 全绿（当前基线 **144** 条，需新增 ≥12 条）、`pnpm typecheck` 0 错、`pnpm build` 成功
5. IPC 白名单三处同步（`src/shared/ipc-channels.ts` / `main/ipc.ts` / `preload`），一致性测试自动校验

## ⚠ 前车之鉴（本单必查，均已有前科）

1. **交付前必须重启 dev 并确认新页面真实生效**——M2-2 曾因旧实例骗过一轮目验
2. **fake 注入函数所需 fs 符号（mkdirSync 等）必须显式导入**——M2-1/M2-2 连续两单在此翻车
3. **SideNav 占位徽标**——M2-1/M2-2 连续两单漏移除，本单交付前自检「实验」图标徽标已去
4. **触控板/滚轮缩放已全局锁定**（`9d8755570`），不要试图用缩放「修复」显示问题

## 交付物

### 1. 迁移 008（追加 MIGRATIONS，勿动 001-007）

- `experiments`：`id INTEGER PK AUTOINCREMENT / user_id TEXT NOT NULL / title TEXT NOT NULL / code TEXT NOT NULL DEFAULT ''（实验编号，如 EXP-20260917-01）/ status TEXT NOT NULL DEFAULT 'ongoing'（draft/ongoing/completed/archived）/ tags TEXT NOT NULL DEFAULT '[]'（JSON 数组）/ content TEXT NOT NULL DEFAULT ''（Markdown 实验记录）/ created_at INTEGER / updated_at INTEGER` + user 索引
- `experiment_files`：`id INTEGER PK AUTOINCREMENT / experiment_id INTEGER NOT NULL / file_name TEXT NOT NULL / file_size INTEGER NOT NULL / created_at INTEGER`（文件本体在 `userData/files/experiments/<id>/`）
- `experiments_fts`：FTS5 虚表（title_seg, content_seg），索引列=bigram 切词文本，走共享 helper

### 2. ExperimentService（`src/main/services/experiment/`）

- `create / list / get / update / delete`：编号自动生成（`EXP-YYYYMMDD-` + 当日序号，可手改）；status 四态流转；delete 含附件进回收站（确认语义同会议）
- `list` 支持按 status 筛选 + 更新时间倒序
- 附件：`addFile（复制落盘，重名追加 (2)）/ removeFile（回收站）/ openFile（注入 openPath）`
- `search(userId, query)`：标题+记录全文检索，摘录取原文（`buildExcerpt`），命中区域标注，上限 50

### 3. IPC 通道组（`experiments:*`，白名单三处同步 + 契约测试）

通道划分自定（list/get/create/update/delete/file-add/file-remove/file-open/search 量级）

### 4. UI（`renderer/views/ExperimentView.vue` 占位转正 + 路由 + **SideNav 移除「实验」M3 占位徽标**）

- 列表页：状态筛选（全部/草稿/进行中/已完成/已归档 chips）+ 检索框（「支持中文」）+ 「＋ 新建实验」+ 卡片（编号/标题/状态徽标/标签/更新时间）+ 空态引导
- 详情页：头部（编号/标题/状态流转按钮/删除）+ 记录 Markdown 编辑保存（同知识库交互）+ 附件三件套（添加/打开/删除走回收站）
- 视觉对标 KnowledgeView/MeetingsView 的容器与排版规范（max-width 容器、设计令牌字号间距）

### 5. 测试（≥12，全部离线）

- 迁移 008 / CRUD 往返 / 编号自动生成（同日递增）+ 手改 / status 四态流转与筛选 / 检索中文 2 字词（记录内命中 + hitSource）/ 编辑后索引同步（旧词 0 新词 1）/ 附件添加复制落盘 + 删除回收站注入 + openPath 注入断言 / 用户隔离 / 现有 **144** 条零回归

## 定义完成（全部满足才算完）

- [ ] 门禁全过：test 144 + 新增 ≥12、typecheck 0 错、build 成功
- [ ] `git status --short` 无保护路径改动
- [ ] **重启 dev 实测确认**：新页面真实生效（截图留证，防旧实例骗检）
- [ ] 断网自证：建实验 → 记录 → 检索 → 附件 → 删除 全流程离线可用
- [ ] 交付报告第 6 项：CHANGELOG 条目草稿（并入 R-2/v0.1.1-alpha）

## 交付报告格式（七项制）

1. 变更/新增文件清单（路径+行数）
2. 门禁输出尾部（注明测试条数：基线 144 → 共 N 条）
3. commit hash + 提交信息
4. 自测记录：编号生成规则 + 各用例结果表
5. 遗留问题 / 对 M3-2（稿件）的接口建议
6. **版本迭代信息（CHANGELOG 条目草稿）**
