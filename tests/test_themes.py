"""背景主題色票（sudoku.themes）的單元測試。

測試接縫：themes 公開 API——內建色票清單（淺色/深色/馬卡龍）、get_theme、
色票欄位皆為合法色碼、深色主題的宮粗線更粗且更亮（票券 09 需求）。
"""

import re

import pytest

from sudoku.themes import (
    DARK,
    LIGHT,
    MACARON,
    THEME_LABELS,
    THEME_ORDER,
    THEMES,
    Theme,
    get_theme,
    theme_names,
)

_色碼 = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _亮度(色碼: str) -> float:
    """sRGB 相對亮度（0–255）。"""
    r = int(色碼[1:3], 16)
    g = int(色碼[3:5], 16)
    b = int(色碼[5:7], 16)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


class Test色票清單:
    """內建三套主題：light / dark / macaron，順序固定，預設為淺色。"""

    def test_內建三套主題且順序固定(self) -> None:
        assert theme_names() == ["light", "dark", "macaron"]
        assert THEME_ORDER == ("light", "dark", "macaron")
        assert set(THEMES) == {"light", "dark", "macaron"}
        assert THEMES["light"] is LIGHT
        assert THEMES["dark"] is DARK
        assert THEMES["macaron"] is MACARON

    def test_預設為淺色主題(self) -> None:
        assert get_theme() is LIGHT
        assert get_theme("light") is LIGHT
        assert get_theme("dark") is DARK
        assert get_theme("macaron") is MACARON

    def test_每套主題都有中文顯示名稱(self) -> None:
        assert set(THEME_LABELS) == {"light", "dark", "macaron"}
        assert THEME_LABELS["light"] == "淺色"
        assert THEME_LABELS["dark"] == "深色"
        assert THEME_LABELS["macaron"] == "馬卡龍"

    def test_未知主題丟出例外(self) -> None:
        with pytest.raises(ValueError):
            get_theme("nightmare")


class Test色票欄位合法:
    """三套色票的所有顏色欄位皆為合法 #RRGGBB 色碼。"""

    @pytest.mark.parametrize("theme", [LIGHT, DARK, MACARON], ids=theme_names())
    def test_所有顏色欄位皆為合法色碼(self, theme: Theme) -> None:
        欄位 = [f for f in theme.__dataclass_fields__ if f != "名稱"]
        assert 欄位
        for 名稱 in 欄位:
            值 = getattr(theme, 名稱)
            if 名稱 in ("宮粗線寬", "圓角"):
                assert isinstance(值, int) and 值 >= 1
                continue
            assert _色碼.match(值), f"{theme.名稱}.{名稱} 不是合法色碼：{值!r}"

    def test_色票為不可變資料結構(self) -> None:
        assert isinstance(LIGHT, Theme)
        with pytest.raises(Exception):
            LIGHT.背景 = "#000000"  # type: ignore[misc]


class Test深色主題宮粗線更明顯:
    """票券 09 需求：深色主題下 3×3 宮粗線線寬與亮度都特別加強。"""

    def test_深色宮粗線比淺色更粗(self) -> None:
        assert DARK.宮粗線寬 > LIGHT.宮粗線寬
        assert DARK.宮粗線寬 > MACARON.宮粗線寬

    def test_深色宮粗線在深色背景上更亮更明顯(self) -> None:
        # 宮粗線亮度需高於背景與一般格線（深色底上才跳得出來）
        assert _亮度(DARK.宮粗線) > _亮度(DARK.背景)
        assert _亮度(DARK.宮粗線) > _亮度(DARK.格線)
        # 且比淺色主題的宮粗線更亮
        assert _亮度(DARK.宮粗線) > _亮度(LIGHT.宮粗線)

    def test_深色背景比淺色背景深(self) -> None:
        assert _亮度(DARK.背景) < _亮度(LIGHT.背景)
        # 深色格線比深色背景亮（格線在深色下仍可見）
        assert _亮度(DARK.格線) > _亮度(DARK.背景)

    def test_淺色與馬卡龍宮粗線寬為一般值(self) -> None:
        assert LIGHT.宮粗線寬 == 3
        assert MACARON.宮粗線寬 == 3
