"""晚安睡眠管理的持久化状态文件工具。"""

from datetime import datetime
from pathlib import Path
from typing import Any

import json

PERSISTENCE_VERSION = 1
STATE_FILE_PATH = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "plugins"
    / "goodnight_sleep_manager"
    / "sleep_state.json"
)


def get_sleep_state_path() -> Path:
    """返回睡眠状态持久化文件路径。"""

    return STATE_FILE_PATH


def load_persisted_sleep_state() -> tuple[datetime, str] | None:
    """读取尚未判定是否过期的睡眠状态。"""

    state_path = get_sleep_state_path()
    if not state_path.exists():
        return None

    raw_data = json.loads(state_path.read_text(encoding="utf-8"))
    if not isinstance(raw_data, dict):
        raise ValueError("睡眠状态文件根节点必须是对象")

    sleep_until_raw = raw_data.get("sleep_until")
    if not isinstance(sleep_until_raw, str) or not sleep_until_raw.strip():
        raise ValueError("睡眠状态文件缺少 sleep_until")

    sleep_until = datetime.fromisoformat(sleep_until_raw.strip())
    sleep_reason = raw_data.get("sleep_reason")
    return sleep_until, sleep_reason.strip() if isinstance(sleep_reason, str) else ""


def save_persisted_sleep_state(sleep_until: datetime, sleep_reason: str) -> None:
    """保存当前睡眠状态。"""

    state_path = get_sleep_state_path()
    state_path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "version": PERSISTENCE_VERSION,
        "sleep_until": sleep_until.isoformat(timespec="seconds"),
        "sleep_reason": sleep_reason,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
    }
    state_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def clear_persisted_sleep_state() -> None:
    """删除持久化睡眠状态文件。"""

    state_path = get_sleep_state_path()
    if state_path.exists():
        state_path.unlink()
