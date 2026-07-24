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
        self.registry = None
        self.refreshed = 0

    def check_state(self):
        pass

    def refresh_screenshot(self):
        self.refreshed += 1


class FakeRegistry:
    reset_flow = None

    def __init__(self, seq):
        self._seq = list(seq)
        self._i = 0

    def identify(self, ctx, *, expected=None):
        # 按顺序取下一项
        s = self._seq[min(self._i, len(self._seq) - 1)]
        self._i += 1
        # 模拟 StateRegistry：expected 非空时只返回该类型的实例
        if expected is not None and s is not None and not isinstance(s, expected):
            return None
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
    eng = Engine(reg, FakeCtx(), on_unknown=lambda ctx: calls.__setitem__("n", calls["n"] + 1),
                 unknown_wait=0, debug_interval=1)
    assert eng.run_until(Goal) is True
    assert calls["n"] == 2


def test_unknown_exceeds_limit_returns_false():
    reg = FakeRegistry([None, None, None, None])
    eng = Engine(reg, FakeCtx(), max_unknown=2, on_unknown=lambda ctx: None,
                 unknown_wait=0, debug_interval=1)
    assert eng.run_until(Goal) is False


def test_max_steps_exhausted_returns_false():
    home = Home()
    home.handle = lambda ctx: Stay()
    reg = FakeRegistry([home] * 10)
    eng = Engine(reg, FakeCtx(), max_steps=3)
    assert eng.run_until(Goal) is False


def test_goal_none_only_done_ends():
    """goal=None 时不靠界面识别终止，只看 Done 信号。"""
    home = Home()
    home.handle = lambda ctx: Stay()
    mid = Goal()  # Goal 类用来模拟"经过的其他界面"，不应触发终止
    mid.handle = lambda ctx: Stay()

    # 序列：home(Stay) → mid(Stay) → mid(Done)
    done_state = Home()
    done_state.handle = lambda ctx: Done()
    reg = FakeRegistry([home, mid, done_state])
    eng = Engine(reg, FakeCtx())
    assert eng.run_until(goal=None) is True
    # 验证：中途经过 Goal 类不会被误终止（因为 goal=None）


def test_goal_none_stay_never_ends_without_done():
    """goal=None 时如果没有 Done，最终步数耗尽返回 False。"""
    home = Home()
    home.handle = lambda ctx: Stay()
    reg = FakeRegistry([home] * 10)
    eng = Engine(reg, FakeCtx(), max_steps=4)
    assert eng.run_until(goal=None) is False


# ---- Goto 行为测试 ----

def test_goto_next_state_is_found():
    """Goto(X) 后下一轮只匹配 X，不匹配其他 State。"""
    a = Home()
    a.handle = lambda ctx: Goto(Goal)
    g = Goal()
    g.handle = lambda ctx: Done()
    reg = FakeRegistry([a, g])
    eng = Engine(reg, FakeCtx())
    assert eng.run_until(goal=None) is True


def test_goto_respects_expected_not_other():
    """Goto(X) 后即使其他 State 也在序列中，引擎只等 X。"""
    a = Home()
    a.handle = lambda ctx: Goto(Goal)
    other = Home()
    other.handle = lambda ctx: Stay()
    g = Goal()
    g.handle = lambda ctx: Done()

    # 序列：a(Goto Goal) → other(Stay, 意外) → Goal(Done)
    # 如果引擎不尊重 Goto，other 会被命中导致死循环
    # 正确行为：引擎设置 expected=Goal，会不断重试直到匹配
    reg = FakeRegistry([a, other, g])
    eng = Engine(reg, FakeCtx(), unknown_wait=0)
    assert eng.run_until(goal=None) is True
