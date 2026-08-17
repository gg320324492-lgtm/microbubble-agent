# Step 8a BaseChunkedUpload 抽象调研 (P2 留口)

**调研时间**: 2026-08-17
**结论**: 3 个 service 接口完全不同, 抽象需 1 周 + 中风险, **不擅自启动**

---

## 现状 (2026-08-17 实测)

### 3 个 Chunked Upload Service
| Service | 行数 | 核心方法 | 业务场景 |
|---|---:|---|---|
| `chunked_upload_service.py` | 171 | save_chunk / list_chunks / merge_chunks / delete_all | 会议录音分片上传 (合并 WebM chunk) |
| `drive_chunked_upload_service.py` | 387 | init_upload / upload_chunk / get_upload / complete_upload | 网盘文件分片 (UUID + SHA256 + 24h TTL) |
| `generic_chunked_upload_service.py` | 226 | init_upload / complete_upload / abort_upload | 通用上传 (单端点 + temp file + 流式) |

### 0 业务代码改动完成
- ✅ 3 个 service 完全独立 + 互不调用
- ✅ 0 重复代码可抽 (3 个 service 内部实现差异极大)
- ✅ 0 风险状态: 保持现状

---

## 抽象成本分析 (P2 留口)

### 真的重复代码?
- **共同点**: 都用 MinIO / 都用 chunk_index / 都有 24h TTL
- **差异**:
  - 会议: WebM 块合并 → 单文件
  - 网盘: 增量 + SHA256 校验 + state machine
  - 通用: 端点流式 + temp file

### 抽象收益 (估计)
- 公共逻辑抽 base (~150 行): get_minio_client / chunk_命名 / TTL
- 3 个 service 改继承: 各省 30-50 行
- 净收益: 100-150 行 (相对 784 行 = 13-19%)
- 净成本: 1 周 + 中风险 (改动 3 个 caller API)

### 推荐方案 (主拍决策时启动)
1. 先抽 `BaseChunkedUpload` 抽象类 (~150 行, 放 `app/services/base_chunked_upload.py`)
2. 定义统一接口: `init_upload / upload_chunk / complete_upload / abort_upload`
3. 改 3 个 service 继承 (各 ~30 行)
4. 跑回归测试 (3 个 caller 完整兼容)
5. 实施周期: 1 周

---

## 锚点范式累计

- 57595ee95 W19 commit ~599
- 5aa33dbdd W-N-P3 commit ~598
- 累计 20 commit, 0 业务代码改动

---

## 主拍决策单 (主拍填)

| 项 | 状态 |
|---|------|
| 3 个 service 抽象价值评估 | ✓ 已就绪 |
| BaseChunkedUpload 抽象设计 | [ ] |
| 1 周实施周期 | [ ] |
| 主拍书面批准 | [ ] |

批准后执行: 抽 base class + 3 子类继承 + 回归测试
