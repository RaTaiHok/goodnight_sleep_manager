"""睡眠时间窗口和时长计算"""

from datetime import datetime, time, timedelta
from typing import Any

import random


def parse_clock(raw_value: str, fallback: time) -> time:
    """解析 HH:MM 时间字符串"""

    try:
        hour_text, minute_text = raw_value.strip().split(":", 1)
        hour = int(hour_text)
        minute = int(minute_text)
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return time(hour, minute)
    except (AttributeError, TypeError, ValueError):
        pass
    return fallback


def is_inside_sleep_window(now: datetime, schedule_config: Any) -> bool:
    """判断当前时间是否落在允许入睡的时间窗口"""

    start_time = parse_clock(schedule_config.sleep_window_start, time(22, 30))
    end_time = parse_clock(schedule_config.sleep_window_end, time(7, 0))
    current_time = now.time()
    if start_time <= end_time:
        return start_time <= current_time < end_time
    return current_time >= start_time or current_time < end_time


def choose_sleep_until(now: datetime, schedule_config: Any) -> datetime:
    """根据当前时间和配置决定本次睡到什么时候"""

    min_minutes = max(1, int(schedule_config.min_sleep_minutes))
    max_minutes = max(min_minutes, int(schedule_config.max_sleep_minutes))
    wake_jitter = max(0, int(schedule_config.wake_jitter_minutes))
    target_wake_time = parse_clock(schedule_config.target_wake_time, time(7, 30))

    target_today = datetime.combine(now.date(), target_wake_time)
    if target_today <= now:
        target_today += timedelta(days=1)

    jitter_minutes = random.randint(-wake_jitter, wake_jitter) if wake_jitter else 0
    target_with_jitter = target_today + timedelta(minutes=jitter_minutes)
    target_minutes = int((target_with_jitter - now).total_seconds() // 60)
    if target_minutes < min_minutes:
        target_minutes = min_minutes

    duration_minutes = min(max_minutes, max(min_minutes, target_minutes))
    return now + timedelta(minutes=duration_minutes)


def format_datetime(value: datetime) -> str:
    """格式化本地时间"""

    return value.strftime("%Y-%m-%d %H:%M:%S")
