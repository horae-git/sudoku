"""對局狀態機（sudoku.session.GameSession）的單元測試。

測試接縫：GameSession 的公開 API（SPEC.md Testing Decisions）——
只驗外部行為：建構、動作（填入/清除/筆記/提示/復原/暫停/計時）、
狀態查詢、序列化讀回、結束時寫入歷史。

storage 相關行為以 SUDOKU_DATA_DIR 隔離到暫存資料夾（同 test_storage 做法）。
"""

from datetime import date

import pytest

from sudoku import storage
from sudoku.generator import Difficulty
from sudoku.session import HINTS_PER_GAME, GameSession


@pytest.fixture(autouse=True)
def 隔離資料目錄(monkeypatch, tmp_path):
    """把使用者資料目錄導向暫存資料夾，不碰真實資料。"""
    monkeypatch.setenv("SUDOKU_DATA_DIR", str(tmp_path / "user-data"))


# ---------- 測試輔助 ----------


def _新局(seed=7):
    return GameSession.new_game(Difficulty.EASY, seed=seed)


def _空格索引(session):
    """所有尚未填入的格子索引（行優先）。"""
    return [i for i in range(81) if session.board[i].value is None]


def _同單元索引(i):
    """格子 i 的同行/列/宮所有格子索引（含自己）。"""
    r, c = divmod(i, 9)
    cells = {r * 9 + cc for cc in range(9)}
    cells.update(rr * 9 + c for rr in range(9))
    br, bc = (r // 3) * 3, (c // 3) * 3
    for dr in range(3):
        for dc in range(3):
            cells.add((br + dr) * 9 + (bc + dc))
    return cells


def _選(session, i):
    r, c = divmod(i, 9)
    session.select(r, c)


def _填正確(session, i):
    _選(session, i)
    return session.place(int(session.solution[i]))


def _填錯(session, i):
    正確 = int(session.solution[i])
    錯的 = next(d for d in range(1, 10) if d != 正確)
    _選(session, i)
    session.place(錯的)
    return 錯的


def _題示索引(session):
    return next(i for i in range(81) if session.board[i].is_given)


def _遊戲狀態(d):
    """state_dict 去掉選取游標 selected 後的遊戲狀態（undo 不還原游標，比對時排除）。"""
    return {k: v for k, v in d.items() if k != "selected"}


def _minimal_state(**覆寫):
    """符合 storage schema 的最小 state_dict（只含 7 個必要欄位）。

    solution 用一個合法的完整解答盤面（行/列/宮不重複）。
    """
    解 = [
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
    solution = "".join(str(v) for row in 解 for v in row)
    state = {
        "puzzle": "0" * 81,
        "solution": solution,
        "board": "0" * 81,
        "notes": [[] for _ in range(81)],
        "mistakes": 0,
        "hints_left": 3,
        "elapsed_sec": 0,
    }
    state.update(覆寫)
    return state


# ---------- 建構 ----------


class Test建構:
    def test_new_game_初始狀態(self):
        s = _新局(seed=7)
        assert len(s.board) == 81
        assert s.mode == "easy"
        assert s.difficulty == "easy"
        assert s.mistakes == 0
        assert s.hints_left == HINTS_PER_GAME == 3
        assert s.elapsed_sec == 0
        assert s.is_paused is False
        assert s.is_won() is False
        assert s.selected is None
        assert s.note_mode is False
        # 題示格：值與 puzzle 一致、不錯不提示、無筆記
        for i in range(81):
            cell = s.board[i]
            if cell.is_given:
                assert cell.value == int(s.puzzle[i])
                assert not cell.is_error and not cell.is_hint
                assert cell.notes == frozenset()
            else:
                assert cell.value is None

    def test_new_game_seed_可重現(self):
        a = GameSession.new_game(Difficulty.EASY, seed=42)
        b = GameSession.new_game(Difficulty.EASY, seed=42)
        assert a.puzzle == b.puzzle
        assert [c.value for c in a.board] == [c.value for c in b.board]

    def test_new_game_接受字串難度(self):
        assert GameSession.new_game("medium", seed=1).mode == "medium"
        with pytest.raises(ValueError):
            GameSession.new_game("nightmare")
        with pytest.raises(TypeError):
            GameSession.new_game(123)

    def test_daily_同一天同一題(self):
        a = GameSession.daily("2026-11-25")
        b = GameSession.daily("2026-11-25")
        assert a.puzzle == b.puzzle
        assert a.mode == "daily"
        assert a.difficulty == "medium"  # 每日挑戰的難度固定記 medium
        assert a.date == "2026-11-25"
        c = GameSession.daily(date(2026, 11, 25))
        assert c.puzzle == a.puzzle

    def test_daily_非法日期報錯(self):
        with pytest.raises(ValueError):
            GameSession.daily("2026-02-30")
        with pytest.raises(ValueError):
            GameSession.daily("not-a-date")

    def test_from_save_最小_state_dict(self):
        s = GameSession.from_save(_minimal_state(mistakes=2, elapsed_sec=9), "easy")
        assert s.mode == "easy"
        assert s.mistakes == 2
        assert s.elapsed_sec == 9
        assert s.hints_left == 3
        assert len(s.board) == 81
        assert all(c.value is None for c in s.board)

    def test_from_save_非法輸入報錯(self):
        with pytest.raises(ValueError):
            GameSession.from_save(_minimal_state(puzzle="0" * 80), "easy")
        with pytest.raises(ValueError):
            GameSession.from_save(_minimal_state(), "nightmare")
        with pytest.raises(ValueError):
            GameSession.from_state_dict({"puzzle": "0" * 81})  # 缺必要欄位


# ---------- 選取與填入 ----------


class Test選取與填入:
    def test_select(self):
        s = _新局()
        s.select(3, 4)
        assert s.selected == (3, 4)
        with pytest.raises(ValueError):
            s.select(9, 0)
        with pytest.raises(ValueError):
            s.select(0, -1)

    def test_place_正確填入(self):
        s = _新局()
        i = _空格索引(s)[0]
        d = int(s.solution[i])
        _選(s, i)
        assert s.place(d) is True
        cell = s.board[i]
        assert cell.value == d
        assert not cell.is_given and not cell.is_error and not cell.is_hint

    def test_place_未選取格_noop(self):
        s = _新局()
        assert s.place(5) is False
        assert s.mistakes == 0

    def test_place_非法數字報錯(self):
        s = _新局()
        _選(s, _空格索引(s)[0])
        with pytest.raises(ValueError):
            s.place(0)
        with pytest.raises(ValueError):
            s.place(10)

    def test_place_題示不可改(self):
        s = _新局()
        g = _題示索引(s)
        orig = s.board[g].value
        _選(s, g)
        other = next(d for d in range(1, 10) if d != orig)
        assert s.place(other) is False
        assert s.place(orig) is False  # 填相同值也不算動作
        assert s.clear() is False
        assert s.board[g].value == orig
        assert s.mistakes == 0

    def test_place_錯誤標記與計次_不設上限(self):
        s = _新局()
        i, j = _空格索引(s)[:2]
        _填錯(s, i)
        assert s.board[i].is_error is True
        assert s.board[i].value is not None  # 錯誤值保留
        assert s.mistakes == 1
        _填錯(s, j)
        assert s.board[j].is_error is True
        assert s.mistakes == 2  # 不設上限

    def test_修改錯誤格_標記清除但計次保留(self):
        s = _新局()
        i = _空格索引(s)[0]
        _填錯(s, i)
        assert s.mistakes == 1
        assert _填正確(s, i) is True
        assert s.board[i].is_error is False
        assert s.board[i].value == int(s.solution[i])
        assert s.mistakes == 1  # 累計錯誤不回退

    def test_place_可覆寫玩家已填的格(self):
        s = _新局()
        i = _空格索引(s)[0]
        d = int(s.solution[i])
        assert _填正確(s, i) is True
        other = next(x for x in range(1, 10) if x != d)
        _選(s, i)
        assert s.place(other) is True
        assert s.board[i].value == other
        assert s.board[i].is_error is True  # 換成錯的


# ---------- 清除 ----------


class Test清除:
    def test_clear_玩家填的格(self):
        s = _新局()
        i = _空格索引(s)[0]
        _填正確(s, i)
        _選(s, i)
        assert s.clear() is True
        assert s.board[i].value is None

    def test_clear_錯誤格連標記一起清(self):
        s = _新局()
        i = _空格索引(s)[0]
        _填錯(s, i)
        _選(s, i)
        assert s.clear() is True
        assert s.board[i].value is None
        assert s.board[i].is_error is False

    def test_clear_空格_noop(self):
        s = _新局()
        _選(s, _空格索引(s)[0])
        assert s.clear() is False


# ---------- 筆記 ----------


class Test筆記:
    def test_toggle_note_加與拿掉(self):
        s = _新局()
        i = _空格索引(s)[0]
        _選(s, i)
        assert s.toggle_note(5) is True
        assert s.board[i].notes == frozenset({5})
        assert s.toggle_note(5) is True
        assert s.board[i].notes == frozenset()

    def test_toggle_note_已填格與未選取_noop(self):
        s = _新局()
        _選(s, _題示索引(s))
        assert s.toggle_note(3) is False  # 題示格不能筆記
        s2 = _新局()
        assert s2.toggle_note(1) is False  # 未選取

    def test_toggle_note_非法數字報錯(self):
        s = _新局()
        _選(s, _空格索引(s)[0])
        with pytest.raises(ValueError):
            s.toggle_note(0)

    def test_note_mode_切換(self):
        s = _新局()
        assert s.note_mode is False
        s.toggle_note_mode()
        assert s.note_mode is True
        s.toggle_note_mode()
        assert s.note_mode is False

    def test_填對自動清同行列宮相同數筆記(self):
        s = _新局(seed=13)
        i = _空格索引(s)[0]
        d = int(s.solution[i])
        peers = sorted(j for j in _同單元索引(i) if j != i and s.board[j].value is None)[:3]
        另一個筆記 = d % 9 + 1
        for j in peers:
            _選(s, j)
            s.toggle_note(d)
            s.toggle_note(另一個筆記)
        _選(s, i)
        s.toggle_note(d)  # 自己格子的筆記也會被清掉
        assert s.place(d) is True
        for j in peers:
            assert d not in s.board[j].notes
            assert 另一個筆記 in s.board[j].notes  # 其他數字的筆記保留
        assert s.board[i].notes == frozenset()
        # 不同單元的筆記不受影響
        far = next(j for j in range(81) if j not in _同單元索引(i) and s.board[j].value is None)
        _選(s, far)
        s.toggle_note(d)
        k = _空格索引(s)[0]
        if k != far and k != i:
            dk = int(s.solution[k])
            if dk == d and k in _同單元索引(i):
                pass
        assert s.board[far].notes == frozenset({d})


# ---------- 提示 ----------


class Test提示:
    def test_hint_填入正確解且鎖定(self):
        s = _新局(seed=9)
        res = s.hint()
        assert res is not None
        r, c, v = res
        idx = r * 9 + c
        cell = s.board[idx]
        assert cell.value == v == int(s.solution[idx])
        assert cell.is_hint is True
        assert s.hints_left == HINTS_PER_GAME - 1
        # 提示格鎖定：不可填入/清除/筆記
        s.select(r, c)
        other = next(d for d in range(1, 10) if d != v)
        assert s.place(other) is False
        assert s.clear() is False
        assert s.toggle_note(1) is False
        assert s.board[idx].value == v

    def test_hint_每局三次_用完回報(self):
        s = _新局(seed=9)
        assert s.hint() is not None
        assert s.hint() is not None
        assert s.hint() is not None
        assert s.hints_left == 0
        assert s.hint() is None  # 超過次數回報 None

    def test_hint_可被_undo_還原(self):
        s = _新局(seed=9)
        before = s.to_state_dict()
        assert s.hint() is not None
        assert s.undo() is True
        assert s.to_state_dict() == before
        assert s.hints_left == HINTS_PER_GAME


# ---------- 復原 ----------


class Test復原:
    def test_undo_一路回開局(self):
        s = _新局(seed=7)
        e1, e2, e3 = _空格索引(s)[:3]
        fresh = s.to_state_dict()  # 開局時尚未選取任何格
        _填正確(s, e1)
        _填錯(s, e2)
        _選(s, e3)
        s.toggle_note(4)
        s.hint()
        count = 0
        while s.undo():
            count += 1
        assert count == 4  # place、place、note、hint 各一次
        assert _遊戲狀態(s.to_state_dict()) == _遊戲狀態(fresh)  # 遊戲狀態完全回到開局
        assert s.mistakes == 0
        assert s.hints_left == HINTS_PER_GAME

    def test_undo_空堆疊回傳_False(self):
        s = _新局()
        assert s.undo() is False


# ---------- 暫停與計時 ----------


class Test暫停與計時:
    def test_tick_每秒計時(self):
        s = _新局()
        s.tick()
        s.tick()
        s.tick()
        assert s.elapsed_sec == 3

    def test_pause_暫停時不計時且動作被擋(self):
        s = _新局()
        s.tick()
        s.pause()
        assert s.is_paused is True
        s.tick()
        s.tick()
        assert s.elapsed_sec == 1  # 暫停不增長
        i = _空格索引(s)[0]
        _選(s, i)
        assert s.place(int(s.solution[i])) is False
        assert s.hint() is None
        s.resume()
        assert s.is_paused is False
        s.tick()
        assert s.elapsed_sec == 2
        assert s.place(int(s.solution[i])) is True


# ---------- 勝利判定 ----------


class Test勝利:
    def test_填滿且全正確才勝利_勝利後計時停止(self):
        s = _新局(seed=3)
        s.tick()
        for i in _空格索引(s):
            _填正確(s, i)
        assert s.is_won() is True
        e = s.elapsed_sec
        s.tick()
        assert s.elapsed_sec == e  # 完成後計時停止
        _選(s, 0)
        assert s.place(1) is False  # 贏後不能再改

    def test_填滿但有錯誤不算勝利(self):
        s = _新局(seed=3)
        empties = _空格索引(s)
        for i in empties[:-1]:
            _填正確(s, i)
        _填錯(s, empties[-1])
        assert s.board[empties[-1]].value is not None  # 已填滿
        assert s.is_won() is False
        assert s.mistakes == 1


# ---------- 序列化 ----------


class Test序列化:
    def test_動作後讀回一致(self):
        s = _新局(seed=11)
        e1, e2, e3 = _空格索引(s)[:3]
        _填正確(s, e1)
        _填錯(s, e2)
        _選(s, e3)
        s.toggle_note(7)
        s.toggle_note_mode()
        s.hint()
        s.tick()
        s.tick()
        s.select(2, 5)
        d1 = s.to_state_dict()

        s2 = GameSession.from_state_dict(d1, s.mode)
        assert s2.to_state_dict() == d1  # 序列化讀回一致
        assert [(c.value, c.is_given, c.is_error, c.is_hint, c.notes) for c in s2.board] == [
            (c.value, c.is_given, c.is_error, c.is_hint, c.notes) for c in s.board
        ]
        assert s2.selected == s.selected == (2, 5)
        assert s2.mistakes == s.mistakes == 1
        assert s2.elapsed_sec == s.elapsed_sec == 2
        assert s2.hints_left == s.hints_left == HINTS_PER_GAME - 1
        assert s2.note_mode is True
        assert s2.mode == s.mode == "easy"

    def test_from_save_續玩後可繼續動作與復原(self):
        s = _新局(seed=21)
        _填正確(s, _空格索引(s)[0])
        s2 = GameSession.from_save(s.to_state_dict(), s.mode)
        讀檔時 = s2.to_state_dict()
        # 續玩：可再填、可 undo 回續玩前的遊戲狀態
        i = _空格索引(s2)[0]
        assert _填正確(s2, i) is True
        assert s2.undo() is True
        assert _遊戲狀態(s2.to_state_dict()) == _遊戲狀態(讀檔時)

    def test_state_dict_符合_storage_schema(self):
        s = _新局(seed=5)
        d = s.to_state_dict()
        # storage docstring 定義的必要 key
        for key in ("puzzle", "solution", "board", "notes", "mistakes", "hints_left", "elapsed_sec"):
            assert key in d
        assert len(d["puzzle"]) == len(d["solution"]) == len(d["board"]) == 81
        assert all(ch.isdigit() for ch in d["board"])
        assert len(d["notes"]) == 81
        # 能直接交給 storage 存檔並讀回
        記錄 = storage.save_game(s.mode, d)
        assert storage.load_game(s.mode) == 記錄


# ---------- 結束時寫入歷史 ----------


class Test結束寫史:
    def test_finish_completed_寫歷史並更新統計(self):
        s = _新局(seed=7)
        s.tick()
        s.tick()
        entry = s.finish("completed")
        assert entry["result"] == "completed"
        assert entry["mode"] == "easy"
        assert entry["difficulty"] == "easy"
        assert entry["duration_sec"] == 2
        assert entry["mistakes"] == 0
        assert len(storage.list_history()) == 1
        assert storage.list_history(result="completed")[0]["mode"] == "easy"
        stats = storage.get_stats()
        assert stats["best_time"]["easy"] == 2
        assert stats["perfect_clears"]["easy"] == 1  # 零錯誤完成

    def test_finish_冪等_不重複寫史(self):
        s = _新局(seed=7)
        e1 = s.finish("completed")
        e2 = s.finish("completed")
        assert e1 == e2
        assert len(storage.list_history()) == 1

    def test_abandon_寫放棄並刪存檔(self):
        s = _新局(seed=7)
        storage.save_game(s.mode, s.to_state_dict())
        assert storage.load_game("easy") is not None
        entry = s.abandon()
        assert entry["result"] == "abandoned"
        assert storage.load_game("easy") is None  # 存檔已刪
        assert storage.list_saves() == []
        assert storage.list_history(result="abandoned")[0]["mode"] == "easy"  # 歷史保留
        # 放棄不計最佳時間
        assert storage.get_stats()["best_time"]["easy"] is None

    def test_daily_完成記連勝(self):
        s = GameSession.daily("2026-11-25")
        entry = s.finish("completed")
        assert entry["mode"] == "daily"
        assert entry["difficulty"] == "medium"
        assert entry["date"] == "2026-11-25"
        stats = storage.get_stats()
        assert stats["daily_streak"] == 1
        assert stats["daily_wins"] == ["2026-11-25"]

    def test_finish_非法結果報錯(self):
        s = _新局()
        with pytest.raises(ValueError):
            s.finish("quit")
