"""晚安睡眠管理的运行期状态"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class SleepState:
    """插件运行期状态。"""

    sleep_until: Optional[datetime] = None
    sleep_reason: str = ""
    allowed_trigger_message_id: str = ""
    control_reply_allowed_until: float = 0.0
    pending_sleep_request_until: float = 0.0
    pending_sleep_request_session_id: str = ""
    pending_sleep_request_group_id: str = ""
    pending_sleep_request_text: str = ""

    def clear_sleep(self) -> None:
        """清理当前睡眠状态"""

        self.sleep_until = None
        self.sleep_reason = ""
        self.allowed_trigger_message_id = ""

    def clear_pending_request(self) -> None:
        """清理待确认的用户催睡状态"""

        self.pending_sleep_request_until = 0.0
        self.pending_sleep_request_session_id = ""
        self.pending_sleep_request_group_id = ""
        self.pending_sleep_request_text = ""
