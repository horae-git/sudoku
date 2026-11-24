"""遊玩紀錄畫面純邏輯（sudoku.ui.history_view）的單元測試。

測試接縫：history_view 中不依賴視窗的純函式——

- ``DIFFICULTY_FILTERS`` / ``RESULT_FILTERS``：下拉篩選選項（含「全部」）；
- ``filter_history(entries, difficulty, result)``：把「全部」對應到 None、
  再委給 storage.list_history 的邏輯（新→舊）；
- ``format_history_row(entry)``：一列顯示文字（日期時間、難度/模式、結果、用時、錯誤數）。

import customtkinter 在 headless 下即可成功，只有建立視窗才需要顯示器；
畫面建構驗證見 test_ui_construct.py。
"""

import pytest

from sudoku import storage
from sudoku.ui.history_view import (
    DIFFICULTY_FILTERS,
    RESULT_FILTERS,
    difficulty_filter_value,
    filter_history,
    format_history_row,
    result_filter_value,
)


@pytest.fixture(autouse=True)
def 隔離資料目錄(monkeypatch, tmp_path):
    資料目錄 = tmp_path / "user-data"
    monkeypatch.setenv("SUDOKU_DATA_DIR", str(資料目錄))
    return 資料目錄


def _entry(**覆寫) -> dict:
    entry = {
        "mode": "easy",
        "difficulty": "easy",
        "result": "completed",
        "played_at": "2026-11-24T10:30:00+08:00",
        "duration_sec": 125,
        "mistakes": 2,
    }
    entry.update(覆寫)
    return entry


class Test篩選選項:
    """兩個下拉篩選的選項：難度（全部/簡單/中等/困難/專家/每日挑戰）、結果（全部/完成/放棄）。"""

    def test_難度篩選選項(self):
        assert DIFFICULTY_FILTERS == ["全部", "簡單", "中等", "困難", "專家", "每日挑戰"]
        assert difficulty_filter_value("全部") is None
        assert difficulty_filter_value("簡單") == "easy"
        assert difficulty_filter_value("中等") == "medium"
        assert difficulty_filter_value("困難") == "hard"
        assert difficulty_filter_value("專家") == "expert"
        assert difficulty_filter_value("每日挑戰") == "daily"  # mode 篩選

    def test_結果篩選選項(self):
        assert RESULT_FILTERS == ["全部", "完成", "放棄"]
        assert result_filter_value("全部") is None
        assert result_filter_value("完成") == "completed"
        assert result_filter_value("放棄") == "abandoned"


class Test篩選邏輯:
    """filter_history：委給 storage.list_history（難度用 difficulty 篩、每日挑戰用 mode 篩）。"""

    def _塞資料(self):
        storage.add_history(_entry(mode="easy", difficulty="easy", result="completed", duration_sec=100))
        storage.add_history(_entry(mode="hard", difficulty="hard", result="abandoned", duration_sec=50))
        storage.add_history(_entry(mode="daily", difficulty="medium", result="completed", duration_sec=88))

    def test_全部不篩回傳全部新在前(self):
        self._塞資料()
        結果 = filter_history("全部", "全部")
        assert [e["mode"] for e in 結果] == ["daily", "hard", "easy"]

    def test_依難度篩(self):
        self._塞資料()
        assert [e["mode"] for e in filter_history("困難", "全部")] == ["hard"]
        # 每日挑戰的 difficulty 記為 medium，但「每日挑戰」篩的是 mode=daily
        assert [e["mode"] for e in filter_history("每日挑戰", "全部")] == ["daily"]
        assert [e["mode"] for e in filter_history("中等", "全部")] == ["daily"]

    def test_依結果篩(self):
        self._塞資料()
        assert [e["mode"] for e in filter_history("全部", "完成")] == ["daily", "easy"]
        assert [e["mode"] for e in filter_history("全部", "放棄")] == ["hard"]

    def test_難度與結果聯合篩(self):
        self._塞資料()
        assert filter_history("簡單", "放棄") == []
        結果 = filter_history("每日挑戰", "完成")
        assert len(結果) == 1 and 結果[0]["duration_sec"] == 88

    def test_空歷史回傳空清單(self):
        assert filter_history("全部", "全部") == []


class Test列格式化:
    """format_history_row：日期時間、難度/模式、結果、用時 mm:ss、錯誤數。"""

    def test_完成局列文字(self):
        列 = format_history_row(_entry())
        assert "2026-11-24 10:30" in 列  # 日期時間（去掉時區）
        assert "簡單" in 列
        assert "完成" in 列
        assert "02:05" in 列  # 125 秒 → mm:ss
        assert "錯誤 2" in 列

    def test_每日挑戰局顯示每日挑戰(self):
        列 = format_history_row(_entry(mode="daily", difficulty="medium"))
        assert "每日挑戰" in 列

    def test_放棄局顯示放棄(self):
        列 = format_history_row(_entry(result="abandoned", duration_sec=0, mistakes=5))
        assert "放棄" in 列
        assert "錯誤 5" in 列

    def test_缺played_at時不炸(self):
        列 = format_history_row({k: v for k, v in _entry().items() if k != "played_at"})
        assert "完成" in 列
