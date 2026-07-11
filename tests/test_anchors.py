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
