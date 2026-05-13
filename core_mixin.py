"""晚安睡眠管理核心逻辑"""

from datetime import datetime
from time import monotonic
from typing import Any

import asyncio

from src.chat.message_receive.chat_manager import chat_manager

from .confirmation_judge import (
    NOT_SLEEP_DECISION,
    SLEEP_DECISION,
    judge_sleep_confirmation,
    should_run_sleep_confirmation_judge,
)
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
from .sleep_review import append_sleep_review_message, generate_sleep_review
from .state import SleepRecord, SleepState
from .state_storage import clear_persisted_sleep_state, load_persisted_sleep_records, save_persisted_sleep_records

GLOBAL_SLEEP_SCOPE = "global"


class SleepCoreMixin:
    """为插件主体提供睡眠状态与判断逻辑"""

    _state: SleepState

    def _init_sleep_state(self) -> None:
        """初始化插件内存状态"""

        self._state = SleepState()

    def _enabled(self) -> bool:
        """返回插件是否启用"""

        return self.config.plugin.enabled

    def _is_sleeping(self, message: dict[str, Any] | None = None, *, session_id: str = "", scope_key: str = "") -> bool:
        """返回指定作用域是否还处于睡眠状态，并在到点后自动醒来"""

        return self._active_sleep_record(message, session_id=session_id, scope_key=scope_key) is not None

    def _enter_sleep(self, sleep_until: datetime, reason: str, message: dict[str, Any] | None = None) -> SleepRecord:
        """进入睡眠状态"""

        scope_key, scope_label = self._sleep_scope_for_message(message)
        session_id = message_session_id(message) if message is not None else ""
        group_id = (message_group_id(message) if message is not None else "") or self._group_id_for_session_id(session_id)
        record = SleepRecord(
            scope_key=scope_key,
            scope_label=scope_label,
            sleep_started_at=datetime.now(),
            sleep_until=sleep_until,
            sleep_reason=reason,
            group_id=group_id,
            session_id=session_id,
        )
        self._state.sleep_records[scope_key] = record
        self._clear_pending_sleep_request()
        self._save_sleep_state()
        self._get_logger().info(
            f"晚安睡眠管理进入睡眠，作用域: {scope_label}，预计醒来: {format_datetime(sleep_until)}，原因: {reason}"
        )
        return record

    def _wake(self, reason: str, message: dict[str, Any] | None = None, *, scope_key: str = "") -> None:
        """退出睡眠状态"""

        target_scope_key = scope_key.strip() or self._sleep_scope_for_message(message)[0]
        record = self._active_sleep_record(scope_key=target_scope_key)
        self._state.clear_sleep(target_scope_key)
        self._clear_pending_sleep_request()
        self._save_sleep_state()
        if record is not None:
            self._get_logger().info(f"晚安睡眠管理已唤醒: scope={record.scope_label} reason={reason}")
            self._schedule_sleep_review(record)

    def _restore_sleep_state(self) -> None:
        """插件加载时从持久化文件恢复未过期的睡眠状态"""

        if not self.config.control.persist_sleep_state:
            self._clear_sleep_state_storage()
            return

        try:
            persisted_records = load_persisted_sleep_records()
        except Exception as exc:
            self._get_logger().warning(f"读取持久化睡眠状态失败，已清理状态文件: {exc}")
            self._clear_sleep_state_storage()
            return

        if not persisted_records:
            return

        now = datetime.now()
        restored_count = 0
        for scope_key, record in persisted_records.items():
            if record.sleep_until is None or now >= record.sleep_until:
                continue
            self._state.sleep_records[scope_key] = record
            restored_count += 1
            self._get_logger().info(
                f"已恢复持久化睡眠状态，作用域: {record.scope_label}，"
                f"预计醒来: {format_datetime(record.sleep_until)}，原因: {record.sleep_reason or '从持久化状态恢复'}"
            )

        self._clear_pending_sleep_request()
        if restored_count:
            self._save_sleep_state()
            return

        self._clear_sleep_state_storage()
        self._get_logger().info("持久化睡眠状态已过期，启动时自动清理")

    def _save_sleep_state(self) -> None:
        """将当前睡眠状态写入持久化文件"""

        if not self.config.control.persist_sleep_state:
            self._clear_sleep_state_storage()
            return
        if not self._state.sleep_records:
            self._clear_sleep_state_storage()
            return

        try:
            save_persisted_sleep_records(self._state.sleep_records)
        except Exception as exc:
            self._get_logger().warning(f"保存持久化睡眠状态失败: {exc}")

    def _clear_sleep_state_storage(self) -> None:
        """清理持久化睡眠状态文件"""

        try:
            clear_persisted_sleep_state()
        except Exception as exc:
            self._get_logger().warning(f"清理持久化睡眠状态失败: {exc}")

    def _handle_plugin_unload(self) -> None:
        """插件卸载时保留未过期睡眠状态，便于重启后恢复"""

        self._prune_expired_sleep_records()
        if self._state.sleep_records:
            if self.config.control.persist_sleep_state:
                self._save_sleep_state()
                self._get_logger().info("晚安睡眠管理卸载，未过期睡眠状态已保留")
            else:
                self._clear_sleep_state_storage()
                self._get_logger().info("晚安睡眠管理卸载，持久化已关闭，未保留睡眠状态")
            return

        self._clear_sleep_state_storage()

    def _active_sleep_record(
        self,
        message: dict[str, Any] | None = None,
        *,
        session_id: str = "",
        scope_key: str = "",
    ) -> SleepRecord | None:
        """返回指定消息、会话或作用域的有效睡眠状态"""

        target_scope_key = scope_key.strip()
        if not target_scope_key:
            if message is not None:
                target_scope_key = self._sleep_scope_for_message(message)[0]
            elif session_id.strip():
                target_scope_key = self._sleep_scope_for_session_id(session_id)[0]
            else:
                self._prune_expired_sleep_records()
                return next(iter(self._state.sleep_records.values()), None)

        record = self._state.sleep_records.get(target_scope_key)
        if record is None:
            return None
        if record.sleep_until is not None and datetime.now() < record.sleep_until:
            return record

        self._expire_sleep_record(target_scope_key, record)
        return None

    def _prune_expired_sleep_records(self) -> None:
        """清理所有已经到点的睡眠状态"""

        now = datetime.now()
        expired_records = [
            (scope_key, record)
            for scope_key, record in self._state.sleep_records.items()
            if record.sleep_until is None or now >= record.sleep_until
        ]
        for scope_key, record in expired_records:
            self._expire_sleep_record(scope_key, record, save=False)
        if expired_records:
            self._save_sleep_state()

    def _expire_sleep_record(self, scope_key: str, record: SleepRecord, *, save: bool = True) -> None:
        """清理单个已经到点的睡眠状态"""

        self._state.clear_sleep(scope_key)
        self._get_logger().info(f"晚安睡眠管理已唤醒: scope={record.scope_label} reason=到达预计醒来时间")
        self._schedule_sleep_review(record)
        if save:
            self._save_sleep_state()

    async def _handle_sleep_request(self, message: dict[str, Any]) -> dict[str, Any] | None:
        """处理用户让 Bot 睡觉的消息"""

        if not self._enabled() or not self.config.sleep_request.enabled or self._is_sleeping(message):
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

        if not self._enabled() or not self.config.control.block_inbound_messages or not self._is_sleeping(message):
            return False
        if self.config.control.control_commands_enabled and self._is_control_command(message):
            return False
        return True

    def _capture_sleep_review_message(self, message: dict[str, Any]) -> None:
        """记录睡眠期间被拦截的消息，供醒来后回顾"""

        if not self._enabled() or not self.config.sleep_review.enabled:
            return

        sleep_record = self._active_sleep_record(message=message)
        if sleep_record is None:
            return
        append_sleep_review_message(message, sleep_record, self._get_logger())

    def _schedule_sleep_review(self, sleep_record: SleepRecord) -> None:
        """醒来后在后台生成睡眠期间聊天回顾"""

        if not self._enabled() or not self.config.sleep_review.enabled:
            return

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            self._get_logger().warning("无法生成睡醒回顾：当前没有运行中的事件循环")
            return

        task_name = f"goodnight_sleep_review_{sleep_record.scope_key.replace(':', '_')}"
        loop.create_task(self._run_sleep_review(sleep_record), name=task_name)

    async def _run_sleep_review(self, sleep_record: SleepRecord) -> None:
        """执行睡醒回顾后台任务，避免异常泄漏到事件循环。"""

        try:
            await generate_sleep_review(self.ctx, sleep_record, self.config.sleep_review, self._get_logger())
        except Exception as exc:
            self._get_logger().warning(f"生成睡醒回顾后台任务失败: scope={sleep_record.scope_label} error={exc}")

    def _should_block_learning(self, session_id: Any = "") -> bool:
        """判断是否需要暂停表达学习"""

        normalized_session_id = str(session_id or "").strip()
        return (
            self._enabled()
            and self.config.control.block_expression_learning
            and self._is_sleeping(session_id=normalized_session_id)
        )

    def _should_block_memory_automation(
        self,
        session_id: Any = "",
        group_id: Any = "",
        message: dict[str, Any] | None = None,
    ) -> bool:
        """判断是否需要暂停自动记忆写回任务入队"""

        if not self._enabled() or not self.config.control.block_memory_automation:
            return False

        if message is not None and self._is_sleeping(message):
            return True

        normalized_group_id = str(group_id or "").strip()
        if normalized_group_id:
            scope_key = self._sleep_scope_for_group_id(normalized_group_id)[0]
            return self._is_sleeping(scope_key=scope_key)

        normalized_session_id = str(session_id or "").strip()
        if normalized_session_id:
            return self._is_sleeping(session_id=normalized_session_id)

        return self._is_sleeping()

    def _should_control_planner(self, session_id: Any = "") -> bool:
        """判断是否需要启用 Planner 兜底保护"""

        normalized_session_id = str(session_id or "").strip()
        return (
            self._enabled()
            and self.config.control.planner_control_enabled
            and self._is_sleeping(session_id=normalized_session_id)
        )

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

        schedule_config, _ = self._schedule_for_message_with_source(message)
        return schedule_config

    def _schedule_for_message_with_source(self, message: dict[str, Any] | None) -> tuple[Any, str]:
        """根据消息所属群聊选择生效的作息配置和来源说明。"""

        if message is None:
            return self.config.schedule, "全局配置"

        group_id = message_group_id(message)
        if not group_id and self._pending_sleep_request_matches_session(message_session_id(message)):
            group_id = self._state.pending_sleep_request_group_id
        if not group_id:
            group_id = self._group_id_for_session_id(message_session_id(message))

        return self._schedule_for_group_id(group_id)

    def _schedule_for_group_id(self, group_id: str) -> tuple[Any, str]:
        """按群号获取分群作息；未命中时回落全局作息"""

        normalized_group_id = group_id.strip()
        group_schedule = self._group_schedule_for_group_id(normalized_group_id)
        if group_schedule is not None:
            return group_schedule, f"群 {normalized_group_id} 分群配置"
        return self.config.schedule, "全局配置"

    def _sleep_scope_for_message(self, message: dict[str, Any] | None) -> tuple[str, str]:
        """根据消息所属群聊决定睡眠状态作用域"""

        if message is None:
            return GLOBAL_SLEEP_SCOPE, "全局配置"
        group_id = message_group_id(message)
        if group_id:
            return self._sleep_scope_for_group_id(group_id)

        session_id = message_session_id(message)
        if session_id:
            return self._sleep_scope_for_session_id(session_id)
        return GLOBAL_SLEEP_SCOPE, "全局配置"

    def _sleep_scope_for_session_id(self, session_id: str) -> tuple[str, str]:
        """根据已有聊天流解析睡眠状态作用域"""

        normalized_session_id = str(session_id or "").strip()
        if not normalized_session_id:
            return GLOBAL_SLEEP_SCOPE, "全局配置"

        group_id = self._group_id_for_session_id(normalized_session_id)
        if group_id:
            return self._sleep_scope_for_group_id(group_id)
        return GLOBAL_SLEEP_SCOPE, "全局配置"

    def _group_id_for_session_id(self, session_id: str) -> str:
        """通过已注册聊天流解析群号。"""

        normalized_session_id = str(session_id or "").strip()
        if not normalized_session_id:
            return ""

        try:
            session = chat_manager.get_existing_session_by_session_id(normalized_session_id)
        except Exception as exc:
            self._get_logger().warning(f"解析会话群号失败: session_id={normalized_session_id} error={exc}")
            return ""
        return str(getattr(session, "group_id", "") or "").strip() if session is not None else ""

    def _sleep_scope_for_group_id(self, group_id: str) -> tuple[str, str]:
        """根据群号决定睡眠状态作用域"""

        normalized_group_id = str(group_id or "").strip()
        if normalized_group_id and self._group_schedule_for_group_id(normalized_group_id) is not None:
            return f"group:{normalized_group_id}", f"群 {normalized_group_id} 分群配置"
        return GLOBAL_SLEEP_SCOPE, "全局配置"

    def _group_schedule_for_group_id(self, group_id: str) -> Any | None:
        """返回群号对应的分群作息配置"""

        normalized_group_id = str(group_id or "").strip()
        if not normalized_group_id:
            return None

        for group_schedule in self.config.group_schedule.group_schedules:
            if not group_schedule.enabled:
                continue
            if group_schedule.group_id.strip() == normalized_group_id:
                return group_schedule
        return None

    def _build_sleep_confirmation_schedule_context(self, message: dict[str, Any]) -> str:
        """构造 AI 入睡确认判定可用的作息上下文"""

        group_id = message_group_id(message)
        if not group_id and self._pending_sleep_request_matches_session(message_session_id(message)):
            group_id = self._state.pending_sleep_request_group_id
        if not group_id:
            group_id = self._group_id_for_session_id(message_session_id(message))

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
        session_id = message_session_id(message)
        group_id = message_group_id(message) or self._group_id_for_session_id(session_id)
        self._state.pending_sleep_request_until = monotonic() + ttl_seconds
        self._state.pending_sleep_request_session_id = session_id
        self._state.pending_sleep_request_group_id = group_id
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
