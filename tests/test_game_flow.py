"""遊戲流程控制（sudoku.ui.flow.GameFlow）的單元測試。

測試接縫：GameFlow 公開 API——每次動作與每次有效 tick 後自動存檔、
暫停時計時不增長、勝利時 finish("completed") 並刪存檔、放棄時記歷史並刪存檔、
以及 continuable_saves / continue_session 的續玩還原（含已結束或損毀存檔的清理）。

純邏輯、不依賴 customtkinter；storage 以 SUDOKU_DATA_DIR 隔離到暫存資料夾。
"""

import pytest

from sudoku import storage
from sudoku.session import HINTS_PER_GAME, GameSession
from sudoku.ui.flow import GameFlow, continuable_saves, continue_session


@pytest.fixture(autouse=True)
def 隔離資料目錄(monkeypatch, tmp_path):
    """把使用者資料目錄導向暫存資料夾，不碰真實資料。"""
    monkeypatch.setenv("SUDOKU_DATA_DIR", str(tmp_path / "user-data"))


# ---------- 測試輔助 ----------


def _新局(seed=7) -> GameSession:
    return GameSession.new_game("easy", seed=seed)


def _空格索引(s: GameSession) -> list[int]:
    return [i for i in range(81) if s.board[i].value is None]


def _選(s: GameSession, i: int) -> None:
    r, c = divmod(i, 9)
    s.select(r, c)


def _填正確(s: GameSession, i: int) -> bool:
    _選(s, i)
    return s.place(int(s.solution[i]))


def _填錯(s: GameSession, i: int) -> int:
    正確 = int(s.solution[i])
    錯的 = next(d for d in range(1, 10) if d != 正確)
    _選(s, i)
    s.place(錯的)
    return 錯的


def _已存狀態(mode: str = "easy") -> dict:
    記錄 = storage.load_game(mode)
    assert 記錄 is not None, f"{mode} 應有存檔"
    return 記錄["state"]


# ---------- 自動存檔 ----------


class Test自動存檔:
    def test_建構即存檔(self):
        s = _新局()
        GameFlow(s)
        assert _已存狀態()["puzzle"] == s.puzzle
        assert "easy" in storage.list_saves()

    def test_place後存檔(self):
        s = _新局()
        flow = GameFlow(s)
        i = _空格索引(s)[0]
        _選(s, i)
        assert flow.place(int(s.solution[i])) is True
        assert _已存狀態() == s.to_state_dict()
        assert _已存狀態()["board"][i] == s.solution[i]

    def test_每次動作後都存檔(self):
        s = _新局(seed=13)
        flow = GameFlow(s)
        e1, e2, e3 = _空格索引(s)[:3]
        _選(s, e1)
        flow.place(int(s.solution[e1]))
        assert _已存狀態() == s.to_state_dict()
        _選(s, e2)
        flow.place(next(d for d in range(1, 10) if d != int(s.solution[e2])))
        assert _已存狀態() == s.to_state_dict()
        _選(s, e3)
        flow.toggle_note(4)
        assert _已存狀態() == s.to_state_dict()
        flow.toggle_note_mode()
        assert _已存狀態() == s.to_state_dict()
        assert flow.undo() is True
        assert _已存狀態() == s.to_state_dict()
        assert flow.hint() is not None
        assert _已存狀態() == s.to_state_dict()
        _選(s, e1)
        assert flow.clear() is True
        assert _已存狀態() == s.to_state_dict()

    def test_無效動作不寫存檔(self, monkeypatch):
        s = _新局()
        flow = GameFlow(s)
        次數 = {"n": 0}
        原save = storage.save_game

        def 計數(mode, state):
            次數["n"] += 1
            return 原save(mode, state)

        monkeypatch.setattr(storage, "save_game", 計數)
        assert flow.place(5) is False  # 未選取：無效動作
        assert flow.clear() is False
        assert flow.toggle_note(3) is False
        assert 次數["n"] == 0  # 無效動作不觸發存檔
        assert flow.undo() is False  # 堆疊空
        assert 次數["n"] == 0

    def test_tick時存檔(self):
        s = _新局()
        flow = GameFlow(s)
        flow.tick()
        flow.tick()
        assert _已存狀態()["elapsed_sec"] == 2 == s.elapsed_sec

    def test_暫停時tick不計時_恢復後繼續(self):
        s = _新局()
        flow = GameFlow(s)
        flow.tick()
        flow.pause()
        assert s.is_paused is True
        assert _已存狀態()["paused"] is True
        flow.tick()
        flow.tick()
        assert s.elapsed_sec == 1  # 暫停不增長
        assert _已存狀態()["elapsed_sec"] == 1
        flow.resume()
        assert _已存狀態()["paused"] is False
        flow.tick()
        assert s.elapsed_sec == 2
        assert _已存狀態()["elapsed_sec"] == 2

    def test_toggle_pause_切換(self):
        s = _新局()
        flow = GameFlow(s)
        assert s.is_paused is False
        flow.toggle_pause()
        assert s.is_paused is True
        flow.toggle_pause()
        assert s.is_paused is False


# ---------- 勝利與放棄 ----------


class Test勝利與放棄:
    def test_填滿全正確_完成寫史且刪存檔(self):
        s = _新局(seed=3)
        flow = GameFlow(s)
        for i in _空格索引(s):
            _選(s, i)
            assert flow.place(int(s.solution[i])) is True
        assert s.is_won() is True
        # 完成：寫 history、刪除進行中存檔、之後 tick 不會把存檔救回來
        assert storage.load_game("easy") is None
        assert storage.list_saves() == []
        flow.tick()
        assert storage.load_game("easy") is None
        entry = storage.list_history(result="completed")[0]
        assert entry["mode"] == "easy"
        assert entry["mistakes"] == 0

    def test_abandon_寫放棄歷史並刪存檔(self):
        s = _新局()
        flow = GameFlow(s)
        flow.tick()
        entry = flow.abandon()
        assert entry["result"] == "abandoned"
        assert storage.load_game("easy") is None
        assert storage.list_history(result="abandoned")[0]["mode"] == "easy"


# ---------- 續玩 ----------


class Test續玩:
    def test_continue_session_還原進行中對局(self):
        s = _新局(seed=11)
        flow = GameFlow(s)
        i = _空格索引(s)[0]
        _選(s, i)
        flow.place(int(s.solution[i]))
        flow.toggle_note_mode()
        flow.tick()
        flow.tick()
        s2 = continue_session("easy")
        assert s2 is not None
        assert s2.mode == "easy"
        assert s2.board_str == s.board_str
        assert s2.mistakes == s.mistakes
        assert s2.elapsed_sec == s.elapsed_sec == 2
        assert s2.note_mode is True
        assert s2.to_state_dict() == _已存狀態()
        # 續玩後仍可動作
        j = _空格索引(s2)[0]
        _選(s2, j)
        assert s2.place(int(s2.solution[j])) is True

    def test_沒有存檔時回傳None(self):
        assert continue_session("easy") is None

    def test_已結束的存檔不可續玩且被清掉(self):
        s = _新局()
        storage.save_game("easy", {**s.to_state_dict(), "finished": True})
        assert continue_session("easy") is None
        assert storage.load_game("easy") is None
        storage.save_game("hard", {**s.to_state_dict(), "mode": "hard", "won": True})
        assert continue_session("hard") is None
        assert storage.load_game("hard") is None

    def test_損毀存檔回傳None並清掉(self):
        storage.save_game("easy", {"puzzle": "bad"})
        assert continue_session("easy") is None
        assert storage.load_game("easy") is None

    def test_continuable_saves_依時間新到舊且跳過已結束(self):
        s = _新局()
        storage.save_game("easy", s.to_state_dict())
        storage.save_game("daily", {**GameSession.daily("2026-11-25").to_state_dict(), "finished": True})
        storage.save_game("medium", GameSession.new_game("medium", seed=2).to_state_dict())
        modes = [m for m, _ in continuable_saves()]
        assert "easy" in modes and "medium" in modes
        assert "daily" not in modes  # 已結束的存檔被清掉
        assert storage.load_game("daily") is None


# ---------- 端到端模擬事件（headless 走完一整局流程） ----------


class Test端到端模擬事件:
    def test_一整局流程_填錯_筆記_復原_提示_暫停_完成(self):
        s = _新局(seed=3)
        flow = GameFlow(s)
        empties = _空格索引(s)

        # 填錯 → 錯誤計次且存檔
        e0 = empties[0]
        _選(s, e0)
        flow.place(next(d for d in range(1, 10) if d != int(s.solution[e0])))
        assert s.mistakes == 1
        assert s.board[e0].is_error is True
        assert _已存狀態()["mistakes"] == 1

        # 筆記模式 + 記筆記 + 復原
        e1 = empties[1]
        flow.toggle_note_mode()
        assert s.note_mode is True
        _選(s, e1)
        flow.toggle_note(3)
        flow.toggle_note(7)
        assert s.board[e1].notes == frozenset({3, 7})
        assert flow.undo() is True
        assert s.board[e1].notes == frozenset({3})
        flow.toggle_note_mode()
        assert s.note_mode is False

        # 提示 → 綠色鎖定格、剩餘次數 -1
        res = flow.hint()
        assert res is not None
        r, c, v = res
        assert s.board[r * 9 + c].is_hint is True
        assert s.hints_left == HINTS_PER_GAME - 1

        # 暫停 → 計時停止；恢復 → 繼續計時
        flow.tick()
        t = s.elapsed_sec
        flow.pause()
        flow.tick()
        assert s.elapsed_sec == t
        flow.resume()
        flow.tick()
        assert s.elapsed_sec == t + 1

        # 把先前填錯的格子改填正確，其餘空格全部填正確 → 勝利、計時停止、寫史、刪存檔
        _選(s, e0)
        flow.place(int(s.solution[e0]))
        assert s.board[e0].is_error is False
        for i in _空格索引(s):
            _選(s, i)
            flow.place(int(s.solution[i]))
        assert s.is_won() is True
        flow.tick()
        assert s.elapsed_sec == t + 1  # 完成後計時停止
        assert storage.load_game("easy") is None
        assert storage.list_history(result="completed")[0]["mistakes"] == 1
