---
title: 安裝
description: 一行指令，另外加裝 pi-better-show 開複查頁。
---

anchorloop 是一個 [pi](https://github.com/earendil-works/pi) 套件：一組 skill，加上隨之載入的兩個小型 extension。

## 安裝套件

```bash
pi install npm:pi-anchorloop
```

這是建議的使用方式，不需要其他東西就能執行。

## 複查頁（選用）

`human-feedback` 的 UAT playbook 和 `visual-designing` 用 [pi-better-show](https://github.com/wayne930242/pi-better-show) 的 `show_doc` 工具開複查頁。
請和 anchorloop 一併安裝，才有這些頁面。

```bash
pi install npm:pi-better-show
```

沒裝時，這兩個 skill 改在回覆裡列出擷圖或畫面的路徑。

## 從本機 checkout 使用

本機 checkout 會直接載入，改完 `/reload` 就生效：

```bash
pi install /path/to/anchorloop
```

<details>
<summary>extension 還會用到什麼</summary>

- 收尾守門會讀 `todo` 的 `anchor` 或 `metadata.anchor`，也會讀 `tasks[]` 裡的項目與 Straw Boss 的檢查規格。安裝 [pi-todo-ledger](https://github.com/wayne930242/pi-todo-ledger) 後，檢查通過時，收尾守門會提醒你用 `todo` 記下證據。沒有 todo 工具時，就用 `Anchor:` 那一行。
- 委派規則使用 `subagent` 工具，例如 [pi-straw-boss](https://wayne930242.github.io/pi-straw-boss/docs/) 提供的工具。
- 兩個 extension 都不需要 key、模型或 Python。

各項在用到的地方另有說明，見[擴充功能參考](/anchorloop/zh-tw/reference/how-it-works/)。

</details>

## 下一步

- [快速開始](/anchorloop/zh-tw/guide/quick-start/)：一步一步走完第一個任務。
- [概念](/anchorloop/zh-tw/guide/concepts/)：循環與它的用語。
