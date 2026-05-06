# 🧠 Claw Memory Engine

> **让 CLI 记住你的工作流 — 企业级长程协作 Memory 系统**

飞书 OpenClaw 赛道参赛作品 | 覆盖方向 A + B + D | 已集成 OpenClaw Plugin + Skills + 飞书渠道

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![OpenClaw Plugin](https://img.shields.io/badge/OpenClaw-Plugin-green.svg)](https://openclaw.ai/)
[![Tests](https://img.shields.io/badge/tests-8%2F8-brightgreen.svg)]()

---

## 快速开始

```bash
git clone https://github.com/your-org/claw-memory-engine.git
cd claw-memory-engine
pip install -e .
claw remember deploy-prod "kubectl apply -f prod/"
claw find 部署
```

⚠️ **注意事项：**
- Windows 用户如果遇到 ChromaDB DLL 加载失败，手动降级版本：`pip install chromadb==0.4.24`
- PowerShell TAB 补全需要 PSReadLine 2.1+，`claw install-shell-completion` 会自动检测升级

---

## 功能全景

### 方向 A：CLI 高频命令与工作流记忆

| 功能 | 命令 | 说明 |
|------|------|------|
| **显式记忆** | `claw remember deploy "kubectl..."` | 主动教系统记住命令 |
| **隐式记忆** | `claw scan-history` | 自动解析 Shell 历史，提取高频命令 |
| **语义搜索** | `claw find 部署` | 中文自然语言搜索，无需精确匹配 |
| **项目上下文** | 自动检测 | 同名命令在不同项目有不同含义 |
| **Shell 级 TAB 补全** | `claw install-shell-completion` | 输入 `deploy-<TAB>` 直接补全为完整命令，< 50ms 响应，自动升级 PSReadLine 到 2.4.5+ |
| **使用统计** | `claw list / claw show` | 频率排序、详情查看 |

### 方向 B：飞书项目决策与上下文记忆

| 功能 | 命令 | 说明 |
|------|------|------|
| **决策提取** | `claw extract-decision "决定用B，因为性能更好"` | 从文本中提取决策+理由+结论+反对意见 |
| **决策搜索** | `claw find-decision "技术选型"` | 语义搜索历史决策 |
| **飞书对话提取** | OpenClaw Gateway 自动路由 | @机器人 对话自动提取决策 |

### 方向 D：团队知识断层与遗忘预警

| 功能 | 命令 | 说明 |
|------|------|------|
| **团队记忆注入** | `claw team-inject "API密钥已更新" --scope team:backend` | 团队级共享记忆 |
| **团队记忆列表** | `claw team-list --scope team:backend` | 查看团队作用域记忆 |
| **版本覆盖** | 同别名再次注入自动更新 | 保留版本链，旧版本可追溯 |
| **遗忘曲线** | Ebbinghaus 模型 | R=exp(-t/S)，频率越高越稳定 |
| **飞书遗忘提醒** | `claw scheduler-check --chat-id oc_xxx` | 即将过期记忆推送飞书卡片 |
| **团队遗忘状态** | `claw team-forgetting --scope team:backend` | 团队记忆遗忘状态概览 |

### OpenClaw 集成

| 功能 | 命令/方式 | 说明 |
|------|-----------|------|
| **插件注册** | `openclaw.plugin.json` | kind: memory 类型插件 |
| **5 个 Skills** | `openclaw-skills/` | remember/find/list/forgetting/feishu，带明确触发条件 |
| **Gateway 对接** | `openclaw gateway` | 飞书→Gateway→Agent→claw 完整链路，WebSocket 长连接 |
| **飞书渠道** | WebSocket 长连接 | 实时接收飞书消息 |
| **安装插件** | `claw openclaw-install` | 一键安装到 OpenClaw 插件目录 |
| **查看状态** | `claw openclaw-status` | 插件+Skills+渠道状态 |
| **Agent 交互** | `openclaw agent --message "..."` | 通过 AI Agent 调用记忆功能 |

⚠️ **Gateway 权限问题解决：**
如果启动 Gateway 报 `scope upgrade pending approval` 错误，手动编辑 `~/.openclaw/devices/paired.json`，在 `scopes` 数组中添加 `operator.write`，重启 Gateway 即可

### 飞书集成

| 功能 | 命令 | 说明 |
|------|------|------|
| **测试连接** | `claw feishu-test` | 验证飞书 App 凭据 |
| **发送消息** | `claw feishu-send` | 推送文本消息到群聊 |
| **遗忘调度** | `claw scheduler-start` | 每日9点检查+启动时立即检查 |
| **交互卡片** | 飞书回调服务 | "我已记住"按钮重置遗忘曲线 |

⚠️ **飞书后台配置必填：**
1. 打开飞书开发者后台 → 你的应用 → 事件与回调 → 事件配置
2. 订阅方式选择：**使用长连接接收事件/回调**
3. 添加事件：`im.message.receive_v1`（接收消息事件）
4. 左侧菜单 → 应用能力 → 机器人 → 启用机器人
5. 创建版本并发布审核（自建应用秒过），才能正常接收群聊@消息

---

## 核心亮点

### 🎯 混合检索引擎

四种模式自动切换，确保最优结果：

```
精确匹配（别名完全匹配）→ 前缀匹配 → 语义搜索（向量相似度）→ 关键词匹配（回退）
```

### 🧠 Ebbinghaus 遗忘曲线

```
R = exp(-t / S)

使用频率  稳定性S   7天后保留率
  1次     0.5       0.00%  ← 极不稳定
  5次     2.0       3.00%  
 10次     4.0      17.00%  ← 较稳定
 20次     8.0      42.00%  ← 非常稳定
```

### 📁 项目上下文感知

```bash
# 项目 A 中
cd /project-a && claw remember deploy "kubectl apply -f a/"
# 项目 B 中
cd /project-b && claw remember deploy "docker-compose up"
# 搜索时自动过滤
cd /project-a && claw find deploy  # → kubectl apply -f a/
cd /project-b && claw find deploy  # → docker-compose up
```

### 🔌 OpenClaw 端到端链路

```
飞书用户 @机器人 "查找部署命令"
    → OpenClaw Gateway (WebSocket)
    → Agent 路由到 memory-find Skill
    → claw find 部署
    → 返回搜索结果
    → Agent 格式化回复给用户
```

---

## 评测结果（8/8 全部通过）

| 测试 | 结果 | 关键数据 |
|------|------|----------|
| 抗干扰测试 | ✅ | 召回率 100%（10/10，100条噪声） |
| 矛盾更新测试 | ✅ | 同项目覆盖 + 不同项目隔离 + 版本链追溯 |
| 效能指标 | ✅ | 字符节省 81.18%，步骤节省 66.67%，延迟 3.08ms |
| 上下文感知命中率 | ✅ | 100%（6/6） |
| 语义搜索准确率 | ✅ | 85.71%（6/7） |
| 遗忘曲线测试 | ✅ | 公式 R=exp(-t/S) 精确匹配 |
| 决策提取测试 | ✅ | 决策+理由+结论+反对意见 3/3 场景 |
| 团队记忆测试 | ✅ | 注入+版本覆盖+列表 |

---

## 完整命令参考

### 记忆管理

```bash
claw remember <alias> <command> [--desc] [--tags] [--project]
claw find <query> [--project] [--limit]
claw list [--project] [--limit] [--all]
claw show <alias> [--project]
claw delete <alias> [--project] [--force]
```

### 隐式记忆

```bash
claw scan-history [--min-freq] [--max] [--dry-run]
```

### 决策提取

```bash
claw extract-decision <text> [--project] [--source] [--chat-id]
claw find-decision <query> [--project] [--limit]
```

### 团队记忆

```bash
claw team-inject <content> [--alias] [--scope] [--desc] [--tags] [--chat-id] [--by]
claw team-list [--scope] [--limit]
claw team-forgetting [--scope] [--chat-id]
```

### Shell 补全

```bash
claw install-shell-completion [--shell bash/zsh/powershell]
claw _shell-complete <prefix>   # 内部命令，被 Shell 脚本调用
```

### 飞书集成

```bash
claw feishu-test [app_id] [app_secret]
claw feishu-send <chat_id> <message>
claw scheduler-start
claw scheduler-check [--chat-id]
```

### OpenClaw 集成

```bash
claw openclaw-install
claw openclaw-config --app-id xxx --app-secret xxx
claw openclaw-skills
claw openclaw-status
```

---

## 技术架构

```
┌──────────────────────────────────────────────────────────────────┐
│                          用户交互层                               │
│  ┌──────────┐  ┌──────────┐  ┌────────────────────────────┐     │
│  │ CLI 终端  │  │ 飞书群聊  │  │ OpenClaw Gateway (Agent)   │     │
│  └─────┬────┘  └─────┬────┘  └──────────┬─────────────────┘     │
│        └──────────────┼─────────────────┘                       │
│                       ▼                                          │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │               统一 API 层 (OpenClawBridge)                │   │
│  └──────────────────────────┬───────────────────────────────┘   │
│                             ▼                                    │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐        │
│  │检索引擎│ │遗忘引擎│ │决策引擎│ │团队引擎│ │隐式引擎│        │
│  │混合检索│ │Ebbinghaus│ │NLP提取│ │共享作用│ │历史解析│        │
│  └────────┘ └────────┘ └────────┘ └────────┘ └────────┘        │
│                             ▼                                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                      │
│  │ SQLite   │  │ ChromaDB │  │ MiniLM   │                      │
│  └──────────┘  └──────────┘  └──────────┘                      │
└──────────────────────────────────────────────────────────────────┘
```

### 技术栈

| 组件 | 技术 | 说明 |
|------|------|------|
| CLI 框架 | Typer | 类型提示驱动 |
| 输出美化 | Rich | 终端美化 |
| 关系存储 | SQLite | 零配置嵌入式 |
| 向量存储 | ChromaDB | 轻量级向量数据库 |
| 嵌入模型 | all-MiniLM-L6-v2 | 384维，中英文兼顾 |
| 遗忘模型 | Ebbinghaus | 认知科学经典模型 |
| 调度器 | APScheduler | Cron + 启动时立即检查 |
| 飞书 SDK | lark-oapi | WebSocket 长连接 |
| AI 模型 | DeepSeek V4 Flash | Agent 推理引擎 |
| OpenClaw | 2026.5.3 | Plugin + Skills + Gateway |

---

## 项目结构

```
claw-memory-engine/
├── docs/WHITEPAPER.md              # Memory 定义与架构白皮书
├── openclaw.plugin.json            # OpenClaw 插件清单
├── openclaw-plugin/                # OpenClaw 插件代码
├── openclaw-skills/                # 5 个 OpenClaw Skills
├── src/
│   ├── cli/
│   │   ├── main.py                 # CLI 入口（全部命令）
│   │   ├── completion.py           # claw 子命令补全
│   │   └── shell_completion.py     # Shell 级 TAB 补全
│   ├── core/
│   │   ├── models.py               # 数据模型
│   │   ├── forgetting.py           # Ebbinghaus 遗忘引擎
│   │   ├── implicit_memory.py      # 隐式记忆（Shell 历史解析）
│   │   ├── decision_engine.py      # 决策提取引擎
│   │   └── team_memory.py          # 团队共享记忆引擎
│   ├── storage/
│   │   ├── sqlite_store.py         # SQLite 存储
│   │   └── chroma_store.py         # ChromaDB 向量存储
│   ├── retrieval/
│   │   ├── embeddings.py           # 嵌入模型
│   │   └── engine.py               # 混合检索引擎
│   ├── integrations/
│   │   ├── feishu.py               # 飞书 API 客户端
│   │   ├── scheduler.py            # 遗忘调度器
│   │   └── openclaw.py             # OpenClaw 桥接器
│   ├── config/config_manager.py    # 配置管理
│   ├── logger/logger.py            # 日志系统
│   └── utils/project.py           # 项目检测
├── tests/
│   ├── benchmark/
│   │   ├── run_benchmark.py        # 8 项评测（真实数据）
│   │   └── benchmark_report.json   # 评测报告
│   ├── unit/                       # 单元测试（12+ 测试文件）
│   └── integration/                # 集成测试
├── feishu_callback_server.py       # 飞书回调服务
├── start_services.py               # 服务启动脚本
├── install.sh / install.bat        # 一键安装脚本
├── sub.md                          # 比赛周期提交文档
├── fin.md                          # 比赛复赛提交文档
├── requirements.txt
└── pyproject.toml
```

---

---

## 运行评测

```bash
# 运行全部 8 项评测
python tests/benchmark/run_benchmark.py

# 评测结果会输出到终端，同时保存到 tests/benchmark/benchmark_report.json
```

---

## 常见问题（FAQ）

### 1. PowerShell 输入 deploy- 按 TAB 没反应？
- 确保已运行 `. C:\Users\TX5PRO\.claw\shell-completion.ps1` 加载补全脚本
- 确保 PSReadLine 版本 >= 2.1：运行 `(Get-Module PSReadLine).Version` 查看
- 升级命令：`Install-Module PSReadLine -Force -SkipPublisherCheck -Scope CurrentUser`
- 旧版本自动降级到 Ctrl+Space 触发补全

### 2. 飞书群聊 @Bot 不回复？
- 检查 Gateway 是否在运行：`openclaw gateway`
- 检查飞书开发者后台是否配置了长连接事件订阅（`im.message.receive_v1` 事件）
- 检查 Bot 是否已加入群聊
- 检查 App 是否发布审核通过

### 3. OpenClaw Gateway 报 scope upgrade pending approval？
- 编辑 `~/.openclaw/devices/paired.json`
- 在 `scopes` 和 `approvedScopes` 数组中添加 `"operator.write"`
- 重启 Gateway 即可

### 4. Windows 启动报 ChromaDB DLL 加载失败？
- 降级 ChromaDB 版本：`pip install chromadb==0.4.24`
- 新版本 ChromaDB 的 Rust 绑定在 Windows 上有兼容性问题

### 5. 语义搜索结果不准？
- 先确保记忆已经成功创建：`claw list` 查看
- 中文搜索尽量用短语，不要太长
- 可以加 `--limit 10` 查看更多结果

---

## 许可证

MIT License
