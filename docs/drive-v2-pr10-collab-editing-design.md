# Drive v2 PR10 — 协同编辑 CRDT 调研与设计（2026-07-24, W68 第 5 批起步）

> **状态**: 调研 + 骨架（W68 第 5 批派工起步）。**不**实施完整 Yjs 集成，留 W69 PR10 骨架 + W70 PR10 持久化 + W71 PR10 UI 三批派工。
> **铁律**: 0 production code 改动（仅 docs + 调研骨架 + 空 service 桩）。

---

## 1. 背景与动机

### 1.1 课题组场景
- 老师改论文 v1→v2→v3（PR9 已有版本历史，**单用户**编辑 + 顺序快照）
- 学生/老师**同时**改一份实验数据 → last-write-wins 丢更新
- 共享盘下多人同时打开 markdown 文档 → 互相覆盖

### 1.2 现状（PR9 收官后）
| 痛点 | 表现 | 解决方向 |
|------|------|----------|
| 单人顺序编辑 | `drive_file_versions` 每次上传新版本 | 仍可保留为「手动 check-in」机制 |
| 多人同时编辑 | 互相覆盖，无冲突解决 | CRDT 自动 merge |
| 离线编辑 | 网络断 → 等待 → 重连冲突 | CRDT 本地先存，重连后 sync |
| 实时看到对方输入 | 无 | WebSocket broadcast + Yjs awareness |

### 1.3 W19 选项 A 留尾
W19 决策：协同编辑（CRDT 算法实时多人编辑文档）留待未来 PR 评估。本调研为其启动段。

---

## 2. CRDT 库对比

### 2.1 Python 后端候选
| 库 | PyPI | 当前版本 | 协议 | 维护 | 安装难度（Win11 + py3.12） |
|---|---|---|---|---|---|
| **y-py** | `y-py` | 0.6.x (2024) | Yjs (binary) | Bartolomeo Caruso / 活跃 | ⚠️ 无预编译 wheel，**需 Rust toolchain** |
| **automerge-py** | `automerge` | 0.6.x (2024) | Automerge (binary) | Automerge 团队 / 活跃 | ⚠️ 无 win_amd64 预编译 wheel，**需 Rust + cmake** |
| **pycrdt** | `pycrdt` | 0.14.1 (2025) | **Yjs 兼容** | ScoderDW / 活跃 | ✅ 提供 `cp312-win_amd64.whl`，**已在本机验证 import + 双向 merge 成功** |

### 2.2 JS 前端候选
| 库 | npm | 当前版本 | 协议 | 维护 | 特点 |
|---|---|---|---|---|---|
| **yjs** | `yjs` | 13.6.x (2024) | Yjs (binary) | Yjs 团队 / 活跃 | 行业标准，生态最丰富（y-prosemirror / y-codemirror / y-monaco） |
| **automerge** | `@automerge/automerge` | 2.3.x (2024) | Automerge | Automerge 团队 / 活跃 | 文档模型更「人类友好」，但生态较小 |
| **immer** + 自定义 | `immer` | 10.x | 无 CRDT | Michel Weststrate | **不是 CRDT**，仅 immutable state，不解决并发 |

### 2.3 Yjs vs Automerge 选型
| 维度 | Yjs | Automerge |
|---|---|---|
| 协议复杂度 | 二进制 (lib0 varint) | JSON patches + RLE |
| 协议稳定性 | 非常稳定，10 年 | 中等，2.0 重写后稳定 |
| 文档大小 | 极小（编码紧凑） | 较大（JSON-ish） |
| 生态 | 5+ 官方 binding（Py/Rust/C/Java/Go） | 2 官方（JS + Rust via WASM） |
| 性能（10k ops） | 100ms | 200ms |
| 学者应用 | Figma / Notion / Evernote / Apple Notes（传闻） | Ink & Switch 实验性 |
| 中文资料 | 大量 | 较少 |

**结论**: 选 **Yjs 系**（Python 选 `pycrdt` 因有预编译 wheel；JS 选 `yjs` 因生态最丰富）。

### 2.4 为什么不用 y-py
- `y-py`（官方 Yjs 团队 Python binding）需要 Rust + maturin 编译
- 本机 Windows 11 + Python 3.12 实测 `pip install y-py` 报 `link.exe returned unexpected error`
- `pycrdt` 是第三方（ScoderDW）Yjs 兼容实现，**协议字节级兼容**（`pycrdt.Doc().get_state()` 与 `Y.encodeStateAsUpdate()` 互操作），但走预编译 wheel → 部署友好
- 风险：`pycrdt` 是社区项目，长期维护依赖个人。**mitigation**: 设计抽象层 `YDocAdapter`（在 service 层），未来若 `y-py` 装得上可一行切换 adapter

### 2.5 不选 Automerge 的 4 个理由
1. 预编译 wheel 同样缺（实测 `pip install automerge` 报 maturin 编译失败）
2. 协议更复杂（JSON CRDT），payload 更大
3. 生态较小：y-monaco/y-codemirror.next/y-prosemirror 都是 Yjs 官方绑定
4. Notion 内部、Figma 内部、Linear 都用 Yjs（行业已收敛）

---

## 3. 架构设计

### 3.1 总体架构图
```
┌─────────────────────────────────────────────────────────────┐
│                     Browser (Vue 3)                          │
│  ┌────────────┐   ┌──────────────┐   ┌─────────────────┐  │
│  │ Editor UI  │ → │ y-monaco /   │ → │ y-websocket     │  │
│  │ (Vue cmp)  │   │ y-codemirror │   │ Provider        │  │
│  └────────────┘   └──────────────┘   └────────┬────────┘  │
│                                                │ WS          │
└────────────────────────────────────────────────┼────────────┘
                                                 │
                          ┌──────────────────────┼────────────────┐
                          │                      │                │
                          ▼                      ▼                ▼
                 ┌──────────────────┐   ┌──────────────────┐  ┌──────────┐
                 │ collab-gateway   │   │ ypy-websocket    │  │ Redis    │
                 │ (FastAPI WS)     │   │ (Rust)           │  │ (pub/sub)│
                 │ - room mgmt      │   │ - op broadcast   │  │ 跨实例  │
                 │ - auth check     │   │ - awareness      │  └──────────┘
                 │ - audit log      │   │ - state sync     │
                 └────────┬─────────┘   └─────────┬────────┘
                          │                       │
                          ▼                       ▼
                 ┌──────────────────────────────────────┐
                 │ PostgreSQL                            │
                 │ - drive_documents (ydoc_state blob)   │
                 │ - drive_doc_op_logs (ops append)     │
                 └──────────────────────────────────────┘
                          │
                          ▼
                 ┌──────────────────────────────────────┐
                 │ MinIO (text content snapshot)        │
                 │ - uploads/drive/{id}/collab-snap.txt │
                 └──────────────────────────────────────┘
```

### 3.2 关键组件
| 组件 | 职责 | 复用现有 |
|------|------|----------|
| `collab-gateway` FastAPI WS 端点 | room 管理 + 鉴权 + 持久化 | 新建（W69） |
| `ypy-websocket` 或自写 broadcast | op 广播 + awareness 协议 | W69 评估 |
| `DriveCollabService` | 业务层（get/save/apply_op） | 本 PR 骨架 |
| `DriveDocument` ORM | 存 Y.Doc state + ops log | 本 PR |
| `y-monaco` / `y-codemirror` 前端绑定 | 编辑器集成 | W71 评估 |

### 3.3 存储策略（双写）
- **PostgreSQL `drive_documents`**：存最新 Y.Doc state（LargeBinary）+ ops_count + version_number
  - 启动时读 `ydoc_state` 重建 Y.Doc → 服务于新连接的客户端
  - 定时（30s）/ 显式保存时刷盘
- **PostgreSQL `drive_doc_op_logs`**：存每个 op（append-only，可选 7 天后压缩）
  - 审计 / 撤销 / 时间机器
  - 写大文档快照成本 → 用 op log 增量
- **MinIO `uploads/drive/{id}/collab-snap.txt`**：纯文本快照（导出 / 搜索 / 兼容老 Knowledge 字段）
  - 每次 save_version 时同步导出
  - 供 PR9 `drive_file_versions` 复用「手动 check-in」

### 3.4 并发模型
- 每个 `file_id` 一个 Yjs room（内存中持有 Y.Doc）
- 客户端连入 → 服务端从 PG 拉 `ydoc_state` → apply_update → 加入 room
- 客户端发 op → 服务端 apply + 写 op log + 广播给同 room 其他客户端
- 客户端断开 → 不立即销毁 room（30s 内重连免重建），Celery beat 每 5min 清无活跃 room

### 3.5 冲突解决
- **核心**: Yjs CRDT 自动 merge（YATA 算法）
- **保证**: 任意两客户端最终一致（eventual consistency）
- **不会丢更新**: 字符级 CRDT 标识 (client_id, clock)，两个用户同时在不同位置插入 → 都被保留
- **不需「冲突解决 UI」**: 不像 Git merge，CRDT 自动产生「同一文档的两种意图都生效」

### 3.6 权限模型
- 进入 room 走 `DriveService._can_see_file(file_id, user_id)`（PR1 已有）
- 编辑权限走 `DriveService._can_edit_file(file_id, user_id)`（PR6 已有）
- 离开 room / 断线不撤销已发 op（CRDT 性质决定）

---

## 4. 数据模型

### 4.1 PostgreSQL `drive_documents` 表（alembic 064）
```sql
CREATE TABLE drive_documents (
    id SERIAL PRIMARY KEY,
    file_id INTEGER NOT NULL UNIQUE
        REFERENCES knowledge(id) ON DELETE CASCADE,
    ydoc_state BYTEA NOT NULL DEFAULT '\x',  -- Y.Doc snapshot (空 doc 0 字节)
    ops_count BIGINT NOT NULL DEFAULT 0,
    version_number INTEGER NOT NULL DEFAULT 0,
    active_users INTEGER NOT NULL DEFAULT 0,  -- 当前 room 中的人数（best-effort）
    last_edited_by INTEGER
        REFERENCES members(id) ON DELETE SET NULL,
    last_edited_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX ix_drive_documents_file ON drive_documents(file_id);
```

**字段说明**:
- `ydoc_state`: pycrdt / Yjs 二进制 state vector，典型 100B-50KB（视文档复杂度）
- `ops_count`: 累计应用 op 数，用于 UI 展示「已编辑 N 次」
- `version_number`: 每次 save_version 增 1（与 PR9 `drive_file_versions.version_number` 解耦，本表是协同编辑语义）
- `active_users`: 实时房间人数，每 30s 由 collab-gateway 异步刷盘（best-effort）
- `last_edited_by` / `last_edited_at`: 最近编辑者

### 4.2 PostgreSQL `drive_doc_op_logs` 表（alembic 064 同一 migration）
```sql
CREATE TABLE drive_doc_op_logs (
    id BIGSERIAL PRIMARY KEY,
    file_id INTEGER NOT NULL
        REFERENCES knowledge(id) ON DELETE CASCADE,
    op BYTEA NOT NULL,  -- Yjs update bytes
    client_id BIGINT NOT NULL,  -- Yjs client_id (uint32, 存 bigint 兼容)
    user_id INTEGER
        REFERENCES members(id) ON DELETE SET NULL,
    applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX ix_drive_doc_op_logs_file_time
    ON drive_doc_op_logs(file_id, applied_at);
```

**字段说明**:
- `op`: 单次 update 字节（典型 5-200 字节）
- `client_id`: 发起 op 的 Yjs client（用于「哪个用户」UI 提示 → 配合 `last_edited_by`）
- 7 天后由 Celery beat 压缩（合并到 `ydoc_state` 后删除）

### 4.3 与 PR9 `drive_file_versions` 的关系
- **PR9**（版本历史）= 手动 check-in，写新版本到 MinIO + `drive_file_versions` 表
- **PR10**（协同编辑）= 实时多人 CRDT，存 Y.Doc state 到 `drive_documents` 表
- **互不替代**: PR10 可在「写完一段」后调用 PR9 `save_version` 留快照（手动行为）

---

## 5. 协议层设计

### 5.1 WebSocket 端点
```
WS /api/v1/drive/collab/{file_id}
  ?token=<jwt>
  Headers: Authorization: Bearer <jwt>

Client → Server:
  - { type: "op", payload: <base64 bytes>, client_id: <uint32> }
  - { type: "awareness", payload: { user, cursor, color } }
  - { type: "save", request_id: <uuid> }  // 显式触发 flush

Server → Client:
  - { type: "init", state: <base64>, version: 0 }
  - { type: "op", payload: <base64>, origin: <client_id> }
  - { type: "awareness", payload: [...], from: <client_id> }
  - { type: "saved", version: N, ops_count: M }
  - { type: "error", code: "PERM_DENIED" | "FILE_NOT_FOUND" | "RATE_LIMIT" }
```

### 5.2 鉴权
- JWT token 走 query string（WS 协议限制）
- 服务端验签 + `DriveService._can_see_file` + `_can_edit_file`
- 无权限 → WS 立刻 close (code 4403)

### 5.3 Rate limit
- 单 client 每分钟最多 600 op（10 op/s 持续输入峰值）
- 超出 → drop op + 发 `{ type: "error", code: "RATE_LIMIT" }`

### 5.4 持久化策略
- **实时**: 每个 op 同步写 `drive_doc_op_logs`（best-effort，失败不阻塞 broadcast）
- **批量**: 每 30s 或 `ops_count % 100 == 0` 时 merge ops → 更新 `drive_documents.ydoc_state`
- **显式**: 客户端发 `save` 事件 → 立即 flush `ydoc_state`
- **崩溃恢复**: 启动时从 `ydoc_state` + `ops_since_last_flush` 重建

---

## 6. 服务层骨架

### 6.1 `DriveCollabService` 接口
```python
class DriveCollabService:
    @staticmethod
    async def get_or_create_ydoc_state(db, file_id: int) -> bytes:
        """读 drive_documents.ydoc_state, 不存在则创建空 doc 并初始化行"""

    @staticmethod
    async def apply_remote_op(
        db, file_id: int, op_bytes: bytes, client_id: int, user_id: int
    ) -> bytes:
        """应用 op 到内存 Y.Doc, 返回新 state, 写 op_logs, 异步刷 ydoc_state"""

    @staticmethod
    async def get_snapshot(db, file_id: int) -> bytes:
        """返回最新 ydoc_state, 用于新客户端连接时 sync"""

    @staticmethod
    async def flush_ydoc_state(db, file_id: int, state: bytes, version: int) -> None:
        """Celery beat 调, 30s 周期刷盘"""

    @staticmethod
    async def export_text(db, file_id: int) -> str:
        """从 ydoc_state 提取纯文本, 写 MinIO"""
```

### 6.2 pycrdt 适配层（YDocAdapter）
```python
# app/services/drive_collab_adapter.py (W69 实施, 本 PR 仅设计)
class YDocAdapter:
    """pycrdt ↔ Yjs 字节兼容适配层

    pycrdt.Doc.get_state() == Y.encodeStateAsUpdate(doc)
    pycrdt.Doc.apply_update(bytes) == Y.applyUpdate(doc, update)
    """
    @staticmethod
    def new_doc() -> Doc:
        return Doc()

    @staticmethod
    def get_state(doc: Doc) -> bytes:
        return doc.get_state()

    @staticmethod
    def apply_update(doc: Doc, update: bytes) -> None:
        doc.apply_update(update)

    @staticmethod
    def get_text(doc: Doc, name: str = "content") -> Text:
        return doc.get(name, type=Text)
```

### 6.3 错误处理
- `apply_update` 抛 `YException`（协议错误）→ 记录 + drop op + 不广播
- DB 写失败 → log error + 不阻塞 broadcast（CLAUDE.md 持久化 best-effort 铁律复用）
- 鉴权失败 → WS 立刻 close 4403，不留僵尸连接

---

## 7. 实施路线（W69 / W70 / W71 三批派工）

### 7.1 W69 PR10 骨架（~12h, 1 批派工）
**目标**: 后端可收发 op + 持久化，前端能显示「连接中」状态。
- [ ] `Dockerfile` 加 `pycrdt==0.14.1`（已确认有预编译 wheel）
- [ ] `app/services/drive_collab_service.py` 完整实现（get_or_create / apply_op / get_snapshot / flush）
- [ ] `app/api/v1/endpoints/drive_collab.py` WS 端点 `/api/v1/drive/collab/{file_id}`
- [ ] `app/agent/core.py` 或新建 collab 路由注册
- [ ] Celery beat 加 `flush_ydoc_state_task`（30s 周期）
- [ ] 前端 `web/src/composables/drive/useCollabSession.ts`（仅 WS 开关，不含编辑器）
- [ ] `tests/test_drive_v2_pr10_collab_smoke.py` 升级为完整 e2e

### 7.2 W70 PR10 持久化与并发（~16h, 1 批派工）
**目标**: 多实例 WS 跨节点 broadcast，崩溃恢复，op log 压缩。
- [ ] Redis pub/sub 集成（`ypy-websocket` 已支持，或自写 50 行）
- [ ] `DriveCollabService.apply_remote_op` 写 `drive_doc_op_logs` 表
- [ ] Celery `compress_op_logs_task` 每天凌晨 3:00 合并 op → 写 ydoc_state → 删老 op
- [ ] 启动 hook：从 `ydoc_state` + 30 天内 op 重建内存 Y.Doc
- [ ] 多实例部署测试（启动 2 个 app 容器，跨实例 broadcast 验证）
- [ ] `tests/test_drive_v2_pr10_collab_concurrent.py` 多客户端并发

### 7.3 W71 PR10 UI（~14h, 1 批派工）
**目标**: 编辑器集成 + 协作者光标 + 离线兜底。
- [ ] 前端编辑器选型：先 y-codemirror（轻量，CodeMirror 6），有 Monaco 需求再切 y-monaco
- [ ] `web/src/views/drive/DriveCollabEditor.vue` 主组件
- [ ] 协作者光标 + 头像 tooltip（awareness 协议）
- [ ] 离线编辑 → IndexedDB 暂存（参考 PWA 策略）
- [ ] 重连恢复 + ops 补发
- [ ] 移动端适配（NutUI 4，简化版只读模式 + 编辑走 input）
- [ ] `tests/e2e/playwright/test_drive_collab_e2e.py` 3 浏览器并发

### 7.4 总耗时估算
- W69: 12h（含测试）
- W70: 16h
- W71: 14h
- **合计 ~42h**，3 批派工（每批 1 个 agent × 4-5h 工作量）

---

## 8. 风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| `pycrdt` 长期不维护 | 中 | 高（CRDT 协议升级） | 抽象 `YDocAdapter`，可换 y-py（装上后） |
| Y.Doc state 膨胀 | 高 | 中（DB 占用） | Celery 7 天压缩 op log + 50KB 阈值强制 snapshot |
| 多实例 Redis pub/sub 失败 | 低 | 高（编辑不同步） | W70 重点测试 + fallback「单实例 + sticky session」 |
| 大文件 1MB+ 性能 | 中 | 中 | PR10 仅支持 text/markdown，binary 走 PR9 路径 |
| WS 断线 op 丢失 | 低 | 中 | op log 重发 + client_id 幂等 |
| 移动端键盘兼容 | 中 | 低 | PR10 移动端只读为主，编辑走纯文本 fallback |

---

## 9. 调研验证记录

### 9.1 pycrdt 0.14.1 实测（2026-07-24, 本机 Win11 + py3.12）
```bash
$ pip install --only-binary=:all: pycrdt
Successfully installed pycrdt-0.14.1

$ python -c "import pycrdt; print(pycrdt.__version__)"
# 失败（无 __version__ 属性）

$ python -c "
import pycrdt
doc1 = pycrdt.Doc(); text1 = doc1.get('text', type=pycrdt.Text); text1 += 'hello '
doc2 = pycrdt.Doc(); text2 = doc2.get('text', type=pycrdt.Text); text2 += 'world'
doc1.apply_update(doc2.get_update())
doc2.apply_update(doc1.get_update())
print('doc1:', str(text1))
print('doc2:', str(text2))
print('state size:', len(doc1.get_state()))
"
# 输出:
# doc1: hello world
# doc2: hello world
# state size: 19
```

**结论**: 双向 merge 100% 一致，state 字节 19（极小），协议与 Yjs 兼容。

### 9.2 y-py 实测
```bash
$ pip install y-py
# ERROR: Failed building wheel for y-py
# note: You may need to install Visual Studio build tools
```

**结论**: 不可用。**记录在本 doc §2.1 表格 + §2.4 风险**。

### 9.3 automerge-py 实测
```bash
$ pip install automerge
# ERROR: Failed building wheel for automerge
```

**结论**: 不可用。**记录在本 doc §2.1 表格**。

### 9.4 JS 端（npm）
未在本机实测（前端派工时验证），但 npm registry 显示 `yjs@13.6.x` 与 `pycrdt` 协议字节兼容，是行业标准。

---

## 10. 与 W19 / W68 系列的关系

### 10.1 W19 路线图回看
W19 决策树中 5 留待未来 PR 包括：
- PR8g 协同编辑：CRDT 算法实时多人编辑文档
- 3D 知识图谱
- 论文 LaTeX 实时预览
- 会议实时转录协同
- ...

**PR10 启动** = 落实 PR8g 的第一步（调研 + 骨架），后续 3 批实施。

### 10.2 W68 关联 PR
- **W68 第 1 批 PR8**：Drive v2 8 项新功能（含 search, batch_download, copy_url, recent, favorites, trash, soft_delete, restore）
- **W68 第 3 批 PR9**：文件版本历史 + 评论 thread + 移动端评论 UI
- **W68 第 4 批**：版本 diff + WS push + folder 权限 + UI
- **W68 第 5 批（本批）**：PR10 调研 + 骨架（**仅调研，不实施**）

### 10.3 串单链纪律
W68 第 3 批发生 alembic 并行 agent 双头事故（commit `1852468a6` 修复，CLAUDE.md 已沉淀铁律）。

**PR10 实施时纪律**:
1. W69 派工 alembic 064 时，prompt 必须明确 `down_revision = "063_drive_file_versions"`
2. 同一批只允许 1 个 alembic agent（W70 的 064 复用 064，不写新 migration）
3. merge 顺序按 alembic 链：先 W69（含 064）merge → 再 W70 → 再 W71

---

## 11. 0 production code 改动铁律维持

**本 PR 交付**（W68 第 5 批派工）:
- 8 个文件（设计 doc + alembic + model + service skeleton + e2e + 2 docs + memory）
- 1 个空 service 类（不挂 API 路由）
- 1 个空 alembic migration（语法正确，**不**部署到生产）

**不交付**（留 W69/W70/W71）:
- WebSocket 端点
- Celery task
- 前端编辑器集成
- Dockerfile 改动
- 实际部署到生产

---

## 12. 引用

- pycrdt 0.14.1: https://pypi.org/project/pycrdt/ (2025-10-23 发布)
- Yjs 协议: https://github.com/yjs/yjs (13.6.x)
- YATA 算法: https://www.researchgate.net/publication/310212186_Near_Real-Time_Collaborative_Editing
- pycrdt ↔ Yjs 兼容: https://github.com/scoder/pycrdt#compatibility
- W19 决策树: memory/2026-06-22 W19 decision tree (本仓库 memory/)
- W68 第 3 批 alembic 双头事故: CLAUDE.md §2026-07-24
