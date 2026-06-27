# 移动端视觉回归测试

本目录包含 Playwright 视觉回归脚本，用于验证移动端页面 dark mode + 主题切换 + 关键页面的视觉一致性。

## 当前状态（v77 P2.6-C）

**6 路由核心覆盖**（与 desktop spec 对齐）：

| # | 路由 | 组件 | 优先级 |
|---|---|---|---|
| 1 | `/dashboard` | MobileDashboard | 核心 |
| 2 | `/chat` | MobileChatView | 核心 |
| 3 | `/knowledge` | MobileKnowledgeView | 核心 |
| 4 | `/tasks` | MobileTaskView | 中高频（v77 P2.6-C 新增） |
| 5 | `/meetings` | MobileMeetingView | 中高频（v77 P2.6-C 新增） |
| 6 | `/settings` | MobileSettingsView | 中高频（v77 P2.6-C 新增） |

**历史演进**：
- **PR #10**（2026-06-13 早期）：14 路由覆盖（README 当时写"12 张截图"但 spec 实际更广）
- **v76.2**（2026-06-26）：从 14 路由收窄到 3 路由（baseline 维护成本失控）
- **v77 P2.6-C**（2026-06-28）：扩展到 6 路由，与 desktop 对齐；修复登录态双注入 bug（之前 3 张 baseline 字节数完全相同 = 登录页）

## 文件

- `visual-regression.spec.mjs` — 6 个移动端路由的截图测试
- `visual-regression.spec.mjs-snapshots/` — baseline PNG（git tracked，正常 `git add`）

## 使用方法

### 1. 安装 Playwright（首次）

```bash
cd web
npm install --save-dev @playwright/test
npx playwright install chromium
```

### 2. 启动应用

需要让 Web 应用在 `localhost:3000` 或 `BASE_URL` 环境变量指定的地址可访问：

```bash
# 方式 A：本地开发服务器
cd web && npm run dev

# 方式 B：远程测试环境
export BASE_URL=https://test.agent.mnb-lab.cn
```

### 3. 注入登录态（避免重定向）

视觉回归需要已登录状态。**v77 P2.6-C 关键**：必须注入真实 JWT token（mock-token 不被后端认可，baseline 拍到 401/empty 页）。

```bash
# 从浏览器 DevTools Application → Cookies → access_token 取值
export TEST_TOKEN=eyJhbGc...
```

> **登录态双注入机制**（v77 P2.6-C 修复）：
> - **Cookie 注入**：兼容 axios withCredentials 的后端 API
> - **localStorage 注入**：router 守卫读 `localStorage.getItem('access_token')` 校验，未注入会重定向 /login
>
> 仅 cookie 注入会导致 baseline 拍到登录页（历史踩坑：3 张旧 baseline 字节数完全相同）。

### 4. 运行测试

```bash
cd web

# 对比模式（基线已存在）
TEST_TOKEN=<jwt> npx playwright test tests/visual/mobile/visual-regression.spec.mjs --project=mobile-iphone14

# 更新基线（仅在确认视觉变更符合预期时）
TEST_TOKEN=<jwt> npx playwright test tests/visual/mobile/visual-regression.spec.mjs --project=mobile-iphone14 --update-snapshots

# 仅对比不写
TEST_TOKEN=<jwt> npx playwright test tests/visual/mobile/visual-regression.spec.mjs --project=mobile-iphone14 --reporter=list
```

### 5. baseline 截图输出

输出到 `tests/visual/mobile/visual-regression.spec.mjs-snapshots/`：

```
01-dashboard-mobile-iphone14-linux.png      (~200KB / 真实数据)
03-chat-mobile-iphone14-linux.png           (~200KB / 真实数据)
04-tasks-mobile-iphone14-linux.png          (v77 P2.6-C 新增)
05-meetings-mobile-iphone14-linux.png       (v77 P2.6-C 新增)
06-knowledge-mobile-iphone14-linux.png      (~200KB / 真实数据)
07-settings-mobile-iphone14-linux.png       (v77 P2.6-C 新增)
```

**后缀说明**：
- 本地 Windows 跑出来是 `-win32.png`
- CI Linux runner 会自动重写为 `-linux.png`
- 接受 v76 教训：本地 commit baseline，CI 会重写后缀

### 6. 视觉差异阈值

`playwright.config.js` 配置 `maxDiffPixelRatio: 0.002`（0.2%）—— anti-aliasing / 字体 sub-pixel 渲染抖动会有微小差异，0.2% 是平衡点。

## 检查清单

每次 PR 视觉回归失败时人工检查：

- [ ] 无横向滚动条
- [ ] 触觉目标 ≥ 44px
- [ ] Safe Area 正确（底部 TabBar 不被 Home Indicator 遮挡）
- [ ] 文字 ≥ 14px 可读
- [ ] 暗色模式颜色对比度足够
- [ ] CardList 卡片间距合理
- [ ] 底部 Sheet 不被 TabBar 遮挡
- [ ] 长按手势可触发 ActionSheet
- [ ] 录音 FAB 安全区适配
- [ ] ECharts 双指缩放工作
- [ ] 离线时显示 offline.html

## 关键纪律

1. **登录态必须真实 JWT**（mock-token 不被后端认可，baseline 拍到 401 页面）
2. **baseline 必须 commit**（git add 即可，snapshots 目录不在 .gitignore）
3. **不要手动编辑 baseline PNG**（必须用 `--update-snapshots` 重生成）
4. **不要本地 + CI 双向 commit baseline**（本地 Windows 跑 commit，CI Linux runner 会自动重写 `-linux.png` 后缀）
5. **视觉差异阈值 0.2%**（playwright.config.js 配置）