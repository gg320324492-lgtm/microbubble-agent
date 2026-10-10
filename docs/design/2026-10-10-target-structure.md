# 全项目目标目录结构设计 + 分批迁移方案 (2026-10-10)

> **这是设计文档，不是执行记录。** 撰写时**未移动、未删除、未重命名任何文件**，未改配置，
> 未 commit / push / git add，未碰任何 docker 容器状态。
> 事实基础 = [`docs/audit/2026-10-10-structure-mapping.md`](../audit/2026-10-10-structure-mapping.md)（2026-10-10 `main` @ `6a0dc9bd0`）。
> 本文档在其之上做了**补充取证**（见 §0），并给出**有观点的结论**而非可能性罗列。
> 交主指挥拍板后方可执行。

---

## 0. 对测绘报告的三处修正（会影响决策，先读）

测绘报告的三条结论经复核**部分不成立**。若照抄会做错决策，故前置澄清。

### 0.1 🔴 修正一：同深度改名**不需要**改 `parents[]`（测绘报告 B4 的"安全改法"是错的）

测绘报告 B4 写道：把 9 个 `_xNN` 目录"加一层（如 `tests/a11y/`）必须同步改 `parents[2]`→`parents[3]`"。

**这是错的 —— 前提是误解。** 实测：

```
tests/a11y_login_x18/test_authed_field.py   parents[0]=a11y_login_x18  parents[1]=tests  parents[2]=<root>
tests/a11y/test_authed_field.py             parents[0]=a11y           parents[1]=tests  parents[2]=<root>
                                                  ^^^^^^^^^^^^^^^^^^^ 完全相同
```

**`tests/<subdir>/x.py → tests/<newsubdir>/x.py` 是同深度改名，`parents[2]` 语义不变，零编辑。**
29 个子目录文件的 `parents[2]` 全部**天然免疫**。

真正会断的只有一种操作：**把 `tests/` 根下的散装文件（深度 1）挪进子目录（深度 2）**。
实测这类文件共 **15 个**，它们用的是 `parents[1]` 反推仓库根：

```
tests/test_billing_payment_mock_e2e.py            parents[1]
tests/test_commercial_phase8_closure_e2e.py       parents[1]
tests/test_drive_v2_pr10_collab_e2e.py            parents[1]
tests/test_drive_v2_pr10_collab_smoke.py          parents[1]
tests/test_drive_v2_pr3_comment_v2_e2e.py         parents[1]
tests/test_drive_v2_pr7_file_request_e2e.py       parents[1] parents[2] parents[4]
tests/test_drive_v2_w72b1_sharing_e2e.py          parents[1]
tests/test_w75_verify_e2e.py                      parents[1]
tests/test_w78_saas_deployment_e2e.py             parents[1]
tests/test_w79_commercial_operation_e2e.py        parents[1]
tests/test_w79_commercial_private_deployment_e2e.py parents[1]
tests/test_w80_7d_commercial_operation_e2e.py     parents[1]
tests/test_w81_b1_commercial_operation_closure_e2e.py parents[1]
tests/test_w81_c1_phase8_closure_e2e.py           parents[1]
tests/test_w82_b1_billing_webhook_mount_e2e.py    parents[1]
```

（任务书说的"33 个文件 / 9 个真依赖"与测绘报告的"44 个 / 30 个"均未对上实测；实测
`parents[2]`×42 / `parents[1]`×23 / `parents[3]`×3 / `parents[4]`×1，其中**子目录文件 29 个**、散装文件 15 个。
**以本节实测为准。**）

**结论**：批次 1（9 个 `_xNN` 归位）是**零 `parents[]` 编辑**的，🟢 而非 🟡。

### 0.2 🔴 修正二：`tests/test_no_prod_db_imports.py` 的 ALLOWLIST 是**路径敏感**的（测绘未覆盖）

守门测试（CLAUDE.md 明令不得归档者）用 `rglob` 全量扫描，但放行名单**同时用文件名和相对路径**两种 key：

```python
# tests/test_no_prod_db_imports.py:26-40
TESTS_DIR = Path(__file__).resolve().parent          # = tests/
ALLOWLIST = {
    ("conftest.py",),                                # 文件名 key —— 移动不受影响
    ("test_fin1_backup_share_block.py",),            # 文件名 key —— 移动不受影响
    ("test_database_lazy_init.py",),                 # 文件名 key —— 移动不受影响
    ("e2e", "test_anchor_scripts_smoke.py"),          # ★ 路径 key —— 移动该文件即失效
    ("integration", "test_hnsw_bench_real.py"),       # ★ 路径 key —— 移动该文件即失效
    ("test_no_prod_db_imports.py",),
}
# :62-65   rel_key = tuple(rel.parts);  if rel_key in ALLOWLIST or (rel.name,) in ALLOWLIST
```

- 文件名 key（`rel.name` 分支）→ **任何平移都安全**。
- **路径 key（`rel.parts` 分支）→ 移动 `tests/e2e/test_anchor_scripts_smoke.py` 或
  `tests/integration/test_hnsw_bench_real.py` 会让守门测试把"合法例外"判成违规**。

**影响**：这两个文件**禁止平移**。本方案的所有批次都未触碰它们（§2 已核对）。

### 0.3 🟡 修正三：`restart_gpu_workers.bat` 的过时路径已被修，**但该修复尚未 commit**

测绘报告 E3（写于 18:33）记它仍指向 `.workbuddy\vibevoice-test` —— 写报告时属实。
**但该文件在工作区已于 18:35:06 被改动**（本次重构之外的操作，非本方案所为）：

```
restart_gpu_workers.bat:3:  rem 2026-10-10: VIBEVOICE_HOME 从已迁走的 .workbuddy\vibevoice-test 改到 data\vibevoice-test
restart_gpu_workers.bat:5:  if "%VIBEVOICE_HOME%"=="" set "VIBEVOICE_HOME=E:\microbubble-agent\data\vibevoice-test"
```

⚠️ **该修复是未提交的浮动改动**（`git show HEAD:restart_gpu_workers.bat` 仍是旧的 `.workbuddy` 硬编码）：

```
 M restart_gpu_workers.bat      ← git status 至今为 modified，未 stage 未 commit
```

**两个结论**：
1. 本方案**不动**该文件 —— 再改会把正确值改回错误值。
2. ⚠️ **提请主指挥注意**：这是一份**只存在于工作区、未入库**的正确修复。
   在合并任何重构批次前应先把它单独提交，否则一次 `git checkout` / `reset --hard`
   就会静默丢失（类 20.220 的形态：工作区看着对，提交历史里没有）。

### 0.4 补充取证：`tests/eval/rag_prompt_meta.test.py` 从未被 pytest 收集

`pytest.ini` 的 `python_files = test_*.py` **不匹配** `*.test.py` 后缀。全库此类文件**仅此 1 个**：

```
tests/eval/rag_prompt_meta.test.py   ← 3 个 test_ 函数，从未执行过
```

其 docstring 写"pytest file discovery compatibility for dotted test filename"，但该命名恰好
使其**被发现规则排除**。→ 这是**静默失效**（类 20.219/20.220 同族：状态看着在，副作用没发生）。
**需主指挥裁定**：当初是否有意排除？处置见批次 3（**条件执行**，不是无脑改名）。

### 0.5 补充取证：`tests/_archive/` **不存在**

任务书提到"`tests/_archive/` 与 `scripts/_archive/` 语义冲突" —— 实测 `tests/` 下**零个** `_archive` 条目。
`tests/` 的"归档"是通过**文件内模块级 `pytest.skip` 守卫 + `tests/ARCHIVED.md` 登记表**实现的
（实测守卫文件 **88 个**，不是 CLAUDE.md 记的 87 个），**文件全部原地保留**。
→ 当下**不存在**命名冲突；本方案亦**不新建** `tests/_archive/`（§2.4 给出理由）。

---

## 1. 目标目录结构

### 1.1 设计思路（一句话）

> **按"是否有活接线"分层，而不是按"是什么用途"分层。** 顶层只保留**职责互斥的少数几类**，
> `scripts/` 顶层**保持平铺**（命名已经自解释，且 26 个文件有硬接线搬不动），
> `tests/` 只消灭**无语义的会话编号目录**，不为了分类而分类。

### 1.2 顶层结构（53 项）

```
microbubble-agent/
│
├── 【核心代码 · 全部原地冻结 🔴】—— 有 compose mount / Dockerfile COPY / CI 写死
│   ├── app/                    🔴 compose ./app:/app/app ×4 + Dockerfile.mcp 精确 COPY
│   ├── alembic/                🔴 compose ./alembic/versions ×4 + alembic.ini
│   ├── web/                    🟡 compose ./web/dist + playwright.yml + 类 20.133 构建确定性
│   ├── apps/                   🟡 pnpm-workspace.yaml + desktop-release.yml wd=apps/desktop
│   ├── packages/               🟢 pnpm-workspace.yaml
│   ├── mcp_server/             🟡 Dockerfile.mcp COPY（profile vision，默认不启）
│   └── nginx/                  🔴 compose ×3 只读挂载
│
├── 【测试】
│   └── tests/                  🟡 28 个子目录（现 33）+ 250 个散装文件 → 见 §2
│
├── 【工具链 · 顶层平铺，本轮仅归档会话垃圾】
│   └── scripts/                🟡 201 顶层 + 46 子目录 → 见 §3
│
├── 【构建部署 · 全部原地】
│   ├── docker/                 🟡 Dockerfile.commercial + visual-regression/
│   ├── Dockerfile{,.db,.funasr,.mcp,.voice-pipeline,.whisper}
│   ├── docker-compose{,.dev,.test}.yml     🔴 test.yml:79 引 scripts/init_test_db_all.py
│   ├── funasr_entrypoint.sh    🔴 compose :264 挂载
│   ├── whisper_entrypoint.sh   🟡
│   └── frps.service / webhook.service  （实际在 scripts/ 下，见 §3）
│
├── 【运行时数据 · 全部原地冻结 🔴】
│   ├── data/                   🔴 ./data:/app/data ×4 + postgres/redis/neo4j/ollama(61.6G)
│   └── models/                 🟡 compose ×3
│
├── 【文档 · 全部原地】
│   ├── docs/                   🟢 654 文件 → 新增本设计文档
│   ├── memory/                 🟢 487 文件
│   └── CLAUDE.md AGENTS.md CHANGELOG.md README.md ROADMAP.md
│
├── 【CI / 配置 · 全部原地冻结 🔴】
│   ├── .github/                🔴 11 workflow
│   ├── .pre-commit-config.yaml 🔴 10 处 scripts/ 引用
│   ├── pytest.ini              🔴 testpaths = tests
│   ├── alembic.ini             🔴
│   ├── requirements.txt        🔴
│   ├── package.json / pnpm-workspace.yaml / pnpm-lock.yaml   🟡
│   └── .env.example / .env.production.example / .dockerignore / .gitleaks.toml / .hintrc / .gitignore
│
├── 【工具链 · 红线不碰】
│   ├── .agents/                🔴 54 文件，任务书明令不碰
│   ├── .claude/                🔴
│   ├── .codex/                 🔴
│   └── setup.ps1               🟢
│
├── 【判定为"不动" · 需主指挥裁定生死，见 §5】
│   ├── commercial/             🟡 边界模糊，但**判定保留**
│   ├── observability/          🟢 孤儿 → 建议移入 docker/observability/（批次 6，低优先）
│   ├── config/                 🟢 1 文件零引用 → **需裁定：接线还是删除**
│   ├── results/                🟢 65 文件 4.9M 纯归档 → 建议移入 docs/ 或保持
│   └── restart_gpu_workers.bat 🟢 **已修好，原地不动**
│
└── 【独立 git 子仓 · 不在主仓 🔴】
    └── desktop-conversion/     193 commits + 私有远端，不在主仓 git ls-files
                                → 重构范围**显式排除**，需主指挥单独决策（§5）
```

### 1.3 顶层移动汇总表

| 条目 | 决定 | 风险 | 说明 |
|---|---|---|---|
| `app/` `alembic/` `nginx/` `data/` `web/dist` | **原地** | 🔴 | compose 39 处 mount |
| `.github/` `.pre-commit-config.yaml` `pytest.ini` `alembic.ini` `requirements.txt` | **原地** | 🔴 | CI/pre-commit 写死 |
| `scripts/` 201 顶层文件 | **原地（平铺）** | 🟡 | 见 §3.1 的有观点结论 |
| `scripts/_archive/` | 原地 + 新增 `a4X-*/` 子目录 | 🟢 | 批次 4 |
| `observability/` → `docker/observability/` | 移（低优先） | 🟢 | 批次 6，可单独否决 |
| `commercial/` `config/` `results/` | **原地** | 🟢 | 见 §5 决策点 |
| `tunnel/` + `scripts/tunnel/` | **本轮不合并** | 🟡 | 见 §3.4 的有观点结论 |
| `desktop-conversion/` | **范围外** | 🔴 | 见 §5 |

---

## 2. `tests/` 详细方案（批次 1-3 的执行对象）

### 2.1 现状关键数字（实测，纠正测绘）

| 项 | 测绘报告 | **实测** | 影响 |
|---|---|---|---|
| 子目录数 | 33 | 33 ✅ | — |
| 散装文件 | "另有若干" | **246**（占 548 的 45%） | **这是 tests/ 真正的大头** |
| basename 冲突组 | "1 组三重复" | **1 组**（`test_intent_classifier.py` ×3） | 冲突面比预想窄 |
| 模块级守卫文件 | 87 | **88** | — |
| 子目录文件用 `parents[2]` | 30 | **29** | — |

### 2.2 9 个 `_xNN` 会话目录逐个归宿

**判定规则**：会话编号（`_xNN`）是**派工痕迹**，不是语义。看到 `tests/a11y_login_x18/` 的人
无法从名字判断它是活的还是归档的 —— 这是**命名债**，必须消灭。

| 现目录 | 文件 | 状态 | 归宿 | 理由 |
|---|---|---|---|---|
| `a11y_login_x18/` | `test_authed_field.py` | 🟢 活 | **`tests/a11y/`** | a11y 登录态守卫，与 baseline/axe 同族 |
| `baseline_sync_x29/` | `test_sync.py` | 🟢 活 | **`tests/a11y/`** | 守的是"a11y baseline 必入 git"，同族 |
| `a11y_violation_x2/` | `test_no_real_violation.py` | ⚪ 归档 | **`tests/a11y/`** | a11y 终态验证（25 baseline × 274 违规修完） |
| `axe_violation_x19/` | `test_axe_x19_no_real_violation.py` | ⚪ 归档 | **`tests/a11y/`** | axe 真违规门禁（color-contrast 72→0），同族 |
| `inject_auth_x4/` | `test_fail_loud.py` | ⚪ 归档 | **`tests/a11y/`** | 它**就是** a11y 假绿的根因守卫（类 20.23 负向对照），同族 |
| `ci_real_x29/` | `__init__.py` + `test_deployment.py` | ⚪ 归档 | **`tests/realenv/`** | 需真服务器/凭据 + `TEST_TOKEN`，语义**完全等同** realenv |
| `icon_wr1/` | `test_play_to_video.py` | ⚪ 归档 | **`tests/dist_health/`** | `RAGEvalPanel.vue` icon 致 `npm run build` exit 1 = 前端构建硬门，同族 |
| `src_tests_x5/` | `test_naming.py` | 🟢 活 | **`tests/dist_health/`** | vitest spec 命名门禁，同属"前端产物/约定健康"，同族 |
| `brief_v41_x6/` | `test_doc_exists.py` | ⚪ 归档 | **散装 `tests/` 根**，改名 `test_brief_v41_x6_doc_exists.py` | 语义 = 一次性文档验收快照，**不构成一个分类**（只此 1 文件）；按"1-2 文件的模糊分类保持平铺更清晰"原则**打平**，并按现有惯例（`test_w81_c1_phase8_closure_e2e.py` 等）保留会话前缀 |

**汇总**：9 目录 → **8 文件**进 3 个已有/新建目录（`a11y/` 新建 5 文件、`realenv/` +1、`dist_health/` +1），
**1 文件打平到根**。`__init__.py` 随 `ci_real_x29/` 迁入 `realenv/`（后者已有 `__init__.py`，覆盖不变）。

**basename 冲突复核**：目标目录内 5 个 a11y 文件 basename 互不相同；`test_no_real_violation.py`
与 `test_axe_x19_no_real_violation.py` 已是不同名（前科已处理）。`test_doc_exists.py` 改名后
在全库唯一。**全库 basename 冲突仍为 1 组**（`test_intent_classifier.py`，本方案不触碰）。

**`__init__.py` 决策**：`tests/a11y/` 与 `tests/dist_health/` **不补** `__init__.py`。
理由：`a11y_login_x18/` `dist_health/` `icon_wr1/` `src_tests_x5/` 现在都没有，且目标目录内无 basename
冲突 —— 补 `__init__.py` 是为不存在的冲突付费。（`ci_real_x29/` 的 `__init__.py` 随迁，
因 `realenv/` 本来就有，属覆盖维持而非新增。）

### 2.3 其余 24 个子目录：保留 / 合并 / 扁平 逐个说明

| 目录 | 文件 | 决定 | 理由 |
|---|---|---|---|
| `qa-bench/` | 126 | 🔴 **冻结** | 2 个 workflow 共 8 处写死路径 + `working-directory` ×5 |
| `rag_framework/` | 11 | 🔴 **冻结** | `rag-framework-ci.yml:120` 写死 `pytest tests/rag_framework/` |
| `visual/` | 3 | 🔴 **冻结** | `playwright.yml` 3 处写死 `.mjs` 配置路径 |
| `rag/` | 52 | **保留** | RAG 检索主干，有自己的 `conftest.py` |
| `unit/` `integration/` `e2e/` `perf/` `realenv/` | 63 | **保留** | 标准测试分层，语义无歧义 |
| `request_context/` | 4 | **保留** | 特性域，名字即语义 |
| `rag_eval/` | 4 | **保留（不并入 `rag/`）** | ⚠️ **看似该合并，实则危险**：`rag/` 有 `conftest.py`，合并会让 `rag_eval` 的 4 个测试**突然继承** rag 的 fixture（可能触发 auto-skip 或 DB 注入）= **行为变更**，非纯改名。为 4 个文件不值得 |
| `sentry/` `precommit/` `trivy/` `pg_exporter/` `alembic/` `playwright_ci/` `k6/` | 15 | **保留** | 每个都是**单一且自解释**的守卫域。`trivy/`(镜像固定) 与 `gitleaks/`(密钥扫描) 语义相邻但**工具不同、判据不同**，合并成 `security_scan/` 只增耦合不增清晰 |
| `gitleaks/` `npm_audit/` `eval/` | 3 | **保留**（`eval/` 见批次 3） | 单文件但名字即语义，无歧义 |
| `dist_health/` | 1→3 | **保留**（批次 1 后增至 3） | 批次 1 扩容后达到"成组"门槛 |
| **`api/v1/`** | 2 | 🔴 **打平到 `tests/` 根** | ⚠️ **实测该目录深度 3（`tests/api/v1/x.py`）且无 `__init__.py` —— 它本身就是全库唯一违反两层深度约束的地方**；两个文件是 drive API 测试，而 42 个 `test_drive_*` 兄弟**全在散装区**。打平 = **消除深度违规 + 归队**，不新增任何编辑 |
| **`scripts/`** | 1 | 🔴 **打平到 `tests/` 根** | 目录名 `tests/scripts/` 指"测 scripts/ 的测试"，但仓内**同类测试散在各处**（`tests/alembic/`、`tests/precommit/`、`tests/pg_exporter/` 都是测 scripts 的）。`tests/scripts/` 只含 1 个 kb_dedup 测试，**这个"分类"名不副实**，打平后与 `test_dedup_kb_duplicates.py` 等兄弟相邻 |

**打平的 basename 冲突复核**：`test_drive_endpoint_envelope.py`、`test_drive_to_kb_endpoints.py`、
`test_kb_dedup_admin_cli_e2e.py` 打平后全库唯一 ✅。

**打平是否触发 `parents[]` 编辑**：实测这 3 个文件**均未使用** `parents[N]` ✅ 零编辑。
**是否触发守门测试 ALLOWLIST**：三者均不在路径 key 中 ✅ 零编辑。

### 2.4 `_archive` 命名冲突：结论是"不存在冲突，但建议统一到 `archived/`"

- 现状：`scripts/_archive/` 存在（5 文件）；`tests/_archive/` **不存在**（§0.5）。
- 本方案**不新建** `tests/_archive/` —— 归档测试**原地保留**（`tests/ARCHIVED.md` 明文：
  "文件**全部保留原位**，只跳过执行"）。把归档文件挪进目录会**破坏恢复流程文档**与 88 个
  文件头的"恢复条件"注释之间的对应关系。
- **一致性建议（低优先，不在本轮批次内）**：仓内已有两处 `archived/` 惯例 ——
  `docs/archived/`、`memory/archived/`。若将来确需物理归档目录，**统一用 `archived/`（无下划线）**，
  弃用 `_archive/`，避免 `_`-前缀与"私有/临时"语义混淆。**本轮不动 `scripts/_archive/`**（改名无收益）。

### 2.5 守门类不得动（重申，批次执行时的硬检查）

- `tests/test_no_prod_db_imports.py` —— 禁止测试直连生产库。**本方案 8 个批次无一触碰它**。
- `tests/e2e/test_anchor_scripts_smoke.py` 与 `tests/integration/test_hnsw_bench_real.py` ——
  因 ALLOWLIST 用**路径 key**（§0.2），**本方案禁止平移这两个文件**。
- 88 个带模块级守卫的文件：允许**移动**，但**必须随文件一起移动文件头的 skip 原因注释**，
  并**同步更新 `tests/ARCHIVED.md`** 的路径列（若该表列了路径）。
- `tests/conftest.py`（452 行，唯一根锚）**原地不动**。5 个子目录 conftest 随目录走。

---

## 3. `scripts/` 详细方案

### 3.1 有观点的结论：**顶层 201 文件保持平铺，不做用途分类**

这是本方案与测绘报告 F 节"批次 2"最大的分歧，理由四条：

1. **分类会撕裂冻结区，产生"半分类"反预测性布局。** 26 个有硬接线的文件搬不动
   （§3.2）。若按用途分类，结果是 `scripts/deploy.sh`（冻结）和 `scripts/ops/deploy-cloud.sh`
   （可搬）并存 —— **看到 `scripts/ops/` 并不意味着"运维脚本都在这"**，直接违背设计原则 #1。
2. **命名已经自解释且可 grep。** `backfill_*`(13) / `migrate_*`(6) / `verify_*`(10) /
   `monitor-*.sh`(6) / `fix_*` / `repair_*` / `cleanup_*`(7) / `purge_*`(4) ——
   前缀即分类，`git grep '^scripts/verify_'` 一次到位。目录分类提供不了额外检索能力。
3. **文档债 136 个文件。** `docs/` 下 136 个文件引用 `scripts/`，`README.md` 有 8 处
   （含 `scripts/run-reprocess.ps1`、`scripts/a46_pptx_page_pipeline.py` 等）。
   搬迁会产生**纯文档 churn**，零功能收益。
4. **收益不对称。** 真正伤害可维护性的不是"平铺"，而是 §3.3 的**会话编号垃圾**。
   把力气花在垃圾上，不是花在分类上。

**替代方案（本轮采纳）**：新建 **`scripts/README.md`** —— 按用途的**索引表** + **冻结清单**，
零路径变更、零引用破坏，却达成"可预测性"的全部实际收益。

### 3.2 原地冻结清单（35 个，逐一列全）

**A. Windows 计划任务硬编码绝对路径（8 个，改名 = 任务静默死亡）**

| 文件 | 计划任务 |
|---|---|
| `scripts/auto-recovery-eventlog.ps1` | `MicroBubble-Auto-Recovery` |
| `scripts/backup_scheduler.bat` | `MicroBubble-Daily-Backup` |
| `scripts/backup_db.sh` | ← `backup_scheduler.bat:44` 绝对路径调用 |
| `scripts/start_gpu_asr_daemon.bat` | `MicroBubble-GPU-ASR-Daemon` |
| `scripts/run-hidden.vbs` | `MicroBubble-SSH-Tunnel-Guard` |
| `scripts/tunnel/guard-ssh-tunnel.ps1` | ← 上一条的 Arguments |
| `scripts/tunnel/guard-ssh-tunnel.bat` | ← `install-tunnel-guard.bat` 注册进任务 |
| `scripts/tunnel/install-tunnel-guard.bat` | 重新注册任务（改动需重注册） |

**B. pre-commit 引用（7 个，改错 = 阻断所有开发者 commit）**

`scripts/setup-hooks.sh`（`:5,:13`）、`scripts/gitleaks/scan-history.sh`（`:34,:36`）、
`scripts/check-secrets-before-commit.sh`（`:36`）、`scripts/trivy/check_pinned_images.py`（`:50`）、
`scripts/alembic/check_single_head.sh`（`:63`，**且被 `tests/alembic/` 引用**）、
`scripts/check_typing_imports.sh`（`:72,:76`，CLAUDE.md 铁律 2）、
`scripts/web/check_dist_manifest.sh`（`:89`）

**C. CI workflow 引用（9 个）**

`scripts/init_test_db_all.py`（`build-image.yml` + `playwright.yml` + **`docker-compose.test.yml:79`**）、
`scripts/init_db.py`（`playwright.yml` + `qa-bench-smoke.yml`）、
`scripts/ensure_test_user.py`（`playwright.yml` + `qa-bench-smoke.yml`）、
`scripts/benchmark_fast_vs_deep.py`（`qa-bench-smoke.yml`）、
`scripts/ci_qa_bench_baseline.sh`（`qa-bench-baseline.yml`）、
`scripts/check-design-tokens-drift.sh` / `check-token-orphans.sh` /
`frontend-size-budget-check.sh` + `frontend-size-budget.txt` / `sync-design-tokens.sh`
（均 `lint-css.yml`）

**D. 跨顶层目录耦合（3 个，`web/package.json` → `../scripts/k6/`）**

`scripts/k6/chat_stream.js` `scripts/k6/ws_notifications.js` `scripts/k6/drive_collab.js`

**处置决策**：**原地不动**。理由 —— k6 压测脚本同时被 `web/package.json` 的 `load:*` 脚本和
`tests/k6/test_scripts_exist.py` 消费；把它移进 `web/` 会让压测脚本依赖前端构建产物树，
把它移进别的目录只会多一处跨顶层耦合。**它已经是独立子目录，可预测性已满足。**
（唯一可选改进：把 `web/package.json` 的 `../scripts/k6/` 改成绝对/包内路径 —— 但这需要
在 `web/` 下放副本或建包，属**独立议题**，本轮不做。）

**E. 自身写死绝对路径者（自冻结，动了自伤）**

`scripts/local-watchdog.ps1`、`scripts/cron_sync_sequences.sh`、`scripts/backup_minio_daily.py`、
`scripts/register_avatar_defenses.ps1`、`scripts/upload_avatars_v2.py`、
`scripts/export_avatars_zip.py`、`scripts/cleanup_voiceprint_embeddings_2026-09-07.py`、
`scripts/notify-templates/claude-voice-alert-*.ps1`（6 个）

**合计 8 + 7 + 9 + 3 + 8 = 35 个原地冻结。**

### 3.3 会话编号垃圾：`aXX_*` 15 个文件（批次 4 的全部内容）

```
scripts/a43_pptx_page_analyse.py        scripts/a44_find_probe_terms.py
scripts/a43_pptx_page_pipeline.py       scripts/a44_ingest_page_transcripts.py
scripts/a43_pptx_page_recon.py          scripts/a44_page_transcript_dryrun.py
scripts/a44_verify_e2e_semantic.py      scripts/a44_verify_probe_rank.py
scripts/a44_verify_retrieval.py         scripts/a44_verify_semantic.py
scripts/a45_verify_lexical_probe.py     scripts/a46_ingest_page_transcripts.py
scripts/a46_pptx_page_pipeline.py       scripts/a46_verify_e2e.py
scripts/a47_pptx_page_pipeline_band.py
```

**取证**：`git grep` 全仓（除 `scripts/` 自身）引用数 **0**（逐一验过 a43/a44/a45/a46/a47 各样本）。
**这是与 `tests/` 的 `_xNN` 完全同型的命名债** —— `git grep a4` 会命中 15 个文件，
而其中没有一个 `aXX` 是有语义的类别。

**⚠️ 一个反对意见（必须让主指挥知道）**：CLAUDE.md 现状段 C 把 PPT 图片入 RAG 描述为
**已投喂的活链路**（2495 行入库、3 条新基础设施），而 `a46_pptx_page_pipeline.py` 正是那条链路的
执行体；`README.md:238` 也在教用户跑
`docker exec -d microbubble-agent-app-1 python scripts/a46_pptx_page_pipeline.py --resume-from N`。
**把它们与"一次性验收探针"一起扫进 `_archive/` 是误导** —— 归档目录的语义是"不再使用"。

**修正后的处置（分两堆，批次 4）**：

| 堆 | 文件 | 归宿 | 理由 |
|---|---|---|---|
| **可重跑的链路组件**（4） | `a46_pptx_page_pipeline.py`、`a46_ingest_page_transcripts.py`、`a43_pptx_page_pipeline.py`、`a47_pptx_page_pipeline_band.py` | **`scripts/ppt_pages/`** | CLAUDE.md C 段记载的活链路；README 教用户直接调用。给它们一个**语义名**，比留 `a46_` 前缀或扫进归档都强 |
| **一次性验证探针**（11） | 其余 `a43_*`/`a44_*`/`a45_*`/`a46_verify_e2e.py` | **`scripts/_archive/a44-verify-probes/`、`a45/`** | 逐次验证"这批数据召回行不行"的探针，跑完使命结束。按会话号分子目录归档（文件名已有 `aXX_` 前缀，目录不必再加） |

`a44_ingest_page_transcripts.py` 归入 ppt_pages（它是 ingest 步骤，不是探针）。
**最终 `scripts/ppt_pages/` = 5 文件**：`a43_pptx_page_pipeline.py`、`a46_pptx_page_pipeline.py`、
`a47_pptx_page_pipeline_band.py`、`a44_ingest_page_transcripts.py`、`a46_ingest_page_transcripts.py`。

⚠️ **README:238 的路径需同步改**（`scripts/a46_...` → `scripts/ppt_pages/a46_...`）。
`git grep -l 'a4[3-7]_' -- README.md docs/` 实测 **1 个文件**（README.md）命中 → 文档债极小。

### 3.4 15 个子目录：保留 / 归位 逐个

| 子目录 | 文件 | 决定 | 理由 |
|---|---|---|---|
| `qa-bench/` | 7 | **保留** | 与 `tests/qa-bench/` 呼应；CI 消费 `gate.py` 等 |
| `rag/` | 6 | **保留** | `check_*.sh` / `verify_*.sh` —— 但注意顶层有同名 `verify_alembic_chain.sh`、`verify_dispatch_claim.sh`（**重复**，见 §3.5） |
| `k6/` | 5 | 🔴 **冻结** | §3.2 D |
| `tunnel/` | 4 | 🔴 **冻结** | §3.2 A |
| `trivy/` | 3 | **保留** | §3.2 B 冻结 |
| `pg-exporter/` | 3 | **保留** | 被 `tests/pg_exporter/` 引用 |
| `notify-templates/` | 7 | **保留** | 6 个 ps1 写死自身绝对路径（§3.2 E） |
| `gitleaks/` `web/` `lib/` `alembic/` | 各 1 | **保留** | B 类冻结 / 已被 `scripts/lib/webhook_payload.sh` 引用 |
| `voiceprint/` | 2 | **保留** | `replay_meeting_151.py` 是 CLAUDE.md 声纹 90% 铁律的锚点 |
| `_archive/` | 5 | **保留**（+ 批次 4 新增） | §2.4 |

**结论：`scripts/` 15 个子目录全部保留，本轮不新建除 `ppt_pages/` 与 `_archive/aXX*/` 外的任何目录。**

### 3.5 `tunnel/` 与 `scripts/tunnel/`：有观点的结论 —— **本轮不合并**

测绘报告批次 3 建议合并。**我反对**，理由：

- 二者语义**互补而非重复**：顶层 `tunnel/`（`start-ssh-tunnel.ps1/.vbs`、`setup-ssh-key.ps1`）= **建**隧道；
  `scripts/tunnel/`（`guard-ssh-tunnel.*`、`install/uninstall-*.bat`）= **守护 + 注册计划任务**。
- 合并必然要动 `install-tunnel-guard.bat:4` 里那条 `New-ScheduledTaskAction -Execute 'E:\...\scripts\tunnel\guard-ssh-tunnel.bat'`
  并**重新注册计划任务**。而 CLAUDE.md **类 20.216** 明确记载：heredoc 写 `schtasks` 反斜杠路径
  曾两次腐坏成控制字符（`scripts\tunnel` → `scripts<TAB>unnel`），**任务永远 exit 1 且日志一行不写**。
- 收益（4 个文件归堆）远小于风险（SSH 隧道守护 = 全站可用性，类 20.214 列为生产单点）。
- `guard-ssh-tunnel.ps1:10` 只是**注释**里提到 `tunnel/start-ssh-tunnel.ps1`，非代码引用。

**处置：原地保留两个目录，仅在 `scripts/README.md` 里写清"建隧道 vs 守护隧道"的分工。**
若主指挥坚持合并，列为 §5 决策点 D4，且**必须先修类 20.216 的注册脚本**再动手。

### 3.6 已知坏引用：本轮修 1 个，不修 1 个

| 坏引用 | 实测 | 本轮处置 |
|---|---|---|
| `scripts/register_avatar_defenses.ps1:36` → `E:\...\scripts\check_orphan_avatars.py --alert` | **文件不存在**（`git ls-files` 0 命中，磁盘亦无）→ 该 ps1 注册计划任务时**必然失败** | ✅ **修**（批次 5）：删除第 36 行这个已不存在的任务注册，或替换为现存脚本。**需主指挥确认该任务是"该删"还是"该补脚本"** |
| `restart_gpu_workers.bat` → `.workbuddy\vibevoice-test` | **已被修好，但修复未 commit**（§0.3，`git status` 仍为 ` M`） | ❌ **不修** —— 动了会把正确值改回错误值。但**须单独提交该浮动修复**（见 §0.3） |
| `app/services/tts_mainplay_pipeline.py:475` → `scripts/monitor-edge-tts.sh` | **文件不存在**，但该处是 **docstring 注释**（"监控快照 (scripts/monitor-edge-tts.sh 消费)"），非执行引用 | ⚪ **不修**（低优先）：改注释即可，无功能影响。列入 §5 待办 |
| `scripts/qa_bench_smoke.py:401` → `scripts/compare_reranker_rounds_v2.py` | **文件不存在**，是一行 `print()` 提示文本 | ⚪ **不修**（低优先）：同上，纯提示串 |

---

## 4. 分批迁移方案

> 通用规则（每批都适用，不再重复）：
> - **一批 = 一个 commit**。回滚：未 push 用 `git reset --hard <prev-sha>`；已 push 用 `git revert --no-edit <sha>`。
> - **一律用 `git mv`**，不用裸 `mv`（保证 git 感知为 rename）。
> - 每批**必须**先跑"批前基线"命令存档数字，批后跑同一命令对比。
> - **零 docker 操作**。所有批次都不需要重启服务、不影响运行中的容器。
> - 批次之间**独立可验证**，可单独 cherry-pick 或放弃。

### 批前基线命令（批次 1-4 通用，务必先存档）

```bash
# B1 预跑一次，记录数字
mkdir -p /tmp/mbbase
git ls-files tests/ > /tmp/mbbase/tests_files_before.txt
find tests -name "test_*.py" | sort > /tmp/mbbase/collect_before.txt
wc -l < /tmp/mbbase/collect_before.txt          # 期望 400（实测 §0.4 口径）
find tests -name "test_*.py" | sed 's|.*/||' | sort | uniq -d > /tmp/mbbase/dup_before.txt
wc -l < /tmp/mbbase/dup_before.txt              # 期望 1（test_intent_classifier.py）
python -m pytest tests/test_no_prod_db_imports.py -q     # 守门测试，必须绿
```

### 批次 1 —— `tests/` 9 个会话目录归位 🟢

| 项 | 内容 |
|---|---|
| **目标一句话** | 消灭 `tests/` 里全部 9 个 `_xNN` 会话编号目录，让"看目录名就知道测什么"成立 |
| **文件清单** | `a11y_login_x18/`+`baseline_sync_x29/`+`a11y_violation_x2/`+`axe_violation_x19/`+`inject_auth_x4/` → `tests/a11y/`（5 文件）<br>`ci_real_x29/` → `tests/realenv/`（2 文件，含 `__init__.py`）<br>`icon_wr1/`+`src_tests_x5/` → `tests/dist_health/`（2 文件）<br>`brief_v41_x6/test_doc_exists.py` → `tests/test_brief_v41_x6_doc_exists.py`（改名 + 打平） |
| **必须同步改的引用** | **无**。同深度改名（§0.1）→ 29 个 `parents[2]` 天然免疫；无文件被本批触及 ALLOWLIST 路径 key（§0.2）；无 CI 引用这 9 个目录 |
| **验证** | ① `find tests -name "test_*.py" \| wc -l` 前后**均为 400**<br>② basename 冲突：前后 `uniq -d` 均只有 `test_intent_classifier.py`<br>③ `python -m pytest tests/a11y tests/dist_health tests/realenv tests/test_brief_v41_x6_doc_exists.py -q`（预期大量 skipped，归档文件跳过后正常）<br>④ `python -m pytest tests/test_no_prod_db_imports.py -q` **必须绿**<br>⑤ CI 等价分片：`find tests -name "test_*.py" \| sort \| awk -v N=8 '{print > (".pytest-chunks/chunk-" (NR % N) ".txt")}'` 后确认 8 片文件数之和 = 400<br>⑥ `git ls-files tests/ \| grep '_x[0-9]'` 应**无输出** |
| **回滚** | `git reset --hard <batch1-base-sha>`（未 push）/ `git revert` |
| **风险** | 🟢 **低**。唯一实质风险是 `a11y/` 内 5 文件若有 basename 冲突 —— 已逐一核对无冲突 |
| **影响面** | **无**。不动 CI、不动 compose、不重启任何服务。分片命令路径无关，8 片内容变化但总数不变 |

### 批次 2 —— `tests/` 三处打平，消除唯一深度违规 🟡

| 项 | 内容 |
|---|---|
| **目标一句话** | 把 `tests/api/v1/`（深度 3、违反两层约束、2 个 drive 孤儿）和 `tests/scripts/`（名不副实的 1 文件分类）打平归队 |
| **文件清单** | `tests/api/v1/test_drive_endpoint_envelope.py` → `tests/`<br>`tests/api/v1/test_drive_to_kb_endpoints.py` → `tests/`<br>`tests/scripts/test_kb_dedup_admin_cli_e2e.py` → `tests/`（删空 `tests/api/`、`tests/api/v1/`、`tests/scripts/`） |
| **必须同步改的引用** | **无**。实测这 3 个文件**均未使用** `parents[N]`；不在守门测试 ALLOWLIST 任何 key 中；无 CI/workflow 引用 `tests/api/` 或 `tests/scripts/` |
| **验证** | ① `find tests -name "test_*.py" \| wc -l` = **400**（不变）<br>② basename 冲突 `uniq -d` 仍只有 1 组<br>③ `python -m pytest tests/test_drive_endpoint_envelope.py tests/test_drive_to_kb_endpoints.py tests/test_kb_dedup_admin_cli_e2e.py -q`<br>④ `python -m pytest tests/test_no_prod_db_imports.py -q` 绿<br>⑤ `git ls-files tests/ \| awk -F/ '{print NF}' \| sort -u` 确认最大深度 ≤ 3（仅 `tests/qa-bench/<sub>/` 与 `tests/e2e/rag/` 合法存在） |
| **回滚** | 同批次 1 |
| **风险** | 🟡 **中低**。风险点是"以为没人引 `tests/api/`"—— 故批前必须跑 `git grep -n "tests/api\|tests/scripts"` 确认无引用（批前检查项，不是批后） |
| **影响面** | **无**。纯路径平移，无运行时代码改动 |

### 批次 3 —— `tests/eval/rag_prompt_meta.test.py`：条件启用 ⚠️

| 项 | 内容 |
|---|---|
| **目标一句话** | 修一个**静默失效**：该文件 3 个测试函数从未被 pytest 收集过（§0.4） |
| **批前强制检查** | `python -m pytest tests/eval/rag_prompt_meta.test.py -q --collect-only` → 确认收集到 **0** 项（复现失效）<br>然后 `python -m pytest tests/eval/rag_prompt_meta.test.py -q -p no:cacheprovider --co -q` 人工指定收集；或直接 `python -m pytest --override-ini="python_files=*.test.py" tests/eval/ -q` 看**真实断言是否通过** |
| **文件清单（仅当上一步全绿）** | `tests/eval/rag_prompt_meta.test.py` → `tests/eval/test_rag_prompt_meta.py`；删空 `tests/eval/` |
| **必须同步改的引用** | 无 |
| **验证** | `python -m pytest tests/eval/ -q` → **collected 3 项**（对比批前 0 项）；`find tests -name "test_*.py" \| wc -l` 由 **400 → 401**（+1 是预期，**必须对上**，对不上说明收集口径理解有误） |
| **回滚** | 若断言**红** → **放弃本批**（不改名，保持现状），把失败详情记入 §5 待办交主指挥。**本批是全部 7 批中唯一允许"不做"的** |
| **风险** | ⚠️ **需裁定**。风险不在改名，在于**一旦被收集就可能立刻红**，把一个"隐形文件"变成"CI 红灯"。故设计为**条件执行** |
| **影响面** | 若启用，CI 用例数 +3；不重启任何服务 |

### 批次 4 —— `scripts/` 会话编号垃圾清理 🟡

| 项 | 内容 |
|---|---|
| **目标一句话** | 把 15 个 `aXX_*` 分成"活链路组件"和"一次性探针"两堆，前者给语义目录名，后者归档 |
| **文件清单 A（5 → `scripts/ppt_pages/`）** | `a43_pptx_page_pipeline.py`、`a46_pptx_page_pipeline.py`、`a47_pptx_page_pipeline_band.py`、`a44_ingest_page_transcripts.py`、`a46_ingest_page_transcripts.py` |
| **文件清单 B（10 → `scripts/_archive/`）** | `a43_pptx_page_analyse.py`、`a43_pptx_page_recon.py`、`a44_find_probe_terms.py`、`a44_page_transcript_dryrun.py`、`a44_verify_e2e_semantic.py`、`a44_verify_probe_rank.py`、`a44_verify_retrieval.py`、`a44_verify_semantic.py`、`a45_verify_lexical_probe.py`、`a46_verify_e2e.py`（`git mv` 到 `scripts/_archive/`，**保留原文件名**） |
| **必须同步改的引用** | `README.md:238` —— `python scripts/a46_pptx_page_pipeline.py` → `python scripts/ppt_pages/a46_pptx_page_pipeline.py`（实测 `git grep -l 'a4[3-7]_' -- README.md docs/` 仅 1 文件命中） |
| **验证** | ① `git grep -l "a4[3-7]_" -- README.md docs/ CLAUDE.md` → 改后**仅剩归档目录内的自引用**，无外部指向旧路径<br>② `git grep -rn "scripts/a4[3-7]_" -- . ':!docs/archived/'` → **0 命中**（旧路径零残留）<br>③ `python -c "import ast,sys;[ast.parse(open(f).read()) for f in ['scripts/ppt_pages/a46_pptx_page_pipeline.py']]"` → 语法 OK<br>④ **不改任何 CI/pre-commit/compose** → `git diff --name-only` 应**不含** `.github/`、`.pre-commit-config.yaml`、`docker-compose*.yml`<br>⑤ 跑一遍 ppt_pages 里任一脚本的 `--help`（若支持 argparse；类 20.155/20.156：须显式 `PYTHONPATH=<repo root>` 且 `capture_output=True`）确认模块级 import 未因换目录而断 |
| **回滚** | 同批次 1 |
| **风险** | 🟡 **中**。① 脚本内部可能有**相对路径假设**（`Path(__file__).parent`）—— 移入 `ppt_pages/` 后多了一层，**必须逐个 grep `__file__`**；② `a44_ingest_page_transcripts.py` 与 `a46_ingest_page_transcripts.py` 名字相近，**移动后极易混淆**，建议在 `ppt_pages/` 加一行 `README.md` 说明各自产出 |
| **影响面** | **无**。这 15 个文件零 CI/计划任务引用；已实测 |

### 批次 5 —— 修既有坏引用 + 补冻结清单文档 🟢

| 项 | 内容 |
|---|---|
| **目标一句话** | 修一个"必然失败"的任务注册脚本，并产出让后来者不会误杀冻结文件的两份索引文档 |
| **文件清单** | ① `scripts/register_avatar_defenses.ps1` —— 删除（或替换）第 36 行对不存在的 `check_orphan_avatars.py` 的任务注册<br>② **新建** `scripts/README.md` —— 按用途的索引 + **§3.2 的 35 个冻结文件表**<br>③ **新建** `tests/STRUCTURE.md` —— 子目录职责表 + "两条硬规则"（两层深度 / 禁动 ALLOWLIST 路径 key 文件） |
| **必须同步改的引用** | 无 |
| **验证** | ① 用 PowerShell 语法检查器解析 `register_avatar_defenses.ps1` 无错<br>② `git grep -n "check_orphan_avatars"` → **0 命中**（坏引用清除）<br>③ 全文回读两份新文档里的每个冻结路径，`test -f` 逐个确认存在<br>④ `python -m pytest tests/ -q --collect-only 2>&1 \| tail -3` → collected 数不变 |
| **回滚** | 同批次 1 |
| **风险** | 🟢 **低**。唯一判断点是 `check_orphan_avatars.py` 该"删任务"还是"补脚本" —— 若主指挥选后者，本批扩为"重写该脚本"，风险升到 🟡 |
| **影响面** | **无**。`register_avatar_defenses.ps1` 不在 4 个活计划任务中（活的是 Auto-Recovery / Daily-Backup / GPU-ASR / SSH-Tunnel-Guard），改动不影响任何正在运行的任务 |

### 批次 6 —— 孤儿目录归位（低优先，可单独否决） 🟢

| 项 | 内容 |
|---|---|
| **目标一句话** | 把 compose 完全不引用的 Grafana provisioning 归到已有的 `docker/` 下（**不新建顶层目录**） |
| **文件清单** | `observability/`（10 文件）→ `docker/observability/` |
| **必须同步改的引用** | 无（实测 compose 无 grafana/prometheus/observability 服务引用）。**批前仍须跑** `git grep -rn "observability/" -- . ':!docs/archived/' ':!observability/'` 确认 |
| **验证** | ① `docker compose config --services \| grep -i "grafana\|observability"` → 前后均**无输出**（证明确实无接线）<br>② `docker compose config` 退出码 0<br>③ `git diff --name-only` 不含任何 `docker-compose*.yml`（类 20.215 纪律：本批**不改** compose） |
| **回滚** | 同批次 1 |
| **风险** | 🟢 **低**。但**收益也低** —— 10 个文件换个位置而已。若主指挥觉得不值得，**整批否决无损失** |
| **影响面** | **无**。不重启容器、不改 mount |

### 批次 7 —— 收尾验收 🟢

| 项 | 内容 |
|---|---|
| **目标一句话** | 全链路验证前 6 批的合并效果，并把新结构写进 CLAUDE.md / README |
| **文件清单** | `CLAUDE.md`（新增"目录结构约定"小节：两层深度铁律 + 冻结清单）、`README.md`（文件树同步） |
| **验证（必须全绿）** | ① `git status` 干净<br>② 收集数 `find tests -name "test_*.py" \| wc -l` = 400（+1 若批次 3 启用 = 401）<br>③ `python -m pytest tests/test_no_prod_db_imports.py -q` 绿<br>④ 8 片分片数之和与 ② 一致<br>⑤ `schtasks /query /tn MicroBubble-Auto-Recovery /xml`、`...Daily-Backup`、`...GPU-ASR-Daemon`、`...SSH-Tunnel-Guard` —— **逐字节回读 Execute/Arguments 比对批前值**（类 20.216/20.220）<br>⑥ 手动触发 `MicroBubble-Auto-Recovery`，**查 `logs/` 下当日日志文件是否新增行**（类 20.220：**不信 `LastTaskResult`**）<br>⑦ `docker compose config` 退出码 0；`docker inspect -f '{{range .Mounts}}{{.Source}} -> {{.Destination}}{{"\n"}}{{end}}' microbubble-agent-app-1` 与批前一致<br>⑧ `docker ps` 容器数与批前一致（**本方案全程零 docker 操作，这是"没碰过"的证据**） |
| **回滚** | 按批回滚 |
| **风险** | 🟢 低（纯文档） |
| **影响面** | 无 |

### 批次总表

| 批 | 目标 | 风险 | 验证方式 | 可否否决 |
|---|---|---|---|---|
| **0** | 基线取证（跑批前基线命令并存档） | 🟢 无 | 收集数=400 / 冲突组=1 / 守门测试绿 | — |
| **1** | `tests/` 9 个 `_xNN` 归位 | 🟢 | 收集数不变 + 守门绿 + `grep _x[0-9]` 空 | 否 |
| **2** | `tests/` 3 处打平（消除深度 3 违规） | 🟡 | 收集数不变 + 逐文件跑 | 否 |
| **3** | 修 `*.test.py` 静默失效 | ⚠️ 需裁定 | collected 0 → 3 | **可（唯一允许不做）** |
| **4** | `scripts/` 15 个 `aXX_*` 清理 | 🟡 | 旧路径 0 残留 + README 同步 | 否 |
| **5** | 修坏引用 + 2 份索引文档 | 🟢 | 坏引用 0 命中 + 冻结路径逐个存在 | 否 |
| **6** | `observability/` → `docker/` | 🟢 | compose services 无 grafana | **可** |
| **7** | 全链路验收 + CLAUDE.md/README | 🟢 | 8 项清单全绿 | 否 |

**合计 8 批**（含批 0）。**高风险批次不存在** —— 这是刻意的：本方案把全部高风险操作
（`web/`、`apps/`、`desktop-conversion/`、`tunnel/` 合并、`commercial/` 归位）**全部排除在外**。

---

## 5. 遗留、决策点与"不做的事"

### 5.1 本轮明确**不做**

| 不做的事 | 理由 |
|---|---|
| `web/` / `apps/` / `packages/` 任何结构调整 | **类 20.133**：改源码输入会改 `BUILD_ID`（源输入清单 sha256），需"先提交源码 → 再 build → 再提 dist"的原子顺序，否则入库 dist 不可逐字节复现。**风险收益比全项目最差** |
| `tunnel/` 与 `scripts/tunnel/` 合并 | §3.4：需重注册计划任务，撞类 20.216 已知坑 |
| `commercial/` 并入 `app/` | 它是 `docker/Dockerfile.commercial` 的 build context（部署单元边界），**不是** FastAPI 应用的一部分，合并语义上错 |
| `scripts/` 顶层 201 文件用途分类 | §3.1：收益为负 |
| `results/` 归档迁移 | 65 文件 4.9M 零引用，移不移动都不影响任何人 |
| `docs/` `memory/` 内部整理 | 🟢 零风险但也零收益，且 `docs/` 有 654 文件的交叉引用 |
| 移动 88 个带守卫的归档测试 | `tests/ARCHIVED.md` 明文要求原地保留；移动会破坏恢复流程与文件头注释的对应 |
| 改 `web/package.json` 的 `../scripts/k6/` | 需在 `web/` 建副本或建包，属独立议题 |
| 补 `scripts/monitor-edge-tts.sh` / `compare_reranker_rounds_v2.py` | 两处引用均在注释/`print()` 里，无功能影响（§3.6） |

### 5.2 将来可能做（不在本轮）

- `scripts/rag/` 与顶层 `verify_alembic_chain.sh` / `verify_dispatch_claim.sh` **同名重复** ——
  实测 `scripts/rag/` 内已有这两个文件，顶层又有同名副本。**去重前必须先确认哪份是活的**
  （`verify_alembic_chain.sh` 被 `rag-framework-ci.yml` 引用？未验证）。
- `scripts/` 内部 5 个 SQL 文件（`orphan_chunk_audit.sql` 等）可归 `scripts/sql/`。
- `tests/api/v1/` 打平后（批次 2），`tests/request_context/` 等 4 文件目录是否也该打平 —— 本轮认为不必。

### 5.3 ⚠️ 需主指挥拍板的决策点

| # | 决策点 | 选项 | 我的建议 | 不决策的后果 |
|---|---|---|---|---|
| **D1** | `config/intent_routing.yaml`（1 文件，**全仓零引用**） | ① 接线（找出本该消费它的代码）② 删除 ③ 原地保留 | **请裁定接线还是删除**。我倾向**删除**——一个零引用的意图路由配置，要么是接线漏了（那是 bug），要么是死配置。**移动它是最差的第三选项**（把死代码搬个家，还制造 diff） | 继续留一个"看起来在配置、实际不生效"的意图路由 |
| **D2** | `desktop-conversion/`（193 commits + 私有远端，**不在主仓 git ls-files**） | ① 合并进主仓 ② 保持独立 ③ 子模块化（需 `.gitmodules`，当前**没有**） | **保持独立 + 本轮显式排除**。合并是**独立的工程决策**（涉及 126+ commits 历史、文档双向引用、主仓体积），不该搭车在目录重构里。但**必须补一份"主仓 ↔ desktop-conversion 文档交叉引用表"**（CLAUDE.md 反复引用其文档） | 未来任何 `git ls-files` 驱动的批量脚本会**静默跳过它**，误以为已处理 |
| **D3** | `tests/eval/rag_prompt_meta.test.py` 是否**有意**排除 | ① 有意排除（那要在文件头写明理由，类 20.220）② 无意（则批次 3 启用） | **先跑断言**。若绿 → 无意，启用；若红 → 有意排除，补文件头注释说明 | 继续留一个"3 个测试函数从未执行过"的文件 |
| **D4** | `tunnel/` + `scripts/tunnel/` 是否合并 | ① 不合并（本方案）② 合并 | **不合并**。若坚持合并，**必须先修类 20.216 的注册脚本**（heredoc 反斜杠腐坏前科 2 次），并在合并后**手动触发任务 + 查 `logs/tunnel-guard.log` 是否新增行** | 维持现状（可接受，但两目录语义分工需要文档化） |
| **D5** | `register_avatar_defenses.ps1` 的 `check_orphan_avatars.py` | ① 删掉这个任务注册 ② 补写该脚本 | **删掉**。脚本不存在 = 该任务当前**必然失败**；且 `backup_minio_daily.py` 已在第 11 行单独注册，孤儿头像检查的业务价值已随功能下线而消失 | 保持一个"注册即失败"的 ps1，下次有人跑还会再踩 |
| **D6** | 批次 6（`observability/` → `docker/`）是否做 | ① 做 ② 否决 | **可做可不做**，收益低。若做，顺带把 `config/` 与 `results/` 一并裁定（§D1） | 孤儿目录继续躺在顶层 |

### 5.4 风险最高的一批

**批次 4（`scripts/` 会话编号清理）是全方案风险最高的一批**，理由：

1. **唯一会移动"有业务含义的活链路"文件的批次。** 前 3 批动的都是测试，且归档件占多数；
   批次 4 动的 `a46_pptx_page_pipeline.py` 是 CLAUDE.md 现状段 C 记载的**已投喂活链路**执行体，
   且 `README.md:238` 正教用户调用它。
2. **换目录会改 `Path(__file__).parent` 的层级。** 这 15 个脚本实测**未被 CI 引用**，
   意味着**它们在 CI 里完全没有回归网** —— 移错了不会变红，只会在下次人工使用时才炸。
   这是最危险的失败模式：**静默**。（迁移前必须逐个 `git grep -n "__file__" -- scripts/a4*/`）
3. **它同时改了归档语义。** 把仍在用的链路脚本放进 `_archive/` 是误导，故我拆成"活链路 → `ppt_pages/`"
   与"探针 → `_archive/`"两堆 —— 这增加了分类判断的复杂度，也增加了判断出错的机会。
4. **文档债虽小但真实。** README 的用户可见指令路径变了，漏改 = 用户照抄命令报"文件不存在"。

**若主指挥只想做一批，做批次 1** —— 它零 `parents[]` 编辑、零 CI 引用、零文档债，
却消灭了 `tests/` 里 100% 的会话编号命名债，收益/风险比最高。

### 5.5 不确定的地方（如实说明）

1. **CI 全绿结论仍是静态分析。** 与测绘报告同样的局限：我**没有执行任何测试**（无 DB、
   未起容器、本任务禁止碰 docker）。批次 1-4 的"验证方式"是**设计给执行者跑的**，不是
   我实测跑过的。`find tests -name "test_*.py" | wc -l` = 400 是我用 git 索引文件复现
   CI 命令得到的，与 CI 实际收集数是否一致，取决于容器内是否有 git 索引外的文件。
2. **`scripts/aXX_*` 内部是否用了 `__file__` 相对路径，我只做了 grep 存在性检查的准备，
   未逐个读完 15 个文件。** 批次 4 的风险评估基于"未被任何 CI/任务引用"这一取证，
   而非逐行审读。若执行者时间允许，批次 4 应先读这 15 个文件。
3. **`scripts/rag/verify_alembic_chain.sh` 与顶层同名文件，哪份是活的未验证。**
   这可能又是一处"看似重复实为互补"（类 20.212）。我在 §5.2 明确标为**待查**，未下结论。
4. **`tests/ARCHIVED.md` 的清单是否列了路径**未逐行核对。若列了，批次 1-2 移动的 8 个归档
   文件需同步更新该表。这属于执行时的检查项。
5. **`apps/desktop/`（213 文件）内部结构未评估。** 测绘已确认它不在 `scripts/` 顶层且被
   `working-directory: apps/desktop` 消费，故本方案**整体排除**——但我没有评估它内部
   是否同样混乱。**若主指挥想继续往下推，`apps/desktop/scripts/` 是下一个测绘对象**
   （注意：按字符串 `scripts/` 匹配会**误伤**它，见测绘 E3）。
6. **`docs/` 654 文件的交叉引用未穷举。** 批次 1-4 的文档债我用了 `git grep` 定向核查，
   但不能保证 `docs/archived/` 之外没有遗漏的旧路径提及。批次 7 的收尾 grep 应扩大到全仓。

---

## 附录：本方案与测绘报告的分歧汇总

| 项 | 测绘报告 | 本方案 | 理由 |
|---|---|---|---|
| 9 个 `_xNN` 归位需改 `parents[2]`→`parents[3]` | 是 | **否** | §0.1：同深度改名语义不变，零编辑 |
| `scripts/` 顶层按用途分类（批次 2） | 是 | **否** | §3.1：26 文件冻结会造成"半分类"反预测布局 + 136 文件文档 churn |
| `tunnel/` + `scripts/tunnel/` 合并（批次 3） | 是 | **否** | §3.4：需重注册计划任务，撞类 20.216 |
| `commercial/` 并入 `app/` | 待定 | **否，保留** | 它是 Dockerfile build context，不是应用代码 |
| `aXX_*` 15 个全部归档 | 是 | **否，拆两堆** | §3.3：其中 5 个是活链路执行体，README 教用户调用 |
| `restart_gpu_workers.bat` 路径待修 | 是 | **否，工作区已修（但未 commit）** | §0.3 |
| `tests/eval/` 文件 | 未提及 | **条件启用** | §0.4：3 个测试函数从未被收集 |
| 守门测试 ALLOWLIST 路径敏感性 | 未提及 | **列为禁动区** | §0.2 |
