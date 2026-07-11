"""截图模块：全屏截图 + 区域裁剪。"""

from PIL import Image, ImageGrab


def fullscreen_screenshot() -> Image.Image:
    """截取 macOS 全屏画面，返回 PIL Image 对象。"""
    img = ImageGrab.grab()
    return img


def crop_region(image: Image.Image, region: tuple[int, int, int, int]) -> Image.Image:
    """从全屏截图中裁剪指定区域。

    Args:
        image: 全屏截图 PIL Image。
        region: (left, top, right, bottom) 像素坐标。

    Returns:
        裁剪后的子图。
    """
    return image.crop(region)
