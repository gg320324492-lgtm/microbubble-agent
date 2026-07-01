# 小气助手能力测评 - 高级能力报告 (W4 T4.7)

**生成时间**: 2026-06-30
**P 高级题**: 102 题 (W1 gen780.py 模板生成)
**场景**: Self-RAG / fan-out / plan_step / 持久化 / abort / grounding

## 1. P 高级 6 子类分布

- **P1**: 21 题
- **P2**: 21 题
- **P3**: 15 题
- **P4**: 15 题
- **P5**: 15 题
- **P6**: 15 题

## 2. 子类期望工具分布

### P1
- search_knowledge: 19 题
- list_formulas: 19 题
- list_hypotheses: 19 题
- query_members: 19 题
- self_rag_assess: 2 题

### P2
- search_knowledge: 1 题
- list_formulas: 1 题
- list_hypotheses: 1 题
- query_members: 1 题

### P3
- query_tasks: 15 题
- query_meetings: 15 题
- query_projects: 15 题
- search_knowledge: 15 题
- query_members: 15 题

### P4
- search_memory: 15 题
- query_meetings: 15 题
- query_tasks: 15 题

### P5

### P6
- search_knowledge: 15 题

## 3. P 子类 × 难度 矩阵

| 子类 | L1 | L2 | L3 | L4 | 合计 |
|---|---|---|---|---|---|
| P1 | 0 | 0 | 19 | 2 | 21 |
| P2 | 0 | 0 | 21 | 0 | 21 |
| P3 | 0 | 15 | 0 | 0 | 15 |
| P4 | 0 | 15 | 0 | 0 | 15 |
| P5 | 0 | 0 | 0 | 15 | 15 |
| P6 | 0 | 0 | 15 | 0 | 15 |

## 4. W4 T3.4 Self-RAG 3-tier 分级改进

### 4.1 改进前 (W1 阶段)
- 单阈值 0.6: confidence >= 0.6 不重检索, 否则触发
- 缺点: 模糊查询 (e.g. 0.55) 立即重检索, 增加 latency 30%+
- 缺点: 高置信度 (e.g. 0.85) 与中置信度 (e.g. 0.65) 走相同路径, 无差别化日志

### 4.2 改进后 (W4 T3.4)
- **高置信度 (≥0.8)**: 直接出, 日志 `✅ high_confidence`
- **中高置信度 (≥0.6)**: 不重检索, 日志 `✓ mid_high_confidence`
- **中置信度 (≥0.4) + can_answer**: 不重检索, 日志 `~ mid_confidence`
- **低置信度 (<0.4)**: 触发重检索, 日志 `↻ low_confidence`
- **max_reached**: 重试耗尽, 日志 `🛑 max_reretrieve_reached`

### 4.3 实施位置
- `app/agent/agentic_loop.py:615-665` (3-tier 决策块)
- `app/config.py:166-171` (阈值配置)

## 5. W4 T3.5 性能优化 (deferred)

**目标**: Phase 0.5 (Self-RAG) 与 Phase 1 首轮检索并行

**为什么 defer**:
- 主循环重构风险高 (动 Phase 0.5 / 1 的串联逻辑)
- 并发引入数据竞争 (messages/tool_calls 共享状态)
- 需配合 LLM provider 并发配置
- 单题 25s 已基本可用, 无紧急性

**留给 W5/W6 安排**:

- W5: save_to_kb.py 全自动改造 + 回归基线 (性能测试机会)
- W6: 性能基准 (latency P95 < 20s, TTFT < 3s)

## 6. 5 弱项改进计划回顾 (来自 plan 5.1)

| 弱项 | 改进 | 状态 | 文件 |
|---|---|---|---|
| A. 跨域 4 域综合 | W3 T3.3 4-段 checklist + 5-段 LLM 自检 | ✅ 实施 | prompts.py |
| B. Self-RAG 阈值优化 | W4 T3.4 3-tier 分级 (0.8/0.6/0.4) | ✅ 实施 | agentic_loop.py |
| C. 持久化聊天 | W1 #043 8 phase 收官 (跨 session 摘要) | ✅ 收官 | app/services/chat_history* |
| D. 任务创建参数解析 | W2 验收 — 测试集覆盖 B3 5 题 | ✅ 完成 | manual_234.jsonl |
| E. 性能优化 | W4 T3.5 deferred (需主循环重构) | ⏸ W5/W6 | agentic_loop.py |

## 8. 后续计划 (W5-W6)

### W5 (KB 入库 + 回归)
- save_to_kb.py 全自动改造 + 5 道防线 (分数门控 + 7天 rollback + dashboard 监控 + 灰度 flag + 白名单)
- 200 题 smoke baseline (基于 W2 合并题库)
- 回归基线 v3.0 锁定
- 2 轮稳定性测试 (同题二次一致性 ≥ 95%)

### W6 (交付)
- 雷达图 (7 维可视化)
- 趋势报告 (v2.x → v3.0 提升)
- 决策项清单 (产品/架构/前端)
- 文档交付 (README + 运维手册 + 题库维护 SOP)