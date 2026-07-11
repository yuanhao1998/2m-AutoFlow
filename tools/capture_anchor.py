"""锚点图采集工具：框选截图、保存参考图、生成代码片段。

用法:
  1. 提前截全屏图: python capture_anchor.py                (按 F5 实时截图)
  2. 打开已有截图: python capture_anchor.py screen.png       (查看静态截图)

操作:
  F5        → 截取当前屏幕并加载
  鼠标悬停  → 实时显示物理像素坐标
  拖拽框选  → 显示区域坐标，按 R 保存裁剪图为参考图，按 C 复制坐标
  滚轮      → 缩放
  Ctrl+拖拽 → 平移
  Space     → 取当前坐标生成 Python DSL 代码片段
  ESC       → 退出
"""

import queue
import sys
import threading
import tkinter as tk
from pathlib import Path

from PIL import Image, ImageGrab, ImageTk
from pynput import keyboard


class CaptureAnchor:
    def __init__(self, image_path: str | None = None):
        self._mode = "file" if image_path else "live"
        self._capture_queue: queue.Queue[Image.Image] = queue.Queue()
        self._listener: keyboard.Listener | None = None

        self.root = tk.Tk()
        title = f"锚点采集 — {Path(image_path).name}" if image_path else "锚点采集 — 按 F5 截取屏幕"
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

        tk.Label(self.root,
                 text="F5=截屏  R=保存参考图  C=复制坐标  T=复制点击坐标  Space=生成代码  ESC=退出",
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
        self.root.bind("<space>", lambda e: self._gen_action())
        self.root.bind("<Escape>", lambda e: self.root.destroy())

        self._pan_x = self._pan_y = None
        self._saved_region = None
        self._last_click = None

        if not image_path:
            self._start_hotkey_listener()
            self._poll_capture()

    def _placeholder_image(self) -> Image.Image:
        """创建一个占位图。"""
        w, h = 800, 600
        img = Image.new("RGB", (w, h), (40, 40, 40))
        from PIL import ImageDraw, ImageFont
        draw = ImageDraw.Draw(img)
        draw.text((w // 2 - 120, h // 2 - 10), "按 F5 截取屏幕",
                  fill=(180, 180, 180))
        return img

    def _start_hotkey_listener(self) -> None:
        """在后台线程中启动热键监听。"""
        def on_press(key: keyboard.Key | keyboard.KeyCode | None) -> None:
            try:
                k = key.name if hasattr(key, "name") else key.char
            except AttributeError:
                return
            if k == "f5":
                self._capture_screen()

        self._listener = keyboard.Listener(on_press=on_press)
        self._listener.daemon = True
        self._listener.start()

    def _capture_screen(self) -> None:
        """截取全屏并将图片放入队列。"""
        try:
            img = ImageGrab.grab()
            self._capture_queue.put(img)
        except Exception as e:
            self._capture_queue.put(e)

    def _poll_capture(self) -> None:
        """定时检查截图队列，有新的则更新显示。"""
        try:
            while True:
                item = self._capture_queue.get_nowait()
                if isinstance(item, Image.Image):
                    self._load_new_image(item)
                    self.root.title("坐标工具 — 按 F5 重新截取")
                    self.info_var.set(
                        f"截图已加载: {item.width}×{item.height} "
                        "— 悬停查看坐标 | 框选操作"
                    )
                elif isinstance(item, Exception):
                    self.info_var.set(f"截图失败: {item}")
        except queue.Empty:
            pass
        self.root.after(200, self._poll_capture)

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
        if self._listener:
            self._listener.stop()
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
            info = f"点击 屏幕: ({self.start_x}, {self.start_y})"
            info += " — 按 T 复制坐标，按 Space 生成代码"
            self.info_var.set(info)
            self._saved_region = None
        else:
            self._saved_region = (left, top, right, bottom)
            self._last_click = None
            info = f"区域 屏幕: ({left}, {top}, {right}, {bottom}) {right-left}×{bottom-top}"
            info += " — R保存参考图 C复制坐标"
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

    # ---- 操作 ----
    def _save_crop(self) -> None:
        out_dir = Path("images")
        out_dir.mkdir(exist_ok=True)

        n = 1
        while (out_dir / f"ref_{n}.png").exists():
            n += 1
        path = out_dir / f"ref_{n}.png"

        if self._saved_region:
            left, top, right, bottom = self._saved_region
            crop = self.pil_image.crop((left, top, right, bottom))
            crop.save(path)
            self.info_var.set(f"已保存裁剪图: {path} ({right-left}x{bottom-top})")
        else:
            self.pil_image.save(path)
            self.info_var.set(f"已保存全屏截图: {path} ({self.pil_image.width}x{self.pil_image.height})")

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
        if self._listener:
            self._listener.stop()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        path = sys.argv[1]
        if not Path(path).exists():
            print(f"错误: 图片 {path} 不存在")
            sys.exit(1)
        CaptureAnchor(path).run()
    else:
        print("锚点图采集工具已启动 — 按 F5 截取当前屏幕")
        CaptureAnchor().run()
