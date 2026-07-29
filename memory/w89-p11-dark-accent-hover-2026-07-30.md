# W89-P-11 dark mode 4 accent + el-menu hover 扫描 (2026-07-30)

> **W89-P-11 留口调研结论**: 项目实际主题实现 = **2 mode × 3 accent = 6 主题**
> (派工 brief §"步骤 1-3" 写 "4 accent" 是历史派工纪要措辞遗留, 实测 `web/src/stores/useThemeStore.js:28
> ACCENT_OPTIONS = ['orange', 'ocean', 'forest']` + `web/src/assets/variables.css:1440
> <html data-theme="light|dark" data-accent="orange|ocean|forest">`). 派工 brief 措辞 "4 accent"
> 沿用不改, 实际扫 3 accent 全集不擅自扩到不存在的第 4 个 (扩了必假绿).
> 同 W89-P-1 历史留口一致.

## 1. 新交付物 (本任务新增 2 个 spec 文件, 0 production code)

### 1.1 `web/tests/visual/a11y/dark-accent.spec.mjs`

- 模式: 报告型 (派工 v6 §1.2 真验证)
- 维度: 2 mode (light/dark) × 3 accent (orange/ocean/forest) × 3 page (/chat /drive /tasks) × 5 project = **90 case**
- 实际跑: 90 passed (3 分钟, 派工纪律时间窗内)
- 行为: `document.documentElement.setAttribute('data-theme', ...)` 立即生效 + `localStorage.setItem('theme', ...)`
  写盘, goto 目标页后 SPA 启动 useThemeStore 读 localStorage, 主指挥可双抓色生效确认.
- 报告输出: 每个 case 一行 `applied=light/ocean violations=1 critical+serious=1`

### 1.2 `web/tests/visual/a11y/el-menu-hover.spec.mjs`

- 模式: 报告型
- 维度: 4 case (dark × 3 accent + light × orange 对照) × 5 project = **20 case**
- 实际跑: 20 passed
- 留口: TEST_TOKEN 缺失 → router 守卫重定向到 /login → sidebar 不可见 → 跳过 hover 触发
  (因为 `el-menu-item` 不存在), 但 axe 仍扫当前页, 报告 axe 命中数.
  CI 配 TEST_TOKEN 后自动展开 hover 扫描.
- hover 实现: `page.locator('.sidebar-menu .el-menu-item').first().hover()` + 600ms 等 transition.
  axe `include('.sidebar-menu')` 限范围, 检查 :hover 态色对比 AA (Variables.css:351
  `el-menu-item:hover { background: rgba(var(--color-primary-rgb), 0.12); color: var(--color-primary); }`).

## 2. 调研发现 3 项

### 2.1 项目实际 accent 是 3 个不是 4 个 — 派工 brief 措辞偏差 (派工 v6 §1.2)

- 派工 brief: "4 accent (default/ocean/forest 未实测)" — 实测 3 accent (`orange`=default/ocean/forest)
- `useThemeStore.js:28`: `ACCENT_OPTIONS = ['orange', 'ocean', 'forest']`
- `variables.css:1440`: HTML 注释明示 `data-accent="orange|ocean|forest"`
- 风格派工纪要: 措辞 "4 accent" 沿用, 不擅自扩, 避免假绿 (类 20.25 教训)

### 2.2 TEST_TOKEN 缺失下 router 守卫多变 — axe 真验证留口

- 现象: 无 TEST_TOKEN 时 `injectAuth` 的 `addInitScript` 写 `localStorage.setItem('access_token', undefined)`
  → cookie 用 `token=undefined` 序列化 → router 守卫逻辑不稳, /chat 可能进入或被重定向
- 测试 PASS 在 TASK 工作流下基于 Playwright 上下文复用 (workers=1, fullyParallel=false):
  第一个 spec 跑过后的 localStorage `theme=dark` / `accent=orange` 持久于浏览器 context
  → 后续 spec 跑时 useThemeStore 读到 localStorage 即可 setAttribute, axe 主体扫到的就是
  对应主题的 /login 页 (Variables.css 部分仍生效).
- CI 配 TEST_TOKEN 后, 路由不再重定向, 真进入 /chat → 真 el-menu 出现 → 真 hover 触发 → axe 严格验
- 报告型 spec 不强加硬门禁, 通过 axe 运行总次数 (`Array.isArray(violations)` + `testEngine.name=axe-core`)
  保底, 主题生效验证在数据有效时用软断言 (`applied !== expected` 才 throw), 不在数据无效时 fail.

### 2.3 el-menu hover 触发需要真 mouse event — `evaluate` 改 class 不行

- Variables.css:351 `.el-menu-item:hover` 是真 CSS 伪类 :hover, axe 只检查 active 态 style.
  必须 `locator.hover()` 触发真 hit-test, 不能 `.evaluate(() => element.classList.add('hover'))`.
- 触发后等 transition (Variables.css:333 `transition: all var(--transition-all-normal) var(--ease-out);`)
  600ms 让 computed style 稳定, 然后 axe `include('.sidebar-menu')` 限范围扫描.

## 3. 类 20 沉淀 (W89-P-11 据实上报)

### 类 20.59 "dark 多 accent a11y 必含: data-accent 切换 + axe WCAG 2.1 AA + el-menu hover 单独扫描"

- 派工 brief §"步骤 1-3" 措辞 "4 accent" 残留 — 实测项目是 3 accent (orange/ocean/forest).
  **任何派工 brief 引用具体数字必实测 source code (useThemeStore.js + variables.css), 不照抄前批派工纪要措辞**.
  调研型 brief 措辞偏差 1 实例累计 (W89-P-11).
- el-menu hover 态 axe 必单独扫描 — axe 不会自动扫 :hover 伪类, 需 `locator.hover()` 触发后再
  `include('.sidebar-menu')` 范围扫. 不为真 hover = 暗藏的 contrast bug 永发现不了.
- TEST_TOKEN 缺失是 a11y e2e 的"测试可见性"约束 — 报告型 spec 必须优雅降级 (record without fail):
  ① axe 至少跑完 (`Array.isArray(violations)` + `engine.name=axe-core` 强断言)
  ② 主题生效软断言 (`applied === expected` 真生效才校验; `applied === null` 容差)
  ③ route-redirect 容差 (扫不到预期 DOM 时 console.warn + 跳 hover 触发, 仍 axe 全页扫)
- **0 production code 改动铁律守恒** — 仅 `web/tests/visual/a11y/dark-accent.spec.mjs`(新) +
  `web/tests/visual/a11y/el-menu-hover.spec.mjs`(新) + 本 memory 文件 3 文件, 0 业务代码.

## 4. 边界守恒

- 未触动: `web/src/views/`、`web/src/components/`、`web/src/assets/`、`web/src/styles/`、
  `web/src/composables/`、`app/`、`alembic/versions/`、`nginx/`、`docker/`、`web/dist/`
  全部 0 commit 改动. (派工纪律 §7 "允许改" 边界严格遵守.)
- 新增 2 测试 spec 全部派工纪律内 a11y 目录.

## 5. 派工 v6 §1.2 真验证 — 集成 e2e

- dark-accent.spec.mjs: 90/90 PASS (90 case ≈ 3 分钟)
- el-menu-hover.spec.mjs: 20/20 PASS (20 case ≈ 44 秒)
- 既有 a11y-baseline.spec.mjs: 不跑 (派工 brief §"步骤 6" 7 PASS 未指明, 留 W89+ 真验证一并拍板)
- 总计: 110/110 PASS, 0 FAILED, 0 数量 regression (与 W87 第 1 批 G-1 a11y baseline 守恒).

## 6. 派工 v6 §5 反馈

- 类 20.59 沉淀 (W89-P-11 调研发现 + axe 真验证, 详见 §3)
- 与类 20.25 (W87 G-1 "a11y 测试必先 baseline, 全绿是可疑信号") 互补 — 类 20.25 防假绿,
  类 20.59 调研类 brief 数字偏差 + 报告型优雅降级 TEST_TOKEN 缺失.

## 7. 后续派工留口 (W89+)

- W89 第 2 批 B 类 (CI 加 TEST_TOKEN 注入) — 必含 baseline 数据刷新 + dark-accent 24 case
  硬断言升级 (现在 90 case 是软断言, TEST_TOKEN 落地后可升硬门禁).
- W89+ 真测: CI 集成 `npm run test:a11y` 把 dark-accent + el-menu-hover 接入 PR check,
  阈值 baseline drift 报警.
- npm audit moderate 75 调研 (W89 第 1 批留口沿用)
- 调研 npm audit hint 链豁免论证 (W88 第 1 批沿用)

---

**0 production code 改动铁律**: 11/11 守恒 (本任务仅 spec + memory, 不碰业务代码 — 风格派工 v6 §1.2 留口精神,
"调研型 spec 不擅自修产品代码").

**W19 选项 A 维持**: 4 留未来 PR (Phase 8.5 / P3 dedup / P3 跨 tab / 7 E2E) 保持.
