# Phase 8-I3-B Scientific Research OS Visual Pro 验证记录

**验证日期：** 2026-08-24

**阶段基线：** `e4eea767ce337232b138133b68115d1ed2ed7105`

**最终提交信息：** `Phase 8-I3-B Scientific Research OS Visual Pro Upgrade`

**范围：** `desktop/**` 科研 UI、可访问性、状态一致性、测试、构建与桌面运行时

## 1. 最终门禁

| 门禁 | 新鲜结果 |
|---|---|
| `npm run typecheck` | 通过；Node `tsc` 与 Web `vue-tsc` 均为 0 errors |
| `npm run test:unit` | 62/62 files，6073/6073 tests，通过率 100% |
| 六个 Phase 8 UI 契约文件 | 6/6 files，489/489 tests，通过率 100% |
| `npm run build` | main 409、preload 2、renderer 783 modules transformed |
| 冷/热双构建确定性 | 两次各 64 个产物；逐文件长度与 SHA-256 比较，diff=0 |
| 真实 Chromium 双视口 | 1440×900 与 1920×1080，10 个科研路由各一轮，共 20/20 通过 |
| 真实 Electron | main/preload/renderer 生产构建由 Electron 32.3.3 启动，进程组正常响应并在验收后停止 |
| `git diff --check` | 最终提交前复验，0 输出 |
| 目录隔离 | baseline 以来全部已跟踪变更均位于 `desktop/**`；`web/app/backend` 0 diff |

六个 UI 契约文件及用例分布：

```text
research-design-tokens.dom.test.ts   72
research-icon.dom.test.ts            48
research-primitives.dom.test.ts      75
research-layout.dom.test.ts          50
research-pages.dom.test.ts          210
scientific-chart.dom.test.ts         34
合计                                489
```

这 489 项为本阶段专属 UI 契约，高于“不少于 300 项”的验收门槛；完整桌面测试总量为 6073 项。

## 2. 实现与终审闭环

- 10 个科研路由已统一到 Scientific Research OS 壳层：科研首页、科研助手、项目空间、文献研究、实验设计、数据分析、论文生成、知识图谱、Agent 中心、系统设置。
- 设计令牌、图标系统、科研卡片/指标/证据/时间线/图表原语、侧栏、顶栏、动效与 reduced-motion 契约均已统一。
- `MainLayout` 真实渲染默认 slot，App 的 `Transition` 不再被布局层截断。
- disabled 按钮使用明确的背景、边框、文字语义，而非仅降低 opacity。
- Dashboard、ProjectWorkspace、Literature 刷新失败时保留已加载科研内容，同时显示中文重试状态。
- Assistant 将 Planner/Retrieval/Tool Call/Analysis/Model Response 等已知英文阶段映射为中文，自定义中文标签原样保留。
- ProjectWorkspace 对已知动力学模型显示中文名称；Experiment 保存改走 Store action，Service 成功后再原子合并，重挂载保持确认值。
- Electron main 明确内联 ESM-only `electron-store`，避免 CommonJS 运行时 `ERR_REQUIRE_ESM`。
- 两轮独立规格/质量复核在状态一致性修复后均未发现 Critical 或 Important 代码问题。

## 3. 构建确定性修复

第一次执行“`npm ci` 后连续两次构建”时，64 个产物中只有 `out/main/index.js` 不一致；renderer 与 preload 均稳定。重复诊断确认 main 的模块数会在 583、590、591 间漂移，且 `node_modules` 在构建前后没有文件或元数据变化。

根因是 Vite/Rollup CommonJS 的 `strictRequires: "auto"`：它在模块加载过程中自动探测循环依赖，`electron-store → conf → ajv` 的大 CommonJS 图会因加载顺序产生不同包装结果。按 TDD 先新增失败契约，再在 main build 设置：

```ts
commonjsOptions: {
  strictRequires: true
}
```

修复后从全新 `npm ci` 状态执行第一次冷构建和紧接第二次构建：

```text
first:  main 409 / preload 2 / renderer 783 / files 64
second: main 409 / preload 2 / renderer 783 / files 64
逐文件 Length + SHA-256 manifest diff: 0
```

这不是依靠“先预热一次”得到的结果；比较包含 `out/main`、`out/preload` 与 `out/renderer` 的全部文件。

## 4. 真实 Chromium 视觉与交互证据

受保护路由使用仅本机、离线、验收后立即撤除的 preload API 夹具；页面本体为真实 Vite renderer + Chromium。最终工作树中 `index.html`、夹具脚本和验收脚本均为零残留。

### 双视口路由

两个视口均逐页验证 hash、激活导航、页面 H1、MainLayout slot 子节点及横向溢出：

| 路由 | 实际 H1 | 1440×900 | 1920×1080 |
|---|---|---:|---:|
| `/research/dashboard` | 科研首页 | 通过 | 通过 |
| `/research/assistant` | 研究会话 | 通过 | 通过 |
| `/research/project` | 项目空间 | 通过 | 通过 |
| `/research/literature` | 文献证据工作区 | 通过 | 通过 |
| `/research/experiment` | 实验设计 | 通过 | 通过 |
| `/research/data-analysis` | 数据分析工作区 | 通过 | 通过 |
| `/research/manuscript` | 臭氧微纳米气泡降解四环素的效率与机理研究 | 通过 | 通过 |
| `/research/knowledge-graph` | 知识图谱 | 通过 | 通过 |
| `/research/agent-center` | Agent 中心 | 通过 | 通过 |
| `/research/settings` | 系统设置 | 通过 | 通过 |

20/20 页面均满足：`mainChildren=1`、document 横向溢出=false、主内容横向溢出=false。截图缓冲分别为 114275 bytes（1440）和 171502 bytes（1920），证明两个视口均完成真实绘制，而非只做源码断言。

### 运行时交互

| 场景 | 实际证据 |
|---|---|
| 侧栏 | 232px → 76px → 232px；收起时标签 10→0，恢复后导航完整 |
| 项目标签 | 聚焦“项目概览”后 ArrowRight，选中项变为“文献” |
| 全局 Tab 顺序 | 科研首页 → 科研助手 → 项目空间 → 文献研究 |
| 文献弹层 | 打开后焦点进入 dialog 内按钮；Escape 关闭；焦点回到原“查看引用位置”触发器 |
| Agent 四态 | 运行中、已完成、异常、等待中四种真实渲染类与中文 aria-label 同时存在 |
| reduced-motion | Chromium `reducedMotion=reduce` 下，侧栏和进度动画计算时长均为 `1e-05s`（浏览器规范化后的近零值） |
| 故障恢复 | 注入知识服务失败后保留“科研首页”与已有科研内容；显示中文失败提示和 1 个重试按钮；原始 `VISUAL_KNOWLEDGE_FAILURE` 未泄漏到 UI |
| 控制台 | 全部正常路由与交互的 console error / pageerror 均为空数组；故障页无未捕获 pageerror |

先前的真实 ECharts 抽查还确认：数据分析页 canvas=1、svg=3、progressbar=1；知识图谱点击实体后 `aria-pressed=true` 并显示作者、来源、年份与引用检查器。

## 5. Electron 与安装环境

- UI 稳定版本曾通过 `npm run dev` 启动真实 Electron，日志含 `[bootstrap] started ... vault=true, session=false`，无 `ERR_REQUIRE_ESM`。
- 最终确定性配置下，main 409 modules 与 preload 2 modules 均可构建；将官方 Electron 32.3.3 zip 完整解压后，直接启动最终 `out/main + out/preload + out/renderer`，Electron 进程组正常响应。
- 本机全局 Node 24.16.0 下，Electron 32.3.3 的 `extract-zip` 生命周期脚本会静默只解出首个 locale，导致 `npm run dev` 报 `Electron uninstall`。官方 zip 本身完整（约 113 MB，包含 `electron.exe`、`version` 和全部资源），使用系统 `tar` 解压后可正常启动。这是本机 Node 24/安装器组合问题，不是仓库构建或应用运行时错误；建议桌面开发环境固定项目兼容的 Node LTS。

## 6. 目录、数据流与安全审计

| 检查 | 结果 |
|---|---|
| `git diff <baseline> -- web app backend` | 0 行 |
| `desktop/src/renderer/src/services/research/**` | 0 diff |
| ResearchAgent、知识层、工具、模型服务、IPC、后端 | 未修改 |
| Research Store | `manuscript.store.ts` 仅删除未使用 type import；`experiment.store.ts` 新增确认后原子提交 action |
| 会话前未跟踪项 | `.agents/skills/verify/` 与 `tmp/` 原样保留，未提交 |

`npm audit --omit=dev --json` 的生产依赖结果为 1 个 moderate、0 high、0 critical：ECharts `<6.1.0` 的 Lines-series tooltip XSS。当前科研 UI 不使用 `type: 'lines'`，也没有该路径的原始 HTML tooltip formatter，因此已知触发条件不可达。官方修复需要升级到 ECharts 6.1.0 主版本，伴随默认主题与部分 API 迁移；本视觉阶段未用一次未经专项回归的主版本升级替代已验证设计。参考：[GitHub Advisory GHSA-fgmj-fm8m-jvvx](https://github.com/advisories/GHSA-fgmj-fm8m-jvvx)、[Apache ECharts 6 Upgrade Guide](https://echarts.apache.org/handbook/en/basics/release-note/v6-upgrade-guide/)。

## 7. 结论

Phase 8-I3-B 的代码、状态语义、可访问性交互、真实双视口、故障态、Agent 四态、reduced-motion、全量测试、Electron 构建与冷/热确定性门禁全部完成。临时夹具零残留，阶段变更严格限定在 `desktop/**`。
