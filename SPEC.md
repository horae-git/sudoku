# SPEC — 數獨桌面遊戲

>術語統一採用 `GLOSSARY.md` 的領域用語。決策來自與使用者的設計訪談（見 GLOSSARY 與本文 Implementation Decisions）。

## Problem Statement

使用者想要一個 Python 桌面數獨遊戲：從主選單進入不同功能畫面，具備難度選擇、計時、提示、錯誤標示、筆記、高亮、鍵盤操作、快速題目生成、每日挑戰、遊玩紀錄、生涯總覽、自動存檔與多種背景主題，整體為現代扁平風格、圓角按鈕，並特別要求深色主題下九宮格線條更明顯、暫停時遮住題目、勝利畫面清楚且返回按鈕不被遮擋。

## Solution

以 customtkinter 打造的單一視窗（固定 960×760）桌面 app：左側置中 9×9 棋盤，右側資訊面板（計時/錯誤/提示次數/操作按鈕）。核心為模組化的 `sudoku` Python package（純邏輯、可測試），UI 層只負責繪製與事件轉發。資料以 JSON 原子寫入使用者資料目錄，達成自動存檔與歷史統計。

## User Stories

### 主選單與導覽
1. As a 玩家，I want a 主選單顯示「每日挑戰 / 各難度開始 / 遊玩紀錄 / 生涯總覽 / 背景主題🎨」按鈕，so that 我能從一處進入所有功能。
2. As a 玩家，I want 背景主題按鈕放在首頁顯眼處，so that 我不用進設定就能換風格。
3. As a 玩家，I want 在任何功能畫面都能返回上一個畫面，so that 操作不會迷路。
4. As a 玩家，I want 開新局時舊的進行中對局不會被覆蓋，so that 我可以同時保有不同模式各一局。

### 開局與難度
5. As a 玩家，I want 選擇 簡單/中等/困難/專家 開始新局，so that 挑戰程度符合我的程度。
6. As a 玩家，I want 難度確實反映解題所需技巧（X-wing、swordfish 等高級技巧頻率）與挖空數，so that 「困難」真的比較難。
7. As a 玩家，I want 開始新局時立刻看到題目（生成時間短），so that 不用等待。
8. As a 玩家，I want 進行中有繼續遊戲的入口，so that 關掉 app 後回來能接關卡玩。

### 遊玩操作
9. As a 玩家，I want 用滑鼠點選格子並用數字鍵或點擊數字鍵盤填入 1–9，so that 操作直覺。
10. As a 玩家，I want 用方向鍵在棋盤上移動選取格，so that 不用滑鼠也能玩。
11. As a 玩家，I want Delete/Backspace 清除我填的格子（題示數不能清），so that 修正方便。
12. As a 玩家，I want 按「筆記」按鈕或 N 鍵切換筆記模式，在格子裡記候選數字，so that 我能記錄推理。
13. As a 玩家，I want 填入正確數字後，同行/列/宮內相同數字的筆記自動清除，so that 候選數保持正確。
14. As a 玩家，I want 選取格子時同行/列/宮與相同數字自動高亮，so that 我一眼看出關聯。
15. As a 玩家，I want 用 Ctrl+Z 或 ↩ 按鈕返回上一步，一路復原到開局，so that 走錯不怕。
16. As a 玩家，I want 不用滑鼠、全靠鍵盤完成一整局，so that 操作效率高。

### 錯誤、提示、計時
17. As a 玩家，I want 填錯立即看到紅色並累計錯誤次數，紅色保留直到我修改，so that 我知道自己錯哪裡。
18. As a 玩家，I want 每局有 3 次提示，隨機填入一個正確格子並顯示綠色且鎖定，so that 卡關時能求助。
19. As a 玩家，I want 遊戲開始自動計時、完成後停止並顯示用時，so that 我知道成績。

### 暫停與存檔
20. As a 玩家，I want 按 ⏸ 或 Escape 暫停，棋盤被遮罩蓋住且計時停止，so that 休息時不會偷看題目也不會被計時。
21. As a 玩家，I want 每次填入與每秒計時都自動存檔，so that 重開 app 能繼續沒玩完的局。

### 每日挑戰
22. As a 玩家，I want 每天進入固定同一道每日挑戰題（日期為種子、中等難度），so that 每天有固定挑戰。
23. As a 玩家，I want 遊玩每日挑戰時畫面標示「本日題目」，so that 我知道這是每日挑戰。
24. As a 玩家，I want 系統記錄每日挑戰連勝天數（當天完成才算），so that 我有連續挑戰的成就感。

### 紀錄與統計
25. As a 玩家，I want 在遊玩紀錄看到歷史清單，並依難度與結果（完成/放棄）篩選，so that 我能回顧過去的對局。
26. As a 玩家，I want 在生涯總覽看到各難度最佳時間、零錯誤完成次數與每日挑戰連勝，so that 我看見自己的進步。
27. As a 玩家，I want 放棄的對局被記為「放棄」進入歷史（但不繼續存檔），so that 紀錄完整。

### 視覺與勝利
28. As a 玩家，I want 在淺色/深色/馬卡龍三種背景主題間切換，so that 依心情選風格。
29. As a 玩家，I want 深色主題下九宮格的粗線更明顯，so that 黑暗中棋盤依然清楚。
30. As a 玩家，I want 整體為現代扁平 UI、按鈕與線條圓角、色塊精緻、邊框柔和，so that 看起來現代舒服。
31. As a 玩家，I want 勝利時看到清楚置中的勝利畫面（用時/錯誤/難度）與不被遮擋的「返回首頁」「再來一局」按鈕，so that 成就感完整、操作不卡住。

## Implementation Decisions

- **UI 框架**：customtkinter（扁平現代、原生圓角、深淺色模式），單一固定視窗 960×760，棋盤置中、右側資訊面板。
- **專案結構**：`pyproject.toml` + `sudoku/` package，模組為 `generator`、`solver`（含技巧鏈）、`session`（對局狀態機）、`storage`、`themes`，`ui/` 放各畫面，`main.py` 進入點；環境與依賴由 uv 管理。
- **題目生成**：完整解 via 亂數洗牌 + 回溯；挖空時以 MRV（最小剩餘值）啟發 + 回溯檢查，保證唯一解，大幅縮短生成時間。
- **難度分級**：技巧鏈求解器由簡到難嘗試（naked/hidden singles → naked/hidden pairs → locked candidates → X-wing → swordfish …），難度 = 解題所需最難技巧等級為主、挖空數為輔的門檻表；生成時對不符門檻者重抽。
- **每日挑戰**：種子 = 日期字串，難度固定中等；當天完成才計連勝一天。
- **錯誤**：填錯立即標紅、計次、紅色保留至修改；不設上限、不結束本局。
- **提示**：每局 3 次，綠色粗體且鎖定不可改。
- **筆記**：填入正確數字後自動清除同行/列/宮相同數的筆記。
- **復原**：完整動作堆疊（含提示填入），可一路回開局。
- **暫停**：棋盤覆半透明遮罩 + 置中「⏸ 已暫停」，計時暫停。
- **存檔**：每次動作 + 每秒 tick 觸發，原子寫入（tmp + rename）；每個模式（簡單/中等/困難/專家/每日挑戰）各保留一份進行中存檔；放棄的局清掉存檔但留歷史紀錄。
- **資料儲存**：使用者資料目錄下的 JSON（save / history / stats）。SPEC 原話 `~/.local/share/sudoku/` 僅為舉例——實際為跨平台行為：macOS 走 `~/Library/Application Support/sudoku`，Linux 走 `$XDG_DATA_HOME/sudoku` 或 `~/.local/share/sudoku`，Windows 走 `%APPDATA%\sudoku`；可用環境變數 `SUDOKU_DATA_DIR` 覆蓋。
- **歷史篩選**：難度 + 結果（完成/放棄）兩個篩選；另外保留「每日挑戰」選項（daily 是歷史裡的實際類別，篩 mode == "daily"）。
- **主題**：3 套色票（淺色 / 深色 / 馬卡龍），深色套自動加粗九宮格粗線；首頁 🎨 置於顯眼處切換、即時套用。
- **歷史篩選**：難度 + 結果（完成/放棄）兩個篩選。
- **勝利畫面**：獨立置中 modal，內含用時/錯誤/難度，底部明確按鈕列（返回首頁 / 再來一局），不被棋盤遮擋。
- **鍵盤**：方向鍵移動、1–9 填入、Delete/Backspace 清除、N 筆記、Ctrl+Z 復原、Esc 暫停；全鍵盤可完成一局。

## Testing Decisions

- **單一測試接縫**：核心 `sudoku` package 的公開 API（generator / solver 技巧鏈與分級 / session 狀態機 / storage 讀寫）視為純邏輯外部行為，以 pytest 測試；UI（customtkinter）不測試。
- **測試原則**：只驗外部行為，不驗內部實作。重點案例：
  - 生成的題目必有唯一解；每日挑戰同一天種子產生同一題。
  - 各難度門檻正確：簡單只需 single、困難需 X-wing、專家需 swordfish 等。
  - session 行為：填錯計次且格子標紅、提示鎖定、筆記自動清除、復原堆疊、暫停不計時。
  - storage：動作後與讀回一致（原子寫入、每模式各一份存檔、放棄清存檔留歷史）。
- **測試工具**：pytest，列於 uv 的 dev 依賴群組。

## Out of Scope

-線上對戰、排行榜、帳號系統。
- 手機版 / Web 版（僅桌面 app）。
- 自訂題目匯入、影像辨識題目。
- UI 自動化測試（畫面截圖比對）。
- 超過 swordfish 以上的技巧（如 fish 複雜鏈、唯一矩形進階型）——技巧鏈實作到 swordfish 為止，專家門檻以此為上限。

## Further Notes

- PRD 原話保留在 `PRD.md`；領域術語見 `GLOSSARY.md`。
- 本專案未設定 issue tracker 與 triage label 語彙（需執行 `/setup-matt-pocock-skills` 才會注入），因此本 spec 未發布到 issue tracker、也未貼 `ready-for-agent` label，而是存於專案根目錄 `SPEC.md`。
- 回覆與註解一律使用繁體中文（見 CLAUDE.md）。
