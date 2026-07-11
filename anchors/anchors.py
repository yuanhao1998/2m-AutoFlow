"""参考图管理器：目录 → 属性映射；Anchor 声明匹配条件。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class ImageRef:
    """对参考图片文件的轻量引用。"""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def __repr__(self) -> str:
        return f"ImageRef({self.path})"

    def __fspath__(self) -> str:
        return str(self.path)


class ImageDirMeta(type):
    """元类：类创建时扫描 path 目录，图片文件映射为 ImageRef 属性。"""

    def __new__(mcs, name, bases, namespace):
        cls = super().__new__(mcs, name, bases, namespace)
        if name == "ImageDir":
            return cls
        cls_path = namespace.get("path", "")
        if cls_path:
            cls._discover(cls_path)
        return cls


class ImageDir(metaclass=ImageDirMeta):
    """声明式参考图管理器。

    子类声明:
        class StoreImages(ImageDir):
            path = "images/store"
        # StoreImages.store_icon -> ImageRef("images/store/store_icon.png")

    或直接实例化:
        d = ImageDir("images/store")
    """

    path: str = ""

    def __init__(self, path: str = "") -> None:
        if path:
            object.__setattr__(self, "path", path)
            self.__class__._discover(path)

    @classmethod
    def _discover(cls, dir_path: str) -> None:
        base = Path(dir_path)
        if not base.is_dir():
            return
        for f in sorted(base.iterdir()):
            if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".bmp"):
                attr = f.stem
                if not hasattr(cls, attr):
                    setattr(cls, attr, ImageRef(f))

    @classmethod
    def list_all(cls) -> list[ImageRef]:
        return [v for v in vars(cls).values() if isinstance(v, ImageRef)]

    @classmethod
    def validate(cls) -> list[str]:
        missing: list[str] = []
        for ref in cls.list_all():
            if not ref.path.exists():
                missing.append(str(ref.path))
        return missing


@dataclass(frozen=True)
class Anchor:
    """匹配锚点：参考图 + 作图坐标搜索区域 + 阈值。"""

    ref: ImageRef
    region: tuple[int, int, int, int] | None = None
    threshold: float = 0.85
