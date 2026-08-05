"""Lightweight late-chunking benchmark using deterministic mock embeddings."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.late_chunking_service import LateChunkingService


class MockModel:
    class tokenizer:
        def __call__(self, text: str, **kwargs: Any) -> Dict[str, np.ndarray]:
            n = max(1, len(text) // 4)
            return {"attention_mask": np.ones((1, n), dtype=np.int64)}

    def forward(self, inputs: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
        n = inputs["attention_mask"].shape[1]
        return {"token_embeddings": np.ones((1, n, 1024), dtype=np.float32)}


def run_benchmark() -> Dict[str, Any]:
    service = LateChunkingService(MockModel(), chunk_size=256, overlap=32)
    docs = [(f"doc-{i}", ("微纳米气泡 ζ 电位与传质研究。" * 180)) for i in range(5)]
    queries = ["微纳米气泡 ζ 电位", "气泡传质", "界面科学", "水处理", "实验方法"]
    rows: List[Dict[str, Any]] = []
    for (doc_id, text), query in zip(docs, queries):
        vectors = service.encode(text)
        parent_score = float(np.dot(np.ones(1024), np.ones(1024)))
        chunk_score = max(float(np.dot(np.ones(1024), vector)) for vector in vectors)
        rows.append({"doc_id": doc_id, "query": query, "chunk_count": len(vectors),
                     "parent_score": parent_score, "chunk_late_score": chunk_score})
    return {"mock": True, "documents": 5, "queries": 5, "rows": rows}


def main() -> None:
    parser = argparse.ArgumentParser(description="Late chunking long-document benchmark")
    parser.add_argument("--output", default="results/late_chunking_bench_2026-08.json")
    args = parser.parse_args()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(run_benchmark(), ensure_ascii=False, indent=2), encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
