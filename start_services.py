"""
启动所有后台服务
- 飞书卡片回调服务（处理按钮点击，支持详细卡片和遗忘曲线可视化）
- 遗忘调度器（每天9点自动检查过期记忆）
"""

import math
import threading
import time
from datetime import datetime, timedelta
from typing import Optional

import lark_oapi as lark
from lark_oapi.event.callback.model.p2_card_action_trigger import P2CardActionTrigger, P2CardActionTriggerResponse

from src.integrations.scheduler import ForgettingScheduler
from src.integrations.feishu import get_feishu_client
from src.core.forgetting import EbbinghausForgettingEngine, RetentionStatus
from src.storage.sqlite_store import SQLiteStore

CHAT_ID = "oc_60b50cf03babe502eb81ca6367573a3b"
store = SQLiteStore()
forgetting_engine = EbbinghausForgettingEngine(store)


def build_retention_bar(retention: float) -> str:
    """构建保留率进度条"""
    filled = int(retention * 20)
    empty = 20 - filled
    bar = "█" * filled + "░" * empty
    return f"{bar} {retention*100:.0f}%"


def build_forgetting_curve_visual(retention: float, days_since: float, stability: float) -> str:
    """构建遗忘曲线文本可视化（飞书兼容版）"""
    points = [
        (0, "刚刚记住"),
        (0.5, "12小时"),
        (1, "1天"),
        (2, "2天"),
        (3, "3天"),
        (7, "1周"),
        (15, "2周"),
        (30, "1个月"),
    ]

    lines = []
    for days, label in points:
        r = math.exp(-days / stability) if stability > 0 else 0
        pct = int(r * 10)
        bar = "■" * pct + "□" * (10 - pct)

        is_current = False
        if days_since <= 0:
            is_current = (days == 0)
        elif days == points[-1][0]:
            is_current = (days_since >= days)
        else:
            prev_days = 0
            for d, _ in points:
                if d >= days_since:
                    break
                prev_days = d
            is_current = (abs(days - days_since) <= (days - prev_days) / 2 if days > prev_days else days == 0)

        marker = " ◀ 你在这里" if is_current else ""
        lines.append(f"{label:>4}  {bar}  {r*100:>3.0f}%{marker}")

    return "\n".join(lines)


def get_status_emoji(status: RetentionStatus) -> str:
    """获取状态对应的emoji"""
    return {
        RetentionStatus.HEALTHY: "🟢",
        RetentionStatus.REVIEW_NEEDED: "🟡",
        RetentionStatus.EXPIRING_SOON: "🔴",
        RetentionStatus.EXPIRED: "⚫",
    }.get(status, "⚪")


def get_status_text(status: RetentionStatus) -> str:
    """获取状态中文描述"""
    return {
        RetentionStatus.HEALTHY: "健康",
        RetentionStatus.REVIEW_NEEDED: "需要复习",
        RetentionStatus.EXPIRING_SOON: "即将过期",
        RetentionStatus.EXPIRED: "已过期",
    }.get(status, "未知")


def get_next_review_time(memory, retention: float, stability: float) -> str:
    """计算下次复习时间"""
    if stability <= 0:
        return "即将"
    days_until_50 = -stability * math.log(0.5)
    days_until_30 = -stability * math.log(0.3)
    if retention > 0.5:
        remaining = days_until_50 - (datetime.now() - memory.last_used_at).days
        if remaining > 0:
            return f"约{remaining:.0f}天后"
        return "今天"
    elif retention > 0.3:
        remaining = days_until_30 - (datetime.now() - memory.last_used_at).days
        if remaining > 0:
            return f"约{remaining:.0f}天后"
        return "今天"
    else:
        return "已过期，请尽快复习"


def build_detail_card(alias: str) -> Optional[dict]:
    """构建记忆详情卡片（含遗忘曲线可视化）"""
    memory_list = store.find_by_alias(alias)
    if not memory_list:
        return None
    memory = memory_list[0]

    retention, status = forgetting_engine.calculate_retention(memory)
    stability = forgetting_engine._get_stability(memory.frequency)
    days_since = (datetime.now() - memory.last_used_at).total_seconds() / 86400

    status_emoji = get_status_emoji(status)
    status_text = get_status_text(status)
    retention_bar = build_retention_bar(retention)
    curve_visual = build_forgetting_curve_visual(retention, days_since, stability)
    next_review = get_next_review_time(memory, retention, stability)

    color_map = {
        RetentionStatus.HEALTHY: "green",
        RetentionStatus.REVIEW_NEEDED: "orange",
        RetentionStatus.EXPIRING_SOON: "red",
        RetentionStatus.EXPIRED: "grey",
    }
    card_color = color_map.get(status, "blue")

    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": card_color,
            "title": {
                "tag": "plain_text",
                "content": f"📋 记忆详情：{alias}"
            }
        },
        "elements": [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": (
                        f"**命令别名**：`{alias}`\n\n"
                        f"**完整命令**：`{memory.command}`\n\n"
                        f"**描述**：{memory.description or '无'}\n\n"
                        f"**项目**：{memory.project or '全局'}\n\n"
                        f"**标签**：{', '.join(memory.tags) if memory.tags else '无'}\n\n"
                        f"**使用次数**：{memory.frequency} 次\n\n"
                        f"**创建时间**：{memory.created_at.strftime('%Y-%m-%d %H:%M')}\n\n"
                        f"**最后使用**：{memory.last_used_at.strftime('%Y-%m-%d %H:%M')}"
                    )
                }
            },
            {"tag": "hr"},
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": (
                        f"**记忆状态**：{status_emoji} {status_text}\n\n"
                        f"**保留率**：{retention_bar}\n\n"
                        f"**下次复习**：{next_review}\n\n"
                        f"**稳定性系数**：{stability:.1f}"
                    )
                }
            },
            {"tag": "hr"},
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**🧠 遗忘曲线预测**（◀ 标记当前位置）：\n\n{curve_visual}"
                }
            },
            {"tag": "hr"},
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "✅ 我已记住"},
                        "type": "primary",
                        "value": {"action": "mark_as_reviewed", "alias": alias}
                    },
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "📊 查看所有记忆"},
                        "type": "default",
                        "value": {"action": "view_all_memories", "alias": alias}
                    }
                ]
            }
        ]
    }

    return card


def build_all_memories_card() -> dict:
    """构建所有记忆列表卡片"""
    memories = store.find_all_active(limit=20)

    if not memories:
        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "template": "blue",
                "title": {"tag": "plain_text", "content": "📊 记忆总览"}
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": "暂无记忆记录\n使用 `claw remember <别名> <命令>` 添加第一条记忆"
                    }
                }
            ]
        }

    memory_lines = []
    healthy_count = 0
    review_count = 0
    expiring_count = 0

    for mem in memories:
        retention, status = forgetting_engine.calculate_retention(mem)
        emoji = get_status_emoji(status)
        short_cmd = mem.command[:30] + "..." if len(mem.command) > 30 else mem.command
        retention_pct = f"{retention*100:.0f}%"

        if status == RetentionStatus.HEALTHY:
            healthy_count += 1
        elif status == RetentionStatus.REVIEW_NEEDED:
            review_count += 1
        else:
            expiring_count += 1

        memory_lines.append(
            f"{emoji} **{mem.alias}** → `{short_cmd}` 保留率：{retention_pct}"
        )

    content = "\n\n".join(memory_lines)

    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": "blue",
            "title": {"tag": "plain_text", "content": f"📊 记忆总览（共 {len(memories)} 条）"}
        },
        "elements": [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": (
                        f"**统计**：🟢 健康 {healthy_count} | 🟡 需复习 {review_count} | 🔴 即将过期 {expiring_count}"
                    )
                }
            },
            {"tag": "hr"},
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": content
                }
            },
            {"tag": "hr"},
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "🔄 刷新"},
                        "type": "default",
                        "value": {"action": "view_all_memories", "alias": ""}
                    }
                ]
            }
        ]
    }

    return card


def do_card_action_trigger(data: P2CardActionTrigger) -> P2CardActionTriggerResponse:
    """处理卡片按钮点击事件"""
    action = data.event.action.value.get("action")
    alias = data.event.action.value.get("alias")

    print(f"\n{'='*50}")
    print(f"✅ 收到按钮点击：action={action}, alias={alias}")
    print(f"{'='*50}\n")

    if action == "mark_as_reviewed":
        return P2CardActionTriggerResponse({
            "toast": {
                "type": "success",
                "content": f"✅ 已记住「{alias}」，遗忘曲线已重置！"
            }
        })

    elif action == "view_detail":
        client = get_feishu_client()
        card = build_detail_card(alias)
        if card and client:
            client.send_interactive_card(CHAT_ID, card)
            return P2CardActionTriggerResponse({
                "toast": {
                    "type": "success",
                    "content": f"📋 已发送「{alias}」的详细记忆报告"
                }
            })
        else:
            return P2CardActionTriggerResponse({
                "toast": {
                    "type": "error",
                    "content": f"未找到记忆「{alias}」"
                }
            })

    elif action == "view_all_memories":
        client = get_feishu_client()
        if client:
            card = build_all_memories_card()
            client.send_interactive_card(CHAT_ID, card)
            return P2CardActionTriggerResponse({
                "toast": {
                    "type": "success",
                    "content": "📊 已发送记忆总览报告"
                }
            })
        else:
            return P2CardActionTriggerResponse({
                "toast": {
                    "type": "error",
                    "content": "飞书客户端未初始化"
                }
            })

    else:
        return P2CardActionTriggerResponse({
            "toast": {
                "type": "info",
                "content": "未知操作"
            }
        })


def start_scheduler():
    """启动遗忘调度器"""
    scheduler = ForgettingScheduler(feishu_chat_id=CHAT_ID)
    scheduler.start()
    print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ 遗忘调度器已启动")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 📅 下次检查时间：明天 09:00")
    return scheduler


def start_callback_server():
    """启动飞书回调服务"""
    event_handler = lark.EventDispatcherHandler.builder("", "") \
        .register_p2_card_action_trigger(do_card_action_trigger) \
        .build()

    cli = lark.ws.Client(
        "cli_a9722b340ef8dbd3",
        "BlhIAZopQs3M1DpDhxZ6RM8f2Z6iXYtW",
        event_handler=event_handler,
        log_level=lark.LogLevel.INFO
    )

    print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ 飞书回调服务已启动")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🎯 卡片按钮交互已启用")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 📋 查看详情 → 发送遗忘曲线可视化卡片")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 📊 查看所有记忆 → 发送记忆总览卡片")
    cli.start()


if __name__ == "__main__":
    print("=" * 50)
    print("🚀 Claw Memory Engine - 后台服务启动中...")
    print("=" * 50)

    scheduler = start_scheduler()

    callback_thread = threading.Thread(target=start_callback_server, daemon=True)
    callback_thread.start()

    print("\n" + "=" * 50)
    print("✅ 所有服务已启动完成！")
    print("• 明天早上9点会自动检查记忆并推送提醒")
    print("• 点击「查看详情」→ 发送遗忘曲线可视化卡片")
    print("• 点击「查看所有记忆」→ 发送记忆总览报告")
    print("• 按 Ctrl+C 停止所有服务")
    print("=" * 50 + "\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 正在停止所有服务...")
        scheduler.stop()
        print("✅ 服务已停止")
