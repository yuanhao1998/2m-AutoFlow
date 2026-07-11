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
