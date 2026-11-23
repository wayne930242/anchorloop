---
title: 快速開始
description: 用四個步驟走完第一個任務。
---

1. **交給 pi 一個任務。** pi 會選描述相符的入口 skill：修 bug 或做功能用 `coding`，回答問題用 `investigating`，審查用 `inspecting`，依此類推。[Skill](/anchorloop/zh-tw/guide/skills/) 列出全部。
2. **讀目標那一行。** 第一則回覆以一行重述你的目標開頭。在這裡抓到誤讀，只花一則訊息，比改錯程式碼便宜，所以請立刻指正。
3. **讀 anchor。** 第一次編輯前，agent 會寫下 `Anchor: <check>`：會觀察結果的那道確切檢查，每條指令用反引號包住。
4. **讀回報。** 回覆附上最後一次變更之後 anchor 通過的執行；沒有被檢查涵蓋的部分標為 `unknown`。回報說還有 review、人工檢查或部署未做時，再請它去做。

## 你可能看到什麼

- 收尾守門的一行提醒：執行停下時，檔案改過之後 anchor 沒有通過的執行，例如 ``anchorloop: no passing run of `pytest -q` after the last change.``。它不會開啟新的一輪。
- 編輯 skill、指令檔或 spec 後附上的驗證器建議。

[擴充功能參考](/anchorloop/zh-tw/reference/how-it-works/)寫明各自何時出現。

## 下一步

- [概念](/anchorloop/zh-tw/guide/concepts/)：循環規則、anchor 與審查規則。
- [Skill](/anchorloop/zh-tw/guide/skills/)：每個入口 skill 以什麼為 anchor。
