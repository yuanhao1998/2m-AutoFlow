from pathlib import Path

from PIL import Image

from anchors.anchors import ImageRef, ImageDir, Anchor, _append_region


def test_imagedir_discovers_png(tmp_path):
    Image.new("RGB", (4, 4)).save(tmp_path / "btn_ok.png")
    Image.new("RGB", (4, 4)).save(tmp_path / "btn_cancel.png")

    d = ImageDir(str(tmp_path))

    assert isinstance(d["btn_ok"], ImageRef)
    assert d["btn_ok"].path.name == "btn_ok.png"
    names = {r.path.name for r in d.list_all()}
    assert "btn_cancel.png" in names


def test_validate_reports_missing(tmp_path):
    Image.new("RGB", (2, 2)).save(tmp_path / "present.png")
    d = ImageDir(str(tmp_path))
    # 手动注入一个不存在的 ref
    d._refs["gone"] = ImageRef(tmp_path / "gone.png")
    missing = d.validate()
    assert str(tmp_path / "gone.png") in missing
    assert str(tmp_path / "present.png") not in missing


def test_imageref_fspath(tmp_path):
    p = tmp_path / "x.png"
    Image.new("RGB", (2, 2)).save(p)
    ref = ImageRef(p)
    import os
    assert os.fspath(ref) == str(p)


# ---- region 从 regions.yaml 读取 ----

def test_imageref_region_from_yaml(tmp_path):
    Image.new("RGB", (4, 4)).save(tmp_path / "btn.png")
    (tmp_path / "regions.yaml").write_text(
        "btn: [100, 200, 300, 400]\n"
        "unknown: [1, 2, 3, 4]\n"
        "fullscreen: null\n",
        encoding="utf-8",
    )
    ref = ImageRef(tmp_path / "btn.png")
    assert ref.region == (100, 200, 300, 400)


def test_imageref_region_none_when_no_yaml(tmp_path):
    Image.new("RGB", (4, 4)).save(tmp_path / "x.png")
    ref = ImageRef(tmp_path / "x.png")
    assert ref.region is None


def test_imageref_region_none_when_key_missing(tmp_path):
    Image.new("RGB", (4, 4)).save(tmp_path / "other.png")
    (tmp_path / "regions.yaml").write_text("btn: [1,2,3,4]\n", encoding="utf-8")
    ref = ImageRef(tmp_path / "other.png")
    assert ref.region is None


def test_imageref_region_none_when_null(tmp_path):
    Image.new("RGB", (4, 4)).save(tmp_path / "fullscreen.png")
    (tmp_path / "regions.yaml").write_text(
        "fullscreen: null\n", encoding="utf-8",
    )
    ref = ImageRef(tmp_path / "fullscreen.png")
    assert ref.region is None


# ---- Anchor 继承 ref.region ----

def test_anchor_inherits_ref_region(tmp_path):
    Image.new("RGB", (4, 4)).save(tmp_path / "x.png")
    (tmp_path / "regions.yaml").write_text(
        "x: [10, 20, 30, 40]\n", encoding="utf-8",
    )
    ref = ImageRef(tmp_path / "x.png")
    a = Anchor(ref=ref)
    assert a.region == (10, 20, 30, 40)


def test_anchor_explicit_region_overrides_yaml(tmp_path):
    Image.new("RGB", (4, 4)).save(tmp_path / "x.png")
    (tmp_path / "regions.yaml").write_text(
        "x: [10, 20, 30, 40]\n", encoding="utf-8",
    )
    ref = ImageRef(tmp_path / "x.png")
    a = Anchor(ref=ref, region=(99, 99, 99, 99))
    assert a.region == (99, 99, 99, 99)


def test_anchor_defaults_and_frozen(tmp_path):
    Image.new("RGB", (2, 2)).save(tmp_path / "z.png")
    ref = ImageRef(tmp_path / "z.png")
    a = Anchor(ref=ref)
    assert a.region is None
    assert a.threshold == 0.85
    assert hash(a) == hash(Anchor(ref=ref))
    b = Anchor(ref=ref, region=(1, 2, 3, 4), threshold=0.9)
    assert b.region == (1, 2, 3, 4)


# ---- 文字锚点 ----

def test_text_anchor_no_ref():
    a = Anchor(text="확인", region=(100, 200, 300, 400))
    assert a.text == "확인"
    assert a.ref is None
    assert a.region == (100, 200, 300, 400)
    assert a.threshold == 0.85


def test_text_anchor_frozen_and_hashable():
    a = Anchor(text="확인")
    b = Anchor(text="확인")
    assert hash(a) == hash(b)
    assert a.ref is None
    assert a.region is None


# ---- _append_region ----

def test_append_region_creates_yaml(tmp_path):
    path = tmp_path / "btn.png"
    Image.new("RGB", (4, 4)).save(path)
    _append_region(path, (111, 222, 333, 444))
    ref = ImageRef(path)
    assert ref.region == (111, 222, 333, 444)


def test_append_region_merges_with_existing(tmp_path):
    (tmp_path / "regions.yaml").write_text("old: [1, 2, 3, 4]\n", encoding="utf-8")
    path = tmp_path / "new.png"
    Image.new("RGB", (4, 4)).save(path)
    _append_region(path, (5, 6, 7, 8))

    from anchors.anchors import _load_regions
    data = _load_regions(tmp_path)
    assert data["old"] == [1, 2, 3, 4]
    assert data["new"] == [5, 6, 7, 8]
