"""睡眠触发与催睡消息匹配"""

from logging import Logger
from typing import Any

from .config_models import SleepRequestConfig, TriggerConfig
from .message_utils import (
    has_at_component,
    has_reply_component,
    is_group_message,
    message_mentions_bot,
    normalize_text,
)
from .pattern_utils import matches_any_pattern


def looks_like_self_goodnight(
    text: str,
    message: dict[str, Any],
    trigger_config: TriggerConfig,
    *,
    has_pending_request: bool,
    logger: Logger,
    set_reply: bool = False,
) -> bool:
    """判断出站文本是否像 Bot 自己准备睡觉，而不是向别人说晚安"""

    normalized_text = normalize_text(text)
    if not normalized_text:
        return False

    max_trigger_chars = trigger_config.max_trigger_chars
    if has_pending_request:
        max_trigger_chars = max(max_trigger_chars, 40)
    if len(normalized_text) > max_trigger_chars:
        return False
    if trigger_config.reject_at_component and has_at_component(message):
        return False
    if trigger_config.reject_reply_message and not has_pending_request and (set_reply or has_reply_component(message)):
        return False
    if has_pending_request and matches_any_pattern(normalized_text, trigger_config.pending_goodnight_patterns, logger):
        return True
    if matches_any_pattern(normalized_text, trigger_config.directed_patterns, logger):
        return False
    if matches_any_pattern(normalized_text, trigger_config.goodnight_patterns, logger):
        return True
    return False


def looks_like_sleep_request(
    text: str,
    message: dict[str, Any],
    sleep_request_config: SleepRequestConfig,
    *,
    logger: Logger,
) -> bool:
    """判断用户消息是否像是在让 Bot 睡觉"""

    normalized_text = normalize_text(text)
    if not normalized_text:
        return False
    if sleep_request_config.require_mention_in_group and is_group_message(message):
        if not message_mentions_bot(message):
            return False
    return matches_any_pattern(normalized_text, sleep_request_config.request_patterns, logger)
