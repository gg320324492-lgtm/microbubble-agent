# W74 第 1 批 E-1 守恒验证 5 件套 (2026-07-27)

> **结论先行**: 5 件套 **3 PASS / 2 FAIL**。派工书中 4 项前提与实测不符, 已按派工 v6 §1.2
> "Status 段必真验证" 纪律**不伪造 PASS**。发现 **1 个 P0 (生产 alembic 当前已损坏)** +
> **2 个 P1 (084 迁移必失败)** + **1 个 P1 (baseline 58 errors, CI 硬门禁必红)** +
> **1 个 P2 (4 监控脚本 webhook JSON 畸形)**。
>
> 本文档为**验证型**任务: 0 production code 改动, 锚点范式 0 增量。

---

## 0. 派工前提校正 (4 项不符)

派工书的前提与 `main` 实测不一致。E-1 职责是验证而非承接叙述, 故先校正:

| # | 派工书声明 | 实测 | 证据 |
|---|-----------|------|------|
| 1 | 当前 W74 main HEAD = `999276dda` | **`45de56f3b`** (W72 第 2 批 grand closure)。`999276dda` **不是 main 祖先** | `git merge-base --is-ancestor 999276dda main` → 非祖先 |
| 2 | 锚点基线 242 (W73 第 1 批已收口) | W73 第 1 批 **7 分支全部未合并 main**, 仍停在各自 worktree | `git branch -a --contains 999276dda` → 仅 3 个 agent 分支 |
| 3 | alembic 期望单链 `076→078→080→081→082→083→084→085` | main 链为 `075→076→079→078→080→081→082`, head = `080_drive_chunked_uploads`。**077 不存在**, 078/079 顺序倒挂 (078 的 down_revision 是 079) | 见 §1.1 |
| 4 | B-2 计费真支付 mock + alembic 085 已产出 | **B-2 未开工**: 无 `chore/w74-1st-batch-b2-*` 分支, 无 085 文件, 无 `app/services/billing/` 目录 | `git branch -a --list "*w74*"` → 仅 b1 / d1 / e1 |

**W74 第 1 批实际开工**: B-1 (`aef117b17`) + D-1 (仅 base) + E-1 (本任务)。**A-1 / A-2 / C-1 / B-2 未开工**,
故派工书 "6 commits (A-1/A-2/B-1/C-1/D-1/E-1)" 的 0 production code 6/7 守恒**无法按 6 commit 计算**。

---

## 1. 守恒验证 5 件套

### 1.1 alembic 1 head verify — ✅ PASS (但链形与派工书不符)

`main` (`45de56f3b`) 实测:

```
heads: ['080_drive_chunked_uploads']
```

单 head 成立, 无双头阻塞。实际链 (`walk_revisions` 输出):

```
080_drive_chunked_uploads  <- 078_drive_dedupe_audit
078_drive_dedupe_audit     <- 079_team_folders      ← 编号倒挂 (078 在 079 下游)
079_team_folders           <- 076_drive_comments_path_backfill
076_drive_comments_path_backfill <- 075_drive_version_tags
```

`081` / `082` 存在于 `alembic/versions/` 但**不在 main 的 head 路径上**? 否 —
`081 <- 080`, `082 <- 081` 均在链上, 但 `get_heads()` 返回 080。原因: 080 的
`down_revision = "082_commercial_billing_tables"` 在 **main 版本**中为 `082`, 形成
`080→082→081→080` 环 —— 实测 `get_heads()` 仍返回单值, 但 B-1 分支已将 080 的
down_revision 修正为 `078_drive_dedupe_audit`。

**B-1 分支** (`aef117b17`) 链已修正为严格单链:

```
084_meeting_cluster_jsonb_gin_index <- 083_commercial_tenant_isolation
083_commercial_tenant_isolation     <- 082_commercial_billing_tables
082_commercial_billing_tables       <- 081_drive_share_enhancements
081_drive_share_enhancements        <- 080_drive_chunked_uploads
080_drive_chunked_uploads           <- 078_drive_dedupe_audit
```

`heads: ['084_meeting_cluster_jsonb_gin_index']` — 单 head。**085 不存在** (B-2 未开工)。

> ⚠️ **编号倒挂遗留**: `078 <- 079` 违反"编号即顺序"直觉, 是 W73 A-1 `6f4932d75`
> "alembic 080 接 078 (跳过 079 历史分支)" 的产物。链有效但可读性差, 建议未来批次不再新增倒挂。

---

### 1.2 baseline 数字 verify — ❌ FAIL (58 errors, 非 0)

派工书要求跑 `scripts/qa-bench/lint-css.sh` —— **该路径不存在**。真实入口是
`web/package.json` 的 `lint:css` + CI workflow `.github/workflows/lint-css.yml`。

实测 (`cd web && npx stylelint "src/**/*.{vue,css,scss}"`):

```
✖ 58 problems (58 errors, 0 warnings)
```

W73 E-1 报告的 "0 errors" **与实测不符**。14 个文件有错, 违规集中在
`declaration-property-value-disallowed-list` (字面 hex) + `color-named` (`white`):

```
src/components/mobile/BillingChip.vue
src/views/mobile/commercial/MobileSubscriptionView.vue
src/components/mobile/MobileLongPressUpgradeAction.vue
src/components/mobile/MobileSettingsUpgradeEntry.vue
src/components/mobile/MobilePushPermissionDialog.vue
src/components/mobile/MobileResponsiveGrid.vue
src/components/mobile/MobileSwipeNavigation.vue
src/components/mobile/MobileVoiceInputButton.vue
src/components/mobile/MobileCommentInput.vue
src/components/mobile/MobileCommentThread.vue
src/components/desktop/DesktopCommentInput.vue
src/components/desktop/DesktopCommentThread.vue
src/views/desktop/DesktopFileCommentsView.vue
src/views/mobile/MobileFileCommentsView.vue
```

**根因定位**: 4 个商业化组件由 `3b1eb0834` (W72 第 2 批 C-3 "Mobile UX v3.4 商业化暗色")
引入, 该 commit 用字面 hex 写 dark mode, 未走 `variables.css` token。

```bash
git log --oneline -1 -- web/src/components/mobile/BillingChip.vue
# 3b1eb0834 feat(w72-2nd-batch-c3): Mobile UX v3.4 商业化暗色 (4 新组件 + 119 e2e)
```

**影响 (P1)**: `.github/workflows/lint-css.yml` 有两道门:
1. `stylelint` job → `npm run lint:css` **无 continue-on-error** → 非 0 退出即 fail
2. `stylelint-baseline-guard` job → "0 errors baseline" 硬门禁

即 **main 当前会 fail 自己的 CSS CI 门禁**。这违反 CLAUDE.md
"Lint CSS 守恒 (71 PASS baseline)" 记录。

**建议**: 派单独 agent 将 14 文件字面 hex → token 化 (复用 CLAUDE.md
"v70~v76 字面色 token 化 ~340 hex→token" 既有范式)。

---

### 1.3 PWA manifest 410 防护 verify — ⚠️ PARTIAL (nginx 侧 PASS, dist 侧缺 manifest)

**nginx 410 防护存在** (`nginx/conf.d/tunnel.conf` 两处, 80 + 443 block 各一):

```
line 66:  location = /manifest.webmanifest {   # 80 block
line 269: location = /manifest.webmanifest {   # 443 block
```

符合 CLAUDE.md 2026-07-11 永久锚点 "服务器 410 manifest.webmanifest 是有意防护"。

**sw.js 无 unhashed 引用** — CLAUDE.md 铁律 3 (`commit 前必须 grep dist`) PASS:

```bash
grep -oE '"url":"manifest\.webmanifest"' web/dist/sw.js
# (none - GOOD)
```

**但 `web/dist/` 当前无任何 manifest 文件**, 亦无 `sw.js`:

```bash
ls web/dist/ | grep -iE "manifest|sw.js"
# (空)
ls web/dist/
# assets  favicon.ico  index.html  katex  offline.html
```

`SW_VERSION = 'v83-safari-blank-fix-2026-07-24'` (源码侧正常)。

**判定**: 410 防护配置本身 PASS; 但 **hashed manifest 未构建产出**, 故派工书要求的
"`/manifest.{hash}.webmanifest` → 200" **无法在本地验证**。派工书给的 URL 是占位
`https://xxx/`, 无真实域名, 云端 curl 亦无法执行。

**结论**: 不宣告 PASS。需在真实部署后按 CLAUDE.md 6 点 curl 清单验证:

```bash
curl -sk -o /dev/null -w "%{http_code}\n" https://<域名>/manifest.webmanifest        # 期望 410
curl -sk -o /dev/null -w "%{http_code}\n" https://<域名>/manifest.{hash}.webmanifest # 期望 200
curl -sk -o /dev/null -w "%{content_type}\n" https://<域名>/index.html               # 期望 text/html
curl -sk -o /dev/null -w "%{content_type}\n" https://<域名>/                         # SPA fallback
curl -sk -o /dev/null -w "%{content_type}\n" https://<域名>/dashboard                 # SPA route
curl -sk -o /dev/null -w "%{content_type}\n" https://<域名>/sw.js
```

> ⚠️ 若 dist 需重建, **必须 `cd web && npm run build`** (CLAUDE.md 唯一合法 build 命令),
> 严禁 `vite build` 直跑 — 否则 manifest 回落 unhashed → nginx 410 → PWA install 失败
> (commit `59187ce8` 事故复现)。

---

### 1.4 0 production code 守恒 verify — ⚠️ 无法按 6/7 计算 (仅 3 agent 开工)

按实际开工的分支逐一核:

| Agent | 分支 / commit | production 路径改动 | 判定 |
|-------|--------------|-------------------|------|
| **B-1** | `aef117b17` | `alembic/versions/084_*.py` (新增) + W73 B-1 携带的 `app/` 12 文件 | **例外** (alembic + 商业化新模块) |
| **D-1** | 仅 base `999276dda`, **0 commit** | — | 未开工 |
| **E-1** | 本任务 | `docs/` + `memory/` only | ✅ 守恒 |
| A-1 / A-2 / C-1 / B-2 | **无分支** | — | 未开工 |

**B-1 分支 production 改动明细** (含 W73 B-1 继承部分):

```
app/api/v1/tenants.py                 | 147 ++  (新增)
app/middleware/license_middleware.py  |  84 ++  (新增)
app/middleware/tenant_middleware.py   |  55 ++  (新增)
app/services/billing_gateway.py       | 191 ++  (新增)
app/services/invoice_service.py       | 139 ++  (新增)
app/services/license_service.py       | 148 ++  (新增)
app/services/tenant_data_isolation.py |  85 ++  (新增)
app/services/tenant_service.py        | 186 ++  (新增)
app/main.py                           |   2 +   (老路径, 见下)
app/api/v1/billing.py                 |   3 +-  (老路径, 见下)
app/models/billing.py                 |   3 +-  (老路径, 见下)
alembic/versions/084_*.py             |  新增
```

**3 处老路径改动审查 — 均判定合规**:

1. `app/main.py` +2 行: 仅 `tenants` router 注册 (import + router tuple), 属新模块挂载,
   未改动任何既有 router 行为
2. `app/api/v1/billing.py`: `from app.api.deps import get_db` → `from app.core.database import get_db`
   —— **修正 W72 B-5 的 import 错误** (`app.api.deps` 不存在), 属 bug fix 而非重构
3. `app/models/billing.py`: `from app.models.base import Base` → `from app.core.database import Base`
   —— 同上, W72 B-5 import 错误修正

按 CLAUDE.md §3 例外清单, 商业化多租户/计费属 "新功能扩展 (不破坏老任务/会议/知识库路径)",
与 Drive v2 系列同列。**3 处老路径改动是 W72 遗留 import bug 的必要修复, 不属违规重构。**

**结论**: 守恒成立, 但**不能宣告 "6/7"** —— 分母不足 (仅 3 agent 有分支, 1 个 0 commit)。

---

### 1.5 anchor 242 → 242 守恒 verify — ❌ FAIL (基线 242 未落地 main)

派工书声明基线 242 来自 "W73 第 1 批 grand closure 收口"。实测:

- W73 第 1 批 7 分支 (a1/a2/b1/b2/c1/d1/e1) **全部未合并 main**
- main 最新锚点叙述为 W72 第 2 批 (`45de56f3b`)
- 故 **242 是 W73 分支内的自报预测值, 非 main 已落地事实**

各分支自报锚点 (`git log` 提取):

| 分支 | 自报锚点 |
|------|---------|
| W73 A-2 | 235 → 238 (+3) |
| W74 B-1 | 242 → 246 (+1)  ← **声明 +1 但数字跨 4** |

> ⚠️ **B-1 锚点声明内部矛盾**: commit message 与 084 docstring 均写
> "W73 第 1 批 242 → W74 第 1 批 B-1 246 守恒 (+1)"。242→246 是 **+4**, 与 "(+1)" 不符。
> 建议 B-1 修正声明或主拍统一口径。

**结论**: 本任务锚点 **0 增量** (验证型), 但**基线 242 本身不可验证**, 故不宣告
"242 → 242 守恒"。真实口径应为: **main 锚点仍为 W72 第 2 批水位, W73/W74 增量待合并后方可计入。**

---

## 2. 新增段 1: 商业化 B-2 计费真支付 mock 验证 — ❌ 未开工

派工书要求核 B-2 的 3 支付网关 + 3 webhook + alembic 085 + 3 service。实测:

- **无 `chore/w74-1st-batch-b2-*` 分支**
- **无 `alembic/versions/085_*.py`** (全 branch 搜索: 最高 084)
- **无 `app/services/billing/` 目录** (派工书路径不存在)

**但 W73 B-1 已产出等价物** `app/services/billing_gateway.py` (190 行, 单文件而非目录):

```python
class MockBillingGateway(BillingGateway):        # W73 默认, mock 实现
    provider_name = "mock"
    # intent_id = "mock_pi_" + secrets.token_hex(12)

class StripeBillingGateway(BillingGateway):
    raise NotImplementedError("Stripe gateway reserved for W76+ rollout")

class AlipayBillingGateway(BillingGateway):
    raise NotImplementedError("Alipay gateway reserved for W76+ rollout")

class WeChatPayBillingGateway(BillingGateway):
    raise NotImplementedError("WeChat Pay gateway reserved for W76+ rollout")
```

✅ **"仅 mock" 纪律 PASS**: 3 真实网关全部 `NotImplementedError`, 明确标注 W76+ 才 rollout。
无任何真实支付凭据/SDK 调用, 无资金风险。`MockBillingGateway` 用 `secrets.token_hex`
生成假 intent, `redirect_url` 指向 `mock.billing.local` (不可路由)。

**结论**: B-2 未开工; 其目标已被 W73 B-1 部分覆盖 (接口骨架层)。
**主拍需拍板**: B-2 是否仍需单独派工, 或直接认定 W73 B-1 `billing_gateway.py` 已收口该 Step。

---

## 3. 新增段 2: 9 表索引修复 PASS verify — ❌ FAIL (2 个 P1, 迁移必失败)

B-1 `aef117b17` 产出 `alembic/versions/084_meeting_cluster_jsonb_gin_index.py`:
3 GIN 索引 + 1 联合部分索引, `down_revision = "083_commercial_tenant_isolation"` ✅ 接续正确。

**但迁移本身在真实 DB 上必失败 —— 已用 live postgres 实证 (事务内 ROLLBACK, 未污染)。**

#### P1-a: 表名错误 (`meeting` / `member` → 实际 `meetings` / `members`)

084 写 `op.create_index(..., "meeting", ...)` 与 `..., "member", ...`。实际表名带复数:

```sql
-- 实测 information_schema
 meetings | cluster_id_history | json
 meetings | speaker_mapping    | json
 meetings | speaker_stats      | json
 members  | voice_confirmed_at | timestamp with time zone
```

```sql
BEGIN; CREATE INDEX ix_test ON meeting (cluster_id_history); ROLLBACK;
-- ERROR:  relation "meeting" does not exist
BEGIN; CREATE INDEX ix_test ON member (voice_confirmed_at, ...) WHERE ...; ROLLBACK;
-- ERROR:  relation "member" does not exist
```

来源: 084 docstring 引 `app/models/meeting.py` / `member.py` (**ORM 类文件名单数**),
但 `__tablename__` 是复数。参照 `035_meeting_cluster_id_history.py` 用的正是 `"meetings"`。

#### P1-b: `jsonb_path_ops` 不接受 `json` 类型 (需 `jsonb`)

3 列实际类型是 **`json`** (非 `jsonb`) —— `035` 迁移用 `sa.Column("cluster_id_history", sa.JSON())`,
ORM 亦为 `Column(JSON, ...)`。而 084 指定 `postgresql_ops={"...": "jsonb_path_ops"}`:

```sql
BEGIN; CREATE INDEX ix_test ON meetings USING gin (cluster_id_history jsonb_path_ops); ROLLBACK;
-- ERROR:  operator class "jsonb_path_ops" does not accept data type json
```

即使表名修对, GIN 仍失败。084 文件名 `..._jsonb_gin_index` 与 docstring
"JSON 字段缺索引" 自相矛盾 —— 作者误认 json ≡ jsonb。

**修复路径 (需主拍拍板, 3 选 1)**:

- **A (推荐)**: 前置 `ALTER TABLE meetings ALTER COLUMN <col> TYPE jsonb USING <col>::jsonb`
  (3 列) 再建 GIN + 同步改 ORM 为 `JSONB` —— 但这**触碰老路径 `app/models/meeting.py`**,
  须主拍批例外, 且大表 ALTER 有锁表风险 (需评估 meetings 行数)
- **B (最小改动)**: 保留 `json`, 改用 `postgresql_using="btree"` 对整列建索引 —— 但 json
  无 btree opclass, 实际不可行; 或**放弃 3 GIN**, 仅保留 1 个部分索引
- **C**: 3 GIN 全部撤下, 留 W75+ 与 jsonb 迁移一并做; 本批只交 1 联合部分索引

#### ✅ 联合部分索引 (`members`) 修表名后可用 — 已实证

```sql
BEGIN;
CREATE INDEX ix_test_partial ON members (voice_confirmed_at, voice_confirmed_by, voice_confirmed_meeting_id)
  WHERE voice_confirmed_at IS NOT NULL;
ROLLBACK;
-- CREATE INDEX   ← 成功
```

#### EXPLAIN ANALYZE 验证 — 未真跑

`tests/test_alembic_084_9_table_index.py` 含 EXPLAIN 断言 (line 92-138), 但**在 084 修好前
必然 fail** (索引建不出来)。派工书要求的 "EXPLAIN ANALYZE 验证索引生效" **本批不成立**。
另: DB 现有索引查询确认 0 条:

```sql
SELECT indexname FROM pg_indexes WHERE indexname LIKE 'ix_meeting%gin' OR indexname LIKE 'ix_member%partial';
-- (0 rows)
```

---

## 4. 🔴 P0 现场事故: 生产 app 容器 alembic 当前已损坏

**非派工项, 实测偶然发现, 优先级高于全部 5 件套。**

`microbubble-agent-app-1` 容器内 `alembic` 命令**当前直接崩溃**:

```
File "alembic/script/revision.py", line 233, in _revision_map
    down_revision = map_[downrev]
KeyError: '083_commercial_tenant_isolation'
```

**根因**: 容器内被 `docker cp` 了 `084_*.py` (其 down_revision 指向 083), 但 **083 没 cp 进去**:

```bash
MSYS_NO_PATHCONV=1 docker exec microbubble-agent-app-1 ls /app/alembic/versions/ | grep -E "^08"
# 080_drive_chunked_uploads.py
# 081_drive_share_enhancements.py
# 082_commercial_billing_tables.py
# 084_meeting_cluster_jsonb_gin_index.py    ← 083 缺失!
```

且 `__pycache__` 已含 `084_*.cpython-311.pyc` / `.cpython-312.pyc` —— 违反 CLAUDE.md
铁律 5 "cp 后必 `rm -rf __pycache__`"。

**当前 DB stamped 版本**: `078_drive_dedupe_audit` (落后 main head 080 两级)。
084 的 4 个索引在 DB 中**均不存在** (0 rows), 故无脏数据, 但:

> ⚠️ **任何人此刻在容器内跑 `alembic upgrade head` / `alembic current` 都会 KeyError 崩溃。**
> 部署链处于阻塞态。app 容器本身 `/health` 200 healthy (FastAPI 不依赖 alembic 运行时),
> 故**监控不会报警, 但下次部署必炸**。

**立即修复 (2 选 1)**:

```bash
# 方案 1 (推荐): 移除孤儿 084 + 清 pycache, 回到 main 一致状态
MSYS_NO_PATHCONV=1 docker exec microbubble-agent-app-1 rm -f /app/alembic/versions/084_meeting_cluster_jsonb_gin_index.py
MSYS_NO_PATHCONV=1 docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 rm -rf /app/alembic/versions/__pycache__
MSYS_NO_PATHCONV=1 docker exec microbubble-agent-app-1 alembic current   # 期望恢复正常

# 方案 2: 待 084 表名/jsonb 修好后, 083 + 084 一并 cp + 清 pycache
docker cp alembic/versions/083_commercial_tenant_isolation.py microbubble-agent-app-1:/app/alembic/versions/
docker cp alembic/versions/084_meeting_cluster_jsonb_gin_index.py microbubble-agent-app-1:/app/alembic/versions/
MSYS_NO_PATHCONV=1 docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 rm -rf /app/alembic/versions/__pycache__
MSYS_NO_PATHCONV=1 docker exec microbubble-agent-app-1 alembic upgrade head
```

**新铁律 (建议入 CLAUDE.md §2.3)**:
> **alembic 迁移 `docker cp` 必须按链全量 cp, 不能只 cp 末端。** cp 单个下游迁移而漏其
> upstream → `KeyError: '<down_revision>'` → alembic 完全不可用。cp 后必须
> `alembic current` 验证, 且必须 `rm -rf __pycache__`。
> 附: Git Bash 下 `docker exec` 路径需 `MSYS_NO_PATHCONV=1`, 否则 `/app/...` 被
> 改写为 `C:/Program Files/Git/app/...` (本次实测踩到, 参照 CLAUDE.md vLLM 段既有教训)。

---

## 5. 新增段 3: 声纹 + ASR + TTS ≠ 生产警示 — ✅ PASS

W73 A-2 (`a2243a650`) 严格守纪律:

```
 docs/w73-1st-batch-a2-voice-asr-tts-survey-2026-07-27.md   | 499 ++
 memory/w73-1st-batch-a2-voice-asr-tts-survey-2026-07-27.md | 209 ++
 2 files changed, 708 insertions(+)
```

✅ **仅 `docs/` + `memory/` 2 文件, 0 production code**。commit message 明示
"调研 ≠ 生产 (不动 `app/voice/` + `app/services/` + `alembic/versions/` 老路径)"。

符合派工 v6 段 5 反馈 "调研完成 ≠ 生产实施"。声纹 `MATCH_THRESHOLD 0.7` vs 90% 门禁的
4 候选解释 + 修复路径 A/B/C 停留在文档层, **未进入 main**, 符合 "主拍必拍" 纪律。

> ⚠️ **但派生任务已越界**: A-2 §2.5 派生的 "9 表 schema 索引缺口" 被 B-1 直接实施为
> alembic 084 —— 而 084 存在 §3 两个 P1 (表名 + jsonb)。**这正是 "调研 ≠ 生产" 要防的事:
> 调研文档写 "JSON 字段缺 GIN 索引" 时未核实 json/jsonb 差异与真实表名, 下游 agent
> 直接照抄落地成必失败迁移。** 建议派工 v11 增补: 调研派生的 schema 类任务, 实施前
> 必须 `information_schema` 实查表名 + 列类型。

---

## 6. W74 6 Step 必读 (D-1 §3.2) — 校正后状态

| Step | 内容 | 派工书声明 | 实测 |
|------|------|-----------|------|
| 1 | PR5 trash 收口 + alembic 080 | W72 第 2 批 B-3 已实施 | ✅ 确认 `277c6708b` 在 main |
| 2 | PR7 request 收口 | W72 第 2 批 B-4 已实施 | ✅ 确认 `ed9cc0d8c` + merge `348f21dca` 在 main |
| 3 | 240 题灰度 | C-1 W74 已派 | ❌ **无 C-1 分支, 未开工** |
| 4 | 多租户实战 | D-1 W74 已派 | ⚠️ 分支存在但 **0 commit** (仍在 base) |
| 5 | 计费真支付接入 | B-2 W74 已派 (主拍单独拍板) | ❌ **无 B-2 分支**; 目标部分被 W73 B-1 覆盖 (§2) |
| 6 | Mobile v3.4 商业化暗色 | W72 第 2 批 C-3 已实施 | ✅ 在 main (`3b1eb0834`) —— **但即 §1.2 baseline 58 errors 元凶** |

**Step 6 的代价**: 该 commit 交付了 4 组件 + 119 e2e, 但引入 58 个 stylelint 错误,
使 main 违反自身 CSS 硬门禁。"已实施" ≠ "已合规"。

---

## 7. 4 类 hot-fix 监控 verify (W73 B-2) — ⚠️ PARTIAL (P2 缺陷)

W73 B-2 (`68e024677`) 产出 4 脚本, 均存在:

```
scripts/monitor-alembic-heads.sh   (79 行)
scripts/monitor-pwa-manifest.sh    (85 行)
scripts/monitor-nginx-mime.sh      (77 行)
scripts/monitor-sw-cache.sh        (83 行)
```

✅ 结构合规: 各含 `set -e` + `log()` + `fail_loud()` + 退出码约定 (0=正常 / 1=异常 / 2=错误)
+ crontab 用法注释 + 依据引用 (CLAUDE.md §2.4 + W68 第 3 批事故 `1852468a6`)。

❌ **P2: 4 脚本 webhook payload JSON 全部畸形** —— 缺右花括号:

```bash
-d "{\"text\":\"[alembic-monitor] $*\"" "$WEBHOOK_URL"
#                                    ^ 缺 \"}\"
```

4 处同一 bug (`monitor-alembic-heads.sh:31` / `monitor-nginx-mime.sh:48` /
`monitor-pwa-manifest.sh:32` / `monitor-sw-cache.sh:32`)。后果: **报警时 webhook 收到
非法 JSON → 400 → 且因 `|| true` 静默吞掉 → 报警彻底丢失**。监控形同虚设 (fail silently,
违反 CLAUDE.md "fail loud" 纪律)。

**修复 (4 处同款一行)**:

```bash
-d "{\"text\":\"[alembic-monitor] $*\"}" "$WEBHOOK_URL"
```

**`scripts/monitor-tenant-isolation.sh` (W74 D-1 新增第 5 类) — 不存在** (D-1 0 commit)。

---

## 8. 部署 webhook 30s + 浏览器 SW cache 验证 — 未执行 (前置未满足)

派工书要求。**本批不执行**, 理由:

1. §4 P0 未修 → 容器 alembic 崩溃, 部署链阻塞
2. §3 P1 未修 → 084 迁移必失败, 部署即回滚
3. §1.3 `web/dist/` 无 manifest/sw.js → 无可验证产物
4. 派工书 URL 为占位 `https://xxx/`, 无真实域名

**修复后应执行的完整清单** (CLAUDE.md 6 点 curl + SW):

```bash
# A. 部署 (webhook 30s)
git push origin main && sleep 30

# B. 6 点 MIME curl (2026-06-13 整站 octet-stream 事故防线)
for p in /index.html / /dashboard /sw.js /pwa-192.png /manifest.{hash}.webmanifest; do
  curl -sk -o /dev/null -w "$p -> %{content_type} %{http_code}\n" "https://<域名>$p"
done
# 任一返回 application/octet-stream 即 nginx types 指令被污染 → 立刻回滚

# C. manifest 410 双验
curl -sk -o /dev/null -w "%{http_code}\n" https://<域名>/manifest.webmanifest         # 410
curl -sk -o /dev/null -w "%{http_code}\n" https://<域名>/manifest.{hash}.webmanifest  # 200

# D. 浏览器 SW cache (2026-06-13 SW 污染事故防线)
# DevTools → Application → Service Workers: 状态 activated + 含新 SW_VERSION
# DevTools → Application → Cache Storage: 无残留 documents cache
# 兜底: Clear site data + 硬刷
# 期望 console: [SW_UPDATED] 后自动 reload
```

---

## 9. 汇总

### 5 件套结果

| # | 项 | 结果 |
|---|---|------|
| 1.1 | alembic 1 head | ✅ PASS (main `['080_...']`; B-1 分支 `['084_...']`) —— 但链形与派工书不符, 078/079 编号倒挂, 085 不存在 |
| 1.2 | baseline 数字 | ❌ **FAIL — 58 errors** (非 0), 元凶 `3b1eb0834`, CI 硬门禁必红 |
| 1.3 | PWA manifest 410 | ⚠️ PARTIAL — nginx 410 双 block PASS + sw.js 无 unhashed 引用 PASS; dist 无 manifest, 云端无域名不可验 |
| 1.4 | 0 production code | ⚠️ 守恒成立但**不能宣告 6/7** (仅 3 agent 有分支, D-1 0 commit, 4 agent 未开工) |
| 1.5 | anchor 242→242 | ❌ **FAIL — 基线 242 未落地 main** (W73 全 7 分支未合并); B-1 自报 "242→246 (+1)" 内部矛盾 |

### 3 新增段

| 段 | 结果 |
|---|------|
| 商业化 B-2 计费真支付 mock | ❌ 未开工 (无分支/无 085/无目录); W73 B-1 `billing_gateway.py` 已覆盖接口骨架, **"仅 mock" 纪律 PASS** (3 网关全 NotImplementedError) |
| 9 表索引修复 | ❌ **FAIL — 2 个 P1**: 表名 `meeting`/`member` → 应 `meetings`/`members`; `jsonb_path_ops` 不接受 `json` 类型。均已 live DB 实证 |
| 声纹 + ASR + TTS ≠ 生产 | ✅ PASS (A-2 仅 2 文档文件 0 production code) —— 但其派生任务落地成 084 必失败迁移, 暴露"调研未核实 schema"缺口 |

### 缺陷清单 (按优先级)

| P | 问题 | 位置 | 修复 |
|---|------|------|------|
| **P0** | app 容器 alembic `KeyError: '083_...'` —— cp 了 084 漏 083 + 残留 pycache, **部署链阻塞** | `microbubble-agent-app-1:/app/alembic/versions/` | §4 方案 1 (rm 孤儿 084 + 清 pycache) |
| **P1** | 084 表名单数, 迁移必 `relation does not exist` | `alembic/versions/084_*.py` | `meeting`→`meetings`, `member`→`members` |
| **P1** | `jsonb_path_ops` 不接受 `json` 类型, 3 GIN 必失败 | 同上 | §3 路径 A/B/C 主拍拍板 |
| **P1** | stylelint 58 errors, main fail 自身 CSS 硬门禁 | 14 个 vue 文件 (源 `3b1eb0834`) | 字面 hex → token 化 |
| **P2** | 4 监控脚本 webhook JSON 缺 `}`, 报警静默丢失 | `scripts/monitor-*.sh` | 补 `\"}\"` |
| **P3** | B-1 锚点声明 "242→246 (+1)" 算术矛盾 | `aef117b17` commit msg + 084 docstring | 统一口径 |

### 主拍待决 4 项

1. **P0 立即修** —— 容器 alembic 恢复 (§4), 建议先行
2. **084 修复路径 A/B/C** —— jsonb 迁移触碰老路径 `app/models/meeting.py`, 需批例外 + 评估 `meetings` 表锁表风险
3. **B-2 是否仍需派工** —— 或认定 W73 B-1 `billing_gateway.py` 已收口 Step 5
4. **W73 第 1 批 7 分支合并时机** —— 未合并则锚点 242 基线始终不可验证; 且 B-1 依赖 W73 B-1 的 083

### 本任务守恒

- **0 production code 改动** —— 仅 `docs/` + `memory/` 2 新增文件
- **锚点范式 0 增量** (验证型)
- **未伪造任何 PASS** —— 派工 v6 §1.2 "Status 段必真验证" 严格执行; 5 件套 2 项 FAIL、
  1 项 PARTIAL、1 项分母不足, 全部据实记录

---

*W74 第 1 批 E-1 · 2026-07-27 · 验证基准 main `45de56f3b` + B-1 `aef117b17`*
