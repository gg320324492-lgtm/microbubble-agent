"""
tests/a11y_login_x18/test_authed_field.py — W91-X-18 a11y baseline 真登录态门禁

W89-P-6 + W89-X-29 + W90-X-14 据实 3 次报告: 25 份 baseline 全部
`authed: no / violations: 0` — 扫的是登录页 (router 守卫重定向), 全绿是**假绿信号**
(类 20.25 "a11y 测试必先 baseline, 全绿是可疑信号" + 类 20.84 "a11y baseline 必入 git
+ 必在登录态生成").

根因: web/tests/visual/a11y/axe-config.mjs:injectAuth() 在 TEST_TOKEN 缺失时
`return false` 静默走匿名态, 上层 spec 照常写 snapshot → baseline 永远是登录页。

本任务 (W91-X-18) 用真 TEST_TOKEN (POST /api/v1/auth/login 拿到的真 JWT) 重录 25 份
baseline, 本文件是防回退守卫: 任何人再用匿名态 --update-snapshots 都会被这 2 个断言拦下。

派工 v6 §5 反馈 类 20.84 加固:
"a11y baseline 必入 git + 必在登录态生成 + 守卫脚本 `authed: yes` 必现"
"""

import re
from pathlib import Path

SNAPSHOT_DIR = (
    Path(__file__).resolve().parents[2]
    / "web"
    / "tests"
    / "visual"
    / "a11y"
    / "__snapshots__"
)


def test_baseline_files_have_authed_yes():
    """a11y baseline 必含 'authed: yes' (登录态真数据, 非登录页假绿)"""
    files = sorted(SNAPSHOT_DIR.glob("*.txt"))
    assert files, f"无 baseline: {SNAPSHOT_DIR} 下 0 个 .txt"

    offenders = []
    for f in files:
        content = f.read_text(encoding="utf-8")
        if "authed: yes" not in content:
            offenders.append(f.name)

    assert not offenders, (
        f"{len(offenders)}/{len(files)} baseline 仍 authed: no — 假绿信号 "
        f"(类 20.25 / 20.84). 重录方法: "
        f"TEST_TOKEN=<真 JWT> npx playwright test -c tests/visual/a11y/"
        f"playwright.a11y.config.mjs --update-snapshots. 违规文件: {offenders[:5]}"
    )


def test_baseline_files_not_redirected_to_login():
    """a11y baseline 不得是登录页快照 (redirected-to-login: no 必现)"""
    files = sorted(SNAPSHOT_DIR.glob("*.txt"))
    assert files, f"无 baseline: {SNAPSHOT_DIR}"

    offenders = [
        f.name
        for f in files
        if "redirected-to-login: yes" in f.read_text(encoding="utf-8")
    ]
    assert not offenders, (
        f"{len(offenders)} baseline 是登录页快照 (router 守卫重定向), "
        f"不是目标页面 a11y 数据. 违规文件: {offenders[:5]}"
    )


def test_baseline_files_have_real_violations():
    """a11y baseline 必含合法 violations 段 (格式 + 真登录态非全 0)"""
    files = sorted(SNAPSHOT_DIR.glob("*.txt"))
    assert len(files) >= 25, f"期望 ≥ 25 baseline, 实际 {len(files)}"

    zero_count = 0
    for f in files:
        content = f.read_text(encoding="utf-8")
        m = re.search(r"^violations: (\d+)$", content, re.MULTILINE)
        assert m, f"{f.name} 缺 'violations: N' 行 — baseline 格式异常"

        n = int(m.group(1))
        if n == 0:
            zero_count += 1
            continue

        # violations > 0 时必列出 N 条 `  <rule-id> [<impact>] ×<nodes>` 明细
        rules = re.findall(r"^  (\S+) \[(\w+)\] ×(\d+)$", content, re.MULTILINE)
        assert len(rules) == n, (
            f"{f.name} 声明 violations: {n} 但明细 {len(rules)} 行 — 格式不一致"
        )

    # 真登录态下 25 份全 0 = 极可能又扫到了登录页/空白页 (类 20.25 可疑信号)
    # S3.20: 本断言被替换, 见文件末尾 test_baseline_render_evidence_* ——
    # "violations == 0" 无法区分"空白页"与"真修好的页" (实测两者都是 0),
    # 原断言因此在两个方向都误判过 (git 物证见新用例上方注释)。
    assert zero_count <= len(files), "zero_count 不可能超过总数 (防御性断言)"


# ---------------------------------------------------------------------------
# S3.20 替换断言: 用**渲染证据**判定"扫的是真实页面", 不再用 violations 计数
# ---------------------------------------------------------------------------
#
# 被替换的原断言 (本文件原 line 89-93):
#     assert zero_count < len(files), "全绿是可疑信号"
# 它把 "violations == 0" 当成"扫到了空白页/登录页"的证据。这个推理是**错的**,
# 且在两个方向都误判过 (两个方向都有 git 物证):
#
#   1. S3.20 本地实测 (app-test:8001 + vite + 真 JWT, 5 页面 x 5 project):
#        真实内容页   -> violations = 0
#        **空白页**   -> violations = 0   <-- 与真实页**同形**!
#        登录页       -> violations = 1   (color-contrast .gate__no, 2 轮实测稳定)
#      空白页与"真修好的页"在 violations 上无法区分, 故原断言**抓不到空白页假绿**。
#   2. 真实全 0 曾被它误判为假绿而改回非 0: 7b8ea2b0d 录成 sum=0,
#      1ae5699ad 又把 10 个文件从 0 改回 1; 反向 84d8d090b 才把修复后的真实 0
#      录回去。即它在"真 0 被当假绿"与"假 0 被当真绿"两边都误判过。
#
# 新判据 = **逐文件核对渲染证据**, 判别力来自实测标定 (S3.20, 见下表):
#
#   场景              violations   render-evidence (正文:可见元素)
#   ---------------- -----------  -------------------------------
#   登录页(桌面)          1           272 : 50
#   登录页(移动)          1            75 : 26
#   空白页                0             0 : 0     <-- 原断言漏掉的假绿
#   真实页(最小)          0            68 : 66
#   真实页(最大)          0           476 : 240
#
# 可见元素数是有判别力的那一维: 登录页 50/26 < 真实页最小 55 < 真实页最大 240,
# 空白页 0。正文长度**单独不可用** (登录页 272 > 真实页 88), 两者**成对**才有判别力。
#
# 本断言查的是"入库证据是否等于实测标定的真实页面证据", 因此:
#   - 有人用登录页/空白页 --update-snapshots 重录 -> 证据对不上 -> 红 (有牙)
#   - 页面真改版导致证据漂移 -> 红, 提示重新标定 (这正是门禁该报的漂移)
#   - 违规真修好了 (violations 0) -> 证据不变 -> 绿 (不再误报)
EXPECTED_RENDER_EVIDENCE = {
    # 桌面视口 (desktop-chrome / desktop-comments, 均 1280 宽)
    "01-chat": "468:224",
    "02-drive": "476:239",
    "03-mobile-chat": "468:224",
    "04-task-trash": "232:103",
    "05-file-comments": "295:137",
    # 窄视口 (mobile-iphone14 390 / mobile-comments 390 / harmonyos-arkweb 720)
    "01-chat-narrow": "129:104",
    "02-drive-narrow": "88:74",
    "03-mobile-chat-narrow": "129:104",
    "04-task-trash-narrow": "71:55",
    "05-file-comments-narrow": "68:66",
}

# 5 个 project 中 desktop-chrome 与 desktop-comments 同为 1280 视口,
# 实测证据值逐字符一致**除 02-drive 外** —— desktop-chrome 记 239、
# desktop-comments 记 240, 连续 3 轮实测稳定 (DPR/滚动条差异, 非噪声),
# 故 02-drive 按 project 分列, 其余桌面页共用一个值。
# mobile-iphone14 / mobile-comments / harmonyos-arkweb 同为窄视口, 三者全等。
NARROW_PROJECTS = {"mobile-iphone14", "mobile-comments", "harmonyos-arkweb"}

# 唯一需要按 project 区分的页面 (实测 3 轮稳定, 非抖动)
PER_PROJECT_EVIDENCE = {
    ("02-drive", "desktop-chrome"): "476:239",
    ("02-drive", "desktop-comments"): "476:240",
}


def test_baseline_render_evidence_matches_real_pages():
    """逐文件核对渲染证据 = 实测标定的真实页面证据 (登录页/空白页必对不上)"""
    files = sorted(SNAPSHOT_DIR.glob("*.txt"))
    assert len(files) >= 25, f"期望 >= 25 baseline, 实际 {len(files)}"

    offenders = []
    for f in files:
        content = f.read_text(encoding="utf-8")

        ev = re.search(r"^render-evidence: (\d+):(\d+)$", content, re.MULTILINE)
        assert ev, (
            f"{f.name} 缺 'render-evidence: <正文>:<可见元素>' 行 - "
            f"baseline 格式异常 (S3.20 起必录, 缺行即无法证明扫的是真实页面)"
        )
        actual = f"{ev.group(1)}:{ev.group(2)}"

        page_name = re.search(r"^page: (\S+)", content, re.MULTILINE)
        project = re.search(r"^project: (\S+)", content, re.MULTILINE)
        assert page_name, f"{f.name} 缺 'page:' 行"
        assert project, f"{f.name} 缺 'project:' 行"

        key = page_name.group(1)
        per_project = PER_PROJECT_EVIDENCE.get((key, project.group(1)))
        if per_project is not None:
            expected = per_project
        else:
            if project.group(1) in NARROW_PROJECTS:
                key = f"{key}-narrow"
            expected = EXPECTED_RENDER_EVIDENCE.get(key)
        assert expected, f"{f.name} 未知页面/项目组合 {key} - 更新标定表时先确认"

        if actual != expected:
            offenders.append(f"{f.name}: 记录 {actual} != 实测 {expected}")

    assert not offenders, (
        f"{len(offenders)}/{len(files)} baseline 的 render-evidence 与实测真实页面不符 - "
        f"极可能又录到了登录页/空白页 (类 20.25 / 20.84)。实测标定: "
        f"登录页 272:50(桌面)/75:26(移动), 空白页 0:0, 真实页最小 68:66。"
        f" 重录方法: TEST_TOKEN=<真 JWT> npx playwright test -c tests/visual/a11y/"
        f"playwright.a11y.config.mjs --update-snapshots. 违规文件: {offenders[:5]}"
    )


def test_baseline_render_evidence_is_not_blank_or_login():
    """渲染证据不得是空白页或登录页的取值 (独立于标定表的第二道牙)"""
    # 实测标定 (S3.20): 空白页 0:0; 登录页 272:50(桌面) / 75:26(移动)
    login_pairs = {"272:50", "75:26"}
    offenders = []
    for f in sorted(SNAPSHOT_DIR.glob("*.txt")):
        content = f.read_text(encoding="utf-8")
        ev = re.search(r"^render-evidence: (\d+):(\d+)$", content, re.MULTILINE)
        if not ev:
            continue  # 缺行由上一个用例负责报错
        text_len, visible = int(ev.group(1)), int(ev.group(2))
        if text_len == 0 or visible == 0:
            offenders.append(f"{f.name}: 空白页证据 {text_len}:{visible}")
        elif f"{text_len}:{visible}" in login_pairs:
            offenders.append(f"{f.name}: 登录页证据 {text_len}:{visible}")

    assert not offenders, (
        f"{len(offenders)} baseline 的渲染证据是空白页或登录页 - 假绿 "
        f"(类 20.25 / 20.84). 违规文件: {offenders[:5]}"
    )