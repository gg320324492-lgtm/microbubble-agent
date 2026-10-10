# 工单 M2-1：本地知识库核心（迁移 006 + FTS5 中文检索 + 导入/浏览/编辑）

> 签发：总指挥 · 2026-09-17
> 状态：**已起草，待激活**——激活条件：v0.1.0-alpha Release 已 publish（总指挥确认）
> 上游：M1-C 闭环 + R-1 发布；测试基线 **109** 条全绿
> 里程碑：M2 共三张——本单（知识库核心）→ M2-2 会议档案 → M2-3 网页端导入向导（依赖云端绑定，后置）

## 你的任务背景

侧边栏「知识库」目前是占位页。本工单把它转正为**本地知识库**：Markdown/文本文档本地导入、SQLite 存储、FTS5 全文检索（**中文可用是硬验收项**）、浏览与编辑。断网全功能（D5 验收底线：数据本地、交互本地，模型 API 是唯一允许的外部依赖，本单甚至用不到它）。

技术栈约束同前：主进程 better-sqlite3；**测试 node:sqlite（`openNodeSqlite` 模式），绝不 import 依赖 Electron ABI 的模块**。

## 常设红线（违反任一直接打回）

1. 保护路径零改动：`app/`、`web/`、`alembic/`、`nginx/`、`docker-compose*`、`.env`、`desktop-conversion/` 一律不碰；交付时贴 `git status --short` 自证
2. 禁止 `git add -A`；只提交：`git commit -- apps/desktop`；遇 `.git/index.lock` 等待重试，禁止删锁
3. 禁止新增任何 npm 依赖
4. 完成门禁：`pnpm test` 全绿（当前基线 **109** 条，需新增 ≥12 条）、`pnpm typecheck` 0 错、`pnpm build` 成功
5. IPC 白名单三处同步（`src/shared/ipc-channels.ts` / `main/ipc.ts` / `preload`），一致性测试自动校验

## 第 0 步：FTS5 可用性探针（先做，结论写进交付报告）

分别在 node:sqlite（测试运行时）与 better-sqlite3（应用运行时）建内存库执行 `CREATE VIRTUAL TABLE t USING fts5(x)` 与一次 match 查询：
- 两者都支持 → 按标准方案实现
- **node:sqlite 不支持** → 停下报告，等总指挥裁决测试策略（不得擅自改动测试基建或降级实现）

## 交付物

### 1. 迁移 006（追加 MIGRATIONS，勿动 001-005）

- `knowledge_documents`：`id INTEGER PK AUTOINCREMENT / user_id TEXT / title TEXT / content TEXT / file_name TEXT / file_size INTEGER / tags TEXT（JSON 数组）/ source TEXT DEFAULT 'local_import' / created_at INTEGER / updated_at INTEGER`
- FTS5 虚表（title + content 入索引）。**中文检索方案**：FTS5 默认 tokenizer 对中文不友好，用 trigram 或「存储前字元 bigram 预切词」，选型前先做小探针验证**能稳定搜到 2 字中文词**，方案与理由写进交付报告；同步方式（触发器/应用层）自定

### 2. KnowledgeService（`src/main/services/knowledge/knowledge.service.ts`）

- `importFromFiles(userId, files: {name, content}[])`：渲染层文件选择器读文本后传主进程（多选 .md / .markdown / .txt）；同名文档给提示不静默覆盖；空内容拒绝；原件副本存 `userData/files/knowledge/<id>_<name>`
- `list(userId)` / `get(userId, id)` / `update(userId, id, {title?, content?, tags?})`（保存后 FTS 索引同步）/ `delete(userId, id)`（删记录 + 原件副本走系统回收站——复用 C-3 的 trashItem 注入模式）
- `search(userId, query)`：FTS5 match，返回标题 + 命中片段（snippet）+ 高亮偏移，按相关度排序，上限 50

### 3. IPC 通道组

`knowledge:list / get / import / update / delete / search`——白名单三处同步 + 契约测试

### 4. UI（`renderer/views/KnowledgeView.vue` 占位转正 + 侧边栏挂接）

- 列表（标题/标签/更新时间）+ 搜索框（命中片段预览，回车或输入即检）+ 「导入文档」按钮 + 空态引导文案
- 详情查看 + 编辑保存（纯 textarea 即可，Markdown 渲染预览后置不阻塞本单）

### 5. 测试（≥12，全部离线，临时目录 + node:sqlite）

- 迁移 006 / 导入（正常 + 重名提示 + 空内容拒绝）/ 列表 / **中文检索（2 字词必测 + 多字词 + 无命中 + snippet 正确）** / 编辑后检索索引同步 / 删除（记录 + 副本进回收站注入验证）/ 现有 109 条零回归

## 定义完成（全部满足才算完）

- [ ] 门禁全过：test 109 + 新增 ≥12、typecheck 0 错、build 成功
- [ ] `git status --short` 无保护路径改动
- [ ] 断网自证：导入 → 检索 → 编辑 → 删除全流程离线可用
- [ ] 交付报告第 6 项：CHANGELOG 条目草稿（v0.1.0-alpha 之后下一版的「知识库」条目）

## 交付报告格式（沿用七项制）

1. 变更/新增文件清单（路径+行数）
2. 门禁输出尾部（注明测试条数：基线 109 → 共 N 条）
3. commit hash + 提交信息
4. 自测记录：FTS5 双运行时探针结论 + 中文检索方案选型依据 + 各用例结果表
5. 遗留问题 / 对 M2-2（会议档案）的接口建议
6. **版本迭代信息（CHANGELOG 条目草稿）**
7. （如触发）FTS5 探针异常的报告与待裁决项
