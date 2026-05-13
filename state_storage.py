"""晚安睡眠管理的持久化状态文件工具"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import json

from .state import SleepRecord

PERSISTENCE_VERSION = 2
GLOBAL_SCOPE_KEY = "global"
STATE_FILE_PATH = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "plugins"
    / "goodnight_sleep_manager"
    / "sleep_state.json"
)


def get_sleep_state_path() -> Path:
    """返回睡眠状态持久化文件路径"""

    return STATE_FILE_PATH


def load_persisted_sleep_records() -> Dict[str, SleepRecord]:
    """读取尚未判定是否过期的睡眠状态"""

    state_path = get_sleep_state_path()
    if not state_path.exists():
        return {}

    raw_data = json.loads(state_path.read_text(encoding="utf-8"))
    if not isinstance(raw_data, dict):
        raise ValueError("睡眠状态文件根节点必须是对象")

    raw_records = raw_data.get("sleep_records")
    if isinstance(raw_records, dict):
        return _load_records_from_mapping(raw_records)

    legacy_record = _load_legacy_record(raw_data)
    return {legacy_record.scope_key: legacy_record} if legacy_record is not None else {}


def save_persisted_sleep_records(sleep_records: Dict[str, SleepRecord]) -> None:
    """保存当前所有睡眠作用域状态"""

    active_records = {
        scope_key: record
        for scope_key, record in sleep_records.items()
        if record.sleep_until is not None and scope_key.strip()
    }

    state_path = get_sleep_state_path()
    if not active_records:
        clear_persisted_sleep_state()
        return

    state_path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "version": PERSISTENCE_VERSION,
        "sleep_records": {
            scope_key: {
                "scope_key": record.scope_key,
                "scope_label": record.scope_label,
                "group_id": record.group_id,
                "session_id": record.session_id,
                "sleep_started_at": (
                    record.sleep_started_at.isoformat(timespec="seconds")
                    if record.sleep_started_at is not None
                    else None
                ),
                "sleep_until": record.sleep_until.isoformat(timespec="seconds"),
                "sleep_reason": record.sleep_reason,
            }
            for scope_key, record in active_records.items()
            if record.sleep_until is not None
        },
        "saved_at": datetime.now().isoformat(timespec="seconds"),
    }
    state_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def clear_persisted_sleep_state() -> None:
    """删除持久化睡眠状态文件"""

    state_path = get_sleep_state_path()
    if state_path.exists():
        state_path.unlink()


def _load_records_from_mapping(raw_records: dict[Any, Any]) -> Dict[str, SleepRecord]:
    """从新版 sleep_records 映射读取睡眠状态"""

    records: Dict[str, SleepRecord] = {}
    for raw_scope_key, raw_record in raw_records.items():
        if not isinstance(raw_record, dict):
            continue

        record = _build_record(
            scope_key=str(raw_record.get("scope_key") or raw_scope_key or "").strip(),
            scope_label=str(raw_record.get("scope_label") or raw_scope_key or "").strip(),
            group_id=str(raw_record.get("group_id") or "").strip(),
            session_id=str(raw_record.get("session_id") or "").strip(),
            sleep_started_at_raw=raw_record.get("sleep_started_at"),
            sleep_until_raw=raw_record.get("sleep_until"),
            sleep_reason_raw=raw_record.get("sleep_reason"),
        )
        if record is not None:
            records[record.scope_key] = record
    return records


def _load_legacy_record(raw_data: dict[str, Any]) -> SleepRecord | None:
    """兼容读取 v1 的单一全局睡眠状态"""

    return _build_record(
        scope_key=GLOBAL_SCOPE_KEY,
        scope_label="全局配置",
        group_id="",
        session_id="",
        sleep_started_at_raw=raw_data.get("sleep_started_at"),
        sleep_until_raw=raw_data.get("sleep_until"),
        sleep_reason_raw=raw_data.get("sleep_reason"),
    )


def _build_record(
    *,
    scope_key: str,
    scope_label: str,
    group_id: str,
    session_id: str,
    sleep_started_at_raw: Any,
    sleep_until_raw: Any,
    sleep_reason_raw: Any,
) -> SleepRecord | None:
    """把持久化字段转换为 SleepRecord"""

    if not scope_key:
        return None
    if not isinstance(sleep_until_raw, str) or not sleep_until_raw.strip():
        return None

    sleep_started_at = None
    if isinstance(sleep_started_at_raw, str) and sleep_started_at_raw.strip():
        sleep_started_at = datetime.fromisoformat(sleep_started_at_raw.strip())
    sleep_until = datetime.fromisoformat(sleep_until_raw.strip())
    sleep_reason = sleep_reason_raw.strip() if isinstance(sleep_reason_raw, str) else ""
    return SleepRecord(
        scope_key=scope_key,
        scope_label=scope_label or scope_key,
        sleep_started_at=sleep_started_at,
        sleep_until=sleep_until,
        sleep_reason=sleep_reason,
        group_id=group_id,
        session_id=session_id,
    )
