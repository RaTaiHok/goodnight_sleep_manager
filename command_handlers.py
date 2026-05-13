"""晚安睡眠管理命令处理器"""

from datetime import datetime
from typing import Any

from maibot_sdk import Command


class SleepCommandHandlersMixin:
    """声明插件命令入口"""

    @Command("sleep_status", description="查看晚安睡眠管理状态", pattern=r"^/sleep_status$")
    async def handle_status_command(self, stream_id: str = "", **kwargs: Any) -> tuple[bool, str, bool]:
        """查看当前睡眠状态"""

        del kwargs

        self._allow_control_reply()
        if self._is_sleeping() and self._state.sleep_until is not None:
            message = (
                "[睡眠管理] 当前正在睡眠\n"
                f"预计醒来时间: {self._format_datetime(self._state.sleep_until)}\n"
                f"原因: {self._state.sleep_reason or '未记录'}\n"
                f"持久化: {'已启用' if self.config.control.persist_sleep_state else '已关闭'}"
            )
        else:
            message = (
                "[睡眠管理] 当前未处于睡眠状态\n"
                f"持久化: {'已启用' if self.config.control.persist_sleep_state else '已关闭'}"
            )
        await self.ctx.send.text(message, stream_id)
        return True, message, True

    @Command("sleep_wake", description="手动唤醒晚安睡眠管理", pattern=r"^/sleep_wake$")
    async def handle_wake_command(self, stream_id: str = "", **kwargs: Any) -> tuple[bool, str, bool]:
        """手动解除睡眠状态"""

        del kwargs

        self._allow_control_reply()
        if self._is_sleeping():
            self._wake("手动唤醒")
            message = "[睡眠管理] 已手动唤醒"
        else:
            message = "[睡眠管理] 当前本来就是醒着"
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

        if self._is_sleeping() and self._state.sleep_until is not None:
            message = f"[睡眠管理] 当前已经在睡眠中\n预计醒来时间: {self._format_datetime(self._state.sleep_until)}"
            await self.ctx.send.text(message, stream_id)
            return True, message, True

        now = datetime.now()
        command_message = self._message_stub_for_command(stream_id, group_id)
        schedule_config, schedule_source = self._schedule_for_group_id(group_id)
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

    async def _handle_sleep_force_command(
        self,
        *,
        stream_id: str,
        group_id: str,
        user_id: str,
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

        if self._is_sleeping() and self._state.sleep_until is not None:
            message = f"[睡眠管理] 当前已经在睡眠中\n预计醒来时间: {self._format_datetime(self._state.sleep_until)}"
            await self.ctx.send.text(message, stream_id)
            return True, message, True

        now = datetime.now()
        command_message = self._message_stub_for_command(stream_id, group_id)
        _, schedule_source = self._schedule_for_group_id(group_id)

        sleep_until = self._choose_sleep_until(now, command_message)
        reason = "/sleep_force 管理命令触发"
        if user_id.strip():
            reason = f"{reason}: user={user_id.strip()}"
        self._enter_sleep(sleep_until, reason)
        message = (
            "[睡眠管理] 已进入睡眠\n"
            f"生效作息: {schedule_source}\n"
            f"预计醒来时间: {self._format_datetime(sleep_until)}"
        )
        await self.ctx.send.text(message, stream_id)
        return True, message, True
