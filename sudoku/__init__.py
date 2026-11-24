"""數獨遊戲 package：純邏輯核心（model / generator / solver / session / storage）與 UI 層分離。"""

from sudoku.generator import daily_challenge, generate_puzzle, generate_solution
from sudoku.model import Box, Cell, Puzzle, Solution
from sudoku.session import HINTS_PER_GAME, GameSession, SessionCell
from sudoku.solver import Difficulty  # 唯一的 Difficulty 定義（generator 由此再匯出）

__all__ = [
    "Box",
    "Cell",
    "Difficulty",
    "GameSession",
    "HINTS_PER_GAME",
    "Puzzle",
    "SessionCell",
    "Solution",
    "daily_challenge",
    "generate_puzzle",
    "generate_solution",
]
