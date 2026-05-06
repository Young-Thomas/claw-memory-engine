"""
隐式记忆模块

自动解析 shell 命令历史文件，统计频率，提取高频命令模式
支持：bash (.bash_history)、zsh (.zsh_history)、PowerShell (PSReadLine)
"""

import os
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from src.core.models import Memory
from src.storage.sqlite_store import SQLiteStore
from src.storage.chroma_store import ChromaStore
from src.retrieval.embeddings import encode_text
from src.logger.logger import get_logger


logger = get_logger(__name__)

IGNORED_COMMANDS = {
    "ls", "cd", "pwd", "clear", "exit", "history", "cat", "echo",
    "man", "which", "type", "alias", "export", "source", ".",
    "git status", "git diff", "git log", "git branch",
    "dir", "cls", "set", "ver", "help",
    "ll", "la", "l", "..", "...",
}

IGNORED_PREFIXES = (
    "cd ", "ls ", "pwd", "clear", "exit", "history",
    "cat ", "echo ", "man ", "which ", "type ",
    "git status", "git diff", "git log", "git branch -",
    "dir ", "cls", "set ", "ver",
)

MIN_COMMAND_LENGTH = 6
MIN_FREQUENCY = 3
MAX_IMPLICIT_MEMORIES = 50


class ShellHistoryParser:
    """Shell 命令历史解析器"""

    def __init__(self):
        self.home = Path.home()

    def get_history_files(self) -> List[Path]:
        """获取所有可用的历史文件"""
        files = []

        bash_history = self.home / ".bash_history"
        if bash_history.exists():
            files.append(bash_history)

        zsh_history = self.home / ".zsh_history"
        if zsh_history.exists():
            files.append(zsh_history)

        if sys.platform == "win32":
            ps_history = self._get_powershell_history()
            if ps_history:
                files.append(ps_history)

        return files

    def _get_powershell_history(self) -> Optional[Path]:
        """获取 PowerShell 历史文件路径"""
        ps_path = (
            Path(os.environ.get("APPDATA", ""))
            / "Microsoft"
            / "Windows"
            / "PowerShell"
            / "PSReadLine"
            / "ConsoleHost_history.txt"
        )
        if ps_path.exists():
            return ps_path
        return None

    def parse_bash_history(self, path: Path) -> List[str]:
        """解析 bash 历史文件"""
        commands = []
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        commands.append(line)
        except Exception as e:
            logger.error(f"Failed to parse bash history {path}: {e}")
        return commands

    def parse_zsh_history(self, path: Path) -> List[str]:
        """解析 zsh 历史文件（处理时间戳前缀）"""
        commands = []
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    cleaned = re.sub(r"^:\s*\d+:\d+;", "", line)
                    if cleaned and not cleaned.startswith("#"):
                        commands.append(cleaned)
        except Exception as e:
            logger.error(f"Failed to parse zsh history {path}: {e}")
        return commands

    def parse_powershell_history(self, path: Path) -> List[str]:
        """解析 PowerShell 历史文件"""
        commands = []
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        commands.append(line)
        except Exception as e:
            logger.error(f"Failed to parse PowerShell history {path}: {e}")
        return commands

    def parse_all(self) -> List[str]:
        """解析所有历史文件"""
        all_commands = []
        for path in self.get_history_files():
            if "bash_history" in str(path):
                all_commands.extend(self.parse_bash_history(path))
            elif "zsh_history" in str(path):
                all_commands.extend(self.parse_zsh_history(path))
            elif "ConsoleHost_history" in str(path):
                all_commands.extend(self.parse_powershell_history(path))
            else:
                all_commands.extend(self.parse_bash_history(path))
        return all_commands


class ImplicitMemoryEngine:
    """隐式记忆引擎"""

    def __init__(self):
        self.parser = ShellHistoryParser()

    def _is_ignored(self, command: str) -> bool:
        """判断命令是否应该被忽略"""
        cmd_lower = command.strip().lower()
        if cmd_lower in IGNORED_COMMANDS:
            return True
        for prefix in IGNORED_PREFIXES:
            if cmd_lower.startswith(prefix.lower()):
                return True
        if len(cmd_lower) < MIN_COMMAND_LENGTH:
            return True
        return False

    def _normalize_command(self, command: str) -> str:
        """标准化命令（移除参数中的路径和变量部分）"""
        command = command.strip()
        command = re.sub(r"\s+", " ", command)
        return command

    def _generate_alias(self, command: str, index: int) -> str:
        """为命令生成别名"""
        parts = command.split()
        if not parts:
            return f"cmd-{index}"

        base = parts[0]
        if len(parts) > 1:
            second = parts[1].lstrip("-")
            if second and second != base:
                alias = f"{base}-{second}"
            else:
                alias = base
        else:
            alias = base

        alias = re.sub(r"[^a-zA-Z0-9_-]", "-", alias)
        alias = alias.strip("-")

        if not alias:
            alias = f"cmd-{index}"

        return alias

    def extract_frequent_commands(
        self, min_freq: int = MIN_FREQUENCY
    ) -> List[Tuple[str, int]]:
        """
        提取高频命令

        Returns:
            (命令, 频率) 列表，按频率降序排列
        """
        all_commands = self.parser.parse_all()
        logger.info(f"Parsed {len(all_commands)} commands from history")

        filtered = [self._normalize_command(c) for c in all_commands if not self._is_ignored(c)]

        counter = Counter(filtered)
        frequent = [
            (cmd, freq) for cmd, freq in counter.most_common()
            if freq >= min_freq
        ]

        logger.info(f"Found {len(frequent)} frequent commands (freq >= {min_freq})")
        return frequent

    def sync_to_memory(
        self,
        min_freq: int = MIN_FREQUENCY,
        max_memories: int = MAX_IMPLICIT_MEMORIES,
        project: Optional[str] = None,
    ) -> Dict[str, int]:
        """
        将高频命令同步到记忆引擎

        Returns:
            统计信息 {"created": n, "updated": n, "skipped": n}
        """
        frequent = self.extract_frequent_commands(min_freq)
        sqlite = SQLiteStore()
        chroma = ChromaStore()

        stats = {"created": 0, "updated": 0, "skipped": 0}

        for i, (command, freq) in enumerate(frequent[:max_memories]):
            alias = self._generate_alias(command, i)

            existing_list = sqlite.find_by_alias(alias, project)
            if existing_list:
                existing = existing_list[0]
                if existing.frequency < freq:
                    existing.frequency = freq
                    existing.last_used_at = datetime.now()
                    if not existing.description:
                        existing.description = f"Auto-detected (used {freq} times)"
                    if "implicit" not in existing.tags:
                        existing.tags = existing.tags + ["implicit"]
                    sqlite.update_memory(existing)

                    embedding = encode_text(f"{alias} {command}")
                    if embedding:
                        chroma.update_memory(existing, embedding)

                    stats["updated"] += 1
                else:
                    stats["skipped"] += 1
            else:
                memory = Memory(
                    alias=alias,
                    command=command,
                    description=f"Auto-detected (used {freq} times)",
                    tags=["implicit", "auto"],
                    project=project,
                    frequency=freq,
                )
                sqlite.create_memory(memory)

                embedding = encode_text(f"{alias} {command}")
                if embedding:
                    chroma.add_memory(memory, embedding)

                stats["created"] += 1

        logger.info(f"Implicit memory sync: {stats}")
        return stats

    def get_history_stats(self) -> Dict[str, any]:
        """获取历史统计信息"""
        history_files = self.parser.get_history_files()
        all_commands = self.parser.parse_all()
        frequent = self.extract_frequent_commands()

        return {
            "history_files": [str(f) for f in history_files],
            "total_commands": len(all_commands),
            "frequent_commands": len(frequent),
            "top_10": frequent[:10],
        }
