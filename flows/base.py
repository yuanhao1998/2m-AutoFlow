# @Create  : 2026/7/20 01:11
# @Author  : great
# @Remark  : 存放所有高优先级的操作，例如：死亡复活、弹框消除等
from __future__ import annotations

import json
import urllib.request
from datetime import date
from pathlib import Path

from anchors.anchors import ImageDir, Anchor
from fsm.state import State, Signal, Back
from target.target import Target


class BaseImages(ImageDir):
    path = "images/base"


base_img = BaseImages()


class Death(State):
    name = "死亡界面"
    priority = 1000
    signature = [Anchor(ref=base_img["复活按钮"])]

    # ---- 配置（按需修改） ----
    WECOM_WEBHOOK: str = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=15868b74-3418-466d-86bf-0b9adc99d1e0"          # 企业微信机器人 webhook 地址
    MAX_DEATH_PER_DAY: int = 5       # 单台云机每日复活上限
    # -----------------------

    def handle(self, ctx) -> Signal:
        self.log.info("检测到死亡界面")

        # 1. 识别云机名称
        device = self._read_device_name(ctx)
        self.log.info("当前云机: %s", device)

        # 2. 查询今日死亡次数
        death_file = Path("images/base") / f"death-{date.today().isoformat()}.json"
        count = self._get_death_count(death_file, device)
        self.log.info("今日已死亡 %d 次（上限 %d）", count, self.MAX_DEATH_PER_DAY)

        # 3. 判断是否复活
        if count < self.MAX_DEATH_PER_DAY:
            self._record_death(death_file, device)
            if ctx.click(Target.image(Anchor(ref=base_img["复活按钮"]))):
                self.log.info("点击复活按钮")
            ctx.wait(2)
        else:
            self.log.warning("已达今日复活上限，不再点击")
            self._send_wecom_alert(device, count)
            ctx.wait(5)

        return Back()

    # ---- 私有方法 ----

    def _read_device_name(self, ctx) -> str:
        """识别云机名称区域的文字。"""
        r = ctx.calibrator.to_screen_region(base_img["云机名称区域"].region)
        text = ctx.read_text(r)
        return text.strip() or "未知云机"

    @staticmethod
    def _get_death_count(death_file: Path, device: str) -> int:
        if not death_file.exists():
            return 0
        try:
            data = json.loads(death_file.read_text(encoding="utf-8"))
            return data.get(device, 0)
        except Exception:
            return 0

    @staticmethod
    def _record_death(death_file: Path, device: str) -> None:
        data: dict = {}
        if death_file.exists():
            try:
                data = json.loads(death_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        data[device] = data.get(device, 0) + 1
        death_file.parent.mkdir(parents=True, exist_ok=True)
        death_file.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                              encoding="utf-8")

    def _send_wecom_alert(self, device: str, count: int) -> None:
        """通过企业微信 webhook 发送告警。"""
        if not self.WECOM_WEBHOOK:
            self.log.warning("企业微信 webhook 未配置，跳过推送")
            return
        payload = json.dumps({
            "msgtype": "text",
            "text": {
                "content": f"⚠️ 云机 [{device}] 今日死亡已达 {count} 次，请人工处理！"
            }
        }).encode("utf-8")
        try:
            req = urllib.request.Request(
                self.WECOM_WEBHOOK,
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=10)
            self.log.info("企业微信告警已发送")
        except Exception as e:
            self.log.error("企业微信推送失败: %s", e)
