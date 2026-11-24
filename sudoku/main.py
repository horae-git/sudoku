"""進入點：`uv run python -m sudoku.main`（或 `uv run sudoku`）啟動數獨 app。"""

import customtkinter as ctk

from sudoku.ui.main_menu import MainMenu

視窗寬 = 960
視窗高 = 760


def main() -> None:
    """建立主視窗並顯示空白主選單後進入事件迴圈。"""
    ctk.set_appearance_mode("system")
    ctk.set_default_color_theme("blue")

    app = ctk.CTk()
    app.title("數獨")
    app.geometry(f"{視窗寬}x{視窗高}")

    主選單 = MainMenu(app)
    主選單.pack(expand=True, fill="both")

    app.mainloop()


if __name__ == "__main__":
    main()
