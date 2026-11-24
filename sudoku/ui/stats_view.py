"""生涯總覽畫面的純邏輯（票券 09）。

不依賴 customtkinter，headless 可測：

- ``DIFFICULTY_ORDER`` / ``DIFFICULTY_LABELS``：各難度顯示順序與中文名；
- ``format_best(sec)``：秒數 → mm:ss，None →「—」；
- ``stats_rows(stats)``：把 ``storage.get_stats()`` 轉成畫面列資料
  （各難度最佳時間、零錯誤完成次數）；
- ``daily_summary(stats)``：每日挑戰連續天數與累計完成天數。
"""

from __future__ import annotations

import customtkinter as ctk

from sudoku.themes import get_current_theme
from sudoku.ui.board import format_mmss

# 難度顯示順序與中文名
DIFFICULTY_ORDER: tuple[str, ...] = ("easy", "medium", "hard", "expert")
DIFFICULTY_LABELS: dict[str, str] = {
    "easy": "簡單",
    "medium": "中等",
    "hard": "困難",
    "expert": "專家",
}


def format_best(sec: int | None) -> str:
    """最佳時間秒數 → mm:ss；無紀錄（None）→「—」。"""
    if sec is None:
        return "—"
    return format_mmss(int(sec))


def stats_rows(stats: dict) -> list[dict]:
    """把 stats 轉成畫面列：[{label, best, perfect}, ...]，依 DIFFICULTY_ORDER 排序。"""
    best_time = stats.get("best_time") or {}
    perfect = stats.get("perfect_clears") or {}
    return [
        {
            "difficulty": d,
            "label": DIFFICULTY_LABELS[d],
            "best": format_best(best_time.get(d)),
            "perfect": int(perfect.get(d) or 0),
        }
        for d in DIFFICULTY_ORDER
    ]


def daily_summary(stats: dict) -> dict:
    """每日挑戰摘要：{"streak": 連續天數, "wins": 累計完成天數}。"""
    return {
        "streak": int(stats.get("daily_streak") or 0),
        "wins": len(stats.get("daily_wins") or []),
    }


class StatsView(ctk.CTkFrame):
    """生涯總覽畫面：各難度最佳時間 / 零錯誤完成次數 + 每日挑戰摘要 + 返回首頁。"""

    def __init__(self, master: ctk.CTk, on_home=None, **kwargs) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)
        self._on_home = on_home
        self.theme = get_current_theme()

        ctk.CTkLabel(
            self, text="📊 生涯總覽", font=ctk.CTkFont(size=32, weight="bold"),
            text_color=self.theme.標題文字,
        ).place(relx=0.5, rely=0.12, anchor="center")

        panel = ctk.CTkFrame(self, fg_color=self.theme.面板, corner_radius=self.theme.圓角, width=640, height=340)
        panel.place(relx=0.5, rely=0.42, anchor="center")
        panel.pack_propagate(False)

        from sudoku import storage

        stats = storage.get_stats()
        ctk.CTkLabel(
            panel, text="各難度最佳時間 / 零錯誤完成", font=ctk.CTkFont(size=16, weight="bold"),
            text_color=self.theme.標題文字,
        ).pack(pady=(16, 4))
        for row in stats_rows(stats):
            行 = ctk.CTkFrame(panel, fg_color="transparent")
            行.pack(fill="x", padx=24, pady=3)
            ctk.CTkLabel(行, text=row["label"], width=60, anchor="w",
                         font=ctk.CTkFont(size=16), text_color=self.theme.文字).pack(side="left")
            ctk.CTkLabel(行, text="最佳", width=40, anchor="w",
                         font=ctk.CTkFont(size=16), text_color=self.theme.文字).pack(side="left")
            ctk.CTkLabel(行, text=row["best"], width=60, anchor="w",
                         font=ctk.CTkFont(size=16, weight="bold"),
                         text_color=self.theme.標題文字).pack(side="left")
            ctk.CTkLabel(行, text="零錯誤完成", width=90, anchor="w",
                         font=ctk.CTkFont(size=16), text_color=self.theme.文字).pack(side="left")
            ctk.CTkLabel(行, text=str(row["perfect"]), width=30, anchor="w",
                         font=ctk.CTkFont(size=16, weight="bold"),
                         text_color=self.theme.文字提示).pack(side="left")
            ctk.CTkLabel(行, text="次", font=ctk.CTkFont(size=16),
                         text_color=self.theme.文字).pack(side="left")
        摘要 = daily_summary(stats)
        ctk.CTkLabel(
            panel, text=f"連續完成 {摘要['streak']} 天",
            font=ctk.CTkFont(size=16, weight="bold"), text_color=self.theme.文字提示,
        ).pack(pady=(14, 0))
        ctk.CTkLabel(
            panel, text=f"累計完成 {摘要['wins']} 天",
            font=ctk.CTkFont(size=16, weight="bold"), text_color=self.theme.文字提示,
        ).pack(pady=(0, 8))

        ctk.CTkButton(
            self, text="🏠 返回首頁", width=180, height=44, corner_radius=self.theme.圓角 + 10,
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color=self.theme.按鈕, hover_color=self.theme.按鈕懸停,
            text_color=self.theme.按鈕文字,
            command=self._go_home,
        ).place(relx=0.5, rely=0.85, anchor="center")

    def _go_home(self) -> None:
        if self._on_home is not None:
            self._on_home()
