"""Late chunking over one long-context embedding pass.

The service deliberately depends only on a model exposing ``tokenizer`` and
``forward``.  This keeps unit tests lightweight and permits an injected
bge-m3/SentenceTransformer adapter in production.
"""
from __future__ import annotations

from typing import Any, List

import numpy as np


class LateChunkingService:
    """Encode a document once, then mean-pool overlapping token windows."""

    def __init__(self, model: Any, chunk_size: int = 256, overlap: int = 32, max_length: int = 8192):
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if overlap < 0 or overlap >= chunk_size:
            raise ValueError("overlap must be >= 0 and < chunk_size")
        if max_length <= 0:
            raise ValueError("max_length must be positive")
        self._model = model
        self._chunk_size = chunk_size
        self._overlap = overlap
        self._max_length = max_length

    def encode(self, text: str) -> List[np.ndarray]:
        """Return one float32 vector per token window, preserving context."""
        if not text:
            return []
        tokenizer = self._model.tokenizer
        if isinstance(tokenizer, type):
            tokenizer = tokenizer()
        inputs = tokenizer(
            text, return_tensors="pt", truncation=True, max_length=self._max_length
        )
        mask = inputs.get("attention_mask") if hasattr(inputs, "get") else None
        output = self._model.forward(inputs)
        token_embeddings = (
            output.get("token_embeddings") if hasattr(output, "get") else output.token_embeddings
        )
        if hasattr(token_embeddings, "detach"):
            token_embeddings = token_embeddings.detach()
        if hasattr(mask, "detach"):
            mask = mask.detach()
        embeddings = np.asarray(token_embeddings)
        masks = np.asarray(mask) if mask is not None else np.ones(embeddings.shape[:2], dtype=np.float32)
        if embeddings.ndim != 3 or embeddings.shape[0] < 1:
            raise ValueError("model token_embeddings must have shape (batch, tokens, dimensions)")
        token_count = min(embeddings.shape[1], masks.shape[1])
        step = self._chunk_size - self._overlap
        vectors: List[np.ndarray] = []
        for start in range(0, token_count, step):
            end = min(start + self._chunk_size, token_count)
            weights = masks[0, start:end].astype(np.float32)
            if not np.any(weights):
                continue
            values = embeddings[0, start:end].astype(np.float32, copy=False)
            pooled = (values * weights[:, None]).sum(axis=0) / weights.sum()
            vectors.append(np.asarray(pooled, dtype=np.float32))
            if end >= token_count:
                break
        return vectors
