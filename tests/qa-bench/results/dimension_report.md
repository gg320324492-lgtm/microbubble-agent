# 小气助手能力测评 - 维度报告 (W3 T3.2)

**生成时间**: 2026-06-30
**题库**: `tests/qa-bench/questions_w2_final.jsonl` (535 题)
**来源**: W1 (700 题) + W2 手工 229 题 + W2 DB 107 题

## 1. 维度分布

### 1.1 业务域
- **A**: 38 题 (7.1%)
- **B**: 35 题 (6.5%)
- **C**: 35 题 (6.5%)
- **D**: 26 题 (4.9%)
- **E**: 31 题 (5.8%)
- **F**: 25 题 (4.7%)
- **G**: 24 题 (4.5%)
- **H**: 21 题 (3.9%)
- **K**: 103 题 (19.3%)
- **M**: 28 题 (5.2%)
- **P**: 102 题 (19.1%)
- **U**: 23 题 (4.3%)
- **X**: 24 题 (4.5%)
- **Z**: 20 题 (3.7%)

### 1.2 难度分布
- **L1**: 92 题 (17.2%)
- **L2**: 189 题 (35.3%)
- **L3**: 210 题 (39.3%)
- **L4**: 44 题 (8.2%)

### 1.3 来源分布
- **db_extract**: 107 题 (20.0%)
- **expert**: 15 题 (2.8%)
- **manual**: 269 题 (50.3%)
- **template**: 144 题 (26.9%)

### 1.4 Intent 分类分布 (W3 T3.0 bug 修复后)
- **search_info (找资料)**: 165 题
- **data_query (查数据)**: 104 题
- **DATA**: 90 题
- **ACTION**: 40 题
- **EXPLAIN_CONCEPT**: 39 题
- **casual_chat (闲聊)**: 27 题
- **execute_action (执行操作)**: 23 题
- **explain_concept (解释概念)**: 17 题
- **DEEP**: 15 题
- **unknown**: 15 题

## 2. 业务域 × 难度 矩阵

| 业务域 | L1 | L2 | L3 | L4 | 合计 |
|---|---|---|---|---|---|
| A | 7 | 25 | 6 | 0 | 38 |
| B | 1 | 12 | 21 | 1 | 35 |
| C | 1 | 14 | 19 | 1 | 35 |
| D | 1 | 11 | 13 | 1 | 26 |
| E | 1 | 11 | 17 | 2 | 31 |
| F | 1 | 8 | 14 | 2 | 25 |
| G | 1 | 6 | 15 | 2 | 24 |
| H | 2 | 9 | 9 | 1 | 21 |
| K | 60 | 40 | 3 | 0 | 103 |
| M | 0 | 11 | 12 | 5 | 28 |
| P | 0 | 30 | 55 | 17 | 102 |
| U | 15 | 5 | 3 | 0 | 23 |
| X | 0 | 0 | 14 | 10 | 24 |
| Z | 2 | 7 | 9 | 2 | 20 |

## 3. 业务域 × Intent 矩阵

| 业务域 | search_info | data_query | execute_action | DATA | ACTION | casual_chat | EXPLAIN_CONCEPT | explain_concept | DEEP | unknown |
|---|---|---|---|---|---|---|---|---|---|---|
| A | 19 | 19 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| B | 13 | 17 | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| C | 15 | 16 | 4 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| D | 18 | 8 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| E | 18 | 12 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| F | 18 | 7 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| G | 14 | 6 | 4 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| H | 13 | 2 | 6 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| K | 2 | 0 | 0 | 60 | 40 | 1 | 0 | 0 | 0 | 0 |
| M | 19 | 9 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| P | 0 | 0 | 0 | 30 | 0 | 0 | 39 | 3 | 15 | 15 |
| U | 0 | 1 | 0 | 0 | 0 | 22 | 0 | 0 | 0 | 0 |
| X | 6 | 5 | 1 | 0 | 0 | 0 | 0 | 12 | 0 | 0 |
| Z | 10 | 2 | 2 | 0 | 0 | 4 | 0 | 2 | 0 | 0 |

## 4. 工具调用分布

| 工具 | 题数 |
|---|---|
| query_members | 96 |
| search_knowledge | 84 |
| query_meetings | 52 |
| list_hypotheses | 48 |
| query_tasks | 44 |
| list_formulas | 40 |
| query_member_tasks | 30 |
| query_projects | 26 |
| query_project_detail | 17 |
| search_memory | 15 |
| query_short_memory | 12 |
| query_team_stats | 11 |
| query_meeting_detail | 11 |
| query_long_memory | 10 |
| calculate_formula | 9 |
| query_papers | 7 |
| resolve_reference | 7 |
| design_experiment | 6 |
| query_knowledge_graph | 6 |
| create_task | 5 |
| unit_convert | 5 |
| forget_long_memory | 5 |
| create_meeting | 4 |
| generate_project_plan | 4 |
| summarize_session | 3 |
| clear_short_memory | 2 |
| self_rag_assess | 2 |
| summarize_text | 2 |
| query_recent_activities | 2 |
| query_my_tasks | 1 |
| query_my_meetings | 1 |
| generate_meeting_minutes | 1 |
| update_hypothesis | 1 |
| query_reminders | 1 |
| reset_session | 1 |
| mark_confidential_cleanup | 1 |
| ui_mobile_check | 1 |
| continue_session | 1 |
| render_table | 1 |
| query_ui_state | 1 |
| query_session_state | 1 |
| query_important_tasks | 1 |
| query_recent_meetings | 1 |
| comprehensive_advice | 1 |
| detect_self_correction | 1 |
| query_chat_history | 1 |
| query_resilience_logs | 1 |
| query_weather | 1 |
| web_search | 1 |
| suggest_research_direction | 1 |
| detect_research_gaps | 1 |
| create_hypothesis | 1 |
| find_cross_disciplinary | 1 |
| analyze_top_journals | 1 |
| query_yesterday_session | 1 |
| cleanup_tasks | 1 |
| evaluate_text | 1 |
| parse_pdf | 1 |
| rewrite_text | 1 |
| list_all_data | 1 |

## 5. 子题 (subcategory) 覆盖

- **A1**: 10 题
- **A2**: 10 题
- **A3**: 9 题
- **A4**: 9 题
- **B1**: 13 题
- **B2**: 13 题
- **B3**: 5 题
- **B4**: 4 题
- **C1**: 10 题
- **C2**: 14 题
- **C3**: 4 题
- **C4**: 4 题
- **C5**: 3 题
- **D1**: 11 题
- **D2**: 11 题
- **D3**: 4 题
- **E1**: 17 题
- **E2**: 5 题
- **E3**: 5 题
- **E4**: 4 题
- **F1**: 13 题
- **F2**: 6 题
- **F3**: 6 题
- **G1**: 12 题
- **G2**: 6 题
- **G3**: 6 题
- **H1**: 5 题
- **H2**: 10 题
- **H3**: 6 题
- **K1**: 21 题
- **K2**: 21 题
- **K3**: 20 题
- **K4**: 20 题
- **K5**: 21 题
- **M1**: 16 题
- **M2**: 6 题
- **M3**: 6 题
- **P1**: 21 题
- **P2**: 21 题
- **P3**: 15 题
- **P4**: 15 题
- **P5**: 15 题
- **P6**: 15 题
- **U1**: 11 题
- **U2**: 6 题
- **U3**: 6 题
- **X1**: 13 题
- **X2**: 6 题
- **X3**: 5 题
- **Z1**: 4 题
- **Z2**: 4 题
- **Z3**: 4 题
- **Z4**: 8 题

## 6. 字段覆盖率（v3.0 schema 校验）

- **id**: 535/535 (100.0%)
- **version**: 535/535 (100.0%)
- **category**: 535/535 (100.0%)
- **subcategory**: 535/535 (100.0%)
- **dimension**: 535/535 (100.0%)
- **difficulty**: 535/535 (100.0%)
- **source**: 535/535 (100.0%)
- **author**: 535/535 (100.0%)
- **created_at**: 535/535 (100.0%)
- **updated_at**: 535/535 (100.0%)
- **question**: 535/535 (100.0%)
- **expect**: 535/535 (100.0%)
- **ground_truth**: 535/535 (100.0%)
- **ground_truth_refs**: 535/535 (100.0%)
- **detector**: 535/535 (100.0%)
- **tags**: 535/535 (100.0%)
- **deprecated**: 535/535 (100.0%)
- **supersedes**: 535/535 (100.0%)

## 8. W3 阶段改进建议 (来自 T3.0 bug 修复 + smoke 实测)

### 8.1 T3.0 已修复
- ✅ MicroBubbleAgent.chat_stream() 添加 `model` + `use_self_rag` 参数 (Self-RAG #009 引入的回归)
- ✅ intent 标签已从 DATA/CASUAL/DEEP/ACTION 改为 data_query/casual_chat/explain_concept/execute_action

### 8.2 待改进 (T3.3-T3.5)
- T3.3: prompts.py 加 4 域综合 checklist (跨域 X 类准确率提升)
- T3.4: Self-RAG gate 阈值分档 (高/中/低 → 不同决策)
- T3.5: 性能优化 (Phase 0.5 + Phase 1 首轮检索并行)

### 8.3 已知问题 (来自 smoke)
- 性能: 每题 25s, 全量 535 题 ~3.7 小时 (建议并发 4 跑)
- 限流: SSE/API 端点限流 30/min (write) + 200/min (read), 高并发需谨慎
- 真答案: 部分 L1/L2 题的回答不引用完整成员名 (forbidden_names_appeared issue)