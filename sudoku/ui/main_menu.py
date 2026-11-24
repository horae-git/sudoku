"""主選單畫面。

標題「數獨 Sudoku」+ 圓角按鈕：每日挑戰、簡單 / 中等 / 困難 / 專家、
遊玩紀錄、生涯總覽，以及置於顯眼處的「🎨 背景主題」按鈕。

點難度或每日挑戰會以 ``GameSession`` 開新局並切換到棋盤畫面（board.BoardView，
由 GameSession 驅動、GameFlow 自動存檔）；若有進行中存檔，主選單另顯示
「▶ 繼續遊戲」按鈕（``flow.continuable_saves`` / ``continue_session`` 續玩）。
遊玩紀錄（history_view.HistoryView）/ 生涯總覽（stats_view.StatsView）/ 背景主題
（theme_picker.ThemePickerView）為票券 09 的畫面；切換主題後整份主選單會依新色票重建。
"""

from datetime import date

import customtkinter as ctk

from sudoku import storage
from sudoku.session import GameSession
from sudoku.themes import get_current_theme
from sudoku.ui.board import BoardView, mode_display_label
from sudoku.ui.flow import continuable_saves, continue_session
from sudoku.ui.history_view import HistoryView
from sudoku.ui.stats_view import StatsView
from sudoku.ui.theme_picker import ThemePickerView

_難度按鈕 = (
    ("簡單", "easy"),
    ("中等", "medium"),
    ("困難", "hard"),
    ("專家", "expert"),
)


class MainMenu(ctk.CTkFrame):
    """主選單：置中標題 + 各入口圓角按鈕；切換畫面時銷毀舊 frame。"""

    def __init__(self, master: ctk.CTk, **kwargs) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)
        self.master_app = master
        self.theme = get_current_theme()  # 目前主題（storage 持久化）
        self._current: ctk.CTkFrame | None = None

        title = ctk.CTkLabel(
            self, text="數獨 Sudoku", font=ctk.CTkFont(size=44, weight="bold"),
            text_color=self.theme.標題文字,
        )
        title.place(relx=0.5, rely=0.16, anchor="center")

        # 🎨 背景主題按鈕放在右上角顯眼處
        theme_btn = ctk.CTkButton(
            self, text="🎨 背景主題", width=130, height=42, corner_radius=21,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color=self.theme.按鈕, hover_color=self.theme.按鈕懸停,
            text_color=self.theme.按鈕文字,
            command=self._open_theme,
        )
        theme_btn.place(relx=0.97, rely=0.04, anchor="ne")

        # 按鈕容器（置中）
        box = ctk.CTkFrame(self, fg_color="transparent")
        box.place(relx=0.5, rely=0.54, anchor="center")

        def 按鈕(text: str, command) -> ctk.CTkButton:
            return ctk.CTkButton(
                box, text=text, width=300, height=52, corner_radius=26,
                font=ctk.CTkFont(size=18, weight="bold"),
                fg_color=self.theme.按鈕, hover_color=self.theme.按鈕懸停,
                text_color=self.theme.按鈕文字,
                command=command,
            )

        # 有進行中存檔時，最上方顯示「▶ 繼續遊戲」（續玩最新一份存檔）
        self._continue_buttons: list[ctk.CTkButton] = []
        for mode, _saved_at in continuable_saves():
            btn = 按鈕(f"▶ 繼續遊戲（{mode_display_label(mode, _存檔日期(mode))}）", lambda m=mode: self._continue(m))
            btn.pack(pady=8)
            self._continue_buttons.append(btn)

        按鈕("📅 每日挑戰", self._start_daily).pack(pady=8)
        for 名稱, mode_str in _難度按鈕:
            按鈕(名稱, lambda m=mode_str: self._start_difficulty(m)).pack(pady=8)
        按鈕("🗂️ 遊玩紀錄", self._open_history).pack(pady=8)
        按鈕("📊 生涯總覽", self._open_stats).pack(pady=8)

    # ---------- 畫面切換 ----------

    def _show(self, frame: ctk.CTkFrame) -> None:
        """切換主畫面：銷毀舊 frame 並顯示新 frame。"""
        if self._current is not None:
            self._current.destroy()
        self._current = frame
        frame.pack(expand=True, fill="both")

    def _back_to_menu(self) -> None:
        """由子畫面返回主選單（隱藏自己、重建一份新的主選單，會重新掃描續玩存檔）。"""
        if self._current is not None:
            self._current.destroy()
            self._current = None
        self.pack_forget()
        new_menu = MainMenu(self.master_app)
        new_menu.pack(expand=True, fill="both")

    # ---------- 開新局 / 繼續遊戲 ----------

    def _open_board(self, session: GameSession) -> None:
        """依 session 切換到棋盤畫面（標籤：每日挑戰顯示「📅 本日題目（日期）」）。

        勝利 modal 的「🔁 再來一局」會以 ``on_play_again`` 交回此處開同模式新局。
        """
        label = mode_display_label(session.mode, session.date)
        view = BoardView(
            self.master_app, session, mode_label=label,
            on_home=self._back_to_menu, on_play_again=self._play_again,
        )
        self._show(view)

    def _start_difficulty(self, mode_str: str) -> None:
        self._open_board(GameSession.new_game(mode_str))

    def _start_daily(self) -> None:
        self._open_board(GameSession.daily(date.today()))

    def _play_again(self, mode: str, date_str: str | None) -> None:
        """勝利 modal 按「🔁 再來一局」：同模式（同難度 / 每日挑戰同日期）開新局。"""
        session = GameSession.daily(date_str) if mode == "daily" and date_str else GameSession.new_game(mode)
        self._open_board(session)

    def _continue(self, mode: str) -> None:
        """由存檔續玩；讀不到（已結束 / 損毀）時重建主選單。"""
        session = continue_session(mode)
        if session is None:
            self._back_to_menu()
            return
        self._open_board(session)

    # ---------- 功能畫面（票券 09） ----------

    def _open_history(self) -> None:
        self._show(HistoryView(self.master_app, on_home=self._back_to_menu))

    def _open_stats(self) -> None:
        self._show(StatsView(self.master_app, on_home=self._back_to_menu))

    def _open_theme(self) -> None:
        # on_theme_changed：切換主題後整份主選單依新色票重建（即時套用到全 app）
        self._show(
            ThemePickerView(
                self.master_app,
                on_home=self._back_to_menu,
                on_theme_changed=self._on_theme_changed,
            )
        )

    def _on_theme_changed(self, name: str) -> None:
        """主題切換後：更新根視窗背景並重建主選單（顏色即時套用）。"""
        self.master_app.configure(bg=get_current_theme().背景)
        self._back_to_menu()


def _存檔日期(mode: str) -> str | None:
    """續玩按鈕標籤用：每日挑戰存檔的日期（非每日挑戰為 None）。"""
    記錄 = storage.load_game(mode)
    if 記錄 is None:
        return None
    state = 記錄.get("state")
    if isinstance(state, dict):
        return state.get("date")
    return None
