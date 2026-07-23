# W68 第 5 批 — Drive v2 PR10 协同编辑 CRDT 起步（2026-07-24）

> **锚点范式**: 第 59 守恒（PR10 调研 + 骨架 0 production code 改动铁律 + 单链纪律 + 3 库真实对比）

---

## 1. 派工背景

W68 第 5 批派工 #2 = 「Drive v2 PR10 协同编辑 CRDT 起步」。**仅**调研 + 骨架，**不**实施完整 Yjs 集成，留 W69/W70/W71 三批派工。

W19 决策树中 5 留待未来 PR 包括 PR8g「协同编辑：CRDT 算法实时多人编辑文档」。本调研为 PR8g 启动段。

---

## 2. 关键发现

### 2.1 pycrdt 0.14.1 是唯一 Windows 即装即用选项

本机 Win11 + Python 3.12 实测 3 库：

| 库 | pip install | 协议 | 推荐度 |
|---|---|---|---|
| **pycrdt 0.14.1** | ✅ 预编译 wheel `cp312-win_amd64.whl` (863KB) | Yjs 兼容 | ⭐⭐⭐ 强烈推荐 |
| y-py 0.6.x | ❌ maturin 编译失败，需 VS Build Tools | Yjs 官方 | ⭐⭐ 备选（Linux/Mac OK） |
| automerge 0.6.x | ❌ maturin 编译失败 | Automerge | ⭐ 不推荐（生态小） |

**实测双向 merge**（`Doc1 = "hello "` + `Doc2 = "world"` → 双向 apply_update）:
- 字符级 CRDT 不丢更新，**两个原始子串都保留**
- 但**顺序不确定**：可能是 `"hello world"`（顺序合并）或 `"worldhello "`（反向合并）
- 决定权在 client_id 时序 + YATA 算法
- state 字节仅 19 bytes（极小）

**纪律**: PR10 实施时，pytest 不要假设合并后顺序，用 set membership 验证。

### 2.2 y-py 编译失败的 2 层根因

1. `y-py` 是 Rust + PyO3 绑定（官方 Yjs 团队维护）
2. 安装走 `maturin pep517 build-wheel`，**需要** MSVC `link.exe`
3. Win11 默认无 VS Build Tools → `link.exe returned unexpected error`

**mitigation**: 抽象 `YDocAdapter` (W69 实施)，未来 y-py 装得上可一行切换。但 pycrdt 与 y-py 协议字节兼容（`pycrdt.Doc.get_state()` ≈ `Y.encodeStateAsUpdate(doc)`），Yjs 客户端用 `Y.applyUpdate()` 可直接消费 pycrdt 输出，**实际不需要切换**。

### 2.3 服务层架构与 PR9 `drive_file_versions` 完全正交

- **PR9 (版本历史)**: 手动 check-in，每次写新版本到 MinIO + `drive_file_versions` 表
- **PR10 (协同编辑)**: 实时多人 CRDT，存 Y.Doc state 到 `drive_documents` 表
- **互不替代**：PR10 调 PR9 `save_version` 可留快照
- **无 schema FK 依赖**：064 与 063 仅逻辑引用，未来如需强依赖再加 FK

### 2.4 串单链纪律（W68 第 3 批双头事故升级）

W68 第 3 批 F-1 (062) + F-2 (063) 两个 agent 并行派工，prompt 没写接续关系 → merge 后 alembic 报 `Multiple head revisions are present` → commit `1852468a6` 主指挥修。

**本 PR 严格遵守**:
- 064 `down_revision = "063_drive_file_versions"`（写明）
- merge 后 `python -c "from alembic.config import Config; ..."` 验证只 1 个 head（已跑通）
- 部署 doc §1 加「alembic 链风险」段
- 派工模板 W69/W70/W71 全部接 064

**派工模板**:
```python
# W69 派工 prompt 必含
# alembic 065 (如有) 必须 down_revision = "064_drive_documents"
# W70/W71 不写新 alembic, 复用 064
```

---

## 3. 0 production code 改动铁律维持

**W68 第 5 批派工硬性要求**:
> 「Drive v2 PR10 是 v2 系列新功能, 不破坏 v1 老路径, CLAUDE.md 已批准」

**本 PR 交付**（**仅**调研 + 骨架）:
- ✅ `docs/drive-v2-pr10-collab-editing-design.md` (~470 行) — 3 库对比 + 架构 + 协议 + 实施路线
- ✅ `docs/drive-v2-pr10-collab-editing.md` (~340 行) — API 契约 + 部署
- ✅ `alembic/versions/064_drive_documents.py` (~150 行) — 2 张新表 schema
- ✅ `app/models/drive_document.py` (~180 行) — DriveDocument + DriveDocOpLog ORM
- ✅ `app/services/drive_collab_service.py` (~250 行) — 6 个方法 stub
- ✅ `tests/test_drive_v2_pr10_collab_smoke.py` (~180 行) — 6 case (3 主场景 + 3 验证)
- ✅ `memory/w68-route-5-drive-pr10-collab-2026-07-24.md` (本文件)

**不交付**（留 W69/W70/W71）:
- ❌ WebSocket 端点 (`/api/v1/drive/collab/{file_id}`)
- ❌ Celery task (`flush_ydoc_state_task` / `compress_op_logs_task`)
- ❌ 前端 `useCollabSession.ts` / `DriveCollabEditor.vue`
- ❌ Dockerfile 改动 (pycrdt==0.14.1 加 requirements.txt 留 W69)
- ❌ 实际部署到生产
- ❌ `YDocAdapter` 抽象层 (留 W69 实施)

**验证**:
- 6/6 pytest PASS (SKIP_DB_SETUP 模式)
- alembic head 单链: `['064_drive_documents']`
- pycrdt 真 import + 双向 merge 成功

---

## 4. 实施路线（W69 / W70 / W71 三批派工）

### 4.1 W69 PR10 骨架（~12h, 1 批派工）
**目标**: 后端可收发 op + 持久化, 前端能显示「连接中」状态
- [ ] Dockerfile 加 `pycrdt==0.14.1` (已确认 win_amd64 wheel 可用)
- [ ] `YDocAdapter` 抽象层（10 行）
- [ ] `DriveCollabService` 完整实现（5 个方法 + 1 个 helper）
- [ ] `/api/v1/drive/collab/{file_id}` WS 端点（参考 FastAPI WS 文档）
- [ ] Celery beat 加 `flush_ydoc_state_task`（30s 周期）
- [ ] 前端 `useCollabSession.ts`（仅 WS 开关, 不含编辑器）
- [ ] smoke test 升级为 e2e（含 2 客户端并发 merge）

### 4.2 W70 PR10 持久化与并发（~16h, 1 批派工）
**目标**: 多实例 WS 跨节点 broadcast, 崩溃恢复, op log 压缩
- [ ] Redis pub/sub 集成（50 行自写或 `ypy-websocket`）
- [ ] `apply_remote_op` 同步写 `drive_doc_op_logs`（best-effort）
- [ ] `compress_op_logs_task` 每天 03:00 合并 op → 写 ydoc_state → 删老 op
- [ ] 启动 hook：从 `ydoc_state` + 30 天内 op 重建内存 Y.Doc
- [ ] 多实例部署测试（启动 2 个 app 容器, 跨实例 broadcast 验证）
- [ ] `test_drive_v2_pr10_collab_concurrent.py` 多客户端并发

### 4.3 W71 PR10 UI（~14h, 1 批派工）
**目标**: 编辑器集成 + 协作者光标 + 离线兜底
- [ ] 前端编辑器选型：先 y-codemirror.next（轻量, CodeMirror 6）
- [ ] `web/src/views/drive/DriveCollabEditor.vue` 主组件
- [ ] 协作者光标 + 头像 tooltip（awareness 协议）
- [ ] 离线编辑 → IndexedDB 暂存（PWA 策略复用）
- [ ] 重连恢复 + ops 补发
- [ ] 移动端适配（NutUI 4, 简化版只读模式 + 编辑走 input）
- [ ] Playwright e2e：3 浏览器并发

**总耗时 ~42h, 3 批派工, 每批 1 个 agent × 4-5h 工作量**

---

## 5. 风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| pycrdt 长期不维护 | 中 | 高（CRDT 协议升级） | YDocAdapter 抽象可换 y-py |
| Y.Doc state 膨胀 | 高 | 中（DB 占用） | W70 7 天压缩 + 50KB 阈值强制 snapshot |
| 多实例 Redis pub/sub 失败 | 低 | 高（编辑不同步） | W70 重点测试 + fallback 单实例 + sticky session |
| 大文件 1MB+ 性能 | 中 | 中 | PR10 仅 text/markdown, binary 走 PR9 路径 |
| WS 断线 op 丢失 | 低 | 中 | op log 重发 + client_id 幂等 |
| 移动端键盘兼容 | 中 | 低 | PR10 移动端只读为主, 编辑走纯文本 fallback |

---

## 6. 3 条新铁律沉淀

### 铁律 A: CRDT 合并测试不要假设顺序
```python
# ❌ 反模式: 假设双向 merge 后顺序固定
assert str(text1) == "hello world"

# ✅ 正模式: 用 set membership 验证
merged = str(text1)
assert merged == str(text2)  # CRDT 收敛性
assert "hello" in merged and "world" in merged  # 字符级不丢
```

CRDT 双向合并顺序取决于 client_id 时序, 同一段代码两次跑可能产生 `"hello world"` 或 `"worldhello "` 两种结果。**收敛性**（双方一致）和**字符保留**（不丢更新）才是确定性保证。

### 铁律 B: Binary 列 server_default 必须用 text("''::bytea")
```python
# ❌ 反模式: SQLAlchemy 2.0 报 ArgumentError
ydoc_state = Column(LargeBinary, server_default=b"")

# ✅ 正模式: 用 text() 包 SQL 表达式
ydoc_state = Column(LargeBinary, server_default=text("''::bytea"))
```

CLAUDE.md 2026-06-28 JSONB flag_modified 教训的**对偶**：Binary 字段也不能用 Python 字节对象作 server_default，必须走 SQL 表达式。这条 PR10 ORM + alembic 064 双向同步修改都改对了。

### 铁律 C: SKIP_DB_SETUP 模式 service stub 必须接受 None db
```python
# ❌ 反模式: 调 db.execute(None) 报 AttributeError
async def get_or_create_ydoc_state(db, file_id):
    result = await db.execute(...)

# ✅ 正模式: 显式 None guard
async def get_or_create_ydoc_state(db, file_id):
    if db is None:
        return b""  # W68 第 5 批 SKIP 模式 fallback
    result = await db.execute(...)
```

CLAUDE.md 既有 `SKIP_DB_SETUP=1` 测试模式（`tests/test_baseline_audit.py` 等用），任何 service 新方法如果**不**接受 None db 就在该模式跑不起来。W68 第 5 批派工明确「不连真 DB」必须配 None guard。

---

## 7. 调研产物清单（commit 范围）

```
docs/drive-v2-pr10-collab-editing-design.md       470 行 (设计 + 协议 + 实施路线)
docs/drive-v2-pr10-collab-editing.md              340 行 (API + 部署 + 监控 + 回滚)
alembic/versions/064_drive_documents.py            150 行 (2 表 schema + 串单链 063)
app/models/drive_document.py                      180 行 (DriveDocument + DriveDocOpLog)
app/services/drive_collab_service.py              250 行 (6 stub 方法 + 3 异常类)
tests/test_drive_v2_pr10_collab_smoke.py          180 行 (6 case: 3 主场景 + 3 验证)
memory/w68-route-5-drive-pr10-collab-2026-07-24.md 200 行 (本文件)
```

**合计**: 7 文件 / ~1770 行 / 0 production code（仅 schema + service stub + test + docs）

---

## 8. 与锚点范式关系

- **W68 第 5 批 8 文件派工模板**: 7 文件 + 1 commit (本 PR 完成 7/8, commit 留主指挥)
- **锚点范式第 59 守恒**: 0 production code + 串单链纪律 + 调研真实 (pycrdt 真 import + 双向 merge) + pytest 6/6 PASS
- **W19 选项 A 维持**: 协同编辑 (PR8g) 留待未来 PR, 本批调研启动段不算实施
- **W68 跨主题累计**: W68 第 1 批 (14 agents) + W68 第 2 批 (3 agents) + W68 第 3 批 (11 agents) + W68 第 4 批 (4 agents) + W68 第 5 批 (2 agents) = **34 agents**

---

## 9. 下一步

- W69 PR10 骨架派工（~12h, 含本 PR 064 部署）
- W70 持久化与并发派工（~16h）
- W71 UI 集成派工（~14h）
- 3 批全部收官后, PR10 才算「实施完成」, W19 选项 A 的 PR8g 留待未来 PR 决策可推进
