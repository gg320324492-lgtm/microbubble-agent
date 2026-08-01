"""W100-RAG-5 fifth-path weight configuration tests (15 cases)."""
from __future__ import annotations

import textwrap

import pytest

from app.services.hybrid_weight_config import (
    HybridABConfig,
    HybridWeights,
    apply_weights,
    load_ab_config_from_yaml,
    load_weights_from_yaml,
)


def test_image_default_value():
    assert HybridWeights().image == 0.15


def test_from_dict_missing_image_uses_default():
    assert HybridWeights.from_dict({"vector": 0.7}).image == 0.15


def test_to_dict_contains_image():
    assert HybridWeights().to_dict()["image"] == 0.15


def test_image_negative_rejected_by_post_init_whitelist():
    with pytest.raises(ValueError, match="image"):
        HybridWeights(image=-0.01)


def test_image_non_numeric_rejected_by_post_init_whitelist():
    with pytest.raises(ValueError, match="image"):
        HybridWeights(image="bad")  # type: ignore[arg-type]


def test_image_zero_is_allowed():
    assert HybridWeights(image=0.0).image == 0.0


def test_apply_weights_accepts_image_method():
    out = apply_weights({"image": [{"id": 1, "score": 0.9}]}, HybridWeights())
    assert out[0]["retrieval_methods"] == ["image"]


def test_apply_weights_image_zero_is_ignored():
    out = apply_weights(
        {"image": [{"id": 1, "score": 0.9}]},
        HybridWeights(image=0.0),
    )
    assert out == []


def test_apply_weights_accumulates_image_with_vector():
    out = apply_weights(
        {
            "vector": [{"id": 1, "score": 0.9}],
            "image": [{"id": 1, "score": 0.8}],
        },
        HybridWeights(),
    )
    assert set(out[0]["retrieval_methods"]) == {"vector", "image"}


def test_yaml_weights_load_image(tmp_path):
    path = tmp_path / "weights.yaml"
    path.write_text("weights:\n  image: 0.27\n", encoding="utf-8")
    assert load_weights_from_yaml(str(path)).image == 0.27


def test_yaml_weights_missing_image_uses_default(tmp_path):
    path = tmp_path / "weights.yaml"
    path.write_text("weights:\n  vector: 0.8\n", encoding="utf-8")
    assert load_weights_from_yaml(str(path)).image == 0.15


def test_yaml_weights_invalid_image_falls_back(tmp_path):
    path = tmp_path / "weights.yaml"
    path.write_text("weights:\n  image: -1\n", encoding="utf-8")
    assert load_weights_from_yaml(str(path)) == HybridWeights()


def test_ab_config_default_groups_have_image():
    config = HybridABConfig()
    assert config.config_a.image == 0.15
    assert config.config_b.image == 0.15


def test_ab_config_yaml_loads_image_for_both_groups(tmp_path):
    path = tmp_path / "weights.yaml"
    path.write_text(
        textwrap.dedent(
            """
            ab_config:
              enabled: true
              config_a: {vector: 0.4, image: 0.11}
              config_b: {vector: 0.3, image: 0.22}
            """
        ),
        encoding="utf-8",
    )
    config = load_ab_config_from_yaml(str(path))
    assert config.config_a.image == 0.11
    assert config.config_b.image == 0.22


def test_ab_pick_bucket_preserves_image_weight():
    config = HybridABConfig(
        enabled=False,
        config_a=HybridWeights(image=0.33),
        config_b=HybridWeights(image=0.44),
    )
    assert config.pick_bucket("user").image == 0.33
