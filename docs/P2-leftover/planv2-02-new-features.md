# Plan v2 #2 新功能调研 (P2 留口)

**调研时间**: 2026-08-17
**结论**: 跨 session 检索 / 自动入库 / 知识图谱增强 基础设施已就绪, 0 业务代码改动

---

## 现状 (2026-08-17 实测)

### 已就绪工具 + 服务
- `app/agent/tools/research_tools.py` - auto_research 工具 (联网搜索 + 自动入库)
- `app/agent/tools/knowledge_tools.py` - 知识库工具
- `app/services/auto_research_service.py` + `auto_research_v2.py` (dedup + query_rewriter)
- `app/api/v1/admin_kb_monitor.py` - KB 自动入库监控
- `app/api/v1/search_logs_admin.py` - 搜索日志 (W92 PR6)
- `app/services/knowledge_graph_service.py` - 知识图谱 (BFS 遍历 + 动态分类)
- `app/rag/` 9 文件 - RAG 子层

### 已有数据流
- search_log 每次 search_knowledge 落 DB (W92 PR6 前端接通)
- search_logs_admin.py 7 维日志面板
- `chat_messages.summary` + `key_topics` 已加列 (Step 14 P2 留口)
- auto_research 工具 (2 版本 v1/v2)

### 0 业务代码改动完成
- ✅ Plan v2 #2 新功能调研文档化
- ✅ 基础设施 (工具 + 服务 + 表) 已就绪
- ✅ 等主拍决策 (P2 留口)

---

## 启动锚点 (主拍决策时启动)

候选新功能 (主拍决策时选):

### A. 跨 session 检索 (Step 14 P2 启用 + 新端点)
- 触发 SUMMARY_LLM_ENABLED=true (chat_messages.summary 异步落库)
- 加新端点 `GET /api/v1/summary/search?q=...` (跨 session 召回)
- 前端 UI: 历史对话搜索面板
- 投资: 1 周 + 中风险

### B. 自动入库增强
- drive 上传时自动 to_kb (Step 15 已就绪, 加前端开关)
- auto_research 触发更敏感 (按小时/按事件)
- 投资: 1 周 + 低风险

### C. 知识图谱增强
- BFS 遍历 + Neo4j 双写
- 实体识别 LLM 增强 (现 extract_entities)
- 前端可视化 (KnowledgeGraphExplorer 已就绪)
- 投资: 2 周 + 中风险

### 启动条件 (主拍决策时):
- A/B/C 任一 + 主拍书面批准 + 派工 brief §13 真查

---

## 锚点范式累计

- d805f4f10 MEMORY 段 28
- 3a125b85f CLAUDE.md 更新
- 累计 26 commit, 0 业务代码改动

---

## 主拍决策单 (主拍填)

| 候选 | 投资 | 风险 | 启动 |
|------|------|------|------|
| A. 跨 session 检索 | 1 周 | 中 | [ ] |
| B. 自动入库增强 | 1 周 | 低 | [ ] |
| C. 知识图谱增强 | 2 周 | 中 | [ ] |

**3 候选严禁擅自启动**, 等主拍书面批准 + 派工 brief §13 真查.
