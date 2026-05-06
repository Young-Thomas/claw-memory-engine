---
name: memory-remember
description: 记录一条命令记忆，让 CLI 记住你的工作流命令
version: 1.0.0
metadata:
  openclaw:
    requires:
      bins:
        - claw
    emoji: "\U0001F4DD"
    homepage: https://github.com/claw-memory-engine
---

# Memory Remember Skill

当用户想要记录或保存一个命令时使用此技能。

## 触发条件

- 用户说"记住这个命令"、"记录命令"、"保存命令"
- 用户说"remember"、"save command"
- 用户提供了别名和命令的组合

## 使用方式

使用 `claw remember` 命令记录：

```bash
claw remember <别名> "<完整命令>" --desc "描述" --tags "标签1,标签2"
```

### 示例

当用户说"记住 deploy-prod 是 kubectl apply -f prod/"时：

```bash
claw remember deploy-prod "kubectl apply -f prod/" --desc "部署到生产环境"
```

当用户说"保存测试命令 pytest tests/unit/"时：

```bash
claw remember test-unit "pytest tests/unit/" --tags testing,python
```

### 参数说明

- **别名**（必填）：命令的短名称，用于快速调用
- **完整命令**（必填）：实际要执行的命令
- **--desc**（可选）：命令描述
- **--tags**（可选）：标签，逗号分隔
- **--project**（可选）：关联项目路径，默认自动检测

### 项目上下文

如果在某个项目目录下执行，系统会自动关联当前项目。同一别名在不同项目中可以有不同的命令。

### 冲突处理

如果同名别名已存在，系统会自动更新为最新命令，并保留版本链用于追溯。
