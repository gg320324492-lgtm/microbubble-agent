#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把异地备份口令存进 Bitwarden —— 口令全程不打印、不作为命令行参数出现。

设计要点（为什么不直接用 shell + jq）：
  · 口令**只**通过 stdin 从文件读进进程，绝不进 argv（argv 会被 shell 历史、
    进程列表、审计日志看到），也绝不 print 到终端（终端会进滚动缓冲/日志）。
  · 不落临时文件：Bitwarden CLI 的 create item 只收 stdin。
  · 幂等：同名条目已存在就 update，不会每次跑都新建一条。

用法（在你自己的终端里跑，会提示输入主密码）：
    python scripts/backup/store_passphrase_in_bitwarden.py

依赖：Bitwarden CLI（bw）。本脚本不会自行安装。
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PASSPHRASE_FILE = REPO_ROOT / ".secrets" / "offsite_backup.passphrase"

ITEM_NAME = "小气工作台-异地备份口令"

NOTES = """小气科研工作台（E:\\microbubble-agent）异地容灾的加解密口令。

【丢了会怎样】
阿里云 OSS 桶 mnb-workbench-backup 上的约 410 MB 备份将永久不可读
（AES-256-GCM 无后门，轮换口令也救不了旧密文）。

【怎么用】
恢复步骤见仓库 docs/disaster-recovery-runbook.md（只含步骤不含密钥）。
本机口令文件：.secrets/offsite_backup.passphrase

【为什么脚本不读 .env 也不读环境变量】
.env 备份本身也会被加密后传到同一个 OSS；若口令能从那里读到，
就等于给同一个秘密开了三个明文出口。

【重要】
新建/更换 Bitwarden 主密码后，请重新同步并确认本条目可解密。
本条目已加密存储，但 Bitwarden 是零知识架构 —— 主密码丢失没有任何人能找回。
"""


def die(msg: str, code: int = 1) -> None:
    print(f"[FATAL] {msg}", file=sys.stderr)
    sys.exit(code)


def run_bw(args: list[str], stdin_data: str | None = None) -> str:
    """跑 bw，返回 stdout。bw 不在 PATH 时给出明确指引。"""
    if shutil.which("bw") is None:
        die(
            "找不到 bw（Bitwarden CLI）。\n"
            "        安装: winget install --id Bitwarden.CLI --source winget\n"
            "        装完需重开终端让 PATH 生效。"
        )
    proc = subprocess.run(
        ["bw"] + args,
        input=stdin_data,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if proc.returncode != 0:
        die(f"bw {' '.join(args)} 失败 (rc={proc.returncode}):\n{proc.stderr.strip()}")
    return proc.stdout


def main() -> int:
    if not PASSPHRASE_FILE.is_file():
        die(
            f"口令文件不存在: {PASSPHRASE_FILE}\n"
            "        先自行生成（脚本不代劳、不打印口令）：\n"
            "        python -c \"import secrets,pathlib;p=pathlib.Path(r'%s');"
            "p.parent.mkdir(parents=True,exist_ok=True);"
            "p.write_text(secrets.token_urlsafe(48),encoding='utf-8')\"" % PASSPHRASE_FILE
        )

    # 只读进内存；不 print、不写临时文件
    passphrase = PASSPHRASE_FILE.read_bytes()
    if passphrase.startswith(b"\xef\xbb\xbf"):
        passphrase = passphrase[3:]
    passphrase = passphrase.rstrip(b"\r\n").decode("utf-8")
    if not passphrase.strip():
        die("口令文件为空或纯空白")

    status = json.loads(run_bw(["status"]))
    if status.get("status") == "unauthenticated":
        die("bw 未登录，先执行: bw login")
    if status.get("status") == "locked":
        die("bw 库已锁定，先执行: bw unlock  （需要你的主密码）")

    # 先看有没有同名条目 -> 幂等
    items = json.loads(run_bw(["list", "items"]) or "[]")
    existing = next((i for i in items if i.get("name") == ITEM_NAME), None)

    payload = {
        "type": 1,
        "name": ITEM_NAME,
        "notes": passphrase + "\n\n" + NOTES,
        "fields": [
            {"name": "bucket", "value": "mnb-workbench-backup", "type": 0},
            {"name": "prefix", "value": "offsite-backup/microbubble/", "type": 0},
            {"name": "runbook", "value": "docs/disaster-recovery-runbook.md", "type": 0},
            {"name": "local_passphrase_file", "value": ".secrets/offsite_backup.passphrase", "type": 0},
        ],
    }
    blob = json.dumps(payload, ensure_ascii=False)

    if existing:
        payload["id"] = existing["id"]
        blob = json.dumps(payload, ensure_ascii=False)
        run_bw(["edit", "item", existing["id"]], stdin_data=blob)
        print(f"[OK] 已更新既有条目: {ITEM_NAME}")
    else:
        run_bw(["create", "item"], stdin_data=blob)
        print(f"[OK] 已新建条目: {ITEM_NAME}")

    # 验证：回读并比对长度（**不打印内容**）
    items2 = json.loads(run_bw(["list", "items"]) or "[]")
    saved = next((i for i in items2 if i.get("name") == ITEM_NAME), None)
    if not saved:
        die("条目创建/更新后回读失败")
    got = saved.get("notes", "")
    ok = got.startswith(passphrase)
    print(f"     回读校验: 长度 {len(got)} | 口令前缀匹配 {ok}")
    if not ok:
        die("回读内容与本地口令不一致，请人工核对")
    print("     （全程未打印口令内容）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
