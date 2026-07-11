#!/usr/bin/env python3
"""
backup_minio_daily.py — 每日 MinIO bucket 全量备份 (Python 原生, 无外部依赖)

v2 (2026-07-11): 改用 urllib 直接调 S3 API (ListObjectsV2 + GetObject), 无需 mc CLI
                  原 mc 版本因为用户机器没装 mc 失败

根因: 2026-07-11 凌晨 microbubble bucket 被 wipe, 25 个成员头像 URL 全部 404
防御: 每天凌晨 3:30 (避开 DB 备份 2:00) 全量备份 microbubble/ 到
       E:\\microbubble-agent\\backups\\minio-daily\\<date>\\
       保留 30 天自动清理

零依赖: Python 3.7+ stdlib only (urllib + hmac + hashlib + base64)

用法:
    python backup_minio_daily.py              # 备份到今天的目录
    python backup_minio_daily.py --cleanup 30 # 清理 30 天前
    python backup_minio_daily.py --dry-run    # 只看不跑
"""

import os
import sys
import io
import shutil
import argparse
import hashlib
import hmac
import base64
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
    except Exception:
        pass

BACKUP_ROOT = Path(r"E:\microbubble-agent\backups\minio-daily")
SOURCE_BUCKET = "microbubble"
MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT", "http://localhost:9000")
DEFAULT_RETENTION_DAYS = 30


def log(msg: str):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def load_minio_credentials() -> tuple[str, str]:
    """从 .env.webhook 或环境变量读 MinIO 凭证"""
    access_key = os.environ.get("MINIO_ACCESS_KEY")
    secret_key = os.environ.get("MINIO_SECRET_KEY")

    env_path = Path(r"E:\microbubble-agent\.env.webhook")
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k, v = k.strip(), v.strip()
            if k == "MINIO_ACCESS_KEY" and not access_key:
                access_key = v
            elif k == "MINIO_SECRET_KEY" and not secret_key:
                secret_key = v

    if not access_key:
        access_key = "minioadmin"
    if not secret_key:
        secret_key = "minio2026secure"
    return access_key, secret_key


# ===== AWS Signature V4 for S3/MinIO =====

def _sign(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _signature_key(secret_key: str, date_stamp: str, region: str, service: str) -> bytes:
    k_date = _sign(("AWS4" + secret_key).encode("utf-8"), date_stamp)
    k_region = _sign(k_date, region)
    k_service = _sign(k_region, service)
    k_signing = _sign(k_service, "aws4_request")
    return k_signing


def _signed_request(method: str, url: str, access_key: str, secret_key: str,
                     region: str = "us-east-1", service: str = "s3",
                     extra_headers: dict = None, body: bytes = b"") -> urllib.request.Request:
    """Build a signed urllib Request for S3/MinIO"""
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc
    canonical_uri = parsed.path or "/"
    canonical_querystring = parsed.query

    now = datetime.now(timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")

    payload_hash = hashlib.sha256(body).hexdigest()

    headers = {
        "host": host,
        "x-amz-content-sha256": payload_hash,
        "x-amz-date": amz_date,
    }
    if extra_headers:
        headers.update(extra_headers)

    sorted_header_keys = sorted(headers.keys())
    canonical_headers = "".join(f"{k}:{headers[k].strip()}\n" for k in sorted_header_keys)
    signed_headers = ";".join(sorted_header_keys)

    canonical_request = f"{method}\n{canonical_uri}\n{canonical_querystring}\n{canonical_headers}\n{signed_headers}\n{payload_hash}"

    algorithm = "AWS4-HMAC-SHA256"
    credential_scope = f"{date_stamp}/{region}/{service}/aws4_request"
    string_to_sign = f"{algorithm}\n{amz_date}\n{credential_scope}\n{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"

    signing_key = _signature_key(secret_key, date_stamp, region, service)
    signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    authorization = (
        f"{algorithm} Credential={access_key}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )
    headers["Authorization"] = authorization

    return urllib.request.Request(url, data=body if body else None, headers=headers, method=method)


def _list_objects_paginated(prefix: str, access_key: str, secret_key: str) -> list[dict]:
    """List all objects in bucket with given prefix (handles pagination)"""
    objects = []
    continuation_token = None

    while True:
        params = {"list-type": "2", "prefix": prefix}
        if continuation_token:
            params["continuation-token"] = continuation_token

        query = urllib.parse.urlencode(params)
        url = f"{MINIO_ENDPOINT}/{SOURCE_BUCKET}?{query}"
        req = _signed_request("GET", url, access_key, secret_key,
                              extra_headers={"prefix": prefix} if False else None)

        with urllib.request.urlopen(req, timeout=60) as resp:
            xml_data = resp.read().decode("utf-8")

        root = ET.fromstring(xml_data)
        ns = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}

        for content in root.findall("s3:Contents", ns):
            objects.append({
                "key": content.findtext("s3:Key", namespaces=ns),
                "size": int(content.findtext("s3:Size", namespaces=ns) or 0),
                "etag": content.findtext("s3:ETag", namespaces=ns),
            })

        is_truncated = root.findtext("s3:IsTruncated", namespaces=ns) == "true"
        if not is_truncated:
            break
        continuation_token = root.findtext("s3:NextContinuationToken", namespaces=ns)

    return objects


def _download_object(key: str, dest: Path, access_key: str, secret_key: str) -> bool:
    """Download a single object to local path"""
    url = f"{MINIO_ENDPOINT}/{SOURCE_BUCKET}/{urllib.parse.quote(key, safe='/')}"
    req = _signed_request("GET", url, access_key, secret_key)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(dest, "wb") as f:
                shutil.copyfileobj(resp, f)
        return True
    except Exception as e:
        log(f"  ❌ 下载失败 {key}: {e}")
        return False


def mirror_bucket(date_str: str, dry_run: bool = False) -> Path:
    """List all objects and download to BACKUP_ROOT/<date>/"""
    target_dir = BACKUP_ROOT / date_str
    access_key, secret_key = load_minio_credentials()

    log(f"  列出 {SOURCE_BUCKET}/ 下所有对象...")
    if dry_run:
        log(f"  [DRY-RUN] list_objects + download")
        return target_dir

    objects = _list_objects_paginated("", access_key, secret_key)
    log(f"  找到 {len(objects)} 个对象")

    target_dir.mkdir(parents=True, exist_ok=True)

    success = 0
    failed = 0
    total_bytes = 0
    for i, obj in enumerate(objects, 1):
        rel_path = obj["key"]
        dest = target_dir / rel_path.replace("/", os.sep)

        # 跳过目录 marker (key 以 / 结尾且 size=0)
        if rel_path.endswith("/"):
            dest.mkdir(parents=True, exist_ok=True)
            continue

        if dest.exists() and dest.stat().st_size == obj["size"]:
            # 已存在且大小一致, 跳过 (增量)
            success += 1
            total_bytes += obj["size"]
            continue

        if _download_object(rel_path, dest, access_key, secret_key):
            success += 1
            total_bytes += obj["size"]
        else:
            failed += 1

        # 进度
        if i % 50 == 0:
            log(f"  进度: {i}/{len(objects)} ({total_bytes / 1024 / 1024:.1f} MB)")

    log(f"  ✅ 备份完成: {success} 个成功, {failed} 个失败, {total_bytes / 1024 / 1024:.1f} MB")
    return target_dir


def cleanup_old_backups(retention_days: int, dry_run: bool = False) -> int:
    """清理 N 天前的旧备份"""
    if not BACKUP_ROOT.exists():
        return 0

    cutoff = datetime.now() - timedelta(days=retention_days)
    removed = 0
    for backup_dir in BACKUP_ROOT.iterdir():
        if not backup_dir.is_dir():
            continue
        try:
            dir_date = datetime.strptime(backup_dir.name, "%Y-%m-%d")
        except ValueError:
            continue
        if dir_date < cutoff:
            if dry_run:
                log(f"  [DRY-RUN] rmdir {backup_dir}")
            else:
                log(f"  清理: {backup_dir.name}")
                shutil.rmtree(backup_dir, ignore_errors=True)
            removed += 1
    return removed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cleanup", type=int, default=DEFAULT_RETENTION_DAYS)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-cleanup", action="store_true")
    parser.add_argument("--no-mirror", action="store_true")
    args = parser.parse_args()

    log("=== MinIO 每日备份 (Python 原生) ===")
    log(f"  备份根目录: {BACKUP_ROOT}")
    log(f"  源 bucket: {SOURCE_BUCKET}/")
    log(f"  Endpoint: {MINIO_ENDPOINT}")
    log(f"  保留天数: {args.cleanup}")
    if args.dry_run:
        log("  模式: DRY-RUN")

    # 1. 备份
    if not args.no_mirror:
        log("\n[1/2] 备份 microbubble bucket...")
        today = datetime.now().strftime("%Y-%m-%d")
        try:
            mirror_bucket(today, dry_run=args.dry_run)
        except Exception as e:
            log(f"❌ 备份失败: {e}")
            sys.exit(1)
    else:
        log("\n[1/2] 跳过备份 (--no-mirror)")

    # 2. 清理
    if not args.no_cleanup:
        log(f"\n[2/2] 清理 {args.cleanup} 天前旧备份...")
        removed = cleanup_old_backups(args.cleanup, dry_run=args.dry_run)
        log(f"  清理了 {removed} 个旧备份")
    else:
        log("\n[2/2] 跳过清理 (--no-cleanup)")

    log("\n=== 完成 ===")


if __name__ == "__main__":
    sys.exit(main() or 0)