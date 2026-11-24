"""主題選擇器（sudoku.ui.theme_picker）的測試。

測試接縫：

- 純邏輯 ``theme_cards()``：三套主題的預覽卡資料（名稱、主題名、背景/按鈕/宮粗線預覽色）；
- UI 建構驗證：三個畫面（主題選擇器 / 遊玩紀錄 / 生涯總覽）在 headless 下可建構、
  資料正確顯示（塞假資料）；customtkinter 在無顯示器環境下 import 與建構 widget 皆可行，
  只有 mainloop 需要顯示器。
"""

import pytest

from sudoku import storage
from sudoku.themes import (
    DARK,
    LIGHT,
    MACARON,
    THEME_LABELS,
    THEME_ORDER,
    get_current_theme_name,
    set_current_theme,
)
from sudoku.ui.theme_picker import ThemePickerView, theme_cards


@pytest.fixture(autouse=True)
def 隔離資料目錄(monkeypatch, tmp_path):
    資料目錄 = tmp_path / "user-data"
    monkeypatch.setenv("SUDOKU_DATA_DIR", str(資料目錄))
    return 資料目錄


class Test主題卡:
    """theme_cards：依 THEME_ORDER 列出三張預覽卡，含預覽色塊顏色。"""

    def test_三張卡順序與名稱(self):
        卡 = theme_cards()
        assert [c["name"] for c in 卡] == list(THEME_ORDER)
        assert [c["label"] for c in 卡] == [THEME_LABELS[n] for n in THEME_ORDER]

    def test_每張卡含預覽色(self):
        卡 = {c["name"]: c for c in theme_cards()}
        assert 卡["light"]["背景"] == LIGHT.背景
        assert 卡["light"]["按鈕"] == LIGHT.按鈕
        assert 卡["dark"]["背景"] == DARK.背景
        assert 卡["dark"]["宮粗線"] == DARK.宮粗線
        assert 卡["macaron"]["背景"] == MACARON.背景


class Test主題切換持久化:
    """點選主題即時套用並持久化（重開 app 記得）。"""

    def test_切換到深色並記得(self):
        assert get_current_theme_name() == "light"
        set_current_theme("dark")
        assert get_current_theme_name() == "dark"
        assert storage.get_setting("theme") == "dark"

    def test_切到馬卡龍(self):
        set_current_theme("macaron")
        assert get_current_theme_name() == "macaron"


class Test畫面建構:
    """UI 建構驗證（headless）：三個新畫面可建構且資料正確顯示。"""

    @pytest.fixture()
    def app(self):
        import customtkinter as ctk

        app = ctk.CTk()
        app.geometry("960x760")
        yield app
        app.destroy()

    @staticmethod
    def _all_texts(widget) -> list[str]:
        """遞迴收集所有子 widget 上可讀到的文字（不支援 text 的 widget 跳過）。"""
        result: list[str] = []
        for child in widget.winfo_children():
            try:
                text = child.cget("text")
            except Exception:
                text = None
            if isinstance(text, str):
                result.append(text)
            result.extend(Test畫面建構._all_texts(child))
        return result

    def test_主題選擇器建構且列出三套(self, app):
        view = ThemePickerView(app, on_home=lambda: None)
        view.pack(expand=True, fill="both")
        全文字 = "\n".join(self._all_texts(view))
        assert "🎨 背景主題" in 全文字
        assert "淺色" in 全文字 and "深色" in 全文字 and "馬卡龍" in 全文字
        assert "返回首頁" in 全文字

    def test_歷史畫面塞假資料後正確顯示(self, app):
        from sudoku.ui.history_view import HistoryView, format_history_row

        storage.add_history({
            "mode": "easy", "difficulty": "easy", "result": "completed",
            "played_at": "2026-11-24T10:30:00+08:00", "duration_sec": 125, "mistakes": 2,
        })
        storage.add_history({
            "mode": "daily", "difficulty": "medium", "result": "abandoned",
            "played_at": "2026-11-25T09:00:00+08:00", "duration_sec": 30, "mistakes": 1,
        })
        view = HistoryView(app, on_home=lambda: None)
        view.pack(expand=True, fill="both")
        文字們 = self._all_texts(view)
        joined = "\n".join(文字們)
        assert "遊玩紀錄" in joined
        # 新→舊：每日挑戰（25 日）在簡單（24 日）之前
        第一列 = format_history_row(storage.list_history()[0])
        assert "每日挑戰" in 第一列 and "放棄" in 第一列
        assert any("每日挑戰" in t for t in 文字們)
        assert any("簡單" in t and "完成" in t for t in 文字們)

    def test_生涯總覽畫面塞假資料後正確顯示(self, app):
        from sudoku.ui.stats_view import StatsView

        storage.add_history({
            "mode": "hard", "difficulty": "hard", "result": "completed",
            "duration_sec": 500, "mistakes": 0,
        })
        storage.record_daily_win("2026-11-24")
        storage.record_daily_win("2026-11-25")
        view = StatsView(app, on_home=lambda: None)
        view.pack(expand=True, fill="both")
        文字們 = self._all_texts(view)
        joined = "\n".join(文字們)
        assert "生涯總覽" in joined
        assert "困難" in joined and "08:20" in joined and "1" in 文字們  # 最佳時間 + 零錯誤次數
        assert "連續完成 2 天" in joined and "累計完成 2 天" in joined
        # 無紀錄的難度顯示「—」
        assert "—" in 文字們


class Test主選單接到三個新畫面:
    """主選單（main_menu.MainMenu）的三個框架按鈕要接到票券 09 的畫面並可建構。"""

    @pytest.fixture()
    def app(self, monkeypatch, tmp_path):
        import customtkinter as ctk

        monkeypatch.setenv("SUDOKU_DATA_DIR", str(tmp_path / "user-data"))
        app = ctk.CTk()
        app.geometry("960x760")
        yield app
        app.destroy()

    def test_主選單建構且有三個入口按鈕(self, app):
        from sudoku.ui.main_menu import MainMenu

        menu = MainMenu(app)
        menu.pack(expand=True, fill="both")
        texts = Test畫面建構._all_texts(menu)
        joined = "\n".join(texts)
        assert "🎨 背景主題" in joined  # 主題按鈕在首頁顯眼處
        assert "🗂️ 遊玩紀錄" in joined and "📊 生涯總覽" in joined
        assert "每日挑戰" in joined

    def test_點遊玩紀錄切到HistoryView(self, app):
        from sudoku.ui.main_menu import MainMenu

        menu = MainMenu(app)
        menu.pack(expand=True, fill="both")
        menu._open_history()
        from sudoku.ui.history_view import HistoryView

        assert isinstance(menu._current, HistoryView)

    def test_點生涯總覽切到StatsView(self, app):
        from sudoku.ui.main_menu import MainMenu

        menu = MainMenu(app)
        menu.pack(expand=True, fill="both")
        menu._open_stats()
        from sudoku.ui.stats_view import StatsView

        assert isinstance(menu._current, StatsView)

    def test_點背景主題切到ThemePickerView(self, app):
        from sudoku.ui.main_menu import MainMenu

        menu = MainMenu(app)
        menu.pack(expand=True, fill="both")
        menu._open_theme()
        assert isinstance(menu._current, ThemePickerView)

    def test_切換主題後主選單依新色票重建且持久化(self, app):
        from sudoku.ui.main_menu import MainMenu

        menu = MainMenu(app)
        menu.pack(expand=True, fill="both")
        menu._open_theme()
        picker = menu._current
        picker._pick("dark")  # 模擬點選深色卡
        # 持久化 + 主選單已重建為新 MainMenu（非 picker）
        assert get_current_theme_name() == "dark"
        assert isinstance(menu._current, type(None)) or menu._current is None or isinstance(menu._current, MainMenu)
