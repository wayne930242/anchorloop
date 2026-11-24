# anchorloop 擴充功能的運作方式 <!-- source: docs/how-it-works.md @ b6c901d -->

[README](../README.zh-TW.md) 背後的完整行為。skill 告訴 agent 怎麼工作；下面兩個 pi extension 只在程式碼裡抓便宜就抓得到的事，兩者都不會多開一輪，也不註冊工具。

| Extension | 作用 | 章節 |
| --- | --- | --- |
| `pi/close-guard.ts` | 一次執行停下時，若檔案改過之後 anchor 沒有通過的執行，就加上一行提醒。 | [收尾守門](#the-close-guard) |
| `pi/validate-tool-use.ts` | 每次編輯後驗證 skill、指令檔與 spec。 | [驗證器](#validators) |

## 收尾守門

值得用程式碼檢查的主張只有一個，就是一次執行最後的那句話：它指定的檢查，在它留下的這棵樹上通過了。
執行停下時，`pi/close-guard.ts` 讀 session 的 branch；若 anchor 最後一次通過之後還有檔案被改，就在 session 加上一行簡短提醒。
這一行會顯示在對話紀錄裡，並隨下一個提示送到模型；它不會開啟新的一輪。

<details>
<summary>什麼算 anchor、什麼算變更、什麼算通過的執行</summary>

anchor 是 agent 最後寫下的 `Anchor: <check>` 行（`Reality anchor:` 和粗體標記也算），或 `todo` 呼叫最後指定的 anchor，以較晚的為準。守衛先讀呼叫本身，再依序讀每個 `tasks[]` 項目；每次從 `anchor`、`metadata.anchor` 依序取第一個非空白字串。
那一行裡每個反引號包住的指令都是一項檢查；沒有反引號的任務 anchor 整個視為一條指令。
沒有指令的 anchor，例如 reviewer 的判定或某個人的驗收，不在判斷範圍內。

變更是成功的 `write` 或 `edit`。
一次檢查的執行，是指令內容包含該檢查文字的 `bash` 呼叫（連續空白視為一個），所以 `uv run pytest -q tests/` 也算 `pytest -q` 的執行。
結束代碼為 0 的執行才算通過。

檔案改過，而且沒有宣告 anchor，或某項檢查最近一次執行早於最後一次變更或失敗時，守門才會出聲。
那一行會列出還缺的檢查，例如：

```text
anchorloop: no passing run of `pytest -q` after the last change.
```

每次變更只提醒一次：之後沒有新變更的停下不再加任何東西，下一次變更才會重新啟動它。
一切都從 branch 讀出，所以恢復或重新載入的 session 讀到的是同樣的狀態。

</details>

## 驗證器

skill 與指令檔常有小地方偏掉，寫下的當下最容易便宜地抓到。

<details>
<summary>驗證什麼，規則放在哪裡</summary>

每次 `write` 或 `edit` 後，`pi/validate-tool-use.ts` 在行程內驗證該檔（`pi/support/validators.ts`，移植自 `hooks/validators/`）。
它替 `SKILL.md`（每次編輯最多三則紅線提醒）、指令檔（`AGENTS.md`、`CLAUDE.md`、`GEMINI.md`、`rules/`）和 `docs/specs/` 產出物附上建議。
不需要 Python。
`hooks/` 的 Python 驗證器仍供 `validate_all.py` 和對照測試使用。

</details>
