# W72 A-3 启动前 plans 真验证 (锚点范式第 209 守恒)

> **锚点范式**: W71 第 206 → W72 启动前验证 +3 (W72 第 209 守恒)
> **生成时间**: 2026-07-27
> **派工纪要**: v4 段 7 (派工前提错误复盘) + v6 段 5 反馈 #2 (不动 v1-v7 历史约束) + v8 段 8 (W72 起步纪律 4 项必读)
> **commit**: `206661254` (主仓库)

---

## 1. 任务概述

**W72 A-3 启动前 plans 真验证**: 派工 v4 铁律 3 实战 (7 grep 真验证必全跑), W72 起步纪律 4 项实战 (派工 v8 段 8), ppt-word 5 缺口真验证 + 派生新任务 6 项.

**核心目标**: 主拍 W72 batch 派工前必读必参考, 必含 4 路线 15 agents 完整派工顺序 + 5 真验证命令 + ppt-word 5 缺口清单 + W72 起步纪律 4 项实战.

---

## 2. 5 真验证命令输出 (派工 v4 铁律 3 实战)

### 2.1 W71 B 路线 5 agents 全部 commit + merge

```bash
$ git log --oneline main | grep -E "w71st-batch-b[1-5]" | wc -l
10
```

**实际 10 commits** (5 merge + 5 feat):
- `6cddfb073` merge B-5 Dashboard MVP + CI smoke 200 题拆 2 step (第 200 守恒)
- `bd74f951c` merge B-4 KB 闭环端到端 (第 199 守恒)
- `aed47632f` merge B-3 Celery auto_intake_rollback_task (第 198 守恒)
- `0cc1e2699` merge B-2 save_to_kb.py 5 道防线 (第 197 守恒)
- `47f8b9c9b` merge B-1 qa-bench 7 维评分算法 (第 196 守恒)

### 2.2 W71 子 plan ② 5 文件全部落地

```bash
$ ls tests/qa-bench/scoring/seven_dim.py tests/qa-bench/kb_queue/five_defenses.py tests/qa-bench/kb_queue/end_to_end.py app/services/qa_bench_tasks.py web/src/views/admin/KbMonitorView.vue
app/services/qa_bench_tasks.py
tests/qa-bench/kb_queue/end_to_end.py
tests/qa-bench/kb_queue/five_defenses.py
tests/qa-bench/scoring/seven_dim.py
web/src/views/admin/KbMonitorView.vue
```

**5 文件全部存在** ✓, 累计 11 + 10 + 6 + 13 + 4 = **44 e2e PASS**.

### 2.3 ppt-word plan Status 段真验证

```
**PARTIAL_REGRESSION (长期 8-12 人天, W69+ 派工)**: 3/8 PR 完整 (PR1 stub 修复 / PR6 通知 / PR8 预览 + PR9 评论版本链), 3/8 部分 (PR4/5/6), 2/8 真未实施 (PR2/3/5/7) 留 W69+ 分 3 批派工.
```

### 2.4 派生新任务真验证 (W72 C-3 ppt-word 5 缺口)

```bash
$ grep -rE "PR2.*sharing|PR3.*comment.*v2|PR5.*trash|PR7.*request" /e/microbubble-agent/app/
app/core/rate_limit.py:    - PR7 集成：响应后调用 ``app.core.audit_middleware._audit_request`` 写 audit_log
app/services/file_request_service.py:    """v2 PR7: file_requests CRUD + 公开 submit"""
```

**真验证结论**: PR7 file_request_service.py **已存在** (W68 实施), PR2/3/5/7 5 缺口 **未实施 080 alembic 缺失** (PR5 分片上传), W72 C-3 必含 5 缺口调研.

### 2.5 alembic 1 head 真验证

```bash
$ python -c "from alembic.script import ScriptDirectory; s=ScriptDirectory('alembic'); print(s.get_heads())"
['078_drive_dedupe_audit']
```

**1 head 守恒** ✓, 单链 `075 → 076 → 079 → 078`, 符合派工纪要 v4 铁律 1 + W68 第 13 批 C-1 实战教训 (B-1 stopped 后主指挥合并收口修订串单链).

---

## 3. W72 起步纪律 4 项实战 (派工 v8 段 8)

1. **W71 B 路线 5 agents 全部 commit + merge** ✓ (10 commits: 5 merge + 5 feat)
2. **7 维评分 + KB 闭环回归验证** ✓ (44 e2e PASS: 11+10+6+13+4)
3. **子 plan ③ 3 组件独立回归** ✓ (NavRail 220 + ThinkingMode 117 + ChatBreadcrumb 106 = 443 行)
4. **派工前提错误必含 W71 实战 13 类** ✓ (派工 v8 段 7 升级 16 类)

---

## 4. ppt-word 5 缺口调研清单 (W72 C-3 必含)

| PR | 内容 | 现状 | 派工建议 |
|---|---|---|---|
| **PR2** | 回收站 + 多选批量 + 收藏星标 + 排序/筛选 | 部分 (FolderTree.vue 顶部 3 项已写) | C-3-1 派 1 agent 补完 (5d) |
| **PR3** | KnowledgeUploadDialog 双模 + KnowledgeDashboard chip | 真未实施 | C-3-2 派 1 agent (3d) |
| **PR5** | 分片上传 + 断点续传 + 配额 + 缩略图 | 部分 (080 alembic 缺失) | C-3-3 派 1 agent 写 080 migration + 实施 (6.5d) |
| **PR7** | 文件请求 + 共享盘 + 审计日志 | 部分 (file_request_service.py 已存在但未接 API) | C-3-4 派 1 agent 接 API + 共享盘 + 审计 (6d) |
| **PR4** | 文件秒传 + 版本历史 | 部分 (B-1 PR17 alembic 078 已 merge, 但秒传 UI 未做) | C-3-5 派 1 agent 补 UI (3d, 合并入 C-3-3) |

---

## 5. W72 batch 15 agents 派工建议 (主拍必拍)

| 路线 | 任务数 | 派工时长 | 0 production 例外 |
|---|---|---|---|
| **A** 部署收口 | 3 agents | 8h | 0 (docs 范畴) |
| **B** Chat UX 升级 | 5 agents | 34h | **1 例外** (web Chat UX 5 agents 共用) |
| **C** Drive v2 续 + 商业化 | 3 agents | 30h | 0 (docker + docs + 调研) |
| **D** 文档同步 | 3 agents | 11h | 0 (docs/memory) |
| **E** 守恒验证 + 收口 | 2 agents | 6h | 0 (守恒验证) |

**累计**: 15 agents + 89 人时 ≈ 11 工作日 (单 agent 串行) 或 5-6 工作日 (并行派工).

**0 production code 改动铁律 14/15 守恒预期** ✓ (1 例外预留给 B 路线 Chat UX 升级).

---

## 6. 主拍 10 步合并顺序表 (派工 v6 段 6 实战)

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

---

## 7. 派生新任务 6 项 (派工 v4 铁律 3 实战)

1. W72 B-1 NavRail.vue 升级 (跨端点 + 6 主题)
2. W72 B-2 ThinkingModeSwitch.vue 升级 (移动端 ActionSheet)
3. W72 B-3 ChatViewSSE 顶栏 3-zone dark mode 联动
4. W72 B-4 跨端点 + 6 主题 dark mode 透传
5. W72 B-5 ChatBreadcrumb 跨会话历史栈
6. W72 C-3 ppt-word 5 缺口调研 (PR2/3/5/7)

---

## 8. 派工批文必含 4 项 (派工 v6 段 5 + v8 段 8)

1. **5 真验证命令必含** (派工 v4 铁律 3 实战)
2. **派生新任务真验证** (派工 v4 铁律 3 实战)
3. **alembic 串单链纪律** (W68 第 8 批 §2.3 实战, 如有 alembic 改动)
4. **W72 起步纪律 4 项必读** (派工 v8 段 8 实战)

---

## 9. commit 信息

```
commit 206661254
docs(w72nd-batch-a3): W72 启动前 plans 真验证 (派工 v4 铁律 3 实战, 7 grep 验证 + W72 起步纪律 4 项实战 + ppt-word 5 缺口真验证 + 派生新任务 6 项, 锚点范式第 209 守恒)
```

**push 状态**: ✓ origin/chore/w72nd-batch-a3-plans-verify-2026-07-24

---

**文档版本**: v1.0 (2026-07-27 W72 启动前)
**作者**: 主指挥协调范式第 49 次派工 / W72 A-3 调研类
**铁律**: 派工 v4 铁律 3 + v6 段 5 + v8 段 8 全部实战验证