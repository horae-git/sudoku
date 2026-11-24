"""背景主題色票（Theme）。

每套主題是一份不可變的色票 dataclass：背景、格線、宮粗線（含線寬）、
各種格子底色與文字色。UI 由此讀取顏色，達成「顏色可由 theme 色票讀取」。

內建三套（票券 09）：

- ``light`` 淺色：預設，現代扁平；
- ``dark`` 深色：背景深、格線淺，且宮粗線**更粗更亮**（``宮粗線寬`` 較大、
  顏色較亮），深色主題下九宮格的 3×3 宮分隔特別明顯（PRD/SPEC 需求）；
- ``macaron`` 馬卡龍粉彩：柔和粉彩色塊。

目前使用中的主題由 storage 持久化（見 ``get_current_theme_name`` /
``set_current_theme``），重開 app 記得上次主題。
"""

from dataclasses import dataclass

from sudoku import storage


@dataclass(frozen=True)
class Theme:
    """一套色票。所有顏色皆為 ``#RRGGBB`` 色碼；``宮粗線寬`` 為宮分隔線寬（px）。"""

    名稱: str
    背景: str  # 視窗背景
    面板: str  # 資訊面板等次要區塊底色
    按鈕: str  # 一般按鈕底色
    按鈕懸停: str  # 按鈕懸停底色
    按鈕文字: str  # 按鈕文字色
    標題文字: str  # 標題文字色
    文字: str  # 一般文字色
    格線: str  # 一般格線色
    宮粗線: str  # 3×3 宮分隔粗線色
    宮粗線寬: int = 3  # 3×3 宮分隔粗線寬（px）；深色主題會加粗
    格子底: str = "#FFFFFF"  # 普通空格底色
    格子題示底: str = "#E9ECF5"  # 題示數格子底色
    格子高亮底: str = "#D6E4FF"  # 同行/列/宮高亮底色
    格子同數底: str = "#B2D0FF"  # 與選取格相同數字的高亮底色
    格子選取底: str = "#8FB8FF"  # 被選取格底色
    格子選取文字: str = "#101828"  # 被選取格文字色
    格子錯誤底: str = "#FFE3E3"  # 填錯格底色
    格子提示底: str = "#D3F9D8"  # 提示填入格底色（綠）
    文字題示: str = "#1B1F2A"  # 題示數文字色
    文字錯誤: str = "#C92A2A"  # 錯誤數字文字色（紅）
    文字提示: str = "#2B8A3E"  # 提示填入數字文字色（綠）
    文字填入: str = "#2F6FED"  # 玩家填入數字文字色
    圓角: int = 12  # 按鈕 / 面板圓角（px）


# 預設淺色主題（現代扁平、柔和邊框、格線在淺色下清楚）
LIGHT = Theme(
    名稱="light",
    背景="#F5F6FA",
    面板="#FFFFFF",
    按鈕="#4C6EF5",
    按鈕懸停="#3B5BDB",
    按鈕文字="#FFFFFF",
    標題文字="#1B1F2A",
    文字="#343A40",
    格線="#C9CEDC",
    宮粗線="#3B4252",
    宮粗線寬=3,
    格子底="#FFFFFF",
    格子題示底="#E9ECF5",
    格子高亮底="#D6E4FF",
    格子同數底="#B2D0FF",
    格子選取底="#8FB8FF",
    格子選取文字="#101828",
    格子錯誤底="#FFE3E3",
    格子提示底="#D3F9D8",
    文字題示="#1B1F2A",
    文字錯誤="#C92A2A",
    文字提示="#2B8A3E",
    文字填入="#2F6FED",
    圓角=12,
)

# 深色主題：背景深、格線淺；宮粗線加粗（5px）且更亮，深色下九宮格分隔特別明顯
DARK = Theme(
    名稱="dark",
    背景="#14161C",
    面板="#1E222B",
    按鈕="#5C7CFA",
    按鈕懸停="#748FFC",
    按鈕文字="#FFFFFF",
    標題文字="#F1F3F8",
    文字="#C9D1E0",
    格線="#3A4150",
    宮粗線="#E8ECF4",  # 比格線更亮，深色背景上跳出來
    宮粗線寬=5,  # 深色主題宮粗線加粗
    格子底="#1E222B",
    格子題示底="#2A303C",
    格子高亮底="#2E3A52",
    格子同數底="#3D5A86",
    格子選取底="#5C7CFA",
    格子選取文字="#FFFFFF",
    格子錯誤底="#4A2B33",
    格子提示底="#2B4A3E",
    文字題示="#F1F3F8",
    文字錯誤="#FF8787",
    文字提示="#8CE99A",
    文字填入="#9EC1FF",
    圓角=12,
)

# 馬卡龍粉彩主題：柔和粉彩色塊、圓角更圓，現代扁平感
MACARON = Theme(
    名稱="macaron",
    背景="#FBF3EE",
    面板="#FFFDFB",
    按鈕="#F4A7B9",
    按鈕懸停="#EE8FA5",
    按鈕文字="#5B3A44",
    標題文字="#5B3A44",
    文字="#6E5560",
    格線="#E8D5CD",
    宮粗線="#B98A96",
    宮粗線寬=3,
    格子底="#FFFDFB",
    格子題示底="#F6E7DE",
    格子高亮底="#FBDCE0",
    格子同數底="#F7C6CE",
    格子選取底="#F4A7B9",
    格子選取文字="#FFFFFF",
    格子錯誤底="#F9D7D7",
    格子提示底="#D8F5DC",
    文字題示="#5B3A44",
    文字錯誤="#C0392B",
    文字提示="#3E8E5A",
    文字填入="#D16A8A",
    圓角=14,
)

# 內建色票表（註冊順序即 theme_names() 順序）
THEMES: dict[str, Theme] = {"light": LIGHT, "dark": DARK, "macaron": MACARON}

# 主題顯示順序與中文名稱（主題選擇器畫面用）
THEME_ORDER: tuple[str, ...] = ("light", "dark", "macaron")
THEME_LABELS: dict[str, str] = {"light": "淺色", "dark": "深色", "macaron": "馬卡龍"}

# 持久化目前主題用的 settings key
_CURRENT_THEME_KEY = "theme"


def theme_names() -> list[str]:
    """所有可用主題名稱（依註冊順序）。"""
    return list(THEMES)


def get_theme(name: str = "light") -> Theme:
    """依名稱取得色票；未知名稱拋出 ValueError。"""
    try:
        return THEMES[name]
    except KeyError:
        raise ValueError(f"未知主題：{name!r}（可用：{', '.join(THEMES)}）") from None


def get_current_theme_name() -> str:
    """目前使用中的主題名稱（讀自 storage settings；無紀錄或非法時回預設 ``light``）。"""
    名稱 = storage.get_setting(_CURRENT_THEME_KEY, "light")
    return 名稱 if 名稱 in THEMES else "light"


def get_current_theme() -> Theme:
    """目前使用中的色票。"""
    return get_theme(get_current_theme_name())


def set_current_theme(name: str) -> Theme:
    """設定目前主題並持久化到 storage settings（重開 app 記得）；回傳該色票。"""
    theme = get_theme(name)  # 未知名稱會丟 ValueError
    storage.set_setting(_CURRENT_THEME_KEY, theme.名稱)
    return theme
