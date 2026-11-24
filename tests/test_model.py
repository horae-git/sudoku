"""領域模型（Cell / Box / Puzzle / Solution）的單元測試。

測試接縫：sudoku.model 的公開 API（SPEC.md Testing Decisions）。
"""

import pytest

from sudoku.model import Box, Cell, Puzzle, Solution


class TestCell:
    """格子：座標 0–8、數值 1–9 或空，不可變。"""

    def test_建立空格子(self):
        cell = Cell(row=0, col=0)
        assert cell.value is None

    def test_建立帶數值的格子(self):
        cell = Cell(row=4, col=5, value=7)
        assert (cell.row, cell.col, cell.value) == (4, 5, 7)

    @pytest.mark.parametrize("row,col", [(-1, 0), (9, 0), (0, -1), (0, 9)])
    def test_行列超出範圍應報錯(self, row, col):
        with pytest.raises(ValueError):
            Cell(row=row, col=col)

    @pytest.mark.parametrize("value", [0, 10, -1])
    def test_數值超出_1至9範圍應報錯(self, value):
        with pytest.raises(ValueError):
            Cell(row=0, col=0, value=value)

    def test_格子不可變(self):
        cell = Cell(row=0, col=0, value=1)
        with pytest.raises(AttributeError):
            cell.value = 5  # type: ignore[misc]

    def test_宮索引(self):
        assert Cell(row=0, col=0).box_index == 0
        assert Cell(row=4, col=5).box_index == 4
        assert Cell(row=8, col=8).box_index == 8


class TestBox:
    """宮：3×3 九宮格區塊，由 9 個格子組成，index 0–8。"""

    def test_宮含九個格子且座標正確(self):
        box = Box(index=4)  # 中央宮：row/col 3–5
        cells = box.cells
        assert len(cells) == 9
        assert sorted((c.row, c.col) for c in cells) == [
            (3, 3), (3, 4), (3, 5),
            (4, 3), (4, 4), (4, 5),
            (5, 3), (5, 4), (5, 5),
        ]

    def test_四個角宮的格子範圍(self):
        assert Box(index=0).cells[0] == Cell(row=0, col=0)
        assert Box(index=2).cells[0] == Cell(row=0, col=6)
        assert Box(index=6).cells[0] == Cell(row=6, col=0)
        assert Box(index=8).cells[0] == Cell(row=6, col=6)

    @pytest.mark.parametrize("index", [-1, 9])
    def test_宮索引超出範圍應報錯(self, index):
        with pytest.raises(ValueError):
            Box(index=index)

    def test_宮不可變(self):
        box = Box(index=0)
        with pytest.raises(AttributeError):
            box.index = 5  # type: ignore[misc]


# 一個已知合法的完整解（用於 Solution 測試的獨立已知解資料）
已知完整解: list[list[int]] = [
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


class TestSolution:
    """解答：9×9 完整填滿的盤面，行/列/宮不得重複、數字範圍 1–9。"""

    def test_合法完整解可建立(self):
        sol = Solution.from_grid(已知完整解)
        assert sol.cell(0, 0).value == 5
        assert sol.cell(8, 8).value == 9
        assert len(sol.cells) == 81

    def test_行內數字重複應報錯(self):
        壞解 = [row[:] for row in 已知完整解]
        壞解[0][1] = 壞解[0][0]  # 第一行出現兩個 5
        with pytest.raises(ValueError, match="行"):
            Solution.from_grid(壞解)

    def test_列內數字重複應報錯(self):
        壞解 = [row[:] for row in 已知完整解]
        # 在同一列內交換 (1,0) 與 (1,5)：行仍是排列，但第 0 列出現兩個 5
        壞解[1][0], 壞解[1][5] = 壞解[1][5], 壞解[1][0]
        with pytest.raises(ValueError, match="列"):
            Solution.from_grid(壞解)

    def test_宮內數字重複應報錯(self):
        壞解 = [row[:] for row in 已知完整解]
        # 交換第 0 行與第 3 行：行與列仍是排列，但第 0 宮出現重複數字
        壞解[0], 壞解[3] = 壞解[3], 壞解[0]
        with pytest.raises(ValueError, match="宮"):
            Solution.from_grid(壞解)

    @pytest.mark.parametrize("value", [0, 10])
    def test_數字超出_1至9應報錯(self, value):
        壞解 = [row[:] for row in 已知完整解]
        壞解[0][0] = value
        with pytest.raises(ValueError):
            Solution.from_grid(壞解)

    def test_盤面不是_9x9_應報錯(self):
        with pytest.raises(ValueError):
            Solution.from_grid([[1] * 9])

    def test_解答不可變(self):
        sol = Solution.from_grid(已知完整解)
        with pytest.raises(AttributeError):
            sol.cell(0, 0).value = 1  # type: ignore[misc]


# 從已知完整解挖去 (0,0) 與 (4,4) 後的題目（其唯一解即為 已知完整解）
已知題目盤面: list[list[int | None]] = [
    [None, 3, 4, 6, 7, 8, 9, 1, 2],
    [6, 7, 2, 1, 9, 5, 3, 4, 8],
    [1, 9, 8, 3, 4, 2, 5, 6, 7],
    [8, 5, 9, 7, 6, 1, 4, 2, 3],
    [4, 2, 6, 8, None, 3, 7, 9, 1],
    [7, 1, 3, 9, 2, 4, 8, 5, 6],
    [9, 6, 1, 5, 3, 7, 2, 8, 4],
    [2, 8, 7, 4, 1, 9, 6, 3, 5],
    [3, 4, 5, 2, 8, 6, 1, 7, 9],
]


class TestPuzzle:
    """題目：9×9 部分格子已填的盤面，行/列/宮內已有數字不得重複。"""

    def test_合法題目可建立(self):
        puzzle = Puzzle.from_grid(已知題目盤面)
        assert puzzle.cell(0, 0).value is None
        assert puzzle.cell(0, 1).value == 3
        assert len(puzzle.cells) == 81

    def test_題目格子帶宮索引(self):
        puzzle = Puzzle.from_grid(已知題目盤面)
        assert puzzle.cell(4, 5).box_index == 4

    def test_行內已有數字重複應報錯(self):
        壞題目 = [row[:] for row in 已知題目盤面]
        壞題目[0][2] = 壞題目[0][1]  # 第一行兩個 3
        with pytest.raises(ValueError, match="行"):
            Puzzle.from_grid(壞題目)

    def test_列內已有數字重複應報錯(self):
        壞題目 = [row[:] for row in 已知題目盤面]
        # 交換第 1 行的 (1,0)=6 與 (1,5)=5：行仍合法，但第 0 列出現兩個 6
        壞題目[1][0], 壞題目[1][5] = 壞題目[1][5], 壞題目[1][0]
        with pytest.raises(ValueError, match="列"):
            Puzzle.from_grid(壞題目)

    def test_宮內已有數字重複應報錯(self):
        壞題目 = [row[:] for row in 已知題目盤面]
        # 交換第 0 行與第 3 行：行與列仍合法，但第 0 宮出現重複數字
        壞題目[0], 壞題目[3] = 壞題目[3], 壞題目[0]
        with pytest.raises(ValueError, match="宮"):
            Puzzle.from_grid(壞題目)

    @pytest.mark.parametrize("value", [0, 10])
    def test_題目數字超出_1至9應報錯(self, value):
        壞題目 = [row[:] for row in 已知題目盤面]
        壞題目[0][0] = value
        with pytest.raises(ValueError):
            Puzzle.from_grid(壞題目)

    def test_盤面不是_9x9_應報錯(self):
        with pytest.raises(ValueError):
            Puzzle.from_grid([[None] * 9])

    def test_空格以_None_表示且不可變(self):
        puzzle = Puzzle.from_grid(已知題目盤面)
        cell = puzzle.cell(0, 0)
        assert cell.value is None
        with pytest.raises(AttributeError):
            cell.value = 5  # type: ignore[misc]
