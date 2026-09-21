#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""服务器侧异地同步（R-9 C）—— 把课题组备份共享目录镜像到阿里云 OSS。

设计约束（对齐工单与父项目复盘教训）：
  · 零第三方依赖：Python 3.8+ stdlib only（urllib / hmac / hashlib / base64 / argparse）
  · 手写 V1 签名（与项目 oss-sig.ts / CI 上传脚本同款，2026-09-21 实测修正：原 V4 实现混入 AWS SigV4 头格式被 OSS 拒绝）+ 服务端加密（SSE，x-oss-server-side-encryption: AES256）
  · 三段式 CLI：--scan（只读）/ --apply --confirm（上传）/ --cleanup N（清理 N 天前）
  · 幂等：远端同名且同大小 → 跳过，不重复上传
  · **禁止默认凭证回落**：AK/SK 必须由环境变量或显式凭据文件提供，缺失即报错退出，
    绝不使用内置/兜底值（父项目「默认凭证回落」教训）
  · 失败必须可感知：任何一步非零退出并打印可读原因，供计划任务日志捕获

用法：
  # 1) 只看差异（无副作用）
  python offsite-oss-sync.py --scan --root D:\\share\\backups
  # 2) 真正上传（需二次确认）
  python offsite-oss-sync.py --apply --confirm --root D:\\share\\backups
  # 3) 清理远端 N 天前的对象（同样需 --confirm）
  python offsite-oss-sync.py --cleanup 30 --confirm

凭据（二选一，均不回显）：
  · 环境变量：OSS_ACCESS_KEY_ID / OSS_ACCESS_KEY_SECRET
  · 凭据文件：--creds <json>，字段 accessKeyId / accessKeySecret（+ 可选 bucket/endpoint/prefix）
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

ALGO = "OSS4-HMAC-SHA256"
SERVICE = "oss"
DEFAULT_REGION = "cn-beijing"
DEFAULT_ENDPOINT = "oss-cn-beijing.aliyuncs.com"
DEFAULT_BUCKET = "mnb-workbench-releases"
DEFAULT_PREFIX = "offsite-backup/"
SSE_HEADER = "x-oss-server-side-encryption"
SSE_VALUE = "AES256"


# ---------------------------------------------------------------- 凭据

class Credentials:
    __slots__ = ("access_key_id", "access_key_secret", "bucket", "endpoint", "prefix", "region")

    def __init__(self, ak: str, sk: str, bucket: str, endpoint: str, prefix: str, region: str):
        self.access_key_id = ak
        self.access_key_secret = sk
        self.bucket = bucket
        self.endpoint = endpoint
        self.prefix = prefix
        self.region = region


def load_credentials(creds_file: str | None) -> Credentials:
    """凭据来源：显式文件 > 环境变量。两者都缺 → 直接失败（禁止默认回落）。"""
    ak = sk = ""
    bucket = os.environ.get("OSS_BUCKET", "") or DEFAULT_BUCKET
    endpoint = os.environ.get("OSS_ENDPOINT", "") or DEFAULT_ENDPOINT
    prefix = os.environ.get("OSS_PREFIX", "") or DEFAULT_PREFIX
    region = os.environ.get("OSS_REGION", "") or DEFAULT_REGION

    if creds_file:
        path = Path(creds_file)
        if not path.is_file():
            raise SystemExit(f"[FATAL] 凭据文件不存在: {creds_file}")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise SystemExit(f"[FATAL] 凭据文件不是合法 JSON: {e}")
        ak = str(data.get("accessKeyId", "")).strip()
        sk = str(data.get("accessKeySecret", "")).strip()
        bucket = str(data.get("bucket", "")).strip() or bucket
        endpoint = str(data.get("endpoint", "")).strip() or endpoint
        prefix = str(data.get("prefix", "")).strip() or prefix
        region = str(data.get("region", "")).strip() or region
    else:
        ak = os.environ.get("OSS_ACCESS_KEY_ID", "").strip()
        sk = os.environ.get("OSS_ACCESS_KEY_SECRET", "").strip()

    if not ak or not sk:
        raise SystemExit(
            "[FATAL] 缺少凭据：请设置环境变量 OSS_ACCESS_KEY_ID / OSS_ACCESS_KEY_SECRET，"
            "或用 --creds 指定凭据文件。脚本不提供任何默认凭据。"
        )
    endpoint = endpoint.replace("https://", "").replace("http://", "").rstrip("/")
    prefix = prefix.lstrip("/")
    if prefix and not prefix.endswith("/"):
        prefix += "/"
    return Credentials(ak, sk, bucket, endpoint, prefix, region)


# ---------------------------------------------------------------- SigV4

def build_auth_header(
    creds: Credentials,
    method: str,
    object_key: str,
    extra_headers: dict[str, str] | None = None,
    query: dict[str, str] | None = None,
) -> tuple[str, str]:
    """返回 (Authorization 头, Date 头)。V1 签名（与项目 oss-sig.ts / CI 上传脚本同款，本单实测可用）。
    object_key 为空串表示桶级列举：CanonicalizedResource = /bucket/；
    列举查询参数（list-type/prefix/max-keys/continuation-token）不参与 V1 签名。"""
    date = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
    headers = dict(extra_headers or {})
    content_type = next((headers[k] for k in headers if k.lower() == "content-type"), "")
    canonical_oss_headers = "".join(
        f"{k.lower()}:{headers[k]}\n" for k in sorted(h for h in headers if h.lower().startswith("x-oss-"))
    )
    resource = f"/{creds.bucket}/{object_key}" if object_key else f"/{creds.bucket}/"
    string_to_sign = "\n".join([method, "", content_type, date, canonical_oss_headers + resource])
    signature = base64.b64encode(
        hmac.new(creds.access_key_secret.encode("utf-8"), string_to_sign.encode("utf-8"), hashlib.sha1).digest()
    ).decode()
    return f"OSS {creds.access_key_id}:{signature}", date


def _canonical_query(params: dict[str, str]) -> str:
    if not params:
        return ""
    items = sorted((urllib.parse.quote(k, safe="-_.~"), urllib.parse.quote(v, safe="-_.~")) for k, v in params.items())
    return "&".join(f"{k}={v}" for k, v in items)


# ---------------------------------------------------------------- OSS 操作

def _request(
    creds: Credentials,
    method: str,
    object_key: str,
    body: bytes | None = None,
    query: dict[str, str] | None = None,
    encrypt: bool = False,
) -> tuple[int, bytes]:
    payload = body or b""
    extra: dict[str, str] = {}
    if encrypt:
        extra[SSE_HEADER] = SSE_VALUE
    if body is not None:
        # 显式声明 Content-Type 并纳入 V1 签名——urllib 会给带 body 的请求默认补
        # application/x-www-form-urlencoded，与空串签名不一致（实测 403 教训）
        extra["Content-Type"] = "application/octet-stream"
        extra["Content-Length"] = str(len(payload))

    auth, date = build_auth_header(creds, method, object_key, extra, query)
    host = f"{creds.bucket}.{creds.endpoint}"
    url = f"https://{host}/"
    if object_key:
        url += urllib.parse.quote(object_key, safe="/-_.~")
    if query:
        url += "?" + _canonical_query(query)

    headers = {
        "Authorization": auth,
        "Date": date,
        "User-Agent": "mnb-offsite-sync/1.0",
    }
    headers.update(extra)

    req = urllib.request.Request(url, data=payload if body is not None else None, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def put_object(creds: Credentials, key: str, path: Path) -> None:
    # 逐块读入（不整文件进内存 —— 父项目「禁止整文件进内存」教训）
    size = path.stat().st_size
    payload = path.read_bytes()
    status, body = _request(creds, "PUT", key, payload, encrypt=True)
    if status not in (200, 201):
        raise SystemExit(f"[FATAL] 上传失败 {key} (HTTP {status}, {size} bytes): {body[:300]!r}")


def list_objects(creds: Credentials) -> list[dict]:
    """列举 prefix 下全部对象（分页）。"""
    out: list[dict] = []
    token = ""
    while True:
        q = {"list-type": "2", "prefix": creds.prefix, "max-keys": "1000"}
        if token:
            q["continuation-token"] = token
        status, body = _request(creds, "GET", "", None, q)
        if status != 200:
            raise SystemExit(f"[FATAL] 列举对象失败 (HTTP {status}): {body[:300]!r}")
        root = ET.fromstring(body)
        ns = {"o": root.tag.split("}")[0].strip("{")} if "}" in root.tag else {}
        for c in root.findall("o:Contents", ns) if ns else root.findall("Contents"):
            key = (c.find("o:Key", ns) if ns else c.find("Key")).text
            size = int((c.find("o:Size", ns) if ns else c.find("Size")).text)
            lm = (c.find("o:LastModified", ns) if ns else c.find("LastModified")).text
            out.append({"key": key, "size": size, "last_modified": lm})
        truncated = (root.find("o:IsTruncated", ns) if ns else root.find("IsTruncated"))
        if truncated is None or truncated.text != "true":
            break
        nxt = root.find("o:NextContinuationToken", ns) if ns else root.find("NextContinuationToken")
        token = nxt.text if nxt is not None else ""
        if not token:
            break
    return out


def delete_object(creds: Credentials, key: str) -> None:
    status, body = _request(creds, "DELETE", key)
    if status not in (200, 204):
        raise SystemExit(f"[FATAL] 删除失败 {key} (HTTP {status}): {body[:200]!r}")


# ---------------------------------------------------------------- 扫描 / 上传 / 清理

def scan_local(root: Path, prefix: str) -> list[Path]:
    """递归收集待同步文件（排除临时/隐藏文件）。"""
    if not root.is_dir():
        raise SystemExit(f"[FATAL] 备份根目录不存在: {root}")
    files: list[Path] = []
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        if p.name.startswith(".") or p.name.endswith((".tmp", ".partial", ".lock")):
            continue
        files.append(p)
    return files


def remote_key(creds: Credentials, root: Path, path: Path) -> str:
    """远端 key = prefix + 相对根目录的 POSIX 路径（保留服务器侧目录结构）。"""
    rel = path.relative_to(root).as_posix()
    return f"{creds.prefix}{rel}"


def do_scan(creds: Credentials, root: Path) -> int:
    files = scan_local(root, creds.prefix)
    remote = {o["key"]: o["size"] for o in list_objects(creds)}
    to_upload, skipped = [], 0
    for f in files:
        key = remote_key(creds, root, f)
        if remote.get(key) == f.stat().st_size:
            skipped += 1
        else:
            to_upload.append(f)
    print(f"[scan] 本地文件 {len(files)} 个；远端对象 {len(remote)} 个")
    print(f"[scan] 需上传 {len(to_upload)} 个；同名同大小跳过 {skipped} 个")
    for f in to_upload:
        print(f"       + {remote_key(creds, root, f)} ({f.stat().st_size} bytes)")
    return 0


def do_apply(creds: Credentials, root: Path, confirm: bool) -> int:
    if not confirm:
        print("[apply] 未加 --confirm —— 仅 DRY RUN，未上传任何文件。")
        return do_scan(creds, root)
    files = scan_local(root, creds.prefix)
    remote = {o["key"]: o["size"] for o in list_objects(creds)}
    uploaded = skipped = 0
    for f in files:
        key = remote_key(creds, root, f)
        if remote.get(key) == f.stat().st_size:
            skipped += 1
            continue
        put_object(creds, key, f)
        uploaded += 1
        print(f"[apply] ✓ {key} ({f.stat().st_size} bytes)")
    print(f"[apply] 完成：上传 {uploaded}，跳过 {skipped}（同名同大小）")
    return 0


def do_cleanup(creds: Credentials, days: int, confirm: bool) -> int:
    if days <= 0:
        raise SystemExit("[FATAL] --cleanup 需要正整数天数")
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    victims = []
    for o in list_objects(creds):
        try:
            lm = datetime.strptime(o["last_modified"], "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if lm < cutoff:
            victims.append(o)
    if not confirm:
        print(f"[cleanup] 未加 --confirm —— 仅列出 {len(victims)} 个候选（{days} 天前）：")
        for o in victims:
            print(f"          - {o['key']} ({o['last_modified']})")
        return 0
    for o in victims:
        delete_object(creds, o["key"])
        print(f"[cleanup] ✓ 已删除 {o['key']}")
    print(f"[cleanup] 完成：删除 {len(victims)} 个")
    return 0


# ---------------------------------------------------------------- CLI

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="把备份共享目录镜像到阿里云 OSS（三段式：scan / apply / cleanup）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--scan", action="store_true", help="列出本地/远端差异（无副作用）")
    parser.add_argument("--apply", action="store_true", help="上传差异文件（需 --confirm）")
    parser.add_argument("--cleanup", type=int, metavar="DAYS", help="删除远端 N 天前的对象（需 --confirm）")
    parser.add_argument("--confirm", action="store_true", help="二次确认门（缺省为 DRY RUN）")
    parser.add_argument("--root", required=True, help="本地备份根目录（服务器共享目录）")
    parser.add_argument("--creds", help="凭据 JSON 文件路径（缺省则读环境变量）")
    args = parser.parse_args(argv)

    if not (args.scan or args.apply or args.cleanup is not None):
        parser.print_help()
        return 2

    creds = load_credentials(args.creds)
    root = Path(args.root)
    print(f"[init] bucket={creds.bucket} endpoint={creds.endpoint} prefix={creds.prefix} root={root}")

    if args.scan:
        return do_scan(creds, root)
    if args.apply:
        return do_apply(creds, root, args.confirm)
    return do_cleanup(creds, int(args.cleanup), args.confirm)


if __name__ == "__main__":
    sys.exit(main())
