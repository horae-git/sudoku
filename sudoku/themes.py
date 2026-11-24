"""背景主題色票（Theme）。

每套主題是一份不可變的色票 dataclass：背景、格線、宮粗線、各種格子底色與文字色。
UI 由此讀取顏色，達成「顏色可由 theme 色票讀取」的預留（票券 09 會補深色/馬卡龍，
並讓深色主題的宮粗線更明顯）。目前票券 06 先提供預設淺色（light）。
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Theme:
    """一套色票。所有顏色皆為 ``#RRGGBB`` 色碼。"""

    名稱: str
    背景: str  # 視窗背景
    面板: str  #資訊面板等次要區塊底色
    按鈕: str  # 一般按鈕底色
    按鈕懸停: str  # 按鈕懸停底色
    按鈕文字: str  # 按鈕文字色
    標題文字: str  # 標題文字色
    文字: str  # 一般文字色
    格線: str  # 一般格線色
    宮粗線: str  # 3×3 宮分隔粗線色
    格子底: str  # 普通空格底色
    格子題示底: str  # 題示數格子底色
    格子高亮底: str  # 同行/列/宮高亮底色
    格子同數底: str  # 與選取格相同數字的高亮底色
    格子選取底: str  # 被選取格底色
    格子選取文字: str  # 被選取格文字色
    格子錯誤底: str  # 填錯格底色
    文字題示: str  # 題示數文字色
    文字錯誤: str  # 錯誤數字文字色（紅）
    文字填入: str  # 玩家填入數字文字色


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
    格子底="#FFFFFF",
    格子題示底="#E9ECF5",
    格子高亮底="#D6E4FF",
    格子同數底="#B2D0FF",
    格子選取底="#8FB8FF",
    格子選取文字="#101828",
    格子錯誤底="#FFE3E3",
    文字題示="#1B1F2A",
    文字錯誤="#C92A2A",
    文字填入="#2F6FED",
)

# 內建色票表（票券 09 會再加入 dark / macaron）
THEMES: dict[str, Theme] = {"light": LIGHT}


def theme_names() -> list[str]:
    """所有可用主題名稱（依註冊順序）。"""
    return list(THEMES)


def get_theme(name: str = "light") -> Theme:
    """依名稱取得色票；未知名稱拋出 ValueError。"""
    try:
        return THEMES[name]
    except KeyError:
        raise ValueError(f"未知主題：{name!r}（可用：{', '.join(THEMES)}）") from None
