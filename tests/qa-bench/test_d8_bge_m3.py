"""Four end-to-end policy scenarios for W71 C-1 qa-bench D8."""

from __future__ import annotations

import pytest

from d8_bge_m3 import (
    d5_d8_route_status,
    d8_r8_bge_m3_rerank,
    d8_r9_production_rollout,
)


ANSWERS = ["answer-a", "answer-b", "answer-c"]
BENCHMARK = {
    "candidate_answers": ANSWERS,
    "candidate_scores_7d": [0.40, 0.95, 0.60],
}


@pytest.mark.asyncio
async def test_scenario_1_matching_top_1_selects_production() -> None:
    async def matching_reranker(_question: str, _answers: list[str]) -> list[int]:
        return [1, 2, 0]

    result = await d8_r8_bge_m3_rerank(
        "How should BGE m3 rank these answers?",
        ANSWERS,
        BENCHMARK,
        rerank=matching_reranker,
    )

    assert result["decision"] == "production"
    assert result["bge_m3_enabled"] is True
    assert result["agreement_rate"] == 1.0
    assert result["bge_top_index"] == result["seven_d_top_index"] == 1


@pytest.mark.asyncio
async def test_scenario_2_mismatching_top_1_selects_gradual() -> None:
    async def mismatching_reranker(_question: str, _answers: list[str]) -> list[int]:
        return [2, 1, 0]

    result = await d8_r8_bge_m3_rerank(
        "How should BGE m3 rank these answers?",
        ANSWERS,
        BENCHMARK,
        rerank=mismatching_reranker,
    )

    assert result["decision"] == "gradual"
    assert result["bge_m3_enabled"] is False
    assert result["agreement_rate"] == 0.0
    assert result["bge_top_index"] == 2
    assert result["seven_d_top_index"] == 1


@pytest.mark.asyncio
async def test_scenario_3_completes_200_question_rollout() -> None:
    result = await d8_r9_production_rollout(sample_size=200)

    assert result == {
        "rollout": "completed",
        "sample_size": 200,
        "duration": "7d",
        "bge_m3_enabled": True,
        "seven_dim_scoring": True,
    }


def test_scenario_4_d5_d8_route_is_connected() -> None:
    status = d5_d8_route_status()

    assert status["connected"] is True
    assert len(status["dashboard_cards"]) == 3
    assert status["ci_gates"] == ["pass_rate_80_percent"]
    assert [stage.split()[0] for stage in status["route"]] == ["D5", "D6", "D7", "D8"]
