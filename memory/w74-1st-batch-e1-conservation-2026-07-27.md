# W74 第 1 批 E-1 守恒验证 5 件套 (2026-07-27)

> **一句话**: 5 件套 3 PASS / 2 FAIL。派工书 4 项前提与 main 实测不符。发现 1 P0
> (生产容器 alembic 已崩溃) + 3 P1 + 1 P2。0 production code, 锚点 0 增量。

**验证基准**: main `45de56f3b` + B-1 分支 `aef117b17`
**完整报告**: [`docs/w74-1st-batch-e1-conservation-verification-2026-07-27.md`](../docs/w74-1st-batch-e1-conservation-verification-2026-07-27.md)

---

## 派工前提 4 项校正 (真验证优先于承接叙述)

| 派工书 | 实测 |
|-------|------|
| main HEAD = `999276dda` | **`45de56f3b`**; `999276dda` 非 main 祖先 |
| 锚点基线 242 已收口 | W73 第 1 批 **7 分支全部未合并 main** |
| 链 `...→083→084→085` | main head = `080_drive_chunked_uploads`; **077/085 不存在**; 078/079 编号倒挂 |
| B-2 已产出 085 + `app/services/billing/` | **B-2 无分支**; 该目录不存在 |

W74 第 1 批实际开工仅 3: B-1 (`aef117b17`) + D-1 (0 commit) + E-1 (本任务)。
A-1 / A-2 / C-1 / B-2 无分支。

---

## 5 件套

| # | 项 | 结果 |
|---|---|------|
| 1 | alembic 1 head | ✅ main `['080_...']` / B-1 `['084_...']` 单头 |
| 2 | baseline | ❌ **58 errors** (非 W73 报的 0), 元凶 `3b1eb0834` W72 C-3 |
| 3 | PWA 410 | ⚠️ nginx 双 block 410 PASS + sw.js 无 unhashed PASS; dist 无 manifest 不可全验 |
| 4 | 0 production code | ⚠️ 守恒成立但**分母不足**, 不能宣告 6/7 |
| 5 | anchor 242→242 | ❌ **基线 242 未落地 main**, 不可验证 |

## 3 新增段

- **B-2 计费真支付 mock**: ❌ 未开工。但 W73 B-1 `app/services/billing_gateway.py` 已覆盖
  接口骨架, ✅ **"仅 mock" 纪律 PASS** — Stripe/Alipay/WeChatPay 3 类全 `NotImplementedError`
  ("reserved for W76+"), Mock 用 `secrets.token_hex` + 不可路由 `mock.billing.local`, 0 资金风险
- **9 表索引**: ❌ **2 P1, 迁移必失败** (见下)
- **声纹 ≠ 生产**: ✅ PASS — A-2 `a2243a650` 仅 `docs/` + `memory/` 2 文件 708 行, 0 production code

---

## 🔴 P0: 生产 app 容器 alembic 当前已崩溃 (非派工项, 实测偶得)

```
KeyError: '083_commercial_tenant_isolation'   ← alembic current / upgrade 全崩
```

**根因**: 容器内被 cp 了 `084_*.py` (down_revision 指 083) 但 **083 没 cp**, 且
`__pycache__` 已含 084 pyc (违反 CLAUDE.md 铁律 5)。DB stamped 仍 `078`, 084 的 4 索引
在 DB 中 0 条 (无脏数据)。

**隐蔽性**: app `/health` 200 healthy (FastAPI 运行时不依赖 alembic) → **监控不报警,
但下次部署必炸**。

**修复**: `rm` 孤儿 084 + `rm -rf __pycache__` + `alembic current` 验证。

**新铁律 (建议入 CLAUDE.md §2.3 第 6 条)**:
> **alembic `docker cp` 必须按链全量, 不能只 cp 末端。** 漏 upstream →
> `KeyError: '<down_revision>'` → alembic 完全不可用。cp 后必 `rm -rf __pycache__`
> + `alembic current` 验证。
> **Git Bash 下 `docker exec` 需 `MSYS_NO_PATHCONV=1`**, 否则 `/app/...` 被改写成
> `C:/Program Files/Git/app/...` (本次实测踩到)。

---

## P1 三连

### a) 084 表名单数 → 迁移必 `relation does not exist`

084 写 `"meeting"` / `"member"`, 真实表名带复数。live DB 事务内实证 (已 ROLLBACK):

```sql
CREATE INDEX ix_test ON meeting (cluster_id_history);
-- ERROR:  relation "meeting" does not exist
```

来源: docstring 引 ORM **文件名** (单数) 而非 `__tablename__` (复数)。`035` 用的正是 `"meetings"`。

### b) `jsonb_path_ops` 不接受 `json` 类型 → 3 GIN 必失败

3 列实际是 **`json`** (`035` 用 `sa.JSON()`, ORM `Column(JSON)`), 非 `jsonb`:

```sql
CREATE INDEX ix_test ON meetings USING gin (cluster_id_history jsonb_path_ops);
-- ERROR:  operator class "jsonb_path_ops" does not accept data type json
```

文件名 `..._jsonb_gin_index` 与 docstring "JSON 字段" 自相矛盾 — 作者误认 json ≡ jsonb。
✅ 1 联合部分索引改表名后实证可建成功。EXPLAIN 断言测试本批必 fail (索引建不出)。

**修复 3 路径 (主拍拍板)**: A) `ALTER ... TYPE jsonb` + 改 ORM (**触老路径 `app/models/meeting.py`,
须批例外 + 评估锁表**) / B) 放弃 3 GIN 仅留部分索引 / C) 全撤留 W75+ 与 jsonb 迁移合做。

### c) stylelint 58 errors → main fail 自身 CSS 硬门禁

14 vue 文件违规 (`declaration-property-value-disallowed-list` 字面 hex + `color-named` white),
4 商业化组件源自 `3b1eb0834` (W72 C-3 "Mobile v3.4 商业化暗色" 用字面 hex 写 dark mode 未走 token)。
`lint-css.yml` 两道门 (`lint:css` 无 continue-on-error + `stylelint-baseline-guard` 0-error 硬门禁)
→ **main 会 fail 自己的 CI**, 违反 CLAUDE.md "Lint CSS 守恒 71 PASS baseline"。
修法: 复用 v70~v76 "~340 hex→token" 既有范式。

---

## P2: 4 监控脚本 webhook JSON 全部畸形

W73 B-2 `68e024677` 4 脚本结构合规 (set -e / log / fail_loud / 退出码 / crontab 注释),
但 payload 缺右花括号 (4 处同 bug):

```bash
-d "{\"text\":\"[alembic-monitor] $*\""      # 缺 \"}\"
```

→ webhook 400 + `|| true` 静默吞 → **报警彻底丢失, 监控形同虚设** (违反 fail loud 纪律)。
`scripts/monitor-tenant-isolation.sh` (W74 D-1 第 5 类) 不存在 (D-1 0 commit)。

---

## W74 6 Step 校正

Step 1 (`277c6708b`) / 2 (`ed9cc0d8c`) / 6 (`3b1eb0834`) ✅ 在 main。
Step 3 (C-1) ❌ 未开工 · Step 4 (D-1) ⚠️ 分支 0 commit · Step 5 (B-2) ❌ 未开工。

> **Step 6 的代价**: "已实施" ≠ "已合规" — 交付 4 组件 + 119 e2e, 同时引入 58 stylelint errors。

---

## 教训沉淀 (2 条)

1. **调研派生的 schema 任务, 实施前必须 `information_schema` 实查表名 + 列类型。**
   A-2 调研写 "JSON 字段缺 GIN 索引" 时未核实 json/jsonb 差异与真实表名 → B-1 照抄落地成
   必失败迁移。这正是 "调研 ≠ 生产" 要防的事: 调研本身合规 (0 production code), 但其
   **结论未经 schema 实证**就被下游直接实施。建议派工 v11 增补。

2. **验证型 agent 必须先校验派工前提, 不能承接叙述。** 本批派工书 4 项前提 (HEAD / 锚点基线 /
   alembic 链 / B-2 产出) 全部与实测不符。若照抄宣告 "5 件套 PASS + 242 守恒", 会把 1 个 P0
   与 3 个 P1 全部掩盖过去。派工 v6 §1.2 "Status 段必真验证" 是本次唯一防线。

---

## 主拍待决 4 项

1. **P0 立即修** — 容器 alembic 恢复 (优先于一切)
2. **084 路径 A/B/C 拍板** — A 触老路径需批例外 + 锁表评估
3. **B-2 是否仍派** — 或认定 W73 B-1 `billing_gateway.py` 已收口 Step 5
4. **W73 7 分支合并时机** — 不合并则锚点 242 基线永不可验, 且 B-1 依赖 W73 B-1 的 083

## 本任务守恒

- 0 production code (仅 `docs/` + `memory/` 2 新增)
- 锚点范式 **0 增量** (验证型)
- **未伪造任何 PASS** — 2 FAIL + 1 PARTIAL + 1 分母不足, 全部据实记录
