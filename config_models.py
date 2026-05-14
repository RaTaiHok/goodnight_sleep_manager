"""晚安睡眠管理插件配置模型"""

from typing import List

from maibot_sdk import Field, PluginConfigBase

from .defaults import (
    default_directed_patterns,
    default_goodnight_patterns,
    default_pending_goodnight_patterns,
    default_sleep_request_patterns,
)


class PluginSectionConfig(PluginConfigBase):
    """插件基础配置"""

    __ui_label__ = "插件"
    __ui_icon__ = "moon"
    __ui_order__ = 0

    enabled: bool = Field(default=True, description="是否启用晚安睡眠管理")
    config_version: str = Field(default="1.8.0", description="配置版本")


class TriggerConfig(PluginConfigBase):
    """晚安触发配置"""

    __ui_label__ = "触发"
    __ui_icon__ = "message-circle"
    __ui_order__ = 1

    goodnight_patterns: List[str] = Field(
        default_factory=default_goodnight_patterns,
        description="Bot 出站消息命中这些规则时，可以进入睡眠",
    )
    ai_confirmation_enabled: bool = Field(default=True, description="使用 AI 判断 Bot 是否确认自己要睡")
    ai_confirmation_timeout_seconds: int = Field(
        default=0,
        description="AI 入睡确认判定的超时时间，单位秒；0 表示插件内部不主动超时",
    )
    ai_confirmation_max_tokens: int = Field(default=64, description="AI 入睡确认判定的最大输出 token 数")
    pending_goodnight_patterns: List[str] = Field(
        default_factory=default_pending_goodnight_patterns,
        description="有人在合适时间催睡后，Bot 出站消息命中这些规则也会进入睡眠",
    )
    directed_patterns: List[str] = Field(
        default_factory=default_directed_patterns,
        description="命中这些规则时视为对别人说晚安，不会进入睡眠",
    )
    max_trigger_chars: int = Field(default=18, description="触发短句的最大长度，过长文本不会触发")
    reject_at_component: bool = Field(default=True, description="出站消息包含 @ 组件时不触发睡眠")
    reject_reply_message: bool = Field(default=True, description="出站消息是引用回复时不触发睡眠")


class SleepRequestConfig(PluginConfigBase):
    """用户催睡配置"""

    __ui_label__ = "催睡"
    __ui_icon__ = "bell"
    __ui_order__ = 2

    enabled: bool = Field(default=True, description="是否识别用户让 Bot 睡觉的消息")
    request_patterns: List[str] = Field(
        default_factory=default_sleep_request_patterns,
        description="用户消息命中这些规则时，视为在建议 Bot 睡觉",
    )
    require_mention_in_group: bool = Field(default=True, description="群聊里需要 @ 或提及 Bot 才识别模糊催睡")
    pending_confirm_seconds: int = Field(default=600, description="合适时间催睡后，等待 Bot 自己说晚安的确认时长")
    off_window_behavior: str = Field(default="reply", description="不合适时间被催睡时的行为：reply/silent/pass")
    off_window_reply: str = Field(default="", description="不合适时间催睡时的固定回复；留空时按人格和表达风格生成")


class ScheduleConfig(PluginConfigBase):
    """睡眠时间配置。"""

    __ui_label__ = "作息"
    __ui_icon__ = "clock"
    __ui_order__ = 3

    sleep_window_start: str = Field(default="22:30", description="允许入睡的开始时间，HH:MM")
    sleep_window_end: str = Field(default="07:00", description="允许入睡的结束时间，HH:MM，可跨午夜")
    target_wake_time: str = Field(default="07:30", description="倾向醒来的时间，HH:MM")
    min_sleep_minutes: int = Field(default=45, description="最短睡眠分钟数")
    max_sleep_minutes: int = Field(default=480, description="最长睡眠分钟数")
    wake_jitter_minutes: int = Field(default=35, description="醒来时间随机浮动分钟数")


class IdleSleepConfig(PluginConfigBase):
    """长时间安静后的自动入睡配置"""

    __ui_label__ = "静默入睡"
    __ui_icon__ = "timer"
    __ui_order__ = 4

    enabled: bool = Field(default=False, description="允许在入睡时间内长时间安静后自动进入睡眠")
    silence_minutes: int = Field(default=15, description="入睡时间内完全没有入站和出站消息多少分钟后自动入睡")
    idle_minutes: int = Field(default=15, description="入睡时间内 Bot 连续多少分钟没有参与后自动入睡")
    check_interval_seconds: int = Field(default=60, description="后台检查安静状态的间隔秒数")
    topic_grace_seconds: int = Field(default=90, description="临近无参与入睡时，新话题进入 Planner 判断的缓冲秒数")
    mention_extends_grace: bool = Field(default=True, description="被提及时延长临睡前判断缓冲")
    at_extends_grace: bool = Field(default=True, description="被 @ 时延长临睡前判断缓冲")
    wake_on_mention_while_sleeping: bool = Field(default=False, description="睡眠期间被提及或 @ 时是否自动唤醒")
    inbound_grace_seconds: int = Field(default=180, description="兼容旧配置；请改用 topic_grace_seconds")
    count_inbound_messages_as_activity: bool = Field(
        default=False,
        description="兼容旧配置；入站消息始终只用于完全安静计时，不再影响无参与计时",
    )
    count_planner_actions_as_activity: bool = Field(
        default=True,
        description="是否把 Planner 的有效动作视为 Bot 参与；no_action/finish/wait/continue 不会刷新无参与计时",
    )


class GroupScheduleEntryConfig(PluginConfigBase):
    """单个群聊的睡眠时间覆盖配置。"""

    enabled: bool = Field(default=True, description="启用")
    group_id: str = Field(default="", description="群号")
    sleep_window_start: str = Field(default="22:30", description="允许入睡开始，HH:MM")
    sleep_window_end: str = Field(default="07:00", description="允许入睡结束，HH:MM，可跨午夜")
    target_wake_time: str = Field(default="07:30", description="目标醒来时间，HH:MM")
    min_sleep_minutes: int = Field(default=45, description="最短睡眠分钟数")
    max_sleep_minutes: int = Field(default=480, description="最长睡眠分钟数")
    wake_jitter_minutes: int = Field(default=35, description="醒来时间随机浮动分钟数")


class GroupScheduleConfig(PluginConfigBase):
    """分群睡眠时间配置。"""

    __ui_label__ = "分群作息"
    __ui_icon__ = "users"
    __ui_order__ = 5

    independent_default_scopes: bool = Field(
        default=True,
        description="未配置分群作息的群聊和私聊也使用独立睡眠状态；关闭时才共用全局睡眠状态",
    )
    group_schedules: List[GroupScheduleEntryConfig] = Field(
        default_factory=list,
        description="按群号覆盖全局作息；命中群号时优先使用这里的时间配置和独立睡眠状态",
    )


class SleepControlConfig(PluginConfigBase):
    """睡眠期间的拦截配置。"""

    __ui_label__ = "拦截"
    __ui_icon__ = "shield"
    __ui_order__ = 6

    block_inbound_messages: bool = Field(default=True, description="睡眠期间拦截入站消息主链路")
    block_expression_learning: bool = Field(default=True, description="睡眠期间暂停表达学习写入")
    block_memory_automation: bool = Field(default=True, description="睡眠期间暂停自动记忆写回入队")
    block_outbound_messages: bool = Field(default=True, description="睡眠期间拦截后续出站消息")
    planner_control_enabled: bool = Field(default=True, description="睡眠期间清空 Planner 工具并丢弃 Planner 响应")
    control_commands_enabled: bool = Field(default=True, description="允许 /sleep_status 和 /sleep_wake 控制命令")
    persist_sleep_state: bool = Field(default=True, description="重启后恢复未过期的睡眠状态")
    natural_wake_enabled: bool = Field(default=True, description="到达预计醒来时间后由后台任务自动唤醒")
    force_sleep_commands_enabled: bool = Field(
        default=True,
        description="允许 /sleep_now、/sleep_force 和 /sleep_forceall 管理命令",
    )
    admin_user_ids: List[str] = Field(default_factory=list, description="允许使用管理入睡命令的用户 ID；留空时不限制")


class SleepReviewConfig(PluginConfigBase):
    """睡醒回顾配置"""

    __ui_label__ = "睡醒回顾"
    __ui_icon__ = "book-open"
    __ui_order__ = 7

    enabled: bool = Field(default=False, description="醒来后按聊天流总结睡眠期间被拦截的消息")
    max_summary_messages_per_chat: int = Field(default=80, description="每个聊天流最多送入总结模型的消息条数")
    max_summary_chars_per_chat: int = Field(default=6000, description="每个聊天流最多送入总结模型的字符数")
    max_review_chats_per_wake: int = Field(default=10, description="每次醒来最多总结的聊天流数量")
    max_summary_tokens: int = Field(default=500, description="每个聊天流总结最多输出 token 数")


class GoodnightSleepManagerConfig(PluginConfigBase):
    """晚安睡眠管理完整配置。"""

    plugin: PluginSectionConfig = Field(default_factory=PluginSectionConfig)
    trigger: TriggerConfig = Field(default_factory=TriggerConfig)
    sleep_request: SleepRequestConfig = Field(default_factory=SleepRequestConfig)
    schedule: ScheduleConfig = Field(default_factory=ScheduleConfig)
    idle_sleep: IdleSleepConfig = Field(default_factory=IdleSleepConfig)
    group_schedule: GroupScheduleConfig = Field(default_factory=GroupScheduleConfig)
    control: SleepControlConfig = Field(default_factory=SleepControlConfig)
    sleep_review: SleepReviewConfig = Field(default_factory=SleepReviewConfig)
