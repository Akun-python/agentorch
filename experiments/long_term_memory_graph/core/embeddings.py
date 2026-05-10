from __future__ import annotations

import hashlib
import math

from agentorch.knowledge.base import EmbeddingProvider


class DeterministicEmbeddingProvider(EmbeddingProvider):
    """离线实验探针使用的确定性 embedding，避免 smoke test 依赖外部 API。"""

    def __init__(self, *, dimensions: int = 32, salt: str = "ltmg") -> None:
        self.dimensions = dimensions
        self.salt = salt

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_one(text) for text in texts]

    def embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        tokens = [token for token in text.lower().replace("_", " ").split() if token]
        if not tokens:
            return vector
        for token in tokens:
            digest = hashlib.sha256(f"{self.salt}:{token}".encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            vector[index] += 1.0
        norm = math.sqrt(sum(item * item for item in vector)) or 1.0
        return [item / norm for item in vector]
