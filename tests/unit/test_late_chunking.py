"""Unit tests for late chunking with a deterministic token-level mock."""
import numpy as np

from app.services.late_chunking_service import LateChunkingService


class MockModel:
    class tokenizer:
        @staticmethod
        def __call__(text, **kwargs):
            count = len(text.split())
            return {
                "input_ids": np.zeros((1, count), dtype=np.int64),
                "attention_mask": np.ones((1, count), dtype=np.int64),
            }

    def forward(self, inputs):
        count = inputs["input_ids"].shape[1]
        values = np.arange(count * 4, dtype=np.float32).reshape(1, count, 4)
        return {"token_embeddings": values}


def test_late_chunking_returns_overlapping_windows():
    vectors = LateChunkingService(MockModel(), chunk_size=4, overlap=1).encode("a b c d e f")
    assert len(vectors) == 2
    assert all(vector.shape == (4,) and vector.dtype == np.float32 for vector in vectors)


def test_late_chunking_applies_attention_mask():
    class Masked(MockModel):
        class tokenizer:
            @staticmethod
            def __call__(text, **kwargs):
                return {"attention_mask": np.array([[1, 1, 0]], dtype=np.int64)}

        def forward(self, inputs):
            return {"token_embeddings": np.array([[[2, 2], [4, 4], [100, 100]]], dtype=np.float32)}

    vectors = LateChunkingService(Masked(), chunk_size=3, overlap=0).encode("a b c")
    np.testing.assert_allclose(vectors[0], [3, 3])
