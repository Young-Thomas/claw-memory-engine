"""
决策提取引擎

从飞书对话/文本中自动提取结构化决策记忆
支持：关键词模式匹配 + 语义理解
决策结构：决策内容 + 理由 + 结论 + 反对意见 + 关联项目
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any

from src.core.models import Memory
from src.storage.sqlite_store import SQLiteStore
from src.storage.chroma_store import ChromaStore
from src.retrieval.embeddings import encode_text
from src.logger.logger import get_logger


logger = get_logger(__name__)


@dataclass
class Decision:
    """结构化决策"""
    content: str
    reason: Optional[str] = None
    conclusion: Optional[str] = None
    opposition: Optional[str] = None
    context: Optional[str] = None
    project: Optional[str] = None
    source: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)

    def to_memory(self, alias: Optional[str] = None) -> Memory:
        """转换为 Memory 对象"""
        if alias is None:
            alias = self._generate_alias()

        description_parts = []
        if self.reason:
            description_parts.append(f"理由: {self.reason}")
        if self.conclusion:
            description_parts.append(f"结论: {self.conclusion}")
        if self.opposition:
            description_parts.append(f"反对: {self.opposition}")

        description = " | ".join(description_parts) if description_parts else self.content

        return Memory(
            alias=alias,
            command=self.content,
            description=description,
            tags=["decision"],
            project=self.project,
        )

    def _generate_alias(self) -> str:
        """为决策生成别名"""
        content = self.content[:20].strip()
        alias = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff_-]", "-", content)
        alias = alias.strip("-")
        if not alias:
            alias = f"decision-{int(self.timestamp.timestamp())}"
        return f"decision-{alias}"


DECISION_PATTERNS = [
    {
        "name": "explicit_decision",
        "patterns": [
            r"我们决定(.+?)(?:[，。,\.]|$)",
            r"决定(?:采用|使用|选)(.+?)(?:[，。,\.]|$)",
            r"最终决定(.+?)(?:[，。,\.]|$)",
            r"we decided (?:to |that )?(.+?)(?:[,\.]|$)",
            r"decision:?\s*(.+?)(?:[,\.]|$)",
        ],
        "type": "decision",
    },
    {
        "name": "reason_pattern",
        "patterns": [
            r"(?:因为|由于|原因是|理由是|because|since|reason:)\s*(.+?)(?:[，。,\.]|$)",
        ],
        "type": "reason",
    },
    {
        "name": "conclusion_pattern",
        "patterns": [
            r"(?:所以|因此|结论是|最终|总之|therefore|conclusion:)\s*(.+?)(?:[，。,\.]|$)",
            r"(?:确认|敲定|定了|confirmed:)\s*(.+?)(?:[，。,\.]|$)",
        ],
        "type": "conclusion",
    },
    {
        "name": "opposition_pattern",
        "patterns": [
            r"(?:但是|不过|反对|不同意|but|however|opposed:)\s*(.+?)(?:[，。,\.]|$)",
            r"(?:不用|不要|放弃|不用)\s*(.+?)(?:[，。,\.]|$)",
        ],
        "type": "opposition",
    },
    {
        "name": "choice_pattern",
        "patterns": [
            r"(.+?)还是(.+?)[，,]选(.+?)(?:[，。,\.]|$)",
            r"(.+?)vs(.+?)[，,]选(.+?)(?:[，。,\.]|$)",
            r"(?:方案|选项)[ABCD][:：]\s*(.+?)(?:[，。,\.]|$)",
        ],
        "type": "choice",
    },
    {
        "name": "deadline_pattern",
        "patterns": [
            r"(?:截止日期|deadline|due date|ddl)[:：]?\s*(.+?)(?:[，。,\.]|$)",
            r"(?:确认|定了).{0,5}(?:日期|时间|期限)[:：]?\s*(.+?)(?:[，。,\.]|$)",
        ],
        "type": "deadline",
    },
]


class DecisionEngine:
    """决策提取引擎"""

    def __init__(self):
        self._compiled_patterns = []
        for group in DECISION_PATTERNS:
            for pattern in group["patterns"]:
                self._compiled_patterns.append({
                    "compiled": re.compile(pattern, re.IGNORECASE),
                    "name": group["name"],
                    "type": group["type"],
                })

    def extract(self, text: str, context: Optional[str] = None,
                project: Optional[str] = None,
                source: Optional[str] = None) -> List[Decision]:
        """
        从文本中提取决策

        Args:
            text: 输入文本（飞书消息、文档段落等）
            context: 上下文信息
            project: 关联项目
            source: 来源（如飞书群聊ID）

        Returns:
            提取到的决策列表
        """
        decisions = []
        extracted = {
            "decision": [],
            "reason": [],
            "conclusion": [],
            "opposition": [],
            "choice": [],
            "deadline": [],
        }

        for pattern_info in self._compiled_patterns:
            matches = pattern_info["compiled"].findall(text)
            for match in matches:
                content = match.strip() if isinstance(match, str) else match[0].strip()
                if content and len(content) >= 2:
                    extracted[pattern_info["type"]].append(content)

        if extracted["decision"]:
            for i, dec_content in enumerate(extracted["decision"]):
                decision = Decision(
                    content=dec_content,
                    reason=extracted["reason"][i] if i < len(extracted["reason"]) else (
                        extracted["reason"][0] if extracted["reason"] else None
                    ),
                    conclusion=extracted["conclusion"][i] if i < len(extracted["conclusion"]) else (
                        extracted["conclusion"][0] if extracted["conclusion"] else None
                    ),
                    opposition=extracted["opposition"][i] if i < len(extracted["opposition"]) else None,
                    context=context or text[:100],
                    project=project,
                    source=source,
                )
                decisions.append(decision)

        if extracted["choice"]:
            for choice in extracted["choice"]:
                decision = Decision(
                    content=f"选择: {choice}",
                    context=context or text[:100],
                    project=project,
                    source=source,
                )
                decisions.append(decision)

        if extracted["deadline"] and not extracted["decision"]:
            for dl in extracted["deadline"]:
                decision = Decision(
                    content=f"截止日期: {dl}",
                    conclusion=dl,
                    context=context or text[:100],
                    project=project,
                    source=source,
                )
                decisions.append(decision)

        if not decisions and self._has_decision_signals(text):
            decision = Decision(
                content=text[:200],
                reason=None,
                conclusion=None,
                context=context or text[:100],
                project=project,
                source=source,
            )
            decisions.append(decision)

        return decisions

    def _has_decision_signals(self, text: str) -> bool:
        """检测文本是否包含决策信号"""
        signals = [
            "决定", "确认", "敲定", "定了", "采用", "选用",
            "不选", "放弃", "否决", "通过",
            "decided", "confirmed", "approved", "rejected",
        ]
        text_lower = text.lower()
        return any(s in text_lower for s in signals)

    def extract_and_store(self, text: str, context: Optional[str] = None,
                          project: Optional[str] = None,
                          source: Optional[str] = None,
                          chat_id: Optional[str] = None) -> Dict[str, Any]:
        """
        提取决策并存储到记忆引擎

        Returns:
            操作结果
        """
        decisions = self.extract(text, context, project, source)

        if not decisions:
            return {"success": True, "decisions_found": 0, "stored": 0}

        sqlite = SQLiteStore()
        chroma = ChromaStore()
        stored = 0

        for decision in decisions:
            memory = decision.to_memory()

            existing = sqlite.find_by_alias(memory.alias, project)
            if existing:
                old = existing[0]
                old.command = memory.command
                old.description = memory.description
                old.tags = list(set(old.tags + memory.tags))
                old.version = old.version + 1
                old.parent_id = old.id
                sqlite.update_memory(old)

                embedding = encode_text(f"{memory.alias} {memory.command} {memory.description}")
                if embedding:
                    chroma.update_memory(old, embedding)
            else:
                sqlite.create_memory(memory)

                embedding = encode_text(f"{memory.alias} {memory.command} {memory.description}")
                if embedding:
                    chroma.add_memory(memory, embedding)

            stored += 1

        result = {
            "success": True,
            "decisions_found": len(decisions),
            "stored": stored,
            "details": [
                {
                    "content": d.content,
                    "reason": d.reason,
                    "conclusion": d.conclusion,
                    "opposition": d.opposition,
                }
                for d in decisions
            ],
        }

        if chat_id and stored > 0:
            try:
                from src.integrations.feishu import get_feishu_client
                feishu = get_feishu_client()
                if feishu:
                    summary = "\n".join(
                        f"• {d.content}" + (f"（理由: {d.reason}）" if d.reason else "")
                        for d in decisions
                    )
                    feishu.send_text_message(
                        chat_id,
                        f"📋 决策已记录:\n{summary}"
                    )
            except Exception as e:
                logger.error(f"Failed to send decision notification: {e}")

        return result

    def find_related_decisions(self, query: str, project: Optional[str] = None,
                               limit: int = 5) -> List[Dict[str, Any]]:
        """
        查找与查询相关的历史决策

        Returns:
            相关决策列表
        """
        from src.retrieval.engine import RetrievalEngine

        store = SQLiteStore()
        chroma = ChromaStore()
        engine = RetrievalEngine(sqlite_store=store, chroma_store=chroma)

        results = engine.search(query, project=project, limit=limit * 2)

        decision_results = []
        for r in results:
            if "decision" in r.memory.tags:
                decision_results.append({
                    "alias": r.memory.alias,
                    "content": r.memory.command,
                    "description": r.memory.description,
                    "project": r.memory.project,
                    "score": r.score,
                    "match_type": r.match_type,
                })

            if len(decision_results) >= limit:
                break

        return decision_results
