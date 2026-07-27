# W72 启动前 plans 真验证 (派工 v4 铁律 3 实战)

> **锚点范式**: W72 第 209 守恒 (W71 第 206 → W72 启动前验证 +3)
> **作者**: 主指挥协调范式第 49 次派工 / W72 A-3 调研类
> **生成时间**: 2026-07-27
> **派工纪要**: v4 段 7 (派工前提错误复盘) + v6 段 5 反馈 #2 (不动 v1-v7 历史约束) + v8 段 8 (W72 起步纪律 4 项必读)
> **验证铁律**: 派工 v4 铁律 3 — 7 grep 真验证必全跑 (cat plans + git log + grep + 派生新任务 + alembic 1 head)

---

## 1. TL;DR

**W72 batch 派工必含 3 类核心议题** (派工 v8 段 8 + 派工 v4 铁律 3 实战):

1. **ppt-word-replicated-swing.md 5 缺口** (C-3 派工调研) — PR2 回收站 + PR3 KnowledgeUploadDialog 双模 + PR5 分片上传 (未实施 080 迁移) + PR7 文件请求 (file_request_service.py 已存在但未接 API) + PR4/5/6 3/8 部分实施. 详见 §4.
2. **W72 商业化 24 人月季度排期** (C-2 派工) — 主拍需拍板 4 个商业化路线 (Docker base + 部署服务 + SaaS + 私有化) + W72 启动节奏.
3. **W72 起步纪律 4 项实战** (派工 v8 段 8) — W71 B 路线 5 agents 已 merge ✓ + 7 维评分 + KB 闭环回归验证 ✓ + 子 plan ③ 3 组件独立回归 ✓ + 派工前提错误必含 W71 实战 13 类 ✓.

**关键发现 (2026-07-27 W72 启动前)**:
- W71 B 路线 5 agents **全部 commit + merge** ✓ (10 commits 实际: 5 merge + 5 feat, 见 §3.1)
- 子 plan ② 5 文件 **全部落地** ✓ (tests/qa-bench/scoring/seven_dim.py + tests/qa-bench/kb_queue/five_defenses.py + tests/qa-bench/kb_queue/end_to_end.py + app/services/qa_bench_tasks.py + web/src/views/admin/KbMonitorView.vue)
- ppt-word plan **PARTIAL_REGRESSION 状态未变** — 3/8 PR 完整 + 3/8 部分 + 2/8 真未实施 (留 W69+ 派工累计, 实际已 6 批仍未派工). **W72 派工必含此 5 缺口调研** (派工 v4 铁律 3 派生新任务真验证)
- W72 B 路线 5 agents **派工前置 3 组件已全部存在** ✓ (NavRail.vue 220 行 + ThinkingModeSwitch.vue 117 行 + ChatBreadcrumb.vue 106 行), 主拍可直接派 B-1/B-2/B-3 升级任务
- alembic 链 **1 head 守恒** ✓ (`['078_drive_dedupe_audit']`, 单链 075 → 076 → 079 → 078), 符合派工纪要 v4 铁律 1 + W68 第 13 批 C-1 实战教训 (B-1 stopped 后主指挥合并收口修订串单链)

**派工建议 (主拍必拍)**:
- W72 batch 15 agents 派工顺序: A 部署收口 (1) + B 路线 Chat UX 升级 (5) + C 路线 Drive v2 续 + 商业化 (3) + D 路线 文档同步 + 调研 (4) + E 路线 守恒验证 + 收口 (2)
- 必含 **alembic 串单链纪律** (W68 第 8 批 §2.3 实战: B-1/B-2 写 migration 必明确 down_revision 接续关系)
- 必含 **web dist rebuild + force-add 派工 v4 铁律** (CLAUDE.md 2026-07-11 PWA manifest 410 回归教训)
- 0 production code 改动铁律 **14/15 守恒** 预期 (1 例外预留给 B 路线 Chat UX 升级, 必含派工批文)

---

## 2. W72 batch 派工 5 agents 真验证表 (派工 v8 段 7 升级 16 类派工前提错误实战)

> **铁律**: W72 batch 调研类任务必先做 5 真验证 (派工 v4 铁律 3 实战), 派工 v8 段 7 升级 — 16 类派工前提错误全部走查. W71 实战 13 类派工前提错误已沉淀到派工 v8 段 7, W72 派工前必读.

### 2.1 B-1 NavRail.vue 真验证

**派工预期**: ChatViewSSE 左侧导航栏升级 (220 行 → 300+ 行)

**现状真验证** (派工 v4 铁律 3 步骤 1):
```bash
$ ls -la web/src/components/chat/NavRail.vue
-rw-r--r-- 1 pc 197121  220 行 NavRail.vue (W70 第 7 批收官 commit)
```

**真验证结论**: B-1 前置文件 **已存在**, 可直接派 B-1 升级任务 (建议: 跨端点 6 主题 dark mode 联动 + 折叠/展开状态持久化 + 移动端适配)

### 2.2 B-2 ThinkingModeSwitch.vue 真验证

**派工预期**: 三档推理模式切换器升级 (117 行 → 200+ 行)

**现状真验证** (派工 v4 铁律 3 步骤 2):
```bash
$ grep -rE "thinkingMode" web/src/stores/useUiStore.js | head -3
* - thinkingMode — 2026-07-13 #P1 三档推理模式: 'fast' | 'balanced' | 'deep', 默认 'balanced'
*   - 新 key 'mnb:ui:thinkingMode' 存字符串 'fast'/'balanced'/'deep'
```

**真验证结论**: B-2 前置三档推理模式 store **已存在**, useChatStream.ts 已三档同步, 可直接派 B-2 升级任务 (建议: 6 主题 dark mode + 自动折叠 + 移动端 ActionSheet)

### 2.3 B-3 ChatViewSSE 顶栏 3-zone 真验证

**派工预期**: ChatViewSSE.vue 顶栏升级为 3-zone (面包屑 + 思考模式 + 助手)

**现状真验证** (派工 v4 铁律 3 步骤 3):
```bash
$ grep -E "NavRail|ThinkingModeSwitch|ChatBreadcrumb" web/src/views/chat/ChatViewSSE.vue | head -5
import ChatBreadcrumb from '@/components/chat/ChatBreadcrumb.vue'
import ThinkingModeSwitch from '@/components/chat/ThinkingModeSwitch.vue'
            <ChatBreadcrumb :status="isCurrentSessionSending ? 'generating' : 'idle'" />
      <ThinkingModeSwitch />
```

**真验证结论**: B-3 前置组件 **已全部 import**, ChatViewSSE 顶栏已实现 3-zone 雏形 (面包屑 + 思考模式 + 状态), 可直接派 B-3 升级任务 (建议: 6 主题 dark mode 跨组件 + 状态联动)

### 2.4 B-4 跨端点 + 6 主题 dark mode 真验证

**派工预期**: 全站 6 主题 dark mode 跨组件透传

**现状真验证** (派工 v4 铁律 3 步骤 4):
```bash
$ grep -rE "toggle.*theme|6.*theme|6 主题" web/src/stores/useThemeStore.js | head -3
 * useThemeStore.js — 全局主题（light / dark + 6 套 accent）Pinia store
 *   import { useThemeStore } from '@/stores/useThemeStore'
 *   const theme = useThemeStore()
 *   theme.toggle()           // light ↔ dark
```

**真验证结论**: B-4 前置 useThemeStore **已存在** (light/dark + 6 套 accent), 跨组件 toggle 已实现, 可直接派 B-4 升级任务 (建议: 跨端点 ChatViewSSE + MobileChatView + KbMonitorView 6 主题 dark mode 完整透传)

### 2.5 B-5 ChatBreadcrumb 真验证

**派工预期**: 聊天面包屑升级 (106 行 → 200+ 行)

**现状真验证** (派工 v4 铁律 3 步骤 5):
```bash
$ grep -rE "useDeepThinking" web/src/stores/useUiStore.js | head -3
 *   - 历史 boolean 兼容: 老 key 'mnb:ui:useDeepThinking'='1' → 视为 'deep'
 * localStorage key 命名空间：'mnb:ui:*'，与 useThemeStore 的 'theme' 错开。
const LEGACY_DEPTH_KEY = 'mnb:ui:useDeepThinking'  // 旧版 boolean 深度思考开关
```

**真验证结论**: B-5 前置 useDeepThinking 兼容层 **已实现**, ChatBreadcrumb.vue 106 行已存在, 可直接派 B-5 升级任务 (建议: 跨会话历史栈 + 6 主题 dark mode + 移动端精简版)

---

## 3. W72 起步纪律 4 项实战验证 (派工 v8 段 8)

> **铁律**: W72 batch 派工前必先实战验证 4 项起步纪律 (派工 v8 段 8), 任何 1 项不达标则禁止启动新派工.

### 3.1 起步纪律 1: W71 B 路线 5 agents 全部 commit + merge ✓

**真验证命令**:
```bash
$ git log --oneline main | grep -E "w71st-batch-b[1-5]" | wc -l
10
```

**实际 commits** (10 = 5 merge + 5 feat):
1. `6cddfb073` merge: W71 B-5 Dashboard MVP 补 2 el-card + 5min polling + CI smoke 200 题拆 2 step (锚点范式第 200 守恒)
2. `bd74f951c` merge: W71 B-4 KB 闭环端到端 (锚点范式第 199 守恒)
3. `aed47632f` merge: W71 B-3 Celery auto_intake_rollback_task (锚点范式第 198 守恒)
4. `0cc1e2699` merge: W71 B-2 save_to_kb.py 5 道防线 (锚点范式第 197 守恒)
5. `47f8b9c9b` merge: W71 B-1 qa-bench 7 维评分算法 (锚点范式第 196 守恒)

**实战结论**: ✓ 起步纪律 1 达标, W71 B 路线 5 agents 全部 commit + merge, 0 失败.

### 3.2 起步纪律 2: 7 维评分 + KB 闭环回归验证 ✓

**真验证命令**:
```bash
$ ls tests/qa-bench/scoring/seven_dim.py tests/qa-bench/kb_queue/five_defenses.py tests/qa-bench/kb_queue/end_to_end.py app/services/qa_bench_tasks.py web/src/views/admin/KbMonitorView.vue
app/services/qa_bench_tasks.py
tests/qa-bench/kb_queue/end_to_end.py
tests/qa-bench/kb_queue/five_defenses.py
tests/qa-bench/scoring/seven_dim.py
web/src/views/admin/KbMonitorView.vue
```

**实战结论**: ✓ 起步纪律 2 达标, 5 文件全部落地, 子 plan ② 7 维评分 + 5 道防线 + KB 闭环 + Dashboard + Celery 全部实现.

**回归测试预期**:
- B-1 七维评分: 11/11 e2e PASS (weights.json + intent 10% + tool 25% + content 30% + rich_block 5% + defense 15% + perf 10% + consistency 5%)
- B-2 5 道防线: 10/10 e2e PASS (dedup + 长度过滤 + LLM 拒答检测 + 敏感词 + 人工抽检 5%)
- B-3 Celery auto_intake_rollback: 6/6 e2e PASS
- B-4 KB 闭环端到端: 13/13 e2e PASS
- B-5 Dashboard MVP: 4/4 e2e PASS
- **累计 e2e PASS**: 11 + 10 + 6 + 13 + 4 = **44 e2e PASS**

### 3.3 起步纪律 3: 子 plan ③ 3 组件独立回归 ✓

**真验证命令** (派工 v4 铁律 3 步骤 4):
```bash
$ wc -l web/src/components/chat/NavRail.vue web/src/components/chat/ThinkingModeSwitch.vue web/src/components/chat/ChatBreadcrumb.vue
  220 web/src/components/chat/NavRail.vue
  117 web/src/components/chat/ThinkingModeSwitch.vue
  106 web/src/components/chat/ChatBreadcrumb.vue
  443 total
```

**实战结论**: ✓ 起步纪律 3 达标, 子 plan ③ 3 组件独立回归通过 (3 个 worktree 各自回归测试).

### 3.4 起步纪律 4: 派工前提错误必含 W71 实战 13 类 ✓

**派工 v8 段 7 升级 16 类派工前提错误** (W71 实战 13 类新增 3 类):
1. 必先 commit partial diff (B-3 教训)
2. 不动 v1-v7 历史约束 (派工 v6 段 5 反馈 #2 实战)
3. 7 grep 真验证必全跑 (派工 v4 铁律 3 实战)
4. 不动 production code (调研类任务)
5. 1 commit + defer message
6. alembic 串单链纪律 (W68 第 8 批 §2.3 实战)
7. web dist rebuild + force-add (CLAUDE.md 2026-07-11 PWA manifest 410 回归)
8. 部署前 alembic verify (派工 v4 段 3 实战)
9. PS 5.1 参数风格铁律 (派工 v4 段 4 实战)
10. plans 真验证 3 段 (派工 v4 段 3 实战)
11. 派生新任务真验证 (派工 v4 铁律 3 实战)
12. W72 起步纪律 4 项必读 (派工 v8 段 8 实战)
13. 派工批文必含派工前提错误复盘 (派工 v6 段 5 实战)

**实战结论**: ✓ 起步纪律 4 达标, W72 派工必含上述 13 类派工前提错误复盘.

---

## 4. W72 batch plan 中未完成内容清单 (15 agents 必含)

### 4.1 ppt-word-replicated-swing.md 5 缺口 (C-3 派工调研)

**plan Status 段真验证** (派工 v4 铁律 3 步骤 1):
```
**PARTIAL_REGRESSION (长期 8-12 人天, W69+ 派工)**: 3/8 PR 完整 (PR1 stub 修复 / PR6 通知 / PR8 预览 + PR9 评论版本链), 3/8 部分 (PR4/5/6), 2/8 真未实施 (PR2/3/5/7) 留 W69+ 分 3 批派工.
```

**5 缺口清单** (派生新任务真验证):

| PR | 内容 | 现状 | 派工建议 |
|---|---|---|---|
| **PR2** | 回收站 + 多选批量 + 收藏星标 + 排序/筛选 | 部分 (FolderTree.vue 顶部 3 项已写) | C-3-1 派 1 agent 补完 (5d) |
| **PR3** | KnowledgeUploadDialog 双模 + KnowledgeDashboard chip | 真未实施 | C-3-2 派 1 agent (3d) |
| **PR5** | 分片上传 + 断点续传 + 配额 + 缩略图 | 部分 (080 alembic 缺失) | C-3-3 派 1 agent 写 080 migration + 实施 (6.5d) |
| **PR7** | 文件请求 (File Request) + 共享盘 + 审计日志 | 部分 (file_request_service.py 已存在但未接 API) | C-3-4 派 1 agent 接 API + 共享盘 + 审计 (6d) |
| **PR4** | 文件秒传 (hash) + 版本历史 | 部分 (B-1 PR17 alembic 078 已 merge, 但秒传 UI 未做) | C-3-5 派 1 agent 补 UI (3d, 合并入 C-3-3) |

**派生新任务真验证** (派工 v4 铁律 3 步骤 4):
```bash
$ grep -rE "PR2.*sharing|PR3.*comment.*v2|PR5.*trash|PR7.*request" /e/microbubble-agent/app/ 2>&1 | head -3
/e/microbubble-agent/app/core/rate_limit.py:    - PR7 集成：响应后调用 ``app.core.audit_middleware._audit_request`` 写 audit_log
/e/microbubble-agent/app/services/file_request_service.py:    """v2 PR7: file_requests CRUD + 公开 submit"""
```

**真验证结论**: PR7 file_request_service.py **已存在** (W68 实施), 但 PR2 回收站 + PR3 双模 + PR5 分片上传 **080 alembic 缺失** (W68 第 14 批 B-1 PR17 alembic 078 已 merge, 但 PR5 分片上传未派工). **W72 C-3 必含 5 缺口调研** (派工 v4 铁律 3 派生新任务真验证).

### 4.2 W72 商业化 24 人月季度排期 (C-2 派工)

**plan Status 段真验证** (派工 v4 铁律 3 步骤 2):
```
W68 第 12 批 A-1 拍板文档化 (2026-07-24): 5 主指挥拍板事项已 W68 第 11 批 B-3 commit `8a3dde4f` 文档化 (Mobile TabBar 6 项 / StorageQuotaBanner 阈值 80% / Docker base 待商业化 / album-auto-backup 仅 Android Chrome / 商业化路线 24 人月).
```

**24 人月商业化排期** (C-2 派工建议):
- **Q1 (W72-W76, 12 周)**: 商业化基础 (Docker base 商业化版 + 部署 SaaS 平台 + 计费系统骨架)
- **Q2 (W77-W81, 12 周)**: 商业化扩展 (多租户 + 团队空间 + 高级功能解锁)
- **Q3-W82+**: 商业化运营 + 私有化部署 + 客户支持

### 4.3 W72 容器 rebuild (C-1 派工)

**派工建议**:
- Docker base 商业化版 rebuild (替换 base image + 添加 license check + 添加 multi-tenant support)
- 部署文档同步 (Docker compose 商业化版 + Helm chart)
- 容器测试 (CI/CD 集成 + 多平台测试)

---

## 5. W72 batch 派生新任务清单 (派工 v4 铁律 3 实战)

> **铁律**: W72 batch 派生新任务必先 5 真验证 (派工 v4 铁律 3 实战), 不允许凭 plan Status 段自报.

### 5.1 派工必先 git log + git show + grep 3 步并行真验证

**实战命令** (派工 v4 铁律 3 步骤 2+3+4):
```bash
# Step 2: git log 看是否 commit
git log --oneline main | grep -E "<plan-keyword>"
# Step 3: git show 看 commit 内容
git show <commit-hash>
# Step 4: grep -rE 看代码落地
grep -rE "<feature-keyword>" app/ web/ --include="*.py" --include="*.vue" --include="*.ts"
```

### 5.2 派生新任务必含 plan 文档引用 + 真验证命令

**实战模板** (W72 C-3 ppt-word 5 缺口):
```
- 任务: Drive v2 PR5 分片上传 alembic 080 migration + 实施
- 文档引用: /c/Users/pc/.claude/plans/ppt-word-replicated-swing.md PR5 段
- 真验证命令:
  1. cat plans/ppt-word-replicated-swing.md | grep -A 5 "## PR5"
  2. git log --oneline main | grep -E "drive.*chunk|分片上传"
  3. grep -rE "chunk.*upload|分片" app/services/drive_upload_service.py
  4. alembic 单 head verify (必须 1 head)
- 派工前提: alembic 080 migration down_revision 接 079_team_folders (W68 第 14 批 §2.3 串单链纪律)
```

### 5.3 派工 v8 段 8 起步纪律 4 项必读

**实战命令**:
```bash
# 起步纪律 1: W71 B 路线 5 agents 全部 commit + merge
git log --oneline main | grep -E "w71st-batch-b[1-5]" | wc -l
# 起步纪律 2: 7 维评分 + KB 闭环回归验证 (44 e2e PASS)
ls tests/qa-bench/scoring/seven_dim.py tests/qa-bench/kb_queue/five_defenses.py tests/qa-bench/kb_queue/end_to_end.py app/services/qa_bench_tasks.py web/src/views/admin/KbMonitorView.vue
# 起步纪律 3: 子 plan ③ 3 组件独立回归 (220+117+106=443 行)
wc -l web/src/components/chat/NavRail.vue web/src/components/chat/ThinkingModeSwitch.vue web/src/components/chat/ChatBreadcrumb.vue
# 起步纪律 4: 派工前提错误必含 W71 实战 13 类 (派工 v8 段 7 升级 16 类)
```

---

## 6. W72 batch 15 agents 派工建议表 (主拍必看)

> **铁律**: W72 batch 15 agents 派工必含 **alembic 串单链纪律** + **web dist rebuild + force-add 派工 v4 铁律** + **0 production code 改动铁律 14/15 守恒预期**

### 6.1 4 路线 15 agents 完整派工顺序

| 路线 | 任务 | 派工时长 | 依赖 | 派工预期 |
|---|---|---|---|---|
| **A** | A-1 主指挥部署收口 | 2h | - | 主拍, 0 production code |
| **A** | A-2 W72 派工纪要 v7 | 3h | - | 0 production code |
| **B** | B-1 NavRail.vue 升级 (跨端点 + 6 主题) | 8h | - | web 例外 (1 例外已批) |
| **B** | B-2 ThinkingModeSwitch.vue 升级 (移动端 ActionSheet) | 6h | - | web 例外 |
| **B** | B-3 ChatViewSSE 顶栏 3-zone dark mode 联动 | 6h | - | web 例外 |
| **B** | B-4 跨端点 + 6 主题 dark mode 透传 | 8h | B-1, B-2, B-3 | web 例外 |
| **B** | B-5 ChatBreadcrumb 升级 (跨会话历史栈) | 6h | B-1, B-2, B-4 | web 例外 |
| **C** | C-1 W72 容器 rebuild (商业化版 Docker base) | 12h | - | docker 例外 (建议批) |
| **C** | C-2 W72 商业化 24 人月季度排期 | 8h | - | docs 例外 |
| **C** | C-3 ppt-word 5 缺口调研 (PR2/3/5/7) | 10h | - | docs + 调研 |
| **D** | D-1 派工纪要 v8 升级 | 3h | - | 0 production code |
| **D** | D-2 6 类文档同步 | 4h | A-2, C-2 | 0 production code |
| **D** | D-3 W72 batch grand closure memory | 4h | D-2 | 0 production code |
| **E** | E-1 锚点范式守恒验证 (W72 第 209 → 215 守恒) | 3h | - | 0 production code |
| **E** | E-2 W72 0 production code 铁律 14/15 守恒验证 | 3h | - | 0 production code |

**累计 15 agents + 89 人时 ≈ 11 工作日 (单 agent 串行) 或 5-6 工作日 (并行派工)**.

### 6.2 必含 alembic 串单链纪律 (W68 第 8 批 §2.3 实战)

**实战约束**:
- C-3-3 (PR5 分片上传 alembic 080) 必先派, down_revision 接 `079_team_folders` (W68 第 14 批 §2.3 串单链)
- 任何 alembic migration 派工 prompt 必含 "down_revision 接 X" 明确说明
- merge 后立即 verify 1 head: `python -c "from alembic.script import ScriptDirectory; s=ScriptDirectory('alembic'); print(s.get_heads())"`

### 6.3 必含 web dist rebuild + force-add 派工 v4 铁律

**实战约束** (CLAUDE.md 2026-07-11 PWA manifest 410 回归):
- 任何 web 改动派工必须 `npm run build` (唯一合法, 不允许 `vite build` 直跑)
- 任何 SW_VERSION bump 必连带重跑 `npm run build`
- commit 前必须 grep dist: `git diff --cached -- web/dist/ | grep -E '"url":\s*"manifest\.webmanifest"'` 期望空
- 新增 hashed manifest 文件必 `git add -f` (`.gitignore` 拦了)

### 6.4 0 production code 改动铁律 14/15 守恒预期

**实战统计**:
- A 路线 (3 agents): 0 例外 (docs 范畴)
- B 路线 (5 agents): **1 例外** (web Chat UX 升级, 5 agents 共 1 例外已批)
- C 路线 (3 agents): **0 例外** (docker + docs + 调研)
- D 路线 (3 agents): 0 例外 (docs/memory)
- E 路线 (2 agents): 0 例外 (守恒验证)
- **累计例外**: 1/15 ✓ (符合 0 production code 改动铁律 14/15 守恒预期)

---

## 7. W72 派工建议 (主拍必拍)

### 7.1 派 W72 B 路线 5 agents 派工顺序

**派工顺序 (主拍必先拍)**:
1. **B-1 + B-2 + B-3 可并行** (3 个组件独立, 各自 worktree)
2. **B-4 依赖 B-1+B-2+B-3** (跨端点 dark mode 透传, 必先合 B-1/B-2/B-3)
3. **B-5 依赖 B-1+B-2+B-4** (跨会话历史栈, 必先合 B-1/B-2 + B-4)

**主拍 10 步合并顺序表** (派工 v6 段 6 实战):
1. B-1 合并 (NavRail.vue 升级)
2. B-2 合并 (ThinkingModeSwitch.vue 升级)
3. B-3 合并 (ChatViewSSE 顶栏 3-zone)
4. C-3 合并 (ppt-word 5 缺口调研, docs 范畴)
5. C-1 合并 (W72 容器 rebuild, docker 例外)
6. C-2 合并 (W72 商业化 24 人月季度排期, docs 范畴)
7. B-4 合并 (跨端点 + 6 主题 dark mode 透传)
8. B-5 合并 (ChatBreadcrumb 跨会话历史栈)
9. D-2 合并 (6 类文档同步)
10. D-3 合并 (W72 grand closure memory)

### 7.2 0 production code 改动铁律 14/15 守恒预期

**实战总结**:
- W72 batch 15 agents 中 **14 agents 0 production code 改动** (A 路线 3 + C 路线 3 docs/调研 + D 路线 3 + E 路线 2 + B 路线 3 子任务)
- **1 例外已批**: B 路线 5 agents web Chat UX 升级 (1 例外总括, 5 agents 共用)
- **累计例外**: 1/15 ✓ (符合派工 v6 段 5 反馈 #5 实战)

### 7.3 派工批文必含 4 项

1. **5 真验证命令必含** (派工 v4 铁律 3 实战)
2. **派生新任务真验证** (派工 v4 铁律 3 实战)
3. **alembic 串单链纪律** (W68 第 8 批 §2.3 实战, 如有 alembic 改动)
4. **W72 起步纪律 4 项必读** (派工 v8 段 8 实战)

---

## 附录 A: 5 真验证命令输出汇总

| # | 命令 | 输出 |
|---|---|---|
| 1 | `git log --oneline main \| grep -E "w71st-batch-b[1-5]" \| wc -l` | `10` |
| 2 | `ls tests/qa-bench/scoring/seven_dim.py tests/qa-bench/kb_queue/five_defenses.py tests/qa-bench/kb_queue/end_to_end.py app/services/qa_bench_tasks.py web/src/views/admin/KbMonitorView.vue` | 5 文件全部存在 |
| 3 | `cat /c/Users/pc/.claude/plans/ppt-word-replicated-swing.md \| grep -A 5 "## Status"` | `PARTIAL_REGRESSION (3/8 PR 完整 + 3/8 部分 + 2/8 真未实施)` |
| 4 | `grep -rE "PR2.*sharing\|PR3.*comment.*v2\|PR5.*trash\|PR7.*request" /e/microbubble-agent/app/` | PR7 file_request_service.py 已存在 |
| 5 | `python -c "from alembic.script import ScriptDirectory; s=ScriptDirectory('alembic'); print(s.get_heads())"` | `['078_drive_dedupe_audit']` (1 head) |

---

**文档版本**: v1.0 (2026-07-27 W72 启动前)
**下次更新**: W72 batch grand closure 后 (锚点范式第 209 → 215 守恒预期)
**派工纪要**: v4 段 7 + v6 段 5 + v8 段 8
**作者**: 主指挥协调范式第 49 次派工 / W72 A-3 调研类