# 移动端视觉回归测试

本目录包含 Playwright 视觉回归脚本，用于验证 PR #10 移动端深度定制效果。

## 文件

- `visual-regression.spec.mjs` — 14 个移动端路由的截图测试

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

视觉回归需要已登录状态。在测试前设置：

```bash
# 从浏览器 DevTools 获取 access_token
export TEST_TOKEN=eyJhbGc...
```

或在浏览器中登录后，从 localStorage 读取 `access_token` 设置。

### 4. 运行测试

```bash
cd web
npx playwright test tests/visual/mobile/visual-regression.spec.mjs --reporter=list
```

### 5. 截图输出

输出到 `tests/visual/mobile/screenshots/`：

```
screenshots/
├── 01-login.png
├── 02-dashboard.png
├── 03-chat.png
├── 04-tasks.png
├── 05-meetings.png
├── 06-knowledge.png
├── 07-projects.png
├── 08-project-stats.png
├── 09-members.png
├── 10-memory.png
├── 11-voiceprint.png
└── 12-settings.png
```

### 6. 截图对比

Playwright 默认不启用 toHaveScreenshot 对比。要启用 baseline 对比：

```js
await expect(page).toHaveScreenshot(`${route.name}.png`)
```

然后首次运行生成 baseline：
```bash
npx playwright test --update-snapshots
```

后续运行自动对比差异 > 0.1% 即失败。

## 检查清单

PR #10 完成后，对每个截图人工检查：

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