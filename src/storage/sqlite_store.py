"""
SQLite 存储层

负责 Memory、Project、UsageLog 的持久化存储
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from src.core.models import Memory, Project, UsageLog


class SQLiteStore:
    """SQLite 存储管理器"""

    def __init__(self, db_path: Optional[str] = None):
        """
        初始化 SQLite 存储

        Args:
            db_path: 数据库路径，默认为 ~/.claw/claw.db
        """
        if db_path is None:
            home = Path.home()
            claw_dir = home / ".claw"
            claw_dir.mkdir(exist_ok=True)
            db_path = claw_dir / "claw.db"

        self.db_path = str(db_path)
        self._init_tables()

    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_tables(self):
        """初始化数据表"""
        with self._get_connection() as conn:
            # 记忆表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    alias TEXT NOT NULL,
                    command TEXT NOT NULL,
                    project TEXT,
                    description TEXT,
                    frequency INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP,
                    is_active INTEGER DEFAULT 1,
                    parent_id TEXT,
                    version INTEGER DEFAULT 1,
                    tags TEXT
                )
            """)

            # 项目表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    path TEXT UNIQUE NOT NULL,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 使用日志表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS usage_logs (
                    id TEXT PRIMARY KEY,
                    memory_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    context TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (memory_id) REFERENCES memories(id)
                )
            """)

            # 索引
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_alias ON memories(alias)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_project ON memories(project)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_active ON memories(is_active)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_parent ON memories(parent_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_logs_memory ON usage_logs(memory_id)")

    # ==================== Memory CRUD ====================

    def create_memory(self, memory: Memory) -> Memory:
        """创建记忆"""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO memories
                (id, alias, command, project, description, frequency,
                 created_at, updated_at, last_used_at, expires_at,
                 is_active, parent_id, version, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    memory.id,
                    memory.alias,
                    memory.command,
                    memory.project,
                    memory.description,
                    memory.frequency,
                    memory.created_at.isoformat(),
                    memory.updated_at.isoformat(),
                    memory.last_used_at.isoformat(),
                    memory.expires_at.isoformat() if memory.expires_at else None,
                    1 if memory.is_active else 0,
                    memory.parent_id,
                    memory.version,
                    json.dumps(memory.tags) if memory.tags else "[]"
                )
            )

            # 记录使用日志
            self._log_action(conn, memory.id, "created")
            return memory

    def get_memory(self, memory_id: str) -> Optional[Memory]:
        """获取单个记忆"""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM memories WHERE id = ?",
                (memory_id,)
            ).fetchone()
            return self._row_to_memory(row) if row else None

    def find_by_alias(self, alias: str, project: Optional[str] = None) -> List[Memory]:
        """
        按别名查找记忆

        Args:
            alias: 命令别名
            project: 项目路径，如果指定则只返回该项目下的记忆
        """
        with self._get_connection() as conn:
            if project:
                rows = conn.execute(
                    """SELECT * FROM memories
                       WHERE alias = ? AND project = ? AND is_active = 1
                       ORDER BY frequency DESC""",
                    (alias, project)
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT * FROM memories
                       WHERE alias = ? AND is_active = 1
                       ORDER BY frequency DESC""",
                    (alias,)
                ).fetchall()
            return [self._row_to_memory(row) for row in rows]

    def find_by_project(self, project: str) -> List[Memory]:
        """查找项目下的所有记忆"""
        with self._get_connection() as conn:
            rows = conn.execute(
                """SELECT * FROM memories
                   WHERE project = ? AND is_active = 1
                   ORDER BY frequency DESC""",
                (project,)
            ).fetchall()
            return [self._row_to_memory(row) for row in rows]

    def find_all_active(self, limit: int = 100) -> List[Memory]:
        """查找所有活跃记忆"""
        with self._get_connection() as conn:
            rows = conn.execute(
                """SELECT * FROM memories
                   WHERE is_active = 1
                   ORDER BY frequency DESC, last_used_at DESC
                   LIMIT ?""",
                (limit,)
            ).fetchall()
            return [self._row_to_memory(row) for row in rows]

    def update_memory(self, memory: Memory) -> Memory:
        """更新记忆"""
        memory.updated_at = datetime.now()

        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE memories SET
                    alias = ?,
                    command = ?,
                    project = ?,
                    description = ?,
                    frequency = ?,
                    updated_at = ?,
                    last_used_at = ?,
                    expires_at = ?,
                    is_active = ?,
                    parent_id = ?,
                    version = ?,
                    tags = ?
                WHERE id = ?
                """,
                (
                    memory.alias,
                    memory.command,
                    memory.project,
                    memory.description,
                    memory.frequency,
                    memory.updated_at.isoformat(),
                    memory.last_used_at.isoformat(),
                    memory.expires_at.isoformat() if memory.expires_at else None,
                    1 if memory.is_active else 0,
                    memory.parent_id,
                    memory.version,
                    json.dumps(memory.tags) if memory.tags else "[]",
                    memory.id
                )
            )

            self._log_action(conn, memory.id, "updated")
            return memory

    def increment_frequency(self, memory_id: str) -> None:
        """增加使用频率"""
        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE memories SET
                    frequency = frequency + 1,
                    last_used_at = ?
                WHERE id = ?
                """,
                (datetime.now().isoformat(), memory_id)
            )
            self._log_action(conn, memory_id, "used")

    def archive_memory(self, memory_id: str) -> None:
        """归档记忆（标记为非活跃）"""
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE memories SET is_active = 0 WHERE id = ?",
                (memory_id,)
            )
            self._log_action(conn, memory_id, "deleted")

    def delete_memory(self, memory_id: str) -> None:
        """删除记忆"""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))

    def get_version_chain(self, memory_id: str) -> List[Memory]:
        """获取记忆版本链"""
        chain = []
        current_id = memory_id

        while current_id:
            memory = self.get_memory(current_id)
            if memory:
                chain.append(memory)
                current_id = memory.parent_id
            else:
                break

        return list(reversed(chain))  # 从旧到新

    # ==================== Project CRUD ====================

    def create_project(self, project: Project) -> Project:
        """创建项目"""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO projects (id, name, path, description, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    project.id,
                    project.name,
                    project.path,
                    project.description,
                    project.created_at.isoformat()
                )
            )
            return project

    def get_project(self, project_id: str) -> Optional[Project]:
        """获取项目"""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM projects WHERE id = ?",
                (project_id,)
            ).fetchone()
            return self._row_to_project(row) if row else None

    def find_project_by_path(self, path: str) -> Optional[Project]:
        """按路径查找项目"""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM projects WHERE path = ?",
                (path,)
            ).fetchone()
            return self._row_to_project(row) if row else None

    def get_or_create_project(self, path: str, name: str = None) -> Project:
        """获取或创建项目"""
        existing = self.find_project_by_path(path)
        if existing:
            return existing

        if name is None:
            name = Path(path).name

        project = Project(name=name, path=path)
        return self.create_project(project)

    # ==================== Usage Log ====================

    def _log_action(self, conn: sqlite3.Connection, memory_id: str, action: str, context: Dict[str, Any] = None):
        """记录操作日志"""
        log = UsageLog(
            memory_id=memory_id,
            action=action,
            context=json.dumps(context) if context else None
        )
        conn.execute(
            """
            INSERT INTO usage_logs (id, memory_id, action, context, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (log.id, log.memory_id, log.action, log.context, log.created_at.isoformat())
        )

    def get_usage_logs(self, memory_id: str, limit: int = 10) -> List[UsageLog]:
        """获取记忆的使用日志"""
        with self._get_connection() as conn:
            rows = conn.execute(
                """SELECT * FROM usage_logs
                   WHERE memory_id = ?
                   ORDER BY created_at DESC
                   LIMIT ?""",
                (memory_id, limit)
            ).fetchall()
            return [self._row_to_usage_log(row) for row in rows]

    # ==================== Helpers ====================

    def _row_to_memory(self, row: sqlite3.Row) -> Memory:
        """将数据库行转换为 Memory 对象"""
        tags_str = row['tags']
        tags = json.loads(tags_str) if tags_str else []

        return Memory(
            id=row['id'],
            alias=row['alias'],
            command=row['command'],
            project=row['project'],
            description=row['description'],
            frequency=row['frequency'],
            created_at=datetime.fromisoformat(row['created_at']),
            updated_at=datetime.fromisoformat(row['updated_at']),
            last_used_at=datetime.fromisoformat(row['last_used_at']),
            expires_at=datetime.fromisoformat(row['expires_at']) if row['expires_at'] else None,
            is_active=bool(row['is_active']),
            parent_id=row['parent_id'],
            version=row['version'],
            tags=tags
        )

    def _row_to_project(self, row: sqlite3.Row) -> Project:
        """将数据库行转换为 Project 对象"""
        return Project(
            id=row['id'],
            name=row['name'],
            path=row['path'],
            description=row['description'],
            created_at=datetime.fromisoformat(row['created_at'])
        )

    def _row_to_usage_log(self, row: sqlite3.Row) -> UsageLog:
        """将数据库行转换为 UsageLog 对象"""
        return UsageLog(
            id=row['id'],
            memory_id=row['memory_id'],
            action=row['action'],
            context=row['context'],
            created_at=datetime.fromisoformat(row['created_at'])
        )
