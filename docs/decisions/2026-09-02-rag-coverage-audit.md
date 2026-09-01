# RAG 内容覆盖审计与补缺口决策 (2026-09-02)

> 背景: 用户目标"全项目内容都可以被 RAG 系统读取到"。全面审计后按缺口分级修复
> (plan: vast-coalescing-micali)。本文档记录覆盖矩阵、修复内容与架构决策。

## 覆盖矩阵 (修复前 → 修复后)

| 内容源 | 量级 | 修复前 | 修复后 | 工作包 |
|--------|------|--------|--------|--------|
| knowledge (kb) | 99 篇 | ✅ 六路齐全 | ✅ (含 WP3 修复 inline 内容盲区) | WP3 |
| 会议转录 | 22 场 ≈ 250 万字 (平均 11.5 万/场) | ❌ 完全缺席 | ✅ meeting_chunks 第 6 路 (向量) + RRF | WP1 |
| 会议摘要 | 22 场 (12 场无向量) | ⚠️ 半失效 | ✅ compute_and_store_embedding 接线 + 补算 | WP1 |
| drive 文件原文 | 277 个 | ❌ 仅文件名 | ✅ knowledge_chunks drive 语料域 + 第 7 路 (可见性过滤) | WP2 |
| 多模态提取 (OCR/表格) | 已提取的文档 | ❌ inline 后不进索引 | ✅ inline 后 resync 全套索引 | WP3 |
| memories | 29 条 | ✅ 非缺口 | ✅ (每请求注入 system prompt) | — |
| tasks/projects/members | 95/4/37 | ⚠️ 不在 RAG | ⚠️ 维持 (见决策 2) | — |
| chat 历史 | 713 条 | ❌ | ❌ 维持 (见决策 3, DEFERRED) | — |

## 决策记录

### 1. 会议转录全组可检索
现状: 会议列表查询无用户过滤 (meeting_service.get_meetings), 全组共享。
RAG 检索对齐现状 — meeting_chunks 不做 per-user 过滤。若未来收紧到
"仅参与者可见", participants 表已具备过滤条件 (MeetingParticipant)。

### 2. 结构化数据 (tasks/projects/members/formulas) 走工具路, 不进向量索引
原因: ① 强结构化查询 (按状态/负责人/日期过滤) 是主要访问模式, 向量检索
反而低效; ② LLM 已有 30+ 专用工具按需查询; ③ 数据更新频繁, 向量索引
实时性成本高。含义: RAG 检索阶段"看不见"这些数据, 依赖综合阶段工具
选择命中 — 属架构选择而非缺陷。

### 3. chat 历史语义检索 — DEFERRED
原因: ① 隐私边界 (chat_messages 全部经 user_id 越权防护, 跨用户检索
需谨慎设计); ② 713 条量小, ILIKE 搜索 (GET /chat/sessions/search) 已
覆盖当前需求; ③ "上次聊到什么"场景价值待验证。触发重评条件:
用户明确提出历史对话检索需求, 或消息量 >1 万。

### 4. drive 内容与 kb 语料域隔离
drive 文件解析文本写入 knowledge_chunks (与 kb 共表), 但**所有 kb 检索路
(vector/chunk/BM25/实体/图片) 保持 storage_mode='kb' 过滤不变** — drive
内容只出现在新 drive 路 (storage_mode='drive' + visibility != 'private'
OR created_by = user_id)。含义: 检索结果可按 retrieval_method='drive'
区分来源; private 文件内容仅 owner 可检索。

### 5. 会议 id 命名空间
meeting_chunks 命中结果的 id = MEETING_ID_NS (10_000_000) + meeting_id,
防止与 knowledge 自增 id 在 RRF/前端去重时互撞; 原始 meeting_id 单独
携带, 前端按 retrieval_method='meeting' 跳转 /meetings/:id。

## 实施清单

- **WP1**: 迁移 130 (meeting_chunks) + meeting_chunk_service (EMO 清洗/
  【speaker】前缀/800 字段边界对齐窗口/幂等/embedding 回填) +
  post_meeting_tasks 接线 (摘要 embedding + 转录索引 dispatch) +
  hybrid meetings 路 + HybridWeights.meetings=0.35 + backfill_meeting_index.py
- **WP2**: drive_index_service (MinIO→parse→chunk→embed, 幂等) +
  create_file 上传钩子 + user_id 线程化 (knowledge_tools → retrieve_with_weights
  → retrieve_per_method, 修 impl 内本地 None 覆盖入参隐患) + drive 路 +
  HybridWeights.drive=0.3 + backfill_drive_content.py
- **WP3**: resync_content_indexes helper (四项索引重刷单一来源) + Step 7b
  inline 后接线 + update_knowledge 收敛 (源码锁) + backfill_resync_kb_indexes.py
- **WP5**: 全量测试 + 容器部署 + 迁移 130 + 三脚本生产回填 + e2e

## 量级预估

- 会议回填: 22 场 ≈ 2.5M 字 → ~4-6K chunks (800 字窗), GPU embedding 分钟级
- drive 回填: 277 文件, 视内容分钟级
- resync 回填: 有提取产物的 kb 文档 (knowledge_images/extractions 有行的子集)
