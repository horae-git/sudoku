"""棋盤畫面純邏輯函式（sudoku.ui.board）的單元測試。

測試接縫：board.py 中不依賴視窗的純函式——時間格式化 format_mmss、
格子外觀決策 cell_style（底色/文字色/粗體優先序）。
import customtkinter 在 headless 下即可成功，只有建立視窗才需要顯示器。
"""

from sudoku.model import Puzzle, Solution
from sudoku.themes import LIGHT
from sudoku.ui.board import cell_style, format_mmss
from sudoku.ui.board_state import BoardState

_PUZZLE_GRID = [
    [5, 3, None, None, 7, None, None, None, None],
    [6, None, None, 1, 9, 5, None, None, None],
    [None, 9, 8, None, None, None, None, 6, None],
    [8, None, None, None, 6, None, None, None, 3],
    [4, None, None, 8, None, 3, None, None, 1],
    [7, None, None, None, 2, None, None, None, 6],
    [None, 6, None, None, None, None, 2, 8, None],
    [None, None, None, 4, 1, 9, None, None, 5],
    [None, None, None, None, 8, None, None, 7, 9],
]

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


def _state() -> BoardState:
    puzzle = Puzzle.from_grid([row[:] for row in _PUZZLE_GRID])
    solution = Solution.from_grid([row[:] for row in _SOLUTION_GRID])
    return BoardState(puzzle, solution)


def test_format_mmss() -> None:
    assert format_mmss(0) == "00:00"
    assert format_mmss(9) == "00:09"
    assert format_mmss(65) == "01:05"
    assert format_mmss(599) == "09:59"
    assert format_mmss(3600) == "60:00"


def test_一般格子與題示格外觀() -> None:
    state = _state()
    fg, color, bold = cell_style(state, LIGHT, 0, 2)  # 空格
    assert (fg, color, bold) == (LIGHT.格子底, LIGHT.文字, False)
    fg, color, bold = cell_style(state, LIGHT, 0, 0)  # 題示數 5
    assert (fg, color, bold) == (LIGHT.格子題示底, LIGHT.文字題示, True)


def test_選取格外觀優先於一切() -> None:
    state = _state()
    state.select(0, 2)
    fg, color, bold = cell_style(state, LIGHT, 0, 2)
    assert (fg, color) == (LIGHT.格子選取底, LIGHT.格子選取文字)
    assert not bold


def test_同行列宮高亮與相同數字高亮() -> None:
    state = _state()
    state.select(0, 0)  # 值 5：同宮/行列內的格子吃高亮，相同數字吃同數底
    fg, color, _ = cell_style(state, LIGHT, 2, 2)  # 同宮、不同數字
    assert fg == LIGHT.格子高亮底
    fg, color, _ = cell_style(state, LIGHT, 7, 8)  # 相同數字 5（不同行列宮）
    assert fg == LIGHT.格子同數底
    fg, _, _ = cell_style(state, LIGHT, 4, 4)  # 無關
    assert fg == LIGHT.格子底


def test_題示格被高亮時仍維持題示樣式優先於普通格() -> None:
    state = _state()
    state.select(0, 2)
    # (0, 0) 是題示數 5，同時是同行格：吃高亮底，但文字仍為題示色且粗體
    fg, color, bold = cell_style(state, LIGHT, 0, 0)
    assert fg == LIGHT.格子高亮底
    assert (color, bold) == (LIGHT.文字題示, True)


def test_錯誤格紅色顯示() -> None:
    state = _state()
    state.select(0, 2)
    state.place(5)  # 錯
    # 未選取的錯誤格：錯誤底 + 紅字
    state.select(1, 1)
    fg, color, _ = cell_style(state, LIGHT, 0, 2)
    assert (fg, color) == (LIGHT.格子錯誤底, LIGHT.文字錯誤)
    # 被選取的錯誤格：底色為選取色，但文字仍紅
    state.select(0, 2)
    fg, color, _ = cell_style(state, LIGHT, 0, 2)
    assert (fg, color) == (LIGHT.格子選取底, LIGHT.文字錯誤)
