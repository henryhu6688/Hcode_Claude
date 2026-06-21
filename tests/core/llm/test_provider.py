"""LLM Provider 测试"""

from hcode_claude.core.llm.provider import AnthropicProvider, BaseProvider


# 功能：验证 AnthropicProvider 是 BaseProvider 的子类
# 设计：确保接口一致性，AgentLoop 可以依赖 BaseProvider 做类型提示
def test_anthropic_provider_is_base_provider():
    provider = AnthropicProvider(api_key="test-key")
    assert isinstance(provider, BaseProvider)


# 功能：验证 AnthropicProvider 有 chat 方法
# 设计：chat 是 BaseProvider 定义的抽象方法，必须实现
def test_anthropic_provider_has_chat():
    provider = AnthropicProvider(api_key="test-key")
    assert hasattr(provider, "chat")
    assert callable(provider.chat)
