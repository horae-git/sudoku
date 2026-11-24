"""數獨領域模型：格子（Cell）、宮（Box）、題目（Puzzle）、解答（Solution）。

全部為不可變（frozen）資料結構，建構時即做合法性驗證。
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Cell:
    """格子：棋盤上第 row 列 col 行（0–8）的單位，value 為 1–9 或 None（空）。

    建構時驗證行列與數值範圍；宮索引由座標推導（左上為 0，橫向遞增）。
    """

    row: int
    col: int
    value: int | None = None

    def __post_init__(self) -> None:
        if not 0 <= self.row <= 8:
            raise ValueError(f"行索引超出範圍 0–8：{self.row}")
        if not 0 <= self.col <= 8:
            raise ValueError(f"列索引超出範圍 0–8：{self.col}")
        if self.value is not None and not 1 <= self.value <= 9:
            raise ValueError(f"數值超出範圍 1–9：{self.value}")

    @property
    def box_index(self) -> int:
        """所屬宮（Box）索引：0–8，左上為 0、橫向遞增。"""
        return (self.row // 3) * 3 + self.col // 3


@dataclass(frozen=True)
class Box:
    """宮：3×3 的九宮格區塊，index 0–8（左上為 0、橫向遞增）。"""

    index: int

    def __post_init__(self) -> None:
        if not 0 <= self.index <= 8:
            raise ValueError(f"宮索引超出範圍 0–8：{self.index}")

    @property
    def cells(self) -> tuple[Cell, ...]:
        """此宮包含的 9 個格子（僅代表座標，value 為 None）。"""
        base_row = (self.index // 3) * 3
        base_col = (self.index % 3) * 3
        return tuple(
            Cell(row=base_row + dr, col=base_col + dc)
            for dr in range(3)
            for dc in range(3)
        )


def _驗證盤面合法(grid: list[list[int | None]], 允許空格: bool) -> None:
    """驗證 9×9 盤面：形狀、數值範圍 1–9、行/列/宮內已有數字不得重複。"""
    if len(grid) != 9 or any(len(row) != 9 for row in grid):
        raise ValueError("盤面必須為 9×9")
    for row in grid:
        for value in row:
            if value is not None and not 1 <= value <= 9:
                raise ValueError(f"數值超出範圍 1–9：{value}")
    if not 允許空格:
        for row in grid:
            if any(value is None for value in row):
                raise ValueError("解答盤面不得有空格")
    已填 = lambda v: v is not None  # noqa: E731
    for r in range(9):
        _驗證單元無重複([grid[r][c] for c in range(9) if 已填(grid[r][c])], f"第 {r} 行")  # type: ignore[arg-type]
    for c in range(9):
        _驗證單元無重複([grid[r][c] for r in range(9) if 已填(grid[r][c])], f"第 {c} 列")  # type: ignore[arg-type]
    for b in range(9):
        box = Box(index=b)
        _驗證單元無重複(
            [grid[c.row][c.col] for c in box.cells if 已填(grid[c.row][c.col])],  # type: ignore[arg-type]
            f"第 {b} 宮",
        )


def _驗證單元無重複(values: list[int], 單元名稱: str) -> None:
    """檢查一個行/列/宮內的數字不得重複。"""
    if len(set(values)) != len(values):
        raise ValueError(f"{單元名稱}內數字重複")


@dataclass(frozen=True)
class Solution:
    """解答：9×9 完整填滿且合法的盤面，建構時驗證行/列/宮不重複。"""

    _grid: tuple[tuple[int, ...], ...]

    @classmethod
    def from_grid(cls, grid: list[list[int]]) -> "Solution":
        """由 9×9 的巢狀 list 建立解答，並驗證合法性。"""
        _驗證盤面合法(grid, 允許空格=False)
        return cls(_grid=tuple(tuple(row) for row in grid))  # type: ignore[arg-type]

    def cell(self, row: int, col: int) -> Cell:
        """取得第 row 列 col 行的格子。"""
        return Cell(row=row, col=col, value=self._grid[row][col])

    @property
    def cells(self) -> tuple[Cell, ...]:
        """全部 81 個格子（依行優先順序）。"""
        return tuple(
            Cell(row=r, col=c, value=self._grid[r][c])
            for r in range(9)
            for c in range(9)
        )


@dataclass(frozen=True)
class Puzzle:
    """題目：9×9 部分格子已填的盤面，行/列/宮內已有數字不得重複。"""

    _grid: tuple[tuple[int | None, ...], ...]

    @classmethod
    def from_grid(cls, grid: list[list[int | None]]) -> "Puzzle":
        """由 9×9 的巢狀 list（空格以 None 表示）建立題目，並驗證合法性。"""
        _驗證盤面合法(grid, 允許空格=True)
        return cls(_grid=tuple(tuple(row) for row in grid))

    def cell(self, row: int, col: int) -> Cell:
        """取得第 row 列 col 行的格子。"""
        return Cell(row=row, col=col, value=self._grid[row][col])

    @property
    def cells(self) -> tuple[Cell, ...]:
        """全部 81 個格子，依行優先順序。"""
        return tuple(
            Cell(row=r, col=c, value=self._grid[r][c])
            for r in range(9)
            for c in range(9)
        )
