"""
项目检测工具

自动检测当前工作目录的项目信息
"""

import os
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List


class ProjectDetector:
    """
    项目检测器

    支持检测的项目类型：
    - Git 仓库
    - Python 项目（有 pyproject.toml/setup.py）
    - Node.js 项目（有 package.json）
    - Rust 项目（有 Cargo.toml）
    - Go 项目（有 go.mod）
    """

    # 项目标识文件
    PROJECT_MARKERS = {
        "git": [".git"],
        "python": ["pyproject.toml", "setup.py", "requirements.txt"],
        "node": ["package.json"],
        "rust": ["Cargo.toml"],
        "go": ["go.mod"],
        "java": ["pom.xml", "build.gradle"],
    }

    def __init__(self):
        pass

    def detect_project_type(self, path: Optional[str] = None) -> Optional[str]:
        """
        检测项目类型

        Args:
            path: 目录路径，默认为当前目录

        Returns:
            项目类型字符串，如 "git", "python", "node" 等
        """
        check_path = Path(path or os.getcwd())

        for project_type, markers in self.PROJECT_MARKERS.items():
            for marker in markers:
                if (check_path / marker).exists():
                    return project_type

        return None

    def find_project_root(self, path: Optional[str] = None) -> Optional[Path]:
        """
        向上查找项目根目录

        Args:
            path: 起始路径

        Returns:
            项目根目录路径
        """
        current = Path(path or os.getcwd()).resolve()

        # 最多向上查找 10 层
        max_depth = 10
        depth = 0

        while current != current.parent and depth < max_depth:
            # 检查是否是 Git 仓库
            if (current / ".git").exists():
                return current

            # 检查其他项目类型
            for markers in self.PROJECT_MARKERS.values():
                for marker in markers:
                    if (current / marker).exists():
                        return current

            current = current.parent
            depth += 1

        return None

    def get_project_info(self, path: Optional[str] = None) -> Dict[str, Any]:
        """
        获取项目完整信息

        Args:
            path: 目录路径

        Returns:
            项目信息字典
        """
        check_path = Path(path or os.getcwd())
        root = self.find_project_root(path)

        if root is None:
            return {
                "is_project": False,
                "type": None,
                "name": check_path.name,
                "root": str(check_path),
            }

        project_type = self.detect_project_type(root)
        project_name = root.name

        # 获取 Git 分支信息
        git_branch = None
        if project_type == "git":
            git_branch = self._get_git_branch(root)

        return {
            "is_project": True,
            "type": project_type,
            "name": project_name,
            "root": str(root),
            "git_branch": git_branch,
        }

    def _get_git_branch(self, repo_path: Path) -> Optional[str]:
        """获取 Git 当前分支"""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None

    def get_context_path(self, path: Optional[str] = None) -> str:
        """
        获取用于存储的上下文路径

        返回项目根目录（如果有），否则返回当前目录
        """
        root = self.find_project_root(path)
        return str(root) if root else str(Path(path or os.getcwd()).resolve())


# 快捷函数
_detector: Optional[ProjectDetector] = None


def get_detector() -> ProjectDetector:
    """获取检测器单例"""
    global _detector
    if _detector is None:
        _detector = ProjectDetector()
    return _detector


def detect_project(path: Optional[str] = None) -> Dict[str, Any]:
    """快捷函数：检测项目"""
    return get_detector().get_project_info(path)


def find_project_root(path: Optional[str] = None) -> Optional[str]:
    """快捷函数：查找项目根目录"""
    root = get_detector().find_project_root(path)
    return str(root) if root else None
