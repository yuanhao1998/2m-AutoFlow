# game-auto 视觉自动化引擎 — 设计文档

日期：2026-07-11
状态：已通过设计评审，待编写实现计划

## 1. 背景与目标

### 1.1 问题来源
现有项目 `game-info-identify` 的视觉自动化引擎存在两个根本痛点：

1. **跨分辨率不准**：所有坐标是基于"作图基准分辨率"的绝对坐标，运行时用手工配置的"非等比缩放（宽/高独立）+ 偏移"映射到实际屏幕。基准与实际宽高比不一致时靠非等比硬凑，点击/识别在别的分辨率上不准。
2. **流程易卡死**：`run()` 是线性命令式脚本，`@step` 只在执行前做一次匹配+重试，系统**无法判断当前处于哪个界面**。任意一步出错，整条流程卡死、无法自愈。

### 1.2 关键决策（已与需求方确认）
- 不同云手机实例的画面差异 = **同布局、仅整体等比缩放**。
- 定位方案 = **锚点相对定位为主 + 一次标定仿射变换兜底**（方案 A）。
- 界面识别 = **声明式状态机**。
- **全面重构，新开独立项目 `game-auto`**；现有代码仅作需求参考。
- 本次里程碑 = **只交付引擎框架** + 一个用真实游戏界面验证的最小冒烟流程；不迁移任何真实业务流程。

### 1.3 本次目标（In Scope）
- 一个分辨率无关、可自愈的视觉自动化引擎框架。
- 用真实游戏界面（HOME ↔ 某面板 ↔ 弹框）跑通的冒烟流程，证明：自动标定、锚点相对点击、状态识别、弹框自愈、账户切换、热键控制均可用。
- 纯逻辑单元测试（pytest）。
- 锚点采集工具、"当前界面"实时探针工具。

### 1.4 非目标（Out of Scope，留待后续里程碑）
- 迁移 delegate/shop/supply/dungeon/SignIn/diamond 等真实业务流程。
- 处理"不同宽高比 / 布局重排"的分辨率（当前明确只支持等比缩放）。
- 钻石统计的完整业务（OCR 能力移植进来，但不搭业务流程）。

## 2. 技术栈与环境
- Python 3.14+，macOS。
- 复用库：`easyocr`、`pyautogui`、`pynput`、`opencv-python-headless`、`pillow`、`ruamel.yaml`。
- 新增：`pytest`（单元测试）。
- 位置：`/Users/yuanhao/Developer/Project/2M_tool/game-auto/`，独立 git 仓库。

## 3. 分层架构

```
game-auto/
├── run.py                统一入口
├── conf/
│   ├── config.yaml         运行时配置（无手工缩放字段）
│   └── log.py              统一日志（移植）
├── core/
│   ├── capture.py          全屏截图 + 区域裁剪，Retina 物理像素（移植）
│   ├── vision.py           多尺度模板匹配 → Match(位置/缩放比/置信度)
│   ├── ocr.py              EasyOCR 文字/数字识别 + 稳定采样（移植）
│   └── input.py            人类化鼠标：贝塞尔移动/点击/拖拽（移植）
├── calib/
│   └── calibrator.py       全局仿射标定(origin+scale) + 作图↔屏幕坐标换算
├── anchors/
│   └── anchors.py          Anchor / ImageDir 声明式参考图（移植 + 作图分辨率元数据）
├── target/
│   └── target.py           Target 抽象：image / rel / at → 解析成屏幕点击点
├── fsm/
│   ├── state.py            State 基类（signature + handle）+ Signal
│   ├── registry.py         StateRegistry.identify() + 转移图 + navigate_to(BFS)
│   └── engine.py           主循环：识别→处理→自愈→直到目标态
├── runner/
│   └── runner.py           热键监听 + 账户循环(repeat/switch)（移植）
├── tools/
│   ├── capture_anchor.py   框选截图 → 存锚点图 + 记录作图分辨率（移植增强）
│   └── whereami.py         实时探针：打印当前命中哪个 State
├── flows/
│   └── smoke.py            最小冒烟流程（真实界面验证）
├── images/                 参考图/锚点图
├── tests/                  pytest 纯逻辑测试 + fixture 图
├── data/                   识别结果 / 调试输出
└── logs/                   运行日志
```

依赖方向自底向上：`core` → `calib`/`anchors` → `target` → `fsm` → `runner`/`flows`。低层不反向依赖高层。

## 4. 关键机制 1：分辨率无关定位（解决痛点 1）

### 4.1 作图分辨率约定
所有锚点图与相对偏移都在**同一个"作图分辨率"**（authoring resolution）下采集与测量。运行时画面是它的等比缩放版本，缩放比未知，由标定求出。作图分辨率记录在配置与锚点元数据里。

### 4.2 多尺度模板匹配（`core/vision.py`）
```python
@dataclass
class Match:
    matched: bool
    confidence: float
    box: tuple[int, int, int, int]   # 屏幕像素 (l, t, r, b)
    scale: float                     # 命中时模板的缩放比
    @property
    def center(self) -> tuple[int, int]: ...

def match_template(screen, template, *, region=None, threshold=0.85,
                   scales=None) -> Match:
    """在 screen 内按一组 scales 缩放 template 逐一匹配，取最高分。
    scales=None 时使用标定得到的单一缩放比（快路径）；
    标定阶段/置信度过低时用一段尺度范围（慢路径）。"""
```
- 快路径：已标定 → 只用缩放比 `s` 匹配一次。
- 慢路径：标定或失配 → 在 `[s_min, s_max]` 扫描一组尺度。

### 4.3 标定（`calib/calibrator.py`）
```python
class Calibrator:
    scale: float
    origin: tuple[int, int]

    def calibrate(self) -> bool:
        """对'标定锚点图'做多尺度匹配，得到 scale 与 origin：
        origin = 命中左上角 - 锚点作图左上角 × scale。成功返回 True。"""
    def to_screen(self, x, y) -> tuple[int, int]:      # 作图坐标 → 屏幕像素
    def to_screen_region(self, region) -> tuple:        # 作图区域 → 屏幕区域
    def is_valid(self) -> bool                          # 缓存是否可用
    def invalidate(self) -> None                        # 触发重标（置信度掉时）
```
标定关系：`屏幕px = origin + 作图px × scale`。启动标定一次并缓存；匹配置信度显著下降或明确失败时 `invalidate()` 后重标。**完全取代**旧项目的 `base_width/actual_width/offset/非等比缩放` 手工配置。

### 4.4 Target 抽象（`target/target.py`）
```python
class Target:
    @staticmethod
    def image(anchor, *, region=None, offset=(0, 0)) -> "Target":
        """匹配 anchor → 点击其中心（+ offset×scale）。首选，天然精准。"""
    @staticmethod
    def rel(anchor, dx, dy) -> "Target":
        """匹配 anchor → 点击 中心 + (dx, dy)×scale。无独特图案的相对目标。"""
    @staticmethod
    def at(x, y) -> "Target":
        """作图坐标 → 经标定变换为屏幕坐标。纯坐标兜底。"""

    def resolve(self, ctx) -> tuple[int, int] | None:
        """返回屏幕点击点；匹配失败返回 None。"""
```
搜索 `region` 一律用作图坐标书写，引擎经标定自动换算。作图体验与旧项目一致，但结果分辨率无关。

## 5. 关键机制 2：声明式状态机（解决痛点 2）

### 5.1 State 与 Signature
```python
@dataclass
class Anchor:
    ref: ImageRef                    # 参考图
    region: tuple | None = None      # 作图坐标搜索区域，None=全屏
    threshold: float = 0.85

class State:
    name: str
    signature: list[Anchor]          # 全部命中才判定为此界面
    priority: int = 0                # 越大越优先（弹框/报错高优先）

    def match(self, ctx) -> bool:    # signature 全部命中
    def handle(self, ctx) -> "Signal":  # 在此界面执行动作，返回下一步信号
```

弹框/报错**本身也是 State**，给高 `priority`，命中即被优先处理——这就是自愈的核心。

### 5.2 Signal（流程控制）
```python
class Signal: ...
class Goto(Signal):  target: type[State]   # 期望进入某界面
class Back(Signal):  ...                    # 回到上一界面（处理完弹框）
class Done(Signal):  ...                    # 达成目标，结束
class Stay(Signal):  ...                    # 停留，下轮重判（等待加载）
```

### 5.3 StateRegistry（`fsm/registry.py`）
```python
class StateRegistry:
    def register(self, state: State, transitions: list[type[State]] = ()) -> None
    def identify(self, ctx) -> State | None:
        """按 priority 降序对已注册 State 逐个 match，返回首个命中；均不命中返回 None。"""
    def navigate_to(self, ctx, target: type[State]) -> bool:
        """在转移图上 BFS 找回目标态（用于未知态恢复 / 回 HOME）。"""
```

### 5.4 Engine 主循环（`fsm/engine.py`）
```python
class Engine:
    def run_until(self, goal: type[State], *, max_steps=200) -> bool:
        for _ in range(max_steps):
            ctx.check_state()                 # 响应 pause/stop 热键
            ctx.refresh_screenshot()          # 每轮截一次图
            if not calibrator.is_valid():
                calibrator.calibrate()
            state = registry.identify(ctx)
            if state is None:
                self._recover(ctx)            # 未知态：navigate_to(HOME) + 存调试截图
                continue
            if isinstance(state, goal):
                return True
            sig = state.handle(ctx)
            # 解释 Goto/Back/Done/Stay
        return False
```

**自愈路径**：
- 意外弹框 → 高优先级 State 命中 → `handle` 关闭 → `Back`；
- 完全不认识的界面 → `identify` 返回 None → `_recover` 尝试 `navigate_to(HOME)`，失败则存调试截图并按策略停止/重试。

### 5.5 Ctx（执行上下文）
贯穿引擎的运行上下文对象，持有：当前截图、`calibrator`、`vision` 匹配器、`input` 鼠标、运行状态标志（running/paused/stopped）、当前账户序号、`device_name`。提供便捷方法：`click(target)`、`find(anchor)`、`wait(s)`、`check_state()`、`refresh_screenshot()`。

## 6. 运行与循环（`runner/runner.py`）
移植旧项目的热键 + 账户循环：
- 热键：`start(F5)/pause(F6)/stop(F7)/exit(ESC)`，写入运行状态，引擎循环内读取。
- 账户循环：`repeat` 轮，每轮 `engine.run_until(goal)`；轮间调用 `switch_to_next()` 切换账户并等待加载。
- 结束统计与日志。

## 7. 数据流
```
截图(core.capture) → 标定(calib) 建立坐标变换
                    → 状态识别(fsm.registry.identify 用 vision 多尺度匹配)
                    → 状态 handle 内：Target.resolve(用 vision/calib) → input 点击
                    → Signal 驱动下一轮
```

## 8. 错误处理与恢复
- **标定失败**：慢路径尺度扫描仍失败 → 记录并停止，提示检查标定锚点图/分辨率。
- **未知界面**：`identify` 返回 None → `navigate_to(HOME)`；失败 → 存调试截图到 `data/debug/`，按配置停止或跳过当前账户。
- **匹配置信度骤降**：`calibrator.invalidate()` 触发重标，排除因偶发画面变化误判分辨率变化。
- **pause/stop**：循环内 `check_state()` 随时响应，安全中断。

## 9. 移植 vs 新写
- **移植（现成可靠）**：`core/capture`、`core/input`（贝塞尔人类化鼠标）、`core/ocr`（EasyOCR + 稳定采样）、`runner`（热键/循环）、`anchors`（ImageDir 声明式）、Retina 缩放检测、`conf/log`。
- **新写**：`core/vision` 多尺度匹配、`calib`、`target`、`fsm`（state/registry/engine）、精简 `config.yaml`、`tools`。

## 10. 测试策略
引入 **pytest**，聚焦纯逻辑（用 fixture 截图，不依赖真实屏幕）：
- `calib`：`to_screen/to_screen_region` 坐标变换数学；已知缩放 fixture 反解出正确 `scale/origin`。
- `vision`：对人工缩放过的 fixture 图，多尺度匹配能找回正确位置与 scale。
- `fsm.registry`：`identify()` 按 priority 命中；多状态/无状态边界。
- `fsm.registry.navigate_to`：转移图 BFS 路径正确。
- `target`：三种 Target 在给定 calibrator/match 下解析出正确屏幕点。

涉及真实屏幕的部分（点击、真实匹配、账户切换）由 `flows/smoke.py` 人工验证。

## 11. 冒烟流程（交付验收物）
`flows/smoke.py` 用真实游戏界面定义 2–3 个 State（如 `Home`、`SomePanel`、`SomePopup`），目标：从 HOME 打开面板、遇弹框自动关闭、再回到 HOME。跑通即证明框架端到端可用。

## 12. 验收标准
1. 引擎在真实分辨率下**无需手工配置缩放**即可标定并精准点击。
2. 人为制造一步失败（如提前弹出报错框），引擎能**自动识别并恢复**，不卡死。
3. 冒烟流程可用 F5/F6/F7 控制，能跑完 ≥2 个账户循环。
4. `pytest` 纯逻辑测试全绿。

## 13. 待明确 / 后续里程碑
- 后续逐个迁移真实业务流程（delegate 优先）。
- 若将来出现非等比 / 布局重排的分辨率，再扩展定位层（当前不做）。
