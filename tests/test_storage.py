"""storage（存檔 / 遊玩紀錄 / 生涯統計）的單元測試。

測試接縫：sudoku.storage 的公開 API（SPEC.md Testing Decisions）。
每個測試都用 tmp_path + monkeypatch 隔離使用者資料目錄（SUDOKU_DATA_DIR），
不會碰到真實的使用者資料目錄。
"""

import json
import os
import sys
from pathlib import Path

import pytest

from sudoku import storage


@pytest.fixture(autouse=True)
def 隔離資料目錄(monkeypatch, tmp_path):
    """把資料目錄導向暫存資料夾，回傳該 Path 供斷言檔案用。"""
    資料目錄 = tmp_path / "user-data"
    monkeypatch.setenv("SUDOKU_DATA_DIR", str(資料目錄))
    return 資料目錄


def _state(**覆寫) -> dict:
    """一份進行中對局的 state_dict（純 dict / JSON 友善）。

    欄位 schema：puzzle / solution / board 為 81 字元字串（空格用 '0'），
    其餘為筆記、錯誤數、剩餘提示、已過秒數。
    """
    state = {
        "puzzle": "0" * 81,
        "solution": "123456789" * 9,
        "board": "0" * 81,
        "notes": [[] for _ in range(81)],
        "mistakes": 0,
        "hints_left": 3,
        "elapsed_sec": 0,
    }
    state.update(覆寫)
    return state


class TestDataDir:
    """使用者資料目錄：跨平台預設路徑 + 環境變數覆蓋。"""

    def test_環境變數優先(self, monkeypatch, tmp_path):
        monkeypatch.setenv("SUDOKU_DATA_DIR", str(tmp_path / "custom"))
        assert storage.data_dir() == tmp_path / "custom"

    def test_macos_預設為_Application_Support(self, monkeypatch):
        monkeypatch.delenv("SUDOKU_DATA_DIR", raising=False)
        monkeypatch.setattr(sys, "platform", "darwin")
        monkeypatch.setenv("HOME", "/Users/tester")
        assert storage.data_dir() == Path("/Users/tester/Library/Application Support/sudoku")

    def test_linux_預設為_XDG_資料目錄(self, monkeypatch):
        monkeypatch.delenv("SUDOKU_DATA_DIR", raising=False)
        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.setenv("HOME", "/home/tester")
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
        assert storage.data_dir() == Path("/home/tester/.local/share/sudoku")
        monkeypatch.setenv("XDG_DATA_HOME", "/xdg-data")
        assert storage.data_dir() == Path("/xdg-data/sudoku")

    def test_windows_預設為_APPDATA(self, monkeypatch):
        monkeypatch.delenv("SUDOKU_DATA_DIR", raising=False)
        monkeypatch.setattr(sys, "platform", "win32")
        monkeypatch.setenv("APPDATA", "C:\\Users\\tester\\AppData\\Roaming")
        assert storage.data_dir() == Path("C:\\Users\\tester\\AppData\\Roaming") / "sudoku"


class TestSaveGame:
    """自動存檔：每模式一份 saves/<mode>.json，原子寫入，讀回一致。"""

    def test_存檔後讀回一致(self, 隔離資料目錄):
        state = _state(elapsed_sec=42, mistakes=1)
        記錄 = storage.save_game("easy", state)
        assert 記錄["mode"] == "easy"
        assert 記錄["state"] == state
        assert storage.load_game("easy") == 記錄
        # 實際寫在 saves/easy.json，且是合法 JSON
        存檔檔 = 隔離資料目錄 / "saves" / "easy.json"
        assert 存檔檔.is_file()
        assert json.loads(存檔檔.read_text(encoding="utf-8")) == 記錄

    def test_各模式各一份互不覆蓋(self, 隔離資料目錄):
        storage.save_game("easy", _state(elapsed_sec=1))
        storage.save_game("hard", _state(elapsed_sec=2))
        storage.save_game("daily", _state(elapsed_sec=3))
        assert storage.list_saves() == ["daily", "easy", "hard"]
        assert storage.load_game("easy")["state"]["elapsed_sec"] == 1
        assert storage.load_game("hard")["state"]["elapsed_sec"] == 2
        assert storage.load_game("daily")["state"]["elapsed_sec"] == 3
        存檔目錄 = 隔離資料目錄 / "saves"
        assert sorted(p.name for p in 存檔目錄.iterdir()) == [
            "daily.json", "easy.json", "hard.json",
        ]

    def test_覆寫同模式存檔只留最新(self, 隔離資料目錄):
        storage.save_game("medium", _state(elapsed_sec=10))
        storage.save_game("medium", _state(elapsed_sec=99))
        assert storage.load_game("medium")["state"]["elapsed_sec"] == 99
        assert storage.list_saves() == ["medium"]

    def test_沒有存檔時讀回為_None(self):
        assert storage.load_game("expert") is None
        assert storage.list_saves() == []

    def test_未知模式應報錯(self):
        with pytest.raises(ValueError):
            storage.save_game("nightmare", _state())
        with pytest.raises(ValueError):
            storage.load_game("nightmare")
        with pytest.raises(ValueError):
            storage.delete_save("nightmare")

    def test_刪除存檔(self, 隔離資料目錄):
        storage.save_game("easy", _state())
        assert storage.delete_save("easy") is True
        assert storage.load_game("easy") is None
        assert storage.list_saves() == []
        assert storage.delete_save("easy") is False  # 已不存在

    def test_原子寫入成功後不留暫存檔(self, 隔離資料目錄):
        storage.save_game("easy", _state())
        存檔目錄 = 隔離資料目錄 / "saves"
        assert [p.name for p in 存檔目錄.iterdir()] == ["easy.json"]

    def test_寫入中途失敗不毀壞舊存檔(self, 隔離資料目錄, monkeypatch):
        舊記錄 = storage.save_game("easy", _state(elapsed_sec=1))

        def 假故障(*args, **kwargs):
            raise OSError("模擬磁碟故障")

        原replace = os.replace
        monkeypatch.setattr(os, "replace", 假故障)
        with pytest.raises(OSError):
            storage.save_game("easy", _state(elapsed_sec=2))
        monkeypatch.setattr(os, "replace", 原replace)  # 只還原 os.replace，保留資料目錄隔離

        # 舊存檔毫髮無傷、暫存檔清乾淨
        assert storage.load_game("easy") == 舊記錄
        存檔目錄 = 隔離資料目錄 / "saves"
        assert [p.name for p in 存檔目錄.iterdir()] == ["easy.json"]
        assert json.loads((存檔目錄 / "easy.json").read_text(encoding="utf-8")) == 舊記錄


def _entry(**覆寫) -> dict:
    """一筆歷史 entry（add_history 前的純 dict）。"""
    entry = {
        "mode": "easy",
        "difficulty": "easy",
        "result": "completed",
        "duration_sec": 120,
        "mistakes": 2,
    }
    entry.update(覆寫)
    return entry


class TestHistory:
    """遊玩紀錄：history.json 陣列，可依難度與結果篩選；放棄留紀錄並清存檔。"""

    def test_新增後可讀回且自動補時間(self, 隔離資料目錄):
        記錄 = storage.add_history(_entry())
        assert 記錄["played_at"][:4].isdigit()  # 自動補 ISO 時間
        歷史 = storage.list_history()
        assert len(歷史) == 1
        assert 歷史[0] == 記錄
        # 實際寫在 history.json
        檔內容 = json.loads((隔離資料目錄 / "history.json").read_text(encoding="utf-8"))
        assert 檔內容 == [記錄]

    def test_依難度篩選(self):
        storage.add_history(_entry(mode="easy", difficulty="easy", result="completed"))
        storage.add_history(_entry(mode="hard", difficulty="hard", result="completed"))
        storage.add_history(_entry(mode="daily", difficulty="medium", result="completed"))
        assert [e["difficulty"] for e in storage.list_history(difficulty="easy")] == ["easy"]
        assert len(storage.list_history(difficulty="hard")) == 1
        assert len(storage.list_history(difficulty="medium")) == 1
        assert storage.list_history(difficulty="expert") == []

    def test_依結果篩選(self):
        storage.add_history(_entry(result="completed"))
        storage.add_history(_entry(mode="medium", difficulty="medium", result="abandoned"))
        assert all(e["result"] == "completed" for e in storage.list_history(result="completed"))
        放棄 = storage.list_history(result="abandoned")
        assert len(放棄) == 1 and 放棄[0]["mode"] == "medium"

    def test_難度與結果聯合篩選_且新在前(self):
        storage.add_history(_entry(mode="easy", difficulty="easy", result="completed", duration_sec=10))
        storage.add_history(_entry(mode="easy", difficulty="easy", result="abandoned"))
        storage.add_history(_entry(mode="hard", difficulty="hard", result="completed", duration_sec=30))
        結果 = storage.list_history(difficulty="easy", result="completed")
        assert len(結果) == 1 and 結果[0]["duration_sec"] == 10
        全部 = storage.list_history()
        assert [e["mode"] for e in 全部] == ["hard", "easy", "easy"]  # 新→舊

    def test_放棄的局留歷史並刪該模式存檔(self, 隔離資料目錄):
        storage.save_game("hard", _state())
        assert storage.list_saves() == ["hard"]
        記錄 = storage.add_history(_entry(mode="hard", difficulty="hard", result="abandoned"))
        assert 記錄["result"] == "abandoned"
        assert storage.load_game("hard") is None  # 存檔已清
        assert storage.list_saves() == []
        assert storage.list_history(result="abandoned")[0]["mode"] == "hard"  # 歷史仍在

    def test_完成的局保留存檔(self):
        storage.save_game("easy", _state())
        storage.add_history(_entry(result="completed"))
        assert storage.load_game("easy") is not None

    def test_非法模式_難度_結果應報錯(self):
        with pytest.raises(ValueError):
            storage.add_history(_entry(mode="nightmare"))
        with pytest.raises(ValueError):
            storage.add_history(_entry(difficulty="nightmare"))
        with pytest.raises(ValueError):
            storage.add_history(_entry(result="quit"))
        with pytest.raises(ValueError):
            storage.list_history(difficulty="nightmare")
        with pytest.raises(ValueError):
            storage.list_history(result="quit")
        assert storage.list_history() == []  # 壞資料不進歷史

    def test_歷史檔損毀時當作空清單(self, 隔離資料目錄):
        隔離資料目錄.mkdir(parents=True)
        (隔離資料目錄 / "history.json").write_text("{不是 JSON", encoding="utf-8")
        assert storage.list_history() == []


class TestStats:
    """生涯統計：各難度最佳時間、零錯誤完成次數、每日挑戰連勝（中斷清零）。"""

    def test_初始統計(self, 隔離資料目錄):
        統計 = storage.get_stats()
        assert 統計["best_time"] == {"easy": None, "medium": None, "hard": None, "expert": None}
        assert 統計["perfect_clears"] == {"easy": 0, "medium": 0, "hard": 0, "expert": 0}
        assert 統計["daily_streak"] == 0
        assert 統計["daily_wins"] == []
        assert (隔離資料目錄 / "stats.json").exists() is False  # 唯讀不建檔

    def test_完成時更新最佳時間_更快才覆蓋(self, 隔離資料目錄):
        storage.add_history(_entry(difficulty="easy", result="completed", duration_sec=300, mistakes=1))
        assert storage.get_stats()["best_time"]["easy"] == 300
        storage.add_history(_entry(difficulty="easy", result="completed", duration_sec=200, mistakes=1))
        assert storage.get_stats()["best_time"]["easy"] == 200  # 更快，覆蓋
        storage.add_history(_entry(difficulty="easy", result="completed", duration_sec=250, mistakes=1))
        assert storage.get_stats()["best_time"]["easy"] == 200  # 較慢，不覆蓋
        # stats.json 實際已寫入
        檔內容 = json.loads((隔離資料目錄 / "stats.json").read_text(encoding="utf-8"))
        assert 檔內容["best_time"]["easy"] == 200

    def test_零錯誤完成次數只計零錯誤(self):
        storage.add_history(_entry(result="completed", mistakes=0))
        storage.add_history(_entry(result="completed", mistakes=0))
        storage.add_history(_entry(result="completed", mistakes=3))
        assert storage.get_stats()["perfect_clears"]["easy"] == 2

    def test_放棄不計最佳時間與零錯誤(self):
        storage.add_history(_entry(result="abandoned", duration_sec=10, mistakes=0))
        統計 = storage.get_stats()
        assert 統計["best_time"]["easy"] is None
        assert 統計["perfect_clears"]["easy"] == 0

    def test_各難度統計獨立(self):
        storage.add_history(_entry(difficulty="easy", result="completed", duration_sec=100, mistakes=0))
        storage.add_history(_entry(mode="hard", difficulty="hard", result="completed", duration_sec=500, mistakes=0))
        統計 = storage.get_stats()
        assert 統計["best_time"] == {"easy": 100, "medium": None, "hard": 500, "expert": None}
        assert 統計["perfect_clears"] == {"easy": 1, "medium": 0, "hard": 1, "expert": 0}

    def test_每日挑戰完成記連勝(self):
        storage.add_history(
            _entry(mode="daily", difficulty="medium", result="completed", duration_sec=88)
        )
        統計 = storage.get_stats()
        assert 統計["daily_streak"] == 1
        assert len(統計["daily_wins"]) == 1

    def test_每日挑戰放棄不計連勝(self):
        storage.add_history(_entry(mode="daily", difficulty="medium", result="abandoned"))
        assert storage.get_stats()["daily_streak"] == 0


class TestDailyStreak:
    """record_daily_win：當天完成才算一天、連續日期才累計、中斷清零。"""

    def test_連續日期累計(self):
        storage.record_daily_win("2026-11-22")
        storage.record_daily_win("2026-11-23")
        storage.record_daily_win("2026-11-24")
        統計 = storage.get_stats()
        assert 統計["daily_streak"] == 3
        assert 統計["daily_wins"] == ["2026-11-22", "2026-11-23", "2026-11-24"]

    def test_同一天重複記不加算(self):
        storage.record_daily_win("2026-11-24")
        storage.record_daily_win("2026-11-24")
        assert storage.get_stats()["daily_streak"] == 1
        assert storage.get_stats()["daily_wins"] == ["2026-11-24"]

    def test_中斷後清零重新計(self):
        storage.record_daily_win("2026-11-20")
        storage.record_daily_win("2026-11-21")
        assert storage.get_stats()["daily_streak"] == 2
        # 跳過 22、23，直接記 24 → 連續斷了，只剩 24 這一天
        storage.record_daily_win("2026-11-24")
        統計 = storage.get_stats()
        assert 統計["daily_streak"] == 1
        assert 統計["daily_wins"] == ["2026-11-20", "2026-11-21", "2026-11-24"]

    def test_中間斷一天後面連續不算(self):
        storage.record_daily_win("2026-11-24")
        storage.record_daily_win("2026-11-22")  # 23 沒贏 → 24 那段只算 1
        assert storage.get_stats()["daily_streak"] == 1
        storage.record_daily_win("2026-11-23")
        assert storage.get_stats()["daily_streak"] == 3

    def test_亂序記錄也正確(self):
        storage.record_daily_win("2026-11-24")
        storage.record_daily_win("2026-11-22")
        storage.record_daily_win("2026-11-23")
        assert storage.get_stats()["daily_streak"] == 3

    def test_日期格式錯誤應報錯(self):
        with pytest.raises(ValueError):
            storage.record_daily_win("2026/11/24")
        with pytest.raises(ValueError):
            storage.record_daily_win("不是日期")
