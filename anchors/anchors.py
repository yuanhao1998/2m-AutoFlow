"""参考图管理器：目录 → 属性映射；Anchor 声明匹配条件。

region 约定：每个图片目录可含一个 regions.yaml 来集中管理搜索区域，
ImageRef 自动从中读取，Anchor 默认继承 ref.region。显式传参则覆盖。

regions.yaml 格式:
    # images/xxx/regions.yaml
    图片名: [left, top, right, bottom]   # 作图坐标搜索区域
    全屏搜的图: null                     # null = 全屏搜索
    不必声明: 跳过                        # 等同于 null = 全屏搜索
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class ImageRef:
    """对参考图片文件的轻量引用，自动从同目录 regions.yaml 读取搜索区域。"""

    __slots__ = ("path", "_regions")

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._regions: dict | None = None  # 懒加载同目录 regions.yaml

    def __repr__(self) -> str:
        return f"ImageRef({self.path})"

    def __fspath__(self) -> str:
        return str(self.path)

    @property
    def region(self) -> tuple[int, int, int, int] | None:
        """从同目录 regions.yaml 读取的搜索区域，未声明则返回 None（全屏搜索）。"""
        if self._regions is None:
            self._regions = _load_regions(self.path.parent)
        v = self._regions.get(self.path.stem)
        return tuple(int(x) for x in v) if v is not None else None


def _load_regions(directory: Path) -> dict:
    """加载目录下的 regions.yaml，不存在或损坏则返回空 dict。"""
    yf = directory / "regions.yaml"
    if not yf.is_file():
        return {}
    try:
        from ruamel.yaml import YAML
        yaml = YAML(typ="safe")
        data = yaml.load(yf.read_text(encoding="utf-8")) or {}
        return dict(data)
    except Exception:
        return {}


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
        # 如果 images/store/regions.yaml 里有 store_icon: [l,t,r,b]
        # 则 StoreImages.store_icon.region 返回该坐标，否则 None

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


def _append_region(save_path: Path, region: tuple[int, int, int, int]) -> None:
    """在 save_path 所在目录的 regions.yaml 中追加一行。供 capture_anchor 调用。"""
    from ruamel.yaml import YAML

    yaml = YAML()
    yf = save_path.parent / "regions.yaml"

    if yf.is_file():
        data = yaml.load(yf.read_text(encoding="utf-8")) or {}
    else:
        data = {}

    data[save_path.stem] = list(region)
    yaml.dump(data, yf)


@dataclass(frozen=True)
class Anchor:
    """匹配锚点：参考图 + 作图坐标搜索区域 + 阈值。

    region 未显式传入时自动从 ref.region（regions.yaml）继承。
    显式传 region 则覆盖 yaml 值。两者均为 None = 全屏搜索。
    """

    ref: ImageRef
    region: tuple[int, int, int, int] | None = None
    threshold: float = 0.85

    def __post_init__(self) -> None:
        if self.region is None:
            object.__setattr__(self, "region", self.ref.region)
