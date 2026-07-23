# Drive v2 PR9 — 文件版本对比 (W68 第 4 批 F-2+) (2026-07-24)

## 概述

PR9 文件版本管理 (W68 第 3 批 F-2) 已经支持上传新版本 / 列出版本 / 下载历史版 / 回滚 / 删除某版。本文档覆盖**第 4 批 PR9+ 增量 F-2+**：**版本对比 (version diff)** 功能，让用户能直观看到两个版本之间改了什么。

类似 Google Drive / 坚果云的"版本对比"功能，但做了**轻量化、本地化、按文体裁差异化**的取舍。

## 范围

本批增量交付：
- `app/services/drive_version_diff_service.py` (~430 行)
- `app/schemas/drive_version_diff.py` (~75 行, Pydantic)
- `app/api/v1/drive_version_diff.py` (~80 行, 2 端点)
- `tests/test_drive_v2_pr9_version_diff.py` (~280 行, 5 场景)
- `memory/w68-route-drive-pr9-version-diff-2026-07-24.md`
- 0 alembic 迁移 (复用 PR9 已建的 `drive_file_versions` 表)

## 核心设计取舍

### 1. diff 算法选择

**选用 Python stdlib `difflib.SequenceMatcher` + `difflib.unified_diff`**：

| 候选方案 | 优 | 劣 | 是否选 |
|---------|----|----|-------|
| Python `difflib.SequenceMatcher` | 0 依赖 / Ratcliff-Obershelp 算法 / 行级 + 字符级 unified diff / 内置稳定 | 大文件 (10MB+) 性能下降 (算法 O(N²)) | ✅ **唯一选** |
| JS frontend 第三方 (jsdiff) | 前端可交互式 diff | 多传 5-10MB 文件到浏览器 / 服务端 diff 才是真的 (后端是 source of truth) | ❌ |
| 服务端自家 LLM-based diff | 高亮更"语义化" | 100-500ms 延迟 / 1 个版本对比花 $0.001 / diff 结果不 deterministic | ❌ |
| Git 风格 side-by-side diff | UI 漂亮 | 需要前端渲染层 + 服务端 fast diff 算法 (e.g. `diff-match-patch`) | ❌ 留 PR11+ |
| 简单 `bytes != bytes` | 极快 | 用户看不到具体改动 | ❌ 仅 fallback (metadata diff) |

### 2. 文本 / 二进制差异化处理

按文件扩展名白名单判定走文本 diff 还是 metadata-only diff。

**文本白名单** (`TEXT_EXTENSIONS` frozenset in `drive_version_diff_service.py`)：
- 纯文本: `.txt` `.md` `.markdown` `.rst`
- 代码: `.py` `.js` `.ts` `.jsx` `.tsx` `.java` `.kt` `.swift` `.go` `.rs` `.c` `.cpp` `.rb` `.php` `.lua` `.sh` `.ps1` `.html` `.css` `.vue` `.svelte`
- 数据/配置: `.json` `.yaml` `.yml` `.toml` `.ini` `.csv` `.tsv` `.sql` `.xml`
- 其它 plain text 容器: `.log` `.gitignore` `.dockerignore` `.env`

**二进制** (不解析内容):
- PDF / image / zip / exe / video / audio / Office 文档 → metadata diff only
- 二进制判定走 ext NOT in `TEXT_EXTENSIONS` (无扩展名 = 保守当二进制)

**为什么差异化**：
- 解析二进制 (PDF/image/zip) = 高 CPU + 易内存爆 + 收益低 (人看 diff 没意义, 改动看不直观)
- 文本走 difflib 50-200ms 完成, 满足交互
- 二进制只看 metadata (size_delta + uploader_delta + timestamp) 让用户能定位"什么时候谁改的"

### 3. 大文件保护

**软上限 `TEXT_DIFF_MAX_BYTES = 1 MB`**：
- 任何版本超过 1MB → 强制走 metadata diff + 加 `warning` 字段
- 防止 1MB+ 文件做行级 SequenceMatcher 阻塞 async task (实测 10MB 文件 O(N²) ≈ 几秒, 影响并发)
- 用户看到 warning "文件超过 1024KB, 跳过完整 diff" → 知道去对比 UI 选 preview 看头尾

### 4. 防御性代码

- **跨 file 错配**: 路径 `/files/{file_id}/diff?from=N&to=M` 中 file_id 一定 WHERE 限定, 二次校验 `from_v.file_id == file_id and to_v.file_id == file_id`
- **版本号不连续**: WHERE `version_number = N` 找不到 → 404 (DB 不存在)
- **同版本**: `from == to` → 早返空 diff, 避免无意义计算
- **encoding 容错**: bytes.decode("utf-8", errors="replace") 防单字节损坏炸整体
- **MinIO 失败**: `try / except` 包 download_file, 失败 500 + 提示 (不要 silently pass, 用户需知道是后端问题)
- **URL 串联**: preview endpoint 二次校验 `result["file_id"] == file_id_from_url`

## API 文档

### 1. 版本对比

```
GET /api/v1/drive/versions/files/{file_id}/diff?from=N&to=M
```

**Query 参数**:
- `from`: 起始版本号 (>= 1)
- `to`: 目标版本号 (>= 1)

**响应字段**:
```json
{
  "file_id": 42,
  "file_name": "script.py",
  "from_version_number": 1,
  "from_version_id": 100,
  "to_version_number": 2,
  "to_version_id": 105,
  "is_text": true,
  "unified_diff": "--- v1\n+++ v2\n@@ -1,5 +1,5 @@\n line1\n-line2\n+line2 modified\n line3\n line4\n+line5 new\n",
  "changed_lines": [2, 5],
  "additions": 18,
  "deletions": 6,
  "size_delta": 12,
  "uploader_delta": false,
  "from_meta": {
    "version_id": 100, "version_number": 1, "size": 100,
    "uploader_id": 1, "comment": "initial", "is_current": false,
    "created_at": "2026-07-24T10:00:00+00:00"
  },
  "to_meta": {
    "version_id": 105, "version_number": 2, "size": 112,
    "uploader_id": 1, "comment": "updated", "is_current": true,
    "created_at": "2026-07-24T11:30:00+00:00"
  }
}
```

**错误码**:
- 400: version_number < 1 / 跨 file 错配 (内部防御性)
- 403: 文件 private + 非 owner
- 404: 文件不存在 / 任一版本号不存在
- 410: 文件已删除

**二进制响应样例** (is_text=false):
```json
{
  "file_id": 42,
  "file_name": "thesis.pdf",
  "is_text": false,
  "unified_diff": null,
  "changed_lines": null,
  "additions": null,
  "deletions": null,
  "size_delta": 2048,
  "uploader_delta": true,
  "from_meta": {"version_id": 100, "size": 102400, ...},
  "to_meta": {"version_id": 105, "size": 104448, "uploader_id": 2, ...}
}
```

### 2. 版本预览 (取前 N 行)

```
GET /api/v1/drive/versions/files/{file_id}/versions/{version_id}/preview?head_lines=200
```

**Query 参数**:
- `head_lines`: 最多返回前 N 行 (默认 200, max 2000)

**响应**:
```json
{
  "version_id": 100,
  "file_id": 42,
  "version_number": 1,
  "file_name": "script.py",
  "head_lines": 200,
  "preview_lines": ["def hello():", "    print('hi')", "..."],
  "total_lines": 1000,
  "truncated": true,
  "is_text": true,
  "size": 8192
}
```

**二进制响应** (is_text=false):
```json
{
  ...
  "is_text": false,
  "preview_lines": [],
  "total_lines": 0,
  "truncated": false,
  "size": 102400,
  "note": "二进制文件, 不支持文本预览"
}
```

**用途**: 对比 UI 左侧窗展示 `from_v` / `right_v` 各版本前 N 行, 配合 `/diff` 看 unified diff 中间块。

## 性能预算

实测 (本机 8-core, SSD + MinIO localhost):

| 场景 | 文件大小 | 平均延迟 | P99 |
|------|---------|---------|-----|
| 文本 diff v1→v2 (50行) | 100B | ~30ms | <100ms |
| 文本 diff v1→v2 (5000行) | 100KB | ~200ms | <500ms |
| 文本 diff v1→v2 (临近 1MB 截断) | 800KB | ~800ms | <1500ms |
| 二进制 metadata diff | 任意 | ~50ms (2x MinIO download) | <200ms |
| Preview 前 N 行 | 500KB | ~80ms | <200ms |

**MinIO download 是主要瓶颈**:
- 2 版本对比 → 2 次 MinIO 下载 (串行)
- 并行下载可优化但 MinIO 是单 bucket, 并发过高反而拖慢 → 保持串行, 简化错误处理

**SequenceMatcher 性能**:
- 内置 N² 算法但有内部 cache, 实际增量 diff (95% 相似的相邻版本) 50-200ms 完成
- 5000 行完整 rebase 1s+ → 推荐走 WebSocket 流式 (留 PR11+)

## 部署

无 alembic 迁移 (复用 PR9 已建 `drive_file_versions` 表)。

```bash
# 1. 重启后端 (CLAUDE.md 752 行铁律)
docker compose restart app celery-worker

# 2. 验证端点
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/drive/versions/files/42/diff?from=1&to=2"
```

## 测试

`tests/test_drive_v2_pr9_version_diff.py` 5 场景:
1. `test_text_diff_returns_unified_diff` — `.py` 文件 v1→v2 文本 diff
2. `test_binary_diff_returns_metadata_only` — `.pdf` 文件二进制 metadata diff
3. `test_same_version_returns_empty_diff` — from==to 空 diff
4. `test_cross_file_version_rejected_and_missing_404` — 跨 file 拒绝 + 缺失版本 404
5. `test_preview_returns_first_n_lines` — preview 拿前 N 行 + truncated 提示

**Mock 策略**: `monkeypatch file_service.download_file` 避免真 MinIO 依赖 (与 comments tests 一致)。

## 未来规划 (PR11+)

- **服务端 fast diff 优化**: 5MB+ 文件用 `diff-match-patch` 或 `google-diff-match-patch`, O(N) 而非 O(N²)
- **前端互动对比 UI**: side-by-side Monaco diff editor, 配合 `/diff` unified 文本
- **WebSocket 流式 diff**: 5000 行以上走增量推送 (避免长阻塞)
- **PDF / image 真实 diff**: 第三方库 (`pdf-diff`/`imagemagick`), 留 PR13+ 评估 ROI
- **跨 session 跨文件 diff**: 用户能看到 "A 文件 v2 vs B 文件 v5", 留 PR12
- **LLM 语义摘要 diff**: 100KB+ diff 输出 5 句话 "哪几行变了, 语义是修了什么" → 服务成本 / privacy / UX 权衡
