"""生涯總覽畫面純邏輯（sudoku.ui.stats_view）的單元測試。

測試接縫：stats_view 中不依賴視窗的純函式——

- ``DIFFICULTY_ORDER`` / ``DIFFICULTY_LABELS``：各難度顯示順序與中文名；
- ``stats_rows(stats)``：把 storage.get_stats() 轉成畫面列資料
  （各難度最佳時間，無紀錄為「—」；各難度零錯誤完成次數）；
- ``daily_summary(stats)``：每日挑戰連續天數與累計完成天數；
- ``format_best(sec)``：秒數 → mm:ss，None →「—」。

畫面建構驗證見 test_ui_construct.py。
"""

import pytest

from sudoku import storage
from sudoku.ui.stats_view import (
    DIFFICULTY_LABELS,
    DIFFICULTY_ORDER,
    daily_summary,
    format_best,
    stats_rows,
)


@pytest.fixture(autouse=True)
def 隔離資料目錄(monkeypatch, tmp_path):
    資料目錄 = tmp_path / "user-data"
    monkeypatch.setenv("SUDOKU_DATA_DIR", str(資料目錄))
    return 資料目錄


class Test難度顯示:
    def test_難度順序與中文名(self):
        assert DIFFICULTY_ORDER == ("easy", "medium", "hard", "expert")
        assert DIFFICULTY_LABELS == {
            "easy": "簡單",
            "medium": "中等",
            "hard": "困難",
            "expert": "專家",
        }


class Test時間格式化:
    def test_秒數轉mmss(self):
        assert format_best(0) == "00:00"
        assert format_best(65) == "01:05"
        assert format_best(3600) == "60:00"

    def test_無紀錄顯示破折號(self):
        assert format_best(None) == "—"


class Test統計列:
    """stats_rows：各難度最佳時間（無紀錄「—」）與零錯誤完成次數，順序固定。"""

    def test_空統計(self):
        列 = stats_rows(storage.get_stats())
        assert [r["label"] for r in 列] == ["簡單", "中等", "困難", "專家"]
        assert all(r["best"] == "—" for r in 列)
        assert all(r["perfect"] == 0 for r in 列)

    def test_有紀錄時正確對應(self):
        storage.add_history({"mode": "easy", "difficulty": "easy", "result": "completed",
                             "duration_sec": 95, "mistakes": 0})
        storage.add_history({"mode": "hard", "difficulty": "hard", "result": "completed",
                             "duration_sec": 600, "mistakes": 3})
        storage.add_history({"mode": "hard", "difficulty": "hard", "result": "completed",
                             "duration_sec": 500, "mistakes": 0})
        列 = stats_rows(storage.get_stats())
        by_label = {r["label"]: r for r in 列}
        assert by_label["簡單"]["best"] == "01:35"  # 95 秒
        assert by_label["簡單"]["perfect"] == 1
        assert by_label["中等"]["best"] == "—"
        assert by_label["困難"]["best"] == "08:20"  # 500 秒（更快的覆蓋 600）
        assert by_label["困難"]["perfect"] == 1  # 只有零錯誤那局計
        assert by_label["專家"]["best"] == "—"

    def test_放棄不進統計(self):
        storage.add_history({"mode": "easy", "difficulty": "easy", "result": "abandoned",
                             "duration_sec": 10, "mistakes": 0})
        列 = stats_rows(storage.get_stats())
        assert all(r["best"] == "—" and r["perfect"] == 0 for r in 列)


class Test每日挑戰摘要:
    """daily_summary：連續天數（daily_streak）與累計完成天數（len(daily_wins)）。"""

    def test_初始為零(self):
        摘要 = daily_summary(storage.get_stats())
        assert 摘要 == {"streak": 0, "wins": 0}

    def test_連續三天(self):
        storage.record_daily_win("2026-11-22")
        storage.record_daily_win("2026-11-23")
        storage.record_daily_win("2026-11-24")
        摘要 = daily_summary(storage.get_stats())
        assert 摘要 == {"streak": 3, "wins": 3}

    def test_累計完成天數可與連勝不同(self):
        storage.record_daily_win("2026-11-20")
        storage.record_daily_win("2026-11-24")  # 中間斷 → 連勝 1，但累計 2 天
        摘要 = daily_summary(storage.get_stats())
        assert 摘要 == {"streak": 1, "wins": 2}
