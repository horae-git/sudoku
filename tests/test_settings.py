"""小設定檔 settings（storage 的 get_setting / set_setting / get_settings）單元測試。

測試接縫：storage 公開 API——settings.json 的讀寫（原子寫入、預設值、
損毀檔當空設定）。票券 09 用來持久化目前背景主題（theme），重開 app 記得。
與存檔 / 歷史 / 統計（save / history / stats）分開存，互不影響。
"""

import json

import pytest

from sudoku import storage


@pytest.fixture(autouse=True)
def 隔離資料目錄(monkeypatch, tmp_path):
    """把資料目錄導向暫存資料夾，回傳該 Path 供斷言檔案用。"""
    資料目錄 = tmp_path / "user-data"
    monkeypatch.setenv("SUDOKU_DATA_DIR", str(資料目錄))
    return 資料目錄


class TestSettings:
    """get_setting / set_setting：settings.json 原子讀寫；預設值、損毀處理、與其他檔案隔離。"""

    def test_預設值與型別(self, 隔離資料目錄):
        assert storage.get_setting("theme") is None
        assert storage.get_setting("theme", "light") == "light"
        assert storage.get_settings() == {}
        assert (隔離資料目錄 / "settings.json").exists() is False  # 唯讀不建檔

    def test_設定後讀回一致且寫進settings檔(self, 隔離資料目錄):
        storage.set_setting("theme", "dark")
        assert storage.get_setting("theme") == "dark"
        assert storage.get_setting("theme", "light") == "dark"  # 有值時預設值不生效
        assert storage.get_settings() == {"theme": "dark"}
        檔內容 = json.loads((隔離資料目錄 / "settings.json").read_text(encoding="utf-8"))
        assert 檔內容 == {"theme": "dark"}

    def test_覆寫既有key只留最新(self):
        storage.set_setting("theme", "dark")
        storage.set_setting("theme", "macaron")
        assert storage.get_setting("theme") == "macaron"
        assert storage.get_settings() == {"theme": "macaron"}

    def test_多個key共存(self):
        storage.set_setting("theme", "dark")
        storage.set_setting("volume", 3)
        assert storage.get_settings() == {"theme": "dark", "volume": 3}

    def test_原子寫入成功後不留暫存檔(self, 隔離資料目錄):
        storage.set_setting("theme", "dark")
        assert [p.name for p in 隔離資料目錄.iterdir()] == ["settings.json"]

    def test_損毀的settings檔當作空設定(self, 隔離資料目錄):
        隔離資料目錄.mkdir(parents=True)
        (隔離資料目錄 / "settings.json").write_text("{不是 JSON", encoding="utf-8")
        assert storage.get_settings() == {}
        assert storage.get_setting("theme", "light") == "light"
        # 損毀後仍可寫入並覆蓋
        storage.set_setting("theme", "dark")
        assert storage.get_setting("theme") == "dark"

    def test_非dict的settings檔當作空設定(self, 隔離資料目錄):
        隔離資料目錄.mkdir(parents=True)
        (隔離資料目錄 / "settings.json").write_text('["不是", "dict"]', encoding="utf-8")
        assert storage.get_settings() == {}
        assert storage.get_setting("theme") is None

    def test_settings與存檔歷史統計互不影響(self, 隔離資料目錄):
        storage.save_game("easy", {"puzzle": "0" * 81})
        storage.add_history({"mode": "easy", "difficulty": "easy", "result": "completed", "duration_sec": 5})
        storage.set_setting("theme", "macaron")
        assert storage.get_setting("theme") == "macaron"
        assert storage.list_saves() == ["easy"]
        assert len(storage.list_history()) == 1
        assert storage.get_stats()["best_time"]["easy"] == 5
        assert sorted(p.name for p in 隔離資料目錄.iterdir()) == [
            "history.json",
            "saves",
            "settings.json",
            "stats.json",
        ]


class TestThemePersistence:
    """主題持久化接縫：themes.set_current_theme / get_current_theme 寫讀 storage settings。"""

    def test_預設主題為淺色(self):
        from sudoku import themes

        assert themes.get_current_theme_name() == "light"
        assert themes.get_current_theme() is themes.LIGHT

    def test_切換主題後記得且重開讀回(self):
        from sudoku import themes

        themes.set_current_theme("dark")
        assert themes.get_current_theme_name() == "dark"
        assert themes.get_current_theme() is themes.DARK
        # 模擬「重開 app」：重新讀 settings（不經任何記憶體狀態）
        assert storage.get_setting("theme") == "dark"
        assert themes.get_theme(themes.get_current_theme_name()) is themes.DARK

    def test_未知主題不會寫入且丟例外(self):
        from sudoku import themes

        with pytest.raises(ValueError):
            themes.set_current_theme("nightmare")
        assert storage.get_setting("theme") is None
        assert themes.get_current_theme_name() == "light"

    def test_settings裝壞值時回預設淺色(self, 隔離資料目錄):
        from sudoku import themes

        storage.set_setting("theme", "nightmare")  # 直接寫壞值
        assert themes.get_current_theme_name() == "light"
        assert themes.get_current_theme() is themes.LIGHT
