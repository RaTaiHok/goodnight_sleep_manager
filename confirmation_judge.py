"""使用 LLM 判断 Bot 出站消息是否是在确认自己要睡觉"""

from typing import Any, Sequence

import asyncio
import re
import time

from .message_utils import normalize_text

SLEEP_DECISION = "SLEEP"
NOT_SLEEP_DECISION = "NOT_SLEEP"
UNSURE_DECISION = "UNSURE"


def parse_sleep_related_keywords(sleep_related_keywords: str | Sequence[str] | None) -> list[str]:
    """解析 AI 入睡判定触发关键词"""

    if sleep_related_keywords is None:
        return []
    if isinstance(sleep_related_keywords, str):
        raw_keywords = sleep_related_keywords.replace("，", ",").split(",")
    else:
        raw_keywords = sleep_related_keywords

    normalized_keywords: list[str] = []
    for keyword in raw_keywords:
        if not isinstance(keyword, str):
            continue
        normalized_keyword = normalize_text(keyword)
        if normalized_keyword:
            normalized_keywords.append(normalized_keyword)
    return normalized_keywords


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


def should_run_sleep_confirmation_judge(
    text: str,
    *,
    has_pending_request: bool,
    sleep_related_keywords: str | Sequence[str] | None = None,
) -> bool:
    """判断是否值得额外调用一次 AI 入睡确认判定"""

    normalized_text = normalize_text(text)
    if not normalized_text:
        return False
    if has_pending_request:
        return True
    normalized_keywords = parse_sleep_related_keywords(sleep_related_keywords)
    return any(keyword in normalized_text for keyword in normalized_keywords)


async def judge_sleep_confirmation(
    ctx: Any,
    *,
    bot_message: str,
    pending_request_text: str,
    has_pending_request: bool,
    schedule_context: str = "",
    outbound_context: str = "",
    timeout_seconds: int = 4,
    max_tokens: int = 64,
    log_enabled: bool = True,
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
                "2. 如果 Bot 表示自己已经躺床上、上床、钻被窝、闭眼、熄灯、关机、下线休息，也返回 SLEEP。\n"
                "3. 如果 Bot 只是回应别人、祝别人晚安、叫别人早点休息、安慰别人，但没有表达自己要睡，返回 NOT_SLEEP。\n"
                "4. 如果 Bot 在拒绝睡觉、继续聊天、转移话题、开玩笑，或含义不清，返回 NOT_SLEEP 或 UNSURE。\n"
                "5. 如果没有合理催睡 pending，要更保守：只有明确自我入睡或群体收尾晚安才返回 SLEEP。\n"
                "6. 只输出一个词：SLEEP、NOT_SLEEP、UNSURE。"
            ),
        },
    ]

    safe_timeout_seconds = max(0, int(timeout_seconds or 0))
    safe_max_tokens = max(16, int(max_tokens or 64))
    started_at = time.perf_counter()
    try:
        generate_task = ctx.llm.generate(prompt, model="replyer", temperature=0.0, max_tokens=safe_max_tokens)
        if safe_timeout_seconds > 0:
            result = await asyncio.wait_for(generate_task, timeout=float(safe_timeout_seconds))
        else:
            result = await generate_task
    except asyncio.TimeoutError:
        elapsed_seconds = time.perf_counter() - started_at
        ctx.logger.warning(f"AI 入睡确认判定超时: timeout={safe_timeout_seconds}s elapsed={elapsed_seconds:.2f}s")
        return UNSURE_DECISION
    except Exception as exc:
        elapsed_seconds = time.perf_counter() - started_at
        ctx.logger.warning(f"AI 入睡确认判定失败: elapsed={elapsed_seconds:.2f}s error={exc}")
        return UNSURE_DECISION

    if not isinstance(result, dict) or not result.get("success", False):
        elapsed_seconds = time.perf_counter() - started_at
        if log_enabled:
            ctx.logger.info(f"AI 入睡确认判定返回失败: elapsed={elapsed_seconds:.2f}s result={result}")
        return UNSURE_DECISION
    raw_response = str(result.get("response") or "")
    decision = _normalize_decision(raw_response)
    elapsed_seconds = time.perf_counter() - started_at
    if log_enabled:
        ctx.logger.info(
            f"AI 入睡确认判定完成: decision={decision} elapsed={elapsed_seconds:.2f}s response={raw_response.strip()}"
        )
    return decision
