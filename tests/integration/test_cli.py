"""
CLI 集成测试
"""

import subprocess
import sys
import pytest


class TestCLIIntegration:
    """CLI 集成测试"""

    def test_cli_help(self):
        """测试帮助命令"""
        result = subprocess.run(
            [sys.executable, "-m", "src.cli.main", "--help"],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0
        assert "Claw Memory Engine" in result.stdout

    def test_cli_version(self):
        """测试版本命令"""
        result = subprocess.run(
            [sys.executable, "-m", "src.cli.main", "--version"],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0
        assert "v" in result.stdout

    def test_cli_remember_and_list(self, tmp_path):
        """测试记忆和列出功能"""
        import os
        import tempfile

        # 设置临时数据目录
        test_db = tmp_path / "test.db"
        env = os.environ.copy()
        env["CLAW_DB_PATH"] = str(test_db)

        # 测试记忆命令
        result = subprocess.run(
            [
                sys.executable, "-m", "src.cli.main",
                "remember", "test-cmd", "echo hello"
            ],
            capture_output=True,
            text=True,
            env=env
        )

        assert result.returncode == 0
        assert "已记录" in result.stdout or "成功" in result.stdout
