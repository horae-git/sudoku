"""主選單畫面。

標題「數獨 Sudoku」+ 圓角按鈕：每日挑戰、簡單 / 中等 / 困難 / 專家、
遊玩紀錄、生涯總覽，以及置於顯眼處的「🎨 背景主題」按鈕。

點難度或每日挑戰會以 generator 生成題目並切換到棋盤畫面（board.BoardView）；
遊玩紀錄 / 生涯總覽 / 主題為後續票券的框架畫面，可點且各有對應頁面。
"""

from datetime import date

import customtkinter as ctk

from sudoku.generator import Difficulty, daily_challenge, generate_puzzle
from sudoku.themes import get_theme, theme_names
from sudoku.ui.board import BoardView, difficulty_mode_label
from sudoku.ui.board_state import unique_solution

_難度按鈕 = (
    ("簡單", Difficulty.EASY),
    ("中等", Difficulty.MEDIUM),
    ("困難", Difficulty.HARD),
    ("專家", Difficulty.EXPERT),
)


class MainMenu(ctk.CTkFrame):
    """主選單：置中標題 + 各入口圓角按鈕；切換畫面時銷毀舊 frame。"""

    def __init__(self, master: ctk.CTk, **kwargs) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)
        self.master_app = master
        self.theme = get_theme()
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
        box.place(relx=0.5, rely=0.52, anchor="center")

        def 按鈕(text: str, command) -> ctk.CTkButton:
            return ctk.CTkButton(
                box, text=text, width=300, height=52, corner_radius=26,
                font=ctk.CTkFont(size=18, weight="bold"),
                fg_color=self.theme.按鈕, hover_color=self.theme.按鈕懸停,
                text_color=self.theme.按鈕文字,
                command=command,
            )

        按鈕("📅 每日挑戰", self._start_daily).pack(pady=8)
        for 名稱, diff in _難度按鈕:
            按鈕(名稱, lambda d=diff: self._start_difficulty(d)).pack(pady=8)
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
        """由子畫面返回主選單（隱藏自己、重建一份新的主選單）。"""
        if self._current is not None:
            self._current.destroy()
            self._current = None
        self.pack_forget()
        new_menu = MainMenu(self.master_app)
        new_menu.pack(expand=True, fill="both")

    # ---------- 開新局 ----------

    def _start_game(self, puzzle, mode_label: str) -> None:
        """求出唯一解並切換到棋盤畫面（本日題目標籤 mode_label）。"""
        solution = unique_solution(puzzle)  # generator 保證唯一解
        view = BoardView(self.master_app, puzzle, solution, mode_label=mode_label, on_home=self._back_to_menu)
        self._show(view)

    def _start_difficulty(self, difficulty: Difficulty) -> None:
        puzzle = generate_puzzle(difficulty)
        self._start_game(puzzle, mode_label=difficulty_mode_label(difficulty))

    def _start_daily(self) -> None:
        today = date.today().isoformat()
        puzzle = daily_challenge(today)
        self._start_game(puzzle, mode_label=f"📅 本日題目（{today}）")

    # ---------- 框架畫面（後續票券填充） ----------

    def _placeholder(self, 標題: str) -> None:
        frame = ctk.CTkFrame(self.master_app, fg_color="transparent")
        label = ctk.CTkLabel(
            frame, text=f"{標題}\n（後續票券實作）", font=ctk.CTkFont(size=24, weight="bold"),
            text_color=self.theme.標題文字,
        )
        label.place(relx=0.5, rely=0.4, anchor="center")
        btn = ctk.CTkButton(
            frame, text="🏠 返回首頁", width=180, height=44, corner_radius=22,
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color=self.theme.按鈕, hover_color=self.theme.按鈕懸停,
            text_color=self.theme.按鈕文字,
            command=self._back_to_menu,
        )
        btn.place(relx=0.5, rely=0.6, anchor="center")
        self._show(frame)

    def _open_history(self) -> None:
        self._placeholder("🗂️ 遊玩紀錄")

    def _open_stats(self) -> None:
        self._placeholder("📊 生涯總覽")

    def _open_theme(self) -> None:
        self._placeholder(f"🎨 背景主題（目前：{', '.join(theme_names())}）")
