"""主選單畫面（框架）。

票券 01 只建立空白主選單視窗框架，各功能入口按鈕由後續票券補上。
"""

import customtkinter as ctk


class MainMenu(ctk.CTkFrame):
    """主選單框架：置中顯示標題，預留按鈕區域。"""

    def __init__(self, master: ctk.CTk, **kwargs) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)
        title = ctk.CTkLabel(
            self, text="數獨", font=ctk.CTkFont(size=40, weight="bold")
        )
        title.place(relx=0.5, rely=0.35, anchor="center")
        subtitle = ctk.CTkLabel(
            self, text="主選單", font=ctk.CTkFont(size=20)
        )
        subtitle.place(relx=0.5, rely=0.45, anchor="center")
