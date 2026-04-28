"""
检索引擎测试
"""

import pytest
import tempfile
from pathlib import Path

from src.storage.sqlite_store import SQLiteStore
from src.storage.chroma_store import ChromaStore
from src.retrieval.engine import RetrievalEngine, ContextManager
from src.core.models import Memory


class TestRetrievalEngine:
    """检索引擎测试"""

    @pytest.fixture
    def engine(self):
        """创建检索引擎"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            chroma_path = Path(tmpdir) / "chroma_db"

            sqlite = SQLiteStore(str(db_path))
            chroma = ChromaStore(persist_dir=str(chroma_path))

            yield RetrievalEngine(sqlite_store=sqlite, chroma_store=chroma)

    def test_search_exact_match(self, engine):
        """测试精确匹配"""
        memory = Memory(
            alias="deploy-prod",
            command="kubectl apply -f prod/",
        )
        engine.sqlite.create_memory(memory)

        results = engine.search("deploy-prod")

        assert len(results) >= 1
        assert results[0].match_type == "exact"
        assert results[0].score == 1.0

    def test_search_prefix_match(self, engine):
        """测试前缀匹配"""
        memory = Memory(
            alias="deploy-prod",
            command="kubectl apply -f prod/",
        )
        engine.sqlite.create_memory(memory)

        results = engine.search("deploy")

        assert len(results) >= 1
        assert results[0].match_type == "prefix"

    def test_search_project_filter(self, engine):
        """测试项目过滤"""
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

        engine.sqlite.create_memory(mem1)
        engine.sqlite.create_memory(mem2)

        results = engine.search("deploy", project="/project-a")

        assert all(r.memory.project == "/project-a" for r in results)

    def test_get_suggestions(self, engine):
        """测试获取建议"""
        memory = Memory(
            alias="test-cmd",
            command="pytest tests/",
        )
        engine.sqlite.create_memory(memory)

        suggestions = engine.get_suggestions("test", limit=5)

        assert len(suggestions) >= 1

    def test_find_by_alias(self, engine):
        """测试按别名查找"""
        memory = Memory(
            alias="unique-alias",
            command="unique-command",
        )
        engine.sqlite.create_memory(memory)

        result = engine.find_by_alias("unique-alias")

        assert result is not None
        assert result.alias == "unique-alias"


class TestContextManager:
    """上下文管理器测试"""

    def test_detect_context(self):
        """测试上下文检测"""
        manager = ContextManager()

        import os
        context = manager.detect_context(os.getcwd())

        assert context is not None
        assert context.current_directory is not None

    def test_find_git_root(self, tmp_path):
        """测试查找 git 根目录"""
        manager = ContextManager()

        # 创建模拟 git 仓库
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        result = manager._find_git_root(tmp_path)

        assert result == tmp_path

    def test_find_git_root_nested(self, tmp_path):
        """测试查找嵌套 git 根目录"""
        manager = ContextManager()

        # 创建模拟 git 仓库
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # 创建子目录
        child_dir = tmp_path / "child" / "grandchild"
        child_dir.mkdir(parents=True)

        result = manager._find_git_root(child_dir)

        assert result == tmp_path
