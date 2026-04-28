"""
检索引擎 - 混合搜索与上下文感知

结合关键词匹配、向量检索和项目上下文进行智能推荐
"""

import re
from typing import List, Optional, Tuple
from collections import Counter

from src.core.models import Memory, SearchResult, ContextInfo
from src.storage.sqlite_store import SQLiteStore
from src.storage.chroma_store import ChromaStore
from src.retrieval.embeddings import get_embedding_model, encode_text


class RetrievalEngine:
    """
    检索引擎

    支持多种检索模式：
    1. 精确匹配 (exact)
    2. 前缀匹配 (prefix)
    3. 语义匹配 (semantic)
    4. 项目上下文匹配 (contextual)
    """

    def __init__(
        self,
        sqlite_store: Optional[SQLiteStore] = None,
        chroma_store: Optional[ChromaStore] = None
    ):
        """
        初始化检索引擎

        Args:
            sqlite_store: SQLite 存储
            chroma_store: ChromaDB 向量存储
        """
        self.sqlite = sqlite_store or SQLiteStore()
        self.chroma = chroma_store or ChromaStore()
        self.embedding_model = get_embedding_model()

    def search(
        self,
        query: str,
        project: Optional[str] = None,
        limit: int = 10
    ) -> List[SearchResult]:
        """
        混合搜索

        结合多种检索策略：
        1. 精确匹配别名
        2. 前缀匹配别名
        3. 语义搜索（向量检索）
        4. 项目过滤

        Args:
            query: 搜索查询
            project: 项目路径过滤
            limit: 返回结果数量

        Returns:
            搜索结果列表
        """
        results = []

        # 1. 精确匹配别名
        exact_matches = self._search_exact(query, project)
        results.extend(exact_matches)

        # 2. 前缀匹配
        prefix_matches = self._search_prefix(query, project)
        results.extend(prefix_matches)

        # 3. 语义搜索
        semantic_matches = self._search_semantic(query, project, limit)
        results.extend(semantic_matches)

        # 4. 去重和排序
        return self._deduplicate_and_rank(results, query, limit)

    def get_suggestions(
        self,
        partial_input: str,
        project: Optional[str] = None,
        limit: int = 5
    ) -> List[SearchResult]:
        """
        获取补全建议

        用于 TAB 补全场景

        Args:
            partial_input: 用户已输入的部分
            project: 项目上下文
            limit: 返回数量

        Returns:
            补全建议列表
        """
        # 如果输入为空，返回高频命令
        if not partial_input.strip():
            return self._get_frequent_commands(project, limit)

        # 否则进行搜索
        return self.search(partial_input, project, limit)

    def find_by_alias(
        self,
        alias: str,
        project: Optional[str] = None
    ) -> Optional[Memory]:
        """
        按别名查找记忆

        Args:
            alias: 命令别名
            project: 项目路径

        Returns:
            匹配的记忆，如果未找到则返回 None
        """
        memories = self.sqlite.find_by_alias(alias, project)

        if not memories:
            # 尝试语义搜索
            results = self.search(alias, project, limit=1)
            if results and results[0].score > 0.8:
                return results[0].memory

        return memories[0] if memories else None

    def _search_exact(
        self,
        query: str,
        project: Optional[str]
    ) -> List[SearchResult]:
        """精确匹配别名"""
        memories = self.sqlite.find_by_alias(query, project)
        return [
            SearchResult(memory=mem, score=1.0, match_type="exact")
            for mem in memories
        ]

    def _search_prefix(
        self,
        query: str,
        project: Optional[str]
    ) -> List[SearchResult]:
        """前缀匹配别名"""
        all_memories = self.sqlite.find_all_active(limit=500)

        if project:
            all_memories = [m for m in all_memories if m.project == project]

        prefix_matches = [
            mem for mem in all_memories
            if mem.alias.lower().startswith(query.lower())
        ]

        # 按匹配长度和频率排序
        prefix_matches.sort(
            key=lambda m: (len(m.alias) - len(query), -m.frequency)
        )

        return [
            SearchResult(memory=mem, score=0.9, match_type="prefix")
            for mem in prefix_matches[:10]
        ]

    def _search_semantic(
        self,
        query: str,
        project: Optional[str],
        limit: int
    ) -> List[SearchResult]:
        """语义搜索"""
        # 计算查询向量
        query_embedding = encode_text(query)

        if query_embedding is None:
            # 模型加载失败，回退到关键词匹配
            return self._search_keyword(query, project, limit)

        # ChromaDB 搜索
        chroma_results = self.chroma.search_by_query(
            query=query,
            embedding=query_embedding,
            n_results=limit * 2,
            project=project
        )

        results = []
        for r in chroma_results:
            memory_id = r.get("metadata", {}).get("memory_id")
            if memory_id:
                memory = self.sqlite.get_memory(memory_id)
                if memory:
                    results.append(
                        SearchResult(
                            memory=memory,
                            score=r.get("score", 0.5),
                            match_type="semantic"
                        )
                    )

        return results

    def _search_keyword(
        self,
        query: str,
        project: Optional[str],
        limit: int
    ) -> List[SearchResult]:
        """关键词匹配（回退方案）"""
        all_memories = self.sqlite.find_all_active(limit=500)

        if project:
            all_memories = [m for m in all_memories if m.project == project]

        # 计算关键词匹配分数
        query_terms = set(query.lower().split())

        scored_memories = []
        for mem in all_memories:
            text = f"{mem.alias} {mem.command} {mem.description or ''}".lower()
            matches = sum(1 for term in query_terms if term in text)
            if matches > 0:
                score = matches / len(query_terms)
                scored_memories.append((mem, score))

        scored_memories.sort(key=lambda x: (-x[1], -x[0].frequency))

        return [
            SearchResult(memory=mem, score=score, match_type="keyword")
            for mem, score in scored_memories[:limit]
        ]

    def _get_frequent_commands(
        self,
        project: Optional[str],
        limit: int
    ) -> List[SearchResult]:
        """获取高频命令"""
        memories = self.sqlite.find_all_active(limit=limit * 2)

        if project:
            memories = [m for m in memories if m.project == project]

        # 按频率排序
        memories.sort(key=lambda m: -m.frequency)

        return [
            SearchResult(memory=mem, score=0.5, match_type="frequent")
            for mem in memories[:limit]
        ]

    def _deduplicate_and_rank(
        self,
        results: List[SearchResult],
        query: str,
        limit: int
    ) -> List[SearchResult]:
        """去重并排序"""
        # 按 memory_id 去重，保留最高分
        seen = {}
        for r in results:
            mid = r.memory.id
            if mid not in seen or r.score > seen[mid].score:
                seen[mid] = r

        unique_results = list(seen.values())

        # 排序：match_type 优先级 + 分数
        type_priority = {"exact": 0, "prefix": 1, "semantic": 2, "keyword": 3}
        unique_results.sort(
            key=lambda r: (type_priority.get(r.match_type, 4), -r.score)
        )

        return unique_results[:limit]


class ContextManager:
    """
    上下文管理器

    检测和管理项目上下文
    """

    def __init__(self):
        self.sqlite = SQLiteStore()

    def detect_context(self, cwd: Optional[str] = None) -> ContextInfo:
        """
        检测当前上下文

        Args:
            cwd: 当前工作目录，默认为 os.getcwd()

        Returns:
            上下文信息
        """
        import os
        from pathlib import Path

        cwd = cwd or os.getcwd()
        cwd_path = Path(cwd).resolve()

        # 检测 git 仓库
        git_root = self._find_git_root(cwd_path)

        # 获取或创建项目
        project = None
        if git_root:
            project = self.sqlite.get_or_create_project(
                path=str(git_root),
                name=git_root.name
            )

        return ContextInfo(
            current_project=project,
            current_directory=str(cwd_path),
            is_git_repo=git_root is not None,
            git_root=str(git_root) if git_root else None
        )

    def _find_git_root(self, path: Path) -> Optional[Path]:
        """向上查找 git 根目录"""
        current = path

        while current != current.parent:
            git_dir = current / ".git"
            if git_dir.exists():
                return current
            current = current.parent

        return None
