"""fix_minio_mime.py — 批量修正 MinIO 对象 Content-Type (按扩展名)

背景: 2026-08-30 发现历史 drive 上传对象 Content-Type 全为
application/octet-stream (前端未透传 MIME), 导致 Office Online 预览器
无法按正确类型处理。已用本脚本对 microbubble 桶 837 个对象完成修正。

用法:
    python scripts/fix_minio_mime.py            # dry-run 统计
    python scripts/fix_minio_mime.py --apply    # 实际重写元数据 (零拷贝,
                                                # 仅替换元数据, 内容不动)

注意: minio SDK 7.2 的 copy_object 用 metadata={"Content-Type": ...} +
metadata_directive="REPLACE"; list_objects 的 content_type 不可靠(常为 None),
故按扩展名无条件重写。增量为新上传对象时, chunked merge 已按文件名推断 MIME。
"""
import sys
from minio import Minio
from minio.commonconfig import CopySource

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ENDPOINT = "127.0.0.1:9000"
client = Minio(ENDPOINT, access_key="minioadmin", secret_key="minio2026secure", secure=False)

MIME = {
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".ppt": "application/vnd.ms-powerpoint",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc": "application/msword",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls": "application/vnd.ms-excel",
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
    ".gif": "image/gif", ".webp": "image/webp", ".svg": "image/svg+xml",
    ".mp4": "video/mp4", ".mov": "video/quicktime", ".avi": "video/x-msvideo",
    ".mp3": "audio/mpeg", ".wav": "audio/wav", ".m4a": "audio/mp4",
    ".txt": "text/plain", ".csv": "text/csv", ".md": "text/markdown",
    ".zip": "application/zip", ".7z": "application/x-7z-compressed",
    ".rar": "application/vnd.rar",
}

dry = "--apply" not in sys.argv
objects = client.list_objects("microbubble", recursive=True, include_user_meta=True)
fix, keep, nomime = [], 0, []
for o in objects:
    name = o.object_name.rsplit("/", 1)[-1]
    ext = ("." + name.rsplit(".", 1)[-1].lower()) if "." in name else ""
    mime = MIME.get(ext)
    if mime:
        fix.append((o.object_name, mime, o.size))
    else:
        nomime.append(o.object_name)

print(f"total scanned: {len(fix) + len(nomime)} | to-fix: {len(fix)} | no-mime-match: {len(nomime)}")
from collections import Counter
by_ext = Counter(n.rsplit(".", 1)[-1].lower() for n, _, _ in fix)
print("fix by ext:", dict(by_ext))

if dry:
    for n, m, s in fix[:5]:
        print(f"  [dry] {n[:60]} -> {m}")
    sys.exit(0)

ok = fail = 0
for n, mime, _ in fix:
    try:
        client.copy_object(
            "microbubble", n,
            CopySource("microbubble", n),
            metadata={"Content-Type": mime},
            metadata_directive="REPLACE",
        )
        ok += 1
    except Exception as e:
        fail += 1
        print("FAIL:", n[:60], repr(e)[:80])
print(f"applied: {ok} ok, {fail} fail")
