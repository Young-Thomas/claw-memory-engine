---
name: memory-list
description: 列出所有已记录的命令记忆，查看高频命令
version: 1.0.0
metadata:
  openclaw:
    requires:
      bins:
        - claw
    emoji: "\U0001F4CB"
---

# Memory List Skill

当用户想要查看所有已记录的命令或高频命令时使用此技能。

## 触发条件

- 用户说"列出命令"、"查看所有记忆"、"我的高频命令"
- 用户说"list"、"show all"、"history"
- 用户想了解自己记录了哪些命令

## 使用方式

使用 `claw list` 命令：

```bash
claw list [选项]
```

### 示例

当用户说"列出所有命令"时：

```bash
claw list
```

当用户说"看项目 A 的命令"时：

```bash
claw list --project /path/to/project-a
```

当用户说"显示前 5 个高频命令"时：

```bash
claw list --limit 5
```

当用户说"包括已归档的"时：

```bash
claw list --all
```

### 输出信息

列表显示以下信息：
- **别名**：命令的短名称
- **命令**：完整命令（过长会截断）
- **项目**：关联的项目路径
- **频率**：使用次数
- **最后使用**：相对时间（如"3天前"）
