"""晚安睡眠管理 Hook 处理器"""

from datetime import datetime
from typing import Any

from maibot_sdk import HookHandler
from maibot_sdk.types import HookMode, HookOrder


class SleepHookHandlersMixin:
    """声明所有插件 Hook 入口"""

    @HookHandler(
        "send_service.after_build_message",
        name="goodnight_sleep_detector",
        description="检测 Bot 是否主动说出晚安或睡觉短句",
        mode=HookMode.BLOCKING,
        order=HookOrder.LATE,
    )
    async def handle_after_build_message(
        self,
        message: dict[str, Any],
        processed_plain_text: str = "",
        set_reply: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any] | None:
        """在出站消息构建完成后判断是否进入睡眠"""

        del kwargs

        if not self._enabled():
            return None

        if self._is_sleeping(message):
            if not self.config.control.block_outbound_messages:
                return None
            if self._is_control_reply(message, processed_plain_text):
                return None
            return self._abort_result("睡眠中，出站消息已在构建后拦截")

        text = self._extract_text(message, processed_plain_text)
        now = datetime.now()
        if not self._is_inside_sleep_window(now, message):
            if self._looks_like_self_goodnight(text, message, set_reply=set_reply):
                self.ctx.logger.info(f"检测到晚安短句但当前不在允许入睡时间内，忽略: {text}")
            return None

        if not await self._should_enter_sleep_from_outbound(text, message, set_reply=set_reply):
            return None

        sleep_until = self._choose_sleep_until(now, message)
        sleep_record = self._enter_sleep(sleep_until, f"Bot 出站短句触发: {text}", message)
        sleep_record.allowed_trigger_message_id = self._message_id(message)
        self._save_sleep_state()
        return None

    @HookHandler(
        "chat.receive.before_process",
        name="sleep_inbound_pre_blocker",
        description="睡眠期间在入站消息预处理前拦截消息",
        mode=HookMode.BLOCKING,
        order=HookOrder.EARLY,
    )
    async def handle_before_receive(self, message: dict[str, Any], **kwargs: Any) -> dict[str, Any] | None:
        """睡眠期间尽早拦截新消息，控制命令除外"""

        del kwargs

        if not self._should_block_inbound(message):
            return None
        return self._abort_result("睡眠中，入站消息已在预处理前拦截")

    @HookHandler(
        "chat.receive.after_process",
        name="sleep_inbound_post_blocker",
        description="睡眠期间在入站消息预处理后拦截消息",
        mode=HookMode.BLOCKING,
        order=HookOrder.EARLY,
    )
    async def handle_after_receive(self, message: dict[str, Any], **kwargs: Any) -> dict[str, Any] | None:
        """作为二次保险，阻止消息进入命令、HeartFlow 与 Maisaka 主链路。"""

        del kwargs

        if not self._should_block_inbound(message):
            return await self._handle_sleep_request(message)
        return self._abort_result("睡眠中，入站消息已在主链路前拦截")

    @HookHandler(
        "expression.learn.after_extract",
        name="sleep_expression_extract_blocker",
        description="睡眠期间暂停表达学习提取结果",
        mode=HookMode.BLOCKING,
        order=HookOrder.EARLY,
    )
    async def handle_expression_after_extract(self, **kwargs: Any) -> dict[str, Any] | None:
        """睡眠期间中止本轮表达学习"""

        if self._should_block_learning(kwargs.get("session_id")):
            return self._abort_result("睡眠中，表达学习提取已暂停")
        return None

    @HookHandler(
        "expression.learn.before_upsert",
        name="sleep_expression_upsert_blocker",
        description="睡眠期间阻止表达学习写入",
        mode=HookMode.BLOCKING,
        order=HookOrder.EARLY,
    )
    async def handle_expression_before_upsert(self, **kwargs: Any) -> dict[str, Any] | None:
        """睡眠期间跳过表达学习写库"""

        if self._should_block_learning(kwargs.get("session_id")):
            return self._abort_result("睡眠中，表达学习写入已暂停")
        return None

    @HookHandler(
        "maisaka.planner.before_request",
        name="sleep_planner_request_controller",
        description="睡眠期间尽量压低 Planner 请求内容与工具能力",
        mode=HookMode.BLOCKING,
        order=HookOrder.EARLY,
    )
    async def handle_planner_before_request(self, **kwargs: Any) -> dict[str, Any] | None:
        """Planner hook 不允许 abort，这里只能改写请求做兜底"""

        if self._should_control_planner(kwargs.get("session_id")):
            modified_kwargs = dict(kwargs)
            modified_kwargs["tool_definitions"] = []
            modified_kwargs["messages"] = [
                {
                    "role": "system",
                    "content": "当前 Bot 正在睡眠状态。不要回复用户，不要调用任何工具，只输出空内容。",
                },
                {
                    "role": "user",
                    "content": "sleep",
                },
            ]
            return {"action": "continue", "modified_kwargs": modified_kwargs}

        planner_context = self._build_pending_sleep_request_planner_context(kwargs.get("session_id"))
        if not planner_context:
            return None

        raw_messages = kwargs.get("messages")
        if not isinstance(raw_messages, list):
            return None

        modified_kwargs = dict(kwargs)
        modified_kwargs["messages"] = [
            *raw_messages,
            {
                "role": "system",
                "content": planner_context,
            },
        ]
        return {"action": "continue", "modified_kwargs": modified_kwargs}

    @HookHandler(
        "maisaka.planner.after_response",
        name="sleep_planner_response_controller",
        description="睡眠期间丢弃 Planner 响应与工具调用",
        mode=HookMode.BLOCKING,
        order=HookOrder.LATE,
    )
    async def handle_planner_after_response(self, **kwargs: Any) -> dict[str, Any] | None:
        """睡眠期间清空 Planner 响应，避免后续动作继续执行"""

        if not self._should_control_planner(kwargs.get("session_id")):
            return None

        modified_kwargs = dict(kwargs)
        modified_kwargs["response"] = ""
        modified_kwargs["tool_calls"] = []
        return {"action": "continue", "modified_kwargs": modified_kwargs}

    @HookHandler(
        "send_service.before_send",
        name="sleep_outbound_blocker",
        description="睡眠期间拦截后续出站消息",
        mode=HookMode.BLOCKING,
        order=HookOrder.EARLY,
    )
    async def handle_before_send(self, message: dict[str, Any], **kwargs: Any) -> dict[str, Any] | None:
        """允许触发睡眠的晚安消息发出，拦截睡眠后的其他出站消息"""

        del kwargs

        if not self._enabled() or not self._is_sleeping(message) or not self.config.control.block_outbound_messages:
            return None

        sleep_record = self._active_sleep_record(message=message)
        if sleep_record is None:
            return None

        message_id = self._message_id(message)
        if message_id and message_id == sleep_record.allowed_trigger_message_id:
            sleep_record.allowed_trigger_message_id = ""
            self._save_sleep_state()
            return None

        if self._is_control_reply(message):
            return None

        return self._abort_result("睡眠中，后续出站消息已拦截")
