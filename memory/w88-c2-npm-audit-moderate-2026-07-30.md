# W88-C-2: npm audit 75 moderate 调研 + `--omit=dev` 政策 (2026-07-30)

> 锚点范式 337 → 338 (+1 守恒)。0 production code 改动守恒(仅 lockfile + 新增 .npmrc/tests/docs/memory)。

## 一、任务与结论

W87-X-4c 留 75 moderate。本批调研后:

| 口径 | before | after |
|------|--------|-------|
| 全树 | 75 moderate / 0 high / 0 critical | **74** moderate / 0 high / 0 critical |
| 生产树 (`--omit=dev`) | 2 moderate | **1** moderate (echarts, 留 W89) |

---

## 二、75 moderate 真实分类 (实测 `npm ls --all`)

| 类别 | 个数 |
|------|------|
| `@hint/*` 命名空间 | 65 |
| `hint` 本体 | 1 |
| hint 传递依赖 (file-type / is-svg / fast-xml-parser / got / package-json / latest-version / update-notifier) | 7 |
| **生产依赖 (dompurify + echarts)** | **2** |

### 派工 brief 错配据实上报 (类 20.13 实战)

| brief 假设 | 实测 | 处理 |
|-----------|------|------|
| "66 集中在 hint" | **73** (65+1+7) | 按实测 |
| "修剩余 9 个非 hint moderate" | 非 hint 链**只有 2 个** | 按实测,不擅自扩缩 |

7 个传递依赖经 `npm ls` 逐个验证,**全部只由 hint 引入**,无第二条路径。

---

## 三、⚠️ 最重要发现:`.npmrc` 写 `omit=dev` 会摧毁构建 (类 20.44)

派工 brief 建议 `.npmrc` 写 `omit=dev` + `audit-level=high`。**实测证明前者是陷阱**。

最小复现:

```bash
# package.json: dependencies={spark-md5}, devDependencies={is-svg}
printf 'omit=dev\n' > .npmrc && npm install
ls node_modules/is-svg     # → 不存在
ls node_modules/spark-md5  # → 存在
```

`.npmrc` 的 `omit` 对 `npm install` / `npm ci` **同样生效**。写进 `web/.npmrc` 会让
`vite` / `vitest` / `playwright` / `stylelint` 全部装不上,`npm run build` 与所有前端测试直接崩。

**正确解法 —— 安装与审计两层分离**:

- 安装层:不设 `omit`,devDeps 正常装
- 审计层:命令行 `npm audit --omit=dev`,仅该次生效

`web/.npmrc` 最终只有一行有效配置 `audit-level=high`,并留注释说明为何禁用 `omit=dev`
(`test_npmrc_documents_the_omit_dev_hazard` 守护该注释,防后人好心加回)。

实测 `audit-level=high` 无安装副作用,仅影响退出码:74 moderate 下 `npm audit` 退出 0。

---

## 四、2 个生产 moderate 处置

### dompurify — 已修 ✅

3.4.7 → **3.4.12**,在已声明的 `^3.4.7` semver 内,`npm update dompurify` 只动
`package-lock.json`,`package.json` **一字未改**(严守"不动生产 dep"边界)。生产树归零。

### echarts — 留 W89 ⏸

5.6.0,XSS(GHSA-fgmj-fm8m-jvvx,CVSS 6.1)。修复需 **6.1.0 major**,`^5.6.0` 不覆盖。
echarts 用于 `KnowledgeGraphView` / `AnalyticsView` / `ProjectStatsView` /
`QaBenchR10Monitor`,major 升级需完整视觉回归,超出本批边界。

`ECHARTS_WAIVER = 1` 是**上限**不是期望值 —— 新增任何生产 moderate 立即变红。

---

## 五、e2e (16 case, 全 PASS)

| 文件 | case | 作用 |
|------|------|------|
| `test_known_vulnerabilities.py` (W87) | 5 | 全树 high/critical == 0 |
| `test_omit_dev_policy.py` (新) | 6 | 生产树门禁 + hint 豁免前提守护 |
| `test_audit_policy.py` (新) | 5 | `.npmrc` 静态校验,无网络也 PASS |

**负向对照实测**(类 20.23,拒绝"全绿即通过"):

- 注入 `omit=dev` → `test_npmrc_does_not_set_omit_dev` FAILED ✅
- `audit-level` 改 `moderate` → `test_audit_level_is_high` FAILED ✅
- 恢复后 16/16 PASS ✅

`test_hint_devdeps_are_excluded_by_omit_dev` 守护豁免论证的**前提**:若 `hint` 被挪进
`dependencies`,豁免立即失效并被当场发现。

### 环境限制

`tests/conftest.py` autouse `setup_db` 需真 Postgres,无 DB 时须 `--noconftest`。
**非本批引入** —— W87-X-4c 的 5 个既有 case 同样被阻断,行为一致。

---

## 六、rolldown panic 据实上报 (非本批引入)

`npm run build` 在本 worktree **必崩**:

```
panicked at compute_cross_chunk_links.rs:584:13:
Symbol "easeInOutCubic" in element-plus/es/utils/easings.mjs should belong to a chunk
```

**已用原始 lockfile 反证**:`git stash` 掉 lockfile 改动 → `npm ci` 回 dompurify 3.4.7 →
`npm run build` **同样崩溃**。故与本批改动无关,是 vite 8 / rolldown + element-plus 的既有
不兼容。

⚠️ 该 panic 发生在 `emptyOutDir` **之后**,会清空 `web/dist/` 221 个产物。本批已
`git checkout -- web/dist` 完整恢复并验证 221 文件齐全、git 状态干净。

**故本批未按类 20.36 重跑 build** —— 不是遗漏,是 build 在本环境不可用。dompurify 是
运行时 sanitize 库,补丁版本无 API 变更,`web/dist/` 保持 W87 产物不动最安全。留 W89 修
rolldown 后再统一 rebuild。

---

## 七、派工 v6 §5 反馈 —— 类 20.44 沉淀

> **类 20.44**:`npm audit` dev 豁免必须用**命令行 `--omit=dev`**,
> **严禁**写进 `.npmrc` —— `.npmrc` 的 `omit` 对 `install`/`ci` 同样生效,
> 会导致 devDependencies 完全不装,摧毁 build 与测试链路。
> `.npmrc` 只放 `audit-level=high`(对安装无副作用)。
> 两层门禁:全树 high/critical == 0 + 生产树 moderate ≤ 已知 waiver。

配套既有铁律:

- 类 20.13(派工 brief 与实测不符,据实上报,不擅自扩缩)—— 本批 2 处实战
- 类 20.23(e2e 必含负向对照)—— 本批 2 个负向对照实测变红
- 类 20.35(npm audit 必须 high/critical 门禁,moderate 留 overrides)—— 本批延续并细化为双层

---

## 八、留 W89

1. echarts 5.6.0 → 6.1.0 major + 4 处图表视觉回归
2. rolldown panic(`easeInOutCubic` / element-plus)修复后统一 rebuild dist
3. hint 73 moderate 根治(等 webhint 上游,或评估移除)

---

## 九、协调提示 (worktree 共享)

本 worktree 在执行期间被多个 W88 agent 共用,HEAD 从 `4219003ac` 前进到 `d5f001e41`
(X-2 `1df74e261` + D-1 `d5f001e41`),分支实为
`claude/w88-h2-logger-contextvars-2026-07-30` 而非 brief 所述 `main`。

本批仅 stage 自己的 6 个文件,未触碰他人改动(`app/services/*.py` 12 个 M、
`web/tests/visual/a11y/*` 4 个 M 等均保持原状),**未 push**,交主指挥统一处理。
