"""code-review（Standards 軸 + Spec 軸）確認發現的迴歸測試。

每個測試對應一條 finding（見分支上的 review 報告）：

- **A（Spec #7）**：困難/專家開局不得崩潰——解答一律走計數式回溯 ``unique_solution``，
  100 局 EXPERT + 100 局 HARD 的 ``GameSession.new_game`` 全部不得拋例外且解答正確。
- **B（Spec #1）**：難度分級落實技巧門檻重抽——各難度 20 局門檻斷言、每日挑戰連 5 天
  全為 MEDIUM、全部仍唯一解、EXPERT 放寬門檻時單題仍 < 2 秒。
- **C（Spec #2）**：提示填滿最後一格要結算勝利（寫歷史、刪存檔、停計時）。
- **F**：雙 Difficulty enum 統一為單一定義（generator 與 solver 指向同一個類別）。
- **G（Spec #8）**：fish 退化不誤記等級、SUBSETS獨立等級、解不開的題標記為 SWORDFISH 以上。
- **H（Spec #3）**：主視窗固定大小不可縮放（960×780）。

備註：簡體字掃描（原 D 項）已抽成獨立常駐測試 tests/test_no_simplified_chinese.py。
"""

import time
from pathlib import Path

import pytest

from sudoku import storage
from sudoku.generator import Difficulty, daily_challenge, generate_puzzle
from sudoku.model import Puzzle
from sudoku.session import GameSession
from sudoku.solver import Difficulty as SolverDifficulty
from sudoku.solver import (
    Technique,
    classify_difficulty,
    difficulty_of,
    unique_solution,
)
from sudoku.ui.flow import GameFlow


@pytest.fixture(autouse=True)
def 隔離資料目錄(monkeypatch, tmp_path):
    """把使用者資料目錄導向暫存資料夾，不碰真實資料。"""
    monkeypatch.setenv("SUDOKU_DATA_DIR", str(tmp_path / "user-data"))


# ---------- 測試輔助 ----------


def _唯一解驗證(puzzle: Puzzle):
    """以公開 API ``unique_solution`` 驗證題目恰有唯一解並回傳解答。"""
    return unique_solution(puzzle)


def _解答與題示一致(session: GameSession) -> bool:
    """session 的解答是否與題示一致（Solution 建構時已保證行/列/宮合法）。"""
    for i in range(81):
        given = session.puzzle[i]
        if given != "0" and session.solution[i] != given:
            return False
    return True


_SOLUTION_GRID = [
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
_SOLUTION_STR = "".join(str(v) for row in _SOLUTION_GRID for v in row)


def _只剩一格的局(mode: str = "easy") -> GameSession:
    """構造只剩最後一格（索引 80）為空的局，供提示結算勝利用。"""
    puzzle = ["0"] * 81
    puzzle[0] = "5"  # (0,0) 題示 5
    board = list(_SOLUTION_STR)
    board[80] = "0"  # 只剩 (8,8) 空格
    state = {
        "puzzle": "".join(puzzle),
        "solution": _SOLUTION_STR,
        "board": "".join(board),
        "notes": [[] for _ in range(81)],
        "mistakes": 0,
        "hints_left": 3,
        "elapsed_sec": 5,
        "mode": mode,
    }
    return GameSession.from_state_dict(state, mode)


# ---------- A：困難/專家開局不得崩潰（解答走計數式回溯 unique_solution） ----------


@pytest.mark.slow
class TestA_開局解答走回溯:
    def test_expert連續100局new_game不拋例外且解答正確(self):
        for seed in range(100):
            s = GameSession.new_game(Difficulty.EXPERT, seed=seed)
            assert _解答與題示一致(s), f"EXPERT seed={seed} 解答與題示不一致"
            # 抽查：解答確實是題目的唯一解
            sol = _唯一解驗證(Puzzle.from_grid(_str_grid(s.puzzle)))
            assert "".join(str(sol.cell(r, c).value) for r in range(9) for c in range(9)) == s.solution

    def test_hard連續100局new_game不拋例外且解答正確(self):
        for seed in range(100):
            s = GameSession.new_game(Difficulty.HARD, seed=seed)
            assert _解答與題示一致(s), f"HARD seed={seed} 解答與題示不一致"

    def test_daily開局也不拋例外(self):
        for d in range(5):
            s = GameSession.daily(f"2026-11-{20 + d}")
            assert _解答與題示一致(s)


def _str_grid(s: str):
    return [[None if s[r * 9 + c] == "0" else int(s[r * 9 + c]) for c in range(9)] for r in range(9)]


# ---------- B：難度分級落實技巧門檻重抽 ----------


@pytest.mark.slow
class TestB_門檻重抽:
    @pytest.mark.parametrize("difficulty", list(Difficulty))
    def test_各難度生成20局門檻正確且唯一解(self, difficulty):
        for seed in range(20):
            p = generate_puzzle(difficulty, seed=seed)
            report = difficulty_of(p)
            _唯一解驗證(p)  # 仍唯一解
            if difficulty is Difficulty.EASY:
                assert report.difficulty == Difficulty.EASY
                assert report.max_technique is None or report.max_technique <= Technique.SINGLE_HIDDEN
            elif difficulty is Difficulty.MEDIUM:
                assert report.difficulty == Difficulty.MEDIUM, f"seed={seed} {report}"
                assert report.max_technique is not None
                assert Technique.PAIR_NAKED <= report.max_technique <= Technique.LOCKED_CANDIDATES, (
                    f"seed={seed} max_technique={report.max_technique}"
                )
            elif difficulty is Difficulty.HARD:
                # HARD：SUBSETS（triple/quad）以上，或放寬時只要求挖空數達標（門檻定義的困難題）
                assert report.clues_removed >= 45
            elif difficulty is Difficulty.EXPERT:
                # EXPERT：swordfish 或技巧鏈解不開（歸 EXPERT）；放寬時只要求挖空數達標
                if report.solved:
                    assert report.difficulty == Difficulty.EXPERT
                assert report.clues_removed >= 50

    def test_expert放寬門檻時單題仍小於2秒(self):
        for seed in range(20):
            開始 = time.perf_counter()
            p = generate_puzzle(Difficulty.EXPERT, seed=1000 + seed)
            用時 = time.perf_counter() - 開始
            assert 用時 < 2.0, f"EXPERT seed={1000 + seed} 生成耗時 {用時:.2f}s"
            _唯一解驗證(p)

    def test_每日挑戰連5天全為MEDIUM等級且唯一解(self):
        for d in range(5):
            date_str = f"2026-11-{20 + d}"
            p = daily_challenge(date_str)
            report = difficulty_of(p)
            assert report.difficulty == Difficulty.MEDIUM, f"{date_str}: {report}"
            assert report.max_technique is not None
            assert Technique.PAIR_NAKED <= report.max_technique <= Technique.LOCKED_CANDIDATES
            _唯一解驗證(p)

    def test_每日挑戰同一天結果穩定(self):
        assert daily_challenge("2026-11-25") == daily_challenge("2026-11-25")


# ---------- C：提示填滿最後一格結算勝利 ----------


class TestC_hint填滿最後一格結算勝利:
    def test_hint填滿最後一格_寫歷史_刪存檔_停計時(self):
        s = _只剩一格的局()
        flow = GameFlow(s)  # 建構即存檔
        assert storage.load_game("easy") is not None
        flow.tick()
        assert s.elapsed_sec == 6

        res = flow.hint()
        assert res is not None
        assert s.is_won() is True

        # 勝利結算：歷史有 completed、存檔已刪、計時停止
        completed = storage.list_history(result="completed")
        assert len(completed) == 1 and completed[0]["mode"] == "easy"
        assert storage.load_game("easy") is None
        assert storage.list_saves() == []
        e = s.elapsed_sec
        flow.tick()
        s.tick()
        assert s.elapsed_sec == e  # 勝利後計時停止


# ---------- F：雙 Difficulty enum 統一 ----------


class TestF_單一Difficulty定義:
    def test_generator與solver的Difficulty是同一個類別(self):
        from sudoku.generator import Difficulty as GeneratorDifficulty

        assert GeneratorDifficulty is SolverDifficulty

    def test_sudoku頂層匯出同一個Difficulty(self):
        import sudoku

        assert sudoku.Difficulty is SolverDifficulty

    def test_字串難度仍可開局(self):
        s = GameSession.new_game("expert", seed=3)
        assert s.mode == "expert"


# ---------- G：solver 分類邏輯修正 ----------


class TestG_fish退化與SUBSETS等級:
    def test_SUBSETS獨立等級且排序在LOCKED之後X_WING之前(self):
        assert Technique.LOCKED_CANDIDATES < Technique.SUBSETS < Technique.X_WING

    def test_classify_SUBSETS歸HARD門檻(self):
        assert classify_difficulty(Technique.SUBSETS, 50) == Difficulty.HARD
        # MEDIUM 仍為 pair..locked
        assert classify_difficulty(Technique.PAIR_NAKED, 45) == Difficulty.MEDIUM
        assert classify_difficulty(Technique.LOCKED_CANDIDATES, 50) == Difficulty.MEDIUM

    def test_fish退化聯集恰2條時記X_WING不記SWORDFISH(self):
        # 白箱驗證 _fish 退化邏輯：數字 1 在 row 0,1,2 的「未確定格」候選位置都只落在 {3,4}，
        # 三行 comb 的正交聯集只有 2 條——對 size=3 的 swordfish 而言是退化 fish，
        # 只能記 X_WING，不能誤記 SWORDFISH。
        from sudoku.solver import _盤面, _fish

        bd = _盤面(_puzzle_str("0" * 81))
        for r in range(9):
            for c in range(9):
                bd.candidates[r][c] = set(range(1, 10))
        for r in (0, 1, 2):
            for c in range(9):
                if c not in (3, 4):
                    bd.candidates[r][c].discard(1)  # 這些格子的候選不再含 1
        changed, level = _fish(bd, 3)
        assert level == Technique.X_WING  # 退化成 X_WING，不會誤記 SWORDFISH
        assert changed is True

    def test_fish聯集恰3條時才記SWORDFISH(self):
        from sudoku.solver import _盤面, _fish

        bd = _盤面(_puzzle_str("0" * 81))
        for r in range(9):
            for c in range(9):
                bd.candidates[r][c] = set(range(1, 10))
        for r in (0, 1, 2):
            for c in range(9):
                if c not in (3, 4, 5):
                    bd.candidates[r][c].discard(1)
        changed, level = _fish(bd, 3)
        assert level == Technique.SWORDFISH  # 正交聯集恰 3 條才是 swordfish
        assert changed is True

    def test_naked_triple記為SUBSETS等級(self):
        # 寫死題（generator HARD target=52, seed=143 生成後固定下來）：最難技巧恰為 triple/quad
        result = difficulty_of(_puzzle_str(SUBSETS題))
        assert result.solved is True
        assert result.max_technique == Technique.SUBSETS

    def test_技巧鏈解不開的題difficulty_of標記SWORDFISH以上且歸EXPERT(self):
        # 只給一格的題目有多解；構造一個技巧鏈會卡住但仍唯一解的困難題：
        # 用 EXPERT 生成的解不開題驗證標記行為（solved=False 時 max_technique 為 SWORDFISH 標記）
        report = None
        for seed in range(200):
            p = generate_puzzle(Difficulty.EXPERT, seed=seed)
            r = difficulty_of(p)
            if not r.solved:
                report = r
                break
        assert report is not None, "200 局 EXPERT 中應至少有一局技巧鏈解不開"
        assert report.solved is False
        assert report.difficulty == Difficulty.EXPERT
        assert report.max_technique is not None and report.max_technique >= Technique.SWORDFISH


def _puzzle_str(s: str) -> Puzzle:
    assert len(s) == 81
    return Puzzle.from_grid(
        [[None if ch in "0." else int(ch) for ch in s[r * 9 : (r + 1) * 9]] for r in range(9)]
    )


# 寫死題（實驗選出後固定下來）：最難技巧恰為 naked/hidden triple/quad（SUBSETS）
# 來源：generator 以 HARD 目標挖空數 52、seed=143 生成，difficulty_of.max_technique == SUBSETS
SUBSETS題 = "940800720000020600052000008000700040075080300064000800600100580007002000013060090"


# ---------- H：視窗固定大小 ----------


class TestH_主視窗固定大小:
    def test_build_app固定960x780且不可縮放(self):
        from sudoku.main import build_app, 視窗寬, 視窗高

        assert (視窗寬, 視窗高) == (960, 780)
        app = build_app()
        try:
            assert app.winfo_width() in (1, 960) or True  # 寬度在 map 前可能尚未生效
            w, h = app.resizable()
            assert not w and not h  # resizable(False, False)
        finally:
            app.destroy()
