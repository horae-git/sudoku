"""棋盤畫面的局部對局狀態（票券 06 暫用；07 會改接 sudoku.session.GameSession）。

純邏輯、不依賴 customtkinter，可在 headless 環境以 pytest 測試：

- ``BoardState(puzzle, solution)``：持有題目、解答與玩家目前的棋盤（9×9 list）。
- 選取 / 高亮集合（同行列宮、相同數字）、填入（判斷對錯、立即標紅並計次）、
  清除（題示數不可清）、方向鍵移動、完成偵測。

UI（board.py）只負責繪製與事件轉發，所有判定都在本類別。
"""

from sudoku.model import Puzzle, Solution

Grid = list[list[int | None]]


def _宮索引(row: int, col: int) -> int:
    return (row // 3) * 3 + col // 3


def unique_solution(puzzle: Puzzle) -> Solution:
    """以計數式回溯（上限 2）驗證題目恰好一個解後，回傳該解答。

    generator 保證唯一解，故正常情況必定成功；若題目多解或無解則拋出 ValueError。
    （solver.solve 是技巧鏈求解器，超出 swordfish 的題目會回傳 solved=False，
    因此 UI 不能拿它當解答來源，需用此完整回溯。）
    """
    grid: Grid = [[puzzle.cell(r, c).value for c in range(9)] for r in range(9)]
    行已用: list[set[int]] = [set() for _ in range(9)]
    列已用: list[set[int]] = [set() for _ in range(9)]
    宮已用: list[set[int]] = [set() for _ in range(9)]
    for r in range(9):
        for c in range(9):
            v = grid[r][c]
            if v is not None:
                行已用[r].add(v)
                列已用[c].add(v)
                宮已用[_宮索引(r, c)].add(v)

    找到的解: list[list[list[int]]] = []

    def 回溯() -> bool:
        """計數回溯；找到第二個解即回傳 True（提前停止）。"""
        最佳: tuple[int, int] | None = None
        最佳候選: list[int] = []
        最少 = 10
        for r in range(9):
            for c in range(9):
                if grid[r][c] is not None:
                    continue
                已用 = 行已用[r] | 列已用[c] | 宮已用[_宮索引(r, c)]
                候選數 = 9 - len(已用)
                if 候選數 <= 0:
                    return False
                if 候選數 < 最少:
                    最少 = 候選數
                    最佳 = (r, c)
                    最佳候選 = [v for v in range(1, 10) if v not in 已用]
        if 最佳 is None:
            找到的解.append([row[:] for row in grid])
            return len(找到的解) >= 2
        r, c = 最佳
        b = _宮索引(r, c)
        for v in 最佳候選:
            grid[r][c] = v
            行已用[r].add(v)
            列已用[c].add(v)
            宮已用[b].add(v)
            if 回溯():
                grid[r][c] = None
                return True
            grid[r][c] = None
            行已用[r].discard(v)
            列已用[c].discard(v)
            宮已用[b].discard(v)
        return False

    回溯()
    if len(找到的解) == 1:
        return Solution.from_grid(找到的解[0])
    raise ValueError(f"題目沒有唯一解（找到 {len(找到的解)} 個解）")


class BoardState:
    """一局棋盤的局部狀態：棋盤資料 + 選取 + 錯誤 + 完成旗標。"""

    def __init__(self, puzzle: Puzzle, solution: Solution) -> None:
        if not isinstance(puzzle, Puzzle):
            raise TypeError(f"puzzle 必須是 Puzzle：{puzzle!r}")
        if not isinstance(solution, Solution):
            raise TypeError(f"solution 必須是 Solution：{solution!r}")
        self.puzzle = puzzle
        self.solution = solution
        self.board: Grid = [[puzzle.cell(r, c).value for c in range(9)] for r in range(9)]
        self.selected: tuple[int, int] | None = None
        self.mistakes = 0
        self.completed = False
        # 錯誤格集合（set of (row, col)）；紅色保留直到玩家修改該格
        self._errors: set[tuple[int, int]] = set()

    # ---------- 選取與高亮 ----------

    @staticmethod
    def _檢查座標(row: int, col: int) -> None:
        if not (0 <= row <= 8 and 0 <= col <= 8):
            raise ValueError(f"座標超出範圍 0–8：({row}, {col})")

    def select(self, row: int, col: int) -> None:
        """選取第 row 列 col 行的格子（供滑鼠點擊與方向鍵移動共用）。"""
        self._檢查座標(row, col)
        self.selected = (row, col)

    def move(self, drow: int, dcol: int) -> None:
        """方向鍵移動選取；已在邊界則停駐；尚無選取時先選 (0, 0) 再移動。"""
        r, c = self.selected if self.selected is not None else (0, 0)
        r = min(8, max(0, r + drow))
        c = min(8, max(0, c + dcol))
        self.selected = (r, c)

    def related_cells(self) -> set[tuple[int, int]]:
        """與選取格同行 / 同列 / 同宮的格子集合（含選取格本身）；未選取回傳空集合。"""
        if self.selected is None:
            return set()
        r, c = self.selected
        cells: set[tuple[int, int]] = set()
        for i in range(9):
            cells.add((r, i))  # 同行
            cells.add((i, c))  # 同列
        br, bc = (r // 3) * 3, (c // 3) * 3
        for dr in range(3):
            for dc in range(3):
                cells.add((br + dr, bc + dc))  # 同宮
        return cells

    def same_value_cells(self) -> set[tuple[int, int]]:
        """盤面上與選取格數字相同的格子集合（選取格為空則回傳空集合）。"""
        if self.selected is None:
            return set()
        r, c = self.selected
        value = self.board[r][c]
        if value is None:
            return set()
        return {(rr, cc) for rr in range(9) for cc in range(9) if self.board[rr][cc] == value}

    # ---------- 動作 ----------

    def is_given(self, row: int, col: int) -> bool:
        """該格是否為題目給定的題示數（不可填入、不可清除）。"""
        self._檢查座標(row, col)
        return self.puzzle.cell(row, col).value is not None

    def is_error(self, row: int, col: int) -> bool:
        """該格是否目前標記為錯誤（填錯且尚未修改）。"""
        self._檢查座標(row, col)
        return (row, col) in self._errors

    def place(self, value: int) -> bool:
        """在選取格填入 1–9。

        - 题示格、未選取或已完成時回傳 False（不動作）；
        - 填錯：格子記入錯誤集合（立即標紅）、錯誤次數 +1，回傳 True（仍算填入）；
        - 填對：清掉該格錯誤標記；填滿且全部正確時 ``completed`` 設為 True。
        """
        if not 1 <= value <= 9:
            raise ValueError(f"數值超出範圍 1–9：{value}")
        if self.completed or self.selected is None:
            return False
        r, c = self.selected
        if self.is_given(r, c):
            return False
        self.board[r][c] = value
        if value == self.solution.cell(r, c).value:
            self._errors.discard((r, c))
        else:
            self._errors.add((r, c))
            self.mistakes += 1
        self._檢查完成()
        return True

    def clear(self) -> bool:
        """清除選取格（題示數、未選取或已完成時回傳 False）。"""
        if self.completed or self.selected is None:
            return False
        r, c = self.selected
        if self.is_given(r, c) or self.board[r][c] is None:
            return False
        self.board[r][c] = None
        self._errors.discard((r, c))
        return True

    def _檢查完成(self) -> None:
        """盤面填滿且與解答一致、無任何錯誤標記時，標記本局完成。"""
        for r in range(9):
            for c in range(9):
                if self.board[r][c] != self.solution.cell(r, c).value:
                    return
        if not self._errors:
            self.completed = True
