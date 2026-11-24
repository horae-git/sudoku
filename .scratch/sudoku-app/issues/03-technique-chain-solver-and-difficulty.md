# 03: 技巧鏈求解器與四級難度分級

**What to build:** 實作「懂技巧」的求解器：依序嘗試由簡到難的技巧（naked/hidden singles → naked/hidden pairs → locked candidates → X-wing → swordfish），記錄解開題目所需的最難技巧等級。難度分級以技巧等級為主、挖空數為輔訂門檻表：簡單＝只需 single、中等＝需 pair/locked candidates、困難＝需 X-wing、專家＝需 swordfish。生成流程會對不符門檻的題目重抽，確保各難度名符其實。

**Blocked by:** 01 專案骨架與核心領域模型

**Status:** ready-for-agent

- [ ] 技巧鏈可正確解開各技巧等級的測試題
- [ ] 各難度門檻正確（簡單只需 single…專家需 swordfish）
- [ ] 生成時能依門檻過濾/重抽
- [ ] pytest 測試：技巧鏈正確性、分級結果
