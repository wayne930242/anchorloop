---
title: 快速開始
description: 用四個步驟走完第一個任務。
---

1. **交給 pi 一個任務。** pi 會選描述相符的入口 skill：修 bug 或做功能用 `coding`，回答問題用 `investigating`，審查用 `inspecting`，依此類推。[Skill](/anchorloop/zh-tw/guide/skills/) 列出全部。
2. **讀對齊那一行。** 第一則回覆以 `Alignment: <你的目標、它要解決的問題，以及預期能達成目標的最小改動>` 開頭。在這裡抓到誤讀，只花一則訊息，比改錯程式碼便宜，所以請立刻指正。
3. **看著 loop 走。** agent 建立第一個 `todo` 時 loop 就開啟，編輯器下方的 widget 顯示 `⚓ <種類> · <最後完成的階段> ✓ → <下一個階段>`。agent 會在 `Reality anchor:` 這一行寫出它的 anchor：會觀察結果的那道檢查。`anchorloop_stage read` 以完整形式顯示 loop 的判讀。
4. **讀回報。** 回覆附上 anchor 觀察到的結果；沒有被檢查涵蓋的部分標為 `unknown`。回報說還有 review、人工檢查或部署未做時，再請它去做。

## 你可能看到什麼

- 編輯後附上一行警告：loop 還沒有 anchor，或 `durable` loop 缺決策、spec 或核准。編輯仍會放行。
- 一輪結束時 second-thought extension 送來的 `next:` 提醒，在 Jev 對 loop 的證據有疑慮時出現。
- 一行請你重新分類：quick 或 inline 的改動超過三個原始碼檔案或兩個目錄時。

[擴充功能參考](/anchorloop/zh-tw/reference/how-it-works/)寫明各自何時出現。

## 下一步

- [概念](/anchorloop/zh-tw/guide/concepts/)：循環、四種 loop 與 anchor。
- [Skill](/anchorloop/zh-tw/guide/skills/)：每個入口 skill 以什麼為 anchor。
