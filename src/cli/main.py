"""
Claw Memory Engine - CLI 主入口

使用 Typer 框架构建现代化 CLI
"""

import sys
import os
from pathlib import Path
from typing import Optional, List

if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.theme import Theme

from src.core.models import Memory
from src.core.implicit_memory import ImplicitMemoryEngine
from src.core.decision_engine import DecisionEngine
from src.core.team_memory import TeamMemoryEngine
from src.storage.sqlite_store import SQLiteStore
from src.storage.chroma_store import ChromaStore
from src.retrieval.engine import RetrievalEngine, ContextManager
from src.retrieval.embeddings import encode_text
from src.cli.completion import install_completion, generate_bash_completion, generate_zsh_completion, get_complete_aliases
from src.cli.shell_completion import get_matching_memories, install_shell_completion
from src.config.config_manager import get_config_manager, Config
from src.integrations.feishu import FeishuClient, get_feishu_client
from src.integrations.scheduler import get_forgetting_scheduler, start_scheduler, stop_scheduler
from src.integrations.openclaw import get_openclaw_bridge

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


# ==================== 团队共享记忆命令 ====================

@app.command("team-inject")
def team_inject_cmd(
    content: str = typer.Argument(..., help="记忆内容"),
    alias: Optional[str] = typer.Option(None, "--alias", "-a", help="别名"),
    scope: str = typer.Option("team:default", "--scope", "-s", help="作用域 (personal / team:{id} / project:{path})"),
    description: Optional[str] = typer.Option(None, "--desc", "-d", help="描述"),
    tags: Optional[str] = typer.Option(None, "--tags", "-t", help="标签（逗号分隔）"),
    chat_id: Optional[str] = typer.Option(None, "--chat-id", help="飞书群聊ID"),
    injected_by: Optional[str] = typer.Option(None, "--by", help="注入者"),
):
    """
    注入团队共享记忆

    示例:

        claw team-inject "API密钥已更新为xxx" --scope team:backend

        claw team-inject "部署流程变更" --alias deploy-process --desc "新流程" --chat-id oc_xxx

        claw team-inject "客户偏好A方案" --scope project:/my-project --by "张三"
    """
    engine = TeamMemoryEngine()
    tag_list = tags.split(",") if tags else None

    result = engine.inject(
        content=content,
        alias=alias,
        scope=scope,
        description=description,
        tags=tag_list,
        chat_id=chat_id,
        injected_by=injected_by,
    )

    action_text = "更新" if result["action"] == "updated" else "创建"
    console.print(
        Panel(
            f"[success]团队记忆已{action_text}[/]\n\n"
            f"  别名: {result['alias']}\n\n"
            f"  作用域: {result['scope']}\n\n"
            f"  版本: v{result['version']}\n\n"
            f"  注入者: {result.get('injected_by', 'N/A')}",
            title="📢 团队共享记忆",
            border_style="green"
        )
    )


@app.command("team-list")
def team_list_cmd(
    scope: str = typer.Option("team:default", "--scope", "-s", help="作用域"),
    limit: int = typer.Option(20, "--limit", "-l", help="最大数量"),
):
    """
    列出团队/项目作用域的记忆

    示例:

        claw team-list --scope team:backend

        claw team-list --scope project:/my-project
    """
    engine = TeamMemoryEngine()
    result = engine.list_team_memories(scope, limit)

    if result["count"] == 0:
        console.print(f"[info]作用域 {scope} 暂无记忆[/]")
        return

    table = Table(
        title=f"📢 团队记忆 (作用域: {scope})",
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("别名", style="cyan")
    table.add_column("内容", style="green")
    table.add_column("标签", style="yellow")
    table.add_column("版本", style="blue")
    table.add_column("频率", style="magenta")

    for m in result["memories"]:
        table.add_row(
            m["alias"],
            m["content"][:40],
            ",".join(m["tags"][:3]),
            f"v{m['version']}",
            str(m["frequency"]),
        )

    console.print(table)


@app.command("team-forgetting")
def team_forgetting_cmd(
    scope: str = typer.Option("team:default", "--scope", "-s", help="作用域"),
    chat_id: Optional[str] = typer.Option(None, "--chat-id", help="飞书群聊ID"),
):
    """
    检查团队记忆的遗忘状态

    示例:

        claw team-forgetting --scope team:backend

        claw team-forgetting --scope team:backend --chat-id oc_xxx
    """
    engine = TeamMemoryEngine()
    result = engine.check_team_forgetting(scope, chat_id)

    console.print(
        Panel(
            f"作用域: {result['scope']}\n\n"
            f"🔴 即将过期: {result['expiring_soon']} 条\n\n"
            f"🟡 需要复习: {result['review_needed']} 条",
            title="⚠️ 团队记忆遗忘状态",
            border_style="yellow"
        )
    )

    if result["expiring_details"]:
        console.print("\n[error]即将过期:[/]")
        for item in result["expiring_details"]:
            console.print(f"  • {item['alias']}: {item['content'][:40]} (保留率: {item['retention']:.0%})")

    if result["review_details"]:
        console.print("\n[warning]需要复习:[/]")
        for item in result["review_details"]:
            console.print(f"  • {item['alias']}: {item['content'][:40]} (保留率: {item['retention']:.0%})")


# ==================== 决策提取命令 ====================

@app.command("extract-decision")
def extract_decision_cmd(
    text: str = typer.Argument(..., help="要提取决策的文本"),
    project: Optional[str] = typer.Option(None, "--project", "-p", help="关联项目"),
    source: Optional[str] = typer.Option(None, "--source", "-s", help="来源（如飞书群聊ID）"),
    chat_id: Optional[str] = typer.Option(None, "--chat-id", help="飞书群聊ID（用于推送通知）"),
):
    """
    从文本中提取结构化决策记忆

    支持提取：决策内容、理由、结论、反对意见

    示例:

        claw extract-decision "我们决定采用方案B，因为性能更好"

        claw extract-decision "确认截止日期是5号" --project /my-project

        claw extract-decision "决定用React，不过有人反对觉得Vue更好" --chat-id oc_xxx
    """
    engine = DecisionEngine()
    result = engine.extract_and_store(
        text=text,
        project=project,
        source=source,
        chat_id=chat_id,
    )

    if result["decisions_found"] == 0:
        console.print("[info]未检测到决策内容[/]")
        return

    console.print(
        Panel(
            f"[success]提取到 {result['decisions_found']} 条决策，已存储 {result['stored']} 条[/]",
            title="📋 决策提取",
            border_style="green"
        )
    )

    for detail in result.get("details", []):
        lines = [f"  决策: {detail['content']}"]
        if detail.get("reason"):
            lines.append(f"  理由: {detail['reason']}")
        if detail.get("conclusion"):
            lines.append(f"  结论: {detail['conclusion']}")
        if detail.get("opposition"):
            lines.append(f"  反对: {detail['opposition']}")
        console.print("\n".join(lines))


@app.command("find-decision")
def find_decision_cmd(
    query: str = typer.Argument(..., help="搜索查询"),
    project: Optional[str] = typer.Option(None, "--project", "-p", help="关联项目"),
    limit: int = typer.Option(5, "--limit", "-l", help="最大结果数"),
):
    """
    查找与查询相关的历史决策

    示例:

        claw find-decision "技术选型"

        claw find-decision "截止日期" --project /my-project
    """
    engine = DecisionEngine()
    results = engine.find_related_decisions(query, project, limit)

    if not results:
        console.print("[info]未找到相关决策[/]")
        return

    table = Table(
        title="📋 相关决策",
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("决策内容", style="cyan")
    table.add_column("描述", style="green")
    table.add_column("匹配度", style="yellow")
    table.add_column("匹配类型", style="blue")

    for r in results:
        table.add_row(
            r["content"][:50],
            (r["description"] or "")[:50],
            f"{r['score']:.2f}",
            r["match_type"],
        )

    console.print(table)


# ==================== 隐式记忆命令 ====================

@app.command("scan-history")
def scan_history_cmd(
    min_freq: int = typer.Option(
        3, "--min-freq", "-m", help="最小频率阈值"
    ),
    max_memories: int = typer.Option(
        50, "--max", help="最大记忆数量"
    ),
    project: Optional[str] = typer.Option(
        None, "--project", "-p", help="关联项目"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="仅预览，不实际写入"
    ),
):
    """
    扫描 Shell 命令历史，自动提取高频命令作为隐式记忆

    支持 Bash (.bash_history)、Zsh (.zsh_history)、PowerShell (PSReadLine)

    示例:

        claw scan-history

        claw scan-history --min-freq 5 --max 30

        claw scan-history --dry-run
    """
    engine = ImplicitMemoryEngine()

    if dry_run:
        stats = engine.get_history_stats()
        console.print(
            Panel(
                f"[info]历史文件：[/]\n"
                + "\n".join(f"  • {f}" for f in stats["history_files"])
                + f"\n\n[info]总命令数：[/]{stats['total_commands']}\n\n"
                f"[info]高频命令数：[/]{stats['frequent_commands']} (freq >= {min_freq})",
                title="📊 历史扫描预览",
                border_style="cyan"
            )
        )

        if stats["top_10"]:
            table = Table(title="Top 10 高频命令", show_header=True, header_style="bold magenta")
            table.add_column("命令", style="green")
            table.add_column("频率", style="yellow", justify="right")
            for cmd, freq in stats["top_10"]:
                table.add_row(cmd, str(freq))
            console.print(table)
        return

    result = engine.sync_to_memory(
        min_freq=min_freq,
        max_memories=max_memories,
        project=project,
    )

    console.print(
        Panel(
            f"[success]隐式记忆同步完成[/]\n\n"
            f"  ✅ 新增：{result['created']} 条\n\n"
            f"  🔄 更新：{result['updated']} 条\n\n"
            f"  ⏭️ 跳过：{result['skipped']} 条",
            title="🧠 隐式记忆",
            border_style="green"
        )
    )


# ==================== OpenClaw 集成命令 ====================

@app.command("openclaw-install")
def openclaw_install_cmd():
    """
    安装插件到 OpenClaw

    将记忆引擎注册为 OpenClaw 插件，包括 Skills 和配置
    """
    bridge = get_openclaw_bridge()

    try:
        bridge.install_to_openclaw()
        console.print(
            Panel(
                "[success]插件安装成功[/]\n\n"
                "[info]已安装以下组件：[/]\n"
                "  • openclaw.plugin.json（插件清单）\n"
                "  • openclaw-plugin/（插件代码）\n"
                "  • openclaw-skills/（5 个 Skills）\n\n"
                "[info]下一步：[/]\n"
                "  1. 运行 [alias]claw openclaw-config[/] 配置飞书渠道\n"
                "  2. 运行 [alias]openclaw gateway[/] 启动网关",
                title="🔌 OpenClaw 集成",
                border_style="green"
            )
        )
    except Exception as e:
        console.print(f"[error]安装失败：{e}[/]")
        raise typer.Exit(1)


@app.command("openclaw-config")
def openclaw_config_cmd(
    app_id: str = typer.Option(..., "--app-id", help="飞书 App ID"),
    app_secret: str = typer.Option(..., "--app-secret", help="飞书 App Secret"),
):
    """
    配置 OpenClaw 飞书渠道

    示例:

        claw openclaw-config --app-id cli_xxx --app-secret xxx
    """
    bridge = get_openclaw_bridge()

    if bridge.configure_openclaw_channel(app_id, app_secret):
        console.print("[success]OpenClaw 飞书渠道配置成功[/]")
        console.print("[info]请运行 openclaw gateway 启动网关[/]")
    else:
        console.print("[error]配置失败，请确认 OpenClaw 已安装[/]")
        console.print("[info]安装 OpenClaw: npm i -g openclaw[/]")
        raise typer.Exit(1)


@app.command("openclaw-skills")
def openclaw_skills_cmd():
    """
    列出所有 OpenClaw Skills
    """
    bridge = get_openclaw_bridge()
    skills = bridge.get_skills_list()

    if not skills:
        console.print("[info]暂无可用 Skills[/]")
        return

    table = Table(
        title="🧩 OpenClaw Skills",
        show_header=True,
        header_style="bold magenta",
    )

    table.add_column("名称", style="cyan")
    table.add_column("描述", style="green")
    table.add_column("版本", style="yellow")

    for skill in skills:
        table.add_row(
            skill.get("name", "unknown"),
            skill.get("description", ""),
            skill.get("version", ""),
        )

    console.print(table)


@app.command("openclaw-status")
def openclaw_status_cmd():
    """
    查看 OpenClaw 集成状态
    """
    bridge = get_openclaw_bridge()
    manifest = bridge.get_plugin_manifest()
    skills = bridge.get_skills_list()

    openclaw_installed = False
    openclaw_version = "未安装"
    try:
        import subprocess
        import shutil
        openclaw_path = shutil.which("openclaw")
        if not openclaw_path:
            for candidate in [
                os.path.join(os.environ.get("APPDATA", ""), "npm", "openclaw.cmd"),
                os.path.join(os.environ.get("APPDATA", ""), "npm", "openclaw"),
                "/usr/local/bin/openclaw",
            ]:
                if os.path.exists(candidate):
                    openclaw_path = candidate
                    break

        if openclaw_path:
            result = subprocess.run(
                [openclaw_path, "--version"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                openclaw_installed = True
                openclaw_version = result.stdout.strip()
    except Exception:
        pass

    console.print(
        Panel(
            f"[info]OpenClaw CLI：[/] {'✅ ' + openclaw_version if openclaw_installed else '❌ 未安装'}\n\n"
            f"[info]插件 ID：[/] {manifest.get('id', 'unknown')}\n\n"
            f"[info]插件版本：[/] {manifest.get('version', 'unknown')}\n\n"
            f"[info]插件类型：[/] {manifest.get('kind', 'unknown')}\n\n"
            f"[info]Skills 数量：[/] {len(skills)}\n\n"
            f"[info]数据目录：[/] {Path.home() / '.claw'}",
            title="🔌 OpenClaw 集成状态",
            border_style="cyan"
        )
    )

    if not openclaw_installed:
        console.print("\n[warning]OpenClaw 未安装，请运行：npm i -g openclaw[/]")


# ==================== Shell 级别补全命令 ====================

@app.command("install-shell-completion")
def install_shell_completion_cmd(
    shell: Optional[str] = typer.Option(
        None, "--shell", "-s", help="Shell type (bash/zsh/powershell)"
    ),
):
    """
    安装 Shell 级别 TAB 补全

    安装后，在终端输入 deploy-<TAB> 即可自动补全为完整命令

    示例:

        claw install-shell-completion

        claw install-shell-completion --shell bash
    """
    if install_shell_completion(shell):
        console.print("[success]Shell 补全安装成功[/]")
        console.print("[info]请按照提示将 source 命令添加到 shell 配置文件中[/]")
    else:
        console.print("[error]安装失败[/]")
        raise typer.Exit(1)


@app.command("_shell-complete", hidden=True)
def shell_complete_cmd(
    prefix: str = typer.Argument(..., help="输入前缀"),
):
    """
    Shell 补全后端（内部命令）

    当用户在终端按 TAB 时，shell 脚本会调用此命令获取补全建议
    """
    import os
    import logging

    logging.disable(logging.CRITICAL)

    matches = get_matching_memories(prefix, project=None)

    if not matches:
        try:
            ctx_manager = get_context_manager()
            context = ctx_manager.detect_context(os.getcwd())
            if context.git_root:
                matches = get_matching_memories(prefix, project=context.git_root)
        except Exception:
            pass

    for m in matches:
        print(m["command"])


if __name__ == "__main__":
    app()
