"""背景主題色票（sudoku.themes）的單元測試。

測試接縫：themes 公開 API——內建色票清單、get_theme、色票欄位皆為合法色碼。
票券 06 只需預設淺色（light）；深色/馬卡龍由票券 09 補上。
"""

import re

import pytest

from sudoku.themes import LIGHT, THEMES, Theme, get_theme, theme_names

_色碼 = re.compile(r"^#[0-9A-Fa-f]{6}$")


def test_預設為淺色主題() -> None:
    assert get_theme() is LIGHT
    assert get_theme("light") is LIGHT
    assert theme_names() == ["light"]
    assert THEMES["light"] is LIGHT


def test_未知主題丟出例外() -> None:
    with pytest.raises(ValueError):
        get_theme("dark")


def test_淺色色票所有顏色欄位皆為合法色碼() -> None:
    欄位 = [f for f in LIGHT.__dataclass_fields__ if f != "名稱"]
    assert 欄位  # 色票必須定義顏色欄位
    for 名稱 in 欄位:
        值 = getattr(LIGHT, 名稱)
        assert _色碼.match(值), f"{名稱} 不是合法色碼：{值!r}"


def test_色票為不可變資料結構() -> None:
    assert isinstance(LIGHT, Theme)
    with pytest.raises(Exception):
        LIGHT.背景 = "#000000"  # type: ignore[misc]
