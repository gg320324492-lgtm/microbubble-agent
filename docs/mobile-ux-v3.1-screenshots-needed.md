# Mobile UX v3.1 截图需求清单 (TODO Real Screenshots)

> **版本**: v3.1
> **日期**: 2026-07-24
> **作者**: W68 第 4 批 Mobile UX v3.1 ASCII 截图替换 Agent
> **对应**: `docs/mobile-ux-v3.1-user-guide.md` 中的 8 个 "TODO 截图" 占位 + 引用编号 S1 ~ S8
> **目的**: 主指挥或未来 PR 用 Playwright/Puppeteer/真机截图替换 ASCII 占位时, 按本清单执行

---

## 目录

1. [§1 语音输入按钮 (3 态) — S1-a ~ S1-c](#1-语音输入按钮-3-态)
2. [§2 ASR 引擎选择弹窗 — S2](#2-asr-引擎选择弹窗)
3. [§3 手势滑动阴影 — S3-a ~ S3-c](#3-手势滑动阴影)
4. [§4 下拉刷新图标 — S4-a ~ S4-c](#4-下拉刷新图标)
5. [§5 PWA 添加主屏弹窗 — S5-a ~ S5-e](#5-pwa-添加主屏弹窗)
6. [§6 iOS Safari 兼容性问题 — S6-a ~ S6-c](#6-ios-safari-兼容性问题)
7. [§7 Android Chrome PWA 安装 — S7-a ~ S7-b](#7-android-chrome-pwa-安装)
8. [§8 FAQ 真实场景 — S8-a ~ S8-l](#8-faq-真实场景)

---

## §0 通用约定

| 维度 | 规范 |
|------|------|
| **截图格式** | PNG (无损) / 失真允许时 WebP |
| **截图命名** | `mobile-ux-v3.1-s{N}-{device}-{viewport}-{state}.png` (e.g. `mobile-ux-v3.1-s1-iphone-14-pro-393x852-idle.png`) |
| **存储路径** | `docs/screenshots/mobile-v3.1/` (新建子目录) |
| **图床上传** | Aliyun OSS (与现有 docs 截图同 bucket) |
| **分辨率** | 1x device pixel ratio (避免 3x 大文件); Retina 设备截图存原图 |
| **尺寸标准** | iOS 393x852 (iPhone 14 Pro) / iOS 375x812 (iPhone X) / Android 360x800 (Pixel 5) / Android 412x915 (Pixel 7) |
| **主题** | 浅色 + 暗色各一份 (12 张图 × 2 = 24 张) |
| **状态标识** | 截图右下角加 `mockup-v3.1` 半透明水印 (避免截图被误用为真实界面) |

### Playwright 伪代码模板

```js
// scripts/capture-mobile-screenshots.js
const { chromium, devices } = require('playwright');
const fs = require('fs');

(async () => {
  const browser = await chromium.launch();
  for (const device of ['iPhone 14 Pro', 'Pixel 7']) {
    for (const theme of ['light', 'dark']) {
      const context = await browser.newContext({
        ...devices[device],
        colorScheme: theme,
        isMobile: true,
        hasTouch: true,
      });
      const page = await context.newPage();
      await page.goto('https://microbubble.xx/mobile/chat');
      // ... 每个截图的具体动作
      await page.screenshot({ path: `docs/screenshots/mobile-v3.1/s1-${device}-${theme}-recording.png` });
    }
  }
  await browser.close();
})();
```

### 工具脚本依赖

```bash
# 安装
npm install playwright --save-dev
npx playwright install chromium
npx playwright install firefox

# 跑
node scripts/capture-mobile-screenshots.js

# 验证
ls -la docs/screenshots/mobile-v3.1/ | head -30
```

---

## §1 语音输入按钮 (3 态)

**引用**: `mobile-ux-v3.1-user-guide.md §1.1 图 1-1`

### S1-a: idle 状态

| 项目 | 值 |
|------|-----|
| **设备** | iPhone 14 Pro (iOS 17.5) Safari standalone + Pixel 7 (Android 14) Chrome |
| **viewport** | 393x852 + 412x915 |
| **页面** | MobileChatView (移动端聊天主页) |
| **触发** | 默认进入页面, 未长按 🎤 |
| **期望画面** | 输入框右侧灰色实心话筒图标 🎤 + 输入框为空 + 顶部 tab 栏 "Dashboard / Task / Knowledge / Workspace" |
| **触觉反馈** | 无 |
| **必须含元素** | (1) 灰色话筒图标 #666 (2) 输入框 placeholder "输入消息..." (3) 底部键盘提示 |
| **避免** | 误让用户以为是录音中 (图标**不可**变红) |

### S1-b: recording 状态

| 项目 | 值 |
|------|-----|
| **设备** | 同 S1-a |
| **viewport** | 同 S1-a |
| **页面** | MobileChatView |
| **触发动作** | Playwright `page.touchscreen.tap(370, 800, { delay: 500 })` 模拟长按 0.5s; 或 `page.evaluate(() => dispatchEvent(touchstart, touchend))` |
| **期望画面** | 红色脉冲圈包住话筒 + 实时波形 (▁▃▅▇▅▃ 滚动) + 计时器 "00:03" + 输入框上方"↑ 上滑松手取消"提示 |
| **触觉反馈** | 触发后 `tap` (10ms) 一次 |
| **必须含元素** | (1) 红色脉冲圈 (2) 实时波形 ≥ 5 个波峰 (3) 计时器 (4) 取消提示文字 |
| **避免** | 波形静止 (要滚动感) / 计时器不显示 |

### S1-c: cancelling 状态

| 项目 | 值 |
|------|-----|
| **设备** | 同 S1-a |
| **viewport** | 同 S1-a |
| **页面** | MobileChatView |
| **触发** | 在 S1-b 状态基础上, 模拟 `touchmove` 上滑 80px |
| **期望画面** | 输入框上方 "松手取消" 气泡变红 + 录音图标淡灰 (透明度 0.5) + 波形停止更新 |
| **触觉反馈** | `warning [30, 50, 30]` |
| **必须含元素** | (1) 红色气泡 (2) 淡灰话筒 (3) 静态波形 (最后一帧) |

---

## §2 ASR 引擎选择弹窗

**引用**: `mobile-ux-v3.1-user-guide.md §1.5`

### S2: ASR 引擎降级弹窗 (debug 模式)

| 项目 | 值 |
|------|-----|
| **设备** | iPhone 14 Pro / Pixel 7 |
| **viewport** | 393x852 / 412x915 |
| **页面** | MobileChatView → 设置 → 高级 → ASR 引擎 (debug 模式开启) |
| **触发** | 录音 1 次 → SenseVoice 失败 → 弹降级弹窗 |
| **期望画面** | 弹窗中央: "ASR 引擎降级" 标题 + 3 个引擎单选 (SenseVoice / faster-whisper / Paraformer) + 当前选中状态 (高亮) + [确认] [取消] |
| **必须含元素** | (1) 弹窗遮罩 (黑色 60% 透明) (2) 3 个引擎选项 (3) 选中的引擎对号 ✅ (4) 错误提示 "SenseVoice 服务暂不可用, 自动切换?" |
| **避免** | 普通用户进入看不到此弹窗 (debug 模式才显示) |
| **截图标注** | 弹窗标题下方加小字 "(仅 debug 模式可见)" |

> **注**: 用户指南 §1.5 中提及的 "ASR 引擎选择" 指的就是这个 debug 弹窗, 普通用户**自动**降级, 不弹窗。

---

## §3 手势滑动阴影

**引用**: `mobile-ux-v3.1-user-guide.md §2.1 图 2-1`

### S3-a: 滑到 30px (未达 50px 阈值) — 回弹后状态

| 项目 | 值 |
|------|-----|
| **设备** | iPhone 14 Pro Safari standalone |
| **viewport** | 393x852 |
| **页面** | MobileTabView 根页面 (4 个 Tab 中的 Dashboard) |
| **触发** | `touchstart` + `touchmove` 横移 30px + `touchend` |
| **期望画面** | Dashboard 页面正常显示 (因为未达阈值, 已回弹到原位置), 但截图中**保留尾迹**: 可见 `transform: translateX(-30px)` 的 0.3 帧 |
| **必须含元素** | (1) 完整 Dashboard 卡片 (2) 顶部 tab 栏 (3) 实时 transform 状态 |
| **截图技巧** | 用 `requestAnimationFrame` + 手动暂停 50ms 后截图 |

### S3-b: 滑到 60px (已过 50px 阈值) — 拖动中

| 项目 | 值 |
|------|-----|
| **设备** | 同 S3-a |
| **viewport** | 同 S3-a |
| **页面** | MobileTabView Dashboard |
| **触发** | `touchstart` + `touchmove` 横移 60px + **不松手**, 立即截图 |
| **期望画面** | Dashboard 向左平移 60px (transform translateX(-60px)) + 透明度 0.5 + 目标 Task 页从屏幕右侧 50% 处进入 + 顶部 tab "Task" 高亮 (珊瑚橙) |
| **必须含元素** | (1) Dashboard 半透明 (2) Task 页从右侧挤入 (3) tab 栏 Task 高亮 (4) 触觉 tap 触发 |
| **截图技巧** | 用 `page.mouse.down()` + `page.mouse.move()` 不调 `mouse.up()` 直接截图 |

### S3-c: 滑到 60px 后松手 — 切换完成

| 项目 | 值 |
|------|-----|
| **设备** | 同 S3-a |
| **viewport** | 同 S3-a |
| **页面** | MobileTabView 已切换到 Task 页面 |
| **触发** | S3-b 基础上 `touchend` |
| **期望画面** | Task 页面完全显示, Dashboard 消失 + 顶部 tab "Task" 高亮 + 切换动画完成的稳定状态 |
| **必须含元素** | (1) 完整 Task 页面 (2) tab 栏稳定状态 |

---

## §4 下拉刷新图标

**引用**: `mobile-ux-v3.1-user-guide.md §2.2 图 2-2`

### S4-a: 阶段 1 (0~50px)

| 项目 | 值 |
|------|-----|
| **设备** | iPhone 14 Pro |
| **viewport** | 393x852 |
| **页面** | MobileTabView Dashboard |
| **触发** | `touchstart` 屏幕顶部 y=50 + `touchmove` 下拉 30px |
| **期望画面** | 顶部状态栏 (y=0~30) 显示 "↓ 下拉刷新" 灰色文字 + 灰色 🔄 静止图标 (向上箭头朝下) + 灰色主页面内容 |
| **必须含元素** | (1) "↓ 下拉刷新" 文字 #666 (2) 🔄 16px (3) 主页面内容 70% 不透明 (4) 顶部状态栏背景透明 |

### S4-b: 阶段 2 (50~80px)

| 项目 | 值 |
|------|-----|
| **设备** | 同 S4-a |
| **viewport** | 同 S4-a |
| **页面** | 同 S4-a |
| **触发** | 同 S4-a 但下拉 65px |
| **期望画面** | 顶部状态栏 "↑ 松手刷新" 主色文字 + 🔄 半旋转 (90° 朝上) 20px 大小 + 主页面内容 50% 不透明 |
| **必须含元素** | (1) "↑ 松手刷新" 文字 #FF7A5C (2) 🔄 旋转 90° (3) 主页面被拉下 ~65px |

### S4-c: 阶段 3 (≥80px + 松手)

| 项目 | 值 |
|------|-----|
| **设备** | 同 S4-a |
| **viewport** | 同 S4-a |
| **页面** | 同 S4-a |
| **触发** | 同 S4-a 但下拉 100px + 松手 500ms 内截图 |
| **期望画面** | 顶部状态栏 "⏳ 正在刷新..." 主色文字 + ⏳ 旋转 spinner + 主页面稳定在 80px 下移位置 |
| **必须含元素** | (1) "⏳ 正在刷新..." 文字 (2) spinner 持续旋转 (3) 主页面下方有新数据 placeholder |
| **避免** | spinner 静止 (要 CSS 动画) |

---

## §5 PWA 添加主屏弹窗

**引用**: `mobile-ux-v3.1-user-guide.md §3.1 图 3-1`

### S5-a: Safari 打开页面 (非 standalone)

| 项目 | 值 |
|------|-----|
| **设备** | iPhone 14 Pro Safari (tab 模式, **非** standalone) |
| **viewport** | 393x852 |
| **页面** | 小气助手桌面端首页 (因 Safari 显示桌面优先; 可在 user-agent 强制 mobile) |
| **触发** | 在 iOS Safari 地址栏输入 URL → 进入页面 |
| **期望画面** | 浏览器 tab 模式 + 顶部 Safari 地址栏 + iOS 状态栏 + 主页面内容 + 底部 Safari 工具栏 |
| **必须含元素** | (1) Safari 地址栏 (2) iOS 状态栏 (3) 浏览器工具栏 (分享按钮 📤) (4) v3.0 PWA install banner (底部横幅) |

### S5-b: Safari 分享面板弹出

| 项目 | 值 |
|------|-----|
| **设备** | 同 S5-a |
| **viewport** | 同 S5-a |
| **页面** | 同 S5-a |
| **触发** | 点击底部分享按钮 📤 |
| **期望画面** | 系统级分享面板从底部弹出 + 列 8 个图标 (微信/邮件/添加到主屏幕/打印等) |
| **必须含元素** | (1) 分享面板遮罩 (黑色 60% 透明) (2) "添加到主屏幕" 图标 (黄色 + 加号) (3) 取消按钮 |

### S5-c: "添加到主屏幕" 按钮位置

| 项目 | 值 |
|------|-----|
| **设备** | 同 S5-a |
| **viewport** | 同 S5-a |
| **页面** | 同 S5-a |
| **触发** | 在 S5-b 状态下, 滑动找到 "添加到主屏幕" |
| **期望画面** | 同 S5-b, 但**用箭头或红框**标注出 "添加到主屏幕" 按钮位置 (用户指南用, 加标注) |

### S5-d: 名称确认模态

| 项目 | 值 |
|------|-----|
| **设备** | 同 S5-a |
| **viewport** | 同 S5-a |
| **页面** | 同 S5-a |
| **触发** | 点 S5-c 的 "添加到主屏幕" |
| **期望画面** | 顶部模态: "添加网页到主屏幕" 标题 + 网站图标预览 + 名称输入框 (默认 "小气助手") + [取消] + [添加] (右上角主色) |
| **必须含元素** | (1) 标题 (2) 图标 (3) 名称输入框 (4) 两按钮 |

### S5-e: 主屏图标 + standalone 启动

| 项目 | 值 |
|------|-----|
| **设备** | 同 S5-a |
| **viewport** | iOS 主屏 → 启动 standalone |
| **页面** | 主屏 → 小气助手 PWA standalone 启动 |
| **触发** | 主屏点击图标 → app 启动 (无 Safari chrome) |
| **期望画面** | 两张合成图: (左) iOS 主屏, 显示 "小气助手" 图标 (彩色 logo) 在 app 列表中; (右) standalone PWA 启动, 全屏无 Safari chrome + iOS 状态栏 + 主页面内容 + theme-color 主色顶栏 |
| **必须含元素** | (1) 彩色图标 (2) standalone 模式无 chrome (3) theme-color 顶栏 |

---

## §6 iOS Safari 兼容性问题

**引用**: `mobile-ux-v3.1-user-guide.md §3.4`

### S6-a: iOS < 15.4 `100dvh` 不识别 → 出现滚动条 bug

| 项目 | 值 |
|------|-----|
| **设备** | iPhone 8 (iOS 15.0) Safari |
| **viewport** | 375x667 |
| **页面** | MobileChatView |
| **触发** | 进入页面, polyfill 失效场景 |
| **期望画面** | 主页面下方出现"幽灵滚动条" + 内容错位 (这是 bug 截图, 用于 issue 报告) |
| **必须含元素** | (1) 滚动条 (2) 错位的主页面 (3) 右下角水印 "BUG: iOS < 15.4 100dvh issue" |

### S6-b: iOS < 14.5 麦克风权限每次重弹

| 项目 | 值 |
|------|-----|
| **设备** | iPhone XR (iOS 14.0) Safari tab 模式 |
| **viewport** | 414x896 |
| **页面** | MobileChatView |
| **触发** | 第 2 次长按 🎤 (应该每次都弹) |
| **期望画面** | 原生权限弹窗: "允许 'microbubble.xx' 使用麦克风?" |
| **必须含元素** | (1) 系统弹窗 (2) 允许 / 不允许 按钮 |

### S6-c: iOS 14-15 `backdrop-filter` 性能卡顿

| 项目 | 值 |
|------|-----|
| **设备** | iPhone 11 (iOS 15.0) Safari |
| **viewport** | 414x896 |
| **页面** | MobileCommandPalette (有 backdrop-filter 模糊) |
| **触发** | 打开命令面板 + 上滑滚动 |
| **期望画面** | 命令面板背景半透明 (替代模糊) + 内容仍可见 + 右下角 "FPS: 30-45" 标注 (性能问题截图) |
| **避免** | 模糊背景 (刻意用半透明代替, 演示降级) |

---

## §7 Android Chrome PWA 安装

**引用**: `mobile-ux-v3.1-user-guide.md §4.1 图 4-1`

### S7-a: Android 系统级 PWA 安装弹窗

| 项目 | 值 |
|------|-----|
| **设备** | Pixel 7 (Android 14) Chrome |
| **viewport** | 412x915 |
| **页面** | 小气助手首页 (满足 5 个条件后) |
| **触发** | 调用 `promptEvent.prompt()` |
| **期望画面** | 系统级底部弹窗: "📥 是否安装 '小气助手' 到设备?" + 网站信息 + [✕] [安装] [取消] 三个按钮 |
| **必须含元素** | (1) 弹窗标题 (2) 来源 URL (3) 图标预览 (4) 三按钮 |

### S7-b: 我们的 PWA install banner (v3.0 自定义)

| 项目 | 值 |
|------|-----|
| **设备** | 同 S7-a |
| **viewport** | 同 S7-a |
| **页面** | 小气助手首页 |
| **触发** | 用户活跃 + 7 天未 dismiss |
| **期望画面** | 底部自定义横幅 (6 列高度, 主题色背景) + 文案 "📲 将小气助手添加到主屏, 获取完整体验" + [安装] [暂不] 按钮 |
| **必须含元素** | (1) 主题色背景 (2) 标题文字 (3) 两个主按钮 (4) 关闭按钮 |

---

## §8 FAQ 真实场景

**引用**: `mobile-ux-v3.1-user-guide.md §5`

> 12 个 FAQ 对应 12 张真实场景截图 (来自"小气助手内测"微信群, 7 天真实用户提问, 已脱敏):

### S8-a: Q1 录音转写错字 (食堂噪声)
**画面**: 用户输入框含 "问一下老王的尾纳米气泡实验数据" + 上方 "🔴 录音中 (3.2s)" 状态 + "↑ 上滑松手取消" 提示
**关键元素**: "尾" 错字高亮 + 输入框可编辑光标位置

### S8-b: Q1 进阶 - 中英混说 (实验室术语)
**画面**: 错误转写 "请帮我算 H2SO4 的摩尔浓度" → 错为 "请帮我算 H2SO4 的摸耳浓度"
**关键元素**: "摩尔" 错字标红 + 重录按钮

### S8-c: Q2 iOS 无震动反馈的视觉替代
**画面**: iPhone 上长按 🎤 → 颜色从 灰→红 渐变过程 (3 帧拼图或 GIF)
**关键元素**: 颜色变化 + 计时器出现

### S8-d: Q3 下拉刷新在 iOS Safari tab 模式被拦截
**画面**: iPhone Safari tab 模式下拉 → 浏览器原生刷新页面 (URL 突然变化)
**关键元素**: 浏览器地址栏出现 loading 指示 + URL 不变但实际是 native reload

### S8-e: Q4 录音机长录音 (45 分钟组会)
**画面**: 录音机列表中显示一条 45 分钟的录音 + 时长 + 分段数 + 转写状态
**关键元素**: 时长 45:23 + 1h 进度 + 76 段 ASR (灰色 "排队中")

### S8-f: Q5 Android Chrome 图标单色化
**画面**: Android 主屏, 小气助手图标为单色 (黑色轮廓) + 对比另一彩色 app 图标
**关键元素**: 单色图标 + 标注 "Chrome 12+ 设计语言"

### S8-g: Q6 iOS PWA push 通知请求弹窗
**画面**: iPhone 14 Pro (iOS 17.5) standalone PWA → 点 "订阅会议提醒" → 系统通知权限弹窗 "允许 '小气助手' 发送通知?"
**关键元素**: 系统弹窗 + 允许 / 不允许 按钮

### S8-h: Q7 触觉反馈设置页 (全局开关)
**画面**: 设置页 → 移动端 → 触觉反馈 → 单个 Toggle 开关 (on/off)
**关键元素**: 开关 + 4 种类型的列举 (tap/success/warning/error) 但不可单独控

### S8-i: Q8 左右滑切页不响应 (Android 全面屏手势冲突)
**画面**: Android 14 设置 → 手势导航 → 显示 "全面屏手势导航" 开启
**关键元素**: 标注 "与小气助手的左右滑冲突"

### S8-j: Q9 录音上传失败 + IndexedDB 队列
**画面**: 输入框中已显示转写文字 + 顶部 toast "上传失败, 网络恢复自动重试" + 队列图标
**关键元素**: toast 提示 + 转写文字保留 (不丢) + 离线状态栏

### S8-k: Q10 iOS PWA 离线模式
**画面**: iOS 17 Safari standalone → 飞行模式 → app 显示骨架屏 + "离线" 状态栏
**关键元素**: skeleton placeholder + "✈️ 离线" 标识

### S8-l: Q12 长按录音被电话中断
**画面**: 锁屏界面有来电 + 录音自动暂停 + 通知 "录音中断 (12.3s), 是否保存?"
**关键元素**: 来电覆盖层 + 录音状态 toast + [保存已录部分] [丢弃] 按钮

---

## §9 截图执行脚本 (主指挥复用模板)

### scripts/capture-mobile-screenshots.cjs

```js
// 伪代码骨架, 完整实现留给主指挥 PR
const { chromium, devices, firefox } = require('playwright');
const fs = require('fs');
const path = require('path');

const OUTPUT_DIR = 'docs/screenshots/mobile-v3.1';
const DEVICES = ['iPhone 14 Pro', 'iPhone 8', 'Pixel 7'];
const THEMES = ['light', 'dark'];

const SCENARIOS = [
  { id: 's1-a', device: ['iPhone 14 Pro', 'Pixel 7'], theme: ['light', 'dark'], action: 'idle' },
  { id: 's1-b', device: ['iPhone 14 Pro', 'Pixel 7'], theme: ['light', 'dark'], action: 'longpress-microphone' },
  { id: 's1-c', device: ['iPhone 14 Pro', 'Pixel 7'], theme: ['light', 'dark'], action: 'slideup-cancel' },
  // ... 全部 24 个场景
];

(async () => {
  if (!fs.existsSync(OUTPUT_DIR)) fs.mkdirSync(OUTPUT_DIR, { recursive: true });

  const browser = await chromium.launch();
  for (const { id, device, theme, action } of SCENARIOS) {
    for (const d of device) {
      for (const t of theme) {
        const context = await browser.newContext({
          ...devices[d],
          colorScheme: t,
          isMobile: true,
          hasTouch: true,
        });
        const page = await context.newPage();
        await page.goto('https://microbubble-test.xx/mobile/chat');
        await page.waitForSelector('[data-testid="chat-input"]');

        // 按 action 触发
        if (action === 'longpress-microphone') {
          await page.touchscreen.tap(370, 800, { delay: 500 });
        }

        const filename = `${OUTPUT_DIR}/${id}-${d.replace(/\s+/g, '-').toLowerCase()}-${t}.png`;
        await page.screenshot({ path: filename, fullPage: false });
        await context.close();
        console.log(`Captured: ${filename}`);
      }
    }
  }
  await browser.close();
})();
```

### 验证脚本 (提交前必跑)

```bash
# 检查所有截图存在
for f in $(cat docs/mobile-ux-v3.1-screenshots-needed.md | grep -oP 'S\d+-[a-z]+'); do
  if [ ! -f "docs/screenshots/mobile-v3.1/${f}-*.png" ]; then
    echo "MISSING: ${f}"
    exit 1
  fi
done

# 检查文件大小 (避免空图)
find docs/screenshots/mobile-v3.1/ -name "*.png" -size -10k | while read f; do
  echo "TOO SMALL: $f"
done

# 更新 user-guide.md 中的 ASCII 占位链接为实际截图
# (脚本略, 需要 AST 解析 markdown)
```

---

## §10 替换 user-guide.md 占位的步骤 (主指挥 PR)

1. 跑 §9 脚本生成全部 24 张截图到 `docs/screenshots/mobile-v3.1/`
2. 上传到 Aliyun OSS 得到 CDN URL
3. 写一个 `scripts/replace-ascii-with-screenshots.cjs` 脚本, 用 AST 解析 user-guide.md, 把 8 个 ASCII code block 替换为 Markdown image 引用:
   ```md
   ![语音三态](https://cdn.xx/mobile-v3.1/s1-iphone-14-pro-light.png)
   ```
4. 跑测试 + 提交 (用户指南从 ASCII 文档升级为图文并茂版本)
5. **commit message**: `docs(mobile-ux-v3.1): replace ASCII placeholders with real screenshots (24 PNG, S1-S8)`

---

## §11 总结

| 维度 | 数值 |
|------|------|
| 截图总数 | 24 (8 个场景 × 平均 3 张设备/主题组合) |
| 设备数 | 3 (iPhone 14 Pro 主流 + iPhone 8 老 iOS + Pixel 7 主流 Android) |
| 主题数 | 2 (light + dark) |
| 引用编号 | S1 ~ S8 (8 个用户指南章节) |
| 子场景 | S1-a/b/c + S3-a/b/c + S4-a/b/c + S5-a-e + S6-a/b/c + S7-a/b + S8-a-l |
| 工作量 | ~4 小时 (Playwright 编写 + 跑 + 验证 + 上传 OSS) |
| 主指挥 PR | 截图替换 + user-guide.md ASCII 清理 |

> **下一步**: 主指挥派工未来 PR (按 `future-pr-roadmap-2026-07-21.md` 第 5 项候选), 用 Playwright 跑本清单 + 替换 user-guide.md。

---

> **返回**: [`docs/mobile-ux-v3.1-user-guide.md`](./mobile-ux-v3.1-user-guide.md)
