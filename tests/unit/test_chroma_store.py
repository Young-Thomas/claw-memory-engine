"""
ChromaDB 存储层测试
"""

import pytest
import tempfile
from pathlib import Path

from src.core.models import Memory
from src.storage.chroma_store import ChromaStore


class TestChromaStore:
    """ChromaStore 测试"""

    @pytest.fixture
    def chroma_store(self):
        """创建临时 ChromaDB 存储"""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ChromaStore(persist_dir=tmpdir)
            yield store

    def test_add_memory(self, chroma_store):
        """测试添加记忆"""
        memory = Memory(
            alias="deploy",
            command="kubectl apply -f prod/",
        )

        # 添加记忆（不带 embedding）
        chroma_store.add_memory(memory)

        # 验证可以获取
        results = chroma_store.get_all_memories()
        assert len(results) >= 1

    def test_update_memory(self, chroma_store):
        """测试更新记忆"""
        memory = Memory(
            alias="deploy",
            command="kubectl apply -f v1/",
        )
        chroma_store.add_memory(memory)

        # 更新
        memory.command = "kubectl apply -f v2/"
        chroma_store.update_memory(memory)

        # 验证更新
        results = chroma_store.get_all_memories()
        assert len(results) >= 1

    def test_delete_memory(self, chroma_store):
        """测试删除记忆"""
        memory = Memory(
            alias="test",
            command="pytest tests/",
        )
        chroma_store.add_memory(memory)

        # 删除
        chroma_store.delete_memory(memory.id)

        # 验证已删除
        results = chroma_store.get_all_memories()
        assert not any(r["metadata"]["memory_id"] == memory.id for r in results)

    def test_search_by_project(self, chroma_store):
        """测试按项目搜索"""
        mem1 = Memory(
            alias="deploy",
            command="kubectl apply -f prod/",
            project="/project-a",
        )
        mem2 = Memory(
            alias="deploy",
            command="docker-compose up",
            project="/project-b",
        )

        chroma_store.add_memory(mem1)
        chroma_store.add_memory(mem2)

        results = chroma_store.search_by_project("/project-a")
        assert len(results) == 1

    def test_reset(self, chroma_store):
        """测试重置"""
        memory = Memory(
            alias="test",
            command="pytest",
        )
        chroma_store.add_memory(memory)

        # 重置
        chroma_store.reset()

        # 验证已清空
        results = chroma_store.get_all_memories()
        assert len(results) == 0
