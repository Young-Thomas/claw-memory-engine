"""
遗忘引擎测试
"""

import pytest
from datetime import datetime, timedelta
import tempfile
from pathlib import Path

from src.core.models import Memory
from src.storage.sqlite_store import SQLiteStore
from src.core.forgetting import EbbinghausForgettingEngine, RetentionStatus


class TestEbbinghausForgettingEngine:
    """遗忘引擎测试"""

    @pytest.fixture
    def engine(self):
        """创建遗忘引擎"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = SQLiteStore(str(db_path))
            yield EbbinghausForgettingEngine(store)

    def test_calculate_retention_fresh(self, engine):
        """测试新鲜记忆的保留率"""
        memory = Memory(
            alias="test",
            command="pytest",
            frequency=1,
            last_used_at=datetime.now(),  # 刚刚使用
        )

        retention, status = engine.calculate_retention(memory)

        assert retention > 0.9
        assert status == RetentionStatus.HEALTHY

    def test_calculate_retention_old(self, engine):
        """测试旧记忆的保留率"""
        memory = Memory(
            alias="test",
            command="pytest",
            frequency=1,
            last_used_at=datetime.now() - timedelta(days=30),  # 30 天前
        )

        retention, status = engine.calculate_retention(memory)

        assert retention < 0.3
        assert status in [RetentionStatus.EXPIRING_SOON, RetentionStatus.EXPIRED]

    def test_high_frequency_memory(self, engine):
        """测试高频记忆的稳定性"""
        memory = Memory(
            alias="test",
            command="pytest",
            frequency=20,  # 高频使用
            last_used_at=datetime.now() - timedelta(days=7),
        )

        retention, status = engine.calculate_retention(memory)

        # 高频使用应该保留率更高
        assert retention > 0.5

    def test_get_expiring_memories(self, engine):
        """测试获取即将过期的记忆"""
        # 创建即将过期的记忆
        old_memory = Memory(
            alias="old",
            command="old-cmd",
            frequency=1,
            last_used_at=datetime.now() - timedelta(days=30),
        )
        engine.store.create_memory(old_memory)

        # 创建健康记忆
        new_memory = Memory(
            alias="new",
            command="new-cmd",
            frequency=10,
            last_used_at=datetime.now() - timedelta(days=1),
        )
        engine.store.create_memory(new_memory)

        expiring = engine.get_expiring_memories(days=3)

        # 应该只包含即将过期的
        assert any(m.alias == "old" for m in expiring)
        assert not any(m.alias == "new" for m in expiring)

    def test_update_after_review(self, engine):
        """测试复习后更新"""
        memory = Memory(
            alias="test",
            command="pytest",
            frequency=1,
            last_used_at=datetime.now() - timedelta(days=7),
        )
        engine.store.create_memory(memory)

        # 复习
        updated = engine.update_after_review(memory.id)

        assert updated.frequency == 2
        assert updated.last_used_at > memory.last_used_at
        assert updated.expires_at is not None

    def test_cleanup_expired(self, engine):
        """测试清理过期记忆"""
        # 创建过期记忆
        expired_memory = Memory(
            alias="expired",
            command="expired-cmd",
            frequency=1,
            last_used_at=datetime.now() - timedelta(days=100),
        )
        engine.store.create_memory(expired_memory)

        # 创建健康记忆
        healthy_memory = Memory(
            alias="healthy",
            command="healthy-cmd",
            frequency=10,
            last_used_at=datetime.now() - timedelta(days=1),
        )
        engine.store.create_memory(healthy_memory)

        # 清理
        cleaned = engine.cleanup_expired()

        assert cleaned >= 1

        # 验证过期记忆已归档
        active = engine.store.find_all_active()
        assert not any(m.alias == "expired" for m in active)
        assert any(m.alias == "healthy" for m in active)
