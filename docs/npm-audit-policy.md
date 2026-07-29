# npm audit 政策 (W88-C-2, 类 20.44)

## 结论速览

| 口径 | 数值 | 门禁 |
|------|------|------|
| `npm audit` (全树) | 74 moderate / 0 high / 0 critical | high+critical == 0 |
| `npm audit --omit=dev` (生产树) | 1 moderate / 0 high / 0 critical | high+critical == 0 且 moderate ≤ 1 |

W87-X-4c 留下的 75 moderate,W88-C-2 调研后降到 74,其中**只有 1 个真正影响生产 bundle**。

---

## 一、75 moderate 分类 (实测)

用 `npm ls <pkg> --all` 逐个追溯依赖链,结果:

| 类别 | 个数 | 说明 |
|------|------|------|
| `@hint/*` 命名空间 | 65 | webhint 官方子包 |
| `hint` 本体 | 1 | devDependency |
| hint 的传递依赖 | 7 | `file-type` / `is-svg` / `fast-xml-parser` / `got` / `package-json` / `latest-version` / `update-notifier` |
| **生产依赖** | **2** | **`dompurify` + `echarts`** |
| 合计 | 75 | |

### 派工 brief 错配据实上报 (类 20.13)

派工 brief 写"66 集中在 hint",实测是 **73**(65 + 1 + 7)。7 个传递依赖全部**只**由 `hint` 引入,`npm ls` 已逐一验证:

```
fast-xml-parser → hint → @hint/utils → is-svg → fast-xml-parser
file-type       → hint → @hint/utils → file-type
got             → hint → {@hint/hint-ssllabs, update-notifier→latest-version→package-json}
```

brief 又说"修剩余 9 个 moderate(非 hint 链)",实测非 hint 链**只有 2 个**(dompurify + echarts),其余 7 个都在 hint 链内。**不擅自扩也不擅自缩** —— 按实测的 2 个处理。

---

## 二、`--omit=dev` 豁免论证

`hint` 声明在 `web/package.json` 的 **devDependencies**:

- 它是 webhint CLI,只在本地/CI 跑静态检查,**不被 `web/src/` 任何文件 import**
- `npm run build` 产出的 `web/dist/` 不含任何 hint 代码
- 生产部署镜像不安装 devDependencies

因此这 73 个 moderate **不进生产 bundle**,用 `npm audit --omit=dev` 豁免成立。

实测佐证:`npm audit --omit=dev` 后 hint 子树 73 个全部消失,只剩 dompurify + echarts。
`test_hint_devdeps_are_excluded_by_omit_dev` 持续守护这个前提 —— 若有人把 `hint` 挪进
`dependencies`,该测试立即变红,豁免论证失效会被当场发现。

---

## 三、⚠️ `.npmrc` 里严禁写 `omit=dev` (类 20.44 核心)

派工 brief 建议在 `.npmrc` 写:

```ini
omit=dev          # ← 危险!
audit-level=high
```

**实测证明这会摧毁构建链路**。最小复现:

```bash
# package.json: dependencies={spark-md5}, devDependencies={is-svg}
printf 'omit=dev\n' > .npmrc
npm install
# 结果: node_modules/is-svg 不存在 —— devDependency 完全没装
```

`.npmrc` 的 `omit` 是**全局配置**,对 `npm install` / `npm ci` 同样生效。若写进
`web/.npmrc`,`vite` / `vitest` / `playwright` / `stylelint` 全部装不上,
`npm run build` 与所有测试直接崩。

### 正确做法:两层分离

| 层 | 手段 | 作用域 |
|----|------|--------|
| 安装 | 不设 `omit` | devDeps 正常安装,build/测试可跑 |
| 审计 | 命令行 `npm audit --omit=dev` | 仅该次审计排除 dev 树 |

`web/.npmrc` 最终只保留一行有效配置:

```ini
audit-level=high
```

实测 `audit-level=high` 对安装**无副作用**(devDeps 照装),只影响 `npm audit` 退出码:
74 moderate 存在时 `npm audit` 退出码为 0,新增 high/critical 才非 0。

---

## 四、2 个生产 moderate 的处置

### 4.1 dompurify — 已修 ✅

- 现状:3.4.7,4 条 advisory(1 moderate + 3 low)
- 修复版:3.4.12,**在已声明的 `^3.4.7` semver 范围内**
- 手段:`npm update dompurify` —— 只动 `package-lock.json`,`package.json` 一字未改
- 结果:生产树 dompurify 归零(75 → 74,生产 2 → 1)

### 4.2 echarts — 留 W89 ⏸

- 现状:5.6.0,XSS advisory(GHSA-fgmj-fm8m-jvvx,CVSS 6.1)
- 修复版:**6.1.0,major 破坏性升级**(`^5.6.0` 不覆盖)
- 决策:**不在本批修**。echarts 在 `KnowledgeGraphView` / `AnalyticsView` /
  `ProjectStatsView` / `QaBenchR10Monitor` 等多处使用,major 升级需完整视觉回归,
  超出 C-2 "0 production code" 边界
- 兜底:`ECHARTS_WAIVER = 1` 是**上限**而非期望值。新增任何生产 moderate 会让
  `test_production_moderate_within_waiver` 立即变红,不会被 waiver 静默吞掉

---

## 五、e2e 门禁

`tests/npm_audit/` 共 16 case:

- `test_known_vulnerabilities.py`(W87-X-4c,5 case)—— 全树 high/critical == 0
- `test_omit_dev_policy.py`(W88-C-2,6 case)—— 生产树门禁 + hint 豁免前提守护
- `test_audit_policy.py`(W88-C-2,5 case)—— `.npmrc` 静态校验,无网络也 PASS

负向对照均已实测(类 20.23):注入 `omit=dev` → 变红;`audit-level` 改 `moderate` → 变红。

### 已知环境限制

`tests/conftest.py` 有 autouse 的 `setup_db` fixture 需要真实 Postgres。
无 DB 环境下须加 `--noconftest`:

```bash
python -m pytest tests/npm_audit/ --noconftest -v
```

这不是 W88-C-2 引入的 —— W87-X-4c 的 5 个既有 case 在本环境同样被该 fixture 阻断,
行为完全一致。

---

## 六、留 W89

1. **echarts 5.6.0 → 6.1.0** major 升级 + 4 处图表视觉回归
2. **rolldown panic**(`easeInOutCubic` / element-plus)—— `npm run build` 当前在本
   worktree 必崩,**与本批改动无关**,已用原始 lockfile 反证(详见报告)
3. hint 73 moderate 的根治(等 webhint 上游更新,或评估移除该工具)
