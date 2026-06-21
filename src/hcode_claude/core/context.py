"""消息上下文管理——维护 Anthropic API 格式的 messages 列表，提供 system prompt 四层拼接"""

from typing import Any


class ExecutionContext:
    """维护多轮对话的完整消息历史，Anthropic 原生 dict 格式"""

    # 初始化空消息列表
    def __init__(self) -> None:
        self._messages: list[dict[str, Any]] = []

    # 当前消息历史（只读）
    @property
    def messages(self) -> list[dict[str, Any]]:
        return self._messages

    # 构建四层 system prompt：base → 全局 context → 项目 context → session notes
    async def build_system_prompt(self, base: str) -> str:
        parts = [
            base,
            self._load_global_context(),
            self._load_project_context(),
            self._load_session_notes(),
        ]
        return "\n\n".join(p for p in parts if p)

    # 追加用户消息到消息历史
    def add_user_message(self, content: str) -> None:
        self._messages.append({"role": "user", "content": content})

    # 追加 assistant 消息——文本 + 工具调用块
    def add_assistant_message(self, content: str, tool_uses: list[dict[str, Any]]) -> None:
        blocks: list[dict[str, Any]] = []
        if content:
            blocks.append({"type": "text", "text": content})
        for tu in tool_uses:
            blocks.append({
                "type": "tool_use",
                "id": tu["id"],
                "name": tu["name"],
                "input": tu["input"],
            })
        self._messages.append({"role": "assistant", "content": blocks})

    # 追加工具结果——多个 tool_result 打包到同一条 user 消息
    def add_tool_results(self, results: list[dict[str, Any]]) -> None:
        blocks = [
            {"type": "tool_result", "tool_use_id": r["tool_use_id"],
             "content": r["content"], "is_error": r.get("is_error", False)}
            for r in results
        ]
        self._messages.append({"role": "user", "content": blocks})

    # 估算当前消息历史的 token 数（字符数 / 4）
    def estimated_tokens(self) -> int:
        import json
        raw = json.dumps(self._messages, ensure_ascii=False)
        return len(raw) // 4

    # 加载全局 context 文件（返回空字符串，S4 实现）
    @staticmethod
    def _load_global_context() -> str:
        return ""

    # 加载项目 context 文件（返回空字符串，S4 实现）
    @staticmethod
    def _load_project_context() -> str:
        return ""

    # 加载会话笔记（返回空字符串，S4 实现）
    @staticmethod
    def _load_session_notes() -> str:
        return ""
