from fsm.state import State
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


def test_find_path_transitive():
    class A(State):
        name = "a"

    class B(State):
        name = "b"

    class C(State):
        name = "c"

    reg = StateRegistry()
    reg.register(A(), transitions=[B])
    reg.register(B(), transitions=[C])
    reg.register(C())
    assert reg.find_path(A, C) == [B, C]
