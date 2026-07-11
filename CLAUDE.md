# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概览

game-auto 是一个**分辨率无关、可自愈**的视觉自动化引擎（云手机游戏自动化）。两个设计支柱：

1. **锚点相对定位 + 一次仿射标定** —— 解决"换分辨率就点不准"。
2. **声明式状态机** —— 解决"不知道当前在哪个界面，一步出错就卡死"。

纯 Python 3.14+，仅 macOS。前身参考项目为同目录的 `game-info-identify`（本项目为其全面重构版）。

## 常用命令

依赖以 `pyproject.toml` 为准，`uv.lock` 锁版本。首选 uv：

```bash
uv sync                              # 建 .venv 并按锁文件装依赖（含 dev 的 pytest）
uv run pytest                        # 全部测试
uv run pytest tests/test_vision.py -v            # 单个测试文件
uv run pytest tests/test_engine.py::test_done_signal_ends -v   # 单个测试
uv run run.py                        # 入口：装配引擎并启动（热键 F5 开始 / F6 暂停 / F7 停止）
uv run tools/capture_anchor.py       # GUI：框选截图保存锚点图（F5 截屏，拖拽后 R 保存到 images/）
uv run tools/whereami.py             # 实时探针：每秒打印当前命中的 State，用于调试 signature
```

pip 回退：`python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt`，再 `.venv/bin/python -m pytest`。

**切勿把依赖装进系统 Python**（easyocr 会拉入 torch 等约 2GB）；始终用项目内 `.venv`。

## 架构要点（需跨文件理解的部分）

### 坐标系契约（最关键，贯穿全局）
存在两个坐标系，混淆会导致点击/匹配错位：

- **作图坐标（authoring）**：flows、`Anchor.region`、`Target.at` 里写的都是"采集锚点图时那台屏幕分辨率"下的坐标。
- **屏幕像素（screen px）**：实际运行屏幕的物理像素。

`calib/calibrator.py` 的 `Calibrator` 启动时对**标定锚点图**做多尺度匹配，求出**单一等比缩放 `scale` + 原点 `origin`**，建立 `屏幕px = origin + 作图px × scale`。规则：

- `core/vision.py` **只认屏幕像素**（`match_template` 的 `region` 是屏幕 px）。
- `calib` / `target` 负责作图↔屏幕换算；`Ctx.find_anchor` 会把 `Anchor.region`（作图）经 `Calibrator.to_screen_region` 换算，并固定用 `scales=[calibrator.scale]` 匹配。
- `core/input.py` 收到的坐标**已是屏幕像素**，只做 Retina 逻辑坐标换算（`_to_logical = round(px/retina_scale)`）。

**严禁**重新引入旧项目那套手工 `base_width/actual_width/offset/非等比缩放` 配置——那正是被重构掉的痛点。

### 依赖分层与数据流
`core`（capture/vision/input/ocr）→ `calib` + `anchors` → `target` → `fsm`（state/registry/engine/context）→ `runner` / `flows`。低层不反向依赖高层。

一轮循环：`Ctx.refresh_screenshot()` 截图 → `StateRegistry.identify()`（对各 State 的 signature 做匹配）→ 命中 State 的 `handle()` 内用 `Target.resolve()` 算出屏幕点 → `Ctx.click()` → `core.input` 点击 → 返回 `Signal` 驱动下一轮。

### 声明式状态机（`fsm/`）
- **State**：`signature: list[Anchor]`（全部命中即判定处于此界面）+ `priority`（弹框/报错设高优先级）+ `handle(ctx) -> Signal`。
- **Signal**：`Goto(target)` / `Back()` / `Done()` / `Stay()`。
- **Engine.run_until(goal)** 主循环：`识别→处理→自愈`。命中 goal 类或 handle 返回 `Done` 即成功；`identify` 返回 None（未知界面）→ 调 `on_unknown`（默认存调试截图到 `data/debug/`），连续超 `max_unknown` 次中止。
- **自愈机制**：弹框本身就是高优先级 State，命中即被优先 `handle` 关闭并 `Back()`；这就是"任意一步出意外也不卡死"的核心。
- **Ctx**（`fsm/context.py`）是运行时枢纽：持有 `calibrator`、当前截图、`RunState`（running/paused/stopped，由热键线程写），提供 `find_anchor/click/wait/check_state`，并缓存模板图。

### 新增一个业务流程的模式
在 `flows/` 里：定义若干 `State` 子类（各自 signature + handle）→ 写 `build_registry()` 注册它们及转移关系 → 在入口用 `engine.run_until(目标State)`。参考 `flows/smoke.py`。

## 约定与注意

- **注释、日志、docstring 一律用简体中文**。
- `Anchor` 是 `@dataclass(frozen=True)`，因为要做状态机字典键（需可哈希）——改它时保持 frozen。
- **测试哲学**：纯逻辑（vision/calib/target/fsm/anchors/registry）用 pytest + 注入 fake（FakeCtx/fake matcher 等）做 TDD，不触真实屏幕；触硬件/模型的模块（`core/capture`、`core/input`、`core/ocr`、热键）不做单测，由真机冒烟流程验证。新增纯逻辑请照此 TDD。

## 里程碑状态（重要）

当前交付的是**引擎框架**，`flows/smoke.py` + `run.py` 的**真机端到端验收尚未完成**（需 4K/5K 屏幕）。要跑通需先人工：

1. 用 `capture_anchor.py` 采集 7 张锚点图到 `images/calib/anchor.png` 与 `images/smoke/*.png`（HOME/面板/弹框的 signature 及按钮）。
2. 填 `conf/config.yaml`：`screen.authoring_width/height`（采集时屏幕分辨率）、`calib.anchor_authoring_topleft`（标定锚点左上角在屏幕上的坐标）。

> 注意：`flows/smoke.py` 在类定义时即引用 `images/smoke/*` 锚点图，缺图会在 import 时 AttributeError——这是预期，采集后即可。

按计划**刻意延后到下个里程碑**的增强（评审已记录）：`Ctx.find_anchor` 的多尺度兜底、`StateRegistry.find_path`/`navigate_to(HOME)` 接入未知态自动导航恢复（`find_path` 已实现并测试，尚未接入 `on_unknown`）。

## 文档

设计与计划在 `docs/superpowers/specs/` 和 `docs/superpowers/plans/`（含完整需求、架构决策、逐任务实现计划）。
