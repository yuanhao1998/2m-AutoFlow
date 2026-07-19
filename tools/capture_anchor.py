"""锚点图采集工具：框选截图、保存参考图、生成代码片段。

用法:
  1. 实时截图:  python capture_anchor.py [-d 保存目录]
  2. 已有截图:  python capture_anchor.py screen.png [-d 保存目录]

操作:
  F5        → 截取当前屏幕并加载
  鼠标悬停  → 实时显示物理像素坐标
  拖拽框选  → 显示区域坐标，按 R 命名保存参考图，Ctrl+R 仅保存文字区域到 yaml，按 C 复制坐标
  滚轮      → 缩放
  Ctrl+拖拽 → 平移
  Space     → 取当前坐标生成 Python DSL 代码片段
  ESC       → 退出
"""

import argparse
import sys
import threading
import tkinter as tk
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from PIL import Image, ImageGrab, ImageTk

# ---- Quartz 全局热键（macOS 原生，避开 CapsLock / TSM 冲突） ----
_F5_KEYCODE = 96
_tap_instance: "CaptureAnchor | None" = None          # 供 C 回调查找实例


def _tap_callback(_proxy, event_type, event, _refcon):
    """CGEventTap 回调：只关心 keydown，检测到 F5 则发 tkinter 虚拟事件。"""
    import Quartz
    if event_type == Quartz.kCGEventKeyDown:
        code = Quartz.CGEventGetIntegerValueField(event,
                                                  Quartz.kCGKeyboardEventKeycode)
        if code == _F5_KEYCODE and _tap_instance is not None:
            _tap_instance.root.event_generate("<<Capture>>", when="tail")
    return event


def _run_event_tap() -> None:
    """在后台线程中启动 CFRunLoop + CGEventTap（只监听 keydown，不碰 modifier）。"""
    import Quartz
    # CGEventMaskBit(kCGEventKeyDown) → 只关心按键按下，排除 FlagsChanged（CapsLock 等）
    mask = 1 << Quartz.kCGEventKeyDown
    tap = Quartz.CGEventTapCreate(
        Quartz.kCGSessionEventTap,              # 会话级
        Quartz.kCGHeadInsertEventTap,           # 队首
        Quartz.kCGEventTapOptionDefault,        # 需要辅助功能权限
        mask,
        _tap_callback,
        None,
    )
    if tap is None:
        return      # 无辅助功能权限时会返回 None
    source = Quartz.CFMachPortCreateRunLoopSource(None, tap, 0)
    Quartz.CFRunLoopAddSource(Quartz.CFRunLoopGetCurrent(), source,
                              Quartz.kCFRunLoopDefaultMode)
    Quartz.CFRunLoopRun()


def _start_global_hotkey(root: tk.Tk) -> None:
    """启动全局 F5 热键：Quartz 优先，失败则仅保留窗口内 F5 作为降级。"""
    # 注册虚拟事件，无论 Quartz 是否可用均绑定
    root.event_add("<<Capture>>", "None")
    try:
        import Quartz                                           # noqa: F401
        threading.Thread(target=_run_event_tap, daemon=True).start()
    except (ImportError, OSError):
        pass                                                    # 非 macOS 或 Quartz 不可用
    root.bind("<F5>", lambda e: root.event_generate("<<Capture>>", when="tail"))


def _stop_global_hotkey() -> None:
    """停止全局热键监听。"""
    try:
        import Quartz
        Quartz.CFRunLoopStop(Quartz.CFRunLoopGetCurrent())
    except Exception:
        pass
# -------------------------------------------------------------------


class CaptureAnchor:
    def __init__(self, image_path: str | None = None, save_dir: str = "images"):
        self._mode = "file" if image_path else "live"
        self._save_dir = Path(save_dir)

        global _tap_instance
        _tap_instance = self

        self.root = tk.Tk()
        title = f"锚点采集 — {Path(image_path).name}" if image_path else "锚点采集 — F5 截取屏幕"
        self.root.title(title)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        if image_path:
            self.pil_image = Image.open(image_path)
        else:
            self.pil_image = self._placeholder_image()

        self.orig_w = self.pil_image.width
        self.orig_h = self.pil_image.height
        self.scale = 1.0

        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        win_w = min(screen_w, int(screen_w * 0.9))
        win_h = min(screen_h, int(screen_h * 0.85))

        if self.orig_w > win_w or self.orig_h > win_h:
            self.scale = min(win_w / self.orig_w, win_h / self.orig_h)

        self._make_photo()

        canvas_w = min(self.scaled_w, win_w)
        canvas_h = min(self.scaled_h, win_h)

        frame = tk.Frame(self.root)
        frame.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(frame, width=canvas_w, height=canvas_h,
                                cursor="cross",
                                scrollregion=(0, 0, self.scaled_w, self.scaled_h))
        self.hbar = tk.Scrollbar(frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
        self.vbar = tk.Scrollbar(frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=self.hbar.set, yscrollcommand=self.vbar.set)
        self.canvas.grid(row=0, column=0, sticky=tk.NSEW)
        self.hbar.grid(row=1, column=0, sticky=tk.EW)
        self.vbar.grid(row=0, column=1, sticky=tk.NS)
        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=1)

        self.canvas.create_image(0, 0, image=self.photo, anchor=tk.NW, tags="bg")

        self.info_var = tk.StringVar(
            value="按 F5 截取当前屏幕" if not image_path
            else "悬停查看坐标 | 拖拽框选 → R保存参考图 | Space 生成代码"
        )
        tk.Label(self.root, textvariable=self.info_var, font=("", 13), pady=6).pack()

        if not image_path:
            tk.Button(self.root, text="📷 截屏 (F5 全局)", font=("", 12),
                      command=self._capture_and_load).pack(pady=(6, 2))
        tk.Label(self.root,
                 text="R=命名保存  Ctrl+R=保存文字区域  C=复制坐标  T=复制点击坐标  Space=生成代码  ESC=退出",
                 font=("", 11), fg="gray").pack(pady=(0, 2))

        input_frame = tk.Frame(self.root)
        input_frame.pack(pady=(0, 4))
        tk.Label(input_frame, text="坐标:", font=("", 11)).pack(side=tk.LEFT)
        self.coord_entry = tk.Entry(input_frame, width=40, font=("", 11))
        self.coord_entry.pack(side=tk.LEFT, padx=(4, 4))
        self.coord_entry.bind("<Return>", self._on_coord_enter)
        tk.Label(input_frame, text="例: (100,200,300,400)", font=("", 10), fg="gray").pack(side=tk.LEFT)

        self.start_x = self.start_y = None
        self.rect_id = None
        self.point_id = None

        self.canvas.bind("<Motion>", self.on_move)
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Control-ButtonPress-1>", self.on_pan_start)
        self.canvas.bind("<Control-B1-Motion>", self.on_pan)
        self.root.bind("<MouseWheel>", self.on_zoom)
        self.canvas.bind("<MouseWheel>", self.on_zoom)
        self.root.bind("<Button-4>", lambda e: self._zoom_step(1.1))
        self.root.bind("<Button-5>", lambda e: self._zoom_step(0.9))
        self.canvas.bind("<Button-4>", lambda e: self._zoom_step(1.1))
        self.canvas.bind("<Button-5>", lambda e: self._zoom_step(0.9))
        self.root.bind("<r>", lambda e: self._save_crop())
        self.root.bind("<c>", lambda e: self._copy_region())
        self.root.bind("<t>", lambda e: self._copy_click())
        self.root.bind("<Control-r>", lambda e: self._save_text_region())
        self.root.bind("<space>", lambda e: self._gen_action())
        self.root.bind("<Escape>", lambda e: self.root.destroy())

        if not image_path:
            self.root.bind("<<Capture>>", lambda e: self._capture_and_load())
            _start_global_hotkey(self.root)

        self._pan_x = self._pan_y = None
        self._saved_region = None
        self._last_click = None

    def _placeholder_image(self) -> Image.Image:
        """创建一个占位图。"""
        w, h = 800, 600
        img = Image.new("RGB", (w, h), (40, 40, 40))
        from PIL import ImageDraw, ImageFont
        draw = ImageDraw.Draw(img)
        draw.text((w // 2 - 120, h // 2 - 10), "按 F5 截取屏幕",
                  fill=(180, 180, 180))
        return img

    def _capture_and_load(self) -> None:
        """隐藏窗口 → 截取全屏 → 恢复窗口并加载显示。"""
        self.root.withdraw()
        self.root.update_idletasks()
        self.root.after(200, self._do_capture_and_load)

    def _do_capture_and_load(self) -> None:
        try:
            img = ImageGrab.grab()
            self._load_new_image(img)
            self.root.title("坐标工具 — 按 F5 重新截取")
            self.info_var.set(
                f"截图已加载: {img.width}×{img.height} "
                "— 悬停查看坐标 | 框选操作"
            )
        except Exception as e:
            self.info_var.set(f"截图失败: {e}")
        finally:
            self.root.deiconify()

    def _load_new_image(self, img: Image.Image) -> None:
        """加载新的截图并自动缩放以适配窗口。"""
        self.pil_image = img
        self.orig_w = img.width
        self.orig_h = img.height

        # 自动计算缩放比使图片适配窗口
        win_w = self.canvas.winfo_width()
        win_h = self.canvas.winfo_height()
        if win_w > 1 and win_h > 1:
            self.scale = min(win_w / self.orig_w, win_h / self.orig_h, 1.0)
        else:
            screen_w = self.root.winfo_screenwidth()
            screen_h = self.root.winfo_screenheight()
            self.scale = min(screen_w / self.orig_w, screen_h / self.orig_h, 1.0)

        self.rect_id = None
        self.point_id = None
        self._saved_region = None
        self._last_click = None
        self._rebuild_photo()

    def _on_close(self) -> None:
        _stop_global_hotkey()
        self.root.destroy()

    # ---- 坐标转换 ----
    def _to_orig(self, cx: float, cy: float) -> tuple[int, int]:
        return int(cx / self.scale), int(cy / self.scale)

    def _to_canvas(self, ox: int, oy: int) -> tuple[float, float]:
        return ox * self.scale, oy * self.scale

    # ---- 缩放 ----
    def on_zoom(self, event: tk.Event) -> None:
        factor = 1.1 if event.delta > 0 else 0.9
        self._zoom_step(factor)

    def _zoom_step(self, factor: float) -> None:
        new_scale = self.scale * factor
        if new_scale < 0.2 or new_scale > 3.0:
            return
        self.scale = new_scale
        self._rebuild_photo()

    def _make_photo(self) -> None:
        if self.scale == 1.0:
            img = self.pil_image
        else:
            nw = max(1, int(self.orig_w * self.scale))
            nh = max(1, int(self.orig_h * self.scale))
            img = self.pil_image.resize((nw, nh), Image.LANCZOS)
        self.photo = ImageTk.PhotoImage(img)
        self.scaled_w = self.photo.width()
        self.scaled_h = self.photo.height()

    def _rebuild_photo(self) -> None:
        self._make_photo()
        self.canvas.delete("all")
        self.canvas.configure(scrollregion=(0, 0, self.scaled_w, self.scaled_h))
        self.canvas.create_image(0, 0, image=self.photo, anchor=tk.NW, tags="bg")

    # ---- 平移 ----
    def on_pan_start(self, event: tk.Event) -> None:
        self._pan_x, self._pan_y = event.x, event.y

    def on_pan(self, event: tk.Event) -> None:
        if self._pan_x is None:
            return
        dx = self._pan_x - event.x
        dy = self._pan_y - event.y
        self.canvas.xview_scroll(dx, "units")
        self.canvas.yview_scroll(dy, "units")
        self._pan_x, self._pan_y = event.x, event.y

    # ---- 鼠标交互 ----
    def on_move(self, event: tk.Event) -> None:
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        ox, oy = self._to_orig(cx, cy)
        info = f"屏幕: ({ox}, {oy})"
        info += "  — 悬停查看 | 拖拽框选 | F5截屏"
        self.info_var.set(info)

    def on_press(self, event: tk.Event) -> None:
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        self.start_x, self.start_y = self._to_orig(cx, cy)
        if self.rect_id:
            self.canvas.delete(self.rect_id)
            self.rect_id = None

    def on_drag(self, event: tk.Event) -> None:
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        sx, sy = self._to_canvas(self.start_x, self.start_y)
        if self.rect_id:
            self.canvas.delete(self.rect_id)
        self.rect_id = self.canvas.create_rectangle(
            sx, sy, cx, cy, outline="lime", width=2)

    def on_release(self, event: tk.Event) -> None:
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        ox, oy = self._to_orig(cx, cy)
        x1, y1 = self.start_x, self.start_y
        x2, y2 = ox, oy
        left, right = sorted([x1, x2])
        top, bottom = sorted([y1, y2])

        if abs(x2 - x1) < 5 and abs(y2 - y1) < 5:
            self._last_click = (self.start_x, self.start_y)
            self._draw_point(self.start_x, self.start_y)
            gray = self._sample_point(self.start_x, self.start_y)
            info = f"点击 屏幕: ({self.start_x}, {self.start_y})  灰度: {gray:.0f}"
            info += " — 按 T 复制坐标，按 Space 生成代码"
            self.info_var.set(info)
            self._saved_region = None
        else:
            self._saved_region = (left, top, right, bottom)
            self._last_click = None
            gray = self._sample_region(left, top, right, bottom)
            info = f"区域 [{left}, {top}, {right}, {bottom}] {right-left}×{bottom-top}  灰度: {gray:.0f}"
            info += " — R命名保存 Ctrl+R保存文字区域 C复制坐标"
            self.info_var.set(info)

    def _draw_point(self, x: int, y: int) -> None:
        if self.point_id:
            for pid in (self.point_id if isinstance(self.point_id, tuple)
                        else [self.point_id]):
                self.canvas.delete(pid)
        r = max(8, int(10 / self.scale))
        sx, sy = self._to_canvas(x, y)
        p1 = self.canvas.create_line(sx - r, sy, sx + r, sy, fill="red", width=2)
        p2 = self.canvas.create_line(sx, sy - r, sx, sy + r, fill="red", width=2)
        self.point_id = (p1, p2)

    def _sample_region(self, left: int, top: int, right: int, bottom: int) -> float:
        """计算区域平均灰度（0=黑, 255=白）。"""
        crop = self.pil_image.crop((left, top, right, bottom)).convert("L")
        import numpy as np
        return float(np.array(crop, dtype=np.float64).mean())

    def _sample_point(self, x: int, y: int) -> float:
        """获取单点灰度。"""
        try:
            return float(self.pil_image.convert("L").getpixel((x, y)))
        except IndexError:
            return 0.0

    # ---- 操作 ----
    def _save_crop(self) -> None:
        if not self._saved_region:
            self._do_save(is_crop=False)
            return
        left, top, right, bottom = self._saved_region
        name = self._ask_name(
            "保存参考图",
            f"输入图片名（不含扩展名）:\n区域: [{left}, {top}, {right}, {bottom}] {right-left}×{bottom-top}",
            initial=f"{right-left}x{bottom-top}",
        )
        if not name:
            self.info_var.set("已取消保存")
            return
        self._do_save(name, is_crop=True)

    def _save_text_region(self) -> None:
        """Ctrl+R：仅将框选区域写入 regions.yaml，不保存图片（供文字锚点用）。"""
        if not self._saved_region:
            self.info_var.set("请先拖拽框选区域")
            return
        left, top, right, bottom = self._saved_region
        name = self._ask_name(
            "保存文字区域",
            f"输入键名（用于 Anchor 引用）:\n区域: [{left}, {top}, {right}, {bottom}] {right-left}×{bottom-top}",
            initial=f"{right-left}x{bottom-top}",
        )
        if not name:
            self.info_var.set("已取消保存")
            return
        from anchors.anchors import _append_text_region
        _append_text_region(self._save_dir, name, (left, top, right, bottom))
        self.info_var.set(
            f"已写入 {self._save_dir / 'regions.yaml'}: {name}: [{left}, {top}, {right}, {bottom}]")

    def _ask_name(self, title: str, prompt: str, initial: str = "") -> str | None:
        """弹出命名对话框，输入框文字默认全选，直接输入即覆盖。"""
        result: str | None = None
        dlg = tk.Toplevel(self.root)
        dlg.title(title)
        dlg.resizable(False, False)
        dlg.transient(self.root)
        dlg.grab_set()
        tk.Label(dlg, text=prompt, font=("", 12), justify=tk.LEFT).pack(
            padx=20, pady=(16, 8))
        entry = tk.Entry(dlg, width=30, font=("", 13))
        entry.insert(0, initial)
        entry.select_range(0, tk.END)
        entry.pack(padx=20, pady=(0, 12))
        entry.focus_set()

        def on_ok(_event=None):
            nonlocal result
            result = entry.get().strip()
            dlg.destroy()

        def on_cancel(_event=None):
            dlg.destroy()

        btn_frame = tk.Frame(dlg)
        btn_frame.pack(pady=(0, 14))
        tk.Button(btn_frame, text="保存", width=10, command=on_ok).pack(side=tk.LEFT, padx=4)
        tk.Button(btn_frame, text="取消", width=10, command=on_cancel).pack(side=tk.LEFT, padx=4)
        dlg.bind("<Return>", on_ok)
        dlg.bind("<Escape>", on_cancel)
        dlg.protocol("WM_DELETE_WINDOW", on_cancel)
        dlg.update_idletasks()
        px = self.root.winfo_x() + (self.root.winfo_width() - dlg.winfo_width()) // 2
        py = self.root.winfo_y() + (self.root.winfo_height() - dlg.winfo_height()) // 2
        dlg.geometry(f"+{px}+{py}")
        dlg.wait_window()
        return result if result else None

    def _do_save(self, name: str = "", *, is_crop: bool = True) -> None:
        """执行实际保存操作。"""
        self._save_dir.mkdir(parents=True, exist_ok=True)
        if not name:
            n = 1
            while (self._save_dir / f"ref_{n}.png").exists():
                n += 1
            name = f"ref_{n}"
        path = self._save_dir / f"{name}.png"
        if is_crop and self._saved_region:
            left, top, right, bottom = self._saved_region
            crop = self.pil_image.crop((left, top, right, bottom))
            crop.save(path)
            from anchors.anchors import _append_region
            try:
                _append_region(path, (left, top, right, bottom))
                self.info_var.set(
                    f"已保存: {path} ({right-left}x{bottom-top})，region 已写入 regions.yaml")
            except Exception as e:
                self.info_var.set(f"已保存裁剪图: {path}，region 写入失败: {e}")
        else:
            self.pil_image.save(path)
            self.info_var.set(
                f"已保存全屏截图: {path} ({self.pil_image.width}x{self.pil_image.height})")

    def _copy_region(self) -> None:
        if not self._saved_region:
            self.info_var.set("请先拖拽框选区域")
            return
        left, top, right, bottom = self._saved_region
        text = f"({left}, {top}, {right}, {bottom})"
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.info_var.set(f"已复制到剪贴板: {text}")

    def _copy_click(self) -> None:
        if not self._last_click:
            self.info_var.set("请先点击取坐标")
            return
        x, y = self._last_click
        text = f"({x}, {y})"
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.info_var.set(f"已复制点击坐标到剪贴板: {text}")

    def _on_coord_enter(self, _event: tk.Event) -> None:
        raw = self.coord_entry.get().strip()
        try:
            parts = [int(x.strip()) for x in raw.strip("[]()").split(",")]
            if len(parts) != 4:
                raise ValueError
            left, top, right, bottom = parts
        except (ValueError, TypeError):
            self.info_var.set("格式错误，示例: (100,200,300,400)")
            return

        if left >= right or top >= bottom:
            self.info_var.set(f"坐标无效: ({left},{top},{right},{bottom})")
            return

        self._saved_region = (left, top, right, bottom)
        w, h = right - left, bottom - top
        self._fit_region(left, top, w, h)
        self._draw_rect(left, top, right, bottom)
        self.info_var.set(f"定位到 ({left}, {top}, {right}, {bottom})  ({w}×{h})")

    def _draw_rect(self, left: int, top: int, right: int, bottom: int) -> None:
        if self.rect_id:
            self.canvas.delete(self.rect_id)
        sl, st = self._to_canvas(left, top)
        sr, sb = self._to_canvas(right, bottom)
        self.rect_id = self.canvas.create_rectangle(
            sl, st, sr, sb, outline="lime", width=3)

    def _fit_region(self, x: int, y: int, w: int, h: int) -> None:
        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()
        if canvas_w <= 1 or canvas_h <= 1:
            return

        margin = 0.85
        scale_x = canvas_w / max(w, 1) * margin
        scale_y = canvas_h / max(h, 1) * margin
        self.scale = min(scale_x, scale_y, 3.0)
        self._rebuild_photo()

        cx = (x + w / 2) * self.scale
        cy = (y + h / 2) * self.scale
        self.canvas.xview_moveto(max(0, (cx - canvas_w / 2) / self.scaled_w))
        self.canvas.yview_moveto(max(0, (cy - canvas_h / 2) / self.scaled_h))

    def _gen_action(self) -> None:
        """生成 Python DSL 代码片段并打印到终端（屏幕坐标）。"""
        if self._saved_region:
            left, top, right, bottom = self._saved_region

            snippet = f"""
    anchor = Anchor(ref=img.xxx, region=({left}, {top}, {right}, {bottom}))
    ctx.click(Target.image(anchor))
"""
        elif self._last_click:
            x, y = self._last_click
            snippet = f"""
    ctx.click(Target.at({x}, {y}))
"""
        else:
            self.info_var.set("请先框选区域或点击取坐标")
            return

        print("\n" + "=" * 50)
        print("复制以下代码到流程文件（屏幕坐标):")
        print("=" * 50)
        print(snippet)
        self.info_var.set("已生成屏幕坐标代码片段（见终端输出）")

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="锚点图采集工具")
    parser.add_argument("image", nargs="?", default=None,
                        help="要打开的已有截图路径（不传则进入实时截图模式）")
    parser.add_argument("-d", "--dir", dest="save_dir", default="images",
                        help="参考图保存目录，默认 images/")
    args = parser.parse_args()

    if args.image and not Path(args.image).exists():
        print(f"错误: 图片 {args.image} 不存在")
        sys.exit(1)

    print(f"锚点图采集工具已启动 — 保存目录: {args.save_dir}/")
    CaptureAnchor(args.image, save_dir=args.save_dir).run()
