---
title: 開發
description: 驗證 skill、跑測試、編輯文件，以及發版前的檢查。
---

這個 repo 就是 `pi-anchorloop` 套件：`skills/` 裡的工作流程 skill，與 `pi/` 裡的 pi extension。

## 檢查

```bash
uv run python hooks/validate_all.py .   # 檢查 skill、規則與 durable spec
uv run --with pytest pytest -q          # 驗證器與 pi extension 的測試（需要 node）
```

宣告一項改動已驗證之前，兩個都要跑；`tests/test_pi_extension.py` 會用 Node 載入 pi extension。

## 文件

- `README.md` 與 `README.zh-TW.md` 保持簡短：一句話介紹、skill 樹、安裝、快速開始，以及每個 extension 一行的表。
- 這個網站才是參考文件。`site/` 是 Starlight 專案，由 `.github/workflows/pages.yml` 發佈到 https://wayne930242.github.io/anchorloop/。
- `docs/how-it-works.md` 是擴充功能參考的來源；`site/scripts/sync.mjs` 依 H2 把它拆成「擴充功能」底下的各頁，所以它的標題要保持穩定。
- `docs/how-it-works.zh-TW.md` 逐行對照它，第一行寫明對應的英文 commit。
- `cd site && npm ci && npm run check && npm run build` 檢查對照譯文、手寫頁面的 zh-TW 對照頁，以及每個站內連結與錨點。

<details>
<summary>發版</summary>

- 套件能力、工作流程契約或設定有變時，`package.json` 與 `pyproject.toml` 的版本一起升。只改文件不需要升版。
- 推 `v*` tag 之前，在要打 tag 那個 commit 的乾淨 detached worktree 裡跑上面兩項檢查（`git worktree add --detach <dir> <sha>`，用完移除）：工作樹裡有 git 之外的檔案，會讓 `validate_all.py` 在發佈 workflow 失敗的地方通過。
- `Publish` workflow 在 tag 上跑這兩項檢查，並發佈到 npm，除非該版本已經在那裡。

</details>
