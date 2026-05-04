"""
飞书 API 客户端
"""

import json
import hmac
import hashlib
import base64
import time
from typing import Optional, Dict, Any, List
from datetime import datetime

import requests

from src.config.config_manager import get_config
from src.logger.logger import get_logger


logger = get_logger(__name__)


class FeishuClient:
    """
    飞书开放平台 API 客户端

    支持功能：
    - 获取 tenant_access_token
    - 发送消息
    - 发送交互式卡片
    """

    def __init__(
        self,
        app_id: Optional[str] = None,
        app_secret: Optional[str] = None,
    ):
        """
        初始化飞书客户端

        Args:
            app_id: 飞书应用 App ID
            app_secret: 飞书应用 App Secret
        """
        self.app_id = app_id
        self.app_secret = app_secret
        self.base_url = "https://open.feishu.cn/open-apis"
        self._tenant_token: Optional[str] = None
        self._token_expire_at: int = 0

        # 如果未提供凭证，尝试从配置加载
        if not self.app_id or not self.app_secret:
            config = get_config()
            self.app_id = getattr(config, 'feishu_app_id', None)
            self.app_secret = getattr(config, 'feishu_app_secret', None)

    def _get_tenant_token(self) -> Optional[str]:
        """获取 tenant_access_token"""
        # 检查缓存
        if self._tenant_token and time.time() < self._token_expire_at:
            return self._tenant_token

        if not self.app_id or not self.app_secret:
            logger.warning("飞书应用凭证未配置")
            return None

        try:
            url = f"{self.base_url}/auth/v3/tenant_access_token/internal"
            payload = {
                "app_id": self.app_id,
                "app_secret": self.app_secret
            }

            response = requests.post(url, json=payload, timeout=10)
            result = response.json()

            if result.get("code") == 0:
                self._tenant_token = result["tenant_access_token"]
                # 提前 5 分钟过期
                self._token_expire_at = time.time() + result["expire"] - 300
                logger.info("获取飞书 tenant_access_token 成功")
                return self._tenant_token
            else:
                logger.error(f"获取 tenant_access_token 失败：{result}")
                return None

        except Exception as e:
            logger.error(f"获取 tenant_access_token 异常：{e}")
            return None

    def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        token = self._get_tenant_token()
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}" if token else ""
        }

    def send_text_message(
        self,
        chat_id: str,
        text: str,
        receive_id_type: str = "chat_id"
    ) -> bool:
        """
        发送文本消息

        Args:
            chat_id: 群聊 ID
            text: 消息文本
            receive_id_type: 接收者类型 (user_id/chat_id/open_id)

        Returns:
            发送是否成功
        """
        url = f"{self.base_url}/im/v1/messages"
        headers = self._get_headers()

        if not headers.get("Authorization"):
            logger.error("飞书客户端未认证")
            return False

        params = {"receive_id_type": receive_id_type}
        payload = {
            "receive_id": chat_id,
            "msg_type": "text",
            "content": json.dumps({"text": text})
        }

        try:
            response = requests.post(
                url,
                headers=headers,
                params=params,
                json=payload,
                timeout=10
            )
            result = response.json()

            if result.get("code") == 0:
                logger.info(f"飞书消息发送成功：{chat_id}")
                return True
            else:
                logger.error(f"飞书消息发送失败：{result}")
                return False

        except Exception as e:
            logger.error(f"飞书消息发送异常：{e}")
            return False

    def send_interactive_card(
        self,
        chat_id: str,
        card_content: Dict[str, Any],
        receive_id_type: str = "chat_id"
    ) -> bool:
        """
        发送交互式卡片消息

        Args:
            chat_id: 群聊 ID
            card_content: 卡片内容 JSON
            receive_id_type: 接收者类型

        Returns:
            发送是否成功
        """
        url = f"{self.base_url}/im/v1/messages"
        headers = self._get_headers()

        if not headers.get("Authorization"):
            logger.error("飞书客户端未认证")
            return False

        params = {"receive_id_type": receive_id_type}
        payload = {
            "receive_id": chat_id,
            "msg_type": "interactive",
            "content": json.dumps(card_content)
        }

        try:
            response = requests.post(
                url,
                headers=headers,
                params=params,
                json=payload,
                timeout=10
            )
            result = response.json()

            if result.get("code") == 0:
                logger.info(f"飞书卡片消息发送成功：{chat_id}")
                return True
            else:
                logger.error(f"飞书卡片消息发送失败：{result}")
                return False

        except Exception as e:
            logger.error(f"飞书卡片消息发送异常：{e}")
            return False

    def send_memory_card(
        self,
        chat_id: str,
        memory_alias: str,
        memory_command: str,
        memory_type: str = "提醒",
        action_text: str = "我已记住"
    ) -> bool:
        """
        发送记忆提醒卡片

        Args:
            chat_id: 群聊 ID
            memory_alias: 记忆别名
            memory_command: 记忆命令
            memory_type: 记忆类型 (提醒/复习/警告)
            action_text: 操作按钮文本

        Returns:
            发送是否成功
        """
        # 根据类型设置颜色
        color_map = {
            "提醒": "blue",
            "复习": "orange",
            "警告": "red",
            "成功": "green",
        }
        color = color_map.get(memory_type, "blue")

        card_content = {
            "config": {
                "wide_screen_mode": True
            },
            "header": {
                "template": color,
                "title": {
                    "tag": "plain_text",
                    "content": f"🧠 记忆{memory_type}: {memory_alias}"
                }
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**命令别名**: {memory_alias}\n\n**完整命令**: `{memory_command}`"
                    }
                },
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {
                                "tag": "plain_text",
                                "content": action_text
                            },
                            "type": "primary",
                            "value": {
                                "action": "mark_as_reviewed",
                                "alias": memory_alias
                            }
                        },
                        {
                            "tag": "button",
                            "text": {
                                "tag": "plain_text",
                                "content": "查看详情"
                            },
                            "type": "default",
                            "value": {
                                "action": "view_detail",
                                "alias": memory_alias
                            }
                        }
                    ]
                }
            ]
        }

        return self.send_interactive_card(chat_id, card_content)

    def get_user_info(self, user_id: str, id_type: str = "user_id") -> Optional[Dict]:
        """
        获取用户信息

        Args:
            user_id: 用户 ID
            id_type: ID 类型 (user_id/open_id/union_id)

        Returns:
            用户信息
        """
        url = f"{self.base_url}/contact/v1/users/{user_id}"
        headers = self._get_headers()
        params = {"user_id_type": id_type}

        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            result = response.json()

            if result.get("code") == 0:
                return result.get("data")
            else:
                logger.error(f"获取用户信息失败：{result}")
                return None

        except Exception as e:
            logger.error(f"获取用户信息异常：{e}")
            return None

    def test_connection(self) -> bool:
        """测试连接"""
        token = self._get_tenant_token()
        if token:
            logger.info("飞书客户端连接测试成功")
            return True
        else:
            logger.warning("飞书客户端连接测试失败")
            return False


# 全局单例
_feishu_client: Optional[FeishuClient] = None


def get_feishu_client() -> Optional[FeishuClient]:
    """获取飞书客户端单例"""
    global _feishu_client
    if _feishu_client is None:
        _feishu_client = FeishuClient()
    return _feishu_client


def send_memory_notification(
    chat_id: str,
    alias: str,
    command: str,
    memory_type: str = "提醒"
) -> bool:
    """快捷函数：发送记忆通知"""
    client = get_feishu_client()
    if client:
        return client.send_memory_card(chat_id, alias, command, memory_type)
    return False
