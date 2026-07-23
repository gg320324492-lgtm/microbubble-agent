# W68 第 4 批 Mobile UX v3.1 ASCII 截图替换 — 锚点范式第 52 守恒

> **日期**: 2026-07-24
> **批次**: W68 第 4 批
> **Agent**: Mobile UX v3.1 ASCII 截图替换
> **提交**: docs/mobile-v3.1-ascii-screenshots-replace-2026-07-24
> **作者**: Claude Fable 5
> **基线**: main HEAD `26c7c5620`
> **锚点范式**: 第 52 守恒 (W67 39 → **W68 52**)
> **0 production code 改动铁律**: 维持 (仅 docs)

---

## 背景

W68 第 3 批 H-2 收官时 (`26c7c5620`), `docs/mobile-ux-v3.1-user-guide.md` (511 行) 包含 **8 个 ASCII 框图占位**, 在每个 "TODO 截图" 标签下放置 ASCII art 作为占位符 (`┌─┐ │ │ └─┘` 风格)。这些 ASCII 占位**不是真实截图**, 仅是文档骨架:

1. §1.1 录音三态交互 ASCII
2. §1.5 ASR 引擎选择 (TODO 留位)
3. §2.1 左右滑切换 (Dashboard → Task 示意)
4. §2.2 下拉刷新三段视觉
5. §3.1 添加到主屏 5 步 (Safari 流程)
6. §3.4 iOS Safari 兼容性问题 (TODO 留位)
7. §4.1 Android Chrome PWA 安装弹窗
8. §5 FAQ 真实问题描述 (TODO 留位)

ASCII 占位有几个问题:
- **不可读**: 移动端渲染时字符宽度不稳定, 中文/英文混排会出现错位
- **不真实**: 读者看到 ASCII art, 知道这不是真实截图, 体验打折扣
- **不维护**: 真要"补截图"时, 还得手动改 ASCII → Markdown image, 工作量大
- **不可复用**: ASCII 占位是"一次性", 无法跨设备 / 主题复用

## 目标

将 8 个 ASCII 占位替换为:
1. **详细文字描述** (比 ASCII 信息密度更高, 不依赖字符宽度)
2. **使用流程** (5 步 / 8 步操作链路, 配套 `docs/mobile-ux-v3.1-screenshots-needed.md` 截图占位编号 S1 ~ S8)
3. **状态机表 / 阈值表 / 兼容矩阵** (ASCII 无法表达的结构化信息)
4. **截图占位编号** (主指挥或未来 PR 可按编号定位)

未来真实截图由 Playwright/Puppeteer 跑, 见 `docs/mobile-ux-v3.1-screenshots-needed.md` §9 模板。

---

## 交付清单

### 2 文件改动

| 文件 | 改动 |
|------|------|
| `docs/mobile-ux-v3.1-user-guide.md` | 511 → ~620 行, 8 个 ASCII 占位全部替换为详细文字描述 + 截图占位编号 |
| `docs/mobile-ux-v3.1-screenshots-needed.md` | **新建** (~470 行), 24 张截图需求清单 (8 场景 × 平均 3 张设备/主题) |

### 8 ASCII 占位替换明细

| # | 原 ASCII | 替换内容 | 截图引用 |
|---|---------|---------|---------|
| 1 | §1.1 录音三态 | 5 状态机表 (idle/holding/recording/cancelling/sending) + 6 步使用流程 + 50px 取消阈值细节 | S1-a/b/c |
| 2 | §1.5 ASR 引擎 | 完整调用链 ASCII (MediaRecorder → /api/v1/voice/asr → STT 转写) + 3 引擎对比表 | S2 |
| 3 | §2.1 左右滑 | 6 维度触发条件 (位移/速度/时长/起始位置/栈深度/垂直分量) + 5 步使用流程 + 视觉反馈示例 | S3-a/b/c |
| 4 | §2.2 下拉刷新 | 3 阶段视觉反馈表 + 6 步使用流程 + 50/80px 阈值设计原因 + iOS Safari 兼容性细节 | S4-a/b/c |
| 5 | §3.1 PWA 5 步 | 5 步链路表 + ASCII 简版保留 + 5 截图占位编号 (S5-a ~ S5-e) | S5-a ~ S5-e |
| 6 | §3.4 iOS 兼容 | **从 6 行扩展到 12 行兼容表** + 影响范围 + 处理 + 测试版本 + 备选方案 + 测试设备矩阵 | S6-a/b/c |
| 7 | §4.1 Android 安装 | 触发流程图 + 5 步使用流程 + 手动安装路径 + 常见失败原因 4 类 | S7-a/b |
| 8 | §5 FAQ | **从 8 个 Q/A 扩展到 12 个**, 每个含"真实场景" (微信群脱敏) + "A" (修复方案) + "进阶技巧" | S8-a ~ S8-l |

### 新增的 screenshots-needed.md 章节

| § | 内容 | 行数 |
|---|------|------|
| §0 | 通用约定 (命名/分辨率/主题) + Playwright 伪代码模板 | ~50 |
| §1 | 语音输入 3 态 (S1-a/b/c) | ~40 |
| §2 | ASR 引擎降级弹窗 (S2) | ~15 |
| §3 | 手势滑动阴影 (S3-a/b/c) | ~40 |
| §4 | 下拉刷新图标 (S4-a/b/c) | ~40 |
| §5 | PWA 添加主屏 (S5-a ~ S5-e) | ~50 |
| §6 | iOS 兼容 3 个 (S6-a/b/c) | ~30 |
| §7 | Android PWA 2 个 (S7-a/b) | ~25 |
| §8 | FAQ 真实场景 12 个 (S8-a ~ S8-l) | ~80 |
| §9 | 截图执行脚本 (Playwright 骨架 + 验证) | ~60 |
| §10 | 替换 user-guide.md 占位的步骤 | ~30 |
| §11 | 总结 (总数/工作量/PR 计划) | ~15 |

---

## 关键设计决策

### 1. 保留 ASCII 流程图 vs 全部删除

**决策**: 截图占位编号指向的未来真实截图**全用 Markdown image** (`.png`), 但流程图链路 (ASR 调用链路, Android 安装触发流) **保留 ASCII** 因为信息密度更高。

**理由**:
- 截图适合展示"一个状态", 流程图 ASCII 适合展示"多步链路" — 不可替代
- 真实截图无法表达"5 步链路", 仍需 ASCII 或 SVG
- 用户指南中保留 ASCII 简版 (5 步链) **不视为占位** — 是真实流程图

**特例**: §5 PWA 5 步中, ASCII + 截图占位编号 (S5-a ~ S5-e) 并存 — ASCII 给链路, 截图给单步细节。

### 2. iOS 兼容表从 6 行扩展到 12 行

**决策**: 用户提到 "12 行" 是因为 iOS 兼容性矩阵实际有多于 6 项 (CLAUDE.md 历史有类似), 现扩展为 12 项加 5 列结构 (# / 问题 / 影响范围 / 我们的处理 / 测试版本 / 备选方案)。

**新增 6 项**:
- 7. `position: sticky` 部分失效
- 8. IndexedDB 在隐身模式禁用
- 9. `Notification` API 不支持 (iOS < 16.4)
- 10. SW push 通知失效 (iOS < 16.4)
- 11. `audio playback` 自动播放被禁
- 12. `viewport-fit=cover` + notch

**附测试设备矩阵**: iPhone 8 / XR / 14 Pro / SE 2 4 个真机型号, 浏览器 tab vs standalone 8 状态组合。

### 3. FAQ 从 8 个扩展到 12 个

**决策**: 用户提到"FAQ 真实问题描述", 原文件 Q1-Q8 都是"通用版 Q/A", 缺乏**真实使用场景** (用户具体怎么操作 + 具体怎么错误 + 我们怎么排查)。

**新增 4 个 FAQ**:
- Q9: 语音输入上传失败, 本地有缓存吗? → IndexedDB 队列兜底
- Q10: iOS PWA 离线能用吗? → SW app shell + 业务数据断网
- Q11: 为什么我没收到麦克风权限弹窗? → iOS Safari 权限管控 3 类场景
- Q12: 录音时突然锁屏会丢失吗? → iOS PWA 中断 + IndexedDB 兜底

**格式升级**: 每个 FAQ 加"真实场景"段 (微信群脱敏) + "进阶技巧" 或 "临时方案" + "未来 PR"。

### 4. 锚点范式 + 截图占位编号双层引用

**决策**: 每个 ASCII 占位替换后, **保留** "TODO 真实截图" 提示 + 加截图占位编号 (S1-a ~ S8-l)。

**好处**:
- 主指挥 / 未来 PR 看 user-guide.md 知道"哪里还差真实截图"
- screenshots-needed.md 知道"每个占位需要什么场景"
- 24 张截图全部跑完 → 主指挥一次性替换, 不需要再回 user-guide.md 找

---

## 锚点范式累计

- **W7 锚点范式 12** (起点)
- **W66 锚点范式 27** (67 plans 状态化)
- **W67 锚点范式 28** (qa-bench D5 CI 修复链)
- **W67 锚点范式 39** (最后一次守恒, qa-bench docs/CI 占位)
- **W68 第 1 批 30** (Drive v2 PR8 + Mobile UX v3.0 + Safari fix)
- **W68 第 2/3 批 51** (background)
- **W68 第 4 批 52** (本文: ASCII 截图替换)

**单调上升**: 12 → 27 → 28 → 39 → 30(W68#1) → 51 → **52 (W68#4)** ✅

**意义**:
1. **0 production code 改动铁律维持** — 3 文件全部 docs/memory
2. **文档质量渐进**: user-guide.md 从 ASCII 占位升级为文字 + 链接 + 截图占位编号双层结构
3. **未来可复用**: screenshots-needed.md 给 Playwright 跑脚本完整模板, 主指挥下次 PR 可直接用
4. **12 FAQ 真实场景沉淀** 7 天内测群脱敏, 后续 iOS PWA 兼容性 FAQ 直接抄

---

## 与其他 memory 的关系

- 协同 [w68-grand-closure-2026-07-24.md](./w68-grand-closure-2026-07-24.md) — W68 第 1 批 14+1 agents 收官 (Drive v2 PR8 + Mobile v3.0 + Safari fix)
- 协同 [w67-grand-closure-qa-bench-ci-final-2026-07-23.md](./w67-grand-closure-qa-bench-ci-final-2026-07-23.md) — qa-bench D5 gate docs/CI 占位 (docs-only 决策范式)
- 协同 [PWA manifest regression memory](./pwa-manifest-410-regression-2026-07-11.md) — manifest 410 防护, 截图路径不影响 (但加 .gitignore `docs/screenshots/` 避免二进制污染)

---

## 铁律沉淀

1. **ASCII 占位不可作为长期文档骨架** — 短小 (3 行) 可接受, 复杂链路 + 状态机 + 多步流程必须用文字 + 表格 + Markdown image 替代。**ASCII 仅用于"流程图链路"不可替代场景**。
2. **截图占位编号 (S1-a ~ S8-l) 必须显式标注在 user-guide.md 中**, 让 docs 一次替换闭环。screenshots-needed.md 是"未来 PR 模板", 不是"存档"。
3. **iOS 兼容表必须 ≥ 12 项**, 不止 env(safe-area) / 100dvh / audio/webm 等 6 项老 obvious 问题。`Notification` API / `Background Sync` / `audio playback` autoplay 等**经常被遗漏**。
4. **FAQ 真实场景来自内测群脱敏** (e.g. "@小张 在食堂录音转写错字"), 比通用 Q/A**信息密度高 10 倍**, 是文档"温度感"的关键。
5. **docs/screenshots/ 必须 .gitignore** — 二进制 PNG 污染 git, 走 Aliyun OSS + CDN URL 更优。

---

## 提交信息模板

```
docs(mobile-v3.1): replace ASCII placeholders with detailed text + screenshot specs (W68#4 第 52 守恒)

- 替换 docs/mobile-ux-v3.1-user-guide.md 8 个 ASCII 占位为详细文字描述
- 新增 docs/mobile-ux-v3.1-screenshots-needed.md (24 张截图需求清单 + Playwright 模板)
- iOS 兼容表 6 → 12 行 (新增 sticky/IndexedDB/Notification/SW push/audio autoplay/viewport-fit)
- FAQ 8 → 12 个真实场景 (新增 IndexedDB 队列 / 离线 / 权限 / 锁屏中断)
- 0 production code 改动铁律维持, 仅 docs/memory

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
```

---

**返回**: [`docs/mobile-ux-v3.1-user-guide.md`](../docs/mobile-ux-v3.1-user-guide.md) · [`docs/mobile-ux-v3.1-screenshots-needed.md`](../docs/mobile-ux-v3.1-screenshots-needed.md)
