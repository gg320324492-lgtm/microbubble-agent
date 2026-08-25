# Scientific Research OS 适应性迁移正式发布实施计划

> **面向 AI 代理的工作者：** 必需子技能：使用 `superpowers:executing-plans` 按批次执行。每个批次完成后运行本批的验证命令、提交指定文件，并等待主指挥放行下一批。

**目标：** 在不修改网页版生产代码、数据库、对象存储或部署配置的条件下，将网页资料转换为可校验 `.mbrp` 包，并使其成为桌面端本地研究工作区的可编辑资料。

**架构：** 迁移流程固定为“网页端只读快照 → NDJSON 与附件清单 → 语义转换 → `.mbrp` ZIP → 桌面端预检 → staging 导入 → 原子切换”。桌面端只写入自身 `userData` 下的 SQLite 与工作区文件；网页端继续作为独立、未改动的原系统运行。

**技术栈：** Electron、TypeScript、better-sqlite3、Node `crypto`、Markdown/JSON/CSV 文件、Python 3.11 只读导出脚本、PostgreSQL 只读角色、MinIO 只读凭据、NSIS。

---

## 全程硬约束

- Claude Code 只能修改 `desktop/`、`docs/superpowers/`、`scripts/desktop_migration/` 与 `tests/desktop_migration/`。
- 禁止修改 `app/`、`web/`、`alembic/`、`docker-compose*.yml`、`nginx/`、`.env`、线上数据库与 MinIO 对象。
- 禁止对网页端执行任何写 SQL；导出连接必须使用数据库只读账号，并在会话开始后执行 `SET TRANSACTION READ ONLY`。
- 禁止迁移密码哈希、JWT、刷新令牌、支付密钥、企业微信密钥、Webhook 密钥和声纹向量。
- R0 首先把开始本发布项目时受保护路径的 Git tree ID 写入 `desktop/resources/release-protected-baseline.json`；该文件是本次发布的基线，不与 `main` 或其他历史分支比较。
- 每一批开始和结束都运行：

```powershell
npm run release:guard
```

预期：脚本确认当前 HEAD 和工作区中 `app`、`web`、`alembic`、`docker-compose*.yml`、`nginx`、`.env` 的 tree ID/文件状态均与 R0 基线一致。若有差异，立即停止并把文件清单报告给主指挥。

## 发布批次与顺序

| 批次 | 交付 | 依赖 | 放行条件 |
|---|---|---|---|
| R0 | 发布隔离与构建可复现性 | 无 | 网页端零改动守卫通过 |
| R1 | `.mbrp` 格式与校验库 | R0 | 包读写、篡改检测通过 |
| R2 | 网页端只读快照导出器 | R1 | 只读角色与快照清单通过 |
| R3 | 语义转换器 | R2 | 固定夹具生成确定性包 |
| R4 | 桌面端 staging 导入与本地工作区 | R1、R3 | 失败不污染正式资料库 |
| R5 | 历史资料可编辑工作区 | R4 | 项目、任务、会议、文档、对话可操作 |
| R6 | 可靠性与发布通道 | R4 | 备份恢复、签名、更新、安装升级通过 |
| R7 | 正式发布演练 | R0-R6 | 迁移、断网、重装恢复全部通过 |

## 资料重写口径

| 源资料 | 目标文件 | 本地可操作方式 |
|---|---|---|
| 项目、里程碑、任务 | `projects/<id>/overview.md`、`work-items.json`、`timeline.json` | 项目概览、任务状态、负责人、截止日期和依赖关系可编辑 |
| 实验与数据 | `experiments/<id>/*.csv`、`conditions.json`、`eln.md` | 进入本地项目/实验/测量/ELN 索引，支持再分析 |
| 会议资料 | `meetings/<id>/record.md`、`transcript.md`、`attachments/` | 编辑纪要与转录，播放原始音频/视频附件 |
| 知识库与网盘 | `knowledge/<id>/`、`drive/<id>/current/`、`versions/` | 编辑当前文档，查看旧版本、评论和来源 |
| 聊天 | `conversations/<id>.md` 与 `<id>.json` | 全文检索、编辑整理后的归档；新对话在桌面端生成 |
| 审计与通知 | `audit/*.ndjson` | 只读证据，保留时间与来源 |

云端特有动作（支付、企业微信回调、公共分享链接、腾讯会议创建、推送订阅）不在本地重演范围内；其历史记录归档到 `.mbrp`，原网页端保持原样继续服务。

---

### 任务 R0：建立发布隔离与可复现构建

**文件：**
- 创建：`desktop/scripts/release/verify-web-unchanged.mjs`
- 创建：`desktop/scripts/release/write-build-metadata.mjs`
- 创建：`desktop/resources/release-protected-baseline.json`
- 修改：`desktop/package.json`
- 修改：`desktop/electron-builder.yml`
- 创建：`desktop/tests/release/release-guard.test.ts`

- [ ] **步骤 1：先写失败的零影响守卫测试**

测试以临时 Git 仓库创建 `desktop/a.txt` 与 `web/a.txt` 两种变更，断言脚本仅在 `web/a.txt` 出现时失败：

```ts
expect(runGuard(['desktop/a.txt']).status).toBe(0)
expect(runGuard(['web/a.txt']).status).toBe(1)
expect(runGuard(['web/a.txt']).stderr).toContain('网页端受保护路径发生变更')
```

- [ ] **步骤 2：运行失败测试**

运行：

```powershell
npx vitest run tests/release/release-guard.test.ts
```

预期：FAIL，提示 `verify-web-unchanged.mjs` 不存在。

- [ ] **步骤 3：实现零影响守卫与构建元数据**

`verify-web-unchanged.mjs` 首次运行时将当前 `HEAD` 中受保护路径的 Git tree ID 写入 `release-protected-baseline.json`；之后比较当前 `HEAD` 与工作区的受保护路径状态，存在任一差异时写出完整文件名并以退出码 1 结束。脚本必须保护 `app`、`web`、`alembic`、`docker-compose*.yml`、`nginx` 和 `.env`，但不得把当前分支早于 R0 的历史差异误判为本发布造成的变更。`write-build-metadata.mjs` 读取 `git rev-parse HEAD`、UTC 时间和 `package.json.version`，写入 `desktop/resources/build-metadata.json`。在 `package.json` 添加：

```json
{
  "scripts": {
    "release:guard": "node scripts/release/verify-web-unchanged.mjs",
    "release:metadata": "node scripts/release/write-build-metadata.mjs",
    "build:release-win": "npm run release:guard && npm run release:metadata && npm run build:win"
  }
}
```

`electron-builder.yml` 的 `publish` 仅保留未启用的发布说明，不得让稳定版指向占位 URL。

- [ ] **步骤 4：验证并提交**

运行：

```powershell
npx vitest run tests/release/release-guard.test.ts
npm run release:guard
npm run typecheck
git add desktop/scripts/release desktop/resources/release-protected-baseline.json desktop/resources/build-metadata.json desktop/package.json desktop/electron-builder.yml desktop/tests/release
git commit -m "build(desktop): add zero-impact release guard"
```

预期：测试通过，守卫通过，工作区保护路径无变更。

### 任务 R1：定义并实现 `.mbrp` 包格式

**文件：**
- 创建：`desktop/src/main/migration/mbrp-types.ts`
- 创建：`desktop/src/main/migration/mbrp-manifest.ts`
- 创建：`desktop/src/main/migration/mbrp-archive.ts`
- 创建：`desktop/src/main/migration/index.ts`
- 修改：`desktop/package.json`
- 修改：`desktop/package-lock.json`
- 创建：`desktop/tests/migration/mbrp-archive.test.ts`

- [ ] **步骤 1：写失败的包完整性测试**

定义最小 `MbrpManifest`：`formatVersion`、`createdAt`、`sourceSnapshot`、`entities`、`files`、`warnings`。测试创建含一个 `projects/p-1/overview.md` 的包并断言读回内容与 SHA-256；改写 ZIP 内文件后断言 `verifyMbrp` 返回 `{ ok: false, code: 'CHECKSUM_MISMATCH' }`。

- [ ] **步骤 2：运行失败测试**

运行：

```powershell
npx vitest run tests/migration/mbrp-archive.test.ts
```

预期：FAIL，提示缺少 `@main/migration` 模块。

- [ ] **步骤 3：实现格式库**

引入一个锁定版本的 ZIP 依赖；`createMbrp(input)` 必须按路径字典序写入、为每个内容文件计算 SHA-256、最后写入 `manifest.json`。`openMbrp(path)` 不允许条目路径包含 `..`、绝对路径或重复名称。`verifyMbrp(path)` 必须逐文件比对清单，不允许遗漏或额外业务文件。

- [ ] **步骤 4：验证并提交**

运行：

```powershell
npx vitest run tests/migration/mbrp-archive.test.ts
npm run typecheck
git add desktop/src/main/migration desktop/package.json desktop/package-lock.json desktop/tests/migration
git commit -m "feat(desktop): add verified mbrp package format"
```

预期：篡改检测、非法路径检测和正常读写全部通过。

### 任务 R2：实现网页端只读快照导出器

**文件：**
- 创建：`scripts/desktop_migration/export_web_snapshot.py`
- 创建：`scripts/desktop_migration/snapshot_schema.py`
- 创建：`scripts/desktop_migration/requirements.txt`
- 创建：`tests/desktop_migration/test_export_web_snapshot.py`
- 创建：`docs/desktop-migration/operator-readonly-export.md`

- [ ] **步骤 1：写失败的只读会话测试**

使用 fake async connection，断言导出器的第一组 SQL 是 `BEGIN READ ONLY` 与 `SET TRANSACTION READ ONLY`；任何非 `SELECT`、`SHOW`、`SET TRANSACTION READ ONLY` 或 `ROLLBACK` 的语句均应引发 `UnsafeSourceQueryError`。

- [ ] **步骤 2：运行失败测试**

运行：

```powershell
python -m pytest tests/desktop_migration/test_export_web_snapshot.py -q
```

预期：FAIL，提示 `export_web_snapshot` 不存在。

- [ ] **步骤 3：实现确定性只读导出**

导出器接收 `--database-url`、`--minio-endpoint`、`--output-dir`、`--snapshot-id`。它为 members、projects、milestones、tasks、meetings、knowledge、drive、chat、audit 分别生成 UTF-8 NDJSON；每条记录写入 `source_type`、`source_id`、`source_updated_at`。附件只通过只读对象清单复制到 `objects/<sha256>`；导出结束写入 `snapshot-manifest.json`，含表计数、对象计数、每个文件 SHA-256 与开始/结束时间。密码、会话、密钥与声纹向量必须在查询层排除。

- [ ] **步骤 4：验证并提交**

运行：

```powershell
python -m pytest tests/desktop_migration/test_export_web_snapshot.py -q
python scripts/desktop_migration/export_web_snapshot.py --help
git add scripts/desktop_migration tests/desktop_migration docs/desktop-migration
git commit -m "feat(migration): add read-only web snapshot exporter"
```

预期：单元测试通过；帮助文本明确要求只读数据库用户与 MinIO 只读凭据。

### 任务 R3：将快照转换为语义化研究资料包

**文件：**
- 创建：`desktop/src/main/migration/semantic-converter.ts`
- 创建：`desktop/src/main/migration/converters/project-converter.ts`
- 创建：`desktop/src/main/migration/converters/meeting-converter.ts`
- 创建：`desktop/src/main/migration/converters/knowledge-converter.ts`
- 创建：`desktop/src/main/migration/converters/conversation-converter.ts`
- 创建：`desktop/tests/migration/semantic-converter.test.ts`
- 创建：`desktop/tests/fixtures/web-snapshot/minimal/`

- [ ] **步骤 1：写失败的转换夹具测试**

夹具包含一个项目、一个任务、一个会议、一个知识文档和一段聊天。断言输出包包含以下精确路径：

```text
projects/project-1/overview.md
projects/project-1/work-items.json
meetings/meeting-1/record.md
knowledge/knowledge-1/metadata.json
conversations/chat-1.md
```

同时断言相同夹具连续转换两次的文件清单和 SHA-256 完全相同。

- [ ] **步骤 2：运行失败测试**

运行：

```powershell
npx vitest run tests/migration/semantic-converter.test.ts
```

预期：FAIL，提示 `convertSnapshotToMbrp` 不存在。

- [ ] **步骤 3：实现转换器**

每个转换器只接收已经导出的 NDJSON 记录与附件路径，不得访问数据库或网络。任务转换器输出保留 `status`、`priority`、`assignee`、`dueDate`、`dependencies` 的 JSON，并在项目概览 Markdown 中生成可阅读清单。会议转换器将纪要、议程、转录和附件引用拆开保存。知识与网盘转换器必须保留源 ID、原路径、版本号、评论与对象 SHA-256。转换警告写入 manifest 的 `warnings`，不可静默丢弃记录。

- [ ] **步骤 4：验证并提交**

运行：

```powershell
npx vitest run tests/migration/semantic-converter.test.ts
npm run typecheck
git add desktop/src/main/migration desktop/tests/migration
git commit -m "feat(desktop): convert web snapshots into research packages"
```

预期：确定性转换、缺失附件告警与源 ID 追溯全部通过。

### 任务 R4：实现桌面端 staging 导入与原子切换

**文件：**
- 创建：`desktop/src/main/database/schema/010-migration-workspace.sql`
- 修改：`desktop/src/main/database/migration-manager.ts`
- 创建：`desktop/src/main/migration/mbrp-importer.ts`
- 创建：`desktop/src/main/migration/workspace-writer.ts`
- 修改：`desktop/src/main/services/database.service.ts`
- 修改：`desktop/src/main/ipc.ts`
- 修改：`desktop/src/preload/index.ts`
- 修改：`desktop/src/shared/preload-api.ts`
- 创建：`desktop/tests/migration/mbrp-importer.test.ts`

- [ ] **步骤 1：写失败的 staging 测试**

创建临时 user-data 目录与有效包，导入后断言 `migration_runs` 状态为 `completed`、工作区目录存在、`source_id_map` 有映射。再使用校验失败包，断言正式工作区与正式 SQLite 记录数保持导入前值，且 `migration_runs` 状态为 `failed`。

- [ ] **步骤 2：运行失败测试**

运行：

```powershell
npx vitest run tests/migration/mbrp-importer.test.ts
```

预期：FAIL，提示导入器或 migration schema 不存在。

- [ ] **步骤 3：实现 staging 导入**

`010-migration-workspace.sql` 创建 `migration_runs`、`source_id_map`、`workspace_documents` 三张表。导入器必须先 `verifyMbrp`，再写入 `<dataDir>/ScientificResearchOS/staging/<runId>`，完成 SQLite transaction 与工作区文件完整性检查后才通过同卷 `rename` 切换到 `<dataDir>/ScientificResearchOS/workspaces/current`。切换前创建数据库备份；失败时保留报告并删除仅属于该 run 的 staging 目录。IPC 只暴露 `migration:preflight`、`migration:import`、`migration:runs`，不暴露任意文件系统写入。

- [ ] **步骤 4：验证并提交**

运行：

```powershell
npx vitest run tests/migration/mbrp-importer.test.ts
npm run typecheck
git add desktop/src/main/database desktop/src/main/migration desktop/src/main/services/database.service.ts desktop/src/main/ipc.ts desktop/src/preload/index.ts desktop/src/shared/preload-api.ts desktop/tests/migration
git commit -m "feat(desktop): import mbrp through staged workspace"
```

预期：成功导入、校验失败隔离、再次导入同包幂等三种场景通过。

### 任务 R5：补齐本地历史资料工作区

**文件：**
- 创建：`desktop/src/renderer/src/pages/migration/MigrationCenter.vue`
- 创建：`desktop/src/renderer/src/pages/workspace/WorkItemsWorkspace.vue`
- 创建：`desktop/src/renderer/src/pages/workspace/MeetingArchiveWorkspace.vue`
- 创建：`desktop/src/renderer/src/pages/workspace/FileLibraryWorkspace.vue`
- 创建：`desktop/src/renderer/src/pages/workspace/ConversationArchiveWorkspace.vue`
- 修改：`desktop/src/renderer/src/router/index.ts`
- 修改：`desktop/src/renderer/src/layouts/Sidebar.vue`
- 创建：`desktop/tests/e2e/migration-workspace.spec.ts`

- [ ] **步骤 1：写失败的端到端验收脚本**

使用测试 `.mbrp` 包，验证：导入预检显示项目/任务/会议/知识/对话数量；任务状态可由 `in_progress` 改为 `done`；会议 Markdown 能保存；当前文件保存后生成新本地版本；对话归档可按关键词搜索。

- [ ] **步骤 2：运行失败验收**

运行：

```powershell
npx playwright test tests/e2e/migration-workspace.spec.ts
```

预期：FAIL，提示迁移中心路由不存在。

- [ ] **步骤 3：实现本地工作区页面**

迁移中心只通过三个 migration IPC 调用显示预检、进度和结果。工作项编辑器读写 `work-items.json`，每次保存产生带时间的版本副本并更新 `workspace_documents`。会议、文件库和对话归档页面使用同一个本地工作区根目录，所有路径由主进程返回受限 document ID，不允许 renderer 自行拼接绝对路径。页面必须明确区分“历史归档”与“新建桌面记录”。

- [ ] **步骤 4：验证并提交**

运行：

```powershell
npx playwright test tests/e2e/migration-workspace.spec.ts
npm run test:unit
npm run typecheck
git add desktop/src/renderer/src/pages desktop/src/renderer/src/router/index.ts desktop/src/renderer/src/layouts/Sidebar.vue desktop/tests/e2e
git commit -m "feat(desktop): add editable migrated research workspaces"
```

预期：四种历史资料均可打开并完成各自的编辑或搜索操作。

### 任务 R6：修复可靠性并建立发布分发链路

**文件：**
- 修改：`desktop/src/main/services/config/config.service.ts`
- 修改：`desktop/src/main/services/config/backup.service.ts`
- 修改：`desktop/src/main/services/update-service.ts`
- 修改：`desktop/electron-builder.yml`
- 创建：`desktop/scripts/release/verify-installed-app.ps1`
- 创建：`desktop/tests/release/backup-restore.test.ts`
- 创建：`desktop/tests/release/config-persistence.test.ts`
- 创建：`docs/desktop-migration/release-operator-runbook.md`

- [ ] **步骤 1：写失败的真实 SQLite 测试**

`config-persistence.test.ts` 写入一个 JSON 配置并重新打开数据库，断言值不丢失。`backup-restore.test.ts` 创建数据库、备份、修改一条项目记录、恢复备份，断言项目值回到备份时的内容且数据库文件路径等于 `resolveDatabaseConfig().path`。

- [ ] **步骤 2：运行失败测试**

运行：

```powershell
npx vitest run tests/release/config-persistence.test.ts tests/release/backup-restore.test.ts
```

预期：FAIL，配置 UPSERT 拼写错误或恢复没有定位数据库文件。

- [ ] **步骤 3：实现可靠性修复与发布配置**

将 `excludedCLUDED.value` 修正为 SQLite 合法的 `excluded.value`。备份服务必须从 `resolveDatabaseConfig().path` 推导备份目录与恢复目标，恢复前校验 SHA-256，恢复操作通过同卷临时文件与 `rename` 完成。更新服务只在配置了真实 HTTPS 发布清单和已验证签名时启用；未配置时在 UI 显示“手动更新”，不得伪造下载成功。`electron-builder.yml` 不允许 `sign: null` 作为稳定版构建配置；稳定版构建要求由 CI 注入 Windows 证书参数。

- [ ] **步骤 4：验证并提交**

运行：

```powershell
npx vitest run tests/release/config-persistence.test.ts tests/release/backup-restore.test.ts
npm run build:release-win
powershell -ExecutionPolicy Bypass -File scripts/release/verify-installed-app.ps1 -InstallerPath release/1.0.0/ScientificResearchOS-1.0.0-x64.exe
git add desktop/src/main/services/config desktop/src/main/services/update-service.ts desktop/electron-builder.yml desktop/scripts/release desktop/tests/release docs/desktop-migration
git commit -m "release(desktop): harden backup and signed distribution"
```

预期：配置持久化、备份恢复、安装包安装、首次启动、登录与迁移中心打开全部通过。

### 任务 R7：执行正式发布演练

**文件：**
- 创建：`desktop/scripts/release/run-release-rehearsal.ps1`
- 创建：`desktop/tests/release/rehearsal-report.schema.json`
- 创建：`desktop/tests/release/rehearsal-report.schema.test.ts`
- 创建：`docs/desktop-migration/release-acceptance-report.md`

- [ ] **步骤 1：写失败的演练报告结构测试**

报告必须包含 `sourceSnapshot`、`mbrpVerification`、`importResult`、`offlineChecks`、`backupRestore`、`installer`、`webUntouched`、`signedBy` 和 `releaseCommit` 字段；缺任一字段即失败。

- [ ] **步骤 2：运行失败测试**

运行：

```powershell
npx vitest run tests/release/rehearsal-report.schema.test.ts
```

预期：FAIL，提示 schema 或测试脚本不存在。

- [ ] **步骤 3：实现可中断演练脚本**

脚本参数为 `-SnapshotDir`、`-PackagePath`、`-InstallerPath`、`-ReportPath`。它依次验证快照清单、`.mbrp` 校验和、干净 Windows 用户数据目录导入、断网后工作项/会议/文件/对话打开、备份恢复、安装升级和网页端保护路径。任一步失败立即返回非零并保留 JSON 报告；不得启动网页端容器、不得访问网页端写接口。

- [ ] **步骤 4：验证并提交**

运行：

```powershell
npx vitest run tests/release/rehearsal-report.schema.test.ts
powershell -ExecutionPolicy Bypass -File scripts/release/run-release-rehearsal.ps1 -SnapshotDir <verified-snapshot> -PackagePath <verified-mbrp> -InstallerPath <signed-installer> -ReportPath release/1.0.0/rehearsal-report.json
git add desktop/scripts/release desktop/tests/release docs/desktop-migration
git commit -m "release(desktop): add formal release rehearsal"
```

预期：所有字段为通过状态；网页端保护路径检查为空；主指挥依据报告决定是否发布。

## Claude Code 每批派工模板

```markdown
你现在执行 Release 批次 Rx。

背景：本项目采用网页端零影响的适应性迁移。网页端是只读来源，桌面端是唯一可写目标。

允许修改：仅本批计划列出的 `desktop/`、`scripts/desktop_migration/`、`tests/desktop_migration/`、`docs/desktop-migration/` 文件。

禁止修改：`app/`、`web/`、`alembic/`、`docker-compose*.yml`、`nginx/`、`.env`、线上数据和任何网页服务。

开始与结束必须运行：
`npm run release:guard`

完成标准：计划中本批所有测试、类型检查和保护路径检查均通过；只提交本批列出的文件；报告命令输出、变更文件清单与提交哈希。

执行：不要扩大范围，不要修改网页端，直接实现并测试。
```
