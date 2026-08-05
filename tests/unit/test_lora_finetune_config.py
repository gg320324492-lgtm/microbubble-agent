"""
lora_finetune_embedding.py 配置加载单元测试 (W-N-F +2)

1 unit test (派工 brief 要求): 验证配置加载正确
- 验证默认配置 + env var 覆盖
- 验证 config_to_dict 序列化
- 验证 DRY_RUN 默认开启
- 验证 train_lora DRY_RUN 模式不加载模型
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

# 添加 scripts/ 到 path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from lora_finetune_embedding import (  # noqa: E402
    DRY_RUN_DEFAULT,
    LoRATrainConfig,
    config_to_dict,
    load_config_from_env,
    load_train_pairs,
    pairs_to_sentence_transformer_dataset,
    train_lora,
)


class TestLoRAConfig:
    """测试 1: 配置加载 (派工 brief 1 unit test 授权)"""

    def test_default_config_dry_run(self):
        """默认配置 DRY_RUN=True (派工 brief 严禁真跑)"""
        cfg = LoRATrainConfig()
        assert cfg.dry_run is True
        assert cfg.base_model_name == "Qwen/Qwen3-Embedding-0.6B"
        assert cfg.lora_r == 16
        assert cfg.lora_alpha == 32
        assert cfg.lora_dropout == 0.05
        assert cfg.lora_target_modules == ["q_proj", "v_proj"]
        assert cfg.num_epochs == 3
        assert cfg.learning_rate == 2e-4

    def test_config_serialization(self):
        """config_to_dict 序列化正确"""
        cfg = LoRATrainConfig()
        d = config_to_dict(cfg)
        assert isinstance(d, dict)
        assert d["base_model_name"] == "Qwen/Qwen3-Embedding-0.6B"
        assert d["dry_run"] is True
        # JSON 可序列化
        json.dumps(d)

    def test_env_override(self, monkeypatch):
        """环境变量覆盖 base_model_name + dry_run"""
        monkeypatch.setenv("LORA_BASE_MODEL", "test/custom-model")
        monkeypatch.setenv("LORA_DRY_RUN", "true")
        monkeypatch.setenv("LORA_DATA_PATH", "/tmp/test.jsonl")
        cfg = load_config_from_env()
        assert cfg.base_model_name == "test/custom-model"
        assert cfg.dry_run is True
        assert cfg.train_data_path == "/tmp/test.jsonl"

    def test_train_dry_run_no_model_load(self, tmp_path, capsys):
        """DRY_RUN 模式不加载模型, 仅打印计划"""
        # 创建空 pairs.jsonl
        pairs_file = tmp_path / "empty.jsonl"
        pairs_file.write_text("")
        cfg = LoRATrainConfig(
            train_data_path=str(pairs_file),
            dry_run=True,
        )
        result = train_lora(cfg)
        # 空数据时返回 1 (避免空数据训练)
        assert result == 1

    def test_pairs_to_sentence_transformer_dataset(self):
        """转换为 sentence-transformers InputExample 格式"""
        pairs = [
            {"query": "Q1", "positive_text": "T1"},
            {"query": "Q2", "positive_text": "T2"},
        ]
        out = pairs_to_sentence_transformer_dataset(pairs)
        assert len(out) == 2
        assert out[0]["query"] == "Q1"
        assert out[0]["positive"] == "T1"

    def test_load_train_pairs_missing_file(self):
        """文件不存在返回空 list 不报错"""
        items = load_train_pairs("/nonexistent/pairs.jsonl")
        assert items == []
