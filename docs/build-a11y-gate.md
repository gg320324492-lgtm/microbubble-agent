# Build 后 a11y 健康检查 (W89-P-5 沉淀, 类 20.52 纪律)

> **CLAUDE.md 永久纪律强化**: `npm run build` 是**唯一**合法 build 命令 (W87 第 1 批永久纪律)。
> 本任务新增: **build 后必跑 a11y health-check** (派工 v6 §5 反馈 类 20.52)。

## 1. 流程

```bash
# 1. 起 dev server (任一)
cd web && npm run dev          # 默认 localhost:3000
# 或
cd web && npm run preview      # 部署 dist (5173)

# 2. 一条龙 (build + a11y health-check)
cd web && npm run build:a11y

# 3. CI / 本地失败 block 合并 / 提交
```

### 1.1 scripts 拆分

| Script | 用途 | 阶段 |
|---|---|---|
| `npm run build` | vite build + postbuild-fix-manifest (CLAUDE.md 永久纪律) | 唯一合法 build |
| `npm run build:a11y` | build + a11y health-check 链 (W89-P-5 新增) | build 后置验证 |
| `npm run test:playwright:a11y` | 单跑 a11y playwright (复用 W87-G-1 config) | 手动跑 / CI 拆步 |
| `prebuild` | 占位 hook (非 destructive, 仅 echo) | npm 生命周期 |

### 1.2 入口配置

```json
"build:a11y": "npm run build && npm run test:playwright:a11y -- --grep='health-check'"
```

`--grep='health-check'` 仅跑本任务的 health-check spec, 不触发 W87-G-1 baseline 25 case。

## 2. 失败处置

### 2.1 critical + serious violations = 0 (硬断言)

类 20.52 核心纪律: **critical + serious violations 必为 0**。任一存在即 test fail, block 合并。

axe impact 等级:

| Impact | 处置 |
|---|---|
| **critical** | 硬断言 = 0, fail-loud |
| **serious** | 硬断言 = 0, fail-loud |
| moderate | WARN, 主指挥拍板 (留 commit / 修 / 退回) |
| minor | WARN, 主指挥拍板 |

### 2.2 处置 SOP

1. **CI 红**: 看 test output 第一段, 找 `criticalOrSerious` 列表
2. **定位**: 对照 rule id (axe 标准), 在 docs/axe-rules.md 或 axe-core 文档查修复方式
3. **修复**: 改 web/src/, 重跑 `npm run build:a11y`
4. **WARN**: moderate + minor 在 testInfo.annotations 列出, 不 block 但必读

## 3. 已知局限

| 局限 | 缓解 |
|---|---|
| **依赖 vite dev server** (localhost:5173 / 3000) | 调用方必先 `npm run dev` / `npm run preview`; spec 内 BASE_URL 环境变量兼容 |
| **不覆盖真实登录态** | W89-P-4 真环境验证覆盖 (login 后页面 a11y) |
| **PWA disabled 时不跑 manifest 检查** | PWA 检查由 webhint (W86 C-1) 覆盖, 不在本任务范围 |
| **3 case (login/chat/drive)** 而非 25 case baseline | 类 20.52 "硬断言 0 漂移" 选高曝光入口, 不重 W87-G-1 baseline |
| **本任务不真跑 health-check** (仅写 spec) | 真跑留 W89+ 派工 (派工 v6 §1.2 真验证原则) |

## 4. e2e 守恒

`tests/build_a11y/test_scripts.py` 4 门禁:

1. **test_build_a11y_script_exists** — `scripts.build:a11y` 必存在 + 必含 build + health-check
2. **test_health_check_spec_exists** — `health-check.spec.mjs` 必存在 + critical+serious 硬断言代码可见
3. **test_prebuild_hook_safe** — prebuild 必非 destructive (no rm/mv/del) + 必含 echo
4. **test_existing_build_script_unchanged** — 回归 已有 `build` script 必未被误改

跑法:

```bash
pytest tests/build_a11y/ -v
```

预期 4 PASS。

## 5. 派工前提铁律

**派工 v6 §5 反馈 类 20.52 新增** (本任务沉淀):

> **build 后必跑 a11y health-check, critical+serious 硬断言 = 0; moderate + minor 由主指挥拍板 (WARN, 不 block)**

不入 doc string, 但记入 CLAUDE.md 永久纪律章节 (主指挥后续 PR 补)。
本纪律出处: W89-P-5 build:a11y 健康检查 (派工 brief §"e2e 加固")。

## 6. 与既有纪律的边界

- **CLAUDE.md 永久纪律**: `npm run build` 唯一合法 build (W87 第 1 批)
- **CLAUDE.md 永久纪律**: `npm run build:a11y` 新链 (W89-P-5)
- **CLAUDE.md 永久纪律**: a11y critical+serious = 0 (类 20.25 + 类 20.52 双锚定)
- **W87-G-1 baseline**: a11y-baseline.spec.mjs 25 case 比对 (与 health-check 互补, 不重叠)
- **W89-P-3 CI**: Playwright 接 CI (CI 必含 build:a11y, 留 W89+ 真接)
- **W89-P-4 真环境**: 真登录态验证 (覆盖 health-check 未覆盖的登录后页面)

## 7. 留口 (W89+ 真跑派工)

| 留口 | 说明 |
|---|---|
| **真跑 health-check** | 本任务仅写 spec, 不真跑 (需 dev server + playwright npx install). 留 W89-P-6 真跑派工 |
| **CI 接入** | build:a11y 链 入 GitHub Actions, 失败 block merge. 留 W89-P-7 |
| **axe rule 文档** | 50+ axe rule 修复 SOP 沉淀 docs/axe-rules.md. 留 W89-P-8 |
| **moderate 调研** | 主指挥拍板 moderate violations 是否逐项修 vs 永久 WARN. 留 W89+ |
| **a11y 0 violation 终极目标** | critical+serious=0 是底线, moderate+minor 仍可能存在. 长期目标=0 |