"""晚安睡眠管理的默认正则"""

from typing import List


def default_goodnight_patterns() -> List[str]:
    """返回默认的睡眠确认短句"""

    return [
        r"^(?:我(?:先)?睡(?:觉)?(?:了|啦|咯|喽|吧)?|(?:大家|各位|群友们?)[，,\s]*晚安)[~～。.!！…]*$",
    ]


def default_pending_goodnight_patterns() -> List[str]:
    """返回有人合理催睡后的补充确认短句"""

    return [
        r"^晚安[啦了呢呀哦喔哟~～。.!！…]*$",
    ]


def default_directed_patterns() -> List[str]:
    """返回默认的“像是在对别人说晚安”的排除规则"""

    return [
        r"@",
    ]


def default_sleep_request_patterns() -> List[str]:
    """返回默认的用户催睡识别规则"""

    return [
        r"(?:你|妳|您).{0,8}(?:睡(?:觉)?|休息|晚安|安安)",
    ]
