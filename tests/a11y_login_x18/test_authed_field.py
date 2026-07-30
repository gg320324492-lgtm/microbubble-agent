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
    assert zero_count < len(files), (
        f"{len(files)}/{len(files)} baseline violations = 0 — 全绿是可疑信号 "
        f"(类 20.25). 真登录态 5 页面不可能 0 a11y 问题, 请核查 TEST_TOKEN 是否真注入."
    )
