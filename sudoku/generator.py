"""題目生成器：回溯產生完整解答，再以 MRV 啟發式挖空並保證唯一解。

流程：
1. 亂數洗牌 + 回溯產生完整合法解答（Solution）。
2. 挖空時以 MRV（最小剩餘值）選擇下一格，每挖一格以計數式回溯
   （上限 2，solver.count_solutions）驗證仍唯一解；若不唯一則還原該格。
3. 難度門檻：生成後用 solver.difficulty_of 分級，不符目標難度即以新种子重抽
   （嘗試上限見 _MAX_ATTEMPTS；超過上限時放寬為「挖空數達標即可」，避免卡死）。
   每日挑戰以日期字串（YYYY-MM-DD）為種子，並在種子上加嘗試計數器 derive
   子種子，保證同一天結果仍穩定。
"""

import random
import re
from datetime import date

from sudoku.model import Puzzle, Solution
from sudoku.solver import Difficulty, Technique, count_solutions, difficulty_of

# 由 solver 再匯出，保持 `from sudoku.generator import Difficulty` 可用（單一定義）
__all__ = ["Difficulty", "daily_challenge", "generate_puzzle", "generate_solution"]


# 各難度的目標挖空數（從 81 格中挖去的格子數，遞增）；超過嘗試上限時放寬為達標即可
# MEDIUM/HARD 需要較深的挖空才常見 pair/locked/X-wing，否則門檻重抽命中率太低
# EASY 目標 40：太淺時重抽很難再壓低技巧，40 格深度下 singles 占絕大多數
_難度目標挖空數: dict[Difficulty, int] = {
    Difficulty.EASY: 40,
    Difficulty.MEDIUM: 54,
    Difficulty.HARD: 50,
    Difficulty.EXPERT: 58,
}

# 各難度的門檻重抽嘗試上限（每次嘗試以「種子 + 嘗試次數」derive 子種子重新生成）。
# 超過「上限 − _放寬剩餘嘗試數」後，接受挖空數達標的題（放寬門檻，避免卡死）。
_MAX_ATTEMPTS: dict[Difficulty, int] = {
    Difficulty.EASY: 30,  # EASY 在淺挖時幾乎必過，上限只是保險
    Difficulty.MEDIUM: 30,  # target 54 時 pair/locked 命中率約 4 成
    Difficulty.HARD: 12,  # 深挖下 X_WING 極稀有，多半走放寬（挖空數達標）
    Difficulty.EXPERT: 30,  # 深挖下「技巧鏈解不開」約五成，很快命中 EXPERT
}
_放寬剩餘嘗試數: int = 8


def _門檻符合(report, difficulty: Difficulty) -> bool:
    """difficulty_of 的結果是否符合目標難度的技巧門檻。

    - EASY：max_technique ≤ SINGLE_HIDDEN；
    - MEDIUM：PAIR_NAKED..LOCKED_CANDIDATES；
    - HARD：SUBSETS（triple/quad）以上，即 X_WING、或更難（含技巧鏈解不開歸 EXPERT 也接受）；
    - EXPERT：SWORDFISH 或技巧鏈解不開（solved=False，difficulty_of標為 SWORDFISH）。
    """
    tech = report.max_technique
    if difficulty is Difficulty.EASY:
        return report.difficulty is Difficulty.EASY and (tech is None or tech <= Technique.SINGLE_HIDDEN)
    if difficulty is Difficulty.MEDIUM:
        return (
            report.difficulty is Difficulty.MEDIUM
            and tech is not None
            and Technique.PAIR_NAKED <= tech <= Technique.LOCKED_CANDIDATES
        )
    if difficulty is Difficulty.HARD:
        return report.difficulty in (Difficulty.HARD, Difficulty.EXPERT) and (
            not report.solved or (tech is not None and tech >= Technique.SUBSETS)
        )
    # EXPERT：swordfish 或技巧鏈解不開（difficulty_of 已把解不開標為 SWORDFISH）
    return report.difficulty is Difficulty.EXPERT


def _挖空數達標(puzzle: Puzzle, difficulty: Difficulty) -> bool:
    """放寬門檻時的保底：挖空數需達到目標。"""
    已填 = sum(1 for cell in puzzle.cells if cell.value is not None)
    return (81 - 已填) >= _難度目標挖空數[difficulty]


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


def _計數解答(grid: list[list[int | None]], 行已用: list[set[int]], 列已用: list[set[int]], 宮已用: list[set[int]], 上限: int = 2) -> int:
    """計數式回溯：計算盤面解答數量，達上限即提前停止（用於唯一解驗證）。

    委派給 solver 的共用實作（見 solver.count_solutions），此處保留薄封裝供內部維持行為。
    """
    from sudoku.model import Puzzle as _Puzzle

    return count_solutions(_Puzzle.from_grid([row[:] for row in grid]), 上限=上限)


def _挖空到目標(grid: list[list[int | None]], seed: int, 目標挖空數: int) -> int:
    """以 MRV 啟發式挖空到目標數；每挖一格驗證仍唯一解，不唯一則還原。回傳實際挖空數。"""
    rng = random.Random(seed ^ 0x5EED)
    空格清單 = [(r, c) for r in range(9) for c in range(9)]
    rng.shuffle(空格清單)
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
    return 已挖


def _生成一題(difficulty: Difficulty, seed: int) -> Puzzle:
    """以單一種子生成一道保證唯一解的題目（不檢查門檻）。"""
    solution = generate_solution(seed=seed)
    grid: list[list[int | None]] = [[solution.cell(r, c).value for c in range(9)] for r in range(9)]
    _挖空到目標(grid, seed, _難度目標挖空數[difficulty])
    return Puzzle.from_grid(grid)


def generate_puzzle(difficulty: Difficulty, seed: int | None = None) -> Puzzle:
    """依難度生成一道保證唯一解、且符合難度技巧門檻的題目。

    先產生完整解答，再以 MRV 啟發式決定挖空順序；每挖一格即驗證仍唯一解，
    不唯一就還原。達到該難度的目標挖空數即停止，接著用 solver.difficulty_of
    分級：不符門檻則以 ``基底種子 + 嘗試次數`` derive 的子種子重抽
    （上限見 _MAX_ATTEMPTS）；接近上限時放寬為「挖空數達標即可」避免卡死
    （EXPERT 可接受技巧鏈解不開，但挖空數仍需達標）。``seed`` 省略時每次隨機；
    同一 seed（含每日挑戰的日期種子）必產生同一道題。
    """
    if not isinstance(difficulty, Difficulty):
        raise TypeError(f"difficulty 必須是 Difficulty：{difficulty!r}")
    基底種子 = seed if seed is not None else random.SystemRandom().randrange(2**63)
    上限 = _MAX_ATTEMPTS[difficulty]
    放寬起點 = 上限 - _放寬剩餘嘗試數
    for 嘗試 in range(上限):
        子種子 = 基底種子 + 嘗試 * 1_000_003
        puzzle = _生成一題(difficulty, 子種子)
        report = difficulty_of(puzzle)
        if _門檻符合(report, difficulty):
            return puzzle
        # 放寬門檻（只對 HARD/EXPERT 生效，避免卡死）：
        # - EXPERT：挖空數達標即可（技巧鏈解不開歸 EXPERT，但深挖的 singles-only 題也算達標）；
        # - HARD：挖空數達標且分級不低於 HARD（避免放寬出太簡單的題）。
        if difficulty is Difficulty.EXPERT:
            if 嘗試 >= 放寬起點 and _挖空數達標(puzzle, difficulty):
                return puzzle
        elif difficulty is Difficulty.HARD:
            # HARD 放寬時挖空數達標即可（深挖的 singles-only 題技巧雖低但挖空數已達標，
            # 依門檻定義仍屬困難題）；門檻未放寬時不在此接受
            if 嘗試 >= 放寬起點 and _挖空數達標(puzzle, difficulty):
                return puzzle
    # 上限用盡：回傳最後一題（保證唯一解；門檻可能放寬）
    return _生成一題(difficulty, 基底種子 + 上限 * 1_000_003)


def daily_challenge(date_str: str) -> Puzzle:
    """每日挑戰：以日期字串（YYYY-MM-DD）為種子、中等難度生成題目（套同樣的門檻重抽）。

    同一天必為同一道題（種子 = 日期數字 + 嘗試計數器 derive 子種子，穩定）；
    日期格式非法或不是真實日期時拋出 ValueError。
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
