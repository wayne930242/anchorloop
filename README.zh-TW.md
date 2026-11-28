# pi-anchorloop

[English](README.md)

**給 [pi](https://github.com/earendil-works/pi) 用的 agent 工作流程 skill：每一種任務都從自己的 skill 進來，選一本 playbook，然後跑同一個簡短的循環：先講好檢查，再改，最後拿出通過的結果。**

**[文件](https://wayne930242.github.io/anchorloop/zh-tw/)** 有繁體中文與 [English](https://wayne930242.github.io/anchorloop/) 兩種版本：概念、skill、合併列車，以及每項擴充功能的行為，也講[搭配 pi-straw-boss 使用](https://wayne930242.github.io/anchorloop/zh-tw/guide/with-straw-boss/)。

## 為什麼

- **第一筆修改前先有 anchor。** 每個任務在第一次編輯前寫下 `Anchor: <check>`，最後一次變更之後拿出這道檢查通過的執行。
- **換一個模型的 reviewer。** 授權、migration、共用契約、資安，或兩個以上 worker，都會加一位不同模型家族的新 reviewer；P0 與 P1 擋住合併。
- **不收回合稅。** 沒有階段機、沒有 stage 工具、也沒有多開一輪的提醒：執行停下卻沒有通過的 anchor 執行時，收尾守門只加一行。

## 評估結果

在篩選後的 16 題 SWE-Bench Pro 任務中，代理在修改前定好檢查，並在最後一次修改後提出檢查通過的證據，兩個條件都達成的比例是 42%（使用 anchorloop）對 6%（未使用；差距 +35 個百分點，95% 信賴區間：+15 到 +56）。
任務通過率是 46% 對 29%（差距 +17 個百分點；95% 信賴區間：−4 到 +38），還不能判定通過率有所提高。
這次只用了一個模型，題目少且經過篩選。

[完整評估報告](docs/evals/2026-11-28-swepro-pro-16.zh-TW.md)

## Skill

```text
anchorloop            循環卡 · playbook：autonomous-run、pause、pickup
├─ answering        explain · compare
├─ investigating    research · diagnose
├─ inspecting       diff-review · qa-release
├─ coding           bug-fix · feature · refactoring · perf · prototype · registered-flow · state-model（+ Mini SDD）
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
| `pi/close-guard.ts` | 執行停下時，若檔案改過之後 anchor 沒有通過的執行，就加上一行提醒；不會開啟新的一輪。 |
| `pi/validate-tool-use.ts` | 每次編輯後驗證 skill、指令檔與 spec。 |

3.0.0 移除了 loop book、anchor gate、decision 工具、second thought 與串流規則；[docs/migration-3.0.md](docs/migration-3.0.md) 列出要改的地方。

## 安裝

```bash
pi install npm:pi-anchorloop
pi install npm:pi-better-show   # 選用：human-feedback 與 visual-designing 的複查頁
```

## 快速開始

1. 交給 pi 一個任務；它會選描述相符的入口 skill。
2. 讀開頭重述目標的那一行，誤讀就立刻指正。
3. 讀 `Anchor:` 那一行：會觀察結果的那道確切檢查。
4. 讀回覆：它附上最後一次變更之後 anchor 通過的執行，沒被檢查涵蓋的部分標為 `unknown`。

## 開發

```bash
uv run python hooks/validate_all.py .   # 檢查 skill、規則與 durable spec
uv run --with pytest pytest -q          # 驗證器與 pi extension 的測試（需要 node）
cd site && npm ci && npm run check && npm run build   # 文件網站
```

## 致謝

- Lauren Tan 的 [pstack](https://github.com/backnotprop/pstack)（MIT），鏡像 repo 的版本 `e44668c`，上游是 [cursor/plugins](https://github.com/cursor/plugins/tree/main/pstack)（2.8.0 的工程標準補充取自 cursor/plugins `c742dd6`）；以及 Michael Denyer 的移植版 [pstack-claude](https://github.com/michael-denyer/pstack-claude)（MIT）：依任務類型分的 playbook、生命週期 playbook、獨立審查前不放行的關卡、交接給新 subagent，以及證據分級；`state-model` playbook 改寫自 `statechart` skill（cursor/plugins `a5539b15`）。
- [google-research/harness2](https://github.com/google-research/harness2)（Apache-2.0），版本 `1cfe254`：solid-loop 的放置判斷、最便宜機制的順序，以及沒有前後對照就不寫成教訓。
- [mattpocock/skills](https://github.com/mattpocock/skills)（MIT）：grilling、domain-modeling、diff review、prototype playbook，以及 feature playbook 的介面檢查。
- [JuliusBrussee/caveman](https://github.com/JuliusBrussee/caveman)（Apache-2.0），revision `bad48a0`：`agent-terse` 的精簡寫法。
- HumanLayer 的 [show-me](https://github.com/humanlayer/skills/tree/main/plugins/show-me)（MIT）：`answering` 的呈現方式。

移植來的檔案在各自的頁尾註明出處。
