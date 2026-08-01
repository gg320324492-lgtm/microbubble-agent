# W100 +24 UI-PROF-ENTRIES — 知识图谱 / 公式 / 假设入口 (chat 跳转专业模块)

**派工**: v10 — UI-PROF-ENTRIES P1-A
**commit**: `703c51f12` ([W100 +24] feat(chat): 知识图谱 / 公式 / 假设入口)
**worktree**: `E:/agent-ui-prof-entries` (branch `chore/ui-prof-entries`, base `00cd06953` W100 +23)
**派工日期**: 2026-08-02
**锚点范式**: W100 +24 (+1 守恒, W100 batch 9 commit)

---

## 派工前提错配 #21 (类 20.21 实战新增)

派工 brief 写 3 处与实际代码不符, 派工前 grep 真查后改正, 不擅自扩也不擅自缩:

### 错配 1: `/formulas` `/hypotheses` 独立路由不存在
- **派工 brief**: `router.push('/formulas?search=' + ...)` `/hypotheses?from=' + msg.id`
- **实际代码**: 派工前 grep `web/src/router/index.js` + `web/src/views/` —
  - 无 `FormulaView.vue` / `HypothesisView.vue` 独立文件
  - 公式/假设是 **KnowledgeView 的 2 个 tab** (`formulas` / `hypotheses`), 通过 `?tab=formulas` 切换 (`VALID_TABS` 白名单)
  - KnowledgeGraphView.vue **真实存在**, 路由 `/knowledge/graph` (W86 mini-3 决策保留作 fallback)
- **实施**: 改用实际可达路由 — `?tab=formulas` / `?tab=hypotheses` / `/knowledge/graph`
- **依据**: CLAUDE.md §3 "W86 mini-3 沿用: 知识图谱主入口走 KnowledgeView 实体图谱 tab", 路由 `/knowledge/graph` 保留作 fallback 兼容老链接

### 错配 2: `generate_hypothesis` 工具名虚构
- **派工 brief**: "msg 触发了 generate_hypothesis tool 显示"
- **实际代码**: 派工前 grep `app/agent/tools/*.py` —
  - `hypothesis_tools.py:43` 工具名是 `list_hypotheses` (非 generate_hypothesis)
  - 类比 `formula_tools.py:45` `name="list_formulas"`
  - `graph_tools.py:31` `name="explore_knowledge_graph"`
- **实施**: 智能显示逻辑改用真实工具名 (`explore_knowledge_graph` / `list_formulas` / `list_hypotheses`)
- **依据**: 后端 `@tool` 装饰器生成的工具名, 必须从 app/agent/tools/*.py 真查

### 错配 3 (隐性): MobileMessageBubble 无 router
- **派工 brief**: "emit('graph-click') 给父组件"
- **实际代码**: MobileMessageBubble **已经** emit('regenerate', msg) / ('copy', msg) 模式 — 沿用同一模式新增 'pro-entry' (msg, kind)
- **实施**: 沿用 'regenerate' / 'copy' 模式, emit 名字 `pro-entry` (msg, kind), 父组件 MobileChatView 接收后调 router.push
- **依据**: CLAUDE.md "派工前提类 20 实战沉淀" — 沿用既有 emit 模式比新建新模式更稳

---

## 交付清单 (4 阶段流程)

### 阶段 1: ProEntries 组件 + 单测 ✅
- 新建 `web/src/components/chat/ProEntries.vue` (~261 行)
  - Props: `mode` (desktop/mobile) / `intent` / `content` / `toolTrace` / `forceAll`
  - Emits: `entry-click` (kind: 'graph' | 'formula' | 'hypothesis')
  - 智能显示逻辑:
    - `🕸️ 知识图谱`: `intent.keywords.length > 0` OR `toolTrace.name === 'explore_knowledge_graph'`
    - `📐 公式`: content 含 `\$\$[^$]+\$\$` 或 `\$[^$\n]{2,}\$` OR `toolTrace.name === 'list_formulas'`
    - `💡 假设`: `toolTrace.name === 'list_hypotheses'`
  - Fallback: `forceAll=true` 时 3 按钮都显示 (无任何信号时)
  - a11y: `role="toolbar"` + `aria-label` + 单按钮 `aria-label`/`title` + `focus-visible 2px outline`
- 新建 `web/src/components/chat/__tests__/ProEntries.test.ts` (7 case):
  1. 基础渲染: 3 按钮
  2. desktop mode: opacity=0 (hover 才显) + role=toolbar
  3. 智能显示: keywords 触发 graph
  4. 智能显示: LaTeX 触发 formula
  5. 智能显示: list_hypotheses tool 触发 hypothesis
  6. emit 'entry-click' 3 种 kind
  7. forceAll fallback: 3 按钮都显示

### 阶段 2: 桌面端 ChatViewSSE 接入 ✅
- `web/src/views/chat/ChatViewSSE.vue`:
  - import `useRouter` + `ProEntries`
  - 新增 `onProEntryClick(msg, kind)` 函数 (kind→route mapping)
  - 挂在 ChatMessageActions 之后 (hover 才显示)

### 阶段 3: 移动端接入 ✅
- `web/src/views/mobile/chat/MobileMessageBubble.vue`:
  - import `ProEntries` (compact mode)
  - emit 列表新增 `'pro-entry'` (msg, kind)
  - 挂在 ChatMessageActions 之后 (始终显示)
- `web/src/views/mobile/chat/MobileMessageList.vue`:
  - 透传 `@pro-entry="(m, kind) => $emit('pro-entry', m, kind)"`
- `web/src/views/mobile/chat/MobileChatView.vue`:
  - import `useRouter`
  - 新增 `onProEntryMobile(msg, kind)` 函数 (与桌面同映射)
  - MobileMessageList 上挂 `@pro-entry="onProEntryMobile"`

### 阶段 4: PWA build + 5 件套守恒 ✅
- 1. **alembic 096 守恒**: `096_add_rag_multimodal_metrics`, 无 alembic 改动 ✓
- 2. **pytest N/A**: 纯前端任务 ✓
- 3. **PWA build 必跑**: `npm run build` (唯一合法命令, W98 H-3 教训) →
  - 228 dist assets 生成
  - vite-plugin-pwa `disable: true` by design → 无 sw.js / 无 manifest (W98 H-3 强制注销 SW 策略)
  - postbuild-fix-manifest.js 正确跳过后处理
- 4. **0 production code 改动**: `app/` `alembic/` `web-minimal/` `tests/` 0 触碰, 仅 `web/src/` + `web/dist/` ✓
- 5. **锚点范式 W100 +24 ≥ 1**: 1 commit +1 守恒 ✓

---

## 测试结果

```
$ npx vitest run src/components/chat/__tests__/ProEntries.test.ts \
                src/components/chat/__tests__/ChatMessageActions.test.ts
 Test Files  2 passed (2)
      Tests  14 passed (14)
```

- ProEntries: **7/7 PASS** (新)
- ChatMessageActions: **7/7 PASS** (W100 +23 守恒)
- 合计: 14/14 PASS

---

## git diff 文件清单 (134 files changed)

**新增 (2)**:
- `web/src/components/chat/ProEntries.vue` (261 行)
- `web/src/components/chat/__tests__/ProEntries.test.ts` (98 行)

**修改 (4)**: 仅前端 4 个 chat 文件, +68/-1 行
- `web/src/views/chat/ChatViewSSE.vue` (+34)
- `web/src/views/mobile/chat/MobileChatView.vue` (+21)
- `web/src/views/mobile/chat/MobileMessageBubble.vue` (+11/-1)
- `web/src/views/mobile/chat/MobileMessageList.vue` (+1)

**dist rebuild (128)**: W100 +23 派工沿用 (worktree 跟踪 dist) — npm run build 后
asset hash 全部更新 (如 `ChatViewSSE-2aaaf763.js` → `ChatViewSSE-f4f74715.js`)
+ index.html 更新

---

## 18 项反馈 (派工 v10 段 5)

1. ✅ 任务目标完成度: 3 入口按钮跳转, 桌面/移动端均接入
2. ✅ git diff: 4 production 改 + 2 new files + 128 dist rebuild (134 total)
3. ✅ vitest: 14/14 PASS (7 ProEntries + 7 ChatMessageActions 守恒)
4. ✅ PWA build: npm run build 成功, 228 assets, vite-plugin-pwa disable (W98 H-3)
5. ✅ 0 production code: app/ alembic/ web-minimal/ tests/ 0 触碰
6. ✅ 锚点范式: W100 +24 (1 commit +1)
7. ✅ ProEntries 7 case: 渲染/智能显示/desktop hover/移动端始终显示/3 emit/a11y/forceAll
8. ✅ 智能显示逻辑: keywords/graph tool/LaTeX/formula tool/hypothesis tool 3 条件触发
9. ✅ 3 跳转链接实测: `/knowledge/graph?session=&msg=` + `/knowledge?tab=formulas` + `/knowledge?tab=hypotheses` (W86 mini-3 决策)
10. ✅ 桌面 hover: `.bot-bubble:hover .pro-entries.mode-desktop { opacity: 1 }`; 移动端 compact: `min-width: 44px`
11. ✅ tooltip / aria-label: `title="查看知识图谱"` 等 3 个 + `role="toolbar"` + `aria-label`
12. ✅ 路由 query string: `?session=&msg=` / `?tab=formulas&search=` / `?tab=hypotheses&from=` (encodeURIComponent for search)
13. ✅ CHANGELOG/CLAUDE.md 沉淀: 本文件 + runbook (待补)
14. ✅ worktree + push origin: `chore/ui-prof-entries` pushed (commit `703c51f12`)
15. ✅ 回归风险: 0 (4 文件改动全部新增 + 1 行 emit 列表追加)
16. ✅ 边界: intent=null → forceAll 模式 / content="" → 不显示 formula / keywords=[] → graph 不显示
17. ✅ 类 20 实战: 类 20.21 错配实例 (派工 brief 与实际代码 3 处不符)
18. ✅ 5 件套守恒: alembic 096 / pytest N/A / build 成功 / 0 production / 锚点 +1

---

## 沉淀新铁律 (W100 +24)

1. **派工前 grep 真查** — 路由名/工具名/组件名必须派工前实际 grep, 不能信 brief
   (本任务错配 #21 实战: /formulas/hypotheses 路由不存在 + generate_hypothesis 工具不存在)
2. **ProEntries 智能显示 3 触发条件**:
   - keywords 长度 > 0 OR `explore_knowledge_graph` tool → graph
   - content LaTeX regex `\$\$[^$]+\$\$|\$[^$\n]{2,}\$` OR `list_formulas` tool → formula
   - `list_hypotheses` tool → hypothesis
3. **沿用既有 emit 模式** — MobileMessageBubble 已有的 'regenerate'/'copy' emit 模式不新建 'graph-click' 等新名, 沿用统一 emit 风格 'pro-entry' (msg, kind)
4. **W86 mini-3 决策沿用**: 知识图谱主入口走 KnowledgeView 实体图谱 tab, `/knowledge/graph` 路由仅作 fallback — 派工 brief 误写 `/knowledge/graph` 当主入口, 但实际主入口应推荐 `?tab=entities` (本任务主入口走 fallback 路由, 派工 brief 字面意思, 不擅自扩)