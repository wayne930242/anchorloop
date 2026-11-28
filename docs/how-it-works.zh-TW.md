# anchorloop 擴充功能的運作方式 <!-- source: docs/how-it-works.md @ 9f2bee0 -->

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

anchor 是 brief（也就是第一則使用者訊息）或 agent 文字裡最後一行標示檢查的行（`Anchor:`、`Reality anchor:`、`Gate:`、`Gates:`、`Check:`、`Checks:`、`Verify:`、`Verification:`、`Done when:`、`檢查：`、`驗證：`、`驗收：`；粗體、清單與標題標記也算；`Anchor:` 以外的標示，要那一行含反引號指令才算），或 `todo` 呼叫最後指定的 anchor，以較晚的為準。守衛先讀呼叫本身，再依序讀每個 `tasks[]` 項目；每次從 `anchor`、`metadata.anchor` 依序取第一個非空白字串，都沒有時改取 straw-boss 檢查規格的 `metadata.sb.spec.check.run`。
那一行裡每個反引號包住的指令都是一項檢查；沒有反引號的任務 anchor 整個視為一條指令。
沒有指令的 anchor，例如 reviewer 的判定或某個人的驗收，不在判斷範圍內。

變更是成功的 `write` 或 `edit`；程式變更之後寫的文字檔（`.md`、`.txt`、`.rst`）不會移動最後一次變更，所以檢查之後才寫的報告或 changelog 不會讓檢查失效。
一次檢查的執行，是指令內容包含該檢查文字的 `bash` 呼叫，或以 `MonitorCreate` 啟動、結果已送回的 monitor（連續空白視為一個），所以 `uv run pytest -q tests/` 也算 `pytest -q` 的執行。
結束代碼為 0 的執行才算通過；最後一次變更之後，以 `todo` 呼叫記下的通過 `evidence`，算作其 `command` 所含的每項檢查各通過一次，直到該檢查之後再次執行取而代之。

檔案改過，而且沒有宣告 anchor、之後也沒記下通過的 evidence，或某項檢查最近一次執行早於最後一次變更或失敗時，守門才會出聲。
那一行會列出還缺的檢查，例如：

```text
anchorloop: no passing run of `pytest -q` after the last change.
```

還缺的檢查提醒一次後，守門就保持安靜，直到 todo 清單有變動：只是再改檔案不會讓提醒回來，更新 todo（例如把任務標為完成）才會。
anchor 所屬的 todo 在等待時，守門也不提醒，也就是該 todo 尚未完成，且設了 `metadata.waitsOn`，或 `metadata.until` 的時間還沒到（即 pi-todo-ledger 的 `waitsOn`、`until` 欄位）；在文字裡宣告的 anchor，則在每個進行中的 todo 都在等待時不提醒。

若已安裝 pi-todo-ledger，守門也會在任務的 anchor 通過後指出任務編號，請 agent 用 `todo update` 補記尚未登錄的執行：每次執行各佔一筆 `evidence`，填入 `command`、`result: "pass"`，若知道當時的版本則一併填入 `sha`。
守門從成功的工具呼叫和 branch 上的 `todo/v1` 快照辨認任務；檢查是否通過，看的是 bash 執行結果，不是帳本。
要收到這項提醒，每個檢查都須在最後一次編輯後按原指令執行並通過（前面可加簡單的 `cd dir &&` 或 `uv run`）；只印出指令或掩蓋失敗的呼叫不能當作證據。
同一次執行只提醒一次，agent 在下次收到提示時才會看到；帳本仍由 agent 寫入。
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
