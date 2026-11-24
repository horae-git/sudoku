"""票券 08：勝利畫面（獨立置中 modal，底部按鈕完整可見、不被遮擋）。

測試接縫：

- 純邏輯：``sudoku.ui.board.victory_summary(session, mode)``——大標題、本局用時（mm:ss）、
  錯誤次數、難度標籤（簡單/中等/困難/專家）、每日挑戰局的「📅 本日題目（日期）」、
  零錯誤時的「✨ 零錯誤！」特別標記；
- headless UI：建構 BoardView、模擬填完一局觸發勝利 → 獨立置中 modal（CTkToplevel +
  ``grab_set`` 唯一焦點、不疊在棋盤格子上）彈出且內容正確；兩個圓角按鈕存在且完整可見；
  點「🏠 返回首頁」切回主選單、點「🔁 再來一局」開同模式新局；
  勝利後計時停止、modal 期間 tick 不再跑、modal 關閉後棋盤不可再編輯。

import customtkinter 在 headless 下即可建構視窗（見 test_theme_picker）。
"""

import pytest

from sudoku import storage
from sudoku.session import GameSession
from sudoku.ui.board import victory_summary

# 經典完整解答（題示 (0,0)=5 與解答一致），供建構可控的 session state_dict
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


def _可控局(mode: str = "easy", date: str | None = None, mistakes: int = 0, elapsed_sec: int = 0) -> GameSession:
    """建構可控的局：題示只有 (0,0)=5，可指定模式 / 日期 / 錯誤數 / 用時。"""
    puzzle = ["0"] * 81
    puzzle[0] = "5"
    board = ["0"] * 81
    board[0] = "5"
    state = {
        "puzzle": "".join(puzzle),
        "solution": _SOLUTION_STR,
        "board": "".join(board),
        "notes": [[] for _ in range(81)],
        "mistakes": mistakes,
        "hints_left": 3,
        "elapsed_sec": elapsed_sec,
        "mode": mode,
        "difficulty": "medium" if mode == "daily" else mode,
        "date": date,
    }
    return GameSession.from_state_dict(state, mode)


# ---------- purely logic：victory_summary ----------


class TestVictorySummary純邏輯:
    def test_標題用時錯誤難度欄位(self):
        s = _可控局(mistakes=2, elapsed_sec=125)
        sm = victory_summary(s)
        assert sm["title"] == "🎉 恭喜完成！"
        assert sm["time"] == "02:05"
        assert sm["mistakes"] == 2
        assert sm["zero_error"] is False
        assert sm["difficulty_label"] == "簡單"
        assert sm["daily_note"] is None
        assert ("本局用時", "02:05") in sm["lines"]
        assert ("錯誤次數", "2 次") in sm["lines"]
        assert ("難度", "簡單") in sm["lines"]

    def test_各難度標籤(self):
        for mode, label in (("easy", "簡單"), ("medium", "中等"), ("hard", "困難"), ("expert", "專家")):
            sm = victory_summary(_可控局(mode=mode), mode)
            assert sm["difficulty_label"] == label
            assert ("難度", label) in sm["lines"]

    def test_每日挑戰額外標本日題目(self):
        s = _可控局(mode="daily", date="2026-11-25")
        sm = victory_summary(s)
        assert sm["daily_note"] == "📅 本日題目（2026-11-25）"
        assert sm["difficulty_label"] == "📅 本日題目（2026-11-25）"
        assert ("每日挑戰", "📅 本日題目（2026-11-25）") in sm["lines"]

    def test_非每日挑戰沒有本日題目行(self):
        sm = victory_summary(_可控局(mode="hard"))
        assert sm["daily_note"] is None
        assert all("本日題目" not in value for _, value in sm["lines"])

    def test_零錯誤特別標記(self):
        sm = victory_summary(_可控局(mistakes=0))
        assert sm["zero_error"] is True
        assert ("成就", "✨ 零錯誤！") in sm["lines"]

    def test_有錯誤時不出現零錯誤標記(self):
        sm = victory_summary(_可控局(mistakes=1))
        assert sm["zero_error"] is False
        assert all("零錯誤" not in value for _, value in sm["lines"])


# ---------- headless UI ----------


@pytest.fixture(scope="module")
def app_root():
    """全模組共用的 headless 主視窗（建構後立刻 map）。

    全程只用這一個根視窗（tests/conftest.py 另有常駐根視窗保駕，避開 Tk9
    在 macOS 上多根視窗建構 / 銷毀的 segfault 怪癖），模組結束才銷毀；
    每個測試結束後由 ``app`` fixture 清掉子畫面 / modal / grab / 計時器。
    """
    import customtkinter as ctk

    root = ctk.CTk()
    root.geometry("960x760")
    root.update_idletasks()
    root.update()
    yield root
    root.destroy()


@pytest.fixture()
def app(app_root, monkeypatch, tmp_path):
    """隔離資料目錄 + 清理上一個測試留下的子畫面 / modal / grab / 計時器後，回傳共用根視窗。"""
    import customtkinter as ctk

    monkeypatch.setenv("SUDOKU_DATA_DIR", str(tmp_path / "user-data"))
    for child in list(app_root.winfo_children()):
        if isinstance(child, ctk.CTkToplevel):
            try:
                child.grab_release()
            except Exception:
                pass
            child.destroy()
        elif getattr(child, "_timer_id", None) is not None:
            child._stop_timer()
        if isinstance(child, (ctk.CTkFrame, ctk.CTkToplevel)):
            child.destroy()
    app_root.update_idletasks()
    return app_root


def _all_texts(widget) -> list[str]:
    """遞迴收集 widget 樹上所有可讀到的文字。"""
    result: list[str] = []
    for child in widget.winfo_children():
        try:
            text = child.cget("text")
        except Exception:
            text = None
        if isinstance(text, str):
            result.append(text)
        result.extend(_all_texts(child))
    return result


def _填完一局(view, 錯一次: bool = False) -> None:
    """模擬填完一局觸發勝利。

    大部分格子透過 ``flow.place`` 走真實對局動作（自動存檔），最後一格用模擬的
    UI 事件 ``view._on_number`` 填入——勝利偵測與 modal 彈出就發生在這次事件。
    （每個 UI 事件都會重繪整個棋盤，81 次全走 UI 事件在 headless 下太慢。）
    """
    s = view.session
    empties = [i for i in range(81) if s.board[i].value is None]
    if 錯一次 and empties:
        i = empties[0]
        r, c = divmod(i, 9)
        s.select(r, c)
        view.flow.place(next(d for d in range(1, 10) if d != int(s.solution[i])))
        s.select(r, c)
        view.flow.place(int(s.solution[i]))  # 改填正確（錯誤次數保留）
    for i in empties:
        if s.board[i].value is None and i != empties[-1]:
            r, c = divmod(i, 9)
            s.select(r, c)
            assert view.flow.place(int(s.solution[i])) is True
    # 最後一格用模擬的數字鍵事件填入 → 觸發勝利 → modal
    last = empties[-1]
    r, c = divmod(last, 9)
    s.select(r, c)
    view._on_number(int(s.solution[last]))
    assert s.is_won() is True


def _按鈕完整可見(modal, btn) -> None:
    """按鈕已 map 且完整落在 modal 視窗範圍內（不被任何東西遮擋 / 裁切）。"""
    assert btn.winfo_ismapped() == 1
    assert btn.winfo_x() >= 0
    assert btn.winfo_y() >= 0
    assert btn.winfo_x() + btn.winfo_width() <= modal.winfo_width()
    assert btn.winfo_y() + btn.winfo_height() <= modal.winfo_height()


class Test勝利Modal彈出與內容:
    def test_填完觸發獨立置中modal且grab唯一焦點(self, app):
        import customtkinter as ctk

        from sudoku.ui.board import BoardView

        view = BoardView(app, GameSession.new_game("easy", seed=3), mode_label="簡單", on_home=lambda: None)
        view.pack(expand=True, fill="both")
        app.update()
        _填完一局(view)
        assert view.session.is_won() is True

        modal = view.victory_modal
        assert modal is not None and modal.winfo_exists() == 1
        app.update()
        # 獨立 Toplevel 視窗（master 為根視窗），絕不疊在棋盤格子上
        assert isinstance(modal, ctk.CTkToplevel)
        assert modal.master is app
        assert app.grab_current() is modal  # grab_set：modal 為唯一焦點
        # 置中且完整落在主視窗範圍內
        assert app.winfo_rootx() <= modal.winfo_rootx()
        assert modal.winfo_rootx() + modal.winfo_width() <= app.winfo_rootx() + app.winfo_width()
        assert app.winfo_rooty() <= modal.winfo_rooty()
        assert modal.winfo_rooty() + modal.winfo_height() <= app.winfo_rooty() + app.winfo_height()

    def test_modal內容含用時錯誤難度與兩個可見按鈕(self, app):
        from sudoku.ui.board import BoardView

        view = BoardView(app, GameSession.new_game("easy", seed=3), mode_label="簡單", on_home=lambda: None)
        view.pack(expand=True, fill="both")
        view.flow.tick()
        view.flow.tick()
        app.update()
        _填完一局(view, 錯一次=True)
        assert view.session.is_won() is True
        assert view.session.mistakes == 1
        assert view.session.elapsed_sec == 2

        modal = view.victory_modal
        app.update()
        文字 = "\n".join(_all_texts(modal))
        assert "🎉 恭喜完成！" in 文字
        assert "本局用時" in 文字 and "00:02" in 文字
        assert "錯誤次數" in 文字 and "1 次" in 文字
        assert "難度" in 文字 and "簡單" in 文字
        assert "零錯誤" not in 文字  # 有錯誤時不標零錯誤
        # 底部兩個圓角按鈕存在且完整可見、不被遮擋
        assert modal.home_button.cget("text") == "🏠 返回首頁"
        assert modal.again_button.cget("text") == "🔁 再來一局"
        assert modal.home_button.cget("corner_radius") > 0
        assert modal.again_button.cget("corner_radius") > 0
        _按鈕完整可見(modal, modal.home_button)
        _按鈕完整可見(modal, modal.again_button)
        # 兩個按鈕在同一排（底部按鈕列）
        assert abs(modal.home_button.winfo_y() - modal.again_button.winfo_y()) <= 2

    def test_零錯誤勝利顯示特別標記(self, app):
        from sudoku.ui.board import BoardView

        view = BoardView(app, GameSession.new_game("easy", seed=3), on_home=lambda: None)
        view.pack(expand=True, fill="both")
        app.update()
        _填完一局(view)  # 全程零錯誤
        modal = view.victory_modal
        app.update()
        文字 = "\n".join(_all_texts(modal))
        assert "✨ 零錯誤！" in 文字
        assert "0 次" in 文字

    def test_每日挑戰modal額外顯示本日題目(self, app):
        from sudoku.ui.board import BoardView, mode_display_label

        s = GameSession.daily("2026-11-25")
        view = BoardView(app, s, mode_label=mode_display_label(s.mode, s.date), on_home=lambda: None)
        view.pack(expand=True, fill="both")
        app.update()
        _填完一局(view)
        modal = view.victory_modal
        app.update()
        文字 = "\n".join(_all_texts(modal))
        assert "📅 本日題目（2026-11-25）" in 文字


class Test勝利後行為:
    def test_勝利後計時停止_modal期間tick不再跑_棋盤不可再編輯(self, app):
        from sudoku.ui.board import BoardView

        view = BoardView(app, GameSession.new_game("easy", seed=3), on_home=lambda: None)
        view.pack(expand=True, fill="both")
        app.update()
        view.flow.tick()
        view.flow.tick()
        view.flow.tick()
        assert view.session.elapsed_sec == 3
        _填完一局(view)
        assert view.session.is_won() is True
        modal = view.victory_modal
        assert modal is not None
        # 計時器已停
        assert view._timer_id is None
        assert view.session.elapsed_sec == 3
        # modal 期間 tick 不再跑（手動觸發也不會計時、不會重排計時器）
        view._tick()
        view.flow.tick()
        assert view.session.elapsed_sec == 3
        assert view._timer_id is None
        # session 已 won：棋盤不可再編輯
        before = view.session.board_str
        view.session.select(0, 1)
        assert view.flow.place(9) is False
        view._on_number(9)
        assert view.session.board_str == before
        assert view.session.mistakes == 0
        # 不會重複彈出第二個 modal
        assert view.victory_modal is modal

    def test_點返回首頁切回主選單_且勝利局不記放棄(self, app):
        from sudoku.ui.board import BoardView

        events: list[str] = []
        view = BoardView(app, GameSession.new_game("easy", seed=3), on_home=lambda: events.append("home"))
        view.pack(expand=True, fill="both")
        app.update()
        _填完一局(view)
        modal = view.victory_modal
        app.update()
        modal.home_button.invoke()
        assert events == ["home"]  # 切回主選單
        assert modal.winfo_exists() == 0  # modal 關閉
        assert app.grab_current() is None  # grab 已釋放
        # 勝利局寫 completed，不會誤記為放棄
        assert storage.list_history(result="abandoned") == []
        completed = storage.list_history(result="completed")
        assert len(completed) == 1 and completed[0]["mode"] == "easy"

    def test_點再來一局_同難度新題(self, app):
        from sudoku.ui.board import BoardView

        calls: list[tuple] = []
        view = BoardView(
            app, GameSession.new_game("hard", seed=5), on_home=lambda: None,
            on_play_again=lambda mode, date: calls.append((mode, date)),
        )
        view.pack(expand=True, fill="both")
        app.update()
        _填完一局(view)
        modal = view.victory_modal
        app.update()
        modal.again_button.invoke()
        assert calls == [("hard", None)]  # 同模式（hard）、非每日（date=None）
        assert modal.winfo_exists() == 0

    def test_每日挑戰再來一局帶同日期(self, app):
        from sudoku.ui.board import BoardView

        calls: list[tuple] = []
        s = GameSession.daily("2026-11-25")
        view = BoardView(app, s, on_home=lambda: None, on_play_again=lambda mode, date: calls.append((mode, date)))
        view.pack(expand=True, fill="both")
        app.update()
        _填完一局(view)
        modal = view.victory_modal
        app.update()
        modal.again_button.invoke()
        assert calls == [("daily", "2026-11-25")]


class Test主選單接線:
    def test_再來一局開同難度新局並銷毀舊畫面(self, app):
        from sudoku.ui.board import BoardView
        from sudoku.ui.main_menu import MainMenu

        menu = MainMenu(app)
        menu.pack(expand=True, fill="both")
        app.update()
        menu._start_difficulty("easy")
        view = menu._current
        assert isinstance(view, BoardView)
        old_session = view.session
        _填完一局(view)
        modal = view.victory_modal
        assert modal is not None
        app.update()
        modal.again_button.invoke()
        new_view = menu._current
        assert isinstance(new_view, BoardView)
        assert new_view is not view
        assert new_view.session is not old_session
        assert new_view.session.mode == "easy"  # 同難度新題
        assert view.winfo_exists() == 0  # 舊棋盤畫面已銷毀
        assert modal.winfo_exists() == 0  # 舊 modal 已關

    def test_返回首頁切回主選單(self, app):
        from sudoku.ui.main_menu import MainMenu

        menu = MainMenu(app)
        menu.pack(expand=True, fill="both")
        app.update()
        menu._start_difficulty("easy")
        view = menu._current
        _填完一局(view)
        modal = view.victory_modal
        app.update()
        modal.home_button.invoke()
        assert view.winfo_exists() == 0  # 棋盤畫面銷毀
        assert modal.winfo_exists() == 0
        assert menu._current is None  # 主選單已重建（_back_to_menu）
