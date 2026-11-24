# 01: 專案骨架與核心領域模型

**What to build:** 建立可執行、可測試的專案骨架：以 uv 管理的 pyproject 與模組化 package（核心邏輯模組：題目/求解器/對局/存檔，以及 UI 層與進入點），並定義領域模型——題目（Puzzle）、解答（Solution）、格子（Cell）、宮（Box）的不可變資料結構與基本驗證（行/列/宮不得重複）。完成本票後，可以在終端機以 uv 執行進入點（先顯示主選單視窗框架）、核心模型有基本單元測試且全數通過。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] `uv` 環境可建立並安裝依賴（含 customtkinter 與 pytest dev 依賴）
- [ ] package 結構建立（核心邏輯模組 + UI 進入點），`uv run` 可啟動空的主視窗
- [ ] 領域模型（題目/解答/格子/宮）定義完成，含合法性驗證
- [ ] 核心模型的單元測試通過（pytest）
