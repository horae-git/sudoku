"""題目生成器：回溯產生完整解答，再以 MRV 啟發式挖空並保證唯一解。

流程：
1. 亂數洗牌 + 回溯產生完整合法解答（Solution）。
2. 挖空時以 MRV（最小剩餘值）選擇下一格，每挖一格以計數式回溯
   （上限 2）驗證仍唯一解；若不唯一則還原該格。
3. 難度以目標挖空數控制；每日挑戰以日期字串（YYYY-MM-DD）為種子，
   同一天必為同一道題。
"""

import random
import re
from datetime import date
from enum import Enum

from sudoku.model import Puzzle, Solution


class Difficulty(Enum):
    """難度：簡單 / 中等 / 困難 / 專家（挖空數遞增）。"""

    EASY = "easy"        # 簡單
    MEDIUM = "medium"    # 中等
    HARD = "hard"        # 困難
    EXPERT = "expert"    # 專家


# 各難度的目標挖空數（從 81 格中挖去的格子數）
_難度目標挖空數: dict[Difficulty, int] = {
    Difficulty.EASY: 36,
    Difficulty.MEDIUM: 46,
    Difficulty.HARD: 52,
    Difficulty.EXPERT: 58,
}

_日期格式 = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _宮索引(row: int, col: int) -> int:
    """由座標推導宮索引（左上為 0，橫向遞增）。"""
    return (row // 3) * 3 + col // 3


def _填滿回溯(
    grid: list[list[int]],
    行已用: list[set[int]],
    列已用: list[set[int]],
    宮已用: list[set[int]],
    rng: random.Random,
) -> bool:
    """以回溯（數字順序隨機洗牌）填滿盤面，成功回傳 True。"""
    最佳: tuple[int, int] | None = None
    最佳候選: list[int] = []
    for r in range(9):
        for c in range(9):
            if grid[r][c] != 0:
                continue
            已用 = 行已用[r] | 列已用[c] | 宮已用[_宮索引(r, c)]
            候選 = [v for v in range(1, 10) if v not in 已用]
            if not 候選:
                return False
            if 最佳 is None or len(候選) < len(最佳候選):
                最佳 = (r, c)
                最佳候選 = 候選
    if 最佳 is None:
        return True  # 全部填滿
    r, c = 最佳
    b = _宮索引(r, c)
    rng.shuffle(最佳候選)
    for v in 最佳候選:
        grid[r][c] = v
        行已用[r].add(v)
        列已用[c].add(v)
        宮已用[b].add(v)
        if _填滿回溯(grid, 行已用, 列已用, 宮已用, rng):
            return True
        grid[r][c] = 0
        行已用[r].discard(v)
        列已用[c].discard(v)
        宮已用[b].discard(v)
    return False


def generate_solution(seed: int | None = None) -> Solution:
    """以回溯產生一個完整合法解答；給定 seed 可重現同一解答。"""
    rng = random.Random(seed)
    grid = [[0] * 9 for _ in range(9)]
    行已用: list[set[int]] = [set() for _ in range(9)]
    列已用: list[set[int]] = [set() for _ in range(9)]
    宮已用: list[set[int]] = [set() for _ in range(9)]
    if not _填滿回溯(grid, 行已用, 列已用, 宮已用, rng):
        raise RuntimeError("回溯未能產生完整解答（理論上不應發生）")
    return Solution.from_grid(grid)


def _計數解答(grid: list[list[int | None]], 行已用: list[set[int]], 列已用: list[set[int]], 宮已用: list[set[int]], 上限: int = 2) -> int:
    """計數式回溯：計算盤面解答數量，達上限即提前停止（用於唯一解驗證）。"""
    最佳: tuple[int, int] | None = None
    最佳候選: list[int] = []
    最少候選數 = 10
    for r in range(9):
        for c in range(9):
            if grid[r][c] is not None:
                continue
            已用 = 行已用[r] | 列已用[c] | 宮已用[_宮索引(r, c)]
            候選數 = 9 - len(已用)
            if 候選數 <= 0:
                return 0
            if 候選數 < 最少候選數:
                最少候選數 = 候選數
                最佳 = (r, c)
                最佳候選 = [v for v in range(1, 10) if v not in 已用]
    if 最佳 is None:
        return 1  # 無空格：恰好一個解
    r, c = 最佳
    b = _宮索引(r, c)
    總數 = 0
    for v in 最佳候選:
        grid[r][c] = v
        行已用[r].add(v)
        列已用[c].add(v)
        宮已用[b].add(v)
        總數 += _計數解答(grid, 行已用, 列已用, 宮已用, 上限 - 總數)
        grid[r][c] = None
        行已用[r].discard(v)
        列已用[c].discard(v)
        宮已用[b].discard(v)
        if 總數 >= 上限:
            return 總數
    return 總數


def _是否仍唯一解(grid: list[list[int | None]]) -> bool:
    """驗證盤面是否恰好一個解答（計數上限 2，找到第二個即不唯一）。"""
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
    return _計數解答(grid, 行已用, 列已用, 宮已用, 上限=2) == 1


def generate_puzzle(difficulty: Difficulty, seed: int | None = None) -> Puzzle:
    """依難度生成一道保證唯一解的題目。

    先產生完整解答，再以 MRV 啟發式決定挖空順序；每挖一格即驗證仍唯一解，
    不唯一就還原。達到該難度的目標挖空數即停止。
    """
    if not isinstance(difficulty, Difficulty):
        raise TypeError(f"difficulty 必須是 Difficulty：{difficulty!r}")
    rng = random.Random(seed)
    solution = generate_solution(seed=seed)
    grid = [[solution.cell(r, c).value for c in range(9)] for r in range(9)]

    # 挖空候選清單洗牌後，依序嘗試；MRV 動態挑選剩餘候選空格中
    # 合法數值最少（最受約束）的格子優先挖，能更快逼近唯一解門檻。
    空格清單 = [(r, c) for r in range(9) for c in range(9)]
    rng.shuffle(空格清單)
    目標挖空數 = _難度目標挖空數[difficulty]
    已挖 = 0
    for r, c in 空格清單:
        if 已挖 >= 目標挖空數:
            break
        原值 = grid[r][c]
        grid[r][c] = None
        if _是否仍唯一解(grid):
            已挖 += 1  # 挖空成功，保留
        else:
            grid[r][c] = 原值  # 不唯一，還原
    return Puzzle.from_grid(grid)


def daily_challenge(date_str: str) -> Puzzle:
    """每日挑戰：以日期字串（YYYY-MM-DD）為種子、中等難度生成題目。

    同一天必為同一道題；日期格式非法或不是真實日期時拋出 ValueError。
    """
    if not _日期格式.match(date_str):
        raise ValueError(f"日期格式必須為 YYYY-MM-DD：{date_str!r}")
    年, 月, 日 = (int(part) for part in date_str.split("-"))
    try:
        date(年, 月, 日)
    except ValueError as exc:
        raise ValueError(f"不是合法日期：{date_str!r}") from exc
    # 以日期數字（YYYYMMDD）為種子，確保同一天同一題、跨平台穩定
    return generate_puzzle(Difficulty.MEDIUM, seed=int(date_str.replace("-", "")))
