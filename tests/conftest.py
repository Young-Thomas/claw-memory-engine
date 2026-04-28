"""
Pytest 共享配置和工具
"""

import pytest
import tempfile
from pathlib import Path

from src.storage.sqlite_store import SQLiteStore
from src.storage.chroma_store import ChromaStore
from src.retrieval.engine import RetrievalEngine


@pytest.fixture
def temp_db_path():
    """创建临时数据库路径"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "test.db"


@pytest.fixture
def temp_chroma_path():
    """创建临时 ChromaDB 路径"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "chroma_db"


@pytest.fixture
def sqlite_store(temp_db_path):
    """创建 SQLite 存储"""
    return SQLiteStore(str(temp_db_path))


@pytest.fixture
def chroma_store(temp_chroma_path):
    """创建 ChromaDB 存储"""
    return ChromaStore(persist_dir=str(temp_chroma_path))


@pytest.fixture
def retrieval_engine(temp_db_path, temp_chroma_path):
    """创建检索引擎"""
    sqlite = SQLiteStore(str(temp_db_path))
    chroma = ChromaStore(persist_dir=str(temp_chroma_path))
    return RetrievalEngine(sqlite_store=sqlite, chroma_store=chroma)


@pytest.fixture
def sample_memories():
    """示例记忆数据"""
    return [
        {
            "alias": "deploy-prod",
            "command": "kubectl apply -f prod/",
            "description": "部署到生产环境",
            "tags": ["k8s", "production"],
        },
        {
            "alias": "deploy-staging",
            "command": "kubectl apply -f staging/",
            "description": "部署到预发环境",
            "tags": ["k8s", "staging"],
        },
        {
            "alias": "test-unit",
            "command": "pytest tests/unit/",
            "description": "运行单元测试",
            "tags": ["testing", "python"],
        },
        {
            "alias": "test-integration",
            "command": "pytest tests/integration/",
            "description": "运行集成测试",
            "tags": ["testing", "python"],
        },
        {
            "alias": "build",
            "command": "npm run build",
            "description": "构建前端项目",
            "tags": ["build", "nodejs"],
        },
    ]
