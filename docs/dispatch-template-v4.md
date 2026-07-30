# 派工 Brief 模板 v4 (W89 第 1+2 批沉淀, 类 20.60-68 + 类 20.82 新增)

> **W89-X-27 据实教训**: W89 第 1+2 批派工时, 派工 brief 仍按 v3 模板缺 9 类 (axe SOP + Playwright 集成 + visual baseline + 硬门禁 + CI 触发 + vitest 调研 + swipe 拦截 + networkidle + 真环境 v2), 反复撞同一类墙. 类 20.82 沉淀: **派工 brief v4 升级必含 ≥ 9 铁律 + 实战举例 + CLAUDE.md 永久纪律**.

## 派工 brief v4 头部必含 5 段 (沿用 v3) + 9 新段 (W89 新增)

### 沿用 v3 5 段 (略)

参见 `docs/dispatch-template-v3.md` 第 12-77 行.

---

### 派工 brief v4 新增 9 段 (W89 第 1+2 批沉淀, 必读)

#### 类 20.60 — axe SOP doc 必含 ≥ 5 规则 + 每规则 ≥ 3 段 + CI 段 + 留 W89+ 段 + e2e 门禁 (W89-P-12 沉淀)

```yaml
派工 brief SOP doc 段:
  触发场景: "axe-core / wcag / a11y 相关派工 (如 P-1 a11y violation fix / P-12 SOP 编写)"
  必含_5_规则:
    - rule_1_color_contrast: "≥ 3 段: 阈值 / 检测 / 修法"
    - rule_2_aria_label: "≥ 3 段: 应用范围 / 检测 / 修法"
    - rule_3_keyboard_navigation: "≥ 3 段: 顺序 / 检测 / 修法"
    - rule_4_focus_visible: "≥ 3 段: 状态机 / 检测 / 修法"
    - rule_5_alt_text: "≥ 3 段: 自动 vs 手动 / 检测 / 修法"
  必含_其他_段:
    - "CI 段: pre-commit hook + build:a11y 命令"
    - "留 W89+ 段: 后续 P-13 / P-14 接续路径"
    - "e2e 门禁段: 必须 22 rule PASS / axe-core 0 violation"
  反例: "只列 5 规则标题, 无每规则 ≥ 3 段 = 拦截沉淀类 20.60"
```

#### 类 20.61 — Playwright 集成必含: 真跑 build:a11y + pre-commit + 3 件套联动 (W89-P-13 沉淀)

```yaml
派工 brief Playwright 集成段:
  触发场景: "Playwright 真部署 / a11y 集成 / 视觉回归相关派工"
  必含_3_件套:
    - 真跑_build_a11y: "cd web && npm run build:a11y 真跑必须 0 violation 退出码 0"
    - pre_commit: "pre-commit hook 必跑 build:a11y + lint + type-check 3 件联动, 不允许只跑单个"
    - 3_件套_联动: "build:a11y + lint + type-check 必须 pipeline 串联, 任一失败拦截 commit"
  反例: "只验证 Playwright 配置可加载, 不真跑 = 拦截沉淀类 20.61"
```

#### 类 20.62 — visual baseline 重 sync 必逐 spec + 统一 canonical project + 拍板 (W89-X-10 沉淀)

```yaml
派工 brief visual baseline 段:
  触发场景: "visual baseline 重 sync / testMatch 调整 / 截图替换"
  必含_3_段:
    - 逐_spec: "必须每 spec 单独跑 baseline 同步, 不准 batch 全量"
    - canonical_project_统一: "选 1 个 project 名为 canonical (e.g. 'microbubble-agent'), 其余 alias 同步"
    - 拍板: "主指挥必须拍板 baseline 数量上限, 默认 ≤ 120 张避免膨胀"
  实战教训: "W89-X-10 visual 113 缺 baseline = 61 张独立 × 重复 (testMatch 双重匹配)"
```

#### 类 20.63 — Playwright 软断言改硬门禁必 TEST_TOKEN 真注入 + throw if missing (W89-X-11 沉淀)

```yaml
派工 brief dark mode 硬门禁段:
  触发场景: "软断言 (soft expect) 改硬门禁 (hard expect) / 暗色模式断言改写"
  必含_2_段:
    - TEST_TOKEN_真注入: "环境变量 TEST_TOKEN 必须走 process.env.TEST_TOKEN, 不允许 hardcode"
    - throw_if_missing: "TEST_TOKEN 缺失必须 throw, 不允许 silent fallback 到默认"
  反例: "硬门禁写了 if TEST_TOKEN 不存在就 skip = 拦截沉淀类 20.63"
```

#### 类 20.64 — 真 CI 触发必含: gh auth status + act 模拟 + 真部署文档化 (W89-X-12 沉淀)

```yaml
派工 brief CI 触发段:
  触发场景: "GitHub Actions 真触发 / pre-commit.ci 集成 / CI 文档"
  必含_3_段:
    - gh_auth_status: "派工前必跑 `gh auth status` 验证登录态, 不允许凭印象认为登录"
    - act_模拟: "本地用 act 模拟 GitHub Actions workflow, 验证 .github/workflows/*.yml 真过"
    - 真部署文档化: "CI 触发后必须文档化 (runbook + 截图 + commit hash), 不允许凭空说 PASS"
  反例: "没跑 gh auth 就 commit workflow 文件 = 拦截沉淀类 20.64"
```

#### 类 20.65 — 19 vitest failed 调研必: 4 类根因分类 + 修法优先级 + 不擅自修 (W89-X-13 沉淀)

```yaml
派工 brief vitest failed 调研段:
  触发场景: "vitest failed 真调研 / 测试优化 / 测试 pass 调研"
  必含_4_类根因:
    - 类型_1_import_error: "vitest 用 playwright API (test.use 等), 写法 import 错位"
    - 类型_2_fixture_leak: "vi.mock / vi.fn 重置不全, fixture 之间污染"
    - 类型_3_async_timeout: "async 测试缺 await / 缺 timeout 配置"
    - 类型_4_dependency_缺失: "testMatch / spec 路径在 vitest 无 plugin 时漏"
  修法优先级:
    - "类型 1 > 类型 2 > 类型 3 > 类型 4"
  不擅自修: "调研完成 ≠ 修, 主指挥拍板后才改"
```

#### 类 20.66 — vitest spec 必无 test.use() (playwright API), 描述 test.use 必在 playwright spec (W89-X-14 拦截沉淀)

```yaml
派工 brief vitest test.use 拦截段:
  触发场景: "vitest / playwright 测试改写 / mobile_swipe_gesture 等 swipe 类测试"
  必含_2_段:
    - vitest_必无_test_use: "vitest spec 文件不允许出现 test.use(), 这是 playwright API"
    - 描述_test_use_必在_playwright: "需要 test.use 描述的测试必须在 playwright spec 而非 vitest spec"
  实战拦截: "W89-X-14 mobile_swipe_gesture.spec 是 Playwright 但被错放 vitest = 类 20.66 拦截沉淀"
  修法: "派工 brief 必明示测试类型 (Playwright vs vitest), 主指挥拦截错放"
```

#### 类 20.67 — WS/SSE/long-polling 页面必删 networkidle, 等明确 UI locator 或目标 API (W89-X-15 沉淀)

```yaml
派工 brief Playwright networkidle 拦截段:
  触发场景: "WebSocket / SSE / long-polling 页面测试"
  必含_3_段:
    - 必删_networkidle: "WS/SSE/long-polling 页面不允许用 waitForLoadState('networkidle'), 永远等不到 idle"
    - 等明确_UI_locator: "用 expect(locator).toBeVisible() 明确 UI 元素可见"
    - 等目标_API: "用 page.waitForResponse(/target.api/) 等目标 API 响应"
  实战教训: "W89-X-15 12/15 测试因 SSE 长连接 networkidle 超时 flake, 改 locator/API 等后 PASS"
```

#### 类 20.68 — Playwright 真环境验证 v2 必含 6 步曲: docker ps 查重 + 12 services + a11y + visual + e2e + 真功能, 前置 npm install (W89-X-16 沉淀)

```yaml
派工 brief Playwright 真环境验证 v2 段:
  触发场景: "Playwright 真环境验证 / docker compose 真部署 / 截图对比"
  必含_6_步曲:
    - 步_1_docker_ps_查重: "`docker ps | grep <service>` 查重, 避免污染"
    - 步_2_12_services: "本地 docker compose 跑 12 services (app / celery / postgres / redis / frontend / nginx / minio / pg_exporter / glitchtip / sentry / k6 / 等)"
    - 步_3_a11y: "npm run build:a11y 真跑 0 violation"
    - 步_4_visual: "npm run build:visual baseline 对比"
    - 步_5_e2e: "cd web && npx playwright test 真跑全套"
    - 步_6_真功能: "真浏览器手动检查核心功能 (登录 / 知识库 / 会议 / 任务)"
  前置_npm_install: "web 依赖变化必先 npm install, 不允许依赖未装就跑"
  实战教训: "W89-X-16 上批缺 npm install 直接跑 e2e 全失败 = 类 20.68 实战沉淀"
```

---

## 实战示例 (W89 第 1+2 批)

```yaml
# 示例 1: W89-P-6 cherry-pick 冲突时
W89-P-6 cherry-pick 冲突:
  实测: "auth-shared-token.spec.mjs cherry-pick 与 P-6 版本冲突"
  据实: "选 P-6 版本 (W89-X-9 暂停教训), 弃 cherry-pick"
  拦截: 类 20.61 "Playwright 集成必含真跑 build:a11y" 守住

# 示例 2: W89-X-14 拦截
W89-X-14 mobile_swipe_gesture 拦截:
  实测: "派工 brief 把 Playwright spec 错发到 vitest 路径"
  拦截: "派工 brief 段 7 实战派工 19 类 类 20.66 拦截 → 不删 test.use, 而是改 spec 路径"
  沉淀: "派工 brief v4 必明示测试类型 (Playwright vs vitest)"

# 示例 3: W89-X-10 visual baseline
W89-X-10 visual baseline 重 sync:
  实测: "113 spec 缺 baseline = 61 张独立 × 重复 (testMatch 双重匹配)"
  修法: "派工 brief 类 20.62 段逐 spec + 统一 canonical project 'microbubble-agent' + 拍板 ≤ 120 张"
  沉淀: "visual baseline 必逐 spec 同步, 不准 batch 全量"
```

---

## 派工 brief v4 与 v3 关键差异 (W89 沉淀)

| 差异 | v3 (W87) | v4 (W89) |
|------|----------|----------|
| axe SOP 段 | 无 | 类 20.60 必含 ≥ 5 规则 + 每规则 ≥ 3 段 |
| Playwright 集成段 | 无 | 类 20.61 必含真跑 build:a11y + pre-commit 3 件套 |
| visual baseline 段 | 无 | 类 20.62 必逐 spec + 统一 canonical + 拍板 ≤ 120 张 |
| 硬门禁段 | 无 | 类 20.63 TEST_TOKEN 真注入 + throw if missing |
| CI 触发段 | 无 | 类 20.64 gh auth status + act + 真部署文档化 |
| vitest 调研段 | 无 | 类 20.65 4 类根因分类 + 修法优先级 + 不擅自修 |
| test.use 拦截段 | 无 | 类 20.66 vitest spec 必无 test.use, playwright spec 才允许 |
| networkidle 段 | 无 | 类 20.67 WS/SSE/long-polling 必删, 等 locator/API |
| 真环境 v2 段 | 无 | 类 20.68 6 步曲 (docker ps + 12 services + a11y + visual + e2e + 真功能) 前置 npm install |

---

## CLAUDE.md 永久纪律沉淀 (W89 第 2 批 X-27 实战)

```yaml
# CLAUDE.md 中"派工前提铁律 12 + 类 20 累计"段必含:
类_20_W89_新增_9_条:
  - "类 20.60 axe SOP doc 必含 ≥ 5 规则 + 每规则 ≥ 3 段 + CI 段 + 留 W89+ 段 + e2e 门禁 (W89-P-12 沉淀)"
  - "类 20.61 Playwright 集成必含真跑 build:a11y + pre-commit + 3 件套联动 (W89-P-13 沉淀)"
  - "类 20.62 visual baseline 重 sync 必逐 spec + 统一 canonical project + 拍板 (W89-X-10 沉淀)"
  - "类 20.63 Playwright 软断言改硬门禁必 TEST_TOKEN 真注入 + throw if missing (W89-X-11 沉淀)"
  - "类 20.64 真 CI 触发必含 gh auth status + act 模拟 + 真部署文档化 (W89-X-12 沉淀)"
  - "类 20.65 19 vitest failed 调研必 4 类根因分类 + 修法优先级 + 不擅自修 (W89-X-13 沉淀)"
  - "类 20.66 vitest spec 必无 test.use() (playwright API), 描述 test.use 必在 playwright spec (W89-X-14 拦截沉淀)"
  - "类 20.67 WS/SSE/long-polling 页面必删 networkidle, 等明确 UI locator 或目标 API (W89-X-15 沉淀)"
  - "类 20.68 Playwright 真环境验证 v2 必含 6 步曲: docker ps 查重 + 12 services + a11y + visual + e2e + 真功能, 前置 npm install (W89-X-16 沉淀)"

# 派工 v6 §5 反馈类 20.82 沉淀 (派工 brief v4 升级必含):
类_20_82:
  - "派工 brief v4 升级必含 ≥ 9 铁律 + 实战举例 + CLAUDE.md 永久纪律"

# 累计更新:
派工前提铁律_12_+_类_20_累计: "36 (W87) → 45 (W89 第 1+2 批 + 9: 20.60-68)"
```

---

## 派工 brief v4 模板历史 (W68-W89)

- **v1**: W68 第 12 批 (派工 v3 段 3 alembic verify)
- **v2**: W68 第 13 批 (5 段 prompt 升级: alembic verify + PS 5.1 + plans 真验证)
- **v3**: W87 第 1 批 (W87-X-5 沉淀: 类 20.31/32 双锚定 + subagent fallback 路径 + base ref 实测 + 集成 e2e 一致性 + 类 20 沉淀必查)
- **v4**: W89 第 2 批 (X-27 沉淀: 类 20.60-68 新增 9 段 + 类 20.82 brief v4 升级必含 ≥ 9 铁律)

详见:
- `docs/w68-13th-batch-prompt-template-v4.md` (v1/v2 历史)
- `docs/w72-prompt-paradigm-v10-2026-07-27.md` (派工协调范式 v10)
- `memory/anchor-paradigm-21-day-validation-2026-07-22.md` (类 20 沉淀起点)
- `memory/w89-x27-brief-v4-2026-07-30.md` (本任务沉淀)
