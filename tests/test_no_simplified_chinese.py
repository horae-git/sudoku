"""機械檢查：原始碼不得混入簡體字（CLAUDE.md「回覆請都使用繁體中文」的自動化版本）。

掃描 sudoku/ 與 tests/ 底下所有 .py；本檔自己含簡體字字面，掃描時排除自己。
注意「折類」等繁簡共用字不算違規。
"""

from pathlib import Path

簡體字 = set(
    "门显们计题这为过还发说语话读写书见观视问间闻达运远连进边没对会数学应试设请让么后双关开时单变实历紧虑悬恳恶恸愿慑懒戏战户扑执扩扫扬扰报担拟拢拣拥拦挡挥挠挣挤捞损换据掳掸掷赏贼贾债赁赚赌赎赐赠赡赢赞车轴轮软较载辆轻辅输辖辈辉辊辑辐边贝负贵买卖质贰贱贴费贺货饰饱饲验类"
)


def test_sudoku與tests原始碼無簡體特有字():
    根 = Path(__file__).resolve().parent.parent
    壞字 = []
    for 資料夾 in (根 / "sudoku", 根 / "tests"):
        for py in 資料夾.rglob("*.py"):
            if py.name == Path(__file__).name and py.parent == 根 / "tests":
                continue  # 排除本測試檔（字面含簡體字）
            if "__pycache__" in py.parts:
                continue
            for 行號, 行 in enumerate(py.read_text(encoding="utf-8").splitlines(), 1):
                for ch in 行:
                    if ch in 簡體字:
                        壞字.append(f"{py.relative_to(根)}:{行號}: {ch}")
    assert not 壞字, "發現簡體字：\n" + "\n".join(壞字)
