"""棋盤畫面純邏輯函式（sudoku.ui.board）的單元測試（票券 07：以 GameSession 驅動）。

測試接縫：board.py 中不依賴視窗的純函式——時間格式化 format_mmss、
格子外觀決策 cell_style（底色/文字色/粗體優先序，含提示綠）、
高亮集合 related_cells / same_value_cells、筆記 3×3 排版 notes_layout、
暫停遮罩旗標 pause_overlay_visible、模式標籤 mode_display_label。

import customtkinter 在 headless 下即可成功，只有建立視窗才需要顯示器。
"""

from sudoku.session import GameSession
from sudoku.themes import LIGHT
from sudoku.ui.board import (
    cell_style,
    format_mmss,
    mode_display_label,
    notes_layout,
    pause_overlay_visible,
    related_cells,
    same_value_cells,
)

# 經典完整解答（行/列/宮不重複），供建構可控的 session state_dict
_SOLUTION_GRID = [
    [5, 3, 4, 6, 7, 8, 9, 1, 2],
    [6, 7, 2, 1, 9, 5, 3, 4, 8],
    [1, 9, 8, 3, 4, 2, 5, 6, 7],
    [8, 5, 9, 7, 6, 1, 4, 2, 3],
    [4, 2, 6, 8, 5, 3, 7, 9, 1],
    [7, 1, 3, 9, 2, 4, 8, 5, 6],
    [9, 6, 1, 5, 3, 7, 2, 8, 4],
    [2, 8, 7, 4, 1, 9, 6, 3, 5],
    [3, 4, 5, 2, 8, 6, 1, 7, 9],
]
_SOLUTION_STR = "".join(str(v) for row in _SOLUTION_GRID for v in row)


def _可控局() -> GameSession:
    """建構一個可控的局：題示只有 (0,0)=5；玩家已在 (1,5) 填對 5（與 (0,0) 同數不同單元）。"""
    puzzle = ["0"] * 81
    puzzle[0] = "5"  # (0,0) 題示 5
    board = ["0"] * 81
    board[0] = "5"
    board[1 * 9 + 5] = "5"  # (1,5) 玩家填入、與解答一致
    state = {
        "puzzle": "".join(puzzle),
        "solution": _SOLUTION_STR,
        "board": "".join(board),
        "notes": [[] for _ in range(81)],
        "mistakes": 0,
        "hints_left": 3,
        "elapsed_sec": 0,
        "mode": "easy",
    }
    return GameSession.from_state_dict(state, "easy")


def _新局(seed=7) -> GameSession:
    return GameSession.new_game("easy", seed=seed)


def _空格索引(s: GameSession) -> list[int]:
    return [i for i in range(81) if s.board[i].value is None]


def _選(s: GameSession, i: int) -> None:
    r, c = divmod(i, 9)
    s.select(r, c)


def test_format_mmss() -> None:
    assert format_mmss(0) == "00:00"
    assert format_mmss(9) == "00:09"
    assert format_mmss(65) == "01:05"
    assert format_mmss(599) == "09:59"
    assert format_mmss(3600) == "60:00"


def test_一般格子與題示格外觀() -> None:
    s = _可控局()
    bg, fg, bold = cell_style(s, LIGHT, 0, 1)  # 空格
    assert (bg, fg, bold) == (LIGHT.格子底, LIGHT.文字, False)
    bg, fg, bold = cell_style(s, LIGHT, 0, 0)  # 題示數 5
    assert (bg, fg, bold) == (LIGHT.格子題示底, LIGHT.文字題示, True)


def test_選取格外觀優先於一切() -> None:
    s = _可控局()
    _選(s, 0 * 9 + 1)  # 選空格
    bg, fg, bold = cell_style(s, LIGHT, 0, 1)
    assert (bg, fg, bold) == (LIGHT.格子選取底, LIGHT.格子選取文字, False)
    _選(s, 0)  # 選題示格：底色選取優先，但不粗體
    bg, fg, bold = cell_style(s, LIGHT, 0, 0)
    assert (bg, fg, bold) == (LIGHT.格子選取底, LIGHT.格子選取文字, False)


def test_高亮集合正確() -> None:
    assert related_cells(None) == set()
    cells = related_cells((0, 0))
    assert (0, 8) in cells and (8, 0) in cells and (2, 2) in cells and (0, 0) in cells
    assert (3, 3) not in cells and len(cells) == 21

    s = _可控局()
    _選(s, 0)  # (0,0) 值 5；(1,5) 也是 5 但不同行列宮
    same = same_value_cells(s)
    assert (0, 0) in same and (1, 5) in same
    _選(s, 0 * 9 + 1)  # 空格：沒有相同數字
    assert same_value_cells(s) == set()


def test_同行列宮高亮與相同數字高亮底色() -> None:
    s = _可控局()
    _選(s, 0)  # (0,0)
    bg, _, _ = cell_style(s, LIGHT, 0, 1)  # 同行、空格
    assert bg == LIGHT.格子高亮底
    bg, _, _ = cell_style(s, LIGHT, 1, 5)  # 相同數字 5、不同行列宮
    assert bg == LIGHT.格子同數底
    bg, _, _ = cell_style(s, LIGHT, 8, 8)  # 無關
    assert bg == LIGHT.格子底


def test_錯誤格紅色顯示() -> None:
    s = _新局()
    i = _空格索引(s)[0]
    _選(s, i)
    正確 = int(s.solution[i])
    s.place(next(d for d in range(1, 10) if d != 正確))  # 填錯
    r, c = divmod(i, 9)
    _選(s, _空格索引(s)[1])  # 改選別格
    bg, fg, _ = cell_style(s, LIGHT, r, c)
    assert (bg, fg) == (LIGHT.格子錯誤底, LIGHT.文字錯誤)
    _選(s, i)  # 被選取的錯誤格：底色為選取色，文字仍紅
    bg, fg, _ = cell_style(s, LIGHT, r, c)
    assert (bg, fg) == (LIGHT.格子選取底, LIGHT.文字錯誤)


def test_提示格綠色粗體顯示() -> None:
    s = _新局(seed=9)
    res = s.hint()
    assert res is not None
    r, c, _ = res
    bg, fg, bold = cell_style(s, LIGHT, r, c)
    assert (bg, fg, bold) == (LIGHT.格子提示底, LIGHT.文字提示, True)
    _選(s, r * 9 + c)  # 選取中的提示格：底色選取優先、文字仍綠、不粗體
    bg, fg, bold = cell_style(s, LIGHT, r, c)
    assert (bg, fg, bold) == (LIGHT.格子選取底, LIGHT.文字提示, False)


def test_notes_layout_3x3排版() -> None:
    assert notes_layout(frozenset({1, 5, 9})) == [
        [True, False, False],
        [False, True, False],
        [False, False, True],
    ]
    assert notes_layout(frozenset()) == [[False] * 3 for _ in range(3)]
    assert notes_layout(frozenset(range(1, 10))) == [[True] * 3 for _ in range(3)]


def test_pause_overlay_visible() -> None:
    s = _新局()
    assert pause_overlay_visible(s) is False
    s.pause()
    assert pause_overlay_visible(s) is True
    s.resume()
    assert pause_overlay_visible(s) is False


def test_mode_display_label() -> None:
    assert mode_display_label("easy") == "簡單"
    assert mode_display_label("medium") == "中等"
    assert mode_display_label("hard") == "困難"
    assert mode_display_label("expert") == "專家"
    assert mode_display_label("daily", "2026-11-25") == "📅 本日題目（2026-11-25）"
    assert mode_display_label("daily") == "📅 每日挑戰"
