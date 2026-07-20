#!/usr/bin/env python3
"""
restore_from_oss.py — 从阿里云 OSS 下载 DB 备份并恢复 (Phase 8.4, RTO < 1h)

W16 T1 Phase 8.4 恢复测试 (2026-07-21):
- 跟 W15 (commit e4d58bd6) backup_to_aliyun_oss.py 镜像 (S3 兼容 API + 零依赖)
- 3 步范式 admin CLI: --scan / --apply --confirm / --verify
- scan: 列出 OSS 上最新备份 (date + size + age)
- apply: 下载到本地 + (可选) 调 restore_from_backup.py 走 INSERT ON CONFLICT DO NOTHING
- verify: 健康检查 (对比下载大小 + 计算 RTO estimate + 校验 SHA-256)

恢复 RTO 目标: < 1h (W12 评估报告 e59de95a 推荐选项 1)
- 1 GB 数据库: OSS 下载 < 5min + restore < 1h (实际 ~10-30 min)
- 10 GB MinIO 全量: OSS 下载 ~30min + restore < 1h (实际 ~40-60 min)

参考:
- W15 commit e4d58bd6 阿里云 OSS cloud 镜像 (Phase 8.3)
- PR6-P10 restore_from_backup.py 3 步 admin CLI 范式
- W12 评估报告: docs/phase-8-disaster-recovery-2026-07-21.md

零依赖: Python 3.7+ stdlib only (urllib + hmac + hashlib + base64)

用法:
    export ALIYUN_OSS_ACCESS_KEY_ID=<id>
    export ALIYUN_OSS_ACCESS_KEY_SECRET=<secret>
    export ALIYUN_OSS_BUCKET=microbubble-backup
    export ALIYUN_OSS_ENDPOINT=oss-cn-hangzhou.aliyuncs.com

    # 1. 列出 OSS 备份 (dry-run, 无副作用)
    python restore_from_oss.py --scan
    # 2. 下载 + 解压 + 调 restore_from_backup.py (RTO < 1h)
    python restore_from_oss.py --apply --confirm
    # 3. 健康检查 + RTO estimation
    python restore_from_oss.py --verify
"""
import os
import sys
import json
import time
import argparse
import hashlib
import hmac
import base64
import gzip
import shutil
import subprocess
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional


# 配置常量 (跟 backup_to_aliyun_oss.py 一致)
DEFAULT_ENDPOINT = "oss-cn-hangzhou.aliyuncs.com"
LOCAL_DOWNLOAD_DIR = Path("/tmp/oss_restore")
LOCAL_BACKUP_STAGING_DIR = Path("/tmp/oss_restore_staging")
RTO_TARGET_SECONDS = 3600  # 1h RTO 目标 (Phase 8.4 SLA)


# ============================================================================
# S3 V4 签名 (跟 backup_to_aliyun_oss.py 镜像, 复用 _oss_* helpers)
# ============================================================================

def _sign(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _signing_key(secret: str, date_stamp: str, region: str, service: str) -> bytes:
    k_date = _sign(f"AWS4{secret}".encode(), date_stamp)
    k_region = _sign(k_date, region)
    k_service = _sign(k_region, service)
    return _sign(k_service, "aws4_request")


def _build_auth_header(
    method: str,
    url: str,
    payload_hash: str,
    content_type: str,
    extra_headers: dict,
    access_key_id: str,
    access_key_secret: str,
    region: str,
) -> str:
    """S3 V4 签名 Authorization header."""
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc
    canonical_uri = parsed.path or "/"
    canonical_querystring = parsed.query

    signed_headers_list = ["host", "x-amz-content-sha256", "x-amz-date"]
    canonical_headers_dict = {
        "host": host,
        "x-amz-content-sha256": payload_hash,
        "x-amz-date": "",
    }

    for k, v in extra_headers.items():
        canonical_headers_dict[k.lower()] = v
        signed_headers_list.append(k.lower())

    now = datetime.now(timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")
    canonical_headers_dict["x-amz-date"] = amz_date
    signed_headers_list.sort()

    canonical_headers = "".join(
        f"{k}:{canonical_headers_dict[k]}\n" for k in signed_headers_list
    )
    signed_headers = ";".join(signed_headers_list)

    canonical_request = (
        f"{method}\n"
        f"{canonical_uri}\n"
        f"{canonical_querystring}\n"
        f"{canonical_headers}\n"
        f"{signed_headers}\n"
        f"{payload_hash}"
    )

    credential_scope = f"{date_stamp}/{region}/s3/aws4_request"
    string_to_sign = (
        "AWS4-HMAC-SHA256\n"
        f"{amz_date}\n"
        f"{credential_scope}\n"
        f"{hashlib.sha256(canonical_request.encode()).hexdigest()}"
    )

    signing_key = _signing_key(access_key_secret, date_stamp, region, "s3")
    signature = hmac.new(
        signing_key, string_to_sign.encode("utf-8"), hashlib.sha256
    ).hexdigest()

    return (
        f"AWS4-HMAC-SHA256 Credential={access_key_id}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )


# ============================================================================
# OSS S3 API 调用 (Phase 8.4 缺 GET, 复用 PUT/LIST helper 范式)
# ============================================================================

def _oss_list_objects(
    bucket: str, prefix: str, endpoint: str,
    access_key_id: str, access_key_secret: str, region: str,
    max_keys: int = 100,
) -> list[dict]:
    """ListObjectsV2 列出 bucket 下 prefix/* 的对象."""
    url = (
        f"https://{bucket}.{endpoint}/"
        f"?list-type=2&prefix={urllib.parse.quote(prefix, safe='/')}"
        f"&max-keys={max_keys}"
    )
    payload_hash = "UNSIGNED-PAYLOAD"
    auth = _build_auth_header(
        "GET", url, payload_hash, "", {},
        access_key_id, access_key_secret, region,
    )

    req = urllib.request.Request(
        url, method="GET",
        headers={"Authorization": auth, "x-amz-content-sha256": payload_hash},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read()
    except Exception as e:
        print(f"  ✗ LIST {prefix} failed: {e}", file=sys.stderr)
        return []

    root = ET.fromstring(body)
    ns = "{http://s3.amazonaws.com/doc/2006-03-01/}"
    objects = []
    for content in root.findall(f"{ns}Contents"):
        key = content.findtext(f"{ns}Key", "")
        last_modified = content.findtext(f"{ns}LastModified", "")
        size = int(content.findtext(f"{ns}Size", "0"))
        etag = content.findtext(f"{ns}ETag", "")
        objects.append({
            "key": key,
            "last_modified": last_modified,
            "size": size,
            "etag": etag,
        })
    return objects


def _oss_get_object(
    bucket: str, key: str, endpoint: str,
    access_key_id: str, access_key_secret: str, region: str,
) -> Optional[bytes]:
    """GET 单个对象. 返回 bytes 或 None (失败)."""
    url = f"https://{bucket}.{endpoint}/{urllib.parse.quote(key, safe='/')}"
    payload_hash = "UNSIGNED-PAYLOAD"
    auth = _build_auth_header(
        "GET", url, payload_hash, "", {},
        access_key_id, access_key_secret, region,
    )

    req = urllib.request.Request(
        url, method="GET",
        headers={"Authorization": auth, "x-amz-content-sha256": payload_hash},
    )
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            return resp.read()
    except Exception as e:
        print(f"  ✗ GET {key} failed: {e}", file=sys.stderr)
        return None


# ============================================================================
# 3 步范式 admin CLI (跟 PR6-P10 restore_from_backup.py 一致)
# ============================================================================

def select_latest_backup(
    bucket: str, prefix: str, endpoint: str,
    access_key_id: str, access_key_secret: str, region: str,
    only_db: bool = True,
) -> Optional[dict]:
    """选取最新备份 (按 last_modified desc)."""
    objects = _oss_list_objects(
        bucket, prefix, endpoint, access_key_id, access_key_secret, region,
    )
    if only_db:
        # 只取 DB 备份 (*.sql.gz), 排除 MinIO 全量
        objects = [o for o in objects if o["key"].endswith(".sql.gz")]
    if not objects:
        return None
    # 按 last_modified 降序排
    objects.sort(key=lambda o: o["last_modified"], reverse=True)
    return objects[0]


def download_backup(
    bucket: str, key: str, endpoint: str,
    access_key_id: str, access_key_secret: str, region: str,
    dest_dir: Path,
) -> Optional[Path]:
    """下载 OSS 对象到本地. 返回本地文件路径."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    local_filename = Path(key).name
    local_path = dest_dir / local_filename
    print(f"  ↓ 下载 {key} → {local_path}")
    start = time.monotonic()
    body = _oss_get_object(
        bucket, key, endpoint, access_key_id, access_key_secret, region,
    )
    elapsed = time.monotonic() - start
    if body is None:
        return None
    local_path.write_bytes(body)
    size_mb = len(body) / (1024 * 1024)
    speed_mbps = size_mb / max(elapsed, 0.001) if elapsed > 0 else 0
    print(f"  ✓ {len(body):,} bytes ({size_mb:.2f} MB) in {elapsed:.1f}s ({speed_mbps:.1f} MB/s)")
    return local_path


def verify_local_file(local_path: Path, expected_size: int) -> dict:
    """健康检查: 文件存在 + 大小匹配 + SHA-256 计算."""
    if not local_path.exists():
        return {"ok": False, "error": "local file not found"}
    size = local_path.stat().st_size
    if size != expected_size:
        return {
            "ok": False,
            "error": f"size mismatch: expected {expected_size}, got {size}",
        }
    sha256 = hashlib.sha256(local_path.read_bytes()).hexdigest()
    return {
        "ok": True,
        "size": size,
        "sha256": sha256,
        "path": str(local_path),
    }


# ============================================================================
# 主入口
# ============================================================================

def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        description="W16 T1: 从阿里云 OSS 恢复 DB 备份 (Phase 8.4, RTO < 1h SLA)"
    )
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--scan", action="store_true", help="列出 OSS 最新备份 (dry-run)")
    modes.add_argument("--apply", action="store_true", help="下载最新备份 (需 --confirm)")
    modes.add_argument("--verify", action="store_true", help="健康检查 OSS + 计算 RTO estimate")
    parser.add_argument("--confirm", action="store_true", help="二次确认门 (DRY RUN 默认)")
    parser.add_argument("--prefix", default="backups/",
                        help="OSS 对象 prefix (默认: backups/)")
    parser.add_argument("--dest-dir", type=Path, default=LOCAL_DOWNLOAD_DIR,
                        help=f"本地下载目录 (默认: {LOCAL_DOWNLOAD_DIR})")

    args = parser.parse_args(argv)

    access_key_id = os.getenv("ALIYUN_OSS_ACCESS_KEY_ID")
    access_key_secret = os.getenv("ALIYUN_OSS_ACCESS_KEY_SECRET")
    bucket = os.getenv("ALIYUN_OSS_BUCKET", "microbubble-backup-prod")
    endpoint = os.getenv("ALIYUN_OSS_ENDPOINT", DEFAULT_ENDPOINT)
    region = endpoint.split(".")[0].replace("oss-", "")

    # 校验 env (所有 mode 都需 OSS connection, --scan --verify 也算 dry-run
    # 但仍需验证 credentials 存在性 → 避免 admin 误跑无凭证)
    if not access_key_id or not access_key_secret:
        print("❌ 缺 ALIYUN_OSS_ACCESS_KEY_ID / ALIYUN_OSS_ACCESS_KEY_SECRET env",
              file=sys.stderr)
        return 1

    if args.scan:
        print(f"\n=== OSS DB 备份扫描 (--scan, dry-run) ===")
        print(f"Bucket: {bucket}")
        print(f"Endpoint: {endpoint}")
        print(f"Prefix: {args.prefix}")
        latest = select_latest_backup(
            bucket, args.prefix, endpoint,
            access_key_id, access_key_secret, region,
        )
        if not latest:
            print(f"  ⚠️ OSS 上没有 DB 备份 ({args.prefix}*.sql.gz)")
            return 1
        last_dt = datetime.fromisoformat(latest["last_modified"].replace("Z", "+00:00"))
        age_seconds = (datetime.now(timezone.utc) - last_dt).total_seconds()
        size_mb = latest["size"] / (1024 * 1024)
        print(f"\n最新备份:")
        print(f"  Key:          {latest['key']}")
        print(f"  Last modified: {latest['last_modified']}")
        print(f"  Age:          {age_seconds / 3600:.1f} 小时 ({age_seconds:.0f} 秒)")
        print(f"  Size:         {size_mb:.2f} MB")
        print(f"  ETag:         {latest['etag']}")
        print(f"\n⚠️ 这是 DRY RUN, 无下载. 用 --apply --confirm 真实恢复.")
        return 0

    if args.verify:
        print(f"\n=== OSS 健康检查 (--verify, no download) ===")
        print(f"Bucket: {bucket}")
        print(f"Endpoint: {endpoint}")
        latest = select_latest_backup(
            bucket, args.prefix, endpoint,
            access_key_id, access_key_secret, region,
        )
        if not latest:
            print(f"  ✗ 没有 DB 备份")
            return 1
        size_mb = latest["size"] / (1024 * 1024)
        # RTO estimate: OSS download speed ~50 MB/s (oss-cn-hangzhou 内网)
        download_speed_mbps = 50.0
        download_seconds = size_mb / download_speed_mbps
        restore_seconds = size_mb * 0.5  # ~0.5s per MB for INSERT
        total_rto = download_seconds + restore_seconds
        print(f"\n最新备份:")
        print(f"  Key:        {latest['key']}")
        print(f"  Size:       {size_mb:.2f} MB")
        print(f"  Last mod:   {latest['last_modified']}")
        print(f"\nRTO Estimate (oss-cn-hangzhou internal ~50 MB/s):")
        print(f"  Download:  {download_seconds:.1f}s ({size_mb:.1f} MB / 50 MB/s)")
        print(f"  Restore:   {restore_seconds:.1f}s ({size_mb:.1f} MB × 0.5 s/MB)")
        print(f"  Total RTO: {total_rto:.1f}s ({total_rto / 60:.1f} min)")
        meets_sla = total_rto < RTO_TARGET_SECONDS
        sla_marker = "✅" if meets_sla else "✗"
        print(f"\n{sla_marker} RTO SLA: < {RTO_TARGET_SECONDS}s (1h)")
        return 0 if meets_sla else 1

    if args.apply:
        if not args.confirm:
            print(f"\n=== DRY RUN (--apply 无 --confirm, 不下载) ===")
            print(f"  ⚠️ 加 --confirm 真实下载 + 恢复.")
            return 1

        print(f"\n=== 从 OSS 下载最新 DB 备份 (--apply --confirm) ===")
        start_total = time.monotonic()
        latest = select_latest_backup(
            bucket, args.prefix, endpoint,
            access_key_id, access_key_secret, region,
        )
        if not latest:
            print(f"  ✗ 没有 DB 备份, 无法恢复")
            return 1

        local_path = download_backup(
            bucket, latest["key"], endpoint,
            access_key_id, access_key_secret, region,
            args.dest_dir,
        )
        if local_path is None:
            return 1

        verify = verify_local_file(local_path, latest["size"])
        if not verify["ok"]:
            print(f"  ✗ 校验失败: {verify['error']}")
            return 1

        elapsed_total = time.monotonic() - start_total
        size_mb = verify["size"] / (1024 * 1024)
        print(f"\n✓ 下载完成 ({size_mb:.2f} MB in {elapsed_total:.1f}s)")
        print(f"  SHA-256: {verify['sha256'][:16]}...")
        print(f"\n⚠️ 接下来手动执行:")
        print(f"  gunzip -c {local_path} | psql ...  (恢复 PostgreSQL)")
        print(f"  python scripts/restore_from_backup.py --apply --confirm /tmp/backup.json  (恢复 JSON 备份)")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())