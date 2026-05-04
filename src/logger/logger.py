"""
日志系统

支持文件日志和控制台日志
"""

import logging
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime

from src.config.config_manager import get_config, get_data_dir


class LoggerManager:
    """
    日志管理器

    统一日志配置，支持多级别日志
    """

    _loggers = {}

    @classmethod
    def get_logger(cls, name: str = "claw") -> logging.Logger:
        """
        获取日志记录器

        Args:
            name: 日志器名称

        Returns:
            logging.Logger 实例
        """
        if name in cls._loggers:
            return cls._loggers[name]

        # 获取配置
        config = get_config()

        # 创建 logger
        logger = logging.getLogger(name)
        logger.setLevel(getattr(logging, config.log_level.upper()))

        # 避免重复添加 handler
        if logger.handlers:
            cls._loggers[name] = logger
            return logger

        # 创建 formatter
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

        # 控制台 handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)

        # 文件 handler（如果配置了）
        if config.log_file:
            log_path = Path(config.log_file)
        else:
            # 默认在数据目录下
            log_path = get_data_dir() / "claw.log"

        # 确保目录存在
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_path, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)

        # 添加 handler
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)

        cls._loggers[name] = logger
        return logger


# 快捷函数
def get_logger(name: str = "claw") -> logging.Logger:
    """获取日志记录器"""
    return LoggerManager.get_logger(name)


# 预定义 logger
logger = get_logger()


def log_debug(message: str, **kwargs) -> None:
    """记录 DEBUG 日志"""
    if kwargs:
        message = f"{message} | {kwargs}"
    logger.debug(message)


def log_info(message: str, **kwargs) -> None:
    """记录 INFO 日志"""
    if kwargs:
        message = f"{message} | {kwargs}"
    logger.info(message)


def log_warning(message: str, **kwargs) -> None:
    """记录 WARNING 日志"""
    if kwargs:
        message = f"{message} | {kwargs}"
    logger.warning(message)


def log_error(message: str, **kwargs) -> None:
    """记录 ERROR 日志"""
    if kwargs:
        message = f"{message} | {kwargs}"
    logger.error(message)


def log_exception(message: str, exc: Exception, **kwargs) -> None:
    """记录异常日志"""
    if kwargs:
        message = f"{message} | {kwargs}"
    logger.exception(f"{message} | {exc}")
