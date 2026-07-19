# # @Create  : 2026/7/12 01:33
# # @Author  : great
# # @Remark  : 存放所有高优先级的操作，例如：死亡复活、弹框消除等
# from __future__ import annotations
#
# from anchors.anchors import ImageDir, Anchor, ImageRef
# from fsm.context import Ctx
# from fsm.state import State, Signal, Back, Goto, Stay
# from target.target import Target
#
#
# class BaseImages(ImageDir):
#     path = "images/base"
#
#
# base_img = BaseImages()
#
#
# class Death(State):
#     name = "死亡界面"
#     priority = 1000
#     signature = [Anchor(ref=base_img["复活按钮"])]
#
#     def handle(self, ctx) -> Signal:
#         self.log.info("检测到复活按钮")
#         if ctx.click(Target.image(Anchor(ref=base_img["复活按钮"]))):
#             self.log.info("点击复活按钮")
#         ctx.wait(2)
#         return Back()
#
#
# class ExpAndEquipageBackIcon(State):
#     name = "经验及装备寻回图标"
#     priority = 950
#     signature = [Anchor(ref=base_img["寻回图标"])]
#
#     def handle(self, ctx) -> Signal:
#         self.log.info("检测到寻回图标")
#         if ctx.click(Target.image(Anchor(ref=base_img["寻回图标"]))):
#             self.log.info("点击寻回图标")
#         ctx.wait(2)
#         return Goto(ExpAndEquipageBackWindow)
#
#
# class ExpAndEquipageBackWindow(State):
#     name = "经验及装备寻回窗口"
#     signature = [
#         Anchor(ref=base_img["寻回弹框关闭按钮"]),
#         Anchor(text="경험치", ref=base_img["经验寻回标题"]),
#         Anchor(text="장비", ref=base_img["装备寻回标题"])
#     ]
#
#     def handle(self, ctx) -> Signal:
#         self.log.info("检测到寻回弹框打开")
#         if ctx.click(Target.image(Anchor(text="경험치", ref=base_img["经验寻回标题"]))):
#             self.log.info("点击经验寻回标题")
#         ctx.wait(2)
#         return Goto(ExpBackSheet)
#
#
# class ExpBackSheet(State):
#     name = "经验寻回页签"
#     priority = 951
#     signature = [Anchor(ref=base_img["选中经验寻回页签"])]
#
#     def handle(self, ctx) -> Signal:
#         self.log.info("已切换到经验寻回页签")
#         if ctx.find_anchor(Anchor(ref=base_img["无找回目标"])):
#             self.log.info("没有要找回的经验")
#             ctx.click(Target.image(Anchor(base_img["装备寻回标题"])))  # 没有经验找回则切换到装备找回
#             return Goto(EquipageBackSheet)
#
#         return Goto(ExpBackFirstHandle)
#
# def check_and_pay_for_free(ctx: Ctx) -> bool:
#     """
#     判断是否免费支付，免费则确认支付，否则取消
#     """
#     if ctx.find_anchor(Anchor(text="무료", ref=base_img["免费找回"])):
#         ctx.click(Target.image(Anchor(ref=base_img["确认找回"])))
#         ctx.wait(2)
#         return True
#
#     ctx.click(Target.image(Anchor(ref=base_img["取消找回"])))
#     ctx.wait(2)
#     return False
#
# class ExpBackFirstHandle(State):
#     name = "处理第一条经验找回"
#     priority = 952
#     signature = [Anchor(ref=base_img["找回经验图标"])]
#
#     def change_pay(self, ctx: Ctx, ref: ImageRef) -> bool:
#         """
#         切换支付方式
#         """
#         for _ in range(3):
#             if not ctx.find_anchor(Anchor(ref=ref)):
#                 self.log.info("发现支付方式不为%s，切换支付方式" % ref.path)
#                 ctx.click(Target.image(Anchor(ref=ref)))
#                 ctx.wait(2)
#                 break
#         else:
#             self.log.info("流程异常：经验找回时无法切换到%s" % ref.path)
#             return False
#
#         return True
#
#     def choose_first_exp_data(self, ctx: Ctx) -> bool:
#         """
#         选中第一条找回经验
#         """
#         for _ in range(3):
#             ctx.click(Target.image(Anchor(ref=base_img["找回经验图标"])))
#             self.log.info("选择第一条经验")
#             ctx.wait(2)
#
#             brightness = ctx.brightness(ctx.calibrator.to_screen_region(Anchor(ref=base_img["经验支付方式确认"]).region))
#             self.log.info("计算经验支付方式确认按钮灰度，判断是否选中了一条经验，灰度值：%s" % brightness)
#             if brightness > 33:
#                 self.log.info("确认选中经验")
#                 break
#         else:
#             self.log.info("流程异常：无法选中第一条经验")
#             return False
#
#         return True
#
#     def handle(self, ctx) -> Signal:
#         self.log.info("发现一条需找回的经验")
#
#         if not self.change_pay(ctx, base_img["经验找回支付货币1"]):  # 无法切换到钻石支付，直接退出
#             return Goto(EquipageBackSheet)
#
#         if not self.choose_first_exp_data(ctx):  # 无法选中第一条要找回的经验，直接退出
#             return Goto(EquipageBackSheet)
#
#         ctx.click(Target.image(Anchor(ref=base_img["经验支付方式确认"])))
#         ctx.wait(2)
#
#         check_and_pay_for_free(ctx)
#
#         return Back()
#
# class ExpBackConfirmPayWindow(State):
#     name = "经验找回确认支付弹框"
#     priority = 999
#     signature = [
#         Anchor(text="선택한 경험치를 복구하시겠습니까", ref=base_img["经验找回提示文字"]),
#         Anchor(text="지불 금액", ref=base_img["支付提示文字"]),
#         Anchor(text="보유 금액", ref=base_img["余额提示文字"]),
#         Anchor(ref=base_img["取消找回"]),
#         Anchor(ref=base_img["确认找回"])
#     ]
#
#     def handle(self, ctx) -> Signal:
#         check_and_pay_for_free(ctx)
#         return Back()
#
#
# class EquipageBackSheet(State):
#     name = "装备寻回页签"
