"""
Shell 补全测试
"""

import pytest

from src.cli.completion import (
    generate_bash_completion,
    generate_zsh_completion,
)


class TestCompletion:
    """补全脚本生成测试"""

    def test_bash_completion_generation(self):
        """测试 Bash 补全脚本生成"""
        script = generate_bash_completion()

        assert "_claw_completion" in script
        assert "complete -F _claw_completion claw" in script
        assert "claw _complete-aliases" in script

    def test_zsh_completion_generation(self):
        """测试 Zsh 补全脚本生成"""
        script = generate_zsh_completion()

        assert "#compdef claw" in script
        assert "_claw_commands" in script
        assert "_claw_get_aliases" in script

    def test_bash_completion_commands(self):
        """测试 Bash 补全命令列表"""
        script = generate_bash_completion()

        # 验证包含所有命令
        assert "remember" in script
        assert "find" in script
        assert "list" in script
        assert "show" in script
        assert "delete" in script

    def test_zsh_completion_commands(self):
        """测试 Zsh 补全命令列表"""
        script = generate_zsh_completion()

        # 验证包含所有命令
        assert "'remember:Record a new command'" in script
        assert "'find:Search memories by query'" in script
        assert "'list:List all memories'" in script
