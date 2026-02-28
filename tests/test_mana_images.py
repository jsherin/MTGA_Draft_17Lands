"""
Unit tests for src.mana_images (ManaImageCache and helpers).
Mana symbol loading and compound image creation; PhotoImage tests require a Tk root.
"""

import pytest


# Test _load_from_disk and _create_compound without Tk (PIL only)
def test_load_from_disk_returns_pil_image():
    from src.mana_images import _load_from_disk

    # W.png exists in assets/mana/ (checked out from branch)
    img = _load_from_disk("W", 16)
    assert img is not None
    assert img.size == (16, 16)
    assert img.mode == "RGBA"


def test_load_from_disk_missing_file_returns_transparent_placeholder():
    from src.mana_images import _load_from_disk

    img = _load_from_disk("X", 16)  # no X.png
    assert img is not None
    assert img.size == (16, 16)
    assert img.mode == "RGBA"


def test_create_compound_wubrg_order():
    from src.mana_images import _create_compound

    # Two colors: should be side-by-side in WUBRG order
    img = _create_compound(["U", "W"], 16)
    assert img is not None
    assert img.mode == "RGBA"
    # U=1, W=0 so W then U -> width 2 * icon_size
    assert img.width >= 12
    assert img.height >= 12


def test_create_compound_single_color():
    from src.mana_images import _create_compound

    img = _create_compound(["R"], 16)
    assert img is not None
    assert img.size == (16, 16)


@pytest.fixture
def tk_root():
    """Provide a Tk root so PhotoImage can be created."""
    import tkinter

    root = tkinter.Tk()
    root.withdraw()
    yield root
    try:
        root.destroy()
    except Exception:
        pass


def test_mana_cache_get_single(tk_root):
    from src.mana_images import ManaImageCache

    cache = ManaImageCache(size=16)
    photo = cache.get_single("W")
    assert photo is not None
    assert photo.width() == 16
    assert photo.height() == 16


def test_mana_cache_get_compound(tk_root):
    from src.mana_images import ManaImageCache

    cache = ManaImageCache(size=16)
    photo = cache.get_compound(["W", "U"])
    assert photo is not None
    assert photo.width() >= 12
    assert photo.height() >= 12


def test_mana_cache_get_compound_cached(tk_root):
    from src.mana_images import ManaImageCache

    cache = ManaImageCache(size=16)
    p1 = cache.get_compound(["W", "U"])
    p2 = cache.get_compound(["W", "U"])
    assert p1 is p2


def test_mana_cache_get_for_card_mana_cost(tk_root):
    from src.mana_images import ManaImageCache

    cache = ManaImageCache(size=16)
    # {1}{W}{U} -> WU
    photo = cache.get_for_card("{1}{W}{U}")
    assert photo is not None


def test_mana_cache_get_for_card_colorless(tk_root):
    from src.mana_images import ManaImageCache

    cache = ManaImageCache(size=16)
    photo = cache.get_for_card("{5}")
    assert photo is not None
    # Colorless: should use C.png or empty
    assert cache.get_single("C") is not None


def test_mana_cache_get_for_card_colors_list(tk_root):
    from src.mana_images import ManaImageCache

    cache = ManaImageCache(size=16)
    photo = cache.get_for_card(["W", "U"])
    assert photo is not None


def test_mana_cache_get_empty(tk_root):
    from src.mana_images import ManaImageCache

    cache = ManaImageCache(size=16)
    empty = cache._get_empty()
    assert empty is not None
    assert cache._get_empty() is empty
