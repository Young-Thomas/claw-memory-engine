"""
嵌入模型封装

使用 sentence-transformers 库进行文本向量化
"""

from functools import lru_cache
from typing import List, Optional
import numpy as np


class EmbeddingModel:
    """
    嵌入模型封装

    使用 all-MiniLM-L6-v2 模型：
    - 输出维度：384
    - 模型大小：~80MB
    - 支持本地运行，无需 API
    """

    _instance = None
    _model = None

    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """延迟加载模型"""
        if self._model is None:
            self._load_model()

    def _load_model(self):
        """加载嵌入模型"""
        try:
            from sentence_transformers import SentenceTransformer

            # 使用轻量级模型，适合中文场景
            self._model = SentenceTransformer("all-MiniLM-L6-v2")
        except Exception as e:
            print(f"警告：无法加载嵌入模型：{e}")
            print("语义搜索功能将不可用，将回退到关键词匹配")
            self._model = None

    def encode(self, text: str) -> Optional[List[float]]:
        """
        将文本编码为向量

        Args:
            text: 输入文本

        Returns:
            384 维向量，如果模型加载失败则返回 None
        """
        if self._model is None:
            return None

        embedding = self._model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    def encode_batch(self, texts: List[str]) -> Optional[List[List[float]]]:
        """
        批量编码文本

        Args:
            texts: 文本列表

        Returns:
            向量列表
        """
        if self._model is None:
            return None

        embeddings = self._model.encode(
            texts,
            convert_to_numpy=True,
            show_progress_bar=len(texts) > 10
        )
        return embeddings.tolist()

    def compute_similarity(
        self,
        text1: str,
        text2: str
    ) -> Optional[float]:
        """
        计算两段文本的余弦相似度

        Args:
            text1: 文本 1
            text2: 文本 2

        Returns:
            相似度分数 (0-1)
        """
        if self._model is None:
            return None

        emb1 = self.encode(text1)
        emb2 = self.encode(text2)

        if emb1 is None or emb2 is None:
            return None

        # 计算余弦相似度
        similarity = self._cosine_similarity(emb1, emb2)
        return float(similarity)

    def _cosine_similarity(
        self,
        vec1: List[float],
        vec2: List[float]
    ) -> float:
        """计算余弦相似度"""
        v1 = np.array(vec1)
        v2 = np.array(vec2)

        dot_product = np.dot(v1, v2)
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))


# 全局单例
_embedding_model: Optional[EmbeddingModel] = None


def get_embedding_model() -> EmbeddingModel:
    """获取嵌入模型单例"""
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = EmbeddingModel()
    return _embedding_model


def encode_text(text: str) -> Optional[List[float]]:
    """快捷函数：编码文本"""
    return get_embedding_model().encode(text)


def compute_similarity(text1: str, text2: str) -> Optional[float]:
    """快捷函数：计算相似度"""
    return get_embedding_model().compute_similarity(text1, text2)
