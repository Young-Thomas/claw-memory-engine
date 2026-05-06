"""
团队共享记忆引擎

支持团队级记忆的注入、共享和遗忘管理
- 团队记忆注入 API
- 共享作用域（personal / team:{team_id} / project:{path}）
- 版本覆盖（信息更新后自动废弃旧版本）
- 团队级遗忘曲线提醒
"""

from datetime import datetime
from typing import Optional, List, Dict, Any

from src.core.models import Memory
from src.storage.sqlite_store import SQLiteStore
from src.storage.chroma_store import ChromaStore
from src.retrieval.embeddings import encode_text
from src.retrieval.engine import RetrievalEngine
from src.core.forgetting import EbbinghausForgettingEngine
from src.logger.logger import get_logger


logger = get_logger(__name__)


SCOPE_PERSONAL = "personal"
SCOPE_TEAM_PREFIX = "team:"
SCOPE_PROJECT_PREFIX = "project:"


class TeamMemoryEngine:
    """团队共享记忆引擎"""

    def __init__(self):
        self.sqlite = SQLiteStore()
        self.chroma = ChromaStore()
        self.engine = RetrievalEngine(sqlite_store=self.sqlite, chroma_store=self.chroma)
        self.forgetting = EbbinghausForgettingEngine(self.sqlite)

    def inject(
        self,
        content: str,
        alias: Optional[str] = None,
        scope: str = SCOPE_PERSONAL,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        chat_id: Optional[str] = None,
        injected_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        注入团队记忆

        Args:
            content: 记忆内容
            alias: 别名（可选，自动生成）
            scope: 作用域（personal / team:{team_id} / project:{path}）
            description: 描述
            tags: 标签
            chat_id: 飞书群聊ID（用于推送通知）
            injected_by: 注入者

        Returns:
            操作结果
        """
        if alias is None:
            alias = self._generate_alias(content, scope)

        tag_list = list(tags or [])
        if "team" not in tag_list and scope.startswith(SCOPE_TEAM_PREFIX):
            tag_list.append("team")
        if "shared" not in tag_list and scope != SCOPE_PERSONAL:
            tag_list.append("shared")

        project = None
        if scope.startswith(SCOPE_PROJECT_PREFIX):
            project = scope[len(SCOPE_PROJECT_PREFIX):]

        existing = self.sqlite.find_by_alias(alias, project)

        if existing:
            old = existing[0]
            old_version = old.version
            old.command = content
            old.description = description or old.description
            old.tags = list(set(old.tags + tag_list))
            old.version = old_version + 1
            old.parent_id = old.id
            old.updated_at = datetime.now()

            self.sqlite.update_memory(old)

            embedding = encode_text(f"{alias} {content} {description or ''}")
            if embedding:
                self.chroma.update_memory(old, embedding)

            result = {
                "success": True,
                "action": "updated",
                "alias": alias,
                "scope": scope,
                "version": old.version,
                "injected_by": injected_by,
            }
        else:
            memory = Memory(
                alias=alias,
                command=content,
                description=description,
                tags=tag_list,
                project=project,
            )

            self.sqlite.create_memory(memory)

            embedding = encode_text(f"{alias} {content} {description or ''}")
            if embedding:
                self.chroma.add_memory(memory, embedding)

            result = {
                "success": True,
                "action": "created",
                "alias": alias,
                "scope": scope,
                "version": 1,
                "injected_by": injected_by,
            }

        if chat_id:
            self._notify_team(chat_id, alias, content, scope, result["action"], injected_by)

        return result

    def list_team_memories(self, scope: str, limit: int = 50) -> Dict[str, Any]:
        """
        列出团队/项目作用域的记忆

        Args:
            scope: 作用域
            limit: 最大数量

        Returns:
            记忆列表
        """
        if scope.startswith(SCOPE_PROJECT_PREFIX):
            project = scope[len(SCOPE_PROJECT_PREFIX):]
            memories = self.sqlite.find_by_project(project)
        elif scope.startswith(SCOPE_TEAM_PREFIX):
            all_memories = self.sqlite.find_all_active(limit=limit * 2)
            memories = [
                m for m in all_memories
                if "team" in m.tags or "shared" in m.tags
            ][:limit]
        else:
            memories = self.sqlite.find_all_active(limit=limit)

        return {
            "success": True,
            "scope": scope,
            "count": len(memories),
            "memories": [
                {
                    "alias": m.alias,
                    "content": m.command,
                    "description": m.description,
                    "tags": m.tags,
                    "project": m.project,
                    "frequency": m.frequency,
                    "version": m.version,
                    "last_used": m.last_used_at.isoformat(),
                }
                for m in memories
            ],
        }

    def check_team_forgetting(self, scope: str, chat_id: Optional[str] = None) -> Dict[str, Any]:
        """
        检查团队记忆的遗忘状态

        Args:
            scope: 作用域
            chat_id: 飞书群聊ID

        Returns:
            遗忘状态
        """
        if scope.startswith(SCOPE_PROJECT_PREFIX):
            project = scope[len(SCOPE_PROJECT_PREFIX):]
            memories = self.sqlite.find_by_project(project)
        elif scope.startswith(SCOPE_TEAM_PREFIX):
            all_memories = self.sqlite.find_all_active(limit=500)
            memories = [
                m for m in all_memories
                if "team" in m.tags or "shared" in m.tags
            ]
        else:
            memories = self.sqlite.find_all_active(limit=100)

        expiring = []
        review_needed = []

        for mem in memories:
            retention, status = self.forgetting.calculate_retention(mem)
            if status.value == "expiring_soon":
                expiring.append({
                    "alias": mem.alias,
                    "content": mem.command,
                    "retention": round(retention, 2),
                })
            elif status.value == "review_needed":
                review_needed.append({
                    "alias": mem.alias,
                    "content": mem.command,
                    "retention": round(retention, 2),
                })

        if chat_id and (expiring or review_needed):
            self._send_forgetting_reminder(chat_id, expiring, review_needed, scope)

        return {
            "success": True,
            "scope": scope,
            "expiring_soon": len(expiring),
            "review_needed": len(review_needed),
            "expiring_details": expiring,
            "review_details": review_needed,
        }

    def _generate_alias(self, content: str, scope: str) -> str:
        """为团队记忆生成别名"""
        import re
        prefix = "team"
        if scope.startswith(SCOPE_TEAM_PREFIX):
            team_id = scope[len(SCOPE_TEAM_PREFIX):]
            prefix = f"team-{team_id[:8]}"
        elif scope.startswith(SCOPE_PROJECT_PREFIX):
            prefix = "project"

        content_part = content[:15].strip()
        content_part = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff_-]", "-", content_part)
        content_part = content_part.strip("-")

        return f"{prefix}-{content_part}" if content_part else f"{prefix}-note-{int(datetime.now().timestamp())}"

    def _notify_team(self, chat_id: str, alias: str, content: str,
                     scope: str, action: str, injected_by: Optional[str] = None):
        """推送团队记忆通知到飞书"""
        try:
            from src.integrations.feishu import get_feishu_client
            feishu = get_feishu_client()
            if feishu:
                action_text = "更新" if action == "updated" else "注入"
                by_text = f" (by {injected_by})" if injected_by else ""
                feishu.send_text_message(
                    chat_id,
                    f"📢 团队记忆已{action_text}{by_text}\n"
                    f"别名: {alias}\n"
                    f"内容: {content}\n"
                    f"作用域: {scope}"
                )
        except Exception as e:
            logger.error(f"Failed to notify team: {e}")

    def _send_forgetting_reminder(self, chat_id: str, expiring: list,
                                  review_needed: list, scope: str):
        """发送遗忘提醒到飞书"""
        try:
            from src.integrations.feishu import get_feishu_client
            feishu = get_feishu_client()
            if feishu:
                lines = [f"⚠️ 团队记忆遗忘提醒 (作用域: {scope})\n"]

                if expiring:
                    lines.append("🔴 即将过期:")
                    for item in expiring:
                        lines.append(f"  • {item['alias']}: {item['content'][:50]} (保留率: {item['retention']:.0%})")

                if review_needed:
                    lines.append("\n🟡 需要复习:")
                    for item in review_needed:
                        lines.append(f"  • {item['alias']}: {item['content'][:50]} (保留率: {item['retention']:.0%})")

                lines.append("\n回复 '我已记住 <别名>' 来重置遗忘曲线")

                feishu.send_text_message(chat_id, "\n".join(lines))
        except Exception as e:
            logger.error(f"Failed to send forgetting reminder: {e}")
