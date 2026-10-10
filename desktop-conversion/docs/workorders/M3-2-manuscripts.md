# 工单 M3-2：本地稿件库（迁移 009 + 全文检索 + 附件 + 字数统计）

> 签发：总指挥 · 2026-09-18
> 上游：R-2（v0.1.1-alpha）已发布；测试基线 **160** 条全绿
> 里程碑：M3 第 2 张——**本单完成后六大 IA 全部落位**（AI 助手/实验 ELN/稿件/知识库/会议/设置）

## 你的任务背景

侧边栏「稿件」是最后一个占位页。本单把它转正为**本地稿件库**：稿件条目（标题/目标期刊/状态/标签）、Markdown 正文、字数统计、附件、全文检索——与知识库/会议/ELN 完全同构，全部本地、断网全功能。

直接复用的成熟四件套（三单验证过，勿重造）：
- `fts.ts` 共享 helper（ftsSyncRow / ftsDeleteRow）
- `cjk-bigram` / `buildExcerpt`（检索）
- `trashItem` / `openPath` 注入模式（ipc.ts 装配）
- 目录约定：`userData/files/manuscripts/<manuscriptId>/<name>`

技术栈约束同前：主进程 better-sqlite3；测试 node:sqlite（`openNodeSqlite` 模式），绝不 import 依赖 Electron ABI 的模块。

## 常设红线（违反任一直接打回）

1. 保护路径零改动：`app/`、`web/`、`alembic/`、`nginx/`、`docker-compose*`、`.env`、`desktop-conversion/` 一律不碰；交付时贴 `git status --short` 自证
2. 禁止 `git add -A`；只提交：`git commit -- apps/desktop`；遇 `.git/index.lock` 等待重试，禁止删锁
3. 禁止新增任何 npm 依赖
4. 门禁：`pnpm test` 全绿（当前基线 **160** 条，需新增 ≥12 条）、`pnpm typecheck` 0 错、`pnpm build` 成功
5. IPC 白名单三处同步（`src/shared/ipc-channels.ts` / `main/ipc.ts` / `preload`），一致性测试自动校验

## ⚠ 前车之鉴四项（M2/M3 连续踩过，交付前自查）

1. **重启 dev 实测新页面真实生效**（M2-2 旧实例骗过一轮目验；交付附生效截图）
2. **fake 注入函数所需 fs 符号显式导入**（M2-1/M2-2 连续翻车）
3. **SideNav 移除「稿件」M3 占位徽标**（M2-1/M2-2 连续漏掉）
4. 缩放已全局锁定，勿动 `9d8755570` 的两处拦截

## 交付物

### 1. 迁移 009（追加 MIGRATIONS，勿动 001-008）

- `manuscripts`：`id INTEGER PK AUTOINCREMENT / user_id TEXT NOT NULL / title TEXT NOT NULL / status TEXT NOT NULL DEFAULT 'draft'（draft/revising/submitted/published 四态，参照 ELN 的 normalizeStatus + 非法态拒绝模式）/ target_journal TEXT NOT NULL DEFAULT ''（目标期刊）/ tags TEXT NOT NULL DEFAULT '[]'（JSON 数组）/ content TEXT NOT NULL DEFAULT ''（Markdown 正文）/ created_at INTEGER / updated_at INTEGER` + user 索引
- `manuscript_files`：同 meeting_files 模式（id / manuscript_id / file_name / file_size / created_at）
- `manuscripts_fts`：FTS5（title_seg, content_seg），索引列=bigram 切词文本，走共享 helper

### 2. ManuscriptService（`src/main/services/manuscript/`）

- `create / list / get / update / delete`：四态流转（normalizeStatus 模式，非法态拒绝）；list 支持 status 筛选 + 更新倒序；delete 含附件回收站
- `stats(content)`：**字数统计纯函数**——中文字符数 + 总词数（中英混合），详情与编辑区展示；纯函数独立导出便于单测
- 附件：`addFile / removeFile（回收站）/ openFile（注入）`
- `search(userId, query)`：标题+正文检索，摘录 `buildExcerpt`，上限 50

### 3. IPC 通道组（`manuscripts:*`，白名单三处同步 + 契约测试）

### 4. UI（`renderer/views/ManuscriptsView.vue` 占位转正 + 路由 + **SideNav 移除「稿件」M3 占位徽标**）

- 列表：状态筛选 chips（全部/草稿/修改中/已投稿/已发表）+ 检索框（「支持中文」）+ 「＋ 新建稿件」+ 卡片（标题/状态徽标/目标期刊/字数/更新时间）+ 空态引导
- 详情：头部（标题/状态流转/删除）+ 目标期刊与字数展示 + 正文 Markdown 编辑保存 + 附件三件套
- 视觉对标 KnowledgeView/MeetingsView/ExperimentView 规范

### 5. 测试（≥12，全部离线）

- 迁移 009 / CRUD 往返 / 四态流转全合法 + 非法态拒绝 / status 筛选倒序 / **字数统计纯函数**（纯中文、纯英文、中英混合三例）/ 检索中文 2 字词（正文内命中 + hitSource）/ 编辑后索引同步 / 附件落盘 + 回收站注入 + openPath 注入 / 用户隔离 / 现有 **160** 条零回归

## 定义完成（全部满足才算完）

- [ ] 门禁全过：test 160 + 新增 ≥12、typecheck 0 错、build 成功
- [ ] `git status --short` 无保护路径改动
- [ ] **重启 dev 实测确认**新页面真实生效（截图留证）
- [ ] 断网自证：建稿 → 正文 → 检索 → 附件 → 删除 全流程离线可用
- [ ] 交付报告第 6 项：CHANGELOG 条目草稿（并入下一版）

## 交付报告格式（六项制）

1. 变更/新增文件清单（路径+行数）
2. 门禁输出尾部（注明测试条数：基线 160 → 共 N 条）
3. commit hash + 提交信息
4. 自测记录：字数统计规则 + 各用例结果表
5. 遗留问题 / 对 M4（桌面集成）的建议
6. **版本迭代信息（CHANGELOG 条目草稿）**
