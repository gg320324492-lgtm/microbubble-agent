#!/usr/bin/env python3
"""
upload_ppts_playwright.py — 把桌面 组会ppt/ 23 个发言人子目录里的 PPT
通过 Playwright 模拟用户操作上传到 Drive 团队共享盘的对应子 folder。

前置:
  - vite dev server 跑在 :3000 (npm run dev)
  - DriveUploadDialog.vue bug 已修 (is_team_shared 漏传)
  - Drive 团队共享盘已有 root folder "组会PPT" (id=336) + 23 个发言人子 folder (id=337-359)
  - xiaoqi_testbot 凭据可登录

操作流 (模仿用户视角):
  1. 打开 http://localhost:3000/login → 用 xiaoqi_testbot 登录
  2. 进入 /drive → 点 "🌐 团队共享盘" 特殊节点 → specialView=team
  3. 对每个发言人 sub folder:
     a. 在 FolderTree 里点击该 sub folder
     b. FileGrid 显示空 → 点工具栏 "上传文件" 按钮
     c. DriveUploadDialog 弹出 → set_input_files 选该发言人桌面子目录下所有 PPT
     d. dialog 自动选好 folder_id (默认) + visibility=team (默认)
     e. 点 "开始上传" 按钮
     f. 等上传进度跑完 + dialog 自动关闭 (1s 延迟)
  4. 截图最终 DriveView 状态
  5. DB 验证: 23 个 sub folder PPT 总数 == 273 (桌面 subdir PPT 数)
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright, expect, Page, BrowserContext, TimeoutError as PlaywrightTimeoutError

# --- Fix Windows console encoding ---
if sys.platform == "win32":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    except Exception:
        pass

# === Config ===
BASE_URL = "http://localhost:3000"
USERNAME = "xiaoqi_testbot"
PASSWORD = "testbot_pass_2026"
SOURCE_DIR = Path("C:/Users/pc/Desktop/组会ppt")
SCREENSHOTS_DIR = Path("e:/microbubble-agent/scripts/playwright_drive_screenshots")
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

# === Sub-folder mapping (发言人 → Drive folder_id, 来自 DB 查询) ===
# 名字一律无空格 (DB 显示就是无空格, 桌面目录也是无空格)
SUB_FOLDERS = {
    "余歆睿": 337, "关小未": 338, "冯懿鑫": 339, "刘子毅": 340, "吴孟铨": 341,
    "宋洋": 342, "张宏魁": 343, "张懿": 344, "李胜景": 345, "李锐远": 346,
    "杜同贺": 347, "杨慈": 348, "王书馨": 349, "耿嘉栋": 350, "胡小琪": 351,
    "艾琳朔": 352, "蒋芦笛": 353, "贾琦": 354, "赵航佳": 355, "陈天祥": 356,
    "陈金薪": 357, "雒培媛": 358, "韩重阳": 359,
}
# 桌面发言人目录名 (与 Drive folder name 完全一致, 无空格)
DESKTOP_DIRS = {
    "余歆睿": "余歆睿", "关小未": "关小未", "冯懿鑫": "冯懿鑫", "刘子毅": "刘子毅",
    "吴孟铨": "吴孟铨", "宋洋": "宋洋", "张宏魁": "张宏魁", "张懿": "张懿",
    "李胜景": "李胜景", "李锐远": "李锐远", "杜同贺": "杜同贺", "杨慈": "杨慈",
    "王书馨": "王书馨", "耿嘉栋": "耿嘉栋", "胡小琪": "胡小琪", "艾琳朔": "艾琳朔",
    "蒋芦笛": "蒋芦笛", "贾琦": "贾琦", "赵航佳": "赵航佳", "陈天祥": "陈天祥",
    "陈金薪": "陈金薪", "雒培媛": "雒培媛", "韩重阳": "韩重阳",
}

# === Logging ===
def log(msg: str) -> None:
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


# === Step 1: 拿 token (用 requests 走 API, 不经浏览器) ===
def get_token() -> str:
    r = requests.post(
        f"{BASE_URL}/api/v1/auth/login",
        json={"username": USERNAME, "password": PASSWORD},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["access_token"]


# === Step 2: DB 直查 校验当前状态 ===
def db_query(sql: str) -> str:
    r = subprocess.run(
        ["docker", "exec", "microbubble-agent-db-1", "psql",
         "-U", "postgres", "-d", "microbubble", "-tAc", sql],
        capture_output=True,
    )
    return r.stdout.decode("utf-8").strip()


def db_count_in_folder(folder_id: int) -> int:
    out = db_query(
        f"SELECT COUNT(*) FROM knowledge "
        f"WHERE folder_id = {folder_id} AND deleted_at IS NULL "
        f"AND storage_mode = 'drive'"
    )
    return int(out) if out else 0


# === Step 3: 主 Playwright 流程 ===
def inject_token_to_browser(context: BrowserContext, token: str, user_info: dict) -> None:
    """DEPRECATED: init script 注入 token 会触发 router guard, /login 自动跳走 → LoginView 不渲染
    改为由 Playwright 走真实 LoginView 填表登录 (见 login_then_navigate_to_drive).
    保留此函数为 no-op 以兼容 main() 调用.
    """
    log("  [inject_token_to_browser] 已禁用, 走真实 LoginView 登录")


def login_then_navigate_to_drive(page: Page) -> None:
    """走真实 LoginView 登录 (模仿用户操作)"""
    log("  打开 /login ...")
    page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded")
    # 等 element-plus input 渲染 (class 在 Vue mounted 后才有)
    # element-plus el-input 内部 <input> 有 .el-input__inner (LoginView 用 el-input size=large)
    page.wait_for_selector("input.el-input__inner", timeout=15_000)
    # 防 Vue reactivity 时序: 等 800ms 让 form 全部绑定好
    page.wait_for_timeout(800)
    inputs = page.locator("input.el-input__inner")
    inputs.nth(0).fill(USERNAME)
    inputs.nth(1).fill(PASSWORD)
    log(f"  填表单: username={USERNAME}")
    page.click("button.login-button")
    # 等跳转出 /login (router.push('/') 触发 URL 变化)
    try:
        page.wait_for_url(lambda url: "/login" not in url, timeout=15_000)
    except PlaywrightTimeoutError:
        log(f"  WARN: 跳转超时, 当前 URL={page.url}")
    page.wait_for_timeout(2000)
    log(f"  登录完成, 当前 URL={page.url}")


def navigate_to_drive_team_shared(page: Page) -> None:
    """进 /drive → 先切到 🌐 团队共享盘 (只是为截图 + 后面 FileGrid 走 view=team)"""
    log("  跳转 /drive ...")
    page.goto(f"{BASE_URL}/drive", wait_until="networkidle")
    page.wait_for_selector(".drive-sidebar", timeout=15_000)
    page.wait_for_timeout(1500)
    log("  DriveView 加载 OK")

    # 关键发现 (2026-07-11): "🌐 团队共享盘" 是 VIRTUAL 视图, 不是真实顶级 folder
    # FolderTree 在 team view 下只显示 5 个固定特殊项, 不会渲染 "组会PPT" tree
    # 所以上传流程必须:
    # 1) 先切到 team view (让 DriveUploadDialog :is-team-shared=true 生效)
    # 2) 切回 "📁 我的网盘" (specialView=null) → FolderTree 渲染组会PPT tree
    # 3) 在 tree 里选 "组会PPT" → 展开 → 选 sub folder (艾琳朔 等)
    # 4) 弹 DriveUploadDialog → 此时 :is-team-shared=true 仍生效 → 文件 is_team_shared=true

    log('  [顺序 1/3] 点 "🌐 团队共享盘" 节点 (为后面 DriveUploadDialog 拿 is-team-shared=true) ...')
    page.locator(".drive-folder-tree-special-item.is-team").click(
        force=True, position={"x": 5, "y": 5}
    )
    page.wait_for_timeout(3000)

    expect(
        page.locator(".drive-folder-tree-special-item.is-team.is-active"),
        "团队共享盘节点应有 .is-active class",
    ).to_have_count(1, timeout=5_000)
    breadcrumb = page.locator(".drive-breadcrumb")
    expect(breadcrumb, "面包屑应含 🌐 团队共享盘").to_contain_text(
        "🌐 团队共享盘", timeout=8_000
    )
    log("  [顺序 1/3] 团队共享盘 view 已激活")
    page.screenshot(
        path=str(SCREENSHOTS_DIR / "1-team-shared-initial.png"),
        full_page=False,
    )

    # 2) 切回 "📁 我的网盘" (但保持 is-team-shared state)
    #    关键: 切回 personal view 时 specialView=null, 但 DriveUploadDialog 拿的是
    #    上一次的 is-team-shared prop. 我们需要传 prop 持续 true.
    #
    #    替代方案: 直接用我的网盘 (personal view), 但 DriveUploadDialog 走的是
    #    selectedFolderId=null 时的特殊路径 (form.folderId=null 表示顶级).
    #    此时 isTeamShared prop 是 false → 文件 is_team_shared=false → 显示个人网盘
    #
    #    所以必须让 isTeamShared 保持 true. 方案:
    #    - 方案 A: 在 team view 下上传到顶级 (folder_id=null + is_team_shared=true)
    #              → 文件出现在 team view 但没分 sub folder. 然后 batch move 到 sub folder
    #    - 方案 B: 直接用 DriveUploadDialog 上传时手动选 sub folder + isTeamShared 持续 true
    #              → 需要 FolderTree 在 team view 下展开 sub folder (但前面发现不能)
    #
    #    选定方案 C: 切到 personal view 后, 在 FolderTree 里选中 sub folder → 然后 DriveUploadDialog
    #               弹时 :default-folder-id=艾琳朔.id + :is-team-shared=specialView==='team'
    #               → 但 specialView 已变 null, :is-team-shared 变 false → 还是错
    #
    #    方案 D (最稳): 走 DriveUploadDialog 但不走 UI 模拟, 而是 page.evaluate 调
    #                  axios 直接 POST /api/v1/drive/files/upload 带 is_team_shared=true
    #                  这样既走 API 又能精准控制 folder_id
    #
    #    方案 E (最终): team view 下, FileGrid 是空的 → 直接点 "上传文件" → dialog 弹
    #                  :is-team-shared=true 持续. 然后手动选目标 folder = 艾琳朔 (从 select dropdown)
    #                  → 文件落到艾琳朔 + is_team_shared=true ✅
    #    缺点: el-select 手动选 23 次 × 273 PPT = 23 次 select 操作. 可接受.

    log('  [顺序 2/3] 仍保持 team view, FileGrid 显示 team view 文件 (这里走 dialog 手动选 sub folder)')
    # 实际不需要切回 personal — 我们会在 team view 下上传, 在 dialog 里手动选 sub folder
    # 见 upload_files_to_sub_folder 修改版

    log('  [顺序 3/3] team view 状态就绪, 准备 23 轮上传')


def upload_files_to_sub_folder(page: Page, sub_name: str, sub_id: int, files: list[Path]) -> tuple[int, int]:
    """在 team shared view 下, 通过 DriveUploadDialog 上传到 sub folder.

    关键流程 (2026-07-11 新发现):
    1) team view (specialView='team') 下 FolderTree 不渲染真实 tree, 只有 5 特殊项
       → 不能用 FolderTree 选 sub folder
    2) 但 DriveUploadDialog 有 :default-folder-id="selectedFolderId" prop, 在 team view 下
       selectedFolderId=null → dialog 默认 folder_id=null (顶级)
    3) DriveUploadDialog 里有 el-select (目标文件夹), 可以手动选 sub folder
       → 我们就在 dialog 里点开 select, 选 sub folder (显示 "─ 杨慈" 等), 提交
    """
    log(f"\n--- 发言人: {sub_name} (folder_id={sub_id}, {len(files)} 个 PPT) ---")

    # 1. 验证 team view (避免被前轮操作 reset)
    team_active = page.locator(".drive-folder-tree-special-item.is-team.is-active").count()
    if team_active == 0:
        log('  重新点 "🌐 团队共享盘" 节点 ...')
        page.locator(".drive-folder-tree-special-item.is-team").click(
            force=True, position={"x": 5, "y": 5}
        )
        page.wait_for_timeout(2500)

    # 2. 点工具栏 "上传文件" (在 team view 下, dialog 拿 :is-team-shared=true)
    log('  点击 "上传文件" 按钮 ...')
    page.click("button:has-text('上传文件')")
    page.wait_for_selector(".el-dialog", timeout=5_000)
    page.wait_for_timeout(1200)  # 等 dialog 完全渲染 + fetchTree 加载 folder select

    # 验证 dialog title (团队共享盘视图下应显示 "上传到团队共享盘")
    dialog_title = page.locator(".el-dialog__title").first.text_content() or ""
    log(f'  dialog title: "{dialog_title.strip()}"')
    if "团队共享盘" not in dialog_title:
        log(f'  WARN: dialog title 不含 "团队共享盘", 可能 is-team-shared 没生效')

    # 验证团队横幅
    expect(
        page.locator(".drive-upload-team-banner"),
        "团队上传 dialog 应有团队横幅",
    ).to_be_visible(timeout=3_000)
    log("  ✓ 团队上传 dialog + 横幅显示 OK")

    # 3. 在 dialog 里手动选目标 folder = sub folder (sub_name)
    log(f'  在 dialog 内 el-select 选目标文件夹 "{sub_name}" ...')
    # el-select: 点击 input 区域打开 dropdown, 然后点击对应 option
    # form.folderId 默认是 null (顶级). 我们要选 sub_name.
    # 先点 el-select (dialog 内的, 排除其他 select)
    select_locator = page.locator('.el-dialog .el-form-item:has-text("目标文件夹") .el-select').first
    select_locator.click()
    page.wait_for_timeout(800)
    # dropdown 弹出后, 找含 sub_name 的 option
    option_locator = page.locator(
        f'.el-select-dropdown__item:has-text("{sub_name}")'
    ).first
    try:
        expect(option_locator, f'el-select option 含 "{sub_name}"').to_be_visible(timeout=3_000)
        option_locator.click()
        page.wait_for_timeout(500)
        log(f'  ✓ el-select 已选 "{sub_name}"')
    except PlaywrightTimeoutError:
        log(f'  ERROR: el-select dropdown 没找到 "{sub_name}" option')
        # 截图调试
        page.screenshot(
            path=str(SCREENSHOTS_DIR / f"debug-no-select-{sub_name}.png"),
            full_page=False,
        )
        # 关 dialog
        page.keyboard.press("Escape")
        page.wait_for_timeout(500)
        return 0, len(files)

    # 验证 select 显示了 sub_name
    selected_text = select_locator.text_content() or ""
    log(f'  当前 select 显示: "{selected_text.strip()}"')

    # 4. set_input_files 选 PPT
    #    DriveUploadDialog 的 <input> 有 webkitdirectory 属性 (Chrome/Edge),
    #    Playwright set_input_files 严格要求传 directory path 而非 file 数组.
    #    修法: 传桌面发言人子目录路径, 浏览器自动收集所有 .pptx
    dir_path = str(files[0].parent.absolute()) if files else ""
    log(f"  set_input_files 选目录: {dir_path} (含 {len(files)} 个 PPT) ...")
    file_input_sel = ".drive-upload-drop-zone input[type='file']"
    page.set_input_files(file_input_sel, dir_path)
    page.wait_for_timeout(2000)

    # 验证 file list 显示正确数量
    file_items = page.locator(".drive-upload-file-item")
    file_count_in_dialog = file_items.count()
    log(f"  dialog 显示 {file_count_in_dialog} 个待上传文件")
    if file_count_in_dialog != len(files):
        log(f"  WARN: 文件数不匹配 ({file_count_in_dialog} vs {len(files)})")
        # 截图 debug
        page.screenshot(
            path=str(SCREENSHOTS_DIR / f"debug-count-mismatch-{sub_name}.png"),
            full_page=False,
        )

    # 5. 点 "开始上传"
    log('  点 "开始上传" ...')
    # 用 el-dialog 内的 button scope 避免点错
    page.click(".el-dialog button.el-button--primary:has-text('开始上传')")

    # 6. 等所有文件上传完: dialog 1s 后自动关闭
    #    单端点顺序上传, 每个文件几秒~几十秒, N 个文件 → 数分钟
    log("  等待 dialog 关闭 (上传中, 可能数分钟) ...")
    try:
        # 等 dialog 自动消失 (uploaded 事件后 1s)
        page.wait_for_selector(".el-dialog", state="detached", timeout=600_000)  # 10 min 上限
    except PlaywrightTimeoutError:
        log(f"  ERROR: 10min 内 dialog 未关闭, 中止 {sub_name}")
        # 强制关闭 dialog
        try:
            page.keyboard.press("Escape")
            page.wait_for_timeout(500)
        except Exception:
            pass
        return 0, len(files)

    log(f"  ✓ {sub_name} dialog 已关闭 (uploaded 完成)")
    page.wait_for_timeout(2500)  # 等 dialog 关闭动画 + FileGrid 刷新

    # 截图 (上传后该 sub folder)
    page.screenshot(
        path=str(SCREENSHOTS_DIR / f"2-uploaded-{sub_name}.png"),
        full_page=False,
    )

    return len(files), 0


def verify_final_state() -> dict:
    """DB 校验最终状态: 23 sub folder PPT 总数 == 273 + root 2 PPT 不变 + 全 team shared"""
    log("\n=== 验证最终状态 ===")

    # 23 sub folder 总数
    total_sub_ppts = 0
    per_folder = {}
    for name, fid in SUB_FOLDERS.items():
        count = db_count_in_folder(fid)
        per_folder[name] = count
        total_sub_ppts += count
    log(f"  23 sub folder PPT 总数: {total_sub_ppts} (期望 273)")

    # root folder
    root_count = db_count_in_folder(336)
    log(f"  root folder 336 PPT 数: {root_count} (期望 2: 2025.9.22.pptx + 2025.6.09.pptx)")

    # 全 team shared
    team_count = int(db_query(
        "SELECT COUNT(*) FROM knowledge WHERE is_team_shared = true "
        "AND storage_mode = 'drive' AND deleted_at IS NULL"
    ))
    log(f"  全 team shared PPT 数: {team_count} (期望 275)")

    # view=personal 应不含 (sub folder 里刚传的)
    personal_count = int(db_query(
        "SELECT COUNT(*) FROM knowledge WHERE is_team_shared = false "
        "AND storage_mode = 'drive' AND deleted_at IS NULL"
    ))
    log(f"  全 personal PPT 数: {personal_count} (期望 0 或少数 root 旧 personal 文件)")

    return {
        "total_sub_ppts": total_sub_ppts,
        "root_count": root_count,
        "team_count": team_count,
        "personal_count": personal_count,
        "per_folder": per_folder,
    }


# === Main ===
def main() -> int:
    log("=== upload_ppts_playwright.py 启动 ===")
    log(f"  base_url={BASE_URL}, source_dir={SOURCE_DIR}")

    # 1. 拿 token (用于后续 init script)
    log("\n[Step 1] 拿 xiaoqi_testbot JWT token ...")
    token = get_token()
    log(f"  token_len={len(token)}, 头 30 字符={token[:30]}...")

    # 2. user_info (from /auth/me)
    user_info = requests.get(
        f"{BASE_URL}/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    ).json()
    log(f"  user: id={user_info.get('id')} username={user_info.get('username')}")

    # 3. 列桌面上每个发言人子目录下的 PPT (按 sys.argv 限定范围)
    log("\n[Step 2] 列桌面 PPT 分布 ...")
    only_speakers_dry = sys.argv[1:] if len(sys.argv) > 1 else list(DESKTOP_DIRS.keys())
    speakers_files = {}
    for speaker, dir_name in DESKTOP_DIRS.items():
        if only_speakers_dry and speaker not in only_speakers_dry:
            continue
        sd = SOURCE_DIR / dir_name
        if not sd.exists():
            log(f"  WARN: 桌面目录不存在: {sd}")
            continue
        files = sorted(sd.glob("*.pptx"))
        speakers_files[speaker] = files
        log(f"  {speaker}: {len(files)} 个 PPT")
    total_desktop_subdir = sum(len(f) for f in speakers_files.values())
    log(f"  本轮桌面 PPT 总数: {total_desktop_subdir}")

    # 4. Playwright 主流程
    log("\n[Step 3] Playwright 启动浏览器 ...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # headed 模式可见
        context = browser.new_context(viewport={"width": 1440, "height": 900})

        # 注入登录态 (init script 每次 page load 前注入 localStorage)
        inject_token_to_browser(context, token, user_info)

        page = context.new_page()

        # 5. 登录 + 跳转 (走真实 LoginView)
        log("\n[Step 4] 走 LoginView 登录 (xiaoqi_testbot) ...")
        login_then_navigate_to_drive(page)

        # 6. 进 drive → 切团队共享盘
        log("\n[Step 5] 跳转 /drive + 切团队共享盘 ...")
        navigate_to_drive_team_shared(page)

        # 7. 23 轮上传 (按 sys.argv 限定发言人, 默认全部 23 个)
        log(f"\n[Step 6] 上传 (每轮一个发言人) ...")
        only_speakers = sys.argv[1:] if len(sys.argv) > 1 else list(SUB_FOLDERS.keys())
        if only_speakers:
            log(f"  sys.argv 限定发言人: {only_speakers}")
        total_success = 0
        total_fail = 0
        per_speaker = {}
        for speaker in only_speakers:
            if speaker not in SUB_FOLDERS:
                log(f"  WARN: 未知发言人 {speaker}, 跳过")
                continue
            files = speakers_files.get(speaker, [])
            if not files:
                log(f"\n--- 发言人 {speaker}: 桌面无 PPT, 跳过 ---")
                continue
            sub_id = SUB_FOLDERS[speaker]
            success, fail = upload_files_to_sub_folder(page, speaker, sub_id, files)
            total_success += success
            total_fail += fail
            per_speaker[speaker] = (success, fail)

            # DB 实时校验: 该 sub folder 现在的 PPT 数
            current = db_count_in_folder(sub_id)
            log(f"  DB 实时: sub folder {speaker} (id={sub_id}) 现在 {current} 个 PPT")

        log(f"\n[Step 7] 23 轮上传完成: success={total_success} fail={total_fail}")

        # 8. 最终截图 (DriveView team shared view, 应看到所有 23 sub folder 都非空)
        page.wait_for_timeout(2000)
        page.screenshot(
            path=str(SCREENSHOTS_DIR / "3-final-drive-team-shared.png"),
            full_page=True,
        )
        log(f"  最终截图已存: 3-final-drive-team-shared.png")

        # 回到 root (组会PPT) 看全景
        page.locator(".drive-folder-tree-special-item.is-team").click(
            force=True, position={"x": 5, "y": 5}
        )
        page.wait_for_timeout(2000)
        page.screenshot(
            path=str(SCREENSHOTS_DIR / "4-final-team-root-view.png"),
            full_page=True,
        )

        context.close()
        browser.close()

    # 9. 最终 DB 校验
    final = verify_final_state()

    log("\n=== 总结 ===")
    log(f"  桌面 273 PPT → Drive 23 sub folder")
    log(f"  Playwright 上传 success={total_success}/{total_desktop_subdir} fail={total_fail}")
    log(f"  DB 验证: 23 sub folder 总 {final['total_sub_ppts']}/273")
    log(f"  DB 验证: root folder {final['root_count']}/2 (2 = 桌面 root PPT 已传)")
    log(f"  DB 验证: team shared total = {final['team_count']}/275")

    if final["total_sub_ppts"] != 273:
        log(f"  ❌ FAIL: sub folder 总数不符")
        return 1
    if final["team_count"] != 275:
        log(f"  ❌ FAIL: team shared 总数不符")
        return 1

    log("\n✅ 全部 273 PPT 已分到 23 发言人 sub folder (团队共享盘) + 2 root PPT 不变")
    return 0


if __name__ == "__main__":
    sys.exit(main())