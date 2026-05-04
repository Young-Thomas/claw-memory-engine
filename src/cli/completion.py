"""
Shell 补全脚本生成

支持 bash 和 zsh
"""

import sys
from typing import Optional

from src.storage.sqlite_store import SQLiteStore
from src.retrieval.engine import RetrievalEngine


def get_aliases() -> list:
    """获取所有活跃的别名"""
    try:
        store = SQLiteStore()
        memories = store.find_all_active(limit=1000)
        return [m.alias for m in memories]
    except Exception:
        return []


def generate_bash_completion() -> str:
    """
    生成 Bash 补全脚本

    返回脚本内容
    """
    script = '''# Bash completion for claw
# Place this script in /etc/bash_completion.d/ or source it from ~/.bashrc

_claw_completion() {
    local cur="${COMP_WORDS[COMP_CWORD]}"
    local cmd="${COMP_WORDS[0]}"
    local prev="${COMP_WORDS[COMP_CWORD-1]}"

    # Claw 命令列表
    local commands="remember find list show delete help --version --help"

    # 获取已记忆的别名
    local aliases

    case "$prev" in
        remember)
            # 完成别名参数
            COMPREPLY=($(compgen -W "$commands" -- "$cur"))
            return 0
            ;;
        find|show|delete)
            # 完成别名
            aliases=$(_claw_get_aliases)
            COMPREPLY=($(compgen -W "$aliases" -- "$cur"))
            return 0
            ;;
        --project|-p)
            # 完成项目路径
            COMPREPLY=($(compgen -d -- "$cur"))
            return 0
            ;;
    esac

    # 检查是否是命令的第一个参数
    if [[ ${COMP_CWORD} -eq 1 ]]; then
        COMPREPLY=($(compgen -W "$commands" -- "$cur"))
    else
        # 默认：文件/目录补全
        COMPREPLY=($(compgen -f -- "$cur"))
    fi
}

# 获取别名的辅助函数
_claw_get_aliases() {
    if command -v claw &> /dev/null; then
        claw _complete-aliases 2>/dev/null || echo ""
    else
        echo ""
    fi
}

# 注册补全
complete -F _claw_completion claw
'''
    return script


def generate_zsh_completion() -> str:
    """
    生成 Zsh 补全脚本

    返回脚本内容
    """
    script = '''# Zsh completion for claw
# Place this file in a directory listed in $fpath (e.g., ~/.zsh/completion/)

#compdef claw

local -a _claw_commands
local -a _claw_aliases

_claw_commands=(
    'remember:Record a new command'
    'find:Search memories by query'
    'list:List all memories'
    'show:Show memory details'
    'delete:Delete a memory'
    'help:Show help message'
)

# 获取别名的辅助函数
_claw_get_aliases() {
    if (( ${+_claw_aliases} )); then
        return
    fi

    if command -v claw &> /dev/null; then
        local output
        output=$(claw _complete-aliases 2>/dev/null)
        _claw_aliases=(${(@s/ /)output})
    else
        _claw_aliases=()
    fi
}

_claw_completion() {
    local -a completions
    local state

    _claw_get_aliases

    _arguments -C \
        ':command:->command' \
        '*::options:->options'

    case $state in
        command)
            _describe 'command' _claw_commands
            ;;
        options)
            case $words[1] in
                remember)
                    _arguments \
                        '--desc[Command description]:description: ' \
                        '--tags[Tags (comma separated)]:tags: ' \
                        '--project[Project path]:project:_files' \
                        '*:alias: '
                    ;;
                find)
                    _arguments \
                        '--project[Project path]:project:_files' \
                        '--limit[Result limit]:limit: ' \
                        '*:query: '
                    ;;
                list)
                    _arguments \
                        '--project[Project path]:project:_files' \
                        '--limit[Result limit]:limit: ' \
                        '--all[Show all including archived]'
                    ;;
                show|delete)
                    _arguments \
                        '--project[Project path]:project:_files' \
                        '*:alias:_claw_aliases'
                    ;;
                *)
                    _message "Unknown command"
                    ;;
            esac

            # 通用选项
            _arguments \
                '--help[Show help]' \
                '--version[Show version]'
            ;;
    esac
}

# 注册补全
_claw_completion "$@"
'''
    return script


def get_complete_aliases() -> str:
    """
    获取所有别名（用于补全脚本调用）

    返回空格分隔的别名字符串
    """
    try:
        aliases = get_aliases()
        return " ".join(aliases)
    except Exception:
        return ""


def install_completion(shell: Optional[str] = None) -> bool:
    """
    安装补全脚本

    Args:
        shell: 指定 shell 类型，自动检测则为 None

    Returns:
        安装是否成功
    """
    import os
    from pathlib import Path

    # 检测 shell 类型
    if shell is None:
        shell = os.environ.get("SHELL", "")
        if "zsh" in shell:
            shell = "zsh"
        else:
            shell = "bash"

    # 生成补全脚本
    if shell == "zsh":
        script = generate_zsh_completion()
        # Zsh 补全目录
        completion_dir = Path.home() / ".zsh" / "completion"
        completion_dir.mkdir(parents=True, exist_ok=True)
        completion_file = completion_dir / "_claw"
    else:
        script = generate_bash_completion()
        # Bash 补全目录
        completion_file = Path.home() / ".claw_completion.bash"

    # 写入文件
    try:
        with open(completion_file, 'w', encoding='utf-8') as f:
            f.write(script)

        print(f"✓ Completion script installed: {completion_file}")

        # 提示用户如何启用
        if shell == "bash":
            print(f"\nAdd this line to your ~/.bashrc:")
            print(f"  source {completion_file}")
        else:
            print(f"\nMake sure {completion_dir} is in your $fpath")
            print(f"Add this line to your ~/.zshrc:")
            print(f"  fpath=(~/.zsh/completion $fpath)")

        return True

    except Exception as e:
        print(f"✗ Failed to install completion: {e}")
        return False
