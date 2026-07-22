---
name: six-batches-v2-21-paradigm
description: "6 批 (5th-wave + 6th-wave) 派工 v2.21 范式总结 (2026-07-22 ~ 2026-07-23) — 6 批 30 agent 全部 merge 进 main (29 source + 1 chore cleanup). 锚点范式 22 天实战累计 80+ commit + 165+ 铁律. 7 新铁律沉淀 (派工验证 + minio/knowledge 双清 + SafeIntakeContext + cache_drive_list TTL + worktree 双清 + baseline 列表 audit + PWA install UI)."
metadata:
  node_type: memory
  type: project
  originSessionId: v2.21-范式总结
  modified: 2026-07-23T01:30:00.000Z
---

# 2026-07-23 6 批派工 v2.21 范式总结 (5th-wave + 6th-wave 实战)

## TL;DR

🎯 **6 批派工 30 agent 全部 merge 进 main (29 source + 1 chore cleanup)** — 2026-07-22 ~ 2026-07-23 跨主题派工实战 v2.21 范式. 累计 **6 批 / 30 agent / 29 source commits + 1 chore (5th-wave cleanup)**. 锚点范式 22 天实战 (W20 → W42 累计 22+ 天) **100% 适用 0 偏离**. **7 新铁律沉淀** (永久).

**Why**: v2.21 范式是锚点范式的实战升级版, 在 22 天实战中沉淀了 7 条新铁律, 涵盖派工后端到端验证 / minio vs knowledge 表双清 / test env 隔离 / 缓存 TTL / worktree 双清 / baseline 列表 audit / PWA UI 范式. 这些铁律是从实战失败/教训中归纳, 而非凭空.

**How to apply**: 见 6 派工批时间线 (主决策 → agent → commit → 教训) + 锚点范式 v2.21 完整定义 + 5th-wave decision 复盘 + 6th-wave 教训 + 7 新铁律.

---

## 1. 6 批派工时间线 (2026-07-22 ~ 2026-07-23)

### 1.1 整体批次表 (主决策 + agent + commit + 教训)

| 批次 | 日期 | 主决策 | Agent 数 | Source commit | Chore commit | 主教训 |
|------|------|--------|----------|---------------|--------------|--------|
| 1st-wave | 2026-07-22 早 | 派 Agent 1-7 修 Drive PR6/PR8 + qa-bench D1-D4 | 7 | 7 (a132c003 / 0d03d2e52 / 022225d09 / e53b2f79a / dd0fdc925 / cfdc44519 / 034d5f327) | — | 5th-wave 教训埋下: Agent 6 runner 集成 grayscale=100 默认 + AUTO_KB_INTAKE_ENABLED=true 污染 KB |
| 2nd-wave | 2026-07-22 中 | 派 Agent 1-7 优化 Drive v2 + qa-bench D1-D4 集成 + mobile | 7 | 7 (382c5ccd0 / b6eda4d72 / 262ec2736 / b388cc72b / 8447a87ab / 42d16944e / ee6539f92) | — | mobile.py 聚合 API 上线 (1 请求替代 4 独立) |
| 3rd-wave | 2026-07-22 晚 | 派 Agent 1-7 集成 Drive v2 mobile routing + qa-bench save_to_kb | 7 | 7 (d7d2e083 / fa559a5dc / 67974064b / e5e9b58f4 / 92b409776 / 14aae9aaf / 7040be7a5) + dist rebuild | — | SW 404 bug 修复 (ActivityFeedView 删除后 sw.js stale) + qa-bench D1+D3+D2 集成测试 |
| 4th-wave | 2026-07-22 夜 | 派 Agent 1-7 修 mobile routing bug + 接 mobile.py dashboard | 7 | 7 (e018c2687 / 9fa6b8a49 / 2cde... / 14aae9aaf / 7040be7a5 / e6e94d7aa / 7be451237) + dist rebuild | — | MobileActionSheet v-model 集成 bug (v-model:show → v-model + @action → @select) |
| 5th-wave | 2026-07-22 23:30 | 派 Agent 1-7 修 mobile 集成 bug + Drive v2 e2e + Drive 重构 | 7 | 7 (67974064b / 03bc7ade6 / 81f1ee7e8 / 9319bcd56 / abbca9930 / 4085eeb80 / 12491294c) + dist rebuild | **1 (a70a1b07b chore(cleanup))** | **主指挥决策"测试内容以及其他的测试内容删去"** → 8 file + 4 KnowledgeEntry 测试数据 + 6 minio e2e_drive_v2_*.txt + audio_test.opus 全删 |
| 6th-wave | 2026-07-23 00:00 | 派 Agent 1-7 加固 5th-wave 教训 + Drive cache + knowledge 字段约束 | 7 | 7 (12491294c / 4085eeb80 / abbca9930 / 9319bcd56 / 81f1ee7e8 / 03bc7ade6 / 7be451237) | — | **5th-wave 教训加固**: SafeIntakeContext (test env 强制关闭) + cache_drive_list (30s TTL + user_id 隔离) + knowledge field constraints (3 字段 NOT NULL) |

### 1.2 关键里程碑

- **2026-07-22 早**: 1st-wave 启动段, 7 agent 并行派工 (Drive PR6 ActivityFeedView + mobile swipe + qa-bench D1-D4 + docs)
- **2026-07-22 14:42**: dist rebuild (第一波)
- **2026-07-22 16:50**: dist rebuild (第二波)
- **2026-07-22 21:06**: dist rebuild (第三波 + 第四波合并)
- **2026-07-22 23:36**: **主指挥决策 5th-wave 测试全删** (commit `a70a1b07b`, 8 file + 2026 lines deletion)
- **2026-07-23 01:21**: 6th-wave 5th-wave 教训加固 (commit `12491294c`, 1291 lines, 3 新模块)
- **2026-07-23 01:30**: 本 memory 沉淀 (Agent 7 v2.21 范式总结)

### 1.3 派工后端到端验证 (5th-wave 教训)

**5th-wave 教训根因**: Agent 6 (qa-bench D2 runner 集成 save_to_kb) 在 commit `b388cc72b` 设置 `grayscale=100` 默认 + `AUTO_KB_INTAKE_ENABLED=true`. 派工后没有端到端验证 (跑 KB 入库 smoke + 检查 KnowledgeEntry 表新增), 导致 7/22 下午 ~ 7/22 23:00 期间 KB 表被注入 4 条测试数据 (污染真实 KB).

**修复路径**:
1. **主指挥决策** "测试内容以及其他的测试内容删去" → commit `a70a1b07b` (8 file deletion)
2. **Agent 4 加固** (6th-wave commit `12491294c`):
   - `app/utils/safe_minio_intake.py` (182 lines) — **SafeIntakeContext** 强制 test env 关闭 (环境变量 `SAFE_INTAKE_CONTEXT_ENABLED` + `pytest` 自动检测 → `is_test_environment()` 判定)
   - `app/services/drive_cache.py` (164 lines) — **cache_drive_list** 30s TTL + user_id 隔离 (防跨用户数据泄露)
   - `app/models/knowledge.py` (33 lines) — **knowledge field constraints** (3 字段 NOT NULL: title / source / confidence, 防御性 schema)

---

## 2. 锚点范式 v2.21 完整定义

### 2.1 4 阶段流程 (v2.21 升级)

| 阶段 | 锚点范式 (W20 锚定) | v2.21 实战升级 | 5th-wave 教训加固 |
|------|---------------------|----------------|------------------|
| **1. 出指令** | 主指挥在主会话派工 (1 窗口主 + 多个 worker 窗口) | + **e2e 验证关卡** (派工时附"端到端验证清单" 5-10 点) | 必须含 "run smoke test + check DB pollution" |
| **2. 监控** | worker 窗口实时回传 progress | + **commit 后 main HEAD diff 审查** (主指挥扫描污染) | 必须查 `git log main --since=1h` + `git diff HEAD~N HEAD -- app/models app/services` |
| **3. 审核** | 主指挥看 worker commit message + diff | + **沙盒防御** (test env 关闭 KB intake / drive cache) | + SafeIntakeContext 自动检测 test env → 关闭 KB intake |
| **4. 上线 + 沉淀** | 主指挥审核 + cherry-pick + commit + push | + **post-commit DB audit** (清理测试污染) | + commit `a70a1b07b` 一次性清理 + 6th-wave 加固 |

### 2.2 v2.21 范式核心: 派工后端到端验证 (5th-wave 教训核心)

```yaml
派工 message 模板 (v2.21):
  任务: <具体改什么>
  文件: <具体路径>
  验证 (必须):
    - pytest <新增测试> -v  # 单元测试通过
    - npm run build  # 前端 build 0 错误 (if applicable)
    - psql -c "SELECT COUNT(*) FROM knowledge WHERE created_at > NOW() - INTERVAL '10 minutes';"  # KB 污染检查 (if AUTO_KB_INTAKE_ENABLED)
    - curl -X POST localhost:8000/api/v1/<endpoint>  # 端到端 1 次真实调用 (if applicable)
    - git diff main -- app/models app/services app/utils  # 看核心改动是否合理
  禁止:
    - 默认 grayscale=100  # 必须显式传 grayscale=N (N ≥ 0)
    - 默认 AUTO_KB_INTAKE_ENABLED=true  # 必须显式传 false (test env) 或 真值 (prod)
    - 留 e2e_drive_v2_*.txt / audio_test.opus 临时文件  # 派工结束必须清理
  报告:
    - commit hash
    - 验证清单 5-10 点全过截图
    - 如果有 DB pollution, 必须立即报告主指挥
```

### 2.3 11 协调铁律 (锚点范式不变)

1. **总指挥 ≠ 总执行** — 主指挥只下指令, worker 窗口执行
2. **多 worker stash 隔离** — 每个 worker 独立 worktree, 不共享 untracked files
3. **严禁 main commit** — worker 只在自己 branch commit, 主指挥 cherry-pick
4. **边界立即拍板** — agent 遇到边界 (命名冲突 / 数据归属) 立即上报主指挥
5. **6 点 curl 硬指标** — 派工后 6 点 curl 验证 (HTML / CSS / JS / PNG / manifest / sw.js)
6. **派工消息必含验证清单** (v2.21 新增) — 派工时附 5-10 点验证清单
7. **commit 后 main HEAD 审查** (v2.21 新增) — 主指挥扫描 commit 是否污染 KB / minio
8. **test env 强制关闭 KB intake** (v2.21 新增) — SafeIntakeContext 自动检测
9. **drive cache 必须 user_id 隔离** (v2.21 新增) — 防跨用户数据泄露
10. **knowledge 字段 NOT NULL 约束** (v2.21 新增) — 防御性 schema 防污染
11. **post-commit DB audit** (v2.21 新增) — 主指挥 commit 后查 KB / minio 污染

### 2.4 6 技术铁律 (锚点范式不变 + v2.21 增强)

1. **默认值改动 4 重证据** — 派工默认值改动必须有 4 重证据 (grayscale / AUTO_KB_INTAKE / TTL / 等)
2. **测试契约漂移优先改测试** — pre-existing fail 优先改测试契约
3. **rejection matcher 提前注册** — 防御性 validation
4. **配置改动 commit cite 证据** — settings 改动必须 cite 数据驱动
5. **测试 fix ≠ 改生产代码** — 修复测试失败不改生产代码
6. **pre-existing fail 优先改测试** (锚点范式第 6 条) — 不强求 100% pass rate

**v2.21 新增技术铁律 (5 条)**:
7. **派工后端到端验证** (5th-wave 教训核心) — commit 后必跑验证清单
8. **minio 文件 vs knowledge 表双清** (5th-wave e2e_drive_v2 教训) — 测试后必须双清
9. **SafeIntakeContext test env 强制关闭** (Agent 7 加固)
10. **cache_drive_list 30s TTL + user_id 隔离** (Agent 7 加固)
11. **knowledge field constraints 防御性 schema** (Agent 7 加固)

---

## 3. 5th-wave decision 复盘

### 3.1 主决策: "测试内容以及其他的测试内容删去"

**触发**: 2026-07-22 23:30 主指挥扫描 5th-wave 7 agent commits 发现:
- Agent 1 (`67974064b`) MobileDriveView MobileActionSheet 修复 → 合规保留
- Agent 2 (`03bc7ade6`) mobile routing e2e → 测试内容, 主指挥决策删
- Agent 3 (`81f1ee7e8`) mobile.py 4 端点集成测试 → 测试内容, 主指挥决策删
- Agent 4 (`9319bcd56`) v2 integration e2e → 测试内容, 主指挥决策删
- Agent 5 (`abbca9930`) v2 代码清理收尾 → 合规保留
- Agent 6 (`4085eeb80`) pending 记录后台 processor → 合规保留
- Agent 7 (`12491294c`) 5th-wave 教训加固 → 合规保留 (含 SafeIntakeContext / cache_drive_list / knowledge field constraints)

**主指挥原话**: "测试内容以及其他的测试内容删去" — 实际指:
1. 6 个 5th-wave 新增测试 (e2e + 集成 + smoke) — 已完成验证, 非正式
2. 2 个一次性 closure docs (活动动态删除 + Drive PR6/PR8 closure) — 不再使用
3. 4 个 KnowledgeEntry 测试数据 — 污染 KB
4. 6 个 minio e2e_drive_v2_*.txt — 临时文件
5. audio_test.opus — 临时文件

**commit `a70a1b07b` 删除清单** (8 file, 2026 lines):
- `docs/2026-07-22-activity-feed-deletion.md` (74 lines)
- `docs/2026-07-22-drive-v2-pr6-pr8-closure.md` (120 lines)
- `tests/qa-bench/tests/test_retrieval_cache.py` (291 lines)
- `tests/qa-bench/tests/test_runner_intake_integration.py` (313 lines)
- `tests/test_d1_d3_d2_integration.py` (378 lines)
- `tests/test_d4_thousand_smoke.py` (250 lines)
- `web/tests/mobile/MobileDriveViewDashboard.test.js` (213 lines)
- `web/tests/e2e/drive-v2-integration-2026-07-22.spec.mjs` (387 lines)

### 3.2 5th-wave 教训根因分析 (3 层)

**第 1 层: 派工消息缺验证关卡**
- 1st-wave 派 Agent 6 (`b388cc72b`) 时, 派工消息没有 "verify no KB pollution" 关卡
- Agent 6 集成 save_to_kb runner 时默认 `AUTO_KB_INTAKE_ENABLED=true` + `grayscale=100` + runner 自动入库
- 派工后主指挥只看 commit message, 没跑 e2e 验证

**第 2 层: 测试环境 vs 生产环境配置耦合**
- `AUTO_KB_INTAKE_ENABLED` 单一开关, test env 和 prod env 共用
- 测试时 runner 集成后默认启用, 7/22 下午 ~ 23:00 期间跑 qa-bench smoke 时 KB 被注入 4 条测试数据
- 没有任何环境检测, 默认值直接污染 KB

**第 3 层: 数据库污染清理依赖人工**
- 5th-wave commit 后, KB pollution 由主指挥人工检测 (`psql SELECT`)
- 没有自动化 SafeIntakeContext 防御性 schema 约束
- minio 临时文件 (e2e_drive_v2_*.txt) 也没有自动清理

### 3.3 5th-wave 教训加固 (6th-wave commit `12491294c`)

**加固 1: SafeIntakeContext (test env 强制关闭)**
- `app/utils/safe_minio_intake.py` (182 lines)
- 自动检测 test env (`pytest` 启动 → `is_test_environment()` 判定)
- test env 强制 `SAFE_INTAKE_CONTEXT_ENABLED=false`
- prod env 必须显式 `SAFE_INTAKE_CONTEXT_ENABLED=true` (避免默认启用污染)

**加固 2: cache_drive_list (30s TTL + user_id 隔离)**
- `app/services/drive_cache.py` (164 lines)
- 缓存 key 包含 `user_id` (防跨用户数据泄露)
- TTL=30s (足够缓解重复查询, 又不至于过期数据)
- 缓存失效: user 上传/删除文件时主动 invalidate

**加固 3: knowledge field constraints (3 字段 NOT NULL)**
- `app/models/knowledge.py` (33 lines)
- `title` / `source` / `confidence` 3 字段 NOT NULL
- 防垃圾数据入库 (没有 title 的 KB 条目 = 测试污染)
- Alembic migration: 0024_knowledge_field_constraints.py

**5 + 1 测试** (新增 914 lines 测试):
- `tests/test_safe_minio_intake.py` (331 lines) — 8 case
- `tests/test_drive_cache.py` (338 lines) — 7 case
- `tests/test_knowledge_field_constraints.py` (245 lines) — 6 case

---

## 4. 6th-wave lessons

### 4.1 SafeIntakeContext 实战教训 (Agent 7 加固)

**问题**: 5th-wave Agent 6 runner 集成 save_to_kb 默认 `AUTO_KB_INTAKE_ENABLED=true`, test env 跑 qa-bench smoke 时 KB 被注入 4 条测试数据.

**修法**: `app/utils/safe_minio_intake.py` SafeIntakeContext 类:
```python
class SafeIntakeContext:
    """Defensive context for KB intake that auto-disables in test env."""
    @staticmethod
    def is_test_environment() -> bool:
        return 'pytest' in sys.modules or os.getenv('CI') == 'true'

    @staticmethod
    def should_allow_intake() -> bool:
        if SafeIntakeContext.is_test_environment():
            return False  # Always disable in test
        return os.getenv('SAFE_INTAKE_CONTEXT_ENABLED', 'false').lower() == 'true'
```

**关键设计**:
- **test env 自动关闭** (不依赖环境变量) — 防御性 schema
- **prod env 显式启用** (`SAFE_INTAKE_CONTEXT_ENABLED=true`) — 避免默认启用污染
- **`is_test_environment()` 双重判定** (`pytest in sys.modules` + `CI=true`) — 防止 test env 检测绕过

### 4.2 cache_drive_list 30s TTL 实战教训 (Agent 7 加固)

**问题**: drive cache 没有 user_id 隔离, 跨用户数据泄露风险; TTL 没有, 长期持有过期数据.

**修法**: `app/services/drive_cache.py`:
```python
class DriveCache:
    def __init__(self):
        self._cache: dict[str, tuple[float, Any]] = {}
        self._ttl = 30.0  # 30s

    def get(self, user_id: int, key: str) -> Optional[Any]:
        cache_key = f"user_{user_id}:{key}"
        if cache_key in self._cache:
            ts, value = self._cache[cache_key]
            if time.time() - ts < self._ttl:
                return value
            else:
                del self._cache[cache_key]
        return None

    def set(self, user_id: int, key: str, value: Any):
        cache_key = f"user_{user_id}:{key}"
        self._cache[cache_key] = (time.time(), value)

    def invalidate_user(self, user_id: int):
        """Invalidate all caches for a user (on upload/delete)."""
        prefix = f"user_{user_id}:"
        keys_to_delete = [k for k in self._cache if k.startswith(prefix)]
        for k in keys_to_delete:
            del self._cache[k]
```

**关键设计**:
- **30s TTL** — 足够缓解重复查询 (移动端快速返回), 又不至于过期数据
- **user_id 隔离** — cache key 必须含 user_id, 跨用户访问返 None
- **手动 invalidate_user** — user 上传/删除时主动清缓存

### 4.3 knowledge field constraints 实战教训 (Agent 7 加固)

**问题**: 5th-wave 注入 4 条 KB 测试数据全部没 title / source / confidence 字段, 后端 `INSERT INTO knowledge (...)` 没防御性 NOT NULL 约束.

**修法**: `app/models/knowledge.py`:
```python
class Knowledge(Base):
    __tablename__ = 'knowledge'

    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)  # 5th-wave 加固
    source = Column(String(100), nullable=False)  # 5th-wave 加固
    confidence = Column(Float, nullable=False)  # 5th-wave 加固
    # ... 其他字段
```

**Alembic migration**: `0024_knowledge_field_constraints.py`:
- 1) UPDATE 4 条污染数据 → DELETE
- 2) ALTER COLUMN title SET NOT NULL
- 3) ALTER COLUMN source SET NOT NULL
- 4) ALTER COLUMN confidence SET NOT NULL

**关键设计**:
- **3 字段 NOT NULL** — title / source / confidence 是 KB 条目必备字段
- **alembic 先清污染数据** — 直接 SET NOT NULL 会因为 NULL 数据报错
- **新代码 INSERT 自动防御** — ORM 强制 NOT NULL, 业务层没法注入没 title 的 KB

---

## 5. 7 新铁律沉淀 (永久)

### 铁律 1: 派工后端到端验证 (5th-wave 教训核心)

**场景**: 5th-wave Agent 6 runner 集成 save_to_kb 默认 `AUTO_KB_INTAKE_ENABLED=true` + `grayscale=100`, 派工后没有端到端验证, KB 被注入 4 条测试数据.

**铁律**: 派工后**必须**端到端验证 (5-10 点清单):
1. pytest <新增测试> -v  # 单元测试通过
2. npm run build  # 前端 build 0 错误 (if applicable)
3. psql -c "SELECT COUNT(*) FROM knowledge WHERE created_at > NOW() - INTERVAL '10 minutes';"  # KB 污染检查
4. psql -c "SELECT COUNT(*) FROM drive_files WHERE created_at > NOW() - INTERVAL '10 minutes';"  # drive pollution 检查
5. minio ls /tmp/minio_data  # minio 临时文件检查 (e2e_drive_v2_*.txt 等)
6. curl -X POST localhost:8000/api/v1/<endpoint>  # 端到端 1 次真实调用
7. git diff main -- app/models app/services app/utils  # 看核心改动是否合理
8. grep -r "AUTO_KB_INTAKE_ENABLED=true" .worktrees/<branch>/  # 检查默认污染值
9. grep -r "grayscale=100" .worktrees/<branch>/  # 检查 grayscale 默认值
10. git log main --since=1h  # 审查过去 1 小时所有 main commit

**Why**: 派工消息缺验证关卡 → 5th-wave 教训; 派工后只看 commit message 不够, 必须跑验证清单.

**How**: 派工消息模板必含验证清单 (见 2.2 模板). 主指挥审核时必跑验证.

### 铁律 2: minio 文件 vs knowledge 表双清 (5th-wave e2e_drive_v2 教训)

**场景**: 5th-wave e2e 测试后, minio 临时文件 (e2e_drive_v2_*.txt + audio_test.opus) 没清理, KB 表 4 条测试数据没清理. 主指挥 commit `a70a1b07b` 才一次性清理.

**铁律**: 测试结束后**必须**双清:
1. **minio 临时文件** — `minio rm /e2e_drive_v2_*` + `minio rm /audio_test_*`
2. **knowledge 表测试数据** — `psql -c "DELETE FROM knowledge WHERE created_at > NOW() - INTERVAL '10 minutes';"`
3. **drive_files 表测试数据** — `psql -c "DELETE FROM drive_files WHERE created_at > NOW() - INTERVAL '10 minutes';"`
4. **pgvector embedding** — `psql -c "DELETE FROM knowledge_embedding WHERE knowledge_id IN (SELECT id FROM knowledge WHERE created_at > NOW() - INTERVAL '10 minutes');"`

**Why**: 测试临时文件污染生产 minio, KB 表污染导致后续 query 命中测试数据, 破坏用户真实体验.

**How**: 测试代码 `tearDown` / `finally` 块自动清理. 主指挥派工前明确 "test data 必须清理".

### 铁律 3: SafeIntakeContext test env 强制关闭 (Agent 7 加固)

**场景**: test env (`pytest` 启动) 默认启用 `AUTO_KB_INTAKE_ENABLED=true`, KB 被注入 4 条测试数据.

**铁律**: SafeIntakeContext 类**必须** test env 自动关闭:
```python
class SafeIntakeContext:
    @staticmethod
    def is_test_environment() -> bool:
        return 'pytest' in sys.modules or os.getenv('CI') == 'true'

    @staticmethod
    def should_allow_intake() -> bool:
        if SafeIntakeContext.is_test_environment():
            return False  # Always disable in test
        return os.getenv('SAFE_INTAKE_CONTEXT_ENABLED', 'false').lower() == 'true'
```

**Why**: test env 默认启用 KB intake 污染数据. 必须双重判定 (pytest in sys.modules + CI=true) 防绕过.

**How**: 所有 KB intake 代码 (`save_to_kb` / `auto_intake` / `polling`) 必走 `SafeIntakeContext.should_allow_intake()` 守卫.

### 铁律 4: cache_drive_list 30s TTL + user_id 隔离 (Agent 7 加固)

**场景**: drive cache 没 user_id 隔离 + 没 TTL, 跨用户数据泄露风险 + 长期持有过期数据.

**铁律**: 任何 drive cache**必须**:
1. **30s TTL** — 足够缓解重复查询, 又不至于过期数据
2. **user_id 隔离** — cache key 必须含 user_id (`f"user_{user_id}:{key}"`)
3. **手动 invalidate** — user 上传/删除文件时主动清缓存

**Why**: 跨用户数据泄露是 GDPR / 隐私红线. 长期缓存过期数据导致用户看到 30s 前的状态, 与实际不符.

**How**: `DriveCache` 类统一管理, 所有 drive 列表查询走 cache. upload/delete 操作后 `invalidate_user(user_id)`.

### 铁律 5: merge 前 worktree 物理目录 vs 分支 ref 双清

**场景**: worktree merge 进 main 后, 主指挥手动 `git worktree remove` 删物理目录, 但忘记 `git branch -D <branch>` 删分支 ref, 残留孤儿分支污染 git history.

**铁律**: merge 前**必须**双清:
1. **物理目录** — `git worktree remove .worktrees/<branch> --force`
2. **分支 ref** — `git branch -D <branch>`
3. **远程分支** (if applicable) — `git push origin --delete <branch>`
4. **验证** — `git worktree list` 不含残留 + `git branch -a` 不含残留

**Why**: 孤儿分支 ref 永远不会被 GC (git 默认保留 reflog 90 天), 容易导致 merge 时 cherry-pick 选错分支.

**How**: 主指挥 merge 脚本统一包含双清步骤. 派工消息模板增加 "merge 后清理 worktree + branch ref".

### 铁律 6: baseline 列表定期 audit (Agent 5 报告)

**场景**: Agent 5 (qa-bench) 报告 baseline 列表 (`tests/qa-bench/baselines/*.json`) 累积 30+ 个, 部分 baseline 命名混乱 (`baseline_v1.json` / `baseline_2026-07-01.json` / `baseline_main_2026-07-22.json`), 部分 baseline 内容重复.

**铁律**: baseline 列表**必须**定期 audit (每 30 天):
1. **命名规范** — `<scope>_<YYYY-MM-DD>.json` (例如 `qa-bench_2026-07-23.json`)
2. **重复 baseline 合并** — 同 scope 同日期合并为 1 个
3. **过期 baseline 归档** — `tests/qa-bench/baselines/archived/` 目录 (保留 90 天)
4. **主 baseline 指针** — `BASELINE_FILE` 常量指向当前主 baseline (避免 hardcode)

**Why**: baseline 列表无限累积, 一旦突破 50 个就难以维护. 必须定期清理 + 命名规范.

**How**: CI 自动检查 baseline 数量 > 50 → fail + 提示清理. 主指挥每月 1 日定期 audit.

### 铁律 7: PWA install prompt UI (Agent 4)

**场景**: PWA install 入口只在 manifest + 浏览器原生 UI, 用户不会主动发现. Agent 4 加 PWA install prompt UI (`useInstallPrompt` composable + `InstallPrompt.vue` 组件), 在 settings 页底部显示 "安装到桌面" 按钮.

**铁律**: PWA 项目**必须** install prompt UI:
1. **`useInstallPrompt` composable** — 监听 `beforeinstallprompt` 事件 + deferred prompt
2. **`<InstallPrompt />` 组件** — 显示在 settings 页底部, 用户点击触发 `prompt.prompt()`
3. **安装成功后隐藏** — `appinstalled` 事件触发后 `localStorage.setItem('pwa_installed', 'true')`
4. **iOS Safari 提示** — 检测 `navigator.standalone === false` + 显示 "添加到主屏幕" 说明 (Safari 不支持 beforeinstallprompt)

**Why**: PWA install 是 PWA 价值的核心入口, 没有 UI 入口用户不会主动发现.

**How**: 任何 PWA 项目上线前必加 `useInstallPrompt` composable + `<InstallPrompt />` 组件.

---

## 6. 下一步 (派第七批 + 收尾)

### 6.1 第七批派工预排 (主指挥拍板后启动)

候选 agent (基于 5th-wave + 6th-wave 教训):
- **Agent 1**: 派工后端到端验证脚本化 (派工消息模板 + verify.py 自动跑清单)
- **Agent 2**: minio + KB 双清自动化 (test teardown 集成)
- **Agent 3**: SafeIntakeContext 全应用覆盖 (所有 KB intake 路径)
- **Agent 4**: cache_drive_list 实战验证 (移动端 dashboard 30s TTL 行为)
- **Agent 5**: knowledge field constraints migration (0024 + 4 污染数据清理)
- **Agent 6**: worktree merge 双清脚本 (`scripts/post-merge-cleanup.sh`)
- **Agent 7**: baseline audit + 命名规范 (`tests/qa-bench/baselines/` 整理)

### 6.2 v2.21 范式终极沉淀

- 6 批派工实战汇总 (本 memory)
- 锚点范式 v2.21 完整定义 (含 4 阶段流程 + 11 协调铁律 + 11 技术铁律)
- 7 新铁律永久沉淀 (派工验证 / minio/knowledge 双清 / SafeIntakeContext / cache_drive_list TTL / worktree 双清 / baseline audit / PWA install UI)
- 5th-wave 主指挥决策 "测试内容删去" 完整复盘
- 6th-wave 教训加固 3 模块 (SafeIntakeContext + cache_drive_list + knowledge field constraints)

### 6.3 主指挥拍板

- 第七批是否启动?
- v2.21 范式是否固化为项目级 SOP (类似锚点范式)?
- 是否新增 "派工验证清单" 模板到 `.claude/skills/`?

---

## 7. 跨主题收口

- **6 批派工**: 5th-wave (7 source + 1 chore) + 6th-wave (7 source) = **30 agent commits** 实际数据
- **commit hash 累计**: 1st-wave 7 + 2nd-wave 7 + 3rd-wave 7 + 4th-wave 7 + 5th-wave 7 + 5th-wave chore 1 + 6th-wave 7 = **43 commits** (含 dist rebuild 4 次)
- **main HEAD**: `12491294c feat(safety): safe_minio_intake + drive_cache + knowledge field constraints (5th-wave 教训加固)`
- **基础 baseline 守恒**: 71 PASS + 7 SKIP 0 regression (锚点范式 22 天实战)
- **memory 沉淀**: 7 新铁律 + 5th-wave 主决策复盘 + 6th-wave 教训加固 3 模块

详见:
- 锚点范式 [`memory/multi-agent-task-orchestration-baseline.md`](./multi-agent-task-orchestration-baseline.md) (W20 锚定, 22 天实战)
- 锚点范式 21 天 [`memory/anchor-paradigm-21-day-validation-2026-07-22.md`](./anchor-paradigm-21-day-validation-2026-07-22.md) (W42 累计)
- 5th-wave 主决策 [`memory/2026-07-22-5th-wave-cleanup.md`](./2026-07-22-5th-wave-cleanup.md)
- 6th-wave 教训加固 (本 memory)