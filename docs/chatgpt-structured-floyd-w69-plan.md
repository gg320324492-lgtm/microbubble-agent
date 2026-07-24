# chatgpt-structured-floyd W69 子计划 — qa-bench 7 维评分 + 自动入库闭环 (子 plan ②/③ 留 W69 派工)

> **任务来源**: W68 第 8 批 B-4 agent 派工 — 调研 plan `chatgpt-structured-floyd.md` 拆 3 子 plan 后的 W69 子 plan ②/③ 实施可行性
>
> **触发场景**: W68 第 8 批 C-3 agent 已修订原 plan 头部 Status 字段 (1/3 子 plan 完成 = chat history 8 phase, 2/3 子 plan 留 W69)
>
> **预期产出**: 子 plan ② (qa-bench 7 维评分 + KB 入库闭环 + Dashboard MVP) + 子 plan ③ (UI redesign NavRail / ThinkingModeSwitch / ChatBreadcrumb) W69/W70 派工预排

---

## 1. 现状

### 1.1 chatgpt-structured-floyd.md 拆分结构

plan `C:/Users/pc/.claude/plans/chatgpt-structured-floyd.md` 是 3 子 plan 拼接的复合文档：

| 子 plan | 内容 | 当前状态 | 关联 commit |
|---|---|---|---|
| **① chat history 8 phase** | 账号持久化聊天历史 (PG 3 表 + 11 API + 流式持久化 + UI 升级 + Celery 30 天清理) | ✅ **已完成** (W68 #043) | `558962b1` + `5bf7c5c7` + `af8c8f7d` + `c369a7181` + `9052906de` 等 |
| **② qa-bench 7 维 + KB 闭环 + Dashboard MVP** | 780 题底数 + 7 维评分 + save_to_kb 5 道防线 + Celery auto_intake_rollback_task + Dashboard MVP + CI smoke 200 题 | ⏸ **留 W69 派工** | (W68 第 8 批 C-3 已修订头部) |
| **③ UI redesign** | NavRail (跨 desktop + mobile) + ThinkingModeSwitch (fast/balanced/deep) + ChatBreadcrumb (会话面包屑) | ⏸ **留 W70 派工** | (W68 第 8 批 C-3 已修订头部) |

### 1.2 已闭环 1/3 子 plan — 不返工原则

子 plan ① chat history 8 phase 已 W68 #043 全部收官 (Phase 1-8 完整):
- ✅ Phase 1：ORM + alembic 039_chat_history.py（commit 558962b1）
- ✅ Phase 2：11 个后端 API 端点（commit 558962b1）
- ✅ Phase 3：流式 chat 持久化（commit 5bf7c5c7）
- ✅ Phase 4：前端 store（commit af8c8f7d）
- ✅ Phase 5：旧数据迁移（commit af8c8f7d）
- ✅ Phase 4+5 fix：sync_from_local tz-aware datetime 500 bug（commit a1dfca2c）
- ✅ Phase 6：UI 升级（vitest 492/492 PASS）
- ✅ Phase 7：Celery 30 天清理（pytest 7/7 PASS）
- ✅ Phase 8：测试 + 沉淀

**W69 派工不重写 chat history 8 phase** — 已闭环的不动，仅实施子 plan ②/③。

### 1.3 锚点范式当前位置

- W68 第 8 批 main HEAD: `f14cb43c1` (锚点范式第 90 守恒)
- 67 plans 全部状态化 (W68 第 7 批 C-1 + C-2 + C-3 修订)
- 0 production code 改动铁律 13/15 守恒 (W68 第 7 批)
- W19 选项 A 维持 (4 留未来 PR 不发起新排期)
- W68 第 9 批计划: W69 派工预排 + 子 plan ②/③ 调研

---

## 2. 子 plan ② qa-bench 7 维评分 + KB 闭环 + Dashboard MVP (W69 派工)

### 2.1 子 plan ② 总体目标

在 `tests/qa-bench/` 现有框架上升级，建立**可量化的能力测评 + 自动回归体系**，解决三个核心问题：
1. **量化能力现状** — 用 7 维评分体系，对 12 业务域 + 6 高级 + 横切防御得出能力雷达图
2. **定位改进点** — 区分 prompt / 架构 / 后处理 / 兜底四种根因，给 P0-P2 优先级
3. **建立回归基线** — 每次 PR 自动跑 200 题子集（< 5 分钟），不破坏旧题

### 2.2 7 维评分体系

| 维度 | 权重 | 子项 | 评分 (0-1) |
|---|---|---|---|
| **1. Intent 正确性** | 10% | CASUAL/DATA/DEEP/ACTION 分类 | 1=正确 0=错误 |
| **2. Tool 选择** | 25% | tools_any 命中 + tools_must_all 命中 | 1=全中 0.5=any 0=全无 |
| **3. Content 准确性** | 30% | must_contain + 禁词 + ground_truth 对比 | 加权 0-1 |
| **4. Rich Block 合规** | 5% | json block、引用、表格正确 | 1=合规 0.5=部分 0=破坏 |
| **5. 防御性** | 15% | 7 个检测器（fake_xml/label/placeholder/hallucinated/filler/duration/abort） | 1=全过 0=任一 fail |
| **6. 性能** | 10% | duration + token + 首字延迟 | 分级 A/B/C |
| **7. 一致性** | 5% | 多轮上下文保持 + 同题二次回答 | 1=一致 0=矛盾 |

**总分公式**:
```
total_score = w1*intent + w2*tool + w3*content + w4*rich
            + w5*defense + w6*perf + w7*consistency
            * 100

# 关键维度 fail 一票否决（content<0.5 或 defense<0.7 → 直接 FAIL，不计总分）
```

**分级**:
- **A 级 (90-100)**: 优秀，进基线
- **B 级 (75-89)**: 合格，需观察
- **C 级 (60-74)**: 需改进，进 P1
- **D 级 (40-59)**: 弱，进 P0
- **F 级 (<40)**: 严重，紧急修复

**当前基线 84%** 对应 B 级，意味着多数题达到 A/B，但仍有 16% 在 C 以下需关注。

### 2.3 题目量分布（780 题 = 业务 500 + 高级 100 + 横切 100 + 极端 80）

| 类别 | 子类 | 题数 | 难度主导 |
|---|---|---|---|
| **A 成员** | A1 基础信息 / A2 画像 / A3 任务聚合 / A4 跨人对比 | 90 | L1-L3 |
| **B 任务** | B1 单人查询 / B2 跨人 / B3 创建 / B4 统计 | 80 | L1-L3 |
| **C 会议** | C1 列表 / C2 详情 / C3 纪要 / C4 转录 / C5 模板创建 | 80 | L2-L3 |
| **D 项目** | D1 列表 / D2 摘要 / D3 计划生成 | 60 | L2-L3 |
| **E 知识** | E1 检索 / E2 摘要 / E3 假设 / E4 公式 | 70 | L2-L3 |
| **F 公式** | F1 列表 / F2 计算验证 / F3 单位换算 | 30 | L2-L3 |
| **G 假设** | G1 列表 / G2 关联 / G3 验证建议 | 30 | L3-L4 |
| **H 记忆** | H1 短期 / H2 长期 / H3 遗忘 | 40 | L2-L3 |
| **M 多轮** | M1 指代消解 / M2 上下文 / M3 状态保持 | 40 | L3-L4 |
| **U 闲聊** | U1 寒暄 / U2 边界 / U3 自我介绍 | 30 | L1-L2 |
| **X 跨域** | X1 4 域综合 / X2 知识图谱 / X3 提议研究 | 60 | L3-L4 |
| **Z 极端** | Z1 长输入 / Z2 截断 / Z3 对抗 / Z4 错别字 | 30 | L4 |
| **P 高级**（新增） | P1 Self-RAG / P2 fan-out / P3 plan_step / P4 持久化 / P5 abort / P6 grounding | 100 | L3-L4 |
| **D 横切** | D1 抗幻觉 / D2 抗 fake XML / D3 性能 / D4 移动端 / D5 dark mode | 100 | L1-L4 |
| **总计** | | **780** | |

### 2.4 save_to_kb.py 5 道防线

**用户决策 (2026-06-30)**: 全自动入库（pass=入库）— 高风险需配套监控

**5 道防线（必须全部启用，否则不启用全自动入库）**:

| # | 防线 | 实现细节 | 拦截类型 |
|---|---|---|---|
| **1. dedup** | 内容去重 | `tests/qa-bench/kb_queue/dedup.py` — embedding 余弦相似度 ≥ 0.95 → skip | 重复污染 |
| **2. 长度过滤** | 长度合理性 | `< 50 字符` 或 `> 4000 字符` → reject | 噪声 / 异常长文本 |
| **3. LLM 拒答检测** | LLM-as-judge | 调用 LLM 判断 answer 是否含"我不知道"/"无法回答"/"incomplete"等拒答标记 | 拒答污染 |
| **4. 敏感词** | 关键词黑名单 | 28 黑名单成员名 + 8 placeholder + 11 filler phrase + 内部 label | hallucination / placeholder |
| **5. 人工抽检** | Celery beat daily 抽样 | 每天抽取 5% 新入库条目，触发 admin UI 待审核列表 | 低质量 / 错误答案 |

### 2.5 Celery auto_intake_rollback_task

**目的**: 入库失败自动回滚 + 告警

```python
# app/services/qa_bench_tasks.py (新增)
@app.task(name='qa_bench.auto_intake_rollback')
def auto_intake_rollback_task():
    """每日凌晨 4:00 跑：检查 24h 内新入库条目"""
    # 1. 查 24h 内入库的 knowledge_entries
    # 2. 检查 grounding ref 可达性（KB 引用 ref 是否失效）
    # 3. 检查下游用户点击次数（< 3 次 → 可疑）
    # 4. 触发回滚：kb_intake_audit 表中 status='rolled_back'
    # 5. 告警：负反馈 > 10% 触发 admin notification
```

**关键纪律**:
- 入库后 7 天 review 期
- 引用 ref 失效或下游用户点击 < 3 次 → 自动 rollback
- 灰度发布开关 `settings.AUTO_KB_INTAKE_ENABLED: bool = False` (默认关)
- 7 天手动审核期通过后切到 `True`，任何时段发现问题 → 切回 `False` 即停

### 2.6 KB 闭环流程

```
评测 pass → save_to_kb.py 自动入库
   ↓
   ├→ 1. dedup (embedding 余弦 ≥ 0.95 skip)
   ├→ 2. 长度过滤 (< 50 / > 4000 reject)
   ├→ 3. LLM 拒答检测 (拒答标记 reject)
   ├→ 4. 敏感词 (28 成员 + 8 placeholder + 11 filler reject)
   └→ 5. 人工抽检 (5% 抽样 admin UI 待审核)
        ↓
        入库成功
        ↓
24h 后 → auto_intake_rollback_task 巡检
        ├→ grounding ref 失效 → rollback
        ├→ 下游点击 < 3 → rollback
        └→ 负反馈 > 10% → 告警 + 暂停 AUTO_KB_INTAKE_ENABLED
```

### 2.7 Dashboard MVP 4 指标卡

**位置**: `/admin/qa-bench-dashboard`

| 指标卡 | 数据源 | 实时性 |
|---|---|---|
| **入库数** (24h) | `knowledge_entries.created_at > now() - 24h` | 5min polling |
| **通过率** (rolling 7d) | `save_to_kb.py` 5 道防线结果聚合 | 5min polling |
| **抽检数** (待审核) | `kb_intake_audit.status='pending'` count | 5min polling |
| **告警数** (rolling 24h) | `rollback_count` + `negative_feedback_count` | 5min polling |

**实现**:
- 4 el-card 横排（grid-template-columns: repeat(4, 1fr)）
- 每卡片：大数字 + 趋势箭头（↑/↓）+ 颜色状态（A=绿/B=蓝/C=黄/D=橙/F=红）
- 点击卡片跳转详情页

### 2.8 CI smoke 200 题 < 5min

**GitHub Actions 配置**:
```yaml
# .github/workflows/qa-bench-smoke.yml
name: qa-bench smoke 200 题
on: [pull_request]
jobs:
  smoke:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@v4
      - name: 设置 Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: 跑 smoke 200 题
        run: |
          PYTHONIOENCODING=utf-8 PYTHONUTF8=1 \
          pytest tests/qa-bench/smoke_200.py -v --timeout=300
```

**200 题策略**:
- `tags: ["hot_path", "regression_smoke"]` 标记的题
- 覆盖 12 业务域各取 10 题 + 5 题横切 + 35 题高级
- 总时长 < 5min（P95 < 1.5s/题）

### 2.9 子 plan ② 实施路径（5 agents 派工预排）

| Agent | 任务 | 工作量 | 风险 |
|---|---|---|---|
| **Agent #1** | 7 维评分算法实施 (`tests/qa-bench/scoring/seven_dim.py`) | 16h | 中 (权重争议需团队拍板) |
| **Agent #2** | save_to_kb.py 5 道防线 (`tests/qa-bench/kb_queue/dedup.py` + 4 防线) | 12h | 高 (灰度期需手动监控) |
| **Agent #3** | Celery auto_intake_rollback_task (`app/services/qa_bench_tasks.py`) | 8h | 中 (回滚需 idempotent) |
| **Agent #4** | KB 闭环 impl (端到端：评测→入库→抽检→回滚) | 12h | 高 (全链路集成测试) |
| **Agent #5** | Dashboard MVP + CI smoke 200 题 | 10h | 低 (复用 web 模板) |

**子 plan ② 总投入**: 58h (约 1.5 周，5 agents 并行)

### 2.10 子 plan ② 关键文件路径

```
e:/microbubble-agent/tests/qa-bench/
├── scoring/seven_dim.py          (NEW ~200 行) - 7 维评分
├── scoring/weights.json          (NEW ~30 行) - 权重配置
├── kb_queue/dedup.py             (NEW ~80 行) - 去重
├── kb_queue/length_filter.py     (NEW ~40 行) - 长度过滤
├── kb_queue/llm_refusal.py       (NEW ~60 行) - LLM 拒答
├── kb_queue/sensitive_words.py   (NEW ~50 行) - 敏感词
├── kb_queue/auto_intake_audit.py (NEW ~80 行) - 抽检审计
├── ci/smoke_200.py               (NEW ~150 行) - smoke 套件
└── dashboard/index.html          (NEW ~150 行) - Dashboard MVP

e:/microbubble-agent/app/services/
└── qa_bench_tasks.py             (NEW ~100 行) - Celery auto_intake_rollback

e:/microbubble-agent/.github/workflows/
└── qa-bench-smoke.yml            (NEW ~30 行) - GitHub Actions

e:/microbubble-agent/app/config.py
└── AUTO_KB_INTAKE_ENABLED        (NEW setting, 默认 False)
```

---

## 3. 子 plan ③ UI redesign (W70 派工)

### 3.1 子 plan ③ 总体目标

解决 ChatViewSSE 现有 4 个用户可观察痛点（plan 内 §Context 现存问题）：
1. SessionSidebar overlap bug (max-width: 160px + hover-only actions)
2. 🧠🧠 双 toggle 冲突 (showThinking + useDeepThinking 同 active)
3. 输入栏 3 个 left icon 无 aria-label
4. 顶栏图标认知负担 (🔍💭🧠🌙清空对话 4 元素拥挤)

**借鉴 ChatGPT / Claude.ai / Doubao 现代 Agent UI 模式** — 3-Zone 重新分区。

### 3.2 3-Zone 布局

```
┌─ LEFT nav rail ─┬─ CENTER main ──────────┬─ RIGHT FAB ─┐
│ 💬 (活跃)       │ ☰ [≡]  小气助手       │ [+ 新对话]  │  ← 永远可见的 + 按钮
│ 📋 任务         │   在线 • 思考中...    │            │
│ 📅 会议         │                       │            │
│ 📊 知识         │   ────────────────    │            │
│ 📚 假设         │   对话消息流          │            │
│ ───              │                       │            │
│ 📌 会话列表头   │                       │            │
│  📌 已置顶      │                       │            │
│  📌 你好        │                       │            │
│  📌 03.会议     │                       │            │
│                 │                       │            │
│ ⚙ 设置 (底部)   │                       │            │
└─────────────────┴───────────────────────┴────────────┘
                ┌─ 思考模式 segmented (在输入栏上方) ─┐
                │ ⚡ 快速回答 | 🧠 深度思考           │
                └─┬────────────────────────────────────┘
                  │ ➕ 图片  📎 文件  🎤 录音 | ... | ↑ 发
                  └────────────────────────────────────┘
```

### 3.3 3 个核心组件

#### 3.3.1 NavRail (侧边导航栏新组件)

**职责**: 跨 desktop + mobile 统一左侧导航

**桌面端** (grid 固定列宽 200-280px):
- 顶部: 用户头像 + 角色
- 中部: 7 个 icon 列 (💬聊天 / 📋任务 / 📅会议 / 📊知识 / 📚假设 / 📌置顶 / ⚙设置)
- 底部: ⚙ ThemeSettingsDrawer 触发按钮
- 嵌入 SessionSidebar 子区块 (仅列表，无 actions)

**移动端** (`< 768px` `display: none`):
- 用 MobileSessionDrawer 模式 (从左侧滑入)
- 不持久占位

**复用**:
- `web/src/components/mobile/MobileActionSheet.vue` — long-press 弹 5 actions
- `web/src/components/chat/SearchPalette.vue` — ⌘K 快捷键
- `web/src/stores/useThemeStore.js` — ThemeSettingsDrawer 包裹
- CLAUDE.md v60-v67 dark mode 教训 — 非 scoped `<style>` 块末尾

#### 3.3.2 ThinkingModeSwitch (思考模式切换器)

**职责**: 替代顶栏 2 个 toggle (🧠🧠 冲突)，用 segmented control 单选

**3 档**:
- ⚡ **快速回答** (`useDeepThinking=false` + `useSelfRag=false`)
- ⚖️ **平衡** (`useDeepThinking=false` + `useSelfRag=true`)
- 🧠 **深度思考** (`useDeepThinking=true` + `useSelfRag=true`)

**位置**: ChatViewSSE.vue line 486-487 之间插入 (输入栏上方)

**绑定**:
```js
// web/src/stores/useUiStore.js
const useDeepThinking = ref(false)
const useSelfRag = ref(true)

// computed 派生 3 档模式
const thinkingMode = computed(() => {
  if (!useDeepThinking.value && !useSelfRag.value) return 'fast'
  if (!useDeepThinking.value && useSelfRag.value) return 'balanced'
  return 'deep'
})
```

**a11y 4-attr 全套**:
- `id="thinking-mode-switch"` + `name="thinking-mode"` + `aria-label="思考模式"` + `title="切换思考模式"`

#### 3.3.3 ChatBreadcrumb (会话面包屑)

**职责**: 中央标题 + 在线状态 + breadcrumb path

**示例**:
```
小气助手 > 📂 课题组 2026 例会 > 💬 "饮用水安全方向现在缺什么研究？"
```

**接受 props**:
- `currentSessionId: string` — 从 chatSessions store 取 title
- `parentPath: string[]` — 可选 breadcrumb 上级路径

**位置**: ChatViewSSE.vue 顶栏中部 (line 348-398 之间)

### 3.4 关键架构决策

| # | 决策 | 选项 | 选择 | 原因 |
|---|---|---|---|---|
| 1 | 3-zone 布局整合 MainLayout | 新独立 layout / 改 MainLayout | 改 MainLayout | 不动 Nuxt-like 全局路由，CLAUDE.md 教训 |
| 2 | 思考模式分段控件位置 | 顶栏 toggle / 输入栏上方 segmented | 输入栏上方 | 上下文感知（用户提问时常切换） |
| 3 | 新会话入口 | "清空对话" 文字 / 单一 + FAB | 单一 + FAB | 语义清晰 (清空 vs 新建) |
| 4 | 搜索/主题位置 | 顶栏 toggle / ⌘K + ⚙ | ⌘K + ⚙ | header 干净，认知负担接近 0 |
| 5 | SessionSidebar actions | hover-only / right-click / long-press | right-click (desktop) + long-press (mobile) | 不与 title 重叠 |
| 6 | 图标 emoji vs EP icons | emoji / EP icons-vue | EP icons-vue | 跨平台渲染一致 |
| 7 | NavRail 移动端 | 持久占位 / 抽屉式 | 抽屉式 (MobileSessionDrawer) | 响应式断点 @media (max-width: 768px) |

### 3.5 子 plan ③ 实施路径（4 agents 派工预排）

| Agent | 任务 | 工作量 | 风险 |
|---|---|---|---|
| **Agent #1** | NavRail.vue 新组件 + SessionSidebar 重构 | 6h | 中 (响应式断点 + dark mode) |
| **Agent #2** | ThinkingModeSwitch.vue + ChatBreadcrumb.vue 新组件 | 6h | 低 (复用 useUiStore) |
| **Agent #3** | ChatViewSSE 顶栏 3-zone 重构 + 输入栏 segmented | 8h | 高 (Playwright baseline 必然冲突) |
| **Agent #4** | 移动端同步 + Playwright 视觉回归 + 测试 + 沉淀 | 8h | 中 (mobile 双栈架构同步) |

**子 plan ③ 总投入**: 28h (约 1 周，4 agents 并行)

### 3.6 子 plan ③ 关键文件清单（11 文件改 + 3 文件新）

| 文件 | 改动 | 行数 |
|---|---|---|
| **`web/src/components/chat/NavRail.vue`** | NEW 左侧 nav rail | +250 |
| **`web/src/components/chat/ThinkingModeSwitch.vue`** | NEW segmented control | +80 |
| **`web/src/components/chat/ChatBreadcrumb.vue`** | NEW 中央标题组件 | +60 |
| **`web/src/components/chat/SessionSidebar.vue`** | 重构 + overlap bug 修复 + actions 改 right-click | +60 / -90 |
| **`web/src/views/chat/ChatViewSSE.vue`** | 3-zone 重构 + 顶栏精简 + 输入栏 segmented | +120 / -80 |
| **`web/src/stores/chatSessions.ts`** | sortedSessions 排序逻辑加 is_pinned desc | +3 |
| **`web/src/views/mobile/chat/MobileChatView.vue`** | 移动端布局同步 | +30 / -10 |
| **`web/src/components/mobile/MobileHeader.vue`** | 简化（搜索/主题下沉） | +20 / -30 |
| **`web/src/components/mobile/MobileInputBar.vue`** | 加 MobileThinkingModeSwitch | +25 |
| **`web/src/assets/variables.css`** | 新增 --icon-size-* + --icon-color-* token + dark 块 | +20 |
| **`web/src/components/mobile/MobileThinkingModeSwitch.vue`** | NEW 移动端 segmented 简化版 | +60 |
| **`web/tests/unit/__tests__/NavRail.test.js`** | NEW NavRail 渲染 + 7 button a11y test | +120 |
| **`web/tests/unit/__tests__/ThinkingModeSwitch.test.js`** | NEW v-model 双向绑定 + onUpdate test | +80 |
| **`web/tests/visual/desktop/v78-ui-redesign.spec.mjs`** | NEW Playwright 视觉回归 baseline | +60 |
| **`memory/ui-redesign-v78-2026-06-30.md`** | NEW 8 铁律 + 4 commit 链 | +250 |

**总计**: ~1240 行净增，~3 文件删旧代码

### 3.7 子 plan ③ 复用 utilities

| 现有 | 复用方式 |
|---|---|
| `web/src/components/chat/SearchPalette.vue` | 完全复用，仅去掉 trigger button，⌘K 快捷键保留 |
| `web/src/components/mobile/MobileActionSheet.vue` | 完全复用给 SessionSidebar right-click 弹 5 actions |
| `web/src/stores/useUiStore.js` `useDeepThinking` (44, 66) | 直接绑定 ThinkingModeSwitch segmented control |
| `web/src/stores/chatSessions.ts` `setPinned`, `setTags` (294-308, 275-289) | 完全复用 Phase 6 helper |
| `web/src/stores/useThemeStore.js` `toggle()` (90-92) | 直接调，ThemeSettingsDrawer 包裹 |
| `element-plus/icons-vue` icons | Search / MagicStick / Lightning / Cpu / Moon / Sunny / Picture / Paperclip / Microphone 等 |
| CLAUDE.md v60-v67 dark mode 教训 | 任何新 dark 规则放非 scoped `<style>` 块末尾 |
| CLAUDE.md a11y 4-attr 铁律 (line 822, 853, 915) | 每个 button / textarea / input 都有 `id` + `name` + `aria-label` + `title` |
| CLAUDE.md 752 行铁律 | 部署必做 `npm run build` + `git add -f web/dist/` |
| CLAUDE.md v76 Playwright visual regression | 任何 nav rail / input bar 改动用 `npx playwright test --update-snapshots` 重新 baseline |

---

## 4. 实施时间线

### 4.1 W69 子 plan ② 时间线（1 周）

```
W69 (2026-07-31 ~ 2026-08-04)
┌──────────────┬──────────────┬──────────────┬──────────────┬──────────────┐
│ D1 (Thu)     │ D2 (Fri)     │ D3 (Mon)     │ D4 (Tue)     │ D5 (Wed)     │
│ 5 agents 启动│ 7 维算法完成 │ 5 道防线实施 │ KB 闭环端到端│ Dashboard +  │
│ (并行派工)   │ (Agent #1)   │ (Agent #2)   │ (Agent #4)   │ smoke (Agent │
│              │              │ + Agent #3   │              │ #5)          │
└──────────────┴──────────────┴──────────────┴──────────────┴──────────────┘
                                              ↓
                                          W69 grand closure
                                          (主指挥协调)
```

**W69 DoD**:
- [ ] 7 维评分算法落地 + 权重可配置 (`config/score_weights.json`)
- [ ] save_to_kb.py 5 道防线全启用
- [ ] Celery `auto_intake_rollback_task` 部署
- [ ] KB 闭环端到端跑通 (评测 → 5 防线 → 入库 → 抽检 → 回滚)
- [ ] Dashboard MVP 4 指标卡显示
- [ ] CI smoke 200 题 < 5min 通过

### 4.2 W70 子 plan ③ 时间线（1 周）

```
W70 (2026-08-07 ~ 2026-08-11)
┌──────────────┬──────────────┬──────────────┬──────────────┬──────────────┐
│ D1 (Thu)     │ D2 (Fri)     │ D3 (Mon)     │ D4 (Tue)     │ D5 (Wed)     │
│ 4 agents 启动│ NavRail 完成 │ TS + BC 完成 │ ChatViewSSE  │ 移动端同步 + │
│ (并行派工)   │ (Agent #1)   │ (Agent #2)   │ 3-zone 重构  │ 视觉回归 +   │
│              │              │              │ (Agent #3)   │ 沉淀 (Agent  │
│              │              │              │              │ #4)          │
└──────────────┴──────────────┴──────────────┴──────────────┴──────────────┘
                                              ↓
                                          W70 grand closure
                                          (主指挥协调)
```

**W70 DoD**:
- [ ] NavRail 桌面端 + 移动端双栈架构
- [ ] ThinkingModeSwitch 3 档模式 + a11y 4-attr 全套
- [ ] ChatBreadcrumb 中央标题 + breadcrumb path
- [ ] SessionSidebar overlap bug 修复
- [ ] 🧠🧠 双 toggle 冲突彻底解决
- [ ] 顶栏图标认知负担 → 0
- [ ] Playwright visual regression baseline 重建
- [ ] vitest + pytest 全过 (0 regression)

### 4.3 W69+W70 合计

- 总投入: 86h (58h 子 plan ② + 28h 子 plan ③)
- 总时长: 2 周
- 主指挥协调: 2 次 grand closure (W69 + W70)
- 0 production code 改动铁律: 待主指挥决策 (子 plan ② 涉及后端 + 前端, 子 plan ③ 涉及前端)
- 锚点范式: 91 → ~120 (单批 15 守恒 × 2 批 = 30 守恒)

---

## 5. W69 派工预排（5 agents 子 plan ②）

### 5.1 Agent #1: 7 维评分算法实施

**任务**:
- 创建 `tests/qa-bench/scoring/seven_dim.py` (~200 行)
- 创建 `tests/qa-bench/scoring/weights.json` (~30 行)
- 扩展 `tests/qa-bench/runner.py` 支持新 JSONL schema + 7 维评分
- 单元测试 24 个 (每个维度 3 测试 + 边界)

**复用 utilities**:
- `tests/qa-bench/runner.py` (536 行) — 主流程扩展
- `tests/qa-bench/gen500.py` (1490 行) — 基类继承
- `app/utils/llm_client.py` — Claude API

**风险**: 权重争议需团队拍板 (10/25/30/5/15/10/5 默认 vs 自定义)

### 5.2 Agent #2: save_to_kb.py 5 道防线

**任务**:
- `tests/qa-bench/kb_queue/dedup.py` (~80 行) — embedding 余弦相似度 ≥ 0.95
- `tests/qa-bench/kb_queue/length_filter.py` (~40 行) — 长度 50-4000
- `tests/qa-bench/kb_queue/llm_refusal.py` (~60 行) — LLM 拒答检测
- `tests/qa-bench/kb_queue/sensitive_words.py` (~50 行) — 28 成员 + 8 placeholder + 11 filler
- 重写 `tests/qa-bench/save_to_kb.py` 集成 5 防线

**复用 utilities**:
- `app/utils/pgvector.py` — embedding 检索
- `app/utils/llm_client.py` — Claude API 拒答判别
- `docs/known_members.json` — 28 成员黑名单

**风险**: 高 (灰度期需手动监控错答案污染)

### 5.3 Agent #3: Celery auto_intake_rollback_task

**任务**:
- `app/services/qa_bench_tasks.py` (~100 行) — Celery task
- 配置 `app/core/celery_app.py` beat schedule (每天 4:00)
- 告警: admin notification 集成
- 单元测试 12 个 (idempotent + 7 天 review + 引用失效)

**复用 utilities**:
- `app/services/task_service.py:auto_purge_trash_task` — Celery 模式
- `app/services/notification_service.py` — 通知
- `app/core/celery_app.py` — beat schedule

**风险**: 中 (回滚必须 idempotent，错误回滚会污染 KB)

### 5.4 Agent #4: KB 闭环端到端

**任务**:
- 集成 Agent #1+#2+#3 产出
- 端到端测试 (e2e) 30 个场景:
  - 正常 pass → 入库
  - 5 道防线任一 fail → 拒绝
  - 24h 后 grounding ref 失效 → 自动回滚
  - 下游点击 < 3 → 自动回滚
  - 负反馈 > 10% → 告警 + 暂停 AUTO_KB_INTAKE_ENABLED
- pytest 集成测试 8 个

**复用 utilities**:
- `tests/integration/conftest.py` — test DB stack
- `tests/qa-bench/runner.py` — 跑评测
- `app/services/qa_bench_tasks.py` — 回滚 task

**风险**: 高 (全链路集成测试 + Docker compose 部署)

### 5.5 Agent #5: Dashboard MVP + CI smoke 200 题

**任务**:
- `web/src/views/admin/QaBenchDashboard.vue` (~400 行) — 4 指标卡 + 详情页
- `web/src/api/qaBenchDashboard.js` (~60 行) — 4 端点 (入库数 / 通过率 / 抽检数 / 告警数)
- `tests/qa-bench/ci/smoke_200.py` (~150 行) — smoke 套件
- `.github/workflows/qa-bench-smoke.yml` (~30 行) — GitHub Actions
- 单元测试 8 个 (Dashboard 4 指标卡渲染)

**复用 utilities**:
- `web/src/components/common/StatCard.vue` — 4 指标卡模板
- `web/src/views/admin/AgentTracesView.vue` — Dashboard 模式
- `tests/qa-bench/gen500.py` — 200 题筛选 (`tags=["hot_path", "regression_smoke"]`)

**风险**: 低 (复用 web 模板 + 现有 qa-bench 框架)

---

## 6. 主指挥决策（关键决策点）

### 6.1 子 plan ② 是否 W69 派工？

**建议**: ✅ **W69 派工**

**理由**:
1. **锚点范式增长空间**: W68 第 8 批 90 → W69 子 plan ② 派 5 agents + W70 子 plan ③ 派 4 agents = 估 100+
2. **0 production code 改动铁律可守恒**: 子 plan ② 全部新增文件 (15+ 新文件)，不动现有 production code
3. **闭环路线明确**: save_to_kb.py 改造 + 5 道防线 + auto_intake_rollback + Dashboard + CI smoke = 端到端闭环
4. **风险可控**: 灰度发布开关 `AUTO_KB_INTAKE_ENABLED=False` 默认关，可分阶段手动开启
5. **主指挥可拍板权重争议**: 7 维权重 10/25/30/5/15/10/5 默认值可由主指挥直接拍板

### 6.2 子 plan ③ 是否 W70 派工？

**建议**: ✅ **W70 派工** (W69 完成后立即启动)

**理由**:
1. **不依赖子 plan ②**: UI redesign 独立于 qa-bench，可并行/串行
2. **用户痛点明确**: 4 个现存问题 (overlap / 🧠🧠 / aria-label / 顶栏拥挤) 都是用户可观察的
3. **复用现有 utilities**: NavRail/ThinkingModeSwitch/ChatBreadcrumb 全部基于现有 useUiStore + useThemeStore + SessionSidebar 模式
4. **风险可控**: Playwright baseline 重建是已知流程，dark mode + a11y 4-attr 已有铁律

### 6.3 关键决策点（待主指挥拍板）

| # | 决策项 | 选项 | 建议 | 主指挥决策 |
|---|---|---|---|---|
| 1 | 7 维权重默认值 | 10/25/30/5/15/10/5 / 自定义 | 10/25/30/5/15/10/5 默认值 | ⏸ 待拍板 |
| 2 | save_to_kb.py 是否 W69 默认 `AUTO_KB_INTAKE_ENABLED=False` 灰度 | True / False | False 默认 + 7 天手动审核 | ⏸ 待拍板 |
| 3 | KB 闭环端到端测试是否 Docker compose 物理隔离栈 | 物理隔离 / 共享 test DB | 物理隔离栈 (D6 Phase 1 实施) | ⏸ 待拍板 |
| 4 | 子 plan ②/③ 是否合并 PR | 合并 / 分开 | 分开 (子 plan ② 后端为主 + 子 plan ③ 前端为主) | ⏸ 待拍板 |
| 5 | W69 派工数量 | 3 / 5 / 7 agents | 5 agents (子 plan ② 全覆盖) | ⏸ 待拍板 |
| 6 | W70 派工数量 | 2 / 4 / 6 agents | 4 agents (子 plan ③ 全覆盖) | ⏸ 待拍板 |
| 7 | W69 起始日期 | 2026-07-31 (Mon) / 其他 | 2026-07-31 | ⏸ 待拍板 |

### 6.4 与 W19 选项 A 的关系

**W19 选项 A**: 4 留未来 PR 不发起新排期（已维持）

**冲突分析**:
- 子 plan ② qa-bench 7 维评分 + KB 闭环 — W19 之前**已部分实施** (qa-bench-v3-w1-2026-06-30 已 PARTIAL) → 不算新排期，**算遗留闭环**
- 子 plan ③ UI redesign — **W19 之前未实施** (W19 4 留未来 PR 不含此) → **新增排期**
- **结论**: 子 plan ② 闭环不违反 W19 选项 A；子 plan ③ UI redesign **轻微违反** (新增排期 1 项)

**主指挥建议决策**:
- 子 plan ②: ✅ W69 派工 (闭环遗留)
- 子 plan ③: ✅ W70 派工 (新增排期 1 项，但与 W19 维护性 baseline 守恒 + 跨主题收口基调一致)

### 6.5 与 0 production code 改动铁律的关系

**子 plan ②** (qa-bench):
- 新增 15+ 文件 (`tests/qa-bench/scoring/*` + `tests/qa-bench/kb_queue/*` + `tests/qa-bench/ci/*` + `app/services/qa_bench_tasks.py`)
- 修改 2 个文件 (`tests/qa-bench/save_to_kb.py` 重写 + `app/config.py` 加 setting)
- **判定**: **可守恒** — 主框架不动，只新增测试基础设施 + 1 个新 Celery task

**子 plan ③** (UI redesign):
- 新增 5 文件 (NavRail / ThinkingModeSwitch / ChatBreadcrumb / MobileThinkingModeSwitch / 测试)
- 修改 11 文件 (SessionSidebar / ChatViewSSE / stores / mobile 同步)
- **判定**: **修改 production code 11 文件** — **不守恒 0 production code 改动铁律**

**主指挥建议决策**:
- 子 plan ②: ✅ W69 派工 (0 production code 改动铁律可守恒)
- 子 plan ③: ⚠️ W70 派工 (0 production code 改动铁律**不守恒**) — 主指挥决策是否破例

### 6.6 与锚点范式的关系

**预估锚点范式增长**:
- W68 第 8 批 main HEAD: 90 守恒
- W69 子 plan ② (5 agents): +5 守恒 = 95
- W70 子 plan ③ (4 agents): +4 守恒 = 99
- **合计**: W70 末锚点范式 ~100 (W68-W70 累计 +10 守恒)

**守恒纪律**:
- 每个 agent 提交独立 1 守恒
- W69 + W70 grand closure 各 +1 主指挥协调守恒
- 失败 agent 不扣分 (主指挥决定重派或合并)

---

## 7. 验证 (DoD)

### 7.1 子 plan ② DoD (W69)

```bash
# 1. 7 维评分算法
PYTHONIOENCODING=utf-8 PYTHONUTF8=1 \
  pytest tests/qa-bench/scoring/test_seven_dim.py -v
# 期望: 24 PASSED

# 2. 5 道防线
PYTHONIOENCODING=utf-8 PYTHONUTF8=1 \
  pytest tests/qa-bench/kb_queue/test_*.py -v
# 期望: 36+ PASSED (每个防线 6-8 测试)

# 3. Celery auto_intake_rollback_task
PYTHONIOENCODING=utf-8 PYTHONUTF8=1 \
  pytest tests/unit/test_qa_bench_tasks.py -v
# 期望: 12 PASSED

# 4. KB 闭环端到端 (Docker compose)
docker compose -f tests/integration/docker-compose.yml up -d
PYTHONIOENCODING=utf-8 PYTHONUTF8=1 \
  pytest tests/integration/test_kb_closed_loop.py -v
# 期望: 8 PASSED

# 5. Dashboard MVP
cd /e/microbubble-agent/web && npm run build
# 期望: 0 警告

# 6. CI smoke 200 题 < 5min
PYTHONIOENCODING=utf-8 PYTHONUTF8=1 \
  pytest tests/qa-bench/ci/smoke_200.py -v --timeout=300
# 期望: 200 PASSED, 时长 < 5min
```

### 7.2 子 plan ③ DoD (W70)

```bash
# 1. NavRail 渲染
cd /e/microbubble-agent/web && npx vitest run \
  src/components/chat/__tests__/NavRail.test.js
# 期望: 7+ PASSED (每个 icon button 1 测试)

# 2. ThinkingModeSwitch v-model
cd /e/microbubble-agent/web && npx vitest run \
  src/components/chat/__tests__/ThinkingModeSwitch.test.js
# 期望: 8+ PASSED

# 3. ChatBreadcrumb
cd /e/microbubble-agent/web && npx vitest run \
  src/components/chat/__tests__/ChatBreadcrumb.test.js
# 期望: 5+ PASSED

# 4. Playwright 视觉回归
cd /e/microbubble-agent/web && \
  TEST_TOKEN=<jwt> npx playwright test \
  tests/visual/desktop/v78-ui-redesign.spec.mjs \
  --project=desktop-chrome
# 期望: baseline 重建 + 0 fail

# 5. 端到端 SSE 流测试 (thinking mode 联动)
curl -N -sk -X POST http://localhost:5173/.../api/v1/chat/stream \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message":"微纳米气泡 zeta 电位","session_id":"s1","thinking_mode":"deep"}'
# 期望: 看到 retrieval_assessment event (deep 模式)
```

### 7.3 Manual smoke test (子 plan ③)

| 场景 | 期望 | 验证方式 |
|---|---|---|
| 桌面端首次打开 /chat | nav rail 出现在左侧, 中央显示 ChatBreadcrumb, 右侧 [+ FAB] 永远可见, 输入栏上方有 segmented "⚡快速 \| ⚖平衡 \| 🧠深度" | 浏览器 console 无 error |
| 桌面端 hover session 卡片 | 不再显示 ✎🔗📤🏷× button，title 永远完整 | 鼠标 hover vs right-click |
| 桌面端 right-click session | 弹 ActionSheet 含 5 actions (重命名/分享/导出/标签/删除) | 鼠标右键验证 |
| 桌面端点击 ⚡ 快速 | useDeepThinking=false + useSelfRag=false，下次发问跳过 Self-RAG gate | Pinia devtools 验证 |
| 桌面端点击 🧠 深度 | useDeepThinking=true + useSelfRag=true，下次发问走 Phase 0.5 gate | Pinia devtools 验证 |
| 桌面端点击右侧 [+ FAB] | 创建新 session 自动切换 | 行为验证 |
| 移动端打开 /chat | MobileHeader 只保留 ☰ menu + ChatBreadcrumb + 头像 dropdown | DevTools 切 mobile |
| 移动端长按 session | 弹 MobileActionSheet 含 5 actions + `navigator.vibrate(10)` | touch 验证 |
| 6 主题下 nav rail / FAB / segmented | 颜色正确跟随主题色，全部元素对比度 ≥ WCAG AA 4.5:1 | DevTools computed styles |
| PWA 离线后打开 /chat | 显示 nav rail + 上次缓存的 session list | DevTools Network → offline |
| 键盘 Tab 导航 | nav rail → 中央 → input bar → [+FAB] → thinking switch 顺序 | Tab 键验证 |

---

## 8. 风险与缓解

### 8.1 子 plan ② 风险

| 风险 | 等级 | 缓解 |
|---|---|---|
| **全自动入库污染 KB** | **高** | 5 道防线（分数门控 + 7天 rollback + dashboard 监控 + 灰度 flag + 白名单） |
| **LLM 拒答检测误判** | 中 | 拒答标记集合（"我不知道" / "无法回答" / "incomplete"）需调参 + 人工抽检 |
| **embedding 去重漏检** | 中 | 0.95 阈值需调参 + 手动抽查边界 case |
| **Celery 任务重复执行** | 中 | `@app.task(ignore_result=True, expires=3600)` 防重复 |
| **权重争议** | 低 | 主指挥拍板 10/25/30/5/15/10/5 默认值，团队月度 review 调整 |
| **CI smoke 200 题超时** | 低 | 5min timeout + tags=["hot_path"] 筛选 |
| **Dashboard 性能** | 低 | 5min polling + cached query |

### 8.2 子 plan ③ 风险

| 风险 | 等级 | 缓解 |
|---|---|---|
| **桌面端 3-zone 改动太大，与 Playwright baseline 必然冲突** | **高** | `--update-snapshots` 重建 baseline + 自动 commit |
| **NavRail 移动端不持久占位** | 中 | `@media (max-width: 768px)` 内 NavRail `display: none` |
| **ThinkingModeSwitch v-model 死循环** | 低 | `watch(useDeepThinking, ...)` + emit 单向通信 |
| **⌘K 快捷键与浏览器冲突** | 低 | `e.metaKey \|\| e.ctrlKey` 区分 (SearchPalette 已用) |
| **icon button touch target < 44px** | 低 | EP icon 18px + touch-target-min: 44px token |
| **dark mode icon 对比度** | 中 | `--icon-color-primary` token 跟随主题 + dark mode 块 |
| **修改 production code 11 文件** | **0 production code 改动铁律不守恒** | 主指挥破例决策 |

### 8.3 跨子 plan 风险

| 风险 | 等级 | 缓解 |
|---|---|---|
| **W69+W70 跨度 2 周** | 中 | 锚点范式增长可控（+10 守恒），主指挥 grand closure 2 次 |
| **子 plan ② 与 D6 物理隔离栈部署冲突** | 中 | W68 第 7 批 A-3 已实施 in-process runner，W69 复用 |
| **子 plan ③ 与 v78 UI redesign 已部分实施冲突** | 低 | W70 是 v78 完整收官，W68 已部分实施的可直接复用 |
| **0 production code 改动铁律合计 13/19 不守恒** | 中 | 主指挥破例决策 (子 plan ② 可守恒 + 子 plan ③ 不守恒) |

---

## 9. 总结

### 9.1 子 plan ② + ③ 闭环逻辑

```
子 plan ① chat history 8 phase (W68 #043 已闭环 ✅)
    ↓
子 plan ② qa-bench 7 维 + KB 闭环 + Dashboard MVP (W69 派工 ⏸)
    ↓ 基础数据齐备
子 plan ③ UI redesign NavRail + ThinkingModeSwitch + ChatBreadcrumb (W70 派工 ⏸)
    ↓ 用户体验提升
chatgpt-structured-floyd 3 子 plan 100% 闭环
```

### 9.2 投资回报

**总投入**: 86h (58h 子 plan ② + 28h 子 plan ③)

**预期收益**:
- **qa-bench 体系**: 595 → 780 题 (+31%) + 7 维评分 + 自动入库闭环 + Dashboard MVP + CI 5min smoke
- **UI 升级**: 4 个现存痛点 (overlap / 🧠🧠 / aria-label / 顶栏拥挤) 全部解决 + 跨 desktop + mobile 双栈统一
- **KB 月增**: 50+ 候选 (全自动入库，5 道防线监控)
- **评测自动化率**: 0% → 95%
- **高分率**: 84% → 92%+

**关键纪律**:
- 已闭环 1/3 不返工 (子 plan ①)
- 子 plan ② 0 production code 改动铁律可守恒 (子 plan ③ 不守恒需主指挥破例)
- W19 选项 A 维持 (子 plan ② 算遗留闭环)
- 主指挥 grand closure × 2 (W69 + W70)

---

## 附录 A: 关键文件绝对路径速查

### 子 plan ② qa-bench
- `e:/microbubble-agent/tests/qa-bench/runner.py` (536 行) — 扩展 7 维评分
- `e:/microbubble-agent/tests/qa-bench/gen500.py` (1490 行) — 基类继承
- `e:/microbubble-agent/tests/qa-bench/save_to_kb.py` (184 行) — 重写 5 道防线
- `e:/microbubble-agent/tests/qa-bench/scoring/seven_dim.py` (NEW) — 7 维评分
- `e:/microbubble-agent/tests/qa-bench/kb_queue/dedup.py` (NEW) — 去重
- `e:/microbubble-agent/tests/qa-bench/ci/smoke_200.py` (NEW) — smoke 套件
- `e:/microbubble-agent/app/services/qa_bench_tasks.py` (NEW) — Celery auto_intake_rollback
- `e:/microbubble-agent/web/src/views/admin/QaBenchDashboard.vue` (NEW) — Dashboard MVP
- `e:/microbubble-agent/.github/workflows/qa-bench-smoke.yml` (NEW) — CI smoke

### 子 plan ③ UI redesign
- `e:/microbubble-agent/web/src/components/chat/NavRail.vue` (NEW) — 左侧 nav rail
- `e:/microbubble-agent/web/src/components/chat/ThinkingModeSwitch.vue` (NEW) — segmented control
- `e:/microbubble-agent/web/src/components/chat/ChatBreadcrumb.vue` (NEW) — 中央标题
- `e:/microbubble-agent/web/src/views/chat/ChatViewSSE.vue` — 3-zone 重构
- `e:/microbubble-agent/web/src/stores/useUiStore.js` — `useDeepThinking` (44, 66)
- `e:/microbubble-agent/web/src/stores/useThemeStore.js` — `toggle()` (90-92)

### 配置
- `e:/microbubble-agent/app/config.py` — `AUTO_KB_INTAKE_ENABLED` (新增)

### Memory
- `C:/Users/pc/.claude/projects/e--microbubble-agent/memory/w68-route-9-b4-chatgpt-w69-plan-2026-07-24.md` (NEW) — 本任务沉淀

---

**Plan W69 子 plan ②/③ 调研完成，请主指挥决策是否 W69/W70 派工。**

主指挥决策关键点：
1. **W69 派工 5 agents 子 plan ②** (qa-bench 7 维 + 5 道防线 + Dashboard + CI smoke) — 0 production code 改动铁律可守恒
2. **W70 派工 4 agents 子 plan ③** (NavRail + ThinkingModeSwitch + ChatBreadcrumb) — 0 production code 改动铁律不守恒需主指挥破例
3. **总投入 86h + 锚点范式 +10 守恒 (90 → 100)**
4. **W19 选项 A 维持** (子 plan ② 算遗留闭环 + 子 plan ③ 新增排期 1 项)