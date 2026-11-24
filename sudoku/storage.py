"""存檔 / 遊玩紀錄 / 生涯統計 storage。

資料以 JSON 原子寫入（先寫 tmp 再 ``os.replace``）使用者資料目錄：

- 自動存檔：每個模式（easy/medium/hard/expert/daily）各一份 ``saves/<mode>.json``；
- 遊玩紀錄：``history.json`` 陣列，可依難度與結果（completed/abandoned）篩選；
- 生涯統計：``stats.json``——各難度最佳時間、零錯誤完成次數、每日挑戰連勝。

所有公開介面皆為純 dict / JSON 友善的資料結構（不依賴 session 模組），
``state_dict`` 的 key schema 由 session 層負責填入：

- ``puzzle`` / ``solution`` / ``board``：81 字元字串（空格以 ``'0'`` 表示，行優先）
- ``notes``：81 個 list（每格的候選數字）
- ``mistakes``：錯誤次數（int）
- ``hints_left``：剩餘提示次數（int）
- ``elapsed_sec``：已過秒數（int）

歷史 entry 的 schema::

    {
        "played_at":    ISO 時間字串（add_history 自動補）,
        "mode":         "easy"/"medium"/"hard"/"expert"/"daily",
        "difficulty":   "easy"/"medium"/"hard"/"expert"（daily 記為 "medium"）,
        "result":       "completed"/"abandoned",
        "duration_sec": 用時秒數（int，預設 0）,
        "mistakes":     錯誤數（int，預設 0）,
    }
"""

import json
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

# 合法模式（難度 + 每日挑戰）
MODES: tuple[str, ...] = ("easy", "medium", "hard", "expert", "daily")

# 合法難度（歷史與統計用；每日挑戰的難度固定記為 medium）
DIFFICULTIES: tuple[str, ...] = ("easy", "medium", "hard", "expert")

# 合法結果
RESULTS: tuple[str, ...] = ("completed", "abandoned")

# 環境變數：覆蓋使用者資料目錄（測試時導向暫存資料夾）
DATA_DIR_ENV = "SUDOKU_DATA_DIR"


def data_dir() -> Path:
    """使用者資料目錄（跨平台）：

    - macOS：``~/Library/Application Support/sudoku``
    - Linux：``$XDG_DATA_HOME/sudoku`` 或 ``~/.local/share/sudoku``
    - Windows：``%APPDATA%\\sudoku``

    設定環境變數 ``SUDOKU_DATA_DIR`` 可覆蓋（測試用）。
    """
    覆蓋 = os.environ.get(DATA_DIR_ENV)
    if 覆蓋:
        return Path(覆蓋)
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "sudoku"
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))) / "sudoku"
    # linux 與其他 POSIX 系統
    xdg = os.environ.get("XDG_DATA_HOME")
    基底 = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return 基底 / "sudoku"


def _驗證模式(mode: str) -> None:
    if mode not in MODES:
        raise ValueError(f"未知模式：{mode!r}（合法：{', '.join(MODES)}）")


def _驗證難度(difficulty: str) -> None:
    if difficulty not in DIFFICULTIES:
        raise ValueError(f"未知難度：{difficulty!r}（合法：{', '.join(DIFFICULTIES)}）")


def _原子寫入JSON(路徑: Path, 資料: Any) -> None:
    """原子寫入 JSON：先寫 ``<路徑>.tmp`` 再 ``os.replace`` 到正式檔；失敗時清掉暫存檔、不毀舊檔。"""
    路徑.parent.mkdir(parents=True, exist_ok=True)
    暫存 = 路徑.with_suffix(路徑.suffix + ".tmp")
    try:
        暫存.write_text(json.dumps(資料, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(暫存, 路徑)
    except BaseException:
        暫存.unlink(missing_ok=True)
        raise


def _讀取JSON(路徑: Path, 預設: Any) -> Any:
    """讀取 JSON 檔；不存在或損毀時回傳預設值（不丟例外，避免中斷遊戲流程）。"""
    try:
        return json.loads(路徑.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 預設


def _現在時間字串() -> str:
    """本地時間的 ISO 格式字串（含時區偏移）。"""
    return datetime.now().astimezone().isoformat(timespec="seconds")


# ---------- 自動存檔 ----------


def save_game(mode: str, state: dict) -> dict:
    """儲存一局進行中的存檔（每次動作與每秒 tick 呼叫），回傳寫入的完整記錄。

    記錄格式::

        {"mode": mode, "saved_at": ISO 時間字串, "state": {...}}

    每個模式各寫一份 ``saves/<mode>.json``，互不覆蓋。
    """
    _驗證模式(mode)
    if not isinstance(state, dict):
        raise TypeError("state 必須是 dict（JSON 友善的純資料結構）")
    記錄 = {"mode": mode, "saved_at": _現在時間字串(), "state": dict(state)}
    _原子寫入JSON(data_dir() / "saves" / f"{mode}.json", 記錄)
    return 記錄


def load_game(mode: str) -> dict | None:
    """讀回某模式的進行中存檔（含 ``mode`` / ``saved_at`` / ``state``）；沒有存檔時回傳 None。"""
    _驗證模式(mode)
    結果 = _讀取JSON(data_dir() / "saves" / f"{mode}.json", None)
    return 結果 if isinstance(結果, dict) else None


def list_saves() -> list[str]:
    """列出所有有存檔的模式（排序後回傳）。"""
    存檔目錄 = data_dir() / "saves"
    try:
        return sorted(p.stem for p in 存檔目錄.glob("*.json") if p.stem in MODES)
    except OSError:
        return []


def delete_save(mode: str) -> bool:
    """刪除某模式的存檔（放棄的局呼叫）；回傳是否真的有刪到。"""
    _驗證模式(mode)
    路徑 = data_dir() / "saves" / f"{mode}.json"
    if not 路徑.is_file():
        return False
    路徑.unlink()
    return True


# ---------- 遊玩紀錄 ----------


def add_history(entry: dict) -> dict:
    """記錄一局結束（完成或放棄）到 history.json，回傳寫入的完整 entry。

    - ``result == "completed"``：同時更新生涯統計（最佳時間、零錯誤次數）；
      若 ``mode == "daily"``，另記一天每日挑戰連勝。
    - ``result == "abandoned"``：刪除該模式的進行中存檔（歷史仍保留）。
    """
    for 欄位 in ("mode", "difficulty", "result"):
        if 欄位 not in entry:
            raise ValueError(f"歷史紀錄缺少欄位：{欄位}")
    _驗證模式(entry["mode"])
    _驗證難度(entry["difficulty"])
    if entry["result"] not in RESULTS:
        raise ValueError(f"未知結果：{entry['result']!r}（合法：{', '.join(RESULTS)}）")
    記錄 = dict(entry)
    記錄.setdefault("played_at", _現在時間字串())
    記錄.setdefault("duration_sec", 0)
    記錄.setdefault("mistakes", 0)
    歷史檔 = data_dir() / "history.json"
    歷史 = _讀取JSON(歷史檔, [])
    if not isinstance(歷史, list):
        歷史 = []
    歷史.append(記錄)
    _原子寫入JSON(歷史檔, 歷史)
    if 記錄["result"] == "completed":
        _更新完成統計(記錄)
    else:
        delete_save(記錄["mode"])  # 放棄的局：清掉該模式存檔
    return 記錄


def list_history(difficulty: str | None = None, result: str | None = None) -> list[dict]:
    """列出遊玩紀錄（新→舊）；可依難度與結果（completed/abandoned）篩選，不篩則回傳全部。"""
    if difficulty is not None:
        _驗證難度(difficulty)
    if result is not None and result not in RESULTS:
        raise ValueError(f"未知結果：{result!r}（合法：{', '.join(RESULTS)}）")
    歷史 = _讀取JSON(data_dir() / "history.json", [])
    if not isinstance(歷史, list):
        return []
    return [
        e
        for e in reversed(歷史)
        if (difficulty is None or e.get("difficulty") == difficulty)
        and (result is None or e.get("result") == result)
    ]


# ---------- 生涯統計 ----------


def _空統計() -> dict:
    return {
        "best_time": {d: None for d in DIFFICULTIES},  # 各難度最佳時間（秒）
        "perfect_clears": {d: 0 for d in DIFFICULTIES},  # 各難度零錯誤完成次數
        "daily_streak": 0,  # 每日挑戰連勝天數
        "daily_wins": [],  # 已完成的每日挑戰日期（YYYY-MM-DD，排序）
    }


def get_stats() -> dict:
    """讀取生涯統計（stats.json）；不存在或欄位缺漏時補初始值。"""
    統計 = _讀取JSON(data_dir() / "stats.json", None)
    初始 = _空統計()
    if not isinstance(統計, dict):
        return 初始
    for key, 初始值 in 初始.items():
        if key not in 統計:
            統計[key] = 初始值
        elif isinstance(初始值, dict):
            for d in DIFFICULTIES:
                統計[key].setdefault(d, 初始值[d])
    return 統計


def _寫統計(統計: dict) -> None:
    _原子寫入JSON(data_dir() / "stats.json", 統計)


def _更新完成統計(記錄: dict) -> None:
    """一局完成時更新 stats：最佳時間（更快才覆蓋）、零錯誤完成次數 +1；每日挑戰另記連勝。"""
    統計 = get_stats()
    難度 = 記錄["difficulty"]
    用時 = 記錄["duration_sec"]
    舊最佳 = 統計["best_time"].get(難度)
    if 舊最佳 is None or 用時 < 舊最佳:
        統計["best_time"][難度] = 用時
    if 記錄["mistakes"] == 0:
        統計["perfect_clears"][難度] += 1
    if 記錄["mode"] == "daily":
        日期 = 記錄.get("date") or str(記錄["played_at"])[:10]
        record_daily_win(日期, _統計=統計)
    _寫統計(統計)


def record_daily_win(d: str, _統計: dict | None = None) -> dict:
    """記錄某天（``d`` 為 ``YYYY-MM-DD``）完成每日挑戰，回傳更新後的 stats。

    連勝規則：當天完成才算一天（重複記同一天不加算）；連勝 =從最近一次獲勝日往前
    連續的天數——中間有中斷（隔超過一天）就清零，從新的獲勝日重新計 1。
    若傳入 ``_統計``，直接更新該 dict（不另行寫檔），供內部複用。
    """
    try:
        date.fromisoformat(d)
    except ValueError:
        raise ValueError(f"日期格式錯誤（應為 YYYY-MM-DD）：{d!r}") from None
    自己寫檔 = _統計 is None
    統計 = _統計 if _統計 is not None else get_stats()
    贏集合 = set(統計.get("daily_wins") or [])
    贏集合.add(d)
    統計["daily_wins"] = sorted(贏集合)
    游標 = max(date.fromisoformat(x) for x in 贏集合)
    連勝 = 0
    while 游標.isoformat() in 贏集合:
        連勝 += 1
        游標 -= timedelta(days=1)
    統計["daily_streak"] = 連勝
    if 自己寫檔:
        _寫統計(統計)
    return 統計
