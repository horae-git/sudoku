"""題目生成器（sudoku.generator）的單元測試。

測試接縫：sudoku.generator 的公開 API（SPEC.md Testing Decisions）。
唯一解以測試端獨立實作的計數回溯驗證，不依賴 generator 內部實作。
"""

import random
import time

import pytest

from sudoku.generator import Difficulty, daily_challenge, generate_puzzle, generate_solution
from sudoku.model import Puzzle, Solution


def _計數解答數量(puzzle: Puzzle, 上限: int = 2) -> int:
    """獨立的計數式回溯：計算題目解答數量（達上限即停止）。測試端自用，與實作無關。"""
    grid = [[puzzle.cell(r, c).value for c in range(9)] for r in range(9)]
    行已用 = [set() for _ in range(9)]
    列已用 = [set() for _ in range(9)]
    宮已用 = [set() for _ in range(9)]

    def 候選數(r: int, c: int) -> list[int]:
        已用 = 行已用[r] | 列已用[c] | 宮已用[(r // 3) * 3 + c // 3]
        return [v for v in range(1, 10) if v not in 已用]

    def 回溯() -> int:
        # 找候選數最少的空格（MRV），加速計數
        最佳: tuple[int, int] | None = None
        最佳候選: list[int] = []
        for r in range(9):
            for c in range(9):
                if grid[r][c] is not None:
                    continue
                候選 = 候選數(r, c)
                if not 候選:
                    return 0
                if 最佳 is None or len(候選) < len(最佳候選):
                    最佳 = (r, c)
                    最佳候選 = 候選
        if 最佳 is None:
            return 1
        r, c = 最佳
        b = (r // 3) * 3 + c // 3
        總數 = 0
        for v in 最佳候選:
            grid[r][c] = v
            行已用[r].add(v)
            列已用[c].add(v)
            宮已用[b].add(v)
            總數 += 回溯()
            grid[r][c] = None
            行已用[r].discard(v)
            列已用[c].discard(v)
            宮已用[b].discard(v)
            if 總數 >= 上限:
                return 總數
        return 總數

    for r in range(9):
        for c in range(9):
            v = grid[r][c]
            if v is not None:
                行已用[r].add(v)
                列已用[c].add(v)
                宮已用[(r // 3) * 3 + c // 3].add(v)
    return 回溯()


class TestGenerateSolution:
    """完整解生成：回溯產生合法且完整的 Solution。"""

    def test_生成合法完整解(self):
        sol = generate_solution(seed=42)
        assert isinstance(sol, Solution)
        assert all(sol.cell(r, c).value is not None for r in range(9) for c in range(9))

    def test_同種子產生相同完整解(self):
        assert generate_solution(seed=7) == generate_solution(seed=7)

    def test_不同種子通常產生不同完整解(self):
        assert generate_solution(seed=1) != generate_solution(seed=2)


class TestGeneratePuzzle:
    """依難度生成題目：MRV 挖空 + 唯一解保證。"""

    def test_生成的題目必唯一解(self):
        puzzle = generate_puzzle(Difficulty.MEDIUM, seed=123)
        assert isinstance(puzzle, Puzzle)
        assert _計數解答數量(puzzle) == 1

    @pytest.mark.parametrize("difficulty", list(Difficulty))
    def test_各難度生成的題目皆唯一解(self, difficulty):
        puzzle = generate_puzzle(difficulty, seed=99)
        assert _計數解答數量(puzzle) == 1

    def test_同種子同難度產生同一題(self):
        assert generate_puzzle(Difficulty.HARD, seed=2026) == generate_puzzle(Difficulty.HARD, seed=2026)

    def test_題目確實有挖空(self):
        puzzle = generate_puzzle(Difficulty.EASY, seed=5)
        已填 = sum(1 for cell in puzzle.cells if cell.value is not None)
        assert 已填 < 81


class TestDailyChallenge:
    """每日挑戰：日期字串為種子，同一天同一題、不同日期不同題。"""

    def test_同一日期種子產生同一題(self):
        assert daily_challenge("2026-11-24") == daily_challenge("2026-11-24")

    def test_不同日期產生不同題(self):
        assert daily_challenge("2026-11-24") != daily_challenge("2026-11-25")

    def test_每日挑戰題目唯一解(self):
        assert _計數解答數量(daily_challenge("2026-11-24")) == 1

    def test_非法日期格式應報錯(self):
        with pytest.raises(ValueError):
            daily_challenge("2026/11/24")


class TestGenerationSpeed:
    """生成速度：單題約 1 秒內。"""

    @pytest.mark.parametrize("difficulty", list(Difficulty))
    def test_各難度單題生成小於一秒(self, difficulty):
        開始 = time.perf_counter()
        generate_puzzle(difficulty, seed=7)
        assert time.perf_counter() - 開始 < 1.0

    def test_每日挑戰生成小於一秒(self):
        開始 = time.perf_counter()
        daily_challenge("2026-11-24")
        assert time.perf_counter() - 開始 < 1.0
