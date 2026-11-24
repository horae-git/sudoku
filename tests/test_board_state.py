"""棋盤局部狀態（sudoku.ui.board_state.BoardState）的單元測試。

測試接縫：BoardState 公開 API——選取、同行/列/宮與相同數字高亮集合、
填入（正確/錯誤）、錯誤計數、清除、方向鍵移動、完成偵測。
純邏輯、不依賴 customtkinter，headless 環境可執行。
票券 07 會以 sudoku.session.GameSession 取代此類別，屆時改接 session。
"""

import pytest

from sudoku.generator import Difficulty, daily_challenge, generate_puzzle
from sudoku.model import Puzzle, Solution
from sudoku.ui.board_state import BoardState, unique_solution

# 經典題目（固定種子，測試資料穩定）
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


def test_初始狀態與題目一致() -> None:
    state = _state()
    assert state.board == _PUZZLE_GRID
    assert state.selected is None
    assert state.mistakes == 0
    assert not state.completed
    assert state.related_cells() == set()
    assert state.same_value_cells() == set()


def test_選取格子() -> None:
    state = _state()
    state.select(4, 4)
    assert state.selected == (4, 4)


def test_選取座標非法時丟出例外() -> None:
    state = _state()
    with pytest.raises(ValueError):
        state.select(9, 0)
    with pytest.raises(ValueError):
        state.select(0, -1)


def test_同行列宮高亮集合正確() -> None:
    state = _state()
    state.select(0, 0)  # 第 0 行、第 0 列、第 0 宮
    cells = state.related_cells()
    assert (0, 8) in cells  # 同行
    assert (8, 0) in cells  # 同列
    assert (2, 2) in cells  # 同宮
    assert (0, 0) in cells
    assert (3, 3) not in cells  # 不同行列宮
    assert (4, 4) not in cells
    assert len(cells) == 21


def test_相同數字高亮集合正確() -> None:
    state = _state()
    state.select(0, 0)  # 值為 5；題目中其他 5 在 (1, 5) 與 (7, 8)
    assert state.same_value_cells() == {(0, 0), (1, 5), (7, 8)}
    state.select(0, 2)  # 空格：沒有相同數字
    assert state.same_value_cells() == set()


def test_填入正確數字() -> None:
    state = _state()
    state.select(0, 2)  # 解答為 4
    assert state.place(4) is True
    assert state.board[0][2] == 4
    assert not state.is_error(0, 2)
    assert state.mistakes == 0


def test_填錯立即標紅並計次() -> None:
    state = _state()
    state.select(0, 2)  # 解答為 4，填 5 即錯
    assert state.place(5) is True
    assert state.board[0][2] == 5
    assert state.is_error(0, 2)
    assert state.mistakes == 1
    # 再錯一次（同格改填另一個錯數）仍計次，紅色保留
    state.place(6)
    assert state.is_error(0, 2)
    assert state.mistakes == 2


def test_修改為正確後紅色消除但錯誤次數保留() -> None:
    state = _state()
    state.select(0, 2)
    state.place(5)
    state.place(4)  # 改填正確
    assert not state.is_error(0, 2)
    assert state.mistakes == 1


def test_題示格不可填入也不可清除() -> None:
    state = _state()
    state.select(0, 0)  # 題示數 5
    assert state.is_given(0, 0)
    assert state.place(1) is False
    assert state.board[0][0] == 5
    assert state.mistakes == 0
    assert state.clear() is False
    assert state.board[0][0] == 5


def test_清除玩家填入的格子() -> None:
    state = _state()
    state.select(0, 2)
    state.place(5)  # 錯
    assert state.clear() is True
    assert state.board[0][2] is None
    assert not state.is_error(0, 2)


def test_未選取格子時填入與清除皆無效() -> None:
    state = _state()
    assert state.place(1) is False
    assert state.clear() is False
    assert state.mistakes == 0


def test_填入數值範圍驗證() -> None:
    state = _state()
    state.select(0, 2)
    with pytest.raises(ValueError):
        state.place(0)
    with pytest.raises(ValueError):
        state.place(10)


def test_方向鍵移動並在邊界停駐() -> None:
    state = _state()
    state.select(0, 0)
    state.move(-1, 0)  # 上邊界：不動
    assert state.selected == (0, 0)
    state.move(0, -1)  # 左邊界：不動
    assert state.selected == (0, 0)
    state.move(1, 0)
    assert state.selected == (1, 0)
    state.select(8, 8)
    state.move(1, 1)  # 右下邊界：不動
    assert state.selected == (8, 8)


def test_未選取時移動先選第一格再移動() -> None:
    state = _state()
    state.move(1, 0)
    assert state.selected == (1, 0)


def test_全部填正即完成() -> None:
    state = _state()
    for r in range(9):
        for c in range(9):
            if state.puzzle.cell(r, c).value is None:
                state.select(r, c)
                assert state.place(state.solution.cell(r, c).value) is True
    assert state.completed
    # 完成後不再接受動作
    state.select(0, 2)
    assert state.place(1) is False
    assert state.clear() is False


def test_有錯誤時即使填滿也不算完成() -> None:
    state = _state()
    for r in range(9):
        for c in range(9):
            if state.puzzle.cell(r, c).value is None:
                state.select(r, c)
                correct = state.solution.cell(r, c).value
                # 第一個空格故意填錯，其餘填正
                state.place(correct if (r, c) != (0, 2) else (correct % 9) + 1)
    assert not state.completed


def test_unique_solution_回傳唯一解且與題目一致() -> None:
    """unique_solution：計數回溯（上限 2）驗證唯一後，回傳完整解答。"""
    puzzle = Puzzle.from_grid([row[:] for row in _PUZZLE_GRID])
    sol = unique_solution(puzzle)
    assert isinstance(sol, Solution)
    for cell in puzzle.cells:
        if cell.value is not None:
            assert sol.cell(cell.row, cell.col).value == cell.value


def test_unique_solution_對各難度生成題皆有唯一解() -> None:
    """generator 保證唯一解，unique_solution 對四難度與每日挑戰都應成功。"""
    for diff in Difficulty:
        sol = unique_solution(generate_puzzle(diff, seed=7))
        assert sol is not None
    sol = unique_solution(daily_challenge("2026-11-25"))
    assert sol is not None


def test_unique_solution_無唯一解時丟出例外() -> None:
    #構造一個明顯多解的題目（只給一格）
    grid = [[None] * 9 for _ in range(9)]
    grid[0][0] = 5
    with pytest.raises(ValueError):
        unique_solution(Puzzle.from_grid(grid))
