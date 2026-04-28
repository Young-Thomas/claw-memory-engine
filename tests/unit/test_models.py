"""
数据模型测试
"""

import pytest
from datetime import datetime
from src.core.models import Memory, Project, UsageLog


class TestMemory:
    """Memory 模型测试"""

    def test_create_memory(self):
        """测试创建记忆"""
        memory = Memory(
            alias="deploy",
            command="kubectl apply -f prod/",
        )

        assert memory.alias == "deploy"
        assert memory.command == "kubectl apply -f prod/"
        assert memory.id is not None
        assert memory.frequency == 1
        assert memory.is_active is True
        assert isinstance(memory.created_at, datetime)

    def test_memory_with_tags(self):
        """测试带标签的记忆"""
        memory = Memory(
            alias="test",
            command="pytest tests/",
            tags=["testing", "python"],
        )

        assert memory.tags == ["testing", "python"]

    def test_memory_with_project(self):
        """测试带项目的记忆"""
        memory = Memory(
            alias="build",
            command="npm run build",
            project="/path/to/project",
        )

        assert memory.project == "/path/to/project"

    def test_memory_version_chain(self):
        """测试版本链"""
        v1 = Memory(
            alias="deploy",
            command="kubectl apply -f v1/",
        )

        v2 = Memory(
            alias="deploy",
            command="kubectl apply -f v2/",
            parent_id=v1.id,
            version=2,
        )

        assert v2.parent_id == v1.id
        assert v2.version == 2


class TestProject:
    """Project 模型测试"""

    def test_create_project(self):
        """测试创建项目"""
        project = Project(
            name="my-project",
            path="/path/to/my-project",
        )

        assert project.name == "my-project"
        assert project.path == "/path/to/my-project"
        assert project.id is not None


class TestUsageLog:
    """UsageLog 模型测试"""

    def test_create_log(self):
        """测试创建日志"""
        log = UsageLog(
            memory_id="mem-123",
            action="created",
        )

        assert log.memory_id == "mem-123"
        assert log.action == "created"
        assert log.id is not None
