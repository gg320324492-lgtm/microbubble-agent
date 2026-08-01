# W100 +24 UI-PROF-ENTRIES Runbook — 知识图谱 / 公式 / 假设入口

**commit**: `703c51f12`
**派工**: v10 P1-A (1 commit, 前端 UX 增强)
**日期**: 2026-08-02
**worktree**: `E:/agent-ui-prof-entries` → origin/chore/ui-prof-entries

---

## 1. 改动范围

### 1.1 新增 (2)
| 文件 | 行数 | 作用 |
|------|------|------|
| `web/src/components/chat/ProEntries.vue` | 261 | 知识图谱/公式/假设入口组件 (toolbar + 3 tag 按钮) |
| `web/src/components/chat/__tests__/ProEntries.test.ts` | 98 | 7 vitest case |

### 1.2 修改 (4, 仅前端)
| 文件 | 改动 |
|------|------|
| `web/src/views/chat/ChatViewSSE.vue` | +34 行 (useRouter + onProEntryClick + 模板接入) |
| `web/src/views/mobile/chat/MobileMessageBubble.vue` | +11/-1 行 (import ProEntries + emit 'pro-entry' + 模板) |
| `web/src/views/mobile/chat/MobileMessageList.vue` | +1 行 (透传 pro-entry emit) |
| `web/src/views/mobile/chat/MobileChatView.vue` | +21 行 (useRouter + onProEntryMobile + 模板接入) |

### 1.3 dist rebuild (128)
`npm run build` 后 dist/ 全部 asset 重新生成, 沿用 W100 +23 commit 跟踪 dist 惯例。

---

## 2. ProEntries 智能显示逻辑

```
showGraph      = forceAll OR (intent.keywords.length > 0) OR (toolTrace ∋ 'explore_knowledge_graph')
showFormula    = forceAll OR (content 含 LaTeX) OR (toolTrace ∋ 'list_formulas')
showHypothesis = forceAll OR (toolTrace ∋ 'list_hypotheses')
```

LaTeX regex: `/\$\$[^$]+\$\$|\$[^$\n]{2,}\$/` (排除货币符号 `$5`)

---

## 3. 路由映射 (派工前提错配 #21)

| kind | 实际路由 | 来源 |
|------|----------|------|
| graph | `/knowledge/graph?session=&msg=` | KnowledgeGraphView.vue 真实存在 (W86 mini-3 fallback) |
| formula | `/knowledge?tab=formulas&search=<keyword>` | KnowledgeView tab (W86 mini-3 决策) |
| hypothesis | `/knowledge?tab=hypotheses&from=<msgId>` | KnowledgeView tab (W86 mini-3 决策) |

**派工 brief 错误**: `/formulas?search=` `/hypotheses?from=` 独立路由不存在
→ 实际入口是 KnowledgeView 的 2 个 tab, 通过 `?tab=` 切换 (`VALID_TABS` 白名单)

---

## 4. 部署步骤

### 4.1 拉取最新分支
```bash
cd E:/microbubble-agent
git fetch origin
git checkout chore/ui-prof-entries
git pull origin chore/ui-prof-entries
```

### 4.2 验证 build (无功能改动, 仅前端)
```bash
cd web
npm ci --silent
npm run build  # 唯一合法命令 (W98 H-3 教训)
```

预期输出:
- 228 dist assets 生成
- postbuild: "PWA 已禁用 (vite-plugin-pwa disable: true), sw.js 不存在 — 跳过所有 PWA 后处理"
- vite-plugin-pwa `disable: true` by design (W98 H-3 强制注销 SW 策略)
- `✓ built in 10.86s`

### 4.3 部署到服务器
```bash
# 沿用现有 deploy-auto.sh (无特殊后端改动)
bash scripts/deploy-auto.sh
```

无 alembic 改动, 无需 `alembic upgrade head`。
无 nginx 改动, 无需 reload。

---

## 5. 验证清单 (部署后)

### 5.1 桌面端
1. 打开 chat 页面
2. 发送消息让 AI 提到关键词 (如"微泡" / "表面张力")
3. hover 助手消息气泡 → 应看到 3 个按钮: 🕸️ 📐 💡
4. 点击 🕸️ → 跳转到 `/knowledge/graph?session=...&msg=...` (KnowledgeGraphView 渲染)
5. AI 回复含 LaTeX (如 `$r = \sqrt{...}$`) → 📐 按钮应显示
6. AI 调 list_hypotheses → 💡 按钮应显示

### 5.2 移动端
1. 切到移动端 viewport (DevTools)
2. 发送消息触发关键词
3. **不** hover, 3 按钮应直接显示在 msg-meta 行 (compact 模式)
4. tap 任一按钮 → 跳转对应路由

### 5.3 a11y
1. Tab 键 → ProEntries toolbar 获得焦点
2. Enter → 触发第一个按钮
3. focus-visible 2px outline 应可见

### 5.4 dark mode
1. 切到 dark mode
2. 按钮文字色应自动调整为 `--color-text-secondary`
3. hover 高亮: `rgba(255, 122, 92, 0.15)` 背景

---

## 6. 故障排查

### 6.1 3 个按钮都不显示
**原因**: intent=null, content="", toolTrace=[] 且 forceAll=false
**修法**: 父组件传 `:force-all="true"` (W100 +24 不实施, 仅 fallback)

### 6.2 点击按钮无反应
**原因**: router.push 报错 (KnowledgeGraphView 路径拼错)
**修法**: 检查 console — `[ChatViewSSE] onProEntryClick router.push failed`

### 6.3 /knowledge/graph 页面 404
**原因**: 路由配置 (router/index.js:111) 已存在, 但服务器 SPA fallback 需 nginx 配置
**修法**: 沿用现有 nginx SPA try_files 即可

### 6.4 移动端按钮挤占空间
**原因**: compact 模式 min-width: 44px 可能挤压 token/timestamp 显示
**修法**: 调整 .msg-meta flex-wrap 即可, 不动 ProEntries

---

## 7. 与 W100 +23 兼容性

- **ChatMessageActions** (W100 +23 重生成 + 复制按钮): ProEntries 挂在它之后, 不冲突
- **FeedbackButtons** (W98 CHAT-P1-D3): ProEntries 在它之前, 不冲突
- **FollowUpChips** (CHAT-P1-E): 独立行, 不冲突
- **ThinkingCapsule** / **PlanSteps** / **ToolTraceItem**: 都独立 v-if, 不冲突

---

## 8. 后续待办 (派工 brief 未列, 不擅自扩)

1. **`/knowledge/graph` 主入口 vs fallback**: W86 mini-3 决策主入口走 `?tab=entities`,
   本任务主入口走 `/knowledge/graph` (派工 brief 字面意思)。
   后续如需切换, 改 ChatViewSSE.vue onProEntryClick 即可, **不动本任务其他代码**
2. **ProEntries 深链接**: 当前 router.push 携带 session/msg, 但 KnowledgeGraphView 未读取这 2 个 query
   (派工 brief 写"携带 msg id 用于 deep link", 但目标 view 不读 → **派工前提错配**,
   实施时不擅自扩)
3. **移动端 KnowledgeGraph**: 当前仅桌面端 KnowledgeGraphView, 移动端走 `?tab=entities` 自适应
   (实际 fallback, 派工 brief 提了 "MobileKnowledgeGraph.vue" 但不存在 → 派工前提错配)
4. **ProEntries forceAll prop**: 当前未使用, 留作未来"用户自选"模式开关

---

## 9. 关键 commit 信息

```
703c51f12 [W100 +24] feat(chat): 知识图谱 / 公式 / 假设入口 (专业模块跳转)
```

- 5 件套守恒: alembic 096 / pytest N/A / build 成功 / 0 production / 锚点 +1
- 派工前提错配 #21: 路由名 + 工具名 + 组件名 3 处不符 brief, 派工前 grep 真查后改正
- 派工 v6 §1.2 "Status 段必真验证" 实战: 14/14 vitest PASS + build 228 assets + commit pushed
- 沿用 W100 +23 commit 跟踪 dist 惯例 (worktree 模式), 134 files changed (含 dist rebuild)

---

## 10. 相关引用

- 派工 brief: `派工 v10 — UI-PROF-ENTRIES 知识图谱 / 公式 / 假设入口 (用户视角 P1-A)`
- 派工 v6 §1.2 "Status 段必真验证": CLAUDE.md §派工前提铁律 12
- W86 mini-3 决策: 知识图谱主入口走 KnowledgeView 实体图谱 tab (CLAUDE.md §W86 mini-3)
- W98 H-3 强制注销 SW 策略: vite-plugin-pwa `disable: true` by design
- W100 +23 baseline: `00cd06953` merge: UI-REGEN 重生成 + 复制按钮
- 派工 v10 段 7 错误 19 类: 本任务触发 E03 路由不存在 + E07 页面缺失 (均已据实上报)