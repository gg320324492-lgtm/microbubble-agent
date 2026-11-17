"""把本次导入误恢复的 'Origin 2019b 安装包.zip'（id 2977）回退成导入前的状态：
软删 knowledge 行 + 删除 MinIO 对象，保持网盘目录与 2026-11-12 清理后一致。"""
import asyncio
from sqlalchemy import update

from app.core.database import async_session
from app.models.knowledge import Knowledge
from app.services.file_service import file_service

TARGET_ID = 2977
TARGET_KEY = 'drive/1557/f535c8050b6a43dc9f6c991427b91980.zip'


async def main() -> int:
    async with async_session() as db:
        row = (await db.execute(
            update(Knowledge).where(Knowledge.id == TARGET_ID)
            .values(deleted_at=__import__('datetime').datetime.utcnow())
        ))
        await db.commit()
        print(f'soft-deleted knowledge id={TARGET_ID}: {row.rowcount} row(s)')
    await asyncio.to_thread(file_service.client.remove_object, file_service.bucket, TARGET_KEY)
    print(f'removed object {TARGET_KEY}')
    return 0


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
