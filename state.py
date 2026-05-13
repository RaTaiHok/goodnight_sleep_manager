"""晚安睡眠管理的运行期状态"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class SleepRecord:
    """单个睡眠作用域的状态"""

    scope_key: str
    scope_label: str
    sleep_started_at: Optional[datetime] = None
    sleep_until: Optional[datetime] = None
    sleep_reason: str = ""
    group_id: str = ""
    session_id: str = ""
    allowed_trigger_message_id: str = ""


@dataclass
class SleepState:
    """插件运行期状态"""

    sleep_records: Dict[str, SleepRecord] = field(default_factory=dict)
    session_scope_keys: Dict[str, str] = field(default_factory=dict)
    last_any_activity_by_scope: Dict[str, float] = field(default_factory=dict)
    last_bot_activity_by_scope: Dict[str, float] = field(default_factory=dict)
    topic_grace_until_by_scope: Dict[str, float] = field(default_factory=dict)
    topic_grace_used_by_scope: Dict[str, bool] = field(default_factory=dict)
    idle_scope_messages: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    control_reply_allowed_until: float = 0.0
    pending_sleep_request_until: float = 0.0
    pending_sleep_request_session_id: str = ""
    pending_sleep_request_group_id: str = ""
    pending_sleep_request_text: str = ""

    def clear_sleep(self, scope_key: str = "") -> None:
        """清理当前睡眠状态"""

        normalized_scope_key = scope_key.strip()
        if normalized_scope_key:
            self.sleep_records.pop(normalized_scope_key, None)
            stale_session_ids = [
                session_id
                for session_id, mapped_scope_key in self.session_scope_keys.items()
                if mapped_scope_key == normalized_scope_key
            ]
            for session_id in stale_session_ids:
                self.session_scope_keys.pop(session_id, None)
            return
        self.sleep_records.clear()
        self.session_scope_keys.clear()

    def clear_pending_request(self) -> None:
        """清理待确认的用户催睡状态"""

        self.pending_sleep_request_until = 0.0
        self.pending_sleep_request_session_id = ""
        self.pending_sleep_request_group_id = ""
        self.pending_sleep_request_text = ""
