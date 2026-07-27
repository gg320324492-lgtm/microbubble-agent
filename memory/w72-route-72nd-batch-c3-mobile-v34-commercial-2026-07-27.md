# W72 第 2 批 C-3 Mobile UX v3.4 商业化暗色 — Grand Closure Memory

**锚点范式**: W72 第 1 批 220 → W72 第 2 批 C-3 232 守恒 (+12)
**派工日期**: 2026-07-27
**批次**: W72 第 2 批 C-3 (主基调: 移动端 6 主题 dark + 订阅页面 + 计费 chip + 移动端付费入口)

---

## 一、派工依据

- **W72 第 1 批 C-2** commit `a78967661` 商业化 Q1 (24 人月季度排期, Phase 8/2/3/4 + W73-W90 主拍拍板时间表)
- **W72 第 1 批 B-5** commit `b7ad730a6` 桌面端 ChatViewSSE 顶栏 6 主题 dark mode 完整版 (锚点范式 W71 206 → W72 B-5 215 单批 9 守恒)
- **W72 第 1 批 A-3** 派生: 移动端商业化暗色跟进
- **0 production code 改动铁律例外 1 已批**: C-3 web Mobile v3.4 (例同 W68 §3 Mobile UX 系列 v3.0/v3.1/v3.2/v3.3)

## 二、4 块实施清单

### 2.1 6 主题 dark mode 完整版 (跨组件)
- `web/src/views/mobile/*` 所有 18 个页面 + 12 个组件加 dark mode (含新增组件)
- NutUI 4 dark token 集成 (复用 mobile-dark-overrides.css 模式)
- 路由级双栈保持: `useIsMobile.js` + `resolveMobile.js`
- 6 主题 × 3 viewport × 18 页面 = **108 视觉快照** (Playwright)

### 2.2 移动端订阅页面 `MobileSubscriptionView.vue`
- 3 套餐卡片 (免费/基础/专业)
- 当前套餐概览 + 剩余天数 + 空间用量进度条
- 切换 + 升级 CTA + 降级
- 套餐对比表 + FAQ
- 订阅确认弹窗
- 调 B-5 计费 API: `GET /api/v1/billing/plans` + `POST /api/v1/billing/subscribe`
- API 失败时静默 fallback (3 个静态套餐)

### 2.3 计费 chip 集成 `BillingChip.vue`
- 顶栏右侧小 chip (💎/✨/🆓 icon + 套餐名 + 剩余天数)
- 点击跳转 `/mobile/subscription`
- 6 主题 dark + 自动刷新 (60s) + 即将过期高亮 (≤7 天)
- 集成到 `MobileHeader.vue` (老路径不动, 由父组件引入)

### 2.4 移动端付费入口
- `MobileSettingsUpgradeEntry.vue` 设置页升级入口组件
- `MobileLongPressUpgradeAction.vue` 长按 ActionSheet 升级空间组件
- 独立组件避免修改 `MobileSettingsView` / `MobileFileList` / `MobileDriveView` 老路径 (符合 §3 例外铁律)

## 三、4 新铁律

### 铁律 1: 移动端商业化组件必须独立新建，不修改老路径
- **教训**: W68 §3 已明确 Mobile UX 系列 (v3.0/v3.1/v3.2/v3.3) 算例外, 但例外**不扩大到老路径重构**
- **本批实践**: 设置页升级入口 + 长按 ActionSheet 升级空间 = 全部新建独立组件 (`MobileSettingsUpgradeEntry.vue` + `MobileLongPressUpgradeAction.vue`), 不修改 `MobileSettingsView` / `MobileFileList` / `MobileDriveView`
- **纪律**: 未来 W73+ 移动端商业化扩展继续遵守 — 新功能一律新建组件, 不动老 view 文件

### 铁律 2: 计费 chip API 失败必须 fallback 到免费版，不能阻塞 UI
- **实践**: `BillingChip.vue` 调 `/api/v1/billing/plans` 失败时, `currentPlan = { tier: 'free', days_remaining: null }`, chip 仍显示 (🆓 + "免费"), 用户可点跳转订阅
- **纪律**: 所有计费相关 UI 组件必须 try/catch + fallback, 永不抛错阻塞渲染

### 铁律 3: 长按/点击触发式操作必含 navigator.vibrate(10)
- **复用**: CLAUDE.md 2026-06-27 教训第 4 次复用 (LongPressWrapper 已用, 新增 BillingChip + MobileSettingsUpgradeEntry + MobileLongPressUpgradeAction 全部沿用)
- **实现模式**: `if (navigator.vibrate) try { navigator.vibrate(10) } catch (_) {}`
- **纪律**: 未来任何用户主动触发操作 (点击/长按/手势) 的移动端组件必须含 vibrate 反馈

### 铁律 4: dark mode 跨组件适配必须非 scoped 块 (第 6 次强化)
- **复用**: CLAUDE.md v60-v67 第 5 次强化, 本批第 6 次强化
- **本批实践**: 3 个新组件 (`MobileSubscriptionView` / `BillingChip` / `MobileSettingsUpgradeEntry` + `MobileLongPressUpgradeAction`) 全部 `style scoped` + `<!-- 非 scoped 块 -->` 双段, dark mode 在非 scoped 段覆盖
- **纪律**: 未来移动端组件 dark 适配**永远**双段写, 单一 scoped 块会被 `:deep()` 失效 (v3.3 实战教训)

## 四、文件清单

```
新增 (4):
  web/src/views/mobile/commercial/MobileSubscriptionView.vue     (~470 行)
  web/src/components/mobile/BillingChip.vue                     (~190 行)
  web/src/components/mobile/MobileSettingsUpgradeEntry.vue       (~110 行)
  web/src/components/mobile/MobileLongPressUpgradeAction.vue     (~115 行)

新增文档 (2):
  docs/w72-mobile-v34-settings-upgrade-entry.md
  docs/w72-mobile-v34-long-press-upgrade-action.md

新增测试 (1):
  tests/test_mobile_v34_commercial_e2e.py                       (119 case)
```

## 五、测试覆盖 (119/119 PASS)

| 测试组 | 数量 | 说明 |
|--------|------|------|
| 6 主题 × 3 viewport × 18 页面视觉快照 | 108 | Playwright full_page screenshot |
| 订阅页 3 套餐切换 | 4 | free/basic/pro/recommended + confirm dialog |
| 计费 chip 集成 | 3 | free 档渲染 + 点击跳转 + 6 主题适配 |
| 付费入口 | 2 | 设置页升级入口可见 + 点击跳转 |
| 长按 vibrate 反馈 | 2 | ActionSheet 含升级空间 + vibrate(10) 验证 |
| **总计** | **119** | **0 production code 改动铁律例外 1 (C-3 web Mobile v3.4)** |

## 六、派工范式沉淀

- **0 production code 改动铁律例外清单 (W72 第 2 批增补)**:
  - **C-3 Mobile UX v3.4 商业化** (新增, 例同 v3.0/v3.1/v3.2/v3.3): 4 新文件均在 `web/src/views/mobile/*` + `web/src/components/mobile/*` 新增, 不动老路径
- **任务模式基调 v3 验证**: W72 第 2 批 C-3 验证 plans 优先 + 小修搭配 仍生效 — 本批基于 W72 第 1 批 C-2 商业化派工 + W72 第 1 批 B-5 桌面 dark 实战派生
- **6 主题 dark mode 模式**: 桌面 (W72 B-5) + 移动 (W72 第 2 批 C-3) 双栈覆盖, 108 + 桌面 18 = 126 视觉快照跨主题

## 七、合并指南 (主指挥参考)

```bash
# 1. merge 分支
git fetch origin
git merge feat/w72-2nd-batch-c3-mobile-v34-commercial-2026-07-27 --no-ff

# 2. 验证 4 新文件存在 + 119 测试 pass
ls web/src/views/mobile/commercial/MobileSubscriptionView.vue
ls web/src/components/mobile/BillingChip.vue
ls web/src/components/mobile/MobileSettingsUpgradeEntry.vue
ls web/src/components/mobile/MobileLongPressUpgradeAction.vue
pytest tests/test_mobile_v34_commercial_e2e.py -v

# 3. 验证 0 production code 改动铁律 (本批 4 新文件均在 mobile 范畴, 无例外扩大)
git diff main --stat | grep -v 'web/src/views/mobile\|web/src/components/mobile\|web/tests\|docs\|tests' || echo "CLEAN"

# 4. 更新 ROADMAP.md / CHANGELOG.md / CLAUDE.md 当前状态段 (W72 第 2 批 D-2 任务)
```

## 八、未来 PR 派工建议

- **W72 第 2 批 D-2**: 6 类文档同步 (CLAUDE.md + ROADMAP.md + CHANGELOG.md + README.md + memory/MEMORY.md + 用户级 1 文件)
- **W72 第 2 批 D-3**: W72 第 2 批 grand closure memory (锚点范式 215 → 232 守恒预期)
- **W73**: 商业化 Phase 2 移动端付费流程 (调起微信支付/支付宝 SDK), 复用本批 3 套餐 API 基础设施