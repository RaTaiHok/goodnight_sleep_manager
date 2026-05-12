"""插件 Hook 消息载荷处理工具"""

from typing import Any, List

import re


def normalize_text(text: str) -> str:
    """清理文本中的空白与不可见字符"""

    normalized = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", text)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def extract_text(message: dict[str, Any], processed_plain_text: str = "") -> str:
    """从 Hook 消息载荷中提取文本"""

    if processed_plain_text.strip():
        return processed_plain_text.strip()

    raw_processed = message.get("processed_plain_text")
    if isinstance(raw_processed, str) and raw_processed.strip():
        return raw_processed.strip()

    raw_parts = message.get("raw_message", [])
    if not isinstance(raw_parts, list):
        return ""

    texts: List[str] = []
    for part in raw_parts:
        if not isinstance(part, dict):
            continue
        if part.get("type") != "text":
            continue
        data = part.get("data")
        if isinstance(data, str):
            texts.append(data)
    return "".join(texts).strip()


def has_at_component(message: dict[str, Any]) -> bool:
    """判断消息中是否存在 @ 组件"""

    raw_parts = message.get("raw_message", [])
    if not isinstance(raw_parts, list):
        return False
    return any(isinstance(part, dict) and part.get("type") == "at" for part in raw_parts)


def has_reply_component(message: dict[str, Any]) -> bool:
    """判断消息中是否存在引用回复组件"""

    if message.get("reply_to"):
        return True

    raw_parts = message.get("raw_message", [])
    if not isinstance(raw_parts, list):
        return False
    return any(isinstance(part, dict) and part.get("type") == "reply" for part in raw_parts)


def is_group_message(message: dict[str, Any]) -> bool:
    """判断消息是否来自群聊"""

    message_info = message.get("message_info")
    if not isinstance(message_info, dict):
        return False
    return isinstance(message_info.get("group_info"), dict)


def message_group_id(message: dict[str, Any]) -> str:
    """提取消息所属群号；私聊或载荷缺失时返回空字符串"""

    message_info = message.get("message_info")
    if not isinstance(message_info, dict):
        return ""

    group_info = message_info.get("group_info")
    if not isinstance(group_info, dict):
        return ""

    group_id = group_info.get("group_id")
    return group_id.strip() if isinstance(group_id, str) else ""


def message_mentions_bot(message: dict[str, Any]) -> bool:
    """判断消息是否显式提及 Bot"""

    if bool(message.get("is_mentioned")) or bool(message.get("is_at")):
        return True
    return has_at_component(message)


def message_id(message: dict[str, Any]) -> str:
    """提取消息 ID"""

    raw_message_id = message.get("message_id")
    return raw_message_id if isinstance(raw_message_id, str) else ""


def message_session_id(message: dict[str, Any]) -> str:
    """提取会话 ID"""

    session_id = message.get("session_id")
    return session_id if isinstance(session_id, str) else ""


def abort_result(reason: str) -> dict[str, Any]:
    """构造 Hook abort 返回值"""

    return {
        "action": "abort",
        "custom_result": {
            "reason": reason,
        },
    }
