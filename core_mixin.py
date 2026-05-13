"""晚安睡眠管理核心逻辑"""

from datetime import datetime
from time import monotonic
from typing import Any

from .confirmation_judge import NOT_SLEEP_DECISION, SLEEP_DECISION, judge_sleep_confirmation, should_run_sleep_confirmation_judge
from .matchers import looks_like_self_goodnight, looks_like_sleep_request
from .message_utils import (
    abort_result,
    extract_text,
    has_at_component,
    has_reply_component,
    message_group_id,
    message_id,
    message_session_id,
    normalize_text,
)
from .reply_generator import generate_off_window_reply
from .schedule_utils import choose_sleep_until, format_datetime, is_inside_sleep_window
from .state import SleepState
from .state_storage import clear_persisted_sleep_state, load_persisted_sleep_state, save_persisted_sleep_state


class SleepCoreMixin:
    """为插件主体提供睡眠状态与判断逻辑"""

    _state: SleepState

    def _init_sleep_state(self) -> None:
        """初始化插件内存状态"""

        self._state = SleepState()

    def _enabled(self) -> bool:
        """返回插件是否启用"""

        return self.config.plugin.enabled

    def _is_sleeping(self) -> bool:
        """返回当前是否还处于睡眠状态，并在到点后自动醒来"""

        if self._state.sleep_until is None:
            return False
        now = datetime.now()
        if now < self._state.sleep_until:
            return True
        self._wake("到达预计醒来时间")
        return False

    def _enter_sleep(self, sleep_until: datetime, reason: str) -> None:
        """进入睡眠状态"""

        self._state.sleep_until = sleep_until
        self._state.sleep_reason = reason
        self._clear_pending_sleep_request()
        self._save_sleep_state()
        self._get_logger().info(f"晚安睡眠管理进入睡眠，预计醒来: {format_datetime(sleep_until)}，原因: {reason}")

    def _wake(self, reason: str) -> None:
        """退出睡眠状态"""

        was_sleeping = self._state.sleep_until is not None
        self._state.clear_sleep()
        self._clear_pending_sleep_request()
        self._clear_sleep_state_storage()
        if was_sleeping:
            self._get_logger().info(f"晚安睡眠管理已唤醒: {reason}")

    def _restore_sleep_state(self) -> None:
        """插件加载时从持久化文件恢复未过期的睡眠状态。"""

        if not self.config.control.persist_sleep_state:
            self._clear_sleep_state_storage()
            return

        try:
            persisted_state = load_persisted_sleep_state()
        except Exception as exc:
            self._get_logger().warning(f"读取持久化睡眠状态失败，已清理状态文件: {exc}")
            self._clear_sleep_state_storage()
            return

        if persisted_state is None:
            return

        sleep_until, sleep_reason = persisted_state
        if datetime.now() >= sleep_until:
            self._state.clear_sleep()
            self._clear_sleep_state_storage()
            self._get_logger().info("持久化睡眠状态已过期，启动时自动清理")
            return

        self._state.sleep_until = sleep_until
        self._state.sleep_reason = sleep_reason or "从持久化状态恢复"
        self._clear_pending_sleep_request()
        self._get_logger().info(
            f"已恢复持久化睡眠状态，预计醒来: {format_datetime(sleep_until)}，原因: {self._state.sleep_reason}"
        )

    def _save_sleep_state(self) -> None:
        """将当前睡眠状态写入持久化文件。"""

        if not self.config.control.persist_sleep_state:
            self._clear_sleep_state_storage()
            return
        if self._state.sleep_until is None:
            self._clear_sleep_state_storage()
            return

        try:
            save_persisted_sleep_state(self._state.sleep_until, self._state.sleep_reason)
        except Exception as exc:
            self._get_logger().warning(f"保存持久化睡眠状态失败: {exc}")

    def _clear_sleep_state_storage(self) -> None:
        """清理持久化睡眠状态文件。"""

        try:
            clear_persisted_sleep_state()
        except Exception as exc:
            self._get_logger().warning(f"清理持久化睡眠状态失败: {exc}")

    def _handle_plugin_unload(self) -> None:
        """插件卸载时保留未过期睡眠状态，便于重启后恢复。"""

        if self._state.sleep_until is not None and datetime.now() < self._state.sleep_until:
            if self.config.control.persist_sleep_state:
                self._save_sleep_state()
                self._get_logger().info("晚安睡眠管理卸载，未过期睡眠状态已保留")
            else:
                self._clear_sleep_state_storage()
                self._get_logger().info("晚安睡眠管理卸载，持久化已关闭，未保留睡眠状态")
            return

        self._clear_sleep_state_storage()

    async def _handle_sleep_request(self, message: dict[str, Any]) -> dict[str, Any] | None:
        """处理用户让 Bot 睡觉的消息"""

        if not self._enabled() or not self.config.sleep_request.enabled or self._is_sleeping():
            return None

        text = extract_text(message)
        if not looks_like_sleep_request(text, message, self.config.sleep_request, logger=self._get_logger()):
            return None

        now = datetime.now()
        if self._is_inside_sleep_window(now, message):
            self._set_pending_sleep_request(message, text)
            return None

        behavior = self.config.sleep_request.off_window_behavior.strip().lower()
        if behavior == "pass":
            return None

        if behavior == "reply":
            stream_id = message_session_id(message)
            reply_text = self.config.sleep_request.off_window_reply.strip()
            if not reply_text:
                reply_text = await generate_off_window_reply(self.ctx, text)
            if stream_id and reply_text:
                await self.ctx.send.text(reply_text, stream_id)

        return abort_result("不在允许入睡时间内，用户催睡消息已处理")

    def _should_block_inbound(self, message: dict[str, Any]) -> bool:
        """判断当前入站消息是否应该被拦截"""

        if not self._enabled() or not self.config.control.block_inbound_messages or not self._is_sleeping():
            return False
        if self.config.control.control_commands_enabled and self._is_control_command(message):
            return False
        return True

    def _should_block_learning(self) -> bool:
        """判断是否需要暂停表达学习"""

        return self._enabled() and self.config.control.block_expression_learning and self._is_sleeping()

    def _should_control_planner(self) -> bool:
        """判断是否需要启用 Planner 兜底保护"""

        return self._enabled() and self.config.control.planner_control_enabled and self._is_sleeping()

    def _looks_like_self_goodnight(self, text: str, message: dict[str, Any], *, set_reply: bool = False) -> bool:
        """判断出站文本是否像 Bot 自己准备睡觉"""

        return looks_like_self_goodnight(
            text,
            message,
            self.config.trigger,
            has_pending_request=self._has_pending_sleep_request(message),
            logger=self._get_logger(),
            set_reply=set_reply,
        )

    async def _should_enter_sleep_from_outbound(
        self,
        text: str,
        message: dict[str, Any],
        *,
        set_reply: bool = False,
    ) -> bool:
        """判断出站消息是否应该触发入睡，优先使用 AI 语义判定"""

        normalized_text = normalize_text(text)
        if not normalized_text or len(normalized_text) > 120:
            return False

        if self.config.trigger.reject_at_component and has_at_component(message):
            return False
        has_pending_request = self._has_pending_sleep_request(message)
        if self.config.trigger.reject_reply_message and not has_pending_request and (
            set_reply or has_reply_component(message)
        ):
            return False

        if self.config.trigger.ai_confirmation_enabled and should_run_sleep_confirmation_judge(
            normalized_text,
            has_pending_request=has_pending_request,
        ):
            decision = await judge_sleep_confirmation(
                self.ctx,
                bot_message=normalized_text,
                pending_request_text=self._state.pending_sleep_request_text,
                has_pending_request=has_pending_request,
                schedule_context=self._build_sleep_confirmation_schedule_context(message),
                outbound_context=self._build_sleep_confirmation_outbound_context(message, set_reply=set_reply),
            )
            if decision == SLEEP_DECISION:
                self._get_logger().info(f"AI 入睡确认判定触发: text={normalized_text}")
                return True
            if decision == NOT_SLEEP_DECISION:
                self._get_logger().info(f"AI 入睡确认判定否定: text={normalized_text}")
                return False
            self._get_logger().info(f"AI 入睡确认判定不确定，转入正则兜底: decision={decision} text={normalized_text}")

        return self._looks_like_self_goodnight(text, message, set_reply=set_reply)

    def _looks_like_sleep_request(self, text: str, message: dict[str, Any]) -> bool:
        """判断用户消息是否像是在让 Bot 睡觉"""

        return looks_like_sleep_request(text, message, self.config.sleep_request, logger=self._get_logger())

    def _choose_sleep_until(self, now: datetime, message: dict[str, Any] | None = None) -> datetime:
        """根据当前时间和配置决定本次睡到什么时候"""

        return choose_sleep_until(now, self._schedule_for_message(message))

    def _is_inside_sleep_window(self, now: datetime, message: dict[str, Any] | None = None) -> bool:
        """判断当前时间是否落在允许入睡的时间窗口"""

        return is_inside_sleep_window(now, self._schedule_for_message(message))

    def _schedule_for_message(self, message: dict[str, Any] | None) -> Any:
        """根据消息所属群聊选择生效的作息配置"""

        if message is None:
            return self.config.schedule

        group_id = message_group_id(message)
        if not group_id and self._pending_sleep_request_matches_session(message_session_id(message)):
            group_id = self._state.pending_sleep_request_group_id

        schedule_config, _ = self._schedule_for_group_id(group_id)
        return schedule_config

    def _schedule_for_group_id(self, group_id: str) -> tuple[Any, str]:
        """按群号获取分群作息；未命中时回落全局作息"""

        normalized_group_id = group_id.strip()
        if normalized_group_id:
            for group_schedule in self.config.group_schedule.group_schedules:
                if not group_schedule.enabled:
                    continue
                if group_schedule.group_id.strip() == normalized_group_id:
                    return group_schedule, f"群 {normalized_group_id} 分群配置"
        return self.config.schedule, "全局配置"

    def _build_sleep_confirmation_schedule_context(self, message: dict[str, Any]) -> str:
        """构造 AI 入睡确认判定可用的作息上下文"""

        group_id = message_group_id(message)
        if not group_id and self._pending_sleep_request_matches_session(message_session_id(message)):
            group_id = self._state.pending_sleep_request_group_id

        active_schedule, schedule_source = self._schedule_for_group_id(group_id)
        now = datetime.now()
        inside_window = is_inside_sleep_window(now, active_schedule)
        return (
            f"当前时间 {now.strftime('%H:%M')}；"
            f"生效作息：{schedule_source}；"
            f"允许入睡：{active_schedule.sleep_window_start} 到 {active_schedule.sleep_window_end}；"
            f"目标醒来：{active_schedule.target_wake_time}；"
            f"当前{'在' if inside_window else '不在'}允许入睡时间内"
        )

    @staticmethod
    def _build_sleep_confirmation_outbound_context(message: dict[str, Any], *, set_reply: bool) -> str:
        """构造 AI 入睡确认判定可用的出站结构上下文"""

        flags: list[str] = []
        if has_at_component(message):
            flags.append("包含 @ 组件")
        if set_reply or has_reply_component(message):
            flags.append("是引用回复")
        return "；".join(flags) if flags else "普通出站消息"

    def _message_stub_for_command(self, stream_id: str, group_id: str = "") -> dict[str, Any]:
        """为控制命令构造最小消息载荷，用于复用作息选择逻辑"""

        message: dict[str, Any] = {
            "session_id": stream_id,
            "message_info": {},
        }
        if group_id.strip():
            message["message_info"] = {
                "group_info": {
                    "group_id": group_id.strip(),
                    "group_name": "",
                }
            }
        return message

    def _can_use_force_sleep_command(self, user_id: str) -> bool:
        """判断用户是否允许使用强制入睡类命令"""

        allowed_user_ids = [item.strip() for item in self.config.control.admin_user_ids if item.strip()]
        if not allowed_user_ids:
            return True
        return user_id.strip() in allowed_user_ids

    def _control_command_names(self) -> set[str]:
        """返回睡眠期间允许穿透入站拦截的控制命令"""

        command_names = {"/sleep_status", "/sleep_wake"}
        if self.config.control.force_sleep_commands_enabled:
            command_names.update({"/sleep_now", "/sleep_force"})
        return command_names

    def _set_pending_sleep_request(self, message: dict[str, Any], text: str) -> None:
        """记录一次合适时间内的用户催睡，等待 Bot 自己确认"""

        ttl_seconds = max(1, int(self.config.sleep_request.pending_confirm_seconds))
        self._state.pending_sleep_request_until = monotonic() + ttl_seconds
        self._state.pending_sleep_request_session_id = message_session_id(message)
        self._state.pending_sleep_request_group_id = message_group_id(message)
        self._state.pending_sleep_request_text = normalize_text(text)
        self._get_logger().info(
            "检测到合适时间内的用户催睡，等待 Bot 自己确认入睡: "
            f"session={self._state.pending_sleep_request_session_id} "
            f"group={self._state.pending_sleep_request_group_id or 'private/global'} "
            f"text={self._state.pending_sleep_request_text}"
        )

    def _clear_pending_sleep_request(self) -> None:
        """清理待确认的用户催睡状态"""

        self._state.clear_pending_request()

    def _has_pending_sleep_request(self, message: dict[str, Any]) -> bool:
        """判断当前出站消息是否对应最近一次合理的用户催睡"""

        if not self._pending_sleep_request_is_active():
            return False

        pending_session_id = self._state.pending_sleep_request_session_id
        if not pending_session_id:
            return True
        return message_session_id(message) == pending_session_id

    def _build_pending_sleep_request_planner_context(self, session_id: Any) -> str:
        """为 Planner 构造一次性催睡上下文，让模型尊重配置的入睡窗口"""

        if not self._pending_sleep_request_matches_session(session_id):
            return ""

        now = datetime.now()
        active_schedule, schedule_source = self._schedule_for_group_id(self._state.pending_sleep_request_group_id)
        if not is_inside_sleep_window(now, active_schedule):
            self._clear_pending_sleep_request()
            return ""

        request_text = self._state.pending_sleep_request_text or "用户建议 Bot 睡觉"
        return (
            "【晚安睡眠管理】刚刚有用户在当前会话建议你睡觉。"
            f"用户原话：{request_text}\n"
            f"当前时间 {now.strftime('%H:%M')} 已经位于{schedule_source}的允许入睡时间内："
            f"{active_schedule.sleep_window_start} 到 {active_schedule.sleep_window_end}。\n"
            f"目标醒来时间配置为：{active_schedule.target_wake_time}。\n"
            "如果当前会话命中了分群配置，分群作息优先级高于全局作息。\n"
            "请把这条建议视为符合配置时间的合理提醒，不要因为“现在太早”“还没到睡觉时间”而拒绝。"
            "你仍然需要结合当前话题、人格和表达风格自己决定是否入睡。"
            "如果你决定入睡，请自然发出一句明确的晚安或睡觉确认；插件会在这句消息发出后进入睡眠。"
            "如果你决定暂时不睡，请自然说明当前还想继续做什么。"
        )

    def _pending_sleep_request_is_active(self) -> bool:
        """判断待确认催睡状态是否仍在有效期内。"""

        if self._state.pending_sleep_request_until <= monotonic():
            self._clear_pending_sleep_request()
            return False
        return True

    def _pending_sleep_request_matches_session(self, session_id: Any) -> bool:
        """判断待确认催睡是否属于当前 Planner 会话。"""

        if not self._pending_sleep_request_is_active():
            return False

        pending_session_id = self._state.pending_sleep_request_session_id
        if not pending_session_id:
            return True
        return isinstance(session_id, str) and session_id == pending_session_id

    def _is_control_command(self, message: dict[str, Any]) -> bool:
        """判断入站消息是否为本插件控制命令"""

        text = normalize_text(extract_text(message))
        if text in self._control_command_names():
            self._allow_control_reply()
            return True
        return False

    def _is_control_reply(self, message: dict[str, Any], processed_plain_text: str = "") -> bool:
        """判断出站消息是否为本插件控制命令的回复"""

        if self._state.control_reply_allowed_until <= monotonic():
            return False
        text = extract_text(message, processed_plain_text)
        return text.startswith("[睡眠管理]")

    def _allow_control_reply(self) -> None:
        """短时间允许插件控制命令发出回复"""

        self._state.control_reply_allowed_until = monotonic() + 5.0

    @staticmethod
    def _message_id(message: dict[str, Any]) -> str:
        """提取消息 ID"""

        return message_id(message)

    @staticmethod
    def _extract_text(message: dict[str, Any], processed_plain_text: str = "") -> str:
        """从 Hook 消息载荷中提取文本"""

        return extract_text(message, processed_plain_text)

    @staticmethod
    def _abort_result(reason: str) -> dict[str, Any]:
        """构造 Hook abort 返回值"""

        return abort_result(reason)

    @staticmethod
    def _format_datetime(value: datetime) -> str:
        """格式化本地时间"""

        return format_datetime(value)
