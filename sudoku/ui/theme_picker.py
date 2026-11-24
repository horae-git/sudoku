"""背景主題選擇器畫面（票券 09）。

``theme_cards()``：依 ``THEME_ORDER`` 列出三張預覽卡資料（名稱、中文名、
背景 / 按鈕 / 宮粗線預覽色），純邏輯可測。

``ThemePickerView``：標題「🎨 背景主題」+ 三張主題卡（點選即 ``set_current_theme``
即時套用並持久化，重開 app 記得）+「🏠 返回首頁」按鈕。
"""

from __future__ import annotations

import customtkinter as ctk

from sudoku.themes import (
    THEME_LABELS,
    THEME_ORDER,
    THEMES,
    get_current_theme,
    set_current_theme,
)


def theme_cards() -> list[dict]:
    """三張主題預覽卡（依 THEME_ORDER）：{name, label, 背景, 按鈕, 宮粗線, 宮粗線寬}。"""
    return [
        {
            "name": name,
            "label": THEME_LABELS[name],
            "背景": THEMES[name].背景,
            "按鈕": THEMES[name].按鈕,
            "宮粗線": THEMES[name].宮粗線,
            "宮粗線寬": THEMES[name].宮粗線寬,
        }
        for name in THEME_ORDER
    ]


class ThemePickerView(ctk.CTkFrame):
    """主題選擇器：三張預覽卡橫排，點卡即切換主題並持久化；底部返回首頁。"""

    def __init__(self, master: ctk.CTk, on_home=None, on_theme_changed=None, **kwargs) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)
        self._on_home = on_home
        self._on_theme_changed = on_theme_changed
        self.theme = get_current_theme()

        ctk.CTkLabel(
            self, text="🎨 背景主題", font=ctk.CTkFont(size=32, weight="bold"),
            text_color=self.theme.標題文字,
        ).place(relx=0.5, rely=0.14, anchor="center")

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.place(relx=0.5, rely=0.45, anchor="center")
        for card in theme_cards():
            self._card(row, card)

        ctk.CTkButton(
            self, text="🏠 返回首頁", width=180, height=44, corner_radius=self.theme.圓角 + 10,
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color=self.theme.按鈕, hover_color=self.theme.按鈕懸停,
            text_color=self.theme.按鈕文字,
            command=self._go_home,
        ).place(relx=0.5, rely=0.78, anchor="center")

    def _card(self, parent: ctk.CTkFrame, card: dict) -> None:
        """一張主題卡：色票預覽色塊 + 主題中文名；點選切換主題。"""
        t = THEMES[card["name"]]
        frame = ctk.CTkButton(
            parent, text="", width=180, height=200, corner_radius=t.圓角,
            fg_color=card["背景"], hover_color=card["背景"],
            command=lambda name=card["name"]: self._pick(name),
        )
        frame.grid(row=0, column=theme_cards().index(card), padx=12, pady=12)
        # 預覽色塊：背景色卡片上畫按鈕色與宮粗線色小色塊
        ctk.CTkFrame(frame, fg_color=card["按鈕"], width=120, height=14,
                     corner_radius=7).place(relx=0.5, rely=0.25, anchor="center")
        ctk.CTkFrame(frame, fg_color=card["宮粗線"], width=120, height=card["宮粗線寬"],
                     corner_radius=0).place(relx=0.5, rely=0.45, anchor="center")
        ctk.CTkLabel(
            frame, text=card["label"], font=ctk.CTkFont(size=20, weight="bold"),
            text_color=t.標題文字, fg_color="transparent",
        ).place(relx=0.5, rely=0.72, anchor="center")

    def _pick(self, name: str) -> None:
        """切換主題（即時套用並持久化到 storage settings），並通知主選單重建畫面。"""
        set_current_theme(name)
        if self._on_theme_changed is not None:
            self._on_theme_changed(name)
        elif self._on_home is not None:
            self._on_home()

    def _go_home(self) -> None:
        if self._on_home is not None:
            self._on_home()
