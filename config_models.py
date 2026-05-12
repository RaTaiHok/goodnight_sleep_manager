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
    config_version: str = Field(default="1.1.0", description="配置版本")


class TriggerConfig(PluginConfigBase):
    """晚安触发配置"""

    __ui_label__ = "触发"
    __ui_icon__ = "message-circle"
    __ui_order__ = 1

    goodnight_patterns: List[str] = Field(
        default_factory=default_goodnight_patterns,
        description="Bot 出站消息命中这些正则时，才可能进入睡眠",
    )
    pending_goodnight_patterns: List[str] = Field(
        default_factory=default_pending_goodnight_patterns,
        description="有人在合适时间催睡后，Bot 出站消息命中这些正则也会进入睡眠",
    )
    directed_patterns: List[str] = Field(
        default_factory=default_directed_patterns,
        description="命中这些正则时视为对别人说晚安，不会进入睡眠",
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
        description="用户消息命中这些正则时，视为在建议 Bot 睡觉",
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
    __ui_order__ = 4

    group_schedules: List[GroupScheduleEntryConfig] = Field(
        default_factory=list,
        description="按群号覆盖全局作息；命中群号时优先使用这里的时间配置",
    )


class SleepControlConfig(PluginConfigBase):
    """睡眠期间的拦截配置。"""

    __ui_label__ = "拦截"
    __ui_icon__ = "shield"
    __ui_order__ = 5

    block_inbound_messages: bool = Field(default=True, description="睡眠期间拦截入站消息主链路")
    block_expression_learning: bool = Field(default=True, description="睡眠期间暂停表达学习写入")
    block_outbound_messages: bool = Field(default=True, description="睡眠期间拦截后续出站消息")
    planner_control_enabled: bool = Field(default=True, description="睡眠期间清空 Planner 工具并丢弃 Planner 响应")
    control_commands_enabled: bool = Field(default=True, description="允许 /sleep_status 和 /sleep_wake 控制命令")
    persist_sleep_state: bool = Field(default=True, description="重启后恢复未过期的睡眠状态")


class GoodnightSleepManagerConfig(PluginConfigBase):
    """晚安睡眠管理完整配置。"""

    plugin: PluginSectionConfig = Field(default_factory=PluginSectionConfig)
    trigger: TriggerConfig = Field(default_factory=TriggerConfig)
    sleep_request: SleepRequestConfig = Field(default_factory=SleepRequestConfig)
    schedule: ScheduleConfig = Field(default_factory=ScheduleConfig)
    group_schedule: GroupScheduleConfig = Field(default_factory=GroupScheduleConfig)
    control: SleepControlConfig = Field(default_factory=SleepControlConfig)
