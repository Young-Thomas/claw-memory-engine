"""
ChromaDB 向量存储层

负责记忆命令的向量化存储与语义检索
"""

import sys
try:
    import pysqlite3
    sys.modules['sqlite3'] = pysqlite3
except ImportError:
    pass

import hashlib
from pathlib import Path
from typing import Optional, List, Dict, Any
from functools import lru_cache

import chromadb
from chromadb.config import Settings

from src.core.models import Memory
from src.config.config_manager import get_chroma_path
from src.logger.logger import get_logger


logger = get_logger(__name__)


class ChromaStore:
    """ChromaDB 向量存储管理器"""

    _instances: Dict[str, 'ChromaStore'] = {}

    def __new__(cls, persist_dir: Optional[str] = None):
        """单例模式"""
        if persist_dir is None:
            persist_dir = str(get_chroma_path())

        if persist_dir not in cls._instances:
            instance = super().__new__(cls)
            instance._initialized = False
            cls._instances[persist_dir] = instance
        return cls._instances[persist_dir]

    def __init__(self, persist_dir: Optional[str] = None):
        """
        初始化 ChromaDB 存储

        Args:
            persist_dir: 持久化目录，默认为 ~/.claw/chroma_db
        """
        if self._initialized:
            return

        if persist_dir is None:
            persist_dir = str(get_chroma_path())

        self.persist_dir = persist_dir

        # 创建持久化目录
        persist_path = Path(persist_dir)
        persist_path.mkdir(exist_ok=True)

        # 初始化 ChromaDB 客户端（持久化模式）
        self.client = chromadb.PersistentClient(
            path=str(persist_path),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )

        # 获取或创建 collection
        self.collection = self.client.get_or_create_collection(
            name="command_memories",
            metadata={
                "description": "CLI command memories with semantic embeddings",
                "dimension": 384  # all-MiniLM-L6-v2 的输出维度
            }
        )

        logger.info(f"ChromaStore initialized: {persist_dir}")
        self._initialized = True

    def add_memory(self, memory: Memory, embedding: Optional[List[float]] = None) -> None:
        """
        添加记忆到向量库

        Args:
            memory: 记忆对象
            embedding: 预计算的向量，如果为 None 则需要外部计算后传入
        """
        # 生成唯一 ID（基于 memory.id）
        doc_id = self._generate_doc_id(memory.id)

        # 构建文档内容
        document = self._build_document(memory)

        # 构建元数据
        metadata = self._build_metadata(memory)

        # 添加到 ChromaDB
        self.collection.add(
            ids=[doc_id],
            documents=[document],
            embeddings=[embedding] if embedding else None,
            metadatas=[metadata]
        )

    def update_memory(self, memory: Memory, embedding: Optional[List[float]] = None) -> None:
        """更新记忆的向量表示"""
        doc_id = self._generate_doc_id(memory.id)

        document = self._build_document(memory)
        metadata = self._build_metadata(memory)

        self.collection.upsert(
            ids=[doc_id],
            documents=[document],
            embeddings=[embedding] if embedding else None,
            metadatas=[metadata]
        )

    def delete_memory(self, memory_id: str) -> None:
        """删除记忆"""
        doc_id = self._generate_doc_id(memory_id)
        self.collection.delete(ids=[doc_id])

    def search_by_query(
        self,
        query: str,
        embedding: Optional[List[float]] = None,
        n_results: int = 10,
        project: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        语义搜索记忆

        Args:
            query: 搜索查询
            embedding: 预计算的查询向量
            n_results: 返回结果数量
            project: 项目路径过滤

        Returns:
            搜索结果列表
        """
        where = None
        if project:
            where = {"project": project}

        results = self.collection.query(
            query_embeddings=[embedding] if embedding else None,
            query_texts=[query] if not embedding else None,
            n_results=n_results,
            where=where,
            include=["documents", "metadatas", "distances"]
        )

        return self._parse_results(results)

    def search_by_project(
        self,
        project: str,
        n_results: int = 50
    ) -> List[Dict[str, Any]]:
        """获取项目相关的所有记忆"""
        results = self.collection.get(
            where={"project": project},
            n_results=n_results,
            include=["documents", "metadatas"]
        )

        return self._parse_results(results)

    def get_all_memories(self, n_results: int = 1000) -> List[Dict[str, Any]]:
        """获取所有记忆"""
        results = self.collection.get(
            n_results=n_results,
            include=["documents", "metadatas"]
        )

        return self._parse_results(results)

    def reset(self) -> None:
        """重置向量库（仅用于测试）"""
        self.client.delete_collection("command_memories")
        self.collection = self.client.create_collection(
            name="command_memories",
            metadata={"description": "CLI command memories", "dimension": 384}
        )

    # ==================== Helpers ====================

    def _generate_doc_id(self, memory_id: str) -> str:
        """生成 ChromaDB 文档 ID"""
        # 使用哈希确保 ID 格式合规
        return f"mem_{hashlib.md5(memory_id.encode()).hexdigest()}"

    def _build_document(self, memory: Memory) -> str:
        """构建向量检索用的文档内容"""
        parts = [
            memory.alias,
            memory.command,
        ]

        if memory.description:
            parts.append(memory.description)

        if memory.project:
            parts.append(f"project:{memory.project}")

        if memory.tags:
            parts.append(f"tags:{' '.join(memory.tags)}")

        return " ".join(parts)

    def _build_metadata(self, memory: Memory) -> Dict[str, Any]:
        """构建元数据"""
        return {
            "memory_id": memory.id,
            "alias": memory.alias,
            "command": memory.command,
            "project": memory.project or "global",
            "frequency": memory.frequency,
            "created_at": memory.created_at.isoformat(),
            "last_used_at": memory.last_used_at.isoformat(),
            "version": memory.version,
        }

    def _parse_results(self, results: Dict) -> List[Dict[str, Any]]:
        """解析 ChromaDB 查询结果"""
        parsed = []

        ids = results.get("ids", [[]])[0] if results.get("ids") else []
        documents = results.get("documents", [[]])[0] if results.get("documents") else []
        metadatas = results.get("metadatas", [[]])[0] if results.get("metadatas") else []
        distances = results.get("distances", [[]])[0] if results.get("distances") else []

        for i in range(len(ids)):
            result = {
                "id": ids[i] if i < len(ids) else None,
                "document": documents[i] if i < len(documents) else None,
                "metadata": metadatas[i] if i < len(metadatas) else None,
                "distance": distances[i] if i < len(distances) else None,
            }
            # 计算相似度分数（从距离转换）
            if result["distance"] is not None:
                # ChromaDB 返回的是欧氏距离，转换为 0-1 的相似度
                result["score"] = 1 / (1 + result["distance"])
            else:
                result["score"] = 0.0

            parsed.append(result)

        return parsed
