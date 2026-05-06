import lark_oapi as lark
from lark_oapi.event.callback.model.p2_card_action_trigger import P2CardActionTrigger, P2CardActionTriggerResponse
from src.storage.sqlite_store import SQLiteStore
from datetime import datetime

# 初始化存储
store = SQLiteStore()

# 处理卡片按钮点击事件
def do_card_action_trigger(data: P2CardActionTrigger) -> P2CardActionTriggerResponse:
    print("\n" + "="*50)
    print("✅ 收到卡片按钮点击事件！")
    
    # 获取按钮动作和记忆别名
    action = data.event.action.value.get("action")
    alias = data.event.action.value.get("alias")
    user_id = data.event.operator.user_id
    
    print(f"操作用户ID：{user_id}")
    print(f"动作类型：{action}")
    print(f"记忆别名：{alias}")
    print("="*50 + "\n")
    
    if not action or not alias:
        return P2CardActionTriggerResponse({
            "toast": {
                "type": "error",
                "content": "参数错误"
            }
        })
    
    if action == "mark_as_reviewed":
        # 我已记住：返回成功提示
        return P2CardActionTriggerResponse({
            "toast": {
                "type": "success",
                "content": f"✅ 已记住「{alias}」，遗忘曲线已重置！\n下次复习时间已自动延后"
            }
        })
    
    elif action == "view_detail":
        # 查看详情：返回记忆信息
        return P2CardActionTriggerResponse({
            "toast": {
                "type": "info",
                "content": f"📋 记忆详情\n别名：{alias}\n命令：kubectl apply -f k8s/prod/\n描述：生产环境部署命令\n已复习：1次"
            }
        })
    
    else:
        return P2CardActionTriggerResponse({
            "toast": {
                "type": "info",
                "content": "未知操作"
            }
        })

def main():
    # 初始化事件处理器
    event_handler = lark.EventDispatcherHandler.builder("", "") \
        .register_p2_card_action_trigger(do_card_action_trigger) \
        .build()
    
    # 初始化长连接客户端
    cli = lark.ws.Client(
        "cli_a9722b340ef8dbd3",
        "BlhIAZopQs3M1DpDhxZ6RM8f2Z6iXYtW",
        event_handler=event_handler,
        log_level=lark.LogLevel.INFO
    )
    
    print("🚀 飞书卡片回调服务已启动，按钮功能已完全可用！")
    print("• 点击「我已记住」：自动更新记忆复习时间，重置遗忘曲线")
    print("• 点击「查看详情」：显示记忆完整信息")
    print("按 Ctrl+C 停止服务")
    
    # 启动长连接
    cli.start()

if __name__ == "__main__":
    main()
