"""
Claw Memory Engine - CLI 主入口

使用 Typer 框架构建现代化 CLI
"""

import sys
from typing import Optional, List

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.theme import Theme

from src.core.models import Memory
from src.storage.sqlite_store import SQLiteStore
from src.storage.chroma_store import ChromaStore
from src.retrieval.engine import RetrievalEngine, ContextManager
from src.retrieval.embeddings import encode_text
from src.cli.completion import install_completion, generate_bash_completion, generate_zsh_completion, get_complete_aliases
from src.config.config_manager import get_config_manager, Config
from src.integrations.feishu import FeishuClient, get_feishu_client
from src.integrations.scheduler import get_forgetting_scheduler, start_scheduler, stop_scheduler

# 自定义主题
custom_theme = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "red",
    "success": "green",
    "alias": "bold cyan",
    "command": "green",
    "project": "yellow",
})

console = Console(theme=custom_theme)

# 创建 Typer 应用
app = typer.Typer(
    name="claw",
    help="🧠 Claw Memory Engine - CLI 智能记忆助手",
    add_completion=True,
    no_args_is_help=True,
)

# 延迟初始化存储
_sqlite_store: Optional[SQLiteStore] = None
_chroma_store: Optional[ChromaStore] = None
_retrieval_engine: Optional[RetrievalEngine] = None
_context_manager: Optional[ContextManager] = None


def get_sqlite_store() -> SQLiteStore:
    """获取 SQLite 存储单例"""
    global _sqlite_store
    if _sqlite_store is None:
        _sqlite_store = SQLiteStore()
    return _sqlite_store


def get_chroma_store() -> ChromaStore:
    """获取 ChromaDB 存储单例"""
    global _chroma_store
    if _chroma_store is None:
        _chroma_store = ChromaStore()
    return _chroma_store


def get_retrieval_engine() -> RetrievalEngine:
    """获取检索引擎单例"""
    global _retrieval_engine
    if _retrieval_engine is None:
        _retrieval_engine = RetrievalEngine(
            sqlite_store=get_sqlite_store(),
            chroma_store=get_chroma_store()
        )
    return _retrieval_engine


def get_context_manager() -> ContextManager:
    """获取上下文管理器单例"""
    global _context_manager
    if _context_manager is None:
        _context_manager = ContextManager()
    return _context_manager


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        help="显示版本号"
    )
):
    """
    🧠 Claw Memory Engine - 让 CLI 记住你的工作流

    使用示例:

        claw remember deploy-prod "kubectl apply -f prod/"

        claw find 部署

        claw list
    """
    if version:
        from src import __version__
        console.print(f"[info]Claw Memory Engine[/] v{__version__}")
        raise typer.Exit()


@app.command("remember")
def remember_command(
    alias: str = typer.Argument(..., help="命令别名"),
    command: str = typer.Argument(..., help="完整命令"),
    description: Optional[str] = typer.Option(
        None,
        "--desc",
        "-d",
        help="命令描述"
    ),
    tags: Optional[str] = typer.Option(
        None,
        "--tags",
        "-t",
        help="标签（逗号分隔）"
    ),
    project: Optional[str] = typer.Option(
        None,
        "--project",
        "-p",
        help="关联项目（默认为当前项目）"
    ),
):
    """
    记录一个命令

    示例:

        claw remember deploy-prod "kubectl apply -f prod/"

        claw remember deploy "docker-compose up" --desc "部署服务"

        claw remember test "pytest tests/" --tags testing,python
    """
    import os
    from datetime import datetime, timedelta

    # 如果没有指定项目，尝试检测当前项目
    if project is None:
        ctx_manager = get_context_manager()
        context = ctx_manager.detect_context(os.getcwd())
        project = context.git_root

    # 解析标签
    tag_list = []
    if tags:
        tag_list = [t.strip() for t in tags.split(",")]

    # 检查别名是否已存在
    engine = get_retrieval_engine()
    existing = engine.find_by_alias(alias, project)

    if existing:
        # 更新现有记忆
        existing.command = command
        existing.description = description
        existing.tags = tag_list if tag_list else existing.tags
        existing.updated_at = datetime.now()

        get_sqlite_store().update_memory(existing)

        # 更新向量索引
        embedding = encode_text(f"{alias} {command} {description or ''}")
        if embedding:
            get_chroma_store().update_memory(existing, embedding)

        console.print(
            Panel(
                f"[success]已更新命令[/]\n\n"
                f"[alias]{alias}[/] → [command]{command}[/]\n\n"
                f"[info]项目：[/]{project or '全局'}",
                title="📝 更新",
                border_style="yellow"
            )
        )
    else:
        # 创建新记忆
        memory = Memory(
            alias=alias,
            command=command,
            description=description,
            tags=tag_list,
            project=project,
        )

        get_sqlite_store().create_memory(memory)

        # 添加到向量索引
        embedding = encode_text(f"{alias} {command} {description or ''}")
        if embedding:
            get_chroma_store().add_memory(memory, embedding)

        console.print(
            Panel(
                f"[success]已记录命令[/]\n\n"
                f"[alias]{alias}[/] → [command]{command}[/]\n\n"
                f"[info]项目：[/]{project or '全局'}\n"
                f"[info]标签：[/]{', '.join(tag_list) if tag_list else '无'}",
                title="✅ 成功",
                border_style="green"
            )
        )


@app.command("list")
def list_command(
    project: Optional[str] = typer.Option(
        None,
        "--project",
        "-p",
        help="只显示指定项目的记忆"
    ),
    limit: int = typer.Option(
        20,
        "--limit",
        "-l",
        help="显示数量上限"
    ),
    all: bool = typer.Option(
        False,
        "--all",
        "-a",
        help="显示所有记忆（包括已归档）"
    ),
):
    """
    列出已记录的命令

    示例:

        claw list

        claw list -p /path/to/project

        claw list --all
    """
    store = get_sqlite_store()

    if project:
        memories = store.find_by_project(project)
    elif all:
        memories = store.find_all_active(limit=limit * 2)
    else:
        memories = store.find_all_active(limit=limit)

    if not memories:
        console.print("[info]暂无记忆记录[/]")
        console.print("使用 [alias]claw remember <别名> <命令>[/] 来记录第一个命令")
        return

    # 创建表格
    table = Table(
        title="🧠 Claw Memory - 记忆列表",
        show_header=True,
        header_style="bold magenta",
    )

    table.add_column("别名", style="cyan", no_wrap=True)
    table.add_column("命令", style="green")
    table.add_column("项目", style="yellow")
    table.add_column("频率", justify="right")
    table.add_column("最后使用")

    for mem in memories:
        # 格式化命令显示
        cmd_display = mem.command
        if len(cmd_display) > 50:
            cmd_display = cmd_display[:47] + "..."

        # 格式化项目显示
        project_display = mem.project or "全局"
        if len(project_display) > 20:
            project_display = "..." + project_display[-17:]

        # 格式化时间
        last_used = format_relative_time(mem.last_used_at)

        table.add_row(
            mem.alias,
            cmd_display,
            project_display,
            str(mem.frequency),
            last_used,
        )

    console.print(table)

    if len(memories) >= limit:
        console.print(f"\n[info]显示前 {len(memories)} 条记录，使用 --limit 调整显示数量[/]")


@app.command("find")
def find_command(
    query: str = typer.Argument(..., help="搜索查询"),
    project: Optional[str] = typer.Option(
        None,
        "--project",
        "-p",
        help="在项目范围内搜索"
    ),
    limit: int = typer.Option(
        10,
        "--limit",
        "-l",
        help="返回结果数量"
    ),
):
    """
    搜索记忆

    支持语义搜索，无需精确匹配

    示例:

        claw find 部署

        claw find "docker compose" -p /path/to/project
    """
    engine = get_retrieval_engine()
    results = engine.search(query, project, limit)

    if not results:
        console.print(f"[warning]未找到匹配 '{query}' 的记忆[/]")
        return

    # 创建结果表格
    table = Table(
        title=f"🔍 搜索结果：'{query}'",
        show_header=True,
        header_style="bold magenta",
    )

    table.add_column("别名", style="cyan", no_wrap=True)
    table.add_column("命令", style="green")
    table.add_column("匹配类型", style="yellow")
    table.add_column("相似度", justify="right")

    for r in results:
        # 格式化命令显示
        cmd_display = r.memory.command
        if len(cmd_display) > 50:
            cmd_display = cmd_display[:47] + "..."

        # 匹配类型图标
        match_icon = {
            "exact": "🎯",
            "prefix": "📍",
            "semantic": "🧠",
            "keyword": "🔑",
        }.get(r.match_type, "")

        # 格式化相似度
        score_display = f"{r.score:.2f}" if r.match_type != "exact" else "精确"

        table.add_row(
            r.memory.alias,
            cmd_display,
            f"{match_icon} {r.match_type}",
            score_display,
        )

    console.print(table)


@app.command("delete")
def delete_command(
    alias: str = typer.Argument(..., help="要删除的命令别名"),
    project: Optional[str] = typer.Option(
        None,
        "--project",
        "-p",
        help="项目路径"
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="强制删除，不确认"
    ),
):
    """
    删除记忆

    示例:

        claw delete deploy-prod

        claw delete deploy-prod -p /path/to/project -f
    """
    engine = get_retrieval_engine()
    memory = engine.find_by_alias(alias, project)

    if not memory:
        console.print(f"[error]未找到别名 '{alias}' 的记忆[/]")
        return

    if not force:
        # 确认删除
        confirm = typer.confirm(
            f"确定要删除 '[alias]{alias}[/]' 吗？\n"
            f"命令：[command]{memory.command}[/]"
        )
        if not confirm:
            console.print("[info]已取消删除[/]")
            return

    # 归档记忆
    store = get_sqlite_store()
    store.archive_memory(memory.id)

    # 从向量索引删除
    get_chroma_store().delete_memory(memory.id)

    console.print(f"[success]已删除记忆 '{alias}'[/]")


@app.command("show")
def show_command(
    alias: str = typer.Argument(..., help="要查看的命令别名"),
    project: Optional[str] = typer.Option(
        None,
        "--project",
        "-p",
        help="项目路径"
    ),
):
    """
    显示记忆详情

    示例:

        claw show deploy-prod
    """
    engine = get_retrieval_engine()
    memory = engine.find_by_alias(alias, project)

    if not memory:
        console.print(f"[error]未找到别名 '{alias}' 的记忆[/]")
        return

    console.print(
        Panel(
            f"[alias]别名：[/] {memory.alias}\n\n"
            f"[command]命令：[/] {memory.command}\n\n"
            f"[info]描述：[/] {memory.description or '无'}\n\n"
            f"[info]项目：[/] {memory.project or '全局'}\n\n"
            f"[info]标签：[/] {', '.join(memory.tags) if memory.tags else '无'}\n\n"
            f"[info]使用次数：[/] {memory.frequency}\n\n"
            f"[info]创建时间：[/] {memory.created_at.strftime('%Y-%m-%d %H:%M')}\n\n"
            f"[info]最后使用：[/] {format_relative_time(memory.last_used_at)}",
            title="📋 记忆详情",
            border_style="cyan"
        )
    )


def format_relative_time(dt) -> str:
    """格式化相对时间"""
    from datetime import datetime

    now = datetime.now()
    diff = now - dt

    seconds = diff.total_seconds()

    if seconds < 60:
        return "刚刚"
    elif seconds < 3600:
        return f"{int(seconds / 60)}分钟前"
    elif seconds < 86400:
        return f"{int(seconds / 3600)}小时前"
    elif seconds < 604800:
        return f"{int(seconds / 86400)}天前"
    else:
        return dt.strftime("%Y-%m-%d")


# ==================== 内部命令（用于补全等）====================

@app.command("_complete-aliases", hidden=True)
def complete_aliases():
    """返回所有别名（用于 shell 补全）"""
    aliases = get_complete_aliases()
    typer.echo(aliases)


# ==================== 配置命令 ====================

@app.command("install-completion")
def install_completion_cmd(
    shell: Optional[str] = typer.Option(
        None,
        "--shell",
        "-s",
        help="Shell 类型 (bash/zsh), 默认自动检测"
    ),
):
    """
    安装 Shell 补全脚本

    示例:

        claw install-completion

        claw install-completion --shell bash
    """
    install_completion(shell)


@app.command("completion")
def completion_cmd(
    shell: str = typer.Argument(
        "bash",
        help="Shell 类型 (bash/zsh)"
    ),
):
    """
    打印补全脚本内容

    示例:

        # Bash
        claw completion bash > ~/.claw_completion.bash
        source ~/.claw_completion.bash

        # Zsh
        claw completion zsh > ~/.zsh/completion/_claw
    """
    if shell == "bash":
        typer.echo(generate_bash_completion())
    elif shell == "zsh":
        typer.echo(generate_zsh_completion())
    else:
        typer.echo(f"Unsupported shell: {shell}")
        raise typer.Exit(1)


@app.command("config")
def config_cmd(
    show: bool = typer.Option(False, "--show", "-s", help="显示当前配置"),
    reset: bool = typer.Option(False, "--reset", "-r", help="重置为默认配置"),
    key: Optional[str] = typer.Option(None, "--key", "-k", help="配置键"),
    value: Optional[str] = typer.Option(None, "--value", "-v", help="配置值"),
):
    """
    管理配置

    示例:

        claw config --show

        claw config --reset

        claw config --key data_dir --value /path/to/data
    """
    manager = get_config_manager()

    if reset:
        manager.reset()
        console.print("[success]配置已重置为默认值[/]")
        return

    if show:
        config = manager.load()
        console.print(Panel(
            "\n".join(f"[info]{k}:[/] {v}" for k, v in config.model_dump().items()),
            title="⚙️ 当前配置",
            border_style="cyan"
        ))
        return

    if key and value:
        manager.set(key, value)
        console.print(f"[success]已设置 {key} = {value}[/]")
        return

    if key:
        val = manager.get(key)
        if val is not None:
            console.print(f"[info]{key}:[/] {val}")
        else:
            console.print(f"[error]未知配置键：{key}[/]")
            raise typer.Exit(1)

    # 默认显示配置
    config = manager.load()
    console.print(Panel(
        "\n".join(f"[info]{k}:[/] {v}" for k, v in config.model_dump().items()),
        title="⚙️ 当前配置",
        border_style="cyan"
    ))


# ==================== 飞书集成命令 ====================

@app.command("feishu-test")
def feishu_test_cmd(
    app_id: str = typer.Argument(..., help="飞书 App ID"),
    app_secret: str = typer.Argument(..., help="飞书 App Secret"),
):
    """
    测试飞书连接

    示例:

        claw feishu-test cli_xxx xxx
    """
    client = FeishuClient(app_id=app_id, app_secret=app_secret)

    if client.test_connection():
        console.print("[success]飞书连接测试成功[/]")
    else:
        console.print("[error]飞书连接测试失败[/]")
        raise typer.Exit(1)


@app.command("feishu-send")
def feishu_send_cmd(
    chat_id: str = typer.Argument(..., help="群聊 ID"),
    message: str = typer.Argument(..., help="消息内容"),
):
    """
    发送飞书消息

    示例:

        claw feishu-send oc_xxx "测试消息"
    """
    client = get_feishu_client()

    if not client:
        console.print("[error]飞书客户端未初始化[/]")
        raise typer.Exit(1)

    if client.send_text_message(chat_id, message):
        console.print("[success]消息发送成功[/]")
    else:
        console.print("[error]消息发送失败[/]")
        raise typer.Exit(1)


@app.command("scheduler-start")
def scheduler_start_cmd():
    """
    启动遗忘调度器

    调度器会每天上午 9 点检查即将过期的记忆并发送提醒
    """
    scheduler = start_scheduler()
    console.print("[success]遗忘调度器已启动[/]")
    console.print("[info]按 Ctrl+C 停止[/]")

    try:
        # 保持运行
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop_scheduler()
        console.print("\n[info]调度器已停止[/]")


@app.command("scheduler-check")
def scheduler_check_cmd(
    chat_id: Optional[str] = typer.Option(
        None,
        "--chat-id",
        "-c",
        help="飞书群聊 ID（可选）"
    ),
):
    """
    手动检查即将过期的记忆

    示例:

        claw scheduler-check

        claw scheduler-check -c oc_xxx
    """
    scheduler = get_forgetting_scheduler(chat_id)
    stats = scheduler.check_expiring_memories()

    console.print(Panel(
        f"[info]即将过期：[/] {stats['expiring_count']}\n"
        f"[info]需要复习：[/] {stats['review_count']}\n"
        f"[success]发送通知：[/] {stats['notified']}\n"
        f"[error]失败：[/] {stats['failed']}",
        title="📊 检查结果",
        border_style="cyan"
    ))


# ==================== 导入 time 模块 ====================

import time

if __name__ == "__main__":
    app()
