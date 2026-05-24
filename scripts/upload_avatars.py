#!/usr/bin/env python3
"""批量上传成员头像脚本"""

import os
import sys
import asyncio
import aiohttp
from pathlib import Path

# 配置
API_BASE = "http://localhost:8000/api/v1"
PHOTOS_DIR = Path(r"D:\综合文件夹\剪辑\年会杂文件\证件照")

async def login(session, username, password):
    """登录获取token"""
    async with session.post(f"{API_BASE}/auth/login", json={"username": username, "password": password}) as resp:
        if resp.status != 200:
            print(f"登录失败，请检查账号密码")
            return None
        data = await resp.json()
        return data.get("access_token")

async def get_members(session, token):
    """获取成员列表"""
    headers = {"Authorization": f"Bearer {token}"}
    async with session.get(f"{API_BASE}/members?page_size=100", headers=headers) as resp:
        if resp.status != 200:
            print(f"获取成员列表失败")
            return {}
        data = await resp.json()
        # 构建 name -> id 映射
        return {m["name"]: m["id"] for m in data.get("items", [])}

async def upload_file(session, token, file_path, prefix="avatars"):
    """上传文件"""
    headers = {"Authorization": f"Bearer {token}"}
    file_name = os.path.basename(file_path)

    with open(file_path, "rb") as f:
        file_data = f.read()

    form = aiohttp.FormData()
    form.add_field("prefix", prefix)
    form.add_field(
        "file",
        file_data,
        filename=file_name,
        content_type="image/jpeg"
    )

    async with session.post(f"{API_BASE}/upload", headers=headers, data=form) as resp:
        if resp.status != 200:
            text = await resp.text()
            print(f"  上传失败 {file_name}: {text}")
            return None
        result = await resp.json()
        return result.get("url")

async def update_member_avatar(session, token, member_id, avatar_url):
    """更新成员头像"""
    headers = {"Authorization": f"Bearer {token}"}
    async with session.put(f"{API_BASE}/members/{member_id}", headers=headers, json={"avatar": avatar_url}) as resp:
        if resp.status != 200:
            text = await resp.text()
            print(f"  更新头像失败: {text}")
            return False
        return True

async def main():
    print("=" * 50)
    print("成员头像批量上传工具")
    print("=" * 50)

    # 获取命令行参数
    if len(sys.argv) != 3:
        print(f"\n用法: python {sys.argv[0]} <用户名> <密码>")
        print(f"示例: python {sys.argv[0]} zhaohangjia 123456")
        return

    username = sys.argv[1]
    password = sys.argv[2]

    # 登录
    async with aiohttp.ClientSession() as session:
        print(f"\n[1/4] 登录为 {username}...")
        token = await login(session, username, password)
        if not token:
            return
        print("  登录成功")

        print("\n[2/4] 获取成员列表...")
        members = await get_members(session, token)
        print(f"  找到 {len(members)} 个成员")
        for name, mid in members.items():
            print(f"    - {name} (id={mid})")

        print("\n[3/4] 上传头像并更新...")
        success = 0
        failed = 0

        # 获取所有照片文件
        photo_files = list(PHOTOS_DIR.glob("*.jpg")) + list(PHOTOS_DIR.glob("*.png"))

        for photo_path in photo_files:
            photo_name = photo_path.stem  # 文件名不含扩展名

            # 尝试匹配成员（照片名包含在成员姓名中）
            matched_member_id = None
            matched_member_name = None
            for member_name, member_id in members.items():
                if photo_name in member_name or member_name in photo_name:
                    matched_member_id = member_id
                    matched_member_name = member_name
                    break

            if not matched_member_id:
                print(f"  [!] 无法匹配成员: {photo_name}.jpg")
                failed += 1
                continue

            # 上传文件
            print(f"  >> 上传 {photo_name}.jpg -> {matched_member_name}...", end=" ")
            url = await upload_file(session, token, str(photo_path))
            if not url:
                failed += 1
                continue

            # 更新头像
            ok = await update_member_avatar(session, token, matched_member_id, url)
            if ok:
                print(f"[OK]")
                success += 1
            else:
                failed += 1

        print("\n[4/4] 完成!")
        print(f"  成功: {success}")
        print(f"  失败: {failed}")

if __name__ == "__main__":
    asyncio.run(main())
