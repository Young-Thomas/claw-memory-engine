"""
嵌入模型封装

支持多种模型，包括中文优化模型
"""

from functools import lru_cache
from typing import List, Optional, Dict
import hashlib
import numpy as np

from src.config.config_manager import get_config
from src.logger.logger import get_logger


logger = get_logger(__name__)


# 预定义模型配置
MODEL_CONFIGS = {
    # 英文场景（轻量级）
    "all-MiniLM-L6-v2": {
        "dim": 384,
        "size": "~80MB",
        "speed": "fast",
        "chinese": False,
    },
    # 中文场景（推荐）
    "BGE-M3": {
        "dim": 1024,
        "size": "~1.1GB",
        "speed": "medium",
        "chinese": True,
    },
    # 中文场景（轻量级）
    "text2vec-base-chinese": {
        "dim": 768,
        "size": "~500MB",
        "speed": "medium",
        "chinese": True,
    },
}


class EmbeddingModel:
    """
    嵌入模型封装

    支持模型选择、缓存机制
    """

    _instance: Optional['EmbeddingModel'] = None
    _model = None
    _cache: Dict[str, List[float]] = {}  # 向量缓存

    def __new__(cls, model_name: str = None):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.model_name = model_name
        return cls._instance

    def __init__(self, model_name: str = None):
        """延迟加载模型"""
        if hasattr(self, '_initialized') and self._initialized:
            return

        # 从配置获取模型名称
        if model_name is None:
            config = get_config()
            model_name = config.embedding_model

        self.model_name = model_name
        self._load_model()
        self._initialized = True

    def _load_model(self):
        """加载嵌入模型"""
        try:
            from sentence_transformers import SentenceTransformer

            logger.info(f"Loading embedding model: {self.model_name}")
            self._model = SentenceTransformer(self.model_name)

            # 获取模型信息
            config = MODEL_CONFIGS.get(self.model_name, {})
            logger.info(
                f"Model loaded: {self.model_name}, "
                f"dim={config.get('dim', 'unknown')}, "
                f"size={config.get('size', 'unknown')}"
            )

        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            logger.warning("Falling back to keyword matching (semantic search disabled)")
            self._model = None

    def encode(self, text: str, use_cache: bool = True) -> Optional[List[float]]:
        """
        将文本编码为向量（带缓存）

        Args:
            text: 输入文本
            use_cache: 是否使用缓存

        Returns:
            向量，如果模型加载失败则返回 None
        """
        # 检查缓存
        if use_cache:
            cache_key = hashlib.md5(f"{self.model_name}:{text}".encode()).hexdigest()
            if cache_key in self._cache:
                logger.debug(f"Cache hit for: {text[:30]}...")
                return self._cache[cache_key]

        if self._model is None:
            return None

        try:
            embedding = self._model.encode(text, convert_to_numpy=True)
            result = embedding.tolist()

            # 缓存结果
            if use_cache:
                self._cache[cache_key] = result
                # 限制缓存大小
                if len(self._cache) > 1000:
                    # 删除一半缓存
                    keys = list(self._cache.keys())[:500]
                    for k in keys:
                        del self._cache[k]

            return result

        except Exception as e:
            logger.error(f"Encoding failed: {e}")
            return None

    def encode_batch(
        self,
        texts: List[str],
        use_cache: bool = True,
        show_progress: bool = False
    ) -> Optional[List[List[float]]]:
        """
        批量编码文本

        Args:
            texts: 文本列表
            use_cache: 是否使用缓存
            show_progress: 显示进度条

        Returns:
            向量列表
        """
        if self._model is None:
            return None

        # 分离缓存和未缓存的文本
        results = []
        texts_to_encode = []
        indices_to_encode = []

        if use_cache:
            for i, text in enumerate(texts):
                cache_key = hashlib.md5(f"{self.model_name}:{text}".encode()).hexdigest()
                if cache_key in self._cache:
                    results.append(self._cache[cache_key])
                else:
                    texts_to_encode.append(text)
                    indices_to_encode.append(i)
                    results.append(None)
        else:
            texts_to_encode = texts
            indices_to_encode = list(range(len(texts)))
            results = [None] * len(texts)

        # 编码未缓存的文本
        if texts_to_encode:
            embeddings = self._model.encode(
                texts_to_encode,
                convert_to_numpy=True,
                show_progress_bar=show_progress and len(texts_to_encode) > 10
            )

            # 填充结果并缓存
            for i, (idx, text) in enumerate(zip(indices_to_encode, texts_to_encode)):
                result = embeddings[i].tolist()
                results[idx] = result

                if use_cache:
                    cache_key = hashlib.md5(f"{self.model_name}:{text}".encode()).hexdigest()
                    self._cache[cache_key] = result

        return results

    def compute_similarity(self, text1: str, text2: str) -> Optional[float]:
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

        return float(self._cosine_similarity(emb1, emb2))

    @staticmethod
    def _cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        """计算余弦相似度"""
        v1 = np.array(vec1)
        v2 = np.array(vec2)

        dot_product = np.dot(v1, v2)
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))

    def clear_cache(self) -> None:
        """清除向量缓存"""
        self._cache.clear()
        logger.info("Embedding cache cleared")

    def get_cache_stats(self) -> Dict[str, int]:
        """获取缓存统计"""
        return {"cache_size": len(self._cache)}


# 全局单例
_embedding_model: Optional[EmbeddingModel] = None


def get_embedding_model(model_name: str = None) -> EmbeddingModel:
    """获取嵌入模型单例"""
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = EmbeddingModel(model_name)
    return _embedding_model


def encode_text(text: str, use_cache: bool = True) -> Optional[List[float]]:
    """快捷函数：编码文本"""
    return get_embedding_model().encode(text, use_cache)


def encode_batch(
    texts: List[str],
    use_cache: bool = True,
    show_progress: bool = False
) -> Optional[List[List[float]]]:
    """快捷函数：批量编码"""
    return get_embedding_model().encode_batch(texts, use_cache, show_progress)


def compute_similarity(text1: str, text2: str) -> Optional[float]:
    """快捷函数：计算相似度"""
    return get_embedding_model().compute_similarity(text1, text2)
