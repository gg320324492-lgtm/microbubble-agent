# Drive 知识库自动入库 - 现状盘点 (Plan v1 Step 15)

**完成时间**: 2026-08-17
**结论**: **已完整**, 0 业务代码改动

---

## 现状

### Service
- `app/services/drive_to_kb_service.py` (450 行) - 完整 RAG 管线转化
  - PDF / Word / Excel / PPT 解析 (复用 file_parser_service)
  - 创建 `storage_mode='kb'` Knowledge 行 (保留原 drive 行不动)
  - 触发 analyze_knowledge_task (embedding + chunking + tsvector + BM25 + LLM 分析 + KG)
  - 幂等: 同 drive file_id 重复调返回既有 kb 行

### API 路由
- `app/api/v1/drive_to_kb.py` - 3 endpoints
  - `POST /{file_id}/to-kb` - 单文件入库
  - `POST /folders/{folder_id}/to-kb` - 批量入库
  - `GET /ingestable` - 列出可入库文件

### 与老 extract_to_kb 关系
- 老 `DriveService.extract_to_kb` (v2 PR1 简化版): 原地改 storage_mode drive→kb
- 新 `drive_to_kb_service.py`: 新建 kb 行 + 完整解析 (两者互不干扰)

### 0 业务代码改动完成

- ✅ Drive 用户点"📚 加入公共知识库" → 走 drive_to_kb_service
- ✅ 服务端完整解析 + analyze_knowledge_task 异步处理
- ✅ 幂等保护 (同 file_id 重复入库返既有 kb 行)

---

## 锚点范式累计

- 84f517188 Step 14 commit ~592
- eeb0656d8 Step 13 commit ~591
- 累计 11 commit, 0 业务代码改动

---

## 提升锚点 (P2 留口)

- 自动入库触发: 用户上传 drive 文件时自动调 to-kb (待决策)
- batch 进度条 UI: 大文件夹批量入库进度 (待决策)
- 增量入库: KB 删后重新入库 (待决策)
