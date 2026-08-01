# W100-RAG-4 Reranker Acceptance Gate Report

**Backend**: `cross_encoder`
**Threshold**: 92.00%
**Result**: [OK] PASS
**Accuracy**: 100.00% (20/20)

## Failures

No failures

## 关键铁律 (3 新)

- **类 20.127**: acceptance gate 失败必 raise, 不静默降级
- **类 20.128**: CrossEncoder 默认 backend, 不破坏 W75 baseline (93.5%)
- **类 20.129**: original_index 缺失时用 id 匹配原始索引
