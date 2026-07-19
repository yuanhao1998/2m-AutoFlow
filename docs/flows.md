# Flows 开发文档

## 概述

flow 是一个**完整的业务流程**，由若干 `State`（界面状态）组成的有向图。引擎在运行时自动识别当前界面、执行对应动作、在界面间跳转，直至抵达目标态。

一个 flow 文件通常包含：

- **`ImageDir` 子类** — 声明该流程所需的锚点参考图
- **若干 `State` 子类** — 每个界面的 signature（怎么认出它）和 handle（认出后做什么）
- **`build_registry()` 函数** — 注册所有 State 及其转移关系

## 快速开始：新增一个流程

### 1. 采集锚点图

用 `capture_anchor.py` 在目标设备上截屏、框选关键区域，按 `R` 保存为参考图：

```bash
python3 tools/capture_anchor.py
```

图片保存到 `images/<流程名>/`，搜索区域自动写入同目录的 `regions.yaml`。

### 2. 创建 flow 文件

在 `flows/` 下新建 `xxx.py`，按以下模板填写：

```python
"""流程描述。"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from anchors.anchors import Anchor, ImageDir
from fsm.state import State, Goto, Back, Stay, Done
from fsm.registry import StateRegistry
from target.target import Target


# ---- 1. 声明参考图目录 ----
class XxxImages(ImageDir):
    path = "images/xxx"          # 锚点图所在目录


img = XxxImages()


# ---- 2. 定义各界面 State ----
class Home(State):
    name = "首页"
    signature = [Anchor(ref=img.home_sig)]   # 命中此图即为首页
    # priority 默认 0，弹框类应设高值

    def handle(self, ctx):
        logging.info("在首页，点击进入商城")
        ctx.click(Target.image(Anchor(ref=img.enter_shop)))
        ctx.wait(2)
        return Goto(Shop)       # 期望下一轮进入 Shop


class Shop(State):
    name = "商城"
    signature = [Anchor(ref=img.shop_sig)]

    def handle(self, ctx):
        logging.info("已抵达商城（目标态）")
        return Stay()           # 停留，后续可在此扩展操作


class Popup(State):
    name = "弹框"
    priority = 100              # 高优先级，优先识别处理
    signature = [Anchor(ref=img.popup_sig)]

    def handle(self, ctx):
        logging.info("关闭弹框")
        ctx.click(Target.image(Anchor(ref=img.popup_close)))
        ctx.wait(1)
        return Back()           # 回到弹框出现前的界面


# ---- 3. 组装注册表 ----
def build_registry() -> StateRegistry:
    reg = StateRegistry()
    reg.register(Home(), transitions=[Shop])
    reg.register(Shop(), transitions=[Home])
    reg.register(Popup())       # 无转移：弹框关闭后由 Back() 自动恢复
    return reg
```

### 3. 在入口注册

在 `run.py` 的 `main()` 中替换 import 和 registry：

```python
from flows.xxx import build_registry, Shop   # 目标态
# ...
registry = build_registry()
# ...
ok = engine.run_until(Shop)
```

## 核心概念详解

### State（界面状态）

| 属性/方法 | 说明 |
|-----------|------|
| `name` | 界面名称，用于日志输出 |
| `signature` | `list[Anchor]`，全部命中才判定处于此界面 |
| `priority` | 优先级（默认 0），值越大越优先识别。弹框/报错/死亡等应为 100~999 |
| `match(ctx)` | 自动判断 signature 全部命中，通常无需覆写 |
| `handle(ctx)` | 在界面中执行动作，返回 `Signal` 驱动下一轮 |

### Signal（流程控制信号）

| 信号 | 含义 | 使用场景 |
|------|------|----------|
| `Goto(target)` | 期望下一轮进入 target 界面 | 点击按钮跳转后 |
| `Back()` | 回到上一界面 | 关闭弹框后 |
| `Done()` | 达成目标，结束循环 | 一轮操作完成时 |
| `Stay()` | 停留当前界面，重新识别 | 等待加载、目标态 |

### Anchor（锚点）

两种匹配模式：

```python
# 图像模板匹配（默认）
Anchor(ref=img.xxx)                              # 全屏搜索
Anchor(ref=img.xxx, region=[l, t, r, b])         # 限区域搜索（regions.yaml 自动注入）
Anchor(ref=img.xxx, threshold=0.9)               # 自定义阈值（默认 0.85）

# OCR 文字定位（无需参考图）
Anchor(text="확인", region=[l, t, r, b])          # 在区域内搜索韩文"확인"
```

`region` 优先级：显式传参 > `regions.yaml` 自动继承 > `None`（全屏搜索）

### Target（点击目标）

```python
Target.image(anchor)                     # 匹配 anchor → 点击其中心
Target.image(anchor, offset=(5, -5))    # 匹配 → 点击中心 + 偏移（偏移会 × scale）
Target.rel(anchor, dx=10, dy=0)         # 相对定位：点击中心 + (dx, dy) × scale
Target.at(x, y)                          # 绝对作图坐标 → 经标定换算为屏幕坐标
```

### ImageDir（参考图管理）

在类属性 `path` 指定的目录下，所有 `.png/.jpg/.jpeg/.bmp` 自动映射为 `ImageRef` 属性：

```
images/xxx/
├── home_sig.png       →  img.home_sig   (ImageRef)
├── shop_sig.png       →  img.shop_sig
├── popup_close.png    →  img.popup_close
└── regions.yaml       →  可选的搜索区域配置
```

`regions.yaml` 格式：

```yaml
home_sig: [100, 200, 300, 400]   # 限区域搜索
shop_sig: null                    # 全屏搜索（null 等价于不声明）
```

### Ctx（执行上下文）

State.handle(ctx) 中可用的核心方法：

| 方法 | 说明 |
|------|------|
| `ctx.find_anchor(anchor) → Match` | 匹配锚点，获取 `matched/box/center/confidence/scale` |
| `ctx.click(target) → bool` | 点击目标，返回是否成功 |
| `ctx.wait(seconds)` | 等待（期间可响应暂停/停止热键） |
| `ctx.check_state()` | 检查运行状态（已暂停则阻塞，已停止则抛 StopFlow） |
| `ctx.refresh_screenshot()` | 重新截屏（通常由引擎自动调用，无需手动） |

## 自愈机制

**这是引擎的核心能力**：弹框/报错/死亡等异常界面设高 priority，引擎识别时会优先命中它们。

关键设计点：
1. 给弹框类 State 设 `priority` 为 100 以上
2. 弹框的 `handle()` 中关闭弹框后返回 `Back()`
3. 弹框不需要在 `register()` 中声明 `transitions`（它通过 `Back()` 自动回到被中断的流程）
4. `base.py` 中预定义了通用异常处理（Death / ExpBack 等），可在 `build_registry()` 中复用

```python
from flows.base import Death, ExpBack

def build_registry() -> StateRegistry:
    reg = StateRegistry()
    # 先注册通用异常处理（高 priority，会被优先识别）
    reg.register(Death())
    reg.register(ExpBack())
    # 再注册业务 State
    reg.register(Home(), transitions=[Shop])
    # ...
    return reg
```

## 设计约定

1. **注释、日志、docstring 一律用简体中文**
2. **锚点图放到 `images/<流程名>/`**，不要混放
3. **Anchor 的 `region` 写的是作图坐标**（采集截图时的分辨率），运行时由 `Calibrator.to_screen_region()` 自动换算
4. **测试**：State 的纯逻辑（match/handle 无副作用部分）用 FakeCtx + fake matcher 做 pytest，触硬件的模块由真机冒烟验证
5. **配合 `base.py`**：通用的死亡/弹框等高优先级 State 放入 `base.py`，业务 flow 直接复用

## 现有流程参考

| 文件 | 用途 | 特点 |
|------|------|------|
| `flows/smoke.py` | 引擎框架端到端冒烟验证 | 最小流程：Home ↔ Panel，含 Popup 自愈 |
| `flows/base.py` | 通用高优先级异常处理 | Death（死亡复活）、ExpBack（经验寻回弹框） |
