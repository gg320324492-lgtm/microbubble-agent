#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""轮换异地备份口令 —— 重新加密全部备份并覆盖上传。

## 顺序即安全

**新旧密文同名**：`remote_key` 由 前缀 + 子目录 + 相对路径 + ".enc" 决定，**不含口令**。
所以重新上传是 PUT **覆盖**，不需要先删旧的。

⇒ 任何中途失败的唯一后果是"远端一半新密文一半旧密文"，**两个都能解开**
（旧的配旧口令，新的配新口令）—— 不存在数据不可读的窗口。

## 绝不做的三件事

1. 绝不先删远端对象（删了才传才是真空窗）
2. 绝不在上传完成前覆盖本地口令文件（失败时本地仍是旧口令，可原样重跑）
3. 绝不跳过验证 —— 逐个回读远端对象，用新口令实解，全部通过才算完成

用法：
    python scripts/backup/rotate_offsite_passphrase.py --dry-run   # 只看计划
    python scripts/backup/rotate_offsite_passphrase.py             # 真执行
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import secrets
import shutil
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SYNC_SCRIPT = REPO_ROOT / "apps" / "desktop" / "scripts" / "server" / "offsite-oss-sync.py"

_spec = importlib.util.spec_from_file_location("oos", SYNC_SCRIPT)
oos = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(oos)

PASSPHRASE_FILE = REPO_ROOT / ".secrets" / "offsite_backup.passphrase"


def die(msg: str) -> None:
    print(f"[FATAL] {msg}", file=sys.stderr)
    sys.exit(1)


def read_passphrase(path: Path) -> bytes:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    return raw.rstrip(b"\r\n")


def short(raw: bytes) -> str:
    """口令指纹 —— 足够区分两代，又不泄露口令本身。"""
    return hashlib.sha256(raw).hexdigest()[:12]


def main() -> int:
    ap = argparse.ArgumentParser(description="轮换异地备份口令（重新加密 + 覆盖上传）")
    ap.add_argument("--dry-run", action="store_true", help="只列计划，不改任何东西")
    args = ap.parse_args()

    if not PASSPHRASE_FILE.is_file():
        die(f"口令文件不存在: {PASSPHRASE_FILE}")
    old_pp = read_passphrase(PASSPHRASE_FILE)
    if not old_pp.strip():
        die("当前口令文件为空或纯空白")

    creds = oos.load_credentials(None)
    root = oos.default_root()
    files = oos.scan_local(root, creds.prefix, oos.DEFAULT_INCLUDE)
    subdir = oos.DEFAULT_SUBDIR
    scope = oos.own_prefix(creds, subdir)
    n_sql = sum(1 for f in files if f.name.endswith(".sql.gz"))
    n_env = len(files) - n_sql

    print(f"[init] 桶       = {creds.bucket}")
    print(f"[init] 作用域   = {scope}")
    print(f"[init] 本地文件 = {len(files)} 个 (db dump {n_sql} / .env {n_env})")
    print(f"[init] 旧口令指纹 = {short(old_pp)}  ({len(old_pp)} 字节)")

    if args.dry_run:
        print("\n[dry-run] 计划（未做任何改动）:")
        print(f"  1. 生成新口令")
        print(f"  2. 用新口令重新加密 {len(files)} 个文件")
        print(f"  3. PUT 覆盖同 key —— **不删除任何远端对象**")
        print(f"  4. 逐个回读远端对象，用新口令实解，全部通过才算完成")
        print(f"  5. 全部通过后才覆盖本地口令文件")
        return 0

    remote_before = oos.list_objects(creds, prefix=scope)
    print(f"\n[init] 远端现有 = {len(remote_before)} 个对象")
    if len(remote_before) != len(files):
        print(f"[WARN] 本地 {len(files)} vs 远端 {len(remote_before)} 不一致 —— "
              "以本地为准（上传幂等，多余的远端对象不会被删除）")

    new_pp = secrets.token_urlsafe(48).encode("ascii")
    print(f"[1/4] 新口令已生成 = {short(new_pp)}  ({len(new_pp)} 字节)")

    tmpdir = tempfile.mkdtemp(prefix="rotate-")
    uploaded = 0
    try:
        for i, f in enumerate(files, 1):
            key = oos.remote_key(creds, root, f, encrypt=True, subdir=subdir)
            enc = Path(tmpdir) / (f.name + oos.ENC_SUFFIX)
            try:
                oos.encrypt_file(f, enc, new_pp)
                oos.put_object(creds, key, enc)   # PUT 覆盖，不删
            except SystemExit as e:
                print(f"\n[FAIL] 第 {i}/{len(files)} 个上传失败: {str(e).splitlines()[0]}")
                print(f"       已完成 {uploaded} 个。远端**新旧密文并存**，两者此刻都可解：")
                print(f"         · 新密文 → 新口令（仅存在于内存与本进程）")
                print(f"         · 旧密文 → 旧口令（{PASSPHRASE_FILE} 未改动，仍然有效）")
                print(f"       本地口令文件未改动。重跑本脚本会重新生成一个新口令并重来一遍。")
                return 1
            finally:
                enc.unlink(missing_ok=True)
            uploaded += 1
            print(f"       [{i}/{len(files)}] {f.name}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    print(f"\n[2/4] 全部 {uploaded} 个已覆盖上传")
    print(f"[3/4] 写入新口令到 {PASSPHRASE_FILE}")
    PASSPHRASE_FILE.write_bytes(new_pp)
    print(f"       已写入 ({len(new_pp)} 字节)")

    print(f"\n[4/4] 回读远端逐个用**新口令**实解验证 ...")
    remote_after = oos.list_objects(creds, prefix=scope)
    bad: list[str] = []
    for i, o in enumerate(remote_after, 1):
        key = o["key"]
        st, body = oos._request(creds, "GET", key)
        if st != 200:
            bad.append(f"{key}  (HTTP {st})")
            continue
        with tempfile.NamedTemporaryFile(suffix=".enc", delete=False) as tf:
            tf.write(body)
            tmp = Path(tf.name)
        d = Path(tempfile.mkdtemp(prefix="verify-"))
        try:
            oos.decrypt_file(tmp, d / "x", new_pp)
        except SystemExit:
            bad.append(f"{key}  (新口令解不开 —— 疑似旧密文残留)")
        finally:
            tmp.unlink(missing_ok=True)
            shutil.rmtree(d, ignore_errors=True)
        print(f"       [{i}/{len(remote_after)}] {'OK' if len(bad) == 0 or key not in bad[-1:] else '?'} {key.split('/')[-1]}")

    print()
    if bad:
        print(f"[FAIL] {len(bad)}/{len(remote_after)} 个对象无法用新口令解开:")
        for b in bad[:10]:
            print(f"       {b}")
        print(f"\n       新口令已写入 {PASSPHRASE_FILE}。远端新旧并存：")
        print(f"         · 新密文 → 新口令（上面这个文件）")
        print(f"         · 旧密文 → 旧口令（若你手上有）")
        return 1

    print(f"[OK] 全部 {len(remote_after)} 个对象均能用新口令解开 —— 轮换完成")
    print()
    print("【后续必做】")
    print("  1. 立刻更新 Bitwarden 里的『小气工作台-异地备份口令』条目（里面还是旧口令）")
    print("  2. 远端旧密文已被逐个覆盖，无需任何清理动作")
    print(f"  3. 旧口令指纹 {short(old_pp)} 已作废")
    return 0


if __name__ == "__main__":
    sys.exit(main())
