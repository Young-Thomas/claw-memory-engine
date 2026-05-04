"""
日志系统测试
"""

import pytest
import tempfile
from pathlib import Path

from src.logger.logger import LoggerManager, get_logger, log_info, log_error


class TestLoggerManager:
    """日志管理器测试"""

    def test_get_logger_singleton(self):
        """测试单例模式"""
        logger1 = LoggerManager.get_logger("test1")
        logger2 = LoggerManager.get_logger("test1")

        assert logger1 is logger2

    def test_get_logger_different_names(self):
        """测试不同名称的 logger"""
        logger1 = LoggerManager.get_logger("test_a")
        logger2 = LoggerManager.get_logger("test_b")

        assert logger1 is not logger2

    def test_log_levels(self, caplog):
        """测试日志级别"""
        logger = get_logger("test_levels")

        logger.debug("debug message")
        logger.info("info message")
        logger.warning("warning message")
        logger.error("error message")

        # 验证日志记录
        assert "info message" in caplog.text
        assert "warning message" in caplog.text
        assert "error message" in caplog.text


class TestLoggerFunctions:
    """快捷日志函数测试"""

    def test_log_info(self, caplog):
        """测试 INFO 日志"""
        log_info("test message", extra="data")

        assert "test message" in caplog.text

    def test_log_error(self, caplog):
        """测试 ERROR 日志"""
        log_error("error message", code=500)

        assert "error message" in caplog.text
