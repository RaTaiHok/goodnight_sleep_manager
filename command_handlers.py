"""晚安睡眠管理命令处理器"""

from datetime import datetime
from typing import Any

from maibot_sdk import Command

from .core_mixin import ALL_SLEEP_SCOPE


class SleepCommandHandlersMixin:
    """声明插件命令入口"""

    @Command("sleep_status", description="查看晚安睡眠管理状态", pattern=r"^/sleep_status$")
    async def handle_status_command(
        self,
        stream_id: str = "",
        group_id: str = "",
        **kwargs: Any,
    ) -> tuple[bool, str, bool]:
        """查看当前睡眠状态"""

        del kwargs

        self._allow_control_reply()
        command_message = self._message_stub_for_command(stream_id, group_id)
        scope_key, scope_label = self._sleep_scope_for_message(command_message)
        sleep_record = self._active_sleep_record(message=command_message)
        if sleep_record is not None and sleep_record.sleep_until is not None:
            message = (
                "[睡眠管理] 当前正在睡眠\n"
                f"作用域: {sleep_record.scope_label}\n"
                f"预计醒来时间: {self._format_datetime(sleep_record.sleep_until)}\n"
                f"原因: {sleep_record.sleep_reason or '未记录'}\n"
                f"持久化: {'已启用' if self.config.control.persist_sleep_state else '已关闭'}"
            )
        else:
            message = (
                "[睡眠管理] 当前未处于睡眠状态\n"
                f"作用域: {scope_label}\n"
                f"持久化: {'已启用' if self.config.control.persist_sleep_state else '已关闭'}"
            )
        await self.ctx.send.text(message, stream_id)
        return True, message, True

    @Command("sleep_wake", description="手动唤醒晚安睡眠管理", pattern=r"^/sleep_wake$")
    async def handle_wake_command(
        self,
        stream_id: str = "",
        group_id: str = "",
        **kwargs: Any,
    ) -> tuple[bool, str, bool]:
        """手动解除睡眠状态"""

        del kwargs

        self._allow_control_reply()
        command_message = self._message_stub_for_command(stream_id, group_id)
        scope_key, scope_label = self._sleep_scope_for_message(command_message)
        sleep_record = self._active_sleep_record(message=command_message)
        if sleep_record is not None:
            self._wake("手动唤醒", scope_key=sleep_record.scope_key)
            message = f"[睡眠管理] 已手动唤醒\n作用域: {sleep_record.scope_label}"
        else:
            message = f"[睡眠管理] 当前本来就是醒着\n作用域: {scope_label}"
        await self.ctx.send.text(message, stream_id)
        return True, message, True

    @Command("sleep_now", description="按当前作息引导 Bot 自己决定是否入睡", pattern=r"^/sleep_now$")
    async def handle_sleep_now_command(
        self,
        stream_id: str = "",
        group_id: str = "",
        user_id: str = "",
        **kwargs: Any,
    ) -> tuple[bool, str, bool]:
        """在允许入睡时间内记录一次管理员催睡，并放行给主链路判断"""

        del kwargs

        self._allow_control_reply()
        if not self.config.control.force_sleep_commands_enabled:
            message = "[睡眠管理] 管理入睡命令已关闭"
            await self.ctx.send.text(message, stream_id)
            return True, message, True

        if not self._can_use_force_sleep_command(user_id):
            message = "[睡眠管理] 你没有使用管理入睡命令的权限"
            await self.ctx.send.text(message, stream_id)
            return True, message, True

        command_message = self._message_stub_for_command(stream_id, group_id)
        sleep_record = self._active_sleep_record(message=command_message)
        if sleep_record is not None and sleep_record.sleep_until is not None:
            message = (
                "[睡眠管理] 当前已经在睡眠中\n"
                f"作用域: {sleep_record.scope_label}\n"
                f"预计醒来时间: {self._format_datetime(sleep_record.sleep_until)}"
            )
            await self.ctx.send.text(message, stream_id)
            return True, message, True

        now = datetime.now()
        schedule_config, schedule_source = self._schedule_for_message_with_source(command_message)
        if not self._is_inside_sleep_window(now, command_message):
            message = (
                "[睡眠管理] 当前不在允许入睡时间内\n"
                f"生效作息: {schedule_source}\n"
                f"允许入睡: {schedule_config.sleep_window_start} - {schedule_config.sleep_window_end}\n"
                "需要无视时间窗口测试时，请使用 /sleep_force"
            )
            await self.ctx.send.text(message, stream_id)
            return True, message, True

        self._set_pending_sleep_request(command_message, "/sleep_now 管理命令催睡")
        message = (
            "[睡眠管理] 已记录管理员催睡，将交给主链路判断是否入睡\n"
            f"生效作息: {schedule_source}"
        )
        await self.ctx.send.text(message, stream_id)
        return True, message, False

    @Command("sleep_force", description="无视作息窗口让晚安睡眠管理立即入睡", pattern=r"^/sleep_force$")
    async def handle_sleep_force_command(
        self,
        stream_id: str = "",
        group_id: str = "",
        user_id: str = "",
        **kwargs: Any,
    ) -> tuple[bool, str, bool]:
        """无视允许入睡窗口手动触发入睡，用于管理员测试和紧急控制"""

        del kwargs

        return await self._handle_sleep_force_command(
            stream_id=stream_id,
            group_id=group_id,
            user_id=user_id,
        )

    @Command("sleep_forceall", description="无视作息窗口让全部聊天流立即入睡", pattern=r"^/sleep_forceall$")
    async def handle_sleep_forceall_command(
        self,
        stream_id: str = "",
        group_id: str = "",
        user_id: str = "",
        **kwargs: Any,
    ) -> tuple[bool, str, bool]:
        """无视允许入睡窗口，手动触发全部聊天流进入睡眠"""

        del kwargs
        del group_id

        return await self._handle_sleep_force_command(
            stream_id=stream_id,
            group_id="",
            user_id=user_id,
            force_all=True,
        )

    async def _handle_sleep_force_command(
        self,
        *,
        stream_id: str,
        group_id: str,
        user_id: str,
        force_all: bool = False,
    ) -> tuple[bool, str, bool]:
        """执行无视时间窗口的强制入睡命令。"""

        self._allow_control_reply()
        if not self.config.control.force_sleep_commands_enabled:
            message = "[睡眠管理] 管理入睡命令已关闭"
            await self.ctx.send.text(message, stream_id)
            return True, message, True

        if not self._can_use_force_sleep_command(user_id):
            message = "[睡眠管理] 你没有使用管理入睡命令的权限"
            await self.ctx.send.text(message, stream_id)
            return True, message, True

        command_message = self._message_stub_for_command(stream_id, group_id)
        sleep_record = (
            self._active_sleep_record(scope_key=ALL_SLEEP_SCOPE)
            if force_all
            else self._active_sleep_record(message=command_message)
        )
        if sleep_record is not None and sleep_record.sleep_until is not None:
            message = (
                "[睡眠管理] 当前已经在睡眠中\n"
                f"作用域: {sleep_record.scope_label}\n"
                f"预计醒来时间: {self._format_datetime(sleep_record.sleep_until)}"
            )
            await self.ctx.send.text(message, stream_id)
            return True, message, True

        now = datetime.now()
        replaced_count = self._wake_all_sleep_records("/sleep_forceall 覆盖已有睡眠状态") if force_all else 0
        _, schedule_source = (
            (self.config.schedule, "全局配置")
            if force_all
            else self._schedule_for_message_with_source(command_message)
        )

        sleep_until = self._choose_sleep_until(now, None if force_all else command_message)
        reason = "/sleep_forceall 管理命令触发" if force_all else "/sleep_force 管理命令触发"
        if user_id.strip():
            reason = f"{reason}: user={user_id.strip()}"
        if force_all:
            self._enter_sleep(sleep_until, reason, None, scope_key=ALL_SLEEP_SCOPE, scope_label="全部聊天流")
        else:
            self._enter_sleep(sleep_until, reason, command_message)
        message = (
            f"[睡眠管理] 已进入{'全体' if force_all else ''}睡眠\n"
            f"生效作息: {schedule_source}\n"
            f"预计醒来时间: {self._format_datetime(sleep_until)}"
        )
        if replaced_count:
            message = f"{message}\n已覆盖原有睡眠作用域: {replaced_count} 个"
        await self.ctx.send.text(message, stream_id)
        return True, message, True
