"""遊戲流程控制（票券 07）：把 GameSession 與自動存檔、勝利 / 放棄結算串起來。

純邏輯、不依賴 customtkinter，UI（board.py）與測試可共用：

- ``GameFlow(session)``：包住一個 ``GameSession``，每次有效動作（place / clear /
  toggle_note / undo / hint / note_mode 切換）與每次有效 ``tick()`` 後，
  以 ``storage.save_game(session.mode, session.to_state_dict())`` 自動存檔；
  暫停中的 tick 不計時也不寫檔；勝利時 ``finish("completed")``（寫歷史並刪存檔）；
  ``abandon()`` 記放棄並刪存檔。
- ``continuable_saves()``：列出所有可續玩的模式存檔（[(mode, saved_at), ...]，新到舊）。
- ``continue_session(mode)``：由某模式存檔還原 ``GameSession``（``from_save``續玩）；
  沒有存檔、存檔已結束（finished / won）或損毀時回傳 None 並清掉該無效存檔。
"""

from __future__ import annotations

from sudoku import storage
from sudoku.session import GameSession


def _存檔(session: GameSession) -> None:
    """把目前對局狀態寫入該模式的自動存檔（原子寫入由 storage 負責）。"""
    storage.save_game(session.mode, session.to_state_dict())


class GameFlow:
    """對局流程控制器：動作 → 更新 session → 自動存檔；勝利 / 放棄時結算。

    包裝 ``GameSession`` 的動作方法，回傳值與 ``GameSession`` 相同；
    無效動作（回傳 False / None 且狀態未變）不觸發存檔。
    """

    def __init__(self, session: GameSession) -> None:
        if not isinstance(session, GameSession):
            raise TypeError(f"session 必須是 GameSession：{session!r}")
        self.session = session
        _存檔(session)  # 開局即存檔，重開 app 能馬上續玩

    # ---------- 動作（動作後自動存檔） ----------

    def place(self, digit: int) -> bool:
        ok = self.session.place(digit)
        if ok:
            self._動作後()
        return ok

    def clear(self) -> bool:
        ok = self.session.clear()
        if ok:
            _存檔(self.session)
        return ok

    def toggle_note(self, digit: int) -> bool:
        ok = self.session.toggle_note(digit)
        if ok:
            _存檔(self.session)
        return ok

    def toggle_note_mode(self) -> None:
        self.session.toggle_note_mode()
        _存檔(self.session)

    def undo(self) -> bool:
        ok = self.session.undo()
        if ok:
            _存檔(self.session)
        return ok

    def hint(self) -> tuple[int, int, int] | None:
        res = self.session.hint()
        if res is not None:
            # 提示填入最後一格也要走勝利結算（finish + 刪存檔 + 停計時）
            self._動作後()
        return res

    def _動作後(self) -> None:
        """填入後：若已勝利則結算完成（寫歷史、刪除進行中存檔），否則自動存檔。"""
        if self.session.is_won():
            self.session.finish("completed")
            storage.delete_save(self.session.mode)  # 已完成的局不是進行中，清掉存檔
            return
        _存檔(self.session)

    # ---------- 暫停 / 計時 ----------

    def pause(self) -> None:
        self.session.pause()
        _存檔(self.session)

    def resume(self) -> None:
        self.session.resume()
        _存檔(self.session)

    def toggle_pause(self) -> None:
        """切換暫停 / 繼續（⏸ 按鈕與 Esc 共用）。"""
        if self.session.is_paused:
            self.resume()
        else:
            self.pause()

    def tick(self) -> None:
        """每秒計時一次並自動存檔；暫停或已勝利時不計時也不寫檔。"""
        if self.session.is_paused or self.session.is_won():
            return
        self.session.tick()
        _存檔(self.session)

    # ---------- 結束 ----------

    def abandon(self) -> dict:
        """放棄本局：寫歷史為放棄、刪除該模式存檔，回傳歷史 entry。"""
        return self.session.abandon()


def continuable_saves() -> list[tuple[str, str]]:
    """列出所有可續玩的模式存檔：[(mode, saved_at), ...]，依存檔時間新到舊排序。

    已結束（finished / won）或損毀的存檔不列入，並順手清掉。
    """
    結果: list[tuple[str, str]] = []
    for mode in storage.list_saves():
        記錄 = storage.load_game(mode)
        if 記錄 is None:
            continue
        state = 記錄.get("state")
        if not isinstance(state, dict) or state.get("finished") or state.get("won"):
            storage.delete_save(mode)  # 已結束的存檔不可續玩，清掉
            continue
        try:
            GameSession.from_save(state, mode)
        except (TypeError, ValueError, KeyError):
            storage.delete_save(mode)  # 損毀的存檔清掉
            continue
        結果.append((mode, 記錄.get("saved_at", "")))
    結果.sort(key=lambda item: item[1], reverse=True)  # saved_at 新到舊
    return 結果


def continue_session(mode: str) -> GameSession | None:
    """由某模式的存檔續玩：回傳還原的 ``GameSession``；無法續玩時回傳 None（並清掉無效存檔）。"""
    記錄 = storage.load_game(mode)
    if 記錄 is None:
        return None
    state = 記錄.get("state")
    if not isinstance(state, dict) or state.get("finished") or state.get("won"):
        storage.delete_save(mode)
        return None
    try:
        return GameSession.from_save(state, mode)
    except (TypeError, ValueError, KeyError):
        storage.delete_save(mode)
        return None
