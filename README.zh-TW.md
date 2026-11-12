# pi-anchorloop

[English](README.md)

**給 [pi](https://github.com/earendil-works/pi) 用的 agent 工作流程 skill 和循環 extension：每一種任務都從自己的 skill 進來，選一本 playbook，然後跑同一個循環，Align → Anchor → Act → Verify。**

**[文件](https://wayne930242.github.io/anchorloop/zh-tw/)** 有繁體中文與 [English](https://wayne930242.github.io/anchorloop/) 兩種版本：概念、skill、合併列車，以及每項擴充功能的行為，也講[搭配 pi-straw-boss 使用](https://wayne930242.github.io/anchorloop/zh-tw/guide/with-straw-boss/)。

## 為什麼

- **第一筆修改前先有 anchor。** 每個任務指名會觀察結果的那道檢查，再小步修改，並回報檢查看到了什麼。
- **讀證據的 book。** loop 走到哪個階段，來自修改、檢查結果、review 與併入，而不是 agent 的說法。
- **Friction 變成規則。** 誤導過一次執行的指令會被記錄，並由 `solid-loop` 從根源修正。

## Skill

```text
anchorloop            核心循環 · 原則 · playbook：autonomous-run、pause、pickup
├─ answering        explain · compare
├─ investigating    research · diagnose
├─ inspecting       diff-review · qa-release
├─ coding           bug-fix · feature · refactoring · perf · prototype · state-model（+ Mini SDD）
├─ integrating      receive-car · train · urgent-car（+ seams）
├─ deploying        deploy · rollback
├─ writing          draft · tighten · comments · pr-description
├─ visual-designing compare · refine · motion（+ canvases、量測腳本）
└─ solid-loop       apply-friction · author-skill · bootstrap
共用                grilling · domain-modeling · human-feedback (uat) · agent-terse
```

## Extension

| 檔案 | 作用 |
| --- | --- |
| `pi/book.ts` | Loop book：開啟 loop、讀證據、算階段、顯示狀態 widget、追蹤 unit 與併入、接手交接的 book。 |
| `pi/anchor-gate.ts` | 前面的階段還沒完成就用編輯開始 act 階段時，警告一次。 |
| `pi/decision-tool.ts` | `anchorloop_decision` 工具：給使用者事後複查的執行寫 TSV 決策軌跡。 |
| `pi/second-thought.ts` | 一次執行結束時，請 Jev 複核階段機的判讀；只是提醒。 |
| `pi/validate-tool-use.ts` | 每次編輯後驗證 skill、指令檔與 spec。 |
| `pi/ttsr.ts` | Time Traveling Stream Rules：agent 自己的輸出命中規則時，規則就觸發。 |

## 安裝

```bash
pi install npm:pi-anchorloop
pi install npm:pi-better-show   # 選用：human-feedback 與 visual-designing 的複查頁
```

## 快速開始

1. 交給 pi 一個任務；它會選描述相符的入口 skill。
2. 讀開頭的 `Alignment:` 那一行，誤讀就立刻指正。
3. 第一個 `todo` 會開啟 loop；編輯器下方的 widget 顯示它的階段，`anchorloop_stage read` 顯示完整內容。
4. 讀回覆：它附上 anchor 觀察到的結果，沒被檢查涵蓋的部分標為 `unknown`。

## 開發

```bash
uv run python hooks/validate_all.py .   # 檢查 skill、規則與 durable spec
uv run --with pytest pytest -q          # 驗證器與 pi extension 的測試（需要 node）
cd site && npm ci && npm run check && npm run build   # 文件網站
```

## 致謝

- Lauren Tan 的 [pstack](https://github.com/backnotprop/pstack)（MIT），鏡像 repo 的版本 `e44668c`，上游是 [cursor/plugins](https://github.com/cursor/plugins/tree/main/pstack)（2.8.0 的工程標準補充取自 cursor/plugins `c742dd6`）；以及 Michael Denyer 的移植版 [pstack-claude](https://github.com/michael-denyer/pstack-claude)（MIT）：依任務類型分的 playbook、具名原則、生命週期 playbook、決策軌跡、獨立審查前不放行的關卡、交接給新 subagent，以及證據分級；`state-model` playbook 改寫自 `statechart` skill（cursor/plugins `a5539b15`）。
- [google-research/harness2](https://github.com/google-research/harness2)（Apache-2.0），版本 `1cfe254`：solid-loop 的放置判斷、最便宜機制的順序，以及沒有前後對照就不寫成教訓。
- [mattpocock/skills](https://github.com/mattpocock/skills)（MIT）：grilling、domain-modeling、diff review、prototype playbook，以及 feature playbook 的介面檢查。
- [JuliusBrussee/caveman](https://github.com/JuliusBrussee/caveman)（Apache-2.0），revision `bad48a0`：`agent-terse` 的精簡寫法。
- HumanLayer 的 [show-me](https://github.com/humanlayer/skills/tree/main/plugins/show-me)（MIT）：`answering` 的呈現方式。
- [oh-my-pi](https://github.com/can1357/oh-my-pi)：Time Traveling Stream Rules。

移植來的檔案在各自的頁尾註明出處。
