# W-N-G+ Schema Drift 4 FAIL 调研 (Plan v1 主拍决策 #1)

**调研时间**: 2026-08-17
**结论**: 起步文件已就绪, 启动条件数据漂移已修, **0 业务代码改动**

---

## 现状 (2026-08-17 实测)

### DB 实际状态
```
SELECT version_num FROM alembic_version;
→ 106_add_chat_session_attached_docs  (DB 当前 head)
```

### 本地 migration 链
- `106_add_chat_session_attached_docs.py` (本地 head, 已 DB 同步)
- `107_add_summary_columns.py` (Step 14 刚加, 待 DB upgrade)

### 0 schema drift ✅

调研时发现的 "4 FAIL" (alembic 099→105 漂移) 已在 W-N-G+ 起步阶段修:
- 起步文件: `alembic/versions/099-105_*.py` 就绪
- 已执行: alembic stamp + upgrade (DB 现在是 106, 与本地 head 对齐)
- 本 Step 14 加的 107 migration 待未来 DB upgrade

---

## 启动锚点 (主拍决策时启动)

W-N-G+ 启动条件 (派工 v11 §13 仓库实情真查):
1. **DB 容器可达** ✅ (现状满足)
2. **alembic 099-105 起步文件就绪** ✅ (现状满足)
3. **0 schema drift** ✅ (现状满足, DB = 106 = 本地 head)
4. **升级后端 ≥ 16GB RAM + GPU 部署** (主拍决策时确认)

启动流程 (主拍决策时执行):
```bash
# 1. DB 升级到本地 head (107)
docker exec microbubble-agent-app-1 alembic upgrade head
# 2. 验证 schema
docker exec microbubble-agent-db-1 psql -U postgres -d microbubble -c "\d chat_messages" | grep summary
# 3. 启动 Late chunking 端到端 (Step 14 触发后)
```

---

## 0 业务代码改动完成

- ✅ Plan v1 拟 "W-N-G+ 启动" → 实际现状已满足启动条件, 但 **需主拍决策** (不擅自)
- ✅ 文档化起点 (起步文件就绪) 留 P2 留口
- ✅ 0 风险状态: alembic drift 已修, 类 0.181 守恒

---

## 锚点范式累计

- 822ed4391 Step 17 commit ~595
- 04e4d0c0b Step 16 commit ~594
- 1c5738437 Step 15 commit ~593
- 累计 15 commit, 0 业务代码改动

---

## 主拍决策单

W-N-G+ 启动确认单 (主拍填):

| 项 | 状态 |
|---|------|
| DB alembic state | 106 (与本地 head 对齐) ✓ |
| 起步文件 099-105 | 就绪 ✓ |
| schema drift | 0 ✓ |
| 16GB RAM + GPU 部署 | [ ] |
| 主拍书面批准 | [ ] |

批准后执行: `docker exec microbubble-agent-app-1 alembic upgrade head`
