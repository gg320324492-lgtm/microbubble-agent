# 工单 M2-2：本地会议档案（纪要 / 转录 / 附件）

> 签发：总指挥 · 2026-09-17
> 上游：M2-1 已验收关闭（`a558d2ba0` + `b4f2efce9`）；测试基线 **126** 条全绿
> 里程碑：M2 第 2/3 张（本单 → M2-3 网页端导入向导）
> **明确不做（本期，骨架计划既定）**：实时录音、声纹通话、说话人分离——会议档案 v1 只做「开完会之后的资料本地化」

## 你的任务背景

侧边栏「会议」是最后一个占位页。本工单把它转正为**本地会议档案**：会议条目（标题/日期/地点/参会人）、纪要（Markdown 文本）、转录文本（导入或粘贴）、附件文件——全部本地存储、可检索、断网全功能（D5 底线）。

M2-1 留给你的复用资产（接口建议已采纳）：
- `cjk-bigram`（切词/查询 phrase）与 `buildExcerpt`（原文摘录+高亮偏移）——本单检索直接复用
- **把「切词→FTS 同步」封装成共享 helper**（如 `src/main/db/fts.ts`），knowledge 与 meetings 共用；重构 knowledge 侧接线时现有 17 条测试会锁定行为，允许小步重构
- 原件副本目录约定：`userData/files/meetings/<meetingId>/<name>`（与 knowledge 同级同风格）
- `trashItem` 注入模式（删除走回收站）——本单附件删除沿用；**附件「打开」需要 `shell.openPath`，同样注入式**（ipc.ts 装配时注入，服务与测试零 Electron import）

技术栈约束同前：主进程 better-sqlite3；测试 node:sqlite（`openNodeSqlite` 模式），绝不 import 依赖 Electron ABI 的模块。

## 常设红线（违反任一直接打回）

1. 保护路径零改动：`app/`、`web/`、`alembic/`、`nginx/`、`docker-compose*`、`.env`、`desktop-conversion/` 一律不碰；交付时贴 `git status --short` 自证
2. 禁止 `git add -A`；只提交：`git commit -- apps/desktop`；遇 `.git/index.lock` 等待重试，禁止删锁
3. 禁止新增任何 npm 依赖
4. 完成门禁：`pnpm test` 全绿（当前基线 **126** 条，需新增 ≥12 条）、`pnpm typecheck` 0 错、`pnpm build` 成功
5. IPC 白名单三处同步（`src/shared/ipc-channels.ts` / `main/ipc.ts` / `preload`），一致性测试自动校验

## 交付物

### 1. 迁移 007（追加 MIGRATIONS，勿动 001-006）

- `meetings`：`id INTEGER PK AUTOINCREMENT / user_id TEXT NOT NULL / title TEXT NOT NULL / meeting_date INTEGER / location TEXT NOT NULL DEFAULT '' / attendees TEXT NOT NULL DEFAULT '[]'（JSON 数组）/ minutes TEXT NOT NULL DEFAULT ''（纪要 Markdown）/ created_at INTEGER / updated_at INTEGER` + user 索引
- `meeting_transcripts`：`id INTEGER PK AUTOINCREMENT / meeting_id INTEGER NOT NULL / content TEXT NOT NULL / source TEXT NOT NULL DEFAULT 'paste'（paste/txt/srt）/ created_at INTEGER / updated_at INTEGER`（一会议可多条，UI 至少支持首条读写）
- `meeting_files`：`id INTEGER PK AUTOINCREMENT / meeting_id INTEGER NOT NULL / file_name TEXT NOT NULL / file_size INTEGER NOT NULL / created_at INTEGER`（文件本体在 `userData/files/meetings/<meetingId>/`）
- FTS：覆盖 **标题 + 纪要 + 转录**（单虚表多列或分表，方案自定说明理由；索引列=切词文本，复用 bigram）

### 2. MeetingService（`src/main/services/meeting/`）

- `create / list / get / update / delete`（delete：删除记录 + 附件文件进回收站，先确认语义：整会删除含附件）
- 转录：`getTranscripts / importTranscript（.txt/.srt 文本读入，source 标记）/ updateTranscript`
- 附件：`addFile（复制进 userData/files/meetings/<id>/）/ removeFile（回收站）/ openFile（注入 openPath）`
- `search(userId, query)`：标题+纪要+转录全文检索，返回命中摘录（复用 `buildExcerpt`），上限 50

### 3. IPC 通道组（`meetings:*`，白名单三处同步 + 契约测试）

通道划分自定（建议 list/get/create/update/delete/transcript/file-add/file-remove/file-open/search 量级），`trashItem` 与 `openPath` 注入装配写在 ipc.ts

### 4. UI（`renderer/views/MeetingsView.vue` 占位转正 + 侧边栏挂接，**记得到 SideNav 移除占位徽标**）

- 列表（日期 + 标题 + 检索框「支持中文」）+ 「＋ 新建会议」表单（标题/日期/地点/参会人逗号分隔）
- 详情页三区：**纪要**（textarea 编辑保存，同知识库交互）/ **转录**（列表 + 导入文件 + 粘贴新建 + 编辑）/ **附件**（添加、列表、打开、删除走回收站确认）
- 空态引导文案

### 5. 测试（≥12，全部离线）

- 迁移 007 / 会议 CRUD / 转录导入（.txt 与 .srt 文本、source 标记）/ 检索中文 2 字词（纪要内 + 转录内各一）/ 编辑后索引同步 / 附件添加（复制落盘）/ 附件删除（回收站注入断言）/ openPath 注入断言（收到绝对路径恰一次）/ 用户隔离 / 现有 **126** 条零回归

## 定义完成（全部满足才算完）

- [ ] 门禁全过：test 126 + 新增 ≥12、typecheck 0 错、build 成功
- [ ] `git status --short` 无保护路径改动
- [ ] 断网自证：建会 → 纪要 → 转录 → 附件 → 检索 → 删除 全流程离线可用
- [ ] 交付报告第 6 项：CHANGELOG 条目草稿（并入下一版）

## 交付报告格式（七项制）

1. 变更/新增文件清单（路径+行数）
2. 门禁输出尾部（注明测试条数：基线 126 → 共 N 条）
3. commit hash + 提交信息
4. 自测记录：FTS 覆盖方案说明 + 各用例结果表
5. 遗留问题 / 对 M2-3（网页端导入向导）的接口建议
6. **版本迭代信息（CHANGELOG 条目草稿）**
