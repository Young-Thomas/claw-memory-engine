"""
遗忘调度器

基于 Ebbinghaus 遗忘曲线的定时任务调度
"""

import time
import threading
from datetime import datetime, timedelta
from typing import List, Callable, Optional
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from src.core.forgetting import EbbinghausForgettingEngine, RetentionStatus
from src.storage.sqlite_store import SQLiteStore
from src.config.config_manager import get_config, get_data_dir
from src.logger.logger import get_logger
from src.integrations.feishu import get_feishu_client, send_memory_notification


logger = get_logger(__name__)


class ForgettingScheduler:
    """
    遗忘调度器

    功能：
    - 定期检查即将过期的记忆
    - 发送飞书提醒
    - 清理已过期记忆
    """

    def __init__(
        self,
        store: Optional[SQLiteStore] = None,
        feishu_chat_id: Optional[str] = None,
    ):
        """
        初始化调度器

        Args:
            store: SQLite 存储
            feishu_chat_id: 飞书群聊 ID
        """
        self.store = store or SQLiteStore()
        self.forgetting_engine = EbbinghausForgettingEngine(self.store)
        self.feishu_chat_id = feishu_chat_id

        # 创建后台调度器
        self.scheduler = BackgroundScheduler(
            timezone="Asia/Shanghai",
            job_defaults={
                "coalesce": True,
                "max_instances": 1,
                "misfire_grace_time": 3600
            }
        )

        self._initialized = False

    def start(self) -> None:
        """启动调度器"""
        if self._initialized:
            logger.warning("调度器已启动")
            return

        self.scheduler.add_job(
            self.check_expiring_memories,
            CronTrigger(hour=9, minute=0),
            id="check_expiring",
            name="检查即将过期的记忆"
        )

        self.scheduler.add_job(
            self.cleanup_expired,
            CronTrigger(day_of_week="sun", hour=2, minute=0),
            id="cleanup_expired",
            name="清理过期记忆"
        )

        self.scheduler.start()
        self._initialized = True
        logger.info("遗忘调度器已启动")

        try:
            self.check_expiring_memories()
            logger.info("启动时立即执行了一次记忆检查")
        except Exception as e:
            logger.error(f"启动时记忆检查失败：{e}")

    def stop(self) -> None:
        """停止调度器"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            self._initialized = False
            logger.info("遗忘调度器已停止")

    def check_expiring_memories(self) -> dict:
        """
        检查即将过期的记忆并发送提醒

        Returns:
            检查结果统计
        """
        logger.info("开始检查即将过期的记忆...")

        expiring = self.forgetting_engine.get_expiring_memories(days=3)
        review_needed = self.forgetting_engine.get_review_reminders()

        stats = {
            "expiring_count": len(expiring),
            "review_count": len(review_needed),
            "notified": 0,
            "failed": 0
        }

        # 发送飞书提醒
        if self.feishu_chat_id and (expiring or review_needed):
            client = get_feishu_client()

            if client and client.test_connection():
                # 发送即将过期提醒
                for memory in expiring[:5]:  # 最多发送 5 条
                    success = send_memory_notification(
                        self.feishu_chat_id,
                        memory.alias,
                        memory.command,
                        memory_type="警告"
                    )
                    if success:
                        stats["notified"] += 1
                    else:
                        stats["failed"] += 1

                # 发送复习提醒
                for memory, retention in review_needed[:5]:
                    success = send_memory_notification(
                        self.feishu_chat_id,
                        memory.alias,
                        memory.command,
                        memory_type="复习"
                    )
                    if success:
                        stats["notified"] += 1
                    else:
                        stats["failed"] += 1

        logger.info(
            f"检查完成：{stats['expiring_count']} 条即将过期，"
            f"{stats['review_count']} 条需要复习，"
            f"发送 {stats['notified']} 条通知"
        )

        return stats

    def cleanup_expired(self) -> int:
        """
        清理已过期的记忆

        Returns:
            清理的记忆数量
        """
        logger.info("开始清理过期记忆...")

        count = self.forgetting_engine.cleanup_expired()

        logger.info(f"清理完成：{count} 条记忆已归档")
        return count

    def add_memory_check(
        self,
        memory_id: str,
        check_time: datetime
    ) -> None:
        """
        添加单个记忆的检查任务

        Args:
            memory_id: 记忆 ID
            check_time: 检查时间
        """
        job_id = f"check_memory_{memory_id}"

        self.scheduler.add_job(
            self._check_single_memory,
            "date",
            run_date=check_time,
            id=job_id,
            args=[memory_id]
        )

        logger.debug(f"添加记忆检查任务：{memory_id} @ {check_time}")

    def _check_single_memory(self, memory_id: str) -> None:
        """检查单个记忆"""
        memory = self.store.get_memory(memory_id)
        if not memory or not memory.is_active:
            return

        retention, status = self.forgetting_engine.calculate_retention(memory)

        if status == RetentionStatus.EXPIRING_SOON and self.feishu_chat_id:
            send_memory_notification(
                self.feishu_chat_id,
                memory.alias,
                memory.command,
                memory_type="提醒"
            )


class MemoryReviewScheduler:
    """
    记忆复习调度器

    为每个记忆安排复习时间
    """

    # 复习间隔（天）- 艾宾浩斯曲线
    REVIEW_INTERVALS = [1, 2, 4, 7, 15, 30, 60, 90]

    def __init__(self, scheduler: ForgettingScheduler):
        """
        初始化复习调度器

        Args:
            scheduler: 遗忘调度器
        """
        self.scheduler = scheduler
        self.store = scheduler.store

    def schedule_review(self, memory_id: str, review_count: int = 0) -> datetime:
        """
        安排复习时间

        Args:
            memory_id: 记忆 ID
            review_count: 已复习次数

        Returns:
            下次复习时间
        """
        # 获取间隔
        interval_index = min(review_count, len(self.REVIEW_INTERVALS) - 1)
        interval_days = self.REVIEW_INTERVALS[interval_index]

        # 计算复习时间
        review_time = datetime.now() + timedelta(days=interval_days)

        # 添加任务
        self.scheduler.add_memory_check(memory_id, review_time)

        logger.info(f"已安排记忆 {memory_id} 在 {review_time} 复习")
        return review_time

    def cancel_review(self, memory_id: str) -> None:
        """
        取消复习任务

        Args:
            memory_id: 记忆 ID
        """
        job_id = f"check_memory_{memory_id}"

        try:
            self.scheduler.scheduler.remove_job(job_id)
            logger.debug(f"已取消记忆 {memory_id} 的复习任务")
        except Exception:
            pass


# 全局单例
_scheduler: Optional[ForgettingScheduler] = None


def get_forgetting_scheduler(chat_id: str = None) -> ForgettingScheduler:
    """获取遗忘调度器单例"""
    global _scheduler
    if _scheduler is None:
        _scheduler = ForgettingScheduler(feishu_chat_id=chat_id)
    return _scheduler


def start_scheduler(chat_id: str = None) -> ForgettingScheduler:
    """启动调度器"""
    scheduler = get_forgetting_scheduler(chat_id)
    scheduler.start()
    return scheduler


def stop_scheduler() -> None:
    """停止调度器"""
    scheduler = get_forgetting_scheduler()
    scheduler.stop()
