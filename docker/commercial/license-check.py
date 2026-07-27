"""
License 服务端校验 (Phase 8 起步版本)

商业化镜像启动前必跑, 离线 7 天宽限.
- 在线: 调 MICROBUBBLE_LICENSE_SERVER 校验 license_key
- 离线: 检查本地缓存 (grace_days 7 天), 过期则启动失败
- 启动失败: 退出码 1, 容器退出
"""
import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path


CACHE_FILE = Path("/app/data/license_cache.json")
LICENSE_SERVER = os.getenv("MICROBUBBLE_LICENSE_SERVER", "https://license.microbubble.cloud/v1")
LICENSE_KEY = os.getenv("MICROBUBBLE_LICENSE_KEY", "")
GRACE_DAYS = int(os.getenv("MICROBUBBLE_LICENSE_GRACE_DAYS", "7"))


def _load_cache() -> dict:
    """读取本地 license 缓存."""
    if not CACHE_FILE.exists():
        return {}
    try:
        with open(CACHE_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def _save_cache(data: dict) -> None:
    """写入本地 license 缓存."""
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, "w") as f:
        json.dump(data, f, indent=2)


def _check_online() -> dict | None:
    """在线校验 License, 失败返回 None."""
    try:
        import urllib.request
        req = urllib.request.Request(
            f"{LICENSE_SERVER}/verify",
            data=json.dumps({"license_key": LICENSE_KEY}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"[license] online check failed: {e}", file=sys.stderr)
        return None


def _check_offline() -> tuple[bool, str]:
    """离线宽限校验, 返回 (是否通过, 状态描述)."""
    cache = _load_cache()
    if not cache:
        return False, "no cached license"

    last_verified_at = cache.get("last_verified_at")
    if not last_verified_at:
        return False, "no last_verified_at"

    try:
        last_dt = datetime.fromisoformat(last_verified_at)
    except Exception:
        return False, "invalid cache format"

    now = datetime.now(timezone.utc)
    age = now - last_dt
    if age > timedelta(days=GRACE_DAYS):
        return False, f"grace expired ({age.days} days > {GRACE_DAYS})"

    return True, f"offline pass ({age.days} days within grace)"


def main() -> int:
    if not LICENSE_KEY:
        print("[license] FATAL: MICROBUBBLE_LICENSE_KEY not set", file=sys.stderr)
        return 1

    # 1. 在线校验
    result = _check_online()
    if result:
        if result.get("valid"):
            _save_cache({
                "license_key": LICENSE_KEY[:8] + "***",
                "last_verified_at": datetime.now(timezone.utc).isoformat(),
                "tier": result.get("tier", "commercial"),
                "expires_at": result.get("expires_at"),
            })
            print(f"[license] OK online, tier={result.get('tier')}")
            return 0
        else:
            print(f"[license] online rejected: {result.get('reason', 'unknown')}", file=sys.stderr)

    # 2. 离线宽限
    ok, msg = _check_offline()
    if ok:
        print(f"[license] OK offline grace: {msg}")
        return 0

    # 3. 失败
    print(f"[license] FATAL: {msg}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
