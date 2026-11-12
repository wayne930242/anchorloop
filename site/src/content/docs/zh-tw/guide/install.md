---
title: 安裝
description: 一行指令，另外加裝 pi-better-show 開複查頁。
---

anchorloop 是一個 [pi](https://github.com/earendil-works/pi) 套件：一組 skill，加上隨之載入的六個 extension。

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

- loop book 的任務紀錄來自 [`@juicesharp/rpiv-todo`](https://github.com/juicesharp/rpiv-mono/tree/main/packages/rpiv-todo#readme) 的 `todo` 工具。
- 把子代理連結到 loop 要透過 [pi-herdr-agents](https://github.com/wayne930242/pi-herdr-agents)；pi 本身沒有 subagent。
- second-thought 提醒需要 Jev 的 TypeSafe key；沒有 key 時它什麼都不做。

各項在用到的地方另有說明，見[擴充功能參考](/anchorloop/zh-tw/reference/how-it-works/)。

</details>

## 下一步

- [快速開始](/anchorloop/zh-tw/guide/quick-start/)：一步一步走完第一個任務。
- [概念](/anchorloop/zh-tw/guide/concepts/)：循環與它的用語。
