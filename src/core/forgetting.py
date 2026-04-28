"""
遗忘引擎 - 基于 Ebbinghaus 遗忘曲线

管理记忆的过期和复习提醒
"""

from datetime import datetime, timedelta
from typing import List, Tuple
from enum import Enum

from src.core.models import Memory
from src.storage.sqlite_store import SQLiteStore


class RetentionStatus(Enum):
    """记忆保留状态"""
    HEALTHY = "healthy"  # 健康
    REVIEW_NEEDED = "review_needed"  # 需要复习
    EXPIRING_SOON = "expiring_soon"  # 即将过期
    EXPIRED = "expired"  # 已过期


class EbbinghausForgettingEngine:
    """
    艾宾浩斯遗忘引擎

    遗忘曲线间隔：1 天 → 2 天 → 4 天 → 7 天 → 15 天 → 30 天

    记忆保留率公式：
    R = exp(-t / S)
    其中：
    - R: 保留率 (0-1)
    - t: 经过时间（天）
    - S: 稳定性系数（由使用频率决定）
    """

    # 遗忘曲线间隔（天）
    REVIEW_INTERVALS = [1, 2, 4, 7, 15, 30, 60, 90]

    # 稳定性系数（基于使用频率）
    STABILITY_BY_FREQUENCY = {
        1: 0.5,      # 使用 1 次
        2: 1.0,      # 使用 2-3 次
        3: 2.0,      # 使用 4-5 次
        5: 4.0,      # 使用 6-10 次
        10: 8.0,     # 使用 11+ 次
    }

    def __init__(self, store: SQLiteStore = None):
        """初始化遗忘引擎"""
        self.store = store or SQLiteStore()

    def calculate_retention(self, memory: Memory) -> Tuple[float, RetentionStatus]:
        """
        计算记忆保留率

        Args:
            memory: 记忆对象

        Returns:
            (保留率，保留状态)
        """
        # 计算经过时间（天）
        now = datetime.now()
        days_since_use = (now - memory.last_used_at).days

        # 获取稳定性系数
        stability = self._get_stability(memory.frequency)

        # 计算保留率：R = exp(-t / S)
        import math
        retention = math.exp(-days_since_use / stability)

        # 确定状态
        status = self._determine_status(retention, days_since_use, stability)

        return retention, status

    def _get_stability(self, frequency: int) -> float:
        """根据使用频率获取稳定性系数"""
        for threshold in sorted(self.STABILITY_BY_FREQUENCY.keys(), reverse=True):
            if frequency >= threshold:
                return self.STABILITY_BY_FREQUENCY[threshold]
        return 0.3  # 默认最低稳定性

    def _determine_status(
        self,
        retention: float,
        days_since_use: int,
        stability: float
    ) -> RetentionStatus:
        """确定保留状态"""
        if retention < 0.1:
            return RetentionStatus.EXPIRED
        elif retention < 0.3 or days_since_use > stability * 2:
            return RetentionStatus.EXPIRING_SOON
        elif retention < 0.5 or days_since_use > stability:
            return RetentionStatus.REVIEW_NEEDED
        else:
            return RetentionStatus.HEALTHY

    def get_expiring_memories(self, days: int = 3) -> List[Memory]:
        """
        获取即将过期的记忆

        Args:
            days: 提前预警天数

        Returns:
            即将过期的记忆列表
        """
        all_memories = self.store.find_all_active(limit=1000)
        expiring = []

        for mem in all_memories:
            retention, status = self.calculate_retention(mem)

            if status in [RetentionStatus.EXPIRING_SOON, RetentionStatus.REVIEW_NEEDED]:
                # 检查是否在预警期内
                if status == RetentionStatus.EXPIRING_SOON:
                    expiring.append(mem)

        return expiring

    def get_review_reminders(self) -> List[Tuple[Memory, float]]:
        """
        获取需要复习的记忆提醒

        Returns:
            [(记忆，保留率), ...] 列表
        """
        all_memories = self.store.find_all_active(limit=1000)
        reminders = []

        for mem in all_memories:
            retention, status = self.calculate_retention(mem)

            if status == RetentionStatus.REVIEW_NEEDED:
                reminders.append((mem, retention))

        # 按保留率排序（最低的优先）
        reminders.sort(key=lambda x: x[1])

        return reminders

    def update_after_review(self, memory_id: str) -> Memory:
        """
        复习后更新记忆状态

        Args:
            memory_id: 记忆 ID

        Returns:
            更新后的记忆
        """
        memory = self.store.get_memory(memory_id)
        if not memory:
            raise ValueError(f"Memory {memory_id} not found")

        # 更新最后使用时间
        memory.last_used_at = datetime.now()

        # 增加稳定性
        memory.frequency += 1

        # 计算下次过期时间
        stability = self._get_stability(memory.frequency)
        next_interval = self._get_next_review_interval(memory.frequency)

        memory.expires_at = datetime.now() + timedelta(days=next_interval)

        return self.store.update_memory(memory)

    def _get_next_review_interval(self, frequency: int) -> int:
        """获取下次复习间隔"""
        # 根据艾宾浩斯曲线，频率对应间隔
        level = min(frequency - 1, len(self.REVIEW_INTERVALS) - 1)
        return self.REVIEW_INTERVALS[max(0, level)]

    def cleanup_expired(self) -> int:
        """
        清理已过期的记忆

        Returns:
            清理的记忆数量
        """
        all_memories = self.store.find_all_active(limit=1000)
        cleaned = 0

        for mem in all_memories:
            retention, status = self.calculate_retention(mem)

            if status == RetentionStatus.EXPIRED:
                self.store.archive_memory(mem.id)
                cleaned += 1

        return cleaned
