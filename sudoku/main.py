"""進入點：`uv run python -m sudoku.main`（或 `uv run sudoku`）啟動數獨 app。"""

import customtkinter as ctk

from sudoku.themes import get_current_theme
from sudoku.ui.main_menu import MainMenu

視窗寬 = 960
視窗高 = 780


def apply_theme(app: ctk.CTk) -> None:
    """把目前主題（storage settings 持久化）套用到根視窗背景（票券 09）。"""
    app.configure(bg=get_current_theme().背景)


def build_app() -> ctk.CTk:
    """建立主視窗（固定 960×780、不可縮放，SPEC.md 第 64 行）並套上目前背景主題。"""
    ctk.set_appearance_mode("system")
    ctk.set_default_color_theme("blue")

    app = ctk.CTk()
    apply_theme(app)  # 重開 app 記得上次主題
    app.title("數獨")
    app.geometry(f"{視窗寬}x{視窗高}")
    app.resizable(False, False)  # 固定大小（SPEC：單一固定視窗 960×780）
    return app


def main() -> None:
    """建立主視窗（套上目前背景主題）並顯示主選單後進入事件迴圈。"""
    app = build_app()

    主選單 = MainMenu(app)
    主選單.pack(expand=True, fill="both")

    app.mainloop()


if __name__ == "__main__":
    main()
