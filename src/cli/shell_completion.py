"""
Shell 级别命令补全

实现真正的 TAB 补全：用户输入 deploy-<TAB> 直接补全为完整命令
支持 Bash、Zsh 和 PowerShell

关键设计：使用纯 SQLite 查询，不加载 ChromaDB/嵌入模型，确保毫秒级响应
PowerShell 需要 PSReadLine 2.1+ 才支持 Set-PSReadLineKeyHandler -ScriptBlock
"""

import os
import sys
import sqlite3
import logging
from pathlib import Path
from typing import List, Optional

from src.config.config_manager import get_db_path


def get_matching_memories(prefix: str, project: Optional[str] = None, limit: int = 20) -> List[dict]:
    """
    根据前缀获取匹配的记忆命令（纯 SQLite 查询，毫秒级响应）
    """
    try:
        db_path = str(get_db_path())
        if not os.path.exists(db_path):
            return []

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        if project:
            rows = conn.execute(
                """SELECT alias, command, description FROM memories
                   WHERE is_active = 1 AND project = ? AND (alias LIKE ? OR command LIKE ?)
                   ORDER BY frequency DESC, last_used_at DESC
                   LIMIT ?""",
                (project, f"{prefix}%", f"{prefix}%", limit)
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT alias, command, description FROM memories
                   WHERE is_active = 1 AND (alias LIKE ? OR command LIKE ?)
                   ORDER BY frequency DESC, last_used_at DESC
                   LIMIT ?""",
                (f"{prefix}%", f"{prefix}%", limit)
            ).fetchall()

        conn.close()

        results = []
        for row in rows:
            results.append({
                "alias": row["alias"],
                "command": row["command"],
                "description": row["description"] or "",
            })

        results.sort(key=lambda x: x["alias"].startswith(prefix), reverse=True)
        return results

    except Exception:
        return []


def generate_bash_shell_completion() -> str:
    return r'''# Claw Memory Engine - Shell-level completion for Bash
# Source this file in ~/.bashrc: source ~/.claw/shell-completion.bash

_claw_shell_complete() {
    local cur="${COMP_WORDS[COMP_CWORD]}"

    if [[ "${COMP_WORDS[0]}" == "claw" ]]; then
        return 124
    fi

    local completions
    completions=$(claw _shell-complete "$cur" 2>/dev/null)

    if [[ -n "$completions" ]]; then
        COMPREPLY=($(echo "$completions" | tr '\n' ' '))
        return 0
    fi

    return 124
}

complete -D -F _claw_shell_complete 2>/dev/null || true
'''


def generate_zsh_shell_completion() -> str:
    return r'''# Claw Memory Engine - Shell-level completion for Zsh
# Add to ~/.zshrc: source ~/.claw/shell-completion.zsh

_claw_shell_complete() {
    local prefix="${words[CURRENT]}"

    if [[ "${words[1]}" == "claw" ]]; then
        return
    fi

    local completions
    completions=(${(f)"$(claw _shell-complete "$prefix" 2>/dev/null)"})

    if [[ ${#completions} -gt 0 ]]; then
        compadd -U -a completions
    fi
}

compdef _claw_shell_complete -first-
'''


def generate_powershell_shell_completion() -> str:
    """
    生成 PowerShell shell 级别补全脚本

    使用 PSReadLine KeyHandler 拦截 TAB 键
    需要 PSReadLine 2.1+（自动安装）
    """
    return r'''# Claw Memory Engine - Shell-level completion for PowerShell
# Requires PSReadLine 2.1+ (auto-installed by claw install-shell-completion)

# Ensure PSReadLine is loaded (use latest version if available)
Import-Module PSReadLine -MinimumVersion 2.1 -ErrorAction SilentlyContinue
if (-not (Get-Module PSReadLine)) {
    Import-Module PSReadLine -ErrorAction SilentlyContinue
}

# Check PSReadLine version
$_clawPsrlVersion = $null
try {
    $_clawPsrlVersion = (Get-Module PSReadLine).Version
} catch {}

$_clawScriptBlockSupported = $false
if ($_clawPsrlVersion -and $_clawPsrlVersion -ge [version]"2.1") {
    $_clawScriptBlockSupported = $true
}

if (-not $_clawScriptBlockSupported) {
    Write-Host "  [Claw] Warning: PSReadLine $($_clawPsrlVersion) does not support custom Tab handlers." -ForegroundColor Yellow
    Write-Host "  [Claw] Please upgrade: Install-Module PSReadLine -Force -SkipPublisherCheck -Scope CurrentUser" -ForegroundColor Yellow
    Write-Host "  [Claw] Falling back to Ctrl+Space for completion." -ForegroundColor Yellow
}

# Define the Tab expansion handler
$clawTabHandler = {
    $line = $null
    $cursor = $null
    [Microsoft.PowerShell.PSConsoleReadLine]::GetBufferState([ref]$line, [ref]$cursor)

    if ($null -eq $line -or $cursor -eq 0) {
        [Microsoft.PowerShell.PSConsoleReadLine]::TabCompleteNext()
        return
    }

    $trimmedLine = $line.TrimStart()
    if ($trimmedLine.StartsWith("claw ") -or $trimmedLine -eq "claw") {
        [Microsoft.PowerShell.PSConsoleReadLine]::TabCompleteNext()
        return
    }

    $wordStart = $cursor - 1
    while ($wordStart -ge 0 -and $line[$wordStart] -notmatch '[\s|;&><(){}]' ) {
        $wordStart--
    }
    $wordStart++
    $prefix = $line.Substring($wordStart, $cursor - $wordStart)

    if ([string]::IsNullOrWhiteSpace($prefix)) {
        [Microsoft.PowerShell.PSConsoleReadLine]::TabCompleteNext()
        return
    }

    $results = $null
    try {
        $results = claw _shell-complete $prefix 2>$null | Where-Object { $_.Trim() -ne "" }
    } catch {
        [Microsoft.PowerShell.PSConsoleReadLine]::TabCompleteNext()
        return
    }

    if (-not $results -or $results.Count -eq 0) {
        [Microsoft.PowerShell.PSConsoleReadLine]::TabCompleteNext()
        return
    }

    $matchList = @($results | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne "" })

    if ($matchList.Count -eq 0) {
        [Microsoft.PowerShell.PSConsoleReadLine]::TabCompleteNext()
        return
    }

    if ($matchList.Count -eq 1) {
        $replacement = $matchList[0]
        [Microsoft.PowerShell.PSConsoleReadLine]::Replace($wordStart, $cursor - $wordStart, $replacement)
    }
    elseif ($matchList.Count -gt 1) {
        Write-Host ""
        Write-Host "  Claw Memory Suggestions:" -ForegroundColor Cyan
        for ($i = 0; $i -lt $matchList.Count; $i++) {
            Write-Host "    $($i+1). $($matchList[$i])" -ForegroundColor Yellow
        }
        Write-Host ""

        $commonPrefix = $matchList[0]
        foreach ($match in $matchList[1..($matchList.Count-1)]) {
            $j = 0
            while ($j -lt $commonPrefix.Length -and $j -lt $match.Length -and $commonPrefix[$j] -eq $match[$j]) {
                $j++
            }
            $commonPrefix = $commonPrefix.Substring(0, $j)
        }

        if ($commonPrefix.Length -gt $prefix.Length) {
            [Microsoft.PowerShell.PSConsoleReadLine]::Replace($wordStart, $cursor - $wordStart, $commonPrefix)
        }
    }
}

# Register the handler
if ($_clawScriptBlockSupported) {
    Set-PSReadLineKeyHandler -Chord Tab -ScriptBlock $clawTabHandler
    Write-Host "  [Claw] TAB completion loaded! Type a prefix (e.g. 'deploy-') and press TAB." -ForegroundColor Green
} else {
    # Fallback: use Ctrl+Spacebar
    Set-PSReadLineKeyHandler -Chord Ctrl+Spacebar -ScriptBlock $clawTabHandler -ErrorAction SilentlyContinue
    Write-Host "  [Claw] Ctrl+Space completion loaded (upgrade PSReadLine for TAB support)." -ForegroundColor Yellow
}
'''


def install_shell_completion(shell: Optional[str] = None) -> bool:
    claw_dir = Path.home() / ".claw"
    claw_dir.mkdir(parents=True, exist_ok=True)

    if shell is None:
        if sys.platform == "win32":
            shell = "powershell"
        else:
            shell_env = os.environ.get("SHELL", "")
            if "zsh" in shell_env:
                shell = "zsh"
            else:
                shell = "bash"

    if shell == "bash":
        script = generate_bash_shell_completion()
        target = claw_dir / "shell-completion.bash"
    elif shell == "zsh":
        script = generate_zsh_shell_completion()
        target = claw_dir / "shell-completion.zsh"
    elif shell == "powershell":
        script = generate_powershell_shell_completion()
        target = claw_dir / "shell-completion.ps1"

        # Auto-install PSReadLine 2.1+ for ScriptBlock support
        _ensure_psreadline()
    else:
        print(f"Unsupported shell: {shell}")
        return False

    with open(target, "w", encoding="utf-8") as f:
        f.write(script)

    print(f"Shell completion installed: {target}")

    if shell == "powershell":
        profile_dir = Path.home() / "Documents" / "PowerShell"
        profile_dir.mkdir(parents=True, exist_ok=True)
        profile_path = profile_dir / "Microsoft.PowerShell_profile.ps1"

        source_line = f". {target}"

        if profile_path.exists():
            content = profile_path.read_text(encoding="utf-8")
            if source_line not in content and "shell-completion.ps1" not in content:
                with open(profile_path, "a", encoding="utf-8") as f:
                    f.write(f"\n{source_line}\n")
                print(f"Added to PowerShell profile: {profile_path}")
            else:
                print(f"PowerShell profile already contains claw completion: {profile_path}")
        else:
            with open(profile_path, "w", encoding="utf-8") as f:
                f.write(f"{source_line}\n")
            print(f"Created PowerShell profile: {profile_path}")

        print(f"\nTo load in current session, run:")
        print(f"  . {target}")

    elif shell == "bash":
        bashrc = Path.home() / ".bashrc"
        source_line = f"source {target}"
        if bashrc.exists():
            content = bashrc.read_text(encoding="utf-8")
            if source_line not in content:
                with open(bashrc, "a", encoding="utf-8") as f:
                    f.write(f"\n{source_line}\n")
        print(f"\nAdd to ~/.bashrc:")
        print(f"  {source_line}")
    elif shell == "zsh":
        zshrc = Path.home() / ".zshrc"
        source_line = f"source {target}"
        if zshrc.exists():
            content = zshrc.read_text(encoding="utf-8")
            if source_line not in content:
                with open(zshrc, "a", encoding="utf-8") as f:
                    f.write(f"\n{source_line}\n")
        print(f"\nAdd to ~/.zshrc:")
        print(f"  {source_line}")

    return True


def _ensure_psreadline():
    """Ensure PSReadLine 2.1+ is installed for ScriptBlock KeyHandler support"""
    try:
        import subprocess
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Import-Module PSReadLine -ErrorAction SilentlyContinue; "
             "$v = (Get-Module PSReadLine).Version; "
             "if ($v -and $v -ge [version]'2.1') { 'OK' } else { 'UPGRADE' }"],
            capture_output=True, text=True, timeout=30
        )
        status = result.stdout.strip()

        if status == "OK":
            print(f"PSReadLine 2.1+ already installed")
            return

        print(f"PSReadLine needs upgrade (current: {status}). Installing...")
        subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
             "Install-PackageProvider -Name NuGet -MinimumVersion 2.8.5.201 -Force -Scope CurrentUser | Out-Null; "
             "Install-Module PSReadLine -Force -SkipPublisherCheck -Scope CurrentUser"],
            capture_output=True, text=True, timeout=120
        )
        print(f"PSReadLine upgraded successfully")

    except Exception as e:
        print(f"Warning: Could not auto-upgrade PSReadLine: {e}")
        print(f"Please run manually: Install-Module PSReadLine -Force -SkipPublisherCheck -Scope CurrentUser")
