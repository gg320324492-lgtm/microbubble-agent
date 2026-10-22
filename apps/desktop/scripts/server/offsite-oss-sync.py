#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""异地备份同步 —— 把本地备份目录加密后镜像到阿里云 OSS。

设计约束（对齐工单与父项目复盘教训）：
  · **OSS 签名是 V1（HMAC-SHA1），不是 SigV4** —— 本文件早年的头注释自称 "SigV4" 是错的，
    会把下一个接手的人带偏。2026-09-21 实测：阿里云 OSS **原生 API** 拒绝 AWS SigV4
    头格式，实现已回退到 V1（与项目 oss-sig.ts / CI 上传脚本同款）。
    注意这与 `scripts/backup_to_aliyun_oss.py` 用的 S3 兼容端点 + SigV4 是**两套并存**
    的东西，不要混为一谈（该脚本本单未改动）。
  · 另加服务端加密 SSE（x-oss-server-side-encryption: AES256）作第二道
  · 三段式 CLI：--scan（只读）/ --apply --confirm（上传）/ --cleanup N（清理 N 天前）
  · 幂等：远端同名且同大小 → 跳过，不重复上传（加密时比对的是**密文**长度，
    它是明文长度的确定函数，故无需重新加密即可判定）
  · **禁止默认凭证回落**：AK/SK/桶/endpoint 必须由环境变量或显式凭据文件提供，
    缺失即报错退出。旧版 DEFAULT_BUCKET 指向 `mnb-workbench-releases` —— 该桶是
    electron-updater 的**匿名可读**发布源，备份落进去等于公开。已移除全部桶默认值
  · **上传前先客户端加密**（AES-256-GCM，PBKDF2-HMAC-SHA256 派生密钥，每文件独立 salt）：
    DB dump 装知识库与会议转写、`.env.*.bak` 装库密码 / JWT SECRET_KEY / MinIO 密钥。
    **加密没有开关** —— 既然连"桶是私有的"都不能当护栏，就更不能当"可以关加密"。
    代价：`cryptography` 成为必需依赖（lazy import，只在真加密时载入）
  · **口令绝不入 git**：只从 `--passphrase-file` 指定的独立文件读，不读 .env、
    不读环境变量兜底、不内置。文件缺失 / 空 / 纯空白 → 立即退出，绝不降级为明文上传
  · 失败必须可感知：任何一步非零退出并打印可读原因，供计划任务日志捕获

用法：
  # 1) 只看差异（无副作用）
  python offsite-oss-sync.py --scan --root D:\\share\\backups
  # 2) 真正上传（需二次确认）—— 加密 + 远端保留 7 天
  python offsite-oss-sync.py --apply --confirm --root E:\\microbubble-agent\\backups \
      --passphrase-file E:\\microbubble-agent\\.secrets\\offsite_backup.passphrase
  # 3) 单独清理远端 N 天前的对象（同样需 --confirm）
  python offsite-oss-sync.py --cleanup 30 --confirm
  # 4) 解密（灾备取回 / 验证往返）
  python offsite-oss-sync.py --decrypt-into ./restored \
      --passphrase-file .secrets/offsite_backup.passphrase ./restored/x.sql.gz.enc

凭据（二选一，均不回显）：
  · 环境变量：OSS_ACCESS_KEY_ID / OSS_ACCESS_KEY_SECRET
  · 凭据文件：--creds <json>，字段 accessKeyId / accessKeySecret（+ 可选 bucket/endpoint/prefix）

生成口令文件（由使用者自己执行一次，脚本不代劳、不打印口令）：
  python -c "import secrets,pathlib;p=pathlib.Path('.secrets/offsite_backup.passphrase');\
p.parent.mkdir(parents=True,exist_ok=True);p.write_text(secrets.token_urlsafe(48),encoding='utf-8')"
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import shutil
import struct
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

ALGO = "OSS4-HMAC-SHA256"
SERVICE = "oss"
# region 不设默认值：从 endpoint 反解（oss-cn-beijing → cn-beijing），反解不出就报错。
# 桶 / endpoint 同样**没有默认值** —— 见 load_credentials 的 fail-loud 说明。
DEFAULT_PREFIX = "offsite-backup/"
# ⚠️ 历史坑：`mnb-workbench-releases` 是 electron-updater 的公开发布源，**匿名可读**
# （2026-10-12 匿名 GET 一个不存在的 key → NoSuchKey 而非 AccessDenied，即证明可读）。
# 备份绝不可用该桶。本机环境变量指向的是私有桶 `mnb-workbench-backup`（匿名探测 AccessDenied）。
SSE_HEADER = "x-oss-server-side-encryption"
SSE_VALUE = "AES256"

# 网络重试（2026-10-12 首次真实上传实测定标：82MB dump 传 39 秒即超时中断）
UPLOAD_RETRIES = 5
UPLOAD_TIMEOUT_S = 300   # 大 dump 上行慢，120s 偏紧
UPLOAD_BACKOFF_BASE_S = 2 # 2/4/8/16s 指数退避，总计约 30s

# ---------------------------------------------------------------- 口令

# 口令**只**从一个独立于 .env、不在 git 的文件读。三条硬约束：
#   ① 文件不存在 → 退出；② 空 / 纯空白 → 退出；③ 绝不回落到空口令或明文直传。
# 不读 .env、不读 OSS_* 环境变量、不内置 —— 这些位置都会随备份一起被复制到 OSS。
DEFAULT_PASSPHRASE_FILE = ".secrets/offsite_backup.passphrase"

# 临时工作目录：放在项目目录的 data\tmp 下，**不要**用 tempfile 的默认位置。
# 2026-10-22：默认临时目录在 C 盘的 %TEMP%，而这里的密文峰值可达 82 MB
# （单个 DB dump 的 AES-256-GCM 密文）。data/ 已被 .gitignore 第 29 行覆盖，不会进 git。
_REPO_ROOT = Path(__file__).resolve().parents[4]  # server -> scripts -> desktop -> apps -> <repo>
_TMP_ROOT = _REPO_ROOT / "data" / "tmp"


class PassphraseMissing(SystemExit):
    """口令不可用。显式子类，便于测试断言且仍以 SystemExit 语义终止进程。"""


def load_passphrase(path: str | Path) -> bytes:
    """读口令文件。fail-loud：任何"拿不到可用口令"的情形都抛 SystemExit，不降级。"""
    p = Path(path)
    if not p.is_file():
        raise PassphraseMissing(
            f"[FATAL] 口令文件不存在: {p}\n"
            "        加密是默认开启的，且**没有**任何降级路径（绝不以明文上传）。\n"
            "        请先自行生成（脚本不会代劳、不会打印口令）：\n"
            "        python -c \"import secrets,pathlib;p=pathlib.Path(r'%s');"
            "p.parent.mkdir(parents=True,exist_ok=True);"
            "p.write_text(secrets.token_urlsafe(48),encoding='utf-8')\"" % p
        )
    try:
        raw = p.read_bytes()
    except OSError as e:  # 权限 / 占用
        raise PassphraseMissing(f"[FATAL] 口令文件无法读取: {p} ({e})")

    # 容忍 UTF-8 BOM 与结尾换行（Windows 编辑器很爱加），但**不**改动其它字符
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    if raw.endswith(b"\r\n"):
        raw = raw[:-2]
    elif raw.endswith(b"\n") or raw.endswith(b"\r"):
        raw = raw[:-1]

    if not raw.strip():
        raise PassphraseMissing(
            f"[FATAL] 口令文件为空或纯空白: {p}\n"
            "        拒绝以空口令继续 —— 那等同于没有加密。"
        )
    if len(raw) < 16:
        print(
            f"[WARN] 口令仅 {len(raw)} 字节，短口令在 PBKDF2 下仍安全但抗爆破更弱，建议 >= 32 字节。",
            file=sys.stderr,
        )
    return raw


# ---------------------------------------------------------------- 加密信封
# ⚠️ **必须定义在使用它的函数之前**（2026-10-12 修）。
# `encrypted_size(plain_size, chunk_bytes=ENC_CHUNK_BYTES)` 把 ENC_CHUNK_BYTES
# 用作**默认参数值** —— 默认参数在函数 `def` 执行时立即求值，不是调用时才查。
# 常量块原先排在函数段之后 ⇒ `import offsite-oss-sync` 直接 NameError 崩掉。
# 注意 py_compile **查不出**这个错（语法完全合法），只有真 import 才暴露（类 20.220）。
#
# 自描述定长头（57 字节），解密只需「密文 + 口令」，不需要任何外部参数：
#   0  magic      7B  b"MNBENC1"
#   7  version    1B  u8
#   8  kdf_id     1B  u8  (1 = PBKDF2-HMAC-SHA256)
#   9  iterations 4B  u32 BE
#  13  chunk      4B  u32 BE
#  17  plain_len  8B  u64 BE
#  25  chunks     4B  u32 BE
#  29  salt      16B
#  45  nonce     12B
ENC_MAGIC = b"MNBENC1"
ENC_VERSION = 1
ENC_KDF_PBKDF2 = 1
ENC_HEADER = struct.Struct(">7sBBI IQI16s12s")  # 57 bytes（空白被 struct 忽略）
ENC_SALT_LEN = 16
ENC_NONCE_LEN = 12
ENC_TAG_LEN = 16
ENC_CHUNK_BYTES = 8 * 1024 * 1024  # 8 MiB —— DB dump 实测 40~82MB，禁止整文件进内存
PBKDF2_ITERS = 600_000  # OWASP 2023 对 PBKDF2-HMAC-SHA256 的推荐值
DERIVED_KEY_LEN = 32  # AES-256
ENC_SUFFIX = ".enc"

# AAD 前缀 = 头的前 29 字节（magic..chunks），绑住 salt/plain_len/chunks 后再拼 chunk 序号，
# 于是跨文件拼接、块重排、尾部截断三种攻击都会被 GCM 标签校验挡住。
ENC_AAD_PREFIX = struct.Struct(">7sBBI IQI")


# ---------------------------------------------------------------- 加密（AES-256-GCM, 分块）

def _crypto():
    """lazy import：只有真要加密时才需要 cryptography，保持默认路径零第三方依赖。"""
    try:
        from cryptography.exceptions import InvalidTag
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography.hazmat.primitives.kdf.hkdf import HKDF
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    except ImportError as e:  # pragma: no cover - 取决于运行环境
        raise SystemExit(
            f"[FATAL] 需要 cryptography 才能加密: {e}\n"
            "        pip install cryptography   （本仓已通过 python-jose[cryptography] 间接依赖）"
        )
    return AESGCM, HKDF, hashes, PBKDF2HMAC, InvalidTag


def _master_key(passphrase: bytes, salt: bytes, iterations: int):
    AESGCM, HKDF, hashes, PBKDF2HMAC, _ = _crypto()
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=DERIVED_KEY_LEN,
        salt=salt,
        iterations=iterations,
    )
    return kdf.derive(passphrase)


def _chunk_key(master: bytes, salt: bytes, index: int) -> bytes:
    """每个分块一把独立子密钥（HKDF-SHA256，info 含块序号）。"""
    _, HKDF, hashes, _, _ = _crypto()
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=DERIVED_KEY_LEN,
        salt=salt,
        info=b"MNBENC1-chunk" + struct.pack(">Q", index),
    )
    return hkdf.derive(master)


def _chunk_nonce(base_nonce: bytes, index: int) -> bytes:
    """nonce_i = base_nonce XOR i（12 字节补零）。base_nonce 每文件随机 ⇒ 不跨文件重用。"""
    return bytes(a ^ b for a, b in zip(base_nonce, struct.pack(">Q", index).rjust(12, b"\x00")))


def encrypted_size(plain_size: int, chunk_bytes: int = ENC_CHUNK_BYTES) -> int:
    """给定明文长度即可算出密文长度 —— 幂等比对不需要真加密一遍。"""
    chunks = max(1, -(-plain_size // chunk_bytes))
    return ENC_HEADER.size + plain_size + chunks * ENC_TAG_LEN


def encrypt_file(src: Path, dst: Path, passphrase: bytes) -> tuple[int, str]:
    """流式加密到 dst。返回 (明文字节数, 十六进制 salt)。

    分块而非整文件进内存：DB dump 实测 40~82MB，且会继续涨；每块 8MiB 恒定占用。
    """
    AESGCM, _, _, _, _ = _crypto()
    plain_len = src.stat().st_size
    chunk_bytes = ENC_CHUNK_BYTES
    chunks = max(1, -(-plain_len // chunk_bytes)) if plain_len else 1

    salt = os.urandom(ENC_SALT_LEN)
    nonce = os.urandom(ENC_NONCE_LEN)
    aad_prefix = ENC_AAD_PREFIX.pack(
        ENC_MAGIC, ENC_VERSION, ENC_KDF_PBKDF2, PBKDF2_ITERS,
        chunk_bytes, plain_len, chunks,
    )
    header = ENC_HEADER.pack(
        ENC_MAGIC, ENC_VERSION, ENC_KDF_PBKDF2, PBKDF2_ITERS,
        chunk_bytes, plain_len, chunks, salt, nonce,
    )
    master = _master_key(passphrase, salt, PBKDF2_ITERS)

    written = 0
    with src.open("rb") as fin, dst.open("wb") as fout:
        fout.write(header)
        for index in range(chunks):
            block = fin.read(chunk_bytes)
            aad = aad_prefix + struct.pack(">Q", index)
            ct = AESGCM(_chunk_key(master, salt, index)).encrypt(
                _chunk_nonce(nonce, index), block, aad
            )
            fout.write(ct)
            written += len(block)
    if written != plain_len:  # pragma: no cover - 源文件在加密期间被改动
        dst.unlink(missing_ok=True)
        raise SystemExit(f"[FATAL] 加密期间源文件长度变化（{plain_len} → {written}），已丢弃密文")
    return plain_len, salt.hex()


def read_envelope_header(path: Path) -> dict:
    with path.open("rb") as fh:
        raw = fh.read(ENC_HEADER.size)
    if len(raw) < ENC_HEADER.size:
        raise SystemExit(f"[FATAL] 文件过短，不是 MNBENC1 密文: {path}")
    magic, version, kdf_id, iters, chunk, plain_len, chunks, salt, nonce = ENC_HEADER.unpack(raw)
    if magic != ENC_MAGIC:
        raise SystemExit(f"[FATAL] 不是 MNBENC1 密文（magic={magic!r}）: {path}")
    if version != ENC_VERSION:
        raise SystemExit(f"[FATAL] 不支持的信封版本 {version}，本脚本只认 v{ENC_VERSION}: {path}")
    if kdf_id != ENC_KDF_PBKDF2:
        raise SystemExit(f"[FATAL] 不支持的 KDF id {kdf_id}，本脚本只认 PBKDF2-HMAC-SHA256: {path}")
    return {
        "iterations": iters, "chunk_bytes": chunk, "plain_len": plain_len,
        "chunks": chunks, "salt": salt, "nonce": nonce,
    }


def last_chunk_plain_len(hdr: dict) -> int:
    """末块的**明文**长度。

    末块通常是"短块"（plain_len 不是 chunk_bytes 的整数倍）—— 加密侧 `fin.read()`
    在 EOF 处自然返回短块，20,000,005 字节 / 8MiB = 2 满块 + 3,222,789 短块。
    解密侧必须按同样规则算出期望长度，否则会把正常的短末块误判成"密文被截断"
    （2026-10-12 实测踩到：任何非 chunk_bytes 整数倍的文件都解不开，而 DB dump
    实测 40~82MB，**必然**落在这个区间）。
    """
    if hdr["chunks"] <= 0:
        return 0
    return hdr["plain_len"] - (hdr["chunks"] - 1) * hdr["chunk_bytes"]


def _discard_partial(dst: Path) -> None:
    """丢弃解密到一半的半成品文件。

    ⚠️ 必须**绝不允许抛异常**（2026-10-12 修）。若清理失败就抛，
    "口令错误"这条本该清晰的 `[FATAL]` 会被无关的 traceback 掩盖，操作者看到的
    是崩溃而不是原因。实测于 Windows 上调用点位于 `with dst.open("wb")` 块内部、
    文件句柄仍开着时，`unlink` 直接抛 `PermissionError [WinError 32]`。
    ⇒ 清理只提示、不中断：错误的**原因**优先级高于"删掉临时文件"。
    """
    try:
        dst.unlink(missing_ok=True)
    except OSError as e:
        print(f"[WARN] 半成品文件未能删除（稍后请手动清理）: {dst} ({e})", file=sys.stderr)


def decrypt_file(src: Path, dst: Path, passphrase: bytes) -> int:
    """解密到 dst，返回明文字节数。口令错 / 被篡改 / 截断 全部抛 SystemExit。

    失败时**不留明文残留**：把失败原因暂存，等 with 块（文件句柄）关闭后再删。
    在块内直接删在 Windows 上必然失败（句柄未关），半成品会留在磁盘上 ——
    而错口令场景下那文件里已是**已解出的明文**，恰恰是最不该留下的东西。
    """
    AESGCM, _, _, _, InvalidTag = _crypto()
    hdr = read_envelope_header(src)
    aad_prefix = ENC_AAD_PREFIX.pack(
        ENC_MAGIC, ENC_VERSION, ENC_KDF_PBKDF2, hdr["iterations"],
        hdr["chunk_bytes"], hdr["plain_len"], hdr["chunks"],
    )
    master = _master_key(passphrase, hdr["salt"], hdr["iterations"])

    written = 0
    failure: str | None = None
    with src.open("rb") as fin, dst.open("wb") as fout:
        fin.read(ENC_HEADER.size)  # 头已单独解析
        for index in range(hdr["chunks"]):
            is_last = index == hdr["chunks"] - 1
            # 末块读"剩余全部"，这样**尾部被追加数据**也会被长度校验抓住
            expect = (
                last_chunk_plain_len(hdr) + ENC_TAG_LEN
                if is_last else hdr["chunk_bytes"] + ENC_TAG_LEN
            )
            block = fin.read() if is_last else fin.read(expect)
            if len(block) != expect:
                failure = (
                    f"[FATAL] 密文第 {index}/{hdr['chunks']} 块长度不符"
                    f"（期望 {expect}，实得 {len(block)}）—— 被截断或尾部被追加: {src}"
                )
                break
            ct, tag = block[:-ENC_TAG_LEN], block[-ENC_TAG_LEN:]
            aad = aad_prefix + struct.pack(">Q", index)
            try:
                pt = AESGCM(_chunk_key(master, hdr["salt"], index)).decrypt(
                    _chunk_nonce(hdr["nonce"], index), ct + tag, aad
                )
            except InvalidTag:
                # InvalidTag 是"口令错"与"密文被改"共同的表现，无法区分 —— 如实说明
                failure = (
                    f"[FATAL] 第 {index} 块 GCM 校验失败："
                    f"口令错误，或密文被篡改/块序被打乱。\n        文件: {src}"
                )
                break
            fout.write(pt)
            written += len(pt)

    if failure:
        _discard_partial(dst)  # 句柄已关，此刻删除才可能成功
        raise SystemExit(failure)
    if written != hdr["plain_len"]:  # pragma: no cover - 头与体不自洽
        _discard_partial(dst)
        raise SystemExit(
            f"[FATAL] 明文长度对账失败（头称 {hdr['plain_len']}，实得 {written}）: {src}"
        )
    return written


# ---------------------------------------------------------------- 备份范围收敛
# 默认只同步**本地备份任务产出的两类文件**，不再 rglob 整个目录：
#   microbubble_*.sql.gz  → backup_db.sh 的 pg_dump 产物（知识库 + 会议转写）
#   .env.*.bak            → 同一脚本备份的 .env（库密码 / JWT SECRET_KEY / MinIO 密钥）
# 注意 .env.*.bak 以点开头，早期版本按 "隐藏文件" 整类跳过 —— 那正好漏掉了最敏感的
# 一类产物。传 --include "*" 可恢复旧的"整目录镜像"行为。
DEFAULT_INCLUDE = ("*.sql.gz", ".env.*.bak")

# 与 scripts/backup_db.sh 的 KEEP_DAYS=7 保持一致
DEFAULT_KEEP_DAYS = 7

# 本项目在共享 prefix 下的专属子目录。依据 = 桶内 `offsite-backup/说明.txt`
# (2026-09-20 建) 规则 1："每人一个子目录，以自己命名，互不混放"。
# 它同时是**权限边界**：--cleanup 只删这个子目录下的对象（见 own_prefix）。
DEFAULT_SUBDIR = "microbubble"


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
    """凭据来源：显式文件 > 环境变量。缺任何一项 → 直接失败（禁止默认回落）。

    **桶与 endpoint 没有任何默认值**，这是刻意设计：
      2026-10-12 匿名探测实测 `mnb-workbench-releases` 返回 NoSuchKey（= 可读，
      它是 electron-updater 公开发布源），`mnb-workbench-backup` 返回 AccessDenied
      （私有）。而本脚本旧版把 releases 写成了 DEFAULT_BUCKET —— 一旦环境变量没设，
      DB dump 与 .env 备份就会静默流进一个**匿名可读**的桶。
    ⇒ 「回落到默认桶」在本项目等于最坏结果（明文备份进公开桶），故一律 fail-loud。
    """
    ak = sk = ""
    bucket = os.environ.get("OSS_BUCKET", "").strip()
    endpoint = os.environ.get("OSS_ENDPOINT", "").strip()
    prefix = os.environ.get("OSS_PREFIX", "").strip() or DEFAULT_PREFIX
    region = os.environ.get("OSS_REGION", "").strip()

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

    missing = [n for n, v in (("OSS_BUCKET", bucket), ("OSS_ENDPOINT", endpoint),
                               ("OSS_ACCESS_KEY_ID", ak), ("OSS_ACCESS_KEY_SECRET", sk)) if not v]
    if missing:
        raise SystemExit(
            "[FATAL] 缺少必需配置: " + ", ".join(missing) + "\n"
            "        本脚本**不提供任何桶/凭据默认值**。曾经的默认桶 mnb-workbench-releases "
            "是匿名可读的公开发布源，备份落进去等于公开。\n"
            "        请显式设置（计划任务账户需能读到）：\n"
            "          setx OSS_BUCKET \"mnb-workbench-backup\"\n"
            "          setx OSS_ENDPOINT \"oss-cn-beijing.aliyuncs.com\"\n"
            "          setx OSS_ACCESS_KEY_ID / OSS_ACCESS_KEY_SECRET\n"
            "        或用 --creds 指定凭据 JSON（字段 accessKeyId/accessKeySecret/bucket/endpoint）。"
        )

    if not region:
        # oss-cn-beijing.aliyuncs.com → cn-beijing
        region = endpoint.split(".")[0].removeprefix("oss-") if endpoint else ""
        if not region:
            raise SystemExit(f"[FATAL] 无法从 endpoint 推导 region: {endpoint!r}，请显式设置 OSS_REGION")

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

    host = f"{creds.bucket}.{creds.endpoint}"
    url = f"https://{host}/"
    if object_key:
        url += urllib.parse.quote(object_key, safe="/-_.~")
    if query:
        url += "?" + _canonical_query(query)

    base_headers = {
        "User-Agent": "mnb-offsite-sync/1.0",
    }
    base_headers.update(extra)

    # 网络层重试（指数退避）。
    # ⚠️ 2026-10-12 首次真实上传实测: 无重试时 39 秒即因 `URLError [WinError 10060]`
    # 连接超时中断，40 个文件只传完 35 个 —— 大文件（40~82MB）最容易撞上。
    # 计划任务每天只跑一次，**一次抖动就丢一天**，故必须在此兜。
    # 只重试传输层错误（URLError/OSError）；HTTPError 已在下面按状态码返回，
    # 交由调用方判断（4xx 重试无意义，403 签名错重试多少次都一样）。
    last_exc: Exception | None = None
    for attempt in range(1, UPLOAD_RETRIES + 1):
        # ⚠️ 每次重试**必须重新签名**：V1 签名的 Date 头有 15 分钟有效期，
        # 退避后复用同一个 auth 头会拿到 403 SignatureDoesNotMatch —— 那是"签名过期"
        # 而非"真的签名错"，不重新签就会把可恢复的网络抖动变成不可恢复的失败。
        auth, date = build_auth_header(creds, method, object_key, extra, query)
        req = urllib.request.Request(
            url, data=payload if body is not None else None,
            headers={**base_headers, "Authorization": auth, "Date": date}, method=method,
        )
        try:
            with urllib.request.urlopen(req, timeout=UPLOAD_TIMEOUT_S) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            last_exc = e
            if attempt == UPLOAD_RETRIES:
                break
            backoff = UPLOAD_BACKOFF_BASE_S * (2 ** (attempt - 1))
            print(f"[retry] {object_key or '(bucket)'} 第 {attempt}/{UPLOAD_RETRIES} 次失败 "
                  f"({e}); {backoff:.0f}s 后重试", file=sys.stderr)
            time.sleep(backoff)
    raise SystemExit(
        f"[FATAL] {object_key or '(bucket)'} 网络重试 {UPLOAD_RETRIES} 次仍失败: {last_exc}"
    )


def put_object(creds: Credentials, key: str, path: Path) -> None:
    # ⚠️ 这里**确实是**整文件进内存（旧注释自称"逐块读入"是不实的，已改正）。
    # 保留现状而非改成真流式上传，理由：V1 签名要把 Content-Length 纳入
    # string_to_sign，先读长度没问题，但真正流式需要额外处理 urllib 的 body 分块，
    # 收益（峰值 80MB → 更低）不值这个复杂度。
    # 峰值受控：加密产物 = 明文 dump + 57B 头 + 每块 16B tag，且**一次只传一个文件**。
    # 加密侧本身是流式的（encrypt_file 分块，不把明文整个读进内存）。
    size = path.stat().st_size
    payload = path.read_bytes()
    status, body = _request(creds, "PUT", key, payload, encrypt=True)
    if status not in (200, 201):
        raise SystemExit(f"[FATAL] 上传失败 {key} (HTTP {status}, {size} bytes): {body[:300]!r}")


def list_objects(creds: Credentials, prefix: str | None = None) -> list[dict]:
    """列举 prefix 下全部对象（分页）。prefix 缺省用 creds.prefix。

    传 prefix 是**权限边界**，不只是过滤 —— 见 own_prefix 的说明。
    """
    use_prefix = creds.prefix if prefix is None else prefix
    out: list[dict] = []
    token = ""
    while True:
        q = {"list-type": "2", "prefix": use_prefix, "max-keys": "1000"}
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

def default_root() -> Path:
    """默认备份根 = 本仓 backups/（scripts/backup_db.sh 的产出目录）。

    脚本位于 <repo>/apps/desktop/scripts/server/，向上 4 层即 <repo>。
    """
    return Path(__file__).resolve().parents[4] / "backups"


def scan_local(root: Path, prefix: str, includes=DEFAULT_INCLUDE) -> list[Path]:
    """递归收集待同步文件。

    `includes` 非空时按 glob 白名单收窄，并且**不再**跳过点开头的文件 ——
    旧实现按 `.startswith(".")` 整类跳过，而 `.env.YYYYMMDD.bak` 正是我们最该备份、
    也最需要加密的那一类，于是被静默漏掉了（"看起来在工作"的典型形态）。
    `includes` 为空 / 含 "*" 时退化为整目录镜像并恢复隐藏文件过滤（服务器共享目录用法）。
    """
    if not root.is_dir():
        raise SystemExit(f"[FATAL] 备份根目录不存在: {root}")
    mirror_all = not includes or "*" in includes
    files: list[Path] = []
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        if p.name.endswith((".tmp", ".partial", ".lock")):
            continue
        if mirror_all:
            if p.name.startswith("."):
                continue
        elif not any(p.match(g) or p.name.endswith(g.lstrip("*")) and p.match(g)
                     for g in includes):
            continue
        files.append(p)
    return files


def remote_key(creds: Credentials, root: Path, path: Path, encrypt: bool,
               subdir: str = "") -> str:
    """远端 key = prefix + [子目录/] + 相对根目录的 POSIX 路径 + 加密时的 .enc 后缀。

    `.enc` 后缀是**结构性**防线：远端一眼可辨哪些是密文，也让保留策略不会误伤
    任何历史遗留的明文对象（明文 key 不带后缀，自然与本轮 key 不匹配）。

    `subdir` 对齐桶内既有约定（`offsite-backup/说明.txt` 规则 1："每人一个子目录，
    以自己命名，互不混放"）。默认值空 = 沿用平铺，但那样其他成员的备份会与本项目的
    文件混在同一前缀下，既违反该约定，也让"谁的文件"无法一眼分辨。
    注意保留策略按 prefix 列前缀，本子目录仍在 prefix 内，清理逻辑不受影响。
    """
    rel = path.relative_to(root).as_posix()
    mid = f"{subdir.strip('/')}/" if subdir.strip("/") else ""
    return f"{creds.prefix}{mid}{rel}{ENC_SUFFIX if encrypt else ''}"


def expected_remote_size(path: Path, encrypt: bool) -> int:
    """远端应有的字节数 —— 幂等判据。加密时密文长度是明文的**确定函数**，
    所以不必真加密一遍就能判断"远端是否已是这一份"。
    （注意：同长度不同内容仍会跳过，这是同名同大小幂等的固有取舍，
    与原实现一致 —— 备份文件名自带时间戳，内容变了名字也变。）"""
    size = path.stat().st_size
    return encrypted_size(size) if encrypt else size


def _print_plan(files: list[Path], creds: Credentials, root: Path, encrypt: bool,
                remote: dict[str, int], subdir: str = "") -> int:
    to_upload, skipped = [], 0
    for f in files:
        if remote.get(remote_key(creds, root, f, encrypt, subdir)) == expected_remote_size(f, encrypt):
            skipped += 1
        else:
            to_upload.append(f)
    print(f"[scan] 本地待同步 {len(files)} 个；远端对象 {len(remote)} 个")
    print(f"[scan] 需上传 {len(to_upload)} 个；同名同大小跳过 {skipped} 个")
    print(f"[scan] 加密={'开（AES-256-GCM）' if encrypt else '关（!! 明文上传 !!）'}")
    for f in to_upload:
        print(f"       + {remote_key(creds, root, f, encrypt, subdir)} "
              f"({f.stat().st_size} → {expected_remote_size(f, encrypt)} bytes)")
    return 0


def own_prefix(creds: Credentials, subdir: str = "") -> str:
    """本项目**独占**的远端前缀 = creds.prefix [+ 子目录/]。

    ⚠️ 这个前缀是权限与安全的边界，不只是命名美化（2026-10-12 补）：
    `list_objects` 按 creds.prefix 列举，若 prefix 共享给全组，那么
      ① 幂等比对会看到别人的对象（无害但噪声大）；
      ② **`--cleanup` 会把别人的备份一起删掉** —— 那是对他人数据的破坏。
    故列出与清理都必须收敛到自己的子目录；子目录不存在时列举返回空，
    清理则变成 no-op（而不是"删光 prefix 下全部"）。
    """
    mid = subdir.strip("/")
    return f"{creds.prefix}{mid}/" if mid else creds.prefix


def do_scan(creds: Credentials, root: Path, includes, encrypt: bool,
            subdir: str = "") -> int:
    files = scan_local(root, creds.prefix, includes)
    remote = {o["key"]: o["size"]
              for o in list_objects(creds, prefix=own_prefix(creds, subdir))}
    return _print_plan(files, creds, root, encrypt, remote, subdir)


def do_apply(creds: Credentials, root: Path, includes, encrypt: bool,
             passphrase: bytes, confirm: bool, subdir: str = "") -> int:
    if not confirm:
        print("[apply] 未加 --confirm —— 仅 DRY RUN，未上传任何文件。")
        return do_scan(creds, root, includes, encrypt, subdir)

    files = scan_local(root, creds.prefix, includes)
    remote = {o["key"]: o["size"]
              for o in list_objects(creds, prefix=own_prefix(creds, subdir))}
    uploaded = skipped = 0
    tmpdir = None
    if encrypt:
        _TMP_ROOT.mkdir(parents=True, exist_ok=True)
        tmpdir = tempfile.mkdtemp(prefix="offsite-enc-", dir=_TMP_ROOT)
    try:
        for f in files:
            key = remote_key(creds, root, f, encrypt, subdir)
            if remote.get(key) == expected_remote_size(f, encrypt):
                skipped += 1
                continue
            if encrypt:
                # 密文落临时文件再 PUT：既不把 80MB 明文留在 backups/ 里，
                # 也不整文件进内存（PBKDF2 600k 次 + AES 都走流式分块）
                enc_path = Path(tmpdir) / (f.name + ENC_SUFFIX)
                plain_len, salt_hex = encrypt_file(f, enc_path, passphrase)
                cipher_len = enc_path.stat().st_size
                put_object(creds, key, enc_path)
                enc_path.unlink(missing_ok=True)
                print(f"[apply] ✓ {key} (明文 {plain_len} → 密文 {cipher_len} bytes, "
                      f"salt {salt_hex[:12]}…)")
            else:
                put_object(creds, key, f)
                print(f"[apply] ✓ {key} ({f.stat().st_size} bytes)")
            uploaded += 1
    finally:
        if tmpdir:
            shutil.rmtree(tmpdir, ignore_errors=True)
    print(f"[apply] 完成：上传 {uploaded}，跳过 {skipped}（同名同大小）")
    return 0


def _parse_last_modified(raw: str):
    """OSS 的 LastModified 可能是 '...T..:..:..000Z' 或无小数秒的写法，两种都收。"""
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def select_expired(days: int, objects: list[dict]) -> tuple[list[dict], list[dict]]:
    """按 keep-days 切出过期对象。返回 (victims, skipped_undated)。

    LastModified 解析不出来的对象**不删** —— 宁可多留，不可凭猜测删备份。
    """
    if days <= 0:
        raise SystemExit("[FATAL] 保留天数需为正整数")
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    victims, skipped = [], []
    for o in objects:
        lm = _parse_last_modified(o["last_modified"])
        if lm is None:
            skipped.append(o)
        elif lm < cutoff:
            victims.append(o)
    return victims, skipped


def do_cleanup(creds: Credentials, days: int, confirm: bool, subdir: str = "") -> int:
    # ⚠️ 必须按 own_prefix 列举，而不是整个 creds.prefix ——
    # prefix 是全组共享的根，按它清理会**删掉别人的备份**（对他人数据的破坏）。
    scope = own_prefix(creds, subdir)
    objs = list_objects(creds, prefix=scope)
    if not objs:
        print(f"[cleanup] {scope} 下无对象，无需清理。")
        return 0
    victims, undated = select_expired(days, objs)
    print(f"[cleanup] 作用域 {scope}：{len(objs)} 个对象，{days} 天前的候选 {len(victims)} 个")
    if not confirm:
        print("[cleanup] 未加 --confirm —— 仅列出候选：")
        for o in victims:
            print(f"          - {o['key']} ({o['last_modified']})")
        return 0
    for o in victims:
        delete_object(creds, o["key"])
        print(f"[cleanup] ✓ 已删除 {o['key']}")
    print(f"[cleanup] 完成：删除 {len(victims)} 个，保留 {len(undated)} 个（时间戳无法解析，未动）")
    return 0


def do_decrypt(src: Path, out_dir: Path, passphrase: bytes) -> int:
    """解密单个 .enc → out_dir/<去掉 .enc 的原名>。灾备取回与往返验证都走这里。"""
    if not src.is_file():
        raise SystemExit(f"[FATAL] 待解密文件不存在: {src}")
    out_dir.mkdir(parents=True, exist_ok=True)
    dst = out_dir / (src.name[:-len(ENC_SUFFIX)] if src.name.endswith(ENC_SUFFIX) else src.name + ".dec")
    n = decrypt_file(src, dst, passphrase)
    print(f"[decrypt] ✓ {src} → {dst} ({n} bytes)")
    return 0


# ---------------------------------------------------------------- CLI

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="把备份目录**加密后**镜像到阿里云 OSS（scan / apply / cleanup / decrypt）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--scan", action="store_true", help="列出本地/远端差异（无副作用）")
    parser.add_argument("--apply", action="store_true", help="上传差异文件（需 --confirm）")
    parser.add_argument("--cleanup", type=int, metavar="DAYS", help="删除远端 N 天前的对象（需 --confirm）")
    parser.add_argument("--confirm", action="store_true", help="二次确认门（缺省为 DRY RUN）")
    parser.add_argument("--root", help="本地备份根目录（默认 <脚本上级仓库>/backups）")
    parser.add_argument("--include", action="append", metavar="GLOB", dest="includes",
                        help=f"只同步匹配的文件，可重复；默认 {' '.join(DEFAULT_INCLUDE)}；"
                             f"传 '*' 恢复整目录镜像")
    parser.add_argument("--creds", help="凭据 JSON 文件路径（缺省则读环境变量）")
    parser.add_argument("--passphrase-file", default=None,
                        help=f"加密口令文件（默认 {DEFAULT_PASSPHRASE_FILE}）。"
                             "加密无开关：任何上传路径都强制加密")
    parser.add_argument("--keep-days", type=int, default=DEFAULT_KEEP_DAYS,
                        help=f"--apply 成功后顺带清理远端 N 天前的对象（默认 {DEFAULT_KEEP_DAYS}，"
                             f"与 scripts/backup_db.sh 的 KEEP_DAYS 一致；传 0 表示不清理）")
    parser.add_argument("--subdir", default=DEFAULT_SUBDIR, metavar="NAME",
                        help=f"远端 prefix 下的本项目专属子目录（默认 {DEFAULT_SUBDIR!r}）。"
                             "既是命名隔离，也是**权限边界**：--cleanup 只作用于该子目录，"
                             "不会删掉同 prefix 下其他成员的备份（桶内说明.txt 规则 1）")
    parser.add_argument("--decrypt-into", metavar="DIR",
                        help="解密模式：把给定 .enc 文件解到 DIR")
    parser.add_argument("files", nargs="*", help="--decrypt-into 模式下的密文文件路径")
    args = parser.parse_args(argv)

    encrypt = True  # 加密无开关（见模块 docstring）
    includes = tuple(args.includes) if args.includes else DEFAULT_INCLUDE
    subdir = args.subdir.strip("/")

    # --- 解密模式：不碰 OSS 凭据，也不需要备份根目录 ---
    if args.decrypt_into:
        pp = load_passphrase(args.passphrase_file or DEFAULT_PASSPHRASE_FILE)
        if not args.files:
            parser.error("--decrypt-into 需要至少一个密文文件参数")
        for src in args.files:
            do_decrypt(Path(src), Path(args.decrypt_into), pp)
        return 0

    if not (args.scan or args.apply or args.cleanup is not None):
        parser.print_help()
        return 2

    # --- 口令 fail-loud 必须发生在**任何** OSS 调用之前 ---
    passphrase = load_passphrase(args.passphrase_file or DEFAULT_PASSPHRASE_FILE)

    creds = load_credentials(args.creds)
    root = Path(args.root) if args.root else default_root()
    print(f"[init] bucket={creds.bucket} endpoint={creds.endpoint} prefix={creds.prefix}")
    print(f"[init] root={root} include={list(includes)} encrypt={encrypt} keep_days={args.keep_days}")
    print(f"[init] subdir={subdir!r} scope={own_prefix(creds, subdir)}")

    if args.scan:
        return do_scan(creds, root, includes, encrypt, subdir)
    if args.apply:
        rc = do_apply(creds, root, includes, encrypt, passphrase, args.confirm, subdir)
        if rc == 0 and args.confirm and args.keep_days > 0:
            # 原设计缺的那块：上传完不清理 → 远端无限增长
            rc = do_cleanup(creds, args.keep_days, confirm=True, subdir=subdir)
        return rc
    return do_cleanup(creds, int(args.cleanup), args.confirm, subdir)


if __name__ == "__main__":
    sys.exit(main())
