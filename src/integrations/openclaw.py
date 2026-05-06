"""
OpenClaw 集成模块

提供与 OpenClaw 网关的集成能力：
- 插件注册与配置
- Skill 调用桥接
- 飞书渠道联动
- 记忆服务 API
"""

import json
import os
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List

from src.core.models import Memory
from src.storage.sqlite_store import SQLiteStore
from src.storage.chroma_store import ChromaStore
from src.retrieval.engine import RetrievalEngine
from src.retrieval.embeddings import encode_text
from src.core.forgetting import EbbinghausForgettingEngine
from src.config.config_manager import get_config, get_data_dir
from src.logger.logger import get_logger


logger = get_logger(__name__)


class OpenClawBridge:
    """
    OpenClaw 桥接器

    连接 Claw Memory Engine 与 OpenClaw 网关，
    提供记忆服务的标准化接口
    """

    def __init__(self):
        self.sqlite = SQLiteStore()
        self.chroma = ChromaStore()
        self.engine = RetrievalEngine(
            sqlite_store=self.sqlite,
            chroma_store=self.chroma
        )
        self.forgetting = EbbinghausForgettingEngine(self.sqlite)
        self._openclaw_config_dir = Path.home() / ".openclaw"

    def _get_project_root(self) -> Path:
        """获取项目根目录"""
        current = Path(__file__).resolve()
        for parent in current.parents:
            if (parent / "openclaw.plugin.json").exists():
                return parent
        return Path(__file__).parent.parent

    def get_plugin_manifest(self) -> Dict[str, Any]:
        """获取插件清单"""
        manifest_path = self._get_project_root() / "openclaw.plugin.json"
        if manifest_path.exists():
            with open(manifest_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def get_skills_list(self) -> List[Dict[str, str]]:
        """获取所有可用 Skills"""
        skills_dir = self._get_project_root() / "openclaw-skills"
        skills = []

        if not skills_dir.exists():
            return skills

        for skill_dir in skills_dir.iterdir():
            if skill_dir.is_dir():
                skill_md = skill_dir / "SKILL.md"
                if skill_md.exists():
                    skill_info = self._parse_skill_md(skill_md)
                    if skill_info:
                        skills.append(skill_info)

        return skills

    def _parse_skill_md(self, skill_md: Path) -> Optional[Dict[str, str]]:
        """解析 SKILL.md 的 frontmatter"""
        try:
            with open(skill_md, 'r', encoding='utf-8') as f:
                content = f.read()

            if not content.startswith("---"):
                return {"name": skill_md.parent.name, "path": str(skill_md)}

            end = content.find("---", 3)
            if end == -1:
                return {"name": skill_md.parent.name, "path": str(skill_md)}

            frontmatter = content[3:end].strip()
            info = {"path": str(skill_md)}

            for line in frontmatter.split("\n"):
                if ":" in line:
                    key, value = line.split(":", 1)
                    info[key.strip()] = value.strip()

            return info

        except Exception as e:
            logger.error(f"Failed to parse skill: {skill_md}, error: {e}")
            return None

    def install_to_openclaw(self) -> bool:
        """
        安装插件到 OpenClaw

        将当前项目注册为 OpenClaw 插件
        """
        config_dir = self._openclaw_config_dir
        workspace_dir = config_dir / "workspace" / "skills"

        workspace_dir.mkdir(parents=True, exist_ok=True)

        skills_src = self._get_project_root() / "openclaw-skills"
        if skills_src.exists():
            for skill_dir in skills_src.iterdir():
                if skill_dir.is_dir():
                    dest = workspace_dir / skill_dir.name
                    if not dest.exists():
                        import shutil
                        shutil.copytree(skill_dir, dest)
                        logger.info(f"Installed skill: {skill_dir.name}")

        plugin_src = self._get_project_root() / "openclaw.plugin.json"
        if plugin_src.exists():
            plugins_dir = config_dir / "plugins" / "claw-memory-engine"
            plugins_dir.mkdir(parents=True, exist_ok=True)

            import shutil
            shutil.copy2(plugin_src, plugins_dir / "openclaw.plugin.json")

            plugin_code_src = self._get_project_root() / "openclaw-plugin"
            if plugin_code_src.exists():
                for f in plugin_code_src.iterdir():
                    shutil.copy2(f, plugins_dir / f.name)

            logger.info("Plugin installed to OpenClaw")

        return True

    def configure_openclaw_channel(self, app_id: str, app_secret: str) -> bool:
        """
        配置 OpenClaw 飞书渠道

        Args:
            app_id: 飞书 App ID
            app_secret: 飞书 App Secret
        """
        try:
            subprocess.run(
                ["openclaw", "config", "set", "--",
                 "channels.feishu.appId", app_id],
                capture_output=True, text=True, timeout=10
            )
            subprocess.run(
                ["openclaw", "config", "set", "--",
                 "channels.feishu.appSecret", app_secret],
                capture_output=True, text=True, timeout=10
            )
            subprocess.run(
                ["openclaw", "config", "set", "--",
                 "channels.feishu.enabled", "true"],
                capture_output=True, text=True, timeout=10
            )
            logger.info("OpenClaw Feishu channel configured")
            return True
        except FileNotFoundError:
            logger.warning("OpenClaw CLI not found. Install with: npm i -g openclaw")
            return False
        except Exception as e:
            logger.error(f"Failed to configure OpenClaw: {e}")
            return False

    def memory_store(self, alias: str, command: str,
                     description: str = None, tags: List[str] = None,
                     project: str = None) -> Dict[str, Any]:
        """
        存储记忆（OpenClaw Skill 调用入口）

        Returns:
            操作结果
        """
        import os
        from datetime import datetime

        if project is None:
            from src.retrieval.engine import ContextManager
            ctx_manager = ContextManager()
            context = ctx_manager.detect_context(os.getcwd())
            project = context.git_root

        tag_list = tags or []

        existing = self.engine.find_by_alias(alias, project)

        if existing:
            existing.command = command
            existing.description = description
            existing.tags = tag_list if tag_list else existing.tags
            existing.updated_at = datetime.now()

            self.sqlite.update_memory(existing)

            embedding = encode_text(f"{alias} {command} {description or ''}")
            if embedding:
                self.chroma.update_memory(existing, embedding)

            return {
                "success": True,
                "action": "updated",
                "alias": alias,
                "command": command,
                "project": project or "global"
            }
        else:
            memory = Memory(
                alias=alias,
                command=command,
                description=description,
                tags=tag_list,
                project=project,
            )

            self.sqlite.create_memory(memory)

            embedding = encode_text(f"{alias} {command} {description or ''}")
            if embedding:
                self.chroma.add_memory(memory, embedding)

            return {
                "success": True,
                "action": "created",
                "alias": alias,
                "command": command,
                "project": project or "global"
            }

    def memory_recall(self, query: str, project: str = None,
                      limit: int = 10) -> Dict[str, Any]:
        """
        检索记忆（OpenClaw Skill 调用入口）

        Returns:
            搜索结果
        """
        results = self.engine.search(query, project, limit)

        return {
            "success": True,
            "query": query,
            "count": len(results),
            "results": [
                {
                    "alias": r.memory.alias,
                    "command": r.memory.command,
                    "description": r.memory.description,
                    "project": r.memory.project,
                    "score": r.score,
                    "match_type": r.match_type,
                    "frequency": r.memory.frequency,
                }
                for r in results
            ]
        }

    def memory_list(self, project: str = None,
                    limit: int = 20) -> Dict[str, Any]:
        """
        列出记忆（OpenClaw Skill 调用入口）

        Returns:
            记忆列表
        """
        if project:
            memories = self.sqlite.find_by_project(project)
        else:
            memories = self.sqlite.find_all_active(limit=limit)

        return {
            "success": True,
            "count": len(memories),
            "memories": [
                {
                    "alias": m.alias,
                    "command": m.command,
                    "project": m.project,
                    "frequency": m.frequency,
                    "last_used": m.last_used_at.isoformat(),
                }
                for m in memories
            ]
        }

    def memory_forgetting_status(self) -> Dict[str, Any]:
        """
        获取遗忘状态（OpenClaw Skill 调用入口）

        Returns:
            遗忘状态概览
        """
        all_memories = self.sqlite.find_all_active(limit=1000)

        healthy = 0
        review_needed = 0
        expiring_soon = 0
        expired = 0

        details = []

        for mem in all_memories:
            retention, status = self.forgetting.calculate_retention(mem)

            if status.value == "healthy":
                healthy += 1
            elif status.value == "review_needed":
                review_needed += 1
            elif status.value == "expiring_soon":
                expiring_soon += 1
            elif status.value == "expired":
                expired += 1

            if status.value in ["review_needed", "expiring_soon"]:
                details.append({
                    "alias": mem.alias,
                    "command": mem.command,
                    "retention": round(retention, 2),
                    "status": status.value,
                    "frequency": mem.frequency,
                })

        return {
            "success": True,
            "total": len(all_memories),
            "summary": {
                "healthy": healthy,
                "review_needed": review_needed,
                "expiring_soon": expiring_soon,
                "expired": expired,
            },
            "attention_needed": details,
        }


_openclaw_bridge: Optional[OpenClawBridge] = None


def get_openclaw_bridge() -> OpenClawBridge:
    """获取 OpenClaw 桥接器单例"""
    global _openclaw_bridge
    if _openclaw_bridge is None:
        _openclaw_bridge = OpenClawBridge()
    return _openclaw_bridge
