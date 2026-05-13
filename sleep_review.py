"""睡眠期间消息记录与醒来回顾生成。"""

from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import json
import re

from .message_utils import extract_text, message_group_id, message_session_id
from .state import SleepRecord

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REVIEW_ROOT = PROJECT_ROOT / "data" / "plugins" / "goodnight_sleep_manager" / "sleep_review"
MESSAGE_DIR = REVIEW_ROOT / "messages"
REPORT_DIR = REVIEW_ROOT / "reports"

MAX_TEXT_CHARS = 240


@dataclass
class SleepReviewMessage:
    """睡眠期间被拦截消息的轻量记录。"""

    scope_key: str
    scope_label: str
    session_id: str
    message_id: str
    timestamp: str
    platform: str
    group_id: str
    group_name: str
    user_id: str
    user_name: str
    user_cardname: str
    text: str


def append_sleep_review_message(message: dict[str, Any], sleep_record: SleepRecord, logger: Any) -> None:
    """把睡眠期间被拦截的消息追加到本地 JSONL"""

    review_message = _build_review_message(message, sleep_record)
    if review_message is None:
        return

    try:
        MESSAGE_DIR.mkdir(parents=True, exist_ok=True)
        record_path = _message_file_path(sleep_record.scope_key)
        with record_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(asdict(review_message), ensure_ascii=False) + "\n")
    except Exception as exc:
        logger.warning(f"记录睡眠期间消息失败: scope={sleep_record.scope_key} error={exc}")


async def generate_sleep_review(ctx: Any, sleep_record: SleepRecord, config: Any, logger: Any) -> Path | None:
    """醒来后按聊天流生成睡眠期间回顾文件，不向任何聊天发送消息"""

    if sleep_record.sleep_until is None:
        return None

    messages = _load_sleep_messages(sleep_record)
    if not messages:
        return None

    grouped_messages = _group_messages_by_chat(messages)
    max_review_chats = _positive_int(getattr(config, "max_review_chats_per_wake", 10), 10)
    sorted_groups = sorted(grouped_messages.items(), key=lambda item: len(item[1]), reverse=True)
    selected_groups = sorted_groups[:max_review_chats]
    skipped_groups = sorted_groups[max_review_chats:]

    chat_summaries: List[dict[str, Any]] = []
    for chat_key, chat_messages in selected_groups:
        chat_summaries.append(
            {
                "chat_key": chat_key,
                "chat_label": _chat_label(chat_messages),
                "message_count": len(chat_messages),
                "participants": _participants(chat_messages),
                "summary": await _summarize_chat(ctx, sleep_record, chat_messages, config, logger),
                "messages": [asdict(item) for item in chat_messages],
            }
        )

    report_payload: dict[str, Any] = {
        "version": 1,
        "scope_key": sleep_record.scope_key,
        "scope_label": sleep_record.scope_label,
        "group_id": sleep_record.group_id,
        "session_id": sleep_record.session_id,
        "sleep_started_at": _format_datetime(sleep_record.sleep_started_at),
        "sleep_until": _format_datetime(sleep_record.sleep_until),
        "sleep_reason": sleep_record.sleep_reason,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "limits": {
            "max_summary_messages_per_chat": _positive_int(getattr(config, "max_summary_messages_per_chat", 80), 80),
            "max_summary_chars_per_chat": _positive_int(getattr(config, "max_summary_chars_per_chat", 6000), 6000),
            "max_review_chats_per_wake": max_review_chats,
            "max_summary_tokens": _positive_int(getattr(config, "max_summary_tokens", 500), 500),
        },
        "skipped_chat_summaries": [
            {
                "chat_key": chat_key,
                "chat_label": _chat_label(chat_messages),
                "message_count": len(chat_messages),
                "participants": _participants(chat_messages),
                "reason": "超过本次醒来最大总结聊天流数量，已保留轻量记录但未调用模型总结",
                "messages": [asdict(item) for item in chat_messages],
            }
            for chat_key, chat_messages in skipped_groups
        ],
        "chat_summaries": chat_summaries,
    }

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{_safe_filename(sleep_record.scope_key)}.json"
    report_path.write_text(json.dumps(report_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _remove_reviewed_messages(sleep_record, messages)
    logger.info(f"睡醒回顾已生成: {report_path}")
    return report_path


def _build_review_message(message: dict[str, Any], sleep_record: SleepRecord) -> SleepReviewMessage | None:
    text = _extract_review_text(message)
    if not text:
        return None

    message_info = message.get("message_info")
    if not isinstance(message_info, dict):
        message_info = {}
    user_info = message_info.get("user_info")
    if not isinstance(user_info, dict):
        user_info = {}
    group_info = message_info.get("group_info")
    if not isinstance(group_info, dict):
        group_info = {}

    return SleepReviewMessage(
        scope_key=sleep_record.scope_key,
        scope_label=sleep_record.scope_label,
        session_id=message_session_id(message),
        message_id=str(message.get("message_id") or "").strip(),
        timestamp=_normalize_timestamp(message.get("timestamp")),
        platform=str(message.get("platform") or "").strip(),
        group_id=message_group_id(message),
        group_name=str(group_info.get("group_name") or "").strip(),
        user_id=str(user_info.get("user_id") or "").strip(),
        user_name=str(user_info.get("user_nickname") or "").strip(),
        user_cardname=str(user_info.get("user_cardname") or "").strip(),
        text=text[:MAX_TEXT_CHARS],
    )


def _extract_review_text(message: dict[str, Any]) -> str:
    text = extract_text(message)
    if text:
        return text

    raw_parts = message.get("raw_message")
    if not isinstance(raw_parts, list):
        return ""

    labels: List[str] = []
    for part in raw_parts:
        if not isinstance(part, dict):
            continue
        part_type = str(part.get("type") or "").strip()
        if part_type == "image":
            labels.append("[图片]")
        elif part_type == "emoji":
            labels.append("[表情包]")
        elif part_type == "voice":
            labels.append("[语音]")
        elif part_type == "forward":
            labels.append("[转发消息]")
    return " ".join(labels).strip()


def _normalize_timestamp(raw_timestamp: Any) -> str:
    if isinstance(raw_timestamp, str) and raw_timestamp.strip():
        timestamp_text = raw_timestamp.strip()
        try:
            return datetime.fromtimestamp(float(timestamp_text)).isoformat(timespec="seconds")
        except Exception:
            return timestamp_text
    if isinstance(raw_timestamp, (int, float)):
        return datetime.fromtimestamp(float(raw_timestamp)).isoformat(timespec="seconds")
    return datetime.now().isoformat(timespec="seconds")


def _load_sleep_messages(sleep_record: SleepRecord) -> List[SleepReviewMessage]:
    record_path = _message_file_path(sleep_record.scope_key)
    if not record_path.exists():
        return []

    loaded_messages: List[SleepReviewMessage] = []
    for line in record_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        review_message = _message_from_payload(payload)
        if review_message is None or not _message_in_sleep_range(review_message, sleep_record):
            continue
        loaded_messages.append(review_message)
    return loaded_messages


def _message_from_payload(payload: dict[str, Any]) -> SleepReviewMessage | None:
    try:
        return SleepReviewMessage(
            scope_key=str(payload.get("scope_key") or "").strip(),
            scope_label=str(payload.get("scope_label") or "").strip(),
            session_id=str(payload.get("session_id") or "").strip(),
            message_id=str(payload.get("message_id") or "").strip(),
            timestamp=str(payload.get("timestamp") or "").strip(),
            platform=str(payload.get("platform") or "").strip(),
            group_id=str(payload.get("group_id") or "").strip(),
            group_name=str(payload.get("group_name") or "").strip(),
            user_id=str(payload.get("user_id") or "").strip(),
            user_name=str(payload.get("user_name") or "").strip(),
            user_cardname=str(payload.get("user_cardname") or "").strip(),
            text=str(payload.get("text") or "").strip(),
        )
    except Exception:
        return None


def _message_in_sleep_range(message: SleepReviewMessage, sleep_record: SleepRecord) -> bool:
    message_time = _parse_datetime(message.timestamp)
    if message_time is None:
        return True
    if sleep_record.sleep_started_at is not None and message_time < sleep_record.sleep_started_at:
        return False
    if sleep_record.sleep_until is not None and message_time > sleep_record.sleep_until:
        return False
    return True


def _group_messages_by_chat(messages: List[SleepReviewMessage]) -> Dict[str, List[SleepReviewMessage]]:
    grouped_messages: Dict[str, List[SleepReviewMessage]] = {}
    for message in messages:
        if message.group_id:
            chat_key = f"group:{message.group_id}"
        elif message.user_id:
            chat_key = f"private:{message.user_id}"
        else:
            chat_key = message.session_id or "unknown"
        grouped_messages.setdefault(chat_key, []).append(message)
    return grouped_messages


async def _summarize_chat(
    ctx: Any,
    sleep_record: SleepRecord,
    messages: List[SleepReviewMessage],
    config: Any,
    logger: Any,
) -> str:
    max_messages = _positive_int(getattr(config, "max_summary_messages_per_chat", 80), 80)
    max_chars = _positive_int(getattr(config, "max_summary_chars_per_chat", 6000), 6000)
    max_tokens = _positive_int(getattr(config, "max_summary_tokens", 500), 500)
    prompt_messages = _prompt_messages(messages, max_messages=max_messages, max_chars=max_chars)
    participants = _participants(messages)
    prompt = [
        {
            "role": "system",
            "content": (
                "你是睡醒后翻聊天记录的记录员。只做记录和总结，不要替 Bot 回复任何历史消息，"
                "不要写成发给群里的话，不要提出已经错过的即时回应。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"睡眠作用域：{sleep_record.scope_label}\n"
                f"睡眠时间：{_format_datetime(sleep_record.sleep_started_at)} 至 {_format_datetime(sleep_record.sleep_until)}\n"
                f"聊天流：{_chat_label(messages)}\n"
                f"参与者：{json.dumps(participants, ensure_ascii=False)}\n"
                f"聊天记录：\n{prompt_messages}\n\n"
                "请用简体中文生成一份简短回顾，包含：\n"
                "1. 这段时间大家主要聊了什么。\n"
                "2. 重要事实、约定、问题或需要醒来后知道的上下文。\n"
                "3. 涉及的人物请保留昵称和 QQ 号。\n"
                "不要补写任何回复。"
            ),
        },
    ]

    try:
        result = await ctx.llm.generate(prompt, model="utils", temperature=0.2, max_tokens=max_tokens)
    except Exception as exc:
        logger.warning(f"生成睡醒回顾失败，使用摘要: chat={_chat_label(messages)} error={exc}")
        return _fallback_summary(messages)

    if not isinstance(result, dict) or not result.get("success", False):
        return _fallback_summary(messages)
    summary = str(result.get("response") or "").strip()
    return summary or _fallback_summary(messages)


def _prompt_messages(messages: List[SleepReviewMessage], *, max_messages: int, max_chars: int) -> str:
    selected_messages = messages[-max_messages:]
    lines: List[str] = []
    total_chars = 0
    for message in selected_messages:
        display_name = message.user_cardname or message.user_name or message.user_id or "未知用户"
        line = f"[{message.timestamp}] {display_name}({message.user_id or 'unknown'}): {message.text}"
        total_chars += len(line)
        if total_chars > max_chars:
            break
        lines.append(line)
    return "\n".join(lines)


def _participants(messages: List[SleepReviewMessage]) -> List[dict[str, Any]]:
    participants: Dict[str, dict[str, Any]] = {}
    for message in messages:
        user_key = message.user_id or message.user_name or "unknown"
        item = participants.setdefault(
            user_key,
            {
                "user_id": message.user_id,
                "user_name": message.user_name,
                "user_cardname": message.user_cardname,
                "message_count": 0,
            },
        )
        item["message_count"] += 1
    return list(participants.values())


def _chat_label(messages: List[SleepReviewMessage]) -> str:
    first_message = messages[0]
    if first_message.group_id:
        group_name = first_message.group_name or "群聊"
        return f"{group_name}({first_message.group_id})"
    user_name = first_message.user_cardname or first_message.user_name or first_message.user_id
    return f"{user_name}的私聊"


def _fallback_summary(messages: List[SleepReviewMessage]) -> str:
    participants = _participants(messages)
    names = [
        item.get("user_cardname") or item.get("user_name") or item.get("user_id") or "未知用户"
        for item in participants[:8]
    ]
    return (
        f"睡眠期间共有 {len(messages)} 条消息，参与者：{', '.join(names) or '无'}。"
        "模型摘要生成失败，已保存原始轻量聊天记录，可查看 messages 字段。"
    )


def _remove_reviewed_messages(sleep_record: SleepRecord, reviewed_messages: List[SleepReviewMessage]) -> None:
    record_path = _message_file_path(sleep_record.scope_key)
    if not record_path.exists():
        return

    if not reviewed_messages:
        return

    remaining_payloads: List[dict[str, Any]] = []
    for message in _load_all_messages(record_path):
        if _message_in_sleep_range(message, sleep_record):
            continue
        remaining_payloads.append(asdict(message))

    if not remaining_payloads:
        record_path.unlink(missing_ok=True)
        return
    record_path.write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in remaining_payloads) + "\n",
        encoding="utf-8",
    )


def _load_all_messages(record_path: Path) -> List[SleepReviewMessage]:
    messages: List[SleepReviewMessage] = []
    for line in record_path.read_text(encoding="utf-8").splitlines():
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if isinstance(payload, dict) and (message := _message_from_payload(payload)) is not None:
            messages.append(message)
    return messages


def _parse_datetime(value: str) -> datetime | None:
    if not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.strip())
    except Exception:
        return None


def _format_datetime(value: datetime | None) -> str:
    return value.isoformat(timespec="seconds") if value is not None else ""


def _message_file_path(scope_key: str) -> Path:
    return MESSAGE_DIR / f"{_safe_filename(scope_key)}.jsonl"


def _safe_filename(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "").strip())
    return normalized[:80] or "global"


def _positive_int(value: Any, default: int) -> int:
    try:
        number = int(value)
    except Exception:
        return max(1, default)
    return max(1, number)
