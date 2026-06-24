"""Qwen3 Embedder - LLM-based embedding via HuggingFace transformers

为什么需要这个文件：
- sentence-transformers==2.3.1 不支持 LLM-based embedding 的 last-token pooling
- Qwen3-Embedding-0.6B 是基于 Qwen3-0.6B LLM 的 embedding 模型
- 必须用 transformers.AutoModel + trust_remote_code + 自定义 last-token pooling

替代 sentence-transformers 的 SentenceTransformer.encode 调用：
- 用法兼容：encode([text]) -> np.ndarray, dim=1024, normalized
- 显存占用：~1.2GB fp16 (Qwen3-Embedding-0.6B)
- 推理速度：GPU ~30-80ms/单条，批量更优
"""

import asyncio
import logging
import os
from typing import List, Optional

import numpy as np
import torch

logger = logging.getLogger("microbubble.qwen_embedder")

# Qwen3 官方推荐的检索指令前缀（用于 query embedding）
QWEN3_QUERY_INSTRUCTION = "为这个句子生成表示以用于检索相关文章"


class Qwen3Embedder:
    """LLM-based embedding wrapper for Qwen3-Embedding 系列.

    模型: Qwen/Qwen3-Embedding-0.6B (1024d, ~600M 参数, fp16 ~1.2GB)
    替换方案: 也支持 Qwen3-Embedding-8B (4096d, 16GB) 但需要显存充足

    用法:
        embedder = Qwen3Embedder("Qwen/Qwen3-Embedding-0.6B", device="cuda")
        vec = embedder.encode(["微纳米气泡"])[0]  # shape (1024,), normalized
        batch_vecs = embedder.encode(["句子1", "句子2"])  # shape (2, 1024)
    """

    def __init__(
        self,
        model_name: str = "Qwen/Qwen3-Embedding-0.6B",
        device: str = "cuda",
        max_length: int = 2048,
        torch_dtype: torch.dtype = torch.float16,
    ):
        """加载 Qwen3 embedding 模型到 GPU.

        Args:
            model_name: HuggingFace 模型路径 (e.g. "Qwen/Qwen3-Embedding-0.6B")
            device: "cuda" 或 "cpu"
            max_length: 单条最大 token 数 (默认 2048, 满足大部分文档)
            torch_dtype: 模型精度, fp16 节省显存 (1.2GB), fp32 需 2.4GB
        """
        # 延迟 import 避免在 sentence-transformers 路径下加载 transformers (节省启动时间)
        from transformers import AutoModel, AutoTokenizer

        self.model_name = model_name
        self.device = device
        self.max_length = max_length

        logger.info(f"加载 Qwen3 embedder: {model_name}, device={device}, dtype={torch_dtype}")

        # tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_name, trust_remote_code=True
        )

        # model (trust_remote_code=True: Qwen3 需要自定义 forward)
        self.model = AutoModel.from_pretrained(
            model_name,
            trust_remote_code=True,
            torch_dtype=torch_dtype,
        ).to(device).eval()

        # 获取实际维度
        actual_dim = self.model.config.hidden_size
        logger.info(
            f"Qwen3 embedder 加载完成: dim={actual_dim}, "
            f"max_length={max_length}, device={next(self.model.parameters()).device}"
        )

        # warm-up: 第一次推理有 JIT/cuBLAS 初始化开销, 跑一次小输入热身
        self._warmup()

    def _warmup(self):
        """首次推理热身, 避免第一次请求的 ~3s JIT 开销."""
        try:
            with torch.no_grad():
                _ = self.encode(["warmup"], batch_size=1)
            logger.info("Qwen3 embedder warm-up 完成")
        except Exception as e:
            logger.warning(f"Qwen3 embedder warm-up 失败: {e}")

    @torch.no_grad()
    def encode(
        self,
        texts: List[str],
        batch_size: int = 32,
        normalize: bool = True,
        for_query: bool = False,
    ) -> np.ndarray:
        """生成文本 embedding.

        Args:
            texts: 文本列表 (>=1 条)
            batch_size: 批量大小 (Qwen3-0.6B 默认 32, 显存够大可调 64)
            normalize: 是否 L2 归一化 (cosine similarity 用, 默认 True)
            for_query: 是否是 query (True 时加检索指令前缀; 入库文本用 False)

        Returns:
            np.ndarray, shape (len(texts), dim), dtype float32
        """
        if not texts:
            return np.zeros((0, self.model.config.hidden_size), dtype=np.float32)

        # Qwen3 query 加检索指令前缀 (官方推荐, 提升 recall@10)
        if for_query:
            texts = [f"{QWEN3_QUERY_INSTRUCTION}：{t}" for t in texts]

        all_emb: List[np.ndarray] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            inputs = self.tokenizer(
                batch,
                padding=True,
                truncation=True,
                max_length=self.max_length,
                return_tensors="pt",
            ).to(self.device)

            outputs = self.model(**inputs)

            # Qwen3-Embedding 用 last-token pooling
            # 注意: pad 在右, 所以每个序列的最后一个非 pad token 就是 hidden_states[:, -1]
            emb = outputs.last_hidden_state[:, -1]

            if normalize:
                emb = torch.nn.functional.normalize(emb, p=2, dim=1)

            all_emb.append(emb.cpu().float().numpy())

        return np.concatenate(all_emb, axis=0)

    async def encode_async(
        self,
        texts: List[str],
        batch_size: int = 32,
        normalize: bool = True,
        for_query: bool = False,
    ) -> np.ndarray:
        """异步版本: GPU 推理放到线程池避免阻塞 event loop."""
        return await asyncio.to_thread(self.encode, texts, batch_size, normalize, for_query)

    @property
    def dim(self) -> int:
        return self.model.config.hidden_size


# 工厂函数: embedding_service.py 用这个创建单例
def create_qwen_embedder(
    model_name: Optional[str] = None,
    device: Optional[str] = None,
) -> Qwen3Embedder:
    """创建 Qwen3Embedder 单例, 从环境变量读取配置."""
    model_name = model_name or os.getenv(
        "EMBEDDING_MODEL_NAME", "Qwen/Qwen3-Embedding-0.6B"
    )
    device = device or os.getenv("EMBEDDING_DEVICE", "auto")
    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    return Qwen3Embedder(model_name=model_name, device=device)
