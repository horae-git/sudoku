"""遊玩紀錄畫面的純邏輯（票券 09）。

不依賴 customtkinter，headless 可測：

- ``DIFFICULTY_FILTERS`` / ``RESULT_FILTERS``：下拉篩選選項（含「全部」）；
- ``difficulty_filter_value`` / ``result_filter_value``：把顯示名對應到內部值
  （「全部」→ None；「每日挑戰」→ mode 篩 daily）；
- ``filter_history(difficulty_label, result_label)``：依篩選委給 ``storage.list_history``
  （新→舊）；難度用 difficulty 篩、每日挑戰用 mode 篩；
- ``format_history_row(entry)``：一列顯示文字（日期時間、難度/模式、結果、用時 mm:ss、錯誤數）。
"""

from __future__ import annotations

import customtkinter as ctk

from sudoku import storage
from sudoku.themes import get_current_theme
from sudoku.ui.board import format_mmss

# 難度篩選下拉選項（顯示名）；「每日挑戰」對 mode=daily 篩
DIFFICULTY_FILTERS: list[str] = ["全部", "簡單", "中等", "困難", "專家", "每日挑戰"]

# 結果篩選下拉選項（顯示名）
RESULT_FILTERS: list[str] = ["全部", "完成", "放棄"]

_DIFFICULTY_VALUES: dict[str, str] = {
    "簡單": "easy",
    "中等": "medium",
    "困難": "hard",
    "專家": "expert",
    "每日挑戰": "daily",
}

_RESULT_VALUES: dict[str, str] = {"完成": "completed", "放棄": "abandoned"}

_DIFFICULTY_LABELS: dict[str, str] = {v: k for k, v in _DIFFICULTY_VALUES.items() if v != "daily"}
_RESULT_LABELS: dict[str, str] = {v: k for k, v in _RESULT_VALUES.items()}


def difficulty_filter_value(label: str) -> str | None:
    """難度篩選顯示名 → 內部值；「全部」→ None；未知名稱拋 ValueError。"""
    if label == "全部":
        return None
    try:
        return _DIFFICULTY_VALUES[label]
    except KeyError:
        raise ValueError(f"未知難度篩選：{label!r}（合法：{', '.join(DIFFICULTY_FILTERS)}）") from None


def result_filter_value(label: str) -> str | None:
    """結果篩選顯示名 → 內部值；「全部」→ None；未知名稱拋 ValueError。"""
    if label == "全部":
        return None
    try:
        return _RESULT_VALUES[label]
    except KeyError:
        raise ValueError(f"未知結果篩選：{label!r}（合法：{', '.join(RESULT_FILTERS)}）") from None


def filter_history(difficulty_label: str, result_label: str) -> list[dict]:
    """依難度與結果篩選遊玩紀錄（新→舊）。

    難度篩選用 ``difficulty`` 欄位；「每日挑戰」改篩 ``mode == "daily"``
    （每日挑戰的 difficulty 記為 medium）。兩個都是「全部」時回傳全部。
    """
    result = result_filter_value(result_label)
    diff = difficulty_filter_value(difficulty_label)
    if diff == "daily":
        return [e for e in storage.list_history(result=result) if e.get("mode") == "daily"]
    return storage.list_history(difficulty=diff, result=result)


def format_history_row(entry: dict) -> str:
    """一列歷史顯示文字：``日期時間 難度/模式 結果 用時 錯誤數``。

    ``played_at`` 缺漏或格式怪時只顯示空字串日期部分；每日挑戰局顯示「每日挑戰」。
    """
    played_at = str(entry.get("played_at") or "")
    時間 = played_at[:16].replace("T", " ") if played_at else ""
    if entry.get("mode") == "daily":
        模式 = "每日挑戰"
    else:
        模式 = _DIFFICULTY_LABELS.get(entry.get("difficulty", ""), entry.get("difficulty", ""))
    結果 = _RESULT_LABELS.get(entry.get("result", ""), entry.get("result", ""))
    用時 = format_mmss(int(entry.get("duration_sec") or 0))
    錯誤 = int(entry.get("mistakes") or 0)
    return f"{時間}　{模式}　{結果}　{用時}　錯誤 {錯誤}"


class HistoryView(ctk.CTkFrame):
    """遊玩紀錄畫面：難度 / 結果兩個下拉篩選 + 歷史清單（新→舊）+ 返回首頁。"""

    def __init__(self, master: ctk.CTk, on_home=None, **kwargs) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)
        self._on_home = on_home
        self.theme = get_current_theme()

        ctk.CTkLabel(
            self, text="🗂️ 遊玩紀錄", font=ctk.CTkFont(size=32, weight="bold"),
            text_color=self.theme.標題文字,
        ).place(relx=0.5, rely=0.12, anchor="center")

        # 篩選列（分段按鈕；OptionMenu 在無顯示器環境會崩潰，故用 SegmentedButton）
        filters = ctk.CTkFrame(self, fg_color="transparent")
        filters.place(relx=0.5, rely=0.22, anchor="center")
        self._diff_seg = ctk.CTkSegmentedButton(
            filters, values=DIFFICULTY_FILTERS, command=lambda _: self._refresh(),
        )
        self._diff_seg.set(DIFFICULTY_FILTERS[0])
        self._diff_seg.pack(side="left", padx=6)
        self._result_seg = ctk.CTkSegmentedButton(
            filters, values=RESULT_FILTERS, command=lambda _: self._refresh(),
        )
        self._result_seg.set(RESULT_FILTERS[0])
        self._result_seg.pack(side="left", padx=6)

        self._list_frame = ctk.CTkFrame(self, fg_color=self.theme.面板, corner_radius=self.theme.圓角, width=760, height=420)
        self._list_frame.place(relx=0.5, rely=0.55, anchor="center")
        self._list_frame.pack_propagate(False)
        self._refresh()

        ctk.CTkButton(
            self, text="🏠 返回首頁", width=180, height=44, corner_radius=self.theme.圓角 + 10,
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color=self.theme.按鈕, hover_color=self.theme.按鈕懸停,
            text_color=self.theme.按鈕文字,
            command=self._go_home,
        ).place(relx=0.5, rely=0.9, anchor="center")

    def _refresh(self) -> None:
        """依目前篩選重繪清單（新→舊）。"""
        for w in self._list_frame.winfo_children():
            w.destroy()
        rows = filter_history(self._diff_seg.get(), self._result_seg.get())
        if not rows:
            ctk.CTkLabel(
                self._list_frame, text="（尚無紀錄）", font=ctk.CTkFont(size=16),
                text_color=self.theme.文字,
            ).pack(pady=20)
            return
        for entry in rows:
            ctk.CTkLabel(
                self._list_frame, text=format_history_row(entry),
                font=ctk.CTkFont(size=15), text_color=self.theme.文字, anchor="w",
            ).pack(fill="x", padx=16, pady=4)

    def _go_home(self) -> None:
        if self._on_home is not None:
            self._on_home()
