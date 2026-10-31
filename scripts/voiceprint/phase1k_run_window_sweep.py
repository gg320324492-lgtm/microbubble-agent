"""Phase 1k: 窗口长度 / 重叠率敏感性 —— 串行跑多档滑窗 (容器内 bash 驱动)。

为什么做这一格
--------------
滑窗是**唯一活着的杠杆** (Phase 1h: 聚类的输入单元)。
⇒ 它的两个参数 (窗长 / 重叠率) 值得量一下 —— 但只是**测量**:
   改生产参数会改 member_spans ⇒ 旧裁决全失效 ⇒ 推翻人工命名 (那是另一件事)。

⚠️ **串行**: 一次只跑一档 ⇒ 不抢显存 (类 20.213 的教训: 并行 GPU 任务互相干扰)。

档位 (基线 1.5s/50% 已有, 不重跑):
    win=1.0 hop=0.5   (50% 重叠, 窗更短)
    win=2.0 hop=1.0   (50% 重叠, 窗更长)
    win=1.5 hop=0.375 (75% 重叠)
    win=1.5 hop=1.125 (25% 重叠)

输出 (每档一个目录 /tmp/vp/phase1k/w{win}_h{hop}/):
    emb_sw.npy / meta_sw.json / identity_check.json
"""
import os
import subprocess
import sys
import time

BASE = "/tmp/vp/phase1k"
SCRIPT = "/tmp/vp/phase1k_window_sensitivity.py"
SETTINGS = [
    (1.0, 0.5),
    (2.0, 1.0),
    (1.5, 0.375),
    (1.5, 1.125),
]


def main():
    os.makedirs(BASE, exist_ok=True)
    for win, hop in SETTINGS:
        out = os.path.join(BASE, "w%g_h%g" % (win, hop))
        if os.path.exists(os.path.join(out, "emb_sw.npy")):
            print("[phase1k] %s 已存在 ⇒ 跳过" % out, flush=True)
            continue
        print("[phase1k] === 开始 win=%.3f hop=%.3f ===" % (win, hop), flush=True)
        t0 = time.time()
        p = subprocess.run(
            [sys.executable, SCRIPT,
             "--phase1", "/tmp/vp/phase1", "--out", out,
             "--win", str(win), "--hop", str(hop)],
            capture_output=True, text=True)
        tail = (p.stdout or "")[-800:]
        print(tail, flush=True)
        if p.returncode != 0:
            print("[phase1k] ❌ win=%g hop=%g 失败 rc=%d\n%s"
                  % (win, hop, p.returncode, (p.stderr or "")[-1500:]), flush=True)
            continue
        print("[phase1k] ✅ win=%g hop=%g 用时 %.0f 秒"
              % (win, hop, time.time() - t0), flush=True)
    print("[phase1k] 全部完成", flush=True)


if __name__ == "__main__":
    main()
