"""
SQLite 存储层测试
"""

import pytest
import tempfile
import os
from pathlib import Path

from src.core.models import Memory
from src.storage.sqlite_store import SQLiteStore


class TestSQLiteStore:
    """SQLiteStore 测试"""

    @pytest.fixture
    def store(self):
        """创建临时数据库"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = SQLiteStore(str(db_path))
            yield store

    def test_create_memory(self, store):
        """测试创建记忆"""
        memory = Memory(
            alias="deploy",
            command="kubectl apply -f prod/",
        )

        result = store.create_memory(memory)

        assert result.id == memory.id
        assert result.alias == "deploy"

        # 验证可以查询到
        retrieved = store.get_memory(memory.id)
        assert retrieved is not None
        assert retrieved.alias == "deploy"

    def test_find_by_alias(self, store):
        """测试按别名查找"""
        memory = Memory(
            alias="test-cmd",
            command="pytest tests/",
        )
        store.create_memory(memory)

        results = store.find_by_alias("test-cmd")
        assert len(results) == 1
        assert results[0].alias == "test-cmd"

    def test_find_by_project(self, store):
        """测试按项目查找"""
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

        store.create_memory(mem1)
        store.create_memory(mem2)

        results = store.find_by_project("/project-a")
        assert len(results) == 1
        assert results[0].project == "/project-a"

    def test_update_memory(self, store):
        """测试更新记忆"""
        memory = Memory(
            alias="deploy",
            command="kubectl apply -f v1/",
        )
        store.create_memory(memory)

        # 更新命令
        memory.command = "kubectl apply -f v2/"
        store.update_memory(memory)

        # 验证更新
        updated = store.get_memory(memory.id)
        assert updated.command == "kubectl apply -f v2/"

    def test_increment_frequency(self, store):
        """测试增加使用频率"""
        memory = Memory(
            alias="test",
            command="pytest",
            frequency=1,
        )
        store.create_memory(memory)

        store.increment_frequency(memory.id)

        updated = store.get_memory(memory.id)
        assert updated.frequency == 2

    def test_archive_memory(self, store):
        """测试归档记忆"""
        memory = Memory(
            alias="test",
            command="pytest",
        )
        store.create_memory(memory)

        store.archive_memory(memory.id)

        # 归档后不应在活跃列表中
        active = store.find_all_active()
        assert not any(m.id == memory.id for m in active)

    def test_version_chain(self, store):
        """测试版本链"""
        v1 = Memory(
            alias="deploy",
            command="kubectl apply -f v1/",
            version=1,
        )
        store.create_memory(v1)

        v2 = Memory(
            alias="deploy",
            command="kubectl apply -f v2/",
            parent_id=v1.id,
            version=2,
        )
        store.create_memory(v2)

        # 获取版本链
        chain = store.get_version_chain(v2.id)
        assert len(chain) == 2
        assert chain[0].version == 1
        assert chain[1].version == 2

    def test_project_crud(self, store):
        """测试项目 CRUD"""
        from src.core.models import Project

        project = Project(
            name="test-project",
            path="/path/to/test",
        )
        store.create_project(project)

        # 按路径查找
        retrieved = store.find_project_by_path("/path/to/test")
        assert retrieved is not None
        assert retrieved.name == "test-project"

        # 获取或创建
        result = store.get_or_create_project("/path/to/test", "new-name")
        assert result.id == project.id  # 返回已存在的

        result2 = store.get_or_create_project("/path/to/new")
        assert result2.name == "new"
