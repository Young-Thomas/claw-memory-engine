---
name: memory-find
description: 语义搜索记忆命令，支持中文自然语言查询
version: 1.0.0
metadata:
  openclaw:
    requires:
      bins:
        - claw
    emoji: "\U0001F50D"
---

# Memory Find Skill

当用户想要查找之前记录的命令时使用此技能。支持语义搜索，无需精确匹配。

## 触发条件

- 用户说"查找命令"、"搜索命令"、"我之前记录的部署命令是什么"
- 用户说"find"、"search"、"lookup"
- 用户想回忆某个命令但只记得大概含义

## 使用方式

使用 `claw find` 命令搜索：

```bash
claw find "<查询内容>"
```

### 示例

当用户说"我之前记录的部署命令是什么"时：

```bash
claw find 部署
```

当用户说"找一下 docker 相关的命令"时：

```bash
claw find docker
```

当用户说"项目 A 的测试命令"时：

```bash
claw find 测试 --project /path/to/project-a
```

### 搜索模式

系统支持四种搜索模式，自动选择最优结果：

1. **精确匹配**：别名完全匹配（优先级最高）
2. **前缀匹配**：别名前缀匹配
3. **语义搜索**：基于向量嵌入的语义相似度匹配
4. **关键词匹配**：关键词命中（回退方案）

### 中文支持

搜索天然支持中文查询，即使记录的是英文命令，用中文描述也能找到。
