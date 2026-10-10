# 工单 FIN-1：发布前收尾（双端 · 全部遗留改进一次性收干净）

> 签发：总指挥 · 2026-09-30 ｜ 性质：**收尾单**（不新增功能，只收敛开发过程中累积的遗留项）
> 目标：本单通过后即发布 **v1.3.2 本阶段最终正式版**
> 覆盖来源：DL-7 验收发现 2 项 / ZB-1 执行端单列 3 项 / ZB-2 验收发现 3 项 —— 全部已在验收记录中登记，此处汇总执行
> **双端工单**（`apps/desktop/` + `app/`），须同批合流

---

## 零、收尾范围总览

| 组 | 项 | 端 | 风险 |
|---|---|---|---|
| **A** | A1 备份形态禁止公开分享 | 服务端 | **高**（真实隐私缺口） |
| **A** | A2 异步任务测试会连生产库 | 服务端 | **中**（违反项目铁律） |
| **B** | B1 节流日志文案与常量不符 | 桌面端 | 低（排障误导） |
| **B** | B2 `buildLatestYml` 尾随多换行有损 | 桌面端 | 低（生产不可达） |
| **B** | B3 备份目录段允许单点 `.` | 桌面端 | 低 |
| **B** | B4 `listFolders` 失败仍继续建夹 | 桌面端 | 低（可能重复建夹） |
| **C** | C1 `_validate_visibility_inherits` 文档与代码矛盾 | 服务端 | 低（陈旧文档） |
| **C** | C2 v1.3.2 CHANGELOG 补「备份隐私加固」段 | 桌面端 | 发布配套 |

**D 组为「经核实后决定不修」，列在第六节，只需在报告中确认知悉即可，不要动手。**

---

## A 组 · 有实际影响

### A1 · 备份形态禁止生成公开分享链接

**问题（总指挥已验实）**：`app/services/drive_service.py:1276-1277`

```python
# 批次⑩.7: 可见性跟随分享 — 分享即公开, 撤销/过期回团队 (用户 2026-09-05 拍板)
f.visibility = "public"
```

ZB-1 的闸只挡**非 owner** 分享；**owner 仍可把自己的 `*.mnbbak.key.json` 分享出去，一键变成 `public`**——密钥信封将随分享链接对外可达。

**为什么不能一刀切**：「分享即公开」是 2026-09-05 对 drive 文件的既定产品决策，**不得推翻**。因此本项**只对备份形态豁免**。

**要求**：

1. `create_share_link()` 在 `_can_see_file` 闸之后，**追加**备份形态拦截：命中 `is_backup_artifact_name(f.file_name)`（`app/services/drive_ingest_tasks.py` 已有该纯函数，直接复用，**不要另写一份判定**）时拒绝，返回明确错误（如「备份文件不支持公开分享」），`DriveServiceError` 或既有返回 None 的口径由你按该方法既有风格定，**但 API 层必须对用户可见**（不能静默）。
2. 同步考虑 `update_visibility` 路径：owner 能否把备份文件直接改成 `public`？同口径拦截。
3. 判定基于**文件名形态 + 备份保留区**双条件还是仅文件名，你定并说明理由（建议：文件名为备份形态即拦截，因为根目录残留形态在迁移 141 后已全部 private，但形态判定更稳）。
4. 单测：备份形态分享被拒；普通 team 文件分享**照旧成功**（不许误伤 09-05 决策）。

### A2 · 异步任务的测试不得连生产库

**问题（总指挥亲历）**：`app/services/drive_ingest_tasks.py:48`

```python
engine = create_async_engine(
    settings.DATABASE_URL.replace(...), poolclass=NullPool,
)
```

任务体硬编码生产库 URL，而测试 fixture 在测试库建行。总指挥首跑复现 **6/8**（任务在生产库查不到 id → 404 → `return None` → 断言炸）；补 `DATABASE_URL` 指向测试库后 **8/8**。执行端报告属实，但**测试不自包含**。

**风险**：`tests/conftest.py:34-36` 明写「测试禁止回退 `settings.DATABASE_URL`（生产库）—— 历史上这批测试在生产留 debris」。当前是只读 SELECT，未留垃圾；但**一旦该任务路径未来出现写操作，就是生产事故**。

**要求**：

1. 让任务引擎 URL **可注入**（默认仍是 `settings.DATABASE_URL`，测试可覆盖）。机制由你选，但必须满足：**生产行为逐字不变**。
2. 检查 `drive_index_service.py` 同类任务是否有相同问题，一并处理。
3. **必须补一条回归守卫测试**：断言测试环境下该任务解析出的 DB URL **不是**生产库 URL。这条守卫比修复本身更重要——它防止同类问题复发。
4. 更新 `tests/test_zb2_backup_ingest_skip.py` 使其在**不设任何额外 env** 的默认环境下自洽通过（当前依赖外部 env 才绿）。

---

## B 组 · 正确性 / 可观测性

### B1 · 节流日志文案与常量对齐

`apps/desktop/src/main/services/update/update.service.ts` 跳过分支日志写「**24h** 内已自动检查过（节流）」，而 `AUTO_CHECK_THROTTLE_MS = 20 * 60 * 60 * 1000`（20h）。

改成与常量一致，或直接引用常量格式化输出。**理由**：本项目历史上多次因日志与实际行为不符走弯路，排障日志误导成本高。

### B2 · `buildLatestYml` 尾随多换行有损

**总指挥实测（js-yaml 4.3.2 往返）**：

| 入参 | 解回 | |
|---|---|---|
| `"abc"` / `"abc\n"` / `"abc\n\ndef\n"` | 逐字一致 | ✓ |
| `"abc\n\n"` | `"abc\n"` | ✗ |
| `"abc\n\n\n"` | `"abc\n"` | ✗ |
| `"\n"` | `""` | ✗ |

**生产路径不可达**：唯一调用方 `extractChangelogSection` 末尾 `replace(/[\s]+$/,'')` 已剥除全部尾随空白，实测真实 CHANGELOG 段落往返一致。

**要求**：在 `releaseNotesLines` 入口对入参做尾随换行归一（或改用能正确表达尾随空行的 chomp 组合），并**补测试用例固化**该行为；在 JSDoc 写明入参契约。

### B3 · 备份目录段允许单点 `.`

`apps/desktop/src/main/ipc.ts` 的 `normalizeBackupSegments` 拒绝 `..` / `\` / 空段，但单点 `.` 会通过并被 find-or-create，会建出名为 `.` 的怪文件夹。

**非穿越**（按名精确匹配，无路径拼接），仅建议把 `.` 一并拒掉。

### B4 · `listFolders` 失败时不应继续建夹

`ensureRemoteFolderId` 中 `listFolders` 返回 `!ok` 时直接落入 `createFolder`。瞬时网络错误会被放大成**重复建夹**。

要求：`!ok` 时显式返回失败并向上传播，让备份以「可感知失败」结束，而不是静默建夹。

---

## C 组 · 文档与发布配套

### C1 · `_validate_visibility_inherits` docstring 与代码矛盾

`app/services/drive_service.py:441-451` docstring 写「folder=team → 文件可以是 private/team/public」，但代码用 `VISIBILITY_ORDER` **禁止** team 文件夹放 public（实测 `batch_update_visibility` 会跳过）。属 2026-06 遗留的陈旧文档。

**只改 docstring，不改行为**。以代码实际行为为准重写该段说明。

### C2 · v1.3.2 CHANGELOG 补「备份隐私加固」段

`apps/desktop/CHANGELOG.md` 的 `## v1.3.2` 段落已由 DL-7 起草，但**未含 ZB-1/ZB-2 的备份隐私加固**（11 处写路径闸、保留区隔离、备份形态不入知识库、`private→team` 修正、历史密钥明文清除）。

**发布时定稿**——本单只需起草段落，措辞如实，**不得夸大为「已修复全部安全问题」**。

---

## 范围红线

- **不新增功能**，只收敛遗留项
- **不推翻**「分享即公开」产品决策（2026-09-05）与「单一团队空间」模型（2026-09）
- **不动** ZB-1 的 11 处 private 写路径闸与保留区判定；**不动** ZB-2 的两个任务入口跳过与 `private→team` 移除
- **不动** 备份容器格式 `MNBBK1`、零感备份的自动配置与触发逻辑
- **不动** `web/` 前端、`.env`、MinIO 凭证、`nginx/`、`docker-compose*`
- **不删** `zb1probe` 账号 / `backups/` 文件夹 / 3 个探针（清理由总指挥在发布后单独处置，不在本单）
- 区外所有 drive/kb 行为**逐字不变**
- 保护路径：除本单点名的 `app/services/*` 与 `alembic/`（若需）外零改动

## 验收证据

1. **A1 双账号实证**：owner 对自己的 `*.key.json` 调分享 API → 明确失败且用户可见；普通 team 文件分享照旧 200
2. **A2 守卫测试**：断言测试环境解析出的 DB URL 非生产库；`test_zb2_backup_ingest_skip.py` **不设额外 env** 即全绿
3. 桌面端 `pnpm gate` 全绿（基线 **781**，本单新增用例后 ≥781）
4. 服务端容器内相关测试全绿（ZB-1/ZB-2 回归不破）
5. 报告注明：每项的改前/改后对照；D 组确认知悉

## 交付

- 两仓各一笔提交，报告贴出后**总指挥独立复跑 gate 与测试，不采信报告**
- 通过后走 **R-12 v1.3.2 发布列车**（本阶段最终正式版）
