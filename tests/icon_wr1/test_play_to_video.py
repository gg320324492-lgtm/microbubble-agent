"""W91-WR-1: RAGEvalPanel.vue Play → VideoPlay icon P0 修 (硬门禁).

根因: @element-plus/icons-vue v2 无 `Play` 导出 (实测 v2.3.2: Play=False,
VideoPlay=True), 导致 `npm run build` 直接 exit 1:
    "Play" is not exported by "@element-plus/icons-vue/dist/index.js"
→ 阻塞 W90-X-2 (dist health) + X-8 (prod chunk) + X-13 (vite verify) 三处。

派工 brief 偏差据实上报 (类 20.22 不照抄建议版本):
  1. brief `RAGEVAL.parents[2] / "web"` 解析为 `web/src/web` (不存在);
     RAGEVAL 是文件路径, parents[2] = web/src, 正确为 parents[3] = web/。
  2. brief `assert "Play," not in content` 恒假 —— "VideoPlay," 子串含
     "Play,", 正确代码也会 FAIL。本文件改用 \b 词边界正则。
  3. brief 称 import 在 line 24; 实测源码 line 27 (Vite 报错 24:18 是
     `<script setup>` 剥离后的偏移量, 两者一致, 非矛盾)。
"""

import re
import subprocess
from pathlib import Path

RAGEVAL = Path(__file__).resolve().parents[2] / "web" / "src" / "views" / "admin" / "RAGEvalPanel.vue"
WEB_DIR = RAGEVAL.parents[3]

# \b 词边界: 匹配裸 Play, 但不匹配 VideoPlay (前缀 o 为词字符, 边界不成立)
BARE_PLAY = re.compile(r"\bPlay\b")


def _content() -> str:
    return RAGEVAL.read_text(encoding="utf-8")


def test_ragevalpanel_exists():
    """定位锚点: 路径漂移时立刻失败, 而非静默跳过后续断言。"""
    assert RAGEVAL.is_file(), f"RAGEvalPanel.vue 未找到: {RAGEVAL}"


def test_no_bare_play_reference():
    """必无裸 Play (import 或模板用法) —— EP v2 无此导出。"""
    hits = [
        f"line {i}: {ln.strip()}"
        for i, ln in enumerate(_content().splitlines(), 1)
        if BARE_PLAY.search(ln)
    ]
    assert not hits, "P0: 残留裸 Play icon 引用 (WR-1 必修):\n" + "\n".join(hits)


def test_video_play_imported():
    """必从 icons-vue 导入 VideoPlay。"""
    content = _content()
    assert re.search(
        r"import\s*\{[^}]*\bVideoPlay\b[^}]*\}\s*from\s*['\"]@element-plus/icons-vue['\"]",
        content,
    ), "WR-1 必修: 缺 VideoPlay import"


def test_video_play_used_in_template():
    """模板必用 <VideoPlay />, 确保 import 非死代码。"""
    assert "<VideoPlay />" in _content(), "WR-1 必修: 模板未用 <VideoPlay />"


def test_sibling_icons_untouched():
    """边界守恒: 同行 Refresh / DataAnalysis 实测有效, 不得被牵连改动。"""
    content = _content()
    for icon in ("Refresh", "DataAnalysis"):
        assert icon in content, f"边界破坏: {icon} 被误改 (实测该 icon 在 EP v2 有效)"


def test_build_passes():
    """`npm run build` 唯一合法 (CLAUDE.md 永久纪律), 必 exit 0。

    Windows 注意: 默认 text=True 走 GBK 解码, Vite 的 UTF-8 输出会抛
    UnicodeDecodeError (实测 'gbk' codec can't decode 0xb7)。必须显式
    encoding="utf-8" + errors="replace"。
    """
    result = subprocess.run(
        ["npm", "run", "build"],
        cwd=WEB_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=900,
        shell=True,
    )
    assert result.returncode == 0, (
        f"build 失败 (returncode={result.returncode}):\n"
        f"--- stderr ---\n{result.stderr[-1500:]}"
    )
    # 精确断言 Play 错配已消失, 而非仅看 returncode
    combined = result.stdout + result.stderr
    assert "is not exported" not in combined, f"仍有未导出符号:\n{combined[-800:]}"
