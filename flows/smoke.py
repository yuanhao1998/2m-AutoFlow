"""冒烟流程：用真实游戏界面验证引擎端到端可用。

界面：Home ⇄ Panel，期间可能出现 Popup（自动关闭）。
目标：从 Home 打开 Panel。
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from anchors.anchors import Anchor, ImageDir
from fsm.state import State, Goto, Back, Stay
from fsm.registry import StateRegistry
from target.target import Target

logger = logging.getLogger(__name__)


class SmokeImages(ImageDir):
    path = "images/smoke"


img = SmokeImages()


class Home(State):
    name = "home"
    signature = [Anchor(ref=img.home_sig)]

    def handle(self, ctx):
        logger.info("在 HOME，点击打开面板")
        if not ctx.click(Target.image(Anchor(ref=img.home_open_panel))):
            logger.warning("未匹配到打开面板按钮，本轮将重试")
        ctx.wait(2)
        return Goto(Panel)


class Panel(State):
    name = "panel"
    signature = [Anchor(ref=img.panel_sig)]

    def handle(self, ctx):
        logger.info("已在面板（目标态）")
        return Stay()


class Popup(State):
    name = "popup"
    priority = 100                      # 弹框优先处理
    signature = [Anchor(ref=img.popup_sig)]

    def handle(self, ctx):
        logger.info("检测到弹框 → 关闭")
        if not ctx.click(Target.image(Anchor(ref=img.popup_close))):
            logger.warning("未匹配到关闭弹框按钮，本轮将重试")
        ctx.wait(1)
        return Back()


def build_registry() -> StateRegistry:
    reg = StateRegistry()
    reg.register(Home(), transitions=[Panel])
    reg.register(Panel(), transitions=[Home])
    reg.register(Popup())
    return reg
