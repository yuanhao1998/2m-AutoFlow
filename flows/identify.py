"""云机信息识别流程：读取云机名称和指定区域文字，记录为 JSON。

用法:
    uv run run.py identify

配置：修改下方 REGIONS，每个字段可指定 region、allowlist、corrections。
"""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from anchors.anchors import ImageDir, Anchor
from fsm.registry import StateRegistry
from fsm.state import State, Done
from fsm.context import Ctx

logger = logging.getLogger(__name__)

# ---- 参考图 ----
class BaseImages(ImageDir):
    path = "images/base"

base_img = BaseImages()

# ---- 输出目录 ----
OUTPUT_DIR = Path("data/identify")

# ---- 要识别的区域配置 ----
# 每个字段:
#   region:     (left, top, right, bottom) 作图坐标
#   allowlist:  限定字符集，如 "0123456789abcdefghijklmnopqrstuvwxyz.-:"
#              省略则不限制；设为 "" 可排除空格（解决 . 识别为空格的问题）
#   corrections: 后处理替换规则 {错误字符: 正确字符}
REGIONS: dict[str, dict] = {
    "云机名称": {
        "region": (6, 8, 89, 62),
    },
    "IP": {
        "region": (1829, 496, 2833, 628),
        "allowlist": "0123456789abcdefghijklmnopqrstuvwxyz.-:/",
    },
    "状态": {
        "region": (2028, 798, 2238, 874),
    },
}

# ---- 全局 OCR 纠错规则 ----
# 在所有字段上自动应用（allowlist 优先于 corrections）
GLOBAL_CORRECTIONS: dict[str, str] = {
    # 数字 0 常被误识别为字母 o（前后有数字时纠正）
    # 由 _fix_ocr_errors() 根据上下文智能处理
}


def _fix_ocr_errors(text: str) -> str:
    """后处理常见 OCR 错误。

    - 数字环境中的 o/O → 0
    - 连续的多个空格 → 单个空格
    """
    # 数字上下文中的 o/O 纠正为 0
    # 模式: 数字o数字, 数字o字母, 开头o数字
    text = re.sub(r"(\d)o(\d)", r"\g<1>0\g<2>", text)
    text = re.sub(r"(\d)o([a-z])", r"\g<1>0\g<2>", text)
    text = re.sub(r"([a-z])o(\d)", r"\g<1>0\g<2>", text)
    text = re.sub(r"(\d)O(\d)", r"\g<1>0\g<2>", text)
    # 合并多余空格
    text = re.sub(r"\s{2,}", " ", text)
    return text


class IdentifyDevice(State):
    """识别当前界面指定区域文字，写入 JSON。"""

    name = "识别云机信息"
    signature = [Anchor(ref=base_img["标定区域"])]

    def handle(self, ctx: Ctx):
        result: dict = {
            "时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        for field, cfg in REGIONS.items():
            screen_region = ctx.calibrator.to_screen_region(cfg["region"])
            allowlist = cfg.get("allowlist")

            raw = ctx.read_text(screen_region, allowlist=allowlist)
            text = raw.strip()

            # 字段级别的自定义纠错规则
            for wrong, correct in cfg.get("corrections", {}).items():
                text = text.replace(wrong, correct)

            # 全局纠错（allowlist 字段跳过，因为字符集已受限）
            if not allowlist:
                text = _fix_ocr_errors(text)

            result[field] = text
            self.log.info("%s: %s", field, text or "(空)")

        self._save(result)
        self.log.info("记录已保存 → %s", OUTPUT_DIR)
        return Done()

    @staticmethod
    def _save(record: dict) -> None:
        """追加一条 JSON 记录。"""
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        filepath = OUTPUT_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.jsonl"
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def build_registry() -> StateRegistry:
    reg = StateRegistry(flow_name="识别流程")
    reg.register(IdentifyDevice())
    return reg
