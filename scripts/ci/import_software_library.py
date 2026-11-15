"""把 E:\\软件库 里的安装包**按网盘既有 PPT 的同一套方式**写入 MinIO + 建 drive 行。

运行方式 (在 app 容器内, 宿主 E:\\软件库 只读挂载到 /software):
  docker run --rm --network microbubble-agent_default \
    -v "E:/软件库:/software:ro" \
    -v "E:/microbubble-agent/app:/app/app:ro" \
    microbubble-agent-app \
    python /app/app/../scripts/...  # 实际由调用方 docker cp 到 /tmp 执行

为什么需要这个脚本:
- 网页上传 128GB 要走浏览器 + 公网隧道, 慢且容易断;
- 本机 Docker 内网直连 MinIO (minio:9000) 流式 put_object, 不经过外网;
- 落点与 PPT 完全一致: 对象键 drive/<folder_id>/<uuid><ext>, knowledge 行
  storage_mode='drive', folder_id 指向软件库子目录;
- 不写第二份到项目目录; E 盘原文件与 MinIO 是两份独立副本 (与 PPT 相同)。

安全:
- 流式上传 (8 MiB 一块), 内存峰值与文件大小无关;
- 上传后**回读** stat_object 比大小 + 流式算 SHA256, 与本地源文件实算值比对;
  不一致即删对象并报错, 不留坏数据 (类 20.220: 验副作用)。
- 幂等: 同 folder_id + file_name + file_size 已存在则跳过, 重跑不会产生重复行。
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import mimetypes
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from app.core.database import async_session
from app.models.knowledge import Knowledge
from app.services.file_service import file_service

ROOT = Path('/software')
FOLDERS = {
    'COMSOL': 1548,
    'Matlab': 1549,   # 网盘显示名 MATLAB
    'AutoCAD': 1550,
    # 2026-11-12: 落点 = 软件库/Gaussian(1554)/Windows 安装包(1555)
    'Gaussian': 1555,
    # 2026-11-12: 落点 = 软件库/Origin(1557)
    'Origin': 1557,
    # 2026-11-15: 学校正版授权 — 落点 = 软件库/Office(1558)、软件库/Visio(1559)
    'Office': 1558,
    'Visio': 1559,
}
OWNER_ID = 3
# 2026-11-15: 软件库所有内容统一挂「团队共享」标识账号 (members.username='team_shared')
# 而不是个人; team_shared 是不可登录的展示账号 (id 1462)。
TEAM_SHARED_USERNAME = 'team_shared'
HASH_BLOCK = 8 * 1024 * 1024
REPORT = Path('/tmp/software_library_import_report.json')


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        while True:
            b = f.read(HASH_BLOCK)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


async def upload_one(src: Path, key: str) -> None:
    """流式 put_object (minio-py 支持 file-like + part_size, 不整份读内存)。"""
    size = src.stat().st_size
    content_type = mimetypes.guess_type(src.name)[0] or 'application/octet-stream'

    def _sync_put():
        with src.open('rb') as f:
            file_service.client.put_object(
                file_service.bucket,
                key,
                f,
                length=size,
                content_type=content_type,
                part_size=HASH_BLOCK,
            )

    await asyncio.to_thread(_sync_put)


async def verify_remote(key: str, expected_size: int, expected_sha: str) -> None:
    st = await asyncio.to_thread(file_service.client.stat_object, file_service.bucket, key)
    if int(st.size or 0) != expected_size:
        raise RuntimeError(f'对象大小不符: {st.size} != {expected_size} ({key})')
    hashed = await file_service.stream_sha256_async(key)
    if int(hashed.get('size') or 0) != expected_size or str(hashed.get('sha256')) != expected_sha:
        raise RuntimeError(f'回读 SHA256 不符 ({key})')


async def main() -> int:
    entries = []
    # 例: SOFTWARE_LABELS=Gaussian 只处理指定软件, 避免重扫全部目录
    only = {s.strip() for s in os.environ.get('SOFTWARE_LABELS', '').split(',') if s.strip()}
    for label, folder_id in FOLDERS.items():
        if only and label not in only:
            continue
        d = ROOT / label
        if not d.is_dir():
            print(f'[WARN] 缺目录 {d}', flush=True)
            continue
        for p in sorted(d.rglob('*')):
            if p.is_file():
                entries.append((label, folder_id, p, p.relative_to(d).as_posix()))
    print(f'待入库 {len(entries)} 个文件, 总计 {sum(p.stat().st_size for _,_,p,_ in entries)} 字节', flush=True)

    report = []
    for n, (label, folder_id, src, rel) in enumerate(entries, 1):
        size = src.stat().st_size
        name = src.name
        async with async_session() as db:
            dup = (await db.execute(
                select(Knowledge.id).where(
                    Knowledge.folder_id == folder_id,
                    Knowledge.file_name == name,
                    Knowledge.file_size == size,
                    Knowledge.deleted_at.is_(None),
                )
            )).scalar_one_or_none()
            if dup:
                print(f'[{n}/{len(entries)}] SKIP 已存在 id={dup} {label}/{rel}', flush=True)
                report.append({'label': label, 'rel': rel, 'status': 'skipped', 'id': dup})
                continue

        expected = sha256_of(src)   # 本地实算 (流式, 不进内存)
        ext = src.suffix[:20]
        key = f'drive/{folder_id}/{uuid.uuid4().hex}{ext}'
        print(f'[{n}/{len(entries)}] PUT {label}/{rel} ({size} B)', flush=True)
        try:
            await upload_one(src, key)
            await verify_remote(key, size, expected)
        except Exception as exc:
            try:
                await asyncio.to_thread(file_service.client.remove_object, file_service.bucket, key)
            except Exception:
                pass
            print(f'[FAIL] {rel}: {exc}', flush=True)
            report.append({'label': label, 'rel': rel, 'status': 'failed', 'error': str(exc)})
            continue

        now = datetime.utcnow()
        async with async_session() as db:
            # 软件库内容统一挂「团队共享」账号; 账号缺失时回退 OWNER_ID 并告警
            team_shared_id = (await db.execute(
                select(Member.id).where(Member.username == TEAM_SHARED_USERNAME)
            )).scalar_one_or_none()
            if team_shared_id is None:
                print(f'[WARN] members 里没有 username={TEAM_SHARED_USERNAME}, 回退 created_by={OWNER_ID}', flush=True)
                team_shared_id = OWNER_ID
            k = Knowledge(
                title=name,
                content=f'[drive upload] {name}',
                file_path=key,
                file_name=name,
                file_type=ext or 'application/octet-stream',
                file_size=size,
                file_hash=expected,
                storage_mode='drive',
                visibility='team',
                folder_id=folder_id,
                # ⚠️ Knowledge 的创建人字段是 created_by (没有 owner_id) ——
                #    传 owner_id 会 TypeError, 且此时 MinIO 对象已写好 ⇒ 孤儿。
                created_by=team_shared_id,
                created_at=now,
                updated_at=now,
                is_latest=True,
                version_number=1,
                is_team_shared=True,
                thumbnail_status='pending',
                embedding_model_version='qwen3-0.6b',
                analysis_status='done',   # 不被 rag_auto_ingest 当待分析正文
            )
            db.add(k)
            await db.commit()
            await db.refresh(k)
            kid = k.id
        print(f'  OK id={kid} sha256={expected[:12]}…', flush=True)
        report.append({'label': label, 'rel': rel, 'status': 'ok', 'id': kid,
                       'size': size, 'sha256': expected, 'key': key})

    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    ok = sum(1 for r in report if r['status'] in ('ok', 'skipped'))
    fail = sum(1 for r in report if r['status'] == 'failed')
    print(f'DONE ok/skip={ok} failed={fail} report={REPORT}', flush=True)
    return 1 if fail else 0


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
