"""把逐页预览缓存目录从旧 key (updated_at) 迁到新 key (file_path)

背景 (2026-10-09 agent39):
  `app/api/v1/drive_files.py` 的预览缓存 key 原为
  `md5("v1:" + str(f.updated_at))[:12]`。updated_at 是**行级**时间戳 ——
  任何碰这一行的写操作都会让它变 (改名/移动/改 visibility/收藏/批量重索引),
  哪怕文件字节一个没动。2026-10-08 18:58 一次批量重索引把 295 个 drive PPT 的
  updated_at 全刷新 → 生产 key 命中率实测 **0/295 = 0.0%**, 而 PNG 内容没变
  (抽验 file 1041 / 1071 重新 soffice 转换, 20/20 + 22/22 页 sha256 逐字节一致)。

  代价不是磁盘而是 CPU: `_LIBREOFFICE_GATE = Semaphore(1)` 全局串行,
  295 个文件重转要几十分钟, 期间这些文件的预览请求全被锁挡成 converting。

修复: key 基准换成 `file_path` (MinIO object_name, 内容身份 ——
  upload_file 走 uuid4().hex; 秒传/新版本/回滚 每次都铸新对象名,
  全仓无原地覆写同一 object 的写路径, 故 file_path 变 ⟺ 内容变)。

本脚本做什么:
  把磁盘上已存在的 `{file_id}_{oldkey}` 目录 **rename** 成 `{file_id}_{newkey}`,
  让 32.5% 已缓存但"算不出 key"的文件直接命中, 不必重转。

安全边界 (为什么 rename 是安全的):
  1. **不删除任何东西** —— 只 rename, 孤儿目录 (无对应活跃行 / 无 ready.json)
     原样保留。孤儿最多占盘, 不会导致正确性问题。
  2. **目标 key 由 DB 的 file_path 现算**, 与文件实际内容绑定; 实测 326 个
     drive 行 file_path 零重复, 且 drive 行 version_number>1 的为 0
     (内容从未原地变更), 故 file_id → file_path → newkey 是单射。
  3. **同一 file_id 多个旧目录时取 mtime 最新的一个** (最近转换的那份),
     其余保留为孤儿 —— 因为 file_path 从未变过, 任意一份内容都正确,
     取最新只是避免回退到更早的渲染。
  4. **目标已存在则跳过** (不覆盖), 幂等: 重跑不会二次动。

⚠️ 前提: 必须先部署 drive_files.py 的新 key 代码, 再跑本脚本。
   反序 (先迁移后部署) 会让新代码找不到目录 → 白迁移一次 (不破坏, 只是无效)。

用法 (⚠️ scripts/ **不是** bind mount, 容器内是镜像旧拷贝, 必须用 stdin 送入):
    docker exec -i -w /app microbubble-agent-app-1 python - < scripts/migrate_preview_cache_key.py
    ... --apply          # 真改名 (默认 dry-run, 只打印计划)
    ... --root /app/data/pptx_pages   # 指定缓存根 (默认按扩展名自动推断)
    ... --ext pptx       # 只处理某一类 (pptx/docx/pdf/xlsx/zip/csv, 默认全部)
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("migrate_preview_cache_key")

# 扩展名 → 缓存根目录名 (与 drive_files.py 的 _pptx_cache_dir 等一致)
CACHE_ROOTS = {
    "pptx": "pptx_pages",
    "docx": "docx_pages",
    "pdf": "pdf_pages",
    "xlsx": "xlsx_preview",
    "zip": "zip_preview",
    "csv": "csv_preview",
}
# 缓存根 → 该管线接受的文件扩展名 (与各端点的 endswith 守卫一致)
ROOT_EXTS = {
    "pptx_pages": (".pptx",),
    "docx_pages": (".docx", ".doc"),
    "pdf_pages": (".pdf",),
    "xlsx_preview": (".xlsx",),
    "zip_preview": (".zip",),
    "csv_preview": (".csv",),
}
DATA_ROOT = Path("/app/data")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="预览缓存目录 key 迁移 (updated_at → file_path)")
    p.add_argument("--apply", action="store_true", help="真改名 (默认 dry-run)")
    p.add_argument("--root", default=None, help="缓存根目录 (默认 /app/data 下按 CACHE_ROOTS 推断)")
    p.add_argument("--ext", default=None, choices=sorted(CACHE_ROOTS), help="只处理某一类")
    p.add_argument("--prune-orphans", action="store_true",
                   help="额外删除无对应活跃行的孤儿目录 (默认关 —— 本脚本原则上不删东西)")
    return p.parse_args()


def new_key(file_path: str) -> str:
    """与 drive_files._preview_cache_key 完全一致 (前缀 v2 + file_path)。"""
    return hashlib.md5(("v2:" + str(file_path)).encode()).hexdigest()[:12]


async def fetch_active_files(exts: Tuple[str, ...]) -> Dict[int, str]:
    """取活跃 drive 行 id → file_path。

    守卫与生产端点一致: deleted_at IS NULL (软删行不参与) + storage_mode='drive'
    + file_path 非空 (各端点在 file_path 为空时先行 404, 不会有缓存目录)。
    """
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from app.config import settings

    db_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
    engine = create_async_engine(db_url, pool_size=2)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    like_clauses = " OR ".join(
        "lower(k.file_name) LIKE '%" + e + "'" for e in exts
    )
    sql = text(
        "SELECT k.id, k.file_path FROM knowledge k "
        "WHERE k.deleted_at IS NULL AND k.storage_mode='drive' "
        f"AND k.file_path IS NOT NULL AND k.file_path <> '' AND ({like_clauses})"
    )
    out: Dict[int, str] = {}
    try:
        async with Session() as db:
            for row in (await db.execute(sql)).all():
                out[int(row[0])] = row[1]
    finally:
        await engine.dispose()
    return out


def dir_size(p: Path) -> int:
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


def plan_one_root(root: Path, active: Dict[int, str], ext_label: str) -> dict:
    """为一个缓存根做迁移计划 (不改任何东西)。"""
    stats = {
        "root": str(root), "ext": ext_label,
        "dirs_total": 0, "ready_dirs": 0, "migratable": 0,
        "renames": [],            # (src, dst)
        "skip_target_exists": 0, "orphans": [], "bytes_reclaimed_if_pruned": 0,
    }
    if not root.is_dir():
        logger.warning("[%s] 缓存根不存在, 跳过: %s", ext_label, root)
        return stats

    # file_id → [(key, mtime, path)], 只收有 ready.json 的 (半成品/error 目录不迁)
    by_id: Dict[int, List[Tuple[str, float, Path]]] = {}
    for d in root.iterdir():
        if not d.is_dir() or "_" not in d.name:
            continue
        stats["dirs_total"] += 1
        fid_s, key = d.name.split("_", 1)
        try:
            fid = int(fid_s)
        except ValueError:
            stats["orphans"].append((str(d), "文件名无合法 file_id"))
            continue
        if not (d / "ready.json").exists():
            # 半成品 / error.txt 目录: 不迁 (重转时会自己重建), 也不删
            stats["orphans"].append((str(d), "无 ready.json (半成品/error)"))
            continue
        stats["ready_dirs"] += 1
        try:
            mt = d.stat().st_mtime
        except OSError:
            mt = 0.0
        by_id.setdefault(fid, []).append((key, mt, d))

    for fid, entries in sorted(by_id.items()):
        fp = active.get(fid)
        if not fp:
            stats["orphans"].append((str(entries[-1][2]), f"file_id={fid} 无活跃 drive 行"))
            continue
        # 同一 file_id 多份旧缓存 → 取 mtime 最新的 (内容等价, 只为不回退)
        entries.sort(key=lambda x: x[1])
        newest_key, newest_mt, newest_dir = entries[-1]
        target = root / f"{fid}_{new_key(fp)}"
        if target.exists():
            stats["skip_target_exists"] += 1
            continue
        stats["migratable"] += 1
        stats["renames"].append((str(newest_dir), str(target)))
        # 同 file_id 的其余旧目录: 保留为孤儿 (不删)
        for k, mt, d in entries[:-1]:
            stats["orphans"].append((str(d), f"file_id={fid} 的非最新旧缓存 (保留)"))

    # 完全对不上任何活跃行的目录
    for d in root.iterdir():
        if not d.is_dir() or "_" not in d.name:
            continue
        fid_s = d.name.split("_", 1)[0]
        try:
            fid = int(fid_s)
        except ValueError:
            continue
        if fid not in by_id and fid not in active:
            stats["orphans"].append((str(d), f"file_id={fid} 既无 ready 缓存也无活跃行"))
    return stats


async def main() -> int:
    args = parse_args()
    roots: List[Tuple[str, Path]] = []
    if args.root:
        roots.append((args.ext or "custom", Path(args.root)))
    else:
        for ext, name in CACHE_ROOTS.items():
            if args.ext and ext != args.ext:
                continue
            roots.append((ext, DATA_ROOT / name))

    all_stats = []
    for ext_label, root in roots:
        exts = ROOT_EXTS.get(root.name)
        if exts is None:
            exts = (f".{ext_label}",)
        active = await fetch_active_files(exts)
        st = plan_one_root(root, active, ext_label)
        all_stats.append(st)

        logger.info("=== %s (%s) ===", root, ext_label)
        logger.info("  活跃 drive 行: %d, 磁盘目录: %d (其中 ready: %d)",
                    len(active), st["dirs_total"], st["ready_dirs"])
        logger.info("  可迁移: %d, 目标已存在跳过: %d, 孤儿(保留): %d",
                    st["migratable"], st["skip_target_exists"], len(st["orphans"]))
        for src, dst in st["renames"][:10]:
            logger.info("    %s -> %s", Path(src).name, Path(dst).name)
        if len(st["renames"]) > 10:
            logger.info("    ... 另 %d 个", len(st["renames"]) - 10)

        if args.apply and st["renames"]:
            ok = fail = 0
            for src, dst in st["renames"]:
                try:
                    Path(src).rename(dst)
                    ok += 1
                except OSError as e:
                    logger.error("  rename 失败 %s -> %s: %s", src, dst, e)
                    fail += 1
            logger.info("  [apply] 改名成功 %d, 失败 %d", ok, fail)

        if args.apply and args.prune_orphans:
            freed = 0
            for path, why in st["orphans"]:
                p = Path(path)
                if not p.is_dir():
                    continue
                try:
                    freed += dir_size(p)
                    shutil.rmtree(p)
                except OSError as e:
                    logger.error("  prune 失败 %s: %s", path, e)
            logger.info("  [apply] prune 孤儿 %d 个, 释放 %.1f MB",
                        len(st["orphans"]), freed / 1e6)

    if not args.apply:
        logger.info("dry-run 结束 (未改动任何文件)。加 --apply 真执行。")
    else:
        logger.info("apply 完成。")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))