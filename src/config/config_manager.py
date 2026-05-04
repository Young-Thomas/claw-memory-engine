"""
配置管理模块

支持自定义数据目录、模型配置等
"""

import json
import os
from pathlib import Path
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class Config(BaseModel):
    """配置模型"""

    # 数据目录
    data_dir: str = Field(
        default_factory=lambda: str(Path.home() / ".claw"),
        description="数据目录路径"
    )

    # SQLite 配置
    sqlite_db: str = Field(
        default="claw.db",
        description="SQLite 数据库文件名"
    )

    # ChromaDB 配置
    chroma_dir: str = Field(
        default="chroma_db",
        description="ChromaDB 持久化目录"
    )

    # 嵌入模型配置
    embedding_model: str = Field(
        default="all-MiniLM-L6-v2",
        description="嵌入模型名称"
    )

    model_cache_dir: Optional[str] = Field(
        default=None,
        description="模型缓存目录"
    )

    # 检索配置
    search_limit: int = Field(
        default=10,
        description="默认搜索返回数量"
    )

    max_freq_memories: int = Field(
        default=100,
        description="高频记忆最大数量"
    )

    # 遗忘曲线配置
    forgetting_enabled: bool = Field(
        default=True,
        description="是否启用遗忘曲线"
    )

    # 日志配置
    log_level: str = Field(
        default="INFO",
        description="日志级别"
    )

    log_file: Optional[str] = Field(
        default=None,
        description="日志文件路径"
    )

    # 飞书集成配置
    feishu_app_id: Optional[str] = Field(
        default=None,
        description="飞书应用 App ID"
    )

    feishu_app_secret: Optional[str] = Field(
        default=None,
        description="飞书应用 App Secret"
    )

    feishu_chat_id: Optional[str] = Field(
        default=None,
        description="飞书群聊 ID（用于推送通知）"
    )

    class Config:
        arbitrary_types_allowed = True


class ConfigManager:
    """
    配置管理器

    单例模式，支持从配置文件加载
    """

    _instance = None
    _config_file = "config.json"

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._config = None
            self._initialized = True

    @property
    def config_file_path(self) -> Path:
        """获取配置文件路径"""
        # 优先从环境变量读取
        custom_path = os.environ.get("CLAW_CONFIG_FILE")
        if custom_path:
            return Path(custom_path)

        # 默认在数据目录下查找
        data_dir = Path.home() / ".claw"
        return data_dir / self._config_file

    def load(self) -> Config:
        """加载配置"""
        if self._config:
            return self._config

        config_file = self.config_file_path

        if config_file.exists():
            # 从文件加载
            with open(config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self._config = Config(**data)
        else:
            # 使用默认配置
            self._config = Config()

        return self._config

    def save(self, config: Config = None) -> None:
        """保存配置"""
        if config:
            self._config = config

        config_file = self.config_file_path

        # 确保目录存在
        config_file.parent.mkdir(parents=True, exist_ok=True)

        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(self._config.model_dump(), f, indent=2, ensure_ascii=False)

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置项"""
        config = self.load()
        return getattr(config, key, default)

    def set(self, key: str, value: Any) -> None:
        """设置配置项"""
        config = self.load()
        if hasattr(config, key):
            setattr(config, key, value)
            self.save(config)

    def reset(self) -> None:
        """重置为默认配置"""
        self._config = Config()
        self.save()


# 全局单例
_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """获取配置管理器单例"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


def get_config() -> Config:
    """快捷函数：获取配置"""
    return get_config_manager().load()


# 快捷函数
def get_data_dir() -> Path:
    """获取数据目录"""
    config = get_config()
    return Path(config.data_dir)


def get_db_path() -> Path:
    """获取数据库路径"""
    config = get_config()
    data_dir = Path(config.data_dir)
    return data_dir / config.sqlite_db


def get_chroma_path() -> Path:
    """获取 ChromaDB 路径"""
    config = get_config()
    data_dir = Path(config.data_dir)
    return data_dir / config.chroma_dir
