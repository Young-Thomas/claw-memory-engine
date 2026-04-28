# 🧠 Claw Memory Engine

> **让 CLI 记住你的工作流**

飞书 OpenClaw 赛道参赛作品 - 基于语义理解的 CLI 智能记忆助手

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 快速开始

### 安装

```bash
# 克隆项目
git clone https://github.com/your-org/claw-memory-engine.git
cd claw-memory-engine

# 安装依赖
pip install -r requirements.txt

# 安装为命令行工具
pip install -e .
```

### 基础使用

```bash
# 记录一个命令
claw remember deploy-prod "kubectl apply -f prod/"

# 记录带描述的命令
claw remember deploy "docker-compose up -d" --desc "部署服务"

# 记录带标签的命令
claw remember test "pytest tests/" --tags testing,python

# 搜索记忆（支持语义搜索）
claw find 部署

# 列出所有记忆
claw list

# 查看记忆详情
claw show deploy-prod

# 删除记忆
claw delete deploy-prod
```

---

## 核心功能

### 🎯 语义搜索

无需精确匹配，输入自然语言即可找到相关命令：

```bash
# 即使输入中文也能找到相关命令
claw find 部署
# → 找到：deploy-prod (相似度 0.89)

# 支持项目上下文
cd my-project && claw find 测试
# → 仅返回当前项目的测试命令
```

### 📁 项目上下文感知

自动检测当前项目，命令与项目关联：

```bash
# 在项目 A 中
cd /path/to/project-a
claw remember deploy "kubectl apply -f a/"

# 在项目 B 中
cd /path/to/project-b
claw remember deploy "docker-compose up -d"

# 搜索时自动过滤
cd /path/to/project-a && claw find deploy
# → 只返回 project-a 的部署命令
```

### 🧠 智能补全

支持 TAB 补全（需要配置 shell completion）：

```bash
# 输入别名后按 TAB
deploy-<TAB>
# → 自动补全为：kubectl apply -f prod/
```

### 📊 使用统计

```bash
# 查看高频命令
claw list --limit 10

# 查看命令详情（包含使用次数）
claw show deploy-prod
```

---

## 技术架构

```
┌─────────────────────────────────────────────────────────────┐
│                      Claw Memory Engine                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐   │
│  │   CLI Layer  │    │  Core Layer  │    │ Storage Layer│   │
│  │    (Typer)   │───▶│  (Processor) │───▶│ (SQLite +    │   │
│  │              │    │              │    │  ChromaDB)   │   │
│  └──────────────┘    └──────────────┘    └──────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Embedding Model                          │   │
│  │         (all-MiniLM-L6-v2, 384 dims)                 │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 技术栈

| 组件 | 技术 | 说明 |
|------|------|------|
| CLI 框架 | [Typer](https://typer.tiangolo.com/) | 现代 Python CLI 框架，基于类型提示 |
| 输出美化 | [Rich](https://github.com/Textualize/rich) | 终端美化库 |
| 关系存储 | [SQLite](https://www.sqlite.org/) | 本地嵌入式数据库 |
| 向量存储 | [ChromaDB](https://docs.trychroma.com/) | 轻量级向量数据库 |
| 嵌入模型 | [all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) | 384 维语义向量 |

---

## 命令参考

### 记录命令

```bash
claw remember <alias> <command> [OPTIONS]

选项:
  -d, --desc TEXT     命令描述
  -t, --tags TEXT     标签（逗号分隔）
  -p, --project TEXT  关联项目路径

示例:
  claw remember deploy-prod "kubectl apply -f prod/"
  claw remember test "pytest tests/" --tags testing,python
  claw remember build "npm run build" --project /path/to/project
```

### 搜索记忆

```bash
claw find <query> [OPTIONS]

选项:
  -p, --project TEXT  在项目范围内搜索
  -l, --limit INT     返回结果数量（默认 10）

示例:
  claw find 部署
  claw find "docker compose" -p /path/to/project
```

### 列出记忆

```bash
claw list [OPTIONS]

选项:
  -p, --project TEXT  只显示指定项目的记忆
  -l, --limit INT     显示数量上限（默认 20）
  -a, --all           显示所有记忆（包括已归档）
```

### 查看详情

```bash
claw show <alias> [OPTIONS]

选项:
  -p, --project TEXT  项目路径

示例:
  claw show deploy-prod
```

### 删除记忆

```bash
claw delete <alias> [OPTIONS]

选项:
  -p, --project TEXT  项目路径
  -f, --force         强制删除，不确认

示例:
  claw delete deploy-prod
  claw delete old-command -f
```

---

## 项目结构

```
claw-memory-engine/
├── README.md                 # 本文件
├── src/
│   ├── __init__.py
│   ├── cli/
│   │   ├── __init__.py
│   │   └── main.py           # CLI 入口
│   ├── core/
│   │   ├── __init__.py
│   │   ├── models.py         # 数据模型
│   │   └── forgetting.py     # 遗忘引擎
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── sqlite_store.py   # SQLite 存储
│   │   └── chroma_store.py   # ChromaDB 向量存储
│   ├── retrieval/
│   │   ├── __init__.py
│   │   ├── embeddings.py     # 嵌入模型
│   │   └── engine.py         # 检索引擎
│   └── utils/
│       ├── __init__.py
│       └── project.py        # 项目检测
├── tests/
│   ├── unit/
│   └── integration/
├── requirements.txt
└── pyproject.toml
```

---

## 贡献指南

欢迎提交 Issue 和 Pull Request！

```bash
# 开发环境设置
pip install -e ".[dev]"

# 运行测试
pytest

# 代码格式化
black src/ tests/
ruff check src/ tests/
```

---

## 许可证

MIT License - 详见 [LICENSE](LICENSE)

---

## 团队

Claw Memory Team - 飞书 OpenClaw 赛道参赛作品
