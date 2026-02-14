"""Load and cache mana symbol images from assets/mana/ for table display."""

import io
import os
import tempfile
from tkinter import PhotoImage

from PIL import Image

from src import constants
from src.card_logic import get_card_colors

_ASSETS_MANA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "assets",
    "mana",
)


def _load_from_disk(color_key: str, size: int) -> Image.Image:
    """Load mana symbol PNG from assets/mana/. Returns transparent placeholder if missing."""
    path = os.path.join(_ASSETS_MANA_DIR, f"{color_key}.png")
    try:
        img = Image.open(path).convert("RGBA")
        if img.size != (size, size):
            img = img.resize((size, size), Image.Resampling.LANCZOS)
        return img
    except Exception:
        return Image.new("RGBA", (size, size), (0, 0, 0, 0))


class ManaImageCache:
    """Cache of mana symbol PhotoImages for use in Treeview and Menu widgets."""

    def __init__(self, size: int = 16):
        self.size = size
        self._cache = {}
        self._empty = None

    def _get_empty(self) -> PhotoImage:
        """Return a transparent placeholder for colorless/unknown."""
        if self._empty is None:
            img = Image.new("RGBA", (self.size, self.size), (0, 0, 0, 0))
            self._empty = _pil_to_photoimage(img)
        return self._empty

    def get_single(self, color_key: str) -> PhotoImage:
        """Get PhotoImage for a single color (W, U, B, R, G, C)."""
        if color_key not in self._cache:
            img = _load_from_disk(color_key, self.size)
            self._cache[color_key] = _pil_to_photoimage(img)
        return self._cache[color_key]

    def get_compound(self, color_keys: list) -> PhotoImage:
        """Get PhotoImage for multiple colors placed side-by-side in WUBRG order."""
        if not color_keys:
            return self._get_empty()
        if len(color_keys) == 1:
            return self.get_single(color_keys[0])
        cache_key = "".join(
            sorted(
                color_keys,
                key=lambda c: (
                    constants.CARD_COLORS.index(c)
                    if c in constants.CARD_COLORS
                    else 99
                ),
            )
        )
        if cache_key not in self._cache:
            img = _create_compound(color_keys, self.size)
            self._cache[cache_key] = _pil_to_photoimage(img)
        return self._cache[cache_key]

    def get_for_card(
        self, mana_cost_or_colors, mana_cost_fallback: str | None = None
    ) -> PhotoImage:
        """Get mana image for a card based on mana cost or color list.
        When mana_cost_or_colors is a list, mana_cost_fallback can be used to fix
        misreported colors (e.g. ['C'] when mana cost has {B} -> use B.png)."""
        if isinstance(mana_cost_or_colors, list):
            colors = [
                c
                for c in mana_cost_or_colors
                if c in constants.CARD_COLORS or c == "C"
            ]
            if (
                colors == ["C"]
                and mana_cost_fallback
                and "B" in (mana_cost_fallback or "")
            ):
                colors = sorted(
                    get_card_colors(mana_cost_fallback).keys(),
                    key=constants.CARD_COLORS.index,
                )
            else:
                colors = sorted(
                    colors,
                    key=lambda c: (
                        constants.CARD_COLORS.index(c)
                        if c in constants.CARD_COLORS
                        else 99
                    ),
                )
        else:
            cost_colors = get_card_colors(mana_cost_or_colors or "").keys()
            colors = sorted(
                [c for c in cost_colors if c in constants.CARD_COLORS],
                key=constants.CARD_COLORS.index,
            )
        if not colors:
            return self._get_empty()
        return self.get_compound(colors)


def _create_compound(color_keys: list, size: int) -> Image.Image:
    """Place single-color icons side-by-side in WUBRG order.
    Uses slightly smaller icons for 2+ colors to fit in the tree column."""
    ordered = sorted(
        color_keys,
        key=lambda c: constants.CARD_COLORS.index(c)
        if c in constants.CARD_COLORS
        else 99,
    )
    n = len(ordered)
    icon_size = max(12, size - 4) if n > 1 else size
    width = n * icon_size
    composite = Image.new("RGBA", (width, icon_size), (0, 0, 0, 0))
    for i, key in enumerate(ordered):
        icon = _load_from_disk(key, size)
        if icon_size != size:
            icon = icon.resize((icon_size, icon_size), Image.Resampling.LANCZOS)
        composite.paste(icon, (i * icon_size, 0), icon)
    return composite


def _pil_to_photoimage(pil_image: Image.Image) -> PhotoImage:
    """Convert PIL Image to tkinter PhotoImage."""
    buffer = io.BytesIO()
    pil_image.save(buffer, format="PNG")
    buffer.seek(0)
    png_bytes = buffer.getvalue()
    try:
        return PhotoImage(data=png_bytes)
    except Exception:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(png_bytes)
            path = f.name
        try:
            return PhotoImage(file=path)
        finally:
            os.unlink(path)
