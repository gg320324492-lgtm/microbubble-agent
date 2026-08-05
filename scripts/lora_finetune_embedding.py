"""
Qwen3 Embedding LoRA 微调脚本骨架 (W-N-F +2, plan §2 任务 F.2 步骤 1 骨架)

**严禁真跑** (派工 brief 派工铁律):
- 默认 --dry-run 强制开启, 真跑需显式 --no-dry-run (但仍 TODO 未实施)
- 派工 brief 严禁真跑 LoRA 训练 (1-2 月长跑, GPU 资源 + 训练数据未就绪)
- 1-2 月长跑任务派工时序未到

**训练目标 (派工 v6 §6 acceptance gate 沿用)**:
- embedding 召回率 ≥ 95%
- qa-bench R7/R8 benchmark verify
- 类 20.127 acceptance gate 必 raise, 不静默降级

**框架**: peft + sentence-transformers
**基座**: Qwen3-Embedding-0.6B (待 W-N-F +2 骨架实测, 派工 brief 待定)

**LoRA 配置 (peft.LoraConfig)**:
- r=16, lora_alpha=32, lora_dropout=0.05
- target_modules: ["q_proj", "v_proj"]  # Qwen3 attention
- bias="none"
- task_type=TaskType.FEATURE_EXTRACTION
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# 严禁真跑 — 默认 dry-run
DRY_RUN_DEFAULT = True

logger = logging.getLogger("microbubble.finetune.lora")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)


# ---------------------------------------------------------------------------
# 配置 dataclass
# ---------------------------------------------------------------------------


@dataclass
class LoRATrainConfig:
    """LoRA 训练配置 (派工 brief 派工起点, 后续 W-N-G+ 真跑迭代)"""

    # 基座模型
    base_model_name: str = "Qwen/Qwen3-Embedding-0.6B"  # 派工 brief 假设, 实测待定

    # 训练数据
    train_data_path: str = "data/finetune/pairs.jsonl"  # W-N-F +1 产出
    eval_data_path: Optional[str] = None  # 留口 W-N-G+ 加 eval split

    # LoRA 超参
    lora_r: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.05
    lora_target_modules: List[str] = field(default_factory=lambda: ["q_proj", "v_proj"])
    lora_bias: str = "none"

    # 训练超参
    num_epochs: int = 3
    per_device_train_batch_size: int = 16
    learning_rate: float = 2e-4
    warmup_steps: int = 100
    max_seq_length: int = 512

    # 输出
    output_dir: str = "data/finetune/lora_adapter"
    save_steps: int = 500
    eval_steps: int = 250

    # 训练模式
    dry_run: bool = DRY_RUN_DEFAULT  # 派工 brief 严禁真跑


# ---------------------------------------------------------------------------
# 配置加载
# ---------------------------------------------------------------------------


def load_config_from_env() -> LoRATrainConfig:
    """从环境变量加载覆盖 (派工 brief 派工起点, 不动 .env)"""
    cfg = LoRATrainConfig()
    if "LORA_BASE_MODEL" in os.environ:
        cfg.base_model_name = os.environ["LORA_BASE_MODEL"]
    if "LORA_DATA_PATH" in os.environ:
        cfg.train_data_path = os.environ["LORA_DATA_PATH"]
    if "LORA_OUTPUT_DIR" in os.environ:
        cfg.output_dir = os.environ["LORA_OUTPUT_DIR"]
    if "LORA_DRY_RUN" in os.environ:
        cfg.dry_run = os.environ["LORA_DRY_RUN"].lower() in ("1", "true", "yes")
    return cfg


def config_to_dict(cfg: LoRATrainConfig) -> Dict[str, Any]:
    return {
        "base_model_name": cfg.base_model_name,
        "train_data_path": cfg.train_data_path,
        "eval_data_path": cfg.eval_data_path,
        "lora_r": cfg.lora_r,
        "lora_alpha": cfg.lora_alpha,
        "lora_dropout": cfg.lora_dropout,
        "lora_target_modules": cfg.lora_target_modules,
        "lora_bias": cfg.lora_bias,
        "num_epochs": cfg.num_epochs,
        "per_device_train_batch_size": cfg.per_device_train_batch_size,
        "learning_rate": cfg.learning_rate,
        "warmup_steps": cfg.warmup_steps,
        "max_seq_length": cfg.max_seq_length,
        "output_dir": cfg.output_dir,
        "save_steps": cfg.save_steps,
        "eval_steps": cfg.eval_steps,
        "dry_run": cfg.dry_run,
    }


# ---------------------------------------------------------------------------
# 训练数据加载 (骨架, 不真跑)
# ---------------------------------------------------------------------------


def load_train_pairs(path: str) -> List[Dict[str, Any]]:
    """加载 W-N-F +1 产出的 pairs.jsonl"""
    items: List[Dict[str, Any]] = []
    p = Path(path)
    if not p.exists():
        logger.warning("训练数据文件不存在: %s", path)
        return items
    with p.open("r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError as e:
                logger.warning("line %d parse error: %s", lineno, e)
                continue
            items.append(d)
    logger.info("加载 %d pairs from %s", len(items), path)
    return items


def pairs_to_sentence_transformer_dataset(
    pairs: List[Dict[str, Any]],
) -> List[Dict[str, str]]:
    """转换为 sentence-transformers InputExample 格式

    实际训练用 sentence-transformers InputExample(texts=[query, positive_text], label=1.0)
    """
    out: List[Dict[str, str]] = []
    for p in pairs:
        out.append(
            {
                "query": p["query"],
                "positive": p.get("positive_text", ""),
            }
        )
    return out


# ---------------------------------------------------------------------------
# 训练入口 (骨架, 不真跑)
# ---------------------------------------------------------------------------


def train_lora(cfg: LoRATrainConfig) -> int:
    """LoRA 训练主入口

    **严禁真跑** (派工 brief 派工铁律):
    - cfg.dry_run = True (默认) → 仅打印计划, 不加载模型, 不跑训练
    - cfg.dry_run = False → TODO marker, 实际不实施
    """
    logger.info("=" * 60)
    logger.info("W-N-F +2 LoRA 微调 (DRY_RUN=%s)", cfg.dry_run)
    logger.info("=" * 60)
    logger.info("配置: %s", json.dumps(config_to_dict(cfg), ensure_ascii=False, indent=2))

    # 1. 加载训练数据
    pairs = load_train_pairs(cfg.train_data_path)
    if not pairs:
        logger.warning("无训练数据, 退出 (派工 brief 严禁真跑空数据训练)")
        return 1

    if cfg.dry_run:
        # 严禁真跑 — 派工 brief 派工铁律
        logger.info("DRY_RUN 模式: 仅打印训练计划, 不加载模型, 不跑训练")
        logger.info("  - 基座模型: %s", cfg.base_model_name)
        logger.info("  - 训练对数: %d", len(pairs))
        logger.info("  - LoRA r=%d alpha=%d dropout=%.2f", cfg.lora_r, cfg.lora_alpha, cfg.lora_dropout)
        logger.info("  - target_modules: %s", cfg.lora_target_modules)
        logger.info("  - num_epochs=%d lr=%.5f", cfg.num_epochs, cfg.learning_rate)
        logger.info("  - output_dir: %s", cfg.output_dir)
        logger.info("  - 真跑实施 TODO: peft + sentence-transformers + trainer.train()")
        logger.info("=" * 60)
        logger.info("W-N-F +2 骨架完成, 等待 W-N-G+ 派工真跑")
        return 0

    # 2. 真跑逻辑 — TODO 不实施 (派工 brief 严禁, 1-2 月长跑)
    logger.error("真跑 LoRA 训练未实施 (派工 brief 严禁, 1-2 月长跑, 派工时序未到)")
    logger.error("如需真跑, 请派 W-N-G+ 工时并准备 GPU 资源")
    raise NotImplementedError(
        "W-N-F +2 仅产出骨架, 真跑 LoRA 训练派工 brief 严禁, 1-2 月长跑"
    )


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Qwen3 LoRA 微调脚本 (W-N-F +2 骨架)")
    parser.add_argument(
        "--config",
        default=None,
        help="可选: JSON 配置文件路径 (派工 brief 派工起点, 后续 W-N-G+ 加)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=DRY_RUN_DEFAULT,
        help="DRY_RUN 模式 (默认开启, 派工 brief 严禁真跑)",
    )
    parser.add_argument(
        "--no-dry-run",
        action="store_false",
        dest="dry_run",
        help="关闭 DRY_RUN (派工 brief 严禁, 真跑 TODO 不实施)",
    )
    args = parser.parse_args(argv)

    # 加载配置
    cfg = load_config_from_env()
    cfg.dry_run = args.dry_run

    if args.config:
        with open(args.config, "r", encoding="utf-8") as f:
            overrides = json.load(f)
        for k, v in overrides.items():
            if hasattr(cfg, k):
                setattr(cfg, k, v)
            else:
                logger.warning("未知配置字段: %s = %s", k, v)

    return train_lora(cfg)


if __name__ == "__main__":
    sys.exit(main())
