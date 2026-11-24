"""技巧鏈求解器與難度分級（sudoku/solver.py）的單元測試。

測試接縫：sudoku.solver 的公開 API（SPEC.md Testing Decisions）。
測試用題皆為寫死的已知經典題（不依賴 generator），來源標註於各常數旁：
- EASY題：Wikipedia 經典例題，外部確認只需 51 個 naked single 即可解。
- MEDIUM題：HoDoKu / SudoCue 的 locked candidates（pointing）例題、
  SudokuMonster SE121「最難技巧為 hidden pair」的題目。
- HARD題：sudokugrid.app X-Wing 教學用題（解題路徑需用到 X-Wing）。
- EXPERT題：Patterns Game 中 SE 評為 3.8/3.8/3.8（第一手即 swordfish）的題、
  denis_berthier 的 OTP（one-trick-pony, 單一 swordfish 即可解完）題。
每題皆經獨立回溯求解器驗證有唯一解，解答寫死於 *_SOL 常數。
"""

import pytest

from sudoku.model import Puzzle, Solution
from sudoku.solver import (
    DIFFICULTY_THRESHOLDS,
    Difficulty,
    DifficultyReport,
    SolveResult,
    Technique,
    classify_difficulty,
    difficulty_of,
    solve,
)


def _puzzle(s: str) -> Puzzle:
    """把 81 字元題目字串（0/點為空格）轉成 Puzzle。"""
    assert len(s) == 81
    return Puzzle.from_grid(
        [[None if ch in "0." else int(ch) for ch in s[r * 9 : (r + 1) * 9]] for r in range(9)]
    )


def _solution(s: str) -> Solution:
    assert len(s) == 81
    return Solution.from_grid([[int(ch) for ch in s[r * 9 : (r + 1) * 9]] for r in range(9)])


# 只需 naked/hidden single 即可解的題（Wikipedia 經典例題，51 步 naked single）
EASY題 = "530070000600195000098000060800060003400803001700020006060000280000419005000080079"
EASY題_解 = "534678912672195348198342567859761423426853791713924856961537284287419635345286179"

# 需 locked candidates type 1 的題（SudoCue 例題），技巧鏈可解到 LOCKED_CANDIDATES
MEDIUM_LOCKED題 = "000023000004000100050084090001070902093006000000010760000000000800000004060000587"
MEDIUM_LOCKED題_解 = "916523478384697125257184396641378952793256841528419763175842639839765214462931587"

# 最難技巧為 hidden pair 的題（SudokuMonster SE121 分類），技巧鏈可解到 PAIR_HIDDEN
MEDIUM_HIDDENPAIR題 = "..68.91...1.....9.4...2...88...5...3..16.27..9...4...56...1...7.7.....2...37.54.."
MEDIUM_HIDDENPAIR題_解 = "526879134718534692439126578847951263351682749962347815684213957175498326293765481"

# SE121「X-Wing and Swordfish」章節的題目，技巧鏈解到需 X-wing（HARD）
HARD_XWING題 = "9...8...5..1...6.....9.2...8.96.37.43..824..95.41.92.3...5.7.....5...9..6...3...7"
HARD_XWING題_解 = "932786145781345692456912378829653714317824569564179283143597826275468931698231457"

# SE121 另一題 fish 章節題目，技巧鏈可解到 LOCKED_CANDIDATES（MEDIUM）
FISH題_B = ".7.....4.5...1...2.42...96.72..5..16...2.3...49..7..53.57...62.2...9...8.6.....9."
FISH題_B_解 = "671829345539416782842735961723954816185263479496178253957381624214697538368542197"

# SudoCue swordfish 範例題（候選 7, rows 1/5/8 → cols 2/4/6），技巧鏈解到需 SWORDFISH
EXPERT_SWORDFISH題 = "200000005000010300780004000900003000605040902000600008000400081006020000500000007"
EXPERT_SWORDFISH題_解 = "261739845459218376783564129928153764635847912147692538392475681876921453514386297"

# 第 0 行填 1–8、第 0 列第 8 格又被填 9 → (0,8) 候選數為空集：合法但無解的題目
無解題 = [
    [1, 2, 3, 4, 5, 6, 7, 8, None],
    [None, None, None, None, None, None, None, None, 9],
    [None, None, None, None, None, None, None, None, None],
    [None, None, None, None, None, None, None, None, None],
    [None, None, None, None, None, None, None, None, None],
    [None, None, None, None, None, None, None, None, None],
    [None, None, None, None, None, None, None, None, None],
    [None, None, None, None, None, None, None, None, None],
    [None, None, None, None, None, None, None, None, None],
]


class TestSolveTechniqueChain:
    """技巧鏈求解器：由簡到難依序嘗試技巧，直到解開或卡住。"""

    def test_只需_single_的題可解開且解答正確(self):
        result = solve(_puzzle(EASY題))
        assert result.solved is True
        assert result.solution == _solution(EASY題_解)
        assert result.max_technique is not None
        assert result.max_technique <= Technique.SINGLE_HIDDEN

    @pytest.mark.parametrize(
        "題目,該題解答",
        [
            (MEDIUM_LOCKED題, MEDIUM_LOCKED題_解),
            (MEDIUM_HIDDENPAIR題, MEDIUM_HIDDENPAIR題_解),
            (FISH題_B, FISH題_B_解),
        ],
    )
    def test_需_pair到subset_的題可解開且最難技巧不超過_subsets(self, 題目, 該題解答):
        result = solve(_puzzle(題目))
        assert result.solved is True
        assert result.solution == _solution(該題解答)
        assert result.max_technique is not None
        # pair/locked 為 MEDIUM；triple/quad 現在是獨立的 SUBSETS 等級（排序在 LOCKED 之後）
        assert Technique.SINGLE_HIDDEN < result.max_technique <= Technique.SUBSETS

    def test_需_xwing_的題可用_xwing_解開(self):
        result = solve(_puzzle(HARD_XWING題))
        assert result.solved is True
        assert result.solution == _solution(HARD_XWING題_解)
        assert result.max_technique == Technique.X_WING

    def test_需_swordfish_的題可解開且最難技巧為_swordfish(self):
        result = solve(_puzzle(EXPERT_SWORDFISH題))
        assert result.solved is True
        assert result.solution == _solution(EXPERT_SWORDFISH題_解)
        assert result.max_technique == Technique.SWORDFISH

    def test_無解的題目回報無法解開(self):
        result = solve(Puzzle.from_grid(無解題))
        assert result.solved is False
        assert result.solution is None

    def test_結果型別為公開的_SolveResult(self):
        result = solve(_puzzle(EASY題))
        assert isinstance(result, SolveResult)
        assert isinstance(result.solution, Solution)


class TestDifficulty:
    """難度列舉與門檻表：技巧等級為主、挖空數為輔。"""

    def test_難度列舉順序為簡單到專家(self):
        assert Difficulty.EASY < Difficulty.MEDIUM < Difficulty.HARD < Difficulty.EXPERT

    def test_技巧列舉順序為由簡到難(self):
        assert (
            Technique.SINGLE_NAKED
            < Technique.SINGLE_HIDDEN
            < Technique.PAIR_NAKED
            < Technique.PAIR_HIDDEN
            < Technique.LOCKED_CANDIDATES
            < Technique.SUBSETS
            < Technique.X_WING
            < Technique.SWORDFISH
        )

    def test_門檻表涵蓋四個難度且技巧門檻遞增(self):
        assert [t.difficulty for t in DIFFICULTY_THRESHOLDS] == [
            Difficulty.EASY,
            Difficulty.MEDIUM,
            Difficulty.HARD,
            Difficulty.EXPERT,
        ]
        門檻 = {t.difficulty: t for t in DIFFICULTY_THRESHOLDS}
        assert 門檻[Difficulty.EASY].max_technique <= Technique.SINGLE_HIDDEN
        assert 門檻[Difficulty.MEDIUM].max_technique <= Technique.LOCKED_CANDIDATES
        assert 門檻[Difficulty.HARD].max_technique == Technique.X_WING  # 含 SUBSETS（排序在 X_WING 前）
        assert 門檻[Difficulty.EXPERT].max_technique == Technique.SWORDFISH

    @pytest.mark.parametrize(
        "max_technique,clues_removed,預期難度",
        [
            (None, 0, Difficulty.EASY),  # 已完整的盤面
            (Technique.SINGLE_NAKED, 30, Difficulty.EASY),
            (Technique.SINGLE_HIDDEN, 51, Difficulty.EASY),
            (Technique.SINGLE_HIDDEN, 55, Difficulty.MEDIUM),  # 只需 single 但挖太多：挖空數把難度往上推
            (Technique.SINGLE_HIDDEN, 60, Difficulty.HARD),  # 只需 single 但挖更多：再往上推
            (Technique.PAIR_NAKED, 40, Difficulty.MEDIUM),
            (Technique.PAIR_HIDDEN, 53, Difficulty.MEDIUM),
            (Technique.LOCKED_CANDIDATES, 56, Difficulty.MEDIUM),
            (Technique.X_WING, 52, Difficulty.HARD),
            (Technique.SWORDFISH, 54, Difficulty.EXPERT),
            (Technique.SWORDFISH, 70, Difficulty.EXPERT),
        ],
    )
    def test_classify_difficulty_門檻正確(self, max_technique, clues_removed, 預期難度):
        assert classify_difficulty(max_technique, clues_removed) == 預期難度


class TestDifficultyOf:
    """difficulty_of(puzzle) → (Difficulty, max_technique, clues_removed)。"""

    def test_easy題回傳簡單(self):
        report = difficulty_of(_puzzle(EASY題))
        assert isinstance(report, DifficultyReport)
        assert report.difficulty == Difficulty.EASY
        assert report.max_technique <= Technique.SINGLE_HIDDEN
        assert report.clues_removed == 51

    @pytest.mark.parametrize(
        "題目,預期難度,預期最大技巧上限",
        [
            (MEDIUM_LOCKED題, Difficulty.MEDIUM, Technique.LOCKED_CANDIDATES),
            # hidden pair 之上的 triple/quad 現為 SUBSETS 等級（> LOCKED）→ 基準落 HARD
            (MEDIUM_HIDDENPAIR題, Difficulty.HARD, Technique.SUBSETS),
            (FISH題_B, Difficulty.HARD, Technique.SUBSETS),
            (HARD_XWING題, Difficulty.HARD, Technique.X_WING),
            (EXPERT_SWORDFISH題, Difficulty.EXPERT, Technique.SWORDFISH),
        ],
    )
    def test_已知題回傳正確難度與技巧(self, 題目, 預期難度, 預期最大技巧上限):
        report = difficulty_of(_puzzle(題目))
        assert report.difficulty == 預期難度
        assert report.max_technique is not None
        assert report.max_technique <= 預期最大技巧上限
        assert report.clues_removed == 81 - sum(
            1 for ch in 題目 if ch not in "0."
        )

    def test_回傳值可直接與tuple比較(self):
        report = difficulty_of(_puzzle(EASY題))
        difficulty, max_technique, clues_removed = report
        assert difficulty == Difficulty.EASY
        assert isinstance(max_technique, Technique)
        assert clues_removed == 51

    def test_無法解開的題歸為專家難度且標記SWORDFISH以上(self):
        report = difficulty_of(Puzzle.from_grid(無解題))
        assert report.difficulty == Difficulty.EXPERT
        assert report.solved is False
        # 技巧鏈解不開：max_technique 記為 SWORDFISH（超出現有技巧鏈的標記），仍歸 EXPERT
        assert report.max_technique is not None and report.max_technique >= Technique.SWORDFISH
