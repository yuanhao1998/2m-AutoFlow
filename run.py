"""game-auto 统一入口：装配并启动冒烟流程。"""

from __future__ import annotations

import logging
from pathlib import Path

from ruamel.yaml import YAML

from conf.log import add_log
from anchors.anchors import Anchor, ImageRef
from calib.calibrator import Calibrator
from fsm.context import Ctx, RunState
from fsm.engine import Engine
from runner.runner import FlowRunner
from flows.smoke import build_registry, Panel

logger = logging.getLogger(__name__)


def _load_cfg() -> dict:
    return YAML(typ="safe").load(open("conf/config.yaml", encoding="utf-8"))


def main() -> None:
    add_log()
    cfg = _load_cfg()
    c = cfg["calib"]
    anchor = Anchor(ref=ImageRef(c["anchor"]), threshold=float(c["threshold"]))
    calibrator = Calibrator(anchor, tuple(c["anchor_authoring_topleft"]),
                            threshold=float(c["threshold"]))

    run_state = RunState()
    ctx = Ctx(calibrator, run_state)
    registry = build_registry()
    eng_cfg = cfg.get("engine", {})
    engine = Engine(registry, ctx,
                    max_steps=int(eng_cfg.get("max_steps", 200)),
                    max_unknown=int(eng_cfg.get("max_unknown", 5)))

    def one_round() -> None:
        ctx.refresh_screenshot()
        if not calibrator.is_valid():
            if not calibrator.calibrate(ctx.screen_bgr):
                logger.error("标定失败，跳过本轮")
                return
        ok = engine.run_until(Panel)
        logger.info("本轮结果: %s", "成功抵达面板" if ok else "失败")

    runner = FlowRunner(run_state, repeat=2,
                        hotkeys=cfg.get("hotkeys"))
    runner.run(one_round)


if __name__ == "__main__":
    main()
