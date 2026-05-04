"""
飞书集成测试
"""

import pytest
from unittest.mock import patch, MagicMock

from src.integrations.feishu import FeishuClient


class TestFeishuClient:
    """飞书客户端测试"""

    def test_init_without_credentials(self):
        """测试无凭证初始化"""
        client = FeishuClient()

        assert client.app_id is None
        assert client.app_secret is None

    def test_init_with_credentials(self):
        """测试带凭证初始化"""
        client = FeishuClient(app_id="test_id", app_secret="test_secret")

        assert client.app_id == "test_id"
        assert client.app_secret == "test_secret"

    @patch('src.integrations.feishu.requests.post')
    def test_get_tenant_token_mock(self, mock_post):
        """测试获取 tenant_token（模拟）"""
        # 模拟响应
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "code": 0,
            "tenant_access_token": "test_token",
            "expire": 7200
        }
        mock_post.return_value = mock_response

        client = FeishuClient(app_id="test", app_secret="test")
        token = client._get_tenant_token()

        assert token == "test_token"

    def test_send_text_message_without_auth(self):
        """测试未认证时发送消息"""
        client = FeishuClient()

        result = client.send_text_message("chat_id", "test")

        assert result is False

    def test_send_memory_card_structure(self):
        """测试记忆卡片内容结构"""
        client = FeishuClient()

        # 生成卡片内容
        card = client.send_memory_card.__doc__

        # 验证方法存在
        assert hasattr(client, 'send_memory_card')


class TestFeishuFunctions:
    """飞书快捷函数测试"""

    def test_get_feishu_client_singleton(self):
        """测试单例模式"""
        from src.integrations.feishu import get_feishu_client

        client1 = get_feishu_client()
        client2 = get_feishu_client()

        # 由于是无凭证初始化，client 可能为 None 或相同实例
        assert client1 is client2
