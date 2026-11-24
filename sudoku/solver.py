"""技巧鏈求解器、唯一解回溯與四級難度分級。

求解器依序嘗試由簡到難的技巧（naked single → hidden single → naked pair →
hidden pair → locked candidates（pointing/claiming）→ naked/hidden triple/quad →
X-wing → swordfish），每輪用最簡單的技巧推進，直到解開或卡住；過程中記錄
「解題所需的最難技巧等級」。

另外提供 ``unique_solution``：計數式回溯（上限 2）求唯一解的完整解答。
技巧鏈只到 swordfish，解不開的唯一解題 ``solve`` 會回傳 solved=False，
因此「解答」一律走 ``unique_solution``（generator 挖空驗證與 session 開局
都用它）；``solve`` 只保留作分級（difficulty_of）用。

難度（Difficulty，本模組唯一的定義，generator 由此 import 再匯出）以技巧等級
為主、挖空數為輔，對照門檻表（DIFFICULTY_THRESHOLDS）：

- 簡單（EASY）：只需 single（naked/hidden）即可解；
- 中等（MEDIUM）：需要 pair / locked candidates；
- 困難（HARD）：需要 naked/hidden triple/quad（SUBSETS）或 X-wing；
- 專家（EXPERT）：需要 swordfish，或技巧鏈解不開（見 SPEC.md Out of Scope）。
"""

from dataclasses import dataclass
from enum import IntEnum

from sudoku.model import Puzzle, Solution


class Technique(IntEnum):
    """解題技巧等級，數值越大越難（排序即技巧鏈順序）。"""

    SINGLE_NAKED = 1  # naked single：某格只剩一個候選數
    SINGLE_HIDDEN = 2  # hidden single：某行/列/宮中某數字只能放在一格
    PAIR_NAKED = 3  # naked pair：兩格候選數相同，可刪去同單元其他格的這兩個候選數
    PAIR_HIDDEN = 4  # hidden pair：某單元中兩個數字只出現在同兩格
    LOCKED_CANDIDATES = 5  # locked candidates：pointing（宮內候選數限於同一行/列）與 claiming（行/列內候選數限於同一宮）
    SUBSETS = 6  # naked/hidden triple、quad：獨立於 pair 的等級（排序在 locked 之後、X-wing 之前）
    X_WING = 7  # X-wing：某數字在兩行（或兩列）各只出現於相同兩列（或兩行）
    SWORDFISH = 8  # swordfish：某數字在三行（或三列）的候選數都落在相同三列（或三行）


class Difficulty(IntEnum):
    """難度等級：簡單 → 中等 → 困難 → 專家（本專案唯一的定義）。"""

    EASY = 1
    MEDIUM = 2
    HARD = 3
    EXPERT = 4


@dataclass(frozen=True)
class SolveResult:
    """技巧鏈求解結果。

    - solved：是否成功解開；
    - solution：解開時的完整解答（未解開為 None）；
    - max_technique：解題過程中用到的最難技巧（已完整盤面為 None）；
    - steps：每一步使用的技巧（供 UI/除錯顯示解題路徑）。
    """

    solved: bool
    solution: Solution | None
    max_technique: Technique | None
    steps: tuple[Technique, ...]


@dataclass(frozen=True)
class DifficultyReport:
    """difficulty_of 的回報：可解包為 (Difficulty, max_technique, clues_removed)。"""

    difficulty: Difficulty
    max_technique: Technique | None
    clues_removed: int
    solved: bool

    def __iter__(self):
        """支援 `difficulty, max_technique, clues_removed = difficulty_of(p)` 的解包。"""
        yield self.difficulty
        yield self.max_technique
        yield self.clues_removed


@dataclass(frozen=True)
class _Threshold:
    """單一難度的門檻：允許的最難技巧上限，以及該難度的挖空數範圍。"""

    difficulty: Difficulty
    max_technique: Technique
    min_clues_removed: int
    max_clues_removed: int


# 門檻表：技巧等級為主、挖空數為輔（SPEC.md／GLOSSARY.md 的難度定義）。
# 挖空數範圍用意：技巧只到某等級但挖空數超出範圍時，難度往上調一級，
# 避免「只需 single 但挖了 60 格」這類題被誤判為簡單。
DIFFICULTY_THRESHOLDS: tuple[_Threshold, ...] = (
    _Threshold(Difficulty.EASY, Technique.SINGLE_HIDDEN, 0, 52),
    _Threshold(Difficulty.MEDIUM, Technique.LOCKED_CANDIDATES, 30, 58),
    _Threshold(Difficulty.HARD, Technique.X_WING, 40, 64),
    _Threshold(Difficulty.EXPERT, Technique.SWORDFISH, 0, 81),
)


def _挖空數調整(基準: Difficulty, clues_removed: int) -> Difficulty:
    """依挖空數決定難度下限（技巧等級為主，挖空數為輔，只升不降）：

    - 挖空數 > 64 → 至少 EXPERT；
    - 挖空數 > 58 → 至少 HARD；
    - 挖空數 > 52 → 至少 MEDIUM；
    - 否則維持技巧等級對應的基準難度。
    """
    if clues_removed > 64:
        下限 = Difficulty.EXPERT
    elif clues_removed > 58:
        下限 = Difficulty.HARD
    elif clues_removed > 52:
        下限 = Difficulty.MEDIUM
    else:
        下限 = Difficulty.EASY
    return max(基準, 下限)


def classify_difficulty(max_technique: Technique | None, clues_removed: int) -> Difficulty:
    """依門檻表判斷難度：先看最難技巧落在哪一級，再以挖空數微調（只升不降）。

    - max_technique 為 None（盤面已完整）視為只需 single，歸簡單。
    - 技巧等級決定基準難度；挖空數超出門檻上限時難度往上推
      （例如只需 hidden single 但挖了 60 格 → 困難；
        需 swordfish 且挖 54 格 → 仍為專家，不會被挖空數降級）。
    - 技巧鏈解不開的題以 SWORDFISH 以上標記呼叫，一律歸專家（見 difficulty_of）。
    """
    if max_technique is None:
        基準 = Difficulty.EASY
    else:
        for 門檻 in DIFFICULTY_THRESHOLDS:
            if max_technique <= 門檻.max_technique:
                基準 = 門檻.difficulty
                break
        else:  # pragma: no cover - 技巧列舉與門檻表必然覆蓋 swordfish
            基準 = Difficulty.EXPERT
    return _挖空數調整(基準, clues_removed)


def difficulty_of(puzzle: Puzzle) -> DifficultyReport:
    """判斷一道題的難度：先以技巧鏈求解，再依門檻表分級。

    回傳 DifficultyReport，可解包為 (Difficulty, max_technique, clues_removed)。
    clues_removed = 81 −題示數（挖空數）。

    技巧鏈解不開（solved=False）的題：max_technique 記為 SWORDFISH
    （表示「超出現有技巧鏈」、仍歸 EXPERT），solved 欄位為 False，
    與 generator 的 EXPERT 門檻一致。
    """
    result = solve(puzzle)
    clues_removed = sum(1 for cell in puzzle.cells if cell.value is None)
    if result.solved:
        max_technique = result.max_technique
    else:
        # 技巧鏈解不開：以 SWORDFISH 標記「無法以現有技巧鏈解開」，歸 EXPERT
        max_technique = Technique.SWORDFISH
    return DifficultyReport(
        difficulty=classify_difficulty(max_technique, clues_removed),
        max_technique=max_technique,
        clues_removed=clues_removed,
        solved=result.solved,
    )


# ---------------------------------------------------------------------------
# 唯一解：計數式回溯（上限 2）——解答的唯一來源
# ---------------------------------------------------------------------------


def _宮索引(row: int, col: int) -> int:
    return (row // 3) * 3 + col // 3


def _計數回溯(
    grid: list[list[int | None]],
    行已用: list[set[int]],
    列已用: list[set[int]],
    宮已用: list[set[int]],
    上限: int,
    收集: list[list[list[int]]] | None = None,
) -> int:
    """計數式回溯（MRV 啟發）：計算解答數量，達 ``上限`` 即提前停止。

    若 ``收集`` 不為 None，第一個找到的完整解會附加到該 list（供 unique_solution 用）。
    """
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
        if 收集 is not None and not 收集:
            收集.append([row[:] for row in grid])  # type: ignore[arg-type]
        return 1  # 無空格：恰好一個解
    r, c = 最佳
    b = _宮索引(r, c)
    總數 = 0
    for v in 最佳候選:
        grid[r][c] = v
        行已用[r].add(v)
        列已用[c].add(v)
        宮已用[b].add(v)
        總數 += _計數回溯(grid, 行已用, 列已用, 宮已用, 上限 - 總數, 收集)
        grid[r][c] = None
        行已用[r].discard(v)
        列已用[c].discard(v)
        宮已用[b].discard(v)
        if 總數 >= 上限:
            return 總數
    return 總數


def count_solutions(puzzle: Puzzle, 上限: int = 2) -> int:
    """計數式回溯：計算題目解答數量，達 ``上限`` 即提前停止（預設 2，用於唯一解驗證）。"""
    grid = [[puzzle.cell(r, c).value for c in range(9)] for r in range(9)]
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
    return _計數回溯(grid, 行已用, 列已用, 宮已用, 上限)


def unique_solution(puzzle: Puzzle) -> Solution:
    """以計數式回溯（上限 2）驗證題目恰好一個解後，回傳該完整解答。

    技巧鏈 ``solve`` 只到 swordfish，超出的唯一解題會回傳 solved=False，
    因此解答一律用此完整回溯取得（generator 挖空驗證、session 開局共用）；
    若題目多解或無解則拋出 ValueError。
    """
    grid = [[puzzle.cell(r, c).value for c in range(9)] for r in range(9)]
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
    總數 = _計數回溯(grid, 行已用, 列已用, 宮已用, 上限=2, 收集=找到的解)
    if 總數 == 1 and len(找到的解) == 1:
        return Solution.from_grid(找到的解[0])
    raise ValueError(f"題目沒有唯一解（找到 {總數 if 總數 < 2 else '2+'} 個解）")


# ---------------------------------------------------------------------------
# 內部狀態：可變的候選數盤面（求解過程中會修改，不對外暴露）
# ---------------------------------------------------------------------------


class _盤面:
    """求解過程中的可變盤面：每格的候選數集合（已填格為單元素集合）。"""

    __slots__ = ("candidates", "givens")

    def __init__(self, puzzle: Puzzle) -> None:
        self.candidates: list[list[set[int]]] = []
        self.givens: set[tuple[int, int]] = set()
        for r in range(9):
            row: list[set[int]] = []
            for c in range(9):
                v = puzzle.cell(r, c).value
                if v is not None:
                    row.append({v})
                    self.givens.add((r, c))
                else:
                    row.append(set(range(1, 10)))
            self.candidates.append(row)
        self._刪除已填數的關聯候選()

    def _刪除已填數的關聯候選(self) -> None:
        """初始化：把每個已填數字從同行/列/宮的空格候選數中刪去。"""
        for r in range(9):
            for c in range(9):
                v = self.candidates[r][c]
                if len(v) == 1:
                    self._刪除關聯(r, c, next(iter(v)))

    def _刪除關聯(self, r: int, c: int, num: int) -> bool:
        """從 (r,c) 的同行/列/宮（不含自己且非已填格）刪去候選數 num，回傳是否有刪到。"""
        changed = False
        for i in range(9):
            for rr, cc in ((r, i), (i, c)):
                if (rr, cc) != (r, c) and len(self.candidates[rr][cc]) > 1 and num in self.candidates[rr][cc]:
                    self.candidates[rr][cc].discard(num)
                    changed = True
        br, bc = (r // 3) * 3, (c // 3) * 3
        for dr in range(3):
            for dc in range(3):
                rr, cc = br + dr, bc + dc
                if (rr, cc) != (r, c) and len(self.candidates[rr][cc]) > 1 and num in self.candidates[rr][cc]:
                    self.candidates[rr][cc].discard(num)
                    changed = True
        return changed

    def 已填(self, r: int, c: int) -> bool:
        """此格是否已確定數值（題示或求解中填入）。"""
        return (r, c) in self.givens or len(self.candidates[r][c]) == 1

    def 空格數(self) -> int:
        """尚未填入（非題示且候選數超過 1 個）的格子數。"""
        return sum(
            1
            for r in range(9)
            for c in range(9)
            if (r, c) not in self.givens and len(self.candidates[r][c]) > 1
        )

    def 是否完整(self) -> bool:
        return all(self.已填(r, c) for r in range(9) for c in range(9))

    def 是否全單(self) -> bool:
        """所有格子（含題示）候選數都恰為 1。"""
        return all(len(self.candidates[r][c]) == 1 for r in range(9) for c in range(9))

    def 是否矛盾(self) -> bool:
        """任一空格候選數為空，或任一單元某數字無處可放 → 矛盾。"""
        for r in range(9):
            for c in range(9):
                if (r, c) not in self.givens and not self.candidates[r][c]:
                    return True
        for 單元 in self._所有單元():
            for num in range(1, 10):
                if not any(num in self.candidates[r][c] for r, c in 單元):
                    return True
        return False

    def _所有單元(self) -> list[list[tuple[int, int]]]:
        """全部 27 個單元（9 行 + 9 列 + 9 宮）的格子座標。"""
        cells: list[list[tuple[int, int]]] = []
        for r in range(9):
            cells.append([(r, c) for c in range(9)])
        for c in range(9):
            cells.append([(r, c) for r in range(9)])
        for b in range(9):
            br, bc = (b // 3) * 3, (b % 3) * 3
            cells.append([(br + dr, bc + dc) for dr in range(3) for dc in range(3)])
        return cells

    def 填入(self, r: int, c: int, num: int) -> None:
        """把 (r,c) 設為 num，並刪去同行/列/宮的候選 num。"""
        self.candidates[r][c] = {num}
        self._刪除關聯(r, c, num)

    def 複製(self) -> "_盤面":
        """深拷貝一份盤面（技巧函式試探用）。"""
        new = _盤面.__new__(_盤面)
        new.candidates = [[set(cell) for cell in row] for row in self.candidates]
        new.givens = set(self.givens)
        return new

    def to_solution(self) -> Solution:
        return Solution.from_grid(
            [[next(iter(self.candidates[r][c])) for c in range(9)] for r in range(9)]
        )


def _naked_single(盤: _盤面) -> tuple[int, int, int] | None:
    """naked single：找一個只剩一個候選數且尚未確定的格子，回傳 (row, col, value)。"""
    for r in range(9):
        for c in range(9):
            if 盤.已填(r, c):
                continue
            cand = 盤.candidates[r][c]
            if len(cand) == 1:
                return r, c, next(iter(cand))
    return None


def _試探(盤: _盤面, fn) -> bool:
    """在盤面的副本上執行技巧函式，確認真的有刪到候選數才套用並回 True（避免假進展造成無限迴圈）。"""
    複本 = 盤.複製()
    有進展 = fn(複本)
    if not 有進展:
        return False
    for r in range(9):
        for c in range(9):
            if 複本.candidates[r][c] != 盤.candidates[r][c]:
                盤.candidates = 複本.candidates
                return True
    return False


def _hidden_single(盤: _盤面) -> tuple[int, int, int] | None:
    """hidden single：某單元中某數字只能放在一格，回傳 (row, col, value)。"""
    for 單元 in 盤._所有單元():
        for num in range(1, 10):
            位置 = [(r, c) for r, c in 單元 if num in 盤.candidates[r][c]]
            if len(位置) == 1:
                r, c = 位置[0]
                if not 盤.已填(r, c):
                    return r, c, num
    return None


def _naked_subset(盤: _盤面, size: int) -> bool:
    """naked subset（size 2 = naked pair、size 3 = naked triple、size 4 = naked quad）：

    同一單元內 size 個未確定格的候選數聯集恰好為 size 個數字 →
    這些數字可從單元內其他格刪去。
    """
    from itertools import combinations

    changed = False
    for 單元 in 盤._所有單元():
        未確定格 = [(r, c) for r, c in 單元 if len(盤.candidates[r][c]) > 1]
        for 格組 in combinations(未確定格, size):
            候選聯集: set[int] = set()
            for r, c in 格組:
                候選聯集 |= 盤.candidates[r][c]
            if len(候選聯集) != size:
                continue
            for r, c in 單元:
                if (r, c) not in 格組:
                    changed |= _刪候選多值(盤, r, c, 候選聯集)
    return changed


def _naked_pair(盤: _盤面) -> bool:
    """naked pair：naked subset size 2。"""
    return _naked_subset(盤, 2)


def _刪候選多值(盤: _盤面, r: int, c: int, nums: set[int]) -> bool:
    """安全地刪去 (r,c) 的多個候選數（不動已填格），回傳是否真的有刪到。"""
    if len(盤.candidates[r][c]) > 1:
        before = set(盤.candidates[r][c])
        盤.candidates[r][c] -= nums
        return 盤.candidates[r][c] != before
    return False


def _hidden_subset(盤: _盤面, size: int) -> bool:
    """hidden subset（size 2 = hidden pair、size 3 = hidden triple、size 4 = hidden quad）：

    某單元中 size 個數字的候選位置聯集恰好落在 size 個格子內 →
    這些格子只能放這 size 個數字，刪去它們的其他候選數。
    """
    from itertools import combinations

    changed = False
    for 單元 in 盤._所有單元():
        for 數字組 in combinations(range(1, 10), size):
            # 若單元內任一數字已有確定值，則該數字不參與 hidden subset
            if any(len(盤.candidates[r][c]) == 1 and num in 盤.candidates[r][c] for r, c in 單元 for num in 數字組):
                continue
            格集合: set[tuple[int, int]] = set()
            for num in 數字組:
                格集合 |= {(r, c) for r, c in 單元 if num in 盤.candidates[r][c] and len(盤.candidates[r][c]) > 1}
            if len(格集合) != size:
                continue
            要留的 = set(數字組)
            for r, c in 格集合:
                if len(盤.candidates[r][c]) > size:
                    before = set(盤.candidates[r][c])
                    盤.candidates[r][c] &= 要留的
                    changed |= 盤.candidates[r][c] != before
    return changed


def _hidden_pair(盤: _盤面) -> bool:
    """hidden pair：hidden subset size 2。"""
    return _hidden_subset(盤, 2)


def _刪候選(盤: _盤面, r: int, c: int, num: int) -> bool:
    """安全地刪去 (r,c) 的候選數 num（不動已填格），回傳是否真的有刪到。"""
    if len(盤.candidates[r][c]) > 1 and num in 盤.candidates[r][c]:
        盤.candidates[r][c].discard(num)
        return True
    return False


def _locked_candidates(盤: _盤面) -> bool:
    """locked candidates：pointing 與 claiming 的候選數刪除，回傳是否有刪到。"""
    changed = False
    for b in range(9):
        br, bc = (b // 3) * 3, (b % 3) * 3
        宮格 = [(br + dr, bc + dc) for dr in range(3) for dc in range(3)]
        for num in range(1, 10):
            位置 = [(r, c) for r, c in 宮格 if num in 盤.candidates[r][c]]
            未確定位置 = [(r, c) for r, c in 位置 if len(盤.candidates[r][c]) > 1]
            # 宮內已有該數的確定值時，宮內已滿足，不需 pointing
            if len(未確定位置) != len(位置):
                continue
            if not 位置 or len(位置) > 3:
                continue
            # pointing：宮內某數字的候選位置全在同一行 → 刪去該行宮外的候選
            rows = {r for r, _ in 位置}
            cols = {c for _, c in 位置}
            if len(rows) == 1:
                r = next(iter(rows))
                for c in range(9):
                    if (r, c) not in 宮格:
                        changed |= _刪候選(盤, r, c, num)
            if len(cols) == 1:
                c = next(iter(cols))
                for r in range(9):
                    if (r, c) not in 宮格:
                        changed |= _刪候選(盤, r, c, num)
    # claiming：某行（列）內某數字的候選位置全在同一宮 → 刪去該宮行外（列外）的候選。
    # 重要：此時必須保證該行（列）內「所有」含該候選數的格子都在同一宮，
    # 包含已確定值的格子也要算進去；若行內已有該數的確定值在不同宮，不能 claiming。
    for r in range(9):
        for num in range(1, 10):
            if any(len(盤.candidates[r][c]) == 1 and num in 盤.candidates[r][c] for c in range(9)):
                continue  #該行已有該數的確定值，宮內即鎖定，不需再 claiming
            位置 = [(r, c) for c in range(9) if num in 盤.candidates[r][c]]
            if not 位置 or len(位置) > 3:
                continue
            boxes = {((r // 3) * 3 + (c // 3)) for _, c in 位置}
            if len(boxes) == 1:
                b = next(iter(boxes))
                br, bc = (b // 3) * 3, (b % 3) * 3
                for rr in range(br, br + 3):
                    if rr == r:
                        continue
                    for cc in range(bc, bc + 3):
                        changed |= _刪候選(盤, rr, cc, num)
    for c in range(9):
        for num in range(1, 10):
            if any(len(盤.candidates[r][c]) == 1 and num in 盤.candidates[r][c] for r in range(9)):
                continue  #該列已有該數的確定值
            位置 = [(r, c) for r in range(9) if num in 盤.candidates[r][c]]
            if not 位置 or len(位置) > 3:
                continue
            boxes = {((r // 3) * 3 + (c // 3)) for r, _ in 位置}
            if len(boxes) == 1:
                b = next(iter(boxes))
                br, bc = (b // 3) * 3, (b % 3) * 3
                for rr in range(br, br + 3):
                    for cc in range(bc, bc + 3):
                        if cc == c:
                            continue
                        changed |= _刪候選(盤, rr, cc, num)
    return changed


def _fish(盤: _盤面, size: int) -> tuple[bool, Technique | None]:
    """fish 技巧（X-wing=size 2、swordfish=size 3）。

    某數字在 size 條基準線（行，或列）上的候選位置（只算尚未確定的格子），
    聯集恰好落在 size 條正交線（列，或行）內 → 這些正交線上、fish 以外的
    格子可刪去該候選數。

    回傳 (是否有刪到候選數, 達成的 fish 等級)。退化處理：正交線聯集小於
    size 時不是該 size 的 fish——聯集恰為 2 條時記為 X_WING（更小的 fish），
    這樣才不會把低階消去誤記為 X_WING/SWORDFISH；聯集小於 2 條則不視為 fish。
    """
    from itertools import combinations

    changed = False
    best_level: Technique | None = None
    for num in range(1, 10):
        for 用行當基準 in (True, False):
            # 每條基準線上該數字在「未確定格」中的候選位置（正交線索引集合）
            基準線位置: dict[int, set[int]] = {}
            for i in range(9):
                if 用行當基準:
                    格 = [(i, c) for c in range(9)]
                else:
                    格 = [(r, i) for r in range(9)]
                # 若該線上已有該數的確定值，表示該線不需要 fish，跳過
                if any(len(盤.candidates[r][c]) == 1 and num in 盤.candidates[r][c] for r, c in 格):
                    continue
                位置 = {
                    c if 用行當基準 else r
                    for r, c in 格
                    if num in 盤.candidates[r][c] and len(盤.candidates[r][c]) > 1
                }
                if 2 <= len(位置) <= size:
                    基準線位置[i] = 位置
            基準線索引 = list(基準線位置)
            if len(基準線索引) < size:
                continue
            for comb in combinations(基準線索引, size):
                正交線集合: set[int] = set()
                for i in comb:
                    正交線集合 |= 基準線位置[i]
                # 正交線聯集必須恰等於 fish size 才記該技巧等級；
                # 小於 size 但恰為 2 條時退化成 X_WING；小於 2 條則不是 fish
                if len(正交線集合) > size or len(正交線集合) < 2:
                    continue
                level = Technique.X_WING if len(正交線集合) == 2 else Technique.SWORDFISH
                if best_level is None or level > best_level:
                    best_level = level
                fish格: set[tuple[int, int]] = set()
                for i in comb:
                    for 正交 in 基準線位置[i]:
                        fish格.add((i, 正交) if 用行當基準 else (正交, i))
                for 正交 in 正交線集合:
                    for k in range(9):
                        r, c = (k, 正交) if 用行當基準 else (正交, k)
                        if (r, c) not in fish格:
                            changed |= _刪候選(盤, r, c, num)
    return changed, best_level


def _x_wing(盤: _盤面) -> tuple[bool, Technique | None]:
    return _fish(盤, 2)


def _swordfish(盤: _盤面) -> tuple[bool, Technique | None]:
    return _fish(盤, 3)


def _試探_fish(盤: _盤面, size: int) -> tuple[bool, Technique | None]:
    """在副本上跑 fish 技巧，確認真的有刪到候選數才套用，回傳 (是否套用, 等級)。"""
    複本 = 盤.複製()
    changed, level = _fish(複本, size)
    if not changed:
        return False, None
    for r in range(9):
        for c in range(9):
            if 複本.candidates[r][c] != 盤.candidates[r][c]:
                盤.candidates = 複本.candidates
                return True, level
    return False, None


def solve(puzzle: Puzzle) -> SolveResult:
    """以技巧鏈解題：每輪依序嘗試最簡單的技巧，有進展就繼續，直到解開或所有技巧都無進展。

    回傳 SolveResult：solved=True 時 solution 為完整解答，
    max_technique 為解題所需的最難技巧等級；解不開時 solved=False
    （此時 solution 為 None，分級見 difficulty_of）。
    """
    盤 = _盤面(puzzle)
    steps: list[Technique] = []
    max_technique: Technique | None = None

    def 記錄(tech: Technique) -> None:
        nonlocal max_technique
        steps.append(tech)
        if max_technique is None or tech > max_technique:
            max_technique = tech

    while True:
        if 盤.是否矛盾():
            return SolveResult(solved=False, solution=None, max_technique=max_technique, steps=tuple(steps))
        if 盤.是否全單():
            return SolveResult(
                solved=True, solution=盤.to_solution(), max_technique=max_technique, steps=tuple(steps)
            )
        # 由簡到難嘗試技巧；任一技巧有進展就記錄並回到最簡技巧重新開始
        if (m := _naked_single(盤)) is not None:
            盤.填入(*m)
            記錄(Technique.SINGLE_NAKED)
            continue
        if (m := _hidden_single(盤)) is not None:
            盤.填入(*m)
            記錄(Technique.SINGLE_HIDDEN)
            continue
        刪除型技巧 = (
            (Technique.PAIR_NAKED, _naked_pair),
            (Technique.PAIR_HIDDEN, _hidden_pair),
            (Technique.LOCKED_CANDIDATES, _locked_candidates),
            (Technique.SUBSETS, lambda bd: _naked_subset(bd, 3)),
            (Technique.SUBSETS, lambda bd: _naked_subset(bd, 4)),
            (Technique.SUBSETS, lambda bd: _hidden_subset(bd, 3)),
            (Technique.SUBSETS, lambda bd: _hidden_subset(bd, 4)),
        )
        for tech, fn in 刪除型技巧:
            if _試探(盤, fn):
                記錄(tech)
                break
        else:
            # fish 技巧：X-wing、swordfish（可能退化記為較低等級）
            fish_level: Technique | None = None
            有進展 = False
            for size in (2, 3):
                applied, level = _試探_fish(盤, size)
                if applied:
                    有進展 = True
                    if level is not None and (fish_level is None or level > fish_level):
                        fish_level = level
            if 有進展:
                記錄(fish_level if fish_level is not None else Technique.SWORDFISH)
                continue
            # 所有技巧都無進展：卡住
            return SolveResult(solved=False, solution=None, max_technique=max_technique, steps=tuple(steps))
