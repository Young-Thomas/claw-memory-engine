"""
嵌入模型缓存测试
"""

import pytest

from src.retrieval.embeddings import EmbeddingModel, encode_text, encode_batch


class TestEmbeddingCache:
    """嵌入模型缓存测试"""

    @pytest.fixture
    def embedding_model(self):
        """创建嵌入模型（可能跳过实际加载）"""
        try:
            model = EmbeddingModel("all-MiniLM-L6-v2")
            return model
        except Exception:
            pytest.skip("Embedding model not available")

    def test_cache_single_encoding(self, embedding_model):
        """测试单次编码缓存"""
        text = "test command"

        # 第一次编码
        result1 = embedding_model.encode(text, use_cache=True)

        # 第二次编码（应该命中缓存）
        result2 = embedding_model.encode(text, use_cache=True)

        assert result1 == result2

    def test_cache_batch_encoding(self, embedding_model):
        """测试批量编码缓存"""
        texts = ["test1", "test2", "test3"]

        # 批量编码
        results = embedding_model.encode_batch(texts, use_cache=True)

        assert len(results) == len(texts)

        # 单个编码应该命中缓存
        for text, expected in zip(texts, results):
            result = embedding_model.encode(text, use_cache=True)
            assert result == expected

    def test_cache_clear(self, embedding_model):
        """测试清除缓存"""
        text = "test command"

        # 编码并缓存
        embedding_model.encode(text, use_cache=True)

        # 检查缓存统计
        stats = embedding_model.get_cache_stats()
        assert stats["cache_size"] > 0

        # 清除缓存
        embedding_model.clear_cache()

        # 验证缓存已清空
        stats = embedding_model.get_cache_stats()
        assert stats["cache_size"] == 0

    def test_cache_size_limit(self, embedding_model):
        """测试缓存大小限制"""
        # 编码大量文本触发缓存限制
        for i in range(600):
            embedding_model.encode(f"test {i}", use_cache=True)

        # 缓存大小应该不超过限制
        stats = embedding_model.get_cache_stats()
        assert stats["cache_size"] <= 1000


class TestEmbeddingFunctions:
    """嵌入快捷函数测试"""

    def test_encode_text_without_model(self, monkeypatch):
        """测试模型不可用时的回退"""
        # 模拟模型加载失败
        monkeypatch.setattr("src.retrieval.embeddings._embedding_model", None)

        result = encode_text("test")

        # 模型不可用时返回 None
        assert result is None
