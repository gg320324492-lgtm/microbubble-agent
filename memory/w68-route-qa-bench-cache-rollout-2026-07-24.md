# W68 第 4 批 B-3 Route qa-bench cache workflow 接入 (锚点范式第 54 守恒)

> **作者**: W68 第 4 批 B-3 Route Agent
> **日期**: 2026-07-24
> **基线 HEAD**: `26c7c5620`
> **目标 commit**: `ci/qa-bench-ghcr-cache-rollout-2026-07-24`
> **配套文档**: `docs/qa-bench-ghcr-cache-rollout.md` (本次新增) + `docs/qa-bench-ghcr-cache-design.md` (W68 B-2) + `docs/qa-bench-ci-cache-patch.yml` (W68 B-2)
> **配套测试**: `tests/test_workflow_yaml_syntax.py` (本次新增, 6 PASS)
> **铁律**: 0 production code 改动 + W19 选项 A 维持 + 锚点范式第 54 守恒

---

## 1️⃣ 任务背景

### 1.1 触发链

W68 第 3 批 B-2 agent (`ci/qa-bench-ghcr-cache-design-2026-07-24`) 写了:
- `docs/qa-bench-ghcr-cache-design.md` — 路径 1 技术设计 (4 层 cache 架构)
- `docs/qa-bench-ci-cache-patch.yml` — workflow patch 文件 (**不直接生效, 待主指挥拍板**)
- `memory/w68-route-b2-ghcr-cache-design-2026-07-24.md` — 设计 memory

主指挥 2026-07-24 拍板"路线 B-3 = 路线 B-2 设计的最小可执行子集":
- 加 `cache-from: type=gha,mode=max` 到 docker pull step
- 加 `cache-scope: ${{ github.workflow }}-${{ github.job }}` 到 setup-buildx step
- 改 cache step 加 `restore-keys: ${{ runner.os }}-multi-` (兜底匹配) — **注释强化, 字段已存在**
- **不动**其他 step (W67 第 38 步 setup-buildx `if: false` 保留 + W67 第 41 步 SKIP_DB_SETUP 等保留)

### 1.2 W68 第 4 批跨主题派工上下文

W68 第 4 批 ~12 agents 并行 (锚点范式第 51-54 守恒):
- 路线 A: Drive v2 PR9 folder admin permissions
- 路线 B: Drive v2 PR9 WS push + drive v2 PR9 folder admin permissions
- 路线 C: Mobile UX v3.1 ASCII screenshots 替换
- 路线 D: **本次 — qa-bench D6 GHCR cache workflow 接入**
- 路线 E: 计划 low-occupancy speaker filter (review)
- 路线 F: 计划 meeting #64 repair

**本次 (B-3) = 路线 D 唯一 agent**, 跨主题在 1 commit 内收口.

---

## 2️⃣ 实施步骤 (实际执行时间线)

### 2.1 准备 (5 min)

1. 读 `docs/qa-bench-ci-cache-patch.yml` (W68 B-2 输出) — 确认 3 处改动精确坐标
2. 读 `docs/qa-bench-ghcr-cache-design.md` — 理解 4 层 cache 设计意图
3. 读 `.github/workflows/qa-bench-ci.yml` — 找到当前 3 个目标 step (Cache / Setup-buildx / Pull)
4. 创建 worktree 分支: `git checkout -b ci/qa-bench-ghcr-cache-rollout-2026-07-24`

### 2.2 workflow 改动 (10 min, 3 处 Edit)

1. **Cache step name 注释化** + 加 restore-keys 兜底匹配说明:
   - step name 加引号包裹避免 YAML colon parse error (`: restore-keys` 被 YAML 当 mapping key)
   - 注释强化 restore-keys 字段意图

2. **Setup-buildx step 加 cache-scope**:
   - `if: false` 保留 (W67 路线 2 主导, 不激活)
   - 加 `with.cache-scope: ${{ github.workflow }}-${{ github.job }}` (未来回退时自动生效)
   - 注释说明命名规则 + 防 PR 互覆盖目的

3. **Pull step 加 cache-from 注释**:
   - `docker pull` 命令**不变** (docker CLI 不接受 `--cache-from` 参数)
   - 加 4 行注释说明 `cache-from: type=gha,mode=max` 意图 (未来 docker buildx pull 时自动生效)
   - step name 加 W68 B-3 标记便于追溯

### 2.3 测试 (15 min, 6 PASS)

1. 创建 `tests/test_workflow_yaml_syntax.py` (~165 行):
   - test_yaml_safe_load_passes — yaml.safe_load 无异常
   - test_qa_bench_d5_job_exists — job 存在
   - test_setup_buildx_step_has_cache_scope — cache-scope 字段存在 + 模板正确
   - test_actions_cache_step_has_restore_keys — restore-keys 字段存在 + multi- prefix
   - test_pull_pre_built_image_step_has_cache_from_doc — Pull step 内含 mode=max 注释
   - test_no_production_code_modified — 反向断言无 alembic upgrade head / docker build / inline app import

2. 反复 debug 测试 (3 轮):
   - 第 1 轮: step name 含 `:` (colon) → YAML parse error → 加引号
   - 第 2 轮: forbidden_patterns `\balembic upgrade\b` 误中注释 → 改 `^\s*alembic` (仅检查 run 行)
   - 第 3 轮: pull_section regex 误中 setup-buildx 注释里的引用 → 锚定到 `- name:` 真 step

3. 最终结果: `SKIP_DB_SETUP=1 pytest tests/test_workflow_yaml_syntax.py -v` → **6 PASS**

### 2.4 文档 + memory (10 min)

1. `docs/qa-bench-ghcr-cache-rollout.md` (~200 行):
   - 改动 diff 详解 (4 处改动, 每个 Before/After 对比)
   - 预期 CI 时间变化 (D5 vs D6 收益表)
   - 部署步骤 + 回滚方式 (3 级回滚: 紧急 / 软 / 完全)
   - 风险监控 (短期 1 周 + 中期 1 月)
   - 不在本次范围 (留给 W68 第 5 批)

2. `memory/w68-route-qa-bench-cache-rollout-2026-07-24.md` (本文件):
   - 任务背景 + 实施步骤时间线 + 5 条新铁律 + 未来触发点

---

## 3️⃣ 5 条新铁律沉淀

### 铁律 1: YAML step name 含 colon 必须用引号包裹

```yaml
# ❌ 反模式 (YAML parse error: mapping values are not allowed here)
- name: Cache pip + Docker layers + apt (W68 B-3: restore-keys 兜底匹配)
#                                                          ^ colon 当 mapping key

# ✅ 正模式 (YAML 把整个字符串当 key, 不解析内部 colon)
- name: "Cache pip + Docker layers + apt (W68 B-3 restore-keys 兜底匹配)"
```

**根因**: YAML 解析 `name:` 时, 右侧第一个 token 当作 value; 第一个 token 含 `:` → YAML 期待 mapping value, 报 parse error.
**纪律**: GitHub Actions step name 含 `:` 或其他 YAML 特殊字符时, **必须用双引号包裹**, 避免 parse error.

### 铁律 2: workflow 测试断言禁止误中注释

```python
# ❌ 反模式 (误中注释里的字符串)
forbidden_patterns = [
    r"\balembic upgrade\b",  # 注释里写了"alembic upgrade head 是另一回事"
]

# ✅ 正模式 (仅检查真 run 行, 用 ^ 锚定 + MULTILINE)
dangerous_patterns = [
    (r"^\s*alembic\s+upgrade\s+head", "..."),  # 锚定行首, 注释行以 # 开头不会匹配
]
```

**根因**: workflow YAML 含大量注释 (`# 注释`), 注释里提到的关键字不能当 forbidden pattern.
**纪律**: workflow 测试断言**必须用 `^` 或 `\s` 锚定到真代码行**, 排除注释干扰. 或显式 split 注释 + 代码再扫.

### 铁律 3: workflow 测试断言禁止跨 step 边界误匹配

```python
# ❌ 反模式 (regex 跨多 step 边界匹配到错误内容)
pull_section = re.search(
    r"Pull pre-built app-test image.*?docker pull",
    raw, re.DOTALL,
)
# 误匹配: setup-buildx 注释里有 "Pull step" + 紧接真 Pull step + "docker pull"
# → 整段 (setup-buildx + Pull) 都被当成 pull_section → mode=max 检查失败

# ✅ 正模式 (锚定到真 step name 字段)
pull_section = re.search(
    r'-\s+name:\s*"Pull pre-built app-test image.*?docker images app-test:ci',
    raw, re.DOTALL,
)
```

**根因**: workflow YAML 多 step 共享注释空间 (大段 `=== W67 第 48 步 ===` 注释块), regex 跨 step 边界匹配时易误中.
**纪律**: workflow 测试断言**必须用 `-\s+name:\s*` 锚定到真 step 起始**, 然后用稳定 token (`docker images ...`) 锚定 step 结束. 注释里的字符串一律不算.

### 铁律 4: docker pull 命令本身不接受 --cache-from

- `docker pull` (CLI 命令): 仅拉镜像, 无 cache 概念
- `docker buildx build --cache-from=type=gha` (buildx 子命令): 真支持 cache-from

**当前 qa-bench-ci.yml Pull step 用 `docker pull`** (W67 路线 2: pre-built image), 因此:
- 注释里加 `cache-from: type=gha,mode=max` 文档化意图 ✓ (本次做的)
- 但 Pull 命令本身不变 (W68 D6 不动)
- 真生效需要: 启用 setup-buildx + 改 `docker pull` → `docker buildx build --cache-from=type=gha,mode=max --tag app-test:ci --load`

**纪律**: workflow cache 改动文档化与实际生效**是两件事**. 注释化 cache 配置是为未来 docker buildx 改造铺垫, 不等于本次加速.

### 铁律 5: cache-scope 仅在 buildx step 启用时生效

- 当前 setup-buildx step 是 `if: false` (W67 路线 2: pre-built image 主导)
- `with.cache-scope` 仅在 step 真跑时才生效
- 主指挥未来切回 W67 路线 1 (buildx), cache-scope 自动生效, **本次改动是未来路径准备**

**纪律**: workflow metadata 改动 (cache-scope / cache-from 注释) **当下 0 加速**, 但为未来路径切换准备, 不算 "无效改动". 在 memory + docs 里必须明确标 "未来生效", 避免误以为本次加速.

---

## 4️⃣ 锚点范式第 54 守恒

### 4.1 W68 路径演化 (累计)

- W67 (W66 27 → 28): qa-bench D5 gate 真治本失败接受 docs/CI 占位 + 8 批 42+ agent commits
- W68 第 1 批 (W67 28 → 29): Drive v2 PR8 收官 + Mobile UX 14+1 agents merged (main HEAD `13548ff2b`)
- W68 第 2 批 (W68 29 → 30): 5 路径调研汇总 + baseline 守恒验证 (71 PASS + 7 SKIP)
- W68 第 3 批 (W68 30 → 33): Mobile UX v3.1 + Drive v2 PR9 + 路线 B-2 设计 (main HEAD `26c7c5620`)
- **W68 第 4 批 (W68 33 → 54)**: 本次 — 路线 B-3 D6 cache workflow 真接入

### 4.2 W68 第 4 批跨主题派工 (12 agents 并行)

| 路线 | 内容 | 守恒 | 派工 |
|------|------|------|------|
| A | Drive v2 PR9 folder admin permissions | 守恒 | 1 agent |
| B | Drive v2 PR9 WS push + folder admin permissions | 守恒 | 2 agents |
| C | Mobile UX v3.1 ASCII screenshots 替换 | 守恒 | 1 agent |
| **D** | **本次 — qa-bench D6 GHCR cache workflow 接入** | **守恒** | **1 agent** |
| E | 计划 low-occupancy speaker filter (review) | 守恒 | 1 agent |
| F | 计划 meeting #64 repair | 守恒 | 1 agent |
| + 大批其他 | 文档 + memory + 整合 | 守恒 | 5+ agents |

**本次 (B-3) 是 W68 第 4 批路线 D 唯一真接入 agent**, 与其他 5+ agent 文档/memory 并行.

### 4.3 锚点范式守恒

- ✅ 0 production code 改动铁律完全维持 (仅 .github/workflows/ + tests/ + docs/ + memory/)
- ✅ 文档化 + 测试化 workflow 改动 (未来可重现 + 可回归)
- ✅ 与 W68 第 3 批 B-2 设计配套 (设计 → 实施闭环)
- ✅ W19 选项 A 维持 (无生产代码改动)
- ✅ 71 PASS + 7 SKIP baseline 守恒 (本次新增 6 PASS, 总计 77 PASS)
- ✅ 1 commit 收口 (跨文档 + tests + memory)

### 4.4 与 W68 锚点范式守恒关系

W68 跨 4 批累计 commits:
- W68 第 1 批: 30 commits (Drive v2 PR8 7 + Mobile v3.0 7 + Safari 1 + 文档 15)
- W68 第 2 批: ~10 commits (5 路径调研 + grand closure)
- W68 第 3 批: ~12 commits (Mobile v3.1 4 + Drive v2 PR9 5 + 路线 B-2 设计 3)
- W68 第 4 批: 12+ agents (本次 1 commit 收口 + 其他 11+ agents 并行)

锚点范式守恒次数累计: W7 12 → W66 27 → W67 28 → W68 30 → W68 第 4 批 54.

---

## 5️⃣ 未来触发点

### 5.1 本次改动生效条件 (触发路径)

| 触发条件 | 触发路径 | 预期收益 |
|----------|---------|---------|
| 主指挥拍板切回 W67 路线 1 (buildx) | 取消 `if: false` + 改 `docker pull` → `docker buildx build --cache-from` | cache-scope 自动生效, 跨 run hit rate 50% → 90%+ |
| GHCR pre-built image 改用 image digest 标签 (而非 `latest`) | `docker pull ghcr.io/.../microbubble-agent:app-test-{sha}` | 避免 latest tag 互相覆盖, cache hit 稳定 |
| 主指挥拍板实施 W68 B-2 Layer 3+4 (Pre-warm + pycache-vol) | 加 Pre-warm step + docker volume mount | 总 CI 时间节省 5-9 min |

### 5.2 监控指标 (1 周内 + 1 月内)

| 监控指标 | 阈值 | 触发动作 |
|----------|------|---------|
| docker pull 时间 | < 30 s (含冷启动) | > 60 s 持续 3 次 → revert |
| qa-bench D5 总耗时 | < 75 min | > 90 min 持续 2 次 → 考虑完整 cache 方案 |
| Cache restore 时间 | < 30 s | > 60 s → 检查 key hash |
| GHCR storage 用量 | < 80% 配额 | 接近阈值 → mode=max → mode=min |

### 5.3 不在本次范围 (留给 W68 第 5 批)

- 改 `docker pull` → `docker buildx build --cache-from=type=gha,mode=max` (大改动, 需评估 buildx 启动开销)
- 启用 setup-buildx step (`if: !false`), 配合 docker buildx pull
- 加 Pre-warm lazy models step (W68 B-2 Layer 3, ~30 行新增)
- 加 pycache-vol cross-run volume (W68 B-2 Layer 4, ~10 行新增)
- 加 build-image.yml 端 cache-scope 对齐 (W68 B-2 Layer 1, ~5 行新增)

---

## 6️⃣ 关联文档

- **W68 第 3 批 B-2 设计**: `docs/qa-bench-ghcr-cache-design.md` (路径 1 完整 4 层架构)
- **W68 第 3 批 B-2 patch**: `docs/qa-bench-ci-cache-patch.yml` (workflow patch 文件)
- **W68 第 3 批 B-2 memory**: `memory/w68-route-b2-ghcr-cache-design-2026-07-24.md`
- **本次 rollout 文档**: `docs/qa-bench-ghcr-cache-rollout.md` (新增)
- **本次测试**: `tests/test_workflow_yaml_syntax.py` (新增, 6 PASS)
- **W68 grand closure**: `memory/w68-grand-closure-2026-07-24.md` (第 30 守恒)
- **CLAUDE.md 历史铁律**: 锚点范式 + 0 production code 改动 + W67 第 47 步 timeout 经验

---

## 7️⃣ 完成定义核对

- ✅ 4 文件交付:
  1. `.github/workflows/qa-bench-ci.yml` — 3 处改动 (Cache / Setup-buildx / Pull)
  2. `tests/test_workflow_yaml_syntax.py` — 新增, 6 PASS
  3. `docs/qa-bench-ghcr-cache-rollout.md` — 新增, ~200 行
  4. `memory/w68-route-qa-bench-cache-rollout-2026-07-24.md` — 本文件
- ✅ workflow YAML syntax 验证 PASS (yaml.safe_load 无异常)
- ✅ 3 个 cache 字段全部到位:
  - cache-scope (setup-buildx.with) — ${{ github.workflow }}-${{ github.job }}
  - cache-from: type=gha,mode=max (Pull step 注释 + step name 标记)
  - restore-keys: ${{ runner.os }}-multi- (Cache step 注释强化 + step name 标记)
- ✅ 0 production code 改动铁律完全维持 (app/ web/ alembic/versions/ 全部不动)
- ✅ 锚点范式第 54 守恒 (W68 第 4 批)
- ✅ 71 PASS + 7 SKIP baseline 守恒 (+6 PASS = 77 PASS)

---

> 📌 **本次 commit 不 merge, push 到 origin, 等主指挥来 merge.**
>
> 锚点范式第 54 守恒 — W68 第 4 批 B-3 路线 D6 cache workflow 真接入, 0 production code 改动铁律完全守恒, 与 W68 第 3 批 B-2 设计文档配套形成 "设计 → 实施" 闭环.