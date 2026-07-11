# game-auto 引擎框架 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从零构建一个分辨率无关、可自愈的视觉自动化引擎框架 game-auto，用真实游戏界面跑通冒烟流程验收。

**Architecture:** 底层截图/匹配/OCR/鼠标 → 一次标定全局仿射变换（origin+scale）建立"作图坐标↔屏幕坐标"映射 → Target 抽象把点击目标解析成屏幕点（锚点相对优先） → 声明式状态机（State signature + handle + Signal）由 Engine 主循环驱动，每轮"截图→识别当前界面→处理→自愈"，弹框/未知态自动恢复。

**Tech Stack:** Python 3.14+, opencv-python-headless, pillow, easyocr, pyautogui, pynput, ruamel.yaml, numpy, pytest。macOS。

## Global Constraints

- Python 3.14+，仅 macOS。
- 依赖限定：pillow, easyocr, pyautogui, pynput, opencv-python-headless, ruamel.yaml, numpy, pytest。不引入其他第三方库。
- 所有 `region` / 作图坐标以「作图分辨率」为基准书写，运行时由 `Calibrator` 换算到屏幕像素；**禁止**再出现手工 `base_width/actual_width/offset/非等比缩放` 配置。
- 坐标系：`vision` 层只认屏幕像素；`calib`/`target` 层负责作图↔屏幕换算。
- 全部注释、日志、docstring 用简体中文（与需求方项目一致）。
- 纯逻辑用 pytest 做 TDD；触硬件/模型的模块（截图、鼠标、EasyOCR、热键）不做单测，由冒烟流程人工验证。
- 每个任务独立可测、独立提交。git 提交信息末尾附：
  `Co-Authored-By: Claude <noreply@anthropic.com>`
- 工作目录：`/Users/yuanhao/Developer/Project/2M_tool/game-auto/`（独立 git，已 `git init`，分支 master）。
- 源参考项目（只读，用于移植）：`/Users/yuanhao/Developer/Project/2M_tool/game-info-identify/`。

---

### Task 1: 项目脚手架与配置

**Files:**
- Create: `game-auto/requirements.txt`
- Create: `game-auto/pytest.ini`
- Create: `game-auto/.gitignore`
- Create: `game-auto/conf/config.yaml`
- Create: `game-auto/conf/log.py`
- Create: `game-auto/conf/__init__.py`
- Create: `game-auto/core/__init__.py`, `calib/__init__.py`, `anchors/__init__.py`, `target/__init__.py`, `fsm/__init__.py`, `runner/__init__.py`, `flows/__init__.py`, `tests/__init__.py`
- Create: `game-auto/README.md`

**Interfaces:**
- Produces: `conf.log.add_log(config_path=None, log_file=None)`；`conf/config.yaml` 内含 `screen.authoring_width/height`、`calib.*`、`match.threshold`、`engine.max_steps/max_unknown`、`wait.jitter`、`mouse.*`、`hotkeys.*`、`logging.level`。

- [ ] **Step 1: 创建 requirements.txt**

```
pillow
easyocr
pyautogui
pynput
opencv-python-headless
ruamel.yaml
numpy
pytest
```

- [ ] **Step 2: 创建 pytest.ini**

```ini
[pytest]
testpaths = tests
python_files = test_*.py
addopts = -q
```

- [ ] **Step 3: 创建 .gitignore**

```
__pycache__/
*.pyc
logs/
data/
debug/
.venv/
.DS_Store
```

- [ ] **Step 4: 创建 conf/config.yaml**

```yaml
# game-auto 运行时配置

screen:
  authoring_width: 5120      # 作图分辨率（采集锚点图时的屏幕宽）
  authoring_height: 2880     # 作图分辨率（采集锚点图时的屏幕高）

calib:
  anchor: images/calib/anchor.png      # 标定锚点图路径
  anchor_authoring_topleft: [0, 0]     # 该锚点图左上角在作图分辨率下的坐标
  coarse_scales_min: 0.40              # 标定粗扫缩放比下限
  coarse_scales_max: 1.20              # 标定粗扫缩放比上限
  coarse_scales_step: 0.02             # 标定粗扫步长
  threshold: 0.80                      # 标定匹配阈值

match:
  threshold: 0.85            # 模板匹配默认阈值

engine:
  max_steps: 200             # 主循环最大步数
  max_unknown: 5             # 连续未知态最大次数，超过则中止

wait:
  jitter: 0.5                # 等待抖动比例，0=精确

mouse:
  move_duration: 0.15
  move_duration_jitter: 0.5
  move_jitter: 200
  overshoot_prob: 0.6
  overshoot_range: 40

hotkeys:
  start: f5
  pause: f6
  stop: f7
  exit: esc

logging:
  level: INFO
```

- [ ] **Step 5: 移植 conf/log.py**

从源项目复制并保持不变（路径基于本项目 `conf/`）：

```bash
cp /Users/yuanhao/Developer/Project/2M_tool/game-info-identify/conf/log.py \
   /Users/yuanhao/Developer/Project/2M_tool/game-auto/conf/log.py
```

- [ ] **Step 6: 创建各包 __init__.py（空文件）与 README**

`conf/__init__.py`、`core/__init__.py`、`calib/__init__.py`、`anchors/__init__.py`、`target/__init__.py`、`fsm/__init__.py`、`runner/__init__.py`、`flows/__init__.py`、`tests/__init__.py` 均为空文件。

`README.md`：

```markdown
# game-auto

分辨率无关、可自愈的视觉自动化引擎。锚点相对定位 + 声明式状态机。

设计文档见 `docs/superpowers/specs/`，实现计划见 `docs/superpowers/plans/`。

## 运行
    pip install -r requirements.txt
    python run.py

## 测试
    pytest
```

- [ ] **Step 7: 验证 pytest 能启动**

Run: `cd /Users/yuanhao/Developer/Project/2M_tool/game-auto && python -m pytest`
Expected: `no tests ran`（退出码 5，无报错即可）。

- [ ] **Step 8: 提交**

```bash
cd /Users/yuanhao/Developer/Project/2M_tool/game-auto
git add -A
git commit -m "chore: 项目脚手架 + 配置 + 日志

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2: 截图层 core/capture.py

**Files:**
- Create: `game-auto/core/capture.py`

**Interfaces:**
- Produces: `fullscreen_screenshot() -> PIL.Image`；`crop_region(image, region) -> PIL.Image`。

- [ ] **Step 1: 移植 capture.py**

从源项目复制，保持不变：

```bash
cp /Users/yuanhao/Developer/Project/2M_tool/game-info-identify/core/capture.py \
   /Users/yuanhao/Developer/Project/2M_tool/game-auto/core/capture.py
```

- [ ] **Step 2: 冒烟验证（人工）**

Run: `cd /Users/yuanhao/Developer/Project/2M_tool/game-auto && python -c "from core.capture import fullscreen_screenshot; im=fullscreen_screenshot(); print(im.size)"`
Expected: 打印当前屏幕分辨率（如 `(3426, 2168)`），无异常。

- [ ] **Step 3: 提交**

```bash
git add core/capture.py
git commit -m "feat: 截图层 core/capture

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3: 参考图管理 anchors/anchors.py

**Files:**
- Create: `game-auto/anchors/anchors.py`
- Test: `game-auto/tests/test_anchors.py`

**Interfaces:**
- Produces:
  - `ImageRef(path: Path)`，属性 `.path`，支持 `os.fspath`。
  - `ImageDir`（元类自动发现子类 `path` 目录下图片 → `ImageRef` 属性）；类方法 `list_all() -> list[ImageRef]`、`validate() -> list[str]`。
  - `Anchor`（**frozen dataclass**）：`ref: ImageRef`, `region: tuple[int,int,int,int] | None = None`, `threshold: float = 0.85`。region 为作图坐标。

- [ ] **Step 1: 写失败测试 tests/test_anchors.py**

```python
from pathlib import Path

from PIL import Image

from anchors.anchors import ImageRef, ImageDir, Anchor


def test_imagedir_discovers_png(tmp_path):
    (tmp_path / "btn_ok.png").write_bytes(b"")
    Image.new("RGB", (4, 4)).save(tmp_path / "btn_ok.png")
    Image.new("RGB", (4, 4)).save(tmp_path / "btn_cancel.png")

    d = ImageDir(str(tmp_path))
    assert isinstance(d.btn_ok, ImageRef)
    assert d.btn_ok.path.name == "btn_ok.png"
    names = {r.path.name for r in ImageDir.list_all.__func__(type(d))} if False else \
            {r.path.name for r in d.__class__.list_all()}
    assert "btn_cancel.png" in names


def test_imageref_fspath(tmp_path):
    p = tmp_path / "x.png"
    Image.new("RGB", (2, 2)).save(p)
    ref = ImageRef(p)
    import os
    assert os.fspath(ref) == str(p)


def test_anchor_defaults_and_frozen():
    ref = ImageRef(Path("images/x.png"))
    a = Anchor(ref=ref)
    assert a.region is None
    assert a.threshold == 0.85
    # frozen → 可哈希（供状态机字典使用）
    assert hash(a) == hash(Anchor(ref=ref))
    b = Anchor(ref=ref, region=(1, 2, 3, 4), threshold=0.9)
    assert b.region == (1, 2, 3, 4)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_anchors.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'anchors.anchors'`）。

- [ ] **Step 3: 实现 anchors/anchors.py**

```python
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
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_anchors.py -v`
Expected: PASS（3 passed）。

- [ ] **Step 5: 提交**

```bash
git add anchors/anchors.py tests/test_anchors.py
git commit -m "feat: 参考图管理 ImageDir + Anchor

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 4: 多尺度模板匹配 core/vision.py

**Files:**
- Create: `game-auto/core/vision.py`
- Test: `game-auto/tests/test_vision.py`

**Interfaces:**
- Consumes: 无（纯 numpy/cv2）。
- Produces:
  - `Match`（dataclass）：`matched: bool`, `confidence: float`, `box: tuple[int,int,int,int]`（屏幕像素 l,t,r,b）, `scale: float`；属性 `center -> tuple[int,int]`。
  - `to_bgr(pil_image) -> np.ndarray`。
  - `load_bgr(path) -> np.ndarray`。
  - `match_template(screen_bgr, template_bgr, *, region=None, threshold=0.85, scales=None) -> Match`。`region` 为屏幕像素；`scales=None` 时默认 `[1.0]`。

- [ ] **Step 1: 写失败测试 tests/test_vision.py**

```python
import numpy as np
import cv2

from core.vision import Match, match_template


def _patch(size):
    """构造有方差的图案块（左白右黑），避免 TM_CCOEFF_NORMED 除零。"""
    p = np.zeros((size, size, 3), dtype=np.uint8)
    p[:, : size // 2] = 255
    return p


def test_match_center_property():
    m = Match(matched=True, confidence=0.9, box=(10, 20, 30, 40), scale=1.0)
    assert m.center == (20, 30)


def test_match_same_scale():
    screen = np.zeros((100, 120, 3), dtype=np.uint8)
    patch = _patch(20)
    screen[40:60, 30:50] = patch
    m = match_template(screen, patch, scales=[1.0], threshold=0.9)
    assert m.matched
    assert m.box == (30, 40, 50, 60)
    assert m.center == (40, 50)
    assert m.scale == 1.0


def test_match_multiscale_finds_2x():
    screen = np.zeros((200, 200, 3), dtype=np.uint8)
    patch = _patch(20)
    big = cv2.resize(patch, (40, 40))
    screen[60:100, 80:120] = big
    m = match_template(screen, patch, scales=[0.5, 1.0, 2.0], threshold=0.9)
    assert m.matched
    assert m.scale == 2.0
    assert m.center == (100, 80)


def test_region_offsets_back_to_screen_coords():
    screen = np.zeros((100, 100, 3), dtype=np.uint8)
    patch = _patch(10)
    screen[70:80, 60:70] = patch
    m = match_template(screen, patch, region=(50, 50, 100, 100),
                       scales=[1.0], threshold=0.9)
    assert m.matched
    assert m.box == (60, 70, 70, 80)


def test_no_match_below_threshold():
    screen = np.zeros((50, 50, 3), dtype=np.uint8)
    patch = _patch(10)  # screen 全黑，patch 半白 → 低相关
    m = match_template(screen, patch, scales=[1.0], threshold=0.9)
    assert not m.matched
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_vision.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'core.vision'`）。

- [ ] **Step 3: 实现 core/vision.py**

```python
"""多尺度模板匹配。vision 层只认屏幕像素坐标。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


@dataclass
class Match:
    """模板匹配结果。box 为屏幕像素 (left, top, right, bottom)。"""

    matched: bool
    confidence: float
    box: tuple[int, int, int, int]
    scale: float

    @property
    def center(self) -> tuple[int, int]:
        left, top, right, bottom = self.box
        return ((left + right) // 2, (top + bottom) // 2)


def to_bgr(image: Image.Image) -> np.ndarray:
    """PIL Image → OpenCV BGR numpy 数组。"""
    return cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2BGR)


def load_bgr(path) -> np.ndarray:
    """从文件加载为 BGR numpy 数组。"""
    return to_bgr(Image.open(Path(path)))


def match_template(screen_bgr: np.ndarray, template_bgr: np.ndarray, *,
                   region: tuple[int, int, int, int] | None = None,
                   threshold: float = 0.85,
                   scales: list[float] | None = None) -> Match:
    """在 screen 内按一组 scales 缩放 template 匹配，取最高分。

    Args:
        screen_bgr: 屏幕截图（BGR）。
        template_bgr: 模板图（BGR，作图分辨率原尺寸）。
        region: 屏幕像素搜索区域 (l,t,r,b)，None=全图。
        threshold: 命中阈值。
        scales: 模板缩放比列表，None 默认 [1.0]。

    Returns:
        Match，box 已换算回屏幕像素。
    """
    scales = scales or [1.0]

    if region is not None:
        left = max(0, region[0])
        top = max(0, region[1])
        right = min(screen_bgr.shape[1], region[2])
        bottom = min(screen_bgr.shape[0], region[3])
        sub = screen_bgr[top:bottom, left:right]
        off_x, off_y = left, top
    else:
        sub = screen_bgr
        off_x, off_y = 0, 0

    best = Match(matched=False, confidence=-1.0, box=(0, 0, 0, 0), scale=1.0)
    for s in scales:
        tw = max(1, int(round(template_bgr.shape[1] * s)))
        th = max(1, int(round(template_bgr.shape[0] * s)))
        if th > sub.shape[0] or tw > sub.shape[1]:
            continue
        tmpl = template_bgr if s == 1.0 else cv2.resize(template_bgr, (tw, th))
        result = cv2.matchTemplate(sub, tmpl, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        if max_val > best.confidence:
            x, y = max_loc
            box = (x + off_x, y + off_y, x + off_x + tw, y + off_y + th)
            best = Match(matched=max_val >= threshold,
                         confidence=float(max_val), box=box, scale=float(s))
    return best
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_vision.py -v`
Expected: PASS（5 passed）。

- [ ] **Step 5: 提交**

```bash
git add core/vision.py tests/test_vision.py
git commit -m "feat: 多尺度模板匹配 core/vision

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 5: 标定 calib/calibrator.py

**Files:**
- Create: `game-auto/calib/calibrator.py`
- Test: `game-auto/tests/test_calibrator.py`

**Interfaces:**
- Consumes: `anchors.anchors.Anchor`, `core.vision.Match / match_template / load_bgr`。
- Produces:
  - `Calibrator(anchor, authoring_topleft, *, coarse_scales=None, threshold=0.80, matcher=match_template, loader=load_bgr, capture=None)`。
  - 属性 `.scale: float`, `.origin: tuple[int,int]`。
  - 方法 `calibrate(screen_bgr=None) -> bool`、`to_screen(x, y) -> tuple[int,int]`、`to_screen_region(region) -> tuple[int,int,int,int]`、`is_valid() -> bool`、`invalidate() -> None`。
  - `屏幕px = origin + 作图px × scale`。

- [ ] **Step 1: 写失败测试 tests/test_calibrator.py**

```python
import numpy as np

from anchors.anchors import Anchor, ImageRef
from core.vision import Match
from calib.calibrator import Calibrator


def _dummy_anchor():
    return Anchor(ref=ImageRef("images/calib/anchor.png"), threshold=0.8)


def test_calibrate_computes_scale_and_origin():
    def fake_matcher(screen, template, *, region=None, threshold=0.85, scales=None):
        return Match(matched=True, confidence=0.99, box=(100, 140, 150, 170), scale=0.5)

    c = Calibrator(
        anchor=_dummy_anchor(),
        authoring_topleft=(50, 60),
        coarse_scales=[0.5],
        matcher=fake_matcher,
        loader=lambda p: np.zeros((10, 10, 3), dtype=np.uint8),
        capture=lambda: np.zeros((300, 300, 3), dtype=np.uint8),
    )
    assert c.calibrate() is True
    assert c.scale == 0.5
    # origin = 命中左上角 - 作图左上角 × scale = (100-25, 140-30)
    assert c.origin == (75, 110)
    assert c.is_valid()


def test_to_screen_transform():
    def fake_matcher(screen, template, *, region=None, threshold=0.85, scales=None):
        return Match(matched=True, confidence=0.99, box=(100, 140, 150, 170), scale=0.5)

    c = Calibrator(_dummy_anchor(), (50, 60), coarse_scales=[0.5],
                   matcher=fake_matcher,
                   loader=lambda p: np.zeros((10, 10, 3), dtype=np.uint8),
                   capture=lambda: np.zeros((300, 300, 3), dtype=np.uint8))
    c.calibrate()
    assert c.to_screen(0, 0) == (75, 110)
    assert c.to_screen(50, 60) == (100, 140)      # 应回到命中左上角
    assert c.to_screen_region((0, 0, 50, 60)) == (75, 110, 100, 140)


def test_calibrate_fail_returns_false():
    def fail_matcher(screen, template, *, region=None, threshold=0.85, scales=None):
        return Match(matched=False, confidence=0.1, box=(0, 0, 0, 0), scale=1.0)

    c = Calibrator(_dummy_anchor(), (0, 0), coarse_scales=[1.0],
                   matcher=fail_matcher,
                   loader=lambda p: np.zeros((10, 10, 3), dtype=np.uint8),
                   capture=lambda: np.zeros((50, 50, 3), dtype=np.uint8))
    assert c.calibrate() is False
    assert not c.is_valid()


def test_invalidate():
    def fake_matcher(screen, template, *, region=None, threshold=0.85, scales=None):
        return Match(matched=True, confidence=0.99, box=(0, 0, 10, 10), scale=1.0)

    c = Calibrator(_dummy_anchor(), (0, 0), coarse_scales=[1.0],
                   matcher=fake_matcher,
                   loader=lambda p: np.zeros((5, 5, 3), dtype=np.uint8),
                   capture=lambda: np.zeros((50, 50, 3), dtype=np.uint8))
    c.calibrate()
    assert c.is_valid()
    c.invalidate()
    assert not c.is_valid()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_calibrator.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'calib.calibrator'`）。

- [ ] **Step 3: 实现 calib/calibrator.py**

```python
"""全局仿射标定：一次匹配标定锚点，建立作图坐标↔屏幕坐标映射。

关系: 屏幕px = origin + 作图px × scale （同布局仅等比缩放场景）。
"""

from __future__ import annotations

import logging
from collections.abc import Callable

import numpy as np

from anchors.anchors import Anchor
from core.vision import Match, match_template, load_bgr

logger = logging.getLogger(__name__)


class Calibrator:
    """标定器：求 scale 与 origin，并做坐标换算。"""

    def __init__(self, anchor: Anchor, authoring_topleft: tuple[int, int], *,
                 coarse_scales: list[float] | None = None,
                 threshold: float = 0.80,
                 matcher: Callable = match_template,
                 loader: Callable = load_bgr,
                 capture: Callable | None = None) -> None:
        self._anchor = anchor
        self._authoring_topleft = authoring_topleft
        self._coarse_scales = coarse_scales or _default_scales()
        self._threshold = threshold
        self._matcher = matcher
        self._loader = loader
        self._capture = capture
        self.scale: float = 1.0
        self.origin: tuple[int, int] = (0, 0)
        self._valid = False

    def calibrate(self, screen_bgr: np.ndarray | None = None) -> bool:
        """匹配标定锚点，计算 scale/origin。成功返回 True。"""
        if screen_bgr is None:
            screen_bgr = self._grab()
        template = self._loader(self._anchor.ref.path)
        m: Match = self._matcher(screen_bgr, template,
                                 threshold=self._threshold,
                                 scales=self._coarse_scales)
        if not m.matched:
            logger.error("标定失败：未匹配到标定锚点（置信度 %.3f）", m.confidence)
            self._valid = False
            return False
        self.scale = m.scale
        ax, ay = self._authoring_topleft
        self.origin = (round(m.box[0] - ax * m.scale),
                       round(m.box[1] - ay * m.scale))
        self._valid = True
        logger.info("标定成功：scale=%.4f origin=%s (置信度 %.3f)",
                    self.scale, self.origin, m.confidence)
        return True

    def to_screen(self, x: int, y: int) -> tuple[int, int]:
        """作图坐标 → 屏幕像素。"""
        ox, oy = self.origin
        return (round(ox + x * self.scale), round(oy + y * self.scale))

    def to_screen_region(self, region: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
        """作图区域 → 屏幕像素区域。"""
        left, top = self.to_screen(region[0], region[1])
        right, bottom = self.to_screen(region[2], region[3])
        return (left, top, right, bottom)

    def is_valid(self) -> bool:
        return self._valid

    def invalidate(self) -> None:
        self._valid = False

    def _grab(self) -> np.ndarray:
        if self._capture is not None:
            return self._capture()
        from core.capture import fullscreen_screenshot
        from core.vision import to_bgr
        return to_bgr(fullscreen_screenshot())


def _default_scales() -> list[float]:
    """从 config.yaml 读取粗扫尺度范围，失败则用内置默认。"""
    lo, hi, step = 0.40, 1.20, 0.02
    try:
        from pathlib import Path
        from ruamel.yaml import YAML
        cfg_path = Path("conf/config.yaml")
        if cfg_path.exists():
            yaml = YAML(typ="safe")
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = (yaml.load(f) or {}).get("calib", {})
            lo = float(cfg.get("coarse_scales_min", lo))
            hi = float(cfg.get("coarse_scales_max", hi))
            step = float(cfg.get("coarse_scales_step", step))
    except Exception:
        pass
    n = int(round((hi - lo) / step)) + 1
    return [round(lo + i * step, 4) for i in range(max(1, n))]
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_calibrator.py -v`
Expected: PASS（4 passed）。

- [ ] **Step 5: 提交**

```bash
git add calib/calibrator.py tests/test_calibrator.py
git commit -m "feat: 全局仿射标定 Calibrator

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 6: 点击目标抽象 target/target.py

**Files:**
- Create: `game-auto/target/target.py`
- Test: `game-auto/tests/test_target.py`

**Interfaces:**
- Consumes: `anchors.anchors.Anchor`, `core.vision.Match`；解析时依赖 ctx 提供 `find_anchor(anchor) -> Match` 与 `calibrator`（含 `to_screen`）。
- Produces:
  - `Target`，静态构造 `Target.image(anchor, *, region=None, offset=(0,0))`、`Target.rel(anchor, dx, dy)`、`Target.at(x, y)`。
  - `Target.resolve(ctx) -> tuple[int,int] | None`。
  - 语义：`image` 匹配锚点→点其中心+`offset×scale`；`rel` 匹配锚点→中心+`(dx,dy)×scale`；`at` 作图坐标经 `ctx.calibrator.to_screen`。匹配失败返回 None。

- [ ] **Step 1: 写失败测试 tests/test_target.py**

```python
from anchors.anchors import Anchor, ImageRef
from core.vision import Match
from target.target import Target


class FakeCal:
    def to_screen(self, x, y):
        return (x + 100, y + 200)


class FakeCtx:
    def __init__(self, match=None):
        self._match = match
        self.calibrator = FakeCal()

    def find_anchor(self, anchor):
        return self._match


A = Anchor(ref=ImageRef("images/x.png"))
HIT = Match(matched=True, confidence=0.9, box=(10, 20, 30, 40), scale=2.0)  # center (20,30)
MISS = Match(matched=False, confidence=0.1, box=(0, 0, 0, 0), scale=1.0)


def test_image_clicks_center_plus_scaled_offset():
    t = Target.image(A, offset=(5, -5))
    assert t.resolve(FakeCtx(match=HIT)) == (20 + 10, 30 - 10)  # offset×scale=±10


def test_image_returns_none_when_not_matched():
    assert Target.image(A).resolve(FakeCtx(match=MISS)) is None


def test_rel_offset_scaled():
    t = Target.rel(A, 10, 0)
    assert t.resolve(FakeCtx(match=HIT)) == (20 + 20, 30)  # 10×2.0


def test_at_uses_calibrator():
    t = Target.at(3, 4)
    assert t.resolve(FakeCtx()) == (103, 204)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_target.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'target.target'`）。

- [ ] **Step 3: 实现 target/target.py**

```python
"""点击目标抽象：锚点相对定位为主，作图坐标兜底。"""

from __future__ import annotations

from anchors.anchors import Anchor


class Target:
    """一个待点击目标，resolve(ctx) 得到屏幕像素点。"""

    _IMAGE = "image"
    _REL = "rel"
    _AT = "at"

    def __init__(self, kind: str, *, anchor: Anchor | None = None,
                 offset: tuple[int, int] = (0, 0),
                 point: tuple[int, int] | None = None) -> None:
        self._kind = kind
        self._anchor = anchor
        self._offset = offset
        self._point = point

    @staticmethod
    def image(anchor: Anchor, *, offset: tuple[int, int] = (0, 0)) -> "Target":
        """匹配 anchor → 点击其中心 + offset×scale。"""
        return Target(Target._IMAGE, anchor=anchor, offset=offset)

    @staticmethod
    def rel(anchor: Anchor, dx: int, dy: int) -> "Target":
        """匹配 anchor → 点击 中心 + (dx,dy)×scale。"""
        return Target(Target._REL, anchor=anchor, offset=(dx, dy))

    @staticmethod
    def at(x: int, y: int) -> "Target":
        """作图坐标 → 经标定变换为屏幕坐标。"""
        return Target(Target._AT, point=(x, y))

    def resolve(self, ctx) -> tuple[int, int] | None:
        """返回屏幕像素点击点；匹配失败返回 None。"""
        if self._kind == Target._AT:
            return ctx.calibrator.to_screen(*self._point)

        m = ctx.find_anchor(self._anchor)
        if not m.matched:
            return None
        cx, cy = m.center
        dx, dy = self._offset
        return (cx + round(dx * m.scale), cy + round(dy * m.scale))
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_target.py -v`
Expected: PASS（4 passed）。

- [ ] **Step 5: 提交**

```bash
git add target/target.py tests/test_target.py
git commit -m "feat: 点击目标抽象 Target

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 7: 状态与信号 fsm/state.py

**Files:**
- Create: `game-auto/fsm/state.py`
- Test: `game-auto/tests/test_state.py`

**Interfaces:**
- Consumes: `anchors.anchors.Anchor`；`match()` 依赖 ctx 提供 `find_anchor(anchor) -> Match`。
- Produces:
  - `Signal` 基类；`Goto(target: type[State])`、`Back()`、`Done()`、`Stay()`。
  - `State` 基类：类属性 `name: str = ""`, `signature: list[Anchor] = []`, `priority: int = 0`；方法 `match(ctx) -> bool`（signature 全部命中）、`handle(ctx) -> Signal`（子类实现，基类 raise NotImplementedError）。

- [ ] **Step 1: 写失败测试 tests/test_state.py**

```python
from anchors.anchors import Anchor, ImageRef
from core.vision import Match
from fsm.state import State, Signal, Goto, Back, Done, Stay


A1 = Anchor(ref=ImageRef("a1.png"))
A2 = Anchor(ref=ImageRef("a2.png"))
HIT = Match(True, 0.9, (0, 0, 1, 1), 1.0)
MISS = Match(False, 0.1, (0, 0, 0, 0), 1.0)


class FakeCtx:
    def __init__(self, mapping):
        self.mapping = mapping

    def find_anchor(self, a):
        return self.mapping[a]


class Panel(State):
    name = "panel"
    signature = [A1, A2]

    def handle(self, ctx):
        return Done()


def test_match_all_anchors_hit():
    ctx = FakeCtx({A1: HIT, A2: HIT})
    assert Panel().match(ctx) is True


def test_match_fails_when_any_miss():
    ctx = FakeCtx({A1: HIT, A2: MISS})
    assert Panel().match(ctx) is False


def test_signals_carry_target():
    assert isinstance(Goto(Panel), Signal)
    assert Goto(Panel).target is Panel
    for s in (Back(), Done(), Stay()):
        assert isinstance(s, Signal)


def test_base_handle_not_implemented():
    import pytest
    with pytest.raises(NotImplementedError):
        State().handle(FakeCtx({}))
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_state.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'fsm.state'`）。

- [ ] **Step 3: 实现 fsm/state.py**

```python
"""声明式状态机：State 基类 + 流程控制信号。"""

from __future__ import annotations

from anchors.anchors import Anchor


class Signal:
    """流程控制信号基类。"""


class Goto(Signal):
    """期望进入 target 界面（下一轮由识别器确认）。"""

    def __init__(self, target: type["State"]) -> None:
        self.target = target


class Back(Signal):
    """回到上一界面（如处理完弹框）。"""


class Done(Signal):
    """达成目标，结束循环。"""


class Stay(Signal):
    """停留当前界面，下一轮重新识别（用于等待加载）。"""


class State:
    """一个游戏界面。signature 全部命中即判定处于此界面。"""

    name: str = ""
    signature: list[Anchor] = []
    priority: int = 0

    def match(self, ctx) -> bool:
        """signature 中所有锚点都命中才算处于此界面。"""
        return all(ctx.find_anchor(a).matched for a in self.signature)

    def handle(self, ctx) -> Signal:
        """在此界面执行动作并返回信号。子类必须实现。"""
        raise NotImplementedError(f"{type(self).__name__} 未实现 handle()")
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_state.py -v`
Expected: PASS（4 passed）。

- [ ] **Step 5: 提交**

```bash
git add fsm/state.py tests/test_state.py
git commit -m "feat: 状态与信号 State/Signal

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 8: 状态注册表 fsm/registry.py

**Files:**
- Create: `game-auto/fsm/registry.py`
- Test: `game-auto/tests/test_registry.py`

**Interfaces:**
- Consumes: `fsm.state.State`。
- Produces:
  - `StateRegistry`：
    - `register(state: State, transitions: list[type[State]] = ()) -> None`
    - `identify(ctx) -> State | None`（按 priority 降序，返回首个 `match()` 命中的实例；均不命中返回 None）
    - `find_path(start: type[State], target: type[State]) -> list[type[State]] | None`（转移图 BFS，返回不含起点的路径；start==target 返回 `[]`；不可达返回 None）

- [ ] **Step 1: 写失败测试 tests/test_registry.py**

```python
from fsm.state import State, Done
from fsm.registry import StateRegistry


class Home(State):
    name = "home"


class Panel(State):
    name = "panel"


class Popup(State):
    name = "popup"
    priority = 100


def _reg():
    reg = StateRegistry()
    reg.register(Home(), transitions=[Panel])
    reg.register(Panel(), transitions=[Home])
    reg.register(Popup())
    return reg


class FakeCtx:
    """按 state 类名决定谁 match。"""

    def __init__(self, matches):
        self.matches = matches  # set of names

    def find_anchor(self, a):
        raise AssertionError("不应被调用")


def _patch_match(reg, ctx):
    # 用 ctx.matches 覆盖各 state.match
    for s in reg._states:
        s.match = (lambda name: (lambda c: name in c.matches))(s.name)


def test_identify_returns_highest_priority_match():
    reg = _reg()
    ctx = FakeCtx({"home", "popup"})
    _patch_match(reg, ctx)
    got = reg.identify(ctx)
    assert got.name == "popup"     # popup 优先级高


def test_identify_none_when_no_match():
    reg = _reg()
    ctx = FakeCtx(set())
    _patch_match(reg, ctx)
    assert reg.identify(ctx) is None


def test_find_path_direct():
    reg = _reg()
    assert reg.find_path(Home, Panel) == [Panel]


def test_find_path_same_is_empty():
    reg = _reg()
    assert reg.find_path(Home, Home) == []


def test_find_path_unreachable():
    reg = _reg()
    assert reg.find_path(Popup, Home) is None
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_registry.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'fsm.registry'`）。

- [ ] **Step 3: 实现 fsm/registry.py**

```python
"""状态注册表：识别当前界面 + 转移图 BFS 寻路。"""

from __future__ import annotations

from collections import deque

from fsm.state import State


class StateRegistry:
    """注册所有 State 并提供识别与寻路。"""

    def __init__(self) -> None:
        self._states: list[State] = []
        self._edges: dict[type[State], list[type[State]]] = {}

    def register(self, state: State, transitions: list[type[State]] = ()) -> None:
        """注册一个 State 实例及其可达的下一界面类型。"""
        self._states.append(state)
        self._edges[type(state)] = list(transitions)

    def identify(self, ctx) -> State | None:
        """按 priority 降序返回首个命中的 State；均不命中返回 None。"""
        for state in sorted(self._states, key=lambda s: -s.priority):
            if state.match(ctx):
                return state
        return None

    def find_path(self, start: type[State], target: type[State]) -> list[type[State]] | None:
        """转移图 BFS：返回从 start 到 target 的路径（不含 start）。

        start==target 返回 []；不可达返回 None。
        """
        if start is target:
            return []
        visited = {start}
        queue: deque[tuple[type[State], list[type[State]]]] = deque([(start, [])])
        while queue:
            node, path = queue.popleft()
            for nxt in self._edges.get(node, []):
                if nxt in visited:
                    continue
                new_path = path + [nxt]
                if nxt is target:
                    return new_path
                visited.add(nxt)
                queue.append((nxt, new_path))
        return None
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_registry.py -v`
Expected: PASS（5 passed）。

- [ ] **Step 5: 提交**

```bash
git add fsm/registry.py tests/test_registry.py
git commit -m "feat: 状态注册表 identify + find_path

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 9: 执行上下文 fsm/context.py

**Files:**
- Create: `game-auto/fsm/context.py`
- Test: `game-auto/tests/test_context.py`

**Interfaces:**
- Consumes: `calib.calibrator.Calibrator`, `core.vision.match_template/load_bgr/to_bgr/Match`, `anchors.anchors.Anchor`, `target.target.Target`。
- Produces:
  - `RunState`：`running/paused/stopped` 布尔标志。
  - `Ctx(calibrator, run_state, *, capture=None, clicker=None, cache_templates=True)`：
    - `refresh_screenshot() -> None`（截图存 `self.screen_bgr`）
    - `find_anchor(anchor: Anchor) -> Match`（作图 region 经 calibrator 换算 → 屏幕；用 `scales=[calibrator.scale]`）
    - `click(target: Target) -> bool`（resolve 得屏幕点 → clicker(x,y)；None 返回 False）
    - `check_state()`（paused 阻塞、stopped 抛 StopFlow）
    - `wait(seconds)`（可被 stopped 打断）
  - `StopFlow(Exception)`。

- [ ] **Step 1: 写失败测试 tests/test_context.py**

```python
import numpy as np
import pytest

from anchors.anchors import Anchor, ImageRef
from core.vision import Match
from target.target import Target
from fsm.context import Ctx, RunState, StopFlow


class FakeCal:
    scale = 0.5

    def to_screen(self, x, y):
        return (x + 10, y + 20)

    def to_screen_region(self, region):
        return (region[0] + 10, region[1] + 20, region[2] + 10, region[3] + 20)


def test_find_anchor_scales_region_and_uses_calibrated_scale():
    seen = {}

    def fake_matcher(screen, template, *, region=None, threshold=0.85, scales=None):
        seen["region"] = region
        seen["scales"] = scales
        seen["threshold"] = threshold
        return Match(True, 0.9, (0, 0, 2, 2), 0.5)

    ctx = Ctx(FakeCal(), RunState(),
              capture=lambda: np.zeros((100, 100, 3), dtype=np.uint8))
    ctx.screen_bgr = np.zeros((100, 100, 3), dtype=np.uint8)
    ctx._matcher = fake_matcher
    ctx._loader = lambda p: np.zeros((4, 4, 3), dtype=np.uint8)

    a = Anchor(ref=ImageRef("x.png"), region=(0, 0, 30, 40), threshold=0.7)
    m = ctx.find_anchor(a)
    assert m.matched
    assert seen["region"] == (10, 20, 40, 60)   # 经 to_screen_region 换算
    assert seen["scales"] == [0.5]
    assert seen["threshold"] == 0.7


def test_click_returns_false_when_unresolved():
    clicked = []
    ctx = Ctx(FakeCal(), RunState(), clicker=lambda x, y: clicked.append((x, y)))
    ctx.screen_bgr = np.zeros((10, 10, 3), dtype=np.uint8)
    ctx._matcher = lambda *a, **k: Match(False, 0.0, (0, 0, 0, 0), 1.0)
    ctx._loader = lambda p: np.zeros((2, 2, 3), dtype=np.uint8)
    ok = ctx.click(Target.image(Anchor(ref=ImageRef("x.png"))))
    assert ok is False
    assert clicked == []


def test_click_uses_calibrator_for_at_target():
    clicked = []
    ctx = Ctx(FakeCal(), RunState(), clicker=lambda x, y: clicked.append((x, y)))
    assert ctx.click(Target.at(1, 2)) is True
    assert clicked == [(11, 22)]


def test_check_state_stop_raises():
    rs = RunState()
    rs.stopped = True
    ctx = Ctx(FakeCal(), rs)
    with pytest.raises(StopFlow):
        ctx.check_state()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_context.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'fsm.context'`）。

- [ ] **Step 3: 实现 fsm/context.py**

```python
"""执行上下文：把标定、匹配、截图、点击、运行状态串起来。"""

from __future__ import annotations

import logging
import time

import numpy as np

from anchors.anchors import Anchor
from core.vision import Match, match_template, load_bgr, to_bgr
from target.target import Target

logger = logging.getLogger(__name__)


class StopFlow(Exception):
    """请求立即终止流程。"""


class RunState:
    """运行状态标志，由热键线程写、执行线程读。"""

    def __init__(self) -> None:
        self.running = False
        self.paused = False
        self.stopped = False


class Ctx:
    """贯穿引擎的执行上下文。"""

    def __init__(self, calibrator, run_state: RunState, *,
                 capture=None, clicker=None, cache_templates: bool = True) -> None:
        self.calibrator = calibrator
        self.run_state = run_state
        self.screen_bgr: np.ndarray | None = None
        self.device_name = ""
        self.account = 0
        self._capture = capture
        self._clicker = clicker
        self._matcher = match_template
        self._loader = load_bgr
        self._cache: dict[str, np.ndarray] = {} if cache_templates else None

    # -- 截图 --
    def refresh_screenshot(self) -> None:
        if self._capture is not None:
            self.screen_bgr = self._capture()
        else:
            from core.capture import fullscreen_screenshot
            self.screen_bgr = to_bgr(fullscreen_screenshot())

    # -- 匹配 --
    def _template(self, anchor: Anchor) -> np.ndarray:
        key = str(anchor.ref.path)
        if self._cache is None:
            return self._loader(anchor.ref.path)
        if key not in self._cache:
            self._cache[key] = self._loader(anchor.ref.path)
        return self._cache[key]

    def find_anchor(self, anchor: Anchor) -> Match:
        """在当前截图中匹配锚点。region 为作图坐标，自动换算到屏幕。"""
        region = None
        if anchor.region is not None:
            region = self.calibrator.to_screen_region(anchor.region)
        return self._matcher(self.screen_bgr, self._template(anchor),
                             region=region, threshold=anchor.threshold,
                             scales=[self.calibrator.scale])

    # -- 点击 --
    def click(self, target: Target) -> bool:
        pt = target.resolve(self)
        if pt is None:
            return False
        if self._clicker is not None:
            self._clicker(*pt)
        else:
            from core.input import click as real_click
            real_click(*pt)
        return True

    # -- 运行控制 --
    def check_state(self) -> None:
        while self.run_state.paused and not self.run_state.stopped:
            time.sleep(0.1)
        if self.run_state.stopped:
            raise StopFlow

    def wait(self, seconds: float) -> None:
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self.check_state()
            time.sleep(min(0.1, max(0.01, end - time.monotonic())))
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_context.py -v`
Expected: PASS（4 passed）。

- [ ] **Step 5: 提交**

```bash
git add fsm/context.py tests/test_context.py
git commit -m "feat: 执行上下文 Ctx + RunState

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 10: 引擎主循环 fsm/engine.py

**Files:**
- Create: `game-auto/fsm/engine.py`
- Test: `game-auto/tests/test_engine.py`

**Interfaces:**
- Consumes: `fsm.state.State/Done/Goto/Back/Stay`, `fsm.registry.StateRegistry`, `fsm.context.Ctx/StopFlow`。
- Produces:
  - `Engine(registry, ctx, *, max_steps=200, max_unknown=5, on_unknown=None)`。
  - `run_until(goal: type[State], *, max_steps=None, max_unknown=None) -> bool`：每轮 `check_state → refresh_screenshot →（标定失效则重标）→ identify`；命中 goal 类或 handle 返回 Done → True；identify None → `on_unknown(ctx)` 且连续超 `max_unknown` → False；步数耗尽 → False。
  - `on_unknown` 默认：保存调试截图到 `data/debug/`。

- [ ] **Step 1: 写失败测试 tests/test_engine.py**

```python
from fsm.state import State, Done, Stay, Goto
from fsm.engine import Engine


class Home(State):
    name = "home"


class Goal(State):
    name = "goal"


class FakeCal:
    def is_valid(self):
        return True

    def calibrate(self):
        return True


class FakeCtx:
    def __init__(self):
        self.calibrator = FakeCal()
        self.refreshed = 0

    def check_state(self):
        pass

    def refresh_screenshot(self):
        self.refreshed += 1


class FakeRegistry:
    def __init__(self, seq):
        self._seq = list(seq)
        self._i = 0

    def identify(self, ctx):
        s = self._seq[self._i]
        self._i += 1
        return s


def test_reaches_goal_by_identification():
    reg = FakeRegistry([Goal()])
    eng = Engine(reg, FakeCtx())
    assert eng.run_until(Goal) is True


def test_stay_then_goal():
    home = Home()
    home.handle = lambda ctx: Stay()
    reg = FakeRegistry([home, Goal()])
    eng = Engine(reg, FakeCtx())
    assert eng.run_until(Goal) is True


def test_done_signal_ends():
    home = Home()
    home.handle = lambda ctx: Done()
    reg = FakeRegistry([home])
    eng = Engine(reg, FakeCtx())
    assert eng.run_until(Goal) is True


def test_unknown_then_recover_then_goal():
    calls = {"n": 0}
    reg = FakeRegistry([None, None, Goal()])
    eng = Engine(reg, FakeCtx(), on_unknown=lambda ctx: calls.__setitem__("n", calls["n"] + 1))
    assert eng.run_until(Goal) is True
    assert calls["n"] == 2


def test_unknown_exceeds_limit_returns_false():
    reg = FakeRegistry([None, None, None, None])
    eng = Engine(reg, FakeCtx(), max_unknown=2, on_unknown=lambda ctx: None)
    assert eng.run_until(Goal) is False


def test_max_steps_exhausted_returns_false():
    home = Home()
    home.handle = lambda ctx: Stay()
    reg = FakeRegistry([home] * 10)
    eng = Engine(reg, FakeCtx(), max_steps=3)
    assert eng.run_until(Goal) is False
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_engine.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'fsm.engine'`）。

- [ ] **Step 3: 实现 fsm/engine.py**

```python
"""引擎主循环：识别当前界面 → 处理 → 自愈，直到目标态。"""

from __future__ import annotations

import logging

from fsm.state import State, Done
from fsm.context import StopFlow

logger = logging.getLogger(__name__)


class Engine:
    """驱动状态机运行的主循环。"""

    def __init__(self, registry, ctx, *, max_steps: int = 200,
                 max_unknown: int = 5, on_unknown=None) -> None:
        self.registry = registry
        self.ctx = ctx
        self.max_steps = max_steps
        self.max_unknown = max_unknown
        self._on_unknown = on_unknown or _default_on_unknown

    def run_until(self, goal: type[State], *, max_steps: int | None = None,
                  max_unknown: int | None = None) -> bool:
        """循环直到进入 goal 界面或收到 Done。返回是否成功抵达。"""
        max_steps = max_steps or self.max_steps
        max_unknown = max_unknown or self.max_unknown
        unknown = 0

        for _ in range(max_steps):
            self.ctx.check_state()
            self.ctx.refresh_screenshot()
            if not self.ctx.calibrator.is_valid():
                self.ctx.calibrator.calibrate()

            state = self.registry.identify(self.ctx)
            if state is None:
                unknown += 1
                logger.warning("未识别当前界面（连续 %d 次）", unknown)
                if unknown > max_unknown:
                    logger.error("连续未知态超过 %d 次，中止", max_unknown)
                    return False
                self._on_unknown(self.ctx)
                continue

            unknown = 0
            if isinstance(state, goal):
                logger.info("已抵达目标界面: %s", state.name or type(state).__name__)
                return True

            logger.info("当前界面: %s → 处理", state.name or type(state).__name__)
            sig = state.handle(self.ctx)
            if isinstance(sig, Done):
                logger.info("收到 Done，结束")
                return True
            # Goto / Back / Stay / None → 下一轮重新识别

        logger.error("超过最大步数 %d，未抵达目标", max_steps)
        return False


def _default_on_unknown(ctx) -> None:
    """未知态默认处理：保存调试截图。"""
    try:
        from pathlib import Path
        from datetime import datetime
        import cv2
        debug_dir = Path("data/debug")
        debug_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%H%M%S")
        if ctx.screen_bgr is not None:
            cv2.imwrite(str(debug_dir / f"unknown_{ts}.png"), ctx.screen_bgr)
            logger.warning("未知态截图已保存 data/debug/unknown_%s.png", ts)
    except Exception:
        logger.exception("保存未知态截图失败")
```

注意：测试里的 `FakeCtx` 没有 `screen_bgr` 属性，但测试传入的 `on_unknown` 覆盖了默认实现，不会触达 `_default_on_unknown`，故安全。

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_engine.py -v`
Expected: PASS（6 passed）。

- [ ] **Step 5: 运行全部测试**

Run: `python -m pytest`
Expected: PASS（全绿，约 30+ passed）。

- [ ] **Step 6: 提交**

```bash
git add fsm/engine.py tests/test_engine.py
git commit -m "feat: 引擎主循环 Engine.run_until + 未知态自愈

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 11: 人类化鼠标 core/input.py（移植）

**Files:**
- Create: `game-auto/core/input.py`

**Interfaces:**
- Produces: `click(*args)`（`click(x,y)` 或 `click(l,t,r,b)` 区域随机）、`drag(x1,y1,x2,y2,duration=0.5)`、`move_to(x,y,force_duration=None)`。**注意坐标已是屏幕像素**，本模块只负责 Retina 逻辑坐标换算与人类化轨迹，**不再做跨分辨率缩放/偏移**（那是 Calibrator 的职责）。

- [ ] **Step 1: 复制源鼠标模块为基底**

```bash
cp /Users/yuanhao/Developer/Project/2M_tool/game-info-identify/core/mouse.py \
   /Users/yuanhao/Developer/Project/2M_tool/game-auto/core/input.py
```

- [ ] **Step 2: 删除跨分辨率逻辑，简化 `_to_logical`**

在 `core/input.py` 中：

1. 删除 `_get_resolution_scale()`、`_get_screen_offset()`、`_load_full_config()` 三个函数（跨分辨率缩放/偏移已由 Calibrator 承担）。
2. 删除模块级变量 `_res_cache`。
3. 将 `_to_logical` 改为只做 Retina 换算：

把原：

```python
def _to_logical(x: int, y: int) -> tuple[int, int]:
    """物理像素坐标 → 逻辑坐标，自动适配 Retina + 跨分辨率缩放 + 偏移量。"""
    scale = _get_scale()
    rs_w, rs_h = _get_resolution_scale()
    ox, oy = _get_screen_offset()
    return round((x * rs_w + ox) / scale), round((y * rs_h + oy) / scale)
```

改为：

```python
def _to_logical(x: int, y: int) -> tuple[int, int]:
    """屏幕物理像素坐标 → 逻辑坐标，仅适配 Retina 缩放。"""
    scale = _get_scale()
    return round(x / scale), round(y / scale)
```

4. 删除文件末尾的 `switch_to_next(...)` 函数（切换账户逻辑归 runner）。

- [ ] **Step 3: 冒烟验证（人工，会移动真实鼠标）**

Run: `cd /Users/yuanhao/Developer/Project/2M_tool/game-auto && python -c "from core.input import move_to; move_to(200, 200)"`
Expected: 鼠标平滑移动到屏幕物理像素 (200,200) 对应位置，无异常。

- [ ] **Step 4: 提交**

```bash
git add core/input.py
git commit -m "feat: 人类化鼠标 core/input（移除跨分辨率逻辑）

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 12: OCR core/ocr.py（移植）

**Files:**
- Create: `game-auto/core/ocr.py`

**Interfaces:**
- Produces: `_get_reader()`、`extract_text(image) -> str`、`extract_digits(image) -> str`、`recognize_diamond(image) -> str`、`recognize_diamond_stable(capture, max_attempts=6, account_index=0, device_name="") -> tuple[str,bool]`。

- [ ] **Step 1: 复制源 OCR 模块（保持不变）**

```bash
cp /Users/yuanhao/Developer/Project/2M_tool/game-info-identify/core/ocr_engine.py \
   /Users/yuanhao/Developer/Project/2M_tool/game-auto/core/ocr.py
```

- [ ] **Step 2: 冒烟验证（人工，首次会下载模型）**

Run: `cd /Users/yuanhao/Developer/Project/2M_tool/game-auto && python -c "from PIL import Image; from core.ocr import extract_digits; print(repr(extract_digits(Image.new('RGB',(60,30),(0,0,0)))))"`
Expected: 打印 `''`（空串），加载 EasyOCR 无异常即通过。

- [ ] **Step 3: 提交**

```bash
git add core/ocr.py
git commit -m "feat: OCR core/ocr（移植 EasyOCR + 稳定采样）

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 13: 运行器 runner/runner.py（热键 + 账户循环）

**Files:**
- Create: `game-auto/runner/runner.py`
- Test: `game-auto/tests/test_runner.py`

**Interfaces:**
- Consumes: `fsm.context.RunState/StopFlow`。
- Produces:
  - `FlowRunner(run_state, *, repeat=1, hotkeys=None, on_round=None, switch=None) `。
  - `_key_name(key) -> str`（pynput key → 小写字符串，纯函数，可测）。
  - `run(target) -> None`：注册热键，等待 start，循环 `repeat` 轮，每轮调 `target()`（一轮业务），轮间调 `switch()`。

- [ ] **Step 1: 写失败测试 tests/test_runner.py（只测纯函数 _key_name）**

```python
from runner.runner import _key_name


class FakeChar:
    def __init__(self, ch):
        self.char = ch


class FakeNamed:
    char = None

    def __repr__(self):
        return "Key.f5"


def test_key_name_char():
    assert _key_name(FakeChar("A")) == "a"


def test_key_name_named():
    assert _key_name(FakeNamed()) == "f5"


def test_key_name_none():
    assert _key_name(None) == ""
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_runner.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'runner.runner'`）。

- [ ] **Step 3: 实现 runner/runner.py**

```python
"""FlowRunner：全局热键监听 + 多轮账户循环。"""

from __future__ import annotations

import logging
import time

from pynput import keyboard

from fsm.context import RunState, StopFlow

logger = logging.getLogger(__name__)

DEFAULT_HOTKEYS = {"start": "f5", "pause": "f6", "stop": "f7", "exit": "esc"}


class FlowRunner:
    """管理热键与循环，驱动一轮轮业务执行。"""

    def __init__(self, run_state: RunState, *, repeat: int = 1,
                 hotkeys: dict | None = None, switch=None) -> None:
        self._state = run_state
        self._repeat = repeat
        self._hotkeys = {**DEFAULT_HOTKEYS, **(hotkeys or {})}
        self._switch = switch
        self._listener: keyboard.Listener | None = None

    def run(self, target) -> None:
        """启动热键，等待 start 后循环执行 target()（一轮业务）。"""
        hk = self._hotkeys

        def on_press(key) -> None:
            k = _key_name(key)
            if k == hk["start"]:
                self._state.running = True
                self._state.paused = False
                logger.info("▶ 开始")
            elif k == hk["pause"]:
                self._state.paused = not self._state.paused
                logger.info("⏸ 暂停" if self._state.paused else "▶ 继续")
            elif k == hk["stop"]:
                self._state.stopped = True
                self._state.paused = False
                logger.info("⏹ 停止")
            elif k == hk["exit"]:
                self._state.stopped = True
                if self._listener:
                    self._listener.stop()

        self._listener = keyboard.Listener(on_press=on_press)
        self._listener.daemon = True
        self._listener.start()

        logger.info("等待按 %s 开始...", hk["start"].upper())
        while not self._state.running and not self._state.stopped:
            time.sleep(0.1)
        if self._state.stopped:
            return

        try:
            for i in range(self._repeat):
                if self._state.stopped:
                    break
                logger.info("===== 第 %d/%d 轮 =====", i + 1, self._repeat)
                target()
                if i < self._repeat - 1 and not self._state.stopped and self._switch:
                    logger.info("切换账户...")
                    self._switch()
        except StopFlow:
            logger.info("流程已停止")
        except Exception:
            logger.exception("流程执行异常")

        if self._listener and self._listener.is_alive():
            self._listener.stop()


def _key_name(key) -> str:
    """pynput key → 小写字符串。"""
    if key is None:
        return ""
    if hasattr(key, "char") and key.char:
        return key.char.lower()
    return str(key).replace("Key.", "").lower()
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_runner.py -v`
Expected: PASS（3 passed）。

- [ ] **Step 5: 提交**

```bash
git add runner/runner.py tests/test_runner.py
git commit -m "feat: 运行器 FlowRunner 热键 + 账户循环

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 14: 工具 tools/capture_anchor.py + tools/whereami.py

**Files:**
- Create: `game-auto/tools/capture_anchor.py`
- Create: `game-auto/tools/whereami.py`
- Create: `game-auto/tools/__init__.py`（空）

**Interfaces:**
- Consumes: `tools/screen_tool.py` 交互逻辑（移植）；`whereami` 消费 `Calibrator`/`StateRegistry`/`Ctx`。
- Produces: 两个可独立运行的 CLI 工具。`capture_anchor.py` 框选保存锚点图；`whereami.py` 实时打印当前命中的 State 名。

- [ ] **Step 1: 移植截图裁剪工具为 capture_anchor.py**

```bash
cp /Users/yuanhao/Developer/Project/2M_tool/game-info-identify/tools/screen_tool.py \
   /Users/yuanhao/Developer/Project/2M_tool/game-auto/tools/capture_anchor.py
```

然后在 `tools/capture_anchor.py` 中删除跨分辨率换算相关部分（本项目锚点图直接用屏幕像素采集，作图分辨率即采集时的屏幕分辨率）：

1. 删除方法 `_load_screen_config`、`_to_5k`、`_toggle_5k`。
2. 在 `__init__` 中，把对 `self._load_screen_config()` 的调用替换为：
```python
self._rs_w, self._rs_h = 1.0, 1.0
self._offset_x, self._offset_y = 0, 0
self._show_5k = False
```
3. 删除快捷键绑定 `self.root.bind("<Key-5>", ...)` 一行，并在提示 Label 文案中去掉 `5=切换5K换算`。

（其余框选、R 保存到 `images/`、坐标显示逻辑保持不变。）

- [ ] **Step 2: 冒烟验证 capture_anchor（人工）**

Run: `cd /Users/yuanhao/Developer/Project/2M_tool/game-auto && python tools/capture_anchor.py`
Expected: 弹出窗口，按 F5 截屏，拖拽框选后按 R，`images/ref_1.png` 生成。

- [ ] **Step 3: 实现 tools/whereami.py**

```python
"""实时探针：每隔 1 秒截图并打印当前命中的 State，用于调试状态机 signature。

用法:
    python tools/whereami.py
需先在下方 build_registry() 中注册要检测的 State（或 import 冒烟流程的注册表）。
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from conf.log import add_log
from calib.calibrator import Calibrator
from anchors.anchors import Anchor, ImageRef
from fsm.context import Ctx, RunState
from fsm.registry import StateRegistry


def build_registry() -> StateRegistry:
    """在此注册要检测的 State。默认从冒烟流程导入。"""
    from flows.smoke import build_registry as smoke_registry
    return smoke_registry()


def build_calibrator() -> Calibrator:
    from ruamel.yaml import YAML
    cfg = YAML(typ="safe").load(open("conf/config.yaml", encoding="utf-8"))
    c = cfg["calib"]
    anchor = Anchor(ref=ImageRef(c["anchor"]), threshold=float(c["threshold"]))
    return Calibrator(anchor, tuple(c["anchor_authoring_topleft"]),
                      threshold=float(c["threshold"]))


def main() -> None:
    add_log()
    registry = build_registry()
    calibrator = build_calibrator()
    ctx = Ctx(calibrator, RunState())
    ctx.refresh_screenshot()
    if not calibrator.calibrate(ctx.screen_bgr):
        print("标定失败：请检查 conf/config.yaml 的 calib.anchor")
        return
    print("开始探测（Ctrl+C 退出）...")
    try:
        while True:
            ctx.refresh_screenshot()
            state = registry.identify(ctx)
            name = state.name if state else "未知界面"
            print(f"当前界面: {name}")
            time.sleep(1)
    except KeyboardInterrupt:
        print("退出")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 提交**

```bash
git add tools/
git commit -m "feat: 锚点采集工具 + whereami 界面探针

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 15: 冒烟流程 flows/smoke.py + run.py（真实界面验收）

**Files:**
- Create: `game-auto/flows/smoke.py`
- Create: `game-auto/run.py`
- Create: `game-auto/images/calib/`（放标定锚点图）、`game-auto/images/smoke/`（放各界面 signature 图）

**Interfaces:**
- Consumes: 全部上游模块。
- Produces:
  - `flows.smoke.build_registry() -> StateRegistry`（供 whereami 复用）。
  - `flows.smoke.SmokeFlow`：定义 `Home`/`Panel`/`Popup` 三个 State + 目标 `Panel`，跑「HOME→开面板→遇弹框自动关→回 HOME」。
  - `run.py`：交互式入口，装配 Calibrator/Registry/Ctx/Engine/FlowRunner 并启动。

- [ ] **Step 1: 采集真实界面锚点图（人工，用 Task 14 工具）**

用 `python tools/capture_anchor.py`，在真实游戏界面依次采集并保存到对应目录：
- `images/calib/anchor.png`：一个在所有界面都稳定存在、图案独特的元素（如顶栏 logo），作为标定锚点。记下它左上角在当前屏幕的坐标，填入 `conf/config.yaml` 的 `calib.anchor_authoring_topleft`，并把 `screen.authoring_width/height` 填为当前屏幕分辨率。
- `images/smoke/home_sig.png`：HOME 界面独有元素。
- `images/smoke/home_open_panel.png`：HOME 上用于打开面板的按钮。
- `images/smoke/panel_sig.png`：面板界面独有元素。
- `images/smoke/panel_close.png`：面板的关闭按钮。
- `images/smoke/popup_sig.png`：某个弹框独有元素。
- `images/smoke/popup_close.png`：弹框关闭按钮。

- [ ] **Step 2: 实现 flows/smoke.py**

```python
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
        ctx.click(Target.image(Anchor(ref=img.home_open_panel)))
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
        ctx.click(Target.image(Anchor(ref=img.popup_close)))
        ctx.wait(1)
        return Back()


def build_registry() -> StateRegistry:
    reg = StateRegistry()
    reg.register(Home(), transitions=[Panel])
    reg.register(Panel(), transitions=[Home])
    reg.register(Popup())
    return reg
```

- [ ] **Step 3: 实现 run.py**

```python
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
```

- [ ] **Step 4: 端到端验收（人工）**

前置：游戏停在 HOME 界面。

Run: `cd /Users/yuanhao/Developer/Project/2M_tool/game-auto && python run.py`
操作：按 F5 开始。
Expected（验收标准）：
1. 日志打印「标定成功：scale=… origin=…」，**无需**手工填缩放/偏移。
2. 引擎识别 HOME → 点击打开面板 → 识别到 Panel → 打印「已抵达目标界面: panel」→「本轮结果: 成功抵达面板」。
3. 若打开过程中弹出弹框，日志出现「检测到弹框 → 关闭」后继续，不卡死（自愈验证）。
4. 按 F6 能暂停/继续，按 F7 能停止。
5. 跑满 2 轮（repeat=2）。

- [ ] **Step 5: 运行全部单测确保未回归**

Run: `python -m pytest`
Expected: 全绿。

- [ ] **Step 6: 提交**

```bash
git add flows/smoke.py run.py images/
git commit -m "feat: 冒烟流程 + 入口 run.py（真实界面验收）

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Self-Review

**1. Spec coverage（逐条对照 spec）:**
- §3 分层架构 → Task 1–15 覆盖 conf/core/calib/anchors/target/fsm/runner/tools/flows。✅
- §4.2 多尺度匹配 → Task 4。✅ §4.3 标定 → Task 5。✅ §4.4 Target → Task 6。✅
- §5.1 State/Signature → Task 7；§5.2 Signal → Task 7；§5.3 Registry/identify/navigate → Task 8（`find_path` 提供 BFS，`navigate_to` 的驱动作为后续里程碑的恢复策略，当前 `_default_on_unknown` 走存图+计数中止，符合 §8「未知态存调试截图」的底线）；§5.4 Engine 主循环 → Task 10；§5.5 Ctx → Task 9。✅
- §6 runner → Task 13。✅ §7 数据流 → 由 Ctx+Engine 串起。✅
- §8 错误恢复：标定失败（Task 5 返回 False + run.py 跳过本轮）、未知态存图+计数（Task 10）、pause/stop（Task 9 check_state）。✅ 「置信度骤降触发 invalidate 重标」提供了 `invalidate()`（Task 5）与 run 循环内 `is_valid()→calibrate()` 钩子（Task 10/15），主动触发策略留待业务流程里程碑细化——已在 §13 声明为后续。✅
- §9 移植清单 → Task 2/11/12/13/14。✅ §10 测试 → 各 TDD 任务。✅ §11 冒烟流程 → Task 15。✅ §12 验收标准 → Task 15 Step 4。✅

**2. Placeholder scan:** 无 TBD/TODO；港口任务给出确切 `cp` 命令与逐条编辑；每个改代码步骤都含完整代码。✅

**3. Type consistency:** `Match(matched, confidence, box, scale)` 全程一致；`Calibrator.to_screen/to_screen_region/is_valid/scale/origin` 在 Task 5 定义、Task 9/15 使用一致；`Ctx.find_anchor/click/check_state/refresh_screenshot/screen_bgr` Task 9 定义、Task 10/14/15 使用一致；`StateRegistry.register/identify/find_path` Task 8 定义、Task 14/15 使用一致；`Target.image/rel/at/resolve` Task 6 定义、Task 9/15 使用一致；`RunState.running/paused/stopped` Task 9 定义、Task 13 使用一致。✅

一致性说明：`Target.image` 的签名为 `image(anchor, *, offset=(0,0))`（Task 6 实现与 Task 6 测试、Task 15 使用一致，未使用 spec 草案里的 `region=` 形参——锚点搜索区域由 `Anchor.region` 承载，避免重复，符合 DRY）。
