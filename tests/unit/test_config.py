"""
配置系统测试
"""

import pytest
import tempfile
from pathlib import Path
import os

from src.config.config_manager import Config, ConfigManager, get_config_manager


class TestConfigManager:
    """配置管理器测试"""

    @pytest.fixture
    def temp_config_dir(self):
        """创建临时配置目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_singleton(self):
        """测试单例模式"""
        cm1 = ConfigManager()
        cm2 = ConfigManager()

        assert cm1 is cm2

    def test_default_config(self, temp_config_dir):
        """测试默认配置"""
        # 设置环境变量
        os.environ["CLAW_CONFIG_FILE"] = str(temp_config_dir / "nonexistent.json")

        cm = get_config_manager()
        config = cm.load()

        assert config.data_dir is not None
        assert config.sqlite_db == "claw.db"
        assert config.chroma_dir == "chroma_db"
        assert config.embedding_model == "all-MiniLM-L6-v2"
        assert config.search_limit == 10
        assert config.log_level == "INFO"

    def test_save_and_load(self, temp_config_dir):
        """测试保存和加载"""
        config_file = temp_config_dir / "config.json"
        os.environ["CLAW_CONFIG_FILE"] = str(config_file)

        cm = ConfigManager()
        config = Config(data_dir=str(temp_config_dir / "data"))

        cm.save(config)

        # 验证文件存在
        assert config_file.exists()

        # 重新加载
        cm2 = ConfigManager()
        loaded_config = cm2.load()

        assert loaded_config.data_dir == str(temp_config_dir / "data")

    def test_get_set(self, temp_config_dir):
        """测试获取和设置配置项"""
        config_file = temp_config_dir / "config.json"
        os.environ["CLAW_CONFIG_FILE"] = str(config_file)

        cm = get_config_manager()

        # 设置
        cm.set("search_limit", 20)

        # 获取
        assert cm.get("search_limit") == 20

        # 获取不存在的键
        assert cm.get("nonexistent", "default") == "default"

    def test_reset(self, temp_config_dir):
        """测试重置配置"""
        config_file = temp_config_dir / "config.json"
        os.environ["CLAW_CONFIG_FILE"] = str(config_file)

        cm = get_config_manager()

        # 修改配置
        cm.set("search_limit", 99)

        # 重置
        cm.reset()

        # 验证恢复默认值
        assert cm.get("search_limit") == 10
