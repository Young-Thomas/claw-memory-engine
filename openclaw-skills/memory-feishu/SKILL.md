---
name: memory-feishu
description: 通过飞书群聊与记忆引擎交互，支持消息通知和卡片交互
version: 1.0.0
metadata:
  openclaw:
    requires:
      env:
        - FEISHU_APP_ID
        - FEISHU_APP_SECRET
    emoji: "\U0001F4E8"
---

# Memory Feishu Integration Skill

当用户想要通过飞书与记忆引擎交互时使用此技能。支持在飞书群聊中记录、查询和管理记忆。

## 触发条件

- 用户在飞书中 @机器人 说"记住命令"、"查找命令"
- 用户想要将记忆通知推送到飞书群聊
- 用户想要查看飞书端的记忆卡片

## 使用方式

### 测试飞书连接

```bash
claw feishu-test <app_id> <app_secret>
```

### 发送飞书消息

```bash
claw feishu-send <chat_id> "<消息内容>"
```

### 飞书卡片交互

记忆引擎会通过飞书交互式卡片提供以下功能：

1. **记忆提醒卡片**：当记忆即将过期时自动推送
   - 显示命令别名和完整命令
   - "我已记住"按钮：重置遗忘曲线
   - "查看详情"按钮：展示遗忘曲线可视化

2. **记忆详情卡片**：展示完整的记忆信息
   - 命令信息（别名、命令、描述、标签）
   - 记忆状态（保留率进度条、状态指示）
   - 遗忘曲线预测可视化
   - 下次复习时间

3. **记忆总览卡片**：展示所有记忆的健康状态
   - 统计信息（健康/需复习/即将过期数量）
   - 每条记忆的保留率

## OpenClaw 集成

通过 OpenClaw 的飞书渠道，用户可以直接在飞书对话中使用记忆功能：

1. 在飞书中 @机器人 说"记住 deploy 是 kubectl apply -f prod/"
2. 机器人自动调用 `claw remember` 记录
3. 在飞书中说"查找部署命令"
4. 机器人自动调用 `claw find` 搜索并返回结果

## 配置要求

需要在 OpenClaw 配置中设置飞书渠道：

```bash
openclaw config set -- channels.feishu.appId "你的AppID"
openclaw config set -- channels.feishu.appSecret "你的AppSecret"
openclaw config set -- channels.feishu.enabled true
```
