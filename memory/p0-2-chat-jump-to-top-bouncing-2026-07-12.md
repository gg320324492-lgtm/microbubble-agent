# P0-#2 chat-jump-to-top 按钮点击'来回跳动' v1~v4 五修收官 (2026-07-12)

> **触发**: 用户截图报 `chat-jump-to-top` 按钮 (↑ 滚回顶部) 在点击瞬间出现视觉跳动/抖动, 不符合预期
> **链路**: `web/src/views/ChatViewSSE.vue` 顶栏按钮 + 滚动事件触发 + EP (Element Plus) `<el-button>` active state
> **完整修复链**: v0 (用户报 bug) → v1 (CSS sticky) → v2 (sticky 修复) → v3 (visual feedback) → v4 (transform !important 防御) → audit trail

## 5 commits (全部 push origin/main)

| commit | 阶段 | 改动 | 行数 |
|--------|------|------|------|
| `0c1ed72c` | v0 → test | Playwright spec + 初始 screenshots audit trail | spec + 4 PNG |
| `494b2917` | v1 → v2 | sticky CSS 修 ↑ 按钮 scrollTop>0 被卷出可见 | 3 文件 |
| `c2b1e50a` | v2 → v3 | 修按钮点击'来回跳动'反馈 + test/spec/screenshot audit | spec + PNG |
| `da94ce74` | v3 → v4 | `transform: none !important` 防御 EP active transform | 1 文件 + dist |
| `43383798` | v4 → audit | 删除 6 PNG 仅保留 60fps 用户视角 spec | spec only |

## 4 轮根因分析 + 修法

### v1 (sticky CSS 修 ↑ 按钮 scrollTop>0 被卷出可见)

**根因**: `position: fixed` 按钮在用户向上滚动时如果 scrollTop 接近 0, 按钮会被滚出可见区域 → 点击不到
**修法**: 改 `position: sticky; bottom: 20px` + `align-self: flex-end` 容器布局, 让按钮始终在 messages 容器的右下角
**效果**: 按钮永远在视口右下角, scrollTop 不影响可见性

### v2 (修按钮点击'来回跳动'反馈)

**根因**: EP `<el-button>` 默认 active 状态下 transform 会变化, 用户快速点击时按钮会有 1-2px 位移 → "跳动"反馈
**修法**: 给按钮加 CSS `&:active { transform: none; }` + `transition: none` 在点击瞬间禁用动画

### v3 (60fps 用户视角验证)

**测试**: Playwright `p0-2-real-user-flow.spec.mjs` + `p0-2-button-bouncing.spec.mjs` + `p0-2-final-verify.spec.mjs` + `p0-2-jump-to-top.spec.mjs` (4 个 spec) 在真实用户视角下记录 60fps 采样 rect 变化
**结果**: v2 修复后大部分 case 通过, 但仍有 1-2 个 pixel 抖动在 hover → active 切换瞬间

### v4 (transform: none !important 防御 EP active transform)

**根因**: EP `<el-button>` active state 应用了 transform (`scale(0.98)` 类似效果), `:active` selector specificity 不够, 被 EP 内部样式覆盖
**修法**: `transform: none !important; transition: none !important;` 强制禁用 EP 内置 transform, 加 `!important` 提升 specificity
**效果**: 完全消除点击瞬间抖动, 按钮 click 反馈纯靠颜色 + 边框变化

## v4 final 验证 (`p0-2-bounce-recv2.spec.mjs` 60fps 采样)

新增 spec 146 行, 4 段测试:
- **Test 1**: 鼠标从远处移到按钮上方 (12×50ms 采样), 验证 hover 进入过程 rect 稳定
- **Test 2**: 鼠标 hover 在按钮上 (10×30ms 采样), transform 字段监控
- **Test 3**: 真实 click (mouse.down + 12×16ms = 60fps 采样), 输出 btnY/scrollTop/transform/display/active 全维度, **delta > 4px 报跳动**
- **Test 4**: 全场景汇总 (y 值 min/max/delta)

结果: v4 修复后 **delta = 0px** ✅, 按钮 y 位置完全稳定

## 5 新铁律 (永久沉淀)

1. **position: sticky 优于 fixed** — 滚动容器内的浮动按钮永远用 sticky + 容器布局, 不要 fixed + 视口定位 (滚动视口变化 fixed 按钮会被卷走)
2. **EP `<el-button>` 默认 active transform 必须显式禁用** — 用 `transform: none !important; transition: none !important;` 强制覆盖
3. **60fps 验证优于静态截图** — Playwright spec 必须 mouse.down + 16ms 间隔采样才能捕获瞬间抖动, 静态截图看不出
4. **`!important` 不是 anti-pattern, 是 specific battle 工具** — 当第三方 UI 库样式 specificity 比你高, `!important` 是唯一可靠手段, 不要为了"代码洁癖"放弃
5. **visual bug 修复必须 audit trail** — 每次修复都留 Playwright spec + delta 阈值, 未来回归测试可重跑验证 (本案例 delta > 4px 报失败)

## 端到端验证清单

- [x] 4 个 Playwright spec (real-user-flow / button-bouncing / final-verify / jump-to-top)
- [x] 1 个 60fps 用户视角 spec (`p0-2-bounce-recv2.spec.mjs`)
- [x] 5 个 commit 全部 push origin/main
- [x] v4 修复后 delta = 0px
- [x] 用户实测无视觉跳动

## 后续 follow-up (留给 admin 决策)

- [ ] 归档 `p0-2-*.spec.mjs` 6 个文件 → 未来 v# 重构时再清理
- [ ] 加 60fps 抖动阈值到 CI 防御 (本案例手测 delta, 未来 regression test 自动化)
- [ ] 其他 EP `<el-button>` 用法审查 (项目有 50+ 处 el-button 是否都有相同 transform 问题?)

## 关联 memory

- `memory/session-load-server-fetch-fallback-2026-07-12.md` (P0-#1.6 v1)
- `memory/ensure-session-loaded-cache-hit-orphan-2026-07-12.md` (P0-#1.6 v2)
- `memory/anthropic-msg-dict-wrapper-mimo-reasoning-content-2026-07-12.md` (P0-#1.5)
- `memory/llm-backend-ollama-residual-connection-error-2026-07-12.md` (P0-#1)
- `memory/playwright-screenshot-cleanup-2026-07-12.md` (PNG 清理, 同日)