# 分片上传：四个文件的关系（2026-09-30 核实）

> **背景**：阶段收尾规划 S3 清单曾列"合并 chunked_upload 四件套"。2026-09-30 逐个核实
> 后**结论是不该合并** —— 它们不是重复代码，是**四种不同的存储契约**。本文件说明区别，
> 避免下一个人再看到相似的文件名而误判。

## 四个文件

| 文件 | 行数 | 状态存哪 | 谁在用 | 契约特点 |
|---|---:|---|---|---|
| `chunked_upload_service.py` | 277 | **本地临时文件 + ffmpeg 子进程合并** | `api/v1/meeting.py`、`meeting_recording.py` | 会议录音**边录边传**：分片落 `tempfile`，完成后调 ffmpeg 合成。进程内 `subprocess` + `tempfile` 是它的固有形态 |
| `generic_chunked_upload_service.py` | 226 | 对象存储（无 ORM 模型） | `api/v1/drive_files.py`、`upload_multipart.py` | 通用分片上传，**不持久化上传会话**（无 DB 表、无 resume） |
| `drive_chunked_upload_service.py` | 400 | **PG 表 `DriveChunkedUpload`（alembic 080）** | `api/v1/drive_chunked_uploads.py` | 网盘分片：**支持断点续传 + sha256 校验 + 过期清理**，状态必须持久（进程重启后仍能 resume） |
| `drive_chunked_upload_tasks.py` | 36 | 无状态 | `app/core/celery.py`（beat 调度） | Celery wrapper，只调 `cleanup_expired_uploads` |

## 为什么不能合

判据是**状态生命周期**，不是代码相似度：

- **临时态 vs 持久态**：`generic` 传完即弃，`drive_chunked` 必须能跨进程重启 resume →
  前者可以放内存/临时文件，后者必须有 PG 表。合成一个服务就要同时承担两套状态管理，
  反而更复杂。
- **本地文件 vs 对象存储**：`chunked_upload_service` 走 `tempfile` + ffmpeg（录音场景要
  处理本地录制文件），另两个直接操作对象存储。
- **有无清理链路**：只有 `drive_chunked` 有 Celery 定时清理（36 行 wrapper 就是为此存在）。

## 真正值得做的（如果要优化）

- `chunked_upload_service` 与 `generic_chunked_upload_service` 的**分片命名规则**
  （`_chunk_object_name` / `_chunk_prefix` / `_derive_object_name`）确实有相似逻辑，
  可以抽一个纯函数工具，但**不要合并服务**。
- 测试覆盖：`drive_chunked_upload_service` 有 e2e（`test_drive_v2_pr5_trash_chunk_e2e.py`、
  `test_w84_b1_chunked_retry_e2e.py`）；另两个的测试见 `tests/ARCHIVED.md`
  （`test_generic_chunked_upload.py` 因需 MinIO 已归档）。

## 相关

- 阶段收尾规划：`desktop-conversion/docs/plans/2026-09-30-phase-closeout-plan.md`（S3 段）
- CLAUDE.md 的 `## 永久铁律` 类 20.155（容器内无 docker CLI 时优雅 skip）