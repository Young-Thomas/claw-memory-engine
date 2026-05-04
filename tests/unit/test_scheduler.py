"""
调度器测试
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from src.integrations.scheduler import (
    ForgettingScheduler,
    MemoryReviewScheduler,
)


class TestForgettingScheduler:
    """遗忘调度器测试"""

    @pytest.fixture
    def scheduler(self):
        """创建调度器（不启动）"""
        return ForgettingScheduler()

    def test_scheduler_init(self, scheduler):
        """测试调度器初始化"""
        assert scheduler.store is not None
        assert scheduler.forgetting_engine is not None
        assert scheduler.scheduler is not None
        assert not scheduler._initialized

    @patch.object(ForgettingScheduler, 'check_expiring_memories')
    def test_start(self, mock_check, scheduler):
        """测试启动调度器"""
        scheduler.start()

        assert scheduler._initialized is True
        assert scheduler.scheduler.running is True

        # 清理
        scheduler.stop()

    def test_stop(self, scheduler):
        """测试停止调度器"""
        scheduler.start()
        scheduler.stop()

        assert scheduler._initialized is False
        assert scheduler.scheduler.running is False

    def test_check_expiring_memories(self, scheduler):
        """测试检查过期记忆"""
        stats = scheduler.check_expiring_memories()

        assert "expiring_count" in stats
        assert "review_count" in stats
        assert "notified" in stats
        assert "failed" in stats

    def test_cleanup_expired(self, scheduler):
        """测试清理过期记忆"""
        count = scheduler.cleanup_expired()

        assert isinstance(count, int)
        assert count >= 0


class TestMemoryReviewScheduler:
    """记忆复习调度器测试"""

    @pytest.fixture
    def review_scheduler(self):
        """创建复习调度器"""
        forgetting_scheduler = ForgettingScheduler()
        return MemoryReviewScheduler(forgetting_scheduler)

    def test_schedule_review(self, review_scheduler):
        """测试安排复习"""
        review_time = review_scheduler.schedule_review("test_memory_id", 0)

        # 第一次复习应该在 1 天后
        expected = datetime.now() + timedelta(days=1)
        assert abs((review_time - expected).total_seconds()) < 60  # 1 分钟误差

    def test_schedule_review_multiple(self, review_scheduler):
        """测试多次复习间隔"""
        intervals = [1, 2, 4, 7, 15, 30, 60, 90]

        for i, expected_days in enumerate(intervals):
            review_time = review_scheduler.schedule_review("test", i)
            expected = datetime.now() + timedelta(days=expected_days)
            assert abs((review_time - expected).total_seconds()) < 60

    def test_cancel_review(self, review_scheduler):
        """测试取消复习任务"""
        # 安排复习
        review_scheduler.schedule_review("test_memory", 0)

        # 取消
        review_scheduler.cancel_review("test_memory")

        # 不应该抛出异常
