"""确保 软件库/<软件名> 文件夹存在, 且 owner=团队共享标识账号。

用法 (app 容器内):
  python ensure_software_folders.py Office Visio
不带参数 = 处理 SOFTWARE_FOLDERS 里全部软件。

背景: import_software_library.py 只负责传文件, 文件夹此前是手工建的;
2026-11-15 起软件库统一挂团队共享 (members.username='team_shared'),
文件夹 owner 也必须一致, 否则列表页「上传者」显示回个人。
"""
import asyncio
import sys
from datetime import datetime

from sqlalchemy import select

from app.core.database import async_session
from app.models.folder import Folder
from app.models.member import Member

SOFTWARE_ROOT_ID = 1547
SOFTWARE_FOLDERS = {
    'COMSOL': 1548,
    'Matlab': 1549,      # 网盘显示名 MATLAB
    'AutoCAD': 1550,
    'Gaussian': 1554,
    'Origin': 1557,
    'Office': 1558,
    'Visio': 1559,
}
TEAM_SHARED_USERNAME = 'team_shared'
FALLBACK_OWNER_ID = 3


async def ensure(names: list[str]) -> int:
    async with async_session() as db:
        team_shared_id = (await db.execute(
            select(Member.id).where(Member.username == TEAM_SHARED_USERNAME)
        )).scalar_one_or_none()
        if team_shared_id is None:
            print(f'[WARN] 缺 {TEAM_SHARED_USERNAME} 账号, 文件夹 owner 回退 {FALLBACK_OWNER_ID}')
            team_shared_id = FALLBACK_OWNER_ID
        root = (await db.execute(select(Folder).where(Folder.id == SOFTWARE_ROOT_ID))).scalar_one()
        changed = 0
        for name in names:
            fid = SOFTWARE_FOLDERS.get(name)
            if fid is None:
                print(f'[WARN] 未知软件名 {name} (需先在 SOFTWARE_FOLDERS 登记)')
                continue
            folder = (await db.execute(select(Folder).where(Folder.id == fid))).scalar_one_or_none()
            if folder is None:
                folder = Folder(
                    name=name, parent_id=SOFTWARE_ROOT_ID, path=f'{root.path}{fid}/',
                    depth=1, visibility='team', owner_id=team_shared_id,
                    created_at=datetime.utcnow(), updated_at=datetime.utcnow(),
                )
                db.add(folder)
                await db.flush()
                folder.path = f'{root.path}{folder.id}/'
                changed += 1
                print(f'created {name} id={folder.id} owner=team_shared')
            elif folder.owner_id != team_shared_id:
                folder.owner_id = team_shared_id
                folder.updated_at = datetime.utcnow()
                changed += 1
                print(f'updated {name} id={folder.id} owner->team_shared')
            else:
                print(f'ok {name} id={folder.id} owner 已是 team_shared')
        await db.commit()
        return changed


if __name__ == '__main__':
    names = sys.argv[1:] or list(SOFTWARE_FOLDERS)
    raise SystemExit(asyncio.run(ensure(names)))
