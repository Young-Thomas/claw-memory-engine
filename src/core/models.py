"""
核心数据模型 - Memory, Project, UsageLog

使用 Pydantic v2 最新语法定义数据模型
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict
from uuid import uuid4


class Memory(BaseModel):
    """记忆数据模型"""

    model_config = ConfigDict(
        frozen=False,
        extra="ignore",
        json_encoders={datetime: lambda v: v.isoformat()}
    )

    id: str = Field(default_factory=lambda: str(uuid4()), description="唯一标识符")
    alias: str = Field(..., description="命令别名")
    command: str = Field(..., description="完整命令")
    project: Optional[str] = Field(default=None, description="关联项目路径")
    description: Optional[str] = Field(default=None, description="命令描述")
    frequency: int = Field(default=1, description="使用频率")

    # 时间戳
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")
    last_used_at: datetime = Field(default_factory=datetime.now, description="最后使用时间")

    # 遗忘曲线相关
    expires_at: Optional[datetime] = Field(default=None, description="过期时间")
    is_active: bool = Field(default=True, description="是否活跃")

    # 版本链
    parent_id: Optional[str] = Field(default=None, description="父记忆 ID（用于版本链）")
    version: int = Field(default=1, description="版本号")

    # 元数据
    tags: List[str] = Field(default_factory=list, description="标签列表")

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        if not isinstance(other, Memory):
            return False
        return self.id == other.id


class Project(BaseModel):
    """项目数据模型"""

    model_config = ConfigDict(
        frozen=False,
        extra="ignore"
    )

    id: str = Field(default_factory=lambda: str(uuid4()), description="唯一标识符")
    name: str = Field(..., description="项目名称")
    path: str = Field(..., description="项目绝对路径")
    description: Optional[str] = Field(default=None, description="项目描述")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")


class UsageLog(BaseModel):
    """使用日志数据模型"""

    model_config = ConfigDict(
        frozen=False,
        extra="ignore"
    )

    id: str = Field(default_factory=lambda: str(uuid4()), description="唯一标识符")
    memory_id: str = Field(..., description="记忆 ID")
    action: str = Field(..., description="动作类型: created/used/updated/deleted")
    context: Optional[str] = Field(default=None, description="上下文信息（JSON）")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")


class SearchResult(BaseModel):
    """搜索结果模型"""

    model_config = ConfigDict(
        frozen=False,
        extra="ignore"
    )

    memory: Memory = Field(..., description="记忆对象")
    score: float = Field(..., description="相似度分数 0-1")
    match_type: str = Field(..., description="匹配类型: exact/prefix/semantic/project")


class ContextInfo(BaseModel):
    """上下文信息模型"""

    model_config = ConfigDict(
        frozen=False,
        extra="ignore"
    )

    current_project: Optional[Project] = Field(default=None, description="当前项目")
    current_directory: str = Field(..., description="当前工作目录")
    is_git_repo: bool = Field(default=False, description="是否在 git 仓库中")
    git_root: Optional[str] = Field(default=None, description="git 根目录")
