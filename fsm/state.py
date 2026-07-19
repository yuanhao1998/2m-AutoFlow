"""声明式状态机：State 基类 + 流程控制信号。"""

from __future__ import annotations

import logging

from anchors.anchors import Anchor
from fsm.context import Ctx


class StateAdapter(logging.LoggerAdapter):
    """在日志消息前自动插入 [StateName] 前缀。"""

    def process(self, msg, kwargs):
        return f"[{self.extra['state']}] {msg}", kwargs


class Signal:
    """流程控制信号基类。"""


class Goto(Signal):
    """期望进入 target 界面（下一轮由识别器确认）。"""

    def __init__(self, target: type["State"]) -> None:
        self.target = target


class Back(Signal):
    """回到上一界面（如处理完弹框）。"""


class Done(Signal):
    """达成目标，结束循环。"""


class Stay(Signal):
    """停留当前界面，下一轮重新识别（用于等待加载）。"""


class State:
    """一个游戏界面。signature 全部命中即判定处于此界面。"""

    name: str = ""
    signature: list[Anchor] | None = None
    priority: int = 0
    flow_name: str = ""             # 由 StateRegistry.register() 自动注入

    @property
    def log(self) -> StateAdapter:
        """返回自动带 [StateName] 前缀的 logger，输出到流程独立日志。"""
        base = logging.getLogger(
            f"flow.{self.flow_name}" if self.flow_name else "flow"
        )
        return StateAdapter(base, {"state": self.name or type(self).__name__})

    def match(self, ctx: Ctx) -> bool:
        """signature 中所有锚点都命中才算处于此界面。"""
        sig = self.signature or []
        return all(ctx.find_anchor(a).matched for a in sig)

    def handle(self, ctx: Ctx) -> Signal:
        """在此界面执行动作并返回信号。子类必须实现。"""
        raise NotImplementedError(f"{type(self).__name__} 未实现 handle()")
