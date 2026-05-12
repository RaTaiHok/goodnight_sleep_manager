"""晚安睡眠管理命令处理器"""

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
