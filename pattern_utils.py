"""正则匹配辅助"""

from logging import Logger
from typing import List, Optional

import re


def matches_any_pattern(text: str, patterns: List[str], logger: Optional[Logger] = None) -> bool:
    """判断文本是否命中任意正则，跳过非法正则"""

    for pattern in patterns:
        try:
            if re.search(pattern, text):
                return True
        except re.error as exc:
            if logger is not None:
                logger.warning(f"晚安睡眠管理正则无效，已跳过: {pattern} ({exc})")
    return False
