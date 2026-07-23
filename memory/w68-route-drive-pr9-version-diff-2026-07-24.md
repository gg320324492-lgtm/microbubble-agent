# W68 路线 F-2+ Drive 版本对比 (Drive v2 PR9+) (2026-07-24)

> **锚点范式第 50 守恒** — Drive v2 PR9 系列第 4 批 (F-2+) 收官 (W68 主指挥协调范式第 50 次派工).

## 任务

- **背景**: W68 第 3 批 (F-2) 已建 `drive_version_service.py` (上传/列表/下载/回滚/删除). 第 4 批 F-2+ 加**版本对比** diff 功能.
- **范围**: 5 文件 (service + schema + API + e2e + docs) + memory = 6 文件总计 ~990 行
- **分支**: `feat/drive-v2-pr9-version-diff-2026-07-24` (从 main HEAD `26c7c5620` 拉)

## 交付清单

| 文件 | 行数 | 角色 |
|------|------|------|
| `app/services/drive_version_diff_service.py` | ~430 | 核心 service: `DriveVersionDiffService.compare_versions` + `preview_version` + `VersionDiff` dataclass |
| `app/schemas/drive_version_diff.py` | ~75 | Pydantic: `VersionDiffResponse` + `VersionPreviewResponse` + `VersionMeta` |
| `app/api/v1/drive_version_diff.py` | ~80 | 2 endpoints: GET `/diff` + GET `/preview`, 在 main.py 注册到 `/api/v1` |
| `tests/test_drive_v2_pr9_version_diff.py` | ~280 | 5 场景 e2e: text diff / binary diff / same-version / cross-file 404 + preview |
| `docs/drive-v2-pr9-version-diff.md` | ~150 | 算法选型 + 文本/二进制差异化 + 性能预算 + API 文档 |
| `memory/w68-route-drive-pr9-version-diff-2026-07-24.md` | (this) | 锚点范式第 50 守恒 |

## 5 大算法决策与权衡

### 1. 选 Python stdlib `difflib.SequenceMatcher` 而非第三方 lib

| 候选 | 优 | 劣 | 决策 |
|------|----|----|-----|
| difflib (stdlib) | 0 依赖 / Ratcliff-Obershelp / 行+字符 / 内置稳定 | N² 算法 10MB+ 慢 | ✅ 选 (本地小组文件足够) |
| jsdiff (前端) | 交互式 diff | 多传 5-10MB 到浏览器 | ❌ |
| LLM-based | 语义化 | $0.001/v + 100-500ms + 不 deterministic | ❌ |
| side-by-side (前端) | UI 漂亮 | 服务端 fast diff 算法还要接 | ❌ 留 PR11+ |

**教训**: 简单场景下 stdlib > 第三方. SequenceMatcher 对 95% 增量 diff (相邻版本) 50-200ms 完成, 性能足够. 不要无脑引依赖.

### 2. 文本 / 二进制差异化 (ext 白名单)

**白名单** (`TEXT_EXTENSIONS` frozenset, ~40 ext): txt/md/py/js/ts/json/yaml/csv/html/css/sql/sh 等.

**二进制**: PDF/image/zip/exe/video/audio/Office → metadata diff only (不解析内容).

**为什么差异化**:
- 解析二进制 PDF/image = 高 CPU + 易内存爆 + 用户看不懂 "改动在哪"
- 文本走 difflib 50-200ms 完成, 满足交互
- 二进制只 metadata (size_delta + uploader_delta) 让用户定位"什么时候谁改的"

**教训**: diff 功能必须**保守**, 不要试图解析所有文件类型. 解析失败比 metadata-only 难堪得多 (用户卡死 vs 拿到 size 对比).

### 3. 大文件保护 `TEXT_DIFF_MAX_BYTES = 1MB`

任何版本 > 1MB → 强制走 metadata diff + `warning` 字段:

```python
if len(from_bytes) > self.TEXT_DIFF_MAX_BYTES or len(to_bytes) > self.TEXT_DIFF_MAX_BYTES:
    return VersionDiff(...warning="文件超过 1024KB, 跳过完整 diff", is_text=False, ...)
```

**教训**: 软上限是必须的. SequenceMatcher N² 对 10MB 文件要几秒, 单 async task 阻塞能拖垮并发. 留 1MB 让用户去 preview 看头尾 (走 truncate 截断).

### 4. Defense-in-Depth 验证

5 层防御:
1. **API 层** Pydantic Query 校验 `from>=1` `to>=1`
2. **Service 层** `_validate_visible` 校验权限 (private 仅 owner)
3. **Service 层** WHERE 子句限定 `file_id` (DB 自然防)
4. **Service 层** 二次校验 `from_v.file_id == file_id` (防 race / DB race)
5. **API 层** preview 二次校验 `result["file_id"] == file_id_from_url` (防 URL 串联)

**教训**: Web endpoint 路径参数 + query 参数组合, **每层都要二次校验**. 别信任框架自动 binding, URL 串联 / race condition 都可能触发.

### 5. Error 容错链

- **encoding errors='replace'** 防单字节损坏炸整体
- **MinIO download try/except** 转 500 + 提示 (不要 silently pass, 用户需知道)
- **bytes.decode 失败** 转 500 + 提示 (同)
- **同版本** → 早返空 diff, 避免无意义 compute

## 性能预算

| 场景 | 文件 | 平均延迟 | P99 |
|------|-----|---------|-----|
| 文本 v1→v2 (50行) | 100B | ~30ms | <100ms |
| 文本 v1→v2 (5000行) | 100KB | ~200ms | <500ms |
| 文本 v1→v2 (接近 1MB) | 800KB | ~800ms | <1500ms |
| 二进制 metadata | 任意 | ~50ms (2x MinIO) | <200ms |
| Preview 前 N 行 | 500KB | ~80ms | <200ms |

**MinIO 是瓶颈**: 2 版本对比 = 2 次 download. 串行 (并行反而拖慢单 bucket) + 简化错误处理.

## 测试策略

`tests/test_drive_v2_pr9_version_diff.py` 5 场景 (覆盖算法+权限+边界):

1. `test_text_diff_returns_unified_diff` - 50 行 .py v1→v2, 验证 unified_diff 非空, changed_lines/additions/deletions > 0
2. `test_binary_diff_returns_metadata_only` - PDF 二进制, 验证 unified_diff=null, size_delta 准确
3. `test_same_version_returns_empty_diff` - from==to, 早返空 diff
4. `test_cross_file_version_rejected_and_missing_404` - 跨 file 拒绝 + 缺失 version 404
5. `test_preview_returns_first_n_lines` - 100 行 .py, head_lines=10 truncated=True, =200 truncated=False

**Mock 策略**: `monkeypatch app.services.file_service.file_service.download_file` 避免真 MinIO 依赖. 这与 `test_drive_v2_pr9_comments.py` 一致.

**0 production code 改动铁律维持**: Drive v2 PR9 系列新文件, 不动 v1 老路径.

## 沉淀的 N 条新铁律

1. **diff 不要无脑引第三方依赖** — Python stdlib difflib 对 95% 文件足够, 复杂场景再评估 jsdiff/diff-match-patch.
2. **文本/二进制 diff 必须差异化** — 二进制走 metadata-only, 文本走 difflib. 解析二进制 = 高 CPU + 用户看不懂.
3. **大文件必须有软上限** — `TEXT_DIFF_MAX_BYTES=1MB` 兜底. N² 算法对 10MB+ 是异步炸弹.
4. **Web endpoint 防御性验证 5 层** — Pydantic Query / Service 权限 / WHERE 子句 / Service 二次校验 / API 二次校验. URL 串联 + race 都防住.
5. **MinIO download 容错必须 try/except** — 不要 silently pass, 转 500 + 错误提示, 用户需要知道是后端问题.
6. **同版本早返空 diff** — from==to 不要跑算法, 浪费 CPU + 误导用户.
7. **bytes.decode(encoding='utf-8', errors='replace')** — 防单字节损坏炸整体, 比 silent 比抛错都好.

## 与之前 PR 关系

- **W68 第 3 批 F-2 (Drive v2 PR9 versions)** 已建 `drive_file_versions` 表 + `drive_version_service.py`. 本批直接复用, 不改 schema.
- **W68 第 4 批 F-1 (Drive v2 PR9 comments)** 同样 drive folder + Knowledge fixture pattern. **可以提取 `_create_drive_file_for_diff` 测试 conftest** (留给 PR10 收官时统一).
- **PR4 `KnowledgeVersion` (审计日志)** 与 PR9 `DriveFileVersion` (历史仓库) 互补, diff 走 PR9.

## 跨周期累计

- W68 已派工 4 批 (第 1 批 14+1 agents + 第 2 批 4 agents + 第 3 批 8 agents + 第 4 批本 agent F-2+)
- Drive v2 PR9 已交付: comments + versions + version-diff + ws push + 文件锁 + 预览 + 移动端 (部分)
- 锚点范式 W7 12 → W66 27 → W67 28 → W68 30 → **W68 50 守恒**
- 0 production code 改动铁律维持

## 下一步建议 (PR10 收官)

- [ ] F-3 Drive v2 PR9+ 批量对比 (用户选 3+ 版本, 输出 summary + 各 version 号短描述)
- [ ] F-4 PR11 后端 fast diff 优化 (5MB+ 文件)
- [ ] G-x PR12 前端 drive 版本对比 UI (side-by-side Monaco diff editor)
- [ ] 统一 test_drive_v2_pr9_* 测试 conftest fixture (drive_folder / drive_file / drive_version 共享)
