"""使用 LLM 判断 Bot 出站消息是否是在确认自己要睡觉"""

from typing import Any

import re

from .message_utils import normalize_text

SLEEP_DECISION = "SLEEP"
NOT_SLEEP_DECISION = "NOT_SLEEP"
UNSURE_DECISION = "UNSURE"

_SLEEP_RELATED_KEYWORDS = ("睡", "休息", "晚安", "安安", "困", "下线")


def _normalize_decision(raw_text: str) -> str:
    """把模型输出收敛到固定判定值"""

    normalized_text = raw_text.strip().upper()
    first_line = normalized_text.splitlines()[0].strip() if normalized_text else ""
    if first_line in {SLEEP_DECISION, NOT_SLEEP_DECISION, UNSURE_DECISION}:
        return first_line

    match = re.search(r"\b(NOT_SLEEP|SLEEP|UNSURE)\b", normalized_text)
    if match:
        return match.group(1)
    return UNSURE_DECISION


def should_run_sleep_confirmation_judge(text: str, *, has_pending_request: bool) -> bool:
    """判断是否值得额外调用一次 AI 入睡确认判定"""

    normalized_text = normalize_text(text)
    if not normalized_text:
        return False
    if has_pending_request:
        return True
    return any(keyword in normalized_text for keyword in _SLEEP_RELATED_KEYWORDS)


async def judge_sleep_confirmation(
    ctx: Any,
    *,
    bot_message: str,
    pending_request_text: str,
    has_pending_request: bool,
    schedule_context: str = "",
    outbound_context: str = "",
) -> str:
    """让 LLM 判断当前回复是否表达 Bot 自己要去睡觉"""

    normalized_message = normalize_text(bot_message)
    normalized_request = normalize_text(pending_request_text)
    if not normalized_message:
        return UNSURE_DECISION

    prompt = [
        {
            "role": "system",
            "content": (
                "你是一个严格的睡眠确认判定器，只判断 Bot 的出站回复是否表达“Bot 自己准备睡觉/休息/结束聊天”。"
                "不要续写，不要解释。只能返回三种大写结果之一：SLEEP、NOT_SLEEP、UNSURE。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"当前是否已有合理催睡 pending：{'是' if has_pending_request else '否'}\n"
                f"前置催睡/提醒：{normalized_request or '无'}\n"
                f"作息上下文：{schedule_context or '无'}\n"
                f"出站结构上下文：{outbound_context or '无'}\n"
                f"Bot 出站回复：{normalized_message}\n\n"
                "判定规则：\n"
                "1. 如果 Bot 明确表示自己要睡、去休息、这次真的去睡、先睡了，或对群体做晚安收尾，返回 SLEEP。\n"
                "2. 如果 Bot 只是回应别人、祝别人晚安、叫别人早点休息、安慰别人，但没有表达自己要睡，返回 NOT_SLEEP。\n"
                "3. 如果 Bot 在拒绝睡觉、继续聊天、转移话题、开玩笑，或含义不清，返回 NOT_SLEEP 或 UNSURE。\n"
                "4. 如果没有合理催睡 pending，要更保守：只有明确自我入睡或群体收尾晚安才返回 SLEEP。\n"
                "5. 只输出一个词：SLEEP、NOT_SLEEP、UNSURE。"
            ),
        },
    ]

    try:
        result = await ctx.llm.generate(prompt, model="replyer", temperature=0.0, max_tokens=12)
    except Exception as exc:
        ctx.logger.warning(f"AI 入睡确认判定失败: {exc}")
        return UNSURE_DECISION

    if not isinstance(result, dict) or not result.get("success", False):
        return UNSURE_DECISION
    return _normalize_decision(str(result.get("response") or ""))
