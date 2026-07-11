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
