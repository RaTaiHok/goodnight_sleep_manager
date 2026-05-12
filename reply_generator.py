"""生成不合适时间催睡时的委婉回复"""

from typing import Any


def _clean_generated_reply(raw_text: str) -> str:
    """清理 LLM 生成结果，保留一条短回复"""

    text = raw_text.strip().strip("\"'“”‘’")
    if not text:
        return ""
    first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
    return first_line[:80]


async def generate_off_window_reply(ctx: Any, user_message: str) -> str:
    """根据主配置的人格和表达风格生成委婉拒绝睡觉的回复"""

    try:
        nickname = await ctx.config.get("bot.nickname", "麦麦")
        personality = await ctx.config.get("personality.personality", "")
        reply_style = await ctx.config.get("personality.reply_style", "")
        prompt = [
            {
                "role": "system",
                "content": (
                    "你要替当前 Bot 生成一句聊天回复。回复必须遵循给定的人格设定和表达风格，"
                    "不要解释规则，不要提到插件、系统或时间窗口"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Bot 昵称：{nickname}\n"
                    f"人格设定：{personality}\n"
                    f"表达风格：{reply_style}\n"
                    f"用户刚才让 Bot 睡觉：{user_message}\n"
                    "但现在还不适合睡觉。请生成一句自然、委婉、简短的拒绝或缓一缓的回复，"
                    "保持 Bot 自己的说话风格。最多 30 个汉字"
                ),
            },
        ]
        result = await ctx.llm.generate(prompt, model="replyer", temperature=0.7, max_tokens=80)
        if not isinstance(result, dict) or not result.get("success", False):
            return ""
        return _clean_generated_reply(str(result.get("response") or ""))
    except Exception as exc:
        ctx.logger.warning(f"生成不合适时间催睡回复失败: {exc}")
        return ""
