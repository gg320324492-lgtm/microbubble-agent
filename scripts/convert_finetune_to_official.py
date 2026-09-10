# -*- coding: utf-8 -*-
"""将 data/asr_finetune/{db*,meeting083} 的训练对合并转换为官方 lora_finetune 格式

输出: data/asr_finetune/train_v1/{i}.wav + {i}.json
json: {"audio_duration", "audio_path", "segments":[{speaker,text,start,end}],
       "customized_context": [热词...]}
"""
import json
import shutil
from pathlib import Path

BASE = Path(r"E:\microbubble-agent")
ROOT = BASE / "data" / "asr_finetune"
OUT = ROOT / "train_v1"
HOTWORDS = ["微纳米气泡", "UV臭氧氧化", "臭氧", "纳米气泡发生器", "空化效应",
            "Zeta电位", "表面张力", "养殖尾水处理", "气浮", "基底", "ESG",
            "国家奖", "王天志", "杜同贺", "杨慈", "陈金薪", "贾琦", "周之超",
            "张宏魁", "吴孟铨", "韩重阳", "宋洋"]

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    idx = 0
    stats = {}
    for d in sorted(ROOT.iterdir()):
        if not d.is_dir() or d.name == OUT.name:
            continue
        manifest = d / "_manifest.json"
        if not manifest.exists():
            continue
        entries = json.loads(manifest.read_text(encoding="utf-8"))
        cnt = 0
        for m in entries:
            src_wav = d / m["file"]
            src_json = d / (m["file"].replace(".wav", ".json"))
            if not src_wav.exists() or not src_json.exists():
                continue
            meta = json.loads(src_json.read_text(encoding="utf-8"))
            text = meta["transcript"][0]["content"]
            dur = m["sec"]
            new_wav = OUT / f"{idx}.wav"
            shutil.copyfile(src_wav, new_wav)
            (OUT / f"{idx}.json").write_text(json.dumps({
                "audio_duration": dur,
                "audio_path": f"{idx}.wav",
                "segments": [{"speaker": 0, "text": text,
                              "start": 0.0, "end": round(dur, 2)}],
                "customized_context": HOTWORDS,
            }, ensure_ascii=False, indent=1), encoding="utf-8")
            idx += 1
            cnt += 1
        stats[d.name] = cnt
        print(f"{d.name}: {cnt} 对")
    total_sec = None
    print(f"\n总计: {idx} 样本 → {OUT}")
    print(json.dumps(stats, ensure_ascii=False))


if __name__ == "__main__":
    main()
