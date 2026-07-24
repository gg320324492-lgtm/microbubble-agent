#!/usr/bin/env python3
"""PR10 collaboration deployment smoke check; dry-run unless --apply."""
from __future__ import annotations
import argparse, asyncio, importlib, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def check_table() -> bool:
    try:
        from app.models.drive import DriveDocument  # type: ignore
        return DriveDocument is not None
    except Exception as exc:
        print(f"[WARN] drive_documents model import: {exc}")
        return False

def check_service() -> bool:
    try:
        mod = importlib.import_module("app.services.drive_collab_service")
        required = ("create_document", "get_document", "apply_update", "get_snapshot", "flush_document", "delete_document")
        missing = [name for name in required if not callable(getattr(mod, name, None))]
        if missing:
            print(f"[FAIL] missing service methods: {', '.join(missing)}")
            return False
        print("[PASS] drive_collab_service six methods available")
        return True
    except Exception as exc:
        print(f"[WARN] service import: {exc}")
        return False

def check_route() -> bool:
    candidates = ("app.api.drive", "app.api.routes.drive", "app.api.v1.drive")
    needle = "/collab"
    for name in candidates:
        try:
            mod = importlib.import_module(name)
            text = Path(getattr(mod, "__file__", "")).read_text(encoding="utf-8")
            if needle in text:
                print(f"[PASS] collab route registered in {name}")
                return True
        except Exception:
            continue
    for path in ROOT.glob("app/api/**/*.py"):
        if needle in path.read_text(encoding="utf-8"):
            print(f"[PASS] collab route found in {path}")
            return True
    print("[WARN] collab route not found by static check")
    return False

async def apply_ws(url: str, token: str | None) -> int:
    try:
        import websockets
    except ImportError:
        print("[FAIL] --apply requires: python -m pip install websockets")
        return 2
    headers = {"Authorization": f"Bearer {token}"} if token else None
    try:
        async with websockets.connect(url, additional_headers=headers) as ws:
            await ws.send(json.dumps({"type": "ping", "dry_run": False}))
            print(f"[PASS] WS connected and test frame sent: {url}")
            return 0
    except Exception as exc:
        print(f"[FAIL] WS connection: {exc}")
        return 1

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="ws://localhost:8000")
    parser.add_argument("--file-id", default="1")
    parser.add_argument("--token")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print("PR10 collab verification (dry-run=%s)" % (not args.apply))
    results = [check_table(), check_service(), check_route()]
    if args.apply:
        base = args.base_url.replace("https://", "wss://").replace("http://", "ws://").rstrip("/")
        results.append(asyncio.run(apply_ws(f"{base}/api/v1/drive/files/{args.file_id}/collab", args.token)) == 0)
    else:
        print("[INFO] no WS frame sent; use --apply during a maintenance window")
    return 0 if all(results) else 1

if __name__ == "__main__":
    sys.exit(main())
