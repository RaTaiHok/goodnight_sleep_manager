"""插件配置 Schema 文案。

当前插件配置页会直接渲染 title/label/hint 字段，不支持把多语言对象作为 React
文本节点渲染。因此这里保留中英文本表，但写回 Schema 时只写入字符串，避免
WebUI 崩溃。
"""

from typing import Any

LocalizedText = dict[str, str]
DEFAULT_LOCALE = "zh_CN"

SECTION_TITLES: dict[str, LocalizedText] = {
    "plugin": {"zh_CN": "插件", "en_US": "Plugin"},
    "trigger": {"zh_CN": "触发", "en_US": "Trigger"},
    "sleep_request": {"zh_CN": "催睡", "en_US": "Sleep Request"},
    "schedule": {"zh_CN": "作息", "en_US": "Schedule"},
    "group_schedule": {"zh_CN": "分群作息", "en_US": "Group Schedule"},
    "control": {"zh_CN": "拦截", "en_US": "Control"},
    "sleep_review": {"zh_CN": "睡醒回顾", "en_US": "Sleep Review"},
}

SECTION_DESCRIPTIONS: dict[str, LocalizedText] = {
    "plugin": {"zh_CN": "插件基础配置", "en_US": "Basic plugin settings."},
    "trigger": {"zh_CN": "Bot 自己确认入睡时使用的语义判定规则", "en_US": "Semantic rules used when the bot confirms sleep by itself."},
    "sleep_request": {"zh_CN": "用户建议 Bot 睡觉时的处理方式", "en_US": "How to handle user messages suggesting the bot should sleep."},
    "schedule": {"zh_CN": "允许入睡和醒来的时间计算", "en_US": "Sleep window and wake-up time calculation."},
    "group_schedule": {
        "zh_CN": "按群号覆盖全局作息，命中时使用独立睡眠状态",
        "en_US": "Override the global schedule by group ID and use independent sleep state.",
    },
    "control": {"zh_CN": "睡眠期间暂停的主程序链路", "en_US": "Runtime chains paused while sleeping."},
    "sleep_review": {
        "zh_CN": "醒来后整理睡眠期间被拦截的聊天记录，不会自动回复历史消息",
        "en_US": "Summarize intercepted messages after waking up without replying to old messages.",
    },
}

FIELD_LABELS: dict[tuple[str, str], LocalizedText] = {
    ("plugin", "enabled"): {"zh_CN": "启用插件", "en_US": "Enable plugin"},
    ("plugin", "config_version"): {"zh_CN": "配置版本", "en_US": "Config version"},
    ("trigger", "ai_confirmation_enabled"): {"zh_CN": "AI 语义入睡判定", "en_US": "AI semantic sleep judge"},
    ("trigger", "max_trigger_chars"): {"zh_CN": "触发短句最大长度", "en_US": "Max trigger length"},
    ("trigger", "reject_at_component"): {"zh_CN": "排除 @ 消息", "en_US": "Reject @ messages"},
    ("trigger", "reject_reply_message"): {"zh_CN": "排除引用回复", "en_US": "Reject quoted replies"},
    ("sleep_request", "enabled"): {"zh_CN": "识别用户催睡", "en_US": "Detect sleep requests"},
    ("sleep_request", "require_mention_in_group"): {"zh_CN": "群聊要求提及 Bot", "en_US": "Require mention in groups"},
    ("sleep_request", "pending_confirm_seconds"): {"zh_CN": "待确认时长", "en_US": "Pending confirmation seconds"},
    ("sleep_request", "off_window_behavior"): {"zh_CN": "非入睡时间行为", "en_US": "Off-window behavior"},
    ("sleep_request", "off_window_reply"): {"zh_CN": "非入睡时间固定回复", "en_US": "Off-window fixed reply"},
    ("schedule", "sleep_window_start"): {"zh_CN": "允许入睡开始", "en_US": "Sleep window start"},
    ("schedule", "sleep_window_end"): {"zh_CN": "允许入睡结束", "en_US": "Sleep window end"},
    ("schedule", "target_wake_time"): {"zh_CN": "目标醒来时间", "en_US": "Target wake time"},
    ("schedule", "min_sleep_minutes"): {"zh_CN": "最短睡眠分钟", "en_US": "Minimum sleep minutes"},
    ("schedule", "max_sleep_minutes"): {"zh_CN": "最长睡眠分钟", "en_US": "Maximum sleep minutes"},
    ("schedule", "wake_jitter_minutes"): {"zh_CN": "醒来随机浮动", "en_US": "Wake jitter minutes"},
    ("group_schedule", "group_schedules"): {"zh_CN": "群作息覆盖", "en_US": "Group schedule overrides"},
    ("control", "block_inbound_messages"): {"zh_CN": "暂停入站消息", "en_US": "Block inbound messages"},
    ("control", "block_expression_learning"): {"zh_CN": "暂停表达学习", "en_US": "Block expression learning"},
    ("control", "block_memory_automation"): {"zh_CN": "暂停记忆写入", "en_US": "Block memory writeback"},
    ("control", "block_outbound_messages"): {"zh_CN": "暂停后续出站消息", "en_US": "Block outbound messages"},
    ("control", "planner_control_enabled"): {"zh_CN": "暂停 Planner 结果", "en_US": "Control planner results"},
    ("control", "control_commands_enabled"): {"zh_CN": "允许控制命令", "en_US": "Allow control commands"},
    ("control", "persist_sleep_state"): {"zh_CN": "持久化睡眠状态", "en_US": "Persist sleep state"},
    ("control", "force_sleep_commands_enabled"): {"zh_CN": "允许管理入睡命令", "en_US": "Allow sleep management commands"},
    ("control", "admin_user_ids"): {"zh_CN": "管理员用户 ID", "en_US": "Admin user IDs"},
    ("sleep_review", "enabled"): {"zh_CN": "启用睡醒回顾", "en_US": "Enable sleep review"},
    ("sleep_review", "max_summary_messages_per_chat"): {"zh_CN": "单聊最大消息数", "en_US": "Max messages per chat"},
    ("sleep_review", "max_summary_chars_per_chat"): {"zh_CN": "单聊最大字符数", "en_US": "Max characters per chat"},
    ("sleep_review", "max_review_chats_per_wake"): {"zh_CN": "单次最大聊天流", "en_US": "Max chats per wake"},
    ("sleep_review", "max_summary_tokens"): {"zh_CN": "单聊总结输出上限", "en_US": "Max summary tokens"},
}

ITEM_FIELD_LABELS: dict[tuple[str, str, str], LocalizedText] = {
    ("group_schedule", "group_schedules", "enabled"): {"zh_CN": "启用", "en_US": "Enabled"},
    ("group_schedule", "group_schedules", "group_id"): {"zh_CN": "群号", "en_US": "Group ID"},
    ("group_schedule", "group_schedules", "sleep_window_start"): {"zh_CN": "允许入睡开始", "en_US": "Sleep window start"},
    ("group_schedule", "group_schedules", "sleep_window_end"): {"zh_CN": "允许入睡结束", "en_US": "Sleep window end"},
    ("group_schedule", "group_schedules", "target_wake_time"): {"zh_CN": "目标醒来时间", "en_US": "Target wake time"},
    ("group_schedule", "group_schedules", "min_sleep_minutes"): {"zh_CN": "最短睡眠分钟", "en_US": "Minimum sleep minutes"},
    ("group_schedule", "group_schedules", "max_sleep_minutes"): {"zh_CN": "最长睡眠分钟", "en_US": "Maximum sleep minutes"},
    ("group_schedule", "group_schedules", "wake_jitter_minutes"): {"zh_CN": "醒来随机浮动", "en_US": "Wake jitter minutes"},
}

FIELD_HINTS: dict[tuple[str, str], LocalizedText] = {
    ("sleep_request", "off_window_reply"): {
        "zh_CN": "留空时会读取主程序人格和表达风格，用 replyer 模型生成一句回复",
        "en_US": "Leave empty to generate a reply from the main personality and reply style using the replyer model.",
    },
    ("sleep_request", "off_window_behavior"): {
        "zh_CN": "reply=回复并拦截，silent=静默拦截，pass=交给主链路处理",
        "en_US": "reply = reply and abort, silent = abort silently, pass = let the main chain handle it.",
    },
    ("trigger", "ai_confirmation_enabled"): {
        "zh_CN": "开启后，在允许入睡时间内，对已有合理催睡或 Bot 自己发出含睡眠意图的短句调用 replyer 模型，只接受 SLEEP/NOT_SLEEP/UNSURE",
        "en_US": "When enabled, during the sleep window, use the replyer model for pending sleep requests or sleep-related bot messages, accepting only SLEEP/NOT_SLEEP/UNSURE.",
    },
    ("group_schedule", "group_schedules"): {
        "zh_CN": "同一群号命中后使用这里的作息和睡眠时长，并拥有独立睡眠状态，不受全局睡眠影响",
        "en_US": "When a group ID matches, this schedule and duration override the global Schedule section and use an independent sleep state.",
    },
    ("control", "persist_sleep_state"): {
        "zh_CN": "开启后会把未过期的睡眠状态保存到 data/plugins/goodnight_sleep_manager/sleep_state.json",
        "en_US": "When enabled, active sleep state is saved to data/plugins/goodnight_sleep_manager/sleep_state.json.",
    },
    ("control", "block_memory_automation"): {
        "zh_CN": "开启后，睡眠期间不再让新触发的人物事实写回和聊天摘要写回进入队列；已经运行中的任务不会被取消",
        "en_US": "When enabled, new person fact and chat summary writeback jobs will not be queued while sleeping. Already running jobs are not cancelled.",
    },
    ("control", "force_sleep_commands_enabled"): {
        "zh_CN": "开启后允许使用 /sleep_now 引导入睡，或使用 /sleep_force 强制入睡",
        "en_US": "Enable /sleep_now and /sleep_force for testing or managing sleep state.",
    },
    ("control", "admin_user_ids"): {
        "zh_CN": "填写后只有这些用户 ID 可使用 /sleep_now 和 /sleep_force；留空则不限制",
        "en_US": "When set, only these user IDs can use /sleep_now and /sleep_force. Empty means unrestricted.",
    },
    ("sleep_review", "enabled"): {
        "zh_CN": "开启后，睡眠期间被拦截的消息会保存到本地；对应作用域醒来时按群聊/私聊生成回顾文件，不会向聊天流补发回复",
        "en_US": "When enabled, intercepted messages are saved locally and summarized by group/private chat when the matching sleep scope wakes. No replies are sent.",
    },
    ("sleep_review", "max_summary_messages_per_chat"): {
        "zh_CN": "启用睡醒回顾后生效。每个群聊/私聊只把最后这些条消息送入总结模型；完整轻量记录仍保存在回顾文件里",
        "en_US": "Effective when sleep review is enabled. Only the latest N messages per group/private chat are sent to the summary model; lightweight records remain in the report.",
    },
    ("sleep_review", "max_summary_chars_per_chat"): {
        "zh_CN": "启用睡醒回顾后生效。每个群聊/私聊送入总结模型的聊天文本字符上限，用于控制输入 token",
        "en_US": "Effective when sleep review is enabled. Maximum chat text characters sent to the summary model per group/private chat, used to control input tokens.",
    },
    ("sleep_review", "max_review_chats_per_wake"): {
        "zh_CN": "启用睡醒回顾后生效。一次醒来最多调用模型总结这些聊天流；超出的聊天流只保存记录和基础统计",
        "en_US": "Effective when sleep review is enabled. Maximum chats summarized with the model per wake; extra chats keep records and basic stats only.",
    },
    ("sleep_review", "max_summary_tokens"): {
        "zh_CN": "启用睡醒回顾后生效。每个聊天流总结的输出 token 上限，用于控制输出成本",
        "en_US": "Effective when sleep review is enabled. Maximum output tokens for each chat summary, used to control output cost.",
    },
}

HIDDEN_VISUAL_FIELDS: set[tuple[str, str]] = {
    ("plugin", "config_version"),
    ("trigger", "goodnight_patterns"),
    ("trigger", "pending_goodnight_patterns"),
    ("trigger", "directed_patterns"),
    ("trigger", "max_trigger_chars"),
    ("sleep_request", "request_patterns"),
}

SLEEP_REVIEW_LIMIT_FIELDS: set[str] = {
    "max_summary_messages_per_chat",
    "max_summary_chars_per_chat",
    "max_review_chats_per_wake",
    "max_summary_tokens",
}


def apply_config_schema_i18n(schema: dict[str, Any]) -> dict[str, Any]:
    """给插件 WebUI 配置 Schema 注入标题、标签和提示"""

    sections = schema.get("sections")
    if not isinstance(sections, dict):
        return schema

    for section_name, section in sections.items():
        if not isinstance(section, dict):
            continue
        if section_name in SECTION_TITLES:
            section["title"] = _resolve_text(SECTION_TITLES[section_name])
        if section_name in SECTION_DESCRIPTIONS:
            section["description"] = _resolve_text(SECTION_DESCRIPTIONS[section_name])

        fields = section.get("fields")
        if not isinstance(fields, dict):
            continue
        for field_name, field in fields.items():
            if not isinstance(field, dict):
                continue
            key = (str(section_name), str(field_name))
            if key in FIELD_LABELS:
                field["label"] = _resolve_text(FIELD_LABELS[key])
            if key in FIELD_HINTS:
                field["hint"] = _resolve_text(FIELD_HINTS[key])
            if key in HIDDEN_VISUAL_FIELDS:
                field["hidden"] = True
            if section_name == "sleep_review" and field_name in SLEEP_REVIEW_LIMIT_FIELDS:
                field["min"] = 1
                field["step"] = 1
            _apply_item_field_labels(str(section_name), str(field_name), field)
    return schema


def _apply_item_field_labels(section_name: str, field_name: str, field: dict[str, Any]) -> None:
    """给列表对象项的字段注入本地化标签。"""

    item_fields = field.get("item_fields")
    if not isinstance(item_fields, dict):
        return

    for item_field_name, item_field in item_fields.items():
        if not isinstance(item_field, dict):
            continue
        key = (section_name, field_name, str(item_field_name))
        if key in ITEM_FIELD_LABELS:
            item_field["label"] = _resolve_text(ITEM_FIELD_LABELS[key])


def _resolve_text(text: LocalizedText, locale: str = DEFAULT_LOCALE) -> str:
    """从本地化文本中取出当前 WebUI 可安全渲染的字符串。"""

    return text.get(locale) or text.get("zh_CN") or next(iter(text.values()), "")
