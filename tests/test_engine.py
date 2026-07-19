from fsm.state import State, Done, Stay
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
