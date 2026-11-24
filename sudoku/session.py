"""對局狀態機 GameSession：集中管理一局的所有遊戲規則（純邏輯層，UI 只訂閱其狀態）。

建構方式（三選一）：

- ``GameSession.new_game(difficulty, seed=None)``：依難度開新局；``difficulty`` 可為
  ``Difficulty`` 或字串（``"easy"`` / ``"medium"`` / ``"hard"`` / ``"expert"``），``mode`` 即難度字串；
- ``GameSession.daily(date)``：每日挑戰，``date`` 為 ``"YYYY-MM-DD"`` 字串或 ``datetime.date``；
  ``mode == "daily"``、``difficulty == "medium"``，同一天必為同一道題；
- ``GameSession.from_save(state_dict, mode)`` / ``GameSession.from_state_dict(state_dict, mode=None)``：
  由存檔續玩（state_dict schema 見下方 ``to_state_dict``）。

公開動作（暫停中或已勝利時動作會被拒絕；作用於題示/提示鎖定格亦會被拒絕）：

- ``select(row, col)``：選取格子（0–8）；
- ``place(digit)``：在選取格填入 1–9，回傳 bool（填錯也算成功填入，回傳 True）。
  題示不可改；填錯→該格 ``is_error`` 標紅、``mistakes + 1``（不設上限，紅色保留至修改）；
  填對→自動清同行/列/宮相同數的筆記；
- ``clear()``：清空選取格（題示/提示鎖定格不可清），回傳 bool；
- ``toggle_note(digit)``：在選取的空格切換候選數字筆記，回傳 bool；
- ``toggle_note_mode()``：切換筆記模式（``note_mode`` 布林，供 UI 判斷數字鍵意義）；
- ``undo()``：復原上一步（place / clear / toggle_note / hint 的完整動作堆疊，
  可一路回開局），回傳 bool（堆疊空為 False）；
- ``hint()``：隨機填一個空格的正確解，該格 ``is_hint`` 鎖定（綠色、不可改/清/筆記），
  每局 ``HINTS_PER_GAME``（3）次，用完回傳 None；成功回傳 ``(row, col, value)``；
- ``pause()`` / ``resume()``：暫停時 ``elapsed_sec`` 不增長、動作被擋；
- ``tick()``：每秒計時一次（暫停或已勝利時不計）；
- ``finish(result)``：結束本局並寫入遊玩紀錄（storage.add_history）。``"completed"`` 完成→
  更新統計（最佳時間/零錯誤/每日連勝）；``"abandoned"`` 放棄→刪該模式存檔。冪等，回傳歷史 entry；
- ``abandon()``：``finish("abandoned")`` 的簡寫。

狀態查詢（唯讀 property）：

- ``is_won()``：填滿且全正確（此時計時停止、動作被擋）；
- ``is_paused``、``elapsed_sec``、``mistakes``、``hints_left``、``selected``（(row, col) 或 None）、
  ``note_mode``、``mode``、``difficulty``、``date``（每日挑戰日期字串，否則 None）；
- ``puzzle`` / ``solution``：81 字元字串（空格 ``'0'``，行優先）；
- ``board``：81 個 ``SessionCell``（行優先）的唯讀 tuple，每格含 ``value`` / ``is_given`` /
  ``is_error`` / ``is_hint`` / ``notes``；``board_str`` 為目前盤面的 81 字元字串。

序列化（符合 storage.py docstring 的 state_dict schema）：``to_state_dict()``產生純 dict；
``from_state_dict(state, mode=None)`` / ``from_save(state, mode)`` 讀回，讀回後再 ``to_state_dict()``
與原 dict 一致（round-trip）。必要欄位為 ``puzzle`` / ``solution`` / ``board``（81 字元字串）、
``notes``（81 個 list）、``mistakes`` / ``hints_left`` / ``elapsed_sec``（int）；
額外欄位 ``mode`` / ``difficulty`` / ``date`` / ``selected`` / ``note_mode`` / ``paused`` /
``won`` / ``finished`` / ``hints`` 供續玩還原。
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date as _date
from typing import Any, Iterable

from sudoku import storage
from sudoku.generator import daily_challenge, generate_puzzle
from sudoku.model import Puzzle, Solution
from sudoku.solver import Difficulty, unique_solution

# 每局提示次數上限
HINTS_PER_GAME = 3

_合法難度字串 = ("easy", "medium", "hard", "expert")
_合法模式 = _合法難度字串 + ("daily",)


@dataclass(frozen=True)
class SessionCell:
    """對外唯讀的格子檢視。

    - ``value``：目前填的數字（1–9 或 None 表示空格）；
    - ``is_given``：是否為題示數（開局給定，不可改/清/筆記）；
    - ``is_error``：是否填錯標紅（保留至修改或清除）；
    - ``is_hint``：是否為提示填入（綠色鎖定，不可改/清/筆記）；
    - ``notes``：筆記候選數字集合（frozenset）。
    """

    value: int | None
    is_given: bool
    is_error: bool
    is_hint: bool
    notes: frozenset[int]


def _驗證_座標(row: int, col: int) -> None:
    if not (0 <= row <= 8 and 0 <= col <= 8):
        raise ValueError(f"座標超出範圍 0–8：({row}, {col})")


def _驗證_數字(digit: int) -> None:
    if not (1 <= digit <= 9):
        raise ValueError(f"數字超出範圍 1–9：{digit}")


def _grid_to_str(grid: Iterable[Iterable[int | None]]) -> str:
    return "".join(str(v) if v is not None else "0" for row in grid for v in row)


def _str_to_grid(s: str) -> list[list[int | None]]:
    return [[int(s[r * 9 + c]) if s[r * 9 + c] != "0" else None for c in range(9)] for r in range(9)]


class GameSession:
    """一局數獨的純邏輯狀態機；所有規則集中於此，UI 只讀狀態、呼叫動作。"""

    def __init__(
        self,
        puzzle: Puzzle,
        solution: Solution,
        *,
        mode: str,
        difficulty: str,
        date: str | None,
    ) -> None:
        if mode not in _合法模式:
            raise ValueError(f"未知模式：{mode!r}（合法：{', '.join(_合法模式)}）")
        if difficulty not in _合法難度字串:
            raise ValueError(f"未知難度：{difficulty!r}（合法：{', '.join(_合法難度字串)}）")
        self._puzzle_grid = [[puzzle.cell(r, c).value for c in range(9)] for r in range(9)]
        self._solution_grid = [[solution.cell(r, c).value for c in range(9)] for r in range(9)]
        self._mode = mode
        self._difficulty = difficulty  # 每日挑戰固定為 "medium"
        self._date = date
        # 可變對局狀態
        self._board = [[self._puzzle_grid[r][c] for c in range(9)] for r in range(9)]
        self._errors = [[False] * 9 for _ in range(9)]
        self._hints = [[False] * 9 for _ in range(9)]
        self._notes: list[list[set[int]]] = [[set() for _ in range(9)] for _ in range(9)]
        self._selected: tuple[int, int] | None = None
        self._note_mode = False
        self._paused = False
        self._finished = False
        self._history_entry: dict | None = None
        self._mistakes = 0
        self._hints_left = HINTS_PER_GAME
        self._elapsed_sec = 0
        self._undo_stack: list[Any] = []
        self._rng = random.Random()

    # ---------- 建構 ----------

    @classmethod
    def new_game(cls, difficulty: Difficulty | str, seed: int | None = None) -> "GameSession":
        """依難度開新局；``seed`` 可重現同一道題。``mode`` = 難度字串。"""
        if isinstance(difficulty, Difficulty):
            diff = difficulty
        elif isinstance(difficulty, str):
            diff = next((d for d in Difficulty if d.name.lower() == difficulty.lower()), None)
            if diff is None:
                raise ValueError(
                    f"未知難度：{difficulty!r}（合法：{', '.join(d.name.lower() for d in Difficulty)}）"
                ) from None
        else:
            raise TypeError(f"difficulty 必須是 Difficulty 或字串：{difficulty!r}")
        puzzle = generate_puzzle(diff, seed=seed)
        # 解答一律用計數式回溯（上限 2）的 unique_solution 求唯一解；
        # 技巧鏈 solve 只到 swordfish，解不開的唯一解題會 solved=False，不能當解答來源
        try:
            solution = unique_solution(puzzle)
        except ValueError as exc:  # pragma: no cover - 生成器保證唯一解
            raise RuntimeError(f"生成的題目沒有唯一解（理論上不應發生）：{exc}") from exc
        return cls(puzzle, solution, mode=diff.name.lower(), difficulty=diff.name.lower(), date=None)

    @classmethod
    def daily(cls, d: str | _date) -> "GameSession":
        """每日挑戰：以日期（``"YYYY-MM-DD"`` 或 ``datetime.date``）為種子開局。

        ``mode == "daily"``、``difficulty == "medium"``；同一天必為同一道題。
        """
        if isinstance(d, _date):
            date_str = d.isoformat()
        elif isinstance(d, str):
            date_str = d
        else:
            raise TypeError(f"日期必須是字串或 datetime.date：{d!r}")
        puzzle = daily_challenge(date_str)  # 內部驗證日期合法性，非法時拋 ValueError
        # 解答同樣走計數式回溯 unique_solution（技巧鏈解不開的題也能開局）
        try:
            solution = unique_solution(puzzle)
        except ValueError as exc:  # pragma: no cover - 生成器保證唯一解
            raise RuntimeError(f"每日挑戰題目沒有唯一解（理論上不應發生）：{exc}") from exc
        return cls(puzzle, solution, mode="daily", difficulty="medium", date=date_str)

    @classmethod
    def from_save(cls, state_dict: dict, mode: str) -> "GameSession":
        """由存檔續玩；``mode`` 為顯式指定（對應 storage 各模式存檔）。"""
        return cls.from_state_dict(state_dict, mode=mode)

    @classmethod
    def from_state_dict(cls, state_dict: dict, mode: str | None = None) -> "GameSession":
        """由 state_dict 還原一局（續玩）。``mode`` 省略時從 state 內的 ``mode`` 欄位推導。

        必要欄位（storage schema）：``puzzle`` / ``solution`` / ``board``（81 字元數字字串）、
        ``notes``（81 個 list）、``mistakes`` / ``hints_left`` / ``elapsed_sec``。
        缺漏或格式錯誤時拋出 ValueError。續玩後 undo 堆疊為空（存檔不保存堆疊，
        見 GLOSSARY 已知限制：續玩的局無法一路復原回開局）。
        """
        if not isinstance(state_dict, dict):
            raise TypeError("state_dict 必須是 dict")
        必要 = ("puzzle", "solution", "board", "notes", "mistakes", "hints_left", "elapsed_sec")
        缺 = [k for k in 必要 if k not in state_dict]
        if 缺:
            raise ValueError(f"state_dict 缺少必要欄位：{', '.join(缺)}")
        for key in ("puzzle", "solution", "board"):
            v = state_dict[key]
            if not isinstance(v, str) or len(v) != 81 or not v.isdigit():
                raise ValueError(f"{key} 必須是 81 字元的數字字串")
        notes = state_dict["notes"]
        if not isinstance(notes, list) or len(notes) != 81:
            raise ValueError("notes 必須是長度 81 的 list")

        resolved_mode = mode if mode is not None else state_dict.get("mode")
        if resolved_mode is None:
            resolved_mode = "daily" if state_dict.get("date") else None
        if resolved_mode not in _合法模式:
            raise ValueError(f"未知模式：{resolved_mode!r}（合法：{', '.join(_合法模式)}）")

        puzzle = Puzzle.from_grid(_str_to_grid(state_dict["puzzle"]))
        solution = Solution.from_grid(_str_to_grid(state_dict["solution"]))
        difficulty = state_dict.get("difficulty") or ("medium" if resolved_mode == "daily" else resolved_mode)
        if difficulty not in _合法難度字串:
            raise ValueError(f"未知難度：{difficulty!r}（合法：{', '.join(_合法難度字串)}）")

        s = cls(puzzle, solution, mode=resolved_mode, difficulty=difficulty, date=state_dict.get("date"))
        board = _str_to_grid(state_dict["board"])
        for r in range(9):
            for c in range(9):
                v = board[r][c]
                if v is None:
                    continue
                given = puzzle.cell(r, c).value
                if given is not None and v != given:
                    raise ValueError(f"存檔盤面與題示衝突於 ({r}, {c})")
                s._board[r][c] = v
                # 非題示格：依是否與解答一致標記錯誤（提示格值必正確，不受影響）
                s._errors[r][c] = given is None and v != solution.cell(r, c).value
        for idx in state_dict.get("hints") or []:
            r, c = divmod(int(idx), 9)
            s._hints[r][c] = True
        for idx, ns in enumerate(notes):
            r, c = divmod(idx, 9)
            s._notes[r][c] = {int(n) for n in ns} if s._board[r][c] is None else set()
        s._mistakes = int(state_dict["mistakes"])
        s._hints_left = int(state_dict["hints_left"])
        s._elapsed_sec = int(state_dict["elapsed_sec"])
        sel = state_dict.get("selected")
        if sel is not None:
            s._selected = (int(sel[0]), int(sel[1]))
        s._note_mode = bool(state_dict.get("note_mode", False))
        s._paused = bool(state_dict.get("paused", False))
        s._finished = bool(state_dict.get("finished", False))
        return s

    # ---------- 唯讀狀態 ----------

    @property
    def mode(self) -> str:
        """模式字串：``"easy"`` / ``"medium"`` / ``"hard"`` / ``"expert"`` / ``"daily"``。"""
        return self._mode

    @property
    def difficulty(self) -> str:
        """難度字串（每日挑戰固定為 ``"medium"``，供歷史與統計使用）。"""
        return self._difficulty

    @property
    def date(self) -> str | None:
        """每日挑戰的日期（``YYYY-MM-DD``）；非每日挑戰為 None。"""
        return self._date

    @property
    def puzzle(self) -> str:
        """題目，81 字元字串（空格 '0'，行優先）。"""
        return _grid_to_str(self._puzzle_grid)

    @property
    def solution(self) -> str:
        """唯一解答，81 字元字串（行優先，無空格）。"""
        return _grid_to_str(self._solution_grid)

    @property
    def board(self) -> tuple[SessionCell, ...]:
        """目前盤面，81 個 SessionCell（行優先）的唯讀 tuple。"""
        return tuple(
            SessionCell(
                value=self._board[r][c],
                is_given=self._puzzle_grid[r][c] is not None,
                is_error=self._errors[r][c],
                is_hint=self._hints[r][c],
                notes=frozenset(self._notes[r][c]),
            )
            for r in range(9)
            for c in range(9)
        )

    @property
    def board_str(self) -> str:
        """目前盤面的 81 字元字串（空格 '0'，行優先），即 state_dict 的 ``board`` 欄位值。"""
        return _grid_to_str(self._board)

    @property
    def selected(self) -> tuple[int, int] | None:
        """目前選取的格子 (row, col)；未選取為 None。"""
        return self._selected

    @property
    def note_mode(self) -> bool:
        """是否為筆記模式（UI 用來決定數字鍵是填入還是記筆記）。"""
        return self._note_mode

    @property
    def is_paused(self) -> bool:
        """是否暫停中（暫停時計時不增長、動作被擋）。"""
        return self._paused

    @property
    def elapsed_sec(self) -> int:
        """已過秒數（暫停與勝利後不增長）。"""
        return self._elapsed_sec

    @property
    def mistakes(self) -> int:
        """累計錯誤次數（不設上限、不因修改而回退）。"""
        return self._mistakes

    @property
    def hints_left(self) -> int:
        """剩餘提示次數（每局 HINTS_PER_GAME = 3 次）。"""
        return self._hints_left

    def is_won(self) -> bool:
        """是否已勝利：盤面填滿且全部正確（此時計時停止、動作被擋、undo 停用）。"""
        return all(
            self._board[r][c] == self._solution_grid[r][c] for r in range(9) for c in range(9)
        )

    # ---------- 內部工具 ----------

    def _可動作(self) -> bool:
        """目前是否接受玩家動作（未暫停且未勝利）。"""
        return not self._paused and not self.is_won()

    def _選取格(self) -> tuple[int, int] | None:
        return self._selected if self._可動作() else None

    def _鎖定(self, r: int, c: int) -> bool:
        """該格是否為題示或提示鎖定（不可改/清/筆記）。"""
        return self._puzzle_grid[r][c] is not None or self._hints[r][c]

    def _同單元(self, r: int, c: int) -> set[tuple[int, int]]:
        """格子 (r,c) 的同行/列/宮所有格子座標（含自己）。"""
        cells = {(r, cc) for cc in range(9)}
        cells.update((rr, c) for rr in range(9))
        br, bc = (r // 3) * 3, (c // 3) * 3
        for dr in range(3):
            for dc in range(3):
                cells.add((br + dr, bc + dc))
        return cells

    def _snapshot(self) -> dict:
        """目前遊戲狀態的深拷貝（undo 用）。選取游標 selected 不屬於遊戲動作，不納入還原。"""
        return {
            "board": [row[:] for row in self._board],
            "errors": [row[:] for row in self._errors],
            "hints": [row[:] for row in self._hints],
            "notes": [[set(ns) for ns in row] for row in self._notes],
            "mistakes": self._mistakes,
            "hints_left": self._hints_left,
            "elapsed": self._elapsed_sec,
        }

    def _restore(self, snap: dict) -> None:
        self._board = [row[:] for row in snap["board"]]
        self._errors = [row[:] for row in snap["errors"]]
        self._hints = [row[:] for row in snap["hints"]]
        self._notes = [[set(ns) for ns in row] for row in snap["notes"]]
        self._mistakes = snap["mistakes"]
        self._hints_left = snap["hints_left"]
        self._elapsed_sec = snap["elapsed"]

    def _push_undo(self) -> None:
        snap = self._snapshot()
        self._undo_stack.append(lambda: self._restore(snap))

    # ---------- 動作 ----------

    def select(self, row: int, col: int) -> None:
        """選取格子 (row, col)（0–8，非法座標拋 ValueError）。暫停/勝利後仍可選取（供 UI 高亮）。"""
        _驗證_座標(row, col)
        self._selected = (row, col)

    def place(self, digit: int) -> bool:
        """在選取格填入 digit（1–9，非法數字拋 ValueError）。

        回傳是否成功填入。未選取、暫停、已勝利、題示/提示鎖定格 → False；
        與現值相同且正確 → False（不算動作）。填錯 → 格子標紅、mistakes + 1；
        填對 → 自動清同行/列/宮相同數的筆記。兩種情況都回傳 True。
        """
        _驗證_數字(digit)
        sel = self._選取格()
        if sel is None:
            return False
        r, c = sel
        if self._鎖定(r, c):
            return False
        if self._board[r][c] == digit and not self._errors[r][c]:
            return False
        self._push_undo()
        self._board[r][c] = digit
        正確 = digit == self._solution_grid[r][c]
        self._errors[r][c] = not 正確
        if not 正確:
            self._mistakes += 1
        self._notes[r][c] = set()  # 填入後自己這格的筆記一律清掉
        if 正確:
            for rr, cc in self._同單元(r, c):
                if (rr, cc) != (r, c):
                    self._notes[rr][cc].discard(digit)
        return True

    def clear(self) -> bool:
        """清空選取格（連錯誤標記一起清）。題示/提示鎖定格、空格、未選取、暫停、已勝利 → False。"""
        sel = self._選取格()
        if sel is None:
            return False
        r, c = sel
        if self._鎖定(r, c) or self._board[r][c] is None:
            return False
        self._push_undo()
        self._board[r][c] = None
        self._errors[r][c] = False
        return True

    def toggle_note(self, digit: int) -> bool:
        """在選取的空格切換筆記 digit（1–9）。非空格/鎖定格/未選取/暫停/已勝利 → False。"""
        _驗證_數字(digit)
        sel = self._選取格()
        if sel is None:
            return False
        r, c = sel
        if self._鎖定(r, c) or self._board[r][c] is not None:
            return False
        self._push_undo()
        if digit in self._notes[r][c]:
            self._notes[r][c].discard(digit)
        else:
            self._notes[r][c].add(digit)
        return True

    def toggle_note_mode(self) -> None:
        """切換筆記模式（``note_mode`` 布林翻轉）。"""
        self._note_mode = not self._note_mode

    def undo(self) -> bool:
        """復原上一步動作（place / clear / toggle_note / hint 的完整堆疊，可一路回開局）。

        堆疊空或已勝利時回傳 False。暫停中仍可 undo。
        """
        if not self._undo_stack or self.is_won():
            return False
        self._undo_stack.pop()()
        return True

    def hint(self) -> tuple[int, int, int] | None:
        """提示：隨機選一個空格填入正確解，該格 ``is_hint`` 綠色鎖定（不可改/清/筆記）。

        每局 HINTS_PER_GAME（3）次；用完、暫停、已勝利、無空格時回傳 None。
        成功回傳 ``(row, col, value)``；提示填入進 undo 堆疊，可被 undo 還原。
        """
        if not self._可動作() or self._hints_left <= 0:
            return None
        empties = [(r, c) for r in range(9) for c in range(9) if self._board[r][c] is None]
        if not empties:
            return None
        r, c = self._rng.choice(empties)
        v = self._solution_grid[r][c]
        self._push_undo()
        self._board[r][c] = v
        self._hints[r][c] = True
        self._errors[r][c] = False
        self._notes[r][c] = set()
        self._hints_left -= 1
        for rr, cc in self._同單元(r, c):  # 與填對一致：清同單元相同數筆記
            if (rr, cc) != (r, c):
                self._notes[rr][cc].discard(v)
        return (r, c, v)

    def pause(self) -> None:
        """暫停：計時停止、動作被擋（棋盤遮罩由 UI繪製）。已暫停時為 no-op。"""
        self._paused = True

    def resume(self) -> None:
        """繼續：解除暫停。未暫停時為 no-op。"""
        self._paused = False

    def tick(self) -> None:
        """每秒計時一次；暫停中或已勝利時不計。"""
        if self._paused or self.is_won():
            return
        self._elapsed_sec += 1

    def finish(self, result: str) -> dict:
        """結束本局並寫入遊玩紀錄（storage.add_history），回傳寫入的歷史 entry。

        - ``result == "completed"``：更新生涯統計（最佳時間、零錯誤完成次數、每日挑戰連勝）；
        - ``result == "abandoned"``：刪除該模式的進行中存檔（歷史仍保留）。

        冪等：已結束過的局重複呼叫回傳同一筆 entry，不重複寫入。
        非法 result 拋 ValueError。
        """
        if result not in storage.RESULTS:
            raise ValueError(f"未知結果：{result!r}（合法：{', '.join(storage.RESULTS)}）")
        if self._finished:
            # 冪等：同一局只寫一次歷史。由存檔還原的已結束局沒有 entry，
            # 回傳依目前狀態重建的 entry 但不重複寫入。
            if self._history_entry is not None:
                return self._history_entry
            return {
                "mode": self._mode,
                "difficulty": self._difficulty,
                "result": result,
                "duration_sec": self._elapsed_sec,
                "mistakes": self._mistakes,
                **({"date": self._date} if self._date else {}),
            }
        self._finished = True
        self._history_entry = storage.add_history(
            {
                "mode": self._mode,
                "difficulty": self._difficulty,
                "result": result,
                "duration_sec": self._elapsed_sec,
                "mistakes": self._mistakes,
                **({"date": self._date} if self._date else {}),
            }
        )
        return self._history_entry

    def abandon(self) -> dict:
        """放棄本局：``finish("abandoned")`` 的簡寫（寫歷史為放棄、刪該模式存檔）。"""
        return self.finish("abandoned")

    # ---------- 序列化 ----------

    def to_state_dict(self) -> dict[str, Any]:
        """序列化為 JSON 友善的純 dict（符合 storage.py docstring 的 state_dict schema）。

        必要欄位：``puzzle`` / ``solution`` / ``board``（81 字元字串，空格 '0'）、
        ``notes``（81 個 list）、``mistakes`` / ``hints_left`` / ``elapsed_sec``（int）；
        另含 ``mode`` / ``difficulty`` / ``date`` / ``selected`` / ``note_mode`` / ``paused`` /
        ``won`` / ``finished`` / ``hints``（提示鎖定格索引 list）供續玩還原。
        ``from_state_dict`` 讀回後再 ``to_state_dict()`` 與本 dict 一致（round-trip）。
        """
        return {
            "puzzle": self.puzzle,
            "solution": self.solution,
            "board": self.board_str,
            "notes": [sorted(self._notes[r][c]) for r in range(9) for c in range(9)],
            "mistakes": self._mistakes,
            "hints_left": self._hints_left,
            "elapsed_sec": self._elapsed_sec,
            "mode": self._mode,
            "difficulty": self._difficulty,
            "date": self._date,
            "selected": list(self._selected) if self._selected is not None else None,
            "note_mode": self._note_mode,
            "paused": self._paused,
            "won": self.is_won(),
            "finished": self._finished,
            "hints": [r * 9 + c for r in range(9) for c in range(9) if self._hints[r][c]],
        }
