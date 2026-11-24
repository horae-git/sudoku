"""技巧鏈求解器與四級難度分級。

求解器依序嘗試由簡到難的技巧（naked single → hidden single → naked pair →
hidden pair → locked candidates（pointing/claiming）→ X-wing → swordfish），
每輪用最簡單的技巧推進，直到解開或卡住；過程中記錄「解題所需的最難技巧等級」。

難度（Difficulty）以技巧等級為主、挖空數為輔，對照門檻表（DIFFICULTY_THRESHOLDS）：
- 簡單（EASY）：只需 single（naked/hidden）即可解；
- 中等（MEDIUM）：需要 pair / locked candidates；
- 困難（HARD）：需要 X-wing；
- 專家（EXPERT）：需要 swordfish（技巧鏈實作到此為止，見 SPEC.md Out of Scope）。
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
    X_WING = 6  # X-wing：某數字在兩行（或兩列）各只出現於相同兩列（或兩行）
    SWORDFISH = 7  # swordfish：某數字在三行（或三列）的候選數都落在相同三列（或三行）


class Difficulty(IntEnum):
    """難度等級：簡單 → 中等 → 困難 → 專家。"""

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
    - 否則維持技巧等級對應的基準難度。"""
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
    - 無法解開的題目（技巧鏈卡住）一律歸專家（見 difficulty_of）。
    """
    if max_technique is None:
        基準 = Difficulty.EASY
    else:
        for 门檻 in DIFFICULTY_THRESHOLDS:
            if max_technique <= 门檻.max_technique:
                基準 = 门檻.difficulty
                break
        else:  # pragma: no cover - 技巧列舉與門檻表必然覆蓋 swordfish
            基準 = Difficulty.EXPERT
    return _挖空數調整(基準, clues_removed)


def difficulty_of(puzzle: Puzzle) -> DifficultyReport:
    """判斷一道題的難度：先以技巧鏈求解，再依門檻表分級。

    回傳 DifficultyReport，可解包為 (Difficulty, max_technique, clues_removed)。
    clues_removed = 81 −題示數（挖空數）。
    """
    result = solve(puzzle)
    clues_removed = sum(1 for cell in puzzle.cells if cell.value is None)
    max_technique = result.max_technique if result.solved else Technique.SWORDFISH
    return DifficultyReport(
        difficulty=classify_difficulty(max_technique, clues_removed),
        max_technique=result.max_technique if result.solved else None,
        clues_removed=clues_removed,
        solved=result.solved,
    )


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


def _有空格填入未確定(盤: _盤面) -> bool:
    """防呆：是否存在候選數恰為 1 但尚未確定的格子（理論上不該發生）。"""
    return any(not 盤.已填(r, c) and len(盤.candidates[r][c]) == 1 for r in range(9) for c in range(9))


def _naked_subset(盤: _盤面, size: int) -> bool:
    """naked subset（size 2 = naked pair、size 3 = naked triple）：
    同一單元內 size 個未確定格的候選數聯集恰好為 size 個數字 →
    這些數字可從單元內其他格刪去。"""
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
    """hidden subset（size 2 = hidden pair、size 3 = hidden triple）：
    某單元中 size 個數字的候選位置聯集恰好落在 size 個格子內 →
    這些格子只能放這 size 個數字，刪去它們的其他候選數。"""
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


def _fish(盤: _盤面, size: int) -> bool:
    """fish 技巧（X-wing=size 2、swordfish=size 3）。

    某數字在 size 條基準線（行，或列）上的候選位置（只算尚未確定的格子），
    聯集恰好落在 size 條正交線（列，或行）內 → 這些正交線上、fish 以外的
    格子可刪去該候選數。回傳是否有刪到任何候選數。
    """
    from itertools import combinations

    changed = False
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
                # 正交線聯集不得超過 size 條（否則不是 fish）；
                # 允許小於 size（退化成更小的 fish），此時以實際聯集為準
                if len(正交線集合) > size:
                    continue
                fish格: set[tuple[int, int]] = set()
                for i in comb:
                    for 正交 in 基準線位置[i]:
                        fish格.add((i, 正交) if 用行當基準 else (正交, i))
                for 正交 in 正交線集合:
                    for k in range(9):
                        r, c = (k, 正交) if 用行當基準 else (正交, k)
                        if (r, c) not in fish格:
                            changed |= _刪候選(盤, r, c, num)
    return changed


def _x_wing(盤: _盤面) -> bool:
    return _fish(盤, 2)


def _swordfish(盤: _盤面) -> bool:
    return _fish(盤, 3)


def solve(puzzle: Puzzle) -> SolveResult:
    """以技巧鏈解題：每輪依序嘗試最簡單的技巧，有進展就繼續，直到解開或所有技巧都無進展。

    回傳 SolveResult：solved=True 時 solution 為完整解答，
    max_technique 為解題所需的最難技巧等級。
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
        for tech, fn in (
            (Technique.PAIR_NAKED, _naked_pair),
            (Technique.PAIR_NAKED, lambda bd: _naked_subset(bd, 3)),
            (Technique.PAIR_NAKED, lambda bd: _naked_subset(bd, 4)),
            (Technique.PAIR_HIDDEN, _hidden_pair),
            (Technique.PAIR_HIDDEN, lambda bd: _hidden_subset(bd, 3)),
            (Technique.PAIR_HIDDEN, lambda bd: _hidden_subset(bd, 4)),
            (Technique.LOCKED_CANDIDATES, _locked_candidates),
            (Technique.X_WING, _x_wing),
            (Technique.SWORDFISH, _swordfish),
        ):
            if _試探(盤, fn):
                記錄(tech)
                break
        else:
            # 所有技巧都無進展：卡住
            return SolveResult(solved=False, solution=None, max_technique=max_technique, steps=tuple(steps))
