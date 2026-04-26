"""
OpenRouter Embedding Service - 使用 OpenAI SDK 访问 OpenRouter embeddings

示例用法:
from openai import OpenAI
client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key="xxx")
client.embeddings.create(model="google/gemini-embedding-001", input="text")
"""

import os
import math
import yaml
from typing import List
from openai import OpenAI


def load_config():
    """从 config.yaml 加载配置"""
    config_path = os.path.join(os.path.dirname(__file__), "..", "..", "config.yaml")
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config


def _l2_normalize(vec: List[float]) -> List[float]:
    """对向量进行L2归一化"""
    s = sum(v * v for v in vec)
    if s <= 0:
        return vec
    norm = math.sqrt(s)
    if norm == 0:
        return vec
    return [v / norm for v in vec]


class OpenRouterEmbedding:
    """通过 OpenAI SDK 调用 OpenRouter embeddings 端点的封装。"""

    def __init__(self):
        config = load_config()
        openrouter_config = config.get("openrouter", {})

        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=openrouter_config.get("api_key"),
        )
        self.model = openrouter_config.get("embedding_model", "google/gemini-embedding-001")

    def embed_text(self, text: str, normalize: bool = False) -> List[float]:
        """为单个文本生成嵌入向量"""
        embedding = self.client.embeddings.create(
            extra_headers={
                "HTTP-Referer": "<YOUR_SITE_URL>",  # Optional. Site URL for rankings on openrouter.ai.
                "X-Title": "<YOUR_SITE_NAME>",  # Optional. Site title for rankings on openrouter.ai.
            },
            model=self.model,
            input=text,
            encoding_format="float"
        )
        vec = embedding.data[0].embedding
        if normalize:
            vec = _l2_normalize(vec)
        return vec

    def embed_texts(self, texts: List[str], normalize: bool = False) -> List[List[float]]:
        """为文本列表生成嵌入向量"""
        embedding = self.client.embeddings.create(
            extra_headers={
                "HTTP-Referer": "<YOUR_SITE_URL>",  # Optional. Site URL for rankings on openrouter.ai.
                "X-Title": "<YOUR_SITE_NAME>",  # Optional. Site title for rankings on openrouter.ai.
            },
            model=self.model,
            input=texts,
            encoding_format="float"
        )
        vecs = [data.embedding for data in embedding.data]
        if normalize:
            vecs = [_l2_normalize(vec) for vec in vecs]
        return vecs


__all__ = ["OpenRouterEmbedding"]
