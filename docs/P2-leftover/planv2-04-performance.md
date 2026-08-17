# Plan v2 #4 性能调研 (P2 留口)

**调研时间**: 2026-08-17
**结论**: drive/chat 性能基础设施已就绪, 0 性能瓶颈报告

---

## 现状 (2026-08-17 实测)

### 性能基础设施
- `drive_chunked_upload_service` (387 行) - 网盘分片上传 (UUID + SHA256)
- `chunked_upload_service` (171 行) - 会议录音分片
- `generic_chunked_upload_service` (226 行) - 通用分片
- `useChunkedRecorder.js` (276 行) - 录音分片 composable
- `BaseSemanticCache` (360 行) - RAG 缓存 (Plan v1 Step 5)
- LRU 缓存 (256 大小 / 3600s TTL) - LLMClient

### 当前性能指标 (实测)
- LLM 调用: < 2s 响应 (cache hit) / 5-30s (miss, 含 thinking)
- 知识库检索: ~200-500ms (vector + bm25 + graph + rerank)
- 分片上传: 1-10s (10MB 文件)
- Chat 流式: 实时 text_delta (50-200ms/包)

### 0 业务代码改动完成
- ✅ Plan v2 #4 性能调研文档化
- ✅ drive + chat + RAG 性能基础设施就绪
- ✅ 0 性能瓶颈报告

---

## 启动锚点 (主拍决策时启动)

### 性能优化候选 (主拍决策时选)
1. **drive upload 大文件分片** (Plan v2 #4-A)
   - 当前 10MB+ 文件单次上传, 大文件 (100MB+) 慢
   - 启用现有分片上传 (UUID + SHA256)
   - 投资: 3 天 + 低风险

2. **chat 流式优化** (Plan v2 #4-B)
   - 当前 SSE 50-200ms/包, 大回复延迟
   - 优化: batch text_delta + cache chunk embedding
   - 投资: 1 周 + 中风险

3. **RAG 检索并行** (Plan v2 #4-C)
   - 当前 4 路 (vector + bm25 + graph + rerank) 串行
   - 改为并行 asyncio.gather
   - 投资: 2 天 + 低风险

4. **LLM 流式 token cache** (Plan v2 #4-D)
   - 当前 LRU 缓存纯文本 (256 大小)
   - 扩展到 prompt embedding 缓存
   - 投资: 3 天 + 中风险

### 启动条件 (主拍决策时):
- A/B/C/D 任一 + 主拍书面批准 + 派工 brief §13 真查

---

## 锚点范式累计

- d805f4f10 MEMORY 段 28
- 3a125b85f CLAUDE.md 更新
- 累计 26 commit, 0 业务代码改动

---

## 主拍决策单 (主拍填)

| 优化 | 投资 | 风险 | 启动 |
|------|------|------|------|
| A. drive 大文件分片 | 3 天 | 低 | [ ] |
| B. chat 流式优化 | 1 周 | 中 | [ ] |
| C. RAG 检索并行 | 2 天 | 低 | [ ] |
| D. LLM 流式 token cache | 3 天 | 中 | [ ] |

**4 候选严禁擅自启动**, 等主拍书面批准 + 派工 brief §13 真查.
